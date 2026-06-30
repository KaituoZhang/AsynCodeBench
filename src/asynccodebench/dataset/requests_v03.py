"""Build v0.3 requests task/scenario records from public Commit0 evidence."""

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

REQUESTS_TASK_ID = "commit0:requests"
REQUESTS_STRIPPED_SHA = "0e5a01d0ed71fd20b6a72cafe92b9a917ce93d7b"
REQUESTS_COMPLETE_SHA = "1ae6fc3137a11e11565ed22436aa1e77277ac98c"
REQUESTS_QUALITY_FILE = "manifests/pilot/v0.3/quality/commit0_requests.json"
REQUESTS_TASK_STATEMENT = """
Restore the public Requests behavior exercised by the scoped public Commit0
tests without modifying the tests.

The request-preparation core must implement case-insensitive and lookup
structures, status-code lookup, URL/proxy/header/body-length utilities, hooks,
cookies, authentication, Request, PreparedRequest, and Response behavior. The
session and transport layer must implement public API helpers, Session
preparation/sending/redirect/environment merge behavior, adapter selection,
connection/proxy/TLS handling, and response construction.

The v0.3 local evaluator uses a public local-core subset that excludes
httpbin-dependent integration tests and the pyOpenSSL help test because the
audited environment lacks pytest-httpbin and has a pyOpenSSL/OpenSSL mismatch.
The initial benchmark source is the stripped Commit0-style ref
`origin/commit0_combined`, with checksum-recorded bootstrap overlays that only
make the public source importable.
""".strip()


def _load_candidate(candidate_file: Path) -> dict[str, Any]:
    inventory = json.loads(candidate_file.read_text(encoding="utf-8"))
    records = inventory.get("records") or inventory.get("candidates") or []
    matches = [
        candidate
        for candidate in records
        if candidate["task_id"] == REQUESTS_TASK_ID
    ]
    if len(matches) != 1:
        raise ValueError("expected exactly one commit0:requests candidate")
    return matches[0]


def dependency_annotations() -> tuple[DependencyAnnotation, ...]:
    return (
        DependencyAnnotation(
            producer_subproblem="request_preparation_core",
            consumer_subproblem="session_transport_layer",
            dependency_type="api_contract",
            description=(
                "Session and adapter request flow consumes PreparedRequest, "
                "Response, cookie, hook, authentication, proxy, URL, and body "
                "length contracts from the preparation core."
            ),
            evidence_paths=(
                "src/requests/models.py",
                "src/requests/cookies.py",
                "src/requests/hooks.py",
                "src/requests/auth.py",
                "src/requests/utils.py",
                "src/requests/sessions.py",
                "src/requests/adapters.py",
                "tests/test_utils.py",
                "tests/test_hooks.py",
                "tests/test_adapters.py",
            ),
        ),
        DependencyAnnotation(
            producer_subproblem="request_preparation_core",
            consumer_subproblem="integration_validation",
            dependency_type="integration",
            description=(
                "Package-level import and vendored dependency compatibility "
                "consume foundation structures, status codes, utility helpers, "
                "and public module exports."
            ),
            evidence_paths=(
                "src/requests/__init__.py",
                "src/requests/status_codes.py",
                "src/requests/structures.py",
                "src/requests/utils.py",
                "tests/test_packages.py",
                "tests/test_structures.py",
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
        "tests/test_structures.py",
        "tests/test_utils.py",
        "tests/test_hooks.py",
        "tests/test_adapters.py",
        "tests/test_packages.py",
    )


def build_task_record(candidate_file: Path) -> TaskRecord:
    _load_candidate(candidate_file)
    return TaskRecord(
        task_id=REQUESTS_TASK_ID,
        task_source="Commit0",
        upstream_version=REQUESTS_STRIPPED_SHA,
        repository="commit0/requests",
        source_materialization=(
            "git archive of the stripped Commit0-style Requests ref "
            f"origin/commit0_combined at {REQUESTS_STRIPPED_SHA}, plus the "
            "checksum-recorded import/bootstrap overlays in "
            "configs/tasks/commit0_curated_tasks.v0.3.json"
        ),
        problem_statement=REQUESTS_TASK_STATEMENT,
        evaluator_command=_evaluator_command(),
        test_targets=(
            "tests/test_structures.py",
            "tests/test_utils.py",
            "tests/test_hooks.py",
            "tests/test_adapters.py",
            "tests/test_packages.py",
        ),
        publicly_implicated_modules=(
            "src/requests/__init__.py",
            "src/requests/adapters.py",
            "src/requests/api.py",
            "src/requests/auth.py",
            "src/requests/compat.py",
            "src/requests/cookies.py",
            "src/requests/hooks.py",
            "src/requests/models.py",
            "src/requests/sessions.py",
            "src/requests/status_codes.py",
            "src/requests/structures.py",
            "src/requests/utils.py",
        ),
        natural_subproblems={
            "request_preparation_core": (
                "src/requests/_internal_utils.py",
                "src/requests/auth.py",
                "src/requests/compat.py",
                "src/requests/cookies.py",
                "src/requests/hooks.py",
                "src/requests/models.py",
                "src/requests/status_codes.py",
                "src/requests/structures.py",
                "src/requests/utils.py",
                "tests/test_structures.py",
                "tests/test_utils.py",
                "tests/test_hooks.py",
            ),
            "session_transport_layer": (
                "src/requests/api.py",
                "src/requests/sessions.py",
                "src/requests/adapters.py",
                "tests/test_adapters.py",
            ),
            "integration_validation": (
                "src/requests/__init__.py",
                "tests/test_packages.py",
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
        quality_evidence_file=REQUESTS_QUALITY_FILE,
        notes=(
            "Task source and tests are unchanged; only bootstrap overlays are applied.",
            (
                "The local commit0/default branch is complete. Benchmark "
                "workspaces must be materialized from origin/commit0_combined."
            ),
            (
                "The evaluator is a local-core subset because this environment "
                "cannot run httpbin and pyOpenSSL help tests reliably."
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
    prep_paths = (
        "src/requests/_internal_utils.py",
        "src/requests/auth.py",
        "src/requests/compat.py",
        "src/requests/cookies.py",
        "src/requests/hooks.py",
        "src/requests/models.py",
        "src/requests/status_codes.py",
        "src/requests/structures.py",
        "src/requests/utils.py",
    )
    transport_paths = (
        "src/requests/api.py",
        "src/requests/sessions.py",
        "src/requests/adapters.py",
    )
    integration_paths = ("src/requests/__init__.py",)
    if execution_mode is ExecutionMode.ITERATIVE_SINGLE:
        return (
            AgentAssignment(
                agent_id="integrator",
                role="iterative full-task coding agent",
                subproblem_id="full_task",
                writable_paths=prep_paths + transport_paths + integration_paths,
                primary_test_targets=_evaluator_command()[6:],
            ),
        )
    return (
        AgentAssignment(
            agent_id="prep_agent",
            role="request preparation, utilities, hooks, cookies, auth, and response specialist",
            subproblem_id="request_preparation_core",
            writable_paths=prep_paths,
            primary_test_targets=(
                "tests/test_structures.py",
                "tests/test_utils.py",
                "tests/test_hooks.py",
            ),
        ),
        AgentAssignment(
            agent_id="transport_agent",
            role="session, public API, adapter, proxy, TLS, and response transport specialist",
            subproblem_id="session_transport_layer",
            writable_paths=transport_paths,
            primary_test_targets=("tests/test_adapters.py",),
        ),
        AgentAssignment(
            agent_id="integration_agent",
            role="package import and public export compatibility specialist",
            subproblem_id="integration_validation",
            writable_paths=integration_paths,
            primary_test_targets=("tests/test_packages.py",),
        ),
    )


def build_scenarios() -> tuple[ScenarioRecord, ...]:
    shared = {
        "task_id": REQUESTS_TASK_ID,
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
            scenario_id="commit0-requests.iterative-single.v0.3",
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
            scenario_id="commit0-requests.serial-specialists.v0.3",
            execution_mode=ExecutionMode.SERIAL_SPECIALISTS,
            agent_count=3,
            assignments=_assignments(ExecutionMode.SERIAL_SPECIALISTS),
            information_profile="private-workspace",
            concurrent_execution=False,
            communication_condition="completed_artifact_handoff",
            message_delivery_policy=(
                "Specialists run with barrier synchronization. Transport and "
                "integration workers receive completed preparation artifacts "
                "and targeted test results before dependent validation."
            ),
            integration_policy=(
                "Apply request-preparation artifacts before transport and "
                "package validation artifacts, then run the local-core evaluator."
            ),
        ),
        ScenarioRecord(
            **shared,
            scenario_id="commit0-requests.async-private.v0.3",
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
            scenario_id="commit0-requests.async-message.v0.3",
            execution_mode=ExecutionMode.ASYNC_MESSAGE,
            agent_count=3,
            assignments=_assignments(ExecutionMode.ASYNC_MESSAGE),
            information_profile="private-workspace",
            concurrent_execution=True,
            communication_condition="structured_message_and_artifact",
            message_delivery_policy=(
                "Workers may transfer prepared-request, cookie, hook, proxy, "
                "adapter, and package-export assumptions while active."
            ),
            integration_policy=(
                "Integrate latest explicitly transferred artifacts and record "
                "stale request-preparation or transport assumptions."
            ),
        ),
    )


def build_quality_record() -> TaskQualityRecord:
    evaluator = _evaluator_command()
    environment = {
        "pytest": "9.0.3",
        "urllib3": "1.26.5",
    }
    return TaskQualityRecord(
        task_id=REQUESTS_TASK_ID,
        quality_status=DatasetQualityStatus.QUALIFICATION_READY,
        coordination_structure_tags=(
            CoordinationStructureTag.INTERFACE_DEPENDENCY,
            CoordinationStructureTag.SHARED_ABSTRACTION,
        ),
        structure_rationale=(
            "Requests exposes a natural producer/consumer split: sessions and "
            "adapters consume prepared request, response, hook, cookie, auth, "
            "URL, proxy, and body-length contracts from the preparation core. "
            "Asynchronous workers can make stale assumptions about those "
            "interfaces that only fail once transport and package tests are integrated."
        ),
        public_statement_sources=(
            "README.md@origin/commit0_combined",
            "src/requests/*.py docstrings@origin/commit0_combined",
            "tests/test_*.py@origin/commit0_combined",
            "manifests/candidates/commit0_async_screening_v0.3.json",
        ),
        environment_requirements=(
            "Python 3.10.12",
            "pytest==9.0.3",
            "urllib3==1.26.5",
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD=1",
            "Run from the repository root with PYTHONPATH=src.",
            (
                "Use the stripped source ref origin/commit0_combined plus "
                "bootstrap overlays from configs/tasks/commit0_curated_tasks.v0.3.json."
            ),
        ),
        test_groups=(
            TaskTestGroup(
                group_id="request_preparation_core_local",
                purpose=TestGroupPurpose.SPECIALIST_LOCAL,
                owner_subproblem="request_preparation_core",
                command=(
                    "python",
                    "-m",
                    "pytest",
                    "-q",
                    "-o",
                    "addopts=",
                    "tests/test_structures.py",
                    "tests/test_utils.py",
                    "tests/test_hooks.py",
                ),
                description=(
                    "Foundation structures, URL/proxy/header/body utilities, "
                    "hooks, cookies, auth, requests, prepared requests, and responses."
                ),
            ),
            TaskTestGroup(
                group_id="session_transport_layer_local",
                purpose=TestGroupPurpose.SPECIALIST_LOCAL,
                owner_subproblem="session_transport_layer",
                command=(
                    "python",
                    "-m",
                    "pytest",
                    "-q",
                    "-o",
                    "addopts=",
                    "tests/test_adapters.py",
                ),
                description="Adapter request URL, proxy, TLS, pool, send, and response behavior.",
            ),
            TaskTestGroup(
                group_id="package_import_local",
                purpose=TestGroupPurpose.SPECIALIST_LOCAL,
                owner_subproblem="integration_validation",
                command=(
                    "python",
                    "-m",
                    "pytest",
                    "-q",
                    "-o",
                    "addopts=",
                    "tests/test_packages.py",
                ),
                description="Package import and vendored dependency compatibility checks.",
            ),
            TaskTestGroup(
                group_id="prep_transport_cross_contract",
                purpose=TestGroupPurpose.CROSS_SUBPROBLEM,
                command=(
                    "python",
                    "-m",
                    "pytest",
                    "-q",
                    "-o",
                    "addopts=",
                    "tests/test_hooks.py::test_default_hooks",
                    "tests/test_utils.py::test_select_proxies",
                    "tests/test_utils.py::test_get_auth_from_url",
                    "tests/test_adapters.py::test_request_url_trims_leading_path_separators",
                ),
                description=(
                    "Transport behavior after hook, auth, proxy, and URL "
                    "preparation contracts are integrated."
                ),
                prerequisites=(
                    "request_preparation_core artifact is integrated",
                    "session_transport_layer artifact is integrated",
                ),
            ),
            TaskTestGroup(
                group_id="full_evaluator",
                purpose=TestGroupPurpose.FULL_EVALUATOR,
                command=evaluator,
                description=(
                    "Public local-core subset excluding httpbin integration "
                    "tests and the pyOpenSSL help test for environment reasons."
                ),
            ),
        ),
        evaluation_snapshots=(
            EvaluationSnapshot(
                snapshot_id="curated_commit0_initial_local_core",
                source_ref=f"origin/commit0_combined:{REQUESTS_STRIPPED_SHA}+bootstrap-overlays",
                evidence_scope="public_initial_state",
                command=evaluator,
                python_version="3.10.12",
                dependency_versions=environment,
                collected=243,
                passed=55,
                failed=175,
                errors=0,
                skipped=13,
                return_code=1,
                duration_seconds=3.36,
                notes=(
                    (
                        "Verified with PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 and "
                        "PYTHONPATH=src after applying only checksum-recorded "
                        "bootstrap overlays."
                    ),
                    (
                        "Failures are caused by unfinished structures, utilities, "
                        "hooks, request preparation, response, adapter, and package behavior."
                    ),
                ),
            ),
            EvaluationSnapshot(
                snapshot_id="complete_commit0_local_core_sanity",
                source_ref=f"commit0:{REQUESTS_COMPLETE_SHA}",
                evidence_scope="evaluator_sanity_only",
                command=evaluator,
                python_version="3.10.12",
                dependency_versions=environment,
                collected=243,
                passed=230,
                failed=0,
                errors=0,
                skipped=13,
                return_code=0,
                duration_seconds=0.36,
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
                "Full Requests tests are not used as the v0.3 evaluator in this "
                "environment because pytest-httpbin is unavailable and tests/test_help.py "
                "hits a pyOpenSSL/OpenSSL X509_V_FLAG_NOTIFY_POLICY mismatch."
            ),
            (
                "Bootstrap overlays supply only import/collection prerequisites; "
                "they do not implement Requests behavior."
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
        "task_id": REQUESTS_TASK_ID,
        "metric_annotation_id": "commit0-requests.async-metrics.v0.3",
        "source_task_record": "manifests/pilot/v0.3/tasks/commit0_requests.json",
        "source_quality_record": "manifests/pilot/v0.3/quality/commit0_requests.json",
        "purpose": (
            "Dependency-level labels for measuring whether asynchronous "
            "multi-agent coding resolves Requests' preparation-to-transport contracts promptly."
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
                "dependency_id": "requests.prep_to_transport.prepared_request_contract",
                "dependency_type": "interface_dependency",
                "producer_subproblem": "request_preparation_core",
                "consumer_subproblem": "session_transport_layer",
                "producer_agent": "prep_agent",
                "consumer_agent": "transport_agent",
                "producer_files": [
                    "src/requests/models.py",
                    "src/requests/cookies.py",
                    "src/requests/hooks.py",
                    "src/requests/auth.py",
                    "src/requests/utils.py",
                ],
                "consumer_files": [
                    "src/requests/sessions.py",
                    "src/requests/adapters.py",
                ],
                "contract_summary": (
                    "PreparedRequest, Response, hooks, cookies, auth, and "
                    "body/header utilities must be stable for Session and HTTPAdapter consumers."
                ),
                "stale_failure_mode": (
                    "The transport agent may implement send or adapter behavior "
                    "against stale PreparedRequest, hook, cookie, or body-length assumptions."
                ),
                "upstream_probe_tests": [
                    "tests/test_hooks.py::test_default_hooks",
                    "tests/test_hooks.py::test_hooks",
                    "tests/test_utils.py::test_get_auth_from_url",
                ],
                "downstream_probe_tests": [
                    "tests/test_adapters.py::test_request_url_trims_leading_path_separators",
                ],
                "integrated_probe_tests": [
                    "tests/test_hooks.py::test_default_hooks",
                    "tests/test_utils.py::test_get_auth_from_url",
                    "tests/test_adapters.py::test_request_url_trims_leading_path_separators",
                ],
                "resolution_criteria": (
                    "Resolved when hook/auth preparation probes and adapter "
                    "consumer probes pass in the integrated workspace."
                ),
                "metrics_enabled": ["ADPR", "DRS", "CAIL", "SAD"],
                "primary_paper_probe": True,
            },
            {
                "dependency_id": "requests.utils_to_adapters.proxy_tls_url_contract",
                "dependency_type": "shared_api_contract",
                "producer_subproblem": "request_preparation_core",
                "consumer_subproblem": "session_transport_layer",
                "producer_agent": "prep_agent",
                "consumer_agent": "transport_agent",
                "producer_files": [
                    "src/requests/utils.py",
                    "src/requests/auth.py",
                ],
                "consumer_files": [
                    "src/requests/adapters.py",
                    "src/requests/sessions.py",
                ],
                "contract_summary": (
                    "Proxy selection, URL normalization, auth extraction, and "
                    "TLS path helpers must match adapter and session expectations."
                ),
                "stale_failure_mode": (
                    "The transport agent may encode proxies or request URLs "
                    "around outdated utility contracts, with failures surfacing only in adapter tests."
                ),
                "upstream_probe_tests": [
                    "tests/test_utils.py::test_select_proxies",
                    "tests/test_utils.py::test_prepend_scheme_if_needed",
                    "tests/test_utils.py::test_urldefragauth",
                ],
                "downstream_probe_tests": [
                    "tests/test_adapters.py::test_request_url_trims_leading_path_separators",
                ],
                "integrated_probe_tests": [
                    "tests/test_utils.py::test_select_proxies",
                    "tests/test_utils.py::test_prepend_scheme_if_needed",
                    "tests/test_adapters.py::test_request_url_trims_leading_path_separators",
                ],
                "resolution_criteria": (
                    "Resolved when URL/proxy utility probes and adapter URL "
                    "consumer probes pass after integration."
                ),
                "metrics_enabled": ["ADPR", "DRS", "CAIL", "SAD"],
            },
            {
                "dependency_id": "requests.foundation_to_public_api.package_contract",
                "dependency_type": "interface_dependency",
                "producer_subproblem": "request_preparation_core",
                "consumer_subproblem": "integration_validation",
                "producer_agent": "prep_agent",
                "consumer_agent": "integration_agent",
                "producer_files": [
                    "src/requests/status_codes.py",
                    "src/requests/structures.py",
                    "src/requests/utils.py",
                ],
                "consumer_files": ["src/requests/__init__.py"],
                "contract_summary": (
                    "Foundation structures, status codes, utilities, and "
                    "compatibility exports must support package import and vendored dependency checks."
                ),
                "stale_failure_mode": (
                    "The integration agent may preserve package exports around "
                    "stale foundation assumptions, causing import/package tests to fail late."
                ),
                "upstream_probe_tests": [
                    "tests/test_utils.py::test_to_native_string",
                    "tests/test_utils.py::test_unicode_is_ascii",
                ],
                "downstream_probe_tests": [
                    "tests/test_packages.py::test_can_access_urllib3_attribute",
                    "tests/test_packages.py::test_can_access_idna_attribute",
                    "tests/test_packages.py::test_can_access_chardet_attribute",
                ],
                "integrated_probe_tests": [
                    "tests/test_utils.py::test_to_native_string",
                    "tests/test_packages.py::test_can_access_urllib3_attribute",
                    "tests/test_packages.py::test_can_access_idna_attribute",
                ],
                "resolution_criteria": (
                    "Resolved when foundation utility probes and package "
                    "compatibility probes pass in the integrated workspace."
                ),
                "metrics_enabled": ["ADPR", "DRS", "CAIL", "SAD"],
            },
        ],
        "aggregate_metrics": {
            "dependency_point_count": 3,
            "primary_async_dependency_ids": [
                "requests.prep_to_transport.prepared_request_contract",
                "requests.utils_to_adapters.proxy_tls_url_contract",
            ],
            "primary_paper_dependency_id": (
                "requests.prep_to_transport.prepared_request_contract"
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
                "The prep_to_transport dependency is the primary signal because "
                "Sessions and HTTPAdapter rely on prepared request, hook, cookie, "
                "auth, response, and utility contracts."
            ),
            (
                "The proxy_tls_url dependency captures Requests-specific async "
                "risk around URL/proxy/TLS helper behavior consumed by adapters."
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
        "task_id": REQUESTS_TASK_ID,
        "candidate_evidence_file": str(candidate_file),
        "task_record_file": str(task_record_file),
        "allowed_labels": tuple(ParallelizabilityLabel),
        "independence_instructions": (
            "Use only public Commit0 evidence and the draft task record.",
            (
                "Review the linked TaskQualityRecord, including the requirement "
                "to use origin/commit0_combined plus checksum-recorded bootstrap overlays."
            ),
            "Do not inspect reference branches, solution patches, or diffs.",
            "Do not consult the other annotator before submitting.",
            (
                "Explicitly assess whether the preparation->transport split is "
                "a natural AsyncCodeBench dependency rather than artificial file partitioning."
            ),
        ),
    }
    return (
        AnnotationForm(**common, annotator_id="annotator_a"),
        AnnotationForm(**common, annotator_id="annotator_b"),
    )


def build_adjudication_form() -> AdjudicationForm:
    return AdjudicationForm(
        task_id=REQUESTS_TASK_ID,
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
