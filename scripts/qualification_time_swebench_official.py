#!/usr/bin/env python
"""Measure selected SWE-bench tasks in the official Docker harness."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from asynccodebench.qualification.swebench_materialization import (
    SWEbenchMaterializationInventory,
)
from asynccodebench.qualification.swebench_timing import (
    build_official_timing_inventory,
    write_official_timing_inventory,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--materialized", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--split", default="test")
    parser.add_argument("--timeout-seconds", type=int, default=1800)
    parser.add_argument(
        "--log-root",
        type=Path,
        default=Path("outputs/swebench_timing"),
    )
    parser.add_argument(
        "--namespace",
        default="swebench",
        help='Docker image namespace. Use "none" to build locally.',
    )
    parser.add_argument("--instance-id", action="append", default=())
    parser.add_argument("--limit", type=int)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    namespace = None if args.namespace == "none" else args.namespace
    materialized = SWEbenchMaterializationInventory.model_validate(
        json.loads(args.materialized.read_text(encoding="utf-8"))
    )
    inventory = build_official_timing_inventory(
        materialized=materialized,
        split=args.split,
        run_id=args.run_id,
        namespace=namespace,
        timeout_seconds=args.timeout_seconds,
        log_root=args.log_root,
        instance_ids=tuple(args.instance_id),
        limit=args.limit,
    )
    write_official_timing_inventory(inventory, args.output)
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
