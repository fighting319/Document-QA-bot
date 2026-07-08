"""Document parsing and file extraction."""

from __future__ import annotations

import os
from typing import Dict

from llama_index.core.readers.base import BaseReader

from app.config import SUPPORTED_FILE_TYPES
from app.ingestion.pdf_reader import HybridPdfReader

_file_extractor: Dict[str, BaseReader] | None = None


def _llamaparse_reader() -> BaseReader:
    from llama_parse import LlamaParse

    return LlamaParse(
        api_key=os.getenv("LLAMA_API_KEY"),
        result_type="markdown",
    )


def build_file_extractor() -> Dict[str, BaseReader]:
    """
    Build per-extension readers.

    - PDF: pdfplumber + quality check (+ optional LlamaParse fallback)
    - Other types: LlamaParse if key set, else LlamaIndex default readers
    """
    extractors: Dict[str, BaseReader] = {".pdf": HybridPdfReader()}

    llama_key = os.getenv("LLAMA_API_KEY", "").strip()
    if llama_key:
        parser = _llamaparse_reader()
        for ext in SUPPORTED_FILE_TYPES:
            if ext != ".pdf":
                extractors[ext] = parser
        print("[Parser] 非 PDF 文件使用 LlamaParse")
    else:
        print(
            "[Parser] 未配置 LLAMA_API_KEY：PDF 使用 pdfplumber；"
            "docx/xlsx 等使用 LlamaIndex 默认解析器"
        )

    return extractors


def get_file_extractor() -> Dict[str, BaseReader]:
    global _file_extractor
    if _file_extractor is None:
        _file_extractor = build_file_extractor()
    return _file_extractor
