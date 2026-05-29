from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import json
import math
import random
import sqlite3
from pathlib import Path
from typing import Any

from .model import DEFAULT_PARAMS, PARAM_LIMITS, SimulationContext, sanitize_params, validate_params


DB_PATH = Path(__file__).resolve().parent / "realtime.db"
MOCK_INTERVAL_SECONDS = 300
MOCK_STEP_HOURS = 5 / 60
PARAM_CONFIG_KEY = "global"
DEFAULT_PROJECT_ID = "default"
MOCK_TASK: asyncio.Task | None = None
MOCK_STATUS: dict[str, Any] = {
    "running": False,
    "intervalSeconds": MOCK_INTERVAL_SECONDS,
    "projectId": DEFAULT_PROJECT_ID,
    "profile": "normal",
    "lastRunAt": None,
    "lastResultId": None,
    "lastError": None,
    "runCount": 0,
}
MOCK_PROFILES: dict[str, dict[str, Any]] = {
    "normal": {
        "id": "normal",
        "label": "正常工况",
        "description": "典型市政污水厂进水，适合演示稳定达标运行。",
        "params": {
            "influentQ": 10000.0,
            "influentCod": 300.0,
            "influentNh4": 25.0,
            "influentNo3": 0.5,
            "influentTss": 160.0,
            "aerobicDo": 2.5,
            "rasRatio": 0.9,
            "internalRecycleRatio": 3.0,
            "wasQ": 260.0,
            "captureEfficiency": 99.7,
        },
        "amplitude": {"Q": 0.08, "COD": 0.12, "NH4": 0.10, "NO3": 0.10, "TSS": 0.12, "DO": 0.10},
        "noise": {"Q": 0.02, "COD": 0.03, "NH4": 0.025, "NO3": 0.03, "TSS": 0.035, "DO": 0.04},
    },
    "shock": {
        "id": "shock",
        "label": "冲击负荷",
        "description": "高负荷扰动工况，用于演示预测风险窗口和运行建议。",
        "params": {
            "influentQ": 12000.0,
            "influentCod": 520.0,
            "influentNh4": 48.0,
            "influentNo3": 0.8,
            "influentTss": 340.0,
            "aerobicDo": 2.0,
            "rasRatio": 0.85,
            "internalRecycleRatio": 2.2,
            "wasQ": 330.0,
        },
        "amplitude": {"Q": 0.18, "COD": 0.24, "NH4": 0.22, "NO3": 0.16, "TSS": 0.26, "DO": 0.16},
        "noise": {"Q": 0.04, "COD": 0.06, "NH4": 0.05, "NO3": 0.05, "TSS": 0.07, "DO": 0.08},
    },
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
REALTIME_BOUNDARY_KEYS = ["influentQ", "influentCod", "influentNh4", "influentNo3", "influentTss", "aerobicDo"]
DEFAULT_POINT_CONFIGS: list[dict[str, Any]] = [
    {
        "pointId": "IN_Q",
        "name": "进水流量",
        "modelKey": "influentQ",
        "unit": "m3/d",
        "source": "manual/mock/api",
        "minValue": 1.0,
        "maxValue": 100000.0,
        "maxDelayMinutes": 15.0,
        "maxRateChange": None,
    },
    {
        "pointId": "IN_COD",
        "name": "进水 COD",
        "modelKey": "influentCod",
        "unit": "mg/L",
        "source": "manual/mock/api",
        "minValue": 0.0,
        "maxValue": 2000.0,
        "maxDelayMinutes": 15.0,
        "maxRateChange": None,
    },
    {
        "pointId": "IN_NH4",
        "name": "进水 NH4-N",
        "modelKey": "influentNh4",
        "unit": "mg/L",
        "source": "manual/mock/api",
        "minValue": 0.0,
        "maxValue": 200.0,
        "maxDelayMinutes": 15.0,
        "maxRateChange": None,
    },
    {
        "pointId": "IN_NO3",
        "name": "进水 NO3-N",
        "modelKey": "influentNo3",
        "unit": "mg/L",
        "source": "manual/mock/api",
        "minValue": 0.0,
        "maxValue": 50.0,
        "maxDelayMinutes": 15.0,
        "maxRateChange": None,
    },
    {
        "pointId": "IN_TSS",
        "name": "进水 TSS",
        "modelKey": "influentTss",
        "unit": "mg/L",
        "source": "manual/mock/api",
        "minValue": 0.0,
        "maxValue": 2000.0,
        "maxDelayMinutes": 15.0,
        "maxRateChange": None,
    },
    {
        "pointId": "OX_DO",
        "name": "好氧池 DO",
        "modelKey": "aerobicDo",
        "unit": "gO2/m3",
        "source": "manual/mock/api",
        "minValue": 0.0,
        "maxValue": 10.0,
        "maxDelayMinutes": 15.0,
        "maxRateChange": None,
    },
]
MUNICIPAL_FORECAST_BOUNDS: dict[str, dict[str, float]] = {
    "influentCod": {"lower": 120.0, "upper": 650.0, "lowFactor": 0.75, "highFactor": 1.25},
    "influentNh4": {"lower": 15.0, "upper": 80.0, "lowFactor": 0.75, "highFactor": 1.25},
    "influentNo3": {"lower": 0.2, "upper": 5.0, "lowFactor": 0.7, "highFactor": 1.4},
    "influentTss": {"lower": 80.0, "upper": 500.0, "lowFactor": 0.7, "highFactor": 1.3},
    "aerobicDo": {"lower": 0.5, "upper": 5.0, "lowFactor": 0.75, "highFactor": 1.25},
}
QUALITY_STATUS_ORDER = {"ok": 0, "warning": 1, "bad": 2}
CLEANING_RULES: dict[str, dict[str, str]] = {
    "range_check": {"id": "range_check", "label": "范围校验", "description": "识别并裁剪超出模型允许范围的边界值。"},
    "rate_change": {"id": "rate_change", "label": "变化率校验", "description": "用于识别短时间突变。当前版本仅保存启用状态，检测逻辑待接入。"},
    "missing_fill": {"id": "missing_fill", "label": "缺失补齐", "description": "缺失值使用当前参数兜底，并记录质量事件。"},
    "delay_check": {"id": "delay_check", "label": "延迟检测", "description": "按点位配置的最大延迟阈值识别长时间未更新数据。"},
    "parse_check": {"id": "parse_check", "label": "解析校验", "description": "识别非数值、空值或无法解析的数据。"},
}
DEFAULT_ENABLED_CLEANING_RULES = ["range_check", "rate_change", "missing_fill", "delay_check", "parse_check"]
DATA_SOURCES: dict[str, dict[str, Any]] = {
    "manual": {
        "id": "manual",
        "label": "Manual/API input",
        "kind": "api",
        "description": "Values submitted directly through the realtime API or UI controls.",
        "enabled": True,
    },
    "mock": {
        "id": "mock",
        "label": "Built-in mock data",
        "kind": "mock",
        "description": "Development data generated by the backend every 5 minutes when enabled.",
        "enabled": True,
    },
    "historian": {
        "id": "historian",
        "label": "External historian",
        "kind": "external",
        "description": "Placeholder adapter for future plant historian or SCADA integration.",
        "enabled": False,
    },
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def age_seconds(value: str | None) -> float | None:
    parsed = parse_iso(value)
    if parsed is None:
        return None
    return max(0.0, (datetime.now(timezone.utc) - parsed).total_seconds())


def add_hours_to_iso(value: str | None, hours: float) -> str:
    base = parse_iso(value) or datetime.now(timezone.utc)
    return (base + timedelta(hours=hours)).isoformat()


def later_iso(first: str | None, second: str | None) -> str:
    first_dt = parse_iso(first)
    second_dt = parse_iso(second)
    if first_dt and second_dt:
        return first if first_dt >= second_dt else second
    return first or second or now_iso()


def list_data_sources() -> dict[str, Any]:
    return {"sources": list(DATA_SOURCES.values())}


def resolve_source(quality: dict[str, Any] | None) -> dict[str, Any]:
    source_id = str((quality or {}).get("source", "manual"))
    source = DATA_SOURCES.get(source_id)
    if source:
        return source
    return {
        "id": source_id,
        "label": source_id,
        "kind": "external",
        "description": "Unregistered external realtime source.",
        "enabled": True,
    }


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def normalize_project_id(project_id: str | None = None) -> str:
    value = (project_id or DEFAULT_PROJECT_ID).strip()
    return value or DEFAULT_PROJECT_ID


def ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


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

            CREATE TABLE IF NOT EXISTS project_realtime_state (
              project_id TEXT PRIMARY KEY,
              timestamp TEXT NOT NULL,
              params_json TEXT NOT NULL,
              state_json TEXT NOT NULL,
              last_input_id INTEGER,
              updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS project_simulation_state (
              project_id TEXT PRIMARY KEY,
              timestamp TEXT NOT NULL,
              params_json TEXT NOT NULL,
              state_json TEXT NOT NULL,
              summary_json TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS cleaning_rule_configs (
              project_id TEXT PRIMARY KEY,
              enabled_rules_json TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS forecast_runs (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              project_id TEXT NOT NULL,
              created_at TEXT NOT NULL,
              source_state_id TEXT,
              source_result_id INTEGER,
              horizon_hours REAL NOT NULL,
              step_hours REAL NOT NULL,
              method TEXT NOT NULL,
              status TEXT NOT NULL,
              summary_json TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS forecast_points (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              run_id INTEGER NOT NULL,
              horizon_hour REAL NOT NULL,
              timestamp TEXT NOT NULL,
              boundary_json TEXT NOT NULL,
              effluent_json TEXT NOT NULL,
              process_json TEXT NOT NULL,
              risk_json TEXT NOT NULL,
              FOREIGN KEY(run_id) REFERENCES forecast_runs(id)
            );

            CREATE TABLE IF NOT EXISTS realtime_observations (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              project_id TEXT NOT NULL,
              timestamp TEXT NOT NULL,
              values_json TEXT NOT NULL,
              source TEXT NOT NULL,
              created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS realtime_point_configs (
              project_id TEXT NOT NULL,
              point_id TEXT NOT NULL,
              name TEXT NOT NULL,
              model_key TEXT NOT NULL,
              unit TEXT NOT NULL,
              source TEXT NOT NULL,
              enabled INTEGER NOT NULL DEFAULT 1,
              min_value REAL,
              max_value REAL,
              max_delay_minutes REAL,
              max_rate_change REAL,
              updated_at TEXT NOT NULL,
              PRIMARY KEY (project_id, point_id)
            );
            """
        )
        ensure_column(conn, "realtime_inputs", "project_id", f"TEXT NOT NULL DEFAULT '{DEFAULT_PROJECT_ID}'")
        ensure_column(conn, "realtime_results", "project_id", f"TEXT NOT NULL DEFAULT '{DEFAULT_PROJECT_ID}'")
        ensure_column(conn, "calculation_logs", "project_id", f"TEXT NOT NULL DEFAULT '{DEFAULT_PROJECT_ID}'")


def point_config_from_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "projectId": row["project_id"],
        "pointId": row["point_id"],
        "name": row["name"],
        "modelKey": row["model_key"],
        "unit": row["unit"],
        "source": row["source"],
        "enabled": bool(row["enabled"]),
        "minValue": row["min_value"],
        "maxValue": row["max_value"],
        "maxDelayMinutes": row["max_delay_minutes"],
        "maxRateChange": row["max_rate_change"],
        "updatedAt": row["updated_at"],
    }


def ensure_default_point_configs(project_id: str | None = None) -> None:
    resolved_project_id = normalize_project_id(project_id)
    updated_at = now_iso()
    with connect() as conn:
        count = conn.execute(
            "SELECT COUNT(*) AS count FROM realtime_point_configs WHERE project_id = ?",
            (resolved_project_id,),
        ).fetchone()["count"]
        if count:
            return
        for point in DEFAULT_POINT_CONFIGS:
            conn.execute(
                """
                INSERT INTO realtime_point_configs (
                  project_id, point_id, name, model_key, unit, source, enabled,
                  min_value, max_value, max_delay_minutes, max_rate_change, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?)
                """,
                (
                    resolved_project_id,
                    point["pointId"],
                    point["name"],
                    point["modelKey"],
                    point["unit"],
                    point["source"],
                    point["minValue"],
                    point["maxValue"],
                    point["maxDelayMinutes"],
                    point["maxRateChange"],
                    updated_at,
                ),
            )


def list_point_configs(project_id: str | None = None) -> dict[str, Any]:
    init_db()
    resolved_project_id = normalize_project_id(project_id)
    ensure_default_point_configs(resolved_project_id)
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM realtime_point_configs
            WHERE project_id = ?
            ORDER BY
              CASE model_key
                WHEN 'influentQ' THEN 1
                WHEN 'influentCod' THEN 2
                WHEN 'influentNh4' THEN 3
                WHEN 'influentNo3' THEN 4
                WHEN 'influentTss' THEN 5
                WHEN 'aerobicDo' THEN 6
                ELSE 99
              END,
              point_id
            """,
            (resolved_project_id,),
        ).fetchall()
    return {"projectId": resolved_project_id, "points": [point_config_from_row(row) for row in rows]}


def point_configs_by_model_key(project_id: str | None = None) -> dict[str, dict[str, Any]]:
    return {point["modelKey"]: point for point in list_point_configs(project_id)["points"]}


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


def normalize_cleaning_rules(enabled_rules: list[str] | None = None) -> list[str]:
    known = set(CLEANING_RULES)
    values = enabled_rules if enabled_rules is not None else DEFAULT_ENABLED_CLEANING_RULES
    normalized = [rule for rule in values if rule in known]
    return normalized or []


def get_cleaning_settings(project_id: str | None = None) -> dict[str, Any]:
    init_db()
    resolved_project_id = normalize_project_id(project_id)
    with connect() as conn:
        row = conn.execute("SELECT * FROM cleaning_rule_configs WHERE project_id = ?", (resolved_project_id,)).fetchone()
    enabled_rules = normalize_cleaning_rules(json.loads(row["enabled_rules_json"])) if row else DEFAULT_ENABLED_CLEANING_RULES
    return {
        "projectId": resolved_project_id,
        "enabledRules": enabled_rules,
        "rules": [{**rule, "enabled": rule_id in enabled_rules} for rule_id, rule in CLEANING_RULES.items()],
        "updatedAt": row["updated_at"] if row else None,
    }


def save_cleaning_settings(project_id: str | None = None, enabled_rules: list[str] | None = None) -> dict[str, Any]:
    init_db()
    resolved_project_id = normalize_project_id(project_id)
    normalized = normalize_cleaning_rules(enabled_rules)
    updated_at = now_iso()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO cleaning_rule_configs (project_id, enabled_rules_json, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(project_id) DO UPDATE SET
              enabled_rules_json = excluded.enabled_rules_json,
              updated_at = excluded.updated_at
            """,
            (resolved_project_id, json.dumps(normalized), updated_at),
        )
    return get_cleaning_settings(resolved_project_id)


def combine_quality_status(current: str, candidate: str) -> str:
    return candidate if QUALITY_STATUS_ORDER[candidate] > QUALITY_STATUS_ORDER[current] else current


def quality_score_label(score: float | None) -> str:
    if score is None:
        return "暂无评分"
    if score >= 90:
        return "可信"
    if score >= 75:
        return "需关注"
    if score >= 60:
        return "低可信"
    return "不可用"


def quality_score_band(score: float | None) -> str:
    if score is None:
        return "none"
    if score >= 90:
        return "good"
    if score >= 75:
        return "watch"
    if score >= 60:
        return "poor"
    return "bad"


def quality_score_from_report(quality: dict[str, Any] | None) -> float | None:
    if not quality:
        return None
    scores = [
        float(field["score"])
        for field in (quality.get("fieldQuality") or {}).values()
        if field.get("enabled", True) and isinstance(field.get("score"), (int, float))
    ]
    if scores:
        average = sum(scores) / len(scores)
        worst_sensitive_score = min(average, min(scores) + 20)
        return round(worst_sensitive_score, 1)
    if isinstance(quality.get("score"), (int, float)):
        return float(quality["score"])
    return None


def assess_realtime_values(
    values: dict[str, Any],
    base_params: dict[str, float],
    quality: dict[str, Any] | None = None,
    project_id: str | None = None,
    timestamp: str | None = None,
) -> dict[str, Any]:
    normalized, parse_warnings = normalize_values(values, base_params)
    cleaning_settings = get_cleaning_settings(project_id)
    point_configs = list_point_configs(project_id)["points"]
    enabled_rules = set(cleaning_settings["enabledRules"])
    accepted: dict[str, float] = {}
    field_quality: dict[str, dict[str, Any]] = {}
    issues: list[dict[str, Any]] = []
    status = "ok"

    if "parse_check" in enabled_rules:
        for warning in parse_warnings:
            status = combine_quality_status(status, "warning")
            issues.append({"severity": "warning", "code": "parse_error", "message": warning})

    record_age_seconds = age_seconds(timestamp)
    for point in point_configs:
        key = point["modelKey"]
        if key not in REALTIME_BOUNDARY_KEYS:
            continue
        source = "input"
        field_status = "ok"
        field_issues: list[dict[str, Any]] = []
        score = 100
        raw_value = normalized.get(key)
        value = raw_value

        if not point["enabled"]:
            value = base_params[key]
            source = "disabled"
            field_status = "idle"
            score = 0
            field_issues.append({"code": "disabled", "message": f"{point['name']} 未启用，模型使用当前参数值。", "scoreImpact": -100})
            accepted[key] = float(value)
            field_quality[key] = {
                "pointId": point["pointId"],
                "pointName": point["name"],
                "modelKey": key,
                "unit": point["unit"],
                "enabled": point["enabled"],
                "status": field_status,
                "source": source,
                "value": accepted[key],
                "rawValue": raw_value,
                "score": score,
                "scoreLabel": quality_score_label(score),
                "scoreBand": quality_score_band(score),
                "scoreReasons": [issue["message"] for issue in field_issues],
                "issues": field_issues,
            }
            continue

        if value is None:
            value = base_params[key]
            source = "fallback_param"
            if "missing_fill" in enabled_rules:
                field_status = "warning"
                score = min(score, 70)
                issue = {"severity": "warning", "code": "missing_value", "field": key, "pointId": point["pointId"], "scoreImpact": -30, "message": f"{point['name']} 缺失，使用当前参数值。"}
                field_issues.append(issue)
                issues.append(issue)
        else:
            minimum = point["minValue"] if point["minValue"] is not None else (PARAM_LIMITS.get(key) or (None, None))[0]
            maximum = point["maxValue"] if point["maxValue"] is not None else (PARAM_LIMITS.get(key) or (None, None))[1]
            limits = (minimum, maximum) if minimum is not None and maximum is not None else None
            if limits and "range_check" in enabled_rules:
                if value < minimum or value > maximum:
                    clipped = max(minimum, min(maximum, value))
                    issue = {
                        "severity": "warning",
                        "code": "out_of_range_clipped",
                        "field": key,
                        "pointId": point["pointId"],
                        "value": value,
                        "clippedValue": clipped,
                        "scoreImpact": -35,
                        "message": f"{point['name']}={value:g} 超出范围，已裁剪到 {clipped:g}。",
                    }
                    field_issues.append(issue)
                    issues.append(issue)
                    value = clipped
                    source = "clipped_input"
                    field_status = "warning"
                    score = min(score, 65)

        if "delay_check" in enabled_rules and point["maxDelayMinutes"] and record_age_seconds is not None:
            if record_age_seconds > float(point["maxDelayMinutes"]) * 60:
                field_status = "warning" if field_status == "ok" else field_status
                score = min(score, 75)
                issue = {
                    "severity": "warning",
                    "code": "delay",
                    "field": key,
                    "pointId": point["pointId"],
                    "ageSeconds": record_age_seconds,
                    "scoreImpact": -25,
                    "message": f"{point['name']} 距最近时间超过 {point['maxDelayMinutes']:g} 分钟。",
                }
                field_issues.append(issue)
                issues.append(issue)

        accepted[key] = float(value)
        if field_status in QUALITY_STATUS_ORDER:
            status = combine_quality_status(status, field_status)
        field_quality[key] = {
            "pointId": point["pointId"],
            "pointName": point["name"],
            "modelKey": key,
            "unit": point["unit"],
            "enabled": point["enabled"],
            "status": field_status,
            "source": source,
            "value": accepted[key],
            "rawValue": raw_value,
            "score": score,
            "scoreLabel": quality_score_label(score),
            "scoreBand": quality_score_band(score),
            "scoreReasons": [issue["message"] for issue in field_issues] or ["数据解析、范围与延迟校验通过。"],
            "issues": field_issues,
        }

    for key in REALTIME_BOUNDARY_KEYS:
        if key not in accepted:
            accepted[key] = float(base_params[key])

    overall_score = quality_score_from_report({"fieldQuality": field_quality})

    source_name = (quality or {}).get("source", "manual")
    source = resolve_source({"source": source_name})
    if issues and (quality or {}).get("strict"):
        status = "bad"
    return {
        **(quality or {}),
        "source": source_name,
        "sourceInfo": source,
        "status": status,
        "score": overall_score,
        "scoreLabel": quality_score_label(overall_score),
        "scoreBand": quality_score_band(overall_score),
        "fieldQuality": field_quality,
        "issues": issues,
        "acceptedValues": accepted,
        "pointConfigs": point_configs,
        "cleaningRules": cleaning_settings,
        "rawKeys": sorted(values.keys()),
    }


def update_input_quality(input_id: int, quality: dict[str, Any]) -> None:
    init_db()
    with connect() as conn:
        conn.execute("UPDATE realtime_inputs SET quality_json = ? WHERE id = ?", (json.dumps(quality), input_id))


def ingest_input(timestamp: str | None, values: dict[str, Any], quality: dict[str, Any] | None = None, project_id: str | None = None) -> dict[str, Any]:
    resolved_project_id = normalize_project_id(project_id)
    saved = load_state(resolved_project_id)
    base_params = sanitize_params(saved["params"] if saved else get_saved_params()["params"])
    ts = timestamp or now_iso()
    enriched_quality = assess_realtime_values(values, base_params, quality, resolved_project_id, ts)
    return insert_input(ts, values, enriched_quality, resolved_project_id)


def insert_input(timestamp: str | None, values: dict[str, Any], quality: dict[str, Any] | None = None, project_id: str | None = None) -> dict[str, Any]:
    init_db()
    ts = timestamp or now_iso()
    resolved_project_id = normalize_project_id(project_id)
    with connect() as conn:
        cursor = conn.execute(
            "INSERT INTO realtime_inputs (project_id, timestamp, values_json, quality_json, created_at) VALUES (?, ?, ?, ?, ?)",
            (resolved_project_id, ts, json.dumps(values), json.dumps(quality or {}), now_iso()),
        )
        row_id = cursor.lastrowid
    return {"id": row_id, "projectId": resolved_project_id, "timestamp": ts, "values": values, "quality": quality or {}}


def get_latest_input(project_id: str | None = None) -> dict[str, Any] | None:
    init_db()
    resolved_project_id = normalize_project_id(project_id)
    with connect() as conn:
        row = conn.execute("SELECT * FROM realtime_inputs WHERE project_id = ? ORDER BY id DESC LIMIT 1", (resolved_project_id,)).fetchone()
    if not row:
        return None
    return {
        "id": row["id"],
        "projectId": row["project_id"],
        "timestamp": row["timestamp"],
        "values": json.loads(row["values_json"]),
        "quality": json.loads(row["quality_json"]),
    }


def load_state(project_id: str | None = None) -> dict[str, Any] | None:
    init_db()
    resolved_project_id = normalize_project_id(project_id)
    with connect() as conn:
        row = conn.execute("SELECT * FROM project_realtime_state WHERE project_id = ?", (resolved_project_id,)).fetchone()
    if not row:
        return None
    return {
        "projectId": row["project_id"],
        "timestamp": row["timestamp"],
        "params": json.loads(row["params_json"]),
        "state": json.loads(row["state_json"]),
        "lastInputId": row["last_input_id"],
        "updatedAt": row["updated_at"],
    }


def save_state(timestamp: str, params: dict[str, float], state: dict[str, Any], input_id: int | None, project_id: str | None = None) -> None:
    init_db()
    resolved_project_id = normalize_project_id(project_id)
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO project_realtime_state (project_id, timestamp, params_json, state_json, last_input_id, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(project_id) DO UPDATE SET
              timestamp = excluded.timestamp,
              params_json = excluded.params_json,
              state_json = excluded.state_json,
              last_input_id = excluded.last_input_id,
              updated_at = excluded.updated_at
            """,
            (resolved_project_id, timestamp, json.dumps(params), json.dumps(state), input_id, now_iso()),
        )


def load_simulation_state(project_id: str | None = None) -> dict[str, Any] | None:
    init_db()
    resolved_project_id = normalize_project_id(project_id)
    with connect() as conn:
        row = conn.execute("SELECT * FROM project_simulation_state WHERE project_id = ?", (resolved_project_id,)).fetchone()
    if not row:
        return None
    return {
        "projectId": row["project_id"],
        "timestamp": row["timestamp"],
        "params": json.loads(row["params_json"]),
        "state": json.loads(row["state_json"]),
        "summary": json.loads(row["summary_json"]),
        "updatedAt": row["updated_at"],
    }


def save_simulation_state(
    project_id: str | None,
    params: dict[str, Any],
    state: dict[str, Any],
    summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    init_db()
    resolved_project_id = normalize_project_id(project_id)
    timestamp = now_iso()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO project_simulation_state (project_id, timestamp, params_json, state_json, summary_json, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(project_id) DO UPDATE SET
              timestamp = excluded.timestamp,
              params_json = excluded.params_json,
              state_json = excluded.state_json,
              summary_json = excluded.summary_json,
              updated_at = excluded.updated_at
            """,
            (
                resolved_project_id,
                timestamp,
                json.dumps(params),
                json.dumps(state),
                json.dumps(summary or {}),
                timestamp,
            ),
        )
    return {"projectId": resolved_project_id, "updatedAt": timestamp}


def clear_simulation_state(project_id: str | None = None) -> dict[str, Any]:
    init_db()
    resolved_project_id = normalize_project_id(project_id)
    with connect() as conn:
        cursor = conn.execute("DELETE FROM project_simulation_state WHERE project_id = ?", (resolved_project_id,))
    return {"status": "cleared", "projectId": resolved_project_id, "deleted": cursor.rowcount}


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
    project_id: str | None = None,
) -> dict[str, Any]:
    init_db()
    created_at = now_iso()
    resolved_project_id = normalize_project_id(project_id)
    with connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO calculation_logs (project_id, event, status, message, detail_json, duration_ms, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (resolved_project_id, event, status, message, json.dumps(detail or {}), duration_ms, created_at),
        )
        row_id = int(cursor.lastrowid)
    return {
        "id": row_id,
        "projectId": resolved_project_id,
        "event": event,
        "status": status,
        "message": message,
        "detail": detail or {},
        "durationMs": duration_ms,
        "createdAt": created_at,
    }


def list_calculation_logs(limit: int = 100, project_id: str | None = None) -> dict[str, Any]:
    init_db()
    safe_limit = max(1, min(int(limit), 500))
    resolved_project_id = normalize_project_id(project_id)
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM calculation_logs WHERE project_id = ? ORDER BY id DESC LIMIT ?",
            (resolved_project_id, safe_limit),
        ).fetchall()
    logs = [
        {
            "id": row["id"],
            "projectId": row["project_id"],
            "event": row["event"],
            "status": row["status"],
            "message": row["message"],
            "detail": json.loads(row["detail_json"]),
            "durationMs": row["duration_ms"],
            "createdAt": row["created_at"],
        }
        for row in rows
    ]
    return {"logs": logs, "limit": safe_limit, "projectId": resolved_project_id}


def clear_calculation_logs(project_id: str | None = None) -> dict[str, Any]:
    init_db()
    resolved_project_id = normalize_project_id(project_id)
    with connect() as conn:
        cursor = conn.execute("DELETE FROM calculation_logs WHERE project_id = ?", (resolved_project_id,))
        deleted = cursor.rowcount
    return {"status": "cleared", "deleted": deleted, "projectId": resolved_project_id}


def insert_result(timestamp: str, input_id: int | None, step_hours: float, result: dict[str, Any], warnings: list[str], project_id: str | None = None) -> int:
    init_db()
    resolved_project_id = normalize_project_id(project_id)
    with connect() as conn:
        cursor = conn.execute(
            "INSERT INTO realtime_results (project_id, timestamp, input_id, step_hours, result_json, warnings_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (resolved_project_id, timestamp, input_id, step_hours, json.dumps(result), json.dumps(warnings), now_iso()),
        )
        return int(cursor.lastrowid)


def get_latest_result(project_id: str | None = None) -> dict[str, Any] | None:
    init_db()
    resolved_project_id = normalize_project_id(project_id)
    with connect() as conn:
        row = conn.execute("SELECT * FROM realtime_results WHERE project_id = ? ORDER BY id DESC LIMIT 1", (resolved_project_id,)).fetchone()
    if not row:
        return None
    return {
        "id": row["id"],
        "projectId": row["project_id"],
        "timestamp": row["timestamp"],
        "inputId": row["input_id"],
        "stepHours": row["step_hours"],
        "result": json.loads(row["result_json"]),
        "warnings": json.loads(row["warnings_json"]),
        "createdAt": row["created_at"],
    }


OBSERVATION_ALIASES = {
    "COD": "effCod",
    "cod": "effCod",
    "effCod": "effCod",
    "NH4": "effNh4",
    "nh4": "effNh4",
    "NH4-N": "effNh4",
    "effNh4": "effNh4",
    "TN": "effTn",
    "tn": "effTn",
    "effTn": "effTn",
    "TSS": "effTss",
    "tss": "effTss",
    "effTss": "effTss",
}
OBSERVATION_METRICS = {
    "effCod": {"label": "COD", "unit": "mg/L", "thresholds": {"good": 5.0, "watch": 12.0}},
    "effNh4": {"label": "NH4-N", "unit": "mg/L", "thresholds": {"good": 0.8, "watch": 2.0}},
    "effTn": {"label": "TN", "unit": "mg/L", "thresholds": {"good": 2.0, "watch": 5.0}},
    "effTss": {"label": "TSS", "unit": "mg/L", "thresholds": {"good": 2.0, "watch": 5.0}},
}
MOCK_OBSERVATION_BIAS = {
    "effCod": 0.01,
    "effNh4": 0.04,
    "effTn": 0.02,
    "effTss": 0.03,
}


def normalize_observation_values(values: dict[str, Any]) -> dict[str, float]:
    normalized: dict[str, float] = {}
    for key, value in (values or {}).items():
        target = OBSERVATION_ALIASES.get(key, key)
        if target not in OBSERVATION_METRICS:
            continue
        parsed = _finite(value, math.nan)
        if math.isfinite(parsed):
            normalized[target] = parsed
    return normalized


def insert_observation(
    timestamp: str | None,
    values: dict[str, Any],
    source: str = "manual",
    project_id: str | None = None,
) -> dict[str, Any]:
    init_db()
    resolved_project_id = normalize_project_id(project_id)
    normalized = normalize_observation_values(values)
    if not normalized:
        raise ValueError("Observation values must include at least one of COD, NH4, TN, or TSS.")
    observed_at = timestamp or now_iso()
    with connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO realtime_observations (project_id, timestamp, values_json, source, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (resolved_project_id, observed_at, json.dumps(normalized), source or "manual", now_iso()),
        )
        row_id = int(cursor.lastrowid)
    return {
        "id": row_id,
        "projectId": resolved_project_id,
        "timestamp": observed_at,
        "values": normalized,
        "source": source or "manual",
    }


def generate_mock_observation(
    project_id: str | None = None,
    source: str = "mock-lab",
    noise_fraction: float = 0.03,
) -> dict[str, Any]:
    latest_result = get_latest_result(project_id)
    if not latest_result:
        raise ValueError("No realtime result is available for mock observation generation.")
    result = latest_result.get("result") or {}
    bounded_noise = max(0.0, min(float(noise_fraction), 0.25))
    values: dict[str, float] = {}
    for metric in OBSERVATION_METRICS:
        predicted = _finite(result.get(metric), math.nan)
        if not math.isfinite(predicted):
            continue
        bias = MOCK_OBSERVATION_BIAS.get(metric, 0.0)
        noise = random.uniform(-bounded_noise, bounded_noise)
        values[metric] = max(0.0, predicted * (1 + bias + noise))
    if not values:
        raise ValueError("Latest realtime result does not contain observable effluent metrics.")
    observation = insert_observation(
        timestamp=result.get("modelTimestamp") or latest_result.get("timestamp"),
        values=values,
        source=source,
        project_id=project_id,
    )
    observation["basisResultId"] = latest_result["id"]
    observation["noiseFraction"] = bounded_noise
    return observation


def list_observations(project_id: str | None = None, hours: float = 24, limit: int = 200) -> dict[str, Any]:
    init_db()
    resolved_project_id = normalize_project_id(project_id)
    safe_limit = max(1, min(int(limit), 500))
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=max(float(hours), 0.1))).isoformat()
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM realtime_observations
            WHERE project_id = ? AND timestamp >= ?
            ORDER BY timestamp DESC, id DESC
            LIMIT ?
            """,
            (resolved_project_id, cutoff, safe_limit),
        ).fetchall()
    observations = [
        {
            "id": row["id"],
            "projectId": row["project_id"],
            "timestamp": row["timestamp"],
            "values": json.loads(row["values_json"]),
            "source": row["source"],
            "createdAt": row["created_at"],
        }
        for row in reversed(rows)
    ]
    return {"projectId": resolved_project_id, "hours": hours, "limit": safe_limit, "observations": observations}


def _find_closest_result(observation_time: datetime, results: list[dict[str, Any]], max_lag_hours: float) -> dict[str, Any] | None:
    best: dict[str, Any] | None = None
    best_delta = float("inf")
    for record in results:
        result_time = parse_iso(record.get("result", {}).get("modelTimestamp") or record.get("timestamp"))
        if result_time is None:
            continue
        delta = abs((result_time - observation_time).total_seconds()) / 3600
        if delta <= max_lag_hours and delta < best_delta:
            best = record
            best_delta = delta
    if best is not None:
        best = dict(best)
        best["matchLagHours"] = best_delta
    return best


def _trust_grade(mae: float | None, metric: str) -> str:
    if mae is None:
        return "no_data"
    thresholds = OBSERVATION_METRICS[metric]["thresholds"]
    if mae <= thresholds["good"]:
        return "good"
    if mae <= thresholds["watch"]:
        return "watch"
    return "poor"


def _trust_suggestions(metric_summary: list[dict[str, Any]]) -> list[dict[str, Any]]:
    suggestions: list[dict[str, Any]] = []
    for row in metric_summary:
        if not row["count"] or row["grade"] == "good":
            continue
        metric = row["metric"]
        bias = row.get("bias")
        direction = "模型预测偏高" if bias and bias > 0 else "模型预测偏低"
        severity = "warning" if row["grade"] == "watch" else "critical"
        if metric == "effNh4":
            suggestions.append(
                {
                    "metric": metric,
                    "severity": severity,
                    "title": "复核硝化能力",
                    "reason": f"NH4-N 误差已进入{ '关注' if row['grade'] == 'watch' else '校准' }区间，当前表现为{direction}。",
                    "actions": ["核对好氧池 DO、SRT 和 MLSS", "检查硝化菌参数 muA / bA / kA", "优先用最近 24-72 小时 NH4 实测值做阶段校准"],
                }
            )
        elif metric == "effTn":
            suggestions.append(
                {
                    "metric": metric,
                    "severity": severity,
                    "title": "复核反硝化与内回流",
                    "reason": f"TN 误差偏大，当前表现为{direction}。",
                    "actions": ["核对内回流比和缺氧区 NO3", "检查可利用碳源和 COD 组分分配", "校准反硝化相关半饱和与水解参数"],
                }
            )
        elif metric == "effTss":
            suggestions.append(
                {
                    "metric": metric,
                    "severity": severity,
                    "title": "复核二沉池与排泥",
                    "reason": f"TSS 误差偏大，当前表现为{direction}。",
                    "actions": ["核对二沉池截留率、沉降参数和污泥层", "检查 WAS 排泥量与 MLSS", "优先校准 Takacs 沉降参数和截留效率"],
                }
            )
        elif metric == "effCod":
            suggestions.append(
                {
                    "metric": metric,
                    "severity": severity,
                    "title": "复核 COD 组分分配",
                    "reason": f"COD 误差偏大，当前表现为{direction}。",
                    "actions": ["核对进水 COD 在线仪表和实验室数据", "检查可溶/颗粒/惰性 COD 比例", "校准水解和异养菌相关参数"],
                }
            )
    if not suggestions and any(row["count"] for row in metric_summary):
        suggestions.append(
            {
                "metric": "overall",
                "severity": "info",
                "title": "保持观测闭环",
                "reason": "最近观测与模型结果整体一致，暂不需要触发校准。",
                "actions": ["继续积累实测出水数据", "保留关键指标的 24-72 小时误差趋势", "当连续偏差扩大时再进入校准中心"],
            }
        )
    return suggestions


def realtime_trust(project_id: str | None = None, hours: float = 24, max_lag_hours: float = 2.0) -> dict[str, Any]:
    resolved_project_id = normalize_project_id(project_id)
    history = realtime_history(resolved_project_id, hours, 500)
    observations = list_observations(resolved_project_id, hours, 500)["observations"]
    results = history["results"]
    comparisons: list[dict[str, Any]] = []
    metric_errors: dict[str, list[float]] = {key: [] for key in OBSERVATION_METRICS}
    metric_biases: dict[str, list[float]] = {key: [] for key in OBSERVATION_METRICS}
    trend: list[dict[str, Any]] = []
    for observation in observations:
        observation_time = parse_iso(observation.get("timestamp"))
        if observation_time is None:
            continue
        matched = _find_closest_result(observation_time, results, max_lag_hours)
        if not matched:
            continue
        result = matched.get("result") or {}
        metrics: dict[str, Any] = {}
        for metric, observed in observation.get("values", {}).items():
            predicted = _finite(result.get(metric), math.nan)
            if not math.isfinite(predicted):
                continue
            residual = predicted - observed
            metrics[metric] = {
                "label": OBSERVATION_METRICS[metric]["label"],
                "unit": OBSERVATION_METRICS[metric]["unit"],
                "observed": observed,
                "predicted": predicted,
                "residual": residual,
                "absoluteError": abs(residual),
            }
            metric_errors[metric].append(abs(residual))
            metric_biases[metric].append(residual)
            trend.append(
                {
                    "timestamp": observation["timestamp"],
                    "resultTime": result.get("modelTimestamp") or matched.get("timestamp"),
                    "source": observation.get("source"),
                    "metric": metric,
                    "label": OBSERVATION_METRICS[metric]["label"],
                    "unit": OBSERVATION_METRICS[metric]["unit"],
                    "observed": observed,
                    "predicted": predicted,
                    "residual": residual,
                    "absoluteError": abs(residual),
                }
            )
        if metrics:
            comparisons.append(
                {
                    "observationId": observation["id"],
                    "observationTime": observation["timestamp"],
                    "resultId": matched["id"],
                    "resultTime": result.get("modelTimestamp") or matched.get("timestamp"),
                    "matchLagHours": matched.get("matchLagHours"),
                    "source": observation.get("source"),
                    "metrics": metrics,
                }
            )
    metric_summary = []
    for metric, meta in OBSERVATION_METRICS.items():
        errors = metric_errors[metric]
        biases = metric_biases[metric]
        mae = sum(errors) / len(errors) if errors else None
        bias = sum(biases) / len(biases) if biases else None
        rmse = math.sqrt(sum(error * error for error in errors) / len(errors)) if errors else None
        metric_summary.append(
            {
                "metric": metric,
                "label": meta["label"],
                "unit": meta["unit"],
                "count": len(errors),
                "mae": mae,
                "bias": bias,
                "rmse": rmse,
                "grade": _trust_grade(mae, metric),
            }
        )
    grade_rank = {"good": 3, "watch": 2, "poor": 1, "no_data": 0}
    available = [row for row in metric_summary if row["count"]]
    if not available:
        overall = "no_data"
    elif any(row["grade"] == "poor" for row in available):
        overall = "poor"
    elif any(row["grade"] == "watch" for row in available):
        overall = "watch"
    else:
        overall = "good"
    return {
        "projectId": resolved_project_id,
        "hours": hours,
        "maxLagHours": max_lag_hours,
        "overall": overall,
        "observationCount": len(observations),
        "matchedCount": len(comparisons),
        "unmatchedCount": max(0, len(observations) - len(comparisons)),
        "metrics": metric_summary,
        "comparisons": comparisons[-50:],
        "trend": trend[-200:],
        "suggestions": _trust_suggestions(metric_summary),
        "statusText": {
            "good": "可信度良好",
            "watch": "需要关注",
            "poor": "需要校准",
            "no_data": "缺少实测数据",
        }[overall],
    }


def realtime_history(project_id: str | None = None, hours: float = 12, limit: int = 200) -> dict[str, Any]:
    init_db()
    resolved_project_id = normalize_project_id(project_id)
    safe_limit = max(1, min(int(limit), 500))
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=max(float(hours), 0.1))).isoformat()
    with connect() as conn:
        input_rows = conn.execute(
            """
            SELECT * FROM realtime_inputs
            WHERE project_id = ? AND timestamp >= ?
            ORDER BY timestamp DESC, id DESC
            LIMIT ?
            """,
            (resolved_project_id, cutoff, safe_limit),
        ).fetchall()
        result_rows = conn.execute(
            """
            SELECT * FROM realtime_results
            WHERE project_id = ? AND timestamp >= ?
            ORDER BY timestamp DESC, id DESC
            LIMIT ?
            """,
            (resolved_project_id, cutoff, safe_limit),
        ).fetchall()

    inputs = [
        {
            "id": row["id"],
            "projectId": row["project_id"],
            "timestamp": row["timestamp"],
            "values": json.loads(row["values_json"]),
            "quality": json.loads(row["quality_json"]),
            "createdAt": row["created_at"],
        }
        for row in reversed(input_rows)
    ]
    results = [
        {
            "id": row["id"],
            "projectId": row["project_id"],
            "timestamp": row["timestamp"],
            "inputId": row["input_id"],
            "stepHours": row["step_hours"],
            "result": json.loads(row["result_json"]),
            "warnings": json.loads(row["warnings_json"]),
            "createdAt": row["created_at"],
        }
        for row in reversed(result_rows)
    ]
    return {
        "projectId": resolved_project_id,
        "hours": hours,
        "limit": safe_limit,
        "inputs": inputs,
        "results": results,
    }


def realtime_quality_score(project_id: str | None = None, hours: float = 12, limit: int = 200) -> dict[str, Any]:
    resolved_project_id = normalize_project_id(project_id)
    history = realtime_history(resolved_project_id, hours, limit)
    points = list_point_configs(resolved_project_id)["points"]
    latest_input = get_latest_input(resolved_project_id)
    inputs = history["inputs"]
    point_scores: list[dict[str, Any]] = []
    current_quality = (latest_input or {}).get("quality") or {}
    field_quality = current_quality.get("fieldQuality") or {}
    for point in points:
        field = field_quality.get(point["modelKey"]) or {}
        score = field.get("score")
        point_scores.append(
            {
                "pointId": point["pointId"],
                "name": point["name"],
                "modelKey": point["modelKey"],
                "unit": point["unit"],
                "enabled": point["enabled"],
                "score": score if isinstance(score, (int, float)) else None,
                "scoreLabel": field.get("scoreLabel") or quality_score_label(score if isinstance(score, (int, float)) else None),
                "scoreBand": field.get("scoreBand") or quality_score_band(score if isinstance(score, (int, float)) else None),
                "status": field.get("status", "unknown"),
                "source": field.get("source", "unknown"),
                "reasons": field.get("scoreReasons") or [],
            }
        )

    issue_counts: dict[str, int] = {}
    trend: list[dict[str, Any]] = []
    scores: list[float] = []
    for record in inputs:
        quality = record.get("quality") or {}
        score = quality_score_from_report(quality)
        if score is not None:
            scores.append(score)
        trend.append(
            {
                "timestamp": record["timestamp"],
                "score": score,
                "scoreLabel": quality_score_label(score),
                "scoreBand": quality_score_band(score),
                "status": quality.get("status", "unknown"),
                "issueCount": len(quality.get("issues") or []),
            }
        )
        for issue in quality.get("issues") or []:
            code = str(issue.get("code") or "unknown")
            issue_counts[code] = issue_counts.get(code, 0) + 1

    current_score = quality_score_from_report(current_quality)
    return {
        "projectId": resolved_project_id,
        "hours": hours,
        "limit": history["limit"],
        "current": {
            "timestamp": (latest_input or {}).get("timestamp"),
            "score": current_score,
            "scoreLabel": quality_score_label(current_score),
            "scoreBand": quality_score_band(current_score),
            "status": current_quality.get("status", "none") if latest_input else "none",
            "issueCount": len(current_quality.get("issues") or []),
            "pointScores": point_scores,
        },
        "rolling": {
            "recordCount": len(inputs),
            "averageScore": round(sum(scores) / len(scores), 1) if scores else None,
            "minScore": min(scores) if scores else None,
            "issueCounts": issue_counts,
            "trend": trend[-200:],
        },
    }


def realtime_step(
    timestamp: str | None = None,
    values: dict[str, Any] | None = None,
    quality: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
    step_hours: float | None = None,
    project_id: str | None = None,
) -> dict[str, Any]:
    init_db()
    resolved_project_id = normalize_project_id(project_id)
    saved = load_state(resolved_project_id)
    clean_params = sanitize_params(saved["params"] if saved else params)
    if params:
        clean_params.update(sanitize_params(params))
    errors, warnings = validate_params(clean_params)
    if errors:
        raise ValueError("; ".join(errors))

    input_record = None
    inserted_input = values is not None
    if values is not None:
        input_record = insert_input(timestamp, values, quality, resolved_project_id)
    else:
        input_record = get_latest_input(resolved_project_id)
    if not input_record:
        input_record = insert_input(timestamp, {}, quality, resolved_project_id)

    quality_report = assess_realtime_values(input_record["values"], clean_params, input_record["quality"], resolved_project_id, input_record["timestamp"])
    if input_record.get("id"):
        update_input_quality(input_record["id"], quality_report)
        input_record["quality"] = quality_report
    boundary_values = quality_report["acceptedValues"]
    warnings.extend(issue["message"] for issue in quality_report.get("issues", []))
    ctx = SimulationContext(params=clean_params, source_name="realtime", mode="realtime")
    state = saved["state"] if saved else ctx.create_simulation_state()
    step = float(step_hours if step_hours is not None else clean_params["timeStepHours"])
    base_timestamp = saved["timestamp"] if saved else input_record["timestamp"]
    if inserted_input:
        base_timestamp = later_iso(base_timestamp, input_record["timestamp"])
    model_timestamp = add_hours_to_iso(base_timestamp, step)
    stepped = ctx.step_realtime_state(state, boundary_values, step)
    result = stepped["snapshot"]
    result["mode"] = "realtime"
    result["projectId"] = resolved_project_id
    result["timestamp"] = model_timestamp
    result["modelTimestamp"] = model_timestamp
    result["inputTimestamp"] = input_record["timestamp"]
    result["inputId"] = input_record["id"]
    result["createdNewInput"] = inserted_input
    result["warnings"] = warnings
    result["quality"] = quality_report
    result["validation"] = {"ok": True, "warningCount": len(warnings), "warnings": warnings}

    save_state(model_timestamp, ctx.params, stepped["state"], input_record["id"], resolved_project_id)
    result_id = insert_result(model_timestamp, input_record["id"], step, result, warnings, resolved_project_id)
    return {"resultId": result_id, "projectId": resolved_project_id, "input": input_record, "result": result, "state": load_state(resolved_project_id)}


def mock_base_params(project_id: str | None = None) -> dict[str, float]:
    saved = load_state(project_id)
    if saved and saved.get("params"):
        return sanitize_params(saved["params"])
    return DEFAULT_PARAMS.copy()


def mock_profile_config(profile: str | None = None) -> dict[str, Any]:
    profile_id = str(profile or MOCK_STATUS.get("profile") or "normal").strip().lower()
    if profile_id not in MOCK_PROFILES:
        raise ValueError(f"Unknown mock profile: {profile_id}")
    return MOCK_PROFILES[profile_id]


def mock_profile_params(profile: str | None = None, project_id: str | None = None) -> dict[str, float]:
    params = mock_base_params(project_id)
    params.update(mock_profile_config(profile)["params"])
    return sanitize_params(params)


def warm_start_mock_state(project_id: str | None = None, profile: str | None = None, days: float = 10.0) -> dict[str, Any]:
    resolved_project_id = normalize_project_id(project_id)
    params = mock_profile_params(profile, resolved_project_id)
    params.update({"simulationDays": days, "outputIntervalHours": 24, "timeStepHours": max(params.get("timeStepHours", 0.5), 0.5)})
    ctx = SimulationContext(params=params, source_name="mock warm start", mode="realtime")
    result = ctx.run_asm1_simulation()
    final_state = result.get("finalState")
    if not final_state:
        raise ValueError("Mock warm start failed to produce a final state.")
    save_state(now_iso(), ctx.params, final_state, None, resolved_project_id)
    return {
        "projectId": resolved_project_id,
        "profile": mock_profile_config(profile)["id"],
        "days": days,
        "effCod": result["effCod"][-1],
        "effNh4": result["effNh4"][-1],
        "effTn": result["effTn"][-1],
        "effTss": result["effTss"][-1],
    }


def generate_mock_values(run_count: int | None = None, profile: str | None = None, project_id: str | None = None) -> dict[str, float]:
    config = mock_profile_config(profile)
    params = mock_profile_params(config["id"], project_id)
    index = MOCK_STATUS["runCount"] if run_count is None else run_count
    phase = (index % 288) / 288 * math.tau

    def vary(name: str, base: float, floor: float = 0.0) -> float:
        amplitude = config["amplitude"].get(name, 0.1)
        noise = config["noise"].get(name, 0.03)
        periodic = 1 + amplitude * math.sin(phase)
        jitter = 1 + random.uniform(-noise, noise)
        return max(floor, base * periodic * jitter)

    return {
        "Q": vary("Q", params["influentQ"], 1),
        "COD": vary("COD", params["influentCod"], 80),
        "NH4": vary("NH4", params["influentNh4"], 10),
        "NO3": vary("NO3", params["influentNo3"], 0.1),
        "TSS": vary("TSS", params["influentTss"], 60),
        "DO": max(0.2, min(5.0, params["aerobicDo"] * (1 + config["amplitude"].get("DO", 0.1) * math.sin(phase + math.pi / 4)) + random.uniform(-config["noise"].get("DO", 0.04), config["noise"].get("DO", 0.04)))),
    }


def run_mock_once(project_id: str | None = None, profile: str | None = None) -> dict[str, Any]:
    resolved_project_id = normalize_project_id(project_id)
    profile_id = mock_profile_config(profile or MOCK_STATUS.get("profile"))["id"]
    started = datetime.now(timezone.utc)
    try:
        values = generate_mock_values(profile=profile_id, project_id=resolved_project_id)
        result = realtime_step(
            timestamp=now_iso(),
            values=values,
            quality={"source": "mock", "profile": profile_id, "profileLabel": mock_profile_config(profile_id)["label"]},
            params=mock_profile_params(profile_id, resolved_project_id),
            step_hours=MOCK_STEP_HOURS,
            project_id=resolved_project_id,
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
            {"resultId": result["resultId"], "stepHours": MOCK_STEP_HOURS, "profile": profile_id},
            duration_ms,
            resolved_project_id,
        )
        return result
    except Exception as exc:
        duration_ms = (datetime.now(timezone.utc) - started).total_seconds() * 1000
        insert_calculation_log("mock_run", "failed", str(exc), {"stepHours": MOCK_STEP_HOURS}, duration_ms, resolved_project_id)
        raise


async def mock_loop() -> None:
    try:
        while True:
            await asyncio.sleep(MOCK_STATUS["intervalSeconds"])
            try:
                run_mock_once(MOCK_STATUS.get("projectId"), MOCK_STATUS.get("profile"))
            except Exception as exc:  # pragma: no cover - defensive background guard
                MOCK_STATUS["lastError"] = str(exc)
    except asyncio.CancelledError:
        raise


async def start_mock(
    interval_seconds: int = MOCK_INTERVAL_SECONDS,
    project_id: str | None = None,
    profile: str | None = None,
    warm_start: bool = True,
) -> dict[str, Any]:
    global MOCK_TASK
    if interval_seconds <= 0:
        raise ValueError("interval_seconds must be positive.")
    profile_id = mock_profile_config(profile)["id"]
    resolved_project_id = normalize_project_id(project_id)
    MOCK_STATUS["intervalSeconds"] = interval_seconds
    MOCK_STATUS["projectId"] = resolved_project_id
    MOCK_STATUS["profile"] = profile_id
    warm_result = None
    if warm_start:
        warm_started = datetime.now(timezone.utc)
        warm_result = warm_start_mock_state(resolved_project_id, profile_id)
        insert_calculation_log(
            "mock_warm_start",
            "success",
            f"Mock {mock_profile_config(profile_id)['label']} 暖启动完成。",
            warm_result,
            (datetime.now(timezone.utc) - warm_started).total_seconds() * 1000,
            resolved_project_id,
        )
    if MOCK_TASK and not MOCK_TASK.done():
        MOCK_STATUS["running"] = True
        status = mock_status()
        status["warmStart"] = warm_result
        return status
    MOCK_STATUS["running"] = True
    MOCK_STATUS["lastError"] = None
    try:
        run_mock_once(resolved_project_id, profile_id)
    except Exception as exc:
        MOCK_STATUS["lastError"] = str(exc)
    MOCK_TASK = asyncio.create_task(mock_loop())
    status = mock_status()
    status["warmStart"] = warm_result
    return status


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
    status = dict(MOCK_STATUS)
    status["profiles"] = [
        {"id": item["id"], "label": item["label"], "description": item["description"]}
        for item in MOCK_PROFILES.values()
    ]
    status["profileLabel"] = mock_profile_config(status.get("profile"))["label"]
    return status


def latest(project_id: str | None = None) -> dict[str, Any]:
    resolved_project_id = normalize_project_id(project_id)
    return {"projectId": resolved_project_id, "input": get_latest_input(resolved_project_id), "state": load_state(resolved_project_id), "result": get_latest_result(resolved_project_id)}


def realtime_status(project_id: str | None = None) -> dict[str, Any]:
    resolved_project_id = normalize_project_id(project_id)
    latest_input = get_latest_input(resolved_project_id)
    latest_state = load_state(resolved_project_id)
    latest_result = get_latest_result(resolved_project_id)
    input_quality = (latest_input or {}).get("quality") or {}
    quality_status = input_quality.get("status", "unknown") if latest_input else "none"
    input_age = age_seconds((latest_input or {}).get("timestamp"))
    result_age = age_seconds((latest_result or {}).get("timestamp"))
    state_age = age_seconds((latest_state or {}).get("updatedAt"))
    scheduler = {
        "mock": mock_status(),
        "lastInputAgeSeconds": input_age,
        "lastResultAgeSeconds": result_age,
        "lastStateUpdateAgeSeconds": state_age,
        "status": "idle",
    }
    if scheduler["mock"].get("running"):
        scheduler["status"] = "mock_running"
    elif latest_result:
        scheduler["status"] = "ready"
    elif latest_input:
        scheduler["status"] = "input_waiting"

    return {
        "status": scheduler["status"],
        "projectId": resolved_project_id,
        "dataSources": list(DATA_SOURCES.values()),
        "latestInput": latest_input,
        "latestResult": latest_result,
        "latestState": latest_state,
        "qualityStatus": quality_status,
        "scheduler": scheduler,
        "counts": realtime_counts(resolved_project_id),
    }


def realtime_counts(project_id: str | None = None) -> dict[str, int]:
    init_db()
    resolved_project_id = normalize_project_id(project_id)
    with connect() as conn:
        inputs = conn.execute("SELECT COUNT(*) AS count FROM realtime_inputs WHERE project_id = ?", (resolved_project_id,)).fetchone()["count"]
        results = conn.execute("SELECT COUNT(*) AS count FROM realtime_results WHERE project_id = ?", (resolved_project_id,)).fetchone()["count"]
        states = conn.execute("SELECT COUNT(*) AS count FROM project_realtime_state WHERE project_id = ?", (resolved_project_id,)).fetchone()["count"]
    return {"inputs": int(inputs), "results": int(results), "states": int(states)}


def _finite(value: Any, fallback: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return fallback
    return parsed if math.isfinite(parsed) else fallback


def _clamp_param(key: str, value: float, params: dict[str, Any]) -> float:
    lower, upper = PARAM_LIMITS.get(key, (0.0, max(abs(value) * 10, 1.0)))
    return float(max(lower, min(upper, value)))


def _record_boundary_value(record: dict[str, Any], key: str, params: dict[str, Any]) -> float:
    quality = record.get("quality") or {}
    values = record.get("values") or {}
    aliases = {
        "influentQ": ["Q", "q", "flow"],
        "influentCod": ["COD", "cod"],
        "influentNh4": ["NH4", "nh4"],
        "influentNo3": ["NO3", "no3"],
        "influentTss": ["TSS", "tss"],
        "aerobicDo": ["DO", "do"],
    }
    accepted = quality.get("acceptedValues") or {}
    if key in accepted:
        return _finite(accepted[key], _finite(params.get(key), 0.0))
    if key in values:
        return _finite(values[key], _finite(params.get(key), 0.0))
    for alias in aliases.get(key, []):
        if alias in values:
            return _finite(values[alias], _finite(params.get(key), 0.0))
    return _finite(params.get(key), 0.0)


def _series_stats(values: list[float]) -> tuple[float, float]:
    if not values:
        return 0.0, 0.0
    mean = sum(values) / len(values)
    variance = sum((value - mean) ** 2 for value in values) / max(len(values), 1)
    return mean, math.sqrt(max(variance, 0.0))


def _forecast_interval(key: str, median: float, uncertainty: float, params: dict[str, Any]) -> tuple[float, float]:
    if key == "influentQ":
        lower = max(_clamp_param(key, median * 0.75, params), median - uncertainty)
        upper = min(_clamp_param(key, median * 1.25, params), median + uncertainty)
        return lower, max(lower, upper)
    bounds = MUNICIPAL_FORECAST_BOUNDS.get(key)
    if not bounds:
        lower = _clamp_param(key, median - uncertainty, params)
        upper = _clamp_param(key, median + uncertainty, params)
        return lower, max(lower, upper)
    lower = max(bounds["lower"], median * bounds["lowFactor"], median - uncertainty)
    upper = min(bounds["upper"], median * bounds["highFactor"], median + uncertainty)
    lower = _clamp_param(key, lower, params)
    upper = _clamp_param(key, upper, params)
    return min(lower, upper), max(lower, upper)


def _forecast_median_value(key: str, value: float, params: dict[str, Any]) -> float:
    value = _clamp_param(key, value, params)
    bounds = MUNICIPAL_FORECAST_BOUNDS.get(key)
    if not bounds:
        return value
    return float(max(bounds["lower"], min(bounds["upper"], value)))


def _forecast_boundaries(history: dict[str, Any], params: dict[str, Any], horizon_hours: int) -> list[dict[str, Any]]:
    inputs = history.get("inputs") or []
    keys = ["influentQ", "influentCod", "influentNh4", "influentNo3", "influentTss", "aerobicDo"]
    current_values = {key: _finite(params.get(key), 0.0) for key in keys}
    series_by_key: dict[str, list[float]] = {key: [] for key in keys}
    for record in inputs:
        for key in keys:
            value = _record_boundary_value(record, key, params)
            series_by_key[key].append(value)
            current_values[key] = value

    if inputs:
        first_time = parse_iso(inputs[0].get("timestamp"))
        last_time = parse_iso(inputs[-1].get("timestamp"))
        elapsed_hours = max(((last_time - first_time).total_seconds() / 3600) if first_time and last_time else 1.0, 1.0)
    else:
        elapsed_hours = 1.0

    forecast: list[dict[str, Any]] = []
    for hour in range(1, horizon_hours + 1):
        scenarios = {"low": {}, "median": {}, "high": {}}
        for key in keys:
            values = series_by_key[key]
            latest = current_values[key]
            if len(values) >= 2:
                raw_slope = (values[-1] - values[0]) / elapsed_hours
            else:
                raw_slope = 0.0
            max_slope = max(abs(latest) * 0.08, 0.02)
            slope = max(-max_slope, min(max_slope, raw_slope))
            _, deviation = _series_stats(values[-48:] if values else [latest])
            base_uncertainty = max(deviation, abs(latest) * 0.035, 0.02)
            uncertainty = min(base_uncertainty * (0.75 + hour / max(horizon_hours, 1)), max(abs(latest) * 0.22, 0.05))
            median = _forecast_median_value(key, latest + slope * hour, params)
            low_value, high_value = _forecast_interval(key, median, uncertainty, params)
            scenarios["low"][key] = low_value
            scenarios["median"][key] = median
            scenarios["high"][key] = high_value
        for scenario in scenarios.values():
            scenario["rasRatio"] = _finite(params.get("rasRatio"), DEFAULT_PARAMS["rasRatio"])
            scenario["internalRecycleRatio"] = _finite(params.get("internalRecycleRatio"), DEFAULT_PARAMS["internalRecycleRatio"])
            scenario["wasQ"] = _finite(params.get("wasQ"), DEFAULT_PARAMS["wasQ"])
        forecast.append({"hour": hour, "scenarios": scenarios})
    return forecast


FORECAST_METRICS: dict[str, dict[str, Any]] = {
    "NH4": {"label": "NH4-N", "unit": "gN/m3", "reference": 5.0, "source": "effNh4"},
    "COD": {"label": "COD", "unit": "gCOD/m3", "reference": 60.0, "source": "effCod"},
    "TN": {"label": "TN", "unit": "gN/m3", "reference": 15.0, "source": "effTn"},
    "TP": {"label": "TP", "unit": "gP/m3", "reference": 0.5, "source": None},
}


def _risk_for(metric: str, high_value: float | None) -> str:
    reference = FORECAST_METRICS[metric]["reference"]
    if high_value is None:
        return "unavailable"
    if high_value >= reference:
        return "warning"
    if high_value >= reference * 0.85:
        return "watch"
    return "ok"


def _range_from_snapshots(metric: str, low: dict[str, Any], median: dict[str, Any], high: dict[str, Any]) -> dict[str, Any]:
    source = FORECAST_METRICS[metric]["source"]
    if not source:
        return {
            "low": None,
            "median": None,
            "high": None,
            "reference": FORECAST_METRICS[metric]["reference"],
            "unit": FORECAST_METRICS[metric]["unit"],
            "risk": "unavailable",
            "note": "当前 ASM1 引擎不包含磷过程，TP 仅保留为后续 ASM2d/除磷模型入口。",
        }
    raw_values = [_finite(low.get(source)), _finite(median.get(source)), _finite(high.get(source))]
    low_value, median_value, high_value = sorted(raw_values)
    values = {
        "low": low_value,
        "median": median_value,
        "high": high_value,
    }
    values["reference"] = FORECAST_METRICS[metric]["reference"]
    values["unit"] = FORECAST_METRICS[metric]["unit"]
    values["risk"] = _risk_for(metric, values["high"])
    return values


def _latest_effluent(latest_result: dict[str, Any] | None) -> dict[str, Any]:
    result = (latest_result or {}).get("result") or {}
    return {
        "COD": result.get("effCod"),
        "NH4": result.get("effNh4"),
        "TN": result.get("effTn"),
        "TSS": result.get("effTss"),
        "DO": result.get("aerobicDo"),
        "MLSS": result.get("aerobicMlss"),
        "timestamp": result.get("modelTimestamp") or (latest_result or {}).get("timestamp"),
    }


def _forecast_advice(points: list[dict[str, Any]], latest_result: dict[str, Any] | None, params: dict[str, Any]) -> dict[str, Any]:
    nh4_watch = [point for point in points if point["metrics"]["NH4"]["risk"] in {"watch", "warning"}]
    tss = _finite(((latest_result or {}).get("result") or {}).get("effTss"), 0.0)
    aerobic_do = _finite(((latest_result or {}).get("result") or {}).get("aerobicDo"), params.get("aerobicDo", 2.0))
    mlss = _finite(((latest_result or {}).get("result") or {}).get("aerobicMlss"), 0.0)
    return {
        "riskLevel": "warning" if nh4_watch or tss >= 10 else "ok",
        "riskWindow": {
            "startHour": nh4_watch[0]["hour"] if nh4_watch else None,
            "endHour": nh4_watch[-1]["hour"] if nh4_watch else None,
            "message": f"+{nh4_watch[0]['hour']}h 至 +{nh4_watch[-1]['hour']}h 接近参考线" if nh4_watch else "未来 8 小时未触发主要出水风险窗口",
        },
        "actions": [
            {"label": "好氧池 DO", "from": round(aerobic_do, 2), "to": round(max(aerobic_do, params.get("aerobicDo", 2.0)) + 0.3, 2), "unit": "gO2/m3"},
            {"label": "内回流比", "from": round(params.get("internalRecycleRatio", 2.0) * 100), "to": round(max(params.get("internalRecycleRatio", 2.0), 2.0) * 120), "unit": "%"},
            {"label": "剩余污泥", "from": round(params.get("wasQ", 350)), "to": round(params.get("wasQ", 350)), "unit": "m3/d"},
            {"label": "复核点位", "from": "NH4 / DO", "to": "NH4 / DO", "unit": ""},
        ],
        "monitors": {
            "MLSS": mlss,
            "anaerobicDO": (((latest_result or {}).get("result") or {}).get("units") or {}).get("anaerobic", {}).get("DO"),
            "anoxicDO": (((latest_result or {}).get("result") or {}).get("units") or {}).get("anoxic", {}).get("DO"),
            "aerobicDO": aerobic_do,
            "WAS": params.get("wasQ"),
        },
        "notes": [
            "预测基于最近实时边界的趋势和波动生成低/中/高负荷情景。",
            "预测运行只读取当前模型状态，不会推进或覆盖真实实时状态。",
            "TP 暂未进入 ASM1 计算，需后续接入 ASM2d 或除磷模块。",
        ],
    }


def _save_forecast(project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    init_db()
    with connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO forecast_runs (project_id, created_at, source_state_id, source_result_id, horizon_hours, step_hours, method, status, summary_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project_id,
                payload["createdAt"],
                payload.get("sourceStateTimestamp"),
                payload.get("sourceResultId"),
                payload["horizonHours"],
                payload["stepHours"],
                payload["method"],
                payload["status"],
                json.dumps(payload["summary"]),
            ),
        )
        run_id = int(cursor.lastrowid)
        for point in payload["points"]:
            conn.execute(
                """
                INSERT INTO forecast_points (run_id, horizon_hour, timestamp, boundary_json, effluent_json, process_json, risk_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    point["hour"],
                    point["timestamp"],
                    json.dumps(point["boundaries"]),
                    json.dumps(point["metrics"]),
                    json.dumps(point.get("process", {})),
                    json.dumps(point.get("risk", {})),
                ),
            )
    payload["runId"] = run_id
    return payload


def realtime_forecast(project_id: str | None = None, horizon_hours: int = 8, step_hours: float = 1.0, history_hours: float = 24) -> dict[str, Any]:
    init_db()
    resolved_project_id = normalize_project_id(project_id)
    safe_horizon = max(1, min(int(horizon_hours), 24))
    safe_step = max(0.05, min(float(step_hours), 6.0))
    saved_state = load_state(resolved_project_id)
    latest_result = get_latest_result(resolved_project_id)
    latest_input = get_latest_input(resolved_project_id)
    params = sanitize_params(saved_state["params"] if saved_state else get_saved_params()["params"])
    history = realtime_history(resolved_project_id, history_hours, 500)
    boundary_forecast = _forecast_boundaries(history, params, safe_horizon)
    base_ctx = SimulationContext(params=params.copy(), source_name="forecast", mode="forecast")
    base_state = base_ctx.normalize_simulation_state(saved_state["state"], int(params["clarifierLayers"])) if saved_state else base_ctx.create_simulation_state()
    scenario_states = {
        "low": base_ctx.copy_simulation_state(base_state),
        "median": base_ctx.copy_simulation_state(base_state),
        "high": base_ctx.copy_simulation_state(base_state),
    }
    scenario_contexts = {
        name: SimulationContext(params=params.copy(), source_name="forecast", mode="forecast")
        for name in scenario_states
    }

    base_timestamp = (saved_state or {}).get("timestamp") or (latest_result or {}).get("timestamp") or now_iso()
    points: list[dict[str, Any]] = []
    for item in boundary_forecast:
        hour = int(item["hour"])
        snapshots: dict[str, dict[str, Any]] = {}
        for scenario_name, boundary_values in item["scenarios"].items():
            stepped = scenario_contexts[scenario_name].step_realtime_state(scenario_states[scenario_name], boundary_values, safe_step)
            scenario_states[scenario_name] = stepped["state"]
            snapshots[scenario_name] = stepped["snapshot"]
        metrics = {
            metric: _range_from_snapshots(metric, snapshots["low"], snapshots["median"], snapshots["high"])
            for metric in FORECAST_METRICS
        }
        point_risks = {metric: values["risk"] for metric, values in metrics.items()}
        points.append(
            {
                "hour": hour,
                "timestamp": add_hours_to_iso(base_timestamp, hour * safe_step),
                "boundaries": item["scenarios"],
                "metrics": metrics,
                "process": {
                    "aerobicDO": snapshots["median"].get("aerobicDo"),
                    "aerobicMLSS": snapshots["median"].get("aerobicMlss"),
                    "rasMLSS": snapshots["median"].get("rasMlss"),
                },
                "risk": point_risks,
            }
        )

    advice = _forecast_advice(points, latest_result, params)
    payload = {
        "projectId": resolved_project_id,
        "createdAt": now_iso(),
        "sourceStateTimestamp": (saved_state or {}).get("timestamp"),
        "sourceResultId": (latest_result or {}).get("id"),
        "horizonHours": safe_horizon,
        "stepHours": safe_step,
        "historyHours": history_hours,
        "method": "trend_scenario_asm1_v1",
        "status": "ready",
        "current": {
            "input": latest_input,
            "effluent": _latest_effluent(latest_result),
            "state": {
                "timestamp": (saved_state or {}).get("timestamp"),
                "hasState": bool(saved_state),
            },
        },
        "points": points,
        "summary": {
            "riskLevel": advice["riskLevel"],
            "riskWindow": advice["riskWindow"],
            "historyInputCount": len(history.get("inputs") or []),
            "historyResultCount": len(history.get("results") or []),
            "metricReferences": {key: {"label": value["label"], "unit": value["unit"], "reference": value["reference"]} for key, value in FORECAST_METRICS.items()},
        },
        "advice": advice,
    }
    return _save_forecast(resolved_project_id, payload)


def reset(project_id: str | None = None) -> dict[str, str]:
    init_db()
    resolved_project_id = normalize_project_id(project_id)
    with connect() as conn:
        conn.execute("DELETE FROM realtime_inputs WHERE project_id = ?", (resolved_project_id,))
        conn.execute("DELETE FROM project_realtime_state WHERE project_id = ?", (resolved_project_id,))
        conn.execute("DELETE FROM realtime_results WHERE project_id = ?", (resolved_project_id,))
    return {"status": "reset", "projectId": resolved_project_id}
