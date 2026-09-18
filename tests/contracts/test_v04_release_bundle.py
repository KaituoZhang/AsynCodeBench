from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
INDEX = ROOT / "manifests/release/v0.4/task_index.json"
OFFICIAL = ROOT / "manifests/release/v0.4/official_tasks.json"
BUILDER = ROOT / "scripts/build_v04_release_index.py"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_v04_release_index_is_current() -> None:
    completed = subprocess.run(
        [sys.executable, str(BUILDER), "--check"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_v04_unifies_twenty_qualified_tasks() -> None:
    index = load(INDEX)
    official = load(OFFICIAL)
    assert index["release"] == official["release"] == "v0.4"
    assert index["task_count"] == official["task_count"] == 20
    assert index["scenario_count"] == 80
    assert index["dependency_point_count"] == 56
    assert index["human_review_passed_task_count"] == 20
    assert index["automated_audit_complete_task_count"] == 20
    assert index["community_preview_ready"] is True
    assert index["stable_release_ready"] is False
    assert index["validated_baseline_bundle_count"] == 0
    assert len(index["tasks"]) == len(official["official_task_ids"]) == 20
    assert len({task["task_id"] for task in index["tasks"]}) == 20
    assert all(task["official_result_eligible"] for task in index["tasks"])
    assert all(
        task["annotation_status"]["human_review_passed"]
        for task in index["tasks"]
    )
    assert {
        "asyncodebench:apache-tvm-20018",
        "asyncodebench:apache-tvm-20073",
        "asyncodebench:apache-tvm-20107",
        "asyncodebench:apache-tvm-20153",
    }.issubset(official["official_task_ids"])


def test_v04_release_artifact_hashes_are_current() -> None:
    index = load(INDEX)
    for task in index["tasks"]:
        for artifact in task["artifacts"].values():
            path = ROOT / artifact["path"]
            assert path.is_file()
            assert hashlib.sha256(path.read_bytes()).hexdigest() == artifact["sha256"]
    baseline = index["validated_baseline_registry"]
    baseline_path = ROOT / baseline["path"]
    assert hashlib.sha256(baseline_path.read_bytes()).hexdigest() == baseline["sha256"]
