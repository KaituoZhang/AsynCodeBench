from __future__ import annotations

from asyncodebench.qualification.swebench_screening import (
    build_sanitized_snapshot,
    sanitize_official_row,
    screen_candidates,
)


def row(instance_id: str, repo: str, tests: int) -> dict[str, object]:
    return {
        "instance_id": instance_id,
        "repo": repo,
        "base_commit": "a" * 40,
        "environment_setup_commit": "b" * 40,
        "problem_statement": "Public issue. " * 30,
        "created_at": "2024-01-01T00:00:00Z",
        "version": "1.0",
        "FAIL_TO_PASS": [
            f"tests/test_{index}.py::test_case" for index in range(tests)
        ],
        "PASS_TO_PASS": ["tests/test_regression.py::test_ok"],
        "difficulty": "15 min - 1 hour",
        "patch": "SECRET SOLUTION",
        "test_patch": "SECRET TEST PATCH",
        "hints_text": "SECRET HINT",
    }


def test_sanitizer_drops_solution_and_hint_fields() -> None:
    task = sanitize_official_row(row("org__repo-1", "org/repo", 2))
    serialized = task.model_dump_json()

    assert task.public_test_files == (
        "tests/test_0.py",
        "tests/test_1.py",
    )
    assert "SECRET" not in serialized
    assert "patch" not in serialized.lower()
    assert "hint" not in serialized.lower()


def test_screen_is_deterministic_and_repo_capped() -> None:
    rows = tuple(
        row(f"org{repo}__repo-{index}", f"org{repo}/repo", index + 2)
        for repo in range(3)
        for index in range(4)
    )
    snapshot = build_sanitized_snapshot(
        rows,
        dataset_id="official",
        dataset_revision="c" * 40,
        dataset_last_modified="2025-01-01T00:00:00Z",
    )

    first = screen_candidates(
        snapshot,
        target_count=6,
        max_per_repo=2,
        min_fail_to_pass=2,
        max_fail_to_pass=10,
    )
    second = screen_candidates(
        snapshot,
        target_count=6,
        max_per_repo=2,
        min_fail_to_pass=2,
        max_fail_to_pass=10,
    )

    assert first == second
    assert first.source_counts == {
        "org0/repo": 2,
        "org1/repo": 2,
        "org2/repo": 2,
    }
