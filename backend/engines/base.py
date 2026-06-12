from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class EngineMetadata:
    id: str
    model_id: str
    model_family: str
    component_count: int
    status: str
    result_contract: str
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class EngineRunOptions:
    params: dict[str, Any] | None = None
    csv_text: str = ""
    csv_file_name: str = ""
    progress_callback: Callable[[float, float], None] | None = None
    partial_result_callback: Callable[[dict[str, Any]], None] | None = None
    initial_state: dict[str, Any] | None = None


class CalculationEngine:
    metadata: EngineMetadata

    def run(self, options: EngineRunOptions) -> dict[str, Any]:
        raise NotImplementedError
