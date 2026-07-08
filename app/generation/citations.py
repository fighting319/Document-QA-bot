"""Citation formatting for retrieved chunks."""

from __future__ import annotations

from llama_index.core.schema import NodeWithScore

# 格式化上下文和引用
def format_context_with_citations(nodes: list[NodeWithScore]) -> str:
    parts = []
    for index, node in enumerate(nodes, start=1):
        metadata = node.metadata if isinstance(node.metadata, dict) else {}
        source = metadata.get("file_name", "未知")
        score = node.score if node.score is not None else "N/A"
        content = node.get_content()
        parts.append(f"[{index}] 来源:{source} | score:{score}\n{content}")
    return "\n\n".join(parts)

# 构建引用列表
def build_citation_list(nodes: list[NodeWithScore], max_preview_chars: int = 120) -> list[dict]:
    citations = []
    for index, node in enumerate(nodes, start=1):
        metadata = node.metadata if isinstance(node.metadata, dict) else {}
        score = node.score
        citations.append(
            {
                "index": index,
                "source": metadata.get("file_name", "未知"),
                "score": float(score) if score is not None else None,
                "preview": node.get_content().replace("\n", " ")[:max_preview_chars],
            }
        )
    return citations

# 格式化引用附录
def format_citation_appendix(nodes: list[NodeWithScore], max_preview_chars: int = 120) -> str:
    if not nodes:
        return ""

    lines = ["\n\n---", "**引用来源**"]
    for index, node in enumerate(nodes, start=1):
        metadata = node.metadata if isinstance(node.metadata, dict) else {}
        source = metadata.get("file_name", "未知")
        score = node.score if node.score is not None else "N/A"
        preview = node.get_content().replace("\n", " ")[:max_preview_chars]
        lines.append(f"- [{index}] `{source}` (score: {score})")
        lines.append(f"  > {preview}...")
    return "\n".join(lines)

# 格式化检索调试
def format_retrieval_debug(nodes: list[NodeWithScore], route_info: str = "") -> str:
    header = route_info.strip()
    if not nodes:
        body = "（未检索到任何片段）"
        return f"{header}\n{body}" if header else body

    chunks = []
    for index, node in enumerate(nodes, start=1):
        metadata = node.metadata if isinstance(node.metadata, dict) else {}
        source = metadata.get("file_name", "未知")
        score = node.score if node.score is not None else "N/A"
        preview = node.get_content()[:200].replace("\n", " ")
        chunks.append(f"[{index}] {source} | score={score}\n  {preview}...")

    body = "\n\n".join(chunks)
    return f"{header}\n\n{body}" if header else body
