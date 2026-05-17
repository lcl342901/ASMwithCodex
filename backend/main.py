from time import perf_counter
from threading import Lock, Thread
from uuid import uuid4
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .calibration import bsm1_calibration_report, bsm1_mapping_report, calibration_optimize
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
    get_saved_params,
    ingest_input,
    insert_calculation_log,
    latest,
    list_data_sources,
    list_calculation_logs,
    mock_status,
    realtime_step,
    realtime_status,
    reset,
    reset_params_config,
    save_params_config,
    start_mock,
    stop_mock,
)
from .schemas import (
    CalibrationPreviewRequest,
    Bsm1CalibrationReportRequest,
    Bsm1MappingRequest,
    CalibrationOptimizeRequest,
    InitialConditionRequest,
    ModelCredibilityRequest,
    ParamConfigRequest,
    ProjectCsvRequest,
    ProjectRequest,
    ProjectUpdateRequest,
    ReferenceComparisonRequest,
    RealtimeIngestRequest,
    RealtimeStepRequest,
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


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


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


def run_simulation_job(job_id: str, request: SimulationRequest) -> None:
    started = perf_counter()
    engine_version = "unknown"

    def report_progress(current_time: float, total_time: float) -> None:
        percent = 0 if total_time <= 0 else min(99, max(0, current_time / total_time * 100))
        update_job(
            job_id,
            status="running",
            progressPercent=percent,
            currentTime=current_time,
            totalTime=total_time,
            message=f"已计算到 {current_time:.2f} / {total_time:.2f} d",
        )

    update_job(job_id, status="running", message="仿真已开始。", progressPercent=0)
    try:
        engine_version = normalize_engine_version(request.params)
        result = simulate_with_engine(
            params=request.params,
            csv_text=request.csvText or "",
            csv_file_name=request.csvFileName or "",
            progress_callback=report_progress,
        )
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
            },
            duration_ms,
        )
    except ValueError as exc:
        duration_ms = (perf_counter() - started) * 1000
        update_job(job_id, status="failed", message=str(exc), error=str(exc), durationMs=duration_ms)
        insert_calculation_log("simulate_job", "failed", str(exc), {"jobId": job_id, "solverMethod": request.params.get("solverMethod", "RK4"), "engineVersion": engine_version}, duration_ms)
    except Exception as exc:
        duration_ms = (perf_counter() - started) * 1000
        update_job(job_id, status="failed", message="仿真任务失败。", error=str(exc), durationMs=duration_ms)
        insert_calculation_log("simulate_job", "failed", str(exc), {"jobId": job_id, "solverMethod": request.params.get("solverMethod", "RK4"), "engineVersion": engine_version}, duration_ms)


@app.post("/api/simulate")
def simulate_endpoint(request: SimulationRequest) -> dict:
    started = perf_counter()
    engine_version = "unknown"
    try:
        engine_version = normalize_engine_version(request.params)
        result = simulate_with_engine(
            params=request.params,
            csv_text=request.csvText or "",
            csv_file_name=request.csvFileName or "",
        )
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
            },
            (perf_counter() - started) * 1000,
        )
        return result
    except ValueError as exc:
        insert_calculation_log(
            "simulate",
            "failed",
            str(exc),
            {"csvFileName": request.csvFileName or "", "hasCsv": bool((request.csvText or "").strip()), "solverMethod": request.params.get("solverMethod", "RK4"), "engineVersion": engine_version},
            (perf_counter() - started) * 1000,
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        insert_calculation_log(
            "simulate",
            "failed",
            str(exc),
            {"csvFileName": request.csvFileName or "", "hasCsv": bool((request.csvText or "").strip()), "solverMethod": request.params.get("solverMethod", "RK4"), "engineVersion": engine_version},
            (perf_counter() - started) * 1000,
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
        }
    Thread(target=run_simulation_job, args=(job_id, request), daemon=True).start()
    return job_public(job_id)


@app.get("/api/simulate/jobs/{job_id}")
def get_simulation_job_endpoint(job_id: str) -> dict:
    try:
        return job_public(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Simulation job not found.") from exc


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


@app.get("/api/realtime/sources")
def realtime_sources_endpoint() -> dict:
    return list_data_sources()


@app.get("/api/realtime/status")
def realtime_status_endpoint(projectId: str = "default") -> dict:
    return realtime_status(projectId)


@app.post("/api/realtime/reset")
def realtime_reset_endpoint(projectId: str = "default") -> dict:
    result = reset(projectId)
    insert_calculation_log("realtime_reset", "success", "Realtime state, inputs, and results were reset.", {"projectId": projectId}, None, projectId)
    return result


@app.post("/api/realtime/mock/start")
async def realtime_mock_start_endpoint() -> dict:
    try:
        result = await start_mock()
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
