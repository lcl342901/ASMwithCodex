from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from . import realtime
from .model import DEFAULT_PARAMS, sanitize_params, validate_params


DEFAULT_PROJECT_ID = "default"
DEFAULT_PROJECT_NAME = "Default Project"


def init_platform_db() -> None:
    realtime.init_db()
    with realtime.connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS projects (
              id TEXT PRIMARY KEY,
              name TEXT NOT NULL,
              description TEXT NOT NULL,
              owner_id TEXT NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS project_param_configs (
              project_id TEXT PRIMARY KEY,
              params_json TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
            );
            """
        )


def row_to_project(row: Any) -> dict[str, Any]:
    return {
        "id": row["id"],
        "name": row["name"],
        "description": row["description"],
        "ownerId": row["owner_id"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


def ensure_default_project() -> dict[str, Any]:
    init_platform_db()
    with realtime.connect() as conn:
        row = conn.execute("SELECT * FROM projects WHERE id = ?", (DEFAULT_PROJECT_ID,)).fetchone()
        if row:
            return row_to_project(row)
        timestamp = realtime.now_iso()
        conn.execute(
            """
            INSERT INTO projects (id, name, description, owner_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (DEFAULT_PROJECT_ID, DEFAULT_PROJECT_NAME, "Local single-user project.", "local", timestamp, timestamp),
        )
    return get_project(DEFAULT_PROJECT_ID)


def list_projects() -> dict[str, Any]:
    ensure_default_project()
    with realtime.connect() as conn:
        rows = conn.execute("SELECT * FROM projects ORDER BY updated_at DESC").fetchall()
    return {"projects": [row_to_project(row) for row in rows]}


def get_project(project_id: str) -> dict[str, Any]:
    init_platform_db()
    with realtime.connect() as conn:
        row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    if not row:
        raise ValueError(f"项目不存在：{project_id}。")
    return row_to_project(row)


def create_project(name: str, description: str = "", owner_id: str = "local") -> dict[str, Any]:
    init_platform_db()
    clean_name = name.strip()
    if not clean_name:
        raise ValueError("项目名称不能为空。")
    project_id = uuid4().hex
    timestamp = realtime.now_iso()
    with realtime.connect() as conn:
        conn.execute(
            """
            INSERT INTO projects (id, name, description, owner_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (project_id, clean_name, description or "", owner_id or "local", timestamp, timestamp),
        )
    return get_project(project_id)


def update_project(project_id: str, name: str | None = None, description: str | None = None) -> dict[str, Any]:
    current = get_project(project_id)
    clean_name = current["name"] if name is None else name.strip()
    if not clean_name:
        raise ValueError("项目名称不能为空。")
    clean_description = current["description"] if description is None else description
    timestamp = realtime.now_iso()
    with realtime.connect() as conn:
        conn.execute(
            """
            UPDATE projects
            SET name = ?, description = ?, updated_at = ?
            WHERE id = ?
            """,
            (clean_name, clean_description or "", timestamp, project_id),
        )
    return get_project(project_id)


def delete_project(project_id: str) -> dict[str, Any]:
    if project_id == DEFAULT_PROJECT_ID:
        raise ValueError("默认项目不能删除。")
    get_project(project_id)
    with realtime.connect() as conn:
        conn.execute("DELETE FROM project_param_configs WHERE project_id = ?", (project_id,))
        cursor = conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
    return {"status": "deleted", "projectId": project_id, "deleted": cursor.rowcount}


def get_project_params(project_id: str) -> dict[str, Any]:
    project = get_project(project_id)
    with realtime.connect() as conn:
        row = conn.execute("SELECT * FROM project_param_configs WHERE project_id = ?", (project_id,)).fetchone()
    if not row:
        return {"project": project, "params": DEFAULT_PARAMS.copy(), "updatedAt": None, "source": "default"}
    return {
        "project": project,
        "params": sanitize_params(json.loads(row["params_json"])),
        "updatedAt": row["updated_at"],
        "source": "database",
    }


def save_project_params(project_id: str, params: dict[str, Any]) -> dict[str, Any]:
    project = get_project(project_id)
    clean_params = sanitize_params(params)
    errors, warnings = validate_params(clean_params)
    if errors:
        raise ValueError("; ".join(errors))
    timestamp = realtime.now_iso()
    with realtime.connect() as conn:
        conn.execute(
            """
            INSERT INTO project_param_configs (project_id, params_json, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(project_id) DO UPDATE SET
              params_json = excluded.params_json,
              updated_at = excluded.updated_at
            """,
            (project_id, json.dumps(clean_params), timestamp),
        )
        conn.execute("UPDATE projects SET updated_at = ? WHERE id = ?", (timestamp, project_id))
    return {
        "project": {**project, "updatedAt": timestamp},
        "params": clean_params,
        "updatedAt": timestamp,
        "source": "database",
        "warnings": warnings,
    }


def reset_project_params(project_id: str) -> dict[str, Any]:
    project = get_project(project_id)
    timestamp = realtime.now_iso()
    with realtime.connect() as conn:
        conn.execute("DELETE FROM project_param_configs WHERE project_id = ?", (project_id,))
        conn.execute("UPDATE projects SET updated_at = ? WHERE id = ?", (timestamp, project_id))
    return {
        "project": {**project, "updatedAt": timestamp},
        "params": DEFAULT_PARAMS.copy(),
        "updatedAt": None,
        "source": "default",
    }
