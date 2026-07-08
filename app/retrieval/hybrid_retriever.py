"""Hybrid BM25 + dense vector retrieval with RRF fusion."""

from __future__ import annotations

from llama_index.core.retrievers import QueryFusionRetriever
from llama_index.core.schema import NodeWithScore, QueryBundle

from app.config import (
    FUSION_MODE,
    HYBRID_BM25_TOP_K,
    HYBRID_VECTOR_TOP_K,
    RERANK_CANDIDATE_TOP_K,
)

# 获取bm25检索器
def _docstore_node_count(vector_index) -> int:
    return len(vector_index.docstore.docs)


def _get_bm25_retriever(vector_index, similarity_top_k: int):
    try:
        from llama_index.retrievers.bm25 import BM25Retriever
    except ImportError as exc:
        raise ImportError(
            "Hybrid Search 需要安装 llama-index-retrievers-bm25==0.4.0，"
            "请执行: pip install llama-index-retrievers-bm25==0.4.0"
        ) from exc

    if _docstore_node_count(vector_index) == 0:
        raise ValueError(
            "docstore 为空，无法构建 BM25（Qdrant 模式需 store_nodes_override=True 写入本地文本）"
        )

    return BM25Retriever.from_defaults(
        docstore=vector_index.docstore,
        similarity_top_k=similarity_top_k,
        language="zh",
    )

# 创建混合检索器
def create_hybrid_retriever(vector_index, embed_model):
    vector_retriever = vector_index.as_retriever(
        embed_model=embed_model,
        similarity_top_k=HYBRID_VECTOR_TOP_K,
    )
    try:
        bm25_retriever = _get_bm25_retriever(vector_index, HYBRID_BM25_TOP_K)
    except ValueError as exc:
        print(f"[警告] BM25 不可用，Hybrid 退化为纯向量检索: {exc}")
        return vector_retriever

    return QueryFusionRetriever(
        retrievers=[vector_retriever, bm25_retriever],
        similarity_top_k=RERANK_CANDIDATE_TOP_K,
        num_queries=1,
        mode=FUSION_MODE,
    )

# 检索节点
def retrieve_nodes(retriever, query: str) -> list[NodeWithScore]:
    return retriever.retrieve(QueryBundle(query_str=query))
