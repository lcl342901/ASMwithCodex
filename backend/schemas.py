from typing import Any, Optional

from pydantic import BaseModel, Field


class SimulationRequest(BaseModel):
    params: dict[str, Any] = Field(default_factory=dict)
    csvText: Optional[str] = ""
    csvFileName: Optional[str] = ""
