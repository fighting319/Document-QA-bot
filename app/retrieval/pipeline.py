"""End-to-end retrieval: hybrid search, rerank, context assembly."""

from __future__ import annotations

from llama_index.core.schema import NodeWithScore, QueryBundle

from app.config import (
    ENABLE_HYBRID_SEARCH,
    ENABLE_RERANK,
    RERANK_TOP_N,
    SIMILARITY_TOP_K,
)
from app.generation.citations import format_context_with_citations

# 检索上下文
def retrieve_context(
    message: str,
    vector_index,
    embed_model,
    embed_model_name: str,
) -> tuple[str, list[NodeWithScore]]:
    nodes = _retrieve_nodes(message, vector_index, embed_model, embed_model_name)
    nodes = _maybe_rerank(nodes, message)
    context = format_context_with_citations(nodes)
    return context, nodes

# 检索节点
def _retrieve_nodes(message: str, vector_index, embed_model, embed_model_name: str) -> list[NodeWithScore]:
    if ENABLE_HYBRID_SEARCH:
        try:
            from app.retrieval.hybrid_retriever import retrieve_nodes
            from app.retrieval.retriever_cache import get_cached_hybrid_retriever

            retriever = get_cached_hybrid_retriever(
                vector_index,
                embed_model,
                embed_model_name,
            )
            nodes = retrieve_nodes(retriever, message)
            print(f"Hybrid 召回 {len(nodes)} 个候选 chunk")
            return nodes
        except ImportError as exc:
            print(f"[警告] Hybrid Search 不可用，回退到纯向量检索: {exc}")
        except ValueError as exc:
            print(f"[警告] Hybrid Search 不可用，回退到纯向量检索: {exc}")
        except Exception as exc:
            print(f"[警告] Hybrid Search 失败，回退到纯向量检索: {exc}")

    nodes = vector_index.as_retriever(
        embed_model=embed_model,
        similarity_top_k=SIMILARITY_TOP_K,
    ).retrieve(QueryBundle(query_str=message))
    print(f"向量检索召回 {len(nodes)} 个 chunk")
    return nodes

# 精排
def _maybe_rerank(nodes: list[NodeWithScore], message: str) -> list[NodeWithScore]:
    if not ENABLE_RERANK or not nodes:
        return nodes
    try:
        from app.retrieval.reranker import get_reranker, rerank_nodes

        reranker = get_reranker(top_n=RERANK_TOP_N)
        nodes = rerank_nodes(nodes, message, reranker)
        print(f"Rerank 后保留 Top-{len(nodes)} 个 chunk")
    except Exception as exc:
        print(f"[警告] Rerank 失败，跳过精排（将使用 Hybrid 召回结果）: {exc}")
    return nodes

# 格式化上下文
def _format_context(nodes: list[NodeWithScore]) -> str:
    """Deprecated: use format_context_with_citations from citations module."""
    return format_context_with_citations(nodes)
