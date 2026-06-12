from __future__ import annotations

from .asm1 import ASM1Engine
from .base import CalculationEngine, EngineMetadata


_ENGINES: dict[str, CalculationEngine] = {
    "v1": ASM1Engine(),
}

_ALIASES = {
    "": "v1",
    "1": "v1",
    "asm1": "v1",
    "asm1_v1": "v1",
    "v1": "v1",
}


def normalize_registered_engine_id(value: object = "v1") -> str:
    normalized = str(value or "v1").strip().lower()
    return _ALIASES.get(normalized, normalized)


def get_engine(engine_id: object = "v1") -> CalculationEngine:
    normalized = normalize_registered_engine_id(engine_id)
    try:
        return _ENGINES[normalized]
    except KeyError as exc:
        known = ", ".join(sorted(_ENGINES))
        raise ValueError(f"unknown calculation engine {normalized!r}; registered engines: {known}") from exc


def list_engines() -> list[EngineMetadata]:
    return [engine.metadata for engine in _ENGINES.values()]
