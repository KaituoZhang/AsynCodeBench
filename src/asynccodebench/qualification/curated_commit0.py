"""Reproducibly materialize curated Commit0 task states."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tarfile
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CuratedOverlay:
    """One reviewed transformation applied to a public Commit0 archive."""

    path: Path
    sha256: str
    rationale: str


@dataclass(frozen=True)
class CuratedCommit0Task:
    """One reproducible base ref plus ordered overlay sequence."""

    task_id: str
    repository: str
    base_ref: str
    base_sha: str
    overlays: tuple[CuratedOverlay, ...]


def load_curated_tasks(
    config_path: Path,
    *,
    project_root: Path,
) -> tuple[CuratedCommit0Task, ...]:
    """Load and validate the curated task inventory."""

    payload = json.loads(config_path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "commit0-curated-tasks-v0.3":
        raise ValueError("unsupported curated Commit0 task inventory")

    tasks = tuple(
        CuratedCommit0Task(
            task_id=record["task_id"],
            repository=record["repository"],
            base_ref=record["base_ref"],
            base_sha=record["base_sha"],
            overlays=tuple(
                CuratedOverlay(
                    path=project_root / overlay["path"],
                    sha256=overlay["sha256"],
                    rationale=overlay["rationale"],
                )
                for overlay in record["overlays"]
            ),
        )
        for record in payload["tasks"]
    )
    task_ids = tuple(task.task_id for task in tasks)
    if len(task_ids) != len(set(task_ids)):
        raise ValueError("duplicate curated Commit0 task IDs")
    return tasks


def file_sha256(path: Path) -> str:
    """Return the hexadecimal SHA-256 digest for one file."""

    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run(
    arguments: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        arguments,
        cwd=cwd,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )


def _safe_extract(archive: Path, destination: Path) -> None:
    destination_resolved = destination.resolve()
    with tarfile.open(archive) as stream:
        for member in stream.getmembers():
            target = (destination / member.name).resolve()
            if (
                target != destination_resolved
                and destination_resolved not in target.parents
            ):
                raise ValueError(f"unsafe archive member: {member.name}")
        stream.extractall(destination)


def materialize_curated_task(
    task: CuratedCommit0Task,
    *,
    repository_path: Path,
    destination: Path,
) -> Path:
    """Export a pinned base ref and apply verified, ordered overlays."""

    actual_sha = _run(
        ["git", "rev-parse", task.base_ref],
        cwd=repository_path,
    ).stdout.strip()
    if actual_sha != task.base_sha:
        raise ValueError(
            f"{task.task_id} base SHA mismatch: expected {task.base_sha}, "
            f"found {actual_sha}"
        )

    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True)

    with tempfile.TemporaryDirectory() as temporary_directory:
        archive = Path(temporary_directory) / "base.tar"
        subprocess.run(
            [
                "git",
                "archive",
                "--format=tar",
                f"--output={archive}",
                task.base_ref,
            ],
            cwd=repository_path,
            check=True,
        )
        _safe_extract(archive, destination)

    for overlay in task.overlays:
        actual_digest = file_sha256(overlay.path)
        if actual_digest != overlay.sha256:
            raise ValueError(
                f"overlay checksum mismatch for {overlay.path}: "
                f"expected {overlay.sha256}, found {actual_digest}"
            )
        # Generated workspaces normally live below the AsyncCodeBench Git
        # checkout. Prevent ``git apply`` from discovering that parent repo;
        # otherwise Git treats patch paths as checkout-root-relative and
        # silently skips every path below the generated workspace.
        apply_env = os.environ.copy()
        apply_env["GIT_CEILING_DIRECTORIES"] = str(destination.resolve().parent)
        _run(
            ["git", "apply", "--check", str(overlay.path)],
            cwd=destination,
            env=apply_env,
        )
        _run(
            ["git", "apply", str(overlay.path)],
            cwd=destination,
            env=apply_env,
        )

    return destination
