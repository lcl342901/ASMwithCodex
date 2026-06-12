from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
from time import perf_counter
from typing import Any, Callable
from uuid import uuid4

from .engines import EngineRunOptions, get_engine
from .engine_scenarios import EngineScenario, default_asm1_scenarios, long_horizon_asm1_scenarios
from .model_trust import get_reference_case
from .model import DEFAULT_PARAMS, sanitize_params


REQUIRED_RESULT_KEYS = {
    "time",
    "effCod",
    "effNh4",
    "effNo3",
    "effTn",
    "effTss",
    "anaerobicNo3",
    "anoxicNo3",
    "aerobicNo3",
    "aerobicDo",
    "aerobicMlss",
    "rasMlss",
    "boundaries",
    "units",
    "clarifier",
    "warnings",
    "validation",
}

CORE_EFFLUENT_METRICS = ["effCod", "effNh4", "effNo3", "effTn", "effTss"]
CORE_STATE_METRICS = ["anaerobicNo3", "anoxicNo3", "aerobicNo3", "aerobicDo", "aerobicMlss", "rasMlss"]
GENERALITY_AXES = ["baseline", "load", "temperature", "hydraulics", "oxygen"]
REPORT_SCHEMA_VERSION = "2026-06-10.engine-evaluation.v1"


@dataclass(frozen=True)
class EngineAdapter:
    """Minimal contract future ASM engines can implement for the test suite."""

    engine_id: str
    model_family: str
    component_count: int
    run: Callable[[dict[str, Any]], dict[str, Any]]
    supported_model_ids: tuple[str, ...] = ("ASM1",)


def asm1_adapter() -> EngineAdapter:
    engine = get_engine("v1")
    metadata = engine.metadata
    return EngineAdapter(
        engine_id=metadata.id,
        model_family=metadata.model_family,
        component_count=metadata.component_count,
        supported_model_ids=(metadata.model_id,),
        run=lambda params: engine.run(EngineRunOptions(params=params)),
    )

def find_non_finite(value: Any, path: str = "result") -> str | None:
    if isinstance(value, dict):
        for key, child in value.items():
            found = find_non_finite(child, f"{path}.{key}")
            if found:
                return found
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found = find_non_finite(child, f"{path}[{index}]")
            if found:
                return found
    elif isinstance(value, (int, float)) and not math.isfinite(value):
        return path
    return None


def _last(result: dict[str, Any], metric: str) -> float:
    values = result.get(metric, [])
    if not values:
        raise ValueError(f"result missing {metric}")
    return float(values[-1])


def _relative_error(left: float, right: float) -> float:
    return abs(left - right) / max(abs(left), 1e-9)


def _series_lengths(result: dict[str, Any]) -> dict[str, int]:
    keys = ["time", *CORE_EFFLUENT_METRICS, *CORE_STATE_METRICS]
    return {key: len(result.get(key, [])) for key in keys}


def _params_digest(params: dict[str, Any]) -> str:
    payload = json.dumps(params, sort_keys=True, separators=(",", ":"))
    return sha256(payload.encode("utf-8")).hexdigest()[:12]


def _time_order_issues(result: dict[str, Any]) -> list[dict[str, Any]]:
    times = result.get("time", [])
    if not isinstance(times, list) or not times:
        return [{"code": "missing_time", "message": "result.time is missing or empty"}]
    issues = []
    for index in range(1, len(times)):
        if not isinstance(times[index], (int, float)) or not isinstance(times[index - 1], (int, float)):
            issues.append({"code": "non_numeric_time", "index": index})
            break
        if times[index] < times[index - 1]:
            issues.append({"code": "time_not_monotonic", "index": index, "previous": times[index - 1], "current": times[index]})
            break
    return issues


def _negative_metric_issues(result: dict[str, Any]) -> list[dict[str, Any]]:
    issues = []
    for metric in [*CORE_EFFLUENT_METRICS, *CORE_STATE_METRICS]:
        values = result.get(metric, [])
        if not isinstance(values, list):
            continue
        for index, value in enumerate(values):
            if isinstance(value, (int, float)) and math.isfinite(value) and value < -1e-9:
                issues.append({"code": "negative_metric", "metric": metric, "index": index, "value": value})
                break
    return issues


def _scenario_result(adapter: EngineAdapter, scenario: EngineScenario, base_params: dict[str, Any]) -> dict[str, Any]:
    params = sanitize_params({**base_params, **scenario.params})
    started = perf_counter()
    result = adapter.run(params)
    duration_ms = (perf_counter() - started) * 1000
    missing_keys = sorted(REQUIRED_RESULT_KEYS.difference(result.keys()))
    non_finite_path = find_non_finite(result)
    lengths = _series_lengths(result)
    expected_length = lengths.get("time", 0)
    length_mismatches = {key: value for key, value in lengths.items() if value != expected_length}
    time_issues = _time_order_issues(result)
    negative_metric_issues = _negative_metric_issues(result)
    range_issues = []
    for metric, (minimum, maximum) in scenario.expected_ranges.items():
        value = _last(result, metric)
        if value < minimum or value > maximum:
            range_issues.append({"metric": metric, "value": value, "expectedMin": minimum, "expectedMax": maximum})

    final_time = _last(result, "time")
    requested_horizon = float(params["simulationDays"])
    horizon_error = abs(final_time - requested_horizon)
    ok = (
        not missing_keys
        and non_finite_path is None
        and expected_length > 1
        and not length_mismatches
        and not range_issues
        and not time_issues
        and not negative_metric_issues
        and horizon_error <= 1e-4
    )
    return {
        "scenarioId": scenario.id,
        "name": scenario.name,
        "title": scenario.title or scenario.id,
        "axis": scenario.axis,
        "tags": list(scenario.tags),
        "status": "pass" if ok else "fail",
        "durationMs": duration_ms,
        "pointCount": expected_length,
        "finalTime": final_time,
        "requestedHorizonDays": requested_horizon,
        "paramsDigest": _params_digest(params),
        "summary": {metric: _last(result, metric) for metric in CORE_EFFLUENT_METRICS},
        "warningCount": result.get("validation", {}).get("warningCount", 0),
        "issues": {
            "missingKeys": missing_keys,
            "nonFinitePath": non_finite_path,
            "lengthMismatches": length_mismatches,
            "timeIssues": time_issues,
            "negativeMetricIssues": negative_metric_issues,
            "rangeIssues": range_issues,
            "horizonErrorDays": horizon_error,
        },
    }


def _repeatability_check(adapter: EngineAdapter, params: dict[str, Any]) -> dict[str, Any]:
    first = adapter.run(params)
    second = adapter.run(params)
    errors = [
        {"metric": metric, "relError": _relative_error(_last(first, metric), _last(second, metric))}
        for metric in CORE_EFFLUENT_METRICS
    ]
    max_rel_error = max((row["relError"] for row in errors), default=0.0)
    return {
        "checkId": "repeatability_same_input",
        "name": "repeatability_same_input",
        "status": "pass" if max_rel_error <= 1e-12 else "fail",
        "maxRelError": max_rel_error,
        "criteria": {"maxRelError": 1e-12},
        "errors": errors,
    }


def _step_consistency_check(adapter: EngineAdapter, params: dict[str, Any]) -> dict[str, Any]:
    coarse = adapter.run({**params, "timeStepHours": 0.5})
    fine = adapter.run({**params, "timeStepHours": 0.04167})
    errors = [
        {"metric": metric, "relError": _relative_error(_last(coarse, metric), _last(fine, metric))}
        for metric in CORE_EFFLUENT_METRICS
    ]
    max_rel_error = max((row["relError"] for row in errors), default=0.0)
    return {
        "checkId": "rk4_internal_step_consistency",
        "name": "rk4_internal_step_consistency",
        "status": "pass" if max_rel_error <= 0.01 else "needs_review",
        "maxRelError": max_rel_error,
        "criteria": {"maxRelError": 0.01},
        "errors": errors,
    }


def _solver_consistency_check(adapter: EngineAdapter, params: dict[str, Any]) -> dict[str, Any]:
    rk4 = adapter.run({**params, "solverMethod": "RK4"})
    lsoda = adapter.run({**params, "solverMethod": "LSODA", "maxSolverStepHours": 0.05})
    errors = [
        {"metric": metric, "relError": _relative_error(_last(rk4, metric), _last(lsoda, metric))}
        for metric in CORE_EFFLUENT_METRICS
    ]
    max_rel_error = max((row["relError"] for row in errors), default=0.0)
    return {
        "checkId": "rk4_vs_lsoda_short_horizon",
        "name": "rk4_vs_lsoda_short_horizon",
        "status": "pass" if max_rel_error <= 0.05 else "needs_review",
        "maxRelError": max_rel_error,
        "criteria": {"maxRelError": 0.05},
        "errors": errors,
    }


def _long_horizon_check(adapter: EngineAdapter, base_params: dict[str, Any]) -> dict[str, Any]:
    runs = [_scenario_result(adapter, scenario, base_params) for scenario in long_horizon_asm1_scenarios()]
    failed = [run for run in runs if run["status"] != "pass"]
    return {
        "checkId": "long_horizon_stability",
        "name": "long_horizon_stability",
        "status": "pass" if not failed else "needs_review",
        "criteria": {"requiredScenarioStatus": "pass"},
        "runs": runs,
        "failedScenarioCount": len(failed),
    }


def _bsm1_reference_gate(scenario_runs: list[dict[str, Any]]) -> dict[str, Any]:
    case = get_reference_case("bsm1_alignment_placeholder")
    baseline = next((run for run in scenario_runs if run["scenarioId"] == "baseline_design_load"), scenario_runs[0] if scenario_runs else None)
    rows = []
    if baseline:
        targets = case.get("targets", {})
        metric_map = {
            "effCod": "effCod",
            "effNh4": "effNh4",
            "effNo3": "effNo3",
            "effTn": "effTn",
            "effTss": "effTss",
        }
        for target_metric, summary_metric in metric_map.items():
            actual = float(baseline["summary"].get(summary_metric, 0))
            target = float(targets[target_metric]["value"])
            rows.append(
                {
                    "metric": target_metric,
                    "actual": actual,
                    "target": target,
                    "absError": actual - target,
                    "relError": abs(actual - target) / max(abs(target), 1e-9),
                    "unit": targets[target_metric]["unit"],
                }
            )
    return {
        "gateId": "bsm1_alignment_placeholder_scale_gate",
        "caseId": case["id"],
        "caseName": case["name"],
        "status": "needs_review",
        "comparisonStatus": "reference_only",
        "criteria": {
            "mode": "scale_only_until_mapping_ready",
            "requiredBeforePassFail": case.get("requiredBeforeUse", []),
        },
        "rows": rows,
        "notes": [
            "This is the first formal reference gate, but it is intentionally not pass/fail yet.",
            "BSM1 targets are dynamic load-weighted averages and require layout, influent fractionation, and averaging-window mapping before engineering-grade gating.",
        ],
    }


def _report_summary(
    overall_status: str,
    scenario_runs: list[dict[str, Any]],
    stability_checks: list[dict[str, Any]],
    reference_gates: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "scenarioCount": len(scenario_runs),
        "passingScenarioCount": sum(1 for run in scenario_runs if run["status"] == "pass"),
        "stabilityCheckCount": len(stability_checks),
        "passingStabilityCheckCount": sum(1 for check in stability_checks if check["status"] == "pass"),
        "referenceGateCount": len(reference_gates),
        "status": overall_status,
    }


def evaluate_engine(
    adapter: EngineAdapter,
    base_params: dict[str, Any] | None = None,
    scenarios: list[EngineScenario] | None = None,
    include_long_horizon: bool = False,
) -> dict[str, Any]:
    clean_base = sanitize_params({**DEFAULT_PARAMS, **(base_params or {})})
    scenario_list = scenarios or default_asm1_scenarios()
    scenario_runs = [_scenario_result(adapter, scenario, clean_base) for scenario in scenario_list]
    stability_params = sanitize_params(
        {
            **clean_base,
            "solverMethod": "RK4",
            "simulationDays": 0.05,
            "timeStepHours": 0.5,
            "outputIntervalHours": 0.5,
            "maxSolverStepHours": 0.05,
        }
    )
    stability_checks = [
        _repeatability_check(adapter, stability_params),
        _step_consistency_check(adapter, stability_params),
        _solver_consistency_check(adapter, stability_params),
    ]
    if include_long_horizon:
        stability_checks.append(_long_horizon_check(adapter, clean_base))
    covered_axes = sorted({run["axis"] for run in scenario_runs})
    missing_axes = sorted(set(GENERALITY_AXES).difference(covered_axes))
    reliability_status = "pass" if all(run["status"] == "pass" for run in scenario_runs) else "fail"
    stability_status = "pass" if all(check["status"] == "pass" for check in stability_checks) else "needs_review"
    generality_status = "pass" if not missing_axes else "needs_review"
    overall_status = "pass" if {reliability_status, stability_status, generality_status} == {"pass"} else "needs_review"
    reference_gates = [_bsm1_reference_gate(scenario_runs)]
    test_layers = [
        {
            "layerId": "model_kernel",
            "name": "模型内核测试",
            "target": "ASM1 reaction kernel",
            "status": "not_implemented",
            "scope": "反应速率、状态变量、单位、质量守恒、数值稳定性",
            "boundary": "不包含池容、工艺流程、沉淀池或回流",
            "nextStep": "Extract ASM1 reaction-rate kernel and add state-vector/unit/mass-balance tests.",
        },
        {
            "layerId": "process_engine",
            "name": "工艺引擎测试",
            "target": "AAO + ASM1 + clarifier + recycle",
            "status": overall_status,
            "scope": "合同完整性、数值稳定性、工况鲁棒性、输出序列一致性",
            "boundary": "包含进水、池容/分区、水力停留、DO、内回流、污泥回流和沉淀池假设",
            "nextStep": "Add explicit process-boundary fixtures for volume, HRT, SRT, recycle ratios, and DO profiles.",
        },
        {
            "layerId": "engineering_reference",
            "name": "工程参考验证",
            "target": "BSM1, measured data, historical project data",
            "status": "needs_review",
            "scope": "与参考案例或实测数据对比，评估工程合理性",
            "boundary": "当前 BSM1 gate is reference-only; not an engineering certification.",
            "nextStep": "Formalize BSM1 mapping, averaging windows, tolerances, and plant-data calibration sets.",
        },
    ]
    warnings = [
        "Current ASM1 evaluation is a validation framework baseline, not an engineering certification.",
        "Model-kernel tests are not implemented yet; current pass/fail mainly covers the process-engine layer.",
        "BSM1 reference gate is scale-only until mapping and averaging windows are formalized.",
    ]
    failures = [
        {"scope": "scenario", "id": run["scenarioId"], "status": run["status"]}
        for run in scenario_runs
        if run["status"] != "pass"
    ] + [
        {"scope": "stability", "id": check["checkId"], "status": check["status"]}
        for check in stability_checks
        if check["status"] == "fail"
    ]

    return {
        "type": "engine_evaluation",
        "schemaVersion": REPORT_SCHEMA_VERSION,
        "runId": uuid4().hex,
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "engine": {
            "id": adapter.engine_id,
            "modelFamily": adapter.model_family,
            "supportedModelIds": list(adapter.supported_model_ids),
            "componentCount": adapter.component_count,
        },
        "status": overall_status,
        "summary": _report_summary(overall_status, scenario_runs, stability_checks, reference_gates),
        "criteria": {
            "reliability": "all scenarios pass result-contract checks",
            "stability": "all stability checks pass their max relative-error thresholds",
            "generality": f"required axes: {', '.join(GENERALITY_AXES)}",
            "reference": "BSM1 gate remains reference-only until mapping is ready",
        },
        "testLayers": test_layers,
        "warnings": warnings,
        "failures": failures,
        "reliability": {
            "status": reliability_status,
            "scenarioCount": len(scenario_runs),
            "criteria": [
                "all required frontend/API result keys exist",
                "all numeric outputs are finite",
                "core time series have matching lengths",
                "each scenario produces more than one output point",
            ],
            "runs": scenario_runs,
        },
        "stability": {
            "status": stability_status,
            "includeLongHorizon": include_long_horizon,
            "checks": stability_checks,
        },
        "generality": {
            "status": generality_status,
            "coveredAxes": covered_axes,
            "missingAxes": missing_axes,
            "futureModelHook": {
                "contract": "Add an EngineAdapter for ASM2d_NDHA or another model and reuse evaluate_engine with model-specific scenarios.",
                "requiredFields": ["engine_id", "model_family", "component_count", "supported_model_ids", "run(params)"],
            },
        },
        "referenceGates": reference_gates,
    }


def evaluate_asm1_engine(base_params: dict[str, Any] | None = None, include_long_horizon: bool = False) -> dict[str, Any]:
    return evaluate_engine(asm1_adapter(), base_params, include_long_horizon=include_long_horizon)


if __name__ == "__main__":
    print(json.dumps(evaluate_asm1_engine(), ensure_ascii=False, indent=2))
