from __future__ import annotations

from typing import Any, Callable

from .engine_bsm1 import run_bsm1_simulation
from .engine_v2 import V2_SOLVER_METHODS, run_vector_simulation_v2
from .model import (
    SimulationContext,
    normalize_csv_records,
    sanitize_params,
    simulate,
    validate_csv_records,
    validate_params,
)
from .model_trust import assess_result_credibility


def normalize_engine_version(params: dict[str, Any] | None) -> str:
    value = (params or {}).get("engineVersion", "v1")
    normalized = str(value).strip().lower()
    if normalized in {"", "1", "v1"}:
        return "v1"
    if normalized in {"2", "v2"}:
        return "v2"
    if normalized in {"bsm1", "bsm"}:
        return "bsm1"
    raise ValueError("engineVersion 必须是 v1、v2 或 bsm1。")


def _merge_warnings(result: dict[str, Any], warnings: list[str]) -> dict[str, Any]:
    merged = warnings + result.get("warnings", [])
    result["warnings"] = merged
    result["validation"] = {
        "ok": True,
        "warningCount": len(merged),
        "warnings": merged,
    }
    return result


def normalize_v2_solver_method(params: dict[str, Any] | None) -> str:
    method = str((params or {}).get("solverMethod", "RK4")).strip().upper()
    if method not in V2_SOLVER_METHODS:
        raise ValueError("engine_v2 solverMethod 必须是 RK4、LSODA、BDF 或 Radau。")
    return method


def simulate_with_engine(
    params: dict[str, Any] | None = None,
    csv_text: str = "",
    csv_file_name: str = "",
    progress_callback: Callable[[float, float], None] | None = None,
) -> dict[str, Any]:
    engine_version = normalize_engine_version(params)
    if engine_version == "v1":
        result = simulate(
            params=params,
            csv_text=csv_text,
            csv_file_name=csv_file_name,
            progress_callback=progress_callback,
        )
        result["engineVersion"] = "v1"
        result["credibility"] = assess_result_credibility(result, params)
        return result

    clean_params = sanitize_params(params)
    clean_params["solverMethod"] = "RK4"
    errors, warnings = validate_params(clean_params)
    if errors:
        raise ValueError("; ".join(errors))
    if engine_version == "bsm1":
        ctx = SimulationContext(
            params=clean_params,
            source_name=csv_file_name or "",
            mode="csv" if csv_text.strip() else "manual",
            progress_callback=progress_callback,
        )
        records = None
        if csv_text.strip():
            records = normalize_csv_records(csv_text, ctx)
            warnings.extend(validate_csv_records(records, clean_params))
        result = run_bsm1_simulation(ctx, records)
        result["engineVersion"] = "bsm1"
        result = _merge_warnings(result, warnings)
        result["credibility"] = assess_result_credibility(result, clean_params)
        return result

    clean_params["solverMethod"] = normalize_v2_solver_method(params)

    ctx = SimulationContext(
        params=clean_params,
        source_name=csv_file_name or "",
        mode="csv" if csv_text.strip() else "manual",
        progress_callback=progress_callback,
    )
    records = None
    if csv_text.strip():
        records = normalize_csv_records(csv_text, ctx)
        warnings.extend(validate_csv_records(records, clean_params))
    result = run_vector_simulation_v2(ctx, records)
    result["engineVersion"] = "v2"
    result = _merge_warnings(result, warnings)
    result["credibility"] = assess_result_credibility(result, clean_params)
    return result
