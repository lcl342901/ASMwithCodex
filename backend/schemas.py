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


class RealtimeForecastRequest(BaseModel):
    projectId: Optional[str] = "default"
    horizonHours: int = 8
    stepHours: float = 1.0
    historyHours: float = 24


class RealtimeMockStartRequest(BaseModel):
    projectId: Optional[str] = "default"
    profile: str = "normal"
    intervalSeconds: int = 300
    warmStart: bool = True


class RealtimeObservationRequest(BaseModel):
    projectId: Optional[str] = "default"
    timestamp: Optional[str] = None
    values: dict[str, Any] = Field(default_factory=dict)
    source: str = "manual"


class RealtimeMockObservationRequest(BaseModel):
    projectId: Optional[str] = "default"
    source: str = "mock-lab"
    noiseFraction: float = 0.03


class StateCorrectionRequest(BaseModel):
    projectId: Optional[str] = "default"
    corrections: dict[str, Any] = Field(default_factory=dict)
    source: str = "manual"
    hours: float = 24
    maxLagHours: float = 2.0


class StateCorrectionClearRequest(BaseModel):
    projectId: Optional[str] = "default"


class CleaningSettingsRequest(BaseModel):
    projectId: Optional[str] = "default"
    enabledRules: list[str] = Field(default_factory=list)


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


class AIAnalysisRequest(BaseModel):
    projectId: Optional[str] = "default"
    model: Optional[str] = None
    result: dict[str, Any] = Field(default_factory=dict)
    params: dict[str, Any] = Field(default_factory=dict)
    context: dict[str, Any] = Field(default_factory=dict)


class AIChatRequest(BaseModel):
    projectId: Optional[str] = "default"
    messages: list[dict[str, str]] = Field(default_factory=list)
    result: dict[str, Any] = Field(default_factory=dict)
    params: dict[str, Any] = Field(default_factory=dict)
    context: dict[str, Any] = Field(default_factory=dict)


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


class HistoricalReplayRequest(BaseModel):
    projectId: Optional[str] = "default"
    name: str = ""
    saveRun: bool = False
    params: dict[str, Any] = Field(default_factory=dict)
    csvText: str = ""
    csvFileName: str = ""
    observations: list[dict[str, Any]] = Field(default_factory=list)
    targets: list[str] = Field(default_factory=list)


class PeriodicCalibrationScheduleRequest(BaseModel):
    name: str = "Weekly calibration check"
    enabled: bool = False
    cadence: str = "weekly"
    dataWindowHours: float = 72
    stageId: str = "nitrification"
    targets: list[str] = Field(default_factory=lambda: ["effNh4"])
    tunableParams: list[str] = Field(default_factory=lambda: ["muA", "kNH"])
    maxIterations: int = 1
    stepFraction: float = 0.05
    maxLagHours: float = 2.0
    useProjectCsv: bool = True
    applyBestParams: bool = False


class PeriodicCalibrationRunRequest(BaseModel):
    observations: list[dict[str, Any]] = Field(default_factory=list)
    csvText: Optional[str] = ""
    csvFileName: Optional[str] = ""
    applyBestParams: Optional[bool] = None
