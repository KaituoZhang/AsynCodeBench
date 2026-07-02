#!/usr/bin/env python
"""Aggregate AsyncCodeBench run-level process metrics.

This script intentionally follows the metric names in SPECIFICATION_v0.3.md and
COMMIT0_DATA_AND_METRIC_LABEL_GUIDE_v0.3.md. It consumes artifacts already
written by async-swe-agents runs plus dependency-resolution reports produced by
scripts/analyze_async_dependency_resolution.py.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


PYTEST_RE = re.compile(r"(pytest|test session starts|\d+\s+passed|\d+\s+failed)")
PASSED_RE = re.compile(r"(?P<passed>\d+)\s+passed\b")
FAILED_RE = re.compile(r"(?P<failed>\d+)\s+failed\b")
ERROR_RE = re.compile(r"(?P<error>\d+)\s+error(?:s)?\b")
ADDED_DEF_RE = re.compile(
    r"^\+\s*(?:async\s+def|def|class)\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)",
    re.MULTILINE,
)
IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]+")
CONTRACT_TOKEN_STOPWORDS = {
    "cache",
    "cached",
    "class",
    "clear",
    "contract",
    "decorator",
    "decorators",
    "function",
    "functions",
    "metadata",
    "method",
    "methods",
    "probe",
    "probes",
    "test",
    "tests",
    "wrapper",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Summarize primary outcome, cost metrics, dependency metrics "
            "(ADPR/DRS/CAIL/SAD), and v0.3 process metrics for one run."
        )
    )
    parser.add_argument(
        "--run-dir",
        type=Path,
        required=True,
        help="Run output directory containing report.json, cost.json, etc.",
    )
    parser.add_argument(
        "--metrics",
        type=Path,
        required=True,
        help="Async metrics manifest, e.g. commit0_cachetools_async_metrics.json.",
    )
    parser.add_argument(
        "--baseline-run-dir",
        type=Path,
        default=None,
        help=(
            "Optional serial/single baseline run directory for "
            "serial-to-async performance deltas."
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Path for the aggregated process-metrics JSON.",
    )
    parser.add_argument(
        "--print-summary",
        action="store_true",
        help="Print a compact human-readable summary.",
    )
    return parser.parse_args()


def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def write_json(payload: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def event_duration_seconds(event: dict[str, Any]) -> float | None:
    start_unix = event.get("start_time_unix")
    end_unix = event.get("end_time_unix")
    if isinstance(start_unix, (int, float)) and isinstance(end_unix, (int, float)):
        return max(0.0, end_unix - start_unix)
    start = parse_iso(event.get("start_time"))
    end = parse_iso(event.get("end_time"))
    if start and end:
        return max(0.0, (end - start).total_seconds())
    return None


def load_agent_events(run_dir: Path) -> dict[str, list[dict[str, Any]]]:
    events_dir = run_dir / "agent_events"
    if not events_dir.exists():
        return {}
    return {
        path.name: load_jsonl(path)
        for path in sorted(events_dir.glob("*.jsonl"))
    }


def count_model_calls(agent_events: dict[str, list[dict[str, Any]]]) -> int:
    response_ids = set()
    for events in agent_events.values():
        for event in events:
            response_id = event.get("llm_response_id")
            if response_id:
                response_ids.add(response_id)
    return len(response_ids)


def count_event_messages(agent_events: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    count = 0
    byte_count = 0
    for events in agent_events.values():
        for event in events:
            if event.get("event_type") != "MessageEvent":
                continue
            count += 1
            byte_count += len(json.dumps(event.get("llm_message", ""), ensure_ascii=False).encode("utf-8"))
    return {"message_event_count": count, "message_event_bytes": byte_count}


def count_framework_messages(outputs: list[dict[str, Any]]) -> dict[str, Any]:
    message_types = {
        "manager_instruction",
        "agent_response",
        "manager_review",
        "single_agent_response",
    }
    count = 0
    byte_count = 0
    by_type: dict[str, int] = defaultdict(int)
    for event in outputs:
        event_type = event.get("event_type")
        if event_type not in message_types:
            continue
        count += 1
        by_type[event_type] += 1
        byte_count += len(json.dumps(event.get("content", ""), ensure_ascii=False).encode("utf-8"))
    return {
        "framework_message_count": count,
        "framework_message_bytes": byte_count,
        "framework_message_count_by_type": dict(sorted(by_type.items())),
    }


def count_test_invocations(agent_events: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    total = 0
    passed = 0
    failed = 0
    errored = 0
    by_log: dict[str, dict[str, int]] = {}
    for name, events in agent_events.items():
        local = {"test_invocations": 0, "passing_test_invocations": 0, "failing_test_invocations": 0}
        for event in events:
            if event.get("event_type") != "ObservationEvent":
                continue
            observation = event.get("observation") or {}
            if observation.get("type") != "TerminalObservation":
                continue
            content = str(observation.get("content", ""))
            if not PYTEST_RE.search(content):
                continue
            total += 1
            local["test_invocations"] += 1
            exit_code = observation.get("exit_code")
            if exit_code == 0:
                passed += 1
                local["passing_test_invocations"] += 1
            else:
                failed += 1
                local["failing_test_invocations"] += 1
                if ERROR_RE.search(content):
                    errored += 1
        by_log[name] = local
    return {
        "test_invocations": total,
        "passing_test_invocations": passed,
        "failing_test_invocations": failed,
        "errored_test_invocations": errored,
        "by_event_log": by_log,
    }


def summarize_primary_outcome(run_dir: Path) -> dict[str, Any]:
    report = load_json(run_dir / "report.json", {})
    summary = report.get("summary", {}) if isinstance(report, dict) else {}
    passed = summary.get("passed")
    total = summary.get("total")
    failed = summary.get("failed", 0)
    errors = summary.get("error", summary.get("errors", 0))
    exitcode = report.get("exitcode")
    final_success = bool(
        exitcode == 0
        or (total is not None and passed == total and not failed and not errors)
    )
    return {
        "upstream_evaluator": "commit0_pytest",
        "passed": passed,
        "failed": failed,
        "errors": errors,
        "total": total,
        "collected": summary.get("collected"),
        "exitcode": exitcode,
        "final_success": final_success,
    }


def summarize_cost_metrics(run_dir: Path, agent_events: dict[str, list[dict[str, Any]]], outputs: list[dict[str, Any]]) -> dict[str, Any]:
    cost = load_json(run_dir / "cost.json", {})
    total = cost.get("total", {}) if isinstance(cost, dict) else {}
    manager = cost.get("manager", {}) if isinstance(cost, dict) else {}
    subagents = cost.get("subagents", {}) if isinstance(cost, dict) else {}
    runtime_text = read_text(run_dir / "runtime.txt").strip()
    runtime_seconds = None
    if runtime_text:
        try:
            runtime_seconds = float(runtime_text)
        except ValueError:
            runtime_seconds = None
    test_counts = count_test_invocations(agent_events)
    event_messages = count_event_messages(agent_events)
    framework_messages = count_framework_messages(outputs)
    integration_attempts = [
        event for event in outputs if event.get("event_type") == "manager_review"
    ]
    return {
        "wall_clock_duration_seconds": total.get("wall_clock_duration", runtime_seconds),
        "runtime_seconds": runtime_seconds,
        "model_calls": count_model_calls(agent_events),
        "input_tokens": total.get("prompt_tokens", manager.get("prompt_tokens")),
        "output_tokens": total.get("completion_tokens", manager.get("completion_tokens")),
        "total_tokens": total.get("total_tokens", manager.get("total_tokens")),
        "cost_usd": total.get("cost", manager.get("cost")),
        "manager_cost_usd": manager.get("cost"),
        "subagent_cost_usd": sum(
            value.get("cost", 0.0) for value in subagents.values() if isinstance(value, dict)
        ),
        "subagent_count": len(subagents),
        "subagent_iterations_total": sum(
            value.get("iterations_total", 0) for value in subagents.values() if isinstance(value, dict)
        ),
        "test_invocations": test_counts["test_invocations"],
        "passing_test_invocations": test_counts["passing_test_invocations"],
        "failing_test_invocations": test_counts["failing_test_invocations"],
        "errored_test_invocations": test_counts["errored_test_invocations"],
        "test_invocations_by_event_log": test_counts["by_event_log"],
        "message_count": event_messages["message_event_count"] + framework_messages["framework_message_count"],
        "message_bytes": event_messages["message_event_bytes"] + framework_messages["framework_message_bytes"],
        "message_breakdown": {
            **event_messages,
            **framework_messages,
        },
        "integration_attempts": len(integration_attempts),
    }


def load_dependency_reports(run_dir: Path) -> list[dict[str, Any]]:
    reports = []
    for path in sorted(run_dir.glob("async_dependency_resolution*.json")):
        data = load_json(path, {})
        if data:
            data["_source_file"] = path.name
            reports.append(data)
    return reports


def summarize_dependency_metrics(reports: list[dict[str, Any]], metrics_manifest: dict[str, Any]) -> dict[str, Any]:
    per_report = []
    aggregate_adpr_values = []
    stale_assumption_candidates = []
    missing_communication_candidates = []
    for report in reports:
        adpr = report.get("ADPR_strict", {})
        if isinstance(adpr.get("value"), (int, float)):
            aggregate_adpr_values.append(adpr["value"])
        dependency_rows = []
        for result in report.get("dependency_results", []):
            strict = result.get("strict_integrated_resolution") or {}
            upstream = result.get("upstream_resolution") or {}
            downstream = result.get("downstream_resolution") or {}
            composed = result.get("composed_resolution") or {}
            upstream_step = upstream.get("logical_iteration")
            downstream_step = downstream.get("logical_iteration")
            strict_step = strict.get("logical_iteration")
            cail = None
            stale_proxy = None
            if isinstance(upstream_step, int) and isinstance(downstream_step, int):
                cail = downstream_step - upstream_step
                if downstream_step < upstream_step:
                    stale_proxy = upstream_step - downstream_step
                    stale_assumption_candidates.append(
                        {
                            "source_file": report["_source_file"],
                            "dependency_id": result.get("dependency_id"),
                            "reason": "downstream probes passed before upstream probes in this event-log view",
                            "proxy_duration_iterations": stale_proxy,
                        }
                    )
                    missing_communication_candidates.append(
                        {
                            "source_file": report["_source_file"],
                            "dependency_id": result.get("dependency_id"),
                            "reason": "downstream-before-upstream resolution may indicate missing or delayed contract visibility; requires trajectory audit",
                        }
                    )
            dependency_rows.append(
                {
                    "dependency_id": result.get("dependency_id"),
                    "DRS": strict_step,
                    "DRS_composed": composed.get("logical_iteration"),
                    "upstream_resolution_step": upstream_step,
                    "downstream_resolution_step": downstream_step,
                    "CAIL": cail,
                    "SAD_proxy_iterations": stale_proxy,
                    "SAD_status": (
                        "proxy_candidate_requires_audit"
                        if stale_proxy is not None
                        else "not_observed_in_available_checkpoints"
                    ),
                }
            )
        per_report.append(
            {
                "source_file": report["_source_file"],
                "ADPR": adpr,
                "checkpoint_count": report.get("checkpoint_count"),
                "dependency_metrics": dependency_rows,
            }
        )
    primary_ids = (
        metrics_manifest.get("aggregate_metrics", {}).get("primary_async_dependency_ids", [])
        if isinstance(metrics_manifest, dict)
        else []
    )
    return {
        "metric_annotation_id": metrics_manifest.get("metric_annotation_id"),
        "primary_async_dependency_ids": primary_ids,
        "ADPR": {
            "per_report": [
                {
                    "source_file": item["source_file"],
                    "resolved": item["ADPR"].get("resolved"),
                    "total": item["ADPR"].get("total"),
                    "value": item["ADPR"].get("value"),
                }
                for item in per_report
            ],
            "mean_value_across_reports": (
                sum(aggregate_adpr_values) / len(aggregate_adpr_values)
                if aggregate_adpr_values
                else None
            ),
        },
        "DRS_CAIL_SAD_by_report": per_report,
        "SAD": {
            "definition_status": "automatic proxy only; full SAD requires structured message/artifact visibility logs or human audit",
            "candidate_incident_count": len(stale_assumption_candidates),
            "candidate_incidents": stale_assumption_candidates,
        },
        "missing_communication": {
            "definition_status": "automatic proxy only; requires human audit for final labels",
            "candidate_incident_count": len(missing_communication_candidates),
            "candidate_incidents": missing_communication_candidates,
        },
    }


def extract_patch_added_defs(patch_text: str) -> dict[str, list[str]]:
    current_file = None
    added_by_file: dict[str, list[str]] = defaultdict(list)
    for line in patch_text.splitlines():
        if line.startswith("+++ b/"):
            current_file = line[len("+++ b/") :]
            continue
        if current_file is None:
            continue
        match = ADDED_DEF_RE.match(line)
        if match:
            added_by_file[current_file].append(match.group("name"))
    return {path: names for path, names in sorted(added_by_file.items())}


def extract_modified_files(patch_text: str) -> list[str]:
    return sorted(set(re.findall(r"^\+\+\+ b/(.+)$", patch_text, re.MULTILINE)))


def identifier_tokens(text: str) -> set[str]:
    tokens = set()
    for token in IDENT_RE.findall(text):
        token = token.lower().strip("_")
        if len(token) >= 4 and token not in CONTRACT_TOKEN_STOPWORDS:
            tokens.add(token)
            if "hash" in token:
                tokens.add("hash")
            if "typed" in token:
                tokens.add("typed")
    return tokens


def unique_duplicate_contract_symbols(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for candidate in candidates:
        key = (candidate["consumer_file"], candidate["added_symbol"])
        row = grouped.setdefault(
            key,
            {
                "consumer_file": candidate["consumer_file"],
                "added_symbol": candidate["added_symbol"],
                "dependency_ids": [],
                "matched_contract_tokens": [],
            },
        )
        row["dependency_ids"].append(candidate["dependency_id"])
        row["matched_contract_tokens"].extend(candidate.get("matched_contract_tokens", []))
    unique = []
    for row in grouped.values():
        row["dependency_ids"] = sorted(set(row["dependency_ids"]))
        row["matched_contract_tokens"] = sorted(set(row["matched_contract_tokens"]))
        unique.append(row)
    return sorted(unique, key=lambda item: (item["consumer_file"], item["added_symbol"]))


def duplicate_contract_candidates(
    *,
    metrics_manifest: dict[str, Any],
    added_defs_by_file: dict[str, list[str]],
) -> list[dict[str, Any]]:
    candidates = []
    for dependency in metrics_manifest.get("dependency_points", []):
        if dependency.get("producer_agent") in {None, "", "integrator"}:
            continue
        producer_text = " ".join(
            [
                dependency.get("dependency_id", ""),
                dependency.get("contract_summary", ""),
                " ".join(dependency.get("producer_files", [])),
                " ".join(dependency.get("upstream_probe_tests", [])),
            ]
        )
        producer_tokens = identifier_tokens(producer_text)
        for consumer_file in dependency.get("consumer_files", []):
            for symbol in added_defs_by_file.get(consumer_file, []):
                symbol_norm = symbol.lower().strip("_")
                matched = sorted(
                    token
                    for token in producer_tokens
                    if token in symbol_norm or symbol_norm in token
                )
                if matched:
                    candidates.append(
                        {
                            "dependency_id": dependency.get("dependency_id"),
                            "consumer_file": consumer_file,
                            "added_symbol": symbol,
                            "matched_contract_tokens": matched[:8],
                            "reason": "consumer patch added a helper/class whose name overlaps the producer contract vocabulary",
                        }
                    )
    return candidates


def outputs_agent_responses(outputs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    responses = []
    for event in outputs:
        if event.get("event_type") == "single_agent_complete":
            content = event.get("content") or {}
            responses.append(
                {
                    "event_type": event.get("event_type"),
                    "source": "single_agent",
                    "target": "manager",
                    "task_id": "single_agent",
                    "success": None,
                    "files_modified": [],
                    "commit_hash": None,
                    "error": None,
                    "cost": None,
                    "total_tokens": None,
                    "actual_iterations": content.get("iterations"),
                    "duration_seconds": content.get("duration"),
                    "start_time_unix": event.get("start_time_unix"),
                    "end_time_unix": event.get("end_time_unix"),
                    "start_time": event.get("start_time"),
                    "end_time": event.get("end_time"),
                }
            )
            continue
        if event.get("event_type") not in {"agent_response", "single_agent_response"}:
            continue
        content = event.get("content") or {}
        responses.append(
            {
                "event_type": event.get("event_type"),
                "source": event.get("source"),
                "target": event.get("target"),
                "task_id": content.get("task_id"),
                "success": content.get("success"),
                "files_modified": content.get("files_modified") or [],
                "commit_hash": content.get("commit_hash"),
                "error": content.get("error"),
                "cost": content.get("cost"),
                "total_tokens": content.get("total_tokens"),
                "actual_iterations": content.get("actual_iterations"),
                "duration_seconds": content.get("duration_seconds"),
                "start_time_unix": event.get("start_time_unix"),
                "end_time_unix": event.get("end_time_unix"),
                "start_time": event.get("start_time"),
                "end_time": event.get("end_time"),
            }
        )
    return responses


def assignment_scope_from_artifacts(run_dir: Path) -> dict[str, set[str]]:
    scope: dict[str, set[str]] = defaultdict(set)
    protocol = load_json(run_dir / "protocol.json", {})
    for assignment in protocol.get("assignments", []) if isinstance(protocol, dict) else []:
        agent = assignment.get("engineer_id")
        if not agent:
            continue
        file_path = assignment.get("file_path")
        if file_path:
            for part in str(file_path).split(","):
                if part.strip():
                    scope[agent].add(part.strip())
        for path in assignment.get("writable_paths", []) or []:
            scope[agent].add(path)

    delegations = load_json(run_dir / "delegations.json", {})
    first_round = (
        delegations.get("delegation_plan", {}).get("first_round", {})
        if isinstance(delegations, dict)
        else {}
    )
    for task in first_round.get("tasks", []) or []:
        agent = task.get("engineer_id")
        if not agent:
            continue
        file_path = task.get("file_path")
        if file_path:
            for part in str(file_path).split(","):
                if part.strip():
                    scope[agent].add(part.strip())
    return {agent: paths for agent, paths in scope.items()}


def scope_violations(run_dir: Path, responses: list[dict[str, Any]]) -> dict[str, Any]:
    scope = assignment_scope_from_artifacts(run_dir)
    violations = []
    scoped_agents = 0
    for response in responses:
        agent = response.get("source")
        if not agent or agent not in scope:
            continue
        scoped_agents += 1
        allowed = scope[agent]
        modified = set(response.get("files_modified") or [])
        out_of_scope = sorted(path for path in modified if path not in allowed)
        if out_of_scope:
            violations.append(
                {
                    "agent": agent,
                    "task_id": response.get("task_id"),
                    "allowed_files": sorted(allowed),
                    "out_of_scope_files": out_of_scope,
                }
            )
    return {
        "scoped_agent_attempt_count": scoped_agents,
        "violating_agent_attempt_count": len(violations),
        "violations": violations,
        "SVR": (len(violations) / scoped_agents) if scoped_agents else None,
    }


def active_overlap_seconds(responses: list[dict[str, Any]]) -> float:
    points = []
    for response in responses:
        start = response.get("start_time_unix")
        end = response.get("end_time_unix")
        if isinstance(start, (int, float)) and isinstance(end, (int, float)) and end > start:
            points.append((start, 1))
            points.append((end, -1))
    if not points:
        return 0.0
    points.sort(key=lambda item: (item[0], -item[1]))
    active = 0
    previous = None
    overlap = 0.0
    for time_value, delta in points:
        if previous is not None and time_value > previous and active >= 2:
            overlap += time_value - previous
        active += delta
        previous = time_value
    return overlap


def actions_after_undelivered_update(
    *,
    responses: list[dict[str, Any]],
    metrics_manifest: dict[str, Any],
    protocol: dict[str, Any],
) -> list[dict[str, Any]]:
    communication_condition = protocol.get("communication_condition")
    concurrent_execution = protocol.get("concurrent_execution")
    if communication_condition not in {"none_in_flight", "private_no_handoff"} and not concurrent_execution:
        return []

    response_by_agent = {
        response.get("source"): response
        for response in responses
        if response.get("source")
    }
    incidents = []
    for dependency in metrics_manifest.get("dependency_points", []):
        producer = dependency.get("producer_agent")
        consumer = dependency.get("consumer_agent")
        if producer not in response_by_agent or consumer not in response_by_agent:
            continue
        producer_response = response_by_agent[producer]
        consumer_response = response_by_agent[consumer]
        producer_end = producer_response.get("end_time_unix")
        consumer_start = consumer_response.get("start_time_unix")
        consumer_end = consumer_response.get("end_time_unix")
        if not all(isinstance(value, (int, float)) for value in (producer_end, consumer_start, consumer_end)):
            continue
        if consumer_end > producer_end:
            incidents.append(
                {
                    "dependency_id": dependency.get("dependency_id"),
                    "producer_agent": producer,
                    "consumer_agent": consumer,
                    "communication_condition": communication_condition,
                    "duration_seconds": max(0.0, consumer_end - max(consumer_start, producer_end)),
                    "reason": "consumer continued after producer artifact completed while in-flight delivery was unavailable",
                }
            )
    return incidents


def summarize_process_metrics(
    *,
    run_dir: Path,
    outputs: list[dict[str, Any]],
    metrics_manifest: dict[str, Any],
    dependency_summary: dict[str, Any],
) -> dict[str, Any]:
    patch_text = read_text(run_dir / "patch.diff")
    modified_files = extract_modified_files(patch_text)
    added_defs_by_file = extract_patch_added_defs(patch_text)
    responses = outputs_agent_responses(outputs)
    scope_summary = scope_violations(run_dir, responses)
    agent_attempts = len(responses)
    successful_attempts = sum(1 for response in responses if response.get("success") is True)
    failed_attempts = sum(1 for response in responses if response.get("success") is False)

    files_by_agent: dict[str, list[str]] = {}
    agents_by_file: dict[str, list[str]] = defaultdict(list)
    for response in responses:
        source = response.get("source") or "single_agent"
        files = response.get("files_modified") or []
        files_by_agent[source] = files
        for file_path in files:
            agents_by_file[file_path].append(source)
    duplicated_file_work = {
        file_path: sorted(set(agents))
        for file_path, agents in agents_by_file.items()
        if len(set(agents)) > 1
    }
    duplicated_contracts = duplicate_contract_candidates(
        metrics_manifest=metrics_manifest,
        added_defs_by_file=added_defs_by_file,
    )
    unique_duplicated_contract_symbols = unique_duplicate_contract_symbols(duplicated_contracts)

    reviews = [event for event in outputs if event.get("event_type") == "manager_review"]
    textual_conflict_events = []
    reviewer_repair_success = 0
    for review in reviews:
        content = review.get("content") or {}
        reason = str(content.get("review_reason", ""))
        merged = content.get("merged")
        if not merged and re.search(r"conflict|CONFLICT", reason):
            textual_conflict_events.append(review)
        if merged and re.search(r"recover|repair|resolved", reason, re.I):
            reviewer_repair_success += 1
    run_logs = "\n".join(read_text(path) for path in sorted(run_dir.glob("run_*.log")))
    textual_patch_conflict = bool(textual_conflict_events or re.search(r"\bCONFLICT\b|merge conflict", run_logs, re.I))

    primary = summarize_primary_outcome(run_dir)
    semantic_integration_failure = (
        bool(patch_text.strip())
        and not primary["final_success"]
        and not textual_patch_conflict
    )
    undelivered = actions_after_undelivered_update(
        responses=responses,
        metrics_manifest=metrics_manifest,
        protocol=load_json(run_dir / "protocol.json", {}),
    )
    failed_attempt_cost = sum(
        response.get("cost") or 0.0
        for response in responses
        if response.get("success") is False
    )
    failed_attempt_tokens = sum(
        response.get("total_tokens") or 0
        for response in responses
        if response.get("success") is False
    )
    return {
        "patch_file_generation_success": {
            "patch_diff_exists": bool(patch_text.strip()),
            "modified_files": modified_files,
            "agent_attempt_count": agent_attempts,
            "successful_agent_attempt_count": successful_attempts,
            "failed_agent_attempt_count": failed_attempts,
            "agent_files_modified": files_by_agent,
        },
        "textual_patch_conflict": {
            "observed": textual_patch_conflict,
            "conflict_event_count": len(textual_conflict_events),
        },
        "semantic_integration_failure": {
            "observed": semantic_integration_failure,
            "definition": "final evaluator failed after patch generation without textual merge conflict",
        },
        "tests_passed_before_and_after_integration": {
            "before_integration_source": "agent event logs and local pytest observations",
            "after_integration_source": "report.json and final runner evaluator",
            "after_integration_final_success": primary["final_success"],
            "after_integration_passed": primary["passed"],
            "after_integration_total": primary["total"],
            "dependency_checkpoint_reports": dependency_summary["ADPR"]["per_report"],
        },
        "duplicated_file_or_function_work": {
            "duplicated_file_work": duplicated_file_work,
            "duplicated_contract_implementation_candidate_count": len(duplicated_contracts),
            "duplicated_contract_unique_added_symbol_count": len(unique_duplicated_contract_symbols),
            "duplicated_contract_unique_added_symbols": unique_duplicated_contract_symbols,
            "duplicated_contract_implementation_candidates": duplicated_contracts,
            "added_definitions_by_file": added_defs_by_file,
        },
        "stale_assumption_incident_count": {
            "automatic_proxy_count": dependency_summary["SAD"]["candidate_incident_count"]
            + len(unique_duplicated_contract_symbols),
            "status": "proxy_candidates_require_human_audit",
            "candidate_sources": {
                "downstream_before_upstream_resolution": dependency_summary["SAD"]["candidate_incidents"],
                "duplicated_contract_implementation": duplicated_contracts,
            },
        },
        "missing_communication_incident_count": {
            "automatic_proxy_count": dependency_summary["missing_communication"]["candidate_incident_count"],
            "status": "proxy_candidates_require_human_audit",
            "candidate_incidents": dependency_summary["missing_communication"]["candidate_incidents"],
        },
        "reviewer_repair_success": {
            "manager_review_count": len(reviews),
            "reviewer_repair_success_count": reviewer_repair_success,
            "merged_review_count": sum(1 for review in reviews if (review.get("content") or {}).get("merged") is True),
        },
        "scope_violation_rate": scope_summary,
        "wasted_model_or_test_work_after_invalidation": {
            "failed_attempt_cost_usd": failed_attempt_cost,
            "failed_attempt_tokens": failed_attempt_tokens,
            "failed_attempt_count": failed_attempts,
            "duplicated_contract_candidate_count": len(duplicated_contracts),
            "duplicated_contract_unique_added_symbol_count": len(unique_duplicated_contract_symbols),
            "status": "proxy; exact invalidation requires structured artifact-version visibility logs",
        },
        "asynchronous_overlap_duration": {
            "overlap_seconds_with_two_or_more_agents_active": active_overlap_seconds(responses),
            "agent_response_intervals": [
                {
                    "agent": response.get("source"),
                    "task_id": response.get("task_id"),
                    "start_time": response.get("start_time"),
                    "end_time": response.get("end_time"),
                    "duration_seconds": response.get("duration_seconds"),
                }
                for response in responses
            ],
        },
        "actions_taken_after_relevant_but_undelivered_teammate_update": {
            "automatic_proxy_count": len(undelivered),
            "status": "proxy based on agent_response intervals and communication_condition",
            "candidate_incidents": undelivered,
        },
    }


def formal_metric_values(
    *,
    primary: dict[str, Any],
    cost: dict[str, Any],
    dependency_summary: dict[str, Any],
    process: dict[str, Any],
) -> dict[str, Any]:
    attempts = process["patch_file_generation_success"]["agent_attempt_count"]
    failed_attempts = process["patch_file_generation_success"]["failed_agent_attempt_count"]
    integration_failure = (
        process["textual_patch_conflict"]["observed"]
        or process["semantic_integration_failure"]["observed"]
    )
    stale_proxy = process["stale_assumption_incident_count"]["automatic_proxy_count"]
    consumer_attempts = attempts
    if attempts and process["patch_file_generation_success"].get("agent_files_modified"):
        consumer_attempts = sum(
            1
            for files in process["patch_file_generation_success"]["agent_files_modified"].values()
            if files
        )
    detected_manager_repair_failures = (
        process["textual_patch_conflict"]["conflict_event_count"]
        + int(process["semantic_integration_failure"]["observed"])
    )
    recovered = process["reviewer_repair_success"]["reviewer_repair_success_count"]
    return {
        "FSR": {
            "name": "Final Success Rate",
            "formula": "# successful runs / # total runs",
            "value": 1.0 if primary["final_success"] else 0.0,
            "numerator": 1 if primary["final_success"] else 0,
            "denominator": 1,
        },
        "DRS_score": {
            "name": "Dependency Resolution Score",
            "formula": "(1 / |D_i|) * sum_{d in D_i} pass(d)",
            "value": dependency_summary["ADPR"]["mean_value_across_reports"],
            "note": (
                "This is the paper_structure_reference DRS score. "
                "The metric guide's DRS means Dependency Resolution Step and is reported separately."
            ),
        },
        "ADPR": {
            "name": "Async Dependency Pass Rate",
            "value": dependency_summary["ADPR"]["mean_value_across_reports"],
            "per_report": dependency_summary["ADPR"]["per_report"],
        },
        "DRS_step": {
            "name": "Dependency Resolution Step",
            "value_source": "dependency_metrics.DRS_CAIL_SAD_by_report[*].dependency_metrics[*].DRS",
        },
        "SAR": {
            "name": "Stale Assumption Rate",
            "formula": "# consumer attempts based on outdated producer contract / # consumer attempts",
            "value": None,
            "status": "requires_human_or_structured_visibility_audit",
            "proxy_candidate_count": stale_proxy,
            "proxy_consumer_attempt_count": consumer_attempts,
            "run_level_proxy_indicator": 1.0 if stale_proxy else 0.0,
            "note": (
                "The current traces expose stale-assumption candidates, but "
                "not enough structured visibility state to divide by audited "
                "consumer attempts without human review."
            ),
        },
        "FSAR": {
            "name": "Failed Subagent Attempt Rate",
            "formula": "# failed subagent attempts / # total subagent attempts",
            "value": (failed_attempts / attempts) if attempts else None,
            "numerator": failed_attempts,
            "denominator": attempts,
        },
        "IFR": {
            "name": "Integration Failure Rate",
            "formula": "# runs with merge, import, or integration failure / # total runs",
            "value": 1.0 if integration_failure else 0.0,
            "numerator": 1 if integration_failure else 0,
            "denominator": 1,
            "components": {
                "textual_patch_conflict": process["textual_patch_conflict"]["observed"],
                "semantic_integration_failure": process["semantic_integration_failure"]["observed"],
            },
        },
        "SVR": {
            "name": "Scope Violation Rate",
            "formula": "# agents modifying out-of-scope files / # total scoped agents",
            "value": process["scope_violation_rate"]["SVR"],
            "numerator": process["scope_violation_rate"]["violating_agent_attempt_count"],
            "denominator": process["scope_violation_rate"]["scoped_agent_attempt_count"],
            "violations": process["scope_violation_rate"]["violations"],
        },
        "MRR": {
            "name": "Manager Recovery Rate",
            "formula": "# recovered dependency or integration failures / # detected dependency or integration failures",
            "value": (
                recovered / detected_manager_repair_failures
                if detected_manager_repair_failures
                else None
            ),
            "numerator": recovered,
            "denominator": detected_manager_repair_failures,
            "status": "only meaningful for manager-mediated protocols with structured repair events",
        },
        "cost_and_runtime": {
            "wall_clock_time_seconds": cost.get("wall_clock_duration_seconds"),
            "token_count": cost.get("total_tokens"),
            "api_cost_usd": cost.get("cost_usd"),
            "agent_turns_or_model_calls": cost.get("model_calls"),
            "subagent_attempts": attempts,
            "merge_review_cycles": cost.get("integration_attempts"),
        },
    }


def baseline_summary(run_dir: Path) -> dict[str, Any]:
    primary = summarize_primary_outcome(run_dir)
    cost = load_json(run_dir / "cost.json", {})
    total = cost.get("total", {}) if isinstance(cost, dict) else {}
    reports = load_dependency_reports(run_dir)
    adpr_values = [
        report.get("ADPR_strict", {}).get("value")
        for report in reports
        if isinstance(report.get("ADPR_strict", {}).get("value"), (int, float))
    ]
    return {
        "final_success": primary["final_success"],
        "passed": primary["passed"],
        "total": primary["total"],
        "cost_usd": total.get("cost"),
        "total_tokens": total.get("total_tokens"),
        "wall_clock_duration_seconds": total.get("wall_clock_duration"),
        "mean_ADPR": sum(adpr_values) / len(adpr_values) if adpr_values else None,
    }


def compute_serial_to_async_delta(run_dir: Path, baseline_run_dir: Path | None) -> dict[str, Any] | None:
    if baseline_run_dir is None:
        return None
    current = baseline_summary(run_dir)
    baseline = baseline_summary(baseline_run_dir)

    def delta(key: str) -> float | int | None:
        left = current.get(key)
        right = baseline.get(key)
        if isinstance(left, (int, float)) and isinstance(right, (int, float)):
            return left - right
        return None

    return {
        "baseline_run_dir": str(baseline_run_dir),
        "current_run_dir": str(run_dir),
        "baseline": baseline,
        "current": current,
        "delta": {
            "final_success": (
                int(current["final_success"]) - int(baseline["final_success"])
                if current.get("final_success") is not None and baseline.get("final_success") is not None
                else None
            ),
            "cost_usd": delta("cost_usd"),
            "total_tokens": delta("total_tokens"),
            "wall_clock_duration_seconds": delta("wall_clock_duration_seconds"),
            "mean_ADPR": delta("mean_ADPR"),
        },
    }


def build_report(run_dir: Path, metrics_path: Path, baseline_run_dir: Path | None) -> dict[str, Any]:
    metrics_manifest = load_json(metrics_path, {})
    outputs = load_jsonl(run_dir / "outputs.jsonl")
    agent_events = load_agent_events(run_dir)
    dependency_reports = load_dependency_reports(run_dir)
    dependency_summary = summarize_dependency_metrics(dependency_reports, metrics_manifest)
    primary = summarize_primary_outcome(run_dir)
    cost = summarize_cost_metrics(run_dir, agent_events, outputs)
    process = summarize_process_metrics(
        run_dir=run_dir,
        outputs=outputs,
        metrics_manifest=metrics_manifest,
        dependency_summary=dependency_summary,
    )
    formal_metrics = formal_metric_values(
        primary=primary,
        cost=cost,
        dependency_summary=dependency_summary,
        process=process,
    )
    serial_delta = compute_serial_to_async_delta(run_dir, baseline_run_dir)
    return {
        "schema_version": "0.1-run-process-metrics",
        "run_dir": str(run_dir),
        "metrics_manifest": str(metrics_path),
        "task_id": metrics_manifest.get("task_id"),
        "metric_names_followed": {
            "dependency_metrics": ["ADPR", "DRS", "CAIL", "SAD"],
            "process_metrics": [
                "patch/file generation success",
                "textual patch conflict",
                "semantic integration failure",
                "tests passed before and after integration",
                "duplicated file or function work",
                "stale-assumption incident count",
                "missing communication incident count",
                "reviewer repair success",
                "wasted model or test work after invalidation",
                "asynchronous overlap duration",
                "actions taken after a relevant but undelivered teammate update",
                "serial-to-async performance delta under fixed decomposition",
            ],
        },
        "primary_outcome": primary,
        "cost_metrics": cost,
        "formal_metrics": formal_metrics,
        "dependency_metrics": dependency_summary,
        "process_metrics": process,
        "serial_to_async_performance_delta_under_fixed_decomposition": serial_delta,
        "limitations": [
            "SAD is reported as proxy candidates unless structured artifact-visibility/message logs are available.",
            "Missing communication incidents are proxy candidates and require human trajectory audit for paper labels.",
            "Duplicated contract implementation is detected by conservative patch-name heuristics and should be confirmed by human review.",
        ],
    }


def print_summary(report: dict[str, Any]) -> None:
    primary = report["primary_outcome"]
    cost = report["cost_metrics"]
    process = report["process_metrics"]
    dependency = report["dependency_metrics"]
    formal = report["formal_metrics"]
    print(f"task_id: {report.get('task_id')}")
    print(f"run_dir: {report['run_dir']}")
    print(
        "final: "
        f"{primary.get('passed')}/{primary.get('total')} "
        f"success={primary.get('final_success')}"
    )
    print(
        "cost: "
        f"${cost.get('cost_usd')} "
        f"tokens={cost.get('total_tokens')} "
        f"wall_clock={cost.get('wall_clock_duration_seconds')}"
    )
    adpr = dependency["ADPR"]
    print(f"ADPR reports: {adpr['per_report']}")
    print(
        "process: "
        f"attempts={process['patch_file_generation_success']['agent_attempt_count']} "
        f"failed_attempts={process['patch_file_generation_success']['failed_agent_attempt_count']} "
        f"textual_conflict={process['textual_patch_conflict']['observed']} "
        f"semantic_integration_failure={process['semantic_integration_failure']['observed']} "
        f"duplicated_contract_unique_symbols="
        f"{process['duplicated_file_or_function_work']['duplicated_contract_unique_added_symbol_count']} "
        f"(candidates={process['duplicated_file_or_function_work']['duplicated_contract_implementation_candidate_count']}) "
        f"async_overlap="
        f"{process['asynchronous_overlap_duration']['overlap_seconds_with_two_or_more_agents_active']}"
    )
    print(
        "formal: "
        f"FSR={formal['FSR']['value']} "
        f"DRS_score={formal['DRS_score']['value']} "
        f"SAR_proxy={formal['SAR']['value']} "
        f"FSAR={formal['FSAR']['value']} "
        f"IFR={formal['IFR']['value']} "
        f"SVR={formal['SVR']['value']} "
        f"MRR={formal['MRR']['value']}"
    )


def main() -> int:
    args = parse_args()
    report = build_report(args.run_dir, args.metrics, args.baseline_run_dir)
    write_json(report, args.output)
    if args.print_summary:
        print_summary(report)
    print(f"wrote: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
