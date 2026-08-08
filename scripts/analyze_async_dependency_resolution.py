#!/usr/bin/env python
"""Analyze dependency-resolution checkpoints from an agent event log."""

from __future__ import annotations

import argparse
from pathlib import Path

from asyncodebench.metrics.dependency_resolution import (
    analyze_dependency_resolution,
    final_evaluator_checkpoint,
    load_json,
    load_jsonl,
    max_logical_iteration,
    write_json,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compute observed dependency-resolution iterations from an "
            "AsynCodeBench metrics manifest and async-swe-agents event log."
        )
    )
    parser.add_argument(
        "--metrics",
        type=Path,
        default=Path(
            "manifests/pilot/v0.3/metrics/commit0_cachetools_async_metrics.json"
        ),
        help="Path to a metrics annotation manifest.",
    )
    parser.add_argument(
        "--events",
        type=Path,
        required=True,
        help="Path to agent_events/*.jsonl.",
    )
    parser.add_argument(
        "--dependency-id",
        default=None,
        help="Optional dependency_id filter.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Path where the JSON analysis report should be written.",
    )
    parser.add_argument(
        "--final-test-output",
        type=Path,
        default=None,
        help=(
            "Optional runner-level final pytest output. If provided, it is "
            "added as a final integrated dependency checkpoint."
        ),
    )
    parser.add_argument(
        "--final-logical-iteration",
        type=int,
        default=None,
        help=(
            "Logical iteration assigned to --final-test-output. Defaults to "
            "one after the largest event-log iteration."
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    metrics = load_json(args.metrics)
    events = load_jsonl(args.events)
    extra_checkpoints = []
    if args.final_test_output is not None:
        final_iteration = args.final_logical_iteration
        if final_iteration is None:
            max_iteration = max_logical_iteration(events)
            final_iteration = None if max_iteration is None else max_iteration + 1
        checkpoint = final_evaluator_checkpoint(
            metrics=metrics,
            output=args.final_test_output.read_text(encoding="utf-8"),
            checkpoint_id="runner-final-evaluator",
            logical_iteration=final_iteration,
            exit_code=0,
        )
        if checkpoint is not None:
            extra_checkpoints.append(checkpoint)

    report = analyze_dependency_resolution(
        metrics=metrics,
        events=events,
        dependency_id=args.dependency_id,
        extra_checkpoints=extra_checkpoints,
    )
    write_json(report, args.output)

    print(f"task_id: {report['task_id']}")
    print(f"checkpoint_count: {report['checkpoint_count']}")
    print(
        "ADPR_strict: "
        f"{report['ADPR_strict']['resolved']}/"
        f"{report['ADPR_strict']['total']} = "
        f"{report['ADPR_strict']['value']}"
    )
    for result in report["dependency_results"]:
        strict = result["strict_integrated_resolution"]
        composed = result["composed_resolution"]
        print(result["dependency_id"])
        print(f"  strict_iteration: {None if strict is None else strict['logical_iteration']}")
        print(f"  composed_iteration: {composed['logical_iteration']}")
        upstream = result["upstream_resolution"]
        downstream = result["downstream_resolution"]
        print(
            "  upstream/downstream: "
            f"{None if upstream is None else upstream['logical_iteration']} / "
            f"{None if downstream is None else downstream['logical_iteration']}"
        )
    print(f"wrote: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
