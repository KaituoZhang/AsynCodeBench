#!/usr/bin/env python3
"""Aggregate an explicitly selected set of valid AsynCodeBench run bundles."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from statistics import mean
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--prefix", required=True)
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def optional_mean(values: list[float | None]) -> float | None:
    observed = [value for value in values if value is not None]
    return mean(observed) if observed else None


def strict_metrics(path: Path) -> dict[str, float | int]:
    data = load_json(path)
    checkpoint_count = int(data["checkpoint_count"])
    dependencies = data["dependency_metrics"]
    drs_values: list[float] = []
    cail_values: list[float] = []
    dre_values: list[float] = []
    unresolved = 0

    for dependency in dependencies:
        drs = dependency.get("strict_DRS")
        upstream = dependency.get("upstream_resolution_step")
        downstream = dependency.get("downstream_resolution_step")
        if drs is None:
            unresolved += 1
            drs_values.append(checkpoint_count + 1)
            dre_values.append(0.0)
        else:
            drs_values.append(float(drs))
            dre_values.append(1 - (float(drs) - 1) / checkpoint_count)

        if upstream is None:
            cail_values.append(checkpoint_count + 1)
        elif downstream is None:
            cail_values.append(checkpoint_count + 1 - float(upstream))
        else:
            cail_values.append(max(0.0, float(downstream) - float(upstream)))

    adpr = data["final_integrated_ADPR"]
    return {
        "dependency_count": len(dependencies),
        "resolved_dependency_count": int(adpr["resolved"]),
        "unresolved_dependency_count": unresolved,
        "ADPR": float(adpr["value"]),
        "penalized_DRS": mean(drs_values),
        "penalized_CAIL": mean(cail_values),
        "DRE": mean(dre_values),
        "checkpoint_count": checkpoint_count,
    }


def selected_rows(selection: dict[str, Any]) -> list[dict[str, Any]]:
    output_root = ROOT / selection["output_root"]
    rows: list[dict[str, Any]] = []
    for task, run_id in selection["task_run_ids"].items():
        for protocol in selection["protocols"]:
            run_dir = output_root / task / protocol / run_id
            bundle = load_json(run_dir / "run_bundle.json")
            if bundle.get("status") != "valid":
                raise ValueError(f"Invalid selected bundle: {run_dir}")
            if not bundle.get("eligibility", {}).get("official_aggregate"):
                raise ValueError(f"Ineligible selected bundle: {run_dir}")
            if bundle.get("provenance", {}).get("model") != selection["model"]:
                raise ValueError(f"Model mismatch in {run_dir}")
            profile = bundle.get("execution_profile", {}).get("profile_id")
            if profile != selection["execution_profile"]:
                raise ValueError(f"Execution profile mismatch in {run_dir}: {profile}")

            strict = strict_metrics(run_dir / "strict_dependency_metrics.json")
            process = load_json(run_dir / "process_metrics_summary.json")
            formal = process["formal_metrics"]
            cost = load_json(run_dir / "cost.json")["total"]
            final_test = bundle["final_test"]
            collected = int(final_test.get("collected") or 0)
            passed = int(final_test.get("passed") or 0)
            pass_rate = passed / collected if collected else 0.0

            rows.append(
                {
                    "model": selection["model_label"],
                    "task": task,
                    "protocol": protocol,
                    "run_id": run_id,
                    "run_dir": str(run_dir.relative_to(ROOT)),
                    "bundle_status": bundle["status"],
                    "official_aggregate_eligible": True,
                    "final_success": bool(final_test["success"]),
                    "final_pass_rate": pass_rate,
                    "final_tests_passed": passed,
                    "final_tests_collected": collected,
                    "evaluation_failure_kind": final_test.get("evaluation_failure_kind"),
                    **strict,
                    "FSAR": formal["FSAR"]["value"],
                    "IFR": formal["IFR"]["value"],
                    "SVR": formal["SVR"]["value"],
                    "MRR": formal["MRR"]["value"],
                    "total_tokens": int(cost["total_tokens"]),
                    "runtime_seconds": float(cost["wall_clock_duration"]),
                    "benchmark_revision": bundle["provenance"]["benchmark_revision"],
                    "generation_configuration_sha256": bundle["provenance"][
                        "generation_configuration_sha256"
                    ],
                    "execution_profile": profile,
                }
            )
    return rows


def protocol_summaries(
    rows: list[dict[str, Any]], protocols: list[str]
) -> list[dict[str, Any]]:
    summaries = []
    for protocol in protocols:
        selected = [row for row in rows if row["protocol"] == protocol]
        summaries.append(
            {
                "model": selected[0]["model"],
                "protocol": protocol,
                "successful_tasks": sum(row["final_success"] for row in selected),
                "task_count": len(selected),
                "success_rate": mean(float(row["final_success"]) for row in selected),
                "mean_test_pass_rate": mean(row["final_pass_rate"] for row in selected),
                "mean_ADPR": mean(row["ADPR"] for row in selected),
                "mean_unresolved_dependencies": mean(
                    row["unresolved_dependency_count"] for row in selected
                ),
                "penalized_DRS": mean(row["penalized_DRS"] for row in selected),
                "penalized_CAIL": mean(row["penalized_CAIL"] for row in selected),
                "mean_DRE": mean(row["DRE"] for row in selected),
                "FSAR": optional_mean([row["FSAR"] for row in selected]),
                "IFR": optional_mean([row["IFR"] for row in selected]),
                "SVR": optional_mean([row["SVR"] for row in selected]),
                "MRR": optional_mean([row["MRR"] for row in selected]),
                "mean_tokens": mean(row["total_tokens"] for row in selected),
                "mean_runtime_seconds": mean(row["runtime_seconds"] for row in selected),
                "serving": "local vLLM",
                "harness_revision": "mixed",
                "execution_profile": selected[0]["execution_profile"],
            }
        )
    return summaries


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=list(rows[0]), lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)


def fmt(value: float | None, digits: int = 3) -> str:
    return "N/A" if value is None else f"{value:.{digits}f}"


def write_report(
    path: Path,
    selection: dict[str, Any],
    rows: list[dict[str, Any]],
    summaries: list[dict[str, Any]],
) -> None:
    revisions = Counter(row["benchmark_revision"] for row in rows)
    configurations = Counter(row["generation_configuration_sha256"] for row in rows)
    protocols = selection["protocols"]
    lines = [
        "# Qwen3.6-27B Results on AsynCodeBench",
        "",
        "## Scope and admission",
        "",
        f"- Model: `{selection['model']}`",
        f"- Tasks: {len(selection['task_run_ids'])} official tasks",
        f"- Runs: {len(rows)} selected task-protocol bundles",
        f"- Execution profile: `{selection['execution_profile']}`",
        "- Per-run validation: all selected bundles are valid and official-aggregate eligible",
        "- Campaign status: **descriptive mixed-lineage aggregate**",
        "",
        "The set is not a lineage-homogeneous official campaign because it spans "
        f"{len(revisions)} benchmark revisions and {len(configurations)} generation-configuration hashes. "
        "The results can be used for descriptive analysis and figures, but the provenance caveat must remain visible.",
        "",
        "## Aggregate results",
        "",
        "| Protocol | Success | Pass | ADPR | Unresolved | DRE | DRS | CAIL | FSAR | IFR | SVR | MRR | Tokens | Runtime |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in summaries:
        lines.append(
            "| {protocol} | {success}/{tasks} ({success_rate:.1%}) | {pass_rate:.1%} | "
            "{adpr:.1%} | {unresolved:.3f} | {dre:.1%} | {drs:.3f} | {cail:.3f} | "
            "{fsar} | {ifr} | {svr} | {mrr} | {tokens:.3f}M | {runtime:.1f} min |".format(
                protocol=row["protocol"],
                success=row["successful_tasks"],
                tasks=row["task_count"],
                success_rate=row["success_rate"],
                pass_rate=row["mean_test_pass_rate"],
                adpr=row["mean_ADPR"],
                unresolved=row["mean_unresolved_dependencies"],
                dre=row["mean_DRE"],
                drs=row["penalized_DRS"],
                cail=row["penalized_CAIL"],
                fsar="N/A" if row["FSAR"] is None else f"{row['FSAR']:.1%}",
                ifr="N/A" if row["IFR"] is None else f"{row['IFR']:.1%}",
                svr="N/A" if row["SVR"] is None else f"{row['SVR']:.1%}",
                mrr="N/A" if row["MRR"] is None else f"{row['MRR']:.1%}",
                tokens=row["mean_tokens"] / 1_000_000,
                runtime=row["mean_runtime_seconds"] / 60,
            )
        )

    lines.extend(
        [
            "",
            "## Per-task outcomes",
            "",
            "Each cell is `success / pass rate / ADPR`.",
            "",
            "| Task | Single | Serial | Async private | CAID |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
    )
    by_cell = {(row["task"], row["protocol"]): row for row in rows}
    labels = ("single", "serial_specialists", "async_private", "caid_manager")
    for task in selection["task_run_ids"]:
        cells = []
        for protocol in labels:
            row = by_cell[(task, protocol)]
            cells.append(
                f"{'yes' if row['final_success'] else 'no'} / "
                f"{row['final_pass_rate']:.1%} / {row['ADPR']:.1%}"
            )
        lines.append(f"| {task} | " + " | ".join(cells) + " |")

    lines.extend(["", "## Provenance distribution", ""])
    lines.append("| Field | Value | Runs |")
    lines.append("| --- | --- | ---: |")
    for revision, count in revisions.most_common():
        lines.append(f"| Benchmark revision | `{revision}` | {count} |")
    for config, count in configurations.most_common():
        lines.append(f"| Generation configuration | `{config}` | {count} |")

    failures = Counter(
        row["evaluation_failure_kind"]
        for row in rows
        if row["evaluation_failure_kind"]
    )
    lines.extend(["", "## Exceptional evaluator outcomes", ""])
    if failures:
        for kind, count in failures.items():
            lines.append(f"- `{kind}`: {count} valid model-failure runs")
    else:
        lines.append("- None")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    selection = load_json(args.selection)
    rows = selected_rows(selection)
    expected = len(selection["task_run_ids"]) * len(selection["protocols"])
    if len(rows) != expected:
        raise ValueError(f"Expected {expected} selected runs, found {len(rows)}")
    summaries = protocol_summaries(rows, selection["protocols"])
    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.output_dir / f"{args.prefix}_per_run.csv", rows)
    write_csv(args.output_dir / f"{args.prefix}_summary_by_protocol.csv", summaries)
    write_report(
        args.output_dir / f"{args.prefix.upper()}_RESULTS.md",
        selection,
        rows,
        summaries,
    )
    print(f"Selected runs: {len(rows)}")
    for summary in summaries:
        print(
            summary["protocol"],
            f"success={summary['successful_tasks']}/{summary['task_count']}",
            f"pass={summary['mean_test_pass_rate']:.3f}",
            f"ADPR={summary['mean_ADPR']:.3f}",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
