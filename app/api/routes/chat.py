"""Chat / QA endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.api.schemas import ChatRequest, ChatResponse, CitationItem, RouteInfo
from app.services.qa_service import answer_question
from app.state import app_state

router = APIRouter(prefix="/api/v1", tags=["chat"])

# 聊天接口
@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    # 检查索引是否加载
    if app_state.vector_index is None:
        raise HTTPException(
            status_code=409,
            detail="索引未加载，请先 POST /api/v1/index/upload 或 POST /api/v1/index/load",
        )

    # 回答问题
    result = answer_question(request.question.strip(), request.history)

    # 获取路由信息
    route = None
    if result.get("route"):
        route = RouteInfo(**result["route"])

    # 获取引用信息
    citations = [CitationItem(**item) for item in result.get("citations", [])]

    # 检查错误
    if result.get("error") == "index_not_loaded":
        raise HTTPException(status_code=409, detail=result["answer"])

    # 返回聊天响应
    return ChatResponse(
        answer=result["answer"],
        citations=citations,
        retrieval_debug=result.get("retrieval_debug", ""),
        route=route,
        refused=result.get("refused", False),
        refusal_reason=result.get("refusal_reason"),
        error=result.get("error"),
    )
