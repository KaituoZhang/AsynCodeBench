#!/usr/bin/env python
"""Materialize pinned Commit0 repositories into AsyncCodeBench local data."""

from __future__ import annotations

import argparse
from pathlib import Path

from asynccodebench.qualification.commit0_repositories import (
    load_commit0_repositories,
    materialize_commit0_repositories,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/tasks/commit0_repositories.v0.3.json"),
    )
    parser.add_argument(
        "--destination-root",
        type=Path,
        default=Path("data/repos/commit0"),
    )
    parser.add_argument(
        "--source-root",
        type=Path,
        help=(
            "Optional local mirror containing one Git repository per configured "
            "name. If omitted, repositories are cloned from their public URLs."
        ),
    )
    parser.add_argument(
        "repositories",
        nargs="*",
        help="Optional repository names; the default is every configured repo.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    inventory = load_commit0_repositories(args.config)
    selected_names = set(args.repositories)
    selected = (
        tuple(repo for repo in inventory if repo.name in selected_names)
        if selected_names
        else inventory
    )
    unknown = selected_names - {repo.name for repo in inventory}
    if unknown:
        raise ValueError(f"unknown Commit0 repositories: {sorted(unknown)}")
    paths = materialize_commit0_repositories(
        selected,
        args.destination_root,
        source_root=args.source_root,
    )
    for path in paths:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
