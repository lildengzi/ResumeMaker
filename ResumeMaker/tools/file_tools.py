from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List

from tools.permission import ensure_workspace_path


MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_RAW_TEXT_CHARS = 200_000

TEXT_SUFFIXES = {".txt"}
MARKDOWN_SUFFIXES = {".md", ".markdown"}
PDF_SUFFIXES = {".pdf"}


def classify_file_type(path: str | Path, declared_type: str | None = None) -> Dict[str, str]:
    """Return stable downstream type labels for an uploaded file."""
    safe_path = ensure_workspace_path(path)
    suffix = safe_path.suffix.lower()

    if suffix in MARKDOWN_SUFFIXES:
        file_type = "markdown"
    elif suffix in TEXT_SUFFIXES:
        file_type = "text"
    elif suffix in PDF_SUFFIXES:
        file_type = "pdf"
    else:
        file_type = "unsupported"

    if declared_type in {"existing_resume", "resume"}:
        classification = "existing_resume"
    elif declared_type in {"readme", "project_readme", "project"}:
        classification = "project_readme"
    elif file_type == "pdf":
        classification = "pdf_document"
    elif file_type in {"markdown", "text"}:
        classification = "text_document"
    else:
        classification = "unsupported"

    return {
        "file_type": file_type,
        "classification": classification,
        "suffix": suffix,
    }


def _base_metadata(path: Path, declared_type: str | None = None) -> Dict[str, Any]:
    type_info = classify_file_type(path, declared_type)
    size_bytes = path.stat().st_size if path.exists() and path.is_file() else 0
    return {
        "name": path.name,
        "file_name": path.name,
        "path": str(path),
        "type": declared_type or type_info["classification"],
        "file_type": type_info["file_type"],
        "classification": type_info["classification"],
        "suffix": type_info["suffix"],
        "size_bytes": size_bytes,
        "raw_text": "",
        "parse_status": "pending",
        "notes": [],
        "metadata": {},
    }


def _decode_text_bytes(data: bytes) -> tuple[str, str]:
    for encoding in ("utf-8-sig", "utf-8", "gb18030", "cp1252"):
        try:
            return data.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace"), "utf-8-replace"


def _text_stats(text: str) -> Dict[str, int]:
    return {
        "char_count": len(text),
        "line_count": 0 if not text else text.count("\n") + 1,
        "word_count": len(re.findall(r"\S+", text)),
    }


def _extract_personal_info(text: str) -> Dict[str, Any]:
    emails = sorted(set(re.findall(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", text)))
    phones = sorted(
        set(
            match.strip()
            for match in re.findall(r"(?<!\w)(?:\+?\d[\d\s().-]{7,}\d)(?!\w)", text)
        )
    )
    urls = sorted(set(re.findall(r"https?://[^\s)>\]]+", text)))
    linkedin = [url for url in urls if "linkedin.com" in url.lower()]
    github = [url for url in urls if "github.com" in url.lower()]

    first_non_empty_line = ""
    for line in text.splitlines():
        stripped = line.strip(" #\t\r\n")
        if stripped:
            first_non_empty_line = stripped[:120]
            break

    return {
        "candidate_name_hint": first_non_empty_line,
        "emails": emails[:5],
        "phones": phones[:5],
        "urls": urls[:10],
        "linkedin": linkedin[:5],
        "github": github[:5],
    }


def _read_text_file(path: Path, metadata: Dict[str, Any]) -> Dict[str, Any]:
    data = path.read_bytes()
    text, encoding = _decode_text_bytes(data)
    truncated = False
    if len(text) > MAX_RAW_TEXT_CHARS:
        text = text[:MAX_RAW_TEXT_CHARS]
        truncated = True
        metadata["notes"].append(f"Raw text truncated to {MAX_RAW_TEXT_CHARS} characters.")

    metadata["raw_text"] = text
    metadata["parse_status"] = "parsed"
    metadata["metadata"].update(
        {
            "encoding": encoding,
            "truncated": truncated,
            "text_stats": _text_stats(text),
            "personal_info": _extract_personal_info(text),
        }
    )
    return metadata


def _load_pdf_parser():
    try:
        from pypdf import PdfReader  # type: ignore

        return PdfReader, "pypdf"
    except Exception:
        pass

    try:
        from PyPDF2 import PdfReader  # type: ignore

        return PdfReader, "PyPDF2"
    except Exception:
        return None, ""


def _read_pdf_file(path: Path, metadata: Dict[str, Any]) -> Dict[str, Any]:
    reader_cls, parser_name = _load_pdf_parser()
    if reader_cls is None:
        metadata["parse_status"] = "metadata_only"
        metadata["notes"].append(
            "PDF text extraction is unavailable because no lightweight PDF parser is installed."
        )
        metadata["metadata"]["pdf_parser"] = None
        return metadata

    try:
        reader = reader_cls(str(path))
        page_count = len(reader.pages)
        chunks = []
        for page in reader.pages:
            chunks.append(page.extract_text() or "")
        text = "\n".join(chunk for chunk in chunks if chunk)
    except Exception as exc:
        metadata["parse_status"] = "metadata_only"
        metadata["notes"].append(f"PDF parser could not extract text: {exc}")
        metadata["metadata"]["pdf_parser"] = parser_name
        return metadata

    truncated = False
    if len(text) > MAX_RAW_TEXT_CHARS:
        text = text[:MAX_RAW_TEXT_CHARS]
        truncated = True
        metadata["notes"].append(f"PDF text truncated to {MAX_RAW_TEXT_CHARS} characters.")

    metadata["raw_text"] = text
    metadata["parse_status"] = "parsed" if text else "metadata_only"
    if not text:
        metadata["notes"].append("PDF parser was available but no text was extracted.")
    metadata["metadata"].update(
        {
            "pdf_parser": parser_name,
            "page_count": page_count,
            "truncated": truncated,
            "text_stats": _text_stats(text),
            "personal_info": _extract_personal_info(text),
        }
    )
    return metadata


def parse_uploaded_file(file_path: str | Path, declared_type: str | None = None) -> Dict[str, Any]:
    """Parse an uploaded user file into safe metadata and optional raw text."""
    path = ensure_workspace_path(file_path)

    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"File does not exist: {path}")

    metadata = _base_metadata(path, declared_type)
    if metadata["size_bytes"] > MAX_FILE_BYTES:
        metadata["parse_status"] = "skipped"
        metadata["notes"].append(f"File exceeds the {MAX_FILE_BYTES} byte size limit.")
        return metadata

    suffix = metadata["suffix"]
    if suffix in TEXT_SUFFIXES | MARKDOWN_SUFFIXES:
        return _read_text_file(path, metadata)

    if suffix in PDF_SUFFIXES:
        return _read_pdf_file(path, metadata)

    metadata["parse_status"] = "unsupported"
    metadata["notes"].append("Unsupported file type for content parsing.")
    return metadata


def scan_resume_assets(paths: List[str]) -> List[Dict[str, Any]]:
    """Scan uploaded files and return metadata that agents can consume safely."""
    assets: List[Dict[str, Any]] = []

    for raw_path in paths:
        try:
            assets.append(parse_uploaded_file(raw_path))
        except (FileNotFoundError, ValueError):
            continue

    return assets


def parse_uploaded_resume(file_path: str) -> Dict[str, Any]:
    """Parse an uploaded existing resume file."""
    return parse_uploaded_file(file_path, declared_type="existing_resume")
