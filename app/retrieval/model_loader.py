"""Resolve model paths, preferring local cache and ModelScope downloads."""

from __future__ import annotations

import os
from pathlib import Path

from app.config import MODELS_DIR, USE_MODELSCOPE

# ModelScope 缓存目录放在项目内，减少与用户全局缓存的锁冲突
MODELSCOPE_CACHE = MODELS_DIR / ".modelscope"
os.environ.setdefault("MODELSCOPE_CACHE", str(MODELSCOPE_CACHE))

# HuggingFace 模型名 -> ModelScope 模型 ID（BAAI 系列通常一致）
MODELSCOPE_MODEL_IDS: dict[str, str] = {
    "BAAI/bge-reranker-v2-m3": "BAAI/bge-reranker-v2-m3",
    "BAAI/bge-large-zh-v1.5": "BAAI/bge-large-zh-v1.5",
    "BAAI/bge-small-en-v1.5": "BAAI/bge-small-en-v1.5",
}

# 验证模型目录是否有效
def _is_valid_model_dir(path: Path) -> bool:
    if not path.is_dir() or not (path / "config.json").exists():
        return False
    return (path / "model.safetensors").exists() or (path / "pytorch_model.bin").exists()

# 获取本地候选路径
def _local_candidate_paths(model_name: str) -> list[Path]:
    short_name = model_name.split("/")[-1]
    return [
        MODELS_DIR / short_name,
        MODELS_DIR / model_name.replace("/", "--"),
        MODELS_DIR / model_name,
    ]

# 查找本地模型
def _find_local_model(model_name: str) -> Path | None:
    for candidate in _local_candidate_paths(model_name):
        if _is_valid_model_dir(candidate):
            return candidate
    return None

# 从ModelScope下载模型
def _download_from_modelscope(model_name: str, target_dir: Path, max_retries: int = 5) -> Path:
    try:
        from modelscope import snapshot_download
    except ImportError as exc:
        raise ImportError(
            "ModelScope 未安装，请执行: "
            "pip install modelscope -i https://mirrors.aliyun.com/pypi/simple/"
        ) from exc

    modelscope_id = MODELSCOPE_MODEL_IDS.get(model_name, model_name)
    if _is_valid_model_dir(target_dir):
        print(f"[ModelScope] 模型已完整存在，跳过下载: {target_dir}")
        return target_dir

    target_dir.mkdir(parents=True, exist_ok=True)
    temp_file = target_dir / "._____temp" / "model.safetensors"
    if temp_file.exists():
        print(f"[ModelScope] 发现未完成文件 {temp_file.stat().st_size / 1024**2:.0f} MB，将续传...")

    last_error: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            print(f"[ModelScope] 下载 {modelscope_id} -> {target_dir} (第 {attempt}/{max_retries} 次)")
            downloaded_path = snapshot_download(
                modelscope_id,
                local_dir=str(target_dir),
            )
            result = Path(downloaded_path)
            if _is_valid_model_dir(result):
                print(f"[ModelScope] 下载完成: {result}")
                return result
            raise RuntimeError("下载结束但 model.safetensors 仍不存在")
        except Exception as exc:
            last_error = exc
            print(f"[ModelScope] 第 {attempt} 次下载失败: {exc}")
            if attempt < max_retries:
                wait_seconds = attempt * 10
                print(f"[ModelScope] {wait_seconds}s 后重试...")
                import time
                time.sleep(wait_seconds)

    raise RuntimeError(f"ModelScope 下载失败（已重试 {max_retries} 次）: {last_error}") from last_error

# 解析本地模型路径
def resolve_local_model_path(model_name: str) -> str:
    """
    Return a local filesystem path for loading with sentence-transformers / transformers.
    Order: existing local dir -> ModelScope download (if enabled).
    """
    local_model = _find_local_model(model_name)
    if local_model is not None:
        print(f"[本地] 使用本地模型: {local_model}")
        return str(local_model)

    if USE_MODELSCOPE:
        short_name = model_name.split("/")[-1]
        target_dir = MODELS_DIR / short_name
        try:
            downloaded = _download_from_modelscope(model_name, target_dir)
            return str(downloaded)
        except Exception as exc:
            raise RuntimeError(
                f"无法从 ModelScope 获取模型 {model_name}，请检查网络或手动下载到 models/"
            ) from exc

    # USE_MODELSCOPE=False 时回退 HuggingFace Hub（需可访问 huggingface.co）
    print(f"[警告] USE_MODELSCOPE=False，将尝试从 HuggingFace Hub 加载: {model_name}")
    return model_name
