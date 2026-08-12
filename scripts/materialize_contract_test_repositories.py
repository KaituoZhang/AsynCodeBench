#!/usr/bin/env python3
"""Materialize the pinned repositories required by source contract tests."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from asyncodebench.qualification.commit0_repositories import (
    load_commit0_repositories,
    materialize_commit0_repositories,
)
from asyncodebench.qualification.curated_commit0 import (
    load_curated_tasks,
    materialize_curated_task,
)

ROOT = Path(__file__).resolve().parents[1]
OFFICIAL_TASKS = ROOT / "manifests/release/v0.3/official_tasks.json"
FULL_INVENTORY = ROOT / "configs/tasks/commit0_repositories_full.v0.3.json"
CURATED_TASKS = ROOT / "configs/tasks/commit0_curated_tasks.v0.3.json"
DEFAULT_DESTINATION = ROOT / "data/repos/commit0"
DEFAULT_CURATED_DESTINATION = ROOT / "data/processed/commit0_curated/v0.3"

# FastAPI is not an official task. Its source-selector regression test remains in
# the historical contract suite, so clean-checkout validation needs its pinned
# repository until that historical suite is split into a separate package.
HISTORICAL_REGRESSION_REPOSITORIES = ("fastapi",)
CURATED_CONTRACT_REPOSITORIES = ("portalocker", "tinydb")


def required_repository_names() -> tuple[str, ...]:
    release = json.loads(OFFICIAL_TASKS.read_text(encoding="utf-8"))
    official = [task_id.split(":", 1)[1] for task_id in release["official_task_ids"]]
    return tuple(dict.fromkeys([*official, *HISTORICAL_REGRESSION_REPOSITORIES]))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--destination-root", type=Path, default=DEFAULT_DESTINATION)
    parser.add_argument(
        "--curated-destination-root",
        type=Path,
        default=DEFAULT_CURATED_DESTINATION,
    )
    parser.add_argument(
        "--source-root",
        type=Path,
        help="Optional local mirror with one Git repository per configured name.",
    )
    return parser.parse_args()


def _git(repository: Path, *arguments: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", "-C", str(repository), *arguments],
        check=check,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _ensure_curated_base_ref(
    repository: Path,
    *,
    source: Path | str,
    base_ref: str,
    base_sha: str,
    local_mirror: bool,
) -> None:
    current = _git(
        repository,
        "rev-parse",
        "--verify",
        f"{base_ref}^{{commit}}",
        check=False,
    )
    if current == base_sha:
        return

    branch = base_ref.removeprefix("origin/")
    source_ref = (
        f"refs/remotes/origin/{branch}" if local_mirror and base_ref.startswith("origin/")
        else f"refs/heads/{branch}"
    )
    _git(repository, "fetch", str(source), source_ref)
    fetched = _git(repository, "rev-parse", "FETCH_HEAD")
    if fetched != base_sha:
        raise ValueError(
            f"curated base SHA mismatch for {repository.name}: "
            f"expected {base_sha}, fetched {fetched}"
        )
    target_ref = (
        f"refs/remotes/origin/{branch}"
        if base_ref.startswith("origin/")
        else f"refs/heads/{branch}"
    )
    _git(repository, "update-ref", target_ref, base_sha)


def main() -> int:
    args = parse_args()
    inventory = load_commit0_repositories(FULL_INVENTORY)
    by_name = {repository.name: repository for repository in inventory}
    curated = {
        task["repository"]: task
        for task in json.loads(CURATED_TASKS.read_text(encoding="utf-8"))["tasks"]
    }
    required = required_repository_names()
    missing = sorted(set(required) - set(by_name))
    if missing:
        raise ValueError(f"contract repository inventory is incomplete: {missing}")

    paths = materialize_commit0_repositories(
        tuple(by_name[name] for name in required),
        args.destination_root,
        source_root=args.source_root,
    )
    for path in paths:
        task = curated[path.name]
        source = (
            (args.source_root / path.name).resolve()
            if args.source_root
            else by_name[path.name].origin_url
        )
        _ensure_curated_base_ref(
            path,
            source=source,
            base_ref=task["base_ref"],
            base_sha=task["base_sha"],
            local_mirror=args.source_root is not None,
        )
        print(path)

    curated_tasks = {
        task.repository: task
        for task in load_curated_tasks(CURATED_TASKS, project_root=ROOT)
    }
    for repository in CURATED_CONTRACT_REPOSITORIES:
        destination = args.curated_destination_root / repository
        materialize_curated_task(
            curated_tasks[repository],
            repository_path=args.destination_root / repository,
            destination=destination,
        )
        print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
