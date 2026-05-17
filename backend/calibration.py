from __future__ import annotations

import math
from time import perf_counter
from typing import Any, Callable

from .engine_bsm1 import run_bsm1_simulation
from .engine_runner import simulate_with_engine
from .model import DEFAULT_PARAMS, PARAM_LIMITS, sanitize_params, validate_params
from .model import SimulationContext
from .model_trust import CALIBRATION_TARGETS, RECOMMENDED_TUNABLE_PARAMS, compare_to_reference_case, get_reference_case


BSM1_MAPPING_NOTE = (
    "BSM1 has two anoxic tanks followed by three aerobic tanks. This mapping approximates that layout in the "
    "current three-zone AAO engine by keeping a minimal anaerobic selector volume and assigning the BSM1 anoxic "
    "and aerobic volumes to the anoxic and aerobic zones. It is suitable for alignment experiments, not final validation."
)


CALIBRATION_STAGES = [
    {
        "id": "nitrification",
        "name": "Nitrification / NH4",
        "description": "Focuses on autotrophic growth and ammonia affinity.",
        "targets": ["effNh4"],
        "tunableParams": ["muA", "kNH", "kOA", "bA"],
    },
    {
        "id": "denitrification_tn",
        "name": "Denitrification / TN",
        "description": "Focuses on nitrate, total nitrogen, anoxic kinetics, and carbon availability.",
        "targets": ["effNo3", "effTn"],
        "tunableParams": ["etaG", "kNO", "muH", "kS"],
    },
    {
        "id": "cod_bod",
        "name": "COD / BOD",
        "description": "Focuses on organic removal and hydrolysis behavior.",
        "targets": ["effCod", "bod5"],
        "tunableParams": ["muH", "kH", "kS", "yH", "bH"],
    },
    {
        "id": "clarifier_tss",
        "name": "Clarifier / TSS",
        "description": "Focuses on solids separation and Takacs settling parameters.",
        "targets": ["effTss"],
        "tunableParams": ["takacsRH", "takacsRP", "takacsV0", "takacsV0Max"],
    },
]


def bsm1_mapped_params(overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    params = {
        **DEFAULT_PARAMS,
        "influentQ": 18446,
        "influentCod": 300,
        "influentNh4": 31.56,
        "influentNo3": 0,
        "influentTss": 211,
        "solubleCodFraction": 40,
        "inertSolubleFraction": 10,
        "inertParticulateFraction": 25,
        "influentOrganicNFactor": 0.2,
        "anaerobicVolume": 1,
        "anoxicVolume": 2000,
        "aerobicVolume": 4000,
        "clarifierArea": 1500,
        "clarifierHeight": 4,
        "clarifierLayers": 10,
        "clarifierFeedLayer": 5,
        "rasRatio": 1.0,
        "internalRecycleRatio": 3.0,
        "wasQ": 385,
        "aerobicDo": 2.0,
        "initialAnaerobicDo": 0.05,
        "initialAnoxicDo": 0.05,
        "initialAerobicDo": 2.0,
        "simulationDays": 14,
        "timeStepHours": 0.5,
        "outputIntervalHours": 1,
        "solverMethod": "RK4",
    }
    if overrides:
        params.update(overrides)
    return sanitize_params(params)


def bsm1_mapping_report(overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    params = bsm1_mapped_params(overrides)
    errors, warnings = validate_params(params)
    if errors:
        raise ValueError("; ".join(errors))
    return {
        "caseId": "bsm1_alignment_placeholder",
        "mapping": "three_zone_aao_approximation",
        "status": "needs_validation",
        "note": BSM1_MAPPING_NOTE,
        "params": params,
        "warnings": warnings,
        "volumeMapping": {
            "bsm1AnoxicVolumeM3": 2000,
            "bsm1AerobicVolumeM3": 4000,
            "mappedAnaerobicVolumeM3": params["anaerobicVolume"],
            "mappedAnoxicVolumeM3": params["anoxicVolume"],
            "mappedAerobicVolumeM3": params["aerobicVolume"],
        },
        "flowMapping": {
            "averageDryWeatherFlowM3D": params["influentQ"],
            "rasRatio": params["rasRatio"],
            "internalRecycleRatio": params["internalRecycleRatio"],
            "wasQ": params["wasQ"],
        },
    }


def calibration_stage_configs() -> dict[str, Any]:
    return {"stages": CALIBRATION_STAGES}


def get_calibration_stage(stage_id: str) -> dict[str, Any]:
    for stage in CALIBRATION_STAGES:
        if stage["id"] == stage_id:
            return stage
    raise ValueError(f"未知校准阶段：{stage_id}。")


def finite_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def interpolate_series(times: list[float], values: list[float], target_time: float) -> float | None:
    if not times or not values or len(times) != len(values):
        return None
    if target_time <= times[0]:
        return values[0]
    if target_time >= times[-1]:
        return values[-1]
    for index in range(1, len(times)):
        if times[index] >= target_time:
            left_t = times[index - 1]
            right_t = times[index]
            left_v = values[index - 1]
            right_v = values[index]
            if right_t == left_t:
                return right_v
            ratio = (target_time - left_t) / (right_t - left_t)
            return left_v + (right_v - left_v) * ratio
    return values[-1]


def metric_series(result: dict[str, Any], metric: str) -> list[float] | None:
    if metric == "bod5":
        series = result.get("units", {}).get("effluent", {}).get("BOD5")
    else:
        series = result.get(metric)
    if not isinstance(series, list):
        return None
    values = [finite_float(value) for value in series]
    if any(value is None for value in values):
        return None
    return [float(value) for value in values]


def observation_objective(result: dict[str, Any], observations: list[dict[str, Any]], targets: list[str], weights: dict[str, float] | None = None) -> dict[str, Any]:
    times = metric_series(result, "time")
    if not times:
        raise ValueError("仿真结果缺少有效 time 序列。")
    weights = weights or {}
    errors: list[dict[str, Any]] = []
    weighted_square_sum = 0.0
    weight_sum = 0.0

    for row in observations:
        target_time = finite_float(row.get("time", row.get("day", times[-1])))
        if target_time is None:
            continue
        for metric in targets:
            observed = finite_float(row.get(metric))
            if observed is None:
                continue
            series = metric_series(result, metric)
            predicted = interpolate_series(times, series or [], target_time)
            if predicted is None:
                continue
            weight = finite_float(row.get(f"{metric}Weight")) or weights.get(metric) or CALIBRATION_TARGETS.get(metric, {}).get("defaultWeight", 1.0)
            residual = predicted - observed
            weighted_square_sum += weight * residual * residual
            weight_sum += weight
            errors.append(
                {
                    "time": target_time,
                    "metric": metric,
                    "predicted": predicted,
                    "observed": observed,
                    "residual": residual,
                    "weight": weight,
                }
            )

    if not errors:
        raise ValueError("没有可用于校准的观测值。")

    return {
        "objective": math.sqrt(weighted_square_sum / max(weight_sum, 1e-12)),
        "count": len(errors),
        "errors": errors,
    }


def reference_observations(case_id: str) -> list[dict[str, Any]]:
    case = get_reference_case(case_id)
    targets = case.get("targets", {})
    row: dict[str, Any] = {"time": 14}
    for metric, target in targets.items():
        row[metric] = target["value"]
    return [row]


def final_metric_value(result: dict[str, Any], metric: str) -> float | None:
    series = metric_series(result, metric)
    if not series:
        return None
    return series[-1]


def validate_calibration_inputs(tunable_params: list[str], targets: list[str]) -> None:
    unknown_targets = [target for target in targets if target not in CALIBRATION_TARGETS and target != "bod5"]
    if unknown_targets:
        raise ValueError(f"未知校准目标：{', '.join(unknown_targets)}。")
    unknown_tunables = [key for key in tunable_params if key not in PARAM_LIMITS]
    if unknown_tunables:
        raise ValueError(f"未知可调参数：{', '.join(unknown_tunables)}。")


def candidate_values(current: float, limits: tuple[float, float], fraction: float) -> list[float]:
    minimum, maximum = limits
    span = max(abs(current), maximum - minimum, 1e-9)
    delta = span * fraction
    values = [current, current - delta, current + delta]
    return sorted({max(minimum, min(maximum, value)) for value in values})


def calibration_optimize(
    params: dict[str, Any] | None = None,
    observations: list[dict[str, Any]] | None = None,
    tunable_params: list[str] | None = None,
    targets: list[str] | None = None,
    csv_text: str = "",
    csv_file_name: str = "",
    max_iterations: int = 2,
    step_fraction: float = 0.1,
    use_bsm1_mapping: bool = False,
    use_bsm1_layout: bool = False,
    progress_callback: Callable[[float, float], None] | None = None,
) -> dict[str, Any]:
    started = perf_counter()
    base_params = bsm1_mapped_params(params) if (use_bsm1_mapping or use_bsm1_layout) else sanitize_params(params)
    selected_tunables = tunable_params or RECOMMENDED_TUNABLE_PARAMS[:5]
    selected_targets = targets or ["effNh4", "effNo3", "effTn", "effTss"]
    validate_calibration_inputs(selected_tunables, selected_targets)
    rows = observations or []
    if not rows:
        rows = reference_observations("bsm1_alignment_placeholder") if (use_bsm1_mapping or use_bsm1_layout) else []
    if not rows:
        raise ValueError("校准需要 observations，或启用 useBsm1Mapping 使用 BSM1 参考目标。")

    errors, warnings = validate_params(base_params)
    if errors:
        raise ValueError("; ".join(errors))

    max_iterations = max(1, min(int(max_iterations), 8))
    step_fraction = max(0.001, min(float(step_fraction), 0.5))
    total_trials = 1 + max_iterations * len(selected_tunables) * 3
    completed_trials = 0

    def report() -> None:
        if progress_callback:
            progress_callback(completed_trials, total_trials)

    def evaluate(candidate: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        nonlocal completed_trials
        if use_bsm1_layout:
            ctx = SimulationContext(params=candidate, source_name=csv_file_name or "", mode="csv" if csv_text.strip() else "manual")
            result = run_bsm1_simulation(ctx)
            result["engineVersion"] = "bsm1"
        else:
            result = simulate_with_engine(candidate, csv_text=csv_text, csv_file_name=csv_file_name)
        objective = observation_objective(result, rows, selected_targets)
        completed_trials += 1
        report()
        return result, objective

    report()
    best_params = base_params.copy()
    best_result, best_objective = evaluate(best_params)
    history = [
        {
            "iteration": 0,
            "param": None,
            "value": None,
            "objective": best_objective["objective"],
        }
    ]

    for iteration in range(1, max_iterations + 1):
        improved = False
        for key in selected_tunables:
            current = float(best_params[key])
            best_for_key = (current, best_result, best_objective)
            for value in candidate_values(current, PARAM_LIMITS[key], step_fraction / iteration):
                candidate = {**best_params, key: value}
                result, objective = evaluate(candidate)
                history.append({"iteration": iteration, "param": key, "value": value, "objective": objective["objective"]})
                if objective["objective"] < best_for_key[2]["objective"]:
                    best_for_key = (value, result, objective)
            if best_for_key[0] != current:
                best_params[key] = best_for_key[0]
                best_result = best_for_key[1]
                best_objective = best_for_key[2]
                improved = True
        if not improved:
            break

    report()
    return {
        "status": "completed",
        "method": "coordinate_search",
        "mapping": "bsm1_5tank" if use_bsm1_layout else "bsm1_three_zone_aao" if use_bsm1_mapping else "custom",
        "initialObjective": history[0]["objective"],
        "bestObjective": best_objective["objective"],
        "improvementPercent": (history[0]["objective"] - best_objective["objective"]) / max(history[0]["objective"], 1e-12) * 100,
        "bestParams": best_params,
        "tunableParams": selected_tunables,
        "targets": selected_targets,
        "observationCount": len(rows),
        "objectiveDetail": best_objective,
        "history": history,
        "warnings": warnings + best_result.get("warnings", []),
        "durationMs": (perf_counter() - started) * 1000,
        "referenceComparison": compare_to_reference_case("bsm1_alignment_placeholder", best_result) if (use_bsm1_mapping or use_bsm1_layout) else None,
    }


def bsm1_calibration_report(
    params: dict[str, Any] | None = None,
    use_bsm1_layout: bool = True,
    max_iterations: int = 1,
    step_fraction: float = 0.1,
) -> dict[str, Any]:
    started = perf_counter()
    reference_case_id = "bsm1_alignment_placeholder"
    reference_case = get_reference_case(reference_case_id)
    targets = list(reference_case.get("targets", {}).keys())
    observations = reference_observations(reference_case_id)
    base_params = bsm1_mapped_params(params)
    errors, warnings = validate_params(base_params)
    if errors:
        raise ValueError("; ".join(errors))

    if use_bsm1_layout:
        ctx = SimulationContext(params=base_params, source_name="", mode="manual")
        baseline_result = run_bsm1_simulation(ctx)
        baseline_result["engineVersion"] = "bsm1"
    else:
        baseline_result = simulate_with_engine(base_params)
    baseline_objective = observation_objective(baseline_result, observations, targets)
    optimized = calibration_optimize(
        params=base_params,
        observations=observations,
        tunable_params=RECOMMENDED_TUNABLE_PARAMS[:5],
        targets=targets,
        max_iterations=max_iterations,
        step_fraction=step_fraction,
        use_bsm1_mapping=not use_bsm1_layout,
        use_bsm1_layout=use_bsm1_layout,
    )

    baseline_comparison = compare_to_reference_case(reference_case_id, baseline_result)
    optimized_comparison = optimized.get("referenceComparison") or {}
    optimized_rows = {row["metric"]: row for row in optimized_comparison.get("rows", [])}
    rows = []
    for baseline_row in baseline_comparison["rows"]:
        metric = baseline_row["metric"]
        target = baseline_row["target"]
        optimized_value = None
        optimized_row = optimized_rows.get(metric)
        if optimized_row:
            optimized_value = optimized_row.get("actualFinal")
        baseline_error = baseline_row.get("absoluteError")
        optimized_error = None if optimized_value is None else optimized_value - target
        rows.append(
            {
                "metric": metric,
                "target": target,
                "unit": baseline_row["unit"],
                "baseline": baseline_row.get("actualFinal"),
                "optimized": optimized_value,
                "baselineError": baseline_error,
                "optimizedError": optimized_error,
                "absoluteErrorImprovement": None
                if baseline_error is None or optimized_error is None
                else abs(baseline_error) - abs(optimized_error),
            }
        )

    return {
        "status": "completed",
        "caseId": reference_case_id,
        "caseName": reference_case["name"],
        "caseStatus": reference_case["status"],
        "layout": "bsm1_5tank" if use_bsm1_layout else "bsm1_three_zone_aao",
        "baselineObjective": baseline_objective["objective"],
        "optimizedObjective": optimized["bestObjective"],
        "improvementPercent": (baseline_objective["objective"] - optimized["bestObjective"]) / max(baseline_objective["objective"], 1e-12) * 100,
        "rows": rows,
        "bestParams": optimized["bestParams"],
        "tunableParams": optimized["tunableParams"],
        "history": optimized["history"],
        "warnings": warnings + optimized.get("warnings", []),
        "notes": baseline_comparison["notes"],
        "durationMs": (perf_counter() - started) * 1000,
    }


def run_calibration_stage(
    stage_id: str,
    params: dict[str, Any] | None = None,
    observations: list[dict[str, Any]] | None = None,
    csv_text: str = "",
    csv_file_name: str = "",
    max_iterations: int = 1,
    step_fraction: float = 0.1,
    use_bsm1_mapping: bool = False,
    use_bsm1_layout: bool = False,
) -> dict[str, Any]:
    stage = get_calibration_stage(stage_id)
    result = calibration_optimize(
        params=params,
        observations=observations,
        tunable_params=stage["tunableParams"],
        targets=stage["targets"],
        csv_text=csv_text,
        csv_file_name=csv_file_name,
        max_iterations=max_iterations,
        step_fraction=step_fraction,
        use_bsm1_mapping=use_bsm1_mapping,
        use_bsm1_layout=use_bsm1_layout,
    )
    return {
        "stage": stage,
        "result": result,
    }
