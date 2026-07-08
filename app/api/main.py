"""FastAPI application factory."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import chat, config, health, index
from app.bootstrap.warmup import warmup_models
from app.config import EMBED_MODELS, LLM_MODELS
from app.kb.index_manager import load_existing_index
from app.state import app_state

# 生命周期管理
@asynccontextmanager
async def lifespan(app: FastAPI):
    app_state.selected_llm_model_name = LLM_MODELS[0]
    app_state.selected_embed_model_name = EMBED_MODELS[0]
    warmup_models()
    load_existing_index()
    yield

# 创建API应用
def create_api_app() -> FastAPI:
    app = FastAPI(
        title="Document QA Bot API",
        description="竞赛智能文档客服机器人 REST API（与 Gradio 共用 RAG 核心）",
        version="1.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(chat.router)
    app.include_router(index.router)
    app.include_router(config.router)

    return app


app = create_api_app()
