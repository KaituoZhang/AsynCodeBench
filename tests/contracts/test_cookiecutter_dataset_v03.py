from __future__ import annotations

import json
from pathlib import Path


TASK_FILE = Path("manifests/pilot/v0.3/tasks/commit0_cookiecutter.json")
SCENARIO_FILE = Path("manifests/pilot/v0.3/scenarios/commit0_cookiecutter.json")
QUALITY_FILE = Path("manifests/pilot/v0.3/quality/commit0_cookiecutter.json")
ANNOTATION_DIR = Path("manifests/annotations/asyncodebench_v0.3/cookiecutter")
CURATED_CONFIG = Path("configs/tasks/commit0_curated_tasks.v0.3.json")


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_cookiecutter_is_saved_as_qualification_ready_task() -> None:
    task = _read_json(TASK_FILE)
    quality = _read_json(QUALITY_FILE)

    assert task["task_id"] == "commit0:cookiecutter"
    assert task["upstream_version"] == "c7a8c70a666270053d848f5664413af1af7a987f"
    assert "origin/commit0_combined" in task["source_materialization"]
    assert task["proposed_parallelizability_label"] == "partially_parallelizable"
    assert quality["quality_status"] == "qualification_ready"
    assert set(quality["coordination_structure_tags"]) == {
        "interface_dependency",
        "shared_abstraction",
        "control",
    }

    snapshots = {
        snapshot["snapshot_id"]: snapshot
        for snapshot in quality["evaluation_snapshots"]
    }
    initial = snapshots["curated_commit0_initial_cookiecutter_workflow_evaluator"]
    assert initial["collected"] == 202
    assert initial["passed"] == 6
    assert initial["failed"] == 169
    assert initial["errors"] == 23
    assert initial["skipped"] == 4
    assert initial["return_code"] == 1

    sanity = snapshots["complete_commit0_cookiecutter_workflow_evaluator_sanity"]
    assert sanity["collected"] == 216
    assert sanity["passed"] == 212
    assert sanity["skipped"] == 4
    assert sanity["return_code"] == 0
    assert any("weak_or_unclear" in item for item in quality["remaining_gates"])


def test_cookiecutter_curated_config_uses_stripped_ref_without_overlay() -> None:
    config = _read_json(CURATED_CONFIG)
    task = next(
        item for item in config["tasks"] if item["task_id"] == "commit0:cookiecutter"
    )

    assert task["repository"] == "cookiecutter"
    assert task["base_ref"] == "origin/commit0_combined"
    assert task["base_sha"] == "c7a8c70a666270053d848f5664413af1af7a987f"
    assert task["overlays"] == []


def test_cookiecutter_scenarios_use_natural_specialists() -> None:
    scenarios = _read_json(SCENARIO_FILE)["scenarios"]

    assert {scenario["execution_mode"] for scenario in scenarios} == {
        "iterative_single",
        "serial_specialists",
        "async_private",
        "async_message",
    }
    specialists = next(
        scenario
        for scenario in scenarios
        if scenario["execution_mode"] == "serial_specialists"
    )
    assert [assignment["agent_id"] for assignment in specialists["assignments"]] == [
        "config_prompt_agent",
        "source_agent",
        "generation_agent",
        "orchestration_agent",
    ]


def test_cookiecutter_annotation_requires_scope_review() -> None:
    for name in ("annotator_a.json", "annotator_b.json"):
        form = _read_json(ANNOTATION_DIR / name)

        if name == "annotator_a.json":
            assert form["include"] is True
            assert form["parallelizability_label"] == "partially_parallelizable"
        else:
            assert form["include"] is None
            assert form["parallelizability_label"] is None
        assert any("weak_or_unclear" in instruction for instruction in form["independence_instructions"])
        assert any("Click-version-sensitive" in instruction for instruction in form["independence_instructions"])
