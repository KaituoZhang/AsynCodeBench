import json

from scripts.check_run_health import inspect_run

SELECTOR = "tests/test_example.py::test_contract"


def create_run(tmp_path, log_text="normal run\n"):
    run_dir = tmp_path / "example_run"
    run_dir.mkdir()
    report = {
        "exitcode": 0,
        "summary": {"passed": 1, "total": 1, "collected": 1},
        "asyncodebench": {
            "final_evaluator_source": "asyncodebench_manifest",
            "synthetic_summary": False,
            "timed_out": False,
            "canonical_test_restore": {},
        },
    }
    (run_dir / "report.json").write_text(json.dumps(report), encoding="utf-8")
    (run_dir / "cost.json").write_text(
        json.dumps({"total": {"total_tokens": 10}}), encoding="utf-8"
    )
    (run_dir / "runtime.txt").write_text("1\n", encoding="utf-8")
    (run_dir / "process_metrics_summary.json").write_text(
        json.dumps({"cost_metrics": {"model_calls": 1}}), encoding="utf-8"
    )
    (run_dir / "metrics_snapshot.json").write_text(
        json.dumps(
            {
                "dependency_points": [
                    {
                        "dependency_id": "example.contract",
                        "integrated_probe_tests": [SELECTOR],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    checkpoint = {
        "checkpoint_id": "final_integrated",
        "checkpoint_type": "final_integrated",
        "probe_test_results": {SELECTOR: {"status": "passed", "passed": True}},
    }
    (run_dir / "dependency_probe_checkpoints.jsonl").write_text(
        json.dumps(checkpoint) + "\n", encoding="utf-8"
    )
    (run_dir / "run_20260804.log").write_text(log_text, encoding="utf-8")
    event_dir = run_dir / "agent_events"
    event_dir.mkdir()
    (event_dir / "engineer_1_events.jsonl").write_text(
        '{"event":"model_response"}\n', encoding="utf-8"
    )
    return run_dir


def test_model_stuck_is_observation_not_infrastructure_failure(tmp_path):
    run_dir = create_run(tmp_path, "Remote conversation got stuck\n")

    result = inspect_run(run_dir)

    assert result["status"] == "valid"
    assert result["hard_failures"] == []
    assert result["observations"] == ["model_trajectory_stuck"]


def test_remote_timeout_is_infrastructure_failure(tmp_path):
    run_dir = create_run(
        tmp_path,
        "Run timed out after 3600.0 seconds. "
        "The conversation may still be running on the server.\n",
    )

    result = inspect_run(run_dir)

    assert result["status"] == "invalid"
    assert "remote_execution_timeout" in result["hard_failures"]


def test_source_code_connection_error_text_is_not_transport_failure(tmp_path):
    run_dir = create_run(
        tmp_path,
        "class ConnectionError(RequestException):\n"
        '    """A Connection error occurred."""\n',
    )

    result = inspect_run(run_dir)

    assert result["status"] == "valid"
    assert "provider_or_transport_error" not in result["hard_failures"]


def test_structured_openai_connection_error_is_transport_failure(tmp_path):
    run_dir = create_run(tmp_path)
    (run_dir / "outputs.jsonl").write_text(
        json.dumps(
            {
                "event_type": "agent_response",
                "content": {
                    "error": "InternalServerError - OpenAIException - Connection error"
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = inspect_run(run_dir)

    assert result["status"] == "invalid"
    assert "provider_or_transport_error" in result["hard_failures"]


def test_model_reasoning_about_authentication_error_is_not_provider_failure(tmp_path):
    run_dir = create_run(tmp_path)
    event_path = run_dir / "agent_events" / "engineer_1_events.jsonl"
    event_path.write_text(
        json.dumps(
            {
                "event": "model_response",
                "content": "The code should raise AuthenticationError: on bad input",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = inspect_run(run_dir)

    assert result["status"] == "valid"
    assert "provider_or_transport_error" not in result["hard_failures"]


def test_downloaded_upstream_tvm_patch_is_solution_leakage(tmp_path):
    run_dir = create_run(
        tmp_path,
        "urllib.request.urlopen("
        "'https://github.com/apache/tvm/pull/20153.patch')\n"
        "bytes 74979\nIDENTICAL TO REFERENCE HEAD\n",
    )

    result = inspect_run(run_dir)

    assert result["status"] == "invalid"
    assert "solution_source_leakage" in result["hard_failures"]


def test_canonical_test_restore_is_recorded_as_model_behavior(tmp_path):
    run_dir = create_run(tmp_path)
    report_path = run_dir / "report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["asyncodebench"]["canonical_test_restore"] = {
        "canonical_ref": "abc123",
        "restored_paths": ["tests/test_utils.py"],
        "untracked_paths_removed": [],
    }
    report_path.write_text(json.dumps(report), encoding="utf-8")

    result = inspect_run(run_dir)

    assert result["status"] == "valid"
    assert result["observations"] == ["canonical_test_paths_restored"]


def test_model_induced_collection_failure_remains_valid_evidence(tmp_path):
    run_dir = create_run(tmp_path)
    report_path = run_dir / "report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report.update(
        {
            "exitcode": 2,
            "summary": {"passed": 0, "failed": 0, "error": 1, "total": 1},
        }
    )
    report["asyncodebench"].update(
        {
            "synthetic_summary": True,
            "evaluation_failure_kind": "collection_failed",
        }
    )
    report_path.write_text(json.dumps(report), encoding="utf-8")

    result = inspect_run(run_dir)

    assert result["status"] == "valid"
    assert result["eligibility"]["functional_metrics"] is True
    assert "model_evaluator_failure:collection_failed" in result["observations"]


def test_failed_collectors_in_real_report_remain_valid_evidence(tmp_path):
    run_dir = create_run(tmp_path)
    report_path = run_dir / "report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report.update(
        {
            "exitcode": 1,
            "summary": {"total": 0, "collected": 0},
            "collectors": [
                {"nodeid": "", "outcome": "passed"},
                {
                    "nodeid": "tests/test_api.py",
                    "outcome": "failed",
                    "longrepr": "ImportError while importing test module",
                },
            ],
        }
    )
    report["asyncodebench"]["synthetic_summary"] = False
    report_path.write_text(json.dumps(report), encoding="utf-8")

    result = inspect_run(run_dir)

    assert result["status"] == "valid"
    assert result["eligibility"]["functional_metrics"] is True
    assert "evaluator_zero_collected" not in result["hard_failures"]
    assert "model_evaluator_failure:collection_failed" in result["observations"]


def test_zero_model_execution_is_invalid(tmp_path):
    run_dir = create_run(tmp_path)
    (run_dir / "cost.json").write_text(
        json.dumps({"total": {"total_tokens": 0}}), encoding="utf-8"
    )
    (run_dir / "process_metrics_summary.json").write_text(
        json.dumps({"cost_metrics": {"model_calls": 0}}), encoding="utf-8"
    )

    result = inspect_run(run_dir)

    assert result["status"] == "invalid"
    assert "no_model_execution_evidence" in result["hard_failures"]


def test_zero_iterations_with_token_usage_is_invalid(tmp_path):
    run_dir = create_run(tmp_path)
    (run_dir / "outputs.jsonl").write_text(
        json.dumps({"content": {"actual_iterations": 0}}) + "\n",
        encoding="utf-8",
    )

    result = inspect_run(run_dir)

    assert result["status"] == "invalid"
    assert "zero_model_iterations" in result["hard_failures"]


def test_execution_error_is_invalid(tmp_path):
    run_dir = create_run(
        tmp_path,
        'agent finished with {"termination_reason": "execution_error"}\n',
    )

    result = inspect_run(run_dir)

    assert result["status"] == "invalid"
    assert "execution_error" in result["hard_failures"]


def test_openhands_event_schema_mismatch_is_invalid(tmp_path):
    run_dir = create_run(
        tmp_path,
        "dynamic_context: Extra inputs are not permitted\n",
    )

    result = inspect_run(run_dir)

    assert result["status"] == "invalid"
    assert "openhands_event_schema_mismatch" in result["hard_failures"]


def test_silent_zero_test_collection_is_invalid(tmp_path):
    run_dir = create_run(tmp_path)
    report_path = run_dir / "report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["summary"] = {"passed": 0, "failed": 0, "total": 0, "collected": 0}
    report_path.write_text(json.dumps(report), encoding="utf-8")

    result = inspect_run(run_dir)

    assert result["status"] == "invalid"
    assert "evaluator_zero_collected" in result["hard_failures"]


def test_missing_final_probe_selector_is_invalid(tmp_path):
    run_dir = create_run(tmp_path)
    checkpoint_path = run_dir / "dependency_probe_checkpoints.jsonl"
    checkpoint = {
        "checkpoint_id": "final_integrated",
        "checkpoint_type": "final_integrated",
        "probe_test_results": {},
    }
    checkpoint_path.write_text(json.dumps(checkpoint) + "\n", encoding="utf-8")

    result = inspect_run(run_dir)

    assert result["status"] == "invalid"
    assert "missing_final_probe_selectors:1" in result["hard_failures"]


def test_20018_caid_rejects_a_corrupt_patch(tmp_path):
    run_dir = create_run(tmp_path)
    report_path = run_dir / "report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["asyncodebench"]["final_evaluator_source"] = "pr_hard_v0.4_manifest"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    (run_dir / "run_metadata.json").write_text(
        json.dumps(
            {
                "task_id": "pr-hard:apache-tvm-20018",
                "protocol": "caid_manager",
                "candidate_lane": {"kind": "pr_hard_v0.4"},
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "patch.diff").write_text(
        """diff --git a/example.py b/example.py
--- a/example.py
+++ b/example.py
@@ -1 +1 @@
-old
""",
        encoding="utf-8",
    )

    result = inspect_run(run_dir)

    assert result["status"] == "invalid"
    assert "invalid_patch_diff" in result["hard_failures"]
