#!/usr/bin/env python
"""Compute strict DRS and CAIL from AsyncCodeBench probe checkpoints."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compute strict dependency metrics from dependency_probe_checkpoints.jsonl. "
            "Unlike event-log inference, this uses explicit probe-test checkpoints."
        )
    )
    parser.add_argument("--metrics", type=Path, required=True)
    parser.add_argument("--checkpoints", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--print-summary", action="store_true")
    return parser.parse_args()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def write_json(payload: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _group_pass(checkpoint: dict[str, Any], dependency_id: str, group_name: str) -> bool:
    for row in checkpoint.get("dependency_results", []) or []:
        if row.get("dependency_id") != dependency_id:
            continue
        return bool((row.get("groups", {}).get(group_name) or {}).get("passed"))
    return False


def _first_step(checkpoints: list[dict[str, Any]], dependency_id: str, group_name: str, *, integrated_only: bool = False) -> int | None:
    for checkpoint in checkpoints:
        if integrated_only and checkpoint.get("workspace_kind") != "integrated_workspace":
            continue
        if _group_pass(checkpoint, dependency_id, group_name):
            step = checkpoint.get("logical_step")
            return step if isinstance(step, int) else None
    return None


def _last_final_checkpoint(checkpoints: list[dict[str, Any]]) -> dict[str, Any] | None:
    finals = [
        checkpoint
        for checkpoint in checkpoints
        if checkpoint.get("checkpoint_type") == "final_integrated"
        or checkpoint.get("checkpoint_id") == "final_integrated"
    ]
    return finals[-1] if finals else (checkpoints[-1] if checkpoints else None)


def compute_strict_metrics(metrics: dict[str, Any], checkpoints: list[dict[str, Any]]) -> dict[str, Any]:
    checkpoints = sorted(
        checkpoints,
        key=lambda row: (
            row.get("logical_step") if isinstance(row.get("logical_step"), int) else 10**9,
            row.get("recorded_at") or "",
        ),
    )
    final_checkpoint = _last_final_checkpoint(checkpoints)
    dependency_rows = []
    final_resolved = 0

    for dependency in metrics.get("dependency_points", []):
        dependency_id = dependency.get("dependency_id")
        upstream_step = _first_step(checkpoints, dependency_id, "upstream")
        downstream_step = _first_step(checkpoints, dependency_id, "downstream")
        strict_drs = _first_step(
            checkpoints,
            dependency_id,
            "integrated",
            integrated_only=True,
        )
        final_integrated_pass = (
            _group_pass(final_checkpoint, dependency_id, "integrated")
            if final_checkpoint
            else False
        )
        if final_integrated_pass:
            final_resolved += 1

        cail = None
        if isinstance(upstream_step, int) and isinstance(downstream_step, int):
            cail = downstream_step - upstream_step

        dependency_rows.append(
            {
                "dependency_id": dependency_id,
                "producer_agent": dependency.get("producer_agent"),
                "consumer_agent": dependency.get("consumer_agent"),
                "strict_DRS": strict_drs,
                "upstream_resolution_step": upstream_step,
                "downstream_resolution_step": downstream_step,
                "strict_CAIL": cail,
                "final_integrated_pass": final_integrated_pass,
                "status": (
                    "resolved"
                    if final_integrated_pass
                    else "unresolved_final_integrated"
                ),
            }
        )

    total = len(metrics.get("dependency_points", []))
    observed_drs = [
        row["strict_DRS"]
        for row in dependency_rows
        if isinstance(row.get("strict_DRS"), int)
    ]
    observed_cail = [
        row["strict_CAIL"]
        for row in dependency_rows
        if isinstance(row.get("strict_CAIL"), int)
    ]
    return {
        "schema_version": "0.1",
        "task_id": metrics.get("task_id"),
        "metric_annotation_id": metrics.get("metric_annotation_id"),
        "checkpoint_count": len(checkpoints),
        "final_checkpoint_id": None if not final_checkpoint else final_checkpoint.get("checkpoint_id"),
        "final_integrated_ADPR": {
            "resolved": final_resolved,
            "total": total,
            "value": (final_resolved / total) if total else None,
        },
        "strict_DRS": {
            "observed_count": len(observed_drs),
            "min": min(observed_drs) if observed_drs else None,
            "max": max(observed_drs) if observed_drs else None,
            "unresolved_count": total - len(observed_drs),
        },
        "strict_CAIL": {
            "observed_count": len(observed_cail),
            "min": min(observed_cail) if observed_cail else None,
            "max": max(observed_cail) if observed_cail else None,
            "mean": (sum(observed_cail) / len(observed_cail)) if observed_cail else None,
            "unobserved_count": total - len(observed_cail),
        },
        "dependency_metrics": dependency_rows,
    }


def main() -> int:
    args = parse_args()
    metrics = load_json(args.metrics)
    checkpoints = load_jsonl(args.checkpoints)
    report = compute_strict_metrics(metrics, checkpoints)
    write_json(report, args.output)
    if args.print_summary:
        adpr = report["final_integrated_ADPR"]
        cail = report["strict_CAIL"]
        drs = report["strict_DRS"]
        print(f"task_id: {report['task_id']}")
        print(f"checkpoints: {report['checkpoint_count']}")
        print(f"final_integrated_ADPR: {adpr['resolved']}/{adpr['total']} = {adpr['value']}")
        print(f"strict_DRS: observed={drs['observed_count']} min={drs['min']} max={drs['max']}")
        print(f"strict_CAIL: observed={cail['observed_count']} min={cail['min']} max={cail['max']} mean={cail['mean']}")
        print(f"wrote: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
