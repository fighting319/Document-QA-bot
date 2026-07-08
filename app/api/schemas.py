"""Pydantic schemas for FastAPI."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

# 路由信息
class RouteInfo(BaseModel):
    question_type: str
    answer_scope: str
    is_ambiguous: bool
    ambiguity_note: str = ""
    reasoning: str = ""
    source: str = ""

# 引用信息
class CitationItem(BaseModel):
    index: int
    source: str
    score: Optional[float] = None
    preview: str = ""

# 聊天请求
class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, description="用户问题")
    history: list[list[str]] = Field(default_factory=list, description="对话历史 [[user, bot], ...]")

# 聊天响应
class ChatResponse(BaseModel):
    answer: str
    citations: list[CitationItem] = Field(default_factory=list)
    retrieval_debug: str = ""
    route: Optional[RouteInfo] = None
    refused: bool = False
    refusal_reason: Optional[str] = None
    error: Optional[str] = None

# 状态响应
class StatusResponse(BaseModel):
    index_loaded: bool
    document_count: int
    embed_model: str
    llm_model: str
    deepseek_api_key_set: bool
    vector_backend: str = "local"
    indexed_files: list[str] = Field(default_factory=list)

# 文档信息
class DocumentItem(BaseModel):
    filename: str
    path: str
    upload_time: str
    version: float | str

# 索引上传响应
class IndexUploadResponse(BaseModel):
    message: str
    saved_files: list[str] = Field(default_factory=list)
    skipped_files: list[str] = Field(default_factory=list)
    updated_files: list[str] = Field(default_factory=list)
    document_count: int = 0

# 消息响应
class MessageResponse(BaseModel):
    message: str
    detail: Optional[str] = None

# 模型响应
class ModelsResponse(BaseModel):
    embed_models: list[str]
    llm_models: list[str]
    current_embed_model: str
    current_llm_model: str

# 设置嵌入模型请求
class SetEmbedModelRequest(BaseModel):
    embed_model: str

# 设置LLM模型请求
class SetLlmModelRequest(BaseModel):
    llm_model: str

# 调试响应  
class DebugResponse(BaseModel):
    debug: str

# 索引统计响应
class IndexStatsResponse(BaseModel):
    node_count: Optional[int] = None
    document_count: int
    embed_model: str
    indexed_files: list[str] = Field(default_factory=list)
