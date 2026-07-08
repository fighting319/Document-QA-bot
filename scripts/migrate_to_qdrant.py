"""One-time migration: local JSON vectors -> Qdrant (docstore stays in storage/)."""

from __future__ import annotations

import os
import sys
import time

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

BATCH_SIZE = 50


def _migrate_nodes_to_qdrant(nodes, embed_model):
    from llama_index.core import VectorStoreIndex

    from app.kb.vector_store import build_storage_context

    total = len(nodes)
    print(
        f"开始迁移: 共 {total} 个 chunk，每 {BATCH_SIZE} 个打印一次进度 "
        "（需重新 embedding，CPU 上可能需 10~30 分钟）",
        flush=True,
    )

    storage_context = build_storage_context()
    qdrant_index = None
    started = time.time()

    for start in range(0, total, BATCH_SIZE):
        batch = nodes[start : start + BATCH_SIZE]
        batch_no = start // BATCH_SIZE + 1
        batch_total = (total + BATCH_SIZE - 1) // BATCH_SIZE
        print(
            f"[迁移] 批次 {batch_no}/{batch_total}: 正在 embedding {len(batch)} 个 chunk...",
            flush=True,
        )

        if qdrant_index is None:
            qdrant_index = VectorStoreIndex(
                batch,
                storage_context=storage_context,
                embed_model=embed_model,
                store_nodes_override=True,
            )
        else:
            qdrant_index.insert_nodes(batch)

        done = min(start + BATCH_SIZE, total)
        elapsed = time.time() - started
        rate = done / elapsed if elapsed > 0 else 0.0
        remaining = (total - done) / rate if rate > 0 else 0.0
        print(
            f"[迁移] {done}/{total} ({100.0 * done / total:.1f}%) chunk 已写入 Qdrant | "
            f"已用时 {elapsed:.0f}s | 预计剩余 {remaining:.0f}s",
            flush=True,
        )

    return qdrant_index


def main() -> int:
    from pathlib import Path

    from dotenv import load_dotenv

    load_dotenv(Path(PROJECT_ROOT) / ".env")

    from app.kb.vector_store import (
        check_qdrant_connection,
        get_vector_backend,
        load_vector_index,
        persist_qdrant_index,
        reset_qdrant_vector_store_cache,
    )
    from app.retrieval.embedder import get_embed_model

    storage = Path(PROJECT_ROOT) / "storage"
    if not (storage / "docstore.json").exists():
        print("❌ 未找到本地索引 storage/docstore.json，请先建库")
        return 1

    embed_model_path = storage / "embed_model.txt"
    embed_model_name = (
        embed_model_path.read_text(encoding="utf-8").strip()
        if embed_model_path.exists()
        else "BAAI/bge-large-zh-v1.5"
    )

    os.environ["VECTOR_BACKEND"] = "local"
    embed_model = get_embed_model(embed_model_name)
    local_index = load_vector_index(embed_model)
    nodes = list(local_index.docstore.docs.values())
    print(f"读取本地索引: {len(nodes)} 个 chunk", flush=True)

    os.environ["VECTOR_BACKEND"] = "qdrant"
    reset_qdrant_vector_store_cache()
    ok, message = check_qdrant_connection()
    if not ok:
        print(f"❌ {message}")
        print("请先启动 Qdrant，例如: docker compose --profile qdrant up -d")
        return 1

    embed_model = get_embed_model(embed_model_name)
    qdrant_index = _migrate_nodes_to_qdrant(nodes, embed_model)
    qdrant_index._store_nodes_override = True
    print("[迁移] 正在持久化 docstore 元数据...", flush=True)
    qdrant_index.storage_context.persist(persist_dir=str(storage))
    persist_qdrant_index(qdrant_index, embed_model_name)

    print(
        f"✅ 迁移完成 | backend={get_vector_backend()} | "
        f"chunks={len(nodes)} | {message}",
        flush=True,
    )
    print("请在 .env 中设置 VECTOR_BACKEND=qdrant 后重启应用", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
