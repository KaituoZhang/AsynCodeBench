from __future__ import annotations

import hashlib
import json
from pathlib import Path


TASK_FILE = Path("manifests/pilot/v0.3/tasks/commit0_filesystem_spec.json")
SCENARIO_FILE = Path("manifests/pilot/v0.3/scenarios/commit0_filesystem_spec.json")
QUALITY_FILE = Path("manifests/pilot/v0.3/quality/commit0_filesystem_spec.json")
ANNOTATION_DIR = Path("manifests/annotations/asyncodebench_v0.3/filesystem_spec")
CURATED_CONFIG = Path("configs/tasks/commit0_curated_tasks.v0.3.json")


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_filesystem_spec_is_saved_as_qualification_ready_task() -> None:
    task = _read_json(TASK_FILE)
    quality = _read_json(QUALITY_FILE)

    assert task["task_id"] == "commit0:filesystem_spec"
    assert task["upstream_version"] == "0d34761eb6ca0af8a6f33eb83dd9630a4a370da0"
    assert "origin/commit0_combined" in task["source_materialization"]
    assert task["proposed_parallelizability_label"] == "partially_parallelizable"
    assert quality["quality_status"] == "qualification_ready"
    assert set(quality["coordination_structure_tags"]) == {
        "interface_dependency",
        "shared_abstraction",
    }

    snapshots = {
        snapshot["snapshot_id"]: snapshot
        for snapshot in quality["evaluation_snapshots"]
    }
    initial = snapshots["curated_commit0_initial_core_evaluator"]
    assert initial["collected"] == 140
    assert initial["passed"] == 1
    assert initial["failed"] == 128
    assert initial["errors"] == 3

    sanity = snapshots["complete_commit0_core_evaluator_sanity"]
    assert sanity["collected"] == 137
    assert sanity["passed"] == 129
    assert sanity["return_code"] == 0


def test_filesystem_spec_curated_config_uses_stripped_ref_and_overlays() -> None:
    config = _read_json(CURATED_CONFIG)
    task = next(
        item
        for item in config["tasks"]
        if item["task_id"] == "commit0:filesystem_spec"
    )

    assert task["base_ref"] == "origin/commit0_combined"
    assert task["base_sha"] == "0d34761c18d98009d76a1c19246606026c0e44a0"
    assert [overlay["path"] for overlay in task["overlays"]] == [
        "data/overlays/commit0/filesystem_spec/0001-version-bootstrap.patch",
        "data/overlays/commit0/filesystem_spec/0002-utils-import-bootstrap.patch",
        "data/overlays/commit0/filesystem_spec/0003-compression-import-bootstrap.patch",
        "data/overlays/commit0/filesystem_spec/0004-core-import-bootstrap.patch",
    ]
    for overlay in task["overlays"]:
        assert hashlib.sha256(Path(overlay["path"]).read_bytes()).hexdigest() == (
            overlay["sha256"]
        )


def test_filesystem_spec_scenarios_use_natural_specialists() -> None:
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
        "registry_agent",
        "utility_agent",
        "core_agent",
    ]


def test_filesystem_spec_annotation_requires_stripped_ref_review() -> None:
    for name in ("annotator_a.json", "annotator_b.json"):
        form = _read_json(ANNOTATION_DIR / name)

        if name == "annotator_a.json":
            assert form["include"] is True
            assert form["parallelizability_label"] == "partially_parallelizable"
        else:
            assert form["include"] is None
            assert form["parallelizability_label"] is None
        assert any(
            "origin/commit0_combined" in instruction
            for instruction in form["independence_instructions"]
        )
        assert any(
            "registry/utility->core" in instruction
            for instruction in form["independence_instructions"]
        )
