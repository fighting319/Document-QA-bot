"""Application configuration and constants."""

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PERSIST_DIR = PROJECT_ROOT / "storage"
UPLOAD_DIR = PROJECT_ROOT / "uploads"
MODELS_DIR = PROJECT_ROOT / "models"

PERSIST_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
MODELS_DIR.mkdir(parents=True, exist_ok=True)

load_dotenv(PROJECT_ROOT / ".env")

# Optional proxy — set HTTP_PROXY / HTTPS_PROXY in .env when needed
for proxy_var in ("HTTP_PROXY", "HTTPS_PROXY"):
    proxy_value = os.getenv(proxy_var)
    if proxy_value:
        os.environ[proxy_var] = proxy_value

# Gradio 启动需直连 localhost，避免代理拦截本地回环地址
_local_bypass = "localhost,127.0.0.1,::1"
existing_no_proxy = os.environ.get("NO_PROXY", "")
if existing_no_proxy:
    os.environ["NO_PROXY"] = f"{existing_no_proxy},{_local_bypass}"
else:
    os.environ["NO_PROXY"] = _local_bypass

LLM_MODELS = ["deepseek-chat"]

EMBED_MODELS = [
    "BAAI/bge-small-en-v1.5",
    "BAAI/bge-large-zh-v1.5",
]

DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"
DEEPSEEK_MAX_TOKENS = 1500

# 相似度TOP_K
SIMILARITY_TOP_K = 5

# 支持的文件类型
SUPPORTED_FILE_TYPES = [".pdf", ".docx", ".doc", ".txt", ".xlsx", ".pptx", ".csv", ".html"]

# --- Chunking (ingestion) ---
USE_SEMANTIC_CHUNKING = True
SEMANTIC_BREAKPOINT_PERCENTILE = 95
MAX_SECTION_CHARS = 800
CHUNK_SIZE = 512
CHUNK_OVERLAP = 50
ENABLE_CONTEXTUAL_HEADER = True

# --- Hybrid retrieval ---
ENABLE_HYBRID_SEARCH = True
HYBRID_VECTOR_TOP_K = 10
HYBRID_BM25_TOP_K = 10
FUSION_MODE = "reciprocal_rerank"

# --- Rerank ---
ENABLE_RERANK = True
RERANK_MODEL = "BAAI/bge-reranker-v2-m3"
RERANK_TOP_N = 5
RERANK_CANDIDATE_TOP_K = 12

# --- Model download (国内推荐 ModelScope 魔塔) ---
USE_MODELSCOPE = True

# --- Week 2: Router + Citations + Refusal ---
ENABLE_LLM_ROUTER = True
ROUTER_FALLBACK_TO_KEYWORDS = True
SHOW_CITATIONS = True
REFUSAL_MIN_TOP_SCORE = 0.0  # 0 = 关闭分数拒答，仅 Router out_of_scope + 空检索

# --- Vector store backend ---
# local: storage/default__vector_store.json（默认，零依赖）
# qdrant: 向量外置到 Qdrant；docstore 仍本地（BM25 暂留内存）
VECTOR_BACKEND = os.getenv("VECTOR_BACKEND", "local").strip().lower()
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333").strip()
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "docbot_chunks").strip()
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "").strip() or None
