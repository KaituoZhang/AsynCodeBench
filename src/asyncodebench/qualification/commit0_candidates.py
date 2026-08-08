"""Build Commit0 candidate evidence using only the public ``commit0`` ref."""

from __future__ import annotations

import ast
import bz2
import io
import json
import os
import re
import subprocess
import sys
import tarfile
import tempfile
import time
from collections.abc import Iterable
from pathlib import Path, PurePosixPath

from asyncodebench.qualification.models import (
    CandidateInventory,
    CandidateRecord,
)

PUBLIC_REF = "commit0"
INCOMPLETE_PATTERN = re.compile(
    r"\bNotImplementedError\b|^\s*pass\s*(?:#.*)?$|^\s*\.\.\.\s*$|\bTODO\b",
    re.MULTILINE,
)


class CandidateExtractionError(RuntimeError):
    """Raised when public Commit0 evidence cannot be extracted safely."""


def _git(
    repository: Path,
    *args: str,
    text: bool = True,
) -> subprocess.CompletedProcess[str] | subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", *args],
        cwd=repository,
        capture_output=True,
        text=text,
        check=False,
    )


def _git_text(repository: Path, *args: str) -> str:
    result = _git(repository, *args)
    if result.returncode != 0:
        raise CandidateExtractionError(
            (result.stderr or result.stdout).strip()
            or f"git {' '.join(args)} failed"
        )
    return result.stdout


def _files_at_public_ref(repository: Path) -> tuple[str, ...]:
    return tuple(
        line
        for line in _git_text(
            repository,
            "ls-tree",
            "-r",
            "--name-only",
            PUBLIC_REF,
        ).splitlines()
        if line
    )


def _show_text(repository: Path, path: str) -> str:
    return _git_text(repository, "show", f"{PUBLIC_REF}:{path}")


def _is_test_path(path: str) -> bool:
    parts = tuple(part.lower() for part in PurePosixPath(path).parts)
    name = parts[-1]
    return path.endswith(".py") and (
        name.startswith("test")
        or any(
            part in {"test", "tests", "testing"} or part.endswith("_tests")
            for part in parts[:-1]
        )
    )


def _is_test_target(path: str) -> bool:
    return _is_test_path(path) and PurePosixPath(path).name != "__init__.py"


def _is_library_source(path: str) -> bool:
    parts = tuple(part.lower() for part in PurePosixPath(path).parts)
    return (
        path.endswith(".py")
        and not _is_test_path(path)
        and not any(
            part in {"docs", "doc", "examples", "example", "bin", "scripts"}
            for part in parts[:-1]
        )
        and PurePosixPath(path).name not in {"setup.py", "conftest.py"}
    )


def _module_name(path: str) -> str:
    parts = list(PurePosixPath(path).with_suffix("").parts)
    if parts and parts[0] == "src":
        parts = parts[1:]
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _imported_modules(path: str, content: str) -> set[str]:
    try:
        tree = ast.parse(content, filename=path)
    except SyntaxError:
        return set()
    current = _module_name(path).split(".")
    package = current[:-1]
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = list(package)
            if node.level:
                trim = max(node.level - 1, 0)
                base = base[: len(base) - trim] if trim <= len(base) else []
            elif node.module:
                base = []
            module_parts = node.module.split(".") if node.module else []
            imported.add(".".join((*base, *module_parts)))
    return {module for module in imported if module}


def _dependency_edges(
    source_text: dict[str, str],
    implicated_paths: tuple[str, ...],
) -> tuple[tuple[str, str], ...]:
    module_to_path = {
        _module_name(path): path for path in source_text if _module_name(path)
    }
    implicated = set(implicated_paths)
    edges: set[tuple[str, str]] = set()
    for source_path in implicated_paths:
        for imported in _imported_modules(source_path, source_text[source_path]):
            matches = [
                (module, path)
                for module, path in module_to_path.items()
                if imported == module or imported.startswith(f"{module}.")
            ]
            if not matches:
                continue
            _, target_path = max(matches, key=lambda item: len(item[0]))
            if target_path in implicated and target_path != source_path:
                edges.add((source_path, target_path))
    return tuple(sorted(edges))


def _safe_export_public_ref(repository: Path, destination: Path) -> None:
    result = _git(repository, "archive", "--format=tar", PUBLIC_REF, text=False)
    if result.returncode != 0:
        raise CandidateExtractionError(
            result.stderr.decode(errors="replace").strip()
        )
    destination.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(result.stdout), mode="r:") as archive:
        for member in archive.getmembers():
            path = PurePosixPath(member.name)
            if (
                path.is_absolute()
                or ".." in path.parts
            ):
                raise CandidateExtractionError(
                    f"Unsafe archive member on {PUBLIC_REF}: {member.name}"
                )
            if member.issym() or member.islnk():
                continue
            if member.isdir():
                (destination / path).mkdir(parents=True, exist_ok=True)
                continue
            if not member.isfile():
                continue
            source = archive.extractfile(member)
            if source is None:
                raise CandidateExtractionError(
                    f"Cannot read archive member: {member.name}"
                )
            target = destination / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read())


def _spec_summary(repository: Path, files: tuple[str, ...]) -> tuple[str, str]:
    if "spec.pdf.bz2" in files:
        result = _git(repository, "show", f"{PUBLIC_REF}:spec.pdf.bz2", text=False)
        if result.returncode == 0:
            with tempfile.TemporaryDirectory(
                prefix="asyncodebench-spec-"
            ) as temp_dir:
                pdf_path = Path(temp_dir) / "spec.pdf"
                pdf_path.write_bytes(bz2.decompress(result.stdout))
                converted = subprocess.run(
                    ["pdftotext", str(pdf_path), "-"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
            if converted.returncode == 0:
                paragraphs = [
                    " ".join(block.split())
                    for block in re.split(r"\n\s*\n", converted.stdout)
                    if block.strip()
                ]
                if paragraphs:
                    return (
                        " ".join(paragraphs[:3])[:1000],
                        "spec.pdf.bz2@commit0",
                    )
    for readme in ("README.md", "README.rst", "README.txt"):
        if readme in files:
            text = _show_text(repository, readme)
            paragraphs = [
                " ".join(block.split())
                for block in re.split(r"\n\s*\n", text)
                if block.strip()
            ]
            if paragraphs:
                return " ".join(paragraphs[:3])[:1000], f"{readme}@commit0"
    return (
        f"Complete the public Commit0 task for {repository.name}.",
        "commit0-ref-file-tree",
    )


def _measure_tests(
    repository: Path,
    *,
    timeout_seconds: float,
) -> tuple[float, tuple[str, ...], int | None, bool]:
    executed_command = (
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "-o",
        "addopts=",
    )
    recorded_command = ("python", "-m", "pytest", "-q", "-o", "addopts=")
    with tempfile.TemporaryDirectory(
        prefix=f"asyncodebench-{repository.name}-"
    ) as temp_dir:
        workspace = Path(temp_dir) / "repo"
        _safe_export_public_ref(repository, workspace)
        environment = os.environ.copy()
        environment["PYTHONNOUSERSITE"] = "1"
        pythonpath = [str(workspace)]
        if (workspace / "src").is_dir():
            pythonpath.insert(0, str(workspace / "src"))
        environment["PYTHONPATH"] = os.pathsep.join(pythonpath)
        started = time.perf_counter()
        try:
            result = subprocess.run(
                executed_command,
                cwd=workspace,
                env=environment,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
            return (
                time.perf_counter() - started,
                recorded_command,
                result.returncode,
                False,
            )
        except subprocess.TimeoutExpired:
            return time.perf_counter() - started, recorded_command, None, True


def extract_commit0_candidate(
    repository: Path | str,
    *,
    timeout_seconds: float = 60.0,
) -> CandidateRecord:
    """Extract one unlabelled candidate without reading a solution ref."""

    repo = Path(repository).resolve()
    if not (repo / ".git").is_dir():
        raise FileNotFoundError(repo)
    public_commit = _git_text(
        repo,
        "rev-parse",
        "--verify",
        PUBLIC_REF,
    ).strip()
    files = _files_at_public_ref(repo)
    source_paths = tuple(sorted(path for path in files if _is_library_source(path)))
    source_text = {path: _show_text(repo, path) for path in source_paths}
    implicated = tuple(
        path
        for path in source_paths
        if INCOMPLETE_PATTERN.search(source_text[path])
    )
    if not implicated:
        implicated = source_paths
    tests = tuple(sorted(path for path in files if _is_test_target(path)))
    edges = _dependency_edges(source_text, implicated)
    summary, summary_source = _spec_summary(repo, files)
    duration, command, return_code, timed_out = _measure_tests(
        repo,
        timeout_seconds=timeout_seconds,
    )

    if edges:
        separability = (
            f"{len(implicated)} public task modules with "
            f"{len(edges)} static dependency edges."
        )
    else:
        separability = (
            f"{len(implicated)} public task modules with no static imports "
            "among the implicated modules."
        )
    if len(tests) > 1:
        target_independence = (
            f"{len(tests)} test modules can be invoked separately; semantic "
            "independence requires annotator review."
        )
    else:
        target_independence = (
            f"{len(tests)} test module is present; independent target coverage "
            "requires annotator review."
        )
    subproblems = tuple(
        [f"implementation:{path}" for path in implicated]
        + ([f"test-and-review:{path}" for path in tests] if tests else [])
    )
    constraints = tuple(f"{source} imports {target}" for source, target in edges)
    overlap = tuple(
        item
        for item, enabled in (
            ("cross-module-implementation", len(implicated) > 1),
            ("implementation-test", bool(tests)),
            ("implementation-review", bool(implicated)),
            ("integration", len(implicated) > 1),
        )
        if enabled
    )
    evidence_sources = (
        f"git-ref:{PUBLIC_REF}:{public_commit}",
        summary_source,
        "python-source-incomplete-markers@commit0",
        "python-static-import-graph@commit0",
        "test-file-tree@commit0",
        "pytest-measurement@commit0",
    )
    return CandidateRecord(
        task_id=f"commit0:{repo.name}",
        task_source="Commit0",
        upstream_version=public_commit,
        issue_summary=summary,
        publicly_implicated_modules=implicated,
        public_module_count=len(implicated),
        dependency_separability=separability,
        static_dependency_edges=edges,
        test_targets=tests,
        test_target_independence=target_independence,
        measured_test_and_build_duration=duration,
        measurement_command=command,
        measurement_return_code=return_code,
        measurement_timed_out=timed_out,
        measurement_environment={
            "python_implementation": sys.implementation.name,
            "python_version": (
                f"{sys.version_info.major}.{sys.version_info.minor}."
                f"{sys.version_info.micro}"
            ),
            "platform": sys.platform,
            "user_site_disabled": os.environ.get("PYTHONNOUSERSITE", "") or "0",
        },
        candidate_parallel_subproblems=subproblems,
        cross_module_constraints=constraints,
        expected_overlap_surface=overlap,
        expected_shared_resource_contention=(
            "Agents share repository integration authority and finite test "
            "workers; no task-specific external resource contention was "
            "inferred from the public ref."
        ),
        public_evidence_sources=evidence_sources,
        gold_informed_secondary_label=None,
    )


def extract_commit0_inventory(
    repositories: Iterable[Path | str],
    *,
    timeout_seconds: float = 60.0,
) -> CandidateInventory:
    candidates = tuple(
        sorted(
            (
                extract_commit0_candidate(
                    repository,
                    timeout_seconds=timeout_seconds,
                )
                for repository in repositories
            ),
            key=lambda candidate: candidate.task_id,
        )
    )
    return CandidateInventory(candidates=candidates)


def write_candidate_inventory(
    inventory: CandidateInventory,
    output_path: Path | str,
) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            inventory.model_dump(mode="json"),
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return output
