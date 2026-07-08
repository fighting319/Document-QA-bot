"""Vector index backend: local JSON (default) or external Qdrant."""

from __future__ import annotations

import json
import os
from typing import Any

from llama_index.core import StorageContext, VectorStoreIndex, load_index_from_storage

from app.config import PERSIST_DIR

_qdrant_vector_store: Any = None


def get_vector_backend() -> str:
    return os.getenv("VECTOR_BACKEND", "local").strip().lower()


def is_qdrant_backend() -> bool:
    return get_vector_backend() == "qdrant"


def _qdrant_url() -> str:
    return os.getenv("QDRANT_URL", "http://localhost:6333").strip()


def _qdrant_collection() -> str:
    return os.getenv("QDRANT_COLLECTION", "docbot_chunks").strip()


def _qdrant_api_key() -> str | None:
    value = os.getenv("QDRANT_API_KEY", "").strip()
    return value or None


def _require_qdrant_packages() -> None:
    try:
        import qdrant_client  # noqa: F401
        from llama_index.vector_stores.qdrant import QdrantVectorStore  # noqa: F401
    except ImportError as exc:
        raise ImportError(
            "Qdrant 后端需要安装: pip install llama-index-vector-stores-qdrant==0.3.3 qdrant-client"
        ) from exc


def get_qdrant_client():
    _require_qdrant_packages()
    from qdrant_client import QdrantClient

    return QdrantClient(url=_qdrant_url(), api_key=_qdrant_api_key())


def create_qdrant_vector_store():
    global _qdrant_vector_store
    if _qdrant_vector_store is not None:
        return _qdrant_vector_store

    _require_qdrant_packages()
    from llama_index.vector_stores.qdrant import QdrantVectorStore
    from qdrant_client import AsyncQdrantClient, QdrantClient

    url = _qdrant_url()
    api_key = _qdrant_api_key()
    client = QdrantClient(url=url, api_key=api_key)
    # QueryFusionRetriever 默认 async 检索，需要 aclient
    aclient = AsyncQdrantClient(url=url, api_key=api_key)

    _qdrant_vector_store = QdrantVectorStore(
        client=client,
        aclient=aclient,
        collection_name=_qdrant_collection(),
    )
    return _qdrant_vector_store


def reset_qdrant_vector_store_cache() -> None:
    global _qdrant_vector_store
    _qdrant_vector_store = None


def check_qdrant_connection() -> tuple[bool, str]:
    if not is_qdrant_backend():
        return True, "local"
    try:
        client = get_qdrant_client()
        client.get_collections()
        return True, f"Qdrant OK ({_qdrant_url()}, collection={_qdrant_collection()})"
    except Exception as exc:
        return False, f"无法连接 Qdrant ({_qdrant_url()}): {exc}"


def read_saved_vector_backend() -> str | None:
    config_path = PERSIST_DIR / "index_config.json"
    if not config_path.exists():
        return None
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    backend = payload.get("vector_backend")
    return str(backend).strip().lower() if backend else None


def _persist_dir_has_docstore() -> bool:
    return (PERSIST_DIR / "docstore.json").exists()


def build_storage_context():
    if is_qdrant_backend():
        ok, message = check_qdrant_connection()
        if not ok:
            raise ConnectionError(message)
        print(f"[Index] 向量后端: Qdrant | {message}")
        kwargs: dict[str, Any] = {"vector_store": create_qdrant_vector_store()}
        if _persist_dir_has_docstore():
            kwargs["persist_dir"] = str(PERSIST_DIR)
        else:
            print("[Index] 未找到 storage/docstore.json，将创建新的 docstore")
        return StorageContext.from_defaults(**kwargs)

    print("[Index] 向量后端: local (storage/*.json)")
    if _persist_dir_has_docstore():
        return StorageContext.from_defaults(persist_dir=str(PERSIST_DIR))
    return StorageContext.from_defaults()


def build_index_from_nodes(nodes, embed_model) -> VectorStoreIndex:
    storage_context = build_storage_context()
    # Qdrant 默认 stores_text=True 时不写 docstore；BM25 需要本地文本
    kwargs: dict[str, Any] = {}
    if is_qdrant_backend():
        kwargs["store_nodes_override"] = True
    return VectorStoreIndex(
        nodes,
        storage_context=storage_context,
        embed_model=embed_model,
        **kwargs,
    )


def _pick_index_id(storage_context) -> str:
    saved = read_saved_index_id()
    if saved:
        try:
            storage_context.index_store.get_index_struct(saved)
            return saved
        except ValueError:
            pass

    best_id = ""
    best_count = -1
    for index_struct in storage_context.index_store.index_structs():
        nodes_dict = getattr(index_struct, "nodes_dict", None) or {}
        count = len(nodes_dict)
        if count > best_count:
            best_count = count
            best_id = index_struct.index_id

    if not best_id:
        raise FileNotFoundError("index_store 中未找到可用索引，请重新上传文档建库")
    return best_id


def read_saved_index_id() -> str | None:
    config_path = PERSIST_DIR / "index_config.json"
    if not config_path.exists():
        return None
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    index_id = payload.get("index_id")
    return str(index_id).strip() if index_id else None


def _prune_index_store(storage_context, keep_index_id: str) -> None:
    for index_struct in storage_context.index_store.index_structs():
        if index_struct.index_id != keep_index_id:
            storage_context.index_store.delete_index_struct(index_struct.index_id)


def load_vector_index(embed_model) -> VectorStoreIndex:
    if is_qdrant_backend():
        ok, message = check_qdrant_connection()
        if not ok:
            raise ConnectionError(message)
        print(f"[Index] 从 Qdrant 加载向量索引 | {message}")
        if not _persist_dir_has_docstore():
            raise FileNotFoundError(
                "未找到 storage/docstore.json。请先上传文档建库，或从 local 索引迁移。"
            )
        storage_context = StorageContext.from_defaults(
            vector_store=create_qdrant_vector_store(),
            persist_dir=str(PERSIST_DIR),
        )
        index_id = _pick_index_id(storage_context)
        index = load_index_from_storage(
            storage_context=storage_context,
            embed_model=embed_model,
            index_id=index_id,
        )
        index._store_nodes_override = True
        print(
            f"[Index] 已加载 index_id={index_id} | docstore={len(index.docstore.docs)} 个 chunk"
        )
        return index

    print("[Index] 从本地 storage/ 加载向量索引")
    if not _persist_dir_has_docstore():
        raise FileNotFoundError("未找到 storage/docstore.json，请先上传文档建库。")
    storage_context = StorageContext.from_defaults(persist_dir=str(PERSIST_DIR))
    return load_index_from_storage(storage_context=storage_context, embed_model=embed_model)


def persist_vector_backend_metadata(
    embed_model_name: str,
    index_id: str | None = None,
) -> None:
    config_path = PERSIST_DIR / "index_config.json"
    payload: dict[str, Any] = {}
    if config_path.exists():
        try:
            payload = json.loads(config_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            payload = {}

    payload.update(
        {
            "vector_backend": get_vector_backend(),
            "qdrant_url": _qdrant_url() if is_qdrant_backend() else None,
            "qdrant_collection": _qdrant_collection() if is_qdrant_backend() else None,
            "embed_model": embed_model_name,
            "index_id": index_id,
        }
    )
    config_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def persist_qdrant_index(index: VectorStoreIndex, embed_model_name: str) -> None:
    """Persist docstore/index_store locally and vectors in Qdrant."""
    index.storage_context.persist(persist_dir=str(PERSIST_DIR))
    if is_qdrant_backend():
        _prune_index_store(index.storage_context, index.index_id)
        index.storage_context.persist(persist_dir=str(PERSIST_DIR))
    persist_vector_backend_metadata(embed_model_name, index_id=index.index_id)


def clear_external_vector_data() -> str:
    if not is_qdrant_backend():
        return ""

    reset_qdrant_vector_store_cache()
    client = get_qdrant_client()
    if client.collection_exists(_qdrant_collection()):
        client.delete_collection(_qdrant_collection())
        return f"已清空 Qdrant collection: {_qdrant_collection()}"
    return f"Qdrant collection 不存在，跳过: {_qdrant_collection()}"
