from __future__ import annotations

import subprocess
from pathlib import Path

from asynccodebench.qualification import extract_commit0_candidate


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


def test_candidate_extraction_reads_only_public_commit0_ref(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "demo"
    repository.mkdir()
    git(repository, "init")
    git(repository, "config", "user.email", "test@example.com")
    git(repository, "config", "user.name", "Test")
    write(
        repository / "README.md",
        "Demo public task\n\nImplement the public demo behavior.\n",
    )
    write(
        repository / "src/demo/a.py",
        "def public_a():\n    raise NotImplementedError\n",
    )
    write(
        repository / "src/demo/b.py",
        "from demo.a import public_a\n\n"
        "def public_b():\n    return public_a()\n",
    )
    write(
        repository / "tests/test_a.py",
        "from demo.a import public_a\n\n"
        "def test_a():\n    assert public_a() == 1\n",
    )
    write(
        repository / "tests/test_b.py",
        "from demo.b import public_b\n\n"
        "def test_b():\n    assert public_b() == 1\n",
    )
    (repository / "ignored-link").symlink_to("/host/secret")
    git(repository, "add", ".")
    git(repository, "commit", "-m", "public commit0 task")
    public_commit = git(repository, "rev-parse", "HEAD")
    git(repository, "branch", "commit0")

    write(
        repository / "src/demo/a.py",
        "SECRET_GOLD_SOLUTION = 1\n\ndef public_a():\n    return 1\n",
    )
    git(repository, "add", ".")
    git(repository, "commit", "-m", "private reference solution")

    candidate = extract_commit0_candidate(
        repository,
        timeout_seconds=10.0,
    )
    serialized = candidate.model_dump_json()

    assert candidate.upstream_version == public_commit
    assert candidate.publicly_implicated_modules == ("src/demo/a.py",)
    assert candidate.public_module_count == 1
    assert candidate.gold_informed_secondary_label is None
    assert "SECRET_GOLD_SOLUTION" not in serialized
    assert "/host/secret" not in serialized
    assert "master" not in serialized
    assert candidate.test_targets == ("tests/test_a.py", "tests/test_b.py")
    assert candidate.measurement_command[-3:] == (
        "-q",
        "-o",
        "addopts=",
    )
