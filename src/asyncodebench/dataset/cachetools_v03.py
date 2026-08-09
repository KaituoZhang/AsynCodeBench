"""Build the v0.3 cachetools task/scenario records from public evidence."""

from __future__ import annotations

import json
from pathlib import Path

from asyncodebench.contracts import ParallelizabilityLabel
from asyncodebench.dataset.models import (
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

CACHE_TOOLS_TASK_ID = "commit0:cachetools"
CACHE_TOOLS_QUALITY_FILE = (
    "manifests/pilot/v0.3/quality/commit0_cachetools.json"
)
CACHE_TOOLS_TASK_STATEMENT = """
Complete the unfinished public APIs in `src/cachetools/keys.py` and
`src/cachetools/func.py` without modifying the tests.

The key layer must implement hashable positional/keyword argument keys,
method-key variants that ignore `self`, typed variants that distinguish equal
values of different types, stable keyword handling, `_HashedTuple` behavior,
and pickle compatibility.

The function-decorator layer must implement the FIFO, LFU, LRU, deprecated
MRU, random-replacement, and TTL cache decorators using the existing cache
classes and `cached()` API. Preserve direct and configured decorator use,
typed/untyped key selection, `maxsize` edge cases, cache metadata methods,
cache clearing, thread safety with a reentrant lock, RR `choice`, TTL
`timer`/`ttl`, and the documented MRU deprecation warning.

Preserve the existing public package API and make the repository's test suite
pass.
""".strip()


def _load_candidate(candidate_file: Path) -> dict:
    inventory = json.loads(candidate_file.read_text(encoding="utf-8"))
    matches = [
        candidate
        for candidate in inventory["candidates"]
        if candidate["task_id"] == CACHE_TOOLS_TASK_ID
    ]
    if len(matches) != 1:
        raise ValueError("expected exactly one commit0:cachetools candidate")
    return matches[0]


def dependency_annotations() -> tuple[DependencyAnnotation, ...]:
    """Return manually reviewed public semantic dependencies."""

    return (
        DependencyAnnotation(
            producer_subproblem="core_cache_api",
            consumer_subproblem="decorator_factories",
            dependency_type="api_contract",
            description=(
                "Decorator factories compose cache classes and cached() from "
                "src/cachetools/__init__.py."
            ),
            evidence_paths=(
                "src/cachetools/__init__.py",
                "src/cachetools/func.py",
                "tests/test_func.py",
            ),
        ),
        DependencyAnnotation(
            producer_subproblem="key_construction",
            consumer_subproblem="decorator_factories",
            dependency_type="api_contract",
            description=(
                "Decorator typed/untyped behavior depends on hashkey and "
                "typedkey semantics from src/cachetools/keys.py."
            ),
            evidence_paths=(
                "src/cachetools/keys.py",
                "src/cachetools/func.py",
                "tests/test_keys.py",
                "tests/test_func.py",
            ),
        ),
        DependencyAnnotation(
            producer_subproblem="decorator_factories",
            consumer_subproblem="integration_validation",
            dependency_type="test_contract",
            description=(
                "Integration tests require cache_parameters, cache_info, "
                "cache_clear, maxsize edge cases, locking, and cache-specific "
                "behavior."
            ),
            evidence_paths=("src/cachetools/func.py", "tests/test_func.py"),
        ),
    )


def build_task_record(candidate_file: Path) -> TaskRecord:
    candidate = _load_candidate(candidate_file)
    return TaskRecord(
        task_id=CACHE_TOOLS_TASK_ID,
        task_source="Commit0",
        upstream_version=candidate["upstream_version"],
        repository="commit0/cachetools",
        source_materialization=(
            "git archive of the upstream Commit0 cachetools repository at "
            "the recorded commit0 SHA"
        ),
        problem_statement=CACHE_TOOLS_TASK_STATEMENT,
        evaluator_command=(
            "python",
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            "-o",
            "addopts=",
            "tests",
        ),
        test_targets=tuple(candidate["test_targets"]),
        publicly_implicated_modules=tuple(
            candidate["publicly_implicated_modules"]
        ),
        natural_subproblems={
            "core_cache_api": ("src/cachetools/__init__.py",),
            "key_construction": ("src/cachetools/keys.py",),
            "key_integration_validation": (
                "tests/test_keys.py",
                "tests/test_cached.py",
                "tests/test_cachedmethod.py",
            ),
            "decorator_factories": ("src/cachetools/func.py",),
            "integration_validation": (
                "tests/test_keys.py",
                "tests/test_func.py",
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
        quality_evidence_file=CACHE_TOOLS_QUALITY_FILE,
        notes=(
            "The proposed label is demonstrative and not a final annotation.",
            "Task source, tests, and Commit0 implementation are unchanged.",
            (
                "The task statement is an answer-free synthesis of public "
                "docstrings, spec.pdf.bz2, and public tests at commit0."
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
                    "src/cachetools/keys.py",
                    "src/cachetools/func.py",
                ),
                primary_test_targets=(
                    "tests/test_keys.py",
                    "tests/test_func.py",
                ),
            ),
        )
    return (
        AgentAssignment(
            agent_id="key_agent",
            role="key construction specialist",
            subproblem_id="key_construction",
            writable_paths=("src/cachetools/keys.py",),
            primary_test_targets=("tests/test_keys.py",),
        ),
        AgentAssignment(
            agent_id="decorator_agent",
            role="decorator factory specialist",
            subproblem_id="decorator_factories",
            writable_paths=("src/cachetools/func.py",),
            primary_test_targets=("tests/test_func.py",),
        ),
    )


def build_scenarios() -> tuple[ScenarioRecord, ...]:
    shared = {
        "task_id": CACHE_TOOLS_TASK_ID,
        "dependency_annotations": dependency_annotations(),
        "shared_agent_scaffold": "iterative-inspect-edit-test-repair",
        "step_budget_per_agent": 24,
        "token_budget_per_agent": 60000,
        "test_budget_per_agent": 8,
        "wall_clock_budget_seconds": 1800,
    }
    return (
        ScenarioRecord(
            **shared,
            scenario_id="commit0-cachetools.iterative-single.v0.3",
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
            scenario_id="commit0-cachetools.serial-specialists.v0.3",
            execution_mode=ExecutionMode.SERIAL_SPECIALISTS,
            agent_count=2,
            assignments=_assignments(ExecutionMode.SERIAL_SPECIALISTS),
            information_profile="private-workspace",
            concurrent_execution=False,
            communication_condition="completed_artifact_handoff",
            message_delivery_policy=(
                "The decorator agent starts after receiving the completed "
                "key artifact and its targeted test result."
            ),
            integration_policy=(
                "Apply the key artifact before starting the decorator agent; "
                "then evaluate the combined workspace."
            ),
        ),
        ScenarioRecord(
            **shared,
            scenario_id="commit0-cachetools.async-private.v0.3",
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
                "Run workers concurrently in private workspaces and integrate "
                "their final artifacts after both finish."
            ),
        ),
        ScenarioRecord(
            **shared,
            scenario_id="commit0-cachetools.async-message.v0.3",
            execution_mode=ExecutionMode.ASYNC_MESSAGE,
            agent_count=2,
            assignments=_assignments(ExecutionMode.ASYNC_MESSAGE),
            information_profile="private-workspace",
            concurrent_execution=True,
            communication_condition="structured_message_and_artifact",
            message_delivery_policy=(
                "Workers may send API assumptions, status, targeted test "
                "results, and explicit patch/artifact transfers while active."
            ),
            integration_policy=(
                "Integrate the latest explicitly transferred artifacts and "
                "record whether delivered information changed later actions."
            ),
        ),
    )


def build_quality_record() -> TaskQualityRecord:
    """Build reproducible evaluator and decomposition evidence."""

    evaluator_command = (
        "python",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "-o",
        "addopts=",
        "tests",
    )
    environment = {
        "pytest": "9.0.3",
        "setuptools": "82.0.1",
    }
    return TaskQualityRecord(
        task_id=CACHE_TOOLS_TASK_ID,
        quality_status=DatasetQualityStatus.QUALIFICATION_READY,
        coordination_structure_tags=(
            CoordinationStructureTag.INTERFACE_DEPENDENCY,
        ),
        structure_rationale=(
            "Decorator factories consume the key-construction API and cannot "
            "be validated independently of its final semantics."
        ),
        public_statement_sources=(
            "spec.pdf.bz2@commit0",
            "src/cachetools/keys.py docstrings@commit0",
            "src/cachetools/func.py docstrings@commit0",
            "tests/*.py@commit0",
        ),
        environment_requirements=(
            "Python 3.10.4",
            "pytest==9.0.3",
            "setuptools==82.0.1",
        ),
        test_groups=(
            TaskTestGroup(
                group_id="core_cache_environment_control",
                purpose=TestGroupPurpose.ENVIRONMENT_CONTROL,
                command=(
                    "python",
                    "-m",
                    "pytest",
                    "-q",
                    "tests/test_cache.py",
                    "tests/test_fifo.py",
                    "tests/test_lfu.py",
                    "tests/test_lru.py",
                    "tests/test_mru.py",
                    "tests/test_rr.py",
                    "tests/test_tlru.py",
                    "tests/test_ttl.py",
                ),
                description=(
                    "Existing cache-class controls. All 127 tests pass at "
                    "commit0 and must not be counted as implementation progress."
                ),
            ),
            TaskTestGroup(
                group_id="key_direct_contract",
                purpose=TestGroupPurpose.SPECIALIST_LOCAL,
                owner_subproblem="key_construction",
                command=(
                    "python",
                    "-m",
                    "pytest",
                    "-q",
                    "tests/test_keys.py",
                ),
                description=(
                    "Direct hashkey, methodkey, typed-key, tuple, hash, and "
                    "pickle behavior."
                ),
            ),
            TaskTestGroup(
                group_id="key_wrapper_integration",
                purpose=TestGroupPurpose.SPECIALIST_LOCAL,
                owner_subproblem="key_construction",
                command=(
                    "python",
                    "-m",
                    "pytest",
                    "-q",
                    "tests/test_cached.py",
                    "tests/test_cachedmethod.py",
                ),
                description=(
                    "Key behavior exercised through the already implemented "
                    "cached() and cachedmethod() wrappers."
                ),
                prerequisites=(
                    "existing core cache and cached-wrapper APIs remain unchanged",
                ),
            ),
            TaskTestGroup(
                group_id="key_decorator_cross_contract",
                purpose=TestGroupPurpose.CROSS_SUBPROBLEM,
                command=(
                    "python",
                    "-m",
                    "pytest",
                    "-q",
                    "tests/test_func.py",
                ),
                description=(
                    "Decorator-factory behavior, metadata, cache algorithms, "
                    "typed key selection, locking, and edge cases."
                ),
                prerequisites=(
                    "key_construction artifact is integrated",
                    "existing core cache APIs remain unchanged",
                ),
            ),
            TaskTestGroup(
                group_id="full_evaluator",
                purpose=TestGroupPurpose.FULL_EVALUATOR,
                command=evaluator_command,
                description="All 215 upstream tests in one integrated workspace.",
            ),
        ),
        evaluation_snapshots=(
            EvaluationSnapshot(
                snapshot_id="commit0_initial",
                source_ref=(
                    "commit0:a0a7e2b73f9e146b8a8f2912948b17a918e5fe83"
                ),
                evidence_scope="public_initial_state",
                command=evaluator_command,
                python_version="3.10.4",
                dependency_versions=environment,
                collected=215,
                passed=153,
                failed=62,
                errors=0,
                skipped=0,
                return_code=1,
                duration_seconds=0.65,
                notes=(
                    "Test collection completed successfully.",
                    (
                        "The 62 failures are attributable to unfinished keys.py "
                        "and func.py implementations."
                    ),
                    (
                        "The 127 passing cache-class controls and other initial "
                        "passes must not be counted as agent progress."
                    ),
                ),
            ),
            EvaluationSnapshot(
                snapshot_id="completed_evaluator_sanity",
                source_ref="public-tag:v5.5.0",
                evidence_scope="evaluator_sanity_only",
                command=evaluator_command,
                python_version="3.10.4",
                dependency_versions=environment,
                collected=215,
                passed=215,
                failed=0,
                errors=0,
                skipped=0,
                return_code=0,
                duration_seconds=0.32,
                notes=(
                    (
                        "Used only to verify that the unchanged public tests "
                        "and environment admit a fully passing implementation."
                    ),
                    (
                        "This snapshot must not define decomposition, labels, "
                        "prompts, or agent-visible evidence."
                    ),
                ),
            ),
        ),
        known_limitations=(
            (
                "Decorator-factory tests require a working key artifact; there "
                "is no meaningful upstream test slice that isolates func.py "
                "from key_construction."
            ),
            (
                "Async-private degradation may include unavailable upstream "
                "key behavior as well as stale assumptions; cross-contract "
                "failure alone does not prove freshness harm."
            ),
            (
                "The task is small and fast, so asynchronous wall-clock overlap "
                "must come from model/tool execution rather than pytest duration."
            ),
        ),
        remaining_gates=(
            "two independent human annotations and adjudication if needed",
            "recorded environment requirements and evaluator command",
            "single-agent baseline result pending evaluation",
            "isolated key-specialist result pending evaluation",
            (
                "decorator-specialist result after completed-key artifact "
                "handoff pending evaluation"
            ),
        ),
    )


def build_annotation_forms(
    *,
    candidate_file: Path,
    task_record_file: Path,
) -> tuple[AnnotationForm, AnnotationForm]:
    common = {
        "task_id": CACHE_TOOLS_TASK_ID.replace("commit0:", "asyncodebench:", 1),
        "source_task_id": CACHE_TOOLS_TASK_ID,
        "candidate_evidence_file": str(candidate_file),
        "task_record_file": str(task_record_file),
        "allowed_labels": tuple(ParallelizabilityLabel),
        "independence_instructions": (
            "Use only public Commit0 evidence and the draft task record.",
            (
                "Review the linked TaskQualityRecord for evaluator validity, "
                "test-group boundaries, limitations, and pending evaluations."
            ),
            "Do not inspect reference branches, solution patches, or diffs.",
            "Do not consult the other annotator before submitting.",
            "Complete include, label, rationale, and exclusion reason if needed.",
        ),
    }
    return (
        AnnotationForm(**common, annotator_id="annotator_a"),
        AnnotationForm(**common, annotator_id="annotator_b"),
    )


def build_adjudication_form() -> AdjudicationForm:
    return AdjudicationForm(
        task_id=CACHE_TOOLS_TASK_ID.replace("commit0:", "asyncodebench:", 1),
        source_task_id=CACHE_TOOLS_TASK_ID,
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
