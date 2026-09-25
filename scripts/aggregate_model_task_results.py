#!/usr/bin/env python3
"""Aggregate per-task AsynCodeBench records for one model."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from datetime import datetime, timezone
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
    "imapclient",
    "pexpect",
    "flask",
    "python-rsa",
    "cookiecutter",
]
LEGACY_MODE_ORDER = ["single", "serial_specialists", "async_private", "caid_manager"]
FIVE_PROTOCOL_MODE_ORDER = [*LEGACY_MODE_ORDER, "async_manager"]
MODE_ORDER = FIVE_PROTOCOL_MODE_ORDER
MODE_ALIASES = {"CAID_multi": "caid_manager"}
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
    parser.add_argument(
        "--protocol-set",
        choices=("auto", "legacy-four", "official-five"),
        default="auto",
        help="Infer four/five rows from inputs, or require one protocol set.",
    )
    parser.add_argument(
        "--allow-ineligible",
        action="store_true",
        help=(
            "Allow legacy, exploratory, or invalid rows in a non-official aggregate. "
            "The default is to reject every row whose run bundle does not set "
            "eligibility.official_aggregate=true."
        ),
    )
    return parser.parse_args()


def resolve_mode_order(args: argparse.Namespace) -> list[str]:
    if args.protocol_set == "legacy-four":
        return LEGACY_MODE_ORDER
    if args.protocol_set == "official-five":
        return FIVE_PROTOCOL_MODE_ORDER
    first = args.input_dir / f"{args.tasks[0]}_{args.model_tag}_metrics_table.csv"
    if not first.is_file():
        raise FileNotFoundError(first)
    observed = [
        MODE_ALIASES.get(row.get("mode"), row.get("mode"))
        for row in csv.DictReader(first.open(encoding="utf-8"))
    ]
    if observed == LEGACY_MODE_ORDER:
        return LEGACY_MODE_ORDER
    if observed == FIVE_PROTOCOL_MODE_ORDER:
        return FIVE_PROTOCOL_MODE_ORDER
    raise ValueError(f"Cannot infer protocol set from {first}: {observed}")


def as_float(value: Any) -> float | None:
    if value in (None, "", "unavailable"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def as_bool(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes"}


def format_number(value: Any, format_spec: str) -> str:
    number = as_float(value)
    return "N/A" if number is None else format(number, format_spec)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def configured_execution_profile(relative_path: str) -> tuple[str, str]:
    path = Path(__file__).resolve().parents[1] / relative_path
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload["profile_id"], sha256_file(path)


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
        if artifact_index.get("task") != task:
            raise ValueError(
                f"Artifact index {index_path} records task={artifact_index.get('task')!r}, "
                f"expected {task!r}"
            )
        if artifact_index.get("model_tag") != args.model_tag:
            raise ValueError(
                f"Artifact index {index_path} records "
                f"model_tag={artifact_index.get('model_tag')!r}, "
                f"expected {args.model_tag!r}"
            )
        task_rows = list(csv.DictReader(path.open(encoding="utf-8")))
        normalized_modes = [
            MODE_ALIASES.get(row.get("mode"), row.get("mode")) for row in task_rows
        ]
        if normalized_modes != MODE_ORDER:
            raise ValueError(f"Unexpected mode order in {path}")
        for row, normalized_mode in zip(task_rows, normalized_modes, strict=True):
            source_mode = row.get("mode")
            row["mode"] = normalized_mode
            passed = as_float(row.get("final_tests_passed"))
            total = as_float(row.get("final_tests_total"))
            run_records = artifact_index.get("runs", {})
            run_record = run_records.get(normalized_mode) or run_records.get(source_mode) or {}
            admission = run_record.get("result_admission", {})
            for field in (
                "run_bundle_schema_version",
                "run_bundle_status",
                "recorded_model",
                "recorded_subagent_model",
                "execution_profile_id",
                "execution_profile_sha256",
                "generation_configuration_sha256",
                "recorded_agent_adapter_name",
                "recorded_agent_adapter_class",
                "recorded_agent_adapter_package",
                "recorded_agent_adapter_package_version",
                "recorded_agent_adapter_source_sha256",
                "recorded_agent_adapter_config_sha256",
                "functional_metrics_eligible",
                "dependency_metrics_eligible",
                "efficiency_metrics_eligible",
                "official_profile_matched",
                "provenance_complete",
                "official_aggregate_eligible",
            ):
                if row.get(field) in (None, "") and field in admission:
                    row[field] = admission[field]
            if not as_bool(row.get("official_aggregate_eligible")) and not args.allow_ineligible:
                raise ValueError(
                    f"{task}/{normalized_mode} is not eligible for the official "
                    f"aggregate (bundle status={row.get('run_bundle_status') or 'missing'}). "
                    "Validate or rerun it, or pass --allow-ineligible only for an "
                    "explicitly exploratory aggregate."
                )
            if (
                as_bool(row.get("official_aggregate_eligible"))
                and row.get("recorded_model") != artifact_index.get("model")
            ):
                raise ValueError(
                    f"{task}/{normalized_mode} records model="
                    f"{row.get('recorded_model')!r}, but its artifact index records "
                    f"{artifact_index.get('model')!r}"
                )
            bundle_artifact = next(
                (
                    artifact
                    for artifact in run_record.get("artifacts", [])
                    if artifact.get("relative_to_run_dir") == "run_bundle.json"
                ),
                {},
            )
            if (
                as_bool(row.get("official_aggregate_eligible"))
                and not bundle_artifact.get("sha256")
            ):
                raise ValueError(
                    f"{task}/{normalized_mode} is eligible but its artifact index "
                    "does not contain run_bundle.json"
                )
            enriched = {
                "model": args.model_tag,
                "model_id": artifact_index.get("model"),
                "task": task,
                **row,
                "run_dir": run_record.get("run_dir"),
                "run_bundle_sha256": bundle_artifact.get("sha256"),
                "metrics_table_path": str(path),
                "metrics_table_sha256": sha256_file(path),
                "artifact_index_path": str(index_path),
                "artifact_index_sha256": sha256_file(index_path),
                "final_pass_rate": (
                    passed / total if passed is not None and total else None
                ),
                "final_tests": f"{row.get('final_tests_passed')}/{row.get('final_tests_total')}",
            }
            rows.append(enriched)
    return rows


def validate_campaign_lineage(args: argparse.Namespace, rows: list[dict[str, Any]]) -> None:
    if args.allow_ineligible:
        return

    if len(args.tasks) != len(set(args.tasks)):
        raise ValueError("Official aggregate task list contains duplicates")
    unknown_tasks = sorted(set(args.tasks) - set(OFFICIAL_TASKS))
    if unknown_tasks:
        raise ValueError(
            f"Official aggregate contains non-release tasks: {unknown_tasks}"
        )

    model_ids = {row.get("model_id") for row in rows if row.get("model_id")}
    if len(model_ids) != 1:
        raise ValueError(f"Official aggregate requires one model ID; found {model_ids}")

    recorded_models = {
        row.get("recorded_model") for row in rows if row.get("recorded_model")
    }
    if recorded_models != model_ids:
        raise ValueError(
            "Run-bundle model IDs do not match the per-task artifact indexes: "
            f"{recorded_models} != {model_ids}"
        )

    subagent_models = {row.get("recorded_subagent_model") for row in rows}
    if len(subagent_models) != 1 or None in subagent_models or "" in subagent_models:
        raise ValueError(
            f"Official aggregate requires one subagent model; found {subagent_models}"
        )

    adapter_identities = {
        (
            row.get("recorded_agent_adapter_name"),
            row.get("recorded_agent_adapter_class"),
            row.get("recorded_agent_adapter_package"),
            row.get("recorded_agent_adapter_package_version"),
            row.get("recorded_agent_adapter_source_sha256"),
            row.get("recorded_agent_adapter_config_sha256"),
        )
        for row in rows
    }
    if len(adapter_identities) != 1 or any(
        not identity[0]
        or not identity[1]
        or not identity[5]
        or (not identity[3] and not identity[4])
        for identity in adapter_identities
    ):
        raise ValueError(
            "Official aggregate requires one bundle-recorded agent adapter "
            f"identity; found {adapter_identities}"
        )

    execution_profiles = {
        (
            row.get("execution_profile_id"),
            row.get("execution_profile_sha256"),
        )
        for row in rows
    }
    profiles_complete = not any(
        not profile_id or not profile_sha256
        for profile_id, profile_sha256 in execution_profiles
    )
    compatible_five_protocol_profiles = False
    if MODE_ORDER == FIVE_PROTOCOL_MODE_ORDER and profiles_complete:
        legacy_profile = configured_execution_profile(
            "configs/evaluation/official_execution_profile.v2.json"
        )
        manager_profiles = {
            configured_execution_profile(path)
            for path in (
                "configs/evaluation/official_execution_profile.v3.json",
                "configs/evaluation/official_execution_profile.v4.json",
            )
        }
        selected_manager_profiles = {
            (
                row.get("execution_profile_id"),
                row.get("execution_profile_sha256"),
            )
            for row in rows
            if row["mode"] == "async_manager"
        }
        compatible_five_protocol_profiles = (
            len(selected_manager_profiles) == 1
            and selected_manager_profiles <= manager_profiles
            and execution_profiles == {legacy_profile, *selected_manager_profiles}
            and all(
                row["mode"] == "async_manager"
                or (
                    row.get("execution_profile_id"),
                    row.get("execution_profile_sha256"),
                )
                == legacy_profile
                for row in rows
            )
        )
    invalid_profile_set = (
        len(execution_profiles) != 1 and not compatible_five_protocol_profiles
    ) or not profiles_complete
    if invalid_profile_set:
        raise ValueError(
            "Official aggregate requires one execution profile ID and SHA256, "
            "or the registered v2/v3 profile pair for the five-protocol "
            "comparison; found "
            f"{execution_profiles}"
        )

    for task in args.tasks:
        selected = [row for row in rows if row["task"] == task]
        configuration_hashes = {
            row.get("generation_configuration_sha256")
            for row in selected
            if row.get("generation_configuration_sha256")
        }
        if len(configuration_hashes) != 1:
            raise ValueError(
                f"{task} protocols do not share one recorded generation "
                f"configuration: {configuration_hashes}"
            )


def write_campaign_manifest(
    path: Path,
    args: argparse.Namespace,
    rows: list[dict[str, Any]],
    aggregate_paths: list[Path],
) -> None:
    all_eligible = all(
        as_bool(row.get("official_aggregate_eligible")) for row in rows
    )
    full_task_set = len(args.tasks) == len(OFFICIAL_TASKS) and set(args.tasks) == set(
        OFFICIAL_TASKS
    )
    if all_eligible and full_task_set:
        scope = "official_full"
    elif all_eligible:
        scope = "official_profile_subset"
    else:
        scope = "exploratory"

    payload = {
        "schema_version": "asyncodebench-campaign-manifest-v1",
        "benchmark": "AsynCodeBench",
        "release": "v0.3",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "model_tag": args.model_tag,
        "model_id": next(
            (row.get("model_id") for row in rows if row.get("model_id")), None
        ),
        "scope": scope,
        "task_count": len(args.tasks),
        "run_count": len(rows),
        "reporting": {
            "runs_per_task_protocol_cell": 1,
            "statistical_unit": "task",
            "inference_scope": "descriptive_single_selected_run_per_cell",
            "retry_policy": "rerun_instrumentation_invalid_only",
        },
        "tasks": list(args.tasks),
        "protocols": MODE_ORDER,
        "execution_profile_ids": sorted(
            {
                row.get("execution_profile_id")
                for row in rows
                if row.get("execution_profile_id")
            }
        ),
        "execution_profiles": [
            {"profile_id": profile_id, "sha256": profile_sha256}
            for profile_id, profile_sha256 in sorted(
                {
                    (
                        row.get("execution_profile_id"),
                        row.get("execution_profile_sha256"),
                    )
                    for row in rows
                    if row.get("execution_profile_id")
                }
            )
        ],
        "runner_adapters": sorted(
            {
                row.get("runner_adapter")
                for row in rows
                if row.get("runner_adapter")
            }
        ),
        "agent_adapters": [
            {
                "name": name,
                "class": class_name,
                "package": package,
                "package_version": package_version,
                "source_sha256": source_sha256,
                "config_sha256": config_sha256,
            }
            for (
                name,
                class_name,
                package,
                package_version,
                source_sha256,
                config_sha256,
            ) in sorted(
                {
                    (
                        row.get("recorded_agent_adapter_name"),
                        row.get("recorded_agent_adapter_class"),
                        row.get("recorded_agent_adapter_package"),
                        row.get("recorded_agent_adapter_package_version"),
                        row.get("recorded_agent_adapter_source_sha256"),
                        row.get("recorded_agent_adapter_config_sha256"),
                    )
                    for row in rows
                    if row.get("recorded_agent_adapter_name")
                },
                key=lambda identity: tuple(value or "" for value in identity),
            )
        ],
        "admission": {
            "all_rows_official_aggregate_eligible": all_eligible,
            "allow_ineligible_used": bool(args.allow_ineligible),
        },
        "runs": [
            {
                "task": row["task"],
                "protocol": row["mode"],
                "run_dir": row.get("run_dir"),
                "run_bundle_status": row.get("run_bundle_status"),
                "official_aggregate_eligible": as_bool(
                    row.get("official_aggregate_eligible")
                ),
                "run_bundle_sha256": row.get("run_bundle_sha256"),
                "execution_profile": {
                    "profile_id": row.get("execution_profile_id"),
                    "sha256": row.get("execution_profile_sha256"),
                },
                "generation_configuration_sha256": row.get(
                    "generation_configuration_sha256"
                ),
                "agent_adapter": {
                    "name": row.get("recorded_agent_adapter_name"),
                    "class": row.get("recorded_agent_adapter_class"),
                    "package": row.get("recorded_agent_adapter_package"),
                    "package_version": row.get(
                        "recorded_agent_adapter_package_version"
                    ),
                    "source_sha256": row.get(
                        "recorded_agent_adapter_source_sha256"
                    ),
                    "config_sha256": row.get(
                        "recorded_agent_adapter_config_sha256"
                    ),
                },
                "metrics_table_sha256": row.get("metrics_table_sha256"),
                "artifact_index_sha256": row.get("artifact_index_sha256"),
            }
            for row in rows
        ],
        "aggregate_artifacts": [
            {
                "path": str(artifact),
                "sha256": sha256_file(artifact),
                "bytes": artifact.stat().st_size,
            }
            for artifact in aggregate_paths
        ],
    }
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def summary_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summaries = []
    for mode in MODE_ORDER:
        selected = [row for row in rows if row["mode"] == mode]
        summaries.append(
            {
                "mode": mode,
                "task_count": len(selected),
                "official_eligible_run_count": sum(
                    as_bool(row.get("official_aggregate_eligible"))
                    for row in selected
                ),
                "ineligible_run_count": sum(
                    not as_bool(row.get("official_aggregate_eligible"))
                    for row in selected
                ),
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
    protocol_labels = {
        "single": "Single",
        "serial_specialists": "Serial",
        "async_private": "Async-private",
        "caid_manager": "Async-RO-Manager",
        "async_manager": "Async-Manager",
    }
    lines = [
        "# Model Aggregate Metrics",
        "",
        (
            "Admission: all rows satisfy the released official aggregate contract."
            if all(as_bool(row.get("official_aggregate_eligible")) for row in rows)
            else "Admission: this is an exploratory aggregate containing one or more ineligible rows; do not report it as an official benchmark table."
        ),
        "",
        (
            "Scope: complete 16-task AsynCodeBench release."
            if tasks == OFFICIAL_TASKS
            else f"Scope: {len(tasks)}/16 task subset; this is not a complete benchmark result."
        ),
        "",
        "## Protocol Summary",
        "",
        "| Mode | Success | Mean pass | Mean ADPR | Mean DRE | Mean DRS* | Mean CAIL* | Mean tokens | Mean runtime |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in summaries:
        lines.append(
            "| {mode} | {success} | {passed} | {adpr} | {dre} | {drs} | {cail} | {tokens} | {runtime} |".format(
                mode=row["mode"],
                success=format_number(row["success_rate"], ".3f"),
                passed=format_number(row["mean_final_pass_rate"], ".3f"),
                adpr=format_number(row["mean_ADPR"], ".3f"),
                dre=format_number(row["mean_DRE"], ".3f"),
                drs=format_number(row["mean_DRS_penalized"], ".3f"),
                cail=format_number(row["mean_CAIL_penalized"], ".3f"),
                tokens=format_number(row["mean_tokens"], ".0f"),
                runtime=(
                    f"{format_number(row['mean_runtime_seconds'], '.1f')}s"
                    if row["mean_runtime_seconds"] is not None
                    else "N/A"
                ),
            )
        )
    lines.extend(
        [
            "",
            "`*` Penalized DRS and CAIL use each run's `T+1` unresolved penalty. Because T differs by protocol, interpret cross-protocol means together with ADPR, DRE, and checkpoint counts.",
            "",
            "## Per-Task Core Results",
            "",
            "| Task | "
            + " | ".join(
                f"{protocol_labels[mode]} pass / ADPR" for mode in MODE_ORDER
            )
            + " |",
            "| --- | " + " | ".join("---:" for _ in MODE_ORDER) + " |",
        ]
    )
    indexed = {(row["task"], row["mode"]): row for row in rows}
    for task in tasks:
        cells = []
        for mode in MODE_ORDER:
            row = indexed[(task, mode)]
            cells.append(
                f"{row['final_tests']} / "
                f"{format_number(row.get('final_integrated_ADPR'), '.3f')}"
            )
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
        "caid_manager": "Async RO Manager",
        "async_manager": "Async Manager",
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
    global MODE_ORDER
    args = parse_args()
    MODE_ORDER = resolve_mode_order(args)
    rows = load_rows(args)
    validate_campaign_lineage(args, rows)
    summaries = summary_rows(rows)
    pivots = pivot_rows(rows, args.tasks)
    prefix = f"{args.model_tag}_{len(args.tasks)}task"

    preferred = [
        "model", "task", "mode", "run_bundle_schema_version",
        "run_bundle_status", "functional_metrics_eligible",
        "dependency_metrics_eligible", "efficiency_metrics_eligible",
        "official_profile_matched", "execution_profile_id",
        "execution_profile_sha256", "provenance_complete",
        "official_aggregate_eligible", "recorded_agent_adapter_name",
        "recorded_agent_adapter_class", "recorded_agent_adapter_package",
        "recorded_agent_adapter_package_version",
        "recorded_agent_adapter_source_sha256",
        "recorded_agent_adapter_config_sha256",
        "final_success", "final_tests_passed",
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
    master_path = args.output_dir / f"{prefix}_all_metrics_master.csv"
    summary_path = args.output_dir / f"{prefix}_summary_by_mode.csv"
    pivot_path = args.output_dir / f"{prefix}_per_task_pivot.csv"
    markdown_path = args.output_dir / f"{prefix}_compact_metrics_table.md"
    grouped_path = args.output_dir / f"{prefix}_grouped_display_table.csv"
    campaign_path = args.output_dir / f"{prefix}_campaign_manifest.json"

    write_csv(master_path, rows, all_fields)
    write_csv(
        summary_path,
        summaries,
        list(summaries[0]),
    )
    write_csv(
        pivot_path,
        pivots,
        list(pivots[0]),
    )
    write_compact_markdown(
        markdown_path,
        summaries,
        rows,
        args.tasks,
    )
    write_grouped_display_csv(
        grouped_path, rows, args.tasks
    )
    write_campaign_manifest(
        campaign_path,
        args,
        rows,
        [master_path, summary_path, pivot_path, markdown_path, grouped_path],
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2) from None
