#!/usr/bin/env python3
"""Reject infrastructure-invalid AsyncCodeBench run directories."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

REQUIRED_FILES = (
    "report.json",
    "cost.json",
    "runtime.txt",
    "dependency_probe_checkpoints.jsonl",
)
ERROR_PATTERNS = {
    "context_window": re.compile(
        r"ContextWindow|maximum context length|input_tokens.*max_tokens",
        re.IGNORECASE,
    ),
    "provider_or_transport": re.compile(
        r"LLMServiceUnavailableError|LLMBadRequestError|APIConnectionError|"
        r"(?:OpenAIException|InternalServerError)\s*-\s*Connection error|"
        r"(?:httpx|httpcore)\.(?:Connect|Read|Write|Pool)Error",
        re.IGNORECASE,
    ),
    "remote_execution_timeout": re.compile(
        r"Run timed out after .*conversation may still be running",
        re.IGNORECASE,
    ),
    "raw_tool_call": re.compile(r"<\|tool_call>"),
}


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def inspect_run(run_dir: Path) -> dict[str, object]:
    issues: list[str] = []
    observations: list[str] = []
    missing = [name for name in REQUIRED_FILES if not (run_dir / name).is_file()]
    if missing:
        issues.append("missing_artifacts:" + ",".join(missing))

    logs = sorted(run_dir.glob("run_*.log"))
    if len(logs) != 1:
        issues.append(f"run_log_count:{len(logs)}")

    report_path = run_dir / "report.json"
    evaluator_source = None
    if report_path.is_file():
        try:
            report = json.loads(read_text(report_path))
            evaluator_source = report.get("asynccodebench", {}).get(
                "final_evaluator_source"
            ) or report.get("metadata", {}).get("final_evaluator_source")
        except (json.JSONDecodeError, OSError) as exc:
            issues.append(f"invalid_report:{type(exc).__name__}")
        else:
            if evaluator_source != "asynccodebench_manifest":
                issues.append(f"wrong_evaluator:{evaluator_source}")
            canonical_restore = report.get("asynccodebench", {}).get(
                "canonical_test_restore", {}
            )
            if canonical_restore.get("restored_paths") or canonical_restore.get(
                "untracked_paths_removed"
            ):
                observations.append("canonical_test_paths_restored")

    scan_files = logs + sorted(run_dir.glob("*.jsonl"))
    scan_files += sorted((run_dir / "agent_events").glob("*.jsonl"))
    combined = "\n".join(read_text(path) for path in scan_files if path.is_file())
    for label, pattern in ERROR_PATTERNS.items():
        if pattern.search(combined):
            issues.append(label)
    if re.search(r"Remote conversation got stuck", combined, re.IGNORECASE):
        observations.append("model_trajectory_stuck")

    iteration_values = [
        int(value) for value in re.findall(r"Iterations used:\s*(\d+)", combined)
    ]
    single_stalled = not iteration_values or max(iteration_values) == 0
    if "_single_" in run_dir.name and single_stalled:
        issues.append("single_agent_zero_iterations")

    event_files = sorted((run_dir / "agent_events").glob("*.jsonl"))
    if not event_files:
        issues.append("missing_agent_events")
    elif not any(path.stat().st_size > 0 for path in event_files):
        issues.append("empty_agent_events")

    return {
        "run_dir": str(run_dir),
        "healthy": not issues,
        "issues": issues,
        "observations": observations,
        "evaluator_source": evaluator_source,
        "iterations_observed": iteration_values,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dirs", nargs="+", type=Path)
    parser.add_argument("--json-output", type=Path)
    args = parser.parse_args()

    results = [inspect_run(path) for path in args.run_dirs]
    payload = {"healthy": all(item["healthy"] for item in results), "runs": results}
    rendered = json.dumps(payload, indent=2)
    print(rendered)
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(rendered + "\n", encoding="utf-8")
    return 0 if payload["healthy"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
