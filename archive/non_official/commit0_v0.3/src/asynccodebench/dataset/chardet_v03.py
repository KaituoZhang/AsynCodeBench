"""Build v0.3 chardet task/scenario records from public Commit0 evidence."""

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

CHARDET_TASK_ID = "commit0:chardet"
CHARDET_STRIPPED_SHA = "5539fa54d17ec61bacb4d3bb29ec6fba9dfcb882"
CHARDET_COMPLETE_SHA = "98b2acd6216e9a0fa4f47940b9f8adabdfd8aa8a"
CHARDET_QUALITY_FILE = "manifests/pilot/v0.3/quality/commit0_chardet.json"
CHARDET_TASK_STATEMENT = """
Restore the core chardet encoding-detection behavior exercised by the public
Commit0 corpus test without modifying the test or corpus files.

The public API must expose `detect()` and `detect_all()` over byte inputs. The
UniversalDetector layer must maintain input-state, BOM/escape/high-byte routing,
result aggregation, and confidence thresholds. Charset prober groups must
aggregate single-byte, multi-byte, escape-sequence, and Unicode probers using a
consistent state and confidence contract. Encoding-specific probers and
distribution/state-machine helpers must produce corpus-level detection results
for the deterministic public fixtures.

Benchmark evaluation uses the deterministic `test_encoding_detection` corpus
test. Hypothesis property tests, when available in the environment, are not part
of this v0.3 evaluator.
""".strip()


def _load_candidate(candidate_file: Path) -> dict[str, Any]:
    inventory = json.loads(candidate_file.read_text(encoding="utf-8"))
    records = inventory.get("records") or inventory.get("candidates") or []
    matches = [
        candidate
        for candidate in records
        if candidate["task_id"] == CHARDET_TASK_ID
    ]
    if len(matches) != 1:
        raise ValueError("expected exactly one commit0:chardet candidate")
    return matches[0]


def dependency_annotations() -> tuple[DependencyAnnotation, ...]:
    return (
        DependencyAnnotation(
            producer_subproblem="prober_base_and_grouping",
            consumer_subproblem="public_api_and_detector_state",
            dependency_type="api_contract",
            description=(
                "UniversalDetector and the public detect/detect_all API consume "
                "charset prober state, confidence, active/inactive routing, "
                "and result naming semantics from the base and group probers."
            ),
            evidence_paths=(
                "chardet/__init__.py",
                "chardet/universaldetector.py",
                "chardet/charsetprober.py",
                "chardet/charsetgroupprober.py",
                "chardet/sbcsgroupprober.py",
                "chardet/mbcsgroupprober.py",
                "test.py",
            ),
        ),
        DependencyAnnotation(
            producer_subproblem="multibyte_state_and_distribution",
            consumer_subproblem="prober_base_and_grouping",
            dependency_type="integration",
            description=(
                "Multi-byte group probers consume coding state machines, "
                "distribution analyzers, language models, and prober feed/"
                "confidence semantics for Big5, EUC-JP, EUC-KR, GB2312, "
                "SHIFT_JIS, Johab, and related encodings."
            ),
            evidence_paths=(
                "chardet/chardistribution.py",
                "chardet/codingstatemachine.py",
                "chardet/mbcharsetprober.py",
                "chardet/mbcsgroupprober.py",
                "chardet/big5prober.py",
                "chardet/eucjpprober.py",
                "chardet/euckrprober.py",
                "chardet/gb2312prober.py",
                "chardet/sjisprober.py",
                "test.py",
            ),
        ),
        DependencyAnnotation(
            producer_subproblem="singlebyte_unicode_probers",
            consumer_subproblem="public_api_and_detector_state",
            dependency_type="integration",
            description=(
                "The public detector consumes UTF, Latin-1, Hebrew, and "
                "single-byte language probers through the same charset prober "
                "state/confidence/result contract."
            ),
            evidence_paths=(
                "chardet/utf8prober.py",
                "chardet/utf1632prober.py",
                "chardet/latin1prober.py",
                "chardet/hebrewprober.py",
                "chardet/sbcharsetprober.py",
                "chardet/sbcsgroupprober.py",
                "chardet/universaldetector.py",
                "test.py",
            ),
        ),
    )


def _evaluator_command() -> tuple[str, ...]:
    return (
        "python",
        "-m",
        "pytest",
        "-q",
        "test.py::test_encoding_detection",
    )


def build_task_record(candidate_file: Path) -> TaskRecord:
    _load_candidate(candidate_file)
    return TaskRecord(
        task_id=CHARDET_TASK_ID,
        task_source="Commit0",
        upstream_version=CHARDET_STRIPPED_SHA,
        repository="commit0/chardet",
        source_materialization=(
            "git archive of the stripped Commit0-style chardet ref "
            f"origin/commit0_combined at {CHARDET_STRIPPED_SHA}"
        ),
        problem_statement=CHARDET_TASK_STATEMENT,
        evaluator_command=_evaluator_command(),
        test_targets=("test.py::test_encoding_detection",),
        publicly_implicated_modules=(
            "chardet/__init__.py",
            "chardet/universaldetector.py",
            "chardet/enums.py",
            "chardet/charsetprober.py",
            "chardet/charsetgroupprober.py",
            "chardet/sbcharsetprober.py",
            "chardet/sbcsgroupprober.py",
            "chardet/mbcharsetprober.py",
            "chardet/mbcsgroupprober.py",
            "chardet/chardistribution.py",
            "chardet/codingstatemachine.py",
            "chardet/escprober.py",
            "chardet/escsm.py",
            "chardet/utf8prober.py",
            "chardet/utf1632prober.py",
            "chardet/latin1prober.py",
            "chardet/hebrewprober.py",
            "chardet/big5prober.py",
            "chardet/eucjpprober.py",
            "chardet/euckrprober.py",
            "chardet/gb2312prober.py",
            "chardet/sjisprober.py",
        ),
        natural_subproblems={
            "public_api_and_detector_state": (
                "chardet/__init__.py",
                "chardet/universaldetector.py",
                "chardet/enums.py",
                "test.py",
            ),
            "prober_base_and_grouping": (
                "chardet/charsetprober.py",
                "chardet/charsetgroupprober.py",
                "chardet/sbcharsetprober.py",
                "chardet/sbcsgroupprober.py",
                "chardet/mbcharsetprober.py",
                "chardet/mbcsgroupprober.py",
            ),
            "multibyte_state_and_distribution": (
                "chardet/chardistribution.py",
                "chardet/codingstatemachine.py",
                "chardet/escprober.py",
                "chardet/escsm.py",
                "chardet/big5prober.py",
                "chardet/eucjpprober.py",
                "chardet/euckrprober.py",
                "chardet/gb2312prober.py",
                "chardet/sjisprober.py",
            ),
            "singlebyte_unicode_probers": (
                "chardet/utf8prober.py",
                "chardet/utf1632prober.py",
                "chardet/latin1prober.py",
                "chardet/hebrewprober.py",
                "chardet/sbcharsetprober.py",
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
        quality_evidence_file=CHARDET_QUALITY_FILE,
        notes=(
            "Task source, tests, corpus files, and stripped Commit0-style implementation are unchanged.",
            (
                "The local main/commit0 branch is complete; benchmark "
                "workspaces must be materialized from origin/commit0_combined."
            ),
            (
                "The evaluator is deliberately scoped to deterministic public "
                "corpus detection and excludes Hypothesis property tests."
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
                    "chardet/__init__.py",
                    "chardet/universaldetector.py",
                    "chardet/enums.py",
                    "chardet/charsetprober.py",
                    "chardet/charsetgroupprober.py",
                    "chardet/sbcharsetprober.py",
                    "chardet/sbcsgroupprober.py",
                    "chardet/mbcharsetprober.py",
                    "chardet/mbcsgroupprober.py",
                    "chardet/chardistribution.py",
                    "chardet/codingstatemachine.py",
                    "chardet/escprober.py",
                    "chardet/escsm.py",
                    "chardet/utf8prober.py",
                    "chardet/utf1632prober.py",
                    "chardet/latin1prober.py",
                    "chardet/hebrewprober.py",
                    "chardet/big5prober.py",
                    "chardet/eucjpprober.py",
                    "chardet/euckrprober.py",
                    "chardet/gb2312prober.py",
                    "chardet/sjisprober.py",
                ),
                primary_test_targets=("test.py::test_encoding_detection",),
            ),
        )
    return (
        AgentAssignment(
            agent_id="detector_agent",
            role="public API and UniversalDetector state specialist",
            subproblem_id="public_api_and_detector_state",
            writable_paths=(
                "chardet/__init__.py",
                "chardet/universaldetector.py",
                "chardet/enums.py",
            ),
            primary_test_targets=("test.py::test_encoding_detection",),
        ),
        AgentAssignment(
            agent_id="group_prober_agent",
            role="charset prober base and group orchestration specialist",
            subproblem_id="prober_base_and_grouping",
            writable_paths=(
                "chardet/charsetprober.py",
                "chardet/charsetgroupprober.py",
                "chardet/sbcharsetprober.py",
                "chardet/sbcsgroupprober.py",
                "chardet/mbcharsetprober.py",
                "chardet/mbcsgroupprober.py",
            ),
            primary_test_targets=("test.py::test_encoding_detection",),
        ),
        AgentAssignment(
            agent_id="multibyte_agent",
            role="multi-byte state machine and distribution specialist",
            subproblem_id="multibyte_state_and_distribution",
            writable_paths=(
                "chardet/chardistribution.py",
                "chardet/codingstatemachine.py",
                "chardet/escprober.py",
                "chardet/escsm.py",
                "chardet/big5prober.py",
                "chardet/eucjpprober.py",
                "chardet/euckrprober.py",
                "chardet/gb2312prober.py",
                "chardet/sjisprober.py",
            ),
            primary_test_targets=("test.py::test_encoding_detection",),
        ),
        AgentAssignment(
            agent_id="singlebyte_unicode_agent",
            role="single-byte and Unicode prober specialist",
            subproblem_id="singlebyte_unicode_probers",
            writable_paths=(
                "chardet/utf8prober.py",
                "chardet/utf1632prober.py",
                "chardet/latin1prober.py",
                "chardet/hebrewprober.py",
                "chardet/sbcharsetprober.py",
            ),
            primary_test_targets=("test.py::test_encoding_detection",),
        ),
    )


def build_scenarios() -> tuple[ScenarioRecord, ...]:
    shared = {
        "task_id": CHARDET_TASK_ID,
        "dependency_annotations": dependency_annotations(),
        "shared_agent_scaffold": "iterative-inspect-edit-test-repair",
        "step_budget_per_agent": 24,
        "token_budget_per_agent": 65000,
        "test_budget_per_agent": 8,
        "wall_clock_budget_seconds": 2400,
    }
    return (
        ScenarioRecord(
            **shared,
            scenario_id="commit0-chardet.iterative-single.v0.3",
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
            scenario_id="commit0-chardet.serial-specialists.v0.3",
            execution_mode=ExecutionMode.SERIAL_SPECIALISTS,
            agent_count=4,
            assignments=_assignments(ExecutionMode.SERIAL_SPECIALISTS),
            information_profile="private-workspace",
            concurrent_execution=False,
            communication_condition="completed_artifact_handoff",
            message_delivery_policy=(
                "Specialists run with barrier synchronization. Detector and "
                "public-API work receives completed prober/group artifacts and "
                "targeted corpus results before final integration."
            ),
            integration_policy=(
                "Apply prober base/group artifacts and encoding-specific "
                "artifacts before integrating UniversalDetector/public API."
            ),
        ),
        ScenarioRecord(
            **shared,
            scenario_id="commit0-chardet.async-private.v0.3",
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
            scenario_id="commit0-chardet.async-message.v0.3",
            execution_mode=ExecutionMode.ASYNC_MESSAGE,
            agent_count=4,
            assignments=_assignments(ExecutionMode.ASYNC_MESSAGE),
            information_profile="private-workspace",
            concurrent_execution=True,
            communication_condition="structured_message_and_artifact",
            message_delivery_policy=(
                "Workers may transfer detector, prober state, confidence, and "
                "corpus-result assumptions while active."
            ),
            integration_policy=(
                "Integrate latest explicitly transferred artifacts and record "
                "stale detector/prober confidence and result-shape assumptions."
            ),
        ),
    )


def build_quality_record() -> TaskQualityRecord:
    evaluator = _evaluator_command()
    environment = {"pytest": "8.4.2"}
    return TaskQualityRecord(
        task_id=CHARDET_TASK_ID,
        quality_status=DatasetQualityStatus.QUALIFICATION_READY,
        coordination_structure_tags=(
            CoordinationStructureTag.INTERFACE_DEPENDENCY,
            CoordinationStructureTag.SHARED_ABSTRACTION,
        ),
        structure_rationale=(
            "The task exposes natural async contracts between public detector "
            "state, prober base/group orchestration, and encoding-specific "
            "single-byte, Unicode, and multi-byte probers. Downstream detector "
            "logic can make stale assumptions about prober state names, "
            "confidence thresholds, charset labels, and active-prober routing."
        ),
        public_statement_sources=(
            "README.rst@origin/commit0_combined",
            "docs/how-it-works.rst@origin/commit0_combined",
            "chardet/*.py docstrings@origin/commit0_combined",
            "test.py@origin/commit0_combined",
            "tests/* corpus files@origin/commit0_combined",
        ),
        environment_requirements=(
            "Python 3.10.4",
            "pytest==8.4.2",
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD=1",
            "Run from the repository root with PYTHONPATH=.",
            (
                "Use the stripped source ref origin/commit0_combined, not the "
                "local complete/default main or commit0 branch."
            ),
            (
                "Use test.py::test_encoding_detection to exclude optional "
                "Hypothesis property tests from this deterministic v0.3 evaluator."
            ),
        ),
        test_groups=(
            TaskTestGroup(
                group_id="detector_public_api_local",
                purpose=TestGroupPurpose.SPECIALIST_LOCAL,
                owner_subproblem="public_api_and_detector_state",
                command=(
                    "python",
                    "-m",
                    "pytest",
                    "-q",
                    "test.py::test_encoding_detection",
                    "-k",
                    "ascii or utf-8 or utf-16 or utf-32",
                ),
                description=(
                    "Public detect/detect_all, BOM/Unicode routing, and detector "
                    "state behavior on deterministic public corpus fixtures."
                ),
            ),
            TaskTestGroup(
                group_id="multibyte_cross_contract",
                purpose=TestGroupPurpose.CROSS_SUBPROBLEM,
                command=(
                    "python",
                    "-m",
                    "pytest",
                    "-q",
                    "test.py::test_encoding_detection",
                    "-k",
                    "Big5 or EUC-JP or SHIFT_JIS",
                ),
                description=(
                    "Multi-byte state/distribution probers integrated with "
                    "group prober and detector result aggregation."
                ),
                prerequisites=(
                    "multibyte_state_and_distribution artifact is integrated",
                    "prober_base_and_grouping artifact is integrated",
                    "public_api_and_detector_state artifact is integrated",
                ),
            ),
            TaskTestGroup(
                group_id="singlebyte_unicode_cross_contract",
                purpose=TestGroupPurpose.CROSS_SUBPROBLEM,
                command=(
                    "python",
                    "-m",
                    "pytest",
                    "-q",
                    "test.py::test_encoding_detection",
                    "-k",
                    "windows-1251 or KOI8-R or utf-8",
                ),
                description=(
                    "Single-byte and Unicode probers integrated with detector "
                    "state, confidence, and charset result naming."
                ),
                prerequisites=(
                    "singlebyte_unicode_probers artifact is integrated",
                    "prober_base_and_grouping artifact is integrated",
                    "public_api_and_detector_state artifact is integrated",
                ),
            ),
            TaskTestGroup(
                group_id="full_evaluator",
                purpose=TestGroupPurpose.FULL_EVALUATOR,
                command=evaluator,
                description=(
                    "Deterministic public encoding-detection corpus test."
                ),
            ),
        ),
        evaluation_snapshots=(
            EvaluationSnapshot(
                snapshot_id="commit0_combined_initial_evaluator",
                source_ref=f"origin/commit0_combined:{CHARDET_STRIPPED_SHA}",
                evidence_scope="public_initial_state",
                command=evaluator,
                python_version="3.10.4",
                dependency_versions=environment,
                collected=381,
                passed=1,
                failed=374,
                errors=0,
                skipped=6,
                return_code=1,
                duration_seconds=4.45,
                notes=(
                    (
                        "Verified in the AsyncCodeBench conda environment "
                        "with PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 and PYTHONPATH=."
                    ),
                    (
                        "Pytest reports 6 xfailed parametrized corpus cases; "
                        "TaskQualityRecord accounts for xfailed cases as skipped."
                    ),
                    (
                        "Failures are functional detector/prober failures, "
                        "primarily missing detector state and incomplete "
                        "encoding-specific corpus behavior."
                    ),
                ),
            ),
            EvaluationSnapshot(
                snapshot_id="complete_commit0_evaluator_sanity",
                source_ref=f"commit0/main:{CHARDET_COMPLETE_SHA}",
                evidence_scope="evaluator_sanity_only",
                command=evaluator,
                python_version="3.10.4",
                dependency_versions=environment,
                collected=382,
                passed=377,
                failed=0,
                errors=0,
                skipped=5,
                return_code=0,
                duration_seconds=36.09,
                notes=(
                    (
                        "The local complete/default main branch passes the "
                        "same deterministic corpus evaluator."
                    ),
                    (
                        "Pytest reports 5 xfailed parametrized corpus cases; "
                        "TaskQualityRecord accounts for xfailed cases as skipped."
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
                "The raw stripped repository is broader than this v0.3 task. "
                "The released evaluator is scoped to deterministic corpus "
                "encoding detection and excludes optional Hypothesis property tests."
            ),
            (
                "Some frequency/model-table recovery remains domain-heavy; "
                "the task is included because the public detector/prober "
                "dependency contracts are cleanly executable and observable."
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
        "task_id": CHARDET_TASK_ID,
        "metric_annotation_id": "commit0-chardet.async-metrics.v0.3",
        "source_task_record": "manifests/pilot/v0.3/tasks/commit0_chardet.json",
        "source_quality_record": "manifests/pilot/v0.3/quality/commit0_chardet.json",
        "purpose": (
            "Dependency-level labels for measuring whether asynchronous "
            "multi-agent coding resolves chardet's detector/prober contracts."
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
                "dependency_id": "chardet.probers_to_detector.input_state_confidence_contract",
                "dependency_type": "interface_dependency",
                "producer_subproblem": "prober_base_and_grouping",
                "consumer_subproblem": "public_api_and_detector_state",
                "producer_agent": "group_prober_agent",
                "consumer_agent": "detector_agent",
                "producer_files": [
                    "chardet/charsetprober.py",
                    "chardet/charsetgroupprober.py",
                    "chardet/sbcsgroupprober.py",
                    "chardet/mbcsgroupprober.py",
                ],
                "consumer_files": [
                    "chardet/__init__.py",
                    "chardet/universaldetector.py",
                ],
                "contract_summary": (
                    "UniversalDetector and detect_all must consume prober "
                    "state, confidence, active/inactive status, and charset "
                    "result names consistently."
                ),
                "stale_failure_mode": (
                    "The detector agent may expose input_state/result behavior "
                    "against stale prober status or confidence semantics, "
                    "causing broad corpus failures despite clean imports."
                ),
                "upstream_probe_tests": [
                    "test.py::test_encoding_detection[tests/ascii/howto.diveintomark.org.xml-ascii]",
                    "test.py::test_encoding_detection[tests/utf-8/_ude_1.txt-utf-8]",
                ],
                "downstream_probe_tests": [
                    "test.py::test_encoding_detection[tests/Big5/_ude_1.txt-big5]",
                    "test.py::test_encoding_detection[tests/windows-1251-russian/_ude_1.txt-windows-1251]",
                ],
                "integrated_probe_tests": [
                    "test.py::test_encoding_detection[tests/ascii/howto.diveintomark.org.xml-ascii]",
                    "test.py::test_encoding_detection[tests/Big5/_ude_1.txt-big5]",
                    "test.py::test_encoding_detection[tests/windows-1251-russian/_ude_1.txt-windows-1251]",
                ],
                "resolution_criteria": (
                    "Resolved when public API detector probes and representative "
                    "prober-backed corpus probes pass in the integrated workspace."
                ),
                "metrics_enabled": ["ADPR", "DRS", "CAIL", "SAD"],
                "primary_paper_probe": True,
            },
            {
                "dependency_id": "chardet.multibyte_to_group.distribution_state_contract",
                "dependency_type": "integration_contract",
                "producer_subproblem": "multibyte_state_and_distribution",
                "consumer_subproblem": "prober_base_and_grouping",
                "producer_agent": "multibyte_agent",
                "consumer_agent": "group_prober_agent",
                "producer_files": [
                    "chardet/chardistribution.py",
                    "chardet/codingstatemachine.py",
                    "chardet/big5prober.py",
                    "chardet/eucjpprober.py",
                    "chardet/sjisprober.py",
                ],
                "consumer_files": [
                    "chardet/mbcharsetprober.py",
                    "chardet/mbcsgroupprober.py",
                ],
                "contract_summary": (
                    "Multi-byte probers must expose feed/state/confidence and "
                    "charset names compatible with group aggregation and "
                    "UniversalDetector result selection."
                ),
                "stale_failure_mode": (
                    "The group prober agent may aggregate multi-byte prober "
                    "results using stale state-machine or distribution analyzer "
                    "semantics, failing Big5/EUC/SHIFT_JIS corpus probes."
                ),
                "upstream_probe_tests": [
                    "test.py::test_encoding_detection[tests/Big5/_ude_1.txt-big5]",
                    "test.py::test_encoding_detection[tests/EUC-JP/_ude_1.txt-euc-jp]",
                ],
                "downstream_probe_tests": [
                    "test.py::test_encoding_detection[tests/SHIFT_JIS/_ude_1.txt-shift_jis]",
                    "test.py::test_encoding_detection[tests/EUC-KR/_ude_euc1.txt-euc-kr]",
                ],
                "integrated_probe_tests": [
                    "test.py::test_encoding_detection[tests/Big5/_ude_1.txt-big5]",
                    "test.py::test_encoding_detection[tests/EUC-JP/_ude_1.txt-euc-jp]",
                    "test.py::test_encoding_detection[tests/SHIFT_JIS/_ude_1.txt-shift_jis]",
                ],
                "resolution_criteria": (
                    "Resolved when representative multi-byte corpus probes pass "
                    "after state/distribution and group prober integration."
                ),
                "metrics_enabled": ["ADPR", "DRS", "CAIL", "SAD"],
            },
            {
                "dependency_id": "chardet.singlebyte_unicode_to_detector.result_contract",
                "dependency_type": "shared_api_contract",
                "producer_subproblem": "singlebyte_unicode_probers",
                "consumer_subproblem": "public_api_and_detector_state",
                "producer_agent": "singlebyte_unicode_agent",
                "consumer_agent": "detector_agent",
                "producer_files": [
                    "chardet/utf8prober.py",
                    "chardet/utf1632prober.py",
                    "chardet/latin1prober.py",
                    "chardet/hebrewprober.py",
                    "chardet/sbcharsetprober.py",
                ],
                "consumer_files": [
                    "chardet/universaldetector.py",
                    "chardet/__init__.py",
                ],
                "contract_summary": (
                    "UTF, Latin-1, Hebrew, and single-byte probers must share "
                    "charset labels, confidence thresholds, and done/not-done "
                    "state semantics with UniversalDetector."
                ),
                "stale_failure_mode": (
                    "The detector agent may finalize results using stale "
                    "single-byte or Unicode confidence semantics, producing "
                    "late corpus mismatches after integration."
                ),
                "upstream_probe_tests": [
                    "test.py::test_encoding_detection[tests/utf-8/_ude_1.txt-utf-8]",
                    "test.py::test_encoding_detection[tests/UTF-16/bom-utf-16-be.srt-utf-16]",
                ],
                "downstream_probe_tests": [
                    "test.py::test_encoding_detection[tests/windows-1251-russian/_ude_1.txt-windows-1251]",
                    "test.py::test_encoding_detection[tests/KOI8-R/_ude_1.txt-koi8-r]",
                ],
                "integrated_probe_tests": [
                    "test.py::test_encoding_detection[tests/utf-8/_ude_1.txt-utf-8]",
                    "test.py::test_encoding_detection[tests/UTF-16/bom-utf-16-be.srt-utf-16]",
                    "test.py::test_encoding_detection[tests/windows-1251-russian/_ude_1.txt-windows-1251]",
                ],
                "resolution_criteria": (
                    "Resolved when representative Unicode and single-byte "
                    "corpus probes pass with the integrated detector."
                ),
                "metrics_enabled": ["ADPR", "DRS", "CAIL", "SAD"],
            },
        ],
        "aggregate_metrics": {
            "dependency_point_count": 3,
            "primary_async_dependency_ids": [
                "chardet.probers_to_detector.input_state_confidence_contract",
                "chardet.multibyte_to_group.distribution_state_contract",
            ],
            "primary_paper_dependency_id": (
                "chardet.probers_to_detector.input_state_confidence_contract"
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
                "The prober_to_detector dependency is primary because the "
                "public API and UniversalDetector can fail broadly if they use "
                "stale prober state or confidence assumptions."
            ),
            (
                "The multibyte dependency captures the group-prober async risk "
                "without requiring the benchmark to treat every language model "
                "table as a separate subtask."
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
        "task_id": CHARDET_TASK_ID,
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
                "Explicitly assess whether detector/prober splits are natural "
                "AsyncCodeBench dependencies rather than a forced split of "
                "encoding-model reconstruction."
            ),
        ),
    }
    return (
        AnnotationForm(**common, annotator_id="annotator_a"),
        AnnotationForm(**common, annotator_id="annotator_b"),
    )


def build_adjudication_form() -> AdjudicationForm:
    return AdjudicationForm(
        task_id=CHARDET_TASK_ID,
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
