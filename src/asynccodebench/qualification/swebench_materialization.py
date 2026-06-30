"""Materialize public SWE-bench base-commit evidence without solution patches."""

from __future__ import annotations

import ast
import json
import re
import subprocess
from pathlib import Path, PurePosixPath
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from asynccodebench.qualification.swebench_screening import (
    SWEbenchPublicTask,
    SWEbenchScreeningInventory,
)

MATERIALIZATION_VERSION = "swebench-materialization-v0.2"
PYTHON_PATH_PATTERN = re.compile(
    r"(?<![\w/.-])(?:[A-Za-z0-9_.-]+/)+[A-Za-z0-9_.-]+\.py"
)


class MaterializationModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    materialization_version: Literal["swebench-materialization-v0.2"] = (
        MATERIALIZATION_VERSION
    )


class SWEbenchMaterializedEvidence(MaterializationModel):
    instance_id: str
    repo: str
    base_commit: str
    issue_explicit_paths: tuple[str, ...]
    available_test_files: tuple[str, ...]
    missing_test_files: tuple[str, ...]
    imported_public_modules: tuple[str, ...]
    publicly_implicated_modules: tuple[str, ...]
    static_dependency_edges: tuple[tuple[str, str], ...]
    source_file_count: int = Field(ge=0)
    measurement_status: Literal["pending_official_environment"]
    public_evidence_sources: tuple[str, ...]

    @model_validator(mode="after")
    def validate_modules(self) -> SWEbenchMaterializedEvidence:
        if len(self.publicly_implicated_modules) != len(
            set(self.publicly_implicated_modules)
        ):
            raise ValueError("publicly_implicated_modules must be unique")
        return self


class SWEbenchMaterializationInventory(MaterializationModel):
    dataset_id: str
    dataset_revision: str
    records: tuple[SWEbenchMaterializedEvidence, ...]


def _git(repository: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repository,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            (result.stderr or result.stdout).strip()
            or f"git {' '.join(args)} failed"
        )
    return result.stdout


def _files_at_commit(repository: Path, commit: str) -> tuple[str, ...]:
    return tuple(
        line
        for line in _git(
            repository,
            "ls-tree",
            "-r",
            "--name-only",
            commit,
        ).splitlines()
        if line
    )


def _show(repository: Path, commit: str, path: str) -> str:
    return _git(repository, "show", f"{commit}:{path}")


def _module_name(path: str) -> str:
    parts = list(PurePosixPath(path).with_suffix("").parts)
    if parts and parts[0] in {"src", "lib"}:
        parts = parts[1:]
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _imports(path: str, content: str) -> set[str]:
    try:
        tree = ast.parse(content, filename=path)
    except SyntaxError:
        return set()
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    return imported


def _resolve_imports(
    imported: set[str],
    module_to_path: dict[str, str],
) -> set[str]:
    resolved: set[str] = set()
    for name in imported:
        matches = [
            (module, path)
            for module, path in module_to_path.items()
            if name == module or name.startswith(f"{module}.")
        ]
        if matches:
            resolved.add(max(matches, key=lambda item: len(item[0]))[1])
    return resolved


def materialize_task_evidence(
    task: SWEbenchPublicTask,
    repository: Path | str,
) -> SWEbenchMaterializedEvidence:
    repo = Path(repository).resolve()
    if not (repo / ".git").is_dir():
        raise FileNotFoundError(repo)
    files = _files_at_commit(repo, task.base_commit)
    file_set = set(files)
    source_files = tuple(
        path
        for path in files
        if path.endswith(".py")
        and "/tests/" not in f"/{path}"
        and not PurePosixPath(path).name.startswith("test_")
    )
    module_to_path = {
        _module_name(path): path for path in source_files if _module_name(path)
    }
    explicit_paths = tuple(
        sorted(
            {
                match.group(0)
                for match in PYTHON_PATH_PATTERN.finditer(task.problem_statement)
                if match.group(0) in file_set
            }
        )
    )
    available_tests = tuple(
        sorted(path for path in task.public_test_files if path in file_set)
    )
    missing_tests = tuple(
        sorted(set(task.public_test_files) - set(available_tests))
    )
    imported_modules: set[str] = set()
    for test_path in available_tests:
        imported_modules.update(
            _resolve_imports(
                _imports(
                    test_path,
                    _show(repo, task.base_commit, test_path),
                ),
                module_to_path,
            )
        )
    implicated_set = {
        path
        for path in (*explicit_paths, *imported_modules)
        if path in source_files
    }
    for source_path in tuple(sorted(implicated_set)):
        implicated_set.update(
            _resolve_imports(
                _imports(
                    source_path,
                    _show(repo, task.base_commit, source_path),
                ),
                module_to_path,
            )
        )
    implicated = tuple(sorted(implicated_set))
    source_text = {
        path: _show(repo, task.base_commit, path) for path in implicated
    }
    edges: set[tuple[str, str]] = set()
    for source_path, content in source_text.items():
        targets = _resolve_imports(_imports(source_path, content), module_to_path)
        edges.update(
            (source_path, target)
            for target in targets
            if target in implicated and target != source_path
        )
    return SWEbenchMaterializedEvidence(
        instance_id=task.instance_id,
        repo=task.repo,
        base_commit=task.base_commit,
        issue_explicit_paths=explicit_paths,
        available_test_files=available_tests,
        missing_test_files=missing_tests,
        imported_public_modules=tuple(sorted(imported_modules)),
        publicly_implicated_modules=implicated,
        static_dependency_edges=tuple(sorted(edges)),
        source_file_count=len(source_files),
        measurement_status="pending_official_environment",
        public_evidence_sources=(
            f"official-problem-statement:{task.instance_id}",
            f"git-base-commit:{task.repo}:{task.base_commit}",
            "FAIL_TO_PASS-test-files",
            "base-commit-test-imports",
            "base-commit-static-import-graph",
        ),
    )


def materialize_screening_inventory(
    screening: SWEbenchScreeningInventory,
    repositories_root: Path | str,
) -> SWEbenchMaterializationInventory:
    root = Path(repositories_root)
    records = tuple(
        materialize_task_evidence(
            task,
            root / task.repo.replace("/", "__"),
        )
        for task in screening.selected
    )
    return SWEbenchMaterializationInventory(
        dataset_id=screening.dataset_id,
        dataset_revision=screening.dataset_revision,
        records=records,
    )


def write_materialization_inventory(
    inventory: SWEbenchMaterializationInventory,
    output_path: Path | str,
) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(inventory.model_dump(mode="json"), indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    return output
