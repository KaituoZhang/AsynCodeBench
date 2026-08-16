import hashlib
import json
from types import SimpleNamespace

import asyncodebench_harness.results as results_module
import pytest
from agents import OpenHandsAgentAdapter
from asyncodebench_harness.cli import main as cli_main
from asyncodebench_harness.results import (
    REQUIRED_ARTIFACTS,
    build_run_bundle,
    validate_run_bundle,
)
from protocols.asyncodebench.profile import load_official_execution_profile

PROTOCOLS = (
    "single",
    "serial_specialists",
    "async_private",
    "caid_manager",
)
SELECTOR = "tests/test_example.py::test_contract"
FAKE_RELEASE_INDEX_PATH = None


@pytest.fixture(autouse=True)
def fake_release_index(tmp_path_factory, monkeypatch):
    global FAKE_RELEASE_INDEX_PATH
    release_dir = tmp_path_factory.mktemp("release-index")
    FAKE_RELEASE_INDEX_PATH = release_dir / "task_index.json"
    monkeypatch.setattr(
        results_module,
        "_release_index_path",
        lambda release: FAKE_RELEASE_INDEX_PATH,
    )


class FakeTask:
    task_id = "asyncodebench:example"
    source_task_id = "commit0:example"
    asyncodebench_config = SimpleNamespace(release="v0.3")

    def scenario_for(self, protocol):
        return {"scenario_id": f"commit0-example.{protocol}.v0.3"}

    def public_scenario_id(self, protocol):
        return f"asyncodebench-example.{protocol}.v0.3"


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_valid_artifacts(path, *, profile_matched=True):
    adapter = OpenHandsAgentAdapter().public_metadata()
    snapshots = {
        "task_snapshot.json": {"task_id": "commit0:example"},
        "scenario_snapshot.json": {
            "scenario_id": "commit0-example.single.v0.3",
            "agent_count": 1,
        },
        "scenario_manifest_snapshot.json": {
            "task_id": "commit0:example",
            "scenarios": [
                {
                    "scenario_id": "commit0-example.single.v0.3",
                    "agent_count": 1,
                }
            ]
        },
        "metrics_snapshot.json": {
            "task_id": "commit0:example",
            "dependency_points": [
                {
                    "dependency_id": "example.contract",
                    "integrated_probe_tests": [SELECTOR],
                }
            ]
        },
        "quality_snapshot.json": {
            "task_id": "commit0:example",
            "quality_status": "qualification_ready",
        },
        "execution_profile_snapshot.json": load_official_execution_profile(),
    }
    for name, payload in snapshots.items():
        (path / name).write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

    profile_snapshot = path / "execution_profile_snapshot.json"
    observed = {
        "manager_max_iterations": 100,
        "max_subagents": 1,
        "subagent_max_iterations": 100,
        "max_rounds_chat": 2,
        "final_pytest_timeout_seconds": 900,
        "probe_timeout_seconds": 60,
        "final_evaluator_source": "asyncodebench_manifest",
        "scenario_declared_agents": 1,
    }
    deviations = (
        []
        if profile_matched
        else [{"field": "manager_max_iterations", "expected": 100, "observed": 10}]
    )
    metadata = {
        "task_id": "asyncodebench:example",
        "source_task_id": "commit0:example",
        "release": "v0.3",
        "protocol": "single",
        "scenario_id": "asyncodebench-example.single.v0.3",
        "source_scenario_id": "commit0-example.single.v0.3",
        "model": "test/model",
        "subagent_model": "test/model",
        "agent_adapter": adapter,
        "budgets": {
            "manager_max_iterations": 100,
            "max_subagents": 1,
            "subagent_max_iterations": 100,
            "max_rounds_chat": 2,
        },
        "execution_profile": {
            "profile_id": "asyncodebench-v0.3-standard-100",
            "schema_version": "asyncodebench-execution-profile-v2",
            "path": "configs/evaluation/official_execution_profile.v2.json",
            "sha256": sha256(profile_snapshot),
            "matched": profile_matched,
            "deviations": deviations,
            "observed": observed,
        },
        "artifacts": {
            key: {"sha256": sha256(path / filename)}
            for filename, key in {
                "task_snapshot.json": "task",
                "scenario_manifest_snapshot.json": "scenario",
                "metrics_snapshot.json": "metrics",
                "quality_snapshot.json": "quality",
            }.items()
        },
        "generation_configuration": {
            "schema_version": "asyncodebench-generation-configuration-v1",
            "parameters": {},
        },
        "model_server": {"configured": False},
        "prompt": {"path": "prompts/asyncodebench.yaml", "sha256": "e" * 64},
        "source": {
            "repository": "https://example.com/example.git",
            "base_ref": "commit0",
            "base_sha": "d" * 40,
            "overlays": [],
        },
        "code_revisions": {
            "asyncodebench": "a" * 40,
            "async_swe_agents": "b" * 40,
            "software_agent_sdk": "c" * 40,
        },
    }
    (path / "run_metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
    release_index = {
        "release": "v0.3",
        "release_version": "0.3.0-test",
        "execution_profile": {
            "profile_id": "asyncodebench-v0.3-standard-100",
            "sha256": sha256(profile_snapshot),
        },
        "tasks": [
            {
                "task_id": "asyncodebench:example",
                "source_task_id": "commit0:example",
                "source": {
                    "repository": "https://example.com/example.git",
                    "base_ref": "commit0",
                    "base_sha": "d" * 40,
                    "overlays": [],
                },
                "protocols": {
                    "single": {
                        "scenario_id": "asyncodebench-example.single.v0.3",
                        "source_scenario_id": "commit0-example.single.v0.3",
                    }
                },
                "artifacts": {
                    key: {"sha256": sha256(path / filename)}
                    for filename, key in {
                        "task_snapshot.json": "task",
                        "scenario_manifest_snapshot.json": "scenarios",
                        "metrics_snapshot.json": "metrics",
                        "quality_snapshot.json": "quality",
                    }.items()
                },
            }
        ],
    }
    FAKE_RELEASE_INDEX_PATH.write_text(
        json.dumps(release_index), encoding="utf-8"
    )
    (path / "protocol.json").write_text(
        json.dumps(
            {
                "task_id": "asyncodebench:example",
                "source_task_id": "commit0:example",
                "protocol": "single",
                "scenario_id": "asyncodebench-example.single.v0.3",
                "source_scenario_id": "commit0-example.single.v0.3",
            }
        ),
        encoding="utf-8",
    )
    report = {
        "exitcode": 1,
        "summary": {"passed": 3, "failed": 2, "total": 5, "collected": 5},
        "asyncodebench": {
            "final_evaluator_source": "asyncodebench_manifest",
            "timed_out": False,
            "synthetic_summary": False,
            "canonical_test_restore": {},
        },
    }
    (path / "report.json").write_text(json.dumps(report), encoding="utf-8")
    checkpoint = {
        "checkpoint_id": "final_integrated",
        "checkpoint_type": "final_integrated",
        "probe_test_results": {SELECTOR: {"status": "failed", "passed": False}},
    }
    (path / "dependency_probe_checkpoints.jsonl").write_text(
        json.dumps(checkpoint) + "\n", encoding="utf-8"
    )
    (path / "process_metrics_summary.json").write_text(
        json.dumps({"cost_metrics": {"model_calls": 3}}), encoding="utf-8"
    )
    (path / "cost.json").write_text(
        json.dumps({"total": {"total_tokens": 100}}), encoding="utf-8"
    )
    (path / "runtime.txt").write_text("1\n", encoding="utf-8")
    (path / "run_20260804.log").write_text("Iterations used: 3\n", encoding="utf-8")
    event_dir = path / "agent_events"
    event_dir.mkdir()
    (event_dir / "single_agent_events.jsonl").write_text(
        '{"event":"model_response"}\n', encoding="utf-8"
    )
    assert set(REQUIRED_ARTIFACTS) <= {item.name for item in path.iterdir()}


def test_result_bundle_accepts_model_failure_with_valid_instrumentation(tmp_path):
    write_valid_artifacts(tmp_path)

    path, bundle = build_run_bundle(
        FakeTask(), tmp_path, "single", OpenHandsAgentAdapter()
    )
    validation = validate_run_bundle(tmp_path)

    assert path.name == "run_bundle.json"
    assert bundle["status"] == "valid"
    assert bundle["final_test"]["failed"] == 2
    assert bundle["final_test"]["success"] is False
    assert bundle["eligibility"]["official_aggregate"] is True
    assert bundle["release_index"]["sha256"] == sha256(FAKE_RELEASE_INDEX_PATH)
    assert validation["valid"] is True


def test_result_bundle_detects_artifact_tampering(tmp_path):
    write_valid_artifacts(tmp_path)
    build_run_bundle(FakeTask(), tmp_path, "single", OpenHandsAgentAdapter())
    (tmp_path / "cost.json").write_text('{"changed":true}\n', encoding="utf-8")

    validation = validate_run_bundle(tmp_path)

    assert validation["valid"] is False
    assert "artifact_checksum_mismatch:cost.json" in validation["issues"]


def test_result_bundle_rejects_self_consistent_nonrelease_snapshot(tmp_path):
    write_valid_artifacts(tmp_path)
    task_path = tmp_path / "task_snapshot.json"
    task = json.loads(task_path.read_text(encoding="utf-8"))
    task["invented"] = True
    task_path.write_text(json.dumps(task), encoding="utf-8")
    metadata_path = tmp_path / "run_metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["artifacts"]["task"]["sha256"] = sha256(task_path)
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    _, bundle = build_run_bundle(
        FakeTask(), tmp_path, "single", OpenHandsAgentAdapter()
    )

    assert bundle["status"] == "invalid"
    assert (
        "release_snapshot_checksum_mismatch:task_snapshot.json"
        in bundle["instrumentation"]["hard_failures"]
    )


def test_result_bundle_detects_unindexed_artifact(tmp_path):
    write_valid_artifacts(tmp_path)
    build_run_bundle(FakeTask(), tmp_path, "single", OpenHandsAgentAdapter())
    (tmp_path / "late_file.txt").write_text("late\n", encoding="utf-8")

    validation = validate_run_bundle(tmp_path)

    assert validation["valid"] is False
    assert "unindexed_artifact:late_file.txt" in validation["issues"]


def test_result_bundle_detects_recorded_outcome_tampering(tmp_path):
    write_valid_artifacts(tmp_path)
    bundle_path, _ = build_run_bundle(
        FakeTask(), tmp_path, "single", OpenHandsAgentAdapter()
    )
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    bundle["final_test"]["passed"] = 5
    bundle_path.write_text(json.dumps(bundle), encoding="utf-8")

    validation = validate_run_bundle(tmp_path)

    assert validation["valid"] is False
    assert "recorded_final_test_mismatch" in validation["issues"]


def test_result_bundle_detects_instrumentation_tampering(tmp_path):
    write_valid_artifacts(tmp_path)
    bundle_path, _ = build_run_bundle(
        FakeTask(), tmp_path, "single", OpenHandsAgentAdapter()
    )
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    bundle["instrumentation"]["observations"].append("invented_observation")
    bundle_path.write_text(json.dumps(bundle), encoding="utf-8")

    validation = validate_run_bundle(tmp_path)

    assert validation["valid"] is False
    assert "recorded_instrumentation_mismatch" in validation["issues"]


def test_result_bundle_marks_provider_failure_invalid(tmp_path):
    write_valid_artifacts(tmp_path)
    log = next(tmp_path.glob("run_*.log"))
    log.write_text(
        "litellm.InternalServerError: OpenAIException - Connection error.\n",
        encoding="utf-8",
    )

    _, bundle = build_run_bundle(
        FakeTask(), tmp_path, "single", OpenHandsAgentAdapter()
    )

    assert bundle["status"] == "invalid"
    assert bundle["eligibility"]["official_aggregate"] is False
    assert "provider_or_transport_error" in bundle["instrumentation"]["hard_failures"]


@pytest.mark.parametrize(
    ("log_text", "failure"),
    [
        ('Termination: execution_error\nIterations used: 1\n', "execution_error"),
        ("Iterations used: 0\n", "zero_model_iterations"),
    ],
)
def test_validate_run_rejects_execution_error_and_zero_iterations(
    tmp_path, log_text, failure
):
    write_valid_artifacts(tmp_path)
    log = next(tmp_path.glob("run_*.log"))
    log.write_text(log_text, encoding="utf-8")

    _, bundle = build_run_bundle(
        FakeTask(), tmp_path, "single", OpenHandsAgentAdapter()
    )
    validation = validate_run_bundle(tmp_path)

    assert bundle["status"] == "invalid"
    assert failure in bundle["instrumentation"]["hard_failures"]
    assert validation["valid"] is False
    assert failure in validation["recorded_hard_failures"]


def test_profile_deviation_is_valid_but_exploratory(tmp_path):
    write_valid_artifacts(tmp_path, profile_matched=False)

    _, bundle = build_run_bundle(
        FakeTask(), tmp_path, "single", OpenHandsAgentAdapter()
    )

    assert bundle["status"] == "valid"
    assert bundle["eligibility"]["functional_metrics"] is True
    assert bundle["eligibility"]["official_profile"] is False
    assert bundle["eligibility"]["official_aggregate"] is False


def test_incomplete_provenance_is_valid_but_not_official(tmp_path):
    write_valid_artifacts(tmp_path)
    metadata_path = tmp_path / "run_metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["prompt"]["sha256"] = None
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    _, bundle = build_run_bundle(
        FakeTask(), tmp_path, "single", OpenHandsAgentAdapter()
    )

    assert bundle["status"] == "valid"
    assert bundle["eligibility"]["provenance_complete"] is False
    assert bundle["eligibility"]["official_aggregate"] is False
    assert "prompt.sha256" in bundle["provenance"]["missing_required_fields"]


def test_empty_generation_configuration_is_not_official(tmp_path):
    write_valid_artifacts(tmp_path)
    metadata_path = tmp_path / "run_metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["generation_configuration"] = {}
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    _, bundle = build_run_bundle(
        FakeTask(), tmp_path, "single", OpenHandsAgentAdapter()
    )

    assert bundle["status"] == "valid"
    assert bundle["provenance"]["generation_configuration_recorded"] is False
    assert bundle["eligibility"]["provenance_complete"] is False
    assert bundle["eligibility"]["official_aggregate"] is False


def test_cli_lists_all_official_tasks(capsys):
    assert cli_main(["tasks", "--json"]) == 0

    tasks = json.loads(capsys.readouterr().out)
    assert len(tasks) == 16
    assert all(item["task_id"].startswith("asyncodebench:") for item in tasks)


def test_cli_reports_release_and_review_status(capsys):
    assert cli_main(["release-status", "--json"]) == 0

    status = json.loads(capsys.readouterr().out)
    assert status["task_count"] == 16
    assert status["scenario_count"] == 64
    assert status["dependency_point_count"] == 47
    assert status["automated_audit_complete_task_count"] == 16
    assert status["human_review_complete_task_count"] == 16
    assert status["human_review_passed_task_count"] == 16
    assert status["executable_release_complete"] is True
    assert status["release_stage"] == "community_preview"
    assert status["community_preview_ready"] is True
    assert status["stable_release_ready"] is False
    assert status["validated_baseline_bundle_count"] == 0
    assert status["human_validation_complete"] is True
    assert status["pending_human_review_task_ids"] == []


def test_cli_release_gate_accepts_preview_and_rejects_stable(capsys):
    assert cli_main(["release-status", "--require", "preview"]) == 0
    capsys.readouterr()
    assert cli_main(["release-status", "--require", "stable"]) == 2


def test_cli_dry_runs_all_four_protocols(capsys):
    assert (
        cli_main(
            [
                "run",
                "--task",
                "asyncodebench:cachetools",
                "--protocol",
                "all",
                "--model",
                "test/model",
                "--dry-run",
            ]
        )
        == 0
    )

    output = capsys.readouterr().out
    for protocol in PROTOCOLS:
        assert f"[DryRun] protocol={protocol}" in output
    assert "execution_profile=asyncodebench-v0.3-standard-100 matched=True" in output
