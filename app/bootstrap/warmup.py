"""Preload heavy models at application startup."""

from __future__ import annotations

from app.config import EMBED_MODELS, ENABLE_RERANK
from app.retrieval.embedder import get_embed_model
from app.state import app_state

# 预加载模型
def warmup_models(embed_model_name: str | None = None) -> None:
    model_name = embed_model_name or app_state.selected_embed_model_name or EMBED_MODELS[0]
    app_state.selected_embed_model_name = model_name

    print(f"[Warmup] 预加载 Embedding: {model_name}")
    try:
        get_embed_model(model_name)
    except Exception as exc:
        print(f"[Warmup] Embedding 预加载失败，将在首次提问时重试: {exc}")

    if ENABLE_RERANK:
        from app.retrieval.reranker import get_reranker

        print("[Warmup] 预加载 Rerank 模型...")
        try:
            get_reranker()
        except Exception as exc:
            print(f"[Warmup] Rerank 预加载失败，将在首次提问时重试: {exc}")

    print("[Warmup] 模型预加载完成")
