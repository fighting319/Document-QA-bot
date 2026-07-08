"""Download BGE embedding models via ModelScope (see app/retrieval/model_loader.py)."""

from app.config import EMBED_MODELS
from app.retrieval.model_loader import resolve_local_model_path

if __name__ == "__main__":
    for model_name in EMBED_MODELS:
        print(f"准备模型: {model_name}")
        path = resolve_local_model_path(model_name)
        print(f"  -> {path}\n")
    print("Embedding 模型就绪。")
