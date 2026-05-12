from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .model import simulate
from .schemas import SimulationRequest


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
