from __future__ import annotations

import subprocess
from pathlib import Path

from asyncodebench.qualification.commit0_async_screening import (
    screen_commit0_repository,
)


def git(repository: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repository,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_screen_commit0_repository_reports_async_curation_signals(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "demo"
    repository.mkdir()
    git(repository, "init")
    git(repository, "config", "user.email", "test@example.com")
    git(repository, "config", "user.name", "Test")
    write(repository / "README.md", "Demo task\n")
    write(
        repository / "src/demo/a.py",
        "def public_a():\n    pass\n",
    )
    write(
        repository / "src/demo/b.py",
        "from demo.a import public_a\n\n"
        "def public_b():\n    public_a()\n    pass\n",
    )
    write(repository / "src/demo/__init__.py", "")
    write(
        repository / "tests/test_demo.py",
        "from demo.b import public_b\n\n"
        "def test_demo():\n    assert public_b() == 1\n",
    )
    git(repository, "add", ".")
    git(repository, "commit", "-m", "commit0")
    git(repository, "branch", "commit0")

    record = screen_commit0_repository(repository, timeout_seconds=10.0)

    assert record.task_id == "commit0:demo"
    assert record.pytest_status == "collects_with_failures"
    assert record.curation_status == "direct_candidate"
    assert record.recommended_label == "partially_parallelizable"
    assert record.recommended_role == "main_async_task"
    assert len(record.unit_dependencies) == 1
    assert record.implementation_units[0].incomplete_marker_count == 1
