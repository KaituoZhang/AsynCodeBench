"""Classify run evidence without confusing coding failure with infra failure."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

REQUIRED_HEALTH_FILES = (
    "report.json",
    "cost.json",
    "runtime.txt",
    "dependency_probe_checkpoints.jsonl",
    "process_metrics_summary.json",
)

HARD_ERROR_PATTERNS = {
    "execution_error": re.compile(
        r'"termination_reason"\s*:\s*"execution_error"|'
        r"Termination:\s*execution_error",
        re.IGNORECASE,
    ),
    "openhands_event_schema_mismatch": re.compile(
        r"dynamic_context.{0,500}Extra inputs are not permitted|"
        r"Extra inputs are not permitted.{0,500}dynamic_context",
        re.IGNORECASE | re.DOTALL,
    ),
    "context_window_error": re.compile(
        r"LLMContextWindowExceed(?:ed)?Error|ContextWindowExceededError|"
        r"This model's maximum context length is \d+ tokens.*you requested",
        re.IGNORECASE,
    ),
    "provider_or_transport_error": re.compile(
        r"(?:LLMServiceUnavailableError|APIConnectionError|AuthenticationError|"
        r"RateLimitError)\s*(?::|-)|"
        r"OpenrouterException\s*-\s*Unable to get json response|"
        r"(?:OpenAIException|InternalServerError)\s*-\s*"
        r"Connection error|"
        r"(?:httpx|httpcore)\.(?:Connect|Read|Write|Pool)Error",
        re.IGNORECASE,
    ),
    "model_server_configuration_error": re.compile(
        r"LLM Provider NOT provided|auto.*tool choice requires|"
        r"tool-call-parser.*(?:required|unsupported|unknown)|"
        r"LLMBadRequestError:.*(?:tool choice|reasoning parser|provider)",
        re.IGNORECASE,
    ),
    "remote_execution_timeout": re.compile(
        r"Run timed out after .*conversation may still be running",
        re.IGNORECASE,
    ),
    "solution_source_leakage": re.compile(
        r"(?:api\.github\.com/repos/apache/tvm/pulls/\d+|"
        r"github\.com/apache/tvm/pull/\d+\.patch).{0,2000}"
        r"(?:bytes\s+\d+|IDENTICAL TO REFERENCE HEAD|byte-identical)",
        re.IGNORECASE | re.DOTALL,
    ),
}

MODEL_EVALUATOR_FAILURES = {"collection_failed", "timeout"}


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _read_json(path: Path, hard_failures: list[str], code: str) -> dict:
    try:
        value = json.loads(_read_text(path))
    except (OSError, json.JSONDecodeError):
        hard_failures.append(code)
        return {}
    if not isinstance(value, dict):
        hard_failures.append(code)
        return {}
    return value


def _read_jsonl(path: Path, hard_failures: list[str], code: str) -> list[dict]:
    records = []
    try:
        lines = _read_text(path).splitlines()
    except OSError:
        hard_failures.append(code)
        return records
    for line in lines:
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            hard_failures.append(code)
            return []
        if not isinstance(record, dict):
            hard_failures.append(code)
            return []
        records.append(record)
    if not records:
        hard_failures.append(code)
    return records


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _structured_error_text(run_dir: Path) -> str:
    """Extract only machine-owned error fields from execution records.

    Agent thoughts and terminal output legitimately discuss exception class
    names while debugging. Scanning those free-form fields caused healthy runs
    to be rejected when a model merely mentioned, for example,
    ``AuthenticationError``. Provider failures are therefore detected only
    from fields whose schema says they are an error or termination reason.
    """

    values: list[str] = []
    error_keys = {
        "error",
        "error_message",
        "exception",
        "termination_reason",
    }

    def collect(value, key: str | None = None) -> None:
        if isinstance(value, dict):
            for child_key, child_value in value.items():
                collect(child_value, str(child_key).lower())
        elif isinstance(value, list):
            for child in value:
                collect(child, key)
        elif key in error_keys and value is not None:
            values.append(str(value))

    for filename in ("outputs.jsonl", "agent_adapter_executions.jsonl"):
        path = run_dir / filename
        if not path.is_file():
            continue
        for line in _read_text(path).splitlines():
            if not line.strip():
                continue
            try:
                collect(json.loads(line))
            except json.JSONDecodeError:
                # Artifact validity is checked separately by inspect_run.
                continue
    for path in sorted((run_dir / "agent_events").glob("*.jsonl")):
        for line in _read_text(path).splitlines():
            if not line.strip():
                continue
            try:
                collect(json.loads(line))
            except json.JSONDecodeError:
                continue
    return "\n".join(values)


def _expected_probe_selectors(metrics: dict) -> set[str]:
    selectors = set()
    for dependency in metrics.get("dependency_points", []) or []:
        for key in (
            "upstream_probe_tests",
            "downstream_probe_tests",
            "integrated_probe_tests",
        ):
            selectors.update(dependency.get(key, []) or [])
    return selectors


def _model_execution_evidence(run_dir: Path, process_summary: dict, cost: dict) -> dict:
    model_calls = int(
        process_summary.get("cost_metrics", {}).get("model_calls", 0) or 0
    )
    total_tokens = int(cost.get("total", {}).get("total_tokens", 0) or 0)
    iterations = []

    outputs_path = run_dir / "outputs.jsonl"
    if outputs_path.is_file():
        try:
            output_records = [
                json.loads(line)
                for line in _read_text(outputs_path).splitlines()
                if line.strip()
            ]
        except json.JSONDecodeError:
            output_records = []
        for record in output_records:
            value = record.get("content", {}).get("actual_iterations")
            if isinstance(value, int):
                iterations.append(value)

    adapter_path = run_dir / "agent_adapter_executions.jsonl"
    if adapter_path.is_file():
        try:
            adapter_records = [
                json.loads(line)
                for line in _read_text(adapter_path).splitlines()
                if line.strip()
            ]
        except json.JSONDecodeError:
            adapter_records = []
        for record in adapter_records:
            value = record.get("response", {}).get("iterations")
            if isinstance(value, int):
                iterations.append(value)

    for log_path in run_dir.glob("run_*.log"):
        iterations.extend(
            int(value)
            for value in re.findall(r"Iterations used:\s*(\d+)", _read_text(log_path))
        )
    return {
        "model_calls": model_calls,
        "total_tokens": total_tokens,
        "iterations": iterations,
        "zero_iteration_run": bool(iterations) and not any(iterations),
        "observed": model_calls > 0 or total_tokens > 0 or any(iterations),
    }


def inspect_run(run_dir: Path) -> dict[str, object]:
    """Return machine-readable health, eligibility, and evidence for one run."""

    run_dir = Path(run_dir)
    hard_failures: list[str] = []
    review_flags: list[str] = []
    observations: list[str] = []

    missing = [name for name in REQUIRED_HEALTH_FILES if not (run_dir / name).is_file()]
    if missing:
        hard_failures.extend(f"missing_artifact:{name}" for name in missing)

    logs = sorted(run_dir.glob("run_*.log"))
    if len(logs) != 1:
        hard_failures.append(f"run_log_count:{len(logs)}")

    report = (
        _read_json(run_dir / "report.json", hard_failures, "invalid_report")
        if (run_dir / "report.json").is_file()
        else {}
    )
    report_metadata = report.get("asyncodebench", {})
    evaluator_source = report_metadata.get("final_evaluator_source")
    run_metadata = (
        _read_json(run_dir / "run_metadata.json", hard_failures, "invalid_run_metadata")
        if (run_dir / "run_metadata.json").is_file()
        else {}
    )
    candidate_lane = run_metadata.get("candidate_lane", {})
    expected_evaluator = (
        "pr_hard_v0.4_manifest"
        if candidate_lane.get("kind") == "pr_hard_v0.4"
        else "asyncodebench_manifest"
    )
    constraints = run_metadata.get("workspace_constraints")
    if candidate_lane.get("kind") == "pr_hard_v0.4" and isinstance(
        constraints, dict
    ):
        if constraints.get("cpu_limit") != 28:
            hard_failures.append("wrong_workspace_cpu_limit")
        if constraints.get("build_parallel_jobs") != 28:
            hard_failures.append("wrong_build_parallel_jobs")
        if not constraints.get("deny_agent_network"):
            hard_failures.append("missing_agent_network_guard")
        if constraints.get("agent_network_policy") != "agent-terminal-egress-v1":
            hard_failures.append("wrong_agent_network_policy")
    evaluator_eligible = True
    if evaluator_source != expected_evaluator:
        hard_failures.append(f"wrong_evaluator:{evaluator_source}")
        evaluator_eligible = False

    synthetic_summary = bool(report_metadata.get("synthetic_summary"))
    failure_kind = report_metadata.get("evaluation_failure_kind")
    summary = report.get("summary", {})
    collected = int(summary.get("collected", summary.get("total", 0)) or 0)
    failed_collectors = [
        collector
        for collector in report.get("collectors", []) or []
        if isinstance(collector, dict) and collector.get("outcome") == "failed"
    ]
    if synthetic_summary:
        if failure_kind in MODEL_EVALUATOR_FAILURES:
            observations.append(f"model_evaluator_failure:{failure_kind}")
        elif failure_kind == "no_tests_collected":
            review_flags.append("evaluator_no_tests_collected")
            evaluator_eligible = False
        else:
            hard_failures.append(f"evaluator_instrumentation_failure:{failure_kind}")
            evaluator_eligible = False
    elif failure_kind == "collection_failed" or failed_collectors:
        observations.append("model_evaluator_failure:collection_failed")
    elif collected <= 0:
        hard_failures.append("evaluator_zero_collected")
        evaluator_eligible = False

    canonical_restore = report_metadata.get("canonical_test_restore", {})
    if canonical_restore.get("restored_paths") or canonical_restore.get(
        "untracked_paths_removed"
    ):
        observations.append("canonical_test_paths_restored")

    process_summary = (
        _read_json(
            run_dir / "process_metrics_summary.json",
            hard_failures,
            "invalid_process_metrics_summary",
        )
        if (run_dir / "process_metrics_summary.json").is_file()
        else {}
    )
    cost = (
        _read_json(run_dir / "cost.json", hard_failures, "invalid_cost")
        if (run_dir / "cost.json").is_file()
        else {}
    )

    efficiency_eligible = bool(process_summary) and bool(cost)
    runtime_path = run_dir / "runtime.txt"
    if runtime_path.is_file():
        try:
            runtime_seconds = float(_read_text(runtime_path).strip())
        except ValueError:
            hard_failures.append("invalid_runtime")
            efficiency_eligible = False
        else:
            if runtime_seconds <= 0:
                hard_failures.append("nonpositive_runtime")
                efficiency_eligible = False
    else:
        runtime_seconds = None

    execution_evidence = _model_execution_evidence(run_dir, process_summary, cost)
    if execution_evidence["zero_iteration_run"]:
        hard_failures.append("zero_model_iterations")
        efficiency_eligible = False
    if not execution_evidence["observed"]:
        hard_failures.append("no_model_execution_evidence")
        efficiency_eligible = False

    event_files = sorted((run_dir / "agent_events").glob("*.jsonl"))
    adapter_execution = run_dir / "agent_adapter_executions.jsonl"
    if not any(path.stat().st_size > 0 for path in event_files) and not (
        adapter_execution.is_file() and adapter_execution.stat().st_size > 0
    ):
        hard_failures.append("missing_agent_execution_trace")

    scan_files = logs + [run_dir / "events.jsonl", run_dir / "outputs.jsonl"]
    scan_files += event_files
    if adapter_execution.is_file():
        scan_files.append(adapter_execution)
    combined = "\n".join(_read_text(path) for path in scan_files if path.is_file())
    structured_errors = _structured_error_text(run_dir)
    for code, pattern in HARD_ERROR_PATTERNS.items():
        haystack = (
            structured_errors
            if code == "provider_or_transport_error"
            else combined
        )
        if pattern.search(haystack):
            hard_failures.append(code)
    if re.search(r"Remote conversation got stuck", combined, re.IGNORECASE):
        observations.append("model_trajectory_stuck")
    if "<|tool_call>" in combined:
        observations.append("raw_tool_call_emitted")

    is_20018_caid = (
        run_metadata.get("task_id") == "pr-hard:apache-tvm-20018"
        and run_metadata.get("protocol") == "caid_manager"
    )
    if is_20018_caid:
        patch_path = run_dir / "patch.diff"
        if not patch_path.is_file():
            hard_failures.append("missing_patch_diff")
        else:
            patch_text = _read_text(patch_path)
            if "# Patch generation failed:" in patch_text:
                hard_failures.append("patch_generation_failed")
            elif "diff --git " in patch_text:
                patch_validation = subprocess.run(
                    ["git", "apply", "--numstat", str(patch_path.resolve())],
                    cwd=run_dir,
                    capture_output=True,
                    text=True,
                    timeout=30,
                    check=False,
                )
                if patch_validation.returncode != 0:
                    hard_failures.append("invalid_patch_diff")

        for filename, field in (
            ("scope_validation.jsonl", "main_workspace_status_before_merge"),
            ("manager_workspace_validation.jsonl", "main_workspace_status"),
        ):
            path = run_dir / filename
            if not path.is_file():
                continue
            records = _read_jsonl(path, hard_failures, f"invalid_{path.stem}")
            remediated = [
                record
                for record in records
                if record.get(field) and record.get("remediated")
            ]
            contaminated = [
                record
                for record in records
                if record.get(field) and not record.get("remediated")
            ]
            if remediated:
                observations.append(
                    f"manager_workspace_writes_rejected:{path.name}:{len(remediated)}"
                )
            if contaminated:
                hard_failures.append(
                    f"integrated_workspace_contamination:{path.name}:{len(contaminated)}"
                )

    checkpoints = (
        _read_jsonl(
            run_dir / "dependency_probe_checkpoints.jsonl",
            hard_failures,
            "invalid_dependency_checkpoints",
        )
        if (run_dir / "dependency_probe_checkpoints.jsonl").is_file()
        else []
    )
    dependency_eligible = bool(checkpoints)
    final_checkpoints = [
        record
        for record in checkpoints
        if record.get("checkpoint_type") == "final_integrated"
        or record.get("checkpoint_id") == "final_integrated"
    ]
    if checkpoints and not final_checkpoints:
        hard_failures.append("missing_final_integrated_checkpoint")
        dependency_eligible = False

    metrics = (
        _read_json(
            run_dir / "metrics_snapshot.json", hard_failures, "invalid_metrics_snapshot"
        )
        if (run_dir / "metrics_snapshot.json").is_file()
        else {}
    )
    expected_selectors = _expected_probe_selectors(metrics)
    if final_checkpoints:
        probe_results = final_checkpoints[-1].get("probe_test_results", {})
        if not isinstance(probe_results, dict):
            hard_failures.append("invalid_final_probe_results")
            dependency_eligible = False
        else:
            missing_selectors = sorted(expected_selectors - set(probe_results))
            if missing_selectors:
                hard_failures.append(
                    f"missing_final_probe_selectors:{len(missing_selectors)}"
                )
                dependency_eligible = False
            invalid_statuses = set()
            for result in probe_results.values():
                if not isinstance(result, dict):
                    invalid_statuses.add("not_an_object")
                    continue
                status_value = result.get("status")
                if status_value not in {
                    "passed",
                    "failed",
                    "not_collected",
                    "timed_out",
                }:
                    invalid_statuses.add(status_value)
            if invalid_statuses:
                hard_failures.append("invalid_final_probe_status")
                dependency_eligible = False

    hard_failures = _dedupe(hard_failures)
    review_flags = _dedupe(review_flags)
    observations = _dedupe(observations)
    if hard_failures:
        status = "invalid"
    elif review_flags:
        status = "review_required"
    else:
        status = "valid"

    eligibility = {
        "functional_metrics": evaluator_eligible
        and not any(
            item.startswith(("wrong_evaluator", "evaluator_instrumentation_failure"))
            for item in hard_failures
        ),
        "dependency_metrics": dependency_eligible,
        "efficiency_metrics": efficiency_eligible and execution_evidence["observed"],
    }
    return {
        "run_dir": str(run_dir),
        "status": status,
        "healthy": status == "valid",
        "hard_failures": hard_failures,
        "review_flags": review_flags,
        "issues": hard_failures + review_flags,
        "observations": observations,
        "eligibility": eligibility,
        "evaluator_source": evaluator_source,
        "model_execution": execution_evidence,
        "checkpoint_records": len(checkpoints),
        "final_collected": collected,
        "runtime_seconds": runtime_seconds,
    }
