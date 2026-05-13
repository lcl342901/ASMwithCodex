from time import perf_counter
from threading import Lock, Thread
from uuid import uuid4
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .model import simulate
from .realtime import (
    clear_calculation_logs,
    get_saved_params,
    insert_input,
    insert_calculation_log,
    latest,
    list_calculation_logs,
    mock_status,
    realtime_step,
    reset,
    reset_params_config,
    save_params_config,
    start_mock,
    stop_mock,
)
from .schemas import ParamConfigRequest, RealtimeIngestRequest, RealtimeStepRequest, SimulationRequest


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
        result = simulate(
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
            },
            duration_ms,
        )
    except ValueError as exc:
        duration_ms = (perf_counter() - started) * 1000
        update_job(job_id, status="failed", message=str(exc), error=str(exc), durationMs=duration_ms)
        insert_calculation_log("simulate_job", "failed", str(exc), {"jobId": job_id}, duration_ms)
    except Exception as exc:
        duration_ms = (perf_counter() - started) * 1000
        update_job(job_id, status="failed", message="仿真任务失败。", error=str(exc), durationMs=duration_ms)
        insert_calculation_log("simulate_job", "failed", str(exc), {"jobId": job_id}, duration_ms)


@app.post("/api/simulate")
def simulate_endpoint(request: SimulationRequest) -> dict:
    started = perf_counter()
    try:
        result = simulate(
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
            },
            (perf_counter() - started) * 1000,
        )
        return result
    except ValueError as exc:
        insert_calculation_log(
            "simulate",
            "failed",
            str(exc),
            {"csvFileName": request.csvFileName or "", "hasCsv": bool((request.csvText or "").strip())},
            (perf_counter() - started) * 1000,
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        insert_calculation_log(
            "simulate",
            "failed",
            str(exc),
            {"csvFileName": request.csvFileName or "", "hasCsv": bool((request.csvText or "").strip())},
            (perf_counter() - started) * 1000,
        )
        raise HTTPException(status_code=500, detail="Simulation failed unexpectedly.") from exc


@app.post("/api/simulate/jobs")
def create_simulation_job_endpoint(request: SimulationRequest) -> dict:
    job_id = uuid4().hex
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
def list_logs_endpoint(limit: int = 100) -> dict:
    return list_calculation_logs(limit)


@app.delete("/api/logs")
def clear_logs_endpoint() -> dict:
    return clear_calculation_logs()


@app.get("/api/config/params")
def get_param_config_endpoint() -> dict:
    return get_saved_params()


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
    return insert_input(request.timestamp, request.values, request.quality)


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
        )
        insert_calculation_log(
            "realtime_step",
            "success",
            f"Realtime step completed, result #{result['resultId']}.",
            {"resultId": result["resultId"], "stepHours": request.stepHours},
            (perf_counter() - started) * 1000,
        )
        return result
    except ValueError as exc:
        insert_calculation_log(
            "realtime_step",
            "failed",
            str(exc),
            {"stepHours": request.stepHours},
            (perf_counter() - started) * 1000,
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        insert_calculation_log(
            "realtime_step",
            "failed",
            str(exc),
            {"stepHours": request.stepHours},
            (perf_counter() - started) * 1000,
        )
        raise HTTPException(status_code=500, detail="Realtime step failed unexpectedly.") from exc


@app.get("/api/realtime/latest")
def realtime_latest_endpoint() -> dict:
    return latest()


@app.post("/api/realtime/reset")
def realtime_reset_endpoint() -> dict:
    result = reset()
    insert_calculation_log("realtime_reset", "success", "Realtime state, inputs, and results were reset.")
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
