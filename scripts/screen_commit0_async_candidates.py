#!/usr/bin/env python
"""Screen local Commit0 repositories for AsynCodeBench v0.3 curation."""

from __future__ import annotations

import argparse
from pathlib import Path

from asyncodebench.qualification.commit0_async_screening import (
    screen_commit0_repositories,
    write_screening_inventory,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--repos-root",
        type=Path,
        default=Path("data/repos/commit0"),
        help="Directory containing one local Git repository per Commit0 task.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("manifests/candidates/commit0_async_screening_v0.3.json"),
    )
    parser.add_argument("--timeout-seconds", type=float, default=60.0)
    parser.add_argument(
        "repositories",
        nargs="*",
        help=(
            "Optional repository names. If omitted, every directory under "
            "--repos-root that contains .git is screened."
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.repositories:
        repositories = tuple(args.repos_root / name for name in args.repositories)
    else:
        repositories = tuple(
            sorted(
                path
                for path in args.repos_root.iterdir()
                if path.is_dir() and (path / ".git").is_dir()
            )
        )
    inventory = screen_commit0_repositories(
        repositories,
        repos_root=args.repos_root,
        timeout_seconds=args.timeout_seconds,
    )
    output = write_screening_inventory(inventory, args.output)
    print(output)
    for record in inventory.records:
        print(
            "\t".join(
                (
                    record.task_id,
                    record.pytest_status,
                    record.curation_status,
                    record.recommended_label,
                    record.recommended_role,
                    record.suggested_next_action,
                )
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
