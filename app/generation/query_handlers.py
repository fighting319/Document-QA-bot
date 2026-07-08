"""Query handlers for different question types."""

from __future__ import annotations

import re
from typing import List, Union

from app.generation.llm_client import call_deepseek_api
from app.routing.models import RouteResult

_CITATION_RULE = (
    "回答中引用文档内容时，请标注引用编号如 [1]、[2]。"
    "若文档信息不足以回答，请明确说明哪一部分无法从文档得出，不要编造。"
)

# 提取文本中的数字
def extract_numbers_from_text(text: str) -> List[Union[int, float]]:
    number_pattern = r"(\d+(?:\.\d+)?)"
    numbers = re.findall(number_pattern, text)
    return [float(num) if "." in num else int(num) for num in numbers]

# 分发答案
def dispatch_answer(
    route: RouteResult,
    question: str,
    context: str,
) -> str:
    ambiguity_hint = route.ambiguity_note if route.is_ambiguous else ""
    if route.question_type == "statistical":
        return analyze_statistics(question, context, ambiguity_hint)
    if route.question_type == "open":
        return handle_open_question(question, context)
    return handle_basic_query(question, context, ambiguity_hint)

# 处理基础查询
def handle_basic_query(
    question: str,
    context: str,
    ambiguity_hint: str = "",
) -> str:
    ambiguity_block = f"\n路由提示（问题可能存在歧义）：{ambiguity_hint}\n" if ambiguity_hint else ""
    query_prompt = f"""
请基于以下带编号引用片段回答问题。

问题: {question}
{ambiguity_block}
文档片段:
{context}

要求:
1. 只使用片段中的信息；允许合理归纳（如「线上举办」可回答「在哪里举办」类问题）。
2. 区分「文档未提及」与「文档明确说明无/线上/不适用」。
3. {_CITATION_RULE}
4. 回答后简要列出关键点。
"""
    system_prompt = (
        "你是专业的文档问答助手。基于引用片段准确作答，可归纳但不可编造。"
        "若片段不足以回答，说明缺失的信息类型。"
    )
    return call_deepseek_api(query_prompt, system_prompt, temperature=0.3)

# 分析统计/数量类问题
def analyze_statistics(
    question: str,
    context: str,
    ambiguity_hint: str = "",
) -> str:
    ambiguity_block = (
        f"\n路由提示：该问题可能有多重统计口径。{ambiguity_hint}\n"
        "请先说明问题口径，再分别给出文档中可支持的统计结论；"
        "若某口径文档无法支持（如全赛专项赛总数），明确拒答该口径并说明原因。\n"
        if ambiguity_hint or "几个" in question or "多少" in question or "一共" in question
        else ""
    )
    query_prompt = f"""
以下是统计/数量类问题及相关文档片段。

问题: {question}
{ambiguity_block}
文档片段:
{context}

要求:
1. 若问题口径不明确，先列出可能的统计维度（如阶段数、组别数、专项赛总数），再逐口径作答。
2. 文档无法支持的口径，明确说明「当前知识库无法得出该统计」。
3. 文档支持的口径，给出具体数字并标注引用 [n]。
4. {_CITATION_RULE}
5. 回答后简要列出关键点。
"""
    system_prompt = (
        "你是数据分析助手。处理模糊统计问题时，先澄清口径再作答；"
        "不得为不支持的口径编造数字。"
    )
    return call_deepseek_api(query_prompt, system_prompt, temperature=0.1)

# 处理开放性问题
def handle_open_question(question: str, context: str) -> str:
    query_prompt = f"""
请回答以下开放性问题。参考提供的文档片段，可适当补充合理建议。

问题: {question}

参考文档片段:
{context}

要求:
1. 先基于文档片段回答，标注引用 [n]。
2. 再提供补充建议，并明确标注「以下为补充建议，非文档原文」。
3. 回答后简要列出关键点。
"""
    system_prompt = (
        "你是专业顾问。先引用文档，再补充建议，并明确区分两者来源。"
    )
    return call_deepseek_api(query_prompt, system_prompt, temperature=0.5)
