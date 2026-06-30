"""Build v0.3 simpy task/scenario records from public Commit0 evidence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

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

SIMPY_TASK_ID = "commit0:simpy"
SIMPY_STRIPPED_SHA = "25496719af798e5a276289279651873ea5b6e7d1"
SIMPY_COMPLETE_SHA = "22cb5d8676f6ecccf0790d609103e975ed4cd120"
SIMPY_QUALITY_FILE = "manifests/pilot/v0.3/quality/commit0_simpy.json"
SIMPY_TASK_STATEMENT = """
Restore the core SimPy discrete-event simulation behavior exercised by the
public Commit0 tests without modifying the tests.

The environment layer must implement scheduling, stepping, running, peeking,
timeouts, and process registration. The event layer must implement event
lifecycle state, callback handling, success/failure propagation, process
resumption, interrupts, and condition composition. The resource layer must build
on those event contracts to implement resource requests, releases, stores,
containers, priority/preemptive behavior, and immediate request triggering.

Benchmark evaluation excludes benchmark tests and the package-version metadata
test. The initial benchmark source is the stripped Commit0-style ref
`origin/commit0_combined`, not the local complete/default branch.
""".strip()


def _load_candidate(candidate_file: Path) -> dict[str, Any]:
    inventory = json.loads(candidate_file.read_text(encoding="utf-8"))
    records = inventory.get("records") or inventory.get("candidates") or []
    matches = [
        candidate
        for candidate in records
        if candidate["task_id"] == SIMPY_TASK_ID
    ]
    if len(matches) != 1:
        raise ValueError("expected exactly one commit0:simpy candidate")
    return matches[0]


def dependency_annotations() -> tuple[DependencyAnnotation, ...]:
    return (
        DependencyAnnotation(
            producer_subproblem="environment_core",
            consumer_subproblem="event_lifecycle",
            dependency_type="api_contract",
            description=(
                "Event, Process, Timeout, and Condition semantics consume the "
                "Environment scheduling contract: now/peek/step/run, event "
                "ordering, callback execution, and exception propagation."
            ),
            evidence_paths=(
                "src/simpy/core.py",
                "src/simpy/events.py",
                "tests/test_environment.py",
                "tests/test_event.py",
                "tests/test_process.py",
                "tests/test_timeout.py",
            ),
        ),
        DependencyAnnotation(
            producer_subproblem="event_lifecycle",
            consumer_subproblem="resource_layer",
            dependency_type="integration",
            description=(
                "Resource, Container, Store, and PriorityStore behavior depends "
                "on event triggering, callback cleanup, process resumption, "
                "interrupt handling, and condition composition."
            ),
            evidence_paths=(
                "src/simpy/events.py",
                "src/simpy/resources/base.py",
                "src/simpy/resources/resource.py",
                "src/simpy/resources/container.py",
                "src/simpy/resources/store.py",
                "tests/test_event.py",
                "tests/test_resources.py",
            ),
        ),
        DependencyAnnotation(
            producer_subproblem="environment_core",
            consumer_subproblem="realtime_and_utilities",
            dependency_type="api_contract",
            description=(
                "RealtimeEnvironment and utility helpers consume the same "
                "Environment.run(), timeout, process, and scheduling behavior "
                "while adding wall-clock pacing and delayed-start helpers."
            ),
            evidence_paths=(
                "src/simpy/core.py",
                "src/simpy/rt.py",
                "src/simpy/util.py",
                "tests/test_rt.py",
                "tests/test_util.py",
            ),
        ),
    )


def _evaluator_command() -> tuple[str, ...]:
    return (
        "python",
        "-m",
        "pytest",
        "tests",
        "-q",
        "-m",
        "not benchmark",
        "-k",
        "not test_simpy_version",
    )


def build_task_record(candidate_file: Path) -> TaskRecord:
    _load_candidate(candidate_file)
    return TaskRecord(
        task_id=SIMPY_TASK_ID,
        task_source="Commit0",
        upstream_version=SIMPY_STRIPPED_SHA,
        repository="commit0/simpy",
        source_materialization=(
            "git archive of the stripped Commit0-style SimPy ref "
            f"origin/commit0_combined at {SIMPY_STRIPPED_SHA}"
        ),
        problem_statement=SIMPY_TASK_STATEMENT,
        evaluator_command=_evaluator_command(),
        test_targets=(
            "tests/test_condition.py",
            "tests/test_environment.py",
            "tests/test_event.py",
            "tests/test_exceptions.py",
            "tests/test_interrupts.py",
            "tests/test_process.py",
            "tests/test_resources.py",
            "tests/test_rt.py",
            "tests/test_timeout.py",
            "tests/test_util.py",
        ),
        publicly_implicated_modules=(
            "src/simpy/core.py",
            "src/simpy/events.py",
            "src/simpy/exceptions.py",
            "src/simpy/resources/base.py",
            "src/simpy/resources/resource.py",
            "src/simpy/resources/container.py",
            "src/simpy/resources/store.py",
            "src/simpy/rt.py",
            "src/simpy/util.py",
        ),
        natural_subproblems={
            "environment_core": (
                "src/simpy/core.py",
                "tests/test_environment.py",
                "tests/test_timeout.py",
            ),
            "event_lifecycle": (
                "src/simpy/events.py",
                "src/simpy/exceptions.py",
                "tests/test_event.py",
                "tests/test_process.py",
                "tests/test_interrupts.py",
                "tests/test_condition.py",
            ),
            "resource_layer": (
                "src/simpy/resources/base.py",
                "src/simpy/resources/resource.py",
                "src/simpy/resources/container.py",
                "src/simpy/resources/store.py",
                "tests/test_resources.py",
            ),
            "realtime_and_utilities": (
                "src/simpy/rt.py",
                "src/simpy/util.py",
                "tests/test_rt.py",
                "tests/test_util.py",
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
        quality_evidence_file=SIMPY_QUALITY_FILE,
        notes=(
            "Task source, tests, and stripped Commit0-style implementation are unchanged.",
            (
                "The local commit0/default branch is complete; benchmark "
                "workspaces must be materialized from origin/commit0_combined."
            ),
            (
                "The evaluator excludes benchmark-marked tests and the package "
                "version metadata test."
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
                    "src/simpy/core.py",
                    "src/simpy/events.py",
                    "src/simpy/exceptions.py",
                    "src/simpy/resources/base.py",
                    "src/simpy/resources/resource.py",
                    "src/simpy/resources/container.py",
                    "src/simpy/resources/store.py",
                    "src/simpy/rt.py",
                    "src/simpy/util.py",
                ),
                primary_test_targets=_evaluator_command()[3:],
            ),
        )
    return (
        AgentAssignment(
            agent_id="environment_agent",
            role="environment scheduling specialist",
            subproblem_id="environment_core",
            writable_paths=("src/simpy/core.py",),
            primary_test_targets=(
                "tests/test_environment.py",
                "tests/test_timeout.py",
            ),
        ),
        AgentAssignment(
            agent_id="event_agent",
            role="event lifecycle and process specialist",
            subproblem_id="event_lifecycle",
            writable_paths=("src/simpy/events.py", "src/simpy/exceptions.py"),
            primary_test_targets=(
                "tests/test_event.py",
                "tests/test_process.py",
                "tests/test_interrupts.py",
                "tests/test_condition.py",
            ),
        ),
        AgentAssignment(
            agent_id="resource_agent",
            role="resource/container/store specialist",
            subproblem_id="resource_layer",
            writable_paths=(
                "src/simpy/resources/base.py",
                "src/simpy/resources/resource.py",
                "src/simpy/resources/container.py",
                "src/simpy/resources/store.py",
            ),
            primary_test_targets=("tests/test_resources.py",),
        ),
        AgentAssignment(
            agent_id="realtime_util_agent",
            role="realtime environment and utility specialist",
            subproblem_id="realtime_and_utilities",
            writable_paths=("src/simpy/rt.py", "src/simpy/util.py"),
            primary_test_targets=("tests/test_rt.py", "tests/test_util.py"),
        ),
    )


def build_scenarios() -> tuple[ScenarioRecord, ...]:
    shared = {
        "task_id": SIMPY_TASK_ID,
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
            scenario_id="commit0-simpy.iterative-single.v0.3",
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
            scenario_id="commit0-simpy.serial-specialists.v0.3",
            execution_mode=ExecutionMode.SERIAL_SPECIALISTS,
            agent_count=4,
            assignments=_assignments(ExecutionMode.SERIAL_SPECIALISTS),
            information_profile="private-workspace",
            concurrent_execution=False,
            communication_condition="completed_artifact_handoff",
            message_delivery_policy=(
                "Specialists run with barrier synchronization. Dependent "
                "workers receive completed upstream artifacts and targeted "
                "test results before they start."
            ),
            integration_policy=(
                "Apply environment and event artifacts before dependent "
                "resource and realtime/utility artifacts, then run the "
                "evaluator."
            ),
        ),
        ScenarioRecord(
            **shared,
            scenario_id="commit0-simpy.async-private.v0.3",
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
            scenario_id="commit0-simpy.async-message.v0.3",
            execution_mode=ExecutionMode.ASYNC_MESSAGE,
            agent_count=4,
            assignments=_assignments(ExecutionMode.ASYNC_MESSAGE),
            information_profile="private-workspace",
            concurrent_execution=True,
            communication_condition="structured_message_and_artifact",
            message_delivery_policy=(
                "Workers may transfer scheduler, event, resource, realtime, "
                "and targeted test assumptions while active."
            ),
            integration_policy=(
                "Integrate latest explicitly transferred artifacts and record "
                "stale scheduling/event/resource assumptions."
            ),
        ),
    )


def build_quality_record() -> TaskQualityRecord:
    evaluator = _evaluator_command()
    environment = {
        "pytest": "8.4.2",
    }
    return TaskQualityRecord(
        task_id=SIMPY_TASK_ID,
        quality_status=DatasetQualityStatus.QUALIFICATION_READY,
        coordination_structure_tags=(
            CoordinationStructureTag.INTERFACE_DEPENDENCY,
            CoordinationStructureTag.SHARED_ABSTRACTION,
        ),
        structure_rationale=(
            "The task exposes natural async contracts between the environment "
            "scheduler, event lifecycle, resource abstractions, and realtime/"
            "utility consumers. Downstream agents can implement resources or "
            "utilities against stale assumptions about event triggering, "
            "callback cleanup, process resumption, or scheduling."
        ),
        public_statement_sources=(
            "README.rst@origin/commit0_combined",
            "src/simpy/*.py docstrings@origin/commit0_combined",
            "tests/*.py@origin/commit0_combined",
            (
                "docs/audits/"
                "COMMIT0_CANDIDATE_REVIEW_minitorch_simpy_bitstring_v0.3.md"
            ),
        ),
        environment_requirements=(
            "Python 3.10.4",
            "pytest==8.4.2",
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD=1",
            "Run from the repository root with PYTHONPATH=src.",
            (
                "Use the stripped source ref origin/commit0_combined, not the "
                "local complete/default commit0 branch."
            ),
        ),
        test_groups=(
            TaskTestGroup(
                group_id="environment_core_local",
                purpose=TestGroupPurpose.SPECIALIST_LOCAL,
                owner_subproblem="environment_core",
                command=(
                    "python",
                    "-m",
                    "pytest",
                    "-q",
                    "tests/test_environment.py",
                    "tests/test_timeout.py",
                ),
                description="Environment scheduling, run/step/peek, and timeout semantics.",
            ),
            TaskTestGroup(
                group_id="event_lifecycle_local",
                purpose=TestGroupPurpose.SPECIALIST_LOCAL,
                owner_subproblem="event_lifecycle",
                command=(
                    "python",
                    "-m",
                    "pytest",
                    "-q",
                    "tests/test_event.py",
                    "tests/test_process.py",
                    "tests/test_interrupts.py",
                    "tests/test_condition.py",
                    "tests/test_exceptions.py",
                ),
                description=(
                    "Event state, callbacks, conditions, processes, interrupts, "
                    "and exception propagation."
                ),
            ),
            TaskTestGroup(
                group_id="event_resource_cross_contract",
                purpose=TestGroupPurpose.CROSS_SUBPROBLEM,
                command=(
                    "python",
                    "-m",
                    "pytest",
                    "-q",
                    "tests/test_event.py::test_triggered",
                    "tests/test_resources.py::test_resource",
                    "tests/test_resources.py::test_immediate_put_request",
                    "tests/test_resources.py::test_immediate_get_request",
                ),
                description=(
                    "Resource request/store behavior after event trigger and "
                    "callback semantics are integrated."
                ),
                prerequisites=(
                    "event_lifecycle artifact is integrated",
                    "resource_layer artifact is integrated",
                ),
            ),
            TaskTestGroup(
                group_id="resource_layer_local",
                purpose=TestGroupPurpose.SPECIALIST_LOCAL,
                owner_subproblem="resource_layer",
                command=("python", "-m", "pytest", "-q", "tests/test_resources.py"),
                description="Resources, containers, stores, queues, and immediate request semantics.",
            ),
            TaskTestGroup(
                group_id="realtime_util_cross_contract",
                purpose=TestGroupPurpose.CROSS_SUBPROBLEM,
                command=(
                    "python",
                    "-m",
                    "pytest",
                    "-q",
                    "tests/test_environment.py::test_run_until_value",
                    "tests/test_rt.py::test_rt[0.1]",
                    "tests/test_util.py::test_start_delayed_error",
                ),
                description=(
                    "Realtime and utility behavior after environment run/"
                    "timeout semantics are integrated."
                ),
                prerequisites=(
                    "environment_core artifact is integrated",
                    "realtime_and_utilities artifact is integrated",
                ),
            ),
            TaskTestGroup(
                group_id="full_evaluator",
                purpose=TestGroupPurpose.FULL_EVALUATOR,
                command=evaluator,
                description=(
                    "All public tests under tests/ except benchmark-marked "
                    "tests and the package-version metadata test."
                ),
            ),
        ),
        evaluation_snapshots=(
            EvaluationSnapshot(
                snapshot_id="commit0_combined_initial_evaluator",
                source_ref=f"origin/commit0_combined:{SIMPY_STRIPPED_SHA}",
                evidence_scope="public_initial_state",
                command=evaluator,
                python_version="3.10.4",
                dependency_versions=environment,
                collected=139,
                passed=82,
                failed=57,
                errors=0,
                skipped=0,
                return_code=1,
                duration_seconds=0.82,
                notes=(
                    (
                        "Verified in the AsyncCodeBench conda environment "
                        "with PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 and PYTHONPATH=src."
                    ),
                    (
                        "The run also reports 11 deselected tests: benchmark "
                        "tests plus the package-version metadata test."
                    ),
                    (
                        "Failures are caused by unfinished environment, event, "
                        "resource, realtime, and utility behavior."
                    ),
                ),
            ),
            EvaluationSnapshot(
                snapshot_id="complete_commit0_evaluator_sanity",
                source_ref=f"commit0:{SIMPY_COMPLETE_SHA}",
                evidence_scope="evaluator_sanity_only",
                command=evaluator,
                python_version="3.10.4",
                dependency_versions=environment,
                collected=139,
                passed=139,
                failed=0,
                errors=0,
                skipped=0,
                return_code=0,
                duration_seconds=2.03,
                notes=(
                    (
                        "The complete/default local commit0 ref passes the same "
                        "scoped evaluator in the same environment."
                    ),
                    (
                        "The complete ref is evaluator validation only and "
                        "must not define decomposition, prompts, or agent-visible "
                        "evidence."
                    ),
                ),
            ),
        ),
        known_limitations=(
            (
                "The local commit0/default branch is complete. Benchmark "
                "workspaces must be materialized from origin/commit0_combined."
            ),
            (
                "Benchmark-marked tests and the package version metadata test "
                "are excluded because this task measures implementation "
                "behavior, not benchmarking infrastructure or distribution "
                "metadata."
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
        "task_id": SIMPY_TASK_ID,
        "metric_annotation_id": "commit0-simpy.async-metrics.v0.3",
        "source_task_record": "manifests/pilot/v0.3/tasks/commit0_simpy.json",
        "source_quality_record": "manifests/pilot/v0.3/quality/commit0_simpy.json",
        "purpose": (
            "Dependency-level labels for measuring whether asynchronous "
            "multi-agent coding resolves SimPy's scheduler/event/resource "
            "contracts promptly."
        ),
        "metric_definitions": {
            "ADPR": {
                "name": "Async Dependency Pass Rate",
                "unit": "fraction",
                "definition": (
                    "Fraction of registered dependency_points whose required "
                    "integrated_probe_tests pass in the final integrated workspace."
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
                    "contract assumption inconsistent with the latest upstream "
                    "artifact visible in the integrated history."
                ),
            },
        },
        "evaluation_checkpoint_policy": {
            "minimum_policy": (
                "Run probe tests after each agent final artifact and after final integration."
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
                "dependency_id": "simpy.environment_to_events.scheduling_contract",
                "dependency_type": "interface_dependency",
                "producer_subproblem": "environment_core",
                "consumer_subproblem": "event_lifecycle",
                "producer_agent": "environment_agent",
                "consumer_agent": "event_agent",
                "producer_files": ["src/simpy/core.py"],
                "consumer_files": ["src/simpy/events.py", "src/simpy/exceptions.py"],
                "contract_summary": (
                    "Environment.run/step/peek/timeout/process must provide "
                    "correct now, scheduling, callback, and exception behavior "
                    "for Event, Process, Timeout, and Condition consumers."
                ),
                "stale_failure_mode": (
                    "The event agent may implement lifecycle transitions or "
                    "condition callbacks against stale scheduler assumptions, "
                    "causing integration failures in process and condition tests."
                ),
                "upstream_probe_tests": [
                    "tests/test_environment.py::test_run_until_value",
                    "tests/test_timeout.py::test_discrete_time_steps",
                ],
                "downstream_probe_tests": [
                    "tests/test_event.py::test_triggered",
                    "tests/test_process.py::test_target",
                    "tests/test_condition.py::test_all_of_empty_list",
                ],
                "integrated_probe_tests": [
                    "tests/test_environment.py::test_run_until_value",
                    "tests/test_timeout.py::test_discrete_time_steps",
                    "tests/test_event.py::test_triggered",
                    "tests/test_process.py::test_target",
                ],
                "resolution_criteria": (
                    "Resolved when scheduler/time probes and event/process "
                    "consumer probes pass in the integrated workspace."
                ),
                "metrics_enabled": ["ADPR", "DRS", "CAIL", "SAD"],
                "primary_paper_probe": True,
            },
            {
                "dependency_id": "simpy.events_to_resources.request_trigger_contract",
                "dependency_type": "shared_api_contract",
                "producer_subproblem": "event_lifecycle",
                "consumer_subproblem": "resource_layer",
                "producer_agent": "event_agent",
                "consumer_agent": "resource_agent",
                "producer_files": ["src/simpy/events.py"],
                "consumer_files": [
                    "src/simpy/resources/base.py",
                    "src/simpy/resources/resource.py",
                    "src/simpy/resources/container.py",
                    "src/simpy/resources/store.py",
                ],
                "contract_summary": (
                    "Resource requests, releases, stores, containers, and "
                    "priority/preemptive queues must consume event triggered/"
                    "processed state, callbacks, and process resumption consistently."
                ),
                "stale_failure_mode": (
                    "The resource agent may build queue/request behavior around "
                    "stale event trigger or callback semantics, producing late "
                    "failures in immediate request and resource scheduling tests."
                ),
                "upstream_probe_tests": [
                    "tests/test_event.py::test_triggered",
                    "tests/test_event.py::test_condition_callback_removal",
                ],
                "downstream_probe_tests": [
                    "tests/test_resources.py::test_resource",
                    "tests/test_resources.py::test_immediate_put_request",
                    "tests/test_resources.py::test_immediate_get_request",
                ],
                "integrated_probe_tests": [
                    "tests/test_event.py::test_triggered",
                    "tests/test_resources.py::test_resource",
                    "tests/test_resources.py::test_immediate_put_request",
                    "tests/test_resources.py::test_immediate_get_request",
                ],
                "resolution_criteria": (
                    "Resolved when event trigger/callback probes and resource "
                    "immediate request probes pass after integration."
                ),
                "metrics_enabled": ["ADPR", "DRS", "CAIL", "SAD"],
            },
            {
                "dependency_id": "simpy.environment_to_realtime_util.run_timeout_contract",
                "dependency_type": "interface_dependency",
                "producer_subproblem": "environment_core",
                "consumer_subproblem": "realtime_and_utilities",
                "producer_agent": "environment_agent",
                "consumer_agent": "realtime_util_agent",
                "producer_files": ["src/simpy/core.py"],
                "consumer_files": ["src/simpy/rt.py", "src/simpy/util.py"],
                "contract_summary": (
                    "RealtimeEnvironment and utility helpers depend on "
                    "Environment.run(), timeout, process, and negative-delay "
                    "semantics."
                ),
                "stale_failure_mode": (
                    "The realtime/util agent may implement wall-clock pacing or "
                    "delayed start behavior against stale run/timeout semantics, "
                    "failing only after integration with the final environment."
                ),
                "upstream_probe_tests": [
                    "tests/test_environment.py::test_run_until_value",
                    "tests/test_timeout.py::test_negative_timeout",
                ],
                "downstream_probe_tests": [
                    "tests/test_rt.py::test_rt[0.1]",
                    "tests/test_util.py::test_start_delayed_error",
                ],
                "integrated_probe_tests": [
                    "tests/test_environment.py::test_run_until_value",
                    "tests/test_rt.py::test_rt[0.1]",
                    "tests/test_util.py::test_start_delayed_error",
                ],
                "resolution_criteria": (
                    "Resolved when environment run/timeout probes and realtime/"
                    "utility probes pass after integration."
                ),
                "metrics_enabled": ["ADPR", "DRS", "CAIL", "SAD"],
            },
        ],
        "aggregate_metrics": {
            "dependency_point_count": 3,
            "primary_async_dependency_ids": [
                "simpy.environment_to_events.scheduling_contract",
                "simpy.events_to_resources.request_trigger_contract",
            ],
            "primary_paper_dependency_id": (
                "simpy.environment_to_events.scheduling_contract"
            ),
            "ADPR_denominator": (
                "All dependency_points unless a paper section explicitly "
                "reports primary_async_dependency_ids only."
            ),
            "minimum_success_condition_for_task_level_async_dependency_resolution": (
                "Both primary_async_dependency_ids pass in the final integrated workspace."
            ),
        },
        "annotation_notes": [
            (
                "The environment_to_events dependency is the primary signal "
                "because many downstream failures arise from stale scheduler "
                "and callback assumptions."
            ),
            (
                "The events_to_resources dependency captures the resource-layer "
                "async risk: resources can be implemented against stale event "
                "trigger semantics and fail only after integration."
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
        "task_id": SIMPY_TASK_ID,
        "candidate_evidence_file": str(candidate_file),
        "task_record_file": str(task_record_file),
        "allowed_labels": tuple(ParallelizabilityLabel),
        "independence_instructions": (
            "Use only public Commit0 evidence and the draft task record.",
            (
                "Review the linked TaskQualityRecord, including the requirement "
                "to use origin/commit0_combined as the initial source ref."
            ),
            "Do not inspect reference branches, solution patches, or diffs.",
            "Do not consult the other annotator before submitting.",
            (
                "Explicitly assess whether the environment->events and "
                "events->resources splits are natural AsyncCodeBench "
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
        task_id=SIMPY_TASK_ID,
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
