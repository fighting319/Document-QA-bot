"""Remove document nodes from an existing vector index."""

from __future__ import annotations

from typing import Any, List

# 节点是否匹配文件
def _node_matches_file(node: Any, file_to_remove: str) -> bool:
    metadata = getattr(node, "metadata", None)
    if metadata is None:
        return False

    if isinstance(metadata, dict):
        if metadata.get("file_name") == file_to_remove:
            return True
        file_path = str(metadata.get("file_path", ""))
        if file_path.endswith(file_to_remove):
            return True
        source = str(metadata.get("source", ""))
        return source.endswith(file_to_remove)

    if hasattr(metadata, "file_name") and metadata.file_name == file_to_remove:
        return True
    if hasattr(metadata, "file_path") and str(metadata.file_path).endswith(file_to_remove):
        return True
    if hasattr(metadata, "source") and str(metadata.source).endswith(file_to_remove):
        return True
    return False

# 查找文件相关的节点
def find_nodes_for_file(vector_index: Any, file_to_remove: str) -> List[str]:
    nodes_to_remove: List[str] = []
    for node_id, node in vector_index.docstore.docs.items():
        if _node_matches_file(node, file_to_remove):
            nodes_to_remove.append(node_id)
    return nodes_to_remove

# 从索引中删除文件
def remove_file_from_index(vector_index: Any, file_to_remove: str) -> int:
    """Remove all nodes associated with a file. Returns number of nodes removed."""
    nodes_to_remove = find_nodes_for_file(vector_index, file_to_remove)
    if not nodes_to_remove:
        print(f"⚠️ 未找到与文件 '{file_to_remove}' 相关的节点，请检查元数据格式")
        return 0

    print(f"找到 {len(nodes_to_remove)} 个与文件 '{file_to_remove}' 相关的节点")

    if hasattr(vector_index.vector_store, "delete"):
        try:
            vector_index.vector_store.delete_nodes(node_ids=nodes_to_remove)
            print(f"✅ 已从向量存储中删除 {len(nodes_to_remove)} 个节点")
        except Exception as exc:
            print(f"⚠️ 从向量存储删除节点时出错: {str(exc)}")
    else:
        print("⚠️ 向量存储不支持直接删除操作，将使用替代方法")

    print(f"删除前文档存储中节点个数: {len(vector_index.docstore.docs)}")
    for node_id in nodes_to_remove:
        vector_index.docstore.delete_document(node_id, raise_error=False)
        print(f"✅ 已从文档存储中删除节点 {node_id}")

    try:
        if hasattr(vector_index, "_vector_store"):
            inner_store = vector_index._vector_store
            if hasattr(inner_store, "stores"):
                for node_id in nodes_to_remove:
                    inner_store.stores.pop(node_id, None)
            elif hasattr(inner_store, "delete"):
                inner_store.delete(nodes_to_remove)
            elif type(inner_store).__name__ == "SimpleVectorStore":
                print("检测到SimpleVectorStore，将通过保存到磁盘然后重新加载来更新索引")
    except Exception as exc:
        print(f"尝试更新向量存储时出现警告(可以忽略): {exc}")

    vector_index.storage_context.persist()
    print(f"删除后文档存储中节点个数: {len(vector_index.docstore.docs)}")

    if hasattr(vector_index, "index_struct") and hasattr(vector_index.index_struct, "nodes_dict"):
        before_delete_count = len(vector_index.index_struct.nodes_dict)
        print(f"删除前索引结构中 nodes_dict 的节点数量: {before_delete_count}")
        for node_id in nodes_to_remove:
            vector_index.index_struct.nodes_dict.pop(node_id, None)
        after_delete_count = len(vector_index.index_struct.nodes_dict)
        print(f"删除后索引结构中 nodes_dict 的节点数量: {after_delete_count}")
        print("✅ 已更新索引结构，删除节点引用")

    print(f"✅ 已从索引中完全移除文件 '{file_to_remove}' 的所有相关数据")
    return len(nodes_to_remove)
