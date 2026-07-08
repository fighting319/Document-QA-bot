"""PDF text and table extraction via pdfplumber."""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path


def _clean_text(text: str) -> str:
    """Light cleanup while preserving line breaks for chunking."""
    if not text:
        return ""
    text = "".join(ch for ch in text if unicodedata.category(ch)[0] != "C")
    text = text.replace("\u200b", "").replace("\ufeff", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _table_to_markdown(table: list[list]) -> str:
    if not table:
        return ""
    rows = [[(cell or "").strip().replace("\n", " ") for cell in row] for row in table]
    rows = [row for row in rows if any(cell for cell in row)]
    if not rows:
        return ""

    lines = ["\n| " + " | ".join(rows[0]) + " |"]
    lines.append("| " + " | ".join(["---"] * len(rows[0])) + " |")
    for row in rows[1:]:
        if len(row) < len(rows[0]):
            row = row + [""] * (len(rows[0]) - len(row))
        lines.append("| " + " | ".join(row[: len(rows[0])]) + " |")
    return "\n".join(lines)


def pdf_is_image_only(pdf_path: str | Path, sample_pages: int = 3) -> bool:
    """Return True when PDF pages have almost no extractable text layer."""
    try:
        import pdfplumber
    except ImportError:
        return False

    path = Path(pdf_path)
    with pdfplumber.open(path) as pdf:
        if not pdf.pages:
            return False
        for page in pdf.pages[:sample_pages]:
            if len(page.chars or []) > 20:
                return False
            text = (page.extract_text() or "").strip()
            if len(text) > 40:
                return False
    return True


def extract_pdf_text(pdf_path: str | Path) -> str:
    """Extract body text and tables from a PDF using pdfplumber."""
    try:
        import pdfplumber
    except ImportError as exc:
        raise ImportError("请安装 pdfplumber: pip install pdfplumber") from exc

    path = Path(pdf_path)
    parts: list[str] = []

    with pdfplumber.open(path) as pdf:
        for page_no, page in enumerate(pdf.pages, start=1):
            page_parts: list[str] = []

            page_text = page.extract_text(x_tolerance=3, y_tolerance=3) or ""
            page_text = _clean_text(page_text)
            if page_text:
                page_parts.append(page_text)

            for table in page.extract_tables() or []:
                md = _table_to_markdown(table)
                if md:
                    page_parts.append(md)

            if page_parts:
                parts.append(f"## 第{page_no}页\n\n" + "\n\n".join(page_parts))

    return "\n\n".join(parts).strip()
