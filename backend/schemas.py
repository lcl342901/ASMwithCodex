from typing import Any, Optional

from pydantic import BaseModel, Field


class SimulationRequest(BaseModel):
    params: dict[str, Any] = Field(default_factory=dict)
    csvText: Optional[str] = ""
    csvFileName: Optional[str] = ""


class RealtimeIngestRequest(BaseModel):
    timestamp: Optional[str] = None
    values: dict[str, Any] = Field(default_factory=dict)
    quality: dict[str, Any] = Field(default_factory=dict)


class RealtimeStepRequest(BaseModel):
    timestamp: Optional[str] = None
    values: Optional[dict[str, Any]] = None
    quality: dict[str, Any] = Field(default_factory=dict)
    params: dict[str, Any] = Field(default_factory=dict)
    stepHours: Optional[float] = None
