from __future__ import annotations

import json
import hashlib
import sqlite3
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List
from uuid import uuid4

from config import get_path_from_storage
from core.data import ensure_resume_shape, get_default_resume_data, normalize_inputs, normalize_uploaded_file_meta
from tools.permission import ensure_workspace_path


DEFAULT_WORKSPACE_ID = "default"
SCHEMA_VERSION = 1


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_database_path() -> Path:
    return get_path_from_storage("database_file")


def _connect(db_path: Path | None = None) -> sqlite3.Connection:
    path = ensure_workspace_path(db_path or get_database_path())
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _dump_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _load_json(value: str | None, fallback: Any) -> Any:
    if not value:
        return deepcopy(fallback)
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return deepcopy(fallback)


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS schema_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS workspaces (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            resume_json TEXT NOT NULL,
            style_json TEXT NOT NULL,
            inputs_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS assets (
            id TEXT PRIMARY KEY,
            workspace_id TEXT NOT NULL,
            kind TEXT NOT NULL,
            original_name TEXT NOT NULL,
            stored_path TEXT NOT NULL,
            mime_type TEXT NOT NULL DEFAULT '',
            suffix TEXT NOT NULL DEFAULT '',
            size_bytes INTEGER NOT NULL DEFAULT 0,
            sha256 TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            FOREIGN KEY(workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS materials (
            id TEXT PRIMARY KEY,
            workspace_id TEXT NOT NULL,
            asset_id TEXT,
            title TEXT NOT NULL,
            category TEXT NOT NULL,
            raw_text TEXT NOT NULL DEFAULT '',
            tags_json TEXT NOT NULL DEFAULT '[]',
            structured_json TEXT NOT NULL DEFAULT '{}',
            metadata_json TEXT NOT NULL DEFAULT '{}',
            file_meta_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
            FOREIGN KEY(asset_id) REFERENCES assets(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS workflow_runs (
            id TEXT PRIMARY KEY,
            workspace_id TEXT NOT NULL,
            status TEXT NOT NULL,
            jd_text TEXT NOT NULL DEFAULT '',
            input_signature TEXT NOT NULL DEFAULT '',
            started_at TEXT NOT NULL,
            finished_at TEXT,
            FOREIGN KEY(workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS workflow_logs (
            id TEXT PRIMARY KEY,
            run_id TEXT,
            workspace_id TEXT NOT NULL,
            agent TEXT NOT NULL DEFAULT 'workflow',
            message_key TEXT NOT NULL DEFAULT '',
            message TEXT NOT NULL DEFAULT '',
            details_json TEXT NOT NULL DEFAULT '[]',
            raw_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            FOREIGN KEY(run_id) REFERENCES workflow_runs(id) ON DELETE CASCADE,
            FOREIGN KEY(workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE
        );
        """
    )
    conn.execute(
        "INSERT OR REPLACE INTO schema_meta(key, value) VALUES (?, ?)",
        ("schema_version", str(SCHEMA_VERSION)),
    )
    conn.commit()


def _material_id_from_meta(file_meta: Dict[str, Any]) -> str:
    raw_id = str(file_meta.get("id") or file_meta.get("material_id") or "").strip()
    if raw_id:
        return raw_id
    stable_source = str(file_meta.get("path") or file_meta.get("name") or uuid4().hex)
    return f"mat_{hashlib.sha256(stable_source.encode('utf-8')).hexdigest()[:16]}"


def _asset_id_from_meta(file_meta: Dict[str, Any]) -> str:
    raw_id = str(file_meta.get("asset_id") or "").strip()
    if raw_id:
        return raw_id
    stable_source = str(file_meta.get("path") or file_meta.get("name") or uuid4().hex)
    return f"asset_{hashlib.sha256(stable_source.encode('utf-8')).hexdigest()[:16]}"


def _upsert_materials(conn: sqlite3.Connection, workspace_id: str, uploaded_files: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    materials: List[Dict[str, Any]] = []
    seen_ids: set[str] = set()
    now = utc_now()

    for raw_meta in uploaded_files:
        file_meta = normalize_uploaded_file_meta(raw_meta)
        if not file_meta or file_meta.get("type") != "readme":
            continue

        material_id = _material_id_from_meta(file_meta)
        asset_id = _asset_id_from_meta(file_meta)
        seen_ids.add(material_id)

        title = str(file_meta.get("material_title") or Path(str(file_meta.get("name") or "")).stem or "Untitled material")
        category = str(file_meta.get("material_category") or "project")
        stored_path = str(file_meta.get("path") or "")
        original_name = str(file_meta.get("name") or file_meta.get("original_name") or "")

        conn.execute(
            """
            INSERT INTO assets(id, workspace_id, kind, original_name, stored_path, suffix, size_bytes, created_at)
            VALUES (?, ?, 'material', ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                original_name = excluded.original_name,
                stored_path = excluded.stored_path,
                suffix = excluded.suffix,
                size_bytes = excluded.size_bytes
            """,
            (
                asset_id,
                workspace_id,
                original_name,
                stored_path,
                str(file_meta.get("suffix") or Path(original_name).suffix),
                int(file_meta.get("size_bytes") or 0),
                now,
            ),
        )
        conn.execute(
            """
            INSERT INTO materials(
                id, workspace_id, asset_id, title, category, raw_text,
                metadata_json, file_meta_json, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                asset_id = excluded.asset_id,
                title = excluded.title,
                category = excluded.category,
                raw_text = excluded.raw_text,
                metadata_json = excluded.metadata_json,
                file_meta_json = excluded.file_meta_json,
                updated_at = excluded.updated_at
            """,
            (
                material_id,
                workspace_id,
                asset_id,
                title,
                category,
                str(file_meta.get("raw_text") or ""),
                _dump_json(file_meta.get("metadata", {})),
                _dump_json({**file_meta, "id": material_id, "material_id": material_id, "asset_id": asset_id}),
                now,
                now,
            ),
        )

        materials.append({**file_meta, "id": material_id, "material_id": material_id, "asset_id": asset_id})

    if seen_ids:
        placeholders = ",".join("?" for _ in seen_ids)
        conn.execute(
            f"DELETE FROM materials WHERE workspace_id = ? AND id NOT IN ({placeholders})",
            [workspace_id, *sorted(seen_ids)],
        )
    else:
        conn.execute("DELETE FROM materials WHERE workspace_id = ?", (workspace_id,))
    return materials


def _upsert_photo_asset(conn: sqlite3.Connection, workspace_id: str, resume_data: Dict[str, Any]) -> None:
    photo_path = str(resume_data.get("basics", {}).get("photo_path", "") or "").strip()
    if not photo_path:
        conn.execute("DELETE FROM assets WHERE workspace_id = ? AND kind = 'photo'", (workspace_id,))
        return

    try:
        safe_path = ensure_workspace_path(photo_path)
    except ValueError:
        return

    now = utc_now()
    conn.execute(
        """
        INSERT INTO assets(id, workspace_id, kind, original_name, stored_path, suffix, size_bytes, created_at)
        VALUES (?, ?, 'photo', ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            original_name = excluded.original_name,
            stored_path = excluded.stored_path,
            suffix = excluded.suffix,
            size_bytes = excluded.size_bytes
        """,
        (
            "photo_current",
            workspace_id,
            safe_path.name,
            str(safe_path),
            safe_path.suffix.lower(),
            safe_path.stat().st_size if safe_path.exists() and safe_path.is_file() else 0,
            now,
        ),
    )


def _list_materials(conn: sqlite3.Connection, workspace_id: str) -> List[Dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT m.*, a.original_name, a.stored_path, a.suffix, a.size_bytes
        FROM materials m
        LEFT JOIN assets a ON a.id = m.asset_id
        WHERE m.workspace_id = ?
        ORDER BY m.created_at, m.id
        """,
        (workspace_id,),
    ).fetchall()

    materials: List[Dict[str, Any]] = []
    for row in rows:
        file_meta = _load_json(row["file_meta_json"], {})
        if not isinstance(file_meta, dict):
            file_meta = {}
        file_meta.update(
            {
                "id": row["id"],
                "material_id": row["id"],
                "asset_id": row["asset_id"] or "",
                "name": file_meta.get("name") or row["original_name"] or row["title"],
                "original_name": file_meta.get("original_name") or row["original_name"] or row["title"],
                "type": "readme",
                "path": file_meta.get("path") or row["stored_path"] or "",
                "suffix": file_meta.get("suffix") or row["suffix"] or "",
                "size_bytes": int(file_meta.get("size_bytes") or row["size_bytes"] or 0),
                "raw_text": row["raw_text"] or "",
                "material_title": row["title"],
                "material_category": row["category"],
                "metadata": _load_json(row["metadata_json"], {}),
            }
        )
        normalized = normalize_uploaded_file_meta(file_meta)
        if normalized:
            materials.append({**normalized, "id": row["id"], "material_id": row["id"], "asset_id": row["asset_id"] or ""})
    return materials


def _upsert_workspace(
    conn: sqlite3.Connection,
    *,
    workspace_id: str,
    shaped: Dict[str, Any],
    inputs: Dict[str, Any],
    now: str,
) -> None:
    conn.execute(
        """
        INSERT INTO workspaces(id, name, resume_json, style_json, inputs_json, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            resume_json = excluded.resume_json,
            style_json = excluded.style_json,
            inputs_json = excluded.inputs_json,
            updated_at = excluded.updated_at
        """,
        (
            workspace_id,
            "Default workspace",
            _dump_json({key: deepcopy(shaped.get(key)) for key in ["basics", "modules"]}),
            _dump_json(shaped.get("style", {})),
            _dump_json(inputs),
            now,
            now,
        ),
    )


def save_workspace(
    resume_data: Dict[str, Any],
    *,
    workspace_id: str = DEFAULT_WORKSPACE_ID,
    db_path: Path | None = None,
) -> Dict[str, Any]:
    shaped = ensure_resume_shape(resume_data)
    inputs = normalize_inputs(resume_data.get("inputs", {}) if isinstance(resume_data, dict) else {})
    uploaded_files = inputs.get("uploaded_files", [])
    now = utc_now()

    conn = _connect(db_path)
    try:
        ensure_schema(conn)
        _upsert_workspace(conn, workspace_id=workspace_id, shaped=shaped, inputs=inputs, now=now)
        materials = _upsert_materials(conn, workspace_id, uploaded_files)
        _upsert_photo_asset(conn, workspace_id, shaped)
        non_material_files = [
            file_meta
            for file_meta in uploaded_files
            if isinstance(file_meta, dict) and file_meta.get("type") != "readme"
        ]
        inputs["uploaded_files"] = non_material_files + materials

        _upsert_workspace(conn, workspace_id=workspace_id, shaped=shaped, inputs=inputs, now=now)
        conn.commit()
    finally:
        conn.close()

    return {
        **deepcopy(shaped),
        "inputs": inputs,
    }


def load_workspace(
    *,
    workspace_id: str = DEFAULT_WORKSPACE_ID,
    db_path: Path | None = None,
    legacy_resume_path: Path | None = None,
) -> Dict[str, Any]:
    conn = _connect(db_path)
    try:
        ensure_schema(conn)
        row = conn.execute("SELECT * FROM workspaces WHERE id = ?", (workspace_id,)).fetchone()
        if row is None:
            if legacy_resume_path and legacy_resume_path.exists():
                with legacy_resume_path.open("r", encoding="utf-8") as file:
                    legacy_data = json.load(file)
                migrated = save_workspace(legacy_data, workspace_id=workspace_id, db_path=db_path)
                return migrated
            return save_workspace(get_default_resume_data(), workspace_id=workspace_id, db_path=db_path)

        resume_core = _load_json(row["resume_json"], {})
        if not isinstance(resume_core, dict):
            resume_core = {}
        resume_core["style"] = _load_json(row["style_json"], {})
        inputs = normalize_inputs(_load_json(row["inputs_json"], {}))
        materials = _list_materials(conn, workspace_id)
        non_material_files = [
            file_meta
            for file_meta in inputs.get("uploaded_files", [])
            if isinstance(file_meta, dict) and file_meta.get("type") != "readme"
        ]
        inputs["uploaded_files"] = non_material_files + materials
    finally:
        conn.close()

    shaped = ensure_resume_shape(resume_core)
    shaped["inputs"] = inputs
    return shaped


def save_workflow_logs(
    logs: List[Dict[str, Any]],
    *,
    workspace_id: str = DEFAULT_WORKSPACE_ID,
    db_path: Path | None = None,
    run_id: str | None = None,
    jd_text: str = "",
    input_signature: str = "",
) -> str:
    resolved_run_id = run_id or f"run_{uuid4().hex}"
    now = utc_now()
    conn = _connect(db_path)
    try:
        ensure_schema(conn)
        conn.execute(
            """
            INSERT OR REPLACE INTO workflow_runs(id, workspace_id, status, jd_text, input_signature, started_at, finished_at)
            VALUES (?, ?, 'completed', ?, ?, ?, ?)
            """,
            (resolved_run_id, workspace_id, jd_text, input_signature, now, now),
        )
        conn.execute("DELETE FROM workflow_logs WHERE run_id = ?", (resolved_run_id,))
        for log in logs:
            if not isinstance(log, dict):
                continue
            conn.execute(
                """
                INSERT INTO workflow_logs(id, run_id, workspace_id, agent, message_key, message, details_json, raw_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"log_{uuid4().hex}",
                    resolved_run_id,
                    workspace_id,
                    str(log.get("agent", "workflow") or "workflow"),
                    str(log.get("message_key", "") or ""),
                    str(log.get("message", "") or ""),
                    _dump_json(log.get("details", [])),
                    _dump_json(log),
                    now,
                ),
            )
        conn.commit()
    finally:
        conn.close()
    return resolved_run_id
