from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "configs/tasks/pr_hard_candidates.v0.4.json"
ENVIRONMENT = ROOT / "configs/environments/pr_hard_tvm.v0.4.json"
PREPARE = ROOT / "scripts/prepare_pr_hard_candidate.py"
PREPARE_RUNTIME = ROOT / "scripts/prepare_pr_hard_runtime.py"
REQUIREMENTS_LOCK = ROOT / "configs/environments/pr_hard_tvm.v0.4.requirements-lock.txt"
SCHEMA = ROOT / "schemas/v0.4/pr_hard_candidate_registry.schema.json"
QUALIFICATION_SCHEMA = ROOT / "schemas/v0.4/pr_hard_qualification_record.schema.json"
SCENARIO_SCHEMA = ROOT / "schemas/v0.3/scenario_record.schema.json"


def load_records() -> list[dict[str, object]]:
    payload = json.loads(CONFIG.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "pr-hard-candidates-v0.4"
    assert payload["release_status"] == "candidate_qualification_pending"
    return payload["records"]


def test_registry_matches_v04_schema() -> None:
    payload = json.loads(CONFIG.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(payload)


def patch_targets(patch_text: str) -> set[str]:
    return {
        line.removeprefix("+++ b/")
        for line in patch_text.splitlines()
        if line.startswith("+++ b/")
    }


def overlay_specs(record: dict[str, object]) -> list[dict[str, str]]:
    return [
        record["public_test_overlay"],
        *record.get("supplemental_public_test_overlays", []),
    ]


def test_registry_contains_reviewed_tvm_candidates() -> None:
    records = load_records()
    assert {record["task_id"] for record in records} == {
        "pr-hard:apache-tvm-20116",
        "pr-hard:apache-tvm-20134",
        "pr-hard:apache-tvm-19605",
        "pr-hard:apache-tvm-20153",
    }
    assert {record["repository"] for record in records} == {"apache/tvm"}
    kinds = {record["task_id"]: record["candidate_kind"] for record in records}
    assert kinds == {
        "pr-hard:apache-tvm-20116": "single_agent_calibration",
        "pr-hard:apache-tvm-20134": "single_agent_calibration",
        "pr-hard:apache-tvm-19605": "multi_agent_benchmark_candidate",
        "pr-hard:apache-tvm-20153": "multi_agent_benchmark_candidate",
    }


def test_base_and_gold_provenance_is_pinned() -> None:
    records = {record["task_id"]: record for record in load_records()}
    older = records["pr-hard:apache-tvm-20116"]
    newer = records["pr-hard:apache-tvm-20134"]
    pipeline = records["pr-hard:apache-tvm-19605"]
    ptx = records["pr-hard:apache-tvm-20153"]

    assert older["base_sha"] == "e85fbb1fa93d7e417fa20d5c48925b6665daeeee"
    assert older["gold_sha"] == "3dea168fe20d6ea5c0d42de2b3fb4ad021fe5cf1"
    assert newer["base_sha"] == older["gold_sha"]
    assert newer["gold_sha"] == "cec83d1badecf35ba73dc206dc5d206ad4eea12e"
    assert pipeline["base_sha"] == "e159487b0e4131b6874622bf03c546e837ae84c6"
    assert pipeline["gold_sha"] == "ec3171ab7a4c06fff4e9c1e441d28ef4e9a5831b"
    assert ptx["base_sha"] == "a35aca6a0ae5a61c486cb9a61c36b09be45f81af"
    assert ptx["gold_sha"] == "f20fa692d5dd71d875a9e310eae3e754169888fb"

    for record in records.values():
        assert re.fullmatch(r"[0-9a-f]{40}", str(record["base_sha"]))
        assert re.fullmatch(r"[0-9a-f]{40}", str(record["gold_sha"]))


def test_public_overlays_are_checksum_pinned_and_test_only() -> None:
    for record in load_records():
        targets: set[str] = set()
        for overlay in overlay_specs(record):
            overlay_path = ROOT / overlay["path"]
            patch_bytes = overlay_path.read_bytes()
            assert hashlib.sha256(patch_bytes).hexdigest() == overlay["sha256"]
            overlay_targets = patch_targets(patch_bytes.decode("utf-8"))
            assert targets.isdisjoint(overlay_targets)
            targets.update(overlay_targets)
        assert targets == set(record["public_test_paths"])
        assert all(path.startswith("tests/") for path in targets)
        assert not targets.intersection(record["editable_paths"])


def test_candidate_eligibility_matches_natural_decomposition() -> None:
    for record in load_records():
        if record["candidate_kind"] == "single_agent_calibration":
            assert record["qualification_status"].startswith("pending_")
            assert record["execution_eligibility"] == ["iterative_single_agent"]
            hypothesis = record["natural_responsibility_hypothesis"]
            assert hypothesis["status"] == (
                "not_admissible_for_current_path_owned_async_conditions"
            )
        else:
            if record["qualification_status"] == "pending_human_review":
                assert record["execution_eligibility"] == [
                    "iterative_single",
                    "serial_specialists",
                    "async_private",
                    "async_message",
                ]
            else:
                assert record["qualification_status"] == "needs_revision"
                assert record["execution_eligibility"] == []
            assert len(record["natural_subproblems"]) == 3
            assert len(record["dependency_points"]) == 2


def test_multi_agent_ownership_is_disjoint_and_complete() -> None:
    for record in load_records():
        if record["candidate_kind"] != "multi_agent_benchmark_candidate":
            continue

        owned: set[str] = set()
        subproblem_ids = set()
        for subproblem in record["natural_subproblems"]:
            paths = set(subproblem["writable_paths"])
            assert owned.isdisjoint(paths)
            owned.update(paths)
            subproblem_ids.add(subproblem["subproblem_id"])
        assert owned == set(record["editable_paths"])

        for dependency in record["dependency_points"]:
            assert dependency["producer_subproblem"] in subproblem_ids
            assert dependency["consumer_subproblem"] in subproblem_ids
            producer = dependency["producer_subproblem"]
            consumer = dependency["consumer_subproblem"]
            assert producer != consumer
            assert dependency["upstream_evidence"]
            assert dependency["downstream_evidence"]
            assert dependency["integrated_evidence"]
            assert all(
                "::" in selector
                for group in (
                    dependency["upstream_evidence"],
                    dependency["downstream_evidence"],
                    dependency["integrated_evidence"],
                )
                for selector in group
            )


def test_multi_agent_scenario_manifests_match_v03_execution_contract() -> None:
    schema = json.loads(SCENARIO_SCHEMA.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    expected_modes = {
        "iterative_single",
        "serial_specialists",
        "async_private",
        "async_message",
    }

    for record in load_records():
        if record["candidate_kind"] != "multi_agent_benchmark_candidate":
            continue

        manifest = json.loads((ROOT / record["scenario_manifest"]).read_text())
        scenarios = manifest["scenarios"]
        assert manifest["task_id"] == record["task_id"]
        assert {scenario["execution_mode"] for scenario in scenarios} == expected_modes
        assert len(scenarios) == 4

        role_paths = {
            subproblem["subproblem_id"]: set(subproblem["writable_paths"])
            for subproblem in record["natural_subproblems"]
        }
        budgets = set()
        for scenario in scenarios:
            validator.validate(scenario)
            assert scenario["task_id"] == record["task_id"]
            assert scenario["official_result_eligible"] is False
            budgets.add(
                (
                    scenario["step_budget_per_agent"],
                    scenario["token_budget_per_agent"],
                    scenario["test_budget_per_agent"],
                    scenario["wall_clock_budget_seconds"],
                )
            )
            if scenario["execution_mode"] == "iterative_single":
                assert scenario["agent_count"] == 1
                assert set(scenario["assignments"][0]["writable_paths"]) == set(
                    record["editable_paths"]
                )
            else:
                assert scenario["agent_count"] == 3
                assignments = {
                    assignment["subproblem_id"]: set(assignment["writable_paths"])
                    for assignment in scenario["assignments"]
                }
                assert assignments == role_paths
        assert len(budgets) == 1


def test_execution_eligible_candidates_have_task_and_metrics_manifests() -> None:
    for record in load_records():
        if record.get("qualification_status") != "pending_human_review":
            continue
        task_stem = record["task_id"].removeprefix("pr-hard:").replace("-", "_")
        task_path = (
            ROOT / "manifests/candidates/pr_hard_v0.4/tasks" / f"{task_stem}.json"
        )
        metrics_path = (
            ROOT
            / "manifests/candidates/pr_hard_v0.4/metrics"
            / f"{task_stem}_async_metrics.json"
        )
        task = json.loads(task_path.read_text())
        metrics = json.loads(metrics_path.read_text())
        assert task["task_id"] == record["task_id"]
        assert metrics["task_id"] == record["task_id"]
        assert task["qualification_status"] == "pending_human_review"
        assert {
            dependency["dependency_id"] for dependency in metrics["dependency_points"]
        } == {dependency["dependency_id"] for dependency in record["dependency_points"]}
        assert set(metrics["aggregate_metrics"]["primary_async_dependency_ids"]) == {
            dependency["dependency_id"] for dependency in record["dependency_points"]
        }


def test_model_visible_statements_do_not_expose_gold_identifiers() -> None:
    for record in load_records():
        statement = str(record["problem_statement"])
        assert str(record["pull_request_number"]) not in statement
        assert str(record["base_sha"]) not in statement
        assert str(record["gold_sha"]) not in statement
        for overlay in overlay_specs(record):
            patch_text = (ROOT / overlay["path"]).read_text()
            assert str(record["pull_request_number"]) not in patch_text
            assert str(record["base_sha"]) not in patch_text
            assert str(record["gold_sha"]) not in patch_text


def test_automated_qualification_records_encode_passes_and_blockers() -> None:
    schema = json.loads(QUALIFICATION_SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    for record in load_records():
        if record["candidate_kind"] != "multi_agent_benchmark_candidate":
            continue
        qualification = json.loads((ROOT / record["qualification_record"]).read_text())
        validator.validate(qualification)
        assert qualification["task_id"] == record["task_id"]
        assert qualification["provenance"]["base_sha"] == record["base_sha"]
        assert qualification["provenance"]["gold_sha"] == record["gold_sha"]
        if record["qualification_status"] == "pending_human_review":
            assert qualification["automated_status"] == "passed_pending_human_review"
            assert qualification["remaining_gates"] == ["human_review"]
            assert all(
                checker[group] == "passed"
                for checker in qualification["dependency_checkers"]
                for group in ("upstream", "downstream", "integrated")
            )
            assert {
                role["subproblem_id"]
                for role in qualification["role_local_observability"]
            } == {
                subproblem["subproblem_id"]
                for subproblem in record["natural_subproblems"]
            }
            assert all(
                role["base_status"] == "base_red"
                for role in qualification["role_local_observability"]
            )
            runtime = qualification["runtime_package_validation"]
            assert runtime["seed_commit_count"] == 1
            assert runtime["seed_has_remotes"] is False
            assert runtime["task_local_ffi_editable"] is False
            assert runtime["base_focused"]["failed"] > 0
            assert runtime["gold_regression"]["passed"] > 0
        else:
            assert record["qualification_status"] == "needs_revision"
            assert qualification["automated_status"] == "needs_revision"
            assert qualification["blocking_findings"]
            assert qualification["remaining_gates"] != ["human_review"]
            assert any(
                checker[group] != "passed"
                for checker in qualification["dependency_checkers"]
                for group in ("upstream", "downstream", "integrated")
            )
            assert any(
                role["base_status"] != "base_red"
                for role in qualification["role_local_observability"]
            )
        assert {
            checker["dependency_id"] for checker in qualification["dependency_checkers"]
        } == {dependency["dependency_id"] for dependency in record["dependency_points"]}
        stages = {run["stage"]: run for run in qualification["evaluator_runs"]}
        assert stages["base_focused"]["expected"] == "red"
        assert stages["base_focused"]["exit_code"] == 1
        assert stages["gold_focused"]["expected"] == "green"
        assert stages["gold_focused"]["exit_code"] == 0
        assert stages["gold_regression"]["exit_code"] == 0


def test_qualification_environment_locks_are_checksum_pinned() -> None:
    environment = json.loads(ENVIRONMENT.read_text(encoding="utf-8"))
    assert environment["status"] == "automated_qualification_frozen"
    for lock in environment["common"]["locks"]:
        lock_bytes = (ROOT / lock["path"]).read_bytes()
        assert hashlib.sha256(lock_bytes).hexdigest() == lock["sha256"]
    for profile in environment["profiles"].values():
        assert "-DUSE_GTEST=OFF" in profile["configure"]
        assert profile["requires_gpu_execution"] is False


def test_pr_hard_python_lock_contains_runtime_build_and_report_dependencies() -> None:
    requirements = {
        line.strip()
        for line in REQUIREMENTS_LOCK.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    }
    assert "Cython==3.3.0" in requirements
    assert "pytest-json-report==1.5.0" in requirements
    assert "pytest-metadata==3.1.1" in requirements


def test_preparation_helper_validates_and_lists_registry() -> None:
    completed = subprocess.run(
        [sys.executable, str(PREPARE), "--config", str(CONFIG)],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "pr-hard:apache-tvm-20116" in completed.stdout
    assert "pr-hard:apache-tvm-20134" in completed.stdout
    assert "pr-hard:apache-tvm-19605" in completed.stdout
    assert "pr-hard:apache-tvm-20153" in completed.stdout


def test_runtime_preparation_helper_has_offline_check_mode() -> None:
    completed = subprocess.run(
        [sys.executable, str(PREPARE_RUNTIME), "--help"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "--check" in completed.stdout
    assert "--runtime-root" in completed.stdout
    assert "pr-hard:apache-tvm-20153" in completed.stdout


def test_runtime_seed_flattens_nested_git_metadata_and_tracks_public_sources(
    tmp_path: Path,
) -> None:
    spec = importlib.util.spec_from_file_location(
        "prepare_pr_hard_runtime", PREPARE_RUNTIME
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    source = tmp_path / "source"
    nested = source / "3rdparty/example"
    nested.mkdir(parents=True)
    (source / ".git").mkdir()
    (nested / ".git").write_text("gitdir: /not/model/visible\n", encoding="utf-8")
    (nested / ".gitignore").write_text("generated.py\n", encoding="utf-8")
    (nested / "generated.py").write_text("PUBLIC = True\n", encoding="utf-8")

    seed = tmp_path / "seed"
    module.create_seed(source, seed)

    assert not (nested.relative_to(source) / ".git").is_absolute()
    assert not (seed / "3rdparty/example/.git").exists()
    tracked = subprocess.run(
        ["git", "-C", str(seed), "ls-files"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    assert "3rdparty/example/generated.py" in tracked
    assert (
        subprocess.run(
            ["git", "-C", str(seed), "rev-list", "--all", "--count"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        == "1"
    )
