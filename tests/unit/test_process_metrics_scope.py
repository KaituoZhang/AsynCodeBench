import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from analyze_run_process_metrics import (  # noqa: E402
    repair_20018_caid_legacy_termination_stats,
    scope_violations,
)


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


def test_20018_caid_repairs_legacy_iteration_cap_fields(tmp_path):
    import json

    (tmp_path / "run_metadata.json").write_text(
        json.dumps(
            {
                "task_id": "pr-hard:apache-tvm-20018",
                "protocol": "caid_manager",
            }
        ),
        encoding="utf-8",
    )
    responses = [
        {
            "actual_iterations": 100,
            "max_iterations": 100,
            "error": "MaxIterationsReached: maximum iterations reached",
            "termination_reason": None,
            "iteration_cap_hit": False,
        },
        {
            "actual_iterations": 99,
            "max_iterations": 100,
            "error": "MaxIterationsReached: malformed legacy record",
            "termination_reason": None,
            "iteration_cap_hit": False,
        },
    ]

    inferred = repair_20018_caid_legacy_termination_stats(tmp_path, responses)

    assert inferred == 1
    assert responses[0]["termination_reason"] == "iteration_limit"
    assert responses[0]["iteration_cap_hit"] is True
    assert responses[1]["termination_reason"] is None
    assert responses[1]["iteration_cap_hit"] is False


def test_20018_caid_repair_does_not_change_other_tasks(tmp_path):
    import json

    (tmp_path / "run_metadata.json").write_text(
        json.dumps(
            {
                "task_id": "pr-hard:apache-tvm-20107",
                "protocol": "caid_manager",
            }
        ),
        encoding="utf-8",
    )
    responses = [
        {
            "actual_iterations": 100,
            "max_iterations": 100,
            "error": "MaxIterationsReached",
            "termination_reason": None,
            "iteration_cap_hit": False,
        }
    ]

    assert repair_20018_caid_legacy_termination_stats(tmp_path, responses) == 0
    assert responses[0]["termination_reason"] is None
    assert responses[0]["iteration_cap_hit"] is False
