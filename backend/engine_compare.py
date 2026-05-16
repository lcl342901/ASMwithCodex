from __future__ import annotations

from typing import Any

from .engine_v2 import run_vector_simulation_v2
from .model import (
    SimulationContext,
    normalize_csv_records,
    sanitize_params,
    simulate,
    validate_csv_records,
    validate_params,
)


EFFLUENT_METRICS = ["effCod", "effNh4", "effNo3", "effTn", "effTss"]
CLARIFIER_METRICS = ["topTss", "middleTss", "bottomTss", "effluentTss", "underflowTss"]


def _last(series: dict[str, Any], key: str) -> float:
    values = series.get(key, [])
    if not values:
        raise ValueError(f"result series missing {key}")
    return float(values[-1])


def _last_nested(series: dict[str, Any], group: str, key: str) -> float:
    values = series.get(group, {}).get(key, [])
    if not values:
        raise ValueError(f"result series missing {group}.{key}")
    return float(values[-1])


def error_row(metric: str, v1_value: float, v2_value: float) -> dict[str, float | str]:
    abs_error = v2_value - v1_value
    rel_error = abs(abs_error) / max(abs(v1_value), 1e-9)
    return {
        "metric": metric,
        "v1": v1_value,
        "v2": v2_value,
        "absError": abs_error,
        "relError": rel_error,
    }


def build_error_table(v1_result: dict[str, Any], v2_result: dict[str, Any], metrics: list[str]) -> list[dict[str, float | str]]:
    return [error_row(metric, _last(v1_result, metric), _last(v2_result, metric)) for metric in metrics]


def build_clarifier_error_table(v1_result: dict[str, Any], v2_result: dict[str, Any]) -> list[dict[str, float | str]]:
    return [
        error_row(metric, _last_nested(v1_result, "clarifier", metric), _last_nested(v2_result, "clarifier", metric))
        for metric in CLARIFIER_METRICS
    ]


def readiness_from_errors(effluent_errors: list[dict[str, float | str]], clarifier_errors: list[dict[str, float | str]]) -> dict[str, Any]:
    max_effluent_rel = max((float(row["relError"]) for row in effluent_errors), default=0.0)
    max_clarifier_rel = max((float(row["relError"]) for row in clarifier_errors), default=0.0)
    open_api_allowed = max_effluent_rel <= 0.05 and max_clarifier_rel <= 0.1
    return {
        "openApiAllowed": open_api_allowed,
        "status": "candidate" if open_api_allowed else "needs_review",
        "maxEffluentRelError": max_effluent_rel,
        "maxClarifierRelError": max_clarifier_rel,
        "criteria": {
            "maxEffluentRelError": 0.05,
            "maxClarifierRelError": 0.1,
        },
        "notes": [
            "engine_v2 仍为实验引擎；即使误差满足阈值，也需要更多工况和公开参考案例验证。",
            "若 needs_review，优先检查连续二沉池层 RHS、RAS 更新方式和输出采样时间。",
        ],
    }


def compare_engines(
    params: dict[str, Any] | None = None,
    csv_text: str = "",
    csv_file_name: str = "",
) -> dict[str, Any]:
    clean_params = sanitize_params(params)
    errors, warnings = validate_params(clean_params)
    if errors:
        raise ValueError("; ".join(errors))

    v1_result = simulate(params=clean_params, csv_text=csv_text, csv_file_name=csv_file_name)

    ctx = SimulationContext(
        params=clean_params.copy(),
        source_name=csv_file_name or "",
        mode="csv" if csv_text.strip() else "manual",
    )
    records = None
    if csv_text.strip():
        records = normalize_csv_records(csv_text, ctx)
        warnings.extend(validate_csv_records(records, clean_params))
    v2_result = run_vector_simulation_v2(ctx, records)

    effluent_errors = build_error_table(v1_result, v2_result, EFFLUENT_METRICS)
    clarifier_errors = build_clarifier_error_table(v1_result, v2_result)
    readiness = readiness_from_errors(effluent_errors, clarifier_errors)

    return {
        "engineComparison": "v1_vs_v2",
        "mode": "csv" if csv_text.strip() else "manual",
        "sourceName": csv_file_name or "",
        "time": {
            "v1Final": _last(v1_result, "time"),
            "v2Final": _last(v2_result, "time"),
        },
        "effluentErrors": effluent_errors,
        "clarifierErrors": clarifier_errors,
        "apiReadiness": readiness,
        "warnings": warnings + v2_result.get("warnings", []),
        "results": {
            "v1": v1_result,
            "v2": v2_result,
        },
    }
