"""Knowledge-base / index endpoints."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.api.schemas import (
    DebugResponse,
    DocumentItem,
    IndexUploadResponse,
    MessageResponse,
)
from app.config import EMBED_MODELS
from app.ingestion.index_builder import load_files
from app.kb.index_manager import (
    clear_all_storage,
    debug_file_updates,
    debug_index,
    load_existing_index,
    reset_index_cache,
    save_index,
)
from app.state import app_state

router = APIRouter(prefix="/api/v1/index", tags=["index"])

# 获取文档列表
@router.get("/documents", response_model=list[DocumentItem])
def list_documents() -> list[DocumentItem]:
    return [DocumentItem(**doc) for doc in app_state.document_metadata]

# 上传并索引文件
@router.post("/upload", response_model=IndexUploadResponse)
async def upload_and_index(
    files: list[UploadFile] = File(...),
    embed_model: str | None = Form(default=None),
    update_existing: bool = Form(default=False),
) -> IndexUploadResponse:
    if not files:
        raise HTTPException(status_code=400, detail="请至少上传一个文件")

    model_name = embed_model or app_state.selected_embed_model_name or EMBED_MODELS[0]
    if model_name not in EMBED_MODELS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的 embed_model: {model_name}，可选: {EMBED_MODELS}",
        )

    saved_paths: list[str] = []
    with tempfile.TemporaryDirectory() as tmp_dir:
        for upload in files:
            if not upload.filename:
                continue
            dest = Path(tmp_dir) / Path(upload.filename).name
            with dest.open("wb") as out:
                shutil.copyfileobj(upload.file, out)
            saved_paths.append(str(dest))

        if not saved_paths:
            raise HTTPException(status_code=400, detail="没有有效文件")

        message = load_files(
            saved_paths,
            model_name,
            reload=False,
            update_existing=update_existing,
        )

    return IndexUploadResponse(
        message=message,
        saved_files=[Path(p).name for p in saved_paths],
        skipped_files=[],
        updated_files=[],
        document_count=len(app_state.document_metadata),
    )

# 加载索引
@router.post("/load", response_model=MessageResponse)
def load_index() -> MessageResponse:
    message = load_existing_index()
    if message.startswith("❌"):
        raise HTTPException(status_code=404, detail=message)
    return MessageResponse(message=message)

# 保存索引
@router.post("/save", response_model=MessageResponse)
def save_index_endpoint() -> MessageResponse:
    message = save_index()
    if message.startswith("❌"):
        raise HTTPException(status_code=409, detail=message)
    return MessageResponse(message=message)

# 清除索引
@router.delete("", response_model=MessageResponse)
def clear_index() -> MessageResponse:
    message = clear_all_storage()
    return MessageResponse(message=message)

# 重置缓存
@router.post("/reset-cache", response_model=MessageResponse)
def reset_cache() -> MessageResponse:
    message = reset_index_cache()
    return MessageResponse(message=message)

# 调试索引
@router.get("/debug", response_model=DebugResponse)
def index_debug() -> DebugResponse:
    return DebugResponse(debug=debug_index())

# 调试文件更新
@router.get("/debug/updates", response_model=DebugResponse)
def index_debug_updates() -> DebugResponse:
    return DebugResponse(debug=debug_file_updates())
