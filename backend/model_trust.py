from __future__ import annotations

import math
from typing import Any

from .model import DEFAULT_PARAMS, METRIC_IDS, PARAM_LIMITS, SimulationContext, sanitize_params, validate_params


ASM1_COMPONENTS = [
    {"id": "S_I", "name": "Soluble inert organic matter", "unit": "gCOD/m3", "phase": "soluble"},
    {"id": "S_S", "name": "Readily biodegradable substrate", "unit": "gCOD/m3", "phase": "soluble"},
    {"id": "S_O", "name": "Dissolved oxygen", "unit": "gO2/m3", "phase": "soluble"},
    {"id": "S_NO", "name": "Nitrate and nitrite nitrogen", "unit": "gN/m3", "phase": "soluble"},
    {"id": "S_NH", "name": "Ammonium and ammonia nitrogen", "unit": "gN/m3", "phase": "soluble"},
    {"id": "S_ND", "name": "Soluble biodegradable organic nitrogen", "unit": "gN/m3", "phase": "soluble"},
    {"id": "S_ALK", "name": "Alkalinity", "unit": "mol/m3", "phase": "soluble"},
    {"id": "X_I", "name": "Particulate inert organic matter", "unit": "gCOD/m3", "phase": "particulate"},
    {"id": "X_S", "name": "Slowly biodegradable substrate", "unit": "gCOD/m3", "phase": "particulate"},
    {"id": "X_BH", "name": "Heterotrophic biomass", "unit": "gCOD/m3", "phase": "particulate"},
    {"id": "X_BA", "name": "Autotrophic biomass", "unit": "gCOD/m3", "phase": "particulate"},
    {"id": "X_P", "name": "Particulate products from decay", "unit": "gCOD/m3", "phase": "particulate"},
    {"id": "X_ND", "name": "Particulate biodegradable organic nitrogen", "unit": "gN/m3", "phase": "particulate"},
]


UNIT_SYSTEM = {
    "flow": "m3/d",
    "volume": "m3",
    "area": "m2",
    "time": "d for model horizon, h for UI step settings",
    "cod": "gCOD/m3",
    "nitrogen": "gN/m3",
    "oxygen": "gO2/m3",
    "tss": "g/m3",
    "alkalinity": "mol/m3",
    "temperature": "degC",
}


REFERENCE_CASES = [
    {
        "id": "default_teaching_aao",
        "name": "Default AAO teaching case",
        "status": "internal_baseline",
        "description": "Current project baseline used for regression checks and UI demonstrations.",
        "params": {
            "influentQ": DEFAULT_PARAMS["influentQ"],
            "influentCod": DEFAULT_PARAMS["influentCod"],
            "influentNh4": DEFAULT_PARAMS["influentNh4"],
            "influentNo3": DEFAULT_PARAMS["influentNo3"],
            "influentTss": DEFAULT_PARAMS["influentTss"],
            "simulationDays": 20,
            "timeStepHours": 0.5,
            "outputIntervalHours": 6,
            "solverMethod": "RK4",
        },
        "expectedChecks": [
            "all result values finite",
            "final time equals requested simulationDays",
            "effluent and unit series have equal lengths",
            "model warnings are reviewed before interpreting results",
        ],
    },
    {
        "id": "bsm1_alignment_placeholder",
        "name": "BSM1 closed-loop dynamic effluent reference",
        "status": "needs_mapping",
        "description": "Public BSM1 closed-loop dynamic effluent averages from the 2008 Lund University/IWA Task Group report. This is a reference target set, not a direct pass/fail case for the current 3-reactor AAO model.",
        "source": {
            "title": "Benchmark Simulation Model no. 1 (BSM1)",
            "publisher": "Lund University",
            "year": 2008,
            "url": "https://www.iea.lth.se/publications/Reports/LTH-IEA-7229.pdf",
        },
        "plant": {
            "averageDryWeatherFlowM3D": 18446,
            "averageBiodegradableCodGM3": 300,
            "biologicalReactorVolumeM3": 6000,
            "settlerVolumeM3": 6000,
            "settlerAreaM2": 1500,
            "settlerHeightM": 4,
            "wastageFlowM3D": 385,
            "layoutNote": "BSM1 uses two anoxic tanks followed by three aerobic tanks, plus a 10-layer settler.",
        },
        "targets": {
            "effCod": {"value": 48.2201, "unit": "gCOD/m3", "statistic": "dynamic_load_weighted_average"},
            "effNh4": {"value": 2.5392, "unit": "gN/m3", "statistic": "dynamic_load_weighted_average"},
            "effNo3": {"value": 12.4199, "unit": "gN/m3", "statistic": "dynamic_load_weighted_average"},
            "effTn": {"value": 16.9245, "unit": "gN/m3", "statistic": "dynamic_load_weighted_average"},
            "effTss": {"value": 13.0038, "unit": "g/m3", "statistic": "dynamic_load_weighted_average"},
            "bod5": {"value": 2.7568, "unit": "g/m3", "statistic": "dynamic_load_weighted_average"},
        },
        "limits": {
            "effCod": {"value": 100, "unit": "gCOD/m3"},
            "effNh4": {"value": 4, "unit": "gN/m3"},
            "effTn": {"value": 18, "unit": "gN/m3"},
            "effTss": {"value": 30, "unit": "g/m3"},
            "bod5": {"value": 10, "unit": "g/m3"},
        },
        "requiredBeforeUse": [
            "map BSM components to this platform's influent fractionation",
            "document clarifier and recycle assumptions",
            "decide whether to approximate BSM1's 5 tanks with current 3 zones or add a BSM1-specific layout",
            "store tolerance bands after the mapping decision",
        ],
    },
]


INITIAL_CONDITION_KEYS = [
    "initialSi",
    "initialAnaerobicSs",
    "initialAnoxicSs",
    "initialAerobicSs",
    "initialAnaerobicDo",
    "initialAnoxicDo",
    "initialAerobicDo",
    "initialAnaerobicNo3",
    "initialAnoxicNo3",
    "initialAerobicNo3",
    "initialAnaerobicNh4",
    "initialAnoxicNh4",
    "initialAerobicNh4",
    "initialSnd",
    "initialAlkalinity",
    "initialXi",
    "initialXs",
    "initialXbh",
    "initialXba",
    "initialXp",
    "initialXnd",
]


CALIBRATION_TARGETS = {
    "effCod": {"label": "Effluent COD", "unit": "gCOD/m3", "defaultWeight": 1.0},
    "effNh4": {"label": "Effluent NH4-N", "unit": "gN/m3", "defaultWeight": 2.0},
    "effNo3": {"label": "Effluent NO3-N", "unit": "gN/m3", "defaultWeight": 1.0},
    "effTn": {"label": "Effluent TN", "unit": "gN/m3", "defaultWeight": 1.0},
    "effTss": {"label": "Effluent TSS", "unit": "g/m3", "defaultWeight": 1.0},
}


RECOMMENDED_TUNABLE_PARAMS = [
    "muH",
    "muA",
    "bH",
    "bA",
    "kH",
    "kA",
    "kS",
    "kNH",
    "kNO",
    "yH",
    "yA",
    "etaG",
    "etaH",
    "takacsRH",
    "takacsRP",
    "takacsV0",
    "takacsV0Max",
]


def finite_series(values: Any) -> bool:
    if not isinstance(values, list) or not values:
        return False
    return all(isinstance(value, (int, float)) and math.isfinite(value) for value in values)


def latest_number(result: dict[str, Any], key: str) -> float | None:
    values = result.get(key)
    if not finite_series(values):
        return None
    return float(values[-1])


def model_metadata() -> dict[str, Any]:
    return {
        "model": "AAO ASM1-style teaching simulator",
        "status": "teaching_mvp_not_engineering_grade",
        "unitSystem": UNIT_SYSTEM,
        "asm1Components": ASM1_COMPONENTS,
        "availableMetrics": METRIC_IDS,
        "initialConditionKeys": INITIAL_CONDITION_KEYS,
        "calibrationTargets": CALIBRATION_TARGETS,
        "recommendedTunableParams": [
            {"key": key, "default": DEFAULT_PARAMS[key], "limits": PARAM_LIMITS[key]}
            for key in RECOMMENDED_TUNABLE_PARAMS
        ],
        "assumptions": [
            "ASM1-style reaction terms are implemented for learning and product iteration.",
            "Influent COD and nitrogen fractionation is parameterized and should be mapped explicitly for external reference cases.",
            "The current v1 clarifier is a simplified Takacs-style layered solids model.",
            "RK4 remains the recommended routine solver for the current Python implementation.",
            "Calibration and BSM validation are not complete yet.",
        ],
    }


def reference_cases() -> dict[str, Any]:
    return {"cases": REFERENCE_CASES}


def get_reference_case(case_id: str) -> dict[str, Any]:
    for case in REFERENCE_CASES:
        if case["id"] == case_id:
            return case
    raise ValueError(f"未知参考案例：{case_id}。")


def compare_to_reference_case(case_id: str, result: dict[str, Any]) -> dict[str, Any]:
    case = get_reference_case(case_id)
    targets = case.get("targets", {})
    rows = []
    for metric, target in targets.items():
        if metric == "bod5":
            series = result.get("units", {}).get("effluent", {}).get("BOD5")
        else:
            series = result.get(metric)
        actual = float(series[-1]) if finite_series(series) else None
        target_value = float(target["value"])
        absolute_error = None if actual is None else actual - target_value
        relative_error_percent = None if actual is None or target_value == 0 else absolute_error / target_value * 100
        rows.append(
            {
                "metric": metric,
                "actualFinal": actual,
                "target": target_value,
                "unit": target["unit"],
                "statistic": target["statistic"],
                "absoluteError": absolute_error,
                "relativeErrorPercent": relative_error_percent,
            }
        )

    return {
        "caseId": case_id,
        "caseName": case["name"],
        "caseStatus": case["status"],
        "comparisonStatus": "reference_only" if case["status"] != "ready" else "comparable",
        "rows": rows,
        "notes": [
            "BSM1 targets are dynamic load-weighted averages; this comparison currently uses final values from the supplied result.",
            "Use this report to inspect scale and direction only until layout, influent fractionation, and averaging window are mapped.",
        ],
    }


def initial_condition_snapshot(params: dict[str, Any] | None = None) -> dict[str, Any]:
    clean_params = sanitize_params(params)
    errors, warnings = validate_params(clean_params)
    if errors:
        raise ValueError("; ".join(errors))
    ctx = SimulationContext(params=clean_params)
    state = ctx.create_simulation_state()
    return {
        "warnings": warnings,
        "components": [component["id"] for component in ASM1_COMPONENTS],
        "units": {component["id"]: component["unit"] for component in ASM1_COMPONENTS},
        "reactors": {
            "anaerobic": state["anaerobic"],
            "anoxic": state["anoxic"],
            "aerobic": state["aerobic"],
            "ras": state["ras"],
        },
        "clarifierLayers": state["clarifierLayers"],
        "summary": {
            unit: ctx.metrics_from_vector(values)
            for unit, values in {
                "anaerobic": state["anaerobic"],
                "anoxic": state["anoxic"],
                "aerobic": state["aerobic"],
                "ras": state["ras"],
            }.items()
        },
    }


def assess_result_credibility(result: dict[str, Any], params: dict[str, Any] | None = None) -> dict[str, Any]:
    clean_params = sanitize_params(params)
    issues: list[dict[str, Any]] = []
    score = 100

    validation = result.get("validation", {})
    warnings = validation.get("warnings", result.get("warnings", []))
    if warnings:
        score -= min(30, 5 * len(warnings))
        issues.append({"severity": "warning", "code": "model_warnings", "message": f"Result contains {len(warnings)} model warning(s)."})

    time_values = result.get("time", [])
    if not finite_series(time_values):
        score -= 40
        issues.append({"severity": "error", "code": "invalid_time_series", "message": "Time series is missing or contains invalid values."})
    elif abs(float(time_values[-1]) - clean_params["simulationDays"]) > 1e-3 and result.get("mode") != "realtime":
        score -= 15
        issues.append({"severity": "warning", "code": "horizon_mismatch", "message": "Final result time does not match requested simulationDays."})

    for key in CALIBRATION_TARGETS:
        if latest_number(result, key) is None:
            score -= 20
            issues.append({"severity": "error", "code": "missing_metric", "metric": key, "message": f"{key} is missing or invalid."})

    final_tss = latest_number(result, "effTss")
    if final_tss is not None and final_tss > max(80, clean_params["influentTss"] * 0.8):
        score -= 15
        issues.append({"severity": "warning", "code": "high_effluent_tss", "metric": "effTss", "message": "Effluent TSS is high; clarifier parameters or solids capture should be reviewed."})

    final_nh4 = latest_number(result, "effNh4")
    if final_nh4 is not None and final_nh4 > clean_params["influentNh4"] * 1.2 + 1:
        score -= 10
        issues.append({"severity": "warning", "code": "nh4_above_influent", "metric": "effNh4", "message": "Effluent NH4-N is above influent baseline; check initial conditions and aeration/nitrification settings."})

    final_cod = latest_number(result, "effCod")
    if final_cod is not None and final_cod > clean_params["influentCod"] * 1.2 + 1:
        score -= 10
        issues.append({"severity": "warning", "code": "cod_above_influent", "metric": "effCod", "message": "Effluent COD is above influent baseline; check initial solids and clarifier behavior."})

    if result.get("engineVersion") == "v2":
        score -= 10
        issues.append({"severity": "info", "code": "experimental_engine", "message": "engine_v2 is still experimental and should be compared with v1 before use."})

    clipped_score = max(0, min(100, score))
    if any(issue["severity"] == "error" for issue in issues):
        status = "invalid"
    elif clipped_score < 70:
        status = "needs_review"
    elif issues:
        status = "caution"
    else:
        status = "ok"

    return {
        "status": status,
        "score": clipped_score,
        "issues": issues,
        "basis": "heuristic_result_screening",
        "note": "This is a screening aid, not a substitute for calibration against measured plant or public benchmark data.",
    }


def calibration_preview(
    params: dict[str, Any] | None = None,
    observations: list[dict[str, Any]] | None = None,
    tunable_params: list[str] | None = None,
    targets: list[str] | None = None,
) -> dict[str, Any]:
    clean_params = sanitize_params(params)
    errors, warnings = validate_params(clean_params)
    if errors:
        raise ValueError("; ".join(errors))

    selected_targets = targets or list(CALIBRATION_TARGETS.keys())
    unknown_targets = [target for target in selected_targets if target not in CALIBRATION_TARGETS]
    if unknown_targets:
        raise ValueError(f"未知校准目标：{', '.join(unknown_targets)}。")

    selected_tunables = tunable_params or RECOMMENDED_TUNABLE_PARAMS[:]
    unknown_tunables = [key for key in selected_tunables if key not in PARAM_LIMITS]
    if unknown_tunables:
        raise ValueError(f"未知可调参数：{', '.join(unknown_tunables)}。")

    rows = observations or []
    usable_rows = 0
    for row in rows:
        if any(target in row and isinstance(row[target], (int, float)) and math.isfinite(float(row[target])) for target in selected_targets):
            usable_rows += 1

    return {
        "status": "ready" if usable_rows else "needs_observations",
        "observationCount": len(rows),
        "usableObservationCount": usable_rows,
        "targets": [
            {"key": target, **CALIBRATION_TARGETS[target]}
            for target in selected_targets
        ],
        "tunableParams": [
            {"key": key, "current": clean_params[key], "limits": PARAM_LIMITS[key]}
            for key in selected_tunables
        ],
        "objective": "weighted_rmse",
        "warnings": warnings,
        "nextStep": "Provide measured effluent observations with time and target columns, then run an optimizer in a later phase.",
    }
