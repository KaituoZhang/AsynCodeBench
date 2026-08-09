from __future__ import annotations

import json
from pathlib import Path

from asyncodebench.dataset.models import AdjudicationForm, AnnotationForm


ROOT = Path(__file__).resolve().parents[2]
OFFICIAL_TASKS_FILE = ROOT / "configs/tasks/commit0_official_tasks.v0.3.json"
ANNOTATION_ROOT = ROOT / "manifests/annotations/asyncodebench_v0.3"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_official_annotations_use_asyncodebench_namespace() -> None:
    official_tasks = _read_json(OFFICIAL_TASKS_FILE)["official_tasks"]

    assert len(official_tasks) == 16
    assert not (ANNOTATION_ROOT.parent / "commit0_v0.3").exists()

    for repository in official_tasks:
        annotation_dir = ANNOTATION_ROOT / repository.replace("-", "_")
        expected_task_id = f"asyncodebench:{repository}"
        expected_source_task_id = f"commit0:{repository}"

        for name in (
            "annotator_a.json",
            "annotator_b.json",
            "annotator_codex_audit.json",
        ):
            form = AnnotationForm.model_validate(_read_json(annotation_dir / name))
            assert form.task_id == expected_task_id
            assert form.source_task_id == expected_source_task_id

        adjudication = AdjudicationForm.model_validate(
            _read_json(annotation_dir / "adjudication.template.json")
        )
        assert adjudication.task_id == expected_task_id
        assert adjudication.source_task_id == expected_source_task_id
