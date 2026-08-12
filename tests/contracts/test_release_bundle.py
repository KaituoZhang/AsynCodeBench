import hashlib
import json
import subprocess
import sys
from pathlib import Path


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
    assert len(set(official["official_task_ids"])) == 16
    assert all(
        task_id.startswith("asyncodebench:")
        for task_id in official["official_task_ids"]
    )
    assert {task["task_id"] for task in index["tasks"]} == set(
        official["official_task_ids"]
    )


def test_release_artifact_checksums_match():
    index = read_json(RELEASE_DIR / "task_index.json")
    for task in index["tasks"]:
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
        assert schema["$schema"].endswith("2020-12/schema")
        assert schema["type"] == "object"
        assert schema["title"].startswith("AsynCodeBench")
