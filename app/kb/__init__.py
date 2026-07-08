"""Knowledge-base index management."""

from app.kb.index_manager import (
    clear_all_storage,
    debug_file_updates,
    debug_index,
    get_indexed_files,
    load_existing_index,
    reset_index_cache,
    save_index,
)

__all__ = [
    "clear_all_storage",
    "debug_file_updates",
    "debug_index",
    "get_indexed_files",
    "load_existing_index",
    "reset_index_cache",
    "save_index",
]
