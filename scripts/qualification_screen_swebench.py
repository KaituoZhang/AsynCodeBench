#!/usr/bin/env python
"""Sanitize and screen an official SWE-bench Verified metadata snapshot."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from asyncodebench.qualification.swebench_screening import (
    build_sanitized_snapshot,
    load_dataset_server_pages,
    screen_candidates,
    write_model,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-info", type=Path, required=True)
    parser.add_argument("--pages", type=Path, nargs="+", required=True)
    parser.add_argument("--snapshot-output", type=Path, required=True)
    parser.add_argument("--screening-output", type=Path, required=True)
    parser.add_argument("--target-count", type=int, default=18)
    parser.add_argument("--max-per-repo", type=int, default=2)
    parser.add_argument("--min-fail-to-pass", type=int, default=1)
    parser.add_argument("--max-fail-to-pass", type=int, default=20)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_info = json.loads(args.repo_info.read_text(encoding="utf-8"))
    snapshot = build_sanitized_snapshot(
        load_dataset_server_pages(tuple(args.pages)),
        dataset_id=str(repo_info["id"]),
        dataset_revision=str(repo_info["sha"]),
        dataset_last_modified=str(repo_info["lastModified"]),
    )
    screening = screen_candidates(
        snapshot,
        target_count=args.target_count,
        max_per_repo=args.max_per_repo,
        min_fail_to_pass=args.min_fail_to_pass,
        max_fail_to_pass=args.max_fail_to_pass,
    )
    print(write_model(snapshot, args.snapshot_output))
    print(write_model(screening, args.screening_output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
