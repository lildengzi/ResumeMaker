from __future__ import annotations

from pathlib import Path

import pytest

from tools import file_tools
from tools.file_tools import parse_uploaded_file, parse_uploaded_resume, scan_resume_assets


@pytest.fixture(autouse=True)
def clean_parser_test_uploads():
    yield
    for path in Path("data/uploads").glob("parser_test_*"):
        if path.is_file():
            path.unlink()


def test_parse_markdown_resume_extracts_text_and_personal_metadata(tmp_path):
    upload_dir = Path("data/uploads")
    upload_dir.mkdir(parents=True, exist_ok=True)
    resume_path = upload_dir / "parser_test_resume.md"
    resume_path.write_text(
        "# Alice Zhang\nalice@example.com\n+1 415 555 0199\nhttps://github.com/alice\n",
        encoding="utf-8",
    )

    parsed = parse_uploaded_resume(str(resume_path))

    assert parsed["type"] == "existing_resume"
    assert parsed["classification"] == "existing_resume"
    assert parsed["file_type"] == "markdown"
    assert parsed["parse_status"] == "parsed"
    assert "# Alice Zhang" in parsed["raw_text"]
    personal_info = parsed["metadata"]["personal_info"]
    assert personal_info["candidate_name_hint"] == "Alice Zhang"
    assert personal_info["emails"] == ["alice@example.com"]
    assert "https://github.com/alice" in personal_info["github"]


def test_parse_text_uses_encoding_fallback(tmp_path):
    upload_dir = Path("data/uploads")
    upload_dir.mkdir(parents=True, exist_ok=True)
    text_path = upload_dir / "parser_test_notes.txt"
    text_path.write_bytes(b"Caf\xe9 resume\nBackend work")

    parsed = parse_uploaded_file(text_path, declared_type="readme")

    assert parsed["classification"] == "project_readme"
    assert parsed["file_type"] == "text"
    assert parsed["parse_status"] == "parsed"
    assert "Caf\u00e9 resume" in parsed["raw_text"]
    assert parsed["metadata"]["encoding"] == "cp1252"


def test_parse_file_rejects_paths_outside_workspace(tmp_path):
    outside_file = tmp_path / "outside.md"
    outside_file.write_text("# Outside", encoding="utf-8")

    with pytest.raises(ValueError):
        parse_uploaded_file(outside_file)


def test_parse_large_file_skips_raw_text(monkeypatch):
    upload_dir = Path("data/uploads")
    upload_dir.mkdir(parents=True, exist_ok=True)
    large_path = upload_dir / "parser_test_large.md"
    large_path.write_text("small body", encoding="utf-8")
    monkeypatch.setattr(file_tools, "MAX_FILE_BYTES", 1)

    parsed = parse_uploaded_file(large_path)

    assert parsed["parse_status"] == "skipped"
    assert parsed["raw_text"] == ""
    assert "size limit" in parsed["notes"][0]


def test_parse_pdf_returns_metadata_when_parser_unavailable(monkeypatch):
    upload_dir = Path("data/uploads")
    upload_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = upload_dir / "parser_test_resume.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%%EOF")
    monkeypatch.setattr(file_tools, "_load_pdf_parser", lambda: (None, ""))

    parsed = parse_uploaded_resume(str(pdf_path))

    assert parsed["file_type"] == "pdf"
    assert parsed["parse_status"] == "metadata_only"
    assert parsed["raw_text"] == ""
    assert parsed["metadata"]["pdf_parser"] is None
    assert "PDF text extraction is unavailable" in parsed["notes"][0]


def test_scan_resume_assets_skips_missing_and_unsafe_paths(tmp_path):
    upload_dir = Path("data/uploads")
    upload_dir.mkdir(parents=True, exist_ok=True)
    readme_path = upload_dir / "parser_test_scan.md"
    readme_path.write_text("Project README", encoding="utf-8")
    outside_file = tmp_path / "outside.md"
    outside_file.write_text("# Outside", encoding="utf-8")

    assets = scan_resume_assets([str(readme_path), str(outside_file), "data/uploads/missing.md"])

    assert [asset["name"] for asset in assets] == ["parser_test_scan.md"]
    assert assets[0]["parse_status"] == "parsed"
