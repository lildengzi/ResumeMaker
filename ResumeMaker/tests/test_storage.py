from pathlib import Path

from core.data import get_default_resume_data
from core.storage import load_workspace, save_workspace


def test_workspace_storage_persists_resume_photo_and_materials():
    db_path = Path("data/parser_test_app.db")
    db_path.unlink(missing_ok=True)
    photo_path = Path("data/uploads/parser_test_photo.jpg")
    material_path = Path("data/uploads/parser_test_material.md")
    photo_path.parent.mkdir(parents=True, exist_ok=True)
    photo_path.write_bytes(b"photo")
    material_path.write_text("Project evidence", encoding="utf-8")

    resume = get_default_resume_data()
    resume["basics"]["name"] = "Alice"
    resume["basics"]["photo_path"] = str(photo_path)
    resume["inputs"] = {
        "jd_text": "Tutor role",
        "uploaded_files": [
            {
                "name": "parser_test_material.md",
                "type": "readme",
                "path": str(material_path),
                "raw_text": "Project evidence",
                "parse_status": "parsed",
                "material_title": "Project proof",
                "material_category": "project",
            }
        ],
    }

    try:
        save_workspace(resume, db_path=db_path)
        loaded = load_workspace(db_path=db_path)

        assert loaded["basics"]["name"] == "Alice"
        assert loaded["basics"]["photo_path"].endswith("parser_test_photo.jpg")
        assert loaded["inputs"]["jd_text"] == "Tutor role"
        assert loaded["inputs"]["uploaded_files"][0]["material_title"] == "Project proof"
        assert loaded["inputs"]["uploaded_files"][0]["raw_text"] == "Project evidence"

        loaded["inputs"]["uploaded_files"] = []
        save_workspace(loaded, db_path=db_path)
        reloaded = load_workspace(db_path=db_path)

        assert reloaded["inputs"]["uploaded_files"] == []
    finally:
        db_path.unlink(missing_ok=True)
        photo_path.unlink(missing_ok=True)
        material_path.unlink(missing_ok=True)

