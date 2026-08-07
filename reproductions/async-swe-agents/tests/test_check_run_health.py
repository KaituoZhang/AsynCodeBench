import json

from scripts.check_run_health import inspect_run


def create_run(tmp_path, log_text):
    run_dir = tmp_path / "gemma_caid_multi_test"
    run_dir.mkdir()
    (run_dir / "report.json").write_text(
        json.dumps(
            {
                "asynccodebench": {
                    "final_evaluator_source": "asynccodebench_manifest"
                }
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "cost.json").write_text("{}\n", encoding="utf-8")
    (run_dir / "runtime.txt").write_text("1\n", encoding="utf-8")
    (run_dir / "dependency_probe_checkpoints.jsonl").write_text(
        "{}\n", encoding="utf-8"
    )
    (run_dir / "run_20260804.log").write_text(log_text, encoding="utf-8")
    event_dir = run_dir / "agent_events"
    event_dir.mkdir()
    (event_dir / "engineer_1_events.jsonl").write_text(
        "{}\n", encoding="utf-8"
    )
    return run_dir


def test_model_stuck_is_observation_not_infrastructure_failure(tmp_path):
    run_dir = create_run(tmp_path, "Remote conversation got stuck\n")

    result = inspect_run(run_dir)

    assert result["healthy"] is True
    assert result["issues"] == []
    assert result["observations"] == ["model_trajectory_stuck"]


def test_remote_timeout_is_infrastructure_failure(tmp_path):
    run_dir = create_run(
        tmp_path,
        "Run timed out after 3600.0 seconds. "
        "The conversation may still be running on the server.\n",
    )

    result = inspect_run(run_dir)

    assert result["healthy"] is False
    assert "remote_execution_timeout" in result["issues"]


def test_source_code_connection_error_text_is_not_transport_failure(tmp_path):
    run_dir = create_run(
        tmp_path,
        'class ConnectionError(RequestException):\n'
        '    """A Connection error occurred."""\n',
    )

    result = inspect_run(run_dir)

    assert result["healthy"] is True
    assert "provider_or_transport" not in result["issues"]


def test_openai_connection_error_is_transport_failure(tmp_path):
    run_dir = create_run(
        tmp_path,
        "litellm.InternalServerError: OpenAIException - Connection error.\n",
    )

    result = inspect_run(run_dir)

    assert result["healthy"] is False
    assert "provider_or_transport" in result["issues"]


def test_canonical_test_restore_is_recorded_as_model_behavior(tmp_path):
    run_dir = create_run(tmp_path, "normal run\n")
    report_path = run_dir / "report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["asynccodebench"]["canonical_test_restore"] = {
        "canonical_ref": "abc123",
        "restored_paths": ["tests/test_utils.py"],
        "untracked_paths_removed": [],
    }
    report_path.write_text(json.dumps(report), encoding="utf-8")

    result = inspect_run(run_dir)

    assert result["healthy"] is True
    assert result["observations"] == ["canonical_test_paths_restored"]
