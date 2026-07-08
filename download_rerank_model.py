"""Pre-download Rerank model via ModelScope (国内镜像)."""

import os
import shutil
import sys
from pathlib import Path

# 将 ModelScope 缓存放到项目内，避免用户目录锁文件冲突
PROJECT_ROOT = Path(__file__).resolve().parent
MODELSCOPE_CACHE = PROJECT_ROOT / "models" / ".modelscope"
os.environ["MODELSCOPE_CACHE"] = str(MODELSCOPE_CACHE)
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

from app.config import MODELS_DIR, RERANK_MODEL
from app.retrieval.model_loader import _is_valid_model_dir, resolve_local_model_path


def _clear_stale_locks() -> None:
    lock_dirs = [
        MODELSCOPE_CACHE / "hub" / ".lock",
        Path.home() / ".cache" / "modelscope" / "hub" / ".lock",
    ]
    for lock_dir in lock_dirs:
        if not lock_dir.exists():
            continue
        for lock_file in lock_dir.glob("*bge-reranker*"):
            try:
                lock_file.unlink(missing_ok=True)
                print(f"[清理] 已移除锁文件: {lock_file}")
            except OSError as exc:
                print(f"[警告] 无法移除锁文件 {lock_file}: {exc}")


def main() -> None:
    target_dir = MODELS_DIR / "bge-reranker-v2-m3"
    if _is_valid_model_dir(target_dir):
        print(f"模型已完整存在: {target_dir}")
        print(f"model.safetensors 大小: {(target_dir / 'model.safetensors').stat().st_size / 1024**3:.2f} GB")
        return

    _clear_stale_locks()
    print(f"开始下载 Rerank 模型: {RERANK_MODEL}")
    print(f"目标目录: {target_dir}")
    if target_dir.exists():
        print("检测到未完成下载，ModelScope 将自动续传...")

    path = resolve_local_model_path(RERANK_MODEL)
    if not _is_valid_model_dir(Path(path)):
        print("[错误] 下载未完成，缺少 model.safetensors")
        sys.exit(1)

    size_gb = (Path(path) / "model.safetensors").stat().st_size / 1024**3
    print(f"模型就绪: {path} ({size_gb:.2f} GB)")


if __name__ == "__main__":
    main()
