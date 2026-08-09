from __future__ import annotations

import hashlib
import json
from pathlib import Path


TASK_FILE = Path("manifests/pilot/v0.3/tasks/commit0_flask.json")
SCENARIO_FILE = Path("manifests/pilot/v0.3/scenarios/commit0_flask.json")
QUALITY_FILE = Path("manifests/pilot/v0.3/quality/commit0_flask.json")
ANNOTATION_DIR = Path("manifests/annotations/asyncodebench_v0.3/flask")
CURATED_CONFIG = Path("configs/tasks/commit0_curated_tasks.v0.3.json")


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_flask_is_saved_as_qualification_ready_task() -> None:
    task = _read_json(TASK_FILE)
    quality = _read_json(QUALITY_FILE)

    assert task["task_id"] == "commit0:flask"
    assert task["upstream_version"] == "af126af63a288df1d4edfe07e82a3b241aa4567a"
    assert "origin/commit0_combined" in task["source_materialization"]
    assert task["proposed_parallelizability_label"] == "partially_parallelizable"
    assert quality["quality_status"] == "qualification_ready"
    assert set(quality["coordination_structure_tags"]) == {
        "interface_dependency",
        "shared_abstraction",
        "shared_state",
    }

    snapshots = {snapshot["snapshot_id"]: snapshot for snapshot in quality["evaluation_snapshots"]}
    initial = snapshots["curated_commit0_initial_flask_app_context_evaluator"]
    assert initial["collected"] == 244
    assert initial["passed"] == 1
    assert initial["failed"] == 30
    assert initial["errors"] == 211

    sanity = snapshots["complete_commit0_flask_app_context_evaluator_sanity"]
    assert sanity["collected"] == 244
    assert sanity["passed"] == 242
    assert sanity["skipped"] == 2
    assert sanity["return_code"] == 0


def test_flask_curated_config_uses_stripped_ref_and_bootstrap_overlays() -> None:
    config = _read_json(CURATED_CONFIG)
    task = next(item for item in config["tasks"] if item["task_id"] == "commit0:flask")

    assert task["base_ref"] == "origin/commit0_combined"
    assert task["base_sha"] == "af126af63a288df1d4edfe07e82a3b241aa4567a"
    assert len(task["overlays"]) == 11
    for overlay in task["overlays"]:
        assert hashlib.sha256(Path(overlay["path"]).read_bytes()).hexdigest() == overlay["sha256"]
        assert "Bootstrap-only" in overlay["rationale"]


def test_flask_scenarios_use_natural_specialists() -> None:
    scenarios = _read_json(SCENARIO_FILE)["scenarios"]

    assert {scenario["execution_mode"] for scenario in scenarios} == {
        "iterative_single",
        "serial_specialists",
        "async_private",
        "async_message",
    }
    specialists = next(scenario for scenario in scenarios if scenario["execution_mode"] == "serial_specialists")
    assert [assignment["agent_id"] for assignment in specialists["assignments"]] == [
        "scaffold_agent",
        "dispatch_agent",
        "session_json_agent",
        "template_testing_agent",
    ]


def test_flask_annotation_requires_scope_and_overlay_review() -> None:
    for name in ("annotator_a.json", "annotator_b.json"):
        form = _read_json(ANNOTATION_DIR / name)

        assert form["include"] is None
        assert form["parallelizability_label"] is None
        assert any("bootstrap overlays" in instruction for instruction in form["independence_instructions"])
        assert any("scaffold/app -> dispatch/context" in instruction for instruction in form["independence_instructions"])
        assert any("CLI" in instruction for instruction in form["independence_instructions"])
