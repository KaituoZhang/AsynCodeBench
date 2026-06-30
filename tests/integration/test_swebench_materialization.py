from __future__ import annotations

import subprocess
from pathlib import Path

from asynccodebench.qualification.swebench_materialization import (
    materialize_task_evidence,
)
from asynccodebench.qualification.swebench_screening import SWEbenchPublicTask


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


def test_materialization_uses_base_commit_not_later_solution(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "org__repo"
    repository.mkdir()
    git(repository, "init")
    git(repository, "config", "user.email", "test@example.com")
    git(repository, "config", "user.name", "Test")
    write(repository / "src/pkg/a.py", "VALUE = 0\n")
    write(
        repository / "src/pkg/b.py",
        "from pkg.a import VALUE\n\nRESULT = VALUE\n",
    )
    write(
        repository / "tests/test_b.py",
        "from pkg.b import RESULT\n\ndef test_result(): assert RESULT == 1\n",
    )
    git(repository, "add", ".")
    git(repository, "commit", "-m", "base")
    base_commit = git(repository, "rev-parse", "HEAD")

    write(repository / "src/pkg/a.py", "SECRET_SOLUTION = True\nVALUE = 1\n")
    git(repository, "add", ".")
    git(repository, "commit", "-m", "solution")

    task = SWEbenchPublicTask(
        instance_id="org__repo-1",
        repo="org/repo",
        base_commit=base_commit,
        environment_setup_commit=base_commit,
        problem_statement="Update src/pkg/b.py to support the public behavior.",
        created_at="2024-01-01T00:00:00Z",
        version="1",
        fail_to_pass=("tests/test_b.py::test_result",),
        difficulty="15 min - 1 hour",
        public_test_files=("tests/test_b.py",),
    )
    evidence = materialize_task_evidence(task, repository)
    serialized = evidence.model_dump_json()

    assert evidence.issue_explicit_paths == ("src/pkg/b.py",)
    assert evidence.publicly_implicated_modules == (
        "src/pkg/a.py",
        "src/pkg/b.py",
    )
    assert evidence.static_dependency_edges == (
        ("src/pkg/b.py", "src/pkg/a.py"),
    )
    assert "SECRET_SOLUTION" not in serialized
