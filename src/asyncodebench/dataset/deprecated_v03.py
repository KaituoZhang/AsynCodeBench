"""Build v0.3 Deprecated task/scenario records from public Commit0 evidence."""

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

DEPRECATED_TASK_ID = "commit0:deprecated"
DEPRECATED_QUALITY_FILE = (
    "manifests/pilot/v0.3/quality/commit0_deprecated.json"
)
DEPRECATED_TASK_STATEMENT = """
Complete the unfinished public APIs in `deprecated/classic.py` and
`deprecated/sphinx.py` without modifying the tests.

The classic layer must provide a `deprecated` decorator that supports both
bare and configured use on functions, methods, static methods, class methods,
and classes. It must emit the documented warning category and message,
including optional reason and version text, respect warning-filter actions,
and preserve class construction and metaclass behavior.

The Sphinx layer must provide `versionadded`, `versionchanged`, and
`deprecated` decorator factories. They must append correctly formatted Sphinx
directives to function and class docstrings, honor `line_length`, preserve
class identity, and emit deprecation warnings only for the `deprecated`
directive. Warning messages must remove Sphinx cross-reference syntax while
retaining the referenced text.

Preserve the existing public package API and make the repository's test suite
pass.
""".strip()


def _load_candidate(candidate_file: Path) -> dict:
    inventory = json.loads(candidate_file.read_text(encoding="utf-8"))
    matches = [
        candidate
        for candidate in inventory["candidates"]
        if candidate["task_id"] == DEPRECATED_TASK_ID
    ]
    if len(matches) != 1:
        raise ValueError("expected exactly one commit0:deprecated candidate")
    return matches[0]


def dependency_annotations() -> tuple[DependencyAnnotation, ...]:
    """Return manually reviewed dependencies visible at the public ref."""

    return (
        DependencyAnnotation(
            producer_subproblem="classic_warning_core",
            consumer_subproblem="sphinx_directive_layer",
            dependency_type="api_contract",
            description=(
                "SphinxAdapter inherits ClassicAdapter and relies on its "
                "constructor, __call__, warning-message, action, category, "
                "reason, and version behavior."
            ),
            evidence_paths=(
                "deprecated/classic.py",
                "deprecated/sphinx.py",
                "tests/test_deprecated.py",
                "tests/test_sphinx.py",
            ),
        ),
        DependencyAnnotation(
            producer_subproblem="classic_warning_core",
            consumer_subproblem="sphinx_directive_layer",
            dependency_type="integration",
            description=(
                "The Sphinx deprecated decorator must preserve the classic "
                "function, method, class, staticmethod, classmethod, warning "
                "filter, and custom warning-category semantics."
            ),
            evidence_paths=(
                "deprecated/classic.py",
                "deprecated/sphinx.py",
                "tests/test_deprecated_class.py",
                "tests/test_deprecated_metaclass.py",
                "tests/test_sphinx.py",
                "tests/test_sphinx_class.py",
                "tests/test_sphinx_metaclass.py",
            ),
        ),
        DependencyAnnotation(
            producer_subproblem="sphinx_directive_layer",
            consumer_subproblem="integration_validation",
            dependency_type="test_contract",
            description=(
                "Integrated behavior must add correctly wrapped Sphinx "
                "directives, strip cross-reference syntax from warnings, "
                "preserve class identity, and emit warnings only for the "
                "deprecated directive."
            ),
            evidence_paths=(
                "deprecated/sphinx.py",
                "tests/test_sphinx.py",
                "tests/test_sphinx_adapter.py",
                "tests/test_sphinx_class.py",
            ),
        ),
    )


def build_task_record(candidate_file: Path) -> TaskRecord:
    candidate = _load_candidate(candidate_file)
    return TaskRecord(
        task_id=DEPRECATED_TASK_ID,
        task_source="Commit0",
        upstream_version=candidate["upstream_version"],
        repository="commit0/deprecated",
        source_materialization=(
            "git archive of the upstream Commit0 Deprecated repository at "
            "the recorded commit0 SHA"
        ),
        problem_statement=DEPRECATED_TASK_STATEMENT,
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
            "classic_warning_core": (
                "deprecated/classic.py",
                "tests/test_deprecated.py",
                "tests/test_deprecated_class.py",
                "tests/test_deprecated_metaclass.py",
                "tests/test_sphinx_metaclass.py",
            ),
            "sphinx_directive_layer": (
                "deprecated/sphinx.py",
                "tests/test_sphinx.py",
                "tests/test_sphinx_adapter.py",
                "tests/test_sphinx_class.py",
            ),
            "integration_validation": (
                "deprecated/__init__.py",
                "tests/test.py",
                "tests/test_sphinx.py",
                "tests/test_sphinx_class.py",
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
        quality_evidence_file=DEPRECATED_QUALITY_FILE,
        notes=(
            "The proposed label is demonstrative and not a final annotation.",
            "Task source, tests, and Commit0 implementation are unchanged.",
            (
                "The public dependency from deprecated/sphinx.py to "
                "deprecated/classic.py defines the serial handoff order."
            ),
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
                    "deprecated/classic.py",
                    "deprecated/sphinx.py",
                ),
                primary_test_targets=(
                    "tests/test_deprecated.py",
                    "tests/test_deprecated_class.py",
                    "tests/test_deprecated_metaclass.py",
                    "tests/test_sphinx.py",
                    "tests/test_sphinx_adapter.py",
                    "tests/test_sphinx_class.py",
                    "tests/test_sphinx_metaclass.py",
                ),
            ),
        )
    return (
        AgentAssignment(
            agent_id="classic_agent",
            role="classic warning and decorator specialist",
            subproblem_id="classic_warning_core",
            writable_paths=("deprecated/classic.py",),
            primary_test_targets=(
                "tests/test_deprecated.py",
                "tests/test_deprecated_class.py",
                "tests/test_deprecated_metaclass.py",
                "tests/test_sphinx_metaclass.py",
            ),
        ),
        AgentAssignment(
            agent_id="sphinx_agent",
            role="Sphinx directive and adapter specialist",
            subproblem_id="sphinx_directive_layer",
            writable_paths=("deprecated/sphinx.py",),
            primary_test_targets=(
                "tests/test_sphinx.py",
                "tests/test_sphinx_adapter.py",
                "tests/test_sphinx_class.py",
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
        "setuptools": "78.1.1",
        "wrapt": "1.17.3",
    }
    return TaskQualityRecord(
        task_id=DEPRECATED_TASK_ID,
        quality_status=DatasetQualityStatus.QUALIFICATION_READY,
        coordination_structure_tags=(
            CoordinationStructureTag.INTERFACE_DEPENDENCY,
            CoordinationStructureTag.SHARED_ABSTRACTION,
        ),
        structure_rationale=(
            "SphinxAdapter inherits and consumes ClassicAdapter while both "
            "layers must preserve one shared decorator and warning abstraction."
        ),
        public_statement_sources=(
            "spec.pdf.bz2@commit0",
            "deprecated/classic.py docstrings@commit0",
            "deprecated/sphinx.py docstrings@commit0",
            "tests/*.py@commit0",
        ),
        environment_requirements=(
            "Python 3.10.4",
            "wrapt==1.17.3",
            "pytest==9.0.3",
            "setuptools==78.1.1",
        ),
        test_groups=(
            TaskTestGroup(
                group_id="environment_control",
                purpose=TestGroupPurpose.ENVIRONMENT_CONTROL,
                command=(
                    "python",
                    "-m",
                    "pytest",
                    "-q",
                    "tests/test.py",
                ),
                description=(
                    "Package metadata controls; these pass at commit0 and "
                    "must not be counted as implementation progress."
                ),
            ),
            TaskTestGroup(
                group_id="classic_local_contract",
                purpose=TestGroupPurpose.SPECIALIST_LOCAL,
                owner_subproblem="classic_warning_core",
                command=(
                    "python",
                    "-m",
                    "pytest",
                    "-q",
                    "tests/test_deprecated.py",
                    "tests/test_deprecated_class.py",
                    "tests/test_deprecated_metaclass.py",
                    "tests/test_sphinx_metaclass.py",
                ),
                description=(
                    "Classic warning, decorator, class-construction, and "
                    "metaclass behavior. test_sphinx_metaclass.py imports the "
                    "Sphinx module but exercises deprecated.classic.deprecated."
                ),
            ),
            TaskTestGroup(
                group_id="sphinx_local_contract",
                purpose=TestGroupPurpose.SPECIALIST_LOCAL,
                owner_subproblem="sphinx_directive_layer",
                command=(
                    "python",
                    "-m",
                    "pytest",
                    "-q",
                    "tests/test_sphinx_adapter.py",
                    "-k",
                    "versionadded or versionchanged",
                ),
                description=(
                    "Sphinx docstring and factory behavior that can make "
                    "progress without a completed classic deprecated path."
                ),
                prerequisites=("ClassicAdapter constructor remains available.",),
            ),
            TaskTestGroup(
                group_id="classic_sphinx_cross_contract",
                purpose=TestGroupPurpose.CROSS_SUBPROBLEM,
                command=(
                    "python",
                    "-m",
                    "pytest",
                    "-q",
                    "tests/test_sphinx.py",
                    "tests/test_sphinx_class.py",
                ),
                description=(
                    "Cross-module warning, decorator, class-identity, "
                    "docstring, and Sphinx-reference behavior."
                ),
                prerequisites=(
                    "classic_warning_core artifact is integrated",
                    "sphinx_directive_layer artifact is integrated",
                ),
            ),
            TaskTestGroup(
                group_id="full_evaluator",
                purpose=TestGroupPurpose.FULL_EVALUATOR,
                command=evaluator_command,
                description="All 171 upstream tests in one integrated workspace.",
            ),
        ),
        evaluation_snapshots=(
            EvaluationSnapshot(
                snapshot_id="commit0_initial",
                source_ref=(
                    "commit0:b7e2114c046abb489e4e23ab9f829778b076650d"
                ),
                evidence_scope="public_initial_state",
                command=evaluator_command,
                python_version="3.10.4",
                dependency_versions=environment,
                collected=171,
                passed=17,
                failed=104,
                errors=50,
                skipped=0,
                return_code=1,
                duration_seconds=1.29,
                notes=(
                    "Test collection completed successfully.",
                    (
                        "Failures and setup errors are caused by unfinished "
                        "public implementations, not missing dependencies."
                    ),
                    (
                        "Initial passing tests are controls and partial "
                        "behavior; progress must use newly passing tests."
                    ),
                ),
            ),
            EvaluationSnapshot(
                snapshot_id="completed_evaluator_sanity",
                source_ref="public-tag:v1.2.14",
                evidence_scope="evaluator_sanity_only",
                command=evaluator_command,
                python_version="3.10.4",
                dependency_versions=environment,
                collected=171,
                passed=171,
                failed=0,
                errors=0,
                skipped=0,
                return_code=0,
                duration_seconds=0.84,
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
                "The Sphinx deprecated path is downstream of ClassicAdapter; "
                "cross-contract failures alone do not prove freshness harm."
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
            "specialist-local baseline results pending evaluation",
        ),
    )


def build_scenarios() -> tuple[ScenarioRecord, ...]:
    shared = {
        "task_id": DEPRECATED_TASK_ID,
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
            scenario_id="commit0-deprecated.iterative-single.v0.3",
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
            scenario_id="commit0-deprecated.serial-specialists.v0.3",
            execution_mode=ExecutionMode.SERIAL_SPECIALISTS,
            agent_count=2,
            assignments=_assignments(ExecutionMode.SERIAL_SPECIALISTS),
            information_profile="private-workspace",
            concurrent_execution=False,
            communication_condition="completed_artifact_handoff",
            message_delivery_policy=(
                "The Sphinx agent starts after receiving the completed "
                "Classic artifact and its targeted test results."
            ),
            integration_policy=(
                "Apply and validate the Classic artifact before starting the "
                "Sphinx agent; then evaluate the combined workspace."
            ),
        ),
        ScenarioRecord(
            **shared,
            scenario_id="commit0-deprecated.async-private.v0.3",
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
                "Run Classic and Sphinx workers concurrently in private "
                "workspaces and integrate final artifacts after both finish."
            ),
        ),
        ScenarioRecord(
            **shared,
            scenario_id="commit0-deprecated.async-message.v0.3",
            execution_mode=ExecutionMode.ASYNC_MESSAGE,
            agent_count=2,
            assignments=_assignments(ExecutionMode.ASYNC_MESSAGE),
            information_profile="private-workspace",
            concurrent_execution=True,
            communication_condition="structured_message_and_artifact",
            message_delivery_policy=(
                "Workers may send adapter/decorator API assumptions, status, "
                "targeted test results, and explicit artifact transfers."
            ),
            integration_policy=(
                "Integrate the latest explicitly transferred artifacts and "
                "record whether delivered information changed later actions."
            ),
        ),
    )


def build_annotation_forms(
    *,
    candidate_file: Path,
    task_record_file: Path,
) -> tuple[AnnotationForm, AnnotationForm]:
    common = {
        "task_id": DEPRECATED_TASK_ID,
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
        task_id=DEPRECATED_TASK_ID,
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
