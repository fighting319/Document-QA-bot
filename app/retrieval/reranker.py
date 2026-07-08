"""Cross-encoder reranking for retrieved nodes."""

from __future__ import annotations

import os
from typing import Optional

from llama_index.core.schema import NodeWithScore, QueryBundle

from app.config import MODELS_DIR, RERANK_MODEL, RERANK_TOP_N
from app.retrieval.model_loader import resolve_local_model_path

_reranker = None
_reranker_model_name: Optional[str] = None

os.environ.setdefault("HF_HOME", str(MODELS_DIR))
os.environ.setdefault("SENTENCE_TRANSFORMERS_HOME", str(MODELS_DIR))

# 获取精排器
def get_reranker(model_name: str = RERANK_MODEL, top_n: int = RERANK_TOP_N):
    global _reranker, _reranker_model_name
    try:
        from llama_index.core.postprocessor import SentenceTransformerRerank
    except ImportError as exc:
        raise ImportError(
            "Rerank 需要 sentence-transformers，请执行: pip install sentence-transformers"
        ) from exc

    model_path = resolve_local_model_path(model_name)

    if _reranker is None or _reranker_model_name != model_name:
        _reranker = SentenceTransformerRerank(
            model=model_path,
            top_n=top_n,
            device="cpu",
        )
        _reranker_model_name = model_name
    elif _reranker.top_n != top_n:
        _reranker.top_n = top_n
    return _reranker

# 精排节点
def rerank_nodes(
    nodes: list[NodeWithScore],
    query: str,
    reranker=None,
) -> list[NodeWithScore]:
    if not nodes:
        return nodes
    reranker = reranker or get_reranker()
    return reranker.postprocess_nodes(nodes, query_bundle=QueryBundle(query_str=query))
