"""Build v0.3 curated Portalocker task records from public evidence."""

from __future__ import annotations

import json
from pathlib import Path

from asynccodebench.contracts import ParallelizabilityLabel
from asynccodebench.dataset.models import (
    AdjudicationForm,
    AgentAssignment,
    AnnotationForm,
    CoordinationStructureTag,
    DatasetQualityStatus,
    DependencyAnnotation,
    EvaluationSnapshot,
    ExecutionMode,
    QualificationStatus,
    ScenarioRecord,
    TaskQualityRecord,
    TaskRecord,
    TaskTestGroup,
    TestGroupPurpose,
)

PORTALOCKER_TASK_ID = "commit0:portalocker"
PORTALOCKER_QUALITY_FILE = (
    "manifests/pilot/v0.3/quality/commit0_portalocker.json"
)
PORTALOCKER_OVERLAY_FILE = (
    "data/overlays/commit0/portalocker/0001-import-bootstrap.patch"
)
PORTALOCKER_OVERLAY_SHA256 = (
    "954c4855872d8c4695e981cc257f72a22a4d6e5302f09f0965c2062cee8d6c54"
)
PORTALOCKER_TASK_STATEMENT = """
Restore the unfinished POSIX file-locking APIs in the Portalocker repository
without modifying the tests.

The platform backend must provide the documented POSIX `lock()` and
`unlock()` operations and translate operating-system locking failures into the
public exception hierarchy.

The utility layer must implement coalescing, atomic file replacement, timeout
handling, file-handle preparation, `Lock`, reentrant `RLock`, temporary-file
locks, and bounded semaphore behavior while preserving the existing public
flags, exceptions, context-manager API, and file lifecycle.

Preserve the public core package API and make the applicable non-Redis
upstream tests pass. RedisLock is outside this task.
""".strip()


def _load_candidate(candidate_file: Path) -> dict:
    inventory = json.loads(candidate_file.read_text(encoding="utf-8"))
    matches = [
        candidate
        for candidate in inventory["candidates"]
        if candidate["task_id"] == PORTALOCKER_TASK_ID
    ]
    if len(matches) != 1:
        raise ValueError("expected exactly one commit0:portalocker candidate")
    return matches[0]


def dependency_annotations() -> tuple[DependencyAnnotation, ...]:
    return (
        DependencyAnnotation(
            producer_subproblem="platform_lock_backend",
            consumer_subproblem="file_lock_utilities",
            dependency_type="api_contract",
            description=(
                "Lock, RLock, and semaphore utilities call the platform "
                "lock/unlock backend and depend on its flags and exceptions."
            ),
            evidence_paths=(
                "portalocker/portalocker.py",
                "portalocker/utils.py",
                "portalocker_tests/tests.py",
            ),
        ),
        DependencyAnnotation(
            producer_subproblem="file_lock_utilities",
            consumer_subproblem="integration_validation",
            dependency_type="test_contract",
            description=(
                "Semaphore, temporary-file, process-lock, and combined-module "
                "tests require consistent backend and utility semantics."
            ),
            evidence_paths=(
                "portalocker/utils.py",
                "portalocker_tests/tests.py",
                "portalocker_tests/test_semaphore.py",
                "portalocker_tests/temporary_file_lock.py",
                "portalocker_tests/test_combined.py",
            ),
        ),
    )


def build_task_record(candidate_file: Path) -> TaskRecord:
    candidate = _load_candidate(candidate_file)
    return TaskRecord(
        task_id=PORTALOCKER_TASK_ID,
        task_source="Commit0",
        upstream_version=candidate["upstream_version"],
        repository="commit0/portalocker",
        source_materialization=(
            "git archive of the upstream Commit0 Portalocker repository at "
            "300136afca11ea23c79ecfd110ed0d2819322f11 plus the verified "
            "curated bootstrap overlay recorded in "
            "configs/tasks/commit0_curated_tasks.v0.3.json"
        ),
        problem_statement=PORTALOCKER_TASK_STATEMENT,
        evaluator_command=(
            "python",
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            "-o",
            "addopts=",
            "portalocker_tests",
            "--ignore=portalocker_tests/test_redis.py",
        ),
        test_targets=tuple(
            target
            for target in candidate["test_targets"]
            if target != "portalocker_tests/test_redis.py"
        ),
        publicly_implicated_modules=(
            "portalocker/portalocker.py",
            "portalocker/utils.py",
        ),
        natural_subproblems={
            "platform_lock_backend": ("portalocker/portalocker.py",),
            "file_lock_utilities": ("portalocker/utils.py",),
            "integration_validation": (
                "portalocker_tests/tests.py",
                "portalocker_tests/test_semaphore.py",
                "portalocker_tests/temporary_file_lock.py",
                "portalocker_tests/test_combined.py",
            ),
        },
        dependency_annotations=dependency_annotations(),
        qualification_status=(
            QualificationStatus.PENDING_INDEPENDENT_ANNOTATION
        ),
        proposed_parallelizability_label=(
            ParallelizabilityLabel.PARTIALLY_PARALLELIZABLE
        ),
        candidate_evidence_file=str(candidate_file),
        quality_evidence_file=PORTALOCKER_QUALITY_FILE,
        notes=(
            (
                "The benchmark initial state is curated from raw Commit0 by "
                f"{PORTALOCKER_OVERLAY_FILE} with SHA-256 "
                f"{PORTALOCKER_OVERLAY_SHA256}."
            ),
            (
                "exceptions.py marker-only classes and the HasFileno Protocol "
                "are not treated as implementation subproblems."
            ),
            (
                "RedisLock and test_redis.py are excluded from the POSIX core "
                "task because they require a separate Python dependency and "
                "running Redis service."
            ),
        ),
    )


def _assignments(
    execution_mode: ExecutionMode,
) -> tuple[AgentAssignment, ...]:
    if execution_mode is ExecutionMode.ITERATIVE_SINGLE:
        return (
            AgentAssignment(
                agent_id="integrator",
                role="iterative full-task coding agent",
                subproblem_id="full_task",
                writable_paths=(
                    "portalocker/portalocker.py",
                    "portalocker/utils.py",
                ),
                primary_test_targets=(
                    "portalocker_tests/tests.py",
                    "portalocker_tests/test_semaphore.py",
                    "portalocker_tests/temporary_file_lock.py",
                    "portalocker_tests/test_combined.py",
                ),
            ),
        )
    return (
        AgentAssignment(
            agent_id="backend_agent",
            role="platform lock and unlock backend specialist",
            subproblem_id="platform_lock_backend",
            writable_paths=("portalocker/portalocker.py",),
            primary_test_targets=("portalocker_tests/tests.py",),
        ),
        AgentAssignment(
            agent_id="utilities_agent",
            role="file lock, reentrant lock, and semaphore specialist",
            subproblem_id="file_lock_utilities",
            writable_paths=("portalocker/utils.py",),
            primary_test_targets=(
                "portalocker_tests/tests.py",
                "portalocker_tests/test_semaphore.py",
                "portalocker_tests/temporary_file_lock.py",
            ),
        ),
    )


def build_scenarios() -> tuple[ScenarioRecord, ...]:
    shared = {
        "task_id": PORTALOCKER_TASK_ID,
        "dependency_annotations": dependency_annotations(),
        "shared_agent_scaffold": "iterative-inspect-edit-test-repair",
        "step_budget_per_agent": 32,
        "token_budget_per_agent": 80000,
        "test_budget_per_agent": 10,
        "wall_clock_budget_seconds": 2400,
    }
    return (
        ScenarioRecord(
            **shared,
            scenario_id="commit0-portalocker.iterative-single.v0.3",
            execution_mode=ExecutionMode.ITERATIVE_SINGLE,
            agent_count=1,
            assignments=_assignments(ExecutionMode.ITERATIVE_SINGLE),
            information_profile="complete-task",
            concurrent_execution=False,
            communication_condition="not_applicable",
            message_delivery_policy="No inter-agent messages.",
            integration_policy="Agent submits its final workspace.",
        ),
        ScenarioRecord(
            **shared,
            scenario_id="commit0-portalocker.serial-specialists.v0.3",
            execution_mode=ExecutionMode.SERIAL_SPECIALISTS,
            agent_count=2,
            assignments=_assignments(ExecutionMode.SERIAL_SPECIALISTS),
            information_profile="private-workspace",
            concurrent_execution=False,
            communication_condition="completed_artifact_handoff",
            message_delivery_policy=(
                "The backend specialist completes first. The utilities "
                "specialist then receives the completed backend artifact and "
                "its targeted test result."
            ),
            integration_policy=(
                "Integrate the backend before starting utilities, then run "
                "the POSIX core evaluator."
            ),
        ),
        ScenarioRecord(
            **shared,
            scenario_id="commit0-portalocker.async-private.v0.3",
            execution_mode=ExecutionMode.ASYNC_PRIVATE,
            agent_count=2,
            assignments=_assignments(ExecutionMode.ASYNC_PRIVATE),
            information_profile="private-workspace",
            concurrent_execution=True,
            communication_condition="none_in_flight",
            message_delivery_policy=(
                "No in-flight worker messages or artifacts are delivered."
            ),
            integration_policy=(
                "Run all specialists concurrently and integrate final "
                "artifacts only after all workers finish."
            ),
        ),
        ScenarioRecord(
            **shared,
            scenario_id="commit0-portalocker.async-message.v0.3",
            execution_mode=ExecutionMode.ASYNC_MESSAGE,
            agent_count=2,
            assignments=_assignments(ExecutionMode.ASYNC_MESSAGE),
            information_profile="private-workspace",
            concurrent_execution=True,
            communication_condition="structured_message_and_artifact",
            message_delivery_policy=(
                "Workers may transfer lock API assumptions, exception "
                "semantics, timeout behavior, tests, and artifacts."
            ),
            integration_policy=(
                "Integrate the latest explicitly transferred artifacts and "
                "record dependency-blocking versus stale-assumption failures."
            ),
        ),
    )


def build_quality_record() -> TaskQualityRecord:
    evaluator = (
        "python",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "-o",
        "addopts=",
        "portalocker_tests",
        "--ignore=portalocker_tests/test_redis.py",
    )
    environment = {
        "pytest": "8.4.2",
        "pytest-timeout": "2.4.0",
        "setuptools": "82.0.1",
    }
    return TaskQualityRecord(
        task_id=PORTALOCKER_TASK_ID,
        quality_status=DatasetQualityStatus.QUALIFICATION_READY,
        coordination_structure_tags=(
            CoordinationStructureTag.INTERFACE_DEPENDENCY,
        ),
        structure_rationale=(
            "Platform lock/unlock and exception semantics are consumed by "
            "Lock, RLock, temporary-file, timeout, and semaphore utilities."
        ),
        public_statement_sources=(
            "spec.pdf.bz2@commit0",
            "portalocker/*.py docstrings@commit0",
            "portalocker_tests/*.py@commit0",
        ),
        environment_requirements=(
            "Python 3.10.4",
            "POSIX locking environment",
            "pytest==8.4.2",
            "pytest-timeout==2.4.0",
            "setuptools==82.0.1",
        ),
        test_groups=(
            TaskTestGroup(
                group_id="curated_state_control",
                purpose=TestGroupPurpose.ENVIRONMENT_CONTROL,
                command=("python", "-c", "import portalocker"),
                description=(
                    "Verify that the checksum-pinned curated state imports. "
                    "This control is not agent implementation progress."
                ),
            ),
            TaskTestGroup(
                group_id="platform_backend_local",
                purpose=TestGroupPurpose.SPECIALIST_LOCAL,
                owner_subproblem="platform_lock_backend",
                command=(
                    "python",
                    "-m",
                    "pytest",
                    "-q",
                    "portalocker_tests/tests.py",
                    "-k",
                    (
                        "test_exceptions or test_simple or test_exlusive or "
                        "test_shared or test_nonblocking or test_lock_fileno"
                    ),
                ),
                description=(
                    "Direct POSIX lock/unlock, conflict, flag, fileno, and "
                    "exception behavior. Curated initial result: 5 passed and "
                    "5 failed."
                ),
            ),
            TaskTestGroup(
                group_id="utilities_local_doctest",
                purpose=TestGroupPurpose.SPECIALIST_LOCAL,
                owner_subproblem="file_lock_utilities",
                command=(
                    "python",
                    "-m",
                    "pytest",
                    "-q",
                    "--doctest-modules",
                    "portalocker/utils.py",
                ),
                description=(
                    "Public coalesce, atomic-write, and semaphore filename "
                    "doctests that do not require a completed lock backend. "
                    "Curated initial result: 4 failed."
                ),
            ),
            TaskTestGroup(
                group_id="backend_utilities_cross_contract",
                purpose=TestGroupPurpose.CROSS_SUBPROBLEM,
                command=(
                    "python",
                    "-m",
                    "pytest",
                    "-q",
                    "portalocker_tests/temporary_file_lock.py",
                    "portalocker_tests/test_combined.py",
                    "portalocker_tests/test_semaphore.py",
                    "portalocker_tests/tests.py::test_with_timeout",
                    "portalocker_tests/tests.py::test_without_timeout",
                    "portalocker_tests/tests.py::test_without_fail",
                    "portalocker_tests/tests.py::test_truncate",
                    "portalocker_tests/tests.py::test_class",
                    "portalocker_tests/tests.py::test_acquire_release",
                    (
                        "portalocker_tests/tests.py::"
                        "test_rlock_acquire_release_count"
                    ),
                    "portalocker_tests/tests.py::test_rlock_acquire_release",
                    "portalocker_tests/tests.py::test_release_unacquired",
                    "portalocker_tests/tests.py::test_blocking_timeout",
                    "portalocker_tests/tests.py::test_shared_processes",
                    "portalocker_tests/tests.py::test_exclusive_processes",
                    "portalocker_tests/tests.py::test_locker_mechanism",
                    "portalocker_tests/tests.py::test_exception",
                ),
                description=(
                    "Lock/RLock, timeout, process, semaphore, temporary-file, "
                    "combined-module, and exception integration. Curated "
                    "initial result: 4 passed and 27 failed."
                ),
                prerequisites=(
                    "platform_lock_backend artifact is integrated",
                    "file_lock_utilities artifact is integrated",
                ),
            ),
            TaskTestGroup(
                group_id="full_evaluator",
                purpose=TestGroupPurpose.FULL_EVALUATOR,
                command=evaluator,
                description=(
                    "All 40 upstream POSIX core tests; RedisLock is excluded."
                ),
            ),
        ),
        evaluation_snapshots=(
            EvaluationSnapshot(
                snapshot_id="raw_commit0_collection",
                source_ref=(
                    "commit0:300136afca11ea23c79ecfd110ed0d2819322f11"
                ),
                evidence_scope="public_initial_state",
                command=evaluator,
                python_version="3.10.4",
                dependency_versions=environment,
                collected=0,
                passed=0,
                failed=0,
                errors=0,
                skipped=0,
                return_code=4,
                duration_seconds=0.83,
                notes=(
                    (
                        "Collection fails while importing portalocker because "
                        "portalocker.portalocker.lock is absent at commit0."
                    ),
                    (
                        "This is an upstream bootstrap dependency, not an "
                        "environment or tool-format failure."
                    ),
                ),
            ),
            EvaluationSnapshot(
                snapshot_id="curated_commit0_initial",
                source_ref=(
                    "commit0:300136afca11ea23c79ecfd110ed0d2819322f11"
                    "+overlay:"
                    "954c4855872d8c4695e981cc257f72a22a4d6e5302f09f096"
                    "5c2062cee8d6c54"
                ),
                evidence_scope="public_initial_state",
                command=evaluator,
                python_version="3.10.4",
                dependency_versions=environment,
                collected=40,
                passed=8,
                failed=32,
                errors=0,
                skipped=0,
                return_code=1,
                duration_seconds=1.34,
                notes=(
                    (
                        "All POSIX core tests collect successfully from the "
                        "checksum-pinned curated initial state."
                    ),
                    (
                        "The two empty lock/unlock stubs are import controls "
                        "and must not be counted as agent progress."
                    ),
                ),
            ),
            EvaluationSnapshot(
                snapshot_id="completed_core_evaluator_sanity",
                source_ref="public-tag:v2.10.1",
                evidence_scope="evaluator_sanity_only",
                command=evaluator,
                python_version="3.10.4",
                dependency_versions=environment,
                collected=40,
                passed=40,
                failed=0,
                errors=0,
                skipped=0,
                return_code=0,
                duration_seconds=4.07,
                notes=(
                    "All unchanged POSIX core tests pass.",
                    (
                        "The completed source is evaluator validation only and "
                        "must not be exposed to agents or annotators."
                    ),
                ),
            ),
        ),
        known_limitations=(
            (
                "The released task uses a checksum-pinned curated state rather "
                "than byte-identical raw Commit0."
            ),
            (
                "Portalocker is evaluated only on Linux/POSIX; Windows uses a "
                "different backend and is outside this task."
            ),
            (
                "RedisLock is excluded from the core task because it requires "
                "the redis package and a running external service."
            ),
            (
                "Several initial passing tests are false-positive controls "
                "under no-op lock stubs and must not count as progress."
            ),
        ),
        remaining_gates=(
            "two independent human inclusion/exclusion annotations",
            "recorded Linux/POSIX environment requirements and evaluator command",
            "single-agent baseline result pending evaluation",
            "specialist-local baseline results pending evaluation",
        ),
    )


def build_annotation_forms(
    *,
    candidate_file: Path,
    task_record_file: Path,
) -> tuple[AnnotationForm, AnnotationForm]:
    common = {
        "task_id": PORTALOCKER_TASK_ID,
        "candidate_evidence_file": str(candidate_file),
        "task_record_file": str(task_record_file),
        "allowed_labels": tuple(ParallelizabilityLabel),
        "independence_instructions": (
            "Use only public Commit0 evidence and the draft task record.",
            "Review the linked TaskQualityRecord and curated overlay provenance.",
            "Do not inspect reference branches, solution patches, or diffs.",
            "Do not consult the other annotator before submitting.",
            (
                "Explicitly assess whether the empty lock/unlock bootstrap is "
                "answer-free and whether excluding Redis preserves task value."
            ),
        ),
    }
    return (
        AnnotationForm(**common, annotator_id="annotator_a"),
        AnnotationForm(**common, annotator_id="annotator_b"),
    )


def build_adjudication_form() -> AdjudicationForm:
    return AdjudicationForm(
        task_id=PORTALOCKER_TASK_ID,
        adjudicator_id="independent_adjudicator",
        annotator_ids=("annotator_a", "annotator_b"),
    )


def write_json(model, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(model.model_dump(mode="json"), indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
