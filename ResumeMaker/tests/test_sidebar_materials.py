from pathlib import Path

from core.resume_document import create_resume_document
from ui import sidebar


class SessionState(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name, value):
        self[name] = value


def test_material_files_deduplicates_repeated_upload_metadata(monkeypatch):
    duplicate_a = {
        "name": "B-test-report.docx",
        "original_name": "B-test-report.docx",
        "type": "readme",
        "size_bytes": 128,
        "raw_text": "same report",
        "path": "data/uploads/candidate_material_a.docx",
    }
    duplicate_b = {
        **duplicate_a,
        "path": "data/uploads/candidate_material_b.docx",
    }
    other_file = {"name": "jd.png", "type": "jd_image", "path": "data/uploads/jd.png"}
    session_state = SessionState(uploaded_files_meta=[duplicate_a, duplicate_b, other_file])
    monkeypatch.setattr(sidebar.st, "session_state", session_state)

    materials = sidebar._material_files()

    assert len(materials) == 1
    assert materials[0]["path"] == "data/uploads/candidate_material_a.docx"
    assert session_state.uploaded_files_meta == [other_file, materials[0]]


def test_persist_material_files_updates_resume_document_inputs(monkeypatch):
    removed = {"name": "old.docx", "type": "readme", "path": "data/uploads/old.docx"}
    retained_non_material = {"name": "jd.png", "type": "jd_image", "path": "data/uploads/jd.png"}
    kept_material = {"name": "new.docx", "type": "readme", "path": "data/uploads/new.docx"}
    document = create_resume_document(
        {"basics": {"name": "Alice", "headline": "Engineer"}, "modules": [], "style": {}},
        {},
        uploaded_files=[removed, retained_non_material],
    )
    session_state = SessionState(
        uploaded_files_meta=[removed, retained_non_material],
        resume_document=document,
    )
    monkeypatch.setattr(sidebar.st, "session_state", session_state)

    sidebar._persist_material_files([kept_material])

    expected = [retained_non_material, kept_material]
    assert session_state.uploaded_files_meta == expected
    assert document["inputs"]["uploaded_files"] == expected


def test_file_fingerprint_changes_when_content_changes():
    first = sidebar._file_fingerprint("B-test-report.docx", b"first")
    second = sidebar._file_fingerprint("B-test-report.docx", b"second")

    assert first != second


def test_material_fingerprint_uses_saved_file_bytes_when_available():
    upload_dir = Path("data/uploads")
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_path = upload_dir / "sidebar_material_test.docx"
    file_path.write_bytes(b"original bytes")

    try:
        fingerprint = sidebar._material_fingerprint(
            {
                "name": "B-test-report.docx",
                "original_name": "B-test-report.docx",
                "type": "readme",
                "path": str(file_path),
                "raw_text": "parsed text",
            }
        )

        assert fingerprint == sidebar._file_fingerprint("B-test-report.docx", b"original bytes")
    finally:
        file_path.unlink(missing_ok=True)
