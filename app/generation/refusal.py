"""Refusal logic when context is insufficient or out of scope."""

from __future__ import annotations

from typing import List

from llama_index.core.schema import NodeWithScore

from app.config import REFUSAL_MIN_TOP_SCORE
from app.routing.models import RouteResult

# 判断是否拒绝回答
def should_refuse(
    question: str,
    nodes: list[NodeWithScore],
    route: RouteResult,
) -> tuple[bool, str]:
    if route.is_out_of_scope:
        return True, "out_of_scope"

    if not nodes:
        return True, "no_retrieval"

    if _all_scores_below_threshold(nodes):
        return True, "low_relevance"

    return False, ""

# 构建拒绝回答消息
def build_refusal_message(
    reason: str,
    question: str,
    indexed_files: List[str],
    route: RouteResult | None = None,
) -> str:
    doc_list = "、".join(indexed_files) if indexed_files else "（暂无）"

    if reason == "out_of_scope":
        return (
            f"抱歉，当前知识库无法回答该问题。\n\n"
            f"**原因**：问题与已索引文档范围不匹配。\n"
            f"**当前知识库包含**：{doc_list}\n\n"
            f"请上传相关文档后重试，或换用与已索引赛事相关的问题。"
        )

    if reason == "no_retrieval":
        return (
            f"抱歉，未在知识库中检索到与问题相关的文档片段。\n\n"
            f"**问题**：{question}\n"
            f"**当前知识库包含**：{doc_list}\n\n"
            f"建议：检查是否已上传/加载索引，或换一种问法。"
        )

    if reason == "low_relevance":
        return (
            f"抱歉，检索到的文档片段与问题相关度较低，无法给出可靠回答。\n\n"
            f"**问题**：{question}\n"
            f"**当前知识库包含**：{doc_list}\n\n"
            f"建议：补充相关文档，或缩小问题范围。"
        )

    return f"抱歉，无法基于当前文档回答该问题。\n\n**问题**：{question}"

# 判断所有分数是否低于阈值
def _all_scores_below_threshold(nodes: list[NodeWithScore]) -> bool:
    scores = [node.score for node in nodes if node.score is not None]
    if not scores:
        return False
    return max(scores) < REFUSAL_MIN_TOP_SCORE
