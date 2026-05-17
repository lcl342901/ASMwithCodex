from typing import Any, Optional

from pydantic import BaseModel, Field


class SimulationRequest(BaseModel):
    projectId: Optional[str] = "default"
    params: dict[str, Any] = Field(default_factory=dict)
    csvText: Optional[str] = ""
    csvFileName: Optional[str] = ""
    useLastFinalState: bool = True
    saveFinalState: bool = True


class RealtimeIngestRequest(BaseModel):
    projectId: Optional[str] = "default"
    timestamp: Optional[str] = None
    values: dict[str, Any] = Field(default_factory=dict)
    quality: dict[str, Any] = Field(default_factory=dict)


class RealtimeStepRequest(BaseModel):
    projectId: Optional[str] = "default"
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


class ProjectCsvRequest(BaseModel):
    csvText: str = ""
    csvFileName: str = ""


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


class Bsm1CalibrationReportRequest(BaseModel):
    params: dict[str, Any] = Field(default_factory=dict)
    useBsm1Layout: bool = True
    maxIterations: int = 1
    stepFraction: float = 0.1


class CalibrationOptimizeRequest(BaseModel):
    projectId: Optional[str] = "default"
    name: str = ""
    saveRun: bool = False
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


class CalibrationStageRunRequest(BaseModel):
    projectId: Optional[str] = "default"
    name: str = ""
    saveRun: bool = False
    stageId: str
    params: dict[str, Any] = Field(default_factory=dict)
    observations: list[dict[str, Any]] = Field(default_factory=list)
    csvText: Optional[str] = ""
    csvFileName: Optional[str] = ""
    maxIterations: int = 1
    stepFraction: float = 0.1
    useBsm1Mapping: bool = False
    useBsm1Layout: bool = False
