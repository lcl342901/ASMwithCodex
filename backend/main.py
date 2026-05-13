from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .model import simulate
from .realtime import insert_input, latest, mock_status, realtime_step, reset, start_mock, stop_mock
from .schemas import RealtimeIngestRequest, RealtimeStepRequest, SimulationRequest


app = FastAPI(title="ASMwithCodex Simulation API")

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


@app.post("/api/simulate")
def simulate_endpoint(request: SimulationRequest) -> dict:
    try:
        return simulate(
            params=request.params,
            csv_text=request.csvText or "",
            csv_file_name=request.csvFileName or "",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/realtime/ingest")
def realtime_ingest_endpoint(request: RealtimeIngestRequest) -> dict:
    return insert_input(request.timestamp, request.values, request.quality)


@app.post("/api/realtime/step")
def realtime_step_endpoint(request: RealtimeStepRequest) -> dict:
    try:
        return realtime_step(
            timestamp=request.timestamp,
            values=request.values,
            quality=request.quality,
            params=request.params,
            step_hours=request.stepHours,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/realtime/latest")
def realtime_latest_endpoint() -> dict:
    return latest()


@app.post("/api/realtime/reset")
def realtime_reset_endpoint() -> dict:
    return reset()


@app.post("/api/realtime/mock/start")
async def realtime_mock_start_endpoint() -> dict:
    try:
        return await start_mock()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/realtime/mock/stop")
async def realtime_mock_stop_endpoint() -> dict:
    return await stop_mock()


@app.get("/api/realtime/mock/status")
def realtime_mock_status_endpoint() -> dict:
    return mock_status()


@app.on_event("shutdown")
async def shutdown_event() -> None:
    await stop_mock()
