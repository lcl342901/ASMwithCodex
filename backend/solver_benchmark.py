from __future__ import annotations

from time import perf_counter
from typing import Any

from .engine_runner import simulate_with_engine
from .engine_compare import EFFLUENT_METRICS, error_row


DEFAULT_SOLVERS = ["RK4", "LSODA", "BDF", "RADAU"]
DEFAULT_LONG_HORIZONS = [20, 50, 100]


def _last(result: dict[str, Any], key: str) -> float:
    values = result.get(key, [])
    if not values:
        raise ValueError(f"result missing {key}")
    return float(values[-1])


def summarize_result(result: dict[str, Any]) -> dict[str, float]:
    return {metric: _last(result, metric) for metric in EFFLUENT_METRICS}


def benchmark_v2_solvers(
    base_params: dict[str, Any] | None = None,
    solvers: list[str] | None = None,
    horizons: list[float] | None = None,
) -> dict[str, Any]:
    """Benchmark v2 solver methods.

    The helper is intentionally parameterized. Unit tests use short horizons,
    while manual P4 analysis can pass `[20, 50, 100]` when runtime is acceptable.
    """

    solver_list = [solver.upper() for solver in (solvers or DEFAULT_SOLVERS)]
    horizon_list = horizons or [0.1]
    runs: list[dict[str, Any]] = []

    for horizon in horizon_list:
        baseline_summary = None
        for solver in solver_list:
            params = {
                **(base_params or {}),
                "engineVersion": "v2",
                "solverMethod": solver,
                "simulationDays": horizon,
            }
            started = perf_counter()
            result = simulate_with_engine(params)
            duration_ms = (perf_counter() - started) * 1000
            summary = summarize_result(result)
            if solver == "RK4" or baseline_summary is None:
                baseline_summary = summary
            errors = [
                error_row(metric, baseline_summary[metric], summary[metric])
                for metric in EFFLUENT_METRICS
            ]
            runs.append(
                {
                    "horizonDays": horizon,
                    "solverMethod": solver,
                    "durationMs": duration_ms,
                    "points": len(result.get("time", [])),
                    "finalTime": _last(result, "time"),
                    "summary": summary,
                    "errorsVsRk4": errors,
                    "warningCount": result.get("validation", {}).get("warningCount", 0),
                }
            )

    recommendation = recommend_solver_strategy(runs)
    return {
        "engineVersion": "v2",
        "solvers": solver_list,
        "horizons": horizon_list,
        "runs": runs,
        "recommendation": recommendation,
    }


def recommend_solver_strategy(runs: list[dict[str, Any]]) -> dict[str, Any]:
    if not runs:
        return {"defaultSolver": "RK4", "reason": "No benchmark runs were provided."}

    grouped: dict[str, list[dict[str, Any]]] = {}
    for run in runs:
        grouped.setdefault(str(run["solverMethod"]), []).append(run)

    safe_candidates = []
    for solver, solver_runs in grouped.items():
        max_rel_error = max(
            (float(error["relError"]) for run in solver_runs for error in run["errorsVsRk4"]),
            default=0.0,
        )
        avg_duration = sum(float(run["durationMs"]) for run in solver_runs) / len(solver_runs)
        safe_candidates.append({"solverMethod": solver, "maxRelError": max_rel_error, "avgDurationMs": avg_duration})

    acceptable = [candidate for candidate in safe_candidates if candidate["maxRelError"] <= 0.05]
    if not acceptable:
        return {
            "defaultSolver": "RK4",
            "reason": "No adaptive solver stayed within the 5% effluent relative-error threshold versus RK4.",
            "candidates": safe_candidates,
        }

    fastest = min(acceptable, key=lambda candidate: candidate["avgDurationMs"])
    return {
        "defaultSolver": fastest["solverMethod"],
        "reason": "Selected the fastest solver within the 5% effluent relative-error threshold versus RK4.",
        "candidates": safe_candidates,
    }


def project_long_horizon_durations(
    benchmark_report: dict[str, Any],
    target_horizons: list[float] | None = None,
) -> dict[str, Any]:
    """Project long-horizon durations from measured short benchmark runs.

    This is deliberately marked as a projection. It is useful for deciding
    whether a full 20/50/100 day benchmark is worth running interactively.
    """

    horizons = target_horizons or DEFAULT_LONG_HORIZONS
    measured_runs = benchmark_report.get("runs", [])
    projections = []
    for run in measured_runs:
        source_horizon = float(run["horizonDays"])
        if source_horizon <= 0:
            continue
        for target in horizons:
            scale = float(target) / source_horizon
            projections.append(
                {
                    "solverMethod": run["solverMethod"],
                    "sourceHorizonDays": source_horizon,
                    "targetHorizonDays": float(target),
                    "measuredDurationMs": run["durationMs"],
                    "projectedDurationMs": run["durationMs"] * scale,
                    "projectionMethod": "linear_by_simulation_days",
                }
            )
    return {
        "type": "duration_projection",
        "engineVersion": benchmark_report.get("engineVersion", "v2"),
        "sourceHorizons": benchmark_report.get("horizons", []),
        "targetHorizons": horizons,
        "projections": projections,
        "warning": "Projected durations are not a substitute for actual long-horizon benchmark runs.",
    }


def step_consistency_report(
    base_params: dict[str, Any] | None = None,
    solver: str = "RK4",
    time_steps_hours: list[float] | None = None,
    horizon_days: float = 0.1,
) -> dict[str, Any]:
    steps = time_steps_hours or [0.5, 0.04167]
    runs = []
    baseline_summary = None
    for step in steps:
        params = {
            **(base_params or {}),
            "engineVersion": "v2",
            "solverMethod": solver.upper(),
            "simulationDays": horizon_days,
            "timeStepHours": step,
        }
        result = simulate_with_engine(params)
        summary = summarize_result(result)
        if baseline_summary is None:
            baseline_summary = summary
        runs.append(
            {
                "timeStepHours": step,
                "points": len(result.get("time", [])),
                "finalTime": _last(result, "time"),
                "summary": summary,
                "errorsVsFirstStep": [
                    error_row(metric, baseline_summary[metric], summary[metric])
                    for metric in EFFLUENT_METRICS
                ],
            }
        )
    max_rel_error = max((float(error["relError"]) for run in runs for error in run["errorsVsFirstStep"]), default=0.0)
    return {
        "engineVersion": "v2",
        "solverMethod": solver.upper(),
        "horizonDays": horizon_days,
        "timeStepsHours": steps,
        "runs": runs,
        "maxRelError": max_rel_error,
        "status": "consistent" if max_rel_error <= 0.01 else "needs_review",
        "criteria": {"maxRelError": 0.01},
    }
