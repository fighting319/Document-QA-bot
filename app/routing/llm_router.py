"""LLM-based question router with keyword fallback."""

from __future__ import annotations

import json
import re
from typing import List

from app.config import ENABLE_LLM_ROUTER, ROUTER_FALLBACK_TO_KEYWORDS
from app.generation.llm_client import call_deepseek_api
from app.routing.classifier import classify_question
from app.routing.models import RouteResult

_VALID_TYPES = {"basic", "statistical", "open"}
_VALID_SCOPES = {"in_scope", "partial", "out_of_scope"}

# 路由问题
def route_question(question: str, indexed_files: List[str] | None = None) -> RouteResult:
    indexed_files = indexed_files or []
    if ENABLE_LLM_ROUTER:
        try:
            result = _route_with_llm(question, indexed_files)
            if result is not None:
                return result
        except Exception as exc:
            print(f"[Router] LLM 路由失败，回退关键词: {exc}")

    if ROUTER_FALLBACK_TO_KEYWORDS:
        return _route_with_keywords(question)
    return RouteResult(question_type="basic", source="keyword")

# 使用关键词路由
def _route_with_keywords(question: str) -> RouteResult:
    return RouteResult(
        question_type=classify_question(question),
        source="keyword",
    )

# 使用LLM路由
def _route_with_llm(question: str, indexed_files: List[str]) -> RouteResult | None:
    doc_list = "\n".join(f"- {name}" for name in indexed_files) if indexed_files else "- （暂无索引文件）"

    prompt = f"""你是竞赛文档问答系统的路由模块。根据用户问题和当前知识库文件列表，输出 JSON（不要 markdown 代码块）。

当前知识库文件：
{doc_list}

用户问题：{question}

请判断：
1. question_type：basic（事实查询）| statistical（数量/统计）| open（流程/建议/开放讨论）
2. is_ambiguous：问题是否存在多种理解口径（如「几个比赛」可能指专项赛总数、阶段数、组别数）
3. ambiguity_note：若 is_ambiguous 为 true，简述可能口径；否则空字符串
4. answer_scope：
   - in_scope：当前知识库很可能能回答
   - partial：只能部分回答（如问全赛总数但库内只有单个专项赛文档）
   - out_of_scope：问题与当前知识库完全无关
5. reasoning：一句话说明路由理由

只输出 JSON：
{{"question_type":"...","is_ambiguous":false,"ambiguity_note":"","answer_scope":"in_scope","reasoning":"..."}}"""

    system_prompt = "你是严谨的路由器，只输出合法 JSON，不输出其他文字。"
    raw = call_deepseek_api(prompt, system_prompt, temperature=0.0, max_tokens=300)
    parsed = _parse_json_response(raw)
    if parsed is None:
        return None

    question_type = parsed.get("question_type", "basic")
    if question_type not in _VALID_TYPES:
        question_type = classify_question(question)

    answer_scope = parsed.get("answer_scope", "in_scope")
    if answer_scope not in _VALID_SCOPES:
        answer_scope = "in_scope"

    return RouteResult(
        question_type=question_type,
        is_ambiguous=bool(parsed.get("is_ambiguous", False)),
        ambiguity_note=str(parsed.get("ambiguity_note", "")).strip(),
        answer_scope=answer_scope,
        reasoning=str(parsed.get("reasoning", "")).strip(),
        source="llm",
    )

# 解析JSON响应
def _parse_json_response(raw: str) -> dict | None:
    if not raw or raw.startswith("Request error") or raw.startswith("DEEPSEEK"):
        return None

    text = raw.strip()
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1)

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        return None

    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
