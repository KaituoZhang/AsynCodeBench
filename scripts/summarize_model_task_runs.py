#!/usr/bin/env python
"""Create a standard AsynCodeBench model-task evaluation record.

The script consumes existing run directories after
scripts/analyze_async_dependency_resolution.py and
scripts/analyze_run_process_metrics.py have been run. It writes the lightweight
record files we want to keep under version control:

- <task>_<model_tag>_metrics_table.csv
- <task>_<model_tag>_artifact_index.json
- <task>.md
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path
from typing import Any


MODE_ORDER = ["single", "serial_specialists", "async_private", "CAID_multi"]
INDEXED_PATTERNS = [
    "report.json",
    "report.pre_manifest_retest.json",
    "manifest_retest_metadata.json",
    "cost.json",
    "runtime.txt",
    "outputs.jsonl",
    "patch.diff",
    "protocol.json",
    "delegations.json",
    "*_test_output.txt",
    "*_test_output.pre_manifest_retest.txt",
    "*_pytest_exit_code.txt",
    "*_pytest_exit_code.pre_manifest_retest.txt",
    "process_metrics_summary.json",
    "dependency_probe_checkpoints.jsonl",
    "strict_dependency_metrics.json",
    "async_dependency_resolution*.json",
    "agent_events/*.jsonl",
]
HYGIENE_MARKERS = (".backup", ".bak", "prototype", "tmp", "temp")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Summarize one model/task across AsynCodeBench protocols."
    )
    parser.add_argument("--task", required=True, help="Task/repo name, e.g. cachetools.")
    parser.add_argument("--model-tag", required=True, help="Filesystem-safe model tag.")
    parser.add_argument("--model", required=True, help="Provider model id.")
    parser.add_argument(
        "--runner-adapter",
        default="native",
        help="Runner/adapter label, e.g. native or deepseek_json_delegation_adapter.",
    )
    parser.add_argument("--metrics", type=Path, required=True, help="Metrics manifest path.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Directory where md/csv/artifact index are written.",
    )
    parser.add_argument(
        "--run",
        action="append",
        required=True,
        metavar="MODE=PATH",
        help="Protocol run directory. Repeat for single/serial_specialists/async_private/CAID_multi.",
    )
    return parser.parse_args()


def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_runs(values: list[str]) -> dict[str, Path]:
    runs = {}
    for value in values:
        if "=" not in value:
            raise ValueError(f"--run must be MODE=PATH, got {value!r}")
        mode, path = value.split("=", 1)
        runs[mode] = Path(path)
    return runs


def summary_adpr_value(report: dict[str, Any]) -> float | None:
    adpr = report.get("ADPR_strict") or report.get("ADPR") or {}
    value = adpr.get("value")
    return value if isinstance(value, (int, float)) else None


def collect_dependency_reports(run_dir: Path, process_summary: dict[str, Any]) -> list[dict[str, Any]]:
    reports = []
    dep_summary = process_summary.get("dependency_metrics", {})
    for row in dep_summary.get("DRS_CAIL_SAD_by_report", []) or []:
        reports.append(
            {
                "source_file": row.get("source_file"),
                "ADPR": row.get("ADPR", {}),
                "dependency_metrics": row.get("dependency_metrics", []),
            }
        )
    if reports:
        return reports

    for path in sorted(run_dir.glob("async_dependency_resolution*.json")):
        data = load_json(path, {})
        if data:
            reports.append(
                {
                    "source_file": path.name,
                    "ADPR": data.get("ADPR_strict", {}),
                    "dependency_metrics": [],
                }
            )
    return reports


def final_integrated_adpr(run_dir: Path, process_summary: dict[str, Any]) -> tuple[float | None, str]:
    strict = load_json(run_dir / "strict_dependency_metrics.json", {})
    strict_adpr = strict.get("final_integrated_ADPR", {}) if isinstance(strict, dict) else {}
    strict_value = strict_adpr.get("value")
    if isinstance(strict_value, (int, float)):
        return strict_value, "strict_dependency_metrics.final_integrated_ADPR"

    final_report = run_dir / "async_dependency_resolution_final_integrated.json"
    if final_report.exists():
        value = summary_adpr_value(load_json(final_report, {}))
        return value, "async_dependency_resolution_final_integrated.json"

    for name in ("async_dependency_resolution_manager.json", "async_dependency_resolution_manager_events.json"):
        path = run_dir / name
        if path.exists():
            value = summary_adpr_value(load_json(path, {}))
            return value, name

    formal = process_summary.get("formal_metrics", {})
    adpr = formal.get("ADPR", {})
    value = adpr.get("value")
    if isinstance(value, (int, float)):
        return value, "process_metrics_summary.formal_metrics.ADPR"

    dep = process_summary.get("dependency_metrics", {})
    value = dep.get("ADPR", {}).get("mean_value_across_reports")
    if isinstance(value, (int, float)):
        return value, "process_metrics_summary.dependency_metrics.ADPR.mean"

    return None, "unavailable"


def mean_per_agent_adpr(reports: list[dict[str, Any]]) -> tuple[float | None, str]:
    values = []
    pieces = []
    for report in reports:
        adpr = report.get("ADPR") or {}
        value = adpr.get("value")
        source = report.get("source_file") or "unknown"
        resolved = adpr.get("resolved")
        total = adpr.get("total")
        if isinstance(value, (int, float)):
            values.append(value)
            pieces.append(f"{source}={resolved}/{total}={value}")
    mean = sum(values) / len(values) if values else None
    return mean, "; ".join(pieces)


def cail_summary(reports: list[dict[str, Any]]) -> dict[str, Any]:
    observed = []
    unresolved = 0
    total = 0
    drs_values = []
    sad_count = 0
    report_bits = []
    for report in reports:
        local_cail = []
        local_unresolved = 0
        for dep in report.get("dependency_metrics", []):
            total += 1
            cail = dep.get("CAIL")
            drs = dep.get("DRS")
            if isinstance(cail, (int, float)):
                observed.append(cail)
                local_cail.append(cail)
            else:
                unresolved += 1
                local_unresolved += 1
            if isinstance(drs, int):
                drs_values.append(drs)
            if dep.get("SAD_proxy_iterations") is not None:
                sad_count += 1
        source = report.get("source_file") or "unknown"
        if local_cail:
            report_bits.append(
                f"{source}: CAIL max={max(local_cail)}, nonzero={sum(1 for v in local_cail if v != 0)}, unresolved={local_unresolved}"
            )
        else:
            report_bits.append(f"{source}: no observed CAIL, unresolved={local_unresolved}")
    return {
        "cail_observed_count": len(observed),
        "cail_unresolved_count": unresolved,
        "cail_total_dependency_views": total,
        "cail_nonzero_count": sum(1 for value in observed if value != 0),
        "cail_max": max(observed) if observed else None,
        "cail_mean": (sum(observed) / len(observed)) if observed else None,
        "drs_observed_count": len(drs_values),
        "drs_min": min(drs_values) if drs_values else None,
        "drs_max": max(drs_values) if drs_values else None,
        "sad_proxy_candidate_count": sad_count,
        "per_report_cail_summary": "; ".join(report_bits),
    }


def strict_cail_summary(run_dir: Path) -> dict[str, Any] | None:
    strict = load_json(run_dir / "strict_dependency_metrics.json", None)
    if not strict:
        return None
    cail = strict.get("strict_CAIL", {})
    drs_summary = strict.get("strict_DRS", {})
    rows = strict.get("dependency_metrics", []) or []
    observed_cail = [
        row.get("strict_CAIL")
        for row in rows
        if isinstance(row.get("strict_CAIL"), int)
    ]
    observed_drs = [
        row.get("strict_DRS")
        for row in rows
        if isinstance(row.get("strict_DRS"), int)
    ]
    total = len(rows)
    checkpoint_count = strict.get("checkpoint_count")
    drs_penalized: list[int] = []
    cail_penalized: list[int] = []
    dependency_resolution_efficiency: list[float] = []
    if isinstance(checkpoint_count, int) and checkpoint_count > 0:
        for row in rows:
            dependency_drs = row.get("strict_DRS")
            upstream = row.get("upstream_resolution_step")
            downstream = row.get("downstream_resolution_step")
            resolved = bool(row.get("final_integrated_pass")) and isinstance(
                dependency_drs, int
            )

            penalized_drs = dependency_drs if resolved else checkpoint_count + 1
            drs_penalized.append(penalized_drs)
            dependency_resolution_efficiency.append(
                1 - (penalized_drs - 1) / checkpoint_count if resolved else 0.0
            )

            if isinstance(upstream, int) and isinstance(downstream, int):
                cail_penalized.append(max(0, downstream - upstream))
            elif isinstance(upstream, int):
                cail_penalized.append(checkpoint_count + 1 - upstream)
            else:
                cail_penalized.append(checkpoint_count + 1)
    return {
        "strict_checkpoint_count": checkpoint_count,
        "strict_unresolved_count": sum(
            1 for row in rows if not row.get("final_integrated_pass")
        ),
        "drs_penalized_mean": (
            sum(drs_penalized) / len(drs_penalized) if drs_penalized else None
        ),
        "cail_penalized_mean": (
            sum(cail_penalized) / len(cail_penalized) if cail_penalized else None
        ),
        "dependency_resolution_efficiency_mean": (
            sum(dependency_resolution_efficiency)
            / len(dependency_resolution_efficiency)
            if dependency_resolution_efficiency
            else None
        ),
        "cail_observed_count": cail.get("observed_count", len(observed_cail)),
        "cail_unresolved_count": cail.get("unobserved_count", total - len(observed_cail)),
        "cail_total_dependency_views": total,
        "cail_nonzero_count": sum(1 for value in observed_cail if value != 0),
        "cail_max": cail.get("max"),
        "cail_mean": cail.get("mean"),
        "drs_observed_count": drs_summary.get("observed_count", len(observed_drs)),
        "drs_min": drs_summary.get("min"),
        "drs_max": drs_summary.get("max"),
        "sad_proxy_candidate_count": 0,
        "per_report_cail_summary": "strict_dependency_metrics.json: "
        + "; ".join(
            f"{row.get('dependency_id')} DRS={row.get('strict_DRS')} CAIL={row.get('strict_CAIL')}"
            for row in rows
        ),
    }


def strict_dependency_diagnostics(run_dir: Path) -> dict[str, Any]:
    strict = load_json(run_dir / "strict_dependency_metrics.json", None)
    if not strict:
        return {
            "strict_dependency_count": None,
            "strict_upstream_resolved_count": None,
            "strict_downstream_resolved_count": None,
            "strict_integrated_resolved_count": None,
            "strict_unresolved_dependency_ids": "",
            "strict_upstream_only_dependency_ids": "",
            "strict_dependency_trace": "",
        }
    rows = strict.get("dependency_metrics", []) or []
    unresolved = []
    upstream_only = []
    trace = []
    upstream_count = 0
    downstream_count = 0
    integrated_count = 0
    for row in rows:
        dependency_id = row.get("dependency_id")
        upstream_step = row.get("upstream_resolution_step")
        downstream_step = row.get("downstream_resolution_step")
        drs = row.get("strict_DRS")
        cail = row.get("strict_CAIL")
        if isinstance(upstream_step, int):
            upstream_count += 1
        if isinstance(downstream_step, int):
            downstream_count += 1
        if row.get("final_integrated_pass"):
            integrated_count += 1
        else:
            unresolved.append(dependency_id)
        if isinstance(upstream_step, int) and not isinstance(downstream_step, int):
            upstream_only.append(dependency_id)
        trace.append(
            f"{dependency_id}:up={fmt(upstream_step)},down={fmt(downstream_step)},DRS={fmt(drs)},CAIL={fmt(cail)}"
        )
    return {
        "strict_dependency_count": len(rows),
        "strict_upstream_resolved_count": upstream_count,
        "strict_downstream_resolved_count": downstream_count,
        "strict_integrated_resolved_count": integrated_count,
        "strict_unresolved_dependency_ids": "; ".join(str(item) for item in unresolved if item),
        "strict_upstream_only_dependency_ids": "; ".join(str(item) for item in upstream_only if item),
        "strict_dependency_trace": "<br>".join(trace),
    }


def modified_files_from_patch(run_dir: Path) -> list[str]:
    patch = read_text(run_dir / "patch.diff")
    files = []
    for line in patch.splitlines():
        if line.startswith("+++ b/"):
            files.append(line[len("+++ b/") :])
    return sorted(set(files))


def hygiene_files(run_dir: Path) -> list[str]:
    out = []
    for path in modified_files_from_patch(run_dir):
        name = Path(path).name.lower()
        if path.startswith("test_") or any(marker in name for marker in HYGIENE_MARKERS):
            out.append(path)
    return out


def final_test_collection_status(run_dir: Path) -> tuple[bool, int]:
    """Return collection-failure evidence without treating it as an infra failure."""
    report = load_json(run_dir / "report.json", {})
    collectors = report.get("collectors", []) if isinstance(report, dict) else []
    failed_collectors = sum(
        1
        for collector in collectors or []
        if isinstance(collector, dict) and collector.get("outcome") == "failed"
    )

    output = "\n".join(
        read_text(path)
        for path in sorted(run_dir.glob("*_test_output.txt"))
        if ".pre_manifest_retest." not in path.name
    )
    lowered = output.lower()
    collection_failure = failed_collectors > 0 or any(
        marker in lowered
        for marker in (
            "error collecting",
            "errors during collection",
            "importerror while loading conftest",
        )
    )
    if failed_collectors:
        return collection_failure, failed_collectors

    matches = re.findall(r"(?:^|\s)(\d+) errors? in [0-9.]+s", lowered)
    if matches:
        return collection_failure, int(matches[-1])
    return collection_failure, 1 if collection_failure else 0


def final_test_timeout_status(run_dir: Path) -> bool:
    report = load_json(run_dir / "report.json", {})
    metadata = report.get("asyncodebench", {}) if isinstance(report, dict) else {}
    if metadata.get("timed_out") is True:
        return True
    output = "\n".join(
        read_text(path)
        for path in sorted(run_dir.glob("*_test_output.txt"))
        if ".pre_manifest_retest." not in path.name
    )
    return "final pytest timed out" in output.lower()


def normalize_expected_test_totals(rows: list[dict[str, Any]]) -> None:
    """Give model-induced collection failures a numeric, task-level denominator.

    A protocol that breaks imports may collect zero tests even though its sibling
    protocols establish the size of the same fixed evaluator suite. We retain the
    collection-failure flag and use that common observed suite size as the expected
    denominator. This makes pass-rate aggregation numeric without claiming that the
    unexecuted assertions were ordinary pytest failures.
    """
    observed_totals = {
        row.get("final_tests_total")
        for row in rows
        if isinstance(row.get("final_tests_total"), int)
        and row.get("final_tests_total") > 0
        and not row.get("final_test_collection_failure")
        and not row.get("final_test_timed_out")
    }
    expected_total = next(iter(observed_totals)) if len(observed_totals) == 1 else None
    for row in rows:
        total = row.get("final_tests_total")
        row["final_tests_observed_total"] = total
        incomplete_evaluation = bool(
            row.get("final_test_collection_failure") or row.get("final_test_timed_out")
        )
        if (
            incomplete_evaluation
            and expected_total is not None
            and (not isinstance(total, int) or total < expected_total)
        ):
            row["final_tests_total"] = expected_total
            if row.get("final_test_collection_failure"):
                row["final_tests_total_source"] = (
                    "sibling_protocol_expected_total_due_collection_failure"
                )
            else:
                row["final_tests_total_source"] = (
                    "sibling_protocol_expected_total_due_evaluator_timeout"
                )
        elif isinstance(total, int) and total > 0:
            row["final_tests_total_source"] = "report.summary.total"
        else:
            row["final_tests_total_source"] = "unavailable"


def run_row(mode: str, run_dir: Path) -> dict[str, Any]:
    summary = load_json(run_dir / "process_metrics_summary.json", {})
    if not summary:
        raise FileNotFoundError(f"Missing process_metrics_summary.json in {run_dir}")

    primary = summary.get("primary_outcome", {})
    cost = summary.get("cost_metrics", {})
    process = summary.get("process_metrics", {})
    reports = collect_dependency_reports(run_dir, summary)
    final_adpr, final_adpr_source = final_integrated_adpr(run_dir, summary)
    mean_adpr, per_agent_adpr = mean_per_agent_adpr(reports)
    cail = strict_cail_summary(run_dir) or cail_summary(reports)
    strict_diag = strict_dependency_diagnostics(run_dir)

    patch = process.get("patch_file_generation_success", {})
    conflict = process.get("textual_patch_conflict", {})
    semantic = process.get("semantic_integration_failure", {})
    overlap = process.get("asynchronous_overlap_duration", {})
    scope = process.get("scope_violation_rate", {})
    stale = process.get("stale_assumption_incident_count", {})
    missing = process.get("missing_communication_incident_count", {})
    review = process.get("reviewer_repair_success", {})
    duplicate = process.get("duplicated_file_or_function_work", {})
    hygiene = hygiene_files(run_dir)
    attempts = patch.get("agent_attempt_count")
    merged = review.get("merged_review_count")
    manager_reviews = review.get("manager_review_count")
    nonmerged = None
    if isinstance(attempts, int) and isinstance(merged, int) and manager_reviews:
        nonmerged = max(0, attempts - merged)
    duplicate_symbols = duplicate.get("duplicated_contract_unique_added_symbols") or []
    collection_failure, collection_error_count = final_test_collection_status(run_dir)
    test_timed_out = final_test_timeout_status(run_dir)

    return {
        "mode": mode,
        "run_dir": str(run_dir),
        "final_tests_passed": primary.get("passed"),
        "final_tests_failed": primary.get("failed"),
        "final_tests_errors": primary.get("errors"),
        "final_tests_total": primary.get("total"),
        "final_tests_observed_total": primary.get("total"),
        "final_tests_total_source": "report.summary.total",
        "final_test_collection_failure": collection_failure,
        "final_test_collection_error_count": collection_error_count,
        "final_test_timed_out": test_timed_out,
        "final_success": primary.get("final_success"),
        "final_integrated_ADPR": final_adpr,
        "final_integrated_ADPR_source": final_adpr_source,
        "mean_per_agent_view_ADPR": mean_adpr,
        "per_agent_view_ADPR": per_agent_adpr,
        "FSR": 1.0 if primary.get("final_success") else 0.0,
        "subagent_artifact_failure_count": patch.get("failed_agent_attempt_count"),
        "agent_attempt_count": patch.get("agent_attempt_count"),
        "nonmerged_attempt_count": nonmerged,
        "manager_review_count": manager_reviews,
        "merged_review_count": review.get("merged_review_count"),
        "merge_failure_count": conflict.get("conflict_event_count"),
        "semantic_integration_failure": semantic.get("observed"),
        "scope_violation_count": scope.get("violating_agent_attempt_count"),
        "scope_violation_rate": scope.get("SVR"),
        "artifact_hygiene_violation_count": len(hygiene),
        "artifact_hygiene_files": "; ".join(hygiene),
        "duplicated_contract_unique_symbol_count": duplicate.get(
            "duplicated_contract_unique_added_symbol_count"
        ),
        "duplicated_contract_symbols": "; ".join(
            f"{item.get('consumer_file')}::{item.get('added_symbol')}"
            for item in duplicate_symbols
        ),
        "async_overlap_seconds": overlap.get("overlap_seconds_with_two_or_more_agents_active"),
        "runtime_seconds": cost.get("wall_clock_duration_seconds") or cost.get("runtime_seconds"),
        "input_tokens": cost.get("input_tokens"),
        "output_tokens": cost.get("output_tokens"),
        "total_tokens": cost.get("total_tokens"),
        "cost_usd": cost.get("cost_usd"),
        "cost_accounting_note": "",
        "sad_proxy_candidate_count": stale.get("automatic_proxy_count", cail["sad_proxy_candidate_count"]),
        "missing_communication_proxy_count": missing.get("automatic_proxy_count"),
        **cail,
        **strict_diag,
    }


def indexed_artifacts(run_dir: Path) -> list[dict[str, Any]]:
    paths = set()
    for pattern in INDEXED_PATTERNS:
        paths.update(path for path in run_dir.glob(pattern) if path.is_file())
    artifacts = []
    for path in sorted(paths):
        artifacts.append(
            {
                "path": str(path),
                "relative_to_run_dir": str(path.relative_to(run_dir)),
                "sha256": sha256_file(path),
                "size_bytes": path.stat().st_size,
            }
        )
    return artifacts


def combined_checksum(artifacts: list[dict[str, Any]]) -> str:
    h = hashlib.sha256()
    for artifact in artifacts:
        h.update(artifact["relative_to_run_dir"].encode())
        h.update(b"\0")
        h.update(artifact["sha256"].encode())
        h.update(b"\n")
    return h.hexdigest()


def write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    fieldnames = [
        "mode",
        "runner_adapter",
        "final_tests_passed",
        "final_tests_failed",
        "final_tests_errors",
        "final_tests_total",
        "final_tests_observed_total",
        "final_tests_total_source",
        "final_test_collection_failure",
        "final_test_collection_error_count",
        "final_test_timed_out",
        "final_success",
        "final_integrated_ADPR",
        "final_integrated_ADPR_source",
        "mean_per_agent_view_ADPR",
        "per_agent_view_ADPR",
        "FSR",
        "subagent_artifact_failure_count",
        "agent_attempt_count",
        "nonmerged_attempt_count",
        "manager_review_count",
        "merged_review_count",
        "merge_failure_count",
        "semantic_integration_failure",
        "scope_violation_count",
        "scope_violation_rate",
        "artifact_hygiene_violation_count",
        "artifact_hygiene_files",
        "duplicated_contract_unique_symbol_count",
        "duplicated_contract_symbols",
        "async_overlap_seconds",
        "runtime_seconds",
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "cost_usd",
        "cost_accounting_note",
        "cail_observed_count",
        "cail_unresolved_count",
        "cail_total_dependency_views",
        "cail_nonzero_count",
        "cail_max",
        "cail_mean",
        "strict_checkpoint_count",
        "strict_unresolved_count",
        "drs_penalized_mean",
        "cail_penalized_mean",
        "dependency_resolution_efficiency_mean",
        "drs_observed_count",
        "drs_min",
        "drs_max",
        "strict_dependency_count",
        "strict_upstream_resolved_count",
        "strict_downstream_resolved_count",
        "strict_integrated_resolved_count",
        "strict_unresolved_dependency_ids",
        "strict_upstream_only_dependency_ids",
        "strict_dependency_trace",
        "sad_proxy_candidate_count",
        "missing_communication_proxy_count",
        "per_report_cail_summary",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field) for field in fieldnames})


def write_index(args: argparse.Namespace, rows: list[dict[str, Any]], runs: dict[str, Path], path: Path) -> None:
    run_payload = {}
    for mode, run_dir in sorted(runs.items()):
        artifacts = indexed_artifacts(run_dir)
        run_payload[mode] = {
            "run_dir": str(run_dir),
            "artifact_count": len(artifacts),
            "artifacts": artifacts,
            "checksum": combined_checksum(artifacts),
            "report_json": str(run_dir / "report.json"),
            "process_metrics_summary": str(run_dir / "process_metrics_summary.json"),
            "final_tests_total_source": next(
                (row.get("final_tests_total_source") for row in rows if row["mode"] == mode),
                None,
            ),
            "final_test_collection_failure": next(
                (
                    row.get("final_test_collection_failure")
                    for row in rows
                    if row["mode"] == mode
                ),
                None,
            ),
            "final_test_timed_out": next(
                (row.get("final_test_timed_out") for row in rows if row["mode"] == mode),
                None,
            ),
            "final_integrated_ADPR_source": next(
                (row.get("final_integrated_ADPR_source") for row in rows if row["mode"] == mode),
                None,
            ),
        }
    payload = {
        "task": args.task,
        "model": args.model,
        "model_tag": args.model_tag,
        "runner_adapter": args.runner_adapter,
        "metrics_manifest": str(args.metrics),
        "analysis_command": "Generated by scripts/summarize_model_task_runs.py",
        "generated_files": {
            "report_markdown": str(args.output_dir / f"{args.task}.md"),
            "metrics_table_csv": str(args.output_dir / f"{args.task}_{args.model_tag}_metrics_table.csv"),
            "artifact_index_json": str(path),
        },
        "notes": [
            "Raw run artifact directories are ignored by git unless explicitly force-added or uploaded to shared storage.",
            "final_integrated_ADPR is canonical for paper tables; mean_per_agent_view_ADPR is diagnostic only.",
            "For model-induced collection failures, a common positive test total observed in sibling protocols is used as the expected denominator; the collection-failure flag remains explicit.",
        ],
        "runs": run_payload,
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def fmt(value: Any) -> str:
    if value is None:
        return "unavailable"
    if isinstance(value, float):
        return f"{value:.4g}"
    return str(value)


def write_markdown(args: argparse.Namespace, rows: list[dict[str, Any]], path: Path) -> None:
    any_success = any(row.get("final_success") for row in rows)
    lines = [
        f"# {args.model_tag} {args.task} Experiment Report",
        "",
        f"Task: `commit0:{args.task}`",
        "",
        f"Model: `{args.model}`",
        "",
        f"Runner adapter: `{args.runner_adapter}`",
        "",
        "This report is an automatically generated AsynCodeBench evaluation record.",
        (
            "At least one protocol reaches final success."
            if any_success
            else "No protocol reaches final success; interpret this as a failure-structure record."
        ),
        "",
        "## Canonical Metrics Table",
        "",
        "ADPR convention: `final_integrated_ADPR` is the canonical run-level dependency score for paper tables. `mean_per_agent_view_ADPR` is diagnostic only.",
        "",
        "| Mode | Final tests | Final success | Final-integrated ADPR | Mean per-agent ADPR | Async overlap | Runtime | Tokens | Cost | Artifact failures | Non-merged attempts | Merge failures | Scope violations | SVR | Duplicated contracts | Hygiene violations |",
        "| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            "| {mode} | {passed}/{total} | {success} | {adpr} | {mean_adpr} | {overlap}s | {runtime}s | {tokens} | ${cost} | {failures} | {nonmerged} | {merge} | {scope} | {svr} | {dups} | {hygiene} |".format(
                mode=row["mode"],
                passed=fmt(row.get("final_tests_passed")),
                total=fmt(row.get("final_tests_total")),
                success=fmt(row.get("final_success")),
                adpr=fmt(row.get("final_integrated_ADPR")),
                mean_adpr=fmt(row.get("mean_per_agent_view_ADPR")),
                overlap=fmt(row.get("async_overlap_seconds")),
                runtime=fmt(row.get("runtime_seconds")),
                tokens=fmt(row.get("total_tokens")),
                cost=fmt(row.get("cost_usd")),
                failures=fmt(row.get("subagent_artifact_failure_count")),
                nonmerged=fmt(row.get("nonmerged_attempt_count")),
                merge=fmt(row.get("merge_failure_count")),
                scope=fmt(row.get("scope_violation_count")),
                svr=fmt(row.get("scope_violation_rate")),
                dups=fmt(row.get("duplicated_contract_unique_symbol_count")),
                hygiene=fmt(row.get("artifact_hygiene_violation_count")),
            )
        )
    collection_failures = [
        row for row in rows if row.get("final_test_collection_failure")
    ]
    if collection_failures:
        lines.extend(
            [
                "",
                "Collection-failure normalization:",
                "",
            ]
        )
        for row in collection_failures:
            lines.append(
                "- `{mode}` failed during pytest collection with {errors} collector error(s). "
                "Its pass count is recorded as `{passed}/{total}` using the fixed suite size "
                "confirmed by sibling protocols; this is a model-induced execution "
                "failure, not an infrastructure failure.".format(
                    mode=row["mode"],
                    errors=fmt(row.get("final_test_collection_error_count")),
                    passed=fmt(row.get("final_tests_passed")),
                    total=fmt(row.get("final_tests_total")),
                )
            )
    timed_out = [row for row in rows if row.get("final_test_timed_out")]
    if timed_out:
        lines.extend(["", "Evaluator-timeout normalization:", ""])
        for row in timed_out:
            lines.append(
                "- `{mode}` exceeded the fixed evaluator timeout. Its conservative "
                "pass count is recorded as `{passed}/{total}` using the suite size "
                "confirmed by sibling protocols; the timeout flag remains explicit.".format(
                    mode=row["mode"],
                    passed=fmt(row.get("final_tests_passed")),
                    total=fmt(row.get("final_tests_total")),
                )
            )
    lines.extend(
        [
            "",
            "## Per-Agent Dependency Views",
            "",
            "| Mode | Final-integrated ADPR source | Mean per-agent ADPR | Per-agent-view ADPR |",
            "| --- | --- | ---: | --- |",
        ]
    )
    for row in rows:
        lines.append(
            f"| {row['mode']} | {row.get('final_integrated_ADPR_source')} | {fmt(row.get('mean_per_agent_view_ADPR'))} | {row.get('per_agent_view_ADPR') or ''} |"
        )
    lines.extend(
        [
            "",
            "## Strict Async Dependency Summary",
            "",
            "| Mode | Checkpoints T | Unresolved deps | Mean DRS penalized | Mean CAIL penalized | Mean DRE | DRS observed | DRS min | DRS max | CAIL observed | CAIL unobserved | CAIL raw mean |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in rows:
        lines.append(
            "| {mode} | {checkpoints} | {unresolved} | {drs_penalized} | {cail_penalized} | {dre} | {drs_count} | {drs_min} | {drs_max} | {cail_obs} | {cail_unres} | {cail_mean} |".format(
                mode=row["mode"],
                checkpoints=fmt(row.get("strict_checkpoint_count")),
                unresolved=fmt(row.get("strict_unresolved_count")),
                drs_penalized=fmt(row.get("drs_penalized_mean")),
                cail_penalized=fmt(row.get("cail_penalized_mean")),
                dre=fmt(row.get("dependency_resolution_efficiency_mean")),
                drs_count=fmt(row.get("drs_observed_count")),
                drs_min=fmt(row.get("drs_min")),
                drs_max=fmt(row.get("drs_max")),
                cail_obs=fmt(row.get("cail_observed_count")),
                cail_unres=fmt(row.get("cail_unresolved_count")),
                cail_mean=fmt(row.get("cail_mean")),
            )
        )
    lines.extend(
        [
            "",
            "## Strict Dependency Diagnostics",
            "",
            "This table is based on `dependency_probe_checkpoints.jsonl` and shows whether each protocol resolves producer-side, consumer-side, and integrated dependency probes.",
            "",
            "| Mode | Dependencies | Upstream resolved | Downstream resolved | Integrated resolved | Unresolved dependencies | Upstream-only dependencies |",
            "| --- | ---: | ---: | ---: | ---: | --- | --- |",
        ]
    )
    for row in rows:
        lines.append(
            "| {mode} | {total} | {upstream} | {downstream} | {integrated} | {unresolved} | {upstream_only} |".format(
                mode=row["mode"],
                total=fmt(row.get("strict_dependency_count")),
                upstream=fmt(row.get("strict_upstream_resolved_count")),
                downstream=fmt(row.get("strict_downstream_resolved_count")),
                integrated=fmt(row.get("strict_integrated_resolved_count")),
                unresolved=row.get("strict_unresolved_dependency_ids") or "",
                upstream_only=row.get("strict_upstream_only_dependency_ids") or "",
            )
        )
    lines.extend(
        [
            "",
            "## Strict Per-Dependency Trace",
            "",
            "| Mode | Trace |",
            "| --- | --- |",
        ]
    )
    for row in rows:
        lines.append(
            f"| {row['mode']} | {row.get('strict_dependency_trace') or ''} |"
        )
    lines.extend(["", "## Interpretation Notes", ""])
    if any_success:
        lines.append(
            "This run is suitable for success-case analysis: final pass is achieved, and dependency/coordination metrics explain the process differences between protocols."
        )
    else:
        lines.append(
            "This run is suitable for failure-structure analysis: final scores alone do not describe dependency progress, local-vs-integrated gaps, or integration burden."
        )
    lines.append("")
    lines.append("Important conventions:")
    lines.append("")
    lines.append("- Use `final_integrated_ADPR` in main paper tables.")
    lines.append("- Use `mean_per_agent_view_ADPR` to discuss local or partial dependency progress.")
    lines.append("- Treat `SAD-proxy` as candidate evidence until dependency-version visibility logs are available.")
    lines.append("- Treat duplicated contract symbols as coordination diagnostics, not as artifact hygiene violations.")
    lines.append("- Keep raw run directories or shared-storage copies for reproducibility; this report only indexes them.")
    lines.append("")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    runs = parse_runs(args.run)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    for mode in MODE_ORDER:
        if mode not in runs:
            continue
        row = run_row(mode, runs[mode])
        row["runner_adapter"] = args.runner_adapter
        rows.append(row)
    for mode in sorted(set(runs) - set(MODE_ORDER)):
        row = run_row(mode, runs[mode])
        row["runner_adapter"] = args.runner_adapter
        rows.append(row)

    normalize_expected_test_totals(rows)

    csv_path = args.output_dir / f"{args.task}_{args.model_tag}_metrics_table.csv"
    index_path = args.output_dir / f"{args.task}_{args.model_tag}_artifact_index.json"
    md_path = args.output_dir / f"{args.task}.md"

    write_csv(rows, csv_path)
    write_index(args, rows, runs, index_path)
    write_markdown(args, rows, md_path)

    print(f"wrote: {csv_path}")
    print(f"wrote: {index_path}")
    print(f"wrote: {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
