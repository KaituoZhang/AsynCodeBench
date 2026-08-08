"""Sanitize and screen official SWE-bench Verified public metadata."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path, PurePosixPath
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SCREENING_VERSION = "swebench-screening-v0.2"
ALLOWED_DIFFICULTIES = ("15 min - 1 hour", "1-4 hours")


class ScreeningModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    screening_version: Literal["swebench-screening-v0.2"] = SCREENING_VERSION


class SWEbenchPublicTask(ScreeningModel):
    """Whitelisted official metadata with all solution fields removed."""

    instance_id: str = Field(min_length=1)
    repo: str = Field(min_length=1)
    base_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    environment_setup_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    problem_statement: str = Field(min_length=1)
    created_at: str = Field(min_length=1)
    version: str = Field(min_length=1)
    fail_to_pass: tuple[str, ...]
    difficulty: str = Field(min_length=1)
    public_test_files: tuple[str, ...]

    @model_validator(mode="after")
    def validate_test_files(self) -> SWEbenchPublicTask:
        if len(self.public_test_files) != len(set(self.public_test_files)):
            raise ValueError("public_test_files must be unique")
        return self


class SWEbenchMetadataSnapshot(ScreeningModel):
    dataset_id: str
    dataset_revision: str = Field(pattern=r"^[0-9a-f]{40}$")
    dataset_last_modified: str
    split: Literal["test"] = "test"
    tasks: tuple[SWEbenchPublicTask, ...]
    excluded_fields: tuple[str, ...] = (
        "patch",
        "test_patch",
        "hints_text",
        "PASS_TO_PASS",
    )


class SWEbenchScreeningInventory(ScreeningModel):
    dataset_id: str
    dataset_revision: str
    selection_rule: str
    target_count: int = Field(gt=0)
    selected: tuple[SWEbenchPublicTask, ...]
    source_counts: dict[str, int]

    @model_validator(mode="after")
    def validate_counts(self) -> SWEbenchScreeningInventory:
        if len(self.selected) != self.target_count:
            raise ValueError("selected task count does not match target_count")
        if dict(Counter(task.repo for task in self.selected)) != self.source_counts:
            raise ValueError("source_counts does not match selected tasks")
        return self


def _parse_json_list(value: Any) -> tuple[str, ...]:
    parsed = json.loads(value) if isinstance(value, str) else value
    if not isinstance(parsed, list) or not all(
        isinstance(item, str) for item in parsed
    ):
        raise ValueError("Expected a JSON list of strings")
    return tuple(parsed)


def _test_file(target: str) -> str | None:
    path = target.split("::", maxsplit=1)[0]
    if not path.endswith(".py") or any(character.isspace() for character in path):
        return None
    return PurePosixPath(path).as_posix()


def sanitize_official_row(row: dict[str, Any]) -> SWEbenchPublicTask:
    """Whitelist public task fields and structurally discard solution fields."""

    fail_to_pass = _parse_json_list(row["FAIL_TO_PASS"])
    test_files = {
        path
        for target in fail_to_pass
        if (path := _test_file(target)) is not None
    }
    return SWEbenchPublicTask(
        instance_id=str(row["instance_id"]),
        repo=str(row["repo"]),
        base_commit=str(row["base_commit"]),
        environment_setup_commit=str(row["environment_setup_commit"]),
        problem_statement=str(row["problem_statement"]),
        created_at=str(row["created_at"]),
        version=str(row["version"]),
        fail_to_pass=fail_to_pass,
        difficulty=str(row["difficulty"]),
        public_test_files=tuple(
            sorted(test_files)
        ),
    )


def load_dataset_server_pages(paths: tuple[Path, ...]) -> tuple[dict[str, Any], ...]:
    rows: list[dict[str, Any]] = []
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        page_rows = payload.get("rows")
        if not isinstance(page_rows, list):
            raise ValueError(f"{path} does not contain dataset-server rows")
        for item in page_rows:
            row = item.get("row") if isinstance(item, dict) else None
            if not isinstance(row, dict):
                raise ValueError(f"{path} contains an invalid row")
            rows.append(row)
    return tuple(rows)


def build_sanitized_snapshot(
    rows: tuple[dict[str, Any], ...],
    *,
    dataset_id: str,
    dataset_revision: str,
    dataset_last_modified: str,
) -> SWEbenchMetadataSnapshot:
    tasks = tuple(
        sorted(
            (sanitize_official_row(row) for row in rows),
            key=lambda task: task.instance_id,
        )
    )
    if len({task.instance_id for task in tasks}) != len(tasks):
        raise ValueError("Official metadata contains duplicate instance IDs")
    return SWEbenchMetadataSnapshot(
        dataset_id=dataset_id,
        dataset_revision=dataset_revision,
        dataset_last_modified=dataset_last_modified,
        tasks=tasks,
    )


def screen_candidates(
    snapshot: SWEbenchMetadataSnapshot,
    *,
    target_count: int = 18,
    max_per_repo: int = 2,
    min_fail_to_pass: int = 1,
    max_fail_to_pass: int = 20,
) -> SWEbenchScreeningInventory:
    """Select a diverse pool without consulting patches, hints, or outcomes."""

    eligible = [
        task
        for task in snapshot.tasks
        if task.difficulty in ALLOWED_DIFFICULTIES
        and len(task.problem_statement) >= 200
        and min_fail_to_pass <= len(task.fail_to_pass) <= max_fail_to_pass
    ]
    by_repo: dict[str, list[SWEbenchPublicTask]] = defaultdict(list)
    for task in eligible:
        by_repo[task.repo].append(task)
    selected: list[SWEbenchPublicTask] = []
    for repo in sorted(by_repo):
        ranked = sorted(
            by_repo[repo],
            key=lambda task: (
                -len(task.fail_to_pass),
                -len(task.problem_statement),
                task.instance_id,
            ),
        )
        selected.extend(ranked[:max_per_repo])
    selected = sorted(
        selected,
        key=lambda task: (
            -len(task.fail_to_pass),
            task.repo,
            task.instance_id,
        ),
    )[:target_count]
    selected.sort(key=lambda task: task.instance_id)
    if len(selected) != target_count:
        raise ValueError(
            f"Only {len(selected)} tasks satisfy the preregistered screen"
        )
    return SWEbenchScreeningInventory(
        dataset_id=snapshot.dataset_id,
        dataset_revision=snapshot.dataset_revision,
        selection_rule=(
            "difficulty in {15 min - 1 hour, 1-4 hours}; "
            f"problem_statement length >= 200; {min_fail_to_pass}-"
            f"{max_fail_to_pass} FAIL_TO_PASS targets; "
            f"max {max_per_repo} per repo; rank by test-file count, issue "
            "length, then instance_id"
        ),
        target_count=target_count,
        selected=tuple(selected),
        source_counts=dict(Counter(task.repo for task in selected)),
    )


def write_model(model: BaseModel, output_path: Path | str) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(model.model_dump(mode="json"), indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    return output
