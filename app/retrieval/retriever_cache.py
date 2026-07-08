"""Cache Hybrid retriever until index or embedding model changes."""

from __future__ import annotations

from typing import Any, Optional, Tuple

from app.retrieval.hybrid_retriever import create_hybrid_retriever

_cached_retriever: Any = None
_cached_key: Optional[Tuple[Any, str, int]] = None

# 构建缓存键
def _build_cache_key(vector_index, embed_model_name: str) -> Tuple[Any, str, int]:
    node_count = len(vector_index.docstore.docs) if vector_index is not None else 0
    return (id(vector_index), embed_model_name, node_count)

# 获取缓存的混合检索器
def get_cached_hybrid_retriever(vector_index, embed_model, embed_model_name: str):
    global _cached_retriever, _cached_key

    cache_key = _build_cache_key(vector_index, embed_model_name)
    if _cached_retriever is not None and _cached_key == cache_key:
        return _cached_retriever

    print("[Retriever] 构建 Hybrid 检索器（BM25 + 向量）...")
    _cached_retriever = create_hybrid_retriever(vector_index, embed_model)
    _cached_key = cache_key
    return _cached_retriever

# 清除缓存的混合检索器
def invalidate_hybrid_retriever_cache() -> None:
    global _cached_retriever, _cached_key
    _cached_retriever = None
    _cached_key = None
