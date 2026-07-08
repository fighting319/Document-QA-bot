"""Question-answering orchestration service."""

from __future__ import annotations

import traceback
from datetime import datetime
from typing import Any

from llama_index.core import Settings

from app.config import SHOW_CITATIONS
from app.generation.citations import (
    build_citation_list,
    format_citation_appendix,
    format_retrieval_debug,
)
from app.generation.query_handlers import dispatch_answer
from app.generation.refusal import build_refusal_message, should_refuse
from app.retrieval.embedder import get_embed_model
from app.retrieval.pipeline import retrieve_context
from app.routing.llm_router import route_question
from app.routing.models import RouteResult
from app.state import app_state

# 获取已索引文件列表
def _indexed_filenames() -> list[str]:
    return [doc["filename"] for doc in app_state.document_metadata]

# 将路由信息转换为字典
def _route_to_dict(route: RouteResult) -> dict[str, Any]:
    return {
        "question_type": route.question_type,
        "answer_scope": route.answer_scope,
        "is_ambiguous": route.is_ambiguous,
        "ambiguity_note": route.ambiguity_note,
        "reasoning": route.reasoning,
        "source": route.source,
    }

# 回答问题
def answer_question(message: str, history: list | None = None) -> dict[str, Any]:
    """Structured QA result for API and Gradio."""
    history = history or []
    empty: dict[str, Any] = {
        "answer": "",
        "citations": [],
        "retrieval_debug": "",
        "route": None,
        "refused": False,
        "refusal_reason": None,
        "error": None,
    }

    try:
        if app_state.vector_index is None:
            empty["error"] = "index_not_loaded"
            empty["answer"] = "请先上传文件或加载已有索引。"
            return empty

        embed_model = get_embed_model(app_state.selected_embed_model_name)
        Settings.llm = None

        indexed_files = _indexed_filenames()
        route = route_question(message, indexed_files)
        print(
            f"[Router] type={route.question_type} scope={route.answer_scope} "
            f"ambiguous={route.is_ambiguous} source={route.source}"
        )
        if route.reasoning:
            print(f"[Router] reasoning: {route.reasoning}")

        relevant_context, retrieved_nodes = retrieve_context(
            message,
            app_state.vector_index,
            embed_model,
            app_state.selected_embed_model_name,
        )

        route_header = (
            f"路由: {route.question_type} | 范围: {route.answer_scope} | 来源: {route.source}"
        )
        if route.is_ambiguous and route.ambiguity_note:
            route_header += f"\n歧义提示: {route.ambiguity_note}"

        retrieval_debug = format_retrieval_debug(retrieved_nodes, route_info=route_header)
        app_state.last_retrieval_debug = retrieval_debug
        citations = build_citation_list(retrieved_nodes)

        print(f"查询: '{message}'")
        for index, node in enumerate(retrieved_nodes, start=1):
            preview = node.get_content()[:120].replace("\n", " ")
            print(f"  检索片段{index}: {preview}...")

        refuse, reason = should_refuse(message, retrieved_nodes, route)
        if refuse:
            response = build_refusal_message(reason, message, indexed_files, route)
            print(f"\n{datetime.now()}: Bot 拒答 ({reason})\n")
            return {
                "answer": response,
                "citations": citations,
                "retrieval_debug": retrieval_debug,
                "route": _route_to_dict(route),
                "refused": True,
                "refusal_reason": reason,
                "error": None,
            }

        response = dispatch_answer(route, message, relevant_context)
        if SHOW_CITATIONS and retrieved_nodes:
            response += format_citation_appendix(retrieved_nodes)

        print(f"\n{datetime.now()}: Bot 回答: '{response[:100]}...'\n")
        return {
            "answer": response,
            "citations": citations,
            "retrieval_debug": retrieval_debug,
            "route": _route_to_dict(route),
            "refused": False,
            "refusal_reason": None,
            "error": None,
        }
    except Exception as exc:
        print(f"错误完整信息: {str(exc)}")
        traceback.print_exc()
        empty["error"] = str(exc)
        empty["answer"] = f"处理查询时发生错误: {str(exc)}"
        return empty

# 响应问题
def respond(message: str, history) -> str:
    result = answer_question(message, history)
    return result["answer"]

# 获取最后一次检索调试
def get_last_retrieval_debug() -> str:
    return app_state.last_retrieval_debug or "（尚未提问，或无检索记录）"
