"""Embedding model factory with singleton cache."""

from __future__ import annotations

from typing import Dict

from llama_index.embeddings.huggingface import HuggingFaceEmbedding

from app.config import MODELS_DIR
from app.retrieval.model_loader import resolve_local_model_path

_embed_models: Dict[str, HuggingFaceEmbedding] = {}

# 获取嵌入模型
def get_embed_model(model_name: str) -> HuggingFaceEmbedding:
    if model_name not in _embed_models:
        model_path = resolve_local_model_path(model_name)
        print(f"[Embedding] 首次加载模型: {model_name} -> {model_path}")
        _embed_models[model_name] = HuggingFaceEmbedding(
            model_name=model_path,
            cache_folder=str(MODELS_DIR),
            trust_remote_code=True,
        )
    return _embed_models[model_name]

# 清除嵌入模型缓存
def clear_embed_cache(model_name: str | None = None) -> None:
    if model_name is None:
        _embed_models.clear()
    else:
        _embed_models.pop(model_name, None)
