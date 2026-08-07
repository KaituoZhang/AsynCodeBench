import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from analyze_run_process_metrics import scope_violations  # noqa: E402


def write_scope_records(run_dir, records):
    import json

    content = "".join(json.dumps(record) + "\n" for record in records)
    (run_dir / "scope_validation.jsonl").write_text(content, encoding="utf-8")


def test_v2_scope_records_override_empty_response_file_lists(tmp_path):
    write_scope_records(
        tmp_path,
        [
            {
                "agent_id": "key_agent",
                "task_assignment_id": "key_construction",
                "writable_paths": ["src/cachetools/keys.py"],
                "changed_paths": [
                    "src/cachetools/keys.py",
                    "src/cachetools/func.py",
                ],
                "violations": ["src/cachetools/func.py"],
                "passed": False,
                "policy": "reject_artifact_on_out_of_scope_change",
            },
            {
                "agent_id": "decorator_agent",
                "task_assignment_id": "decorator_factories",
                "writable_paths": ["src/cachetools/func.py"],
                "changed_paths": [],
                "violations": [],
                "passed": True,
                "policy": "reject_artifact_on_out_of_scope_change",
            },
        ],
    )

    result = scope_violations(
        tmp_path,
        [
            {
                "source": "key_agent",
                "task_id": "key_construction",
                "files_modified": [],
            }
        ],
    )

    assert result["evidence_source"] == "scope_validation.jsonl"
    assert result["scoped_agent_attempt_count"] == 2
    assert result["violating_agent_attempt_count"] == 1
    assert result["SVR"] == 0.5
    assert result["unique_agent_SVR"] == 0.5
    assert result["violations"][0]["out_of_scope_files"] == [
        "src/cachetools/func.py"
    ]


def test_v2_scope_rate_counts_retries_as_attempts_and_agents_once(tmp_path):
    write_scope_records(
        tmp_path,
        [
            {
                "agent_id": "engineer_1",
                "writable_paths": ["src/cachetools/keys.py"],
                "changed_paths": ["src/cachetools/keys.py"],
                "violations": [],
                "passed": True,
            },
            {
                "agent_id": "engineer_2",
                "writable_paths": ["src/cachetools/func.py"],
                "changed_paths": [
                    "src/cachetools/func.py",
                    "src/cachetools/keys.py",
                ],
                "violations": ["src/cachetools/keys.py"],
                "passed": False,
            },
            {
                "agent_id": "engineer_2",
                "writable_paths": ["src/cachetools/func.py"],
                "changed_paths": ["src/cachetools/keys.py"],
                "violations": ["src/cachetools/keys.py"],
                "passed": False,
            },
        ],
    )

    result = scope_violations(tmp_path, [])

    assert result["scoped_agent_attempt_count"] == 3
    assert result["violating_agent_attempt_count"] == 2
    assert result["SVR"] == 2 / 3
    assert result["unique_scoped_agent_count"] == 2
    assert result["unique_violating_agent_count"] == 1
    assert result["unique_agent_SVR"] == 0.5
