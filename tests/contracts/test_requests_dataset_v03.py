from __future__ import annotations

import json
from pathlib import Path


TASK_FILE = Path("manifests/pilot/v0.3/tasks/commit0_requests.json")
SCENARIO_FILE = Path("manifests/pilot/v0.3/scenarios/commit0_requests.json")
QUALITY_FILE = Path("manifests/pilot/v0.3/quality/commit0_requests.json")
ANNOTATION_DIR = Path("manifests/annotations/commit0_v0.3/requests")
CURATED_CONFIG = Path("configs/tasks/commit0_curated_tasks.v0.3.json")


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_requests_is_saved_as_qualification_ready_task() -> None:
    task = _read_json(TASK_FILE)
    quality = _read_json(QUALITY_FILE)

    assert task["task_id"] == "commit0:requests"
    assert task["upstream_version"] == "0e5a01d0ed71fd20b6a72cafe92b9a917ce93d7b"
    assert "origin/commit0_combined" in task["source_materialization"]
    assert "bootstrap overlays" in task["source_materialization"]
    assert task["proposed_parallelizability_label"] == "partially_parallelizable"
    assert quality["quality_status"] == "qualification_ready"
    assert set(quality["coordination_structure_tags"]) == {
        "interface_dependency",
        "shared_abstraction",
    }
    assert quality["remaining_gates"] == [
        "two independent human inclusion/exclusion annotations",
    ]

    snapshots = {
        snapshot["snapshot_id"]: snapshot
        for snapshot in quality["evaluation_snapshots"]
    }
    initial = snapshots["curated_commit0_initial_local_core"]
    assert initial["collected"] == 243
    assert initial["passed"] == 55
    assert initial["failed"] == 175
    assert initial["errors"] == 0

    sanity = snapshots["complete_commit0_local_core_sanity"]
    assert sanity["collected"] == 243
    assert sanity["passed"] == 230
    assert sanity["return_code"] == 0


def test_requests_curated_config_uses_stripped_ref_and_bootstrap_overlays() -> None:
    config = _read_json(CURATED_CONFIG)
    task = next(
        item for item in config["tasks"] if item["task_id"] == "commit0:requests"
    )

    assert task["base_ref"] == "origin/commit0_combined"
    assert task["base_sha"] == "0e5a01d0ed71fd20b6a72cafe92b9a917ce93d7b"
    assert [overlay["path"] for overlay in task["overlays"]] == [
        "data/overlays/commit0/requests/0001-syntax-bootstrap.patch",
        "data/overlays/commit0/requests/0002-status-codes-bootstrap.patch",
        "data/overlays/commit0/requests/0003-utils-import-bootstrap.patch",
    ]


def test_requests_scenarios_use_natural_specialists() -> None:
    payload = _read_json(SCENARIO_FILE)
    scenarios = payload["scenarios"]

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
        "prep_agent",
        "transport_agent",
        "integration_agent",
    ]


def test_requests_annotation_requires_stripped_ref_review() -> None:
    for name in ("annotator_a.json", "annotator_b.json"):
        form = _read_json(ANNOTATION_DIR / name)

        assert form["include"] is None
        assert form["parallelizability_label"] is None
        assert any(
            "origin/commit0_combined" in instruction
            for instruction in form["independence_instructions"]
        )
        assert any(
            "preparation->transport" in instruction
            for instruction in form["independence_instructions"]
        )
