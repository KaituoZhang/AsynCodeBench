#!/usr/bin/env python
"""Build the cross-source Phase 2 candidate status index."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--commit0", type=Path, required=True)
    parser.add_argument("--swebench", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def _status_counts(records: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in records:
        status = str(record["status"])
        counts[status] = counts.get(status, 0) + 1
    return dict(sorted(counts.items()))


def _commit0_records(
    commit0: dict[str, Any],
    evidence_file: Path,
) -> list[dict[str, Any]]:
    return [
        {
            "task_id": candidate["task_id"],
            "task_source": "Commit0",
            "status": "ready_for_independent_annotation",
            "evidence_file": str(evidence_file),
        }
        for candidate in commit0["candidates"]
    ]


def _swebench_records(
    swebench: dict[str, Any],
    evidence_file: Path,
) -> list[dict[str, Any]]:
    if "records" in swebench:
        return [
            {
                "task_id": record["instance_id"],
                "task_source": "SWE-bench",
                "status": "pending_official_environment_timing",
                "evidence_file": str(evidence_file),
                "measurement_status": record["measurement_status"],
                "repo": record["repo"],
                "base_commit": record["base_commit"],
            }
            for record in swebench["records"]
        ]
    return [
        {
            "task_id": task["instance_id"],
            "task_source": "SWE-bench",
            "status": "pending_base_commit_materialization",
            "evidence_file": str(evidence_file),
            "repo": task["repo"],
            "base_commit": task["base_commit"],
        }
        for task in swebench["selected"]
    ]


def main() -> int:
    args = parse_args()
    commit0 = json.loads(args.commit0.read_text(encoding="utf-8"))
    swebench = json.loads(args.swebench.read_text(encoding="utf-8"))
    records = _commit0_records(commit0, args.commit0)
    records.extend(_swebench_records(swebench, args.swebench))
    records.sort(key=lambda record: record["task_id"])
    status_counts = _status_counts(records)
    payload = {
        "phase": 2,
        "specification_version": "v0.2",
        "candidate_count": len(records),
        "status_counts": status_counts,
        "ready_for_independent_annotation": status_counts.get(
            "ready_for_independent_annotation",
            0,
        ),
        "pending_base_commit_materialization": status_counts.get(
            "pending_base_commit_materialization",
            0,
        ),
        "pending_official_environment_timing": status_counts.get(
            "pending_official_environment_timing",
            0,
        ),
        "records": records,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
