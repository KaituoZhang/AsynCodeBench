from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from asyncodebench.qualification.commit0_repositories import (
    Commit0Repository,
    load_commit0_repositories,
    materialize_commit0_repository,
)


def _git(path: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments],
        cwd=path,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _build_source_repository(path: Path, *, create_commit0_branch: bool = True) -> str:
    path.mkdir(parents=True)
    _git(path, "init")
    _git(path, "config", "user.email", "test@example.invalid")
    _git(path, "config", "user.name", "AsynCodeBench Test")
    (path / "task.py").write_text("raise NotImplementedError\n", encoding="utf-8")
    _git(path, "add", "task.py")
    _git(path, "commit", "-m", "commit0")
    sha = _git(path, "rev-parse", "HEAD")
    if create_commit0_branch:
        _git(path, "branch", "commit0")
    (path / "untracked.cache").write_text("do not copy\n", encoding="utf-8")
    return sha


def test_load_commit0_repositories_rejects_duplicate_names(tmp_path: Path) -> None:
    config = tmp_path / "repositories.json"
    record = {
        "name": "example",
        "origin_url": "https://example.invalid/example.git",
        "commit0_sha": "0" * 40,
    }
    config.write_text(
        json.dumps(
            {
                "schema_version": "commit0-repositories-v0.3",
                "repositories": [record, record],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="duplicate"):
        load_commit0_repositories(config)


def test_materialize_from_local_source_omits_untracked_files(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "sources"
    source = source_root / "example"
    sha = _build_source_repository(source)
    repository = Commit0Repository(
        name="example",
        origin_url="https://example.invalid/example.git",
        commit0_sha=sha,
    )

    destination = materialize_commit0_repository(
        repository,
        tmp_path / "destinations",
        source_root=source_root,
    )

    assert (destination / "task.py").is_file()
    assert not (destination / "untracked.cache").exists()
    assert _git(destination, "rev-parse", "commit0") == sha
    assert (
        _git(destination, "remote", "get-url", "origin")
        == repository.origin_url
    )


def test_materialize_creates_local_commit0_branch_from_pinned_sha(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "sources"
    source = source_root / "example"
    sha = _build_source_repository(source, create_commit0_branch=False)
    repository = Commit0Repository(
        name="example",
        origin_url="https://example.invalid/example.git",
        commit0_sha=sha,
    )

    destination = materialize_commit0_repository(
        repository,
        tmp_path / "destinations",
        source_root=source_root,
    )

    assert _git(destination, "rev-parse", "commit0") == sha
