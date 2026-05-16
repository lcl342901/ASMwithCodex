from __future__ import annotations

from typing import Any

from .model import C, EPSILON_DAYS, MAX_SOLVER_STEP_DAYS, SimulationContext, attach_validation, clamp, csv_values_at


BSM1_TANK_IDS = ["anoxic1", "anoxic2", "aerobic1", "aerobic2", "aerobic3"]
BSM1_TANK_VOLUMES = {
    "anoxic1": 1000.0,
    "anoxic2": 1000.0,
    "aerobic1": 1333.0,
    "aerobic2": 1333.0,
    "aerobic3": 1334.0,
}
BSM1_TANK_KLA = {
    "anoxic1": 0.0,
    "anoxic2": 0.0,
    "aerobic1": 60.0,
    "aerobic2": 60.0,
    "aerobic3": 60.0,
}


def configure_bsm1_params(params: dict[str, Any]) -> dict[str, Any]:
    configured = params.copy()
    configured["anaerobicVolume"] = 1
    configured["anoxicVolume"] = BSM1_TANK_VOLUMES["anoxic1"] + BSM1_TANK_VOLUMES["anoxic2"]
    configured["aerobicVolume"] = BSM1_TANK_VOLUMES["aerobic1"] + BSM1_TANK_VOLUMES["aerobic2"] + BSM1_TANK_VOLUMES["aerobic3"]
    configured["clarifierArea"] = 1500
    configured["clarifierHeight"] = 4
    configured["clarifierLayers"] = 10
    configured["clarifierFeedLayer"] = 5
    configured.setdefault("rasRatio", 1.0)
    configured.setdefault("internalRecycleRatio", 3.0)
    configured.setdefault("wasQ", 385)
    return configured


def initial_bsm1_state(ctx: SimulationContext) -> dict[str, Any]:
    aerobic = ctx.initial_reactor_state("aerobic")
    return {
        "tanks": {
            "anoxic1": ctx.initial_reactor_state("anoxic"),
            "anoxic2": ctx.initial_reactor_state("anoxic"),
            "aerobic1": aerobic.copy(),
            "aerobic2": aerobic.copy(),
            "aerobic3": aerobic.copy(),
        },
        "ras": aerobic.copy(),
        "clarifierLayers": [ctx.tss(aerobic)] * int(clamp(round(ctx.params["clarifierLayers"]), 4, 20)),
    }


def create_bsm1_series(ctx: SimulationContext) -> dict[str, Any]:
    series = ctx.create_result_series()
    series["layout"] = {
        "id": "bsm1_5tank",
        "tankOrder": BSM1_TANK_IDS,
        "tankVolumes": BSM1_TANK_VOLUMES,
        "note": "Two anoxic tanks followed by three aerobic tanks, using the shared ASM1 and clarifier implementation.",
    }
    series["bsm1Units"] = {tank_id: {metric_id: [] for metric_id in ctx.create_unit_series()["aerobic"]} for tank_id in BSM1_TANK_IDS}
    return series


def push_bsm1_snapshot(
    ctx: SimulationContext,
    series: dict[str, Any],
    time: float,
    influent: list[float],
    state: dict[str, Any],
    split: dict[str, Any],
) -> None:
    tanks = state["tanks"]
    ctx.push_snapshot(
        series,
        time,
        influent,
        tanks["anoxic1"],
        tanks["anoxic2"],
        tanks["aerobic3"],
        split,
        state["ras"],
        state["clarifierLayers"],
    )
    for tank_id in BSM1_TANK_IDS:
        ctx.push_unit_metrics(series["bsm1Units"], tank_id, ctx.metrics_from_vector(tanks[tank_id]))


def step_bsm1_state(ctx: SimulationContext, state: dict[str, Any], influent: list[float], dt: float) -> dict[str, Any]:
    q = ctx.params["influentQ"]
    ras_q = q * ctx.params["rasRatio"]
    ir_q = q * ctx.params["internalRecycleRatio"]
    was_q = min(ctx.params["wasQ"], q * 0.8)
    capture = clamp(ctx.params["captureEfficiency"] / 100, 0.8, 0.9995)
    tanks = state["tanks"]

    anoxic1_in = ctx.mix_vectors([{"q": q, "c": influent}, {"q": ras_q, "c": state["ras"]}, {"q": ir_q, "c": tanks["aerobic3"]}])
    tanks["anoxic1"] = ctx.rk4_reactor(tanks["anoxic1"], anoxic1_in, q + ras_q + ir_q, BSM1_TANK_VOLUMES["anoxic1"], BSM1_TANK_KLA["anoxic1"], dt)
    tanks["anoxic2"] = ctx.rk4_reactor(tanks["anoxic2"], tanks["anoxic1"], q + ras_q + ir_q, BSM1_TANK_VOLUMES["anoxic2"], BSM1_TANK_KLA["anoxic2"], dt)
    tanks["aerobic1"] = ctx.rk4_reactor(tanks["aerobic1"], tanks["anoxic2"], q + ras_q + ir_q, BSM1_TANK_VOLUMES["aerobic1"], BSM1_TANK_KLA["aerobic1"] * ctx.params["aerobicDo"], dt)
    tanks["aerobic2"] = ctx.rk4_reactor(tanks["aerobic2"], tanks["aerobic1"], q + ras_q + ir_q, BSM1_TANK_VOLUMES["aerobic2"], BSM1_TANK_KLA["aerobic2"] * ctx.params["aerobicDo"], dt)
    tanks["aerobic3"] = ctx.rk4_reactor(tanks["aerobic3"], tanks["aerobic2"], q + ras_q + ir_q, BSM1_TANK_VOLUMES["aerobic3"], BSM1_TANK_KLA["aerobic3"] * ctx.params["aerobicDo"], dt)

    split = ctx.takacs_clarifier_step(state["clarifierLayers"], tanks["aerobic3"], q + ras_q, ras_q, was_q, dt, capture)
    state["clarifierLayers"] = split["layers"]
    state["ras"] = split["under"]
    return split


def run_bsm1_simulation(ctx: SimulationContext, records: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    saved_params = ctx.params.copy()
    ctx.params = configure_bsm1_params(ctx.params)
    ctx.sync_asm1_params()
    state = initial_bsm1_state(ctx)
    series = create_bsm1_series(ctx)
    series["engineVersion"] = "bsm1"
    series["solverMethod"] = "RK4"
    series["mode"] = "csv" if records else "manual"
    solver_dt = min(ctx.requested_step_days(), MAX_SOLVER_STEP_DAYS)
    end_time = ctx.params["simulationDays"]
    output_interval = max(solver_dt, ctx.params["outputIntervalHours"] / 24)
    current_time = 0.0
    next_output = output_interval
    cursor = {"index": 0}

    try:
        if records:
            ctx.params.update(csv_values_at(records, current_time, cursor))
            ctx.params = configure_bsm1_params(ctx.params)
            ctx.sync_asm1_params()
        influent = ctx.influent_vector()
        split = ctx.takacs_clarifier_step(state["clarifierLayers"], state["tanks"]["aerobic3"], ctx.params["influentQ"] * (1 + ctx.params["rasRatio"]), ctx.params["influentQ"] * ctx.params["rasRatio"], min(ctx.params["wasQ"], ctx.params["influentQ"] * 0.8), 0, clamp(ctx.params["captureEfficiency"] / 100, 0.8, 0.9995))
        push_bsm1_snapshot(ctx, series, current_time, influent, state, split)
        ctx.report_progress(current_time, end_time)

        while current_time < end_time - EPSILON_DAYS:
            if records:
                ctx.params.update(csv_values_at(records, current_time, cursor))
                ctx.params = configure_bsm1_params(ctx.params)
                ctx.sync_asm1_params()
            influent = ctx.influent_vector()
            target_time = min(end_time, next_output)
            dt = min(solver_dt, target_time - current_time)
            split = step_bsm1_state(ctx, state, influent, dt)
            current_time += dt
            if current_time >= next_output - EPSILON_DAYS or current_time >= end_time - EPSILON_DAYS:
                push_bsm1_snapshot(ctx, series, current_time, influent, state, split)
                ctx.report_progress(current_time, end_time)
                while next_output <= current_time + EPSILON_DAYS:
                    next_output += output_interval
    finally:
        ctx.params = saved_params
        ctx.sync_asm1_params()

    return attach_validation(series, ["BSM1 五池布局为第一版实验实现，仍需与官方动态输入和评价窗口进一步对齐。"])
