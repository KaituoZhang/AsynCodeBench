from core import dependency_checker, dependency_probes
from core.subagent import task_metrics_manifest_path


def test_candidate_tasks_use_their_explicit_metrics_manifest() -> None:
    expected = "/candidate/metrics.json"
    task = type("Task", (), {"manifest_paths": {"metrics": expected}})()
    assert task_metrics_manifest_path(task) == expected
    assert task_metrics_manifest_path(object()) is None


def test_dependency_checker_facade_preserves_existing_implementation() -> None:
    assert (
        dependency_checker.write_dependency_checker_checkpoint
        is dependency_probes.write_dependency_probe_checkpoint
    )
    assert dependency_checker.default_metrics_path is dependency_probes.default_metrics_path
    assert dependency_checker.load_metrics_manifest is dependency_probes.load_metrics_manifest
    assert dependency_checker.next_checkpoint_step is dependency_probes.next_checkpoint_step
    assert dependency_checker.probe_timeout_seconds is dependency_probes.probe_timeout_seconds
