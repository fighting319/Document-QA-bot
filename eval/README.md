# 评测集说明

## Week 1：手工 Baseline（当前阶段）

Week 1 不做 RAGAS 自动化，只做 **Golden Set + 人工判分**，为 Week 3 量化对比留底。

### 文件

| 文件 | 用途 |
|------|------|
| `questions.json` | 标准问题 + 期望答案口径 + 通过标准 |
| `week1_results.json` | Week 1 实际回答 + 人工 pass/fail |
| `week2_results.json` | Week 2 完成后追加（Router + 溯源 + 拒答） |
| `week3_ragas/` | Week 3 RAGAS 脚本输出目录 |

### 如何新增一题

在 `questions.json` 追加一条，必填字段：

```json
{
  "id": "Q004",
  "question": "原样用户问题",
  "type": "basic | statistical | open",
  "source_docs": ["对应 PDF 文件名"],
  "expected_answer": "参考答案或要点",
  "must_include": ["必须出现的要点"],
  "must_not_say": ["明显错误表述"],
  "acceptance": "怎样算通过/部分通过/不通过",
  "ambiguity_notes": "歧义说明（可选）"
}
```

### 如何记录一次验收结果

1. 在 Gradio 提问，**完整复制** Bot 回答（含 Week 2 的「引用来源」附录，如有）
2. 在 `week1_results.json`（或对应 week 文件）追加：

```json
{
  "id": "Q001",
  "evaluated_at": "2026-07-06",
  "pipeline_version": "week1-hybrid-rerank-semantic-chunk",
  "actual_answer": "粘贴 Bot 完整原文，不要用摘要",
  "pass": true,
  "partial_pass": false,
  "notes": "判分理由（可简短）"
}
```

**字段约定**

| 字段 | 要求 |
|------|------|
| `actual_answer` | **必须**为 Bot 完整原文，便于人工复核与 Week 3 RAGAS |
| `notes` | 判分理由，可简短；不要用它替代 `actual_answer` |
| `pass` / `partial_pass` | 对照 `questions.json` 的 `acceptance` 人工标注 |

### 判分规则（Week 1 人工）

| 结果 | 含义 |
|------|------|
| `pass: true` | 满足 `must_include`，且无 `must_not_say` |
| `partial_pass: true` | 方向对但缺要点（如只答选拔赛线上、未答决赛线上） |
| 两者皆 false | 答错或拒答不当 |

### Week 1 验收汇总（当前）

| ID | 问题 | Week 1 |
|----|------|--------|
| Q001 | 3D 专项赛在哪里举办 | 部分通过 |
| Q002 | 一共有几个比赛 | 部分通过 |
| Q003 | 未来校园参赛流程 | 通过 |
| Q004 | 3D 专项赛报名时间 | 通过 |
| Q005 | 两专项赛参赛资格（跨文档） | 通过 |

**Week 1 结论**：流程类（Q003）正常；地点归纳（Q001）与模糊统计（Q002）待 Week 2 改进。

**Week 2 验收**：用同一套 `questions.json` 重跑 5 题，结果写入 `week2_results.json`，`pipeline_version` 填 `week2-router-citations-refusal`。

### Week 1 vs Week 2 对比（2026-07-06）

| ID | 问题 | Week 1 | Week 2 |
|----|------|--------|--------|
| Q001 | 在哪举办 | 部分通过 | 部分通过（有引用，仍漏「决赛线上」） |
| Q002 | 一共几个比赛 | 部分通过 | 部分通过（分口径更好，但有幻觉+漏 3D 统计） |
| Q003 | 未来校园流程 | 通过 | 通过 |
| Q004 | 3D 报名时间 | 通过 | 通过 |
| Q005 | 两赛参赛资格 | 通过 | 部分通过（未来校园资格检索失败） |

**Week 2 小结**：引用溯源、歧义分口径明显改善；Q001 检索缺口、Q002 幻觉、Q005 跨文档检索仍待优化（可调 Rerank / query 扩展）。

---

## Week 3：RAGAS 自动化

```bash
python eval/run_ragas.py
```

输出：

| 文件 | 内容 |
|------|------|
| `week3_ragas/week1_ragas.json` | Week 1 回答的 RAGAS 分数 |
| `week3_ragas/week2_ragas.json` | Week 2 回答的 RAGAS 分数 |
| `week3_ragas/comparison.md` | Week 1 vs Week 2 对比表 |

指标：**faithfulness**、**context_precision**、**answer_relevancy**（DeepSeek 作评判 LLM，本地 bge-small 作 embedding）。

---
