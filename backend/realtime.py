from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import json
import math
import random
import sqlite3
from pathlib import Path
from typing import Any

from .model import DEFAULT_PARAMS, SimulationContext, sanitize_params, validate_params


DB_PATH = Path(__file__).resolve().parent / "realtime.db"
MOCK_INTERVAL_SECONDS = 300
MOCK_STEP_HOURS = 5 / 60
PARAM_CONFIG_KEY = "global"
MOCK_TASK: asyncio.Task | None = None
MOCK_STATUS: dict[str, Any] = {
    "running": False,
    "intervalSeconds": MOCK_INTERVAL_SECONDS,
    "lastRunAt": None,
    "lastResultId": None,
    "lastError": None,
    "runCount": 0,
}
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

            CREATE TABLE IF NOT EXISTS saved_param_configs (
              key TEXT PRIMARY KEY,
              params_json TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS calculation_logs (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              event TEXT NOT NULL,
              status TEXT NOT NULL,
              message TEXT NOT NULL,
              detail_json TEXT NOT NULL,
              duration_ms REAL,
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


def get_saved_params() -> dict[str, Any]:
    init_db()
    with connect() as conn:
        row = conn.execute("SELECT * FROM saved_param_configs WHERE key = ?", (PARAM_CONFIG_KEY,)).fetchone()
    if not row:
        return {"params": DEFAULT_PARAMS.copy(), "updatedAt": None, "source": "default"}
    return {
        "params": sanitize_params(json.loads(row["params_json"])),
        "updatedAt": row["updated_at"],
        "source": "database",
    }


def save_params_config(params: dict[str, Any]) -> dict[str, Any]:
    init_db()
    clean_params = sanitize_params(params)
    errors, warnings = validate_params(clean_params)
    if errors:
        raise ValueError("; ".join(errors))
    updated_at = now_iso()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO saved_param_configs (key, params_json, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
              params_json = excluded.params_json,
              updated_at = excluded.updated_at
            """,
            (PARAM_CONFIG_KEY, json.dumps(clean_params), updated_at),
        )
    return {
        "params": clean_params,
        "updatedAt": updated_at,
        "source": "database",
        "warnings": warnings,
    }


def reset_params_config() -> dict[str, Any]:
    init_db()
    with connect() as conn:
        conn.execute("DELETE FROM saved_param_configs WHERE key = ?", (PARAM_CONFIG_KEY,))
    return {"params": DEFAULT_PARAMS.copy(), "updatedAt": None, "source": "default"}


def insert_calculation_log(
    event: str,
    status: str,
    message: str,
    detail: dict[str, Any] | None = None,
    duration_ms: float | None = None,
) -> dict[str, Any]:
    init_db()
    created_at = now_iso()
    with connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO calculation_logs (event, status, message, detail_json, duration_ms, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (event, status, message, json.dumps(detail or {}), duration_ms, created_at),
        )
        row_id = int(cursor.lastrowid)
    return {
        "id": row_id,
        "event": event,
        "status": status,
        "message": message,
        "detail": detail or {},
        "durationMs": duration_ms,
        "createdAt": created_at,
    }


def list_calculation_logs(limit: int = 100) -> dict[str, Any]:
    init_db()
    safe_limit = max(1, min(int(limit), 500))
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM calculation_logs ORDER BY id DESC LIMIT ?",
            (safe_limit,),
        ).fetchall()
    logs = [
        {
            "id": row["id"],
            "event": row["event"],
            "status": row["status"],
            "message": row["message"],
            "detail": json.loads(row["detail_json"]),
            "durationMs": row["duration_ms"],
            "createdAt": row["created_at"],
        }
        for row in rows
    ]
    return {"logs": logs, "limit": safe_limit}


def clear_calculation_logs() -> dict[str, Any]:
    init_db()
    with connect() as conn:
        cursor = conn.execute("DELETE FROM calculation_logs")
        deleted = cursor.rowcount
    return {"status": "cleared", "deleted": deleted}


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


def mock_base_params() -> dict[str, float]:
    saved = load_state()
    if saved and saved.get("params"):
        return sanitize_params(saved["params"])
    return DEFAULT_PARAMS.copy()


def generate_mock_values(run_count: int | None = None) -> dict[str, float]:
    params = mock_base_params()
    index = MOCK_STATUS["runCount"] if run_count is None else run_count
    phase = (index % 288) / 288 * math.tau

    def vary(base: float, amplitude: float, noise: float, floor: float = 0.0) -> float:
        periodic = 1 + amplitude * math.sin(phase)
        jitter = 1 + random.uniform(-noise, noise)
        return max(floor, base * periodic * jitter)

    return {
        "Q": vary(params["influentQ"], 0.08, 0.02, 1),
        "COD": vary(params["influentCod"], 0.12, 0.04),
        "NH4": vary(params["influentNh4"], 0.1, 0.03),
        "NO3": vary(params["influentNo3"], 0.08, 0.02),
        "TSS": vary(params["influentTss"], 0.15, 0.05),
        "DO": max(0.2, min(5.0, params["aerobicDo"] + 0.25 * math.sin(phase + math.pi / 4) + random.uniform(-0.08, 0.08))),
    }


def run_mock_once() -> dict[str, Any]:
    started = datetime.now(timezone.utc)
    try:
        values = generate_mock_values()
        result = realtime_step(
            timestamp=now_iso(),
            values=values,
            quality={"source": "mock"},
            step_hours=MOCK_STEP_HOURS,
        )
        MOCK_STATUS["lastRunAt"] = now_iso()
        MOCK_STATUS["lastResultId"] = result["resultId"]
        MOCK_STATUS["lastError"] = None
        MOCK_STATUS["runCount"] += 1
        duration_ms = (datetime.now(timezone.utc) - started).total_seconds() * 1000
        insert_calculation_log(
            "mock_run",
            "success",
            f"Mock 自动推进完成，结果 #{result['resultId']}。",
            {"resultId": result["resultId"], "stepHours": MOCK_STEP_HOURS},
            duration_ms,
        )
        return result
    except Exception as exc:
        duration_ms = (datetime.now(timezone.utc) - started).total_seconds() * 1000
        insert_calculation_log("mock_run", "failed", str(exc), {"stepHours": MOCK_STEP_HOURS}, duration_ms)
        raise


async def mock_loop() -> None:
    try:
        while True:
            await asyncio.sleep(MOCK_STATUS["intervalSeconds"])
            try:
                run_mock_once()
            except Exception as exc:  # pragma: no cover - defensive background guard
                MOCK_STATUS["lastError"] = str(exc)
    except asyncio.CancelledError:
        raise


async def start_mock(interval_seconds: int = MOCK_INTERVAL_SECONDS) -> dict[str, Any]:
    global MOCK_TASK
    if interval_seconds <= 0:
        raise ValueError("interval_seconds must be positive.")
    MOCK_STATUS["intervalSeconds"] = interval_seconds
    if MOCK_TASK and not MOCK_TASK.done():
        MOCK_STATUS["running"] = True
        return mock_status()
    MOCK_STATUS["running"] = True
    MOCK_STATUS["lastError"] = None
    try:
        run_mock_once()
    except Exception as exc:
        MOCK_STATUS["lastError"] = str(exc)
    MOCK_TASK = asyncio.create_task(mock_loop())
    return mock_status()


async def stop_mock() -> dict[str, Any]:
    global MOCK_TASK
    if MOCK_TASK and not MOCK_TASK.done():
        MOCK_TASK.cancel()
        try:
            await MOCK_TASK
        except asyncio.CancelledError:
            pass
    MOCK_TASK = None
    MOCK_STATUS["running"] = False
    return mock_status()


def mock_status() -> dict[str, Any]:
    running = bool(MOCK_TASK and not MOCK_TASK.done())
    MOCK_STATUS["running"] = running
    return dict(MOCK_STATUS)


def latest() -> dict[str, Any]:
    return {"input": get_latest_input(), "state": load_state(), "result": get_latest_result()}


def reset() -> dict[str, str]:
    init_db()
    with connect() as conn:
        conn.execute("DELETE FROM realtime_inputs")
        conn.execute("DELETE FROM realtime_state")
        conn.execute("DELETE FROM realtime_results")
    return {"status": "reset"}
