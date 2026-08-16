from __future__ import annotations

import hashlib
import json
from pathlib import Path


TASK_FILE = Path("manifests/pilot/v0.3/tasks/commit0_pexpect.json")
SCENARIO_FILE = Path("manifests/pilot/v0.3/scenarios/commit0_pexpect.json")
QUALITY_FILE = Path("manifests/pilot/v0.3/quality/commit0_pexpect.json")
ANNOTATION_DIR = Path("manifests/annotations/asyncodebench_v0.3/pexpect")
CURATED_CONFIG = Path("configs/tasks/commit0_curated_tasks.v0.3.json")


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_pexpect_is_saved_as_qualification_ready_task() -> None:
    task = _read_json(TASK_FILE)
    quality = _read_json(QUALITY_FILE)

    assert task["task_id"] == "commit0:pexpect"
    assert task["upstream_version"] == "21b5908ea5b9b38ca996fec50dc449bff5c2c82f"
    assert "origin/commit0_combined" in task["source_materialization"]
    assert task["proposed_parallelizability_label"] == "partially_parallelizable"
    assert quality["quality_status"] == "qualification_ready"
    assert set(quality["coordination_structure_tags"]) == {
        "interface_dependency",
        "shared_abstraction",
        "shared_state",
    }

    snapshots = {snapshot["snapshot_id"]: snapshot for snapshot in quality["evaluation_snapshots"]}
    initial = snapshots["curated_commit0_initial_expect_transport_evaluator"]
    assert initial["collected"] == 77
    assert initial["passed"] == 14
    assert initial["failed"] == 63
    assert initial["errors"] == 0

    sanity = snapshots["complete_commit0_expect_transport_evaluator_sanity"]
    assert sanity["collected"] == 77
    assert sanity["passed"] == 77
    assert sanity["return_code"] == 0


def test_pexpect_curated_config_uses_stripped_ref_and_overlay() -> None:
    config = _read_json(CURATED_CONFIG)
    task = next(item for item in config["tasks"] if item["task_id"] == "commit0:pexpect")

    assert task["base_ref"] == "origin/commit0_combined"
    assert task["base_sha"] == "21b5908ea5b9b38ca996fec50dc449bff5c2c82f"
    assert [Path(overlay["path"]).name for overlay in task["overlays"]] == [
        "0001-spawnbase-buffer-property-bootstrap.patch",
    ]
    for overlay in task["overlays"]:
        assert hashlib.sha256(Path(overlay["path"]).read_bytes()).hexdigest() == overlay["sha256"]


def test_pexpect_scenarios_use_natural_specialists() -> None:
    scenarios = _read_json(SCENARIO_FILE)["scenarios"]

    assert {scenario["execution_mode"] for scenario in scenarios} == {
        "iterative_single",
        "serial_specialists",
        "async_private",
        "async_message",
    }
    specialists = next(scenario for scenario in scenarios if scenario["execution_mode"] == "serial_specialists")
    assert [assignment["agent_id"] for assignment in specialists["assignments"]] == [
        "expect_agent",
        "spawn_agent",
        "transport_agent",
        "wrapper_agent",
    ]


def test_pexpect_annotation_requires_scope_and_environment_review() -> None:
    for name in ("annotator_a.json", "annotator_b.json"):
        form = _read_json(ANNOTATION_DIR / name)

        if name == "annotator_a.json":
            assert form["include"] is True
            assert form["parallelizability_label"] == "partially_parallelizable"
        else:
            assert form["include"] is None
            assert form["parallelizability_label"] is None
        assert any("POSIX/ptyprocess" in instruction for instruction in form["independence_instructions"])
        assert any("expect/search -> SpawnBase -> transport/wrapper" in instruction for instruction in form["independence_instructions"])
        assert any("pxssh" in instruction for instruction in form["independence_instructions"])
