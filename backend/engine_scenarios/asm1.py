from __future__ import annotations

from .base import EngineScenario


def _common() -> dict[str, float | str]:
    return {
        "solverMethod": "RK4",
        "simulationDays": 0.05,
        "timeStepHours": 0.5,
        "outputIntervalHours": 0.5,
    }


def default_asm1_scenarios() -> list[EngineScenario]:
    common = _common()
    return [
        EngineScenario("baseline_design_load", "baseline", common, "Baseline design load", ("smoke", "baseline")),
        EngineScenario(
            "high_cod_and_nh4_load",
            "load",
            {**common, "influentCod": 720, "influentNh4": 55, "influentTss": 360},
            "High COD and NH4 load",
            ("smoke", "stress", "load"),
        ),
        EngineScenario(
            "low_temperature_winter",
            "temperature",
            {**common, "temp": 8, "aerobicDo": 2.5},
            "Low temperature winter",
            ("smoke", "stress", "temperature"),
        ),
        EngineScenario(
            "high_hydraulic_load",
            "hydraulics",
            {**common, "influentQ": 18000, "rasRatio": 1.2, "internalRecycleRatio": 3.0},
            "High hydraulic load",
            ("smoke", "stress", "hydraulics"),
        ),
        EngineScenario(
            "low_do_operation",
            "oxygen",
            {**common, "aerobicDo": 0.8, "initialAerobicDo": 0.8},
            "Low DO operation",
            ("smoke", "stress", "oxygen"),
        ),
    ]


def long_horizon_asm1_scenarios() -> list[EngineScenario]:
    common = _common()
    return [
        EngineScenario(
            "long_horizon_1d",
            "long_horizon",
            {**common, "simulationDays": 1, "outputIntervalHours": 6},
            "Long horizon 1 day",
            ("long_horizon", "regression"),
        ),
        EngineScenario(
            "long_horizon_5d",
            "long_horizon",
            {**common, "simulationDays": 5, "outputIntervalHours": 12},
            "Long horizon 5 days",
            ("long_horizon", "regression"),
        ),
        EngineScenario(
            "long_horizon_20d",
            "long_horizon",
            {**common, "simulationDays": 20, "outputIntervalHours": 24},
            "Long horizon 20 days",
            ("long_horizon", "explicit"),
        ),
    ]
