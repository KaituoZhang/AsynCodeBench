"""Build v0.3 parsel task/scenario records from public Commit0 evidence."""

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

PARSEL_TASK_ID = "commit0:parsel"
PARSEL_STRIPPED_SHA = "7e73d60665ef2e3ddfe3c1bb01eed981cd317c6f"
PARSEL_COMPLETE_SHA = "740734252efd246679e5c6ee4028a47d5851712d"
PARSEL_QUALITY_FILE = "manifests/pilot/v0.3/quality/commit0_parsel.json"
PARSEL_TASK_STATEMENT = """
Restore the public Parsel selector behavior exercised by the scoped Commit0
tests without modifying the tests.

The utility and XPath support layer must implement flattening, regex
extraction, shortening, XPath function registration, and has-class semantics.
The CSS translation layer must implement pseudo-element handling for ::text
and ::attr(), unknown pseudo-element errors, and cached CSS-to-XPath
translation. The selector query core must consume those contracts to implement
HTML/XML/JSON root creation, Selector and SelectorList query chaining, XPath,
CSS, JMESPath, regex extraction, serialization, namespace handling, node
removal/drop behavior, XML attack protections, and package imports.

The initial benchmark source is the stripped Commit0-style ref
`origin/commit0_combined`, plus a checksum-recorded bootstrap overlay that only
exposes the setup() import hook required by parsel.__init__.
""".strip()


def _load_candidate(candidate_file: Path) -> dict[str, Any]:
    inventory = json.loads(candidate_file.read_text(encoding="utf-8"))
    records = inventory.get("records") or inventory.get("candidates") or []
    matches = [
        candidate
        for candidate in records
        if candidate["task_id"] == PARSEL_TASK_ID
    ]
    if len(matches) != 1:
        raise ValueError("expected exactly one commit0:parsel candidate")
    return matches[0]


def dependency_annotations() -> tuple[DependencyAnnotation, ...]:
    return (
        DependencyAnnotation(
            producer_subproblem="utility_xpath_support",
            consumer_subproblem="selector_query_core",
            dependency_type="api_contract",
            description=(
                "Selector and SelectorList behavior consumes utility flattening, "
                "regex extraction, shortening, XPath extension registration, "
                "and has-class semantics."
            ),
            evidence_paths=(
                "parsel/utils.py",
                "parsel/xpathfuncs.py",
                "parsel/selector.py",
                "tests/test_utils.py",
                "tests/test_xpathfuncs.py",
                "tests/test_selector.py",
            ),
        ),
        DependencyAnnotation(
            producer_subproblem="css_translation_layer",
            consumer_subproblem="selector_query_core",
            dependency_type="api_contract",
            description=(
                "Selector.css() consumes the CSS translator contract for "
                "::text, ::attr(), pseudo-element errors, and CSS-to-XPath "
                "translation before executing XPath queries."
            ),
            evidence_paths=(
                "parsel/csstranslator.py",
                "parsel/selector.py",
                "tests/test_selector_csstranslator.py",
                "tests/test_selector.py",
            ),
        ),
    )


def _evaluator_command() -> tuple[str, ...]:
    return (
        "python",
        "-m",
        "pytest",
        "-q",
        "-o",
        "addopts=",
        "tests/test_selector.py",
        "tests/test_selector_csstranslator.py",
        "tests/test_selector_jmespath.py",
        "tests/test_utils.py",
        "tests/test_xml_attacks.py",
        "tests/test_xpathfuncs.py",
    )


def build_task_record(candidate_file: Path) -> TaskRecord:
    _load_candidate(candidate_file)
    return TaskRecord(
        task_id=PARSEL_TASK_ID,
        task_source="Commit0",
        upstream_version=PARSEL_STRIPPED_SHA,
        repository="commit0/parsel",
        source_materialization=(
            "git archive of the stripped Commit0-style Parsel ref "
            f"origin/commit0_combined at {PARSEL_STRIPPED_SHA}, plus the "
            "checksum-recorded setup bootstrap overlay in "
            "configs/tasks/commit0_curated_tasks.v0.3.json"
        ),
        problem_statement=PARSEL_TASK_STATEMENT,
        evaluator_command=_evaluator_command(),
        test_targets=(
            "tests/test_selector.py",
            "tests/test_selector_csstranslator.py",
            "tests/test_selector_jmespath.py",
            "tests/test_utils.py",
            "tests/test_xml_attacks.py",
            "tests/test_xpathfuncs.py",
        ),
        publicly_implicated_modules=(
            "parsel/__init__.py",
            "parsel/csstranslator.py",
            "parsel/selector.py",
            "parsel/utils.py",
            "parsel/xpathfuncs.py",
        ),
        natural_subproblems={
            "utility_xpath_support": (
                "parsel/utils.py",
                "parsel/xpathfuncs.py",
                "tests/test_utils.py",
                "tests/test_xpathfuncs.py",
            ),
            "css_translation_layer": (
                "parsel/csstranslator.py",
                "tests/test_selector_csstranslator.py",
            ),
            "selector_query_core": (
                "parsel/__init__.py",
                "parsel/selector.py",
                "tests/test_selector.py",
                "tests/test_selector_jmespath.py",
                "tests/test_xml_attacks.py",
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
        quality_evidence_file=PARSEL_QUALITY_FILE,
        notes=(
            "Task source and tests are unchanged; only the setup bootstrap overlay is applied.",
            (
                "The local commit0/default branch is complete. Benchmark "
                "workspaces must be materialized from origin/commit0_combined."
            ),
            (
                "The screening manifest marked Parsel as manual_review because "
                "raw collection failed before the setup bootstrap was audited."
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
    utility_paths = ("parsel/utils.py", "parsel/xpathfuncs.py")
    css_paths = ("parsel/csstranslator.py",)
    selector_paths = ("parsel/__init__.py", "parsel/selector.py")
    if execution_mode is ExecutionMode.ITERATIVE_SINGLE:
        return (
            AgentAssignment(
                agent_id="integrator",
                role="iterative full-task coding agent",
                subproblem_id="full_task",
                writable_paths=utility_paths + css_paths + selector_paths,
                primary_test_targets=_evaluator_command()[6:],
            ),
        )
    return (
        AgentAssignment(
            agent_id="utility_xpath_agent",
            role="utility flattening, regex extraction, shortening, and XPath function specialist",
            subproblem_id="utility_xpath_support",
            writable_paths=utility_paths,
            primary_test_targets=(
                "tests/test_utils.py",
                "tests/test_xpathfuncs.py",
            ),
        ),
        AgentAssignment(
            agent_id="css_agent",
            role="CSS-to-XPath translator and pseudo-element specialist",
            subproblem_id="css_translation_layer",
            writable_paths=css_paths,
            primary_test_targets=("tests/test_selector_csstranslator.py",),
        ),
        AgentAssignment(
            agent_id="selector_agent",
            role="Selector, SelectorList, root parsing, XPath, CSS, JMESPath, and package integration specialist",
            subproblem_id="selector_query_core",
            writable_paths=selector_paths,
            primary_test_targets=(
                "tests/test_selector.py",
                "tests/test_selector_jmespath.py",
                "tests/test_xml_attacks.py",
            ),
        ),
    )


def build_scenarios() -> tuple[ScenarioRecord, ...]:
    shared = {
        "task_id": PARSEL_TASK_ID,
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
            scenario_id="commit0-parsel.iterative-single.v0.3",
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
            scenario_id="commit0-parsel.serial-specialists.v0.3",
            execution_mode=ExecutionMode.SERIAL_SPECIALISTS,
            agent_count=3,
            assignments=_assignments(ExecutionMode.SERIAL_SPECIALISTS),
            information_profile="private-workspace",
            concurrent_execution=False,
            communication_condition="completed_artifact_handoff",
            message_delivery_policy=(
                "Specialists run with barrier synchronization. Selector "
                "receives completed utility/XPath and CSS translator artifacts "
                "before dependent validation."
            ),
            integration_policy=(
                "Apply utility/XPath and CSS artifacts before selector core, "
                "then run the full scoped evaluator."
            ),
        ),
        ScenarioRecord(
            **shared,
            scenario_id="commit0-parsel.async-private.v0.3",
            execution_mode=ExecutionMode.ASYNC_PRIVATE,
            agent_count=3,
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
            scenario_id="commit0-parsel.async-message.v0.3",
            execution_mode=ExecutionMode.ASYNC_MESSAGE,
            agent_count=3,
            assignments=_assignments(ExecutionMode.ASYNC_MESSAGE),
            information_profile="private-workspace",
            concurrent_execution=True,
            communication_condition="structured_message_and_artifact",
            message_delivery_policy=(
                "Workers may transfer utility, XPath function, CSS translator, "
                "and selector-query assumptions while active."
            ),
            integration_policy=(
                "Integrate latest explicitly transferred artifacts and record "
                "stale selector utility or CSS translation assumptions."
            ),
        ),
    )


def build_quality_record() -> TaskQualityRecord:
    evaluator = _evaluator_command()
    environment = {
        "pytest": "9.0.3",
        "lxml": "6.0.3",
        "cssselect": "1.4.0",
        "jmespath": "1.1.0",
        "w3lib": "2.4.1",
        "packaging": "24.1",
    }
    return TaskQualityRecord(
        task_id=PARSEL_TASK_ID,
        quality_status=DatasetQualityStatus.QUALIFICATION_READY,
        coordination_structure_tags=(
            CoordinationStructureTag.INTERFACE_DEPENDENCY,
            CoordinationStructureTag.SHARED_ABSTRACTION,
        ),
        structure_rationale=(
            "Parsel exposes semantic async dependencies between utility/XPath "
            "support, CSS pseudo-element translation, and the selector query "
            "core. Selector workers can make stale assumptions about flattening, "
            "regex extraction, has-class registration, or CSS-to-XPath output "
            "that only fail once query chaining and selector integration tests run."
        ),
        public_statement_sources=(
            "README.rst@origin/commit0_combined",
            "parsel/*.py docstrings@origin/commit0_combined",
            "tests/test_*.py@origin/commit0_combined",
            "manifests/candidates/commit0_async_screening_v0.3.json",
        ),
        environment_requirements=(
            "Python 3.10.12",
            "pytest==9.0.3",
            "lxml==6.0.3",
            "cssselect==1.4.0",
            "jmespath==1.1.0",
            "w3lib==2.4.1",
            "packaging==24.1",
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD=1",
            "Run from the repository root with PYTHONPATH=.",
            (
                "Use the stripped source ref origin/commit0_combined plus "
                "bootstrap overlays from configs/tasks/commit0_curated_tasks.v0.3.json."
            ),
        ),
        test_groups=(
            TaskTestGroup(
                group_id="utility_xpath_support_local",
                purpose=TestGroupPurpose.SPECIALIST_LOCAL,
                owner_subproblem="utility_xpath_support",
                command=(
                    "python",
                    "-m",
                    "pytest",
                    "-q",
                    "-o",
                    "addopts=",
                    "tests/test_utils.py",
                    "tests/test_xpathfuncs.py",
                ),
                description=(
                    "Flattening, regex extraction, shortening, XPath function "
                    "registration, and has-class semantics."
                ),
            ),
            TaskTestGroup(
                group_id="css_translation_layer_local",
                purpose=TestGroupPurpose.SPECIALIST_LOCAL,
                owner_subproblem="css_translation_layer",
                command=(
                    "python",
                    "-m",
                    "pytest",
                    "-q",
                    "-o",
                    "addopts=",
                    "tests/test_selector_csstranslator.py",
                ),
                description="CSS-to-XPath translation and pseudo-element behavior.",
            ),
            TaskTestGroup(
                group_id="selector_query_core_local",
                purpose=TestGroupPurpose.SPECIALIST_LOCAL,
                owner_subproblem="selector_query_core",
                command=(
                    "python",
                    "-m",
                    "pytest",
                    "-q",
                    "-o",
                    "addopts=",
                    "tests/test_selector.py",
                    "tests/test_selector_jmespath.py",
                    "tests/test_xml_attacks.py",
                ),
                description=(
                    "Selector/SelectorList root parsing, XPath, CSS, JMESPath, "
                    "serialization, namespaces, node removal, and XML protections."
                ),
            ),
            TaskTestGroup(
                group_id="css_selector_cross_contract",
                purpose=TestGroupPurpose.CROSS_SUBPROBLEM,
                command=(
                    "python",
                    "-m",
                    "pytest",
                    "-q",
                    "-o",
                    "addopts=",
                    "tests/test_selector_csstranslator.py::HTMLTranslatorTest::test_text_pseudo_element",
                    "tests/test_selector_csstranslator.py::GenericTranslatorTest::test_text_pseudo_element",
                    "tests/test_selector_csstranslator.py::CSSSelectorTest::test_pseudoclass_has",
                    "tests/test_selector.py::SelectorTestCase::test_select_on_text_nodes",
                ),
                description=(
                    "Selector.css behavior after CSS pseudo-element translation "
                    "and selector query execution are integrated."
                ),
                prerequisites=(
                    "css_translation_layer artifact is integrated",
                    "selector_query_core artifact is integrated",
                ),
            ),
            TaskTestGroup(
                group_id="utility_selector_cross_contract",
                purpose=TestGroupPurpose.CROSS_SUBPROBLEM,
                command=(
                    "python",
                    "-m",
                    "pytest",
                    "-q",
                    "-o",
                    "addopts=",
                    "tests/test_utils.py::test_extract_regex",
                    "tests/test_xpathfuncs.py::XPathFuncsTestCase::test_has_class_simple",
                    "tests/test_selector.py::ExsltTestCase::test_regexp",
                ),
                description=(
                    "Selector regex and XPath extension behavior after utility "
                    "and XPath support are integrated."
                ),
                prerequisites=(
                    "utility_xpath_support artifact is integrated",
                    "selector_query_core artifact is integrated",
                ),
            ),
            TaskTestGroup(
                group_id="full_evaluator",
                purpose=TestGroupPurpose.FULL_EVALUATOR,
                command=evaluator,
                description=(
                    "Scoped public Parsel test suite excluding typing-only checks."
                ),
            ),
        ),
        evaluation_snapshots=(
            EvaluationSnapshot(
                snapshot_id="curated_commit0_initial_evaluator",
                source_ref=f"origin/commit0_combined:{PARSEL_STRIPPED_SHA}+setup-bootstrap-overlay",
                evidence_scope="public_initial_state",
                command=evaluator,
                python_version="3.10.12",
                dependency_versions=environment,
                collected=208,
                passed=13,
                failed=193,
                errors=0,
                skipped=2,
                return_code=1,
                duration_seconds=5.19,
                notes=(
                    (
                        "Verified with PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 and "
                        "PYTHONPATH=. after applying only the checksum-recorded "
                        "setup bootstrap overlay."
                    ),
                    (
                        "Failures are caused by unfinished utility, XPath "
                        "function, CSS translation, selector, JMESPath, and XML "
                        "protection behavior."
                    ),
                ),
            ),
            EvaluationSnapshot(
                snapshot_id="complete_commit0_evaluator_sanity",
                source_ref=f"commit0:{PARSEL_COMPLETE_SHA}",
                evidence_scope="evaluator_sanity_only",
                command=evaluator,
                python_version="3.10.12",
                dependency_versions=environment,
                collected=208,
                passed=206,
                failed=0,
                errors=0,
                skipped=2,
                return_code=0,
                duration_seconds=0.33,
                notes=(
                    (
                        "The complete/default local commit0 ref passes the "
                        "same scoped evaluator in the same environment."
                    ),
                    (
                        "The complete ref is evaluator validation only and "
                        "must not define decomposition, prompts, or agent-visible evidence."
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
                "Raw origin/commit0_combined collection fails before the setup "
                "bootstrap because parsel.__init__ calls xpathfuncs.setup()."
            ),
            (
                "The bootstrap overlay supplies only the setup import hook; it "
                "does not implement selector, CSS translator, utility, or XPath behavior."
            ),
            (
                "Typing-only checks under tests/typing are not part of this "
                "behavioral v0.3 evaluator."
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
        "task_id": PARSEL_TASK_ID,
        "metric_annotation_id": "commit0-parsel.async-metrics.v0.3",
        "source_task_record": "manifests/pilot/v0.3/tasks/commit0_parsel.json",
        "source_quality_record": "manifests/pilot/v0.3/quality/commit0_parsel.json",
        "purpose": (
            "Dependency-level labels for measuring whether asynchronous "
            "multi-agent coding resolves Parsel's utility/CSS-to-selector contracts promptly."
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
                "dependency_id": "parsel.css_to_selector.pseudo_element_contract",
                "dependency_type": "interface_dependency",
                "producer_subproblem": "css_translation_layer",
                "consumer_subproblem": "selector_query_core",
                "producer_agent": "css_agent",
                "consumer_agent": "selector_agent",
                "producer_files": ["parsel/csstranslator.py"],
                "consumer_files": ["parsel/selector.py"],
                "contract_summary": (
                    "CSS translator output for ::text, ::attr(), unknown "
                    "pseudo-elements, and css2xpath must be consumed correctly by Selector.css()."
                ),
                "stale_failure_mode": (
                    "The selector agent may implement CSS query execution "
                    "against stale pseudo-element output assumptions, causing "
                    "late failures in selector CSS tests."
                ),
                "upstream_probe_tests": [
                    "tests/test_selector_csstranslator.py::HTMLTranslatorTest::test_text_pseudo_element",
                    "tests/test_selector_csstranslator.py::GenericTranslatorTest::test_text_pseudo_element",
                    "tests/test_selector_csstranslator.py::HTMLTranslatorTest::test_attr_function",
                    "tests/test_selector_csstranslator.py::GenericTranslatorTest::test_attr_function",
                    "tests/test_selector_csstranslator.py::UtilCss2XPathTest::test_css2xpath",
                ],
                "downstream_probe_tests": [
                    "tests/test_selector_csstranslator.py::CSSSelectorTest::test_text_pseudo_element",
                    "tests/test_selector.py::SelectorTestCase::test_select_on_text_nodes",
                ],
                "integrated_probe_tests": [
                    "tests/test_selector_csstranslator.py::HTMLTranslatorTest::test_text_pseudo_element",
                    "tests/test_selector_csstranslator.py::GenericTranslatorTest::test_text_pseudo_element",
                    "tests/test_selector_csstranslator.py::CSSSelectorTest::test_text_pseudo_element",
                    "tests/test_selector.py::SelectorTestCase::test_select_on_text_nodes",
                ],
                "resolution_criteria": (
                    "Resolved when translator pseudo-element probes and "
                    "Selector.css consumer probes pass in the integrated workspace."
                ),
                "metrics_enabled": ["ADPR", "DRS", "CAIL", "SAD"],
                "primary_paper_probe": True,
            },
            {
                "dependency_id": "parsel.xpath_utils_to_selector.regex_has_class_contract",
                "dependency_type": "shared_api_contract",
                "producer_subproblem": "utility_xpath_support",
                "consumer_subproblem": "selector_query_core",
                "producer_agent": "utility_xpath_agent",
                "consumer_agent": "selector_agent",
                "producer_files": ["parsel/utils.py", "parsel/xpathfuncs.py"],
                "consumer_files": ["parsel/selector.py", "parsel/__init__.py"],
                "contract_summary": (
                    "Utility flatten/extract_regex/shorten behavior and XPath "
                    "has-class registration must support selector regex extraction, repr, and XPath queries."
                ),
                "stale_failure_mode": (
                    "The selector agent may implement query chaining or regex "
                    "extraction around stale utility or XPath-function contracts, "
                    "with failures surfacing only after integration."
                ),
                "upstream_probe_tests": [
                    "tests/test_utils.py::test_extract_regex",
                    "tests/test_utils.py::test_shorten",
                    "tests/test_xpathfuncs.py::XPathFuncsTestCase::test_has_class_simple",
                ],
                "downstream_probe_tests": [
                    "tests/test_selector.py::ExsltTestCase::test_regexp",
                    "tests/test_selector_csstranslator.py::CSSSelectorTest::test_pseudoclass_has",
                ],
                "integrated_probe_tests": [
                    "tests/test_utils.py::test_extract_regex",
                    "tests/test_xpathfuncs.py::XPathFuncsTestCase::test_has_class_simple",
                    "tests/test_selector.py::ExsltTestCase::test_regexp",
                    "tests/test_selector_csstranslator.py::CSSSelectorTest::test_pseudoclass_has",
                ],
                "resolution_criteria": (
                    "Resolved when utility/XPath probes and selector regex/"
                    "has-class consumer probes pass after integration."
                ),
                "metrics_enabled": ["ADPR", "DRS", "CAIL", "SAD"],
            },
        ],
        "aggregate_metrics": {
            "dependency_point_count": 2,
            "primary_async_dependency_ids": [
                "parsel.css_to_selector.pseudo_element_contract",
                "parsel.xpath_utils_to_selector.regex_has_class_contract",
            ],
            "primary_paper_dependency_id": (
                "parsel.css_to_selector.pseudo_element_contract"
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
                "The CSS-to-selector dependency is the primary signal because "
                "Selector.css can be implemented against stale translator "
                "pseudo-element semantics even when patches merge cleanly."
            ),
            (
                "The utility/XPath dependency captures stale assumptions around "
                "shared flattening, regex extraction, repr shortening, and has-class registration."
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
        "task_id": PARSEL_TASK_ID.replace("commit0:", "asyncodebench:", 1),
        "source_task_id": PARSEL_TASK_ID,
        "candidate_evidence_file": str(candidate_file),
        "task_record_file": str(task_record_file),
        "allowed_labels": tuple(ParallelizabilityLabel),
        "independence_instructions": (
            "Use only public Commit0 evidence and the draft task record.",
            (
                "Review the linked TaskQualityRecord, including the requirement "
                "to use origin/commit0_combined plus the checksum-recorded setup bootstrap overlay."
            ),
            "Do not inspect reference branches, solution patches, or diffs.",
            "Do not consult the other annotator before submitting.",
            (
                "Explicitly assess whether the utility/CSS->selector splits "
                "are natural AsynCodeBench dependencies rather than artificial file partitioning."
            ),
        ),
    }
    return (
        AnnotationForm(**common, annotator_id="annotator_a"),
        AnnotationForm(**common, annotator_id="annotator_b"),
    )


def build_adjudication_form() -> AdjudicationForm:
    return AdjudicationForm(
        task_id=PARSEL_TASK_ID.replace("commit0:", "asyncodebench:", 1),
        source_task_id=PARSEL_TASK_ID,
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
