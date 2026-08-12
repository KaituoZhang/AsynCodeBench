import json
from types import SimpleNamespace

from agents import OpenHandsAgentAdapter
from asyncodebench_harness.cli import main as cli_main
from asyncodebench_harness.results import (
    REQUIRED_ARTIFACTS,
    build_run_bundle,
    validate_run_bundle,
)

PROTOCOLS = (
    "single",
    "serial_specialists",
    "async_private",
    "caid_manager",
)


class FakeTask:
    task_id = "asyncodebench:example"
    source_task_id = "commit0:example"
    asyncodebench_config = SimpleNamespace(release="v0.3")

    def scenario_for(self, protocol):
        return {"scenario_id": f"asyncodebench-example.{protocol}.v0.3"}

    def public_scenario_id(self, protocol):
        return self.scenario_for(protocol)["scenario_id"]


def write_valid_artifacts(path):
    for name in REQUIRED_ARTIFACTS:
        target = path / name
        if name in {"run_metadata.json", "protocol.json"}:
            target.write_text(
                json.dumps(
                    {
                        "task_id": "asyncodebench:example",
                        "protocol": "single",
                        "scenario_id": "asyncodebench-example.single.v0.3",
                    }
                ),
                encoding="utf-8",
            )
        elif name == "report.json":
            payload = {
                "exitcode": 1,
                "summary": {"passed": 3, "failed": 2, "collected": 5},
                "asyncodebench": {
                    "final_evaluator_source": "asyncodebench_manifest",
                    "timed_out": False,
                },
            }
            target.write_text(json.dumps(payload), encoding="utf-8")
        elif name == "dependency_probe_checkpoints.jsonl":
            target.write_text(
                '{"checkpoint_id":"final_integrated"}\n', encoding="utf-8"
            )
        elif name.endswith(".json"):
            target.write_text("{}\n", encoding="utf-8")
        else:
            target.write_text("1\n", encoding="utf-8")


def test_result_bundle_accepts_model_failure_with_valid_instrumentation(tmp_path):
    write_valid_artifacts(tmp_path)

    path, bundle = build_run_bundle(
        FakeTask(), tmp_path, "single", OpenHandsAgentAdapter()
    )
    validation = validate_run_bundle(tmp_path)

    assert path.name == "run_bundle.json"
    assert bundle["instrumentation"]["valid"] is True
    assert bundle["final_test"]["failed"] == 2
    assert validation["valid"] is True


def test_result_bundle_detects_artifact_tampering(tmp_path):
    write_valid_artifacts(tmp_path)
    build_run_bundle(FakeTask(), tmp_path, "single", OpenHandsAgentAdapter())
    (tmp_path / "cost.json").write_text('{"changed":true}\n', encoding="utf-8")

    validation = validate_run_bundle(tmp_path)

    assert validation["valid"] is False
    assert "artifact checksum mismatch: cost.json" in validation["issues"]


def test_result_bundle_marks_instrumentation_failure_invalid(tmp_path):
    write_valid_artifacts(tmp_path)
    (tmp_path / "dependency_probe_checkpoints.jsonl").unlink()

    _, bundle = build_run_bundle(
        FakeTask(), tmp_path, "async_private", OpenHandsAgentAdapter()
    )

    assert bundle["instrumentation"]["valid"] is False
    assert "dependency_probe_checkpoints.jsonl" in " ".join(
        bundle["instrumentation"]["issues"]
    )


def test_cli_lists_all_official_tasks(capsys):
    assert cli_main(["tasks", "--json"]) == 0

    tasks = json.loads(capsys.readouterr().out)
    assert len(tasks) == 16
    assert all(item["task_id"].startswith("asyncodebench:") for item in tasks)


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
