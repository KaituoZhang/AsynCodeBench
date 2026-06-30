from __future__ import annotations

import json
from pathlib import Path

from asynccodebench.dataset.cachetools_v03 import (
    build_annotation_forms,
    build_quality_record,
    build_scenarios,
    build_task_record,
    write_json,
)
from asynccodebench.dataset.export import export_dataset_schemas


def test_cachetools_v03_assets_are_serializable(tmp_path: Path) -> None:
    candidate_file = Path(
        "manifests/candidates/commit0_public_candidates_v0.2.json"
    )
    task_path = tmp_path / "tasks" / "cachetools.json"
    task = build_task_record(candidate_file)
    write_json(task, task_path)
    quality_path = tmp_path / "quality" / "cachetools.json"
    write_json(build_quality_record(), quality_path)

    scenarios_path = tmp_path / "scenarios" / "cachetools.json"
    scenarios_path.parent.mkdir(parents=True)
    scenarios_path.write_text(
        json.dumps(
            {
                "schema_version": "0.3",
                "task_id": task.task_id,
                "scenarios": [
                    scenario.model_dump(mode="json")
                    for scenario in build_scenarios()
                ],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    forms = build_annotation_forms(
        candidate_file=candidate_file,
        task_record_file=task_path,
    )
    for form in forms:
        write_json(form, tmp_path / "annotations" / f"{form.annotator_id}.json")

    schemas = export_dataset_schemas(tmp_path / "schemas")

    assert json.loads(task_path.read_text())["task_id"] == "commit0:cachetools"
    quality_data = json.loads(quality_path.read_text())
    assert quality_data["quality_status"] == "qualification_ready"
    assert len(quality_data["test_groups"]) == 5
    scenario_data = json.loads(scenarios_path.read_text())
    assert len(scenario_data["scenarios"]) == 4
    assert len(schemas) == 5
