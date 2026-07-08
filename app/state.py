"""Shared application runtime state."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional


@dataclass
class AppState:
    """Holds in-memory knowledge-base and model selection state."""
    # 向量索引
    vector_index: Any = None
    # 文档元数据
    document_metadata: List[dict] = field(default_factory=list)
    # LLM模型名称
    selected_llm_model_name: str = ""
    # 嵌入模型名称
    selected_embed_model_name: str = ""
    # 最后一次检索调试
    last_retrieval_debug: str = ""
    # 重置状态
    def reset(self) -> None:
        self.vector_index = None
        self.document_metadata = []
        self.last_retrieval_debug = ""


app_state = AppState()
