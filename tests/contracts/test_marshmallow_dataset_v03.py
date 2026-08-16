from __future__ import annotations

import hashlib
import json
from pathlib import Path


TASK_FILE = Path("manifests/pilot/v0.3/tasks/commit0_marshmallow.json")
SCENARIO_FILE = Path("manifests/pilot/v0.3/scenarios/commit0_marshmallow.json")
QUALITY_FILE = Path("manifests/pilot/v0.3/quality/commit0_marshmallow.json")
METRICS_FILE = Path("manifests/pilot/v0.3/metrics/commit0_marshmallow_async_metrics.json")
ANNOTATION_DIR = Path("manifests/annotations/asyncodebench_v0.3/marshmallow")
CURATED_CONFIG = Path("configs/tasks/commit0_curated_tasks.v0.3.json")


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_marshmallow_is_saved_as_qualification_ready_task() -> None:
    task = _read_json(TASK_FILE)
    quality = _read_json(QUALITY_FILE)

    assert task["task_id"] == "commit0:marshmallow"
    assert task["upstream_version"] == "bd290d2b49f5030a2369aedc5538cffa4815982d"
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
    initial = snapshots["curated_commit0_initial_evaluator"]
    assert initial["collected"] == 1228
    assert initial["passed"] == 148
    assert initial["failed"] == 1080
    assert initial["errors"] == 0

    sanity = snapshots["complete_commit0_evaluator_sanity"]
    assert sanity["collected"] == 1230
    assert sanity["passed"] == 1230
    assert sanity["return_code"] == 0


def test_marshmallow_curated_config_uses_stripped_ref_and_overlays() -> None:
    config = _read_json(CURATED_CONFIG)
    task = next(
        item for item in config["tasks"] if item["task_id"] == "commit0:marshmallow"
    )

    assert task["base_ref"] == "origin/commit0_combined"
    assert task["base_sha"] == "bd290d2b49f5030a2369aedc5538cffa4815982d"
    assert [overlay["path"] for overlay in task["overlays"]] == [
        "data/overlays/commit0/marshmallow/0001-utils-import-bootstrap.patch",
        "data/overlays/commit0/marshmallow/0002-schema-import-bootstrap.patch",
        "data/overlays/commit0/marshmallow/0003-utils-collection-bootstrap.patch",
        "data/overlays/commit0/marshmallow/0004-decorators-import-bootstrap.patch",
    ]
    for overlay in task["overlays"]:
        assert hashlib.sha256(Path(overlay["path"]).read_bytes()).hexdigest() == (
            overlay["sha256"]
        )


def test_marshmallow_scenarios_use_natural_specialists() -> None:
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
        "field_agent",
        "schema_agent",
    ]


def test_marshmallow_dependency_probes_are_collectable_tests() -> None:
    metrics = _read_json(METRICS_FILE)
    quality = _read_json(QUALITY_FILE)
    dead_selector = (
        "tests/test_schema.py::MySchema::"
        "test_custom_error_handler_with_validates_schema_decorator"
    )
    replacement = "tests/test_decorators.py::test_decorator_error_handling"

    serialized_metrics = json.dumps(metrics)
    serialized_quality = json.dumps(quality)
    assert metrics["metric_annotation_id"] == "commit0-marshmallow.async-metrics.v0.3.1"
    assert dead_selector not in serialized_metrics
    assert dead_selector not in serialized_quality
    assert replacement in serialized_metrics
    assert replacement in serialized_quality


def test_marshmallow_annotation_requires_stripped_ref_review() -> None:
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
            "registry/field/decorator->schema" in instruction
            for instruction in form["independence_instructions"]
        )
