from __future__ import annotations

import hashlib
import json
from pathlib import Path


TASK_FILE = Path("manifests/pilot/v0.3/tasks/commit0_imapclient.json")
SCENARIO_FILE = Path("manifests/pilot/v0.3/scenarios/commit0_imapclient.json")
QUALITY_FILE = Path("manifests/pilot/v0.3/quality/commit0_imapclient.json")
ANNOTATION_DIR = Path("manifests/annotations/asyncodebench_v0.3/imapclient")
CURATED_CONFIG = Path("configs/tasks/commit0_curated_tasks.v0.3.json")


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_imapclient_is_saved_as_qualification_ready_task() -> None:
    task = _read_json(TASK_FILE)
    quality = _read_json(QUALITY_FILE)

    assert task["task_id"] == "commit0:imapclient"
    assert task["upstream_version"] == "7ca5a23640bcb0b102673eaaf5eaa6e7fcebd76b"
    assert "origin/commit0_combined" in task["source_materialization"]
    assert task["proposed_parallelizability_label"] == "partially_parallelizable"
    assert quality["quality_status"] == "qualification_ready"
    assert set(quality["coordination_structure_tags"]) == {
        "interface_dependency",
        "shared_abstraction",
        "shared_state",
    }

    snapshots = {snapshot["snapshot_id"]: snapshot for snapshot in quality["evaluation_snapshots"]}
    initial = snapshots["curated_commit0_initial_response_client_evaluator"]
    assert initial["collected"] == 229
    assert initial["passed"] == 0
    assert initial["failed"] == 229
    assert initial["errors"] == 0

    sanity = snapshots["complete_commit0_response_client_evaluator_sanity"]
    assert sanity["collected"] == 229
    assert sanity["passed"] == 229
    assert sanity["return_code"] == 0


def test_imapclient_curated_config_uses_stripped_ref_and_overlays() -> None:
    config = _read_json(CURATED_CONFIG)
    task = next(item for item in config["tasks"] if item["task_id"] == "commit0:imapclient")

    assert task["base_ref"] == "origin/commit0_combined"
    assert task["base_sha"] == "7ca5a23640bcb0b102673eaaf5eaa6e7fcebd76b"
    assert [Path(overlay["path"]).name for overlay in task["overlays"]] == [
        "0001-util-import-bootstrap.patch",
        "0002-class-import-bootstrap.patch",
        "0003-iteritems-import-bootstrap.patch",
        "0004-public-helper-import-bootstrap.patch",
        "0005-text-helper-import-bootstrap.patch",
    ]
    for overlay in task["overlays"]:
        assert hashlib.sha256(Path(overlay["path"]).read_bytes()).hexdigest() == overlay["sha256"]


def test_imapclient_scenarios_use_natural_specialists() -> None:
    scenarios = _read_json(SCENARIO_FILE)["scenarios"]

    assert {scenario["execution_mode"] for scenario in scenarios} == {
        "iterative_single",
        "serial_specialists",
        "async_private",
        "async_message",
    }
    specialists = next(scenario for scenario in scenarios if scenario["execution_mode"] == "serial_specialists")
    assert [assignment["agent_id"] for assignment in specialists["assignments"]] == [
        "utility_lexer_agent",
        "parser_agent",
        "client_agent",
    ]


def test_imapclient_annotation_requires_stripped_ref_and_bootstrap_review() -> None:
    for name in ("annotator_a.json", "annotator_b.json"):
        form = _read_json(ANNOTATION_DIR / name)

        if name == "annotator_a.json":
            assert form["include"] is True
            assert form["parallelizability_label"] == "partially_parallelizable"
        else:
            assert form["include"] is None
            assert form["parallelizability_label"] is None
        assert any("origin/commit0_combined" in instruction for instruction in form["independence_instructions"])
        assert any("utility/lexer -> parser -> client" in instruction for instruction in form["independence_instructions"])
        assert any("bootstrap overlays" in instruction for instruction in form["independence_instructions"])
