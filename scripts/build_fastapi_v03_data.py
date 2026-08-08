"""Validate the v0.3 Commit0 FastAPI task records."""

from __future__ import annotations

import json
from pathlib import Path

from asyncodebench.dataset.models import (
    AdjudicationForm,
    AnnotationForm,
    ScenarioRecord,
    TaskQualityRecord,
    TaskRecord,
)


TASK = Path("manifests/pilot/v0.3/tasks/commit0_fastapi.json")
SCENARIOS = Path("manifests/pilot/v0.3/scenarios/commit0_fastapi.json")
QUALITY = Path("manifests/pilot/v0.3/quality/commit0_fastapi.json")
ANNOTATION_DIR = Path("manifests/annotations/commit0_v0.3/fastapi")


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    TaskRecord.model_validate(_read_json(TASK))
    TaskQualityRecord.model_validate(_read_json(QUALITY))
    for scenario in _read_json(SCENARIOS)["scenarios"]:
        ScenarioRecord.model_validate(scenario)
    for name in ("annotator_a.json", "annotator_b.json"):
        AnnotationForm.model_validate(_read_json(ANNOTATION_DIR / name))
    AdjudicationForm.model_validate(_read_json(ANNOTATION_DIR / "adjudication.template.json"))
    print("validated commit0:fastapi v0.3 records")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
