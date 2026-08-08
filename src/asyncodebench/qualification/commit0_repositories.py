"""Materialize pinned Commit0 repositories without cross-project dependencies."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Commit0Repository:
    """One reproducible Commit0 repository source."""

    name: str
    origin_url: str
    commit0_sha: str


def load_commit0_repositories(config_path: Path) -> tuple[Commit0Repository, ...]:
    """Load and minimally validate the public repository inventory."""

    payload = json.loads(config_path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "commit0-repositories-v0.3":
        raise ValueError("unsupported Commit0 repository inventory")
    repositories = tuple(
        Commit0Repository(
            name=record["name"],
            origin_url=record["origin_url"],
            commit0_sha=record["commit0_sha"],
        )
        for record in payload["repositories"]
    )
    names = tuple(repository.name for repository in repositories)
    if len(names) != len(set(names)):
        raise ValueError("duplicate Commit0 repository names")
    return repositories


def _run_git(*arguments: str, cwd: Path | None = None) -> str:
    result = subprocess.run(
        ["git", *arguments],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def validate_commit0_repository(
    repository_path: Path,
    expected: Commit0Repository,
) -> None:
    """Validate repository identity and the pinned public ``commit0`` ref."""

    if not (repository_path / ".git").is_dir():
        raise ValueError(f"not a Git repository: {repository_path}")
    actual_sha = _run_git("rev-parse", "commit0", cwd=repository_path)
    if actual_sha != expected.commit0_sha:
        raise ValueError(
            f"{expected.name} commit0 SHA mismatch: "
            f"expected {expected.commit0_sha}, found {actual_sha}"
        )


def _ensure_local_commit0_ref(
    repository_path: Path,
    expected: Commit0Repository,
) -> None:
    result = subprocess.run(
        ["git", "rev-parse", "--verify", "commit0^{commit}"],
        cwd=repository_path,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return
    result = subprocess.run(
        ["git", "cat-file", "-e", f"{expected.commit0_sha}^{{commit}}"],
        cwd=repository_path,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        _run_git("branch", "commit0", expected.commit0_sha, cwd=repository_path)
        return
    remote_sha = _run_git(
        "rev-parse",
        "--verify",
        "refs/remotes/origin/commit0^{commit}",
        cwd=repository_path,
    )
    if remote_sha != expected.commit0_sha:
        raise ValueError(
            f"{expected.name} remote commit0 SHA mismatch: "
            f"expected {expected.commit0_sha}, found {remote_sha}"
        )
    _run_git("branch", "commit0", expected.commit0_sha, cwd=repository_path)


def materialize_commit0_repository(
    repository: Commit0Repository,
    destination_root: Path,
    *,
    source_root: Path | None = None,
) -> Path:
    """Clone one pinned repository from a local mirror or its public origin."""

    destination = destination_root / repository.name
    if destination.exists():
        _ensure_local_commit0_ref(destination, repository)
        validate_commit0_repository(destination, repository)
        return destination

    destination_root.mkdir(parents=True, exist_ok=True)
    source: Path | str = (
        source_root / repository.name
        if source_root is not None
        else repository.origin_url
    )
    clone_arguments = ["clone"]
    if source_root is not None:
        if not (source / ".git").is_dir():
            raise ValueError(f"local Commit0 source is missing: {source}")
        clone_arguments.append("--no-hardlinks")
    clone_arguments.extend((str(source), str(destination)))
    _run_git(*clone_arguments)
    _run_git("remote", "set-url", "origin", repository.origin_url, cwd=destination)
    _ensure_local_commit0_ref(destination, repository)
    validate_commit0_repository(destination, repository)
    return destination


def materialize_commit0_repositories(
    repositories: tuple[Commit0Repository, ...],
    destination_root: Path,
    *,
    source_root: Path | None = None,
) -> tuple[Path, ...]:
    """Materialize and validate a repository collection."""

    return tuple(
        materialize_commit0_repository(
            repository,
            destination_root,
            source_root=source_root,
        )
        for repository in repositories
    )
