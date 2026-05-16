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


class ParamConfigRequest(BaseModel):
    params: dict[str, Any] = Field(default_factory=dict)


class ProjectRequest(BaseModel):
    name: str = ""
    description: str = ""
    ownerId: str = "local"


class ProjectUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class ModelCredibilityRequest(BaseModel):
    result: dict[str, Any] = Field(default_factory=dict)
    params: dict[str, Any] = Field(default_factory=dict)


class ReferenceComparisonRequest(BaseModel):
    result: dict[str, Any] = Field(default_factory=dict)


class InitialConditionRequest(BaseModel):
    params: dict[str, Any] = Field(default_factory=dict)


class CalibrationPreviewRequest(BaseModel):
    params: dict[str, Any] = Field(default_factory=dict)
    observations: list[dict[str, Any]] = Field(default_factory=list)
    tunableParams: list[str] = Field(default_factory=list)
    targets: list[str] = Field(default_factory=list)


class Bsm1MappingRequest(BaseModel):
    params: dict[str, Any] = Field(default_factory=dict)


class CalibrationOptimizeRequest(BaseModel):
    params: dict[str, Any] = Field(default_factory=dict)
    observations: list[dict[str, Any]] = Field(default_factory=list)
    tunableParams: list[str] = Field(default_factory=list)
    targets: list[str] = Field(default_factory=list)
    csvText: Optional[str] = ""
    csvFileName: Optional[str] = ""
    maxIterations: int = 2
    stepFraction: float = 0.1
    useBsm1Mapping: bool = False
    useBsm1Layout: bool = False
