from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class EngineScenario:
    id: str
    axis: str
    params: dict[str, Any] = field(default_factory=dict)
    title: str = ""
    tags: tuple[str, ...] = ("smoke",)
    expected_ranges: dict[str, tuple[float, float]] = field(default_factory=dict)

    @property
    def name(self) -> str:
        return self.id
