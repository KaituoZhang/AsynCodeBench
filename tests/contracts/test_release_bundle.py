import hashlib
import json
import subprocess
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
RELEASE_DIR = ROOT / "manifests" / "release" / "v0.3"


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_release_index_is_current():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "build_release_index.py"), "--check"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_release_contains_only_the_16_official_tasks():
    official = read_json(RELEASE_DIR / "official_tasks.json")
    index = read_json(RELEASE_DIR / "task_index.json")
    assert official["task_count"] == 16
    assert index["task_count"] == 16
    assert index["scenario_count"] == 64
    assert index["dependency_point_count"] == 47
    assert official["human_review_complete_task_count"] == 1
    assert index["human_review_complete_task_count"] == 1
    assert official["automated_audit_complete_task_count"] == 16
    assert index["automated_audit_complete_task_count"] == 16
    assert len(set(official["official_task_ids"])) == 16
    assert all(
        task_id.startswith("asyncodebench:")
        for task_id in official["official_task_ids"]
    )
    assert {task["task_id"] for task in index["tasks"]} == set(
        official["official_task_ids"]
    )
    assert official["execution_profile"] == index["execution_profile"]
    assert official["execution_profile"]["profile_id"] == (
        "asyncodebench-v0.3-standard-30"
    )
    assert all(task["quality_status"] == "qualification_ready" for task in index["tasks"])
    assert sum(
        task["annotation_status"]["human_review_complete"]
        for task in index["tasks"]
    ) == 1
    assert all(
        task["annotation_status"]["automated_audit_complete"]
        for task in index["tasks"]
    )
    assert all(
        protocol["scenario_id"].startswith("asyncodebench-")
        and protocol["source_scenario_id"].startswith("commit0-")
        for task in index["tasks"]
        for protocol in task["protocols"].values()
    )


def test_release_artifact_checksums_match():
    index = read_json(RELEASE_DIR / "task_index.json")
    for task in index["tasks"]:
        assert {
            "task",
            "scenarios",
            "metrics",
            "quality",
            "annotation_a",
            "annotation_b",
            "annotation_audit",
            "adjudication_template",
        } == set(task["artifacts"])
        assert set(task["protocols"]) == {
            "single",
            "serial_specialists",
            "async_private",
            "caid_manager",
        }
        for artifact in task["artifacts"].values():
            path = ROOT / artifact["path"]
            assert path.is_file()
            assert hashlib.sha256(path.read_bytes()).hexdigest() == artifact["sha256"]
        assert task["source"]["overlay_count"] == len(task["source"]["overlays"])
        for overlay in task["source"]["overlays"]:
            path = ROOT / overlay["path"]
            assert path.is_file()
            assert hashlib.sha256(path.read_bytes()).hexdigest() == overlay["sha256"]


def test_public_execution_schemas_are_valid_json_schema_documents():
    schema_dir = ROOT / "schemas" / "release"
    expected = {
        "agent_request.schema.json",
        "agent_response.schema.json",
        "run_bundle.schema.json",
    }
    assert expected <= {path.name for path in schema_dir.glob("*.json")}
    for name in expected:
        schema = read_json(schema_dir / name)
        Draft202012Validator.check_schema(schema)
        assert schema["$schema"].endswith("2020-12/schema")
        assert schema["type"] == "object"
        assert schema["title"].startswith("AsynCodeBench")
