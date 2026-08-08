"""Build v0.3 curated TinyDB task records from public Commit0 evidence."""

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

TINYDB_TASK_ID = "commit0:tinydb"
TINYDB_QUALITY_FILE = "manifests/pilot/v0.3/quality/commit0_tinydb.json"
TINYDB_OVERLAY_FILE = (
    "data/overlays/commit0/tinydb/0001-import-bootstrap.patch"
)
TINYDB_OVERLAY_SHA256 = (
    "fa0d43a64a64d6bcd085661328bfca566f678f384ac4bf6c8bf2b79b0c01a464"
)
TINYDB_TASK_STATEMENT = """
Restore the unfinished public APIs in the TinyDB repository without modifying
the tests.

The query and utility layer must provide immutable query values, LRU caching,
query construction and composition, and document update operations.

The persistence and table layer must provide JSON and memory storage plus
table insertion, lookup, search, update, upsert, removal, ID allocation, query
caching, and complete-database read/write behavior.

The database and middleware layer must provide table lifecycle management,
default-table forwarding, storage access and cleanup, and caching middleware
read/write/flush behavior.

Preserve the public package API and the shared database representation across
all layers, and make the repository's test suite pass.
""".strip()


def _load_candidate(candidate_file: Path) -> dict:
    inventory = json.loads(candidate_file.read_text(encoding="utf-8"))
    matches = [
        candidate
        for candidate in inventory["candidates"]
        if candidate["task_id"] == TINYDB_TASK_ID
    ]
    if len(matches) != 1:
        raise ValueError("expected exactly one commit0:tinydb candidate")
    return matches[0]


def dependency_annotations() -> tuple[DependencyAnnotation, ...]:
    """Return manually reviewed dependencies visible at the public ref."""

    return (
        DependencyAnnotation(
            producer_subproblem="query_contract_layer",
            consumer_subproblem="database_state_stack",
            dependency_type="api_contract",
            description=(
                "Table search and query caching consume QueryLike, freeze, "
                "and LRUCache behavior from the query and utility layer."
            ),
            evidence_paths=(
                "tinydb/utils.py",
                "tinydb/queries.py",
                "tinydb/table.py",
                "tests/test_utils.py",
                "tests/test_queries.py",
                "tests/test_tables.py",
            ),
        ),
        DependencyAnnotation(
            producer_subproblem="database_state_stack",
            consumer_subproblem="integration_validation",
            dependency_type="integration",
            description=(
                "TinyDB, Table, Storage, and CachingMiddleware must agree on "
                "the complete database mapping, table names, document IDs, "
                "read/write lifecycle, and cache invalidation semantics."
            ),
            evidence_paths=(
                "tinydb/storages.py",
                "tinydb/table.py",
                "tinydb/database.py",
                "tinydb/middlewares.py",
                "tests/test_storages.py",
                "tests/test_tables.py",
                "tests/test_tinydb.py",
                "tests/test_middlewares.py",
            ),
        ),
        DependencyAnnotation(
            producer_subproblem="query_contract_layer",
            consumer_subproblem="integration_validation",
            dependency_type="test_contract",
            description=(
                "Document transforms and composed queries are exercised "
                "through integrated TinyDB update, search, and cache paths."
            ),
            evidence_paths=(
                "tinydb/operations.py",
                "tinydb/queries.py",
                "tinydb/table.py",
                "tests/test_operations.py",
                "tests/test_tinydb.py",
            ),
        ),
    )


def build_task_record(candidate_file: Path) -> TaskRecord:
    candidate = _load_candidate(candidate_file)
    return TaskRecord(
        task_id=TINYDB_TASK_ID,
        task_source="Commit0",
        upstream_version=candidate["upstream_version"],
        repository="commit0/tinydb",
        source_materialization=(
            "git archive of the upstream Commit0 TinyDB repository at "
            "ed761a72c8c1e1cb24ca4dbcc089f35c5264d357 plus the verified "
            "curated bootstrap overlay recorded in "
            "configs/tasks/commit0_curated_tasks.v0.3.json"
        ),
        problem_statement=TINYDB_TASK_STATEMENT,
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
        publicly_implicated_modules=(
            "tinydb/database.py",
            "tinydb/middlewares.py",
            "tinydb/operations.py",
            "tinydb/queries.py",
            "tinydb/storages.py",
            "tinydb/table.py",
            "tinydb/utils.py",
        ),
        natural_subproblems={
            "query_contract_layer": (
                "tinydb/utils.py",
                "tinydb/queries.py",
                "tinydb/operations.py",
                "tests/test_utils.py",
                "tests/test_queries.py",
            ),
            "database_state_stack": (
                "tinydb/storages.py",
                "tinydb/table.py",
                "tinydb/database.py",
                "tinydb/middlewares.py",
                "tests/test_storages.py",
                "tests/test_middlewares.py",
            ),
            "integration_validation": (
                "tests/conftest.py",
                "tests/test_operations.py",
                "tests/test_tables.py",
                "tests/test_tinydb.py",
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
        quality_evidence_file=TINYDB_QUALITY_FILE,
        notes=(
            (
                "The benchmark initial state is curated from raw Commit0 by "
                f"{TINYDB_OVERLAY_FILE} with SHA-256 "
                f"{TINYDB_OVERLAY_SHA256}."
            ),
            (
                "tinydb/__init__.py is excluded from the implementation "
                "surface because its automatic incomplete marker is a false "
                "positive."
            ),
            (
                "The overlay restores only runtime class-definition "
                "prerequisites; it does not provide query, storage, table, "
                "database, middleware, or correct immutability behavior."
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
                    "tinydb/utils.py",
                    "tinydb/queries.py",
                    "tinydb/operations.py",
                    "tinydb/storages.py",
                    "tinydb/table.py",
                    "tinydb/database.py",
                    "tinydb/middlewares.py",
                ),
                primary_test_targets=(
                    "tests/test_utils.py",
                    "tests/test_queries.py",
                    "tests/test_operations.py",
                    "tests/test_storages.py",
                    "tests/test_tables.py",
                    "tests/test_tinydb.py",
                    "tests/test_middlewares.py",
                ),
            ),
        )
    return (
        AgentAssignment(
            agent_id="query_agent",
            role="query, utility, and document-operation specialist",
            subproblem_id="query_contract_layer",
            writable_paths=(
                "tinydb/utils.py",
                "tinydb/queries.py",
                "tinydb/operations.py",
            ),
            primary_test_targets=(
                "tests/test_utils.py",
                "tests/test_queries.py",
                "tests/test_operations.py",
            ),
        ),
        AgentAssignment(
            agent_id="state_agent",
            role="shared database-state stack specialist",
            subproblem_id="database_state_stack",
            writable_paths=(
                "tinydb/storages.py",
                "tinydb/table.py",
                "tinydb/database.py",
                "tinydb/middlewares.py",
            ),
            primary_test_targets=(
                "tests/test_storages.py",
                "tests/test_tables.py",
                "tests/test_tinydb.py",
                "tests/test_middlewares.py",
            ),
        ),
    )


def build_scenarios() -> tuple[ScenarioRecord, ...]:
    shared = {
        "task_id": TINYDB_TASK_ID,
        "dependency_annotations": dependency_annotations(),
        "shared_agent_scaffold": "iterative-inspect-edit-test-repair",
        "step_budget_per_agent": 40,
        "token_budget_per_agent": 100000,
        "test_budget_per_agent": 12,
        "wall_clock_budget_seconds": 3600,
    }
    return (
        ScenarioRecord(
            **shared,
            scenario_id="commit0-tinydb.iterative-single.v0.3",
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
            scenario_id="commit0-tinydb.serial-specialists.v0.3",
            execution_mode=ExecutionMode.SERIAL_SPECIALISTS,
            agent_count=2,
            assignments=_assignments(ExecutionMode.SERIAL_SPECIALISTS),
            information_profile="private-workspace",
            concurrent_execution=False,
            communication_condition="completed_artifact_handoff",
            message_delivery_policy=(
                "The query-contract specialist completes first. The shared "
                "database-state specialist then receives its completed "
                "artifact and targeted test result."
            ),
            integration_policy=(
                "Integrate each completed layer before starting its consumer, "
                "then run the full evaluator."
            ),
        ),
        ScenarioRecord(
            **shared,
            scenario_id="commit0-tinydb.async-private.v0.3",
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
            scenario_id="commit0-tinydb.async-message.v0.3",
            execution_mode=ExecutionMode.ASYNC_MESSAGE,
            agent_count=2,
            assignments=_assignments(ExecutionMode.ASYNC_MESSAGE),
            information_profile="private-workspace",
            concurrent_execution=True,
            communication_condition="structured_message_and_artifact",
            message_delivery_policy=(
                "Workers may transfer database-representation assumptions, "
                "API contracts, cache semantics, targeted tests, and explicit "
                "artifacts while active."
            ),
            integration_policy=(
                "Integrate the latest explicitly transferred artifacts and "
                "record stale shared-state or API assumptions."
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
        "tests",
    )
    environment = {
        "pytest": "9.0.3",
        "PyYAML": "6.0.3",
        "setuptools": "82.0.1",
    }
    return TaskQualityRecord(
        task_id=TINYDB_TASK_ID,
        quality_status=DatasetQualityStatus.QUALIFICATION_READY,
        coordination_structure_tags=(
            CoordinationStructureTag.INTERFACE_DEPENDENCY,
            CoordinationStructureTag.SHARED_ABSTRACTION,
        ),
        structure_rationale=(
            "Query/cache semantics feed Table, while Storage, Table, TinyDB, "
            "and Middleware share one complete-database state abstraction."
        ),
        public_statement_sources=(
            "spec.pdf.bz2@commit0",
            "tinydb/*.py docstrings@commit0",
            "tests/*.py@commit0",
        ),
        environment_requirements=(
            "Python 3.10.4",
            "pytest==9.0.3",
            "PyYAML==6.0.3",
            "setuptools==82.0.1",
        ),
        test_groups=(
            TaskTestGroup(
                group_id="curated_state_control",
                purpose=TestGroupPurpose.ENVIRONMENT_CONTROL,
                command=(
                    "python",
                    "-c",
                    "import tinydb; from tinydb.utils import FrozenDict",
                ),
                description=(
                    "Verify that the checksum-pinned curated state imports. "
                    "This control is not agent implementation progress."
                ),
            ),
            TaskTestGroup(
                group_id="query_contract_local",
                purpose=TestGroupPurpose.SPECIALIST_LOCAL,
                owner_subproblem="query_contract_layer",
                command=(
                    "python",
                    "-m",
                    "pytest",
                    "-q",
                    "tests/test_utils.py",
                    "tests/test_queries.py",
                ),
                description=(
                    "Query, immutable-value, and LRU cache behavior. Curated "
                    "initial result: 2 passed and 39 failed."
                ),
            ),
            TaskTestGroup(
                group_id="database_state_local",
                purpose=TestGroupPurpose.SPECIALIST_LOCAL,
                owner_subproblem="database_state_stack",
                command=(
                    "python",
                    "-m",
                    "pytest",
                    "-q",
                    "tests/test_storages.py",
                    "tests/test_middlewares.py",
                ),
                description=(
                    "Storage and caching-middleware behavior owned by the "
                    "shared-state specialist. Curated initial result: 2 "
                    "passed, 14 failed, and 5 errors."
                ),
            ),
            TaskTestGroup(
                group_id="query_state_cross_contract",
                purpose=TestGroupPurpose.CROSS_SUBPROBLEM,
                command=(
                    "python",
                    "-m",
                    "pytest",
                    "-q",
                    "tests/test_operations.py",
                    "tests/test_tables.py",
                    "tests/test_tinydb.py",
                ),
                description=(
                    "Integrated operations, Table, TinyDB, query-cache, "
                    "document-ID, and persistence behavior. Curated initial "
                    "result: 1 passed, 18 failed, and 120 errors."
                ),
                prerequisites=(
                    "query_contract_layer artifact is integrated",
                    "database_state_stack artifact is integrated",
                ),
            ),
            TaskTestGroup(
                group_id="full_evaluator",
                purpose=TestGroupPurpose.FULL_EVALUATOR,
                command=evaluator,
                description="All 201 upstream TinyDB tests.",
            ),
        ),
        evaluation_snapshots=(
            EvaluationSnapshot(
                snapshot_id="raw_commit0_collection",
                source_ref=(
                    "commit0:ed761a72c8c1e1cb24ca4dbcc089f35c5264d357"
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
                duration_seconds=0.35,
                notes=(
                    (
                        "Raw Commit0 fails during package import because "
                        "FrozenDict aliases an undefined _immutable symbol."
                    ),
                    (
                        "This snapshot motivates the reviewed bootstrap "
                        "overlay and is not the released agent initial state."
                    ),
                ),
            ),
            EvaluationSnapshot(
                snapshot_id="curated_commit0_initial",
                source_ref=(
                    "commit0:ed761a72c8c1e1cb24ca4dbcc089f35c5264d357"
                    "+overlay:"
                    "fa0d43a64a64d6bcd085661328bfca566f678f384ac4bf6c8"
                    "bf2b79b0c01a464"
                ),
                evidence_scope="public_initial_state",
                command=evaluator,
                python_version="3.10.4",
                dependency_versions=environment,
                collected=201,
                passed=5,
                failed=71,
                errors=125,
                skipped=0,
                return_code=1,
                duration_seconds=53.19,
                notes=(
                    (
                        "All upstream tests collect successfully from the "
                        "checksum-pinned curated initial state."
                    ),
                    (
                        "Failures and setup errors are caused by unfinished "
                        "public implementations, not missing dependencies."
                    ),
                    (
                        "The two import-only overlay edits are controls and "
                        "must not be counted as agent progress."
                    ),
                ),
            ),
            EvaluationSnapshot(
                snapshot_id="completed_evaluator_sanity",
                source_ref="public-tag:v4.8.0",
                evidence_scope="evaluator_sanity_only",
                command=evaluator,
                python_version="3.10.4",
                dependency_versions=environment,
                collected=201,
                passed=201,
                failed=0,
                errors=0,
                skipped=0,
                return_code=0,
                duration_seconds=0.66,
                notes=(
                    (
                        "The unchanged public tests pass against the completed "
                        "public release in the same environment."
                    ),
                    (
                        "Completed source is evaluator validation only and "
                        "must not define decomposition or agent-visible context."
                    ),
                ),
            ),
        ),
        known_limitations=(
            (
                "The released task uses an explicitly curated initial state "
                "rather than byte-identical raw Commit0."
            ),
            (
                "The database-state specialist owns four tightly coupled "
                "modules; this preserves the natural abstraction but creates "
                "an asymmetric workload."
            ),
            (
                "The task is substantially larger than cachetools and "
                "Deprecated; single-agent, serial-specialist, and async "
                "results must be interpreted separately."
            ),
            (
                "Cross-contract tests produce many setup errors until storage "
                "and table foundations exist; errors alone do not establish "
                "asynchronous freshness harm."
            ),
        ),
        remaining_gates=(
            "two independent human inclusion/exclusion annotations",
            "recorded environment requirements and evaluator command",
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
        "task_id": TINYDB_TASK_ID,
        "candidate_evidence_file": str(candidate_file),
        "task_record_file": str(task_record_file),
        "allowed_labels": tuple(ParallelizabilityLabel),
        "independence_instructions": (
            "Use only public Commit0 evidence and the draft task record.",
            "Review the linked TaskQualityRecord and curated overlay provenance.",
            "Do not inspect reference branches, solution patches, or diffs.",
            "Do not consult the other annotator before submitting.",
            (
                "Explicitly assess whether the two-edit import bootstrap is "
                "answer-free and whether the two-specialist split is natural."
            ),
        ),
    }
    return (
        AnnotationForm(**common, annotator_id="annotator_a"),
        AnnotationForm(**common, annotator_id="annotator_b"),
    )


def build_adjudication_form() -> AdjudicationForm:
    return AdjudicationForm(
        task_id=TINYDB_TASK_ID,
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
