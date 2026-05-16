from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from scipy.integrate import solve_ivp

from .model import C, EPSILON_DAYS, MAX_SOLVER_STEP_DAYS, PARTICULATE, SOLUBLE, attach_validation, clamp, csv_values_at, SimulationContext


ASM1_COMPONENT_COUNT = 13
V2_SOLVER_METHODS = {"RK4", "LSODA", "BDF", "RADAU"}
SCIPY_METHODS = {"LSODA": "LSODA", "BDF": "BDF", "RADAU": "Radau"}


@dataclass(frozen=True)
class VectorStateLayout:
    """Global state-vector layout for the next-generation engine.

    The first version intentionally mirrors the current model states while
    keeping them in one flat vector. Clarifier dynamics remain bridged through
    the existing discrete Takacs step until the continuous clarifier RHS is
    implemented.
    """

    clarifier_layers: int
    anaerobic: slice
    anoxic: slice
    aerobic: slice
    ras: slice
    clarifier: slice
    size: int

    def unit_slices(self) -> dict[str, slice]:
        return {
            "anaerobic": self.anaerobic,
            "anoxic": self.anoxic,
            "aerobic": self.aerobic,
            "ras": self.ras,
            "clarifierLayers": self.clarifier,
        }


def create_layout(params: dict[str, Any]) -> VectorStateLayout:
    layer_count = int(clamp(round(params["clarifierLayers"]), 4, 20))
    offset = 0
    anaerobic = slice(offset, offset + ASM1_COMPONENT_COUNT)
    offset = anaerobic.stop
    anoxic = slice(offset, offset + ASM1_COMPONENT_COUNT)
    offset = anoxic.stop
    aerobic = slice(offset, offset + ASM1_COMPONENT_COUNT)
    offset = aerobic.stop
    ras = slice(offset, offset + ASM1_COMPONENT_COUNT)
    offset = ras.stop
    clarifier = slice(offset, offset + layer_count)
    offset = clarifier.stop
    return VectorStateLayout(
        clarifier_layers=layer_count,
        anaerobic=anaerobic,
        anoxic=anoxic,
        aerobic=aerobic,
        ras=ras,
        clarifier=clarifier,
        size=offset,
    )


def _slice_values(vector: list[float], target: slice) -> list[float]:
    return [max(0.0, float(value)) for value in vector[target]]


def pack_state(state: dict[str, Any], layout: VectorStateLayout) -> list[float]:
    vector = [0.0] * layout.size
    vector[layout.anaerobic] = state["anaerobic"][:ASM1_COMPONENT_COUNT]
    vector[layout.anoxic] = state["anoxic"][:ASM1_COMPONENT_COUNT]
    vector[layout.aerobic] = state["aerobic"][:ASM1_COMPONENT_COUNT]
    vector[layout.ras] = state["ras"][:ASM1_COMPONENT_COUNT]
    vector[layout.clarifier] = state["clarifierLayers"][: layout.clarifier_layers]
    return [max(0.0, float(value)) for value in vector]


def unpack_state(vector: list[float], layout: VectorStateLayout) -> dict[str, Any]:
    if len(vector) != layout.size:
        raise ValueError(f"state vector size {len(vector)} does not match layout size {layout.size}")
    return {
        "anaerobic": _slice_values(vector, layout.anaerobic),
        "anoxic": _slice_values(vector, layout.anoxic),
        "aerobic": _slice_values(vector, layout.aerobic),
        "ras": _slice_values(vector, layout.ras),
        "clarifierLayers": _slice_values(vector, layout.clarifier),
    }


def initial_vector_state(ctx: SimulationContext) -> tuple[VectorStateLayout, list[float]]:
    layout = create_layout(ctx.params)
    return layout, pack_state(ctx.create_simulation_state(), layout)


def add_scaled(vector: list[float], delta: list[float], scale: float) -> list[float]:
    return [max(0.0, value + delta[index] * scale) for index, value in enumerate(vector)]


def reactor_rhs(ctx: SimulationContext, vector: list[float], influent: list[float], layout: VectorStateLayout) -> list[float]:
    q = ctx.params["influentQ"]
    ras_q = q * ctx.params["rasRatio"]
    ir_q = q * ctx.params["internalRecycleRatio"]
    anaerobic = _slice_values(vector, layout.anaerobic)
    anoxic = _slice_values(vector, layout.anoxic)
    aerobic = _slice_values(vector, layout.aerobic)
    ras = _slice_values(vector, layout.ras)

    anaerobic_in = ctx.mix_vectors([{"q": q, "c": influent}, {"q": ras_q, "c": ras}])
    anoxic_in = ctx.mix_vectors([{"q": q + ras_q, "c": anaerobic}, {"q": ir_q, "c": aerobic}])

    derivative = [0.0] * layout.size
    derivative[layout.anaerobic] = ctx.reactor_derivative(anaerobic, anaerobic_in, q + ras_q, ctx.params["anaerobicVolume"], 0)
    derivative[layout.anoxic] = ctx.reactor_derivative(anoxic, anoxic_in, q + ras_q + ir_q, ctx.params["anoxicVolume"], 0)
    derivative[layout.aerobic] = ctx.reactor_derivative(aerobic, anoxic, q + ras_q + ir_q, ctx.params["aerobicVolume"], 60 * ctx.params["aerobicDo"])
    return derivative


def clarifier_layer_rhs(ctx: SimulationContext, layers: list[float], inlet: list[float]) -> list[float]:
    """Continuous Takacs-style TSS layer derivatives.

    This is the RHS equivalent of the current discrete clarifier update. It
    keeps the same hydraulic and settling terms, but returns dX/dt so a solver
    can integrate clarifier layers together with the reactor states.
    """

    n = len(layers)
    q = ctx.params["influentQ"]
    ras_q = q * ctx.params["rasRatio"]
    was_q = min(ctx.params["wasQ"], q * 0.8)
    q_clarifier = q + ras_q
    capture = clamp(ctx.params["captureEfficiency"] / 100, 0.8, 0.9995)
    area = max(ctx.params["clarifierArea"], 1)
    height = max(ctx.params["clarifierHeight"], 0.1)
    h_layer = height / n
    v_layer = area * h_layer
    feed_layer = int(clamp(round(ctx.params["clarifierFeedLayer"]) - 1, 0, n - 1))
    q_under = max(ras_q + was_q, 1e-6)
    q_eff = max(q_clarifier - q_under, 1e-6)
    x_in = max(ctx.tss(inlet), 1e-6)
    x_min = (1 - capture) * x_in
    d = [0.0] * n

    d[feed_layer] += (q_clarifier * x_in) / v_layer

    for index in range(feed_layer + 1):
        flux = q_eff * layers[index]
        d[index] -= flux / v_layer
        if index > 0:
            d[index - 1] += flux / v_layer

    for index in range(feed_layer, n):
        flux = q_under * layers[index]
        d[index] -= flux / v_layer
        if index < n - 1:
            d[index + 1] += flux / v_layer

    for index in range(n - 1):
        upper_flux = ctx.settling_velocity(layers[index], x_min) * layers[index]
        lower_flux = ctx.settling_velocity(layers[index + 1], x_min) * layers[index + 1]
        gravity_flux = min(upper_flux, lower_flux)
        d[index] -= gravity_flux / h_layer
        d[index + 1] += gravity_flux / h_layer

    return d


def split_from_layers(ctx: SimulationContext, layers: list[float], inlet: list[float]) -> dict[str, Any]:
    q = ctx.params["influentQ"]
    ras_q = q * ctx.params["rasRatio"]
    was_q = min(ctx.params["wasQ"], q * 0.8)
    capture = clamp(ctx.params["captureEfficiency"] / 100, 0.8, 0.9995)
    q_clarifier = q + ras_q
    q_under = max(ras_q + was_q, 1e-6)
    q_eff = max(q_clarifier - q_under, 1e-6)
    x_in = max(ctx.tss(inlet), 1e-6)
    x_min = (1 - capture) * x_in
    eff_tss = max(x_min, layers[0])
    under_tss = max(eff_tss, layers[-1])
    eff_ratio = clamp(eff_tss / x_in, 0, 1.2)
    under_ratio = clamp(under_tss / x_in, 0, max(1, ctx.params["maxLayerTss"] / x_in))
    eff = inlet.copy()
    under = inlet.copy()
    for index in SOLUBLE:
        eff[index] = inlet[index]
        under[index] = inlet[index]
    for index in PARTICULATE:
        eff[index] = inlet[index] * eff_ratio
        under[index] = inlet[index] * under_ratio
    return {"layers": layers, "eff": eff, "under": under, "qEff": q_eff, "qUnder": q_under}


def full_rhs(ctx: SimulationContext, vector: list[float], influent: list[float], layout: VectorStateLayout) -> list[float]:
    derivative = reactor_rhs(ctx, vector, influent, layout)
    aerobic = _slice_values(vector, layout.aerobic)
    layers = _slice_values(vector, layout.clarifier)
    derivative[layout.clarifier] = clarifier_layer_rhs(ctx, layers, aerobic)
    return derivative


def rk4_reactor_vector(ctx: SimulationContext, vector: list[float], influent: list[float], layout: VectorStateLayout, dt: float) -> list[float]:
    k1 = reactor_rhs(ctx, vector, influent, layout)
    k2 = reactor_rhs(ctx, add_scaled(vector, k1, dt / 2), influent, layout)
    k3 = reactor_rhs(ctx, add_scaled(vector, k2, dt / 2), influent, layout)
    k4 = reactor_rhs(ctx, add_scaled(vector, k3, dt), influent, layout)
    return [
        max(0.0, value + (dt / 6) * (k1[index] + 2 * k2[index] + 2 * k3[index] + k4[index]))
        for index, value in enumerate(vector)
    ]


def rk4_full_vector(ctx: SimulationContext, vector: list[float], influent: list[float], layout: VectorStateLayout, dt: float) -> list[float]:
    k1 = full_rhs(ctx, vector, influent, layout)
    k2 = full_rhs(ctx, add_scaled(vector, k1, dt / 2), influent, layout)
    k3 = full_rhs(ctx, add_scaled(vector, k2, dt / 2), influent, layout)
    k4 = full_rhs(ctx, add_scaled(vector, k3, dt), influent, layout)
    next_vector = [
        max(0.0, value + (dt / 6) * (k1[index] + 2 * k2[index] + 2 * k3[index] + k4[index]))
        for index, value in enumerate(vector)
    ]
    next_vector[layout.clarifier] = [clamp(value, 0, ctx.params["maxLayerTss"]) for value in next_vector[layout.clarifier]]
    return next_vector


def v2_solver_method(ctx: SimulationContext) -> str:
    method = str(ctx.params.get("solverMethod", "RK4")).strip().upper()
    if method not in V2_SOLVER_METHODS:
        raise ValueError("engine_v2 solverMethod 必须是 RK4、LSODA、BDF 或 Radau。")
    return method


def solve_full_vector(ctx: SimulationContext, vector: list[float], influent: list[float], layout: VectorStateLayout, dt: float) -> list[float]:
    method = v2_solver_method(ctx)
    if method == "RK4":
        return rk4_full_vector(ctx, vector, influent, layout, min(dt, MAX_SOLVER_STEP_DAYS))

    if dt <= 0:
        return vector.copy()

    def derivative(_time: float, values: list[float]) -> list[float]:
        clean_values = [max(0.0, float(value)) for value in values]
        return full_rhs(ctx, clean_values, influent, layout)

    solution = solve_ivp(
        derivative,
        (0.0, dt),
        vector,
        method=SCIPY_METHODS[method],
        rtol=ctx.params["solverRtol"],
        atol=ctx.params["solverAtol"],
        max_step=max(min(ctx.params["maxSolverStepHours"] / 24, dt), 1e-12),
    )
    if not solution.success:
        raise ValueError(f"engine_v2 {method} 解算失败：{solution.message}")
    next_vector = [max(0.0, float(value)) for value in solution.y[:, -1]]
    next_vector[layout.clarifier] = [clamp(value, 0, ctx.params["maxLayerTss"]) for value in next_vector[layout.clarifier]]
    return next_vector


def hybrid_step(ctx: SimulationContext, vector: list[float], influent: list[float], layout: VectorStateLayout, dt: float) -> tuple[list[float], dict[str, Any]]:
    """Advance the v2 vector state once.

    Reactors are advanced through a single coupled RHS. The clarifier and RAS
    are then updated through the current Takacs discrete step. This keeps v2
    testable while making the future continuous clarifier replacement local to
    this module.
    """

    dt = min(max(dt, 0.0), MAX_SOLVER_STEP_DAYS)
    reactor_vector = rk4_reactor_vector(ctx, vector, influent, layout, dt)
    state = unpack_state(reactor_vector, layout)
    q = ctx.params["influentQ"]
    ras_q = q * ctx.params["rasRatio"]
    was_q = min(ctx.params["wasQ"], q * 0.8)
    capture = clamp(ctx.params["captureEfficiency"] / 100, 0.8, 0.9995)
    split = ctx.takacs_clarifier_step(state["clarifierLayers"], state["aerobic"], q + ras_q, ras_q, was_q, dt, capture)
    state["clarifierLayers"] = split["layers"]
    state["ras"] = split["under"]
    return pack_state(state, layout), split


def continuous_step(ctx: SimulationContext, vector: list[float], influent: list[float], layout: VectorStateLayout, dt: float) -> tuple[list[float], dict[str, Any]]:
    """Advance v2 with continuous clarifier layer dynamics.

    This is still an experimental bridge: clarifier TSS layers are continuous,
    while RAS composition is updated from the final underflow at the end of the
    step. A later iteration can turn RAS into an algebraic connection or add a
    small hold-up state if needed.
    """

    dt = max(dt, 0.0)
    next_vector = solve_full_vector(ctx, vector, influent, layout, dt)
    state = unpack_state(next_vector, layout)
    split = split_from_layers(ctx, state["clarifierLayers"], state["aerobic"])
    state["ras"] = split["under"]
    return pack_state(state, layout), split


def push_vector_snapshot(
    ctx: SimulationContext,
    series: dict[str, Any],
    time: float,
    vector: list[float],
    layout: VectorStateLayout,
    influent: list[float],
    split: dict[str, Any] | None = None,
) -> None:
    state = unpack_state(vector, layout)
    resolved_split = split or split_from_layers(ctx, state["clarifierLayers"], state["aerobic"])
    ctx.push_snapshot(
        series,
        time,
        influent,
        state["anaerobic"],
        state["anoxic"],
        state["aerobic"],
        resolved_split,
        state["ras"],
        state["clarifierLayers"],
    )


def run_vector_simulation_v2(ctx: SimulationContext, records: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Run the experimental v2 engine with a frontend-compatible result shape."""

    ctx.sync_asm1_params()
    layout, vector = initial_vector_state(ctx)
    series = ctx.create_result_series()
    series["engineVersion"] = "v2"
    series["solverMethod"] = v2_solver_method(ctx)
    if series["solverMethod"] == "RK4":
        solver_dt = min(ctx.requested_step_days(), MAX_SOLVER_STEP_DAYS)
    else:
        solver_dt = min(ctx.requested_step_days(), ctx.params["maxSolverStepHours"] / 24)
    end_time = ctx.params["simulationDays"]
    output_interval = max(solver_dt, ctx.params["outputIntervalHours"] / 24)
    cursor = {"index": 0}
    saved_params = ctx.params.copy()
    has_records = bool(records)

    try:
        if has_records:
            ctx.mode = "csv"
            ctx.params.update(csv_values_at(records or [], 0.0, cursor))
            ctx.sync_asm1_params()
        else:
            ctx.mode = "manual"

        series["mode"] = ctx.mode
        series["sourceName"] = ctx.source_name
        influent = ctx.influent_vector()
        push_vector_snapshot(ctx, series, 0.0, vector, layout, influent)
        ctx.report_progress(0, end_time)

        current_time = 0.0
        next_output = output_interval
        while current_time < end_time - EPSILON_DAYS:
            if has_records:
                ctx.params.update(csv_values_at(records or [], current_time, cursor))
                ctx.sync_asm1_params()
            influent = ctx.influent_vector()
            target_time = min(end_time, next_output)
            dt = min(solver_dt, target_time - current_time)
            vector, split = continuous_step(ctx, vector, influent, layout, dt)
            current_time += dt
            if current_time >= next_output - EPSILON_DAYS or current_time >= end_time - EPSILON_DAYS:
                push_vector_snapshot(ctx, series, current_time, vector, layout, influent, split)
                ctx.report_progress(current_time, end_time)
                while next_output <= current_time + EPSILON_DAYS:
                    next_output += output_interval
    finally:
        ctx.params = saved_params
        ctx.sync_asm1_params()

    warnings = ["engine_v2 当前为实验引擎，结果需要与 v1 基准对比后再用于正式分析。"]
    if series["solverMethod"] != "RK4":
        warnings.append(f"engine_v2 当前使用 {series['solverMethod']} 自适应解算器，仍需通过 P4 基准测试确认速度和稳定性。")
    return attach_validation(series, warnings)


def vector_snapshot(ctx: SimulationContext, vector: list[float], layout: VectorStateLayout) -> dict[str, float]:
    state = unpack_state(vector, layout)
    return {
        "anaerobicNo3": state["anaerobic"][C["S_NO"]],
        "anoxicNo3": state["anoxic"][C["S_NO"]],
        "aerobicNo3": state["aerobic"][C["S_NO"]],
        "aerobicDo": state["aerobic"][C["S_O"]],
        "aerobicMlss": ctx.tss(state["aerobic"]),
        "rasMlss": ctx.tss(state["ras"]),
        "clarifierTopTss": state["clarifierLayers"][0],
        "clarifierBottomTss": state["clarifierLayers"][-1],
    }
