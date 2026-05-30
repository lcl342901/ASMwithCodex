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

            CREATE TABLE IF NOT EXISTS project_csv_inputs (
              project_id TEXT PRIMARY KEY,
              file_name TEXT NOT NULL,
              csv_text TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS calibration_runs (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              project_id TEXT NOT NULL,
              name TEXT NOT NULL,
              status TEXT NOT NULL,
              request_json TEXT NOT NULL,
              result_json TEXT NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS periodic_calibration_schedules (
              project_id TEXT PRIMARY KEY,
              enabled INTEGER NOT NULL,
              config_json TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              last_run_at TEXT,
              last_run_id INTEGER,
              last_status TEXT,
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
    if project_id == DEFAULT_PROJECT_ID:
        ensure_default_project()
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
    realtime.reset(project_id)
    realtime.clear_calculation_logs(project_id)
    with realtime.connect() as conn:
        conn.execute("DELETE FROM project_param_configs WHERE project_id = ?", (project_id,))
        conn.execute("DELETE FROM project_csv_inputs WHERE project_id = ?", (project_id,))
        conn.execute("DELETE FROM calibration_runs WHERE project_id = ?", (project_id,))
        conn.execute("DELETE FROM periodic_calibration_schedules WHERE project_id = ?", (project_id,))
        cursor = conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
    return {"status": "deleted", "projectId": project_id, "deleted": cursor.rowcount}


def default_periodic_calibration_config() -> dict[str, Any]:
    return {
        "name": "Weekly calibration check",
        "enabled": False,
        "cadence": "weekly",
        "dataWindowHours": 72,
        "stageId": "nitrification",
        "targets": ["effNh4"],
        "tunableParams": ["muA", "kNH"],
        "maxIterations": 1,
        "stepFraction": 0.05,
        "maxLagHours": 2.0,
        "useProjectCsv": True,
        "applyBestParams": False,
    }


def normalize_periodic_calibration_config(config: dict[str, Any] | None = None) -> dict[str, Any]:
    merged = {**default_periodic_calibration_config(), **(config or {})}
    merged["name"] = str(merged.get("name") or "Periodic calibration").strip()[:120] or "Periodic calibration"
    merged["enabled"] = bool(merged.get("enabled"))
    cadence = str(merged.get("cadence") or "weekly").lower()
    merged["cadence"] = cadence if cadence in {"manual", "daily", "weekly"} else "weekly"
    merged["dataWindowHours"] = max(1.0, min(float(merged.get("dataWindowHours") or 72), 24 * 30))
    merged["stageId"] = str(merged.get("stageId") or "nitrification")
    merged["targets"] = [str(item) for item in (merged.get("targets") or []) if str(item).strip()]
    merged["tunableParams"] = [str(item) for item in (merged.get("tunableParams") or []) if str(item).strip()]
    merged["maxIterations"] = max(1, min(int(merged.get("maxIterations") or 1), 4))
    merged["stepFraction"] = max(0.001, min(float(merged.get("stepFraction") or 0.05), 0.25))
    merged["maxLagHours"] = max(0.1, min(float(merged.get("maxLagHours") or 2.0), 24.0))
    merged["useProjectCsv"] = bool(merged.get("useProjectCsv"))
    merged["applyBestParams"] = bool(merged.get("applyBestParams"))
    return merged


def get_periodic_calibration_schedule(project_id: str) -> dict[str, Any]:
    project = get_project(project_id)
    with realtime.connect() as conn:
        row = conn.execute("SELECT * FROM periodic_calibration_schedules WHERE project_id = ?", (project_id,)).fetchone()
    if not row:
        return {
            "project": project,
            "projectId": project_id,
            "config": default_periodic_calibration_config(),
            "enabled": False,
            "updatedAt": None,
            "lastRunAt": None,
            "lastRunId": None,
            "lastStatus": None,
            "source": "default",
        }
    config = normalize_periodic_calibration_config(json.loads(row["config_json"]))
    return {
        "project": project,
        "projectId": row["project_id"],
        "config": config,
        "enabled": bool(row["enabled"]),
        "updatedAt": row["updated_at"],
        "lastRunAt": row["last_run_at"],
        "lastRunId": row["last_run_id"],
        "lastStatus": row["last_status"],
        "source": "database",
    }


def save_periodic_calibration_schedule(project_id: str, config: dict[str, Any]) -> dict[str, Any]:
    project = get_project(project_id)
    clean_config = normalize_periodic_calibration_config(config)
    timestamp = realtime.now_iso()
    with realtime.connect() as conn:
        conn.execute(
            """
            INSERT INTO periodic_calibration_schedules (project_id, enabled, config_json, updated_at, last_run_at, last_run_id, last_status)
            VALUES (?, ?, ?, ?, NULL, NULL, NULL)
            ON CONFLICT(project_id) DO UPDATE SET
              enabled = excluded.enabled,
              config_json = excluded.config_json,
              updated_at = excluded.updated_at
            """,
            (project_id, 1 if clean_config["enabled"] else 0, json.dumps(clean_config), timestamp),
        )
        conn.execute("UPDATE projects SET updated_at = ? WHERE id = ?", (timestamp, project_id))
    return get_periodic_calibration_schedule(project_id) | {"project": {**project, "updatedAt": timestamp}}


def update_periodic_calibration_last_run(project_id: str, run_id: int | None, status: str) -> dict[str, Any]:
    get_project(project_id)
    timestamp = realtime.now_iso()
    with realtime.connect() as conn:
        row = conn.execute("SELECT config_json, enabled FROM periodic_calibration_schedules WHERE project_id = ?", (project_id,)).fetchone()
        if not row:
            config = default_periodic_calibration_config()
            enabled = 0
            conn.execute(
                """
                INSERT INTO periodic_calibration_schedules (project_id, enabled, config_json, updated_at, last_run_at, last_run_id, last_status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (project_id, enabled, json.dumps(config), timestamp, timestamp, run_id, status),
            )
        else:
            conn.execute(
                """
                UPDATE periodic_calibration_schedules
                SET last_run_at = ?, last_run_id = ?, last_status = ?
                WHERE project_id = ?
                """,
                (timestamp, run_id, status, project_id),
            )
        conn.execute("UPDATE projects SET updated_at = ? WHERE id = ?", (timestamp, project_id))
    return get_periodic_calibration_schedule(project_id)


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


def get_project_csv(project_id: str) -> dict[str, Any]:
    project = get_project(project_id)
    with realtime.connect() as conn:
        row = conn.execute("SELECT * FROM project_csv_inputs WHERE project_id = ?", (project_id,)).fetchone()
    if not row:
        return {"project": project, "csvText": "", "csvFileName": "", "updatedAt": None, "source": "none"}
    return {
        "project": project,
        "csvText": row["csv_text"],
        "csvFileName": row["file_name"],
        "updatedAt": row["updated_at"],
        "source": "database",
    }


def save_project_csv(project_id: str, csv_text: str, csv_file_name: str = "") -> dict[str, Any]:
    project = get_project(project_id)
    if not csv_text.strip():
        raise ValueError("CSV 文本不能为空。")
    timestamp = realtime.now_iso()
    with realtime.connect() as conn:
        conn.execute(
            """
            INSERT INTO project_csv_inputs (project_id, file_name, csv_text, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(project_id) DO UPDATE SET
              file_name = excluded.file_name,
              csv_text = excluded.csv_text,
              updated_at = excluded.updated_at
            """,
            (project_id, csv_file_name or "boundary-data.csv", csv_text, timestamp),
        )
        conn.execute("UPDATE projects SET updated_at = ? WHERE id = ?", (timestamp, project_id))
    return {
        "project": {**project, "updatedAt": timestamp},
        "csvText": csv_text,
        "csvFileName": csv_file_name or "boundary-data.csv",
        "updatedAt": timestamp,
        "source": "database",
    }


def clear_project_csv(project_id: str) -> dict[str, Any]:
    project = get_project(project_id)
    timestamp = realtime.now_iso()
    with realtime.connect() as conn:
        cursor = conn.execute("DELETE FROM project_csv_inputs WHERE project_id = ?", (project_id,))
        conn.execute("UPDATE projects SET updated_at = ? WHERE id = ?", (timestamp, project_id))
    return {"project": {**project, "updatedAt": timestamp}, "status": "cleared", "deleted": cursor.rowcount}


def insert_calibration_run(project_id: str, name: str, status: str, request: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    project = get_project(project_id)
    timestamp = realtime.now_iso()
    clean_name = name.strip() or f"Calibration {timestamp}"
    with realtime.connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO calibration_runs (project_id, name, status, request_json, result_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (project_id, clean_name, status, json.dumps(request), json.dumps(result), timestamp, timestamp),
        )
        row_id = int(cursor.lastrowid)
        conn.execute("UPDATE projects SET updated_at = ? WHERE id = ?", (timestamp, project_id))
    return get_calibration_run(project_id, row_id) | {"project": project}


def list_calibration_runs(project_id: str, limit: int = 100) -> dict[str, Any]:
    project = get_project(project_id)
    safe_limit = max(1, min(int(limit), 500))
    with realtime.connect() as conn:
        rows = conn.execute(
            """
            SELECT id, project_id, name, status, result_json, created_at, updated_at
            FROM calibration_runs
            WHERE project_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (project_id, safe_limit),
        ).fetchall()
    runs = []
    for row in rows:
        result = json.loads(row["result_json"])
        runs.append(
            {
                "id": row["id"],
                "projectId": row["project_id"],
                "name": row["name"],
                "status": row["status"],
                "bestObjective": result.get("bestObjective"),
                "initialObjective": result.get("initialObjective"),
                "mapping": result.get("mapping"),
                "method": result.get("method"),
                "createdAt": row["created_at"],
                "updatedAt": row["updated_at"],
            }
        )
    return {"project": project, "runs": runs, "limit": safe_limit}


def get_calibration_run(project_id: str, run_id: int) -> dict[str, Any]:
    project = get_project(project_id)
    with realtime.connect() as conn:
        row = conn.execute(
            "SELECT * FROM calibration_runs WHERE project_id = ? AND id = ?",
            (project_id, run_id),
        ).fetchone()
    if not row:
        raise ValueError(f"校准任务不存在：{run_id}。")
    return {
        "project": project,
        "id": row["id"],
        "projectId": row["project_id"],
        "name": row["name"],
        "status": row["status"],
        "request": json.loads(row["request_json"]),
        "result": json.loads(row["result_json"]),
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


def delete_calibration_run(project_id: str, run_id: int) -> dict[str, Any]:
    get_calibration_run(project_id, run_id)
    with realtime.connect() as conn:
        cursor = conn.execute("DELETE FROM calibration_runs WHERE project_id = ? AND id = ?", (project_id, run_id))
    return {"status": "deleted", "projectId": project_id, "runId": run_id, "deleted": cursor.rowcount}
