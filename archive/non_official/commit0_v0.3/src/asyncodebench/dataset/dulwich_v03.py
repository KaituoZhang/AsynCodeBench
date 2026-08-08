"""Build v0.3 dulwich task/scenario records from public Commit0 evidence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

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

DULWICH_TASK_ID = "commit0:dulwich"
DULWICH_COMMIT0_SHA = "be5d53457f7ea6d8b71c3b3d276ea45a70b33a6a"
DULWICH_QUALITY_FILE = (
    "manifests/pilot/v0.3/quality/commit0_dulwich.json"
)
DULWICH_TASK_STATEMENT = """
Restore the core Dulwich behavior exercised by the public Commit0 tests without
modifying the tests.

The config layer must treat missing or inaccessible default user/system config
files as absent configuration sources. Repository initialization and refs
operations must consume that config behavior without surfacing environment
permission errors, preserve symbolic HEAD behavior, and update concrete branch
refs consistently.

The pack/object-store layer must preserve the shared Git-object contract between
pack reading/writing and object-store insertion/lookup. Optional fuzzing,
compatibility, and contrib smoke tests that require unavailable external
dependencies are excluded from this v0.3 evaluator subset.
""".strip()


def _load_candidate(candidate_file: Path) -> dict[str, Any]:
    inventory = json.loads(candidate_file.read_text(encoding="utf-8"))
    records = inventory.get("records") or inventory.get("candidates") or []
    matches = [
        candidate
        for candidate in records
        if candidate["task_id"] == DULWICH_TASK_ID
    ]
    if len(matches) != 1:
        raise ValueError("expected exactly one commit0:dulwich candidate")
    return matches[0]


def dependency_annotations() -> tuple[DependencyAnnotation, ...]:
    """Return manually reviewed dependencies visible at the public ref."""

    return (
        DependencyAnnotation(
            producer_subproblem="config_defaults",
            consumer_subproblem="repo_refs_integration",
            dependency_type="api_contract",
            description=(
                "Repo.init() and DiskRefsContainer symbolic-ref behavior "
                "consume StackedConfig.default_backends(). If the config "
                "layer raises on an inaccessible global config path, refs "
                "tests fail before ref semantics can be validated."
            ),
            evidence_paths=(
                "dulwich/config.py",
                "dulwich/repo.py",
                "dulwich/refs.py",
                "tests/test_config.py",
                "tests/test_refs.py",
            ),
        ),
        DependencyAnnotation(
            producer_subproblem="pack_format_layer",
            consumer_subproblem="object_store_layer",
            dependency_type="integration",
            description=(
                "Object-store add/read behavior depends on the pack layer's "
                "object iteration, checksums, and raw object lookup contract."
            ),
            evidence_paths=(
                "dulwich/pack.py",
                "dulwich/object_store.py",
                "dulwich/objects.py",
                "tests/test_pack.py",
                "tests/test_object_store.py",
            ),
        ),
    )


def _evaluator_command() -> tuple[str, ...]:
    return (
        "python",
        "-m",
        "pytest",
        "-q",
        "tests/test_object_store.py",
        "tests/test_pack.py",
        "tests/test_refs.py",
        "tests/test_config.py",
        "tests/test_objectspec.py",
        "tests/test_objects.py",
        "tests/test_diff_tree.py",
        "tests/test_walk.py",
    )


def build_task_record(candidate_file: Path) -> TaskRecord:
    candidate = _load_candidate(candidate_file)
    return TaskRecord(
        task_id=DULWICH_TASK_ID,
        task_source="Commit0",
        upstream_version=candidate.get("upstream_version", DULWICH_COMMIT0_SHA),
        repository="commit0/dulwich",
        source_materialization=(
            "git archive of the upstream Commit0 dulwich repository at "
            f"{DULWICH_COMMIT0_SHA}"
        ),
        problem_statement=DULWICH_TASK_STATEMENT,
        evaluator_command=_evaluator_command(),
        test_targets=(
            "tests/test_object_store.py",
            "tests/test_pack.py",
            "tests/test_refs.py",
            "tests/test_config.py",
            "tests/test_objectspec.py",
            "tests/test_objects.py",
            "tests/test_diff_tree.py",
            "tests/test_walk.py",
        ),
        publicly_implicated_modules=(
            "dulwich/config.py",
            "dulwich/repo.py",
            "dulwich/refs.py",
            "dulwich/pack.py",
            "dulwich/object_store.py",
            "dulwich/objects.py",
            "dulwich/objectspec.py",
            "dulwich/diff_tree.py",
            "dulwich/walk.py",
        ),
        natural_subproblems={
            "config_defaults": (
                "dulwich/config.py",
                "tests/test_config.py",
            ),
            "repo_refs_integration": (
                "dulwich/repo.py",
                "dulwich/refs.py",
                "tests/test_refs.py",
            ),
            "pack_format_layer": (
                "dulwich/pack.py",
                "dulwich/objects.py",
                "tests/test_pack.py",
                "tests/test_objects.py",
            ),
            "object_store_layer": (
                "dulwich/object_store.py",
                "tests/test_object_store.py",
            ),
            "integration_validation": (
                "tests/test_objectspec.py",
                "tests/test_diff_tree.py",
                "tests/test_walk.py",
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
        quality_evidence_file=DULWICH_QUALITY_FILE,
        notes=(
            "Task source, tests, and Commit0 implementation are unchanged.",
            (
                "The evaluator subset excludes fuzzing and contrib/swift "
                "smoke tests that require optional dependencies not needed "
                "for the core config/refs/object-store task."
            ),
            (
                "This construction follows the manual audit in "
                "docs/audits/COMMIT0_CANDIDATE_REVIEW_dulwich_scrapy_v0.3.md."
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
                    "dulwich/config.py",
                    "dulwich/repo.py",
                    "dulwich/refs.py",
                    "dulwich/pack.py",
                    "dulwich/object_store.py",
                    "dulwich/objects.py",
                    "dulwich/objectspec.py",
                    "dulwich/diff_tree.py",
                    "dulwich/walk.py",
                ),
                primary_test_targets=_evaluator_command()[3:],
            ),
        )
    return (
        AgentAssignment(
            agent_id="config_agent",
            role="default config backend specialist",
            subproblem_id="config_defaults",
            writable_paths=("dulwich/config.py",),
            primary_test_targets=("tests/test_config.py",),
        ),
        AgentAssignment(
            agent_id="repo_refs_agent",
            role="repository and refs integration specialist",
            subproblem_id="repo_refs_integration",
            writable_paths=("dulwich/repo.py", "dulwich/refs.py"),
            primary_test_targets=("tests/test_refs.py",),
        ),
        AgentAssignment(
            agent_id="pack_agent",
            role="pack-format and Git object specialist",
            subproblem_id="pack_format_layer",
            writable_paths=("dulwich/pack.py", "dulwich/objects.py"),
            primary_test_targets=(
                "tests/test_pack.py",
                "tests/test_objects.py",
            ),
        ),
        AgentAssignment(
            agent_id="object_store_agent",
            role="object-store integration specialist",
            subproblem_id="object_store_layer",
            writable_paths=("dulwich/object_store.py",),
            primary_test_targets=("tests/test_object_store.py",),
        ),
    )


def build_scenarios() -> tuple[ScenarioRecord, ...]:
    shared = {
        "task_id": DULWICH_TASK_ID,
        "dependency_annotations": dependency_annotations(),
        "shared_agent_scaffold": "iterative-inspect-edit-test-repair",
        "step_budget_per_agent": 28,
        "token_budget_per_agent": 70000,
        "test_budget_per_agent": 10,
        "wall_clock_budget_seconds": 2400,
    }
    return (
        ScenarioRecord(
            **shared,
            scenario_id="commit0-dulwich.iterative-single.v0.3",
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
            scenario_id="commit0-dulwich.serial-specialists.v0.3",
            execution_mode=ExecutionMode.SERIAL_SPECIALISTS,
            agent_count=4,
            assignments=_assignments(ExecutionMode.SERIAL_SPECIALISTS),
            information_profile="private-workspace",
            concurrent_execution=False,
            communication_condition="completed_artifact_handoff",
            message_delivery_policy=(
                "Specialists run with barrier synchronization. Each worker "
                "receives the completed earlier artifacts and targeted test "
                "results before starting dependent work."
            ),
            integration_policy=(
                "Apply config and pack artifacts before dependent repo/refs "
                "and object-store integration, then run the evaluator subset."
            ),
        ),
        ScenarioRecord(
            **shared,
            scenario_id="commit0-dulwich.async-private.v0.3",
            execution_mode=ExecutionMode.ASYNC_PRIVATE,
            agent_count=4,
            assignments=_assignments(ExecutionMode.ASYNC_PRIVATE),
            information_profile="private-workspace",
            concurrent_execution=True,
            communication_condition="none_in_flight",
            message_delivery_policy=(
                "No in-flight worker messages or artifacts are delivered."
            ),
            integration_policy=(
                "Run specialists concurrently in private workspaces and "
                "integrate final artifacts after all workers finish."
            ),
        ),
        ScenarioRecord(
            **shared,
            scenario_id="commit0-dulwich.async-message.v0.3",
            execution_mode=ExecutionMode.ASYNC_MESSAGE,
            agent_count=4,
            assignments=_assignments(ExecutionMode.ASYNC_MESSAGE),
            information_profile="private-workspace",
            concurrent_execution=True,
            communication_condition="structured_message_and_artifact",
            message_delivery_policy=(
                "Workers may transfer config exception semantics, symbolic "
                "ref assumptions, pack/object-store contracts, targeted test "
                "results, and explicit artifacts while active."
            ),
            integration_policy=(
                "Integrate latest explicitly transferred artifacts and record "
                "stale config or pack/object-store assumptions."
            ),
        ),
    )


def build_quality_record() -> TaskQualityRecord:
    evaluator = _evaluator_command()
    environment = {
        "pytest": "8.4.2",
    }
    return TaskQualityRecord(
        task_id=DULWICH_TASK_ID,
        quality_status=DatasetQualityStatus.QUALIFICATION_READY,
        coordination_structure_tags=(
            CoordinationStructureTag.INTERFACE_DEPENDENCY,
            CoordinationStructureTag.SHARED_ABSTRACTION,
        ),
        structure_rationale=(
            "The task exposes two natural async contracts: config default "
            "backend fallback feeds repo/refs behavior, and pack-format "
            "semantics feed object-store behavior. Both can fail semantically "
            "after clean textual integration if downstream agents assume stale "
            "producer behavior."
        ),
        public_statement_sources=(
            "README.rst@commit0",
            "dulwich/*.py docstrings@commit0",
            "tests/*.py@commit0",
            (
                "docs/audits/"
                "COMMIT0_CANDIDATE_REVIEW_dulwich_scrapy_v0.3.md"
            ),
        ),
        environment_requirements=(
            "Python 3.10.4",
            "pytest==8.4.2",
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD=1",
            (
                "Run from the repository root with PYTHONPATH=. so the "
                "Commit0 workspace package is imported."
            ),
            (
                "The evaluator subset excludes fuzzing/fuzz-targets and "
                "tests/contrib/test_swift_smoke.py because they require "
                "optional atheris/gevent dependencies."
            ),
        ),
        test_groups=(
            TaskTestGroup(
                group_id="config_defaults_local",
                purpose=TestGroupPurpose.SPECIALIST_LOCAL,
                owner_subproblem="config_defaults",
                command=(
                    "python",
                    "-m",
                    "pytest",
                    "-q",
                    "tests/test_config.py",
                ),
                description=(
                    "Config parsing and default backend behavior, including "
                    "the inaccessible global config path exercised by public "
                    "tests."
                ),
            ),
            TaskTestGroup(
                group_id="repo_refs_cross_contract",
                purpose=TestGroupPurpose.CROSS_SUBPROBLEM,
                command=(
                    "python",
                    "-m",
                    "pytest",
                    "-q",
                    "tests/test_config.py::StackedConfigTests::test_default_backends",
                    "tests/test_refs.py::DiskRefsContainerTests::test_add_if_new_symbolic",
                ),
                description=(
                    "The config fallback contract plus the repo/refs symbolic "
                    "HEAD consumer path."
                ),
                prerequisites=(
                    "config_defaults artifact is integrated",
                    "repo_refs_integration artifact is integrated",
                ),
            ),
            TaskTestGroup(
                group_id="pack_format_local",
                purpose=TestGroupPurpose.SPECIALIST_LOCAL,
                owner_subproblem="pack_format_layer",
                command=(
                    "python",
                    "-m",
                    "pytest",
                    "-q",
                    "tests/test_pack.py",
                    "tests/test_objects.py",
                ),
                description=(
                    "Pack reading/writing, Git object serialization, and raw "
                    "object lookup semantics."
                ),
            ),
            TaskTestGroup(
                group_id="object_store_cross_contract",
                purpose=TestGroupPurpose.CROSS_SUBPROBLEM,
                command=(
                    "python",
                    "-m",
                    "pytest",
                    "-q",
                    "tests/test_pack.py::TestPack::test_get",
                    "tests/test_object_store.py::DiskObjectStoreTests::test_add_pack",
                ),
                description=(
                    "Object-store add_pack behavior after the pack layer "
                    "defines object lookup and iteration semantics."
                ),
                prerequisites=(
                    "pack_format_layer artifact is integrated",
                    "object_store_layer artifact is integrated",
                ),
            ),
            TaskTestGroup(
                group_id="full_evaluator",
                purpose=TestGroupPurpose.FULL_EVALUATOR,
                command=evaluator,
                description=(
                    "Core config, refs, object-store, pack, objectspec, "
                    "objects, diff-tree, and walk tests."
                ),
            ),
        ),
        evaluation_snapshots=(
            EvaluationSnapshot(
                snapshot_id="commit0_initial_core_subset",
                source_ref=f"commit0:{DULWICH_COMMIT0_SHA}",
                evidence_scope="public_initial_state",
                command=evaluator,
                python_version="3.10.4",
                dependency_versions=environment,
                collected=540,
                passed=526,
                failed=2,
                errors=0,
                skipped=12,
                return_code=1,
                duration_seconds=1.24,
                notes=(
                    (
                        "Verified in the AsynCodeBench conda environment "
                        "with PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 and PYTHONPATH=. "
                        "The run produced 526 passed, 2 failed, 11 skipped, "
                        "and 1 xfailed; xfailed is counted with skipped for "
                        "the v0.3 accounting schema."
                    ),
                    (
                        "The two failing public tests are "
                        "tests/test_config.py::StackedConfigTests::"
                        "test_default_backends and tests/test_refs.py::"
                        "DiskRefsContainerTests::test_add_if_new_symbolic."
                    ),
                ),
            ),
        ),
        known_limitations=(
            (
                "Full upstream collection includes optional fuzzing and "
                "contrib smoke tests that require dependencies outside the "
                "core offline evaluator."
            ),
            (
                "The core subset is broad and mostly passing at commit0; the "
                "primary async signal should be reported with dependency "
                "metrics rather than only full-suite pass/fail."
            ),
            (
                "Completed-version evaluator sanity is unavailable for this "
                "local Commit0 materialization: origin/master equals commit0, "
                "origin/commit0_combined collection fails for this evaluator, "
                "and origin/upstream uses an incompatible test layout."
            ),
            (
                "Single-agent and multi-agent model results are evaluation "
                "outputs to report, not dataset qualification gates."
            ),
        ),
        remaining_gates=(
            "two independent human inclusion/exclusion annotations",
        ),
    )


def build_metric_labels() -> dict[str, Any]:
    return {
        "schema_version": "0.3-async-metrics",
        "task_id": DULWICH_TASK_ID,
        "metric_annotation_id": "commit0-dulwich.async-metrics.v0.3",
        "source_task_record": "manifests/pilot/v0.3/tasks/commit0_dulwich.json",
        "source_quality_record": (
            "manifests/pilot/v0.3/quality/commit0_dulwich.json"
        ),
        "purpose": (
            "Dependency-level labels for measuring whether asynchronous "
            "multi-agent coding resolves Dulwich's config/repo/refs and "
            "pack/object-store contracts promptly."
        ),
        "metric_definitions": {
            "ADPR": {
                "name": "Async Dependency Pass Rate",
                "unit": "fraction",
                "definition": (
                    "Fraction of registered dependency_points whose required "
                    "integrated_probe_tests pass in the final integrated "
                    "workspace."
                ),
            },
            "DRS": {
                "name": "Dependency Resolution Step",
                "unit": "agent iteration or evaluation checkpoint",
                "definition": (
                    "First recorded checkpoint at which all required "
                    "integrated_probe_tests for a dependency point pass."
                ),
            },
            "CAIL": {
                "name": "Cross-Agent Integration Lag",
                "unit": "agent iteration or evaluation checkpoint",
                "definition": (
                    "downstream_resolution_step minus upstream_resolution_step "
                    "when both probe groups have been evaluated."
                ),
            },
            "SAD": {
                "name": "Stale Assumption Duration",
                "unit": "agent iteration or event interval",
                "definition": (
                    "Interval during which a downstream worker acts on a "
                    "contract assumption inconsistent with the latest "
                    "upstream artifact visible in the integrated history."
                ),
            },
        },
        "evaluation_checkpoint_policy": {
            "minimum_policy": (
                "Run probe tests after each agent final artifact and after "
                "final integration."
            ),
            "recommended_policy": (
                "Run probe tests after every committed patch, every explicit "
                "artifact transfer, and final integration."
            ),
            "checkpoint_record_fields": [
                "run_id",
                "scenario_id",
                "checkpoint_id",
                "logical_iteration",
                "agent_id",
                "visible_upstream_artifact_version",
                "integrated_workspace_version",
                "probe_test_results",
            ],
        },
        "dependency_points": [
            {
                "dependency_id": (
                    "dulwich.config_to_repo_refs.default_backend_contract"
                ),
                "dependency_type": "interface_dependency",
                "producer_subproblem": "config_defaults",
                "consumer_subproblem": "repo_refs_integration",
                "producer_agent": "config_agent",
                "consumer_agent": "repo_refs_agent",
                "producer_files": ["dulwich/config.py"],
                "consumer_files": ["dulwich/repo.py", "dulwich/refs.py"],
                "contract_summary": (
                    "StackedConfig.default_backends() must ignore missing or "
                    "inaccessible default config files, allowing Repo.init() "
                    "and symbolic HEAD updates to proceed under HOME=/nonexistent."
                ),
                "stale_failure_mode": (
                    "The repo/refs agent may assume global config lookup can "
                    "raise filesystem permission errors or may locally mask the "
                    "exception in repo.py, leaving the producer config contract "
                    "inconsistent with other consumers."
                ),
                "upstream_probe_tests": [
                    (
                        "tests/test_config.py::StackedConfigTests::"
                        "test_default_backends"
                    )
                ],
                "downstream_probe_tests": [
                    (
                        "tests/test_refs.py::DiskRefsContainerTests::"
                        "test_add_if_new_symbolic"
                    )
                ],
                "integrated_probe_tests": [
                    (
                        "tests/test_config.py::StackedConfigTests::"
                        "test_default_backends"
                    ),
                    (
                        "tests/test_refs.py::DiskRefsContainerTests::"
                        "test_add_if_new_symbolic"
                    ),
                ],
                "resolution_criteria": (
                    "Resolved when both the config default-backend probe and "
                    "the repo/refs symbolic HEAD probe pass in the integrated "
                    "workspace."
                ),
                "metrics_enabled": ["ADPR", "DRS", "CAIL", "SAD"],
                "primary_paper_probe": True,
            },
            {
                "dependency_id": (
                    "dulwich.pack_to_object_store.add_pack_contract"
                ),
                "dependency_type": "shared_api_contract",
                "producer_subproblem": "pack_format_layer",
                "consumer_subproblem": "object_store_layer",
                "producer_agent": "pack_agent",
                "consumer_agent": "object_store_agent",
                "producer_files": ["dulwich/pack.py", "dulwich/objects.py"],
                "consumer_files": ["dulwich/object_store.py"],
                "contract_summary": (
                    "Object-store add_pack behavior depends on the pack "
                    "layer's object lookup, iteration, checksum, and raw object "
                    "semantics."
                ),
                "stale_failure_mode": (
                    "The object-store agent may implement add_pack around a "
                    "stale pack iteration or raw-object assumption, producing "
                    "a clean merge that fails once the final pack layer is "
                    "integrated."
                ),
                "upstream_probe_tests": [
                    "tests/test_pack.py::TestPack::test_get"
                ],
                "downstream_probe_tests": [
                    (
                        "tests/test_object_store.py::DiskObjectStoreTests::"
                        "test_add_pack"
                    )
                ],
                "integrated_probe_tests": [
                    "tests/test_pack.py::TestPack::test_get",
                    (
                        "tests/test_object_store.py::DiskObjectStoreTests::"
                        "test_add_pack"
                    ),
                ],
                "resolution_criteria": (
                    "Resolved when pack lookup and object-store add_pack probes "
                    "both pass after integration."
                ),
                "metrics_enabled": ["ADPR", "DRS", "CAIL", "SAD"],
            },
        ],
        "aggregate_metrics": {
            "dependency_point_count": 2,
            "primary_async_dependency_ids": [
                "dulwich.config_to_repo_refs.default_backend_contract",
                "dulwich.pack_to_object_store.add_pack_contract",
            ],
            "primary_paper_dependency_id": (
                "dulwich.config_to_repo_refs.default_backend_contract"
            ),
            "ADPR_denominator": (
                "All dependency_points unless a paper section explicitly "
                "reports primary_async_dependency_ids only."
            ),
            "minimum_success_condition_for_task_level_async_dependency_resolution": (
                "Both primary_async_dependency_ids pass in the final integrated "
                "workspace."
            ),
        },
        "annotation_notes": [
            (
                "The config_to_repo_refs dependency is the clearest async "
                "signal because downstream repo/refs behavior can continue "
                "under a stale assumption about config exception semantics."
            ),
            (
                "The pack_to_object_store dependency is retained as a shared "
                "API-contract probe for semantic integration beyond textual "
                "merge conflicts."
            ),
            (
                "These labels identify public test-observable contracts and "
                "implicated files, not solution code."
            ),
        ],
    }


def build_annotation_forms(
    *,
    candidate_file: Path,
    task_record_file: Path,
) -> tuple[AnnotationForm, AnnotationForm]:
    common = {
        "task_id": DULWICH_TASK_ID,
        "candidate_evidence_file": str(candidate_file),
        "task_record_file": str(task_record_file),
        "allowed_labels": tuple(ParallelizabilityLabel),
        "independence_instructions": (
            "Use only public Commit0 evidence and the draft task record.",
            (
                "Review the linked TaskQualityRecord, including the excluded "
                "optional fuzzing/contrib tests and the dependency-metric "
                "labels."
            ),
            "Do not inspect reference branches, solution patches, or diffs.",
            "Do not consult the other annotator before submitting.",
            (
                "Explicitly assess whether the config->repo/refs and "
                "pack->object-store splits are natural AsynCodeBench "
                "dependencies rather than artificial file partitioning."
            ),
        ),
    }
    return (
        AnnotationForm(**common, annotator_id="annotator_a"),
        AnnotationForm(**common, annotator_id="annotator_b"),
    )


def build_adjudication_form() -> AdjudicationForm:
    return AdjudicationForm(
        task_id=DULWICH_TASK_ID,
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


def write_payload(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
