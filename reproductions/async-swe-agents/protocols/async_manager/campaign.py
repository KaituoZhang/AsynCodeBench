"""Validate and summarize an online Async-Manager campaign."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from statistics import mean

from protocols.async_manager.results import validate

EXPECTED_TASKS = frozenset(
    {
        "asyncodebench:cachetools",
        "asyncodebench:deprecated",
        "asyncodebench:portalocker",
        "asyncodebench:tinydb",
        "asyncodebench:wcwidth",
        "asyncodebench:requests",
        "asyncodebench:simpy",
        "asyncodebench:parsel",
        "asyncodebench:filesystem_spec",
        "asyncodebench:marshmallow",
        "asyncodebench:graphene",
        "asyncodebench:imapclient",
        "asyncodebench:pexpect",
        "asyncodebench:flask",
        "asyncodebench:python-rsa",
        "asyncodebench:cookiecutter",
        "pr-hard:apache-tvm-20018",
        "pr-hard:apache-tvm-20073",
        "pr-hard:apache-tvm-20107",
        "pr-hard:apache-tvm-20153",
    }
)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def trajectory_metrics(checkpoints: list[dict]) -> dict:
    canonical = sorted(
        (
            row
            for row in checkpoints
            if row.get("workspace_kind") == "integrated_workspace"
        ),
        key=lambda row: (
            row.get("logical_step", 10**9),
            row.get("recorded_at", ""),
        ),
    )
    dependency_ids = sorted(
        {
            result.get("dependency_id")
            for row in canonical
            for result in row.get("dependency_results", []) or []
            if result.get("dependency_id")
        }
    )
    total_steps = len(canonical)
    rows = []
    for dependency_id in dependency_ids:
        states = []
        for checkpoint in canonical:
            matching = next(
                (
                    result
                    for result in checkpoint.get("dependency_results", []) or []
                    if result.get("dependency_id") == dependency_id
                ),
                {},
            )
            states.append(
                bool((matching.get("groups", {}).get("integrated") or {}).get("passed"))
            )
        drs = next((index for index, passed in enumerate(states, 1) if passed), None)
        scs = next(
            (
                index
                for index in range(1, total_steps + 1)
                if states[index - 1] and all(states[index - 1 :])
            ),
            None,
        )
        regressions = sum(
            before and not after
            for before, after in zip(states, states[1:], strict=False)
        )
        penalty = total_steps + 1
        rows.append(
            {
                "dependency_id": dependency_id,
                "final_pass": states[-1] if states else False,
                "DRS": drs,
                "SCS": scs,
                "RC": regressions,
                "DRS_normalized_penalized": (drs or penalty) / penalty,
                "SCS_normalized_penalized": (scs or penalty) / penalty,
                "RC_normalized": (
                    regressions / (total_steps - 1) if total_steps > 1 else None
                ),
            }
        )
    resolved = sum(row["final_pass"] for row in rows)
    return {
        "checkpoint_count": total_steps,
        "dependency_count": len(rows),
        "resolved_dependencies": resolved,
        "ADPR": resolved / len(rows) if rows else None,
        "DRS_normalized_penalized": (
            mean(row["DRS_normalized_penalized"] for row in rows) if rows else None
        ),
        "SCS_normalized_penalized": (
            mean(row["SCS_normalized_penalized"] for row in rows) if rows else None
        ),
        "RC_normalized": (
            mean(
                row["RC_normalized"] for row in rows if row["RC_normalized"] is not None
            )
            if total_steps > 1 and rows
            else None
        ),
        "dependencies": rows,
    }


def discover(root: Path, run_id: str) -> list[Path]:
    return sorted(
        path for path in root.glob(f"**/async_manager/{run_id}") if path.is_dir()
    )


def task_row(directory: Path) -> dict:
    metadata = read_json(directory / "run_metadata.json")
    bundle = read_json(directory / "run_bundle.json")
    cost = read_json(directory / "cost.json")
    trajectory = trajectory_metrics(
        read_jsonl(directory / "dependency_probe_checkpoints.jsonl")
    )
    online = bundle.get("online_manager", {})
    final = bundle.get("final_test", {})
    collected = int(final.get("collected", 0) or 0)
    passed = int(final.get("passed", 0) or 0)
    return {
        "task_id": metadata.get("task_id"),
        "directory": str(directory.resolve()),
        "bundle_status": bundle.get("status"),
        "final_success": bool(final.get("success")),
        "final_pass_rate": passed / collected if collected else None,
        **{key: value for key, value in trajectory.items() if key != "dependencies"},
        "total_tokens": cost.get("total", {}).get("total_tokens"),
        "runtime_seconds": float((directory / "runtime.txt").read_text().strip()),
        "manager_intervention_events": online.get("events", 0),
        "manager_interventions_accepted": online.get("accepted", 0),
        "manager_scope_rejections": online.get("scope_rejected", 0),
        "trajectory": trajectory["dependencies"],
    }


def optional_mean(rows: list[dict], key: str):
    values = [row[key] for row in rows if row.get(key) is not None]
    return mean(values) if values else None


def summarize(rows: list[dict], issues: dict[str, list[str]]) -> dict:
    resolved = sum(row["resolved_dependencies"] for row in rows)
    dependencies = sum(row["dependency_count"] for row in rows)
    events = sum(row["manager_intervention_events"] for row in rows)
    accepted = sum(row["manager_interventions_accepted"] for row in rows)
    return {
        "schema_version": "async-manager-campaign-summary-v1",
        "protocol": "async_manager",
        "valid": not issues,
        "validation_issues": issues,
        "task_count": len(rows),
        "metrics": {
            "FSR_higher_is_better": (
                mean(row["final_success"] for row in rows) if rows else None
            ),
            "mean_final_pass_rate_higher_is_better": optional_mean(
                rows, "final_pass_rate"
            ),
            "macro_ADPR_higher_is_better": optional_mean(rows, "ADPR"),
            "micro_ADPR_higher_is_better": (
                resolved / dependencies if dependencies else None
            ),
            "mean_DRS_normalized_penalized_lower_is_better": optional_mean(
                rows, "DRS_normalized_penalized"
            ),
            "mean_SCS_normalized_penalized_lower_is_better": optional_mean(
                rows, "SCS_normalized_penalized"
            ),
            "mean_RC_normalized_lower_is_better": optional_mean(rows, "RC_normalized"),
            "mean_tokens_lower_is_better": optional_mean(rows, "total_tokens"),
            "mean_runtime_seconds_lower_is_better": optional_mean(
                rows, "runtime_seconds"
            ),
            "manager_intervention_acceptance_rate_diagnostic": (
                accepted / events if events else None
            ),
        },
        "tasks": rows,
    }


def write_outputs(summary: dict, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "async_manager_campaign_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    fields = [
        "task_id",
        "bundle_status",
        "final_success",
        "final_pass_rate",
        "checkpoint_count",
        "dependency_count",
        "resolved_dependencies",
        "ADPR",
        "DRS_normalized_penalized",
        "SCS_normalized_penalized",
        "RC_normalized",
        "total_tokens",
        "runtime_seconds",
        "manager_intervention_events",
        "manager_interventions_accepted",
        "manager_scope_rejections",
        "directory",
    ]
    with (output_dir / "async_manager_task_metrics.csv").open(
        "w", newline="", encoding="utf-8"
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(summary["tasks"])
    metrics = summary["metrics"]
    lines = [
        "# Async-Manager Campaign Summary",
        "",
        f"Validated: **{summary['valid']}**; tasks: **{summary['task_count']}**.",
        "",
        "| Metric | Value | Direction |",
        "| --- | ---: | :---: |",
    ]
    for key, value in metrics.items():
        direction = "↑" if "higher_is_better" in key else "↓"
        if key.endswith("_diagnostic"):
            direction = "diagnostic"
        rendered = "N/A" if value is None else f"{value:.4f}"
        label = key.replace("_higher_is_better", "").replace("_lower_is_better", "")
        lines.append(f"| {label} | {rendered} | {direction} |")
    (output_dir / "async_manager_campaign_summary.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--require-complete", action="store_true")
    args = parser.parse_args()

    directories = discover(args.root, args.run_id)
    issues = {
        str(directory): found
        for directory in directories
        if (found := validate(directory))
    }
    rows = [task_row(directory) for directory in directories]
    task_ids = [row["task_id"] for row in rows]
    if len(task_ids) != len(set(task_ids)):
        issues["campaign"] = ["duplicate_task_ids"]
    if args.require_complete and set(task_ids) != EXPECTED_TASKS:
        issues.setdefault("campaign", []).append(
            "task_set_mismatch:missing="
            + repr(sorted(EXPECTED_TASKS - set(task_ids)))
            + ":unexpected="
            + repr(sorted(set(task_ids) - EXPECTED_TASKS))
        )
    summary = summarize(rows, issues)
    write_outputs(summary, args.output_dir)
    print(json.dumps({"valid": summary["valid"], "tasks": len(rows)}, indent=2))
    return 0 if summary["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
