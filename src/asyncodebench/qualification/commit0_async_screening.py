"""Audit local Commit0 repositories for AsynCodeBench v0.3 structure."""

from __future__ import annotations

import ast
import io
import json
import os
import re
import subprocess
import sys
import tarfile
import tempfile
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from asyncodebench.qualification.commit0_candidates import (
    INCOMPLETE_PATTERN,
    PUBLIC_REF,
    extract_commit0_candidate,
)

SCREENING_SCHEMA_VERSION = "commit0-async-structure-audit-v0.3"

RecommendedLabel = Literal[
    "parallelizable",
    "partially_parallelizable",
    "effectively_serial",
    "unclear",
    "reject",
]
RecommendedRole = Literal[
    "main_async_task",
    "positive_parallel_control",
    "serial_control",
    "bootstrap_review",
    "manual_review",
    "already_in_v0.3",
    "reject",
]
CurationStatus = Literal[
    "already_in_v0.3",
    "direct_candidate",
    "bootstrap_candidate",
    "control_candidate",
    "weak_or_unclear",
    "reject_or_defer",
]


class Commit0AsyncPytestSummary(BaseModel):
    """Parsed pytest outcome summary for one public Commit0 workspace."""

    collected: int | None = Field(default=None, ge=0)
    passed: int = Field(default=0, ge=0)
    failed: int = Field(default=0, ge=0)
    errors: int = Field(default=0, ge=0)
    skipped: int = Field(default=0, ge=0)
    deselected: int = Field(default=0, ge=0)
    warnings: int = Field(default=0, ge=0)
    no_tests_ran: bool = False


class ImplementationUnit(BaseModel):
    """One candidate implementation unit inferred from public evidence."""

    unit_id: str
    paths: tuple[str, ...]
    incomplete_marker_count: int
    imports_implicated_units: tuple[str, ...]
    imported_by_implicated_units: tuple[str, ...]
    test_ownership_hints: tuple[str, ...]


class UnitDependency(BaseModel):
    """Directed dependency between candidate implementation units."""

    producer: str
    consumer: str
    dependency_type: str
    evidence: tuple[str, ...]


class TestOwnershipHint(BaseModel):
    """Heuristic mapping from one test file to implementation units."""

    test_path: str
    primary_units: tuple[str, ...]
    evidence: tuple[str, ...]


class Commit0AsyncScreeningRecord(BaseModel):
    """One answer-free structural audit record for AsynCodeBench curation."""

    model_config = ConfigDict(extra="forbid")

    task_id: str
    repository_name: str
    upstream_version: str
    existing_v0_3_task: bool
    curated_overlay_configured: bool
    measurement_command: tuple[str, ...]
    measurement_return_code: int | None
    measurement_timed_out: bool
    pytest_status: str
    pytest_summary: Commit0AsyncPytestSummary
    publicly_implicated_modules: tuple[str, ...]
    test_targets: tuple[str, ...]
    static_dependency_edges: tuple[tuple[str, str], ...]
    implementation_units: tuple[ImplementationUnit, ...]
    unit_dependencies: tuple[UnitDependency, ...]
    test_ownership_hints: tuple[TestOwnershipHint, ...]
    async_risk_hypotheses: tuple[str, ...]
    recommended_label: RecommendedLabel
    recommended_role: RecommendedRole
    curation_status: CurationStatus
    suggested_next_action: str
    risks: tuple[str, ...]
    rationale: tuple[str, ...]
    candidate_evidence_sources: tuple[str, ...]


class Commit0AsyncScreeningInventory(BaseModel):
    """Collection of Commit0 async-structure audit records."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = SCREENING_SCHEMA_VERSION
    repositories_root: str
    records: tuple[Commit0AsyncScreeningRecord, ...]


@dataclass(frozen=True)
class PytestRun:
    command: tuple[str, ...]
    return_code: int | None
    timed_out: bool
    output: str


def _git(
    repository: Path,
    *args: str,
    text: bool = True,
) -> subprocess.CompletedProcess[str] | subprocess.CompletedProcess[bytes]:
    kwargs = (
        {"encoding": "utf-8", "errors": "replace"}
        if text
        else {}
    )
    return subprocess.run(
        ["git", *args],
        cwd=repository,
        capture_output=True,
        text=text,
        check=False,
        **kwargs,
    )


def _git_text(repository: Path, *args: str) -> str:
    result = _git(repository, *args)
    if result.returncode != 0:
        raise RuntimeError(
            (result.stderr or result.stdout).strip()
            or f"git {' '.join(args)} failed"
        )
    return result.stdout


def _safe_export_public_ref(repository: Path, destination: Path) -> None:
    result = _git(repository, "archive", "--format=tar", PUBLIC_REF, text=False)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.decode(errors="replace").strip())
    destination.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(result.stdout), mode="r:") as archive:
        for member in archive.getmembers():
            path = PurePosixPath(member.name)
            if path.is_absolute() or ".." in path.parts:
                raise RuntimeError(f"unsafe archive member: {member.name}")
            if member.issym() or member.islnk():
                continue
            if member.isdir():
                (destination / path).mkdir(parents=True, exist_ok=True)
                continue
            if not member.isfile():
                continue
            source = archive.extractfile(member)
            if source is None:
                raise RuntimeError(f"cannot read archive member: {member.name}")
            target = destination / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read())


def _show_text(repository: Path, path: str) -> str:
    return _git_text(repository, "show", f"{PUBLIC_REF}:{path}")


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


def _run_pytest(
    repository: Path,
    *,
    timeout_seconds: float,
) -> PytestRun:
    executed = (
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "-o",
        "addopts=",
    )
    recorded = ("python", "-m", "pytest", "-q", "-o", "addopts=")
    with tempfile.TemporaryDirectory(
        prefix=f"asyncodebench-audit-{repository.name}-"
    ) as temp_dir:
        workspace = Path(temp_dir) / "repo"
        _safe_export_public_ref(repository, workspace)
        environment = os.environ.copy()
        environment["PYTHONNOUSERSITE"] = "1"
        pythonpath = [str(workspace)]
        if (workspace / "src").is_dir():
            pythonpath.insert(0, str(workspace / "src"))
        environment["PYTHONPATH"] = os.pathsep.join(pythonpath)
        try:
            result = subprocess.run(
                executed,
                cwd=workspace,
                env=environment,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            output = "\n".join(
                part
                for part in (
                    exc.stdout if isinstance(exc.stdout, str) else None,
                    exc.stderr if isinstance(exc.stderr, str) else None,
                )
                if part
            )
            return PytestRun(
                command=recorded,
                return_code=None,
                timed_out=True,
                output=output,
            )
    return PytestRun(
        command=recorded,
        return_code=result.returncode,
        timed_out=False,
        output=f"{result.stdout}\n{result.stderr}",
    )


def _extract_count(output: str, word: str) -> int:
    matches = re.findall(rf"(\d+)\s+{word}\b", output)
    return int(matches[-1]) if matches else 0


def parse_pytest_summary(output: str) -> Commit0AsyncPytestSummary:
    """Parse the stable parts of pytest's terminal summary."""

    collected_matches = re.findall(r"collected\s+(\d+)\s+items?", output)
    no_tests = bool(re.search(r"\bno tests ran\b", output, flags=re.I))
    passed = _extract_count(output, "passed")
    failed = _extract_count(output, "failed")
    errors = _extract_count(output, "errors?")
    skipped = _extract_count(output, "skipped")
    deselected = _extract_count(output, "deselected")
    warnings = _extract_count(output, "warnings?")
    collected = int(collected_matches[-1]) if collected_matches else None
    if collected is None and not no_tests:
        active = passed + failed + errors + skipped
        if active:
            collected = active + deselected
    return Commit0AsyncPytestSummary(
        collected=collected,
        passed=passed,
        failed=failed,
        errors=errors,
        skipped=skipped,
        deselected=deselected,
        warnings=warnings,
        no_tests_ran=no_tests,
    )


def _classify_pytest_status(
    run: PytestRun,
    summary: Commit0AsyncPytestSummary,
) -> str:
    if run.timed_out:
        return "timeout"
    if summary.no_tests_ran or summary.collected == 0:
        return "no_tests_collected"
    if run.return_code == 0:
        return "passes_at_commit0"
    if run.return_code in {2, 4}:
        return "collection_or_import_error"
    if summary.errors and not summary.failed:
        return "collection_or_import_error"
    if summary.failed or summary.errors:
        return "collects_with_failures"
    return "unknown_nonzero"


def _existing_task_ids(tasks_dir: Path) -> set[str]:
    task_ids: set[str] = set()
    if not tasks_dir.exists():
        return task_ids
    for path in tasks_dir.glob("commit0_*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        task_id = payload.get("task_id")
        if isinstance(task_id, str):
            task_ids.add(task_id)
    return task_ids


def _existing_task_labels(tasks_dir: Path) -> dict[str, str]:
    labels: dict[str, str] = {}
    if not tasks_dir.exists():
        return labels
    for path in tasks_dir.glob("commit0_*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        task_id = payload.get("task_id")
        label = (
            payload.get("qualification_label")
            or payload.get("proposed_parallelizability_label")
        )
        if isinstance(task_id, str) and isinstance(label, str):
            labels[task_id] = label
    return labels


def _curated_task_ids(config_path: Path) -> set[str]:
    if not config_path.exists():
        return set()
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    return {
        task["task_id"]
        for task in payload.get("tasks", [])
        if isinstance(task.get("task_id"), str)
    }


def _risk_flags(
    *,
    repository: Path,
    pytest_status: str,
    test_targets: tuple[str, ...],
    curated_overlay_configured: bool,
) -> tuple[str, ...]:
    files = _git_text(repository, "ls-tree", "-r", "--name-only", PUBLIC_REF)
    lower = files.lower()
    risks: list[str] = []
    if pytest_status == "collection_or_import_error":
        risks.append("raw_collection_or_import_blocker")
        if curated_overlay_configured:
            risks.append("curated_overlay_configured")
        else:
            risks.append("substantive_bootstrap_review_needed")
    if "redis" in lower or "postgres" in lower or "mysql" in lower:
        risks.append("external_service_hint")
    if "docker" in lower or "compose" in lower:
        risks.append("container_or_service_hint")
    if any(
        "test_package_version" in _show_text(repository, path)
        for path in test_targets
    ):
        risks.append("packaging_metadata_test_hint")
    if "requirements" in lower or "pyproject.toml" in lower:
        risks.append("dependency_environment_review_needed")
    return tuple(dict.fromkeys(risks))


def _implementation_units(
    *,
    repository: Path,
    implicated_modules: tuple[str, ...],
    static_edges: tuple[tuple[str, str], ...],
    test_targets: tuple[str, ...],
) -> tuple[ImplementationUnit, ...]:
    imports_by_unit: dict[str, set[str]] = defaultdict(set)
    imported_by_unit: dict[str, set[str]] = defaultdict(set)
    for source, target in static_edges:
        imports_by_unit[source].add(target)
        imported_by_unit[target].add(source)
    marker_counts = {
        path: len(INCOMPLETE_PATTERN.findall(_show_text(repository, path)))
        for path in implicated_modules
    }
    test_hints = _test_ownership_hints(
        repository=repository,
        implicated_modules=implicated_modules,
        test_targets=test_targets,
    )
    tests_by_unit: dict[str, list[str]] = defaultdict(list)
    for hint in test_hints:
        for unit in hint.primary_units:
            tests_by_unit[unit].append(hint.test_path)
    return tuple(
        ImplementationUnit(
            unit_id=path,
            paths=(path,),
            incomplete_marker_count=marker_counts[path],
            imports_implicated_units=tuple(sorted(imports_by_unit[path])),
            imported_by_implicated_units=tuple(sorted(imported_by_unit[path])),
            test_ownership_hints=tuple(sorted(set(tests_by_unit[path]))),
        )
        for path in implicated_modules
    )


def _unit_dependencies(
    static_edges: tuple[tuple[str, str], ...],
) -> tuple[UnitDependency, ...]:
    return tuple(
        UnitDependency(
            producer=target,
            consumer=source,
            dependency_type="api_contract_static_import",
            evidence=(f"{source} imports {target}",),
        )
        for source, target in static_edges
    )


def _test_ownership_hints(
    *,
    repository: Path,
    implicated_modules: tuple[str, ...],
    test_targets: tuple[str, ...],
) -> tuple[TestOwnershipHint, ...]:
    module_names = {
        path: _module_name(path) for path in implicated_modules
    }
    hints: list[TestOwnershipHint] = []
    for test_path in test_targets:
        text = _show_text(repository, test_path)
        imports = _imported_modules(test_path, text)
        primary: list[str] = []
        evidence: list[str] = []
        for path, module in module_names.items():
            if module and any(
                imported == module or imported.startswith(f"{module}.")
                for imported in imports
            ):
                primary.append(path)
                evidence.append(f"{test_path} imports {module}")
            elif PurePosixPath(path).stem.lower() in test_path.lower():
                primary.append(path)
                evidence.append(
                    f"{test_path} filename matches {PurePosixPath(path).stem}"
                )
        hints.append(
            TestOwnershipHint(
                test_path=test_path,
                primary_units=tuple(sorted(set(primary))),
                evidence=tuple(evidence),
            )
        )
    return tuple(hints)


def _async_risk_hypotheses(
    dependencies: tuple[UnitDependency, ...],
    label: RecommendedLabel,
) -> tuple[str, ...]:
    if label == "partially_parallelizable" and dependencies:
        return tuple(
            (
                f"A consumer agent editing {dependency.consumer} may proceed "
                f"with stale or incorrect assumptions about the producer "
                f"artifact {dependency.producer}."
            )
            for dependency in dependencies[:3]
        )
    if label == "parallelizable":
        return (
            "Units appear weakly coupled; async execution should be a positive "
            "parallel-control condition rather than a stale-state stress test.",
        )
    if label == "effectively_serial":
        return (
            "Work appears concentrated in one implementation surface; "
            "multi-agent execution mainly measures decomposition overhead.",
        )
    return ()


def _recommend(
    *,
    existing_v0_3_task: bool,
    existing_label: str | None,
    curated_overlay_configured: bool,
    pytest_status: str,
    module_count: int,
    edge_count: int,
    test_count: int,
    risks: tuple[str, ...],
) -> tuple[
    RecommendedLabel,
    RecommendedRole,
    CurationStatus,
    str,
    tuple[str, ...],
]:
    rationale: list[str] = []
    if existing_v0_3_task:
        rationale.append("task already has v0.3 task/scenario/quality assets")
        return (
            _coerce_label(existing_label),
            "already_in_v0.3",
            "already_in_v0.3",
            "continue annotation or evaluation; do not reselect",
            tuple(rationale),
        )

    if pytest_status == "collection_or_import_error":
        rationale.append("raw public Commit0 does not cleanly collect")
        if curated_overlay_configured:
            rationale.append("curated bootstrap overlay is configured")
            return (
                "unclear",
                "bootstrap_review",
                "bootstrap_candidate",
                "review overlay answer-freeness before task construction",
                tuple(rationale),
            )
        rationale.append("no curated overlay is configured")
        return (
            "unclear",
            "manual_review",
            "weak_or_unclear",
            "defer unless manual review proves an answer-free bootstrap",
            tuple(rationale),
        )

    if pytest_status in {"passes_at_commit0", "no_tests_collected", "timeout"}:
        rationale.append(f"pytest status is {pytest_status}")
        return (
            "reject",
            "reject",
            "reject_or_defer",
            "defer or reject for v0.3 curation",
            tuple(rationale),
        )

    if any(
        risk in {"external_service_hint", "container_or_service_hint"}
        for risk in risks
    ):
        rationale.append("external service or container risk detected")
        return (
            "unclear",
            "manual_review",
            "weak_or_unclear",
            "manual review required before curation",
            tuple(rationale),
        )

    if edge_count and module_count >= 2:
        rationale.append("dependent implementation units are visible")
        return (
            "partially_parallelizable",
            "main_async_task",
            "direct_candidate",
            "prioritize for v0.3 task construction",
            tuple(rationale),
        )
    if module_count >= 2 and test_count >= 2:
        rationale.append("multiple implementation units with weak coupling")
        return (
            "parallelizable",
            "positive_parallel_control",
            "direct_candidate",
            "review as positive parallel-control task",
            tuple(rationale),
        )
    if module_count <= 1:
        rationale.append("work is concentrated in one implementation unit")
        return (
            "effectively_serial",
            "serial_control",
            "control_candidate",
            "review as serial/control task",
            tuple(rationale),
        )
    rationale.append("structure requires manual interpretation")
    return (
        "unclear",
        "manual_review",
        "weak_or_unclear",
        "manual structural review required",
        tuple(rationale),
    )


def _coerce_label(label: str | None) -> RecommendedLabel:
    if label in {
        "parallelizable",
        "partially_parallelizable",
        "effectively_serial",
    }:
        return label  # type: ignore[return-value]
    return "unclear"


def screen_commit0_repository(
    repository: Path | str,
    *,
    timeout_seconds: float = 60.0,
    existing_task_ids: set[str] | None = None,
    existing_task_labels: dict[str, str] | None = None,
    curated_task_ids: set[str] | None = None,
) -> Commit0AsyncScreeningRecord:
    """Build one answer-free async-structure audit record."""

    repo = Path(repository).resolve()
    candidate = extract_commit0_candidate(
        repo,
        timeout_seconds=timeout_seconds,
    )
    task_id = candidate.task_id
    existing = task_id in (existing_task_ids or set())
    curated = task_id in (curated_task_ids or set())
    run = _run_pytest(repo, timeout_seconds=timeout_seconds)
    summary = parse_pytest_summary(run.output)
    status = _classify_pytest_status(run, summary)
    risks = _risk_flags(
        repository=repo,
        pytest_status=status,
        test_targets=candidate.test_targets,
        curated_overlay_configured=curated,
    )
    label, role, curation_status, action, recommendation_rationale = (
        _recommend(
            existing_v0_3_task=existing,
            existing_label=(existing_task_labels or {}).get(task_id),
            curated_overlay_configured=curated,
            pytest_status=status,
            module_count=candidate.public_module_count,
            edge_count=len(candidate.static_dependency_edges),
            test_count=len(candidate.test_targets),
            risks=risks,
        )
    )
    dependencies = _unit_dependencies(candidate.static_dependency_edges)
    return Commit0AsyncScreeningRecord(
        task_id=task_id,
        repository_name=repo.name,
        upstream_version=candidate.upstream_version,
        existing_v0_3_task=existing,
        curated_overlay_configured=curated,
        measurement_command=run.command,
        measurement_return_code=run.return_code,
        measurement_timed_out=run.timed_out,
        pytest_status=status,
        pytest_summary=summary,
        publicly_implicated_modules=candidate.publicly_implicated_modules,
        test_targets=candidate.test_targets,
        static_dependency_edges=candidate.static_dependency_edges,
        implementation_units=_implementation_units(
            repository=repo,
            implicated_modules=candidate.publicly_implicated_modules,
            static_edges=candidate.static_dependency_edges,
            test_targets=candidate.test_targets,
        ),
        unit_dependencies=dependencies,
        test_ownership_hints=_test_ownership_hints(
            repository=repo,
            implicated_modules=candidate.publicly_implicated_modules,
            test_targets=candidate.test_targets,
        ),
        async_risk_hypotheses=_async_risk_hypotheses(dependencies, label),
        recommended_label=label,
        recommended_role=role,
        curation_status=curation_status,
        suggested_next_action=action,
        risks=risks,
        rationale=tuple(
            (
                *recommendation_rationale,
                f"{candidate.public_module_count} implicated modules",
                f"{len(candidate.static_dependency_edges)} unit dependencies",
                f"{len(candidate.test_targets)} test targets",
            )
        ),
        candidate_evidence_sources=candidate.public_evidence_sources,
    )


def screen_commit0_repositories(
    repositories: tuple[Path, ...],
    *,
    repos_root: Path,
    timeout_seconds: float = 60.0,
    existing_tasks_dir: Path = Path("manifests/pilot/v0.3/tasks"),
    curated_tasks_config: Path = Path(
        "configs/tasks/commit0_curated_tasks.v0.3.json"
    ),
) -> Commit0AsyncScreeningInventory:
    """Screen many local Commit0 repositories."""

    existing_ids = _existing_task_ids(existing_tasks_dir)
    existing_labels = _existing_task_labels(existing_tasks_dir)
    curated_ids = _curated_task_ids(curated_tasks_config)
    records = tuple(
        sorted(
            (
                screen_commit0_repository(
                    repository,
                    timeout_seconds=timeout_seconds,
                    existing_task_ids=existing_ids,
                    existing_task_labels=existing_labels,
                    curated_task_ids=curated_ids,
                )
                for repository in repositories
            ),
            key=lambda record: record.task_id,
        )
    )
    return Commit0AsyncScreeningInventory(
        repositories_root=str(repos_root),
        records=records,
    )


def write_screening_inventory(
    inventory: Commit0AsyncScreeningInventory,
    output_path: Path | str,
) -> Path:
    """Write screening JSON."""

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
