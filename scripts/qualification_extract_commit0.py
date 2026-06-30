#!/usr/bin/env python
"""Extract unlabelled Commit0 candidates from public ``commit0`` refs."""

from __future__ import annotations

import argparse
from pathlib import Path

from asynccodebench.qualification.commit0_candidates import (
    extract_commit0_inventory,
    write_candidate_inventory,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repos-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=float, default=60.0)
    parser.add_argument("repositories", nargs="+")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repositories = tuple(args.repos_root / name for name in args.repositories)
    inventory = extract_commit0_inventory(
        repositories,
        timeout_seconds=args.timeout_seconds,
    )
    output = write_candidate_inventory(inventory, args.output)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
