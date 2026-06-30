#!/usr/bin/env python

"""Materialize a curated Commit0 task from a pinned base and overlays."""

from __future__ import annotations

import argparse
from pathlib import Path

from asynccodebench.qualification.curated_commit0 import (
    load_curated_tasks,
    materialize_curated_task,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("task_id")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/tasks/commit0_curated_tasks.v0.3.json"),
    )
    parser.add_argument(
        "--repository-root",
        type=Path,
        default=Path("data/repos/commit0"),
    )
    parser.add_argument(
        "--destination-root",
        type=Path,
        default=Path("data/processed/commit0_curated/v0.3"),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_root = Path.cwd()
    tasks = load_curated_tasks(args.config, project_root=project_root)
    matches = [task for task in tasks if task.task_id == args.task_id]
    if len(matches) != 1:
        raise ValueError(f"unknown curated task: {args.task_id}")
    task = matches[0]
    destination = args.destination_root / task.repository
    materialize_curated_task(
        task,
        repository_path=args.repository_root / task.repository,
        destination=destination,
    )
    print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
