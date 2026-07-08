"""Model configuration endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.api.schemas import ModelsResponse, SetEmbedModelRequest, SetLlmModelRequest
from app.config import EMBED_MODELS, LLM_MODELS
from app.retrieval.retriever_cache import invalidate_hybrid_retriever_cache
from app.state import app_state

router = APIRouter(prefix="/api/v1/config", tags=["config"])

# 获取模型列表
@router.get("/models", response_model=ModelsResponse)
def get_models() -> ModelsResponse:
    return ModelsResponse(
        embed_models=list(EMBED_MODELS),
        llm_models=list(LLM_MODELS),
        current_embed_model=app_state.selected_embed_model_name,
        current_llm_model=app_state.selected_llm_model_name,
    )

# 设置嵌入模型
@router.put("/embed-model", response_model=ModelsResponse)
def set_embed_model(request: SetEmbedModelRequest) -> ModelsResponse:
    if request.embed_model not in EMBED_MODELS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的 embed_model: {request.embed_model}，可选: {EMBED_MODELS}",
        )
    if app_state.selected_embed_model_name != request.embed_model:
        invalidate_hybrid_retriever_cache()
    app_state.selected_embed_model_name = request.embed_model
    return get_models()

# 设置LLM模型
@router.put("/llm-model", response_model=ModelsResponse)
def set_llm_model(request: SetLlmModelRequest) -> ModelsResponse:
    if request.llm_model not in LLM_MODELS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的 llm_model: {request.llm_model}，可选: {LLM_MODELS}",
        )
    app_state.selected_llm_model_name = request.llm_model
    return get_models()
