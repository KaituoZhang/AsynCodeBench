import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from analyze_run_process_metrics import summarize_primary_outcome  # noqa: E402
from summarize_model_task_runs import run_bundle_admission  # noqa: E402

MODES = ("single", "serial_specialists", "async_private", "caid_manager")
PROFILE_SHA256 = hashlib.sha256(
    (ROOT / "configs/evaluation/official_execution_profile.v2.json").read_bytes()
).hexdigest()


def write_report(path, *, collected, synthetic=False):
    path.mkdir(parents=True, exist_ok=True)
    report = {
        "exitcode": 0,
        "summary": {
            "passed": collected,
            "failed": 0,
            "error": 0,
            "total": collected,
            "collected": collected,
        },
        "asyncodebench": {
            "final_evaluator_source": "asyncodebench_manifest",
            "synthetic_summary": synthetic,
        },
    }
    (path / "report.json").write_text(json.dumps(report), encoding="utf-8")


def write_task_records(path, *, model_tag="test-model", eligible):
    path.mkdir(parents=True, exist_ok=True)
    rows = []
    for mode in MODES:
        rows.append(
            {
                "mode": mode,
                "runner_adapter": "native-strict-checkpoints",
                "run_bundle_schema_version": "0.2",
                "run_bundle_status": "valid" if eligible else "invalid",
                "recorded_model": "test/provider-model",
                "recorded_subagent_model": "test/provider-model",
                "execution_profile_id": "asyncodebench-v0.3-standard-100",
                "execution_profile_sha256": PROFILE_SHA256,
                "generation_configuration_sha256": "a" * 64,
                "recorded_agent_adapter_name": "openhands",
                "recorded_agent_adapter_class": (
                    "agents.openhands:OpenHandsAgentAdapter"
                ),
                "recorded_agent_adapter_package": "async-swe-agents",
                "recorded_agent_adapter_package_version": "0.1.0",
                "recorded_agent_adapter_source_sha256": "d" * 64,
                "recorded_agent_adapter_config_sha256": "f" * 64,
                "official_aggregate_eligible": eligible,
                "final_success": False,
                "final_tests_passed": 3,
                "final_tests_failed": 2,
                "final_tests_errors": 0,
                "final_tests_total": 5,
                "final_integrated_ADPR": 0.5,
                "drs_penalized_mean": 2.0,
                "cail_penalized_mean": 1.0,
                "dependency_resolution_efficiency_mean": 0.5,
                "strict_unresolved_count": 1,
                "total_tokens": 100,
                "runtime_seconds": 10,
                "async_overlap_seconds": 0,
                "subagent_artifact_failure_count": 0,
                "final_test_collection_failure": False,
                "final_test_timed_out": False,
            }
        )
    csv_path = path / f"cachetools_{model_tag}_metrics_table.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    artifact_index = {
        "task": "cachetools",
        "model": "test/provider-model",
        "model_tag": model_tag,
        "runs": {
            mode: {
                "run_dir": f"runs/{mode}",
                "result_admission": {
                    "run_bundle_schema_version": "0.2",
                    "run_bundle_status": "valid" if eligible else "invalid",
                    "recorded_model": "test/provider-model",
                    "recorded_subagent_model": "test/provider-model",
                    "execution_profile_id": "asyncodebench-v0.3-standard-100",
                    "execution_profile_sha256": PROFILE_SHA256,
                    "generation_configuration_sha256": "a" * 64,
                    "recorded_agent_adapter_name": "openhands",
                    "recorded_agent_adapter_class": (
                        "agents.openhands:OpenHandsAgentAdapter"
                    ),
                    "recorded_agent_adapter_package": "async-swe-agents",
                    "recorded_agent_adapter_package_version": "0.1.0",
                    "recorded_agent_adapter_source_sha256": "d" * 64,
                    "recorded_agent_adapter_config_sha256": "f" * 64,
                    "official_aggregate_eligible": eligible,
                },
                "artifacts": [
                    {
                        "relative_to_run_dir": "run_bundle.json",
                        "sha256": "b" * 64,
                    }
                ],
            }
            for mode in MODES
        }
    }
    (path / f"cachetools_{model_tag}_artifact_index.json").write_text(
        json.dumps(artifact_index), encoding="utf-8"
    )


def aggregate_command(input_dir, output_dir, *extra):
    return [
        sys.executable,
        str(SCRIPTS / "aggregate_model_task_results.py"),
        "--input-dir",
        str(input_dir),
        "--output-dir",
        str(output_dir),
        "--model-tag",
        "test-model",
        "--tasks",
        "cachetools",
        *extra,
    ]


def test_zero_collected_tests_cannot_be_final_success(tmp_path):
    write_report(tmp_path, collected=0)

    outcome = summarize_primary_outcome(tmp_path)

    assert outcome["exitcode"] == 0
    assert outcome["collected"] == 0
    assert outcome["final_success"] is False


def test_synthetic_summary_cannot_be_final_success(tmp_path):
    write_report(tmp_path, collected=5, synthetic=True)

    outcome = summarize_primary_outcome(tmp_path)

    assert outcome["synthetic_summary"] is True
    assert outcome["final_success"] is False


def test_missing_bundle_is_fail_closed(tmp_path):
    admission = run_bundle_admission(tmp_path)

    assert admission["run_bundle_status"] == "legacy_unbundled"
    assert admission["official_aggregate_eligible"] is False


def test_official_aggregate_rejects_ineligible_rows(tmp_path):
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    write_task_records(input_dir, eligible=False)

    result = subprocess.run(
        aggregate_command(input_dir, output_dir),
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert "not eligible for the official aggregate" in result.stderr


def test_exploratory_override_is_explicitly_labeled(tmp_path):
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    write_task_records(input_dir, eligible=False)

    result = subprocess.run(
        aggregate_command(input_dir, output_dir, "--allow-ineligible"),
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    report = output_dir / "test-model_1task_compact_metrics_table.md"
    content = report.read_text(encoding="utf-8")
    assert "exploratory aggregate" in content
    assert "1/19 task subset" in content
    campaign = json.loads(
        (output_dir / "test-model_1task_campaign_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    assert campaign["scope"] == "exploratory"
    assert campaign["admission"]["allow_ineligible_used"] is True


def test_official_aggregate_accepts_eligible_model_failures(tmp_path):
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    write_task_records(input_dir, eligible=True)

    result = subprocess.run(
        aggregate_command(input_dir, output_dir),
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    report = output_dir / "test-model_1task_compact_metrics_table.md"
    content = report.read_text(encoding="utf-8")
    assert "all rows satisfy the released official aggregate contract" in content
    assert "1/19 task subset" in content
    assert "0.000" in content
    campaign = json.loads(
        (output_dir / "test-model_1task_campaign_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    assert campaign["scope"] == "official_profile_subset"
    assert campaign["run_count"] == 4
    assert campaign["reporting"]["runs_per_task_protocol_cell"] == 1
    assert campaign["reporting"]["statistical_unit"] == "task"
    assert all(run["run_bundle_sha256"] == "b" * 64 for run in campaign["runs"])


def test_official_aggregate_rejects_cross_protocol_config_drift(tmp_path):
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    write_task_records(input_dir, eligible=True)
    csv_path = input_dir / "cachetools_test-model_metrics_table.csv"
    rows = list(csv.DictReader(csv_path.open(encoding="utf-8")))
    rows[-1]["generation_configuration_sha256"] = "c" * 64
    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    result = subprocess.run(
        aggregate_command(input_dir, output_dir),
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert "do not share one recorded generation configuration" in result.stderr


def test_official_aggregate_rejects_bundle_adapter_drift(tmp_path):
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    write_task_records(input_dir, eligible=True)
    csv_path = input_dir / "cachetools_test-model_metrics_table.csv"
    rows = list(csv.DictReader(csv_path.open(encoding="utf-8")))
    rows[-1]["recorded_agent_adapter_class"] = "third_party:DifferentAdapter"
    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    result = subprocess.run(
        aggregate_command(input_dir, output_dir),
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert "bundle-recorded agent adapter identity" in result.stderr


def test_official_aggregate_rejects_adapter_config_drift(tmp_path):
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    write_task_records(input_dir, eligible=True)
    csv_path = input_dir / "cachetools_test-model_metrics_table.csv"
    rows = list(csv.DictReader(csv_path.open(encoding="utf-8")))
    rows[-1]["recorded_agent_adapter_config_sha256"] = "1" * 64
    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    result = subprocess.run(
        aggregate_command(input_dir, output_dir),
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert "bundle-recorded agent adapter identity" in result.stderr


def test_official_aggregate_rejects_execution_profile_drift(tmp_path):
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    write_task_records(input_dir, eligible=True)
    csv_path = input_dir / "cachetools_test-model_metrics_table.csv"
    rows = list(csv.DictReader(csv_path.open(encoding="utf-8")))
    rows[-1]["execution_profile_sha256"] = "e" * 64
    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    result = subprocess.run(
        aggregate_command(input_dir, output_dir),
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert "execution profile ID and SHA256" in result.stderr


def test_official_aggregate_rejects_missing_subagent_model(tmp_path):
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    write_task_records(input_dir, eligible=True)
    csv_path = input_dir / "cachetools_test-model_metrics_table.csv"
    rows = list(csv.DictReader(csv_path.open(encoding="utf-8")))
    rows[-1]["recorded_subagent_model"] = ""
    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    index_path = input_dir / "cachetools_test-model_artifact_index.json"
    artifact_index = json.loads(index_path.read_text(encoding="utf-8"))
    artifact_index["runs"][MODES[-1]]["result_admission"][
        "recorded_subagent_model"
    ] = ""
    index_path.write_text(json.dumps(artifact_index), encoding="utf-8")

    result = subprocess.run(
        aggregate_command(input_dir, output_dir),
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert "requires one subagent model" in result.stderr
