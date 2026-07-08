# Document QA Bot 升级日志

> 记录每次优化改进的核心内容，便于后期复盘整个项目的演进过程。

---

## 2026-07-08 · Qdrant 向量外置（可选，BM25 仍本地）

### 背景

文档规模增大后，本地 `default__vector_store.json`（向量）会占用大量内存。外置向量到 Qdrant，**docstore 仍保留在 `storage/`** 供 BM25 使用。

### 架构

```
入库: chunk → embedding → Qdrant（向量）
              └→ storage/docstore.json（文本，BM25 用；store_nodes_override=True）
问答: Hybrid 检索不变 → Rerank → LLM（仍只 Top-5 chunk）
```

**可直接从空库用 Qdrant 模式**：上传 → 建库 → 问答，无需先 local 再迁移。

### 配置（`.env`）

```env
VECTOR_BACKEND=qdrant
QDRANT_URL=http://localhost:6333
QDRANT_COLLECTION=docbot_chunks
```

默认 `VECTOR_BACKEND=local`，**不装 Qdrant 也能正常运行**。

### 安装 Qdrant（不麻烦）

**方式 1：Docker（推荐，一条命令）**

```bash
docker compose --profile qdrant up -d
```

**方式 2：Windows 二进制（无 Docker）**

1. 打开 [Qdrant Releases](https://github.com/qdrant/qdrant/releases)，下载 Windows 版 zip  
2. 解压后运行 `qdrant.exe`（默认监听 `http://localhost:6333`）  
3. 浏览器访问 `http://localhost:6333/dashboard` 可查看管理界面

### 从本地索引迁移

```bash
docker compose --profile qdrant up -d
# .env 先保持 VECTOR_BACKEND=local
python scripts/migrate_to_qdrant.py
# 完成后 .env 改为 VECTOR_BACKEND=qdrant，重启应用
```

### 使用注意

- **清除索引**：仅删除 `storage/` + Qdrant collection，**不再删除** `uploads/` 原始文件
- 清除后首次上传：自动创建新 docstore（无需手动建 `docstore.json`）
- 若上传报「0 字节」或「不是 PDF」：删除 `uploads/` 中损坏文件后，从原始来源重新选择上传

---

## 2026-07-08 · PDF 解析优化（pdfplumber + 质检 + LlamaParse fallback）

### 背景

未配置 `LLAMA_API_KEY` 时，所有格式统一走 LlamaParse，导致 PDF 入库乱码（如高教社杯通知），检索命中但无法作答。

### 方案

```
PDF → pdfplumber（正文 + 表格 Markdown）
    → parse_quality 质检（CJK 占比、乱码符号）
    → 不合格且已配置 LLAMA_API_KEY → LlamaParse fallback
非 PDF → 有 Key 用 LlamaParse，否则 LlamaIndex 默认解析器
```

### 新增文件

| 文件 | 说明 |
|------|------|
| `app/ingestion/pdf_parser.py` | pdfplumber 正文/表格抽取 |
| `app/ingestion/parse_quality.py` | 解析质量启发式检测 |
| `app/ingestion/pdf_reader.py` | `HybridPdfReader`（LlamaIndex BaseReader） |

### 使用注意

- **已有乱码索引需重建**：加载索引后，对问题 PDF 勾选「更新已有文件」重新上传
- `LLAMA_API_KEY` 仍为可选，仅作 PDF 质检失败时的 fallback
- **fallback 仅在质量更优时采用**：避免「pdfplumber 为空 → 误用 LlamaParse 乱码」
- **扫描件/图片型 PDF**（如 `19_高教社杯...pdf`）会拒绝入库并提示需 OCR；21 份样本中 20 份 pdfplumber 直接通过

---

## 2026-07-06 · Phase 4（Week 4 · 阶段 B）：Docker 化

### 目标

一条命令拉起完整运行环境，模型与索引数据通过 volume 挂载，镜像内不包含大体积 `models/`。

### 新增文件

| 文件 | 说明 |
|------|------|
| `Dockerfile` | Python 3.10-slim，安装依赖，entrypoint 启动 |
| `docker-compose.yml` | `api` 服务（默认）+ `gradio`（`--profile ui`） |
| `.dockerignore` | 排除 venv、models、storage、uploads 等 |
| `scripts/entrypoint.sh` | `APP_MODE=api\|gradio` 分发启动 |
| `.env.example` | 环境变量模板 |

### 架构

```
docker compose up
    └── docbot-api (:8000)
            ├── volume: ./models   → /app/models
            ├── volume: ./storage  → /app/storage
            ├── volume: ./uploads  → /app/uploads
            └── env: .env (DEEPSEEK_API_KEY)

docker compose --profile ui up   # 可选 Gradio
    └── docbot-gradio (:7860)
```

### 启动方式

```bash
# 1. 准备环境变量（若尚无 .env）
cp .env.example .env   # 填写 DEEPSEEK_API_KEY

# 2. 确保本地 models/ 已有 embedding / rerank 模型

# 3. 启动 API（默认）
docker compose up -d --build

# 4. 可选：同时启动 Gradio UI
docker compose --profile ui up -d --build

# 5. 验证
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/api/v1/status
# Swagger: http://127.0.0.1:8000/docs
# Gradio:  http://127.0.0.1:7860
```

国内构建加速（可选）：

```bash
PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple docker compose up -d --build
```

### 代码小改

| 文件 | 改动 |
|------|------|
| `main.py` | `GRADIO_HOST` / `GRADIO_PORT` 环境变量，Docker 内绑定 `0.0.0.0` |

RAG 核心、API 路由 **无改动**。

### 实施状态（阶段 B）

- [x] Dockerfile + compose + entrypoint
- [x] models / storage / uploads volume 挂载
- [x] API 健康检查
- [x] Gradio 可选 profile
- [ ] 阶段 C：生产部署文档（Nginx、资源限制等）

---

## 2026-07-06 · Phase 4（Week 4 · 阶段 A）：FastAPI 服务层

### 背景

Week 1–3 完成 RAG 流水线、Router/引用/拒答与 RAGAS 评估。Week 4 阶段 A 在 **不改动 RAG 核心** 的前提下，增加 HTTP API，与 Gradio 共用 `qa_service`，便于集成、答辩演示与后续 Docker 化。

### 架构

```
app/services/qa_service.py   ← answer_question() 结构化结果
    ├── main.py              ← Gradio UI :7860
    └── app/api/main.py      ← FastAPI :8000
```

### 已实现接口

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/health` | 存活检查 |
| `GET` | `/api/v1/status` | 索引/模型/文档状态 |
| `POST` | `/api/v1/chat` | 问答（answer + citations + route + retrieval_debug） |
| `POST` | `/api/v1/index/upload` | 上传文件并建/增量索引 |
| `POST` | `/api/v1/index/load` | 从 storage 加载索引 |
| `POST` | `/api/v1/index/save` | 持久化索引 |
| `GET` | `/api/v1/index/documents` | 已索引文件列表 |
| `DELETE` | `/api/v1/index` | 清空 storage + uploads |
| `POST` | `/api/v1/index/reset-cache` | 仅清内存缓存 |
| `GET` | `/api/v1/index/debug` | 索引调试信息 |
| `GET` | `/api/v1/index/debug/updates` | 文件更新调试 |
| `GET` | `/api/v1/config/models` | 可选 embed/llm 列表 |
| `PUT` | `/api/v1/config/embed-model` | 切换 Embedding |
| `PUT` | `/api/v1/config/llm-model` | 切换 LLM |

### 启动方式

```bash
.\venv\Scripts\activate   # Windows
python api_server.py
# Swagger: http://127.0.0.1:8000/docs
```

启动时自动：`warmup_models()` + 尝试 `load_existing_index()`（与 Gradio 一致）。

### 冒烟测试（2026-07-06 已通过）

| 接口 | 结果 |
|------|------|
| `GET /health` | 200 |
| `GET /api/v1/status` | index_loaded=true, 2 文档 |
| `GET /api/v1/config/models` | embed/llm 列表正常 |
| `GET /api/v1/index/documents` | 2 条记录 |
| `POST /api/v1/chat` | ~30s，含 answer + 5 citations + route |

### 示例

```bash
# 状态
curl http://127.0.0.1:8000/api/v1/status

# 问答（需已加载索引）
curl -X POST http://127.0.0.1:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d "{\"question\": \"3D编程模型创新设计专项赛报名时间是什么时候？\"}"

# 加载已有索引
curl -X POST http://127.0.0.1:8000/api/v1/index/load
```

### 新增文件

| 文件 | 说明 |
|------|------|
| `app/api/main.py` | FastAPI 应用工厂 |
| `app/api/schemas.py` | Pydantic 模型 |
| `app/api/routes/*.py` | 路由 |
| `api_server.py` | uvicorn 入口 |

### 实施状态（阶段 A）

- [x] `answer_question()` 结构化输出
- [x] 健康 / 状态 / 问答 / 索引 / 配置 API
- [x] 启动时 warmup + 自动加载索引
- [x] 本地冒烟测试通过
- [x] 阶段 B：Docker / docker-compose
- [ ] 阶段 C：部署文档完善

---

## 2026-07-06 · Phase 3（Week 3）：RAGAS 评估 + Week 1/2 量化对比

### 背景

Week 1、Week 2 已完成人工判分（`eval/week1_results.json`、`week2_results.json`），需要 **自动化指标** 验证 Week 2 是否在 Faithfulness 等方面真正提升。

### 核心产出

| 产出 | 路径 | 说明 |
|------|------|------|
| RAGAS 脚本 | `eval/run_ragas.py` | 加载索引 → 检索 context → 对历史回答跑 RAGAS |
| Week 1 指标 | `eval/week3_ragas/week1_ragas.json` | 5 题 per-question + 平均 |
| Week 2 指标 | `eval/week3_ragas/week2_ragas.json` | 同上 |
| 对比报告 | `eval/week3_ragas/comparison.md` | 总体 + 逐题表格 |

### 运行方式

```bash
# 需 .env 中 DEEPSEEK_API_KEY，且 storage/ 已有索引
python eval/run_ragas.py
```

评估时 **重新检索 context**（与当前 Hybrid+Rerank 配置一致），Week 1/Week 2 共用同一批 context；差异仅来自 `actual_answer`。

### RAGAS 总体结果（2026-07-06，5 题平均）

| 指标 | Week 1 | Week 2 | 变化 | 解读 |
|------|--------|--------|------|------|
| **faithfulness** | 0.732 | **0.865** | +0.133 | Week 2 回答更贴合检索 context，幻觉更少 |
| **answer_relevancy** | 0.492 | **0.527** | +0.035 | 与问题相关度略升 |
| **context_precision** | 0.467 | 0.467 | 0 | 检索质量相同（同一 pipeline） |

### 逐题亮点

| ID | faithfulness W1→W2 | 人工 W1→W2 | 说明 |
|----|-------------------|-------------|------|
| Q001 | 1.0 → 1.0 | 部分→部分 | faithfulness 高但人工仍漏「决赛线上」— 指标与业务口径不完全一致 |
| Q002 | 0.71 → 0.48 | 部分→部分 | W2 分口径更好，但出现文件数幻觉，faithfulness 反降 |
| Q005 | **0.25 → 1.0** | 通过→部分 | W2 对 3D 部分更忠实，但漏答未来校园，人工退步 |

### 结论

- Week 2 在 **faithfulness（+13%）** 上整体优于 Week 1，Router + 引用策略有效。
- **context_precision 不变** — 检索层未改，提升空间在 Rerank Top-N / query 扩展。
- RAGAS 与人工判分可能不一致（如 Q001），评估时需 **RAGAS + 人工 + 引用面板** 三者对照。

### 实施状态

- [x] `eval/run_ragas.py`（Faithfulness / Context Precision / Answer Relevancy）
- [x] `eval/week3_ragas/` 结果与 `comparison.md`
- [x] README / HELP 对比表
- [ ] result_2/3 附件对比实验（可选，竞赛提交用）

---

## 2026-07-06 · Phase 2（Week 2）：LLM Router + 引用溯源 + 拒答

### 背景

Week 1 完成 Hybrid + Rerank 检索后，仍有三类体验问题：

1. **关键词路由** — 「一共有几个」一律走统计 handler，模糊问题答非所问
2. **无引用溯源** — 用户看不到检索到了哪些片段，无法判断是检索还是生成的问题
3. **拒答不当** — 该归纳时不归纳（如「线上举办」），该分口径时不分口径（如统计题）

### 核心改进

| 能力 | 实现 | 效果 |
|------|------|------|
| **LLM Router** | `routing/llm_router.py` 调用 DeepSeek 输出 JSON 路由 | 识别问题类型、歧义、知识库范围；失败回退关键词 |
| **引用溯源** | `generation/citations.py` + 回答末尾引用附录 | 回答标注 [1][2]，UI 展示最近检索片段 |
| **拒答机制** | `generation/refusal.py` | Router 判定 out_of_scope、空检索时结构化拒答 |
| **生成策略** | `query_handlers.dispatch_answer` | 基础题允许合理归纳；统计题先澄清口径再作答 |

### 问答流水线（Week 2）

```
用户提问
  → LLM Router（类型 / 歧义 / 范围）
  → Hybrid 召回 + Rerank
  → 拒答检查（out_of_scope / 空检索）
  → dispatch_answer（basic / statistical / open）
  → 回答 + 引用附录
  → UI 检索溯源面板更新
```

### 配置项（`app/config.py`）

| 开关 | 默认 | 说明 |
|------|------|------|
| `ENABLE_LLM_ROUTER` | `True` | 使用 LLM 路由；`False` 回退关键词 |
| `ROUTER_FALLBACK_TO_KEYWORDS` | `True` | LLM 路由失败时回退 |
| `SHOW_CITATIONS` | `True` | 回答末尾附加引用来源 |
| `REFUSAL_MIN_TOP_SCORE` | `0.0` | 0=关闭分数拒答 |

### 新增 / 修改文件

| 文件 | 说明 |
|------|------|
| `app/routing/llm_router.py` | LLM 路由器 |
| `app/routing/models.py` | `RouteResult` 数据模型 |
| `app/generation/citations.py` | 引用格式化 |
| `app/generation/refusal.py` | 拒答逻辑 |
| `app/generation/query_handlers.py` | Week 2 提示词 + `dispatch_answer` |
| `app/services/qa_service.py` | 编排 Router / 拒答 / 引用 |
| `app/ui/gradio_app.py` | 自定义 Chat + 检索溯源面板 |

### 预期改善（对照 eval 集）

| ID | 问题 | Week 1 | Week 2 目标 |
|----|------|--------|-------------|
| Q001 | 在哪举办 | 部分通过 | 归纳「全程线上、无线下城市」 |
| Q002 | 一共几个比赛 | 部分通过 | 分口径作答 / 拒答全赛总数 |
| Q003~Q005 | 流程/时间/资格 | 通过 | 保持 + 引用溯源 |

### 使用注意

- Router 每次提问增加约 **1 次 DeepSeek 调用**（~1–3s）
- 控制台会打印 `[Router] type=... scope=...`
- 提问后可在「引用溯源 / 检索片段」面板查看 Top 片段
- Week 3 用 `eval/week2_results.json` 记录对比结果

### 实施状态

- [x] LLM Router + 关键词回退
- [x] 引用溯源（回答附录 + UI 面板）
- [x] 结构化拒答（out_of_scope / 空检索）
- [x] 统计/基础题提示词优化（歧义口径）
- [x] 用 eval 集跑 Week 2 对比并写入 `week2_results.json`

---

## 2026-07-06 · Phase 1.1：推理性能优化（单例 + 预加载 + 检索器缓存）

### 背景

Phase 1 引入 Hybrid + Rerank 后，虽然模型均在本地，但每次提问仍要 **重新加载 Embedding**、**重建 BM25/Hybrid 检索器**，导致首个及后续问题等待时间长达 30~60 秒。

### 核心改进

| 优化 | 实现 | 效果 |
|------|------|------|
| **Embedding 单例** | `embedder.py` 按模型名缓存实例 | 同一 Embedding 只加载一次 |
| **启动预加载** | `main.py` → `bootstrap/warmup.py` | 启动时加载 Embedding + Rerank，首个问题不再冷启动 |
| **Hybrid 检索器缓存** | `retriever_cache.py` 按 `(index_id, embed_model, node_count)` 缓存 | 索引不变时复用 BM25 + 向量检索器 |

### 缓存失效时机

索引或 Embedding 变更时自动 `invalidate_hybrid_retriever_cache()`：

- 上传/重建索引（`index_builder.py`）
- 加载已有索引（`index_manager.py`）
- 清除/重置存储
- UI 切换 Embedding 模型

### 新增 / 修改文件

| 文件 | 说明 |
|------|------|
| `app/retrieval/embedder.py` | Embedding 单例缓存 |
| `app/retrieval/retriever_cache.py` | Hybrid 检索器缓存 |
| `app/bootstrap/warmup.py` | 启动预加载 |
| `main.py` | 启动时调用 warmup，移除启动时 DeepSeek 测试请求 |

### 预期体验变化

| 场景 | 优化前 | 优化后（约） |
|------|--------|-------------|
| `python main.py` 启动 | 几秒 | +20~40s（预加载，仅首次） |
| 第一个问题 | 30~60s | 10~20s |
| 后续问题（索引不变） | 20~40s | 8~15s |

### 使用注意

- 启动时会打印 `[Warmup] 预加载 Embedding/Rerank`，属正常现象
- 切换 Embedding 模型或更新索引后，首次提问会重建 Hybrid 检索器（仅一次）
- Rerank 在 CPU 上仍有数秒开销；要进一步加速可设 `ENABLE_RERANK = False` 或使用 GPU

---

## 2026-07-06 · Phase 1：高级检索流水线（语义切块 + Hybrid Search + Rerank）

### 背景

原系统使用 `VectorStoreIndex.from_documents()` 默认固定长度切块，查询时仅做单向量 Top-5 检索。对竞赛规程类文档（结构化 PDF、精确字段查询）召回不稳定，容易出现「答案被切断」「专有名词匹配不到」等问题。

### 核心改进

| 层级 | 改进 | 作用 |
|------|------|------|
| **摄入（Ingestion）** | Markdown 结构切分 + 语义二次切分 + Contextual Header | 按标题保留「报名时间 / 组织单位」等完整语义块；chunk 前缀附带文档名/章节，提升检索命中率 |
| **检索（Retrieval）** | BM25 + 向量 Hybrid Search，RRF 融合 | 同时覆盖语义相似与关键词精确匹配（赛项全名、日期、URL） |
| **重排（Rerank）** | BGE Cross-Encoder（`bge-reranker-v2-m3`） | 从 30 个候选 chunk 中精排 Top-5，减少噪声片段进入 LLM |
| **编排（Service）** | `qa_service` 改用显式检索流水线 | 与 `as_query_engine` 解耦，控制台输出召回片段便于调试 |

### 检索链路（改后）

```
用户问题
  → Hybrid 召回（Vector Top-20 + BM25 Top-20 → RRF 融合 Top-30）
  → Rerank（Cross-Encoder → Top-5）
  → 问题分类 → DeepSeek 生成回答
```

### 切块链路（改后）

```
LlamaParse 解析 PDF
  → MarkdownNodeParser（按 # / ## 标题切分）
  → 超长 section（>800 字）→ SemanticSplitterNodeParser（语义断点切分）
  → 添加 【文档:xxx】【章节:xxx】 前缀
  → Embedding → VectorStoreIndex
```

### 新增 / 修改文件

| 文件 | 说明 |
|------|------|
| `app/ingestion/chunker.py` | 语义/结构切块 |
| `app/retrieval/hybrid_retriever.py` | BM25 + 向量混合检索 |
| `app/retrieval/reranker.py` | Cross-Encoder 重排 |
| `app/retrieval/model_loader.py` | ModelScope 国内模型下载 |
| `app/retrieval/pipeline.py` | 检索流水线编排 |
| `download_rerank_model.py` | 预下载 Rerank 模型脚本 |
| `app/config.py` | 新增切块/检索/重排配置项 |
| `app/ingestion/index_builder.py` | 建索引改用 `build_nodes()` |
| `app/services/qa_service.py` | 问答改用 `retrieve_context()` |
| `requirements.txt` | 新增 `llama-index-retrievers-bm25`、`sentence-transformers` |

### 配置开关（`app/config.py`）

```python
USE_SEMANTIC_CHUNKING = True       # 语义/结构切块
ENABLE_HYBRID_SEARCH = True        # Hybrid 检索
ENABLE_RERANK = True               # Cross-Encoder 重排
HYBRID_VECTOR_TOP_K = 20
HYBRID_BM25_TOP_K = 20
RERANK_TOP_N = 5
RERANK_CANDIDATE_TOP_K = 30
RERANK_MODEL = "BAAI/bge-reranker-v2-m3"
```

设为 `False` 可逐项回退到旧行为，便于 A/B 对比。

### 使用注意

1. **必须重建索引**：切块策略变更后，旧 `storage/` 索引不兼容，需清除存储后重新上传文档。
2. **首次 Rerank 会下载模型**：`bge-reranker-v2-m3` 缓存至 `models/bge-reranker-v2-m3/`；国内环境通过 **ModelScope 魔塔** 下载，无需访问 HuggingFace。
3. **推荐 Embedding 模型**：中文赛题文档建议使用 `BAAI/bge-large-zh-v1.5`。
4. **统计类问题**：Hybrid + Rerank 对「有多少个竞赛」类问题改善有限，后续可考虑 Structured RAG / Map-Reduce。

### 依赖安装

> **版本注意**：`llama-index-retrievers-bm25` 必须锁定 `0.4.0`，与 `llama-index==0.11.17` 配套；安装 `0.6.x` 会导致 core 版本冲突。

```bash
# 清华镜像（推荐）
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 阿里镜像（备选）
pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/
```

### 常见问题：Gradio 启动报 localhost 不可访问

**现象**：
```
ValueError: When localhost is not accessible, a shareable link must be created.
Please set share=True or check your proxy settings...
```

**原因**：`.env` 中配置了 `HTTP_PROXY` / `HTTPS_PROXY`（如 `127.0.0.1:7890`），Gradio 检测本地服务时请求被代理拦截。

**已做修复**（`app/config.py`）：
- 自动设置 `NO_PROXY=localhost,127.0.0.1,::1`，让本地地址不走代理

**若仍失败**，可尝试：
1. 临时注释 `.env` 中的代理配置后重启
2. 或在 `main.py` 的 `demo.launch(share=True)` 生成公网链接（需网络）

### 常见问题：Gradio 页面 500 / TypeError bool is not iterable

**现象**：
```
TypeError: argument of type 'bool' is not iterable
  File ".../gradio_client/utils.py", line 863, in get_type
    if "const" in schema:
```

**原因**：`pydantic 2.11+` 生成的 JSON Schema 中 `additionalProperties` 为布尔值，与 `gradio 4.44.1` 内置的 `gradio_client 1.3.0` 不兼容。

**已做修复**：
1. `requirements.txt` 锁定 `pydantic==2.10.6`
2. `main.py` 启动前自动应用 `gradio_client` 兼容补丁（`app/ui/gradio_compat.py`）

**若需手动降级 pydantic**（清华镜像）：
```bash
pip install pydantic==2.10.6 -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 常见问题：Rerank 模型无法从 HuggingFace 下载

**现象**：
```
OSError: We couldn't connect to 'https://huggingface.co' to load ...
BAAI/bge-reranker-v2-m3
```

**原因**：国内网络无法稳定访问 HuggingFace Hub。

**已做修复**（`app/retrieval/model_loader.py`）：
- 优先使用 `models/bge-reranker-v2-m3/` 本地缓存
- 本地不存在时，通过 **ModelScope 魔塔** 自动下载（`USE_MODELSCOPE = True`）
- 下载失败时，Rerank 自动跳过，仍使用 Hybrid 召回的 30 个 chunk 回答

**预下载 Rerank 模型**（阿里 PyPI 镜像）：
```bash
pip install modelscope -i https://mirrors.aliyun.com/pypi/simple/
python download_rerank_model.py
```

模型将保存至 `models/bge-reranker-v2-m3/`，与 HuggingFace 版本完全一致。

### 降级回退

代码已实现优雅降级：若 Hybrid / Rerank 依赖未安装，会自动回退到纯向量检索并在控制台打印警告，语义切块仍可独立生效。

| 开关 | 关闭后行为 |
|------|-----------|
| `USE_SEMANTIC_CHUNKING = False` | 回退 SentenceSplitter 固定长度切块 |
| `ENABLE_HYBRID_SEARCH = False` | 纯向量 Top-K |
| `ENABLE_RERANK = False` | 跳过 Cross-Encoder 精排 |

### 实施状态

- [x] 语义/结构切块（`chunker.py`）
- [x] Hybrid Search + RRF 融合（`hybrid_retriever.py`）
- [x] Cross-Encoder Rerank（`reranker.py`）
- [x] 检索流水线编排（`pipeline.py`）
- [x] 索引构建 / 问答服务接入
- [x] ModelScope 国内模型下载（`model_loader.py`）
- [ ] 本地依赖安装验证（需手动 `pip install -r requirements.txt`）
- [ ] 清除旧索引并重建后做问答对比测试

### 后续计划

- [x] 用 eval 5 题集跑 RAGAS，量化 Faithfulness / Context Precision（`eval/run_ragas.py`）
- [ ] 扩展至附件 2 全量问题集
- [x] Gradio Debug 面板展示检索片段（用户可见）
- [ ] 统计类问题接入 `result_1.xlsx` 结构化查询
- [x] LLM Router 替代关键词问题分类
- [x] Faithfulness 校验 + 拒答机制（Router scope + 空检索；Week 3 RAGAS 量化）

---

<!-- 下一次升级请在上方追加新条目，保留最新日期在最前 -->
