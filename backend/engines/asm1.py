from __future__ import annotations

from .base import CalculationEngine, EngineMetadata, EngineRunOptions
from ..model import simulate


class ASM1Engine(CalculationEngine):
    metadata = EngineMetadata(
        id="v1",
        model_id="ASM1",
        model_family="ASM",
        component_count=13,
        status="current",
        result_contract="frontend_series_v1",
        notes=(
            "Three-zone AAO reactor layout with anaerobic, anoxic, and aerobic CSTRs.",
            "Uses the existing ASM1 reaction implementation and Takacs-style clarifier.",
        ),
    )

    def run(self, options: EngineRunOptions) -> dict[str, object]:
        result = simulate(
            params={**(options.params or {}), "engineVersion": "v1"},
            csv_text=options.csv_text,
            csv_file_name=options.csv_file_name,
            progress_callback=options.progress_callback,
            partial_result_callback=options.partial_result_callback,
            initial_state=options.initial_state,
        )
        result["engineVersion"] = self.metadata.id
        result["modelId"] = self.metadata.model_id
        result["engineMetadata"] = {
            "id": self.metadata.id,
            "modelId": self.metadata.model_id,
            "modelFamily": self.metadata.model_family,
            "componentCount": self.metadata.component_count,
            "status": self.metadata.status,
            "resultContract": self.metadata.result_contract,
            "notes": list(self.metadata.notes),
        }
        return result
