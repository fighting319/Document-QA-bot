"""LlamaIndex reader: pdfplumber first, optional LlamaParse fallback."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from llama_index.core import Document
from llama_index.core.readers.base import BaseReader

from app.ingestion.parse_quality import assess_parse_quality, is_better_parse
from app.ingestion.pdf_parser import extract_pdf_text, pdf_is_image_only


def _load_with_llamaparse(file_path: Path) -> str:
    api_key = os.getenv("LLAMA_API_KEY", "").strip()
    if not api_key:
        return ""

    try:
        from llama_parse import LlamaParse

        parser = LlamaParse(api_key=api_key, result_type="markdown")
        docs = parser.load_data(str(file_path))
        if not docs:
            return ""
        return "\n\n".join(doc.text for doc in docs if getattr(doc, "text", None))
    except Exception as exc:
        print(f"[Parser] LlamaParse fallback 失败: {exc}")
        return ""


class HybridPdfReader(BaseReader):
    """PDF: pdfplumber (+ quality check) -> LlamaParse fallback if configured."""

    def load_data(self, file: Path, extra_info: dict | None = None, **kwargs: Any) -> list[Document]:
        file_path = Path(file)
        extra_info = dict(extra_info or {})
        extra_info.setdefault("file_name", file_path.name)

        text = extract_pdf_text(file_path)
        quality = assess_parse_quality(text)
        parser_used = "pdfplumber"

        print(
            f"[Parser] pdfplumber: {file_path.name} | "
            f"len={quality.length} cjk={quality.cjk_ratio:.1%} "
            f"garbage={quality.garbage_ratio:.1%} | {quality.reason}"
        )

        if not quality.ok:
            fallback_text = _load_with_llamaparse(file_path)
            if fallback_text:
                fallback_quality = assess_parse_quality(fallback_text)
                print(
                    f"[Parser] LlamaParse fallback: {file_path.name} | "
                    f"len={fallback_quality.length} cjk={fallback_quality.cjk_ratio:.1%} "
                    f"garbage={fallback_quality.garbage_ratio:.1%} | {fallback_quality.reason}"
                )
                if is_better_parse(fallback_quality, quality):
                    text = fallback_text
                    quality = fallback_quality
                    parser_used = "llamaparse"
                else:
                    print(
                        f"[Parser] LlamaParse fallback 未采用（质量未优于 pdfplumber）: "
                        f"{file_path.name}"
                    )
            elif not quality.ok:
                print(
                    f"[Parser] 警告: {file_path.name} 解析质量较差（{quality.reason}），"
                    "仍将使用 pdfplumber 结果；建议配置 LLAMA_API_KEY 或检查 PDF 源文件"
                )

        extra_info["parser"] = parser_used
        extra_info["parse_quality"] = quality.reason
        extra_info["image_only_pdf"] = pdf_is_image_only(file_path)

        if not text.strip():
            if extra_info["image_only_pdf"]:
                raise ValueError(
                    f"PDF 为扫描件/图片型，无法抽取文字: {file_path.name}。"
                    "请使用带 OCR 的解析方案（如 LlamaParse premium / PaddleOCR）后重新上传。"
                )
            raise ValueError(f"PDF 解析结果为空: {file_path.name}")

        if not quality.ok:
            raise ValueError(
                f"PDF 解析质量未达标: {file_path.name}（{quality.reason}）。"
                "请检查源文件或更换解析方式后重新上传。"
            )

        return [Document(text=text, metadata=extra_info)]
