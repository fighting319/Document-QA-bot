"""Heuristics to detect low-quality document parsing before indexing."""

from __future__ import annotations

import re
from dataclasses import dataclass

# 中文文档：有效字符中 CJK 占比下限
MIN_CJK_RATIO = 0.08
# 乱码符号占比上限
MAX_GARBAGE_RATIO = 0.22
# 最短有效文本长度
MIN_TEXT_LENGTH = 80

_CJK_RE = re.compile(r"[\u4e00-\u9fff]")
_MEANINGFUL_RE = re.compile(r"[\u4e00-\u9fffA-Za-z0-9]")
# 常见 PDF 乱码符号
_GARBAGE_RE = re.compile(r"[^\u4e00-\u9fffA-Za-z0-9\s，。：；、（）【】《》%￥\-—_\.·\|\n\r\t/\\]")


@dataclass
class ParseQualityResult:
    ok: bool
    reason: str
    cjk_ratio: float = 0.0
    garbage_ratio: float = 0.0
    length: int = 0


def is_better_parse(candidate: ParseQualityResult, current: ParseQualityResult) -> bool:
    """Whether candidate parse should replace current parse."""
    if candidate.ok and not current.ok:
        return True
    if candidate.ok and current.ok:
        return candidate.length > current.length
    if not candidate.ok and current.ok:
        return False

    if candidate.length < MIN_TEXT_LENGTH and current.length < MIN_TEXT_LENGTH:
        return False

    candidate_score = candidate.cjk_ratio - candidate.garbage_ratio
    current_score = current.cjk_ratio - current.garbage_ratio
    if candidate_score > current_score + 0.02:
        return True

    return (
        candidate.cjk_ratio >= MIN_CJK_RATIO
        and current.cjk_ratio < MIN_CJK_RATIO
        and candidate.garbage_ratio <= current.garbage_ratio + 0.05
    )


def assess_parse_quality(text: str) -> ParseQualityResult:
    """Return whether parsed text is good enough to index."""
    cleaned = (text or "").strip()
    length = len(cleaned)
    if length < MIN_TEXT_LENGTH:
        return ParseQualityResult(False, f"文本过短（{length} 字符）", length=length)

    cjk_count = len(_CJK_RE.findall(cleaned))
    meaningful_count = len(_MEANINGFUL_RE.findall(cleaned))
    if meaningful_count == 0:
        return ParseQualityResult(False, "未检测到有效中英文字符", length=length)

    cjk_ratio = cjk_count / meaningful_count
    garbage_count = len(_GARBAGE_RE.findall(cleaned))
    garbage_ratio = garbage_count / max(length, 1)

    if garbage_ratio > MAX_GARBAGE_RATIO:
        return ParseQualityResult(
            False,
            f"乱码符号过多（{garbage_ratio:.1%}）",
            cjk_ratio=cjk_ratio,
            garbage_ratio=garbage_ratio,
            length=length,
        )

    if cjk_ratio < MIN_CJK_RATIO and garbage_ratio > 0.12:
        return ParseQualityResult(
            False,
            f"中文占比偏低且疑似乱码（cjk={cjk_ratio:.1%}）",
            cjk_ratio=cjk_ratio,
            garbage_ratio=garbage_ratio,
            length=length,
        )

    return ParseQualityResult(
        True,
        "ok",
        cjk_ratio=cjk_ratio,
        garbage_ratio=garbage_ratio,
        length=length,
    )
