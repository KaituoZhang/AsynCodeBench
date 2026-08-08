import json
import os
import re
import shlex
from datetime import datetime
from pathlib import Path


def _repo_root():
    return Path(__file__).resolve().parents[3]


def default_metrics_path(repo_name):
    normalized = repo_name.replace("-", "_")
    return (
        _repo_root()
        / "manifests"
        / "pilot"
        / "v0.3"
        / "metrics"
        / f"commit0_{normalized}_async_metrics.json"
    )


def load_metrics_manifest(repo_name, metrics_path=None):
    path = Path(metrics_path) if metrics_path else default_metrics_path(repo_name)
    if not path.exists():
        return None, path
    with path.open("r", encoding="utf-8") as f:
        return json.load(f), path


def _all_probe_selectors(metrics):
    selectors = set()
    for dependency in metrics.get("dependency_points", []):
        for key in (
            "upstream_probe_tests",
            "downstream_probe_tests",
            "integrated_probe_tests",
        ):
            selectors.update(dependency.get(key, []))
    return sorted(selectors)


def _selector_statuses(report):
    by_nodeid = {}
    for test in report.get("tests", []) or []:
        nodeid = test.get("nodeid")
        outcome = test.get("outcome")
        if nodeid:
            by_nodeid[nodeid] = outcome
    return by_nodeid


def _selector_passed(selector, by_nodeid):
    matched = []
    for nodeid, outcome in by_nodeid.items():
        if nodeid == selector or re.sub(r"\[[^\]]+\]$", "", nodeid) == selector:
            matched.append(outcome)
    if not matched:
        return {
            "status": "not_collected",
            "passed": False,
            "matched_nodeids": [],
        }
    return {
        "status": "passed" if all(outcome == "passed" for outcome in matched) else "failed",
        "passed": all(outcome == "passed" for outcome in matched),
        "matched_nodeids": [
            {"nodeid": nodeid, "outcome": outcome}
            for nodeid, outcome in by_nodeid.items()
            if nodeid == selector or re.sub(r"\[[^\]]+\]$", "", nodeid) == selector
        ],
    }


def _selector_timed_out(selector):
    return {
        "status": "timed_out",
        "passed": False,
        "matched_nodeids": [],
    }


def _dependency_group_statuses(metrics, probe_results):
    dependency_results = []
    for dependency in metrics.get("dependency_points", []):
        row = {
            "dependency_id": dependency.get("dependency_id"),
            "producer_agent": dependency.get("producer_agent"),
            "consumer_agent": dependency.get("consumer_agent"),
            "groups": {},
        }
        for group_name, selector_key in (
            ("upstream", "upstream_probe_tests"),
            ("downstream", "downstream_probe_tests"),
            ("integrated", "integrated_probe_tests"),
        ):
            selectors = dependency.get(selector_key, [])
            passed = bool(selectors) and all(
                probe_results.get(selector, {}).get("passed") for selector in selectors
            )
            row["groups"][group_name] = {
                "selectors": selectors,
                "passed": passed,
                "passed_count": sum(
                    1 for selector in selectors
                    if probe_results.get(selector, {}).get("passed")
                ),
                "total": len(selectors),
            }
        dependency_results.append(row)
    return dependency_results


def next_checkpoint_step(output_dir):
    checkpoints_path = Path(output_dir) / "dependency_probe_checkpoints.jsonl"
    if not checkpoints_path.exists():
        return 1
    with checkpoints_path.open("r", encoding="utf-8") as f:
        return sum(1 for line in f if line.strip()) + 1


def probe_timeout_seconds(timeout):
    raw_value = os.getenv("ASYNCODEBENCH_PROBE_TIMEOUT_SECONDS")
    if raw_value is None:
        return timeout
    try:
        parsed = int(raw_value)
    except ValueError:
        print(
            "[AsynCodeBench] Warning: invalid "
            f"ASYNCODEBENCH_PROBE_TIMEOUT_SECONDS={raw_value!r}; "
            f"using {timeout}"
        )
        return timeout
    return max(parsed, 30)


def _checkpoint_exit_code(probe_results):
    if any(result.get("status") == "timed_out" for result in probe_results.values()):
        return 124
    if all(result.get("passed") for result in probe_results.values()):
        return 0
    return 1


def _checkpoint_summary(probe_results):
    statuses = [result.get("status") for result in probe_results.values()]
    return {
        "total": len(statuses),
        "passed": statuses.count("passed"),
        "failed": statuses.count("failed"),
        "not_collected": statuses.count("not_collected"),
        "timed_out": statuses.count("timed_out"),
    }


def _run_one_selector_probe(
    workspace,
    *,
    selector,
    workspace_path,
    report_path,
    output_path,
    timeout,
):
    quoted_workspace = shlex.quote(workspace_path)
    quoted_selector = shlex.quote(selector)
    quoted_report = shlex.quote(report_path)
    quoted_output = shlex.quote(output_path)
    command = (
        f"cd {quoted_workspace} && "
        f"export PYTHONPATH={quoted_workspace}/src:{quoted_workspace}:$PYTHONPATH && "
        f"timeout {timeout}s python -m pytest "
        f"--json-report --json-report-file={quoted_report} "
        f"--continue-on-collection-errors {quoted_selector} "
        f"> {quoted_output} 2>&1"
    )
    run_result = workspace.execute_command(command, timeout=timeout + 30)
    report_result = workspace.execute_command(
        f"cat {quoted_report} 2>/dev/null || echo '{{}}'",
        timeout=30,
    )
    output_result = workspace.execute_command(
        f"cat {quoted_output} 2>/dev/null || true",
        timeout=30,
    )
    workspace.execute_command(
        f"rm -f {quoted_report} {quoted_output}",
        timeout=30,
    )

    try:
        report = json.loads(report_result.stdout or "{}")
    except json.JSONDecodeError:
        report = {}

    by_nodeid = _selector_statuses(report)
    timed_out = str(run_result.exit_code) in {"124", "-1"}
    if timed_out and not by_nodeid:
        probe_result = _selector_timed_out(selector)
    else:
        probe_result = _selector_passed(selector, by_nodeid)

    return {
        "exit_code": run_result.exit_code,
        "report": report,
        "output": output_result.stdout or "",
        "result": probe_result,
        "timed_out": timed_out,
    }


def write_dependency_probe_checkpoint(
    *,
    workspace,
    output_dir,
    repo_name,
    workspace_path,
    checkpoint_id,
    checkpoint_type,
    logical_step,
    agent_id=None,
    task_id=None,
    workspace_kind="agent_workspace",
    artifact_version=None,
    visible_upstream_artifact_version=None,
    integrated_workspace_version=None,
    metrics_path=None,
    timeout=60,
):
    if os.getenv("ASYNCODEBENCH_DISABLE_PROBE_CHECKPOINTS") == "1":
        return None

    metrics, resolved_metrics_path = load_metrics_manifest(repo_name, metrics_path)
    if not metrics:
        print(f"[AsynCodeBench] No metrics manifest found at {resolved_metrics_path}; skipping probe checkpoint")
        return None

    selectors = _all_probe_selectors(metrics)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    checkpoints_path = output_dir / "dependency_probe_checkpoints.jsonl"

    if not selectors:
        print("[AsynCodeBench] Metrics manifest has no probe selectors; skipping probe checkpoint")
        return None

    safe_id = re.sub(r"[^A-Za-z0-9_.-]+", "_", checkpoint_id)
    probe_timeout = probe_timeout_seconds(timeout)

    probe_results = {}
    selector_exit_codes = {}
    selector_timed_out = {}
    output_chunks = []
    for index, selector in enumerate(selectors):
        selector_safe_id = re.sub(r"[^A-Za-z0-9_.-]+", "_", f"{safe_id}_{index}")
        selector_report_path = f"/tmp/asyncodebench_probe_{selector_safe_id}.json"
        selector_output_path = f"/tmp/asyncodebench_probe_{selector_safe_id}.txt"
        selector_run = _run_one_selector_probe(
            workspace,
            selector=selector,
            workspace_path=workspace_path,
            report_path=selector_report_path,
            output_path=selector_output_path,
            timeout=probe_timeout,
        )
        probe_results[selector] = selector_run["result"]
        selector_exit_codes[selector] = selector_run["exit_code"]
        selector_timed_out[selector] = selector_run["timed_out"]
        output_chunks.append(
            f"\n--- selector: {selector} "
            f"(exit={selector_run['exit_code']}, "
            f"status={selector_run['result'].get('status')}) ---\n"
            f"{selector_run['output']}"
        )

    timed_out = any(selector_timed_out.values())
    checkpoint_exit_code = _checkpoint_exit_code(probe_results)
    checkpoint_summary = _checkpoint_summary(probe_results)
    dependency_results = _dependency_group_statuses(metrics, probe_results)

    checkpoint = {
        "schema_version": "0.1",
        "task_id": metrics.get("task_id", f"commit0:{repo_name}"),
        "metric_annotation_id": metrics.get("metric_annotation_id"),
        "metrics_manifest": str(resolved_metrics_path),
        "checkpoint_id": checkpoint_id,
        "checkpoint_type": checkpoint_type,
        "logical_step": logical_step,
        "recorded_at": datetime.now().isoformat(),
        "agent_id": agent_id,
        "task_assignment_id": task_id,
        "workspace_kind": workspace_kind,
        "workspace_path": workspace_path,
        "artifact_version": artifact_version,
        "visible_upstream_artifact_version": visible_upstream_artifact_version,
        "integrated_workspace_version": integrated_workspace_version,
        "pytest_exit_code": checkpoint_exit_code,
        "pytest_summary": checkpoint_summary,
        "probe_execution_mode": "per_selector",
        "probe_timeout_seconds": probe_timeout,
        "timed_out": timed_out,
        "selector_exit_codes": selector_exit_codes,
        "selector_timed_out": selector_timed_out,
        "probe_test_results": probe_results,
        "dependency_results": dependency_results,
        "test_output_excerpt": "".join(output_chunks)[-4000:],
    }

    with checkpoints_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(checkpoint, sort_keys=True) + "\n")

    passed_dependencies = sum(
        1
        for row in dependency_results
        if row["groups"]["integrated"]["passed"]
    )
    print(
        "[AsynCodeBench] Probe checkpoint "
        f"{checkpoint_id}: integrated {passed_dependencies}/{len(dependency_results)} "
        f"dependencies passed"
    )
    return checkpoint
