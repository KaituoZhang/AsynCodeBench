import json
from pathlib import Path

from asyncodebench.dataset.tinydb_v03 import (
    build_quality_record,
    build_scenarios,
    build_task_record,
    write_json,
)


def test_tinydb_candidate_assets_are_serializable(tmp_path: Path) -> None:
    candidate_file = Path(
        "manifests/candidates/commit0_public_candidates_v0.2.json"
    )
    task_path = tmp_path / "tasks" / "tinydb.json"
    quality_path = tmp_path / "quality" / "tinydb.json"
    scenario_path = tmp_path / "scenarios" / "tinydb.json"

    task = build_task_record(candidate_file)
    write_json(task, task_path)
    write_json(build_quality_record(), quality_path)
    scenario_path.parent.mkdir(parents=True)
    scenario_path.write_text(
        json.dumps(
            {
                "schema_version": "0.3",
                "task_id": task.task_id,
                "scenarios": [
                    scenario.model_dump(mode="json")
                    for scenario in build_scenarios()
                ],
            }
        ),
        encoding="utf-8",
    )

    assert json.loads(task_path.read_text())["task_id"] == "commit0:tinydb"
    assert json.loads(quality_path.read_text())["quality_status"] == (
        "qualification_ready"
    )
    assert len(json.loads(scenario_path.read_text())["scenarios"]) == 4
