#!/usr/bin/env python3
"""Aggregate per-task AsynCodeBench records for one model."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from statistics import mean
from typing import Any


OFFICIAL_TASKS = [
    "cachetools",
    "deprecated",
    "portalocker",
    "tinydb",
    "wcwidth",
    "requests",
    "simpy",
    "parsel",
    "filesystem_spec",
    "marshmallow",
    "graphene",
    "imapclient",
    "pexpect",
    "flask",
    "python-rsa",
    "cookiecutter",
]
MODE_ORDER = ["single", "serial_specialists", "async_private", "CAID_multi"]
DISPLAY_METRICS = [
    "final_success",
    "final_tests",
    "final_pass_rate",
    "final_integrated_ADPR",
    "drs_penalized_mean",
    "cail_penalized_mean",
    "dependency_resolution_efficiency_mean",
    "strict_unresolved_count",
    "total_tokens",
    "runtime_seconds",
    "async_overlap_seconds",
    "subagent_artifact_failure_count",
    "final_test_collection_failure",
    "final_test_timed_out",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--model-tag", required=True)
    parser.add_argument("--tasks", nargs="*", default=OFFICIAL_TASKS)
    return parser.parse_args()


def as_float(value: Any) -> float | None:
    if value in (None, "", "unavailable"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def as_bool(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes"}


def average(rows: list[dict[str, Any]], field: str) -> float | None:
    values = [as_float(row.get(field)) for row in rows]
    present = [value for value in values if value is not None]
    return mean(present) if present else None


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def load_rows(args: argparse.Namespace) -> list[dict[str, Any]]:
    rows = []
    for task in args.tasks:
        path = args.input_dir / f"{task}_{args.model_tag}_metrics_table.csv"
        index_path = args.input_dir / f"{task}_{args.model_tag}_artifact_index.json"
        if not path.exists():
            raise FileNotFoundError(path)
        if not index_path.exists():
            raise FileNotFoundError(index_path)
        artifact_index = json.loads(index_path.read_text(encoding="utf-8"))
        task_rows = list(csv.DictReader(path.open(encoding="utf-8")))
        if [row.get("mode") for row in task_rows] != MODE_ORDER:
            raise ValueError(f"Unexpected mode order in {path}")
        for row in task_rows:
            passed = as_float(row.get("final_tests_passed"))
            total = as_float(row.get("final_tests_total"))
            enriched = {
                "model": args.model_tag,
                "task": task,
                **row,
                "run_dir": (artifact_index.get("runs", {}).get(row["mode"], {}) or {}).get(
                    "run_dir"
                ),
                "final_pass_rate": (
                    passed / total if passed is not None and total else None
                ),
                "final_tests": f"{row.get('final_tests_passed')}/{row.get('final_tests_total')}",
            }
            rows.append(enriched)
    return rows


def summary_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summaries = []
    for mode in MODE_ORDER:
        selected = [row for row in rows if row["mode"] == mode]
        summaries.append(
            {
                "mode": mode,
                "task_count": len(selected),
                "success_count": sum(as_bool(row.get("final_success")) for row in selected),
                "success_rate": mean(as_bool(row.get("final_success")) for row in selected),
                "mean_final_pass_rate": average(selected, "final_pass_rate"),
                "mean_ADPR": average(selected, "final_integrated_ADPR"),
                "mean_DRS_penalized": average(selected, "drs_penalized_mean"),
                "mean_CAIL_penalized": average(selected, "cail_penalized_mean"),
                "mean_DRE": average(selected, "dependency_resolution_efficiency_mean"),
                "mean_unresolved_dependencies": average(selected, "strict_unresolved_count"),
                "full_ADPR_task_count": sum(
                    as_float(row.get("final_integrated_ADPR")) == 1.0 for row in selected
                ),
                "positive_ADPR_task_count": sum(
                    (as_float(row.get("final_integrated_ADPR")) or 0.0) > 0.0
                    for row in selected
                ),
                "mean_tokens": average(selected, "total_tokens"),
                "total_tokens": sum(as_float(row.get("total_tokens")) or 0.0 for row in selected),
                "mean_runtime_seconds": average(selected, "runtime_seconds"),
                "total_runtime_seconds": sum(
                    as_float(row.get("runtime_seconds")) or 0.0 for row in selected
                ),
                "mean_async_overlap_seconds": average(selected, "async_overlap_seconds"),
                "collection_failure_run_count": sum(
                    as_bool(row.get("final_test_collection_failure")) for row in selected
                ),
                "evaluator_timeout_run_count": sum(
                    as_bool(row.get("final_test_timed_out")) for row in selected
                ),
                "artifact_failure_count": sum(
                    as_float(row.get("subagent_artifact_failure_count")) or 0.0
                    for row in selected
                ),
            }
        )
    return summaries


def pivot_rows(rows: list[dict[str, Any]], tasks: list[str]) -> list[dict[str, Any]]:
    indexed = {(row["task"], row["mode"]): row for row in rows}
    output = []
    for task in tasks:
        result: dict[str, Any] = {"task": task}
        for mode in MODE_ORDER:
            row = indexed[(task, mode)]
            for metric in DISPLAY_METRICS:
                result[f"{mode}_{metric}"] = row.get(metric)
        output.append(result)
    return output


def write_compact_markdown(
    path: Path,
    summaries: list[dict[str, Any]],
    rows: list[dict[str, Any]],
    tasks: list[str],
) -> None:
    lines = [
        "# Model Aggregate Metrics",
        "",
        "## Protocol Summary",
        "",
        "| Mode | Success | Mean pass | Mean ADPR | Mean DRE | Mean DRS* | Mean CAIL* | Mean tokens | Mean runtime |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in summaries:
        lines.append(
            "| {mode} | {success:.3f} | {passed:.3f} | {adpr:.3f} | {dre:.3f} | {drs:.3f} | {cail:.3f} | {tokens:.0f} | {runtime:.1f}s |".format(
                mode=row["mode"],
                success=row["success_rate"],
                passed=row["mean_final_pass_rate"],
                adpr=row["mean_ADPR"],
                dre=row["mean_DRE"],
                drs=row["mean_DRS_penalized"],
                cail=row["mean_CAIL_penalized"],
                tokens=row["mean_tokens"],
                runtime=row["mean_runtime_seconds"],
            )
        )
    lines.extend(
        [
            "",
            "`*` Penalized DRS and CAIL use each run's `T+1` unresolved penalty. Because T differs by protocol, interpret cross-protocol means together with ADPR, DRE, and checkpoint counts.",
            "",
            "## Per-Task Core Results",
            "",
            "| Task | Single pass / ADPR | Serial pass / ADPR | Async-private pass / ADPR | CAID pass / ADPR |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
    )
    indexed = {(row["task"], row["mode"]): row for row in rows}
    for task in tasks:
        cells = []
        for mode in MODE_ORDER:
            row = indexed[(task, mode)]
            cells.append(f"{row['final_tests']} / {float(row['final_integrated_ADPR']):.3f}")
        lines.append(f"| {task} | " + " | ".join(cells) + " |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_grouped_display_csv(
    path: Path, rows: list[dict[str, Any]], tasks: list[str]
) -> None:
    metrics = [
        ("Success Rate", "final_success"),
        ("Mean Pass", "final_pass_rate"),
        ("Mean ADPR", "final_integrated_ADPR"),
        ("Mean CAIL", "cail_penalized_mean"),
        ("Mean DRS", "drs_penalized_mean"),
        ("Mean DRE", "dependency_resolution_efficiency_mean"),
        ("Tokens", "total_tokens"),
        ("Runtime", "runtime_seconds"),
    ]
    labels = {
        "single": "Single",
        "serial_specialists": "Serial",
        "async_private": "Async Private",
        "CAID_multi": "CAID Multi",
    }
    indexed = {(row["task"], row["mode"]): row for row in rows}
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        group_header = ["Task"]
        metric_header = ["Task"]
        for mode in MODE_ORDER:
            group_header.extend([labels[mode]] + [""] * (len(metrics) - 1))
            metric_header.extend(name for name, _ in metrics)
        writer.writerow(group_header)
        writer.writerow(metric_header)
        for task in tasks:
            output: list[Any] = [task]
            for mode in MODE_ORDER:
                row = indexed[(task, mode)]
                for _, field in metrics:
                    value = row.get(field)
                    if field == "final_success":
                        value = 1.0 if as_bool(value) else 0.0
                    output.append(value)
            writer.writerow(output)


def main() -> int:
    args = parse_args()
    rows = load_rows(args)
    summaries = summary_rows(rows)
    pivots = pivot_rows(rows, args.tasks)
    prefix = f"{args.model_tag}_{len(args.tasks)}task"

    preferred = [
        "model", "task", "mode", "final_success", "final_tests_passed",
        "final_tests_failed", "final_tests_errors", "final_tests_total",
        "final_tests", "final_pass_rate", "final_integrated_ADPR",
        "strict_dependency_count", "strict_integrated_resolved_count",
        "strict_unresolved_count", "strict_checkpoint_count",
        "drs_penalized_mean", "cail_penalized_mean",
        "dependency_resolution_efficiency_mean", "total_tokens",
        "runtime_seconds", "cost_usd", "async_overlap_seconds",
        "subagent_artifact_failure_count", "nonmerged_attempt_count",
        "merge_failure_count", "semantic_integration_failure",
        "final_test_collection_failure", "final_test_timed_out", "run_dir",
    ]
    all_fields = preferred + sorted(
        {key for row in rows for key in row} - set(preferred)
    )
    write_csv(args.output_dir / f"{prefix}_all_metrics_master.csv", rows, all_fields)
    write_csv(
        args.output_dir / f"{prefix}_summary_by_mode.csv",
        summaries,
        list(summaries[0]),
    )
    write_csv(
        args.output_dir / f"{prefix}_per_task_pivot.csv",
        pivots,
        list(pivots[0]),
    )
    write_compact_markdown(
        args.output_dir / f"{prefix}_compact_metrics_table.md",
        summaries,
        rows,
        args.tasks,
    )
    write_grouped_display_csv(
        args.output_dir / f"{prefix}_grouped_display_table.csv",
        rows,
        args.tasks,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
