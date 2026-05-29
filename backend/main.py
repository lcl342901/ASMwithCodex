from __future__ import annotations

import copy
import os
from time import perf_counter
from threading import Lock, Thread
from uuid import uuid4
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .ai_analysis import analyze_result, chat_with_deepseek, deepseek_config
from .calibration import bsm1_calibration_report, bsm1_mapping_report, calibration_optimize, calibration_stage_configs, run_calibration_stage
from .engine_runner import normalize_engine_version, simulate_with_engine
from .model_trust import (
    assess_result_credibility,
    calibration_preview,
    compare_to_reference_case,
    get_reference_case,
    initial_condition_snapshot,
    model_metadata,
    reference_cases,
)
from .platform import (
    create_project,
    clear_project_csv,
    delete_project,
    ensure_default_project,
    get_project,
    delete_calibration_run,
    get_calibration_run,
    insert_calibration_run,
    list_calibration_runs,
    get_project_csv,
    get_project_params,
    list_projects,
    reset_project_params,
    save_project_csv,
    save_project_params,
    update_project,
)
from .realtime import (
    clear_calculation_logs,
    get_cleaning_settings,
    get_saved_params,
    generate_mock_observation,
    ingest_input,
    insert_calculation_log,
    insert_observation,
    latest,
    list_data_sources,
    list_calculation_logs,
    list_observations,
    list_point_configs,
    load_simulation_state,
    mock_status,
    realtime_forecast,
    realtime_history,
    realtime_step,
    realtime_status,
    realtime_trust,
    reset,
    reset_params_config,
    save_cleaning_settings,
    save_params_config,
    save_simulation_state,
    start_mock,
    stop_mock,
)
from .schemas import (
    AIAnalysisRequest,
    AIChatRequest,
    CalibrationPreviewRequest,
    Bsm1CalibrationReportRequest,
    Bsm1MappingRequest,
    CalibrationStageRunRequest,
    CleaningSettingsRequest,
    CalibrationOptimizeRequest,
    InitialConditionRequest,
    ModelCredibilityRequest,
    ParamConfigRequest,
    ProjectCsvRequest,
    ProjectRequest,
    ProjectUpdateRequest,
    ReferenceComparisonRequest,
    RealtimeIngestRequest,
    RealtimeForecastRequest,
    RealtimeStepRequest,
    RealtimeMockStartRequest,
    RealtimeMockObservationRequest,
    RealtimeObservationRequest,
    SimulationRequest,
)


app = FastAPI(title="ASMwithCodex Simulation API")
SIMULATION_JOBS: dict[str, dict[str, Any]] = {}
SIMULATION_JOBS_LOCK = Lock()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def configured_api_token() -> str:
    return os.getenv("ASM_API_TOKEN", "").strip()


def request_api_token(request: Request) -> str:
    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        return auth_header[7:].strip()
    return request.headers.get("x-api-key", "").strip()


@app.middleware("http")
async def optional_api_token_middleware(request: Request, call_next):
    token = configured_api_token()
    if not token or request.method == "OPTIONS" or request.url.path == "/api/health":
        return await call_next(request)
    if request_api_token(request) != token:
        return JSONResponse(status_code=401, content={"detail": "Missing or invalid API token."})
    return await call_next(request)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/ai/status")
def ai_status_endpoint() -> dict[str, Any]:
    config = deepseek_config()
    return {
        "provider": config["provider"],
        "configured": config["configured"],
        "model": config["model"],
        "models": config.get("models", []),
    }


@app.post("/api/ai/analyze")
def ai_analyze_endpoint(request: AIAnalysisRequest) -> dict[str, Any]:
    started = perf_counter()
    project_id = request.projectId or "default"
    try:
        result = analyze_result(
            result=request.result,
            params=request.params,
            context={**request.context, "projectId": project_id},
            model=request.model,
        )
        insert_calculation_log(
            "ai_analysis",
            "success",
            "AI simulation analysis completed.",
            {"projectId": project_id, "provider": result.get("provider"), "model": result.get("model")},
            (perf_counter() - started) * 1000,
            project_id,
        )
        return result
    except RuntimeError as exc:
        insert_calculation_log(
            "ai_analysis",
            "failed",
            str(exc),
            {"projectId": project_id},
            (perf_counter() - started) * 1000,
            project_id,
        )
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/api/ai/chat")
def ai_chat_endpoint(request: AIChatRequest) -> dict[str, Any]:
    started = perf_counter()
    project_id = request.projectId or "default"
    try:
        result = chat_with_deepseek(
            messages=request.messages,
            params=request.params,
            result=request.result,
            context={**request.context, "projectId": project_id},
        )
        insert_calculation_log(
            "ai_chat",
            "success",
            "AI platform chat completed.",
            {"projectId": project_id, "provider": result.get("provider"), "model": result.get("model")},
            (perf_counter() - started) * 1000,
            project_id,
        )
        return result
    except RuntimeError as exc:
        insert_calculation_log(
            "ai_chat",
            "failed",
            str(exc),
            {"projectId": project_id},
            (perf_counter() - started) * 1000,
            project_id,
        )
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def job_public(job_id: str) -> dict[str, Any]:
    with SIMULATION_JOBS_LOCK:
        job = SIMULATION_JOBS.get(job_id)
        if not job:
            raise KeyError(job_id)
        return {key: value for key, value in job.items() if key != "result"}


def update_job(job_id: str, **values: Any) -> None:
    with SIMULATION_JOBS_LOCK:
        if job_id in SIMULATION_JOBS:
            SIMULATION_JOBS[job_id].update(values)


class SimulationCancelled(Exception):
    pass


def job_cancel_requested(job_id: str) -> bool:
    with SIMULATION_JOBS_LOCK:
        return bool(SIMULATION_JOBS.get(job_id, {}).get("cancelRequested"))


def result_state_summary(result: dict[str, Any]) -> dict[str, Any]:
    last_index = len(result.get("time", [])) - 1
    if last_index < 0:
        return {}
    return {
        "time": result["time"][last_index],
        "mode": result.get("mode", ""),
        "engineVersion": result.get("engineVersion", ""),
        "effCod": result.get("effCod", [None])[last_index],
        "effNh4": result.get("effNh4", [None])[last_index],
        "effTn": result.get("effTn", [None])[last_index],
        "effTss": result.get("effTss", [None])[last_index],
    }


def stateful_initial_state(request: SimulationRequest, engine_version: str) -> tuple[str, dict[str, Any] | None, dict[str, Any] | None]:
    project_id = request.projectId or "default"
    saved = load_simulation_state(project_id) if request.useLastFinalState and engine_version == "v1" else None
    return project_id, saved, saved["state"] if saved else None


def persist_result_state(request: SimulationRequest, result: dict[str, Any], project_id: str, saved_state: dict[str, Any] | None) -> dict[str, Any]:
    final_state = result.get("finalState")
    saved_final = False
    updated_at = None
    if request.saveFinalState and isinstance(final_state, dict):
        saved = save_simulation_state(project_id, request.params, final_state, result_state_summary(result))
        saved_final = True
        updated_at = saved["updatedAt"]
    metadata = {
        "projectId": project_id,
        "usedPreviousState": bool(saved_state),
        "previousStateUpdatedAt": saved_state.get("updatedAt") if saved_state else None,
        "savedFinalState": saved_final,
        "updatedAt": updated_at,
    }
    result["statePersistence"] = metadata
    return metadata


def run_simulation_job(job_id: str, request: SimulationRequest) -> None:
    started = perf_counter()
    engine_version = "unknown"

    def report_progress(current_time: float, total_time: float) -> None:
        if job_cancel_requested(job_id):
            raise SimulationCancelled("仿真已由用户终止。")
        percent = 0 if total_time <= 0 else min(99, max(0, current_time / total_time * 100))
        update_job(
            job_id,
            status="running",
            progressPercent=percent,
            currentTime=current_time,
            totalTime=total_time,
            message=f"已计算到 {current_time:.2f} / {total_time:.2f} d",
        )

    def report_partial_result(partial: dict[str, Any]) -> None:
        if job_cancel_requested(job_id):
            raise SimulationCancelled("仿真已由用户终止。")
        partial_copy = copy.deepcopy(partial)
        partial_copy["engineVersion"] = engine_version
        partial_copy["solverMethod"] = request.params.get("solverMethod", "RK4")
        update_job(
            job_id,
            partialResult=partial_copy,
            partialPoints=len(partial_copy.get("time", [])),
        )

    update_job(job_id, status="running", message="仿真已开始。", progressPercent=0)
    try:
        engine_version = normalize_engine_version(request.params)
        project_id, saved_state, initial_state = stateful_initial_state(request, engine_version)
        result = simulate_with_engine(
            params=request.params,
            csv_text=request.csvText or "",
            csv_file_name=request.csvFileName or "",
            progress_callback=report_progress,
            partial_result_callback=report_partial_result,
            initial_state=initial_state,
        )
        state_metadata = persist_result_state(request, result, project_id, saved_state)
        duration_ms = (perf_counter() - started) * 1000
        with SIMULATION_JOBS_LOCK:
            SIMULATION_JOBS[job_id].update(
                {
                    "status": "success",
                    "progressPercent": 100,
                    "currentTime": result["time"][-1] if result["time"] else None,
                    "totalTime": result["time"][-1] if result["time"] else None,
                    "message": "仿真完成。",
                    "durationMs": duration_ms,
                    "result": result,
                    "partialResult": result,
                    "partialPoints": len(result["time"]),
                }
            )
        insert_calculation_log(
            "simulate_job",
            "success",
            f"Simulation job {job_id} completed with {len(result['time'])} output points.",
            {
                "jobId": job_id,
                "mode": result["mode"],
                "sourceName": result.get("sourceName", ""),
                "points": len(result["time"]),
                "lastTime": result["time"][-1] if result["time"] else None,
                "warningCount": result.get("validation", {}).get("warningCount", 0),
                "solverMethod": request.params.get("solverMethod", "RK4"),
                "engineVersion": result.get("engineVersion", engine_version),
                "projectId": project_id,
                "usedPreviousState": state_metadata["usedPreviousState"],
                "savedFinalState": state_metadata["savedFinalState"],
            },
            duration_ms,
            project_id,
        )
    except SimulationCancelled as exc:
        duration_ms = (perf_counter() - started) * 1000
        update_job(job_id, status="cancelled", message=str(exc), error=None, durationMs=duration_ms, progressPercent=progress_value(job_id))
        insert_calculation_log("simulate_job", "cancelled", str(exc), {"jobId": job_id, "projectId": request.projectId or "default", "solverMethod": request.params.get("solverMethod", "RK4"), "engineVersion": engine_version}, duration_ms, request.projectId)
    except ValueError as exc:
        duration_ms = (perf_counter() - started) * 1000
        update_job(job_id, status="failed", message=str(exc), error=str(exc), durationMs=duration_ms)
        insert_calculation_log("simulate_job", "failed", str(exc), {"jobId": job_id, "projectId": request.projectId or "default", "solverMethod": request.params.get("solverMethod", "RK4"), "engineVersion": engine_version}, duration_ms, request.projectId)
    except Exception as exc:
        duration_ms = (perf_counter() - started) * 1000
        update_job(job_id, status="failed", message="仿真任务失败。", error=str(exc), durationMs=duration_ms)
        insert_calculation_log("simulate_job", "failed", str(exc), {"jobId": job_id, "projectId": request.projectId or "default", "solverMethod": request.params.get("solverMethod", "RK4"), "engineVersion": engine_version}, duration_ms, request.projectId)


@app.post("/api/simulate")
def simulate_endpoint(request: SimulationRequest) -> dict:
    started = perf_counter()
    engine_version = "unknown"
    try:
        engine_version = normalize_engine_version(request.params)
        project_id, saved_state, initial_state = stateful_initial_state(request, engine_version)
        result = simulate_with_engine(
            params=request.params,
            csv_text=request.csvText or "",
            csv_file_name=request.csvFileName or "",
            initial_state=initial_state,
        )
        state_metadata = persist_result_state(request, result, project_id, saved_state)
        insert_calculation_log(
            "simulate",
            "success",
            f"{result['mode']} simulation completed with {len(result['time'])} output points.",
            {
                "mode": result["mode"],
                "sourceName": result.get("sourceName", ""),
                "points": len(result["time"]),
                "lastTime": result["time"][-1] if result["time"] else None,
                "warningCount": result.get("validation", {}).get("warningCount", 0),
                "solverMethod": request.params.get("solverMethod", "RK4"),
                "engineVersion": result.get("engineVersion", engine_version),
                "projectId": project_id,
                "usedPreviousState": state_metadata["usedPreviousState"],
                "savedFinalState": state_metadata["savedFinalState"],
            },
            (perf_counter() - started) * 1000,
            project_id,
        )
        return result
    except ValueError as exc:
        insert_calculation_log(
            "simulate",
            "failed",
            str(exc),
            {"projectId": request.projectId or "default", "csvFileName": request.csvFileName or "", "hasCsv": bool((request.csvText or "").strip()), "solverMethod": request.params.get("solverMethod", "RK4"), "engineVersion": engine_version},
            (perf_counter() - started) * 1000,
            request.projectId,
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        insert_calculation_log(
            "simulate",
            "failed",
            str(exc),
            {"projectId": request.projectId or "default", "csvFileName": request.csvFileName or "", "hasCsv": bool((request.csvText or "").strip()), "solverMethod": request.params.get("solverMethod", "RK4"), "engineVersion": engine_version},
            (perf_counter() - started) * 1000,
            request.projectId,
        )
        raise HTTPException(status_code=500, detail="Simulation failed unexpectedly.") from exc


@app.post("/api/simulate/jobs")
def create_simulation_job_endpoint(request: SimulationRequest) -> dict:
    job_id = uuid4().hex
    try:
        engine_version = normalize_engine_version(request.params)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    with SIMULATION_JOBS_LOCK:
        SIMULATION_JOBS[job_id] = {
            "jobId": job_id,
            "status": "queued",
            "progressPercent": 0,
            "currentTime": 0,
            "totalTime": request.params.get("simulationDays"),
            "message": "仿真任务已创建。",
            "error": None,
            "durationMs": None,
            "solverMethod": request.params.get("solverMethod", "RK4"),
            "engineVersion": engine_version,
            "partialResult": None,
            "partialPoints": 0,
            "cancelRequested": False,
        }
    Thread(target=run_simulation_job, args=(job_id, request), daemon=True).start()
    return job_public(job_id)


@app.get("/api/simulate/jobs/{job_id}")
def get_simulation_job_endpoint(job_id: str) -> dict:
    try:
        return job_public(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Simulation job not found.") from exc


def progress_value(job_id: str) -> float:
    with SIMULATION_JOBS_LOCK:
        return float(SIMULATION_JOBS.get(job_id, {}).get("progressPercent") or 0)


@app.post("/api/simulate/jobs/{job_id}/cancel")
def cancel_simulation_job_endpoint(job_id: str) -> dict:
    with SIMULATION_JOBS_LOCK:
        job = SIMULATION_JOBS.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Simulation job not found.")
        if job["status"] in {"success", "failed", "cancelled"}:
            return {key: value for key, value in job.items() if key != "result"}
        job["cancelRequested"] = True
        job["message"] = "正在终止仿真..."
    return job_public(job_id)


@app.get("/api/simulate/jobs/{job_id}/result")
def get_simulation_job_result_endpoint(job_id: str) -> dict:
    with SIMULATION_JOBS_LOCK:
        job = SIMULATION_JOBS.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Simulation job not found.")
        if job["status"] == "failed":
            raise HTTPException(status_code=400, detail=job.get("error") or "Simulation job failed.")
        if job["status"] != "success" or "result" not in job:
            raise HTTPException(status_code=409, detail="Simulation job is not complete.")
        return job["result"]


@app.get("/api/logs")
def list_logs_endpoint(limit: int = 100, projectId: str = "default") -> dict:
    return list_calculation_logs(limit, projectId)


@app.delete("/api/logs")
def clear_logs_endpoint(projectId: str = "default") -> dict:
    return clear_calculation_logs(projectId)


@app.get("/api/model/metadata")
def model_metadata_endpoint() -> dict:
    return model_metadata()


@app.get("/api/model/reference-cases")
def model_reference_cases_endpoint() -> dict:
    return reference_cases()


@app.get("/api/model/reference-cases/{case_id}")
def model_reference_case_endpoint(case_id: str) -> dict:
    try:
        return get_reference_case(case_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/model/reference-cases/{case_id}/compare")
def model_reference_case_compare_endpoint(case_id: str, request: ReferenceComparisonRequest) -> dict:
    try:
        return compare_to_reference_case(case_id, request.result)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/model/initial-conditions")
def model_initial_conditions_endpoint(request: InitialConditionRequest) -> dict:
    try:
        return initial_condition_snapshot(request.params)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/model/credibility")
def model_credibility_endpoint(request: ModelCredibilityRequest) -> dict:
    try:
        return assess_result_credibility(request.result, request.params)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/calibration/preview")
def calibration_preview_endpoint(request: CalibrationPreviewRequest) -> dict:
    try:
        return calibration_preview(
            params=request.params,
            observations=request.observations,
            tunable_params=request.tunableParams,
            targets=request.targets,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/calibration/bsm1/mapping")
def calibration_bsm1_mapping_endpoint(request: Bsm1MappingRequest) -> dict:
    try:
        return bsm1_mapping_report(request.params)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/calibration/bsm1/report")
def calibration_bsm1_report_endpoint(request: Bsm1CalibrationReportRequest) -> dict:
    started = perf_counter()
    try:
        result = bsm1_calibration_report(
            params=request.params,
            use_bsm1_layout=request.useBsm1Layout,
            max_iterations=request.maxIterations,
            step_fraction=request.stepFraction,
        )
        insert_calculation_log(
            "calibration_bsm1_report",
            "success",
            "BSM1 calibration report completed.",
            {
                "layout": result["layout"],
                "baselineObjective": result["baselineObjective"],
                "optimizedObjective": result["optimizedObjective"],
            },
            (perf_counter() - started) * 1000,
        )
        return result
    except ValueError as exc:
        insert_calculation_log("calibration_bsm1_report", "failed", str(exc), {}, (perf_counter() - started) * 1000)
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/calibration/stages")
def calibration_stages_endpoint() -> dict:
    return calibration_stage_configs()


@app.post("/api/calibration/stages/run")
def calibration_stage_run_endpoint(request: CalibrationStageRunRequest) -> dict:
    started = perf_counter()
    try:
        request_payload = request.model_dump()
        payload = run_calibration_stage(
            stage_id=request.stageId,
            params=request.params,
            observations=request.observations,
            csv_text=request.csvText or "",
            csv_file_name=request.csvFileName or "",
            max_iterations=request.maxIterations,
            step_fraction=request.stepFraction,
            use_bsm1_mapping=request.useBsm1Mapping,
            use_bsm1_layout=request.useBsm1Layout,
        )
        result = payload["result"]
        insert_calculation_log(
            "calibration_stage_run",
            "success",
            "Calibration stage completed.",
            {
                "stageId": payload["stage"]["id"],
                "bestObjective": result["bestObjective"],
                "targetCount": len(result["targets"]),
                "tunableCount": len(result["tunableParams"]),
            },
            (perf_counter() - started) * 1000,
            request.projectId,
        )
        if request.saveRun:
            saved = insert_calibration_run(
                request.projectId or "default",
                request.name or f"Calibration stage: {payload['stage']['name']}",
                result["status"],
                request_payload,
                {**result, "stage": payload["stage"]},
            )
            payload["savedRun"] = {"id": saved["id"], "name": saved["name"], "projectId": saved["projectId"]}
        return payload
    except ValueError as exc:
        insert_calculation_log("calibration_stage_run", "failed", str(exc), {}, (perf_counter() - started) * 1000, request.projectId)
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/calibration/optimize")
def calibration_optimize_endpoint(request: CalibrationOptimizeRequest) -> dict:
    started = perf_counter()
    try:
        request_payload = request.model_dump()
        result = calibration_optimize(
            params=request.params,
            observations=request.observations,
            tunable_params=request.tunableParams,
            targets=request.targets,
            csv_text=request.csvText or "",
            csv_file_name=request.csvFileName or "",
            max_iterations=request.maxIterations,
            step_fraction=request.stepFraction,
            use_bsm1_mapping=request.useBsm1Mapping,
            use_bsm1_layout=request.useBsm1Layout,
        )
        insert_calculation_log(
            "calibration_optimize",
            "success",
            "Calibration optimization completed.",
            {
                "method": result["method"],
                "mapping": result["mapping"],
                "bestObjective": result["bestObjective"],
                "targetCount": len(result["targets"]),
                "tunableCount": len(result["tunableParams"]),
            },
            (perf_counter() - started) * 1000,
            request.projectId,
        )
        if request.saveRun:
            saved = insert_calibration_run(
                request.projectId or "default",
                request.name or "Calibration run",
                result["status"],
                request_payload,
                result,
            )
            result["savedRun"] = {"id": saved["id"], "name": saved["name"], "projectId": saved["projectId"]}
        return result
    except ValueError as exc:
        insert_calculation_log("calibration_optimize", "failed", str(exc), {}, (perf_counter() - started) * 1000, request.projectId)
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/config/params")
def get_param_config_endpoint() -> dict:
    return get_saved_params()


@app.get("/api/projects")
def list_projects_endpoint() -> dict:
    return list_projects()


@app.post("/api/projects")
def create_project_endpoint(request: ProjectRequest) -> dict:
    try:
        project = create_project(request.name, request.description, request.ownerId)
        insert_calculation_log("project_create", "success", f"Project {project['id']} created.", {"projectId": project["id"]})
        return project
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/projects/default")
def default_project_endpoint() -> dict:
    return ensure_default_project()


@app.get("/api/projects/{project_id}")
def get_project_endpoint(project_id: str) -> dict:
    try:
        return get_project(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.patch("/api/projects/{project_id}")
def update_project_endpoint(project_id: str, request: ProjectUpdateRequest) -> dict:
    try:
        return update_project(project_id, request.name, request.description)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/api/projects/{project_id}")
def delete_project_endpoint(project_id: str) -> dict:
    try:
        return delete_project(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/projects/{project_id}/params")
def get_project_params_endpoint(project_id: str) -> dict:
    try:
        return get_project_params(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/projects/{project_id}/params")
def save_project_params_endpoint(project_id: str, request: ParamConfigRequest) -> dict:
    try:
        return save_project_params(project_id, request.params)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/api/projects/{project_id}/params")
def reset_project_params_endpoint(project_id: str) -> dict:
    try:
        return reset_project_params(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/projects/{project_id}/csv")
def get_project_csv_endpoint(project_id: str) -> dict:
    try:
        return get_project_csv(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/projects/{project_id}/csv")
def save_project_csv_endpoint(project_id: str, request: ProjectCsvRequest) -> dict:
    try:
        return save_project_csv(project_id, request.csvText, request.csvFileName)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/api/projects/{project_id}/csv")
def clear_project_csv_endpoint(project_id: str) -> dict:
    try:
        return clear_project_csv(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/projects/{project_id}/calibration-runs")
def list_project_calibration_runs_endpoint(project_id: str, limit: int = 100) -> dict:
    try:
        return list_calibration_runs(project_id, limit)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/projects/{project_id}/calibration-runs/{run_id}")
def get_project_calibration_run_endpoint(project_id: str, run_id: int) -> dict:
    try:
        return get_calibration_run(project_id, run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.delete("/api/projects/{project_id}/calibration-runs/{run_id}")
def delete_project_calibration_run_endpoint(project_id: str, run_id: int) -> dict:
    try:
        return delete_calibration_run(project_id, run_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/config/params")
def save_param_config_endpoint(request: ParamConfigRequest) -> dict:
    started = perf_counter()
    try:
        result = save_params_config(request.params)
        insert_calculation_log(
            "config_save",
            "success",
            "Parameter configuration saved.",
            {"warningCount": len(result.get("warnings", []))},
            (perf_counter() - started) * 1000,
        )
        return result
    except ValueError as exc:
        insert_calculation_log(
            "config_save",
            "failed",
            str(exc),
            {},
            (perf_counter() - started) * 1000,
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/api/config/params")
def reset_param_config_endpoint() -> dict:
    result = reset_params_config()
    insert_calculation_log("config_reset", "success", "Parameter configuration reset to defaults.")
    return result


@app.post("/api/realtime/ingest")
def realtime_ingest_endpoint(request: RealtimeIngestRequest) -> dict:
    return ingest_input(request.timestamp, request.values, request.quality, request.projectId)


@app.post("/api/realtime/step")
def realtime_step_endpoint(request: RealtimeStepRequest) -> dict:
    started = perf_counter()
    try:
        result = realtime_step(
            timestamp=request.timestamp,
            values=request.values,
            quality=request.quality,
            params=request.params,
            step_hours=request.stepHours,
            project_id=request.projectId,
        )
        insert_calculation_log(
            "realtime_step",
            "success",
            f"Realtime step completed, result #{result['resultId']}.",
            {"resultId": result["resultId"], "stepHours": request.stepHours, "projectId": request.projectId},
            (perf_counter() - started) * 1000,
            request.projectId,
        )
        return result
    except ValueError as exc:
        insert_calculation_log(
            "realtime_step",
            "failed",
            str(exc),
            {"stepHours": request.stepHours, "projectId": request.projectId},
            (perf_counter() - started) * 1000,
            request.projectId,
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        insert_calculation_log(
            "realtime_step",
            "failed",
            str(exc),
            {"stepHours": request.stepHours, "projectId": request.projectId},
            (perf_counter() - started) * 1000,
            request.projectId,
        )
        raise HTTPException(status_code=500, detail="Realtime step failed unexpectedly.") from exc


@app.get("/api/realtime/latest")
def realtime_latest_endpoint(projectId: str = "default") -> dict:
    return latest(projectId)


@app.get("/api/realtime/history")
def realtime_history_endpoint(projectId: str = "default", hours: float = 12, limit: int = 200) -> dict:
    return realtime_history(projectId, hours, limit)


@app.post("/api/realtime/observations")
def realtime_observation_endpoint(request: RealtimeObservationRequest) -> dict:
    started = perf_counter()
    try:
        result = insert_observation(
            timestamp=request.timestamp,
            values=request.values,
            source=request.source,
            project_id=request.projectId,
        )
        insert_calculation_log(
            "realtime_observation",
            "success",
            f"Realtime observation #{result['id']} saved.",
            {"observationId": result["id"], "projectId": request.projectId, "source": request.source},
            (perf_counter() - started) * 1000,
            request.projectId,
        )
        return result
    except ValueError as exc:
        insert_calculation_log(
            "realtime_observation",
            "failed",
            str(exc),
            {"projectId": request.projectId, "source": request.source},
            (perf_counter() - started) * 1000,
            request.projectId,
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/realtime/observations")
def realtime_observations_endpoint(projectId: str = "default", hours: float = 24, limit: int = 200) -> dict:
    return list_observations(projectId, hours, limit)


@app.post("/api/realtime/observations/mock")
def realtime_mock_observation_endpoint(request: RealtimeMockObservationRequest) -> dict:
    started = perf_counter()
    try:
        result = generate_mock_observation(
            project_id=request.projectId,
            source=request.source,
            noise_fraction=request.noiseFraction,
        )
        insert_calculation_log(
            "realtime_mock_observation",
            "success",
            f"Mock observation #{result['id']} generated.",
            {"observationId": result["id"], "basisResultId": result.get("basisResultId"), "projectId": request.projectId},
            (perf_counter() - started) * 1000,
            request.projectId,
        )
        return result
    except ValueError as exc:
        insert_calculation_log(
            "realtime_mock_observation",
            "failed",
            str(exc),
            {"projectId": request.projectId},
            (perf_counter() - started) * 1000,
            request.projectId,
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/realtime/trust")
def realtime_trust_endpoint(projectId: str = "default", hours: float = 24, maxLagHours: float = 2.0) -> dict:
    return realtime_trust(projectId, hours, maxLagHours)


@app.post("/api/realtime/forecast")
def realtime_forecast_endpoint(request: RealtimeForecastRequest) -> dict:
    started = perf_counter()
    try:
        result = realtime_forecast(
            project_id=request.projectId,
            horizon_hours=request.horizonHours,
            step_hours=request.stepHours,
            history_hours=request.historyHours,
        )
        insert_calculation_log(
            "realtime_forecast",
            "success",
            "Realtime forecast completed.",
            {
                "projectId": request.projectId,
                "runId": result.get("runId"),
                "horizonHours": request.horizonHours,
                "method": result.get("method"),
            },
            (perf_counter() - started) * 1000,
            request.projectId,
        )
        return result
    except ValueError as exc:
        insert_calculation_log(
            "realtime_forecast",
            "failed",
            str(exc),
            {"projectId": request.projectId, "horizonHours": request.horizonHours},
            (perf_counter() - started) * 1000,
            request.projectId,
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        insert_calculation_log(
            "realtime_forecast",
            "failed",
            str(exc),
            {"projectId": request.projectId, "horizonHours": request.horizonHours},
            (perf_counter() - started) * 1000,
            request.projectId,
        )
        raise HTTPException(status_code=500, detail="Realtime forecast failed unexpectedly.") from exc


@app.get("/api/realtime/sources")
def realtime_sources_endpoint() -> dict:
    return list_data_sources()


@app.get("/api/realtime/points")
def realtime_points_endpoint(projectId: str = "default") -> dict:
    return list_point_configs(projectId)


@app.get("/api/realtime/cleaning-settings")
def realtime_cleaning_settings_endpoint(projectId: str = "default") -> dict:
    return get_cleaning_settings(projectId)


@app.post("/api/realtime/cleaning-settings")
def save_realtime_cleaning_settings_endpoint(request: CleaningSettingsRequest) -> dict:
    result = save_cleaning_settings(request.projectId, request.enabledRules)
    insert_calculation_log(
        "cleaning_settings",
        "success",
        "Realtime cleaning rules updated.",
        {"projectId": request.projectId, "enabledRules": result["enabledRules"]},
        None,
        request.projectId,
    )
    return result


@app.get("/api/realtime/status")
def realtime_status_endpoint(projectId: str = "default") -> dict:
    return realtime_status(projectId)


@app.post("/api/realtime/reset")
def realtime_reset_endpoint(projectId: str = "default") -> dict:
    result = reset(projectId)
    insert_calculation_log("realtime_reset", "success", "Realtime state, inputs, and results were reset.", {"projectId": projectId}, None, projectId)
    return result


@app.post("/api/realtime/mock/start")
async def realtime_mock_start_endpoint(request: RealtimeMockStartRequest = RealtimeMockStartRequest()) -> dict:
    try:
        result = await start_mock(
            interval_seconds=request.intervalSeconds,
            project_id=request.projectId,
            profile=request.profile,
            warm_start=request.warmStart,
        )
        insert_calculation_log("mock_start", "success", "Mock realtime runner started.", result)
        return result
    except ValueError as exc:
        insert_calculation_log("mock_start", "failed", str(exc))
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/realtime/mock/stop")
async def realtime_mock_stop_endpoint() -> dict:
    result = await stop_mock()
    insert_calculation_log("mock_stop", "success", "Mock realtime runner stopped.", result)
    return result


@app.get("/api/realtime/mock/status")
def realtime_mock_status_endpoint() -> dict:
    return mock_status()


@app.on_event("shutdown")
async def shutdown_event() -> None:
    await stop_mock()
