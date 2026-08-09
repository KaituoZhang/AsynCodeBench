from __future__ import annotations

import hashlib
import json
from pathlib import Path


TASK_FILE = Path("manifests/pilot/v0.3/tasks/commit0_fastapi.json")
SCENARIO_FILE = Path("manifests/pilot/v0.3/scenarios/commit0_fastapi.json")
QUALITY_FILE = Path("manifests/pilot/v0.3/quality/commit0_fastapi.json")
ANNOTATION_DIR = Path("archive/non_official/commit0_v0.3/manifests/annotations/commit0_v0.3/fastapi")
CURATED_CONFIG = Path("configs/tasks/commit0_curated_tasks.v0.3.json")


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_fastapi_is_saved_as_needs_revision_task() -> None:
    task = _read_json(TASK_FILE)
    quality = _read_json(QUALITY_FILE)

    assert task["task_id"] == "commit0:fastapi"
    assert task["upstream_version"] == "0ee9d513da2f664b076c13a5f0969ecd1bfd25dd"
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
    initial = snapshots[
        "curated_commit0_initial_fastapi_encoder_evaluator_collection"
    ]
    assert initial["collected"] == 1
    assert initial["errors"] == 1
    assert initial["return_code"] == 2

    sanity = snapshots["complete_commit0_fastapi_encoder_evaluator_sanity"]
    assert sanity["collected"] == 21
    assert sanity["passed"] == 18
    assert sanity["skipped"] == 3
    assert sanity["return_code"] == 0
    assert any("bootstrap overlay" in item for item in quality["remaining_gates"])
    assert any("collect the scoped public evaluator" in item for item in quality["remaining_gates"])


def test_fastapi_curated_config_uses_stripped_ref_and_bootstrap_overlay() -> None:
    config = _read_json(CURATED_CONFIG)
    task = next(
        item for item in config["tasks"] if item["task_id"] == "commit0:fastapi"
    )

    assert task["base_ref"] == "origin/commit0_combined"
    assert task["base_sha"] == "0ee9d513da2f664b076c13a5f0969ecd1bfd25dd"
    assert len(task["overlays"]) == 1
    overlay = task["overlays"][0]
    assert Path(overlay["path"]).exists()
    assert hashlib.sha256(Path(overlay["path"]).read_bytes()).hexdigest() == overlay["sha256"]
    assert "import" in overlay["rationale"]


def test_fastapi_scenarios_use_natural_specialists() -> None:
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
        "parameter_agent",
        "dependency_agent",
        "routing_agent",
        "serialization_agent",
    ]


def test_fastapi_annotation_requires_scope_and_bootstrap_review() -> None:
    for name in ("annotator_a.json", "annotator_b.json"):
        form = _read_json(ANNOTATION_DIR / name)

        assert form["include"] is None
        assert form["parallelizability_label"] is None
        assert any("bootstrap overlay" in instruction for instruction in form["independence_instructions"])
        assert any("weak_or_unclear" in instruction for instruction in form["independence_instructions"])
