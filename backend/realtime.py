from __future__ import annotations

from datetime import datetime, timezone
import json
import sqlite3
from pathlib import Path
from typing import Any

from .model import SimulationContext, sanitize_params, validate_params


DB_PATH = Path(__file__).resolve().parent / "realtime.db"
BOUNDARY_ALIASES = {
    "Q": "influentQ",
    "q": "influentQ",
    "flow": "influentQ",
    "COD": "influentCod",
    "cod": "influentCod",
    "NH4": "influentNh4",
    "nh4": "influentNh4",
    "NO3": "influentNo3",
    "no3": "influentNo3",
    "TSS": "influentTss",
    "tss": "influentTss",
    "DO": "aerobicDo",
    "do": "aerobicDo",
    "RAS_Q": "rasRatio",
    "IR_Q": "internalRecycleRatio",
    "WAS_Q": "wasQ",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS realtime_inputs (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              timestamp TEXT NOT NULL,
              values_json TEXT NOT NULL,
              quality_json TEXT NOT NULL,
              created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS realtime_state (
              id INTEGER PRIMARY KEY CHECK (id = 1),
              timestamp TEXT NOT NULL,
              params_json TEXT NOT NULL,
              state_json TEXT NOT NULL,
              last_input_id INTEGER,
              updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS realtime_results (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              timestamp TEXT NOT NULL,
              input_id INTEGER,
              step_hours REAL NOT NULL,
              result_json TEXT NOT NULL,
              warnings_json TEXT NOT NULL,
              created_at TEXT NOT NULL
            );
            """
        )


def normalize_values(values: dict[str, Any], base_params: dict[str, float]) -> tuple[dict[str, float], list[str]]:
    normalized: dict[str, float] = {}
    warnings: list[str] = []
    influent_q = base_params.get("influentQ", 1)
    for key, value in values.items():
        target = BOUNDARY_ALIASES.get(key, key)
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            warnings.append(f"{key} 无法解析为数值，已忽略。")
            continue
        if target == "rasRatio" and key in {"RAS_Q"}:
            parsed = parsed / max(influent_q, 1e-9)
        if target == "internalRecycleRatio" and key in {"IR_Q"}:
            parsed = parsed / max(influent_q, 1e-9)
        normalized[target] = parsed
    return normalized, warnings


def insert_input(timestamp: str | None, values: dict[str, Any], quality: dict[str, Any] | None = None) -> dict[str, Any]:
    init_db()
    ts = timestamp or now_iso()
    with connect() as conn:
        cursor = conn.execute(
            "INSERT INTO realtime_inputs (timestamp, values_json, quality_json, created_at) VALUES (?, ?, ?, ?)",
            (ts, json.dumps(values), json.dumps(quality or {}), now_iso()),
        )
        row_id = cursor.lastrowid
    return {"id": row_id, "timestamp": ts, "values": values, "quality": quality or {}}


def get_latest_input() -> dict[str, Any] | None:
    init_db()
    with connect() as conn:
        row = conn.execute("SELECT * FROM realtime_inputs ORDER BY id DESC LIMIT 1").fetchone()
    if not row:
        return None
    return {
        "id": row["id"],
        "timestamp": row["timestamp"],
        "values": json.loads(row["values_json"]),
        "quality": json.loads(row["quality_json"]),
    }


def load_state() -> dict[str, Any] | None:
    init_db()
    with connect() as conn:
        row = conn.execute("SELECT * FROM realtime_state WHERE id = 1").fetchone()
    if not row:
        return None
    return {
        "timestamp": row["timestamp"],
        "params": json.loads(row["params_json"]),
        "state": json.loads(row["state_json"]),
        "lastInputId": row["last_input_id"],
        "updatedAt": row["updated_at"],
    }


def save_state(timestamp: str, params: dict[str, float], state: dict[str, Any], input_id: int | None) -> None:
    init_db()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO realtime_state (id, timestamp, params_json, state_json, last_input_id, updated_at)
            VALUES (1, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
              timestamp = excluded.timestamp,
              params_json = excluded.params_json,
              state_json = excluded.state_json,
              last_input_id = excluded.last_input_id,
              updated_at = excluded.updated_at
            """,
            (timestamp, json.dumps(params), json.dumps(state), input_id, now_iso()),
        )


def insert_result(timestamp: str, input_id: int | None, step_hours: float, result: dict[str, Any], warnings: list[str]) -> int:
    init_db()
    with connect() as conn:
        cursor = conn.execute(
            "INSERT INTO realtime_results (timestamp, input_id, step_hours, result_json, warnings_json, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (timestamp, input_id, step_hours, json.dumps(result), json.dumps(warnings), now_iso()),
        )
        return int(cursor.lastrowid)


def get_latest_result() -> dict[str, Any] | None:
    init_db()
    with connect() as conn:
        row = conn.execute("SELECT * FROM realtime_results ORDER BY id DESC LIMIT 1").fetchone()
    if not row:
        return None
    return {
        "id": row["id"],
        "timestamp": row["timestamp"],
        "inputId": row["input_id"],
        "stepHours": row["step_hours"],
        "result": json.loads(row["result_json"]),
        "warnings": json.loads(row["warnings_json"]),
        "createdAt": row["created_at"],
    }


def realtime_step(
    timestamp: str | None = None,
    values: dict[str, Any] | None = None,
    quality: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
    step_hours: float | None = None,
) -> dict[str, Any]:
    init_db()
    saved = load_state()
    clean_params = sanitize_params(saved["params"] if saved else params)
    if params:
        clean_params.update(sanitize_params(params))
    errors, warnings = validate_params(clean_params)
    if errors:
        raise ValueError("; ".join(errors))

    input_record = None
    if values is not None:
        input_record = insert_input(timestamp, values, quality)
    else:
        input_record = get_latest_input()
    if not input_record:
        input_record = insert_input(timestamp, {}, quality)

    boundary_values, value_warnings = normalize_values(input_record["values"], clean_params)
    warnings.extend(value_warnings)
    ctx = SimulationContext(params=clean_params, source_name="realtime", mode="realtime")
    state = saved["state"] if saved else ctx.create_simulation_state()
    step = float(step_hours if step_hours is not None else clean_params["timeStepHours"])
    stepped = ctx.step_realtime_state(state, boundary_values, step)
    result = stepped["snapshot"]
    result["mode"] = "realtime"
    result["timestamp"] = input_record["timestamp"]
    result["inputId"] = input_record["id"]
    result["warnings"] = warnings
    result["validation"] = {"ok": True, "warningCount": len(warnings), "warnings": warnings}

    save_state(input_record["timestamp"], ctx.params, stepped["state"], input_record["id"])
    result_id = insert_result(input_record["timestamp"], input_record["id"], step, result, warnings)
    return {"resultId": result_id, "input": input_record, "result": result, "state": load_state()}


def latest() -> dict[str, Any]:
    return {"input": get_latest_input(), "state": load_state(), "result": get_latest_result()}


def reset() -> dict[str, str]:
    init_db()
    with connect() as conn:
        conn.execute("DELETE FROM realtime_inputs")
        conn.execute("DELETE FROM realtime_state")
        conn.execute("DELETE FROM realtime_results")
    return {"status": "reset"}
