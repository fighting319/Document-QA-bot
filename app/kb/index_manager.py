"""Knowledge-base index persistence and debugging utilities."""

from __future__ import annotations

import gc
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from app.config import PERSIST_DIR, UPLOAD_DIR
from app.kb.vector_store import (
    clear_external_vector_data,
    is_qdrant_backend,
    load_vector_index,
    persist_qdrant_index,
    reset_qdrant_vector_store_cache,
)
from app.retrieval.embedder import get_embed_model
from app.retrieval.retriever_cache import invalidate_hybrid_retriever_cache
from app.state import app_state

# 持久化元数据
def _persist_metadata(embed_model_name: str) -> None:
    (PERSIST_DIR / "embed_model.txt").write_text(embed_model_name, encoding="utf-8")
    with open(PERSIST_DIR / "document_metadata.json", "w", encoding="utf-8") as file:
        json.dump(app_state.document_metadata, file, ensure_ascii=False)

# 加载已有索引
def load_existing_index() -> str:
    try:
        if not PERSIST_DIR.exists() or not any(PERSIST_DIR.iterdir()):
            return "❌ 没有找到已有的索引"

        embed_model_path = PERSIST_DIR / "embed_model.txt"
        if embed_model_path.exists():
            app_state.selected_embed_model_name = embed_model_path.read_text(encoding="utf-8").strip()

        metadata_path = PERSIST_DIR / "document_metadata.json"
        if metadata_path.exists():
            with open(metadata_path, encoding="utf-8") as file:
                app_state.document_metadata = json.load(file)

        from app.kb.vector_store import get_vector_backend as _get_vector_backend
        from app.kb.vector_store import read_saved_vector_backend as _read_saved_vector_backend

        saved_backend = _read_saved_vector_backend()
        current_backend = _get_vector_backend()
        if saved_backend and saved_backend != current_backend:
            print(
                f"[Index] 警告: 索引保存时使用 {saved_backend}，"
                f"当前 VECTOR_BACKEND={current_backend}，可能导致加载失败或检索异常"
            )

        embed_model = get_embed_model(app_state.selected_embed_model_name)
        app_state.vector_index = load_vector_index(embed_model)

        try:
            retriever = app_state.vector_index.as_retriever(similarity_top_k=1)
            nodes = retriever.retrieve("测试查询")
            print(f"索引加载验证 - 检索到 {len(nodes)} 个节点")
        except Exception as test_exc:
            print(f"索引加载验证失败: {str(test_exc)}")

        invalidate_hybrid_retriever_cache()
        backend = "Qdrant" if is_qdrant_backend() else "local"
        return (
            f"✅ 成功加载已有索引！embedding: {app_state.selected_embed_model_name} | "
            f"向量后端: {backend}"
        )
    except Exception as exc:
        print(f"加载索引出错详情: {str(exc)}")
        return f"❌ 加载索引时出错: {str(exc)}"

# 保存索引
def save_index() -> str:
    if app_state.vector_index is None:
        return "❌ 没有可保存的索引"

    (PERSIST_DIR / "embed_model.txt").write_text(app_state.selected_embed_model_name, encoding="utf-8")
    (PERSIST_DIR / "saved_timestamp.txt").write_text(str(datetime.now()), encoding="utf-8")
    with open(PERSIST_DIR / "document_metadata.json", "w", encoding="utf-8") as file:
        json.dump(app_state.document_metadata, file, ensure_ascii=False)

    persist_qdrant_index(app_state.vector_index, app_state.selected_embed_model_name)
    config_path = PERSIST_DIR / "index_config.json"
    payload: dict[str, Any] = {}
    if config_path.exists():
        try:
            payload = json.loads(config_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            payload = {}
    payload.update(
        {
            "saved_time": str(datetime.now()),
            "index_info": "vector_index",
            "document_count": len(app_state.document_metadata),
            "vector_backend": "qdrant" if is_qdrant_backend() else "local",
        }
    )
    config_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    return f"✅ 索引已完全保存 | 使用的embedding模型: {app_state.selected_embed_model_name}"

# 清除所有存储
def clear_all_storage() -> str:
    qdrant_msg = clear_external_vector_data()
    for file_path in PERSIST_DIR.glob("*"):
        if file_path.is_file():
            file_path.unlink()
    reset_index_cache()
    message = "🗑️ 索引数据已清除（storage/ + Qdrant）；uploads/ 原始文件已保留"
    if qdrant_msg:
        message += f"\n{qdrant_msg}"
    return message

# 重置索引缓存
def reset_index_cache() -> str:
    app_state.reset()
    reset_qdrant_vector_store_cache()
    invalidate_hybrid_retriever_cache()
    gc.collect()
    return "索引和缓存已重置"

# 获取已索引文件
def get_indexed_files() -> str:
    if not app_state.document_metadata:
        return "当前没有索引文件"

    file_list = "\n".join(
        f"{index + 1}. {doc['filename']} (上传时间: {doc['upload_time']})"
        for index, doc in enumerate(app_state.document_metadata)
    )
    return f"当前已索引 {len(app_state.document_metadata)} 个文件:\n{file_list}"

# 调试索引
def debug_index() -> str:
    if app_state.vector_index is None:
        return "当前没有加载任何索引"

    try:
        nodes = app_state.vector_index.docstore.docs.values()
        node_count = len(list(nodes))

        embed_info = f"当前embedding模型: {app_state.selected_embed_model_name}"
        doc_info = f"已加载文档: {len(app_state.document_metadata)}个"
        if app_state.document_metadata:
            doc_names = [doc["filename"] for doc in app_state.document_metadata]
            doc_info += f"\n文档列表: {', '.join(doc_names)}"

        embed_model = get_embed_model(app_state.selected_embed_model_name)
        retriever = app_state.vector_index.as_retriever(
            embed_model=embed_model,
            similarity_top_k=1,
        )
        nodes = retriever.retrieve("测试")
        preview = nodes[0].get_content()[:80].replace("\n", " ") if nodes else "（无结果）"

        return (
            f"索引状态: 包含{node_count}个文档片段\n"
            f"{embed_info}\n{doc_info}\n"
            f"抽样检索: {preview}..."
        )
    except Exception as exc:
        return f"调试索引时出错: {str(exc)}"

# 调试文件更新
def debug_file_updates() -> str:
    if app_state.vector_index is None:
        return "当前没有加载任何索引"

    try:
        all_nodes = list(app_state.vector_index.docstore.docs.values())
        file_info: dict[str, int] = {}

        for node in all_nodes:
            metadata = getattr(node, "metadata", None)
            if not metadata:
                continue

            file_name = None
            if isinstance(metadata, dict) and "file_name" in metadata:
                file_name = metadata["file_name"]
            elif hasattr(metadata, "file_name"):
                file_name = metadata.file_name

            if file_name:
                file_info[file_name] = file_info.get(file_name, 0) + 1

        metadata_files: dict[str, dict[str, Any]] = {}
        for doc in app_state.document_metadata:
            filename = doc["filename"]
            if filename not in metadata_files:
                metadata_files[filename] = {
                    "count": 0,
                    "upload_time": doc.get("upload_time", "Unknown"),
                    "version": doc.get("version", "Unknown"),
                }
            metadata_files[filename]["count"] += 1

        report = "=== 文件更新调试信息 ===\n\n"
        report += "索引内文档节点统计:\n"
        for filename, count in file_info.items():
            report += f"- {filename}: {count} 个节点\n"

        report += "\n文档元数据信息:\n"
        for filename, info in metadata_files.items():
            report += (
                f"- {filename}: 上传时间={info['upload_time']}, 版本={info['version']}\n"
            )

        index_filenames = set(file_info.keys())
        metadata_filenames = set(metadata_files.keys())
        if index_filenames != metadata_filenames:
            report += "\n⚠️ 发现索引与元数据不一致:\n"
            only_in_index = index_filenames - metadata_filenames
            only_in_metadata = metadata_filenames - index_filenames
            if only_in_index:
                report += f"- 仅在索引中存在: {', '.join(only_in_index)}\n"
            if only_in_metadata:
                report += f"- 仅在元数据中存在: {', '.join(only_in_metadata)}\n"

        return report
    except Exception as exc:
        return f"调试文件更新时出错: {str(exc)}"

# 获取存储信息HTML
def get_storage_info_html() -> str:
    return (
        f"<div style='color: #666; font-size: 0.8em'>"
        f"存储位置: ./storage/ (docstore) + "
        f"{'Qdrant' if is_qdrant_backend() else 'local JSON'} (vectors)<br>"
        f"当前使用的embedding模型: {app_state.selected_embed_model_name}<br>"
        f"已加载文档数量: {len(app_state.document_metadata)}<br>"
        f"上次更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>"
    )

# 持久化索引后更新
def persist_index_after_update(embed_model_name: str) -> None:
    if app_state.vector_index is None:
        return
    persist_qdrant_index(app_state.vector_index, embed_model_name)
    _persist_metadata(embed_model_name)
