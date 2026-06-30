from __future__ import annotations

import hashlib
import json
from pathlib import Path


TASK_FILE = Path("manifests/pilot/v0.3/tasks/commit0_graphene.json")
SCENARIO_FILE = Path("manifests/pilot/v0.3/scenarios/commit0_graphene.json")
QUALITY_FILE = Path("manifests/pilot/v0.3/quality/commit0_graphene.json")
ANNOTATION_DIR = Path("manifests/annotations/commit0_v0.3/graphene")
CURATED_CONFIG = Path("configs/tasks/commit0_curated_tasks.v0.3.json")


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_graphene_is_saved_as_qualification_ready_task() -> None:
    task = _read_json(TASK_FILE)
    quality = _read_json(QUALITY_FILE)

    assert task["task_id"] == "commit0:graphene"
    assert task["upstream_version"] == "ec2d3f476a7fa94a7a2ffc3c145422b0c3b7e71a"
    assert "origin/commit0_combined" in task["source_materialization"]
    assert task["proposed_parallelizability_label"] == "partially_parallelizable"
    assert quality["quality_status"] == "qualification_ready"
    assert set(quality["coordination_structure_tags"]) == {
        "interface_dependency",
        "shared_abstraction",
        "shared_state",
    }

    snapshots = {
        snapshot["snapshot_id"]: snapshot
        for snapshot in quality["evaluation_snapshots"]
    }
    initial = snapshots["curated_commit0_initial_type_schema_evaluator"]
    assert initial["collected"] == 59
    assert initial["passed"] == 10
    assert initial["failed"] == 48
    assert initial["errors"] == 0
    assert initial["deselected"] == 1

    sanity = snapshots["complete_commit0_type_schema_evaluator_sanity"]
    assert sanity["collected"] == 59
    assert sanity["passed"] == 58
    assert sanity["failed"] == 0
    assert sanity["return_code"] == 0


def test_graphene_curated_config_uses_stripped_ref_and_overlays() -> None:
    config = _read_json(CURATED_CONFIG)
    task = next(
        item for item in config["tasks"] if item["task_id"] == "commit0:graphene"
    )

    assert task["base_ref"] == "origin/commit0_combined"
    assert task["base_sha"] == "ec2d3f476a7fa94a7a2ffc3c145422b0c3b7e71a"
    assert [overlay["path"] for overlay in task["overlays"]] == [
        "data/overlays/commit0/graphene/0001-types-utils-import-bootstrap.patch",
        "data/overlays/commit0/graphene/0002-subclass-meta-syntax-bootstrap.patch",
        "data/overlays/commit0/graphene/0003-props-import-bootstrap.patch",
        "data/overlays/commit0/graphene/0004-utils-import-bootstrap.patch",
        "data/overlays/commit0/graphene/0005-scalars-class-bootstrap.patch",
        "data/overlays/commit0/graphene/0006-base-options-bootstrap.patch",
        "data/overlays/commit0/graphene/0007-enum-class-bootstrap.patch",
        "data/overlays/commit0/graphene/0008-argument-field-import-bootstrap.patch",
        "data/overlays/commit0/graphene/0009-resolver-import-bootstrap.patch",
        "data/overlays/commit0/graphene/0010-relay-mutation-import-bootstrap.patch",
        "data/overlays/commit0/graphene/0011-resolve-only-args-import-bootstrap.patch",
    ]
    for overlay in task["overlays"]:
        assert hashlib.sha256(Path(overlay["path"]).read_bytes()).hexdigest() == (
            overlay["sha256"]
        )


def test_graphene_scenarios_use_natural_specialists() -> None:
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
        "mounting_agent",
        "metadata_agent",
        "schema_agent",
    ]


def test_graphene_annotation_requires_stripped_ref_and_bootstrap_review() -> None:
    for name in ("annotator_a.json", "annotator_b.json"):
        form = _read_json(ANNOTATION_DIR / name)

        assert form["include"] is None
        assert form["parallelizability_label"] is None
        assert any(
            "origin/commit0_combined" in instruction
            for instruction in form["independence_instructions"]
        )
        assert any(
            "mounting/object-input/schema" in instruction
            for instruction in form["independence_instructions"]
        )
        assert any(
            "props bootstrap" in instruction
            for instruction in form["independence_instructions"]
        )
