"""Regression tests for the immutable-artifact / event-safe Async-Manager revision."""

import hashlib
import json
import os
import subprocess
import sys
import tarfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import core.subagent as scheduler
import pytest
from protocols.async_manager.checkpoint_bridge import online_checkpoint_bridge
from protocols.async_manager.manager import OnlineManager
from protocols.async_manager.timeouts import manager_timeout
from test_async_manager_protocol import (
    FakeTask,
    LocalWorkspace,
    git,
    initialize_repository,
)


def manager_fixture(tmp_path):
    root = tmp_path / "repo"
    base = initialize_repository(root)
    worker = tmp_path / "worker"
    git(root, "worktree", "add", "-b", "worker", str(worker), base)
    output = tmp_path / "out"
    output.mkdir()
    m = OnlineManager.__new__(OnlineManager)
    m.repo_dir = str(root)
    m.manager_worktree = str(worker)
    m.workspace = LocalWorkspace()
    m.task = FakeTask()
    m.task.should_stash_before_merge = False
    m.config = SimpleNamespace(output_dir=str(output))
    m.log = lambda *a: None
    m.output_logger = None
    m.intervention_sequence = 0
    m.intervention_records = []
    m.pending_integration_event = None
    m.active_scenario = lambda: {
        "assignments": [
            {
                "subproblem_id": "producer",
                "writable_paths": ["pkg"],
                "primary_test_targets": ["tests/test_pkg.py"],
            }
        ]
    }
    result = SimpleNamespace(
        engineer_id="engineer_1",
        task_id="producer",
        round_num=1,
        file_path="pkg",
        files_modified=["pkg/module.py"],
        worktree_path=str(worker),
        branch_name="worker",
        commit_hash="",
        success=True,
        error="",
        merged=False,
    )
    return m, root, worker, result, base


def commit(worker, text="VALUE = 2\n"):
    (worker / "pkg/module.py").write_text(text)
    git(worker, "add", "pkg/module.py")
    git(worker, "commit", "-qm", "implementation")
    return git(worker, "rev-parse", "HEAD")


def test_committed_artifact_ignores_and_archives_untracked_scratch(tmp_path):
    m, root, worker, r, base = manager_fixture(tmp_path)
    r.commit_hash = commit(worker)
    (worker / "spec.pdf").write_bytes(b"private scratch")
    review = m.collect_and_merge(r)
    assert review["merged"]
    assert git(root, "rev-parse", "HEAD") == r.commit_hash
    assert not (root / "spec.pdf").exists()
    archive = m.artifact_records[0]["uncommitted_archive"]["artifacts"][
        "untracked.tar.gz"
    ]["path"]
    with tarfile.open(Path(m.config.output_dir) / archive) as stream:
        assert stream.extractfile("spec.pdf").read() == b"private scratch"


def test_scope_gate_rejects_actual_foreign_commit(tmp_path):
    m, root, worker, r, base = manager_fixture(tmp_path)
    (worker / "forbidden.py").write_text("VALUE = 1\n")
    git(worker, "add", ".")
    git(worker, "commit", "-qm", "out of scope")
    r.commit_hash = git(worker, "rev-parse", "HEAD")
    assert not m.collect_and_merge(r)["merged"]
    assert git(root, "rev-parse", "HEAD") == base


def test_merge_uses_pinned_commit_when_branch_moves(tmp_path):
    m, root, worker, r, base = manager_fixture(tmp_path)
    r.commit_hash = commit(worker)
    original_merge = m.merge_branch

    def race(ref):
        commit(worker, "VALUE = 999\n")
        return original_merge(ref)

    m.merge_branch = race
    assert m.collect_and_merge(r)["merged"]
    assert (root / "pkg/module.py").read_text() == "VALUE = 2\n"


def test_uncommitted_recovery_uses_isolated_index_and_only_scope(tmp_path):
    m, root, worker, r, base = manager_fixture(tmp_path)
    (worker / "pkg/module.py").write_text("VALUE = 3\n")
    (worker / "forbidden.py").write_text("PRIVATE = 1\n")
    git(worker, "add", ".")
    old_index = git(worker, "write-tree")
    assert m.collect_and_merge(r)["merged"]
    assert git(worker, "write-tree") == old_index
    assert not (root / "forbidden.py").exists()
    assert (root / "pkg/module.py").read_text() == "VALUE = 3\n"


def test_refresh_archives_staged_unstaged_and_untracked(tmp_path):
    m, root, worker, r, base = manager_fixture(tmp_path)
    (worker / "pkg/module.py").write_text("STAGED = 1\n")
    git(worker, "add", ".")
    (worker / "pkg/module.py").write_text("UNSTAGED = 2\n")
    (worker / "pkg/new.py").write_text("NEW = 3\n")
    record = m._refresh_triggering_specialist({"subagent_result": r}, base, 1)
    parts = record["archive_manifest"]["artifacts"]
    assert (
        "STAGED = 1"
        in (Path(m.config.output_dir) / parts["staged.patch"]["path"]).read_text()
    )
    assert (
        "UNSTAGED = 2"
        in (Path(m.config.output_dir) / parts["unstaged.patch"]["path"]).read_text()
    )
    with tarfile.open(
        Path(m.config.output_dir) / parts["untracked.tar.gz"]["path"]
    ) as stream:
        assert stream.extractfile("pkg/new.py").read() == b"NEW = 3\n"
    assert not git(worker, "status", "--porcelain")


def test_archive_failure_refuses_to_reset(tmp_path, monkeypatch):
    m, root, worker, r, base = manager_fixture(tmp_path)
    (worker / "pkg/module.py").write_text("KEEP = 42\n")
    monkeypatch.setattr(
        "protocols.async_manager.manager.archive_worktree",
        lambda *a: (_ for _ in ()).throw(OSError("archive disk full")),
    )
    with pytest.raises(OSError):
        m._refresh_triggering_specialist({"subagent_result": r}, base, 1)
    assert (worker / "pkg/module.py").read_text() == "KEEP = 42\n"


def candidate_fixture(tmp_path):
    m, root, worker, r, base = manager_fixture(tmp_path)
    (worker / "pkg/module.py").write_text("VALUE = 2\n")
    patch = m._write_patch(1, base, ["pkg/module.py"])
    selector = "tests/test_pkg.py::test_dep"
    metrics = tmp_path / "metrics.json"
    metrics.write_text(
        json.dumps(
            {
                "dependency_points": [
                    {
                        "dependency_id": "dep",
                        "producer_files": ["pkg"],
                        "consumer_files": [],
                        "producer_subproblem": "producer",
                        "integrated_probe_tests": [selector],
                    }
                ]
            }
        )
    )
    m.task.manifest_paths = {"metrics": str(metrics)}
    m.candidate_patch_validation = {"enabled": True}
    kwargs = dict(
        sequence=1,
        event={
            "specialist_checkpoint": {
                "probe_test_results": {selector: {"passed": True}}
            }
        },
        changed=["pkg/module.py"],
        head_before=base,
        patch_sha=hashlib.sha256(patch.read_bytes()).hexdigest(),
        termination_reason="iteration_limit",
    )
    return m, worker, kwargs, selector


def test_validation_rejects_same_path_unstaged_mutation(tmp_path):
    m, worker, kwargs, selector = candidate_fixture(tmp_path)

    def probe(*a):
        (worker / "pkg/module.py").write_text("VALUE = 999\n")
        return {
            "exit_code": 0,
            "timed_out": False,
            "summary": {"not_collected": 0},
            "selector_results": {selector: {"passed": True}},
        }

    m._run_candidate_dependency_probes = probe
    record = m._validate_candidate_patch(**kwargs)
    assert not record["passed"]
    assert "candidate_worktree_changed_during_validation" in record["reason_codes"]


def test_directory_scope_and_identical_candidate_are_accepted(tmp_path):
    m, worker, kwargs, selector = candidate_fixture(tmp_path)
    m._run_candidate_dependency_probes = lambda *a: {
        "exit_code": 0,
        "timed_out": False,
        "summary": {"not_collected": 0},
        "selector_results": {selector: {"passed": True}},
    }
    record = m._validate_candidate_patch(**kwargs)
    assert record["passed"], record
    assert record["candidate_tree"] == git(worker, "write-tree")


@pytest.mark.parametrize("failure", ["checkpoint", "intervention"])
def test_event_exception_does_not_poison_following_result(
    tmp_path, monkeypatch, failure
):
    m, root, worker, r, base = manager_fixture(tmp_path)
    count = 0

    def writer(**kw):
        nonlocal count
        count += 1
        if count == 1 and failure == "checkpoint":
            raise TimeoutError("probe timed out")
        return kw

    monkeypatch.setattr(scheduler, "write_dependency_probe_checkpoint", writer)

    def intervention(event):
        m.intervention_sequence += 1
        if m.intervention_sequence == 1:
            raise RuntimeError("intervention failed")
        return {
            "sequence": m.intervention_sequence,
            "accepted": False,
            "status": "no_change",
        }

    m.intervene = intervention
    OnlineManager.active_instance = m
    with online_checkpoint_bridge():
        for index in [1, 2]:
            m.pending_integration_event = {"subagent_result": r, "collect_result": {}}
            scheduler.write_dependency_probe_checkpoint(
                checkpoint_type="integration_after_merge",
                checkpoint_id=f"integration:{index}",
                logical_step=index,
            )
            assert m.pending_integration_event is None
    assert [row["sequence"] for row in m.intervention_records] == [1, 2]
    assert m.intervention_records[0]["status"] == "execution_error"
    assert m.intervention_records[1]["status"] == "no_change"


def test_manager_timeout_does_not_leak_to_worker_thread(monkeypatch):
    monkeypatch.setattr(scheduler, "conversation_run_timeout", lambda: 3600)
    with online_checkpoint_bridge():
        token = manager_timeout.set(12)
        try:
            assert scheduler.conversation_run_timeout() == 12
            with ThreadPoolExecutor(1) as pool:
                assert pool.submit(scheduler.conversation_run_timeout).result() == 3600
        finally:
            manager_timeout.reset(token)
    assert scheduler.conversation_run_timeout() == 3600


@pytest.mark.parametrize("passed", [False, True])
def test_partial_repair_preserves_work_until_primary_tests_pass(tmp_path, passed):
    m, root, worker, r, base = manager_fixture(tmp_path)
    (worker / "pkg/module.py").write_text("KEEP = 42\n")
    target = "tests/test_pkg.py"
    m._run_candidate_dependency_probes = lambda *a: {
        "exit_code": 0 if passed else 1,
        "timed_out": False,
        "selector_results": {target: {"passed": passed}},
    }
    m._changed_paths = lambda: []
    calls = []
    m._refresh_triggering_specialist = lambda *a: calls.append(a) or {"refreshed": True}
    conflicts = ["pkg/module.py"]
    event = {
        "subagent_result": r,
        "collect_result": {"merged": False, "conflict_files": conflicts},
    }
    record = {"sequence": 1, "manager_commit": base}
    m.reconcile_specialist_after_repair(event, record)
    assert r.merged is passed
    assert bool(calls) is passed
    assert record["specialist_resolution"]["original_integration"]["merged"] is False
    if passed:
        assert conflicts == []
    else:
        assert (worker / "pkg/module.py").read_text() == "KEEP = 42\n"


def test_file_selector_matches_all_parameterized_tests():
    report = {
        "tests": [
            {"nodeid": "test.py::test_x[0]", "outcome": "passed"},
            {"nodeid": "test.py::test_x[1]", "outcome": "failed"},
        ]
    }
    assert not OnlineManager._probe_selector_results(report, ["test.py"])["test.py"][
        "passed"
    ]


def test_source_sync_refreshes_native_runtime(tmp_path):
    m, root, worker, r, base = manager_fixture(tmp_path)
    calls = []
    m.task.refresh_source_build = lambda *a: calls.append(a) or {"status": "passed"}
    m._sync_manager_worktree(base)
    assert calls == [(m.workspace, str(worker))]


def test_runtime_origin_check_rejects_foreign_module(monkeypatch):
    import sys

    from run_async_manager import assert_runtime_source_origins

    monkeypatch.setitem(
        sys.modules, "core.foreign", SimpleNamespace(__file__="/tmp/foreign.py")
    )
    with pytest.raises(RuntimeError, match="Cross-checkout"):
        assert_runtime_source_origins()


def test_invalid_bundles_are_not_counted_as_model_failures():
    from protocols.async_manager.campaign import summarize

    row = {
        "task_id": "one",
        "directory": "/valid",
        "policy": "v2",
        "final_success": True,
        "resolved_dependencies": 2,
        "dependency_count": 2,
        "manager_intervention_events": 1,
        "manager_interventions_accepted": 1,
        "ADPR": 1,
        "final_pass_rate": 1,
    }
    invalid = {
        **row,
        "task_id": "two",
        "directory": "/invalid",
        "final_success": False,
        "resolved_dependencies": 0,
        "ADPR": 0,
        "final_pass_rate": 0,
    }
    summary = summarize([row, invalid], {"/invalid": ["checkpoint_missing"]})
    assert not summary["valid"]
    assert summary["task_count"] == 1
    assert summary["excluded_task_count"] == 1
    assert summary["metrics"]["FSR_higher_is_better"] == 1
    assert summary["metric_scope"] == "validated_subset"


def test_duplicate_tasks_are_not_best_of_selected():
    from protocols.async_manager.campaign import summarize

    summary = summarize([{"task_id": "one"}, {"task_id": "one"}], {})
    assert not summary["valid"]
    assert summary["excluded_task_count"] == 2
    assert summary["metrics"]["FSR_higher_is_better"] is None


def test_unknown_shutdown_status_is_not_confirmation(tmp_path):
    from test_async_manager_budget import bare_manager

    m = bare_manager(tmp_path)
    m.manager_shutdown_grace = 0
    called = []
    m.conversation = SimpleNamespace(
        _poll_status_once=lambda: None, interrupt=lambda: called.append(True)
    )
    record = m._interrupt_and_confirm("test")
    assert called
    assert not record["confirmed"]


def test_budget_archive_failure_does_not_discard_private_changes(tmp_path, monkeypatch):
    from protocols.async_manager.budget import BudgetedOnlineManager

    m, root, worker, result, base = manager_fixture(tmp_path)
    (worker / "pkg/module.py").write_text("KEEP = 42\n")
    monkeypatch.setattr(
        "protocols.async_manager.artifacts.archive_worktree",
        lambda *a: (_ for _ in ()).throw(OSError("disk full")),
    )
    with pytest.raises(OSError):
        BudgetedOnlineManager._archive_and_discard_partial_manager_changes(m, "timeout")
    assert (worker / "pkg/module.py").read_text() == "KEEP = 42\n"


def test_runtime_hook_builds_before_tests_and_denies_build_failure(tmp_path):
    from protocols.async_manager.runtime import runtime_command
    from test_async_manager_protocol import run_hook

    event = {
        "tool_name": "terminal",
        "tool_input": {"command": "python -m pytest tests"},
    }
    assert (
        run_hook(runtime_command(str(tmp_path), "true"), event)["decision"] == "allow"
    )
    assert (
        run_hook(runtime_command(str(tmp_path), "false"), event)["decision"] == "deny"
    )
    assert (
        run_hook(
            runtime_command(str(tmp_path), "false"),
            {"tool_name": "terminal", "tool_input": {"command": "git status"}},
        )["decision"]
        == "allow"
    )


def test_missing_intervention_is_detected_by_new_profile(tmp_path, monkeypatch):
    import protocols.async_manager.results as results

    monkeypatch.setattr(results.v1_results, "validate", lambda *a, **k: [])
    monkeypatch.setattr(results.v1_results, "_load_interventions", lambda *a: [])
    monkeypatch.setattr(results, "_budget_issues", lambda *a: [])
    (tmp_path / "async_manager_profile_snapshot.json").write_text(
        json.dumps({"event_completeness_required": True})
    )
    (tmp_path / "dependency_probe_checkpoints.jsonl").write_text(
        json.dumps(
            {
                "checkpoint_id": "integration_after_merge:e1:round1",
                "checkpoint_type": "integration_after_merge",
            }
        )
        + "\n"
    )
    (tmp_path / "scope_validation.jsonl").write_text("{}\n")
    issues = results.validate(tmp_path, verify_inventory=False)
    assert "manager_intervention_checkpoint_coverage_mismatch" in issues
    assert "manager_intervention_artifact_coverage_mismatch" in issues


def test_result_lost_before_collection_cannot_be_a_valid_run(tmp_path, monkeypatch):
    import protocols.async_manager.results as results

    monkeypatch.setattr(results.v1_results, "validate", lambda *a, **k: [])
    monkeypatch.setattr(results.v1_results, "_load_interventions", lambda *a: [])
    monkeypatch.setattr(results, "_budget_issues", lambda *a: [])
    (tmp_path / "async_manager_profile_snapshot.json").write_text(
        json.dumps({"event_completeness_required": True})
    )
    (tmp_path / "dependency_probe_checkpoints.jsonl").write_text("")
    (tmp_path / "scope_validation.jsonl").write_text("")
    (tmp_path / "outputs.jsonl").write_text(
        json.dumps(
            {
                "event_type": "agent_response",
                "source": "engineer_1",
                "target": "manager",
                "round_num": 1,
                "content": {"task_id": "producer"},
            }
        )
        + "\n"
    )
    assert "specialist_result_collection_coverage_mismatch" in results.validate(
        tmp_path, verify_inventory=False
    )


@pytest.mark.parametrize("value,accepted", [(2, True), (9, False)])
def test_real_pytest_candidate_gate(tmp_path, monkeypatch, value, accepted):
    """Exercise real Git + real pytest JSON reports, not a mocked probe result."""
    executable = os.environ.get("ASYNC_MANAGER_AUDIT_PYTHON", sys.executable)
    available = subprocess.run(
        [executable, "-c", "import pytest_jsonreport"], capture_output=True
    )
    if available.returncode:
        pytest.skip(
            "Set ASYNC_MANAGER_AUDIT_PYTHON to a runtime with pytest-json-report"
        )
    monkeypatch.setenv(
        "PATH", str(Path(executable).parent) + os.pathsep + os.environ["PATH"]
    )
    m, root, worker, result, base = manager_fixture(tmp_path)
    (root / "tests").mkdir()
    (root / "tests/test_pkg.py").write_text(
        "from pkg.module import VALUE\ndef test_dep():\n    assert VALUE == 2\n"
    )
    (root / ".gitignore").write_text("__pycache__/\n.pytest_cache/\n")
    git(root, "add", ".")
    git(root, "commit", "-qm", "canonical fixture tests")
    base = git(root, "rev-parse", "HEAD")
    git(worker, "reset", "--hard", base)
    (worker / "pkg/module.py").write_text(f"VALUE = {value}\n")
    patch = m._write_patch(1, base, ["pkg/module.py"])
    selector = "tests/test_pkg.py::test_dep"
    metrics = tmp_path / "metrics.json"
    metrics.write_text(
        json.dumps(
            {
                "dependency_points": [
                    {
                        "dependency_id": "dep",
                        "producer_files": ["pkg/module.py"],
                        "consumer_files": [],
                        "integrated_probe_tests": [selector],
                    }
                ]
            }
        )
    )
    m.task.manifest_paths = {"metrics": str(metrics)}
    m.candidate_patch_validation = {"enabled": True}
    validation = m._validate_candidate_patch(
        sequence=1,
        event={
            "specialist_checkpoint": {
                "probe_test_results": {selector: {"passed": True}}
            }
        },
        changed=["pkg/module.py"],
        head_before=base,
        patch_sha=hashlib.sha256(patch.read_bytes()).hexdigest(),
        termination_reason="iteration_limit",
    )
    assert validation["passed"] is accepted, validation
    assert validation["probe"]["selector_results"][selector]["passed"] is accepted
