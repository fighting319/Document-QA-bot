"""Document ingestion and vector index building."""

from __future__ import annotations

import os
import traceback
from datetime import datetime
from pathlib import Path
from typing import List

from llama_index.core import SimpleDirectoryReader

from app.config import UPLOAD_DIR
from app.ingestion.chunker import build_nodes
from app.ingestion.parser import get_file_extractor
from app.kb.index_manager import persist_index_after_update
from app.kb.node_removal import remove_file_from_index
from app.kb.vector_store import build_index_from_nodes
from app.retrieval.embedder import get_embed_model
from app.retrieval.retriever_cache import invalidate_hybrid_retriever_cache
from app.state import app_state

# 保存上传的文件
def _save_uploaded_files(
    file_paths: List[str],
    update_existing: bool,
) -> tuple[list[str], list[str], list[str], list[dict]]:
    existing_files = {doc["filename"]: doc for doc in app_state.document_metadata}
    saved_files: List[str] = []
    skipped_files: List[str] = []
    updated_files: List[str] = []
    files_to_remove: List[dict] = []

    for src_path in file_paths:
        if not os.path.exists(src_path):
            print(f"❌ 文件不存在: {src_path}")
            continue

        filename = Path(src_path).name
        print(f"处理文件: {filename}")

        if filename in existing_files:
            if update_existing:
                files_to_remove.append(existing_files[filename])
                updated_files.append(filename)
                print(f"🔄 文件已存在，将更新: {filename}")
            else:
                skipped_files.append(filename)
                print(f"⚠️ 文件已存在，跳过: {filename}")
                continue

        dst_path = UPLOAD_DIR / filename
        try:
            src = Path(src_path)
            if not src.is_file():
                print(f"❌ 不是有效文件: {src_path}")
                continue

            if src.resolve() == dst_path.resolve():
                file_size = src.stat().st_size
                if file_size == 0:
                    print(f"❌ 文件为空（0 字节）: {filename}")
                    continue
                saved_files.append(str(dst_path))
                print(f"✅ 使用已存在文件: {dst_path} ({file_size} 字节)")
            else:
                file_bytes = src.read_bytes()
                if not file_bytes:
                    print(f"❌ 上传文件为空（0 字节）: {filename}")
                    continue
                dst_path.write_bytes(file_bytes)
                saved_files.append(str(dst_path))
                print(f"✅ 成功保存文件: {dst_path} ({len(file_bytes)} 字节)")

            if update_existing and filename in existing_files:
                app_state.document_metadata = [
                    doc for doc in app_state.document_metadata if doc["filename"] != filename
                ]

            app_state.document_metadata.append(
                {
                    "filename": filename,
                    "path": str(dst_path),
                    "upload_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "version": datetime.now().timestamp(),
                }
            )
        except Exception as file_error:
            print(f"❌ 文件保存失败: {filename}")
            print(f"错误详情: {str(file_error)}")

    return saved_files, skipped_files, updated_files, files_to_remove

# 追加到现有索引
def _append_to_existing_index(
    new_documents: list,
    saved_files: List[str],
    embed_model,
    embed_model_name: str,
    files_to_remove: List[dict],
    update_existing: bool,
    reload: bool,
) -> bool:
    if update_existing and files_to_remove and app_state.vector_index is not None:
        try:
            for file_info in files_to_remove:
                file_to_remove = file_info["filename"]
                print(f"🗑️ 尝试从索引中移除旧版本文件: {file_to_remove}")
                remove_file_from_index(app_state.vector_index, file_to_remove)
        except Exception as remove_error:
            print(f"⚠️ 移除旧索引时出错: {str(remove_error)}")
            traceback.print_exc()
            if not reload:
                print("由于删除过程中出现错误，将重建整个索引")
                return True

    nodes = build_nodes(new_documents, embed_model, saved_files)
    print(f"开始将 {len(nodes)} 个 chunk 添加到索引中")
    app_state.vector_index.insert_nodes(nodes)
    for node in nodes:
        print(f"✅ 已添加 chunk: {node.metadata.get('file_name', '未知文件')}")

    print("正在持久化保存更新后的索引...")
    persist_index_after_update(embed_model_name)
    print("✅ 索引和元数据保存完成")
    return False

# 构建结果消息
def _build_result_message(
    saved_files: List[str],
    updated_files: List[str],
    skipped_files: List[str],
    processing_time: float,
    *,
    rebuilt: bool,
) -> str:
    filenames = [Path(path).name for path in saved_files]
    if rebuilt:
        result_msg = f"✅ 成功为 {len(filenames)} 个文件构建和保存知识库索引！"
    else:
        result_msg = f"✅ 成功处理 {len(filenames)} 个文件: {', '.join(filenames)}"

    if updated_files:
        suffix = (
            f"\n🔄 其中 {len(updated_files)} 个文件是更新版本: {', '.join(updated_files)}"
            if not rebuilt
            else f"\n🔄 其中 {len(updated_files)} 个文件是更新版本"
        )
        result_msg += suffix
    if skipped_files:
        result_msg += f"\n⚠️ {len(skipped_files)} 个文件已跳过(已存在): {', '.join(skipped_files)}"

    result_msg += f"\n处理时间: {processing_time:.2f} 秒"
    return result_msg


# 加载文件,两种模式:追加到现有索引或重建整个索引
def load_files(
    file_paths: List[str],
    embed_model_name: str,
    reload: bool = False,
    update_existing: bool = False,
) -> str:
    start_time = datetime.now()
    try:
        if not file_paths:
            return "请选择要上传的文件"

        print("=== 文件加载调试信息 ===")
        print(f"待上传文件路径: {file_paths}")
        print(f"当前已索引文档数: {len(app_state.document_metadata)}")
        print(f"更新模式: {'启用' if update_existing else '禁用'}")
        print(f"已存在的文件: {[doc['filename'] for doc in app_state.document_metadata]}")

        app_state.selected_embed_model_name = embed_model_name
        saved_files, skipped_files, updated_files, files_to_remove = _save_uploaded_files(
            file_paths,
            update_existing,
        )

        if not saved_files:
            if skipped_files:
                return (
                    f"⚠️ 所有文件({', '.join(skipped_files)})已存在于索引中，未进行更新。"
                    "如需更新，请启用'更新已有文件'选项。"
                )
            return "没有文件需要处理"

        embed_model = get_embed_model(embed_model_name)
        try:
            new_documents = SimpleDirectoryReader(
                input_files=saved_files,
                file_extractor=get_file_extractor(),
            ).load_data()
            print(f"成功加载 {len(new_documents)} 个文档")
            for doc in new_documents:
                print(f"文档标题/元数据: {doc.metadata.get('file_name', '未知文件')}")
        except Exception as load_error:
            print(f"❌ 文档加载失败: {str(load_error)}")
            return f"❌ 文档加载错误: {str(load_error)}"

        if not new_documents:
            return "❌ 未能从上传文件中解析出任何内容，请检查文件是否损坏或为空"

        should_rebuild = reload or app_state.vector_index is None
        if not should_rebuild:
            should_rebuild = _append_to_existing_index(
                new_documents,
                saved_files,
                embed_model,
                embed_model_name,
                files_to_remove,
                update_existing,
                reload,
            )
        else:
            print("创建新索引或重建整个索引...")
            nodes = build_nodes(new_documents, embed_model, saved_files)
            if not nodes:
                return "❌ 切块结果为空，请检查文档内容或解析日志"
            app_state.vector_index = build_index_from_nodes(nodes, embed_model)
            persist_index_after_update(embed_model_name)

        invalidate_hybrid_retriever_cache()
        processing_time = (datetime.now() - start_time).total_seconds()
        return _build_result_message(
            saved_files,
            updated_files,
            skipped_files,
            processing_time,
            rebuilt=should_rebuild,
        )
    except Exception as exc:
        print(f"错误详情: {str(exc)}")
        traceback.print_exc()
        processing_time = (datetime.now() - start_time).total_seconds()
        return f"❌ 错误: {str(exc)}\n处理时间: {processing_time:.2f} 秒"
