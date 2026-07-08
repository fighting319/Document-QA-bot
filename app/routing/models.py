"""Routing result models."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RouteResult:
    question_type: str  # basic | statistical | open
    is_ambiguous: bool = False
    ambiguity_note: str = ""
    answer_scope: str = "in_scope"  # in_scope | partial | out_of_scope
    reasoning: str = ""
    source: str = "keyword"  # llm | keyword

    @property
    def is_out_of_scope(self) -> bool:
        return self.answer_scope == "out_of_scope"
