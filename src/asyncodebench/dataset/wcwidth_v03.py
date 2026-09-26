"""Build v0.3 wcwidth task/scenario records from public Commit0 evidence."""

from __future__ import annotations

import json
from pathlib import Path

from asyncodebench.dataset.models import (
    AdjudicationForm,
    AgentAssignment,
    AnnotationForm,
    CoordinationStructureTag,
    DatasetQualityStatus,
    DependencyAnnotation,
    EvaluationSnapshot,
    ExecutionMode,
    ParallelizabilityLabel,
    QualificationStatus,
    ScenarioRecord,
    TaskQualityRecord,
    TaskRecord,
    TaskTestGroup,
    TestGroupPurpose,
)

WCWIDTH_TASK_ID = "commit0:wcwidth"
WCWIDTH_QUALITY_FILE = (
    "manifests/pilot/v0.3/quality/commit0_wcwidth.json"
)
WCWIDTH_TASK_STATEMENT = """
Restore the unfinished Unicode terminal-width APIs in the wcwidth repository
without modifying the tests.

The Unicode-version layer must expose the supported Unicode version strings in
ascending order.

The width-computation layer must implement interval-table lookup, Unicode
version matching, single-codepoint width calculation, string width
calculation, control-character handling, combining/zero-width behavior,
East-Asian wide character behavior, VS-16 emoji presentation behavior, and
the public `wcwidth()` / `wcswidth()` API.

Preserve the public package API and make the core non-packaging evaluator pass.
The package-metadata version test is excluded because it depends on editable
installation metadata rather than the unfinished implementation.
""".strip()


def _load_candidate(candidate_file: Path) -> dict:
    inventory = json.loads(candidate_file.read_text(encoding="utf-8"))
    matches = [
        candidate
        for candidate in inventory["candidates"]
        if candidate["task_id"] == WCWIDTH_TASK_ID
    ]
    if len(matches) != 1:
        raise ValueError("expected exactly one commit0:wcwidth candidate")
    return matches[0]


def dependency_annotations() -> tuple[DependencyAnnotation, ...]:
    """Return manually reviewed dependencies visible at the public ref."""

    return (
        DependencyAnnotation(
            producer_subproblem="unicode_version_catalog",
            consumer_subproblem="width_algorithm",
            dependency_type="api_contract",
            description=(
                "The width algorithm imports list_versions() and depends on "
                "its ordering and string format when matching requested "
                "Unicode versions."
            ),
            evidence_paths=(
                "wcwidth/unicode_versions.py",
                "wcwidth/wcwidth.py",
                "tests/test_ucslevel.py",
            ),
        ),
        DependencyAnnotation(
            producer_subproblem="width_algorithm",
            consumer_subproblem="integration_validation",
            dependency_type="test_contract",
            description=(
                "Core, emoji, table-integrity, and Unicode-version tests "
                "jointly validate binary search, version matching, single "
                "codepoint width, and whole-string width semantics."
            ),
            evidence_paths=(
                "wcwidth/wcwidth.py",
                "tests/test_core.py",
                "tests/test_emojis.py",
                "tests/test_table_integrity.py",
                "tests/test_ucslevel.py",
            ),
        ),
    )


def _evaluator_command() -> tuple[str, ...]:
    return (
        "python",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "-o",
        "addopts=",
        "tests",
        "-k",
        "not test_package_version",
    )


def build_task_record(candidate_file: Path) -> TaskRecord:
    candidate = _load_candidate(candidate_file)
    return TaskRecord(
        task_id=WCWIDTH_TASK_ID,
        task_source="Commit0",
        upstream_version=candidate["upstream_version"],
        repository="commit0/wcwidth",
        source_materialization=(
            "git archive of the upstream Commit0 wcwidth repository at "
            "0d0054189bdb0fc7b9de0456fc3cee2b67a6ceba"
        ),
        problem_statement=WCWIDTH_TASK_STATEMENT,
        evaluator_command=_evaluator_command(),
        test_targets=tuple(candidate["test_targets"]),
        publicly_implicated_modules=(
            "wcwidth/unicode_versions.py",
            "wcwidth/wcwidth.py",
        ),
        natural_subproblems={
            "unicode_version_catalog": (
                "wcwidth/unicode_versions.py",
                "tests/test_ucslevel.py",
            ),
            "width_algorithm": (
                "wcwidth/wcwidth.py",
                "tests/test_core.py",
                "tests/test_emojis.py",
                "tests/test_table_integrity.py",
            ),
            "integration_validation": (
                "tests/test_core.py",
                "tests/test_emojis.py",
                "tests/test_table_integrity.py",
                "tests/test_ucslevel.py",
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
        quality_evidence_file=WCWIDTH_QUALITY_FILE,
        notes=(
            "Task source, tests, and Commit0 implementation are unchanged.",
            (
                "The evaluator excludes tests/test_core.py::"
                "test_package_version because it checks distribution "
                "metadata rather than implementation behavior."
            ),
            (
                "The proposed label is a draft curation decision and not a "
                "final independent annotation."
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
                    "wcwidth/unicode_versions.py",
                    "wcwidth/wcwidth.py",
                ),
                primary_test_targets=(
                    "tests/test_core.py",
                    "tests/test_emojis.py",
                    "tests/test_table_integrity.py",
                    "tests/test_ucslevel.py",
                ),
            ),
        )
    return (
        AgentAssignment(
            agent_id="version_agent",
            role="Unicode version catalog specialist",
            subproblem_id="unicode_version_catalog",
            writable_paths=("wcwidth/unicode_versions.py",),
            primary_test_targets=("tests/test_ucslevel.py",),
        ),
        AgentAssignment(
            agent_id="width_agent",
            role="terminal width algorithm specialist",
            subproblem_id="width_algorithm",
            writable_paths=("wcwidth/wcwidth.py",),
            primary_test_targets=(
                "tests/test_core.py",
                "tests/test_emojis.py",
                "tests/test_table_integrity.py",
            ),
        ),
    )


def build_scenarios() -> tuple[ScenarioRecord, ...]:
    shared = {
        "task_id": WCWIDTH_TASK_ID,
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
            scenario_id="commit0-wcwidth.iterative-single.v0.3",
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
            scenario_id="commit0-wcwidth.serial-specialists.v0.3",
            execution_mode=ExecutionMode.SERIAL_SPECIALISTS,
            agent_count=2,
            assignments=_assignments(ExecutionMode.SERIAL_SPECIALISTS),
            information_profile="private-workspace",
            concurrent_execution=False,
            communication_condition="completed_artifact_handoff",
            message_delivery_policy=(
                "The version specialist completes first. The width "
                "algorithm specialist then receives the completed version "
                "catalog artifact and its targeted test result."
            ),
            integration_policy=(
                "Apply the version artifact before starting the width "
                "algorithm agent, then run the core evaluator."
            ),
        ),
        ScenarioRecord(
            **shared,
            scenario_id="commit0-wcwidth.async-private.v0.3",
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
                "Run both specialists concurrently in private workspaces and "
                "integrate final artifacts after both finish."
            ),
        ),
        ScenarioRecord(
            **shared,
            scenario_id="commit0-wcwidth.async-message.v0.3",
            execution_mode=ExecutionMode.ASYNC_MESSAGE,
            agent_count=2,
            assignments=_assignments(ExecutionMode.ASYNC_MESSAGE),
            information_profile="private-workspace",
            concurrent_execution=True,
            communication_condition="structured_message_and_artifact",
            message_delivery_policy=(
                "Workers may transfer Unicode version assumptions, public API "
                "contracts, targeted test results, and explicit artifacts "
                "while active."
            ),
            integration_policy=(
                "Integrate the latest explicitly transferred artifacts and "
                "record stale version-catalog or API assumptions."
            ),
        ),
    )


def build_quality_record() -> TaskQualityRecord:
    evaluator = _evaluator_command()
    environment = {
        "pytest": "9.0.3",
        "setuptools": "82.0.1",
    }
    return TaskQualityRecord(
        task_id=WCWIDTH_TASK_ID,
        quality_status=DatasetQualityStatus.QUALIFICATION_READY,
        coordination_structure_tags=(
            CoordinationStructureTag.INTERFACE_DEPENDENCY,
        ),
        structure_rationale=(
            "The width algorithm consumes the Unicode version catalog through "
            "list_versions() and must keep version matching, table lookup, "
            "and public width semantics consistent."
        ),
        public_statement_sources=(
            "spec.pdf.bz2@commit0",
            "wcwidth/*.py docstrings@commit0",
            "tests/*.py@commit0",
        ),
        environment_requirements=(
            "Python 3.10.4",
            "pytest==9.0.3",
            "setuptools==82.0.1",
            (
                "Run from the repository root with PYTHONPATH pointing at "
                "the repository; package metadata tests are excluded."
            ),
        ),
        test_groups=(
            TaskTestGroup(
                group_id="package_metadata_control",
                purpose=TestGroupPurpose.ENVIRONMENT_CONTROL,
                command=(
                    "python",
                    "-m",
                    "pytest",
                    "-q",
                    "tests/test_core.py::test_package_version",
                ),
                description=(
                    "Packaging metadata check excluded from the benchmark "
                    "evaluator because it requires installed distribution "
                    "metadata rather than unfinished implementation behavior."
                ),
            ),
            TaskTestGroup(
                group_id="unicode_version_catalog_local",
                purpose=TestGroupPurpose.SPECIALIST_LOCAL,
                owner_subproblem="unicode_version_catalog",
                command=(
                    "python",
                    "-m",
                    "pytest",
                    "-q",
                    "tests/test_ucslevel.py",
                ),
                description=(
                    "Unicode version list and nearest-version matching. "
                    "This group depends on list_versions() from the version "
                    "catalog and _wcmatch_version() from the width layer."
                ),
            ),
            TaskTestGroup(
                group_id="width_algorithm_local",
                purpose=TestGroupPurpose.SPECIALIST_LOCAL,
                owner_subproblem="width_algorithm",
                command=(
                    "python",
                    "-m",
                    "pytest",
                    "-q",
                    "tests/test_core.py",
                    "tests/test_emojis.py",
                    "tests/test_table_integrity.py",
                    "-k",
                    "not test_package_version",
                ),
                description=(
                    "Binary search, single-codepoint widths, string widths, "
                    "emoji VS-16/ZWJ behavior, and table integrity."
                ),
            ),
            TaskTestGroup(
                group_id="version_width_cross_contract",
                purpose=TestGroupPurpose.CROSS_SUBPROBLEM,
                command=(
                    "python",
                    "-m",
                    "pytest",
                    "-q",
                    "tests/test_ucslevel.py",
                    "tests/test_core.py",
                    "tests/test_emojis.py",
                    "-k",
                    "not test_package_version",
                ),
                description=(
                    "Integrated version matching and width behavior. The "
                    "width layer must consume the completed version catalog "
                    "without stale assumptions about ordering or format."
                ),
                prerequisites=(
                    "unicode_version_catalog artifact is integrated",
                    "width_algorithm artifact is integrated",
                ),
            ),
            TaskTestGroup(
                group_id="full_evaluator",
                purpose=TestGroupPurpose.FULL_EVALUATOR,
                command=evaluator,
                description=(
                    "All core wcwidth tests except package metadata version "
                    "resolution."
                ),
            ),
        ),
        evaluation_snapshots=(
            EvaluationSnapshot(
                snapshot_id="commit0_initial_core",
                source_ref=(
                    "commit0:0d0054189bdb0fc7b9de0456fc3cee2b67a6ceba"
                ),
                evidence_scope="public_initial_state",
                command=evaluator,
                python_version="3.10.4",
                dependency_versions=environment,
                collected=38,
                passed=0,
                failed=37,
                errors=0,
                skipped=1,
                return_code=1,
                duration_seconds=0.28,
                notes=(
                    (
                        "All core tests collect successfully once the "
                        "packaging metadata test is excluded."
                    ),
                    (
                        "Failures are caused by unfinished "
                        "unicode_versions.py and wcwidth.py implementations."
                    ),
                    (
                        "The skipped test is the public upstream narrow-build "
                        "guard and is not agent progress."
                    ),
                ),
            ),
            EvaluationSnapshot(
                snapshot_id="completed_evaluator_sanity_core",
                source_ref="public-ref:origin/master",
                evidence_scope="evaluator_sanity_only",
                command=evaluator,
                python_version="3.10.4",
                dependency_versions=environment,
                collected=38,
                passed=37,
                failed=0,
                errors=0,
                skipped=1,
                return_code=0,
                duration_seconds=0.18,
                notes=(
                    (
                        "The public completed branch passes the same core "
                        "non-packaging evaluator in the same environment."
                    ),
                    (
                        "Completed source is evaluator validation only and "
                        "must not define decomposition, prompts, or "
                        "agent-visible evidence."
                    ),
                ),
            ),
        ),
        known_limitations=(
            (
                "The evaluator excludes one package metadata test so that the "
                "benchmark measures implementation behavior rather than "
                "editable-install state."
            ),
            (
                "The task is small and has only one writable algorithm module "
                "plus one version-catalog module; it is best treated as an "
                "interface-dependency pilot, not a large shared-abstraction "
                "task."
            ),
            (
                "The version local test group is not fully isolated because "
                "tests/test_ucslevel.py also exercises _wcmatch_version() in "
                "wcwidth.py."
            ),
        ),
        remaining_gates=(
            "two independent human inclusion/exclusion annotations",
            "recorded environment requirements and evaluator command",
            "single-agent baseline result pending evaluation",
            (
                "serial-specialist result after version-catalog handoff "
                "pending evaluation"
            ),
        ),
    )


def build_annotation_forms(
    *,
    candidate_file: Path,
    task_record_file: Path,
) -> tuple[AnnotationForm, AnnotationForm]:
    common = {
        "task_id": WCWIDTH_TASK_ID.replace("commit0:", "asyncodebench:", 1),
        "source_task_id": WCWIDTH_TASK_ID,
        "candidate_evidence_file": str(candidate_file),
        "task_record_file": str(task_record_file),
        "allowed_labels": tuple(ParallelizabilityLabel),
        "independence_instructions": (
            "Use only public Commit0 evidence and the draft task record.",
            (
                "Review the linked TaskQualityRecord, including the excluded "
                "package metadata test and specialist-test limitations."
            ),
            "Do not inspect reference branches, solution patches, or diffs.",
            "Do not consult the other annotator before submitting.",
            (
                "Explicitly assess whether the version-catalog to width-"
                "algorithm split is natural enough for AsynCodeBench."
            ),
        ),
    }
    return (
        AnnotationForm(**common, annotator_id="annotator_a"),
        AnnotationForm(**common, annotator_id="annotator_b"),
    )


def build_adjudication_form() -> AdjudicationForm:
    return AdjudicationForm(
        task_id=WCWIDTH_TASK_ID.replace("commit0:", "asyncodebench:", 1),
        source_task_id=WCWIDTH_TASK_ID,
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
