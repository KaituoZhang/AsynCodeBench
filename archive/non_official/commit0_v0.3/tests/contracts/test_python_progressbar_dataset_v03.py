from __future__ import annotations

import json
from pathlib import Path


TASK_FILE = Path("manifests/pilot/v0.3/tasks/commit0_python_progressbar.json")
SCENARIO_FILE = Path("manifests/pilot/v0.3/scenarios/commit0_python_progressbar.json")
QUALITY_FILE = Path("manifests/pilot/v0.3/quality/commit0_python_progressbar.json")
ANNOTATION_DIR = Path("manifests/annotations/commit0_v0.3/python_progressbar")
CURATED_CONFIG = Path("configs/tasks/commit0_curated_tasks.v0.3.json")


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_python_progressbar_is_saved_as_needs_revision_task() -> None:
    task = _read_json(TASK_FILE)
    quality = _read_json(QUALITY_FILE)

    assert task["task_id"] == "commit0:python-progressbar"
    assert task["upstream_version"] == "afd18fd921caccca5f0c01576434869ddd7c0043"
    assert "origin/commit0_combined" in task["source_materialization"]
    assert task["proposed_parallelizability_label"] == "partially_parallelizable"
    assert quality["quality_status"] == "needs_revision"
    assert set(quality["coordination_structure_tags"]) == {
        "interface_dependency",
        "shared_abstraction",
    }

    snapshots = {
        snapshot["snapshot_id"]: snapshot
        for snapshot in quality["evaluation_snapshots"]
    }
    initial = snapshots["curated_commit0_initial_progressbar_evaluator_collection"]
    assert initial["collected"] == 1
    assert initial["errors"] == 1
    assert initial["return_code"] == 4

    sanity = snapshots["complete_commit0_progressbar_evaluator_sanity"]
    assert sanity["collected"] == 90
    assert sanity["passed"] == 90
    assert sanity["return_code"] == 0
    assert any("bootstrap overlay" in item for item in quality["remaining_gates"])


def test_python_progressbar_curated_config_uses_stripped_ref_without_accepted_overlay() -> None:
    config = _read_json(CURATED_CONFIG)
    task = next(
        item for item in config["tasks"] if item["task_id"] == "commit0:python-progressbar"
    )

    assert task["repository"] == "python-progressbar"
    assert task["base_ref"] == "origin/commit0_combined"
    assert task["base_sha"] == "afd18fd921caccca5f0c01576434869ddd7c0043"
    assert task["overlays"] == []


def test_python_progressbar_scenarios_use_natural_specialists() -> None:
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
        "terminal_agent",
        "core_bar_agent",
        "widget_agent",
        "stream_agent",
    ]


def test_python_progressbar_annotation_requires_bootstrap_review() -> None:
    for name in ("annotator_a.json", "annotator_b.json"):
        form = _read_json(ANNOTATION_DIR / name)

        assert form["include"] is None
        assert form["parallelizability_label"] is None
        assert any("weak_or_unclear" in instruction for instruction in form["independence_instructions"])
        assert any("bootstrap overlay" in instruction for instruction in form["independence_instructions"])
