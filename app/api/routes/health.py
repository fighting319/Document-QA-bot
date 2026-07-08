"""Health and status endpoints."""

from __future__ import annotations

import os

from fastapi import APIRouter

from app.api.schemas import StatusResponse
from app.kb.vector_store import get_vector_backend
from app.state import app_state

router = APIRouter(tags=["health"])

# 健康检查接口  
@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

# 获取状态接口
@router.get("/api/v1/status", response_model=StatusResponse)
def get_status() -> StatusResponse:
    return StatusResponse(
        # 检查索引是否加载
        index_loaded=app_state.vector_index is not None,
        # 检查文档数量
        document_count=len(app_state.document_metadata),
        # 检查嵌入模型
        embed_model=app_state.selected_embed_model_name,
        # 检查LLM模型
        llm_model=app_state.selected_llm_model_name,
        # 检查DeepSeek API密钥是否设置
        deepseek_api_key_set=bool(os.getenv("DEEPSEEK_API_KEY")),
        vector_backend=get_vector_backend(),
        indexed_files=[doc["filename"] for doc in app_state.document_metadata],
    )
