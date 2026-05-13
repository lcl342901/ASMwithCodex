from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import math
import re
from typing import Any, Callable


DEFAULT_PARAMS: dict[str, float] = {
    "influentQ": 10000,
    "influentCod": 420,
    "influentNh4": 32,
    "influentNo3": 0.5,
    "influentTss": 220,
    "solubleCodFraction": 38,
    "inertSolubleFraction": 25,
    "inertParticulateFraction": 25,
    "influentXbh": 25,
    "influentXba": 1,
    "influentOrganicNFactor": 0.2,
    "influentAlkalinity": 7,
    "anaerobicVolume": 1200,
    "anoxicVolume": 1800,
    "aerobicVolume": 3500,
    "clarifierArea": 1500,
    "rasRatio": 0.75,
    "internalRecycleRatio": 2.0,
    "wasQ": 350,
    "aerobicDo": 2.0,
    "simulationDays": 20,
    "timeStepHours": 0.5,
    "outputIntervalHours": 6,
    "muH": 6,
    "muA": 0.8,
    "bH": 0.62,
    "bA": 0.15,
    "kH": 3,
    "kA": 0.08,
    "kS": 20,
    "kX": 0.03,
    "kOH": 0.2,
    "kOA": 0.4,
    "kNO": 0.5,
    "kNH": 1,
    "yH": 0.67,
    "yA": 0.24,
    "etaG": 0.8,
    "etaH": 0.4,
    "fp": 0.08,
    "temp": 15,
    "clarifierHeight": 4,
    "clarifierLayers": 10,
    "clarifierFeedLayer": 5,
    "captureEfficiency": 99.5,
    "takacsRH": 0.00019,
    "takacsRP": 0.00286,
    "takacsV0": 474,
    "takacsV0Max": 250,
    "maxLayerTss": 30000,
}

PARAM_LIMITS: dict[str, tuple[float, float]] = {
    "influentQ": (1, 200000),
    "influentCod": (0, 3000),
    "influentNh4": (0, 300),
    "influentNo3": (0, 200),
    "influentTss": (0, 3000),
    "solubleCodFraction": (1, 99),
    "inertSolubleFraction": (0, 95),
    "inertParticulateFraction": (0, 95),
    "influentXbh": (0, 2000),
    "influentXba": (0, 500),
    "influentOrganicNFactor": (0, 2),
    "influentAlkalinity": (0, 60),
    "anaerobicVolume": (1, 200000),
    "anoxicVolume": (1, 200000),
    "aerobicVolume": (1, 300000),
    "clarifierArea": (1, 100000),
    "rasRatio": (0, 10),
    "internalRecycleRatio": (0, 20),
    "wasQ": (0, 20000),
    "aerobicDo": (0, 10),
    "simulationDays": (0.01, 3650),
    "timeStepHours": (0.001, 24),
    "outputIntervalHours": (0.001, 168),
    "muH": (0.001, 50),
    "muA": (0.001, 20),
    "bH": (0, 10),
    "bA": (0, 10),
    "kH": (0, 100),
    "kA": (0, 5),
    "kS": (0.001, 1000),
    "kX": (0.000001, 10),
    "kOH": (0.000001, 20),
    "kOA": (0.000001, 20),
    "kNO": (0.000001, 20),
    "kNH": (0.000001, 50),
    "yH": (0.001, 2),
    "yA": (0.001, 2),
    "etaG": (0, 1),
    "etaH": (0, 1),
    "fp": (0, 1),
    "temp": (0, 45),
    "clarifierHeight": (0.1, 20),
    "clarifierLayers": (4, 20),
    "clarifierFeedLayer": (1, 20),
    "captureEfficiency": (50, 99.99),
    "takacsRH": (0.000001, 0.1),
    "takacsRP": (0.000001, 0.1),
    "takacsV0": (0.001, 5000),
    "takacsV0Max": (0.001, 5000),
    "maxLayerTss": (100, 200000),
}

MAX_SOLVER_STEP_DAYS = 0.0005
EPSILON_DAYS = 1e-12

C = {
    "S_I": 0,
    "S_S": 1,
    "S_O": 2,
    "S_NO": 3,
    "S_NH": 4,
    "S_ND": 5,
    "S_ALK": 6,
    "X_I": 7,
    "X_S": 8,
    "X_BH": 9,
    "X_BA": 10,
    "X_P": 11,
    "X_ND": 12,
}

SOLUBLE = [C["S_I"], C["S_S"], C["S_O"], C["S_NO"], C["S_NH"], C["S_ND"], C["S_ALK"]]
PARTICULATE = [C["X_I"], C["X_S"], C["X_BH"], C["X_BA"], C["X_P"], C["X_ND"]]
METRIC_IDS = [
    "COD",
    "BOD5",
    "DO",
    "NH4",
    "NO3",
    "TN",
    "TKN",
    "TSS",
    "S_I",
    "S_S",
    "S_O",
    "S_NO",
    "S_NH",
    "S_ND",
    "S_ALK",
    "X_I",
    "X_S",
    "X_BH",
    "X_BA",
    "X_P",
    "X_ND",
]

ASM1_DEFAULTS: dict[str, float] = {
    "Y_A": 0.24,
    "Y_H": 0.67,
    "f_P": 0.08,
    "i_N_S_I": 0,
    "i_X_B": 0.086,
    "i_X_P": 0.06,
    "K_NH": 1,
    "K_NH_H": 0.05,
    "K_NO": 0.5,
    "K_OA": 0.4,
    "K_OH": 0.2,
    "K_S": 20,
    "K_X": 0.03,
    "b_A": 0.15,
    "b_H": 0.62,
    "k_a": 0.08,
    "k_h": 3,
    "mu_A": 0.8,
    "mu_H": 6,
    "n_g": 0.8,
    "n_h": 0.4,
    "F_TSS_COD": 0.75,
    "temp": 15,
}


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def safe(value: float, floor: float = 1e-9) -> float:
    return max(value, floor)


def zeros() -> list[float]:
    return [0.0] * 13


def as_number(value: Any, fallback: float | None = None) -> float | None:
    if isinstance(value, bool):
        return fallback
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return fallback
    return parsed if math.isfinite(parsed) else fallback


@dataclass
class SimulationContext:
    params: dict[str, float] = field(default_factory=lambda: DEFAULT_PARAMS.copy())
    source_name: str = ""
    mode: str = "manual"
    progress_callback: Callable[[float, float], None] | None = None
    asm1: dict[str, float] = field(default_factory=lambda: ASM1_DEFAULTS.copy())

    def __post_init__(self) -> None:
        self.sync_asm1_params()

    def sync_asm1_params(self) -> None:
        self.asm1["Y_A"] = self.params["yA"]
        self.asm1["Y_H"] = self.params["yH"]
        self.asm1["f_P"] = self.params["fp"]
        self.asm1["K_NH"] = self.params["kNH"]
        self.asm1["K_NO"] = self.params["kNO"]
        self.asm1["K_OA"] = self.params["kOA"]
        self.asm1["K_OH"] = self.params["kOH"]
        self.asm1["K_S"] = self.params["kS"]
        self.asm1["K_X"] = self.params["kX"]
        self.asm1["b_A"] = self.params["bA"]
        self.asm1["b_H"] = self.params["bH"]
        self.asm1["k_a"] = self.params["kA"]
        self.asm1["k_h"] = self.params["kH"]
        self.asm1["mu_A"] = self.params["muA"]
        self.asm1["mu_H"] = self.params["muH"]
        self.asm1["n_g"] = self.params["etaG"]
        self.asm1["n_h"] = self.params["etaH"]
        self.asm1["temp"] = self.params["temp"]

    def add_scaled(self, base: list[float], delta: list[float], scale: float) -> list[float]:
        return [max(0.0, value + delta[index] * scale) for index, value in enumerate(base)]

    def mix_vectors(self, streams: list[dict[str, Any]]) -> list[float]:
        total_q = sum(item["q"] for item in streams)
        out = zeros()
        if total_q <= 0:
            return out
        for item in streams:
            for index, value in enumerate(item["c"]):
                out[index] += (item["q"] * value) / total_q
        return out

    def influent_vector(self) -> list[float]:
        soluble_fraction = clamp(self.params["solubleCodFraction"] / 100, 0.05, 0.95)
        x_cod = min(
            self.params["influentCod"] * (1 - soluble_fraction),
            self.params["influentTss"] / self.asm1["F_TSS_COD"],
        )
        s_cod = max(0.0, self.params["influentCod"] - x_cod)
        si_fraction = clamp(self.params["inertSolubleFraction"] / 100, 0, 0.9)
        xi_fraction = clamp(self.params["inertParticulateFraction"] / 100, 0, 0.9)
        organic_n = self.params["influentNh4"] * clamp(self.params["influentOrganicNFactor"], 0, 1)
        c = zeros()
        c[C["S_I"]] = s_cod * si_fraction
        c[C["S_S"]] = s_cod * (1 - si_fraction)
        c[C["S_O"]] = 0.2
        c[C["S_NO"]] = self.params["influentNo3"]
        c[C["S_NH"]] = self.params["influentNh4"]
        c[C["S_ND"]] = organic_n * 0.4
        c[C["S_ALK"]] = self.params["influentAlkalinity"]
        c[C["X_I"]] = x_cod * xi_fraction
        c[C["X_S"]] = x_cod * (1 - xi_fraction)
        c[C["X_BH"]] = self.params["influentXbh"]
        c[C["X_BA"]] = self.params["influentXba"]
        c[C["X_P"]] = 0
        c[C["X_ND"]] = organic_n * 0.6
        return c

    def oxygen_saturation(self, temp: float) -> float:
        return 290326 * math.exp(-66.7354 + 87.4755 / ((temp + 273.15) / 100) + 24.4526 * math.log((temp + 273.15) / 100))

    def temperature_corrected(self) -> dict[str, float]:
        temp = self.asm1["temp"]
        return {
            "K_X": self.asm1["K_X"] * 1.116 ** (temp - 20),
            "b_A": self.asm1["b_A"] * 1.116 ** (temp - 20),
            "b_H": self.asm1["b_H"] * 1.12 ** (temp - 20),
            "k_a": self.asm1["k_a"] * 1.072 ** (temp - 20),
            "k_h": self.asm1["k_h"] * 1.116 ** (temp - 20),
            "mu_A": self.asm1["mu_A"] * 1.103 ** (temp - 20),
            "mu_H": self.asm1["mu_H"] * 1.072 ** (temp - 20),
        }

    def asm1_conversion(self, c: list[float], kla: float) -> list[float]:
        p = self.temperature_corrected()
        so_sat = self.oxygen_saturation(self.asm1["temp"])
        conv = zeros()
        sto = [zeros() for _ in range(9)]

        sto[0][C["S_ALK"]] = -(self.asm1["i_X_B"] / 14) - 1 / (7 * self.asm1["Y_A"])
        sto[0][C["S_NH"]] = -self.asm1["i_X_B"] - 1 / self.asm1["Y_A"]
        sto[0][C["S_NO"]] = 1 / self.asm1["Y_A"]
        sto[0][C["S_O"]] = -(4.57 - self.asm1["Y_A"]) / self.asm1["Y_A"]
        sto[0][C["X_BA"]] = 1

        sto[1][C["S_ALK"]] = -self.asm1["i_X_B"] / 14
        sto[1][C["S_NH"]] = -self.asm1["i_X_B"]
        sto[1][C["S_O"]] = -(1 - self.asm1["Y_H"]) / self.asm1["Y_H"]
        sto[1][C["S_S"]] = -1 / self.asm1["Y_H"]
        sto[1][C["X_BH"]] = 1

        sto[2][C["S_O"]] = 1

        sto[3][C["S_ALK"]] = 1 / 14
        sto[3][C["S_ND"]] = -1
        sto[3][C["S_NH"]] = 1

        sto[4][C["S_ALK"]] = (1 - self.asm1["Y_H"]) / (14 * 2.86 * self.asm1["Y_H"]) - self.asm1["i_X_B"] / 14
        sto[4][C["S_NH"]] = -self.asm1["i_X_B"]
        sto[4][C["S_NO"]] = -(1 - self.asm1["Y_H"]) / (2.86 * self.asm1["Y_H"])
        sto[4][C["S_S"]] = -1 / self.asm1["Y_H"]
        sto[4][C["X_BH"]] = 1

        sto[5][C["X_BA"]] = -1
        sto[5][C["X_ND"]] = self.asm1["i_X_B"] - self.asm1["f_P"] * self.asm1["i_X_P"]
        sto[5][C["X_P"]] = self.asm1["f_P"]
        sto[5][C["X_S"]] = 1 - self.asm1["f_P"]

        sto[6][C["X_BH"]] = -1
        sto[6][C["X_ND"]] = self.asm1["i_X_B"] - self.asm1["f_P"] * self.asm1["i_X_P"]
        sto[6][C["X_P"]] = self.asm1["f_P"]
        sto[6][C["X_S"]] = 1 - self.asm1["f_P"]

        sto[7][C["S_S"]] = 1
        sto[7][C["X_S"]] = -1
        sto[8][C["S_ND"]] = 1
        sto[8][C["X_ND"]] = -1

        x_ratio = c[C["X_S"]] / safe(c[C["X_BH"]])
        hydrolysis_switch = (
            c[C["S_O"]] / (self.asm1["K_OH"] + c[C["S_O"]])
            + self.asm1["n_h"]
            * (self.asm1["K_OH"] / (self.asm1["K_OH"] + c[C["S_O"]]))
            * (c[C["S_NO"]] / (self.asm1["K_NO"] + c[C["S_NO"]]))
        )
        hydrolysis = p["k_h"] * (x_ratio / (p["K_X"] + x_ratio)) * hydrolysis_switch * c[C["X_BH"]]

        rates = [
            p["mu_A"]
            * (c[C["S_NH"]] / (self.asm1["K_NH"] + c[C["S_NH"]]))
            * (c[C["S_O"]] / (self.asm1["K_OA"] + c[C["S_O"]]))
            * c[C["X_BA"]],
            p["mu_H"]
            * (c[C["S_S"]] / (self.asm1["K_S"] + c[C["S_S"]]))
            * (c[C["S_O"]] / (self.asm1["K_OH"] + c[C["S_O"]]))
            * (c[C["S_NH"]] / (self.asm1["K_NH_H"] + c[C["S_NH"]]))
            * c[C["X_BH"]],
            kla * (so_sat - c[C["S_O"]]),
            p["k_a"] * c[C["S_ND"]] * c[C["X_BH"]],
            p["mu_H"]
            * (c[C["S_S"]] / (self.asm1["K_S"] + c[C["S_S"]]))
            * (self.asm1["K_OH"] / (self.asm1["K_OH"] + c[C["S_O"]]))
            * (c[C["S_NO"]] / (self.asm1["K_NO"] + c[C["S_NO"]]))
            * (c[C["S_NH"]] / (self.asm1["K_NH_H"] + c[C["S_NH"]]))
            * self.asm1["n_g"]
            * c[C["X_BH"]],
            p["b_A"] * c[C["X_BA"]],
            p["b_H"] * c[C["X_BH"]],
            hydrolysis,
            hydrolysis * (c[C["X_ND"]] / safe(c[C["X_S"]])),
        ]

        for process_index, row in enumerate(sto):
            for component_index, coefficient in enumerate(row):
                conv[component_index] += coefficient * rates[process_index]
        return conv

    def reactor_derivative(self, state: list[float], input_vector: list[float], q_in: float, volume: float, kla: float) -> list[float]:
        reaction = self.asm1_conversion(state, kla)
        return [(q_in / volume) * (input_vector[index] - value) + reaction[index] for index, value in enumerate(state)]

    def rk4_reactor(self, state: list[float], input_vector: list[float], q_in: float, volume: float, kla: float, dt: float) -> list[float]:
        k1 = self.reactor_derivative(state, input_vector, q_in, volume, kla)
        k2 = self.reactor_derivative(self.add_scaled(state, k1, dt / 2), input_vector, q_in, volume, kla)
        k3 = self.reactor_derivative(self.add_scaled(state, k2, dt / 2), input_vector, q_in, volume, kla)
        k4 = self.reactor_derivative(self.add_scaled(state, k3, dt), input_vector, q_in, volume, kla)
        return [max(0.0, value + (dt / 6) * (k1[index] + 2 * k2[index] + 2 * k3[index] + k4[index])) for index, value in enumerate(state)]

    def cod(self, c: list[float]) -> float:
        return c[C["S_I"]] + c[C["S_S"]] + c[C["X_I"]] + c[C["X_S"]] + c[C["X_BH"]] + c[C["X_BA"]] + c[C["X_P"]]

    def bod5(self, c: list[float]) -> float:
        return 0.65 * (c[C["S_S"]] + c[C["X_S"]] + (1 - self.asm1["f_P"]) * (c[C["X_BH"]] + c[C["X_BA"]]))

    def tss(self, c: list[float]) -> float:
        return (c[C["X_BH"]] + c[C["X_BA"]] + c[C["X_I"]] + c[C["X_S"]] + c[C["X_P"]]) * self.asm1["F_TSS_COD"]

    def tkn(self, c: list[float]) -> float:
        return (
            c[C["S_NH"]]
            + c[C["S_ND"]]
            + c[C["X_ND"]]
            + self.asm1["i_X_B"] * (c[C["X_BH"]] + c[C["X_BA"]])
            + self.asm1["i_X_P"] * (c[C["X_P"]] + c[C["X_I"]])
            + self.asm1["i_N_S_I"] * c[C["S_I"]]
        )

    def tn(self, c: list[float]) -> float:
        return c[C["S_NO"]] + self.tkn(c)

    def metrics_from_vector(self, c: list[float]) -> dict[str, float]:
        return {
            "COD": self.cod(c),
            "BOD5": self.bod5(c),
            "DO": c[C["S_O"]],
            "NH4": c[C["S_NH"]],
            "NO3": c[C["S_NO"]],
            "TN": self.tn(c),
            "TKN": self.tkn(c),
            "TSS": self.tss(c),
            "S_I": c[C["S_I"]],
            "S_S": c[C["S_S"]],
            "S_O": c[C["S_O"]],
            "S_NO": c[C["S_NO"]],
            "S_NH": c[C["S_NH"]],
            "S_ND": c[C["S_ND"]],
            "S_ALK": c[C["S_ALK"]],
            "X_I": c[C["X_I"]],
            "X_S": c[C["X_S"]],
            "X_BH": c[C["X_BH"]],
            "X_BA": c[C["X_BA"]],
            "X_P": c[C["X_P"]],
            "X_ND": c[C["X_ND"]],
        }

    def create_unit_series(self) -> dict[str, dict[str, list[float]]]:
        return {unit_id: {metric_id: [] for metric_id in METRIC_IDS} for unit_id in ["influent", "anaerobic", "anoxic", "aerobic", "clarifier", "effluent", "ras", "was"]}

    def create_result_series(self) -> dict[str, Any]:
        return {
            "time": [],
            "effCod": [],
            "effNh4": [],
            "effNo3": [],
            "effTn": [],
            "effTss": [],
            "anaerobicNo3": [],
            "anoxicNo3": [],
            "aerobicNo3": [],
            "aerobicDo": [],
            "aerobicMlss": [],
            "rasMlss": [],
            "mode": self.mode,
            "sourceName": self.source_name,
            "boundaries": {"q": [], "cod": [], "nh4": [], "no3": [], "tss": [], "do": [], "rasQ": [], "irQ": [], "wasQ": []},
            "units": self.create_unit_series(),
            "clarifier": {"topTss": [], "middleTss": [], "bottomTss": [], "effluentTss": [], "underflowTss": []},
        }

    def boundary_snapshot(self, influent: list[float]) -> dict[str, float]:
        q = self.params["influentQ"]
        return {
            "q": q,
            "cod": self.cod(influent),
            "nh4": influent[C["S_NH"]],
            "no3": influent[C["S_NO"]],
            "tss": self.tss(influent),
            "do": self.params["aerobicDo"],
            "rasQ": q * self.params["rasRatio"],
            "irQ": q * self.params["internalRecycleRatio"],
            "wasQ": min(self.params["wasQ"], q * 0.8),
        }

    def push_unit_metrics(self, unit_series: dict[str, dict[str, list[float]]], unit_id: str, metric_values: dict[str, float]) -> None:
        for metric_id in METRIC_IDS:
            unit_series[unit_id][metric_id].append(metric_values.get(metric_id, 0))

    def push_snapshot(
        self,
        series: dict[str, Any],
        time: float,
        influent: list[float],
        anaerobic: list[float],
        anoxic: list[float],
        aerobic: list[float],
        split: dict[str, Any],
        ras: list[float],
        clarifier_layers: list[float],
    ) -> None:
        series["time"].append(round(time, 4))
        for key, value in self.boundary_snapshot(influent).items():
            series["boundaries"][key].append(value)
        series["effCod"].append(self.cod(split["eff"]))
        series["effNh4"].append(split["eff"][C["S_NH"]])
        series["effNo3"].append(split["eff"][C["S_NO"]])
        series["effTn"].append(self.tn(split["eff"]))
        series["effTss"].append(self.tss(split["eff"]))
        series["anaerobicNo3"].append(anaerobic[C["S_NO"]])
        series["anoxicNo3"].append(anoxic[C["S_NO"]])
        series["aerobicNo3"].append(aerobic[C["S_NO"]])
        series["aerobicDo"].append(aerobic[C["S_O"]])
        series["aerobicMlss"].append(self.tss(aerobic))
        series["rasMlss"].append(self.tss(ras))

        self.push_unit_metrics(series["units"], "influent", self.metrics_from_vector(influent))
        self.push_unit_metrics(series["units"], "anaerobic", self.metrics_from_vector(anaerobic))
        self.push_unit_metrics(series["units"], "anoxic", self.metrics_from_vector(anoxic))
        self.push_unit_metrics(series["units"], "aerobic", self.metrics_from_vector(aerobic))
        self.push_unit_metrics(series["units"], "clarifier", self.metrics_from_vector(split["eff"]))
        self.push_unit_metrics(series["units"], "effluent", self.metrics_from_vector(split["eff"]))
        self.push_unit_metrics(series["units"], "ras", self.metrics_from_vector(ras))
        self.push_unit_metrics(series["units"], "was", self.metrics_from_vector(split["under"]))
        series["clarifier"]["topTss"].append(clarifier_layers[0])
        series["clarifier"]["middleTss"].append(clarifier_layers[math.floor(len(clarifier_layers) / 2)])
        series["clarifier"]["bottomTss"].append(clarifier_layers[-1])
        series["clarifier"]["effluentTss"].append(self.tss(split["eff"]))
        series["clarifier"]["underflowTss"].append(self.tss(split["under"]))

    def settling_velocity(self, x: float, x_min: float) -> float:
        effective_x = max(0.0, x - x_min)
        return clamp(
            self.params["takacsV0"] * (math.exp(-self.params["takacsRH"] * effective_x) - math.exp(-self.params["takacsRP"] * effective_x)),
            0,
            self.params["takacsV0Max"],
        )

    def takacs_clarifier_step(
        self,
        layers: list[float],
        inlet: list[float],
        q_clarifier: float,
        ras_q: float,
        was_q: float,
        dt: float,
        capture: float,
    ) -> dict[str, Any]:
        n = len(layers)
        area = max(self.params["clarifierArea"], 1)
        height = max(self.params["clarifierHeight"], 0.1)
        h_layer = height / n
        v_layer = area * h_layer
        feed_layer = int(clamp(round(self.params["clarifierFeedLayer"]) - 1, 0, n - 1))
        q_under = max(ras_q + was_q, 1e-6)
        q_eff = max(q_clarifier - q_under, 1e-6)
        x_in = max(self.tss(inlet), 1e-6)
        x_min = (1 - capture) * x_in
        d = [0.0] * n

        d[feed_layer] += (q_clarifier * x_in) / v_layer

        for i in range(feed_layer + 1):
            flux = q_eff * layers[i]
            d[i] -= flux / v_layer
            if i > 0:
                d[i - 1] += flux / v_layer

        for i in range(feed_layer, n):
            flux = q_under * layers[i]
            d[i] -= flux / v_layer
            if i < n - 1:
                d[i + 1] += flux / v_layer

        for i in range(n - 1):
            upper_flux = self.settling_velocity(layers[i], x_min) * layers[i]
            lower_flux = self.settling_velocity(layers[i + 1], x_min) * layers[i + 1]
            gravity_flux = min(upper_flux, lower_flux)
            d[i] -= gravity_flux / h_layer
            d[i + 1] += gravity_flux / h_layer

        next_layers = [clamp(x + dt * d[index], 0, self.params["maxLayerTss"]) for index, x in enumerate(layers)]
        eff_tss = max(x_min, next_layers[0])
        under_tss = max(eff_tss, next_layers[-1])
        eff_ratio = clamp(eff_tss / x_in, 0, 1.2)
        under_ratio = clamp(under_tss / x_in, 0, max(1, self.params["maxLayerTss"] / x_in))
        eff = inlet.copy()
        under = inlet.copy()
        for index in SOLUBLE:
            eff[index] = inlet[index]
            under[index] = inlet[index]
        for index in PARTICULATE:
            eff[index] = inlet[index] * eff_ratio
            under[index] = inlet[index] * under_ratio
        return {"layers": next_layers, "eff": eff, "under": under, "qEff": q_eff, "qUnder": q_under}

    def initial_reactor_state(self, kind: str) -> list[float]:
        c = zeros()
        c[C["S_I"]] = 30
        c[C["S_S"]] = 75 if kind == "anaerobic" else 45 if kind == "anoxic" else 20
        c[C["S_O"]] = self.params["aerobicDo"] if kind == "aerobic" else 0.05
        c[C["S_NO"]] = 0.2 if kind == "anaerobic" else 4 if kind == "anoxic" else 10
        c[C["S_NH"]] = 8 if kind == "aerobic" else 24
        c[C["S_ND"]] = 2
        c[C["S_ALK"]] = 7
        c[C["X_I"]] = 120
        c[C["X_S"]] = 160
        c[C["X_BH"]] = 2600
        c[C["X_BA"]] = 180
        c[C["X_P"]] = 80
        c[C["X_ND"]] = 15
        return c

    def create_simulation_state(self) -> dict[str, Any]:
        layer_count = int(clamp(round(self.params["clarifierLayers"]), 4, 20))
        self.params["clarifierFeedLayer"] = clamp(round(self.params["clarifierFeedLayer"]), 1, layer_count)
        aerobic = self.initial_reactor_state("aerobic")
        return {
            "anaerobic": self.initial_reactor_state("anaerobic"),
            "anoxic": self.initial_reactor_state("anoxic"),
            "aerobic": aerobic,
            "ras": aerobic.copy(),
            "clarifierLayers": [self.tss(aerobic)] * layer_count,
        }

    def step_simulation_state(self, state: dict[str, Any], influent: list[float], dt: float) -> dict[str, Any]:
        q = self.params["influentQ"]
        ras_q = q * self.params["rasRatio"]
        ir_q = q * self.params["internalRecycleRatio"]
        was_q = min(self.params["wasQ"], q * 0.8)
        capture = clamp(self.params["captureEfficiency"] / 100, 0.8, 0.9995)

        anaerobic_in = self.mix_vectors([{"q": q, "c": influent}, {"q": ras_q, "c": state["ras"]}])
        state["anaerobic"] = self.rk4_reactor(state["anaerobic"], anaerobic_in, q + ras_q, self.params["anaerobicVolume"], 0, dt)

        anoxic_in = self.mix_vectors([{"q": q + ras_q, "c": state["anaerobic"]}, {"q": ir_q, "c": state["aerobic"]}])
        state["anoxic"] = self.rk4_reactor(state["anoxic"], anoxic_in, q + ras_q + ir_q, self.params["anoxicVolume"], 0, dt)

        state["aerobic"] = self.rk4_reactor(state["aerobic"], state["anoxic"], q + ras_q + ir_q, self.params["aerobicVolume"], 60 * self.params["aerobicDo"], dt)

        split = self.takacs_clarifier_step(state["clarifierLayers"], state["aerobic"], q + ras_q, ras_q, was_q, dt, capture)
        state["clarifierLayers"] = split["layers"]
        state["ras"] = split["under"]
        return split

    def requested_step_days(self) -> float:
        return max(0.001 / 24, self.params["timeStepHours"] / 24)

    def solver_step_days(self) -> float:
        return min(self.requested_step_days(), MAX_SOLVER_STEP_DAYS)

    def output_interval_days(self) -> float:
        return max(self.solver_step_days(), self.params["outputIntervalHours"] / 24)

    def report_progress(self, current_time: float, total_time: float) -> None:
        if self.progress_callback:
            self.progress_callback(current_time, total_time)

    def run_asm1_simulation(self) -> dict[str, Any]:
        self.sync_asm1_params()
        solver_dt = self.solver_step_days()
        end_time = self.params["simulationDays"]
        output_interval = self.output_interval_days()
        influent = self.influent_vector()
        state = self.create_simulation_state()
        series = self.create_result_series()
        split = self.takacs_clarifier_step(state["clarifierLayers"], state["aerobic"], self.params["influentQ"] * (1 + self.params["rasRatio"]), self.params["influentQ"] * self.params["rasRatio"], min(self.params["wasQ"], self.params["influentQ"] * 0.8), 0, clamp(self.params["captureEfficiency"] / 100, 0.8, 0.9995))
        self.push_snapshot(series, 0, influent, state["anaerobic"], state["anoxic"], state["aerobic"], split, state["ras"], state["clarifierLayers"])
        self.report_progress(0, end_time)

        current_time = 0.0
        next_output = output_interval
        while current_time < end_time - EPSILON_DAYS:
            target_time = min(end_time, next_output)
            dt = min(solver_dt, target_time - current_time)
            split = self.step_simulation_state(state, influent, dt)
            current_time += dt
            if current_time >= next_output - EPSILON_DAYS or current_time >= end_time - EPSILON_DAYS:
                self.push_snapshot(series, current_time, influent, state["anaerobic"], state["anoxic"], state["aerobic"], split, state["ras"], state["clarifierLayers"])
                self.report_progress(current_time, end_time)
                while next_output <= current_time + EPSILON_DAYS:
                    next_output += output_interval
        return series

    def run_historical_simulation(self, records: list[dict[str, Any]]) -> dict[str, Any]:
        if not records:
            self.mode = "manual"
            self.source_name = ""
            return self.run_asm1_simulation()
        saved_params = self.params.copy()
        self.mode = "csv"
        state = self.create_simulation_state()
        series = self.create_result_series()
        solver_dt = self.solver_step_days()
        end_time = self.params["simulationDays"]
        output_interval = self.output_interval_days()
        cursor = {"index": 0}

        try:
            current_time = 0.0
            self.params.update(csv_values_at(records, current_time, cursor))
            self.sync_asm1_params()
            influent = self.influent_vector()
            split = self.takacs_clarifier_step(state["clarifierLayers"], state["aerobic"], self.params["influentQ"] * (1 + self.params["rasRatio"]), self.params["influentQ"] * self.params["rasRatio"], min(self.params["wasQ"], self.params["influentQ"] * 0.8), 0, clamp(self.params["captureEfficiency"] / 100, 0.8, 0.9995))
            self.push_snapshot(series, current_time, influent, state["anaerobic"], state["anoxic"], state["aerobic"], split, state["ras"], state["clarifierLayers"])
            self.report_progress(current_time, end_time)

            next_output = output_interval
            while current_time < end_time - EPSILON_DAYS:
                self.params.update(csv_values_at(records, current_time, cursor))
                self.sync_asm1_params()
                influent = self.influent_vector()
                target_time = min(end_time, next_output)
                dt = min(solver_dt, target_time - current_time)
                split = self.step_simulation_state(state, influent, dt)
                current_time += dt
                if current_time >= next_output - EPSILON_DAYS or current_time >= end_time - EPSILON_DAYS:
                    self.push_snapshot(series, current_time, influent, state["anaerobic"], state["anoxic"], state["aerobic"], split, state["ras"], state["clarifierLayers"])
                    self.report_progress(current_time, end_time)
                    while next_output <= current_time + EPSILON_DAYS:
                        next_output += output_interval
        finally:
            self.params = saved_params
            self.sync_asm1_params()
        return series

    def step_realtime_state(self, state: dict[str, Any], boundary_values: dict[str, float], step_hours: float) -> dict[str, Any]:
        self.params.update(boundary_values)
        self.sync_asm1_params()
        total_dt = max(step_hours, 0.001) / 24
        max_dt = MAX_SOLVER_STEP_DAYS
        influent = self.influent_vector()
        elapsed = 0.0
        split = None
        while elapsed < total_dt:
            dt = min(max_dt, total_dt - elapsed)
            split = self.step_simulation_state(state, influent, dt)
            elapsed += dt
        series = self.create_result_series()
        self.push_snapshot(series, 0, influent, state["anaerobic"], state["anoxic"], state["aerobic"], split, state["ras"], state["clarifierLayers"])
        return {
            "state": state,
            "snapshot": {
                "effCod": series["effCod"][-1],
                "effNh4": series["effNh4"][-1],
                "effNo3": series["effNo3"][-1],
                "effTn": series["effTn"][-1],
                "effTss": series["effTss"][-1],
                "aerobicDo": series["aerobicDo"][-1],
                "aerobicMlss": series["aerobicMlss"][-1],
                "rasMlss": series["rasMlss"][-1],
                "boundaries": {key: values[-1] for key, values in series["boundaries"].items()},
                "units": {unit_id: {metric_id: values[-1] for metric_id, values in metrics.items()} for unit_id, metrics in series["units"].items()},
                "clarifier": {key: values[-1] for key, values in series["clarifier"].items()},
            },
        }


def parse_csv_rows(text: str) -> list[list[str]]:
    rows: list[list[str]] = []
    row: list[str] = []
    cell = ""
    quoted = False
    i = 0
    while i < len(text):
        char = text[i]
        next_char = text[i + 1] if i + 1 < len(text) else ""
        if char == '"' and quoted and next_char == '"':
            cell += '"'
            i += 1
        elif char == '"':
            quoted = not quoted
        elif char == "," and not quoted:
            row.append(cell.strip())
            cell = ""
        elif char in "\n\r" and not quoted:
            if char == "\r" and next_char == "\n":
                i += 1
            row.append(cell.strip())
            if any(value != "" for value in row):
                rows.append(row)
            row = []
            cell = ""
        else:
            cell += char
        i += 1
    row.append(cell.strip())
    if any(value != "" for value in row):
        rows.append(row)
    return rows


def normalize_header(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def parse_maybe_number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        parsed = float(str(value).replace(",", ""))
    except ValueError:
        return None
    return parsed if math.isfinite(parsed) else None


def get_csv_number(row: dict[str, str], aliases: list[str], fallback: float | None = None) -> float | None:
    for alias in aliases:
        key = normalize_header(alias)
        if key in row:
            parsed = parse_maybe_number(row[key])
            if parsed is not None:
                return parsed
    return fallback


def parse_date_ms(value: str | None) -> float | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized).timestamp() * 1000
    except ValueError:
        return None


def parse_csv_time(value: str | None, index: int, first_timestamp: float, ctx: SimulationContext) -> float:
    numeric = parse_maybe_number(value)
    if numeric is not None:
        return numeric
    timestamp = parse_date_ms(value)
    if timestamp is not None:
        return (timestamp - first_timestamp) / 86400000
    return index * ctx.requested_step_days()


def normalize_csv_records(text: str, ctx: SimulationContext) -> list[dict[str, Any]]:
    rows = parse_csv_rows(text)
    if len(rows) < 2:
        raise ValueError("CSV needs at least a header and one data row.")
    headers = [normalize_header(value) for value in rows[0]]
    raw_rows: list[dict[str, str]] = []
    for values in rows[1:]:
        raw_rows.append({header: values[index] if index < len(values) else "" for index, header in enumerate(headers)})

    time_aliases = ["time", "timestamp", "datetime", "date", "day", "days", "t"]
    first_time_value = next((raw_rows[0].get(normalize_header(alias)) for alias in time_aliases if raw_rows[0].get(normalize_header(alias))), None)
    parsed_first_timestamp = None if parse_maybe_number(first_time_value) is not None else parse_date_ms(first_time_value)
    first_timestamp = parsed_first_timestamp if parsed_first_timestamp is not None else 0

    records: list[dict[str, Any]] = []
    mapping = [
        ("influentQ", ["q", "qin", "q in", "flow", "flowrate", "influentq"]),
        ("influentCod", ["cod", "influentcod", "tcod"]),
        ("influentNh4", ["nh4", "snh", "ammonium", "ammonia", "nh4n"]),
        ("influentNo3", ["no3", "sno", "nitrate", "no3n"]),
        ("influentTss", ["tss", "influenttss", "sst"]),
        ("aerobicDo", ["do", "doset", "aerobicdo", "so", "setdo"]),
        ("rasRatio", ["rasratio", "rasr", "qrasqin"]),
        ("internalRecycleRatio", ["irratio", "internalrecycleratio", "qirqin"]),
        ("wasQ", ["wasq", "qwas", "wasflow"]),
        ("solubleCodFraction", ["solublecodfraction", "scodfraction", "scodpercent"]),
        ("temp", ["temp", "temperature"]),
    ]

    for index, row in enumerate(raw_rows):
        time_value = next((row.get(normalize_header(alias)) for alias in time_aliases if row.get(normalize_header(alias)) not in (None, "")), None)
        values: dict[str, float] = {}
        for target, aliases in mapping:
            value = get_csv_number(row, aliases)
            if value is not None:
                values[target] = value
        ras_q = get_csv_number(row, ["rasq", "qras", "rasflow"])
        if ras_q is not None and values.get("influentQ"):
            values["rasRatio"] = ras_q / values["influentQ"]
        ir_q = get_csv_number(row, ["irq", "qir", "internalrecycleq", "internalrecycleflow"])
        if ir_q is not None and values.get("influentQ"):
            values["internalRecycleRatio"] = ir_q / values["influentQ"]
        records.append({"time": parse_csv_time(time_value, index, first_timestamp, ctx), "values": values})

    return sorted([record for record in records if math.isfinite(record["time"])], key=lambda record: record["time"])


def interpolate_values(previous: dict[str, Any] | None, next_record: dict[str, Any] | None, time: float) -> dict[str, float]:
    if previous is None:
        return dict(next_record["values"]) if next_record else {}
    if next_record is None:
        return dict(previous["values"])
    span = next_record["time"] - previous["time"]
    if span <= 0:
        return dict(previous["values"])
    ratio = clamp((time - previous["time"]) / span, 0, 1)
    keys = set(previous["values"].keys()) | set(next_record["values"].keys())
    values: dict[str, float] = {}
    for key in keys:
        a = previous["values"].get(key)
        b = next_record["values"].get(key)
        if a is not None and b is not None:
            values[key] = a + (b - a) * ratio
        elif a is not None:
            values[key] = a
        elif b is not None:
            values[key] = b
    return values


def csv_values_at(records: list[dict[str, Any]], time: float, cursor: dict[str, int]) -> dict[str, float]:
    while cursor["index"] < len(records) - 2 and records[cursor["index"] + 1]["time"] <= time:
        cursor["index"] += 1
    previous = records[cursor["index"]]
    next_record = records[cursor["index"] + 1] if cursor["index"] + 1 < len(records) else None
    if time <= records[0]["time"]:
        return dict(records[0]["values"])
    if next_record is None:
        return dict(previous["values"])
    return interpolate_values(previous, next_record, time)


def sanitize_params(params: dict[str, Any] | None) -> dict[str, float]:
    merged = DEFAULT_PARAMS.copy()
    if not params:
        return merged
    for key, value in params.items():
        if key not in merged:
            continue
        parsed = as_number(value)
        if parsed is not None:
            merged[key] = parsed
    return merged


def validate_params(params: dict[str, float]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    for key, value in params.items():
        if not math.isfinite(value):
            errors.append(f"{key} 必须是有限数值。")
            continue
        limits = PARAM_LIMITS.get(key)
        if not limits:
            continue
        minimum, maximum = limits
        if value < minimum or value > maximum:
            errors.append(f"{key}={value:g} 超出允许范围 [{minimum:g}, {maximum:g}]。")

    if params["clarifierFeedLayer"] > params["clarifierLayers"]:
        errors.append("clarifierFeedLayer 不能大于 clarifierLayers。")

    total_volume = params["anaerobicVolume"] + params["anoxicVolume"] + params["aerobicVolume"]
    hrt_hours = total_volume / max(params["influentQ"], 1e-9) * 24
    if hrt_hours < 2:
        warnings.append(f"总反应池 HRT 偏低 ({hrt_hours:.2f} h)，水力停留时间可能不合理。")
    if hrt_hours > 72:
        warnings.append(f"总反应池 HRT 偏高 ({hrt_hours:.1f} h)，请检查池容和进水流量。")

    surface_overflow = params["influentQ"] * (1 + params["rasRatio"]) / max(params["clarifierArea"], 1e-9)
    if surface_overflow > 50:
        warnings.append(f"二沉池表面负荷偏高 ({surface_overflow:.1f} m/d)，固液分离结果可能不可靠。")

    requested_step = params["timeStepHours"] / 24
    if requested_step > MAX_SOLVER_STEP_DAYS:
        warnings.append(f"设定计算步长大于内部求解器上限，后端会使用 {MAX_SOLVER_STEP_DAYS:g} d 作为内部步长。")
    if params["outputIntervalHours"] < params["timeStepHours"]:
        warnings.append("结果输出间隔短于设定计算步长，输出会跟随内部求解器步长。")
    if params["wasQ"] > params["influentQ"] * 0.8:
        warnings.append("WAS 排泥量超过进水量的 80%，计算中会被内部截断。")
    if params["takacsV0Max"] < params["takacsV0"]:
        warnings.append("takacsV0Max 小于 takacsV0，沉降速度会被 takacsV0Max 限制。")

    return errors, warnings


def validate_csv_records(records: list[dict[str, Any]], params: dict[str, float]) -> list[str]:
    warnings: list[str] = []
    if not records:
        warnings.append("已提供 CSV 文本，但没有找到有效记录。")
        return warnings
    if len(records) == 1:
        warnings.append("CSV 只有一行有效记录，该边界条件会保持到仿真结束。")
    if records[0]["time"] > 0:
        warnings.append(f"CSV 第一条时间为 {records[0]['time']:.2f} d，在此之前会使用第一条边界条件。")
    if records[-1]["time"] < params["simulationDays"]:
        warnings.append(f"CSV 数据到 {records[-1]['time']:.2f} d 结束，最后一条边界条件会保持到 {params['simulationDays']:.2f} d。")

    empty_value_rows = sum(1 for record in records if not record["values"])
    if empty_value_rows:
        warnings.append(f"CSV 有 {empty_value_rows} 行没有识别到可用边界字段。")

    duplicate_times = sum(1 for index in range(1, len(records)) if records[index]["time"] == records[index - 1]["time"])
    if duplicate_times:
        warnings.append(f"CSV 有 {duplicate_times} 行重复时间戳，插值时可能优先使用较早记录。")

    return warnings


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


def attach_validation(result: dict[str, Any], warnings: list[str]) -> dict[str, Any]:
    found = find_non_finite(result)
    if found:
        raise ValueError(f"仿真结果在 {found} 出现非有限数值。")
    result["warnings"] = warnings
    result["validation"] = {
        "ok": True,
        "warningCount": len(warnings),
        "warnings": warnings,
    }
    return result


def simulate(
    params: dict[str, Any] | None = None,
    csv_text: str = "",
    csv_file_name: str = "",
    progress_callback: Callable[[float, float], None] | None = None,
) -> dict[str, Any]:
    clean_params = sanitize_params(params)
    errors, warnings = validate_params(clean_params)
    if errors:
        raise ValueError("; ".join(errors))

    ctx = SimulationContext(
        params=clean_params,
        source_name=csv_file_name or "",
        mode="csv" if csv_text.strip() else "manual",
        progress_callback=progress_callback,
    )
    if csv_text.strip():
        records = normalize_csv_records(csv_text, ctx)
        warnings.extend(validate_csv_records(records, clean_params))
        return attach_validation(ctx.run_historical_simulation(records), warnings)
    return attach_validation(ctx.run_asm1_simulation(), warnings)
