"""Export v0.3 dataset JSON schemas."""

from __future__ import annotations

import json
from pathlib import Path

from asynccodebench.dataset.models import (
    AdjudicationForm,
    AnnotationForm,
    ScenarioRecord,
    TaskQualityRecord,
    TaskRecord,
)

DATASET_CONTRACTS = {
    "adjudication_form": AdjudicationForm,
    "annotation_form": AnnotationForm,
    "scenario_record": ScenarioRecord,
    "task_quality_record": TaskQualityRecord,
    "task_record": TaskRecord,
}


def export_dataset_schemas(output_directory: Path | str) -> tuple[Path, ...]:
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name, model in sorted(DATASET_CONTRACTS.items()):
        destination = output / f"{name}.schema.json"
        destination.write_text(
            json.dumps(model.model_json_schema(), indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
        written.append(destination)
    return tuple(written)
