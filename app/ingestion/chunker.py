"""Semantic and structural document chunking."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from llama_index.core import Document
from llama_index.core.node_parser import (
    MarkdownNodeParser,
    SemanticSplitterNodeParser,
    SentenceSplitter,
)
from llama_index.core.schema import BaseNode

from app.config import (
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    ENABLE_CONTEXTUAL_HEADER,
    MAX_SECTION_CHARS,
    SEMANTIC_BREAKPOINT_PERCENTILE,
    USE_SEMANTIC_CHUNKING,
)

# 确保文件名
def _ensure_file_name(documents: List[Document], saved_files: Optional[List[str]] = None) -> None:
    for doc in documents:
        if not isinstance(doc.metadata, dict):
            continue
        if doc.metadata.get("file_name"):
            continue
        if saved_files:
            for file_path in saved_files:
                if str(file_path).endswith(Path(file_path).name):
                    doc.metadata["file_name"] = Path(file_path).name
                    break

# 添加上下文头
def _add_contextual_header(node: BaseNode) -> None:
    if not ENABLE_CONTEXTUAL_HEADER:
        return

    metadata = node.metadata if isinstance(node.metadata, dict) else {}
    file_name = metadata.get("file_name") or metadata.get("source_file", "未知文件")
    header = metadata.get("header_path") or metadata.get("section_title", "")

    prefix = f"【文档:{file_name}】"
    if header:
        prefix += f"【章节:{header}】"
    node.set_content(f"{prefix}\n{node.get_content()}")

# 使用句子分割器切块
def _chunk_with_sentence_splitter(documents: List[Document]) -> List[BaseNode]:
    splitter = SentenceSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
    return splitter.get_nodes_from_documents(documents)

# 使用Markdown和语义切块
def _chunk_with_markdown_and_semantic(
    documents: List[Document],
    embed_model,
) -> List[BaseNode]:
    md_parser = MarkdownNodeParser()
    md_nodes = md_parser.get_nodes_from_documents(documents)

    semantic_parser = SemanticSplitterNodeParser(
        embed_model=embed_model,
        buffer_size=1,
        breakpoint_percentile_threshold=SEMANTIC_BREAKPOINT_PERCENTILE,
    )

    final_nodes: List[BaseNode] = []
    for node in md_nodes:
        content = node.get_content()
        if len(content) > MAX_SECTION_CHARS:
            sub_doc = Document(text=content, metadata=dict(node.metadata))
            final_nodes.extend(semantic_parser.get_nodes_from_documents([sub_doc]))
        else:
            final_nodes.append(node)

    return final_nodes

# 构建节点
def build_nodes(
    documents: List[Document],
    embed_model,
    saved_files: Optional[List[str]] = None,
) -> List[BaseNode]:
    """Parse documents into retrieval-ready nodes."""
    _ensure_file_name(documents, saved_files)

    if USE_SEMANTIC_CHUNKING:
        nodes = _chunk_with_markdown_and_semantic(documents, embed_model)
    else:
        nodes = _chunk_with_sentence_splitter(documents)

    for node in nodes:
        _add_contextual_header(node)

    print(f"切块完成: {len(documents)} 篇文档 → {len(nodes)} 个 chunk")
    return nodes
