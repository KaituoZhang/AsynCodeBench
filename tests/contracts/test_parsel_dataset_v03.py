from __future__ import annotations

import hashlib
import json
from pathlib import Path


TASK_FILE = Path("manifests/pilot/v0.3/tasks/commit0_parsel.json")
SCENARIO_FILE = Path("manifests/pilot/v0.3/scenarios/commit0_parsel.json")
QUALITY_FILE = Path("manifests/pilot/v0.3/quality/commit0_parsel.json")
ANNOTATION_DIR = Path("manifests/annotations/asyncodebench_v0.3/parsel")
CURATED_CONFIG = Path("configs/tasks/commit0_curated_tasks.v0.3.json")


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_parsel_is_saved_as_qualification_ready_task() -> None:
    task = _read_json(TASK_FILE)
    quality = _read_json(QUALITY_FILE)

    assert task["task_id"] == "commit0:parsel"
    assert task["upstream_version"] == "7e73d60665ef2e3ddfe3c1bb01eed981cd317c6f"
    assert "origin/commit0_combined" in task["source_materialization"]
    assert "bootstrap overlay" in task["source_materialization"]
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
    initial = snapshots["curated_commit0_initial_evaluator"]
    assert initial["collected"] == 208
    assert initial["passed"] == 13
    assert initial["failed"] == 193
    assert initial["errors"] == 0

    sanity = snapshots["complete_commit0_evaluator_sanity"]
    assert sanity["collected"] == 208
    assert sanity["passed"] == 206
    assert sanity["return_code"] == 0


def test_parsel_curated_config_uses_stripped_ref_and_checksum_overlay() -> None:
    config = _read_json(CURATED_CONFIG)
    task = next(
        item for item in config["tasks"] if item["task_id"] == "commit0:parsel"
    )

    assert task["base_ref"] == "origin/commit0_combined"
    assert task["base_sha"] == "7e73d60665ef2e3ddfe3c1bb01eed981cd317c6f"
    assert task["python_dependencies"] == ["psutil==5.6.3"]
    assert [overlay["path"] for overlay in task["overlays"]] == [
        "data/overlays/commit0/parsel/0001-xpathfuncs-setup-bootstrap.patch",
    ]
    overlay = task["overlays"][0]
    assert hashlib.sha256(Path(overlay["path"]).read_bytes()).hexdigest() == (
        overlay["sha256"]
    )


def test_parsel_scenarios_use_natural_specialists() -> None:
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
        "utility_xpath_agent",
        "css_agent",
        "selector_agent",
    ]


def test_parsel_annotation_requires_stripped_ref_review() -> None:
    for name in ("annotator_a.json", "annotator_b.json"):
        form = _read_json(ANNOTATION_DIR / name)

        assert form["include"] is None
        assert form["parallelizability_label"] is None
        assert any(
            "origin/commit0_combined" in instruction
            for instruction in form["independence_instructions"]
        )
        assert any(
            "utility/CSS->selector" in instruction
            for instruction in form["independence_instructions"]
        )
