"""Build v0.3 filesystem_spec task/scenario records from Commit0 evidence."""

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

FILESYSTEM_SPEC_TASK_ID = "commit0:filesystem_spec"
FILESYSTEM_SPEC_STRIPPED_SHA = "0d34761eb6ca0af8a6f33eb83dd9630a4a370da0"
FILESYSTEM_SPEC_COMPLETE_SHA = "b842cf4cc7e4e22caa3110157cec9b4959582993"
FILESYSTEM_SPEC_QUALITY_FILE = (
    "manifests/pilot/v0.3/quality/commit0_filesystem_spec.json"
)
FILESYSTEM_SPEC_TASK_STATEMENT = """
Restore the scoped core fsspec behavior exercised by the public Commit0 tests
without modifying the tests.

The registry layer must implement protocol registration, deferred imports,
entry-point loading, and filesystem instantiation. The utility/compression
layer must implement URL/protocol parsing, path helpers, read-block behavior,
compression inference/registration, and logging helpers. The filesystem
backend layer must implement the abstract filesystem operations and the
local, memory, and cache behavior exercised indirectly by the public core
tests. The core open/path layer must consume those contracts to implement
OpenFile/OpenFiles, URL to filesystem resolution, path expansion, compression
selection, local-open handling, and multi-file context behavior.

The v0.3 evaluator intentionally excludes optional implementation backends,
HTTP/Arrow-dependent test_spec import paths, callbacks requiring pytest-mock,
and implementation test conftests. The initial benchmark source is the stripped
Commit0-style ref `origin/commit0_combined`, plus checksum-recorded bootstrap
overlays that only make public core tests importable.
""".strip()


def _load_candidate(candidate_file: Path) -> dict[str, Any]:
    inventory = json.loads(candidate_file.read_text(encoding="utf-8"))
    records = inventory.get("records") or inventory.get("candidates") or []
    matches = [
        candidate
        for candidate in records
        if candidate["task_id"] == FILESYSTEM_SPEC_TASK_ID
    ]
    if len(matches) != 1:
        raise ValueError("expected exactly one commit0:filesystem_spec candidate")
    return matches[0]


def dependency_annotations() -> tuple[DependencyAnnotation, ...]:
    return (
        DependencyAnnotation(
            producer_subproblem="registry_protocol_layer",
            consumer_subproblem="core_open_path_layer",
            dependency_type="api_contract",
            description=(
                "Core URL resolution and open path behavior consume registry "
                "protocol lookup, deferred class imports, and filesystem instantiation."
            ),
            evidence_paths=(
                "fsspec/registry.py",
                "fsspec/core.py",
                "fsspec/tests/test_registry.py",
                "fsspec/tests/test_core.py",
            ),
        ),
        DependencyAnnotation(
            producer_subproblem="utility_compression_layer",
            consumer_subproblem="core_open_path_layer",
            dependency_type="api_contract",
            description=(
                "OpenFile, open_files, path expansion, and local-open behavior "
                "consume utility path/protocol helpers and compression lookup."
            ),
            evidence_paths=(
                "fsspec/utils.py",
                "fsspec/compression.py",
                "fsspec/core.py",
                "fsspec/tests/test_utils.py",
                "fsspec/tests/test_compression.py",
                "fsspec/tests/test_core.py",
            ),
        ),
        DependencyAnnotation(
            producer_subproblem="filesystem_backend_layer",
            consumer_subproblem="core_open_path_layer",
            dependency_type="api_contract",
            description=(
                "OpenFile, open_local, and multi-file context behavior consume "
                "AbstractFileSystem plus the local, memory, and cache backend "
                "contracts reached by the public core tests."
            ),
            evidence_paths=(
                "fsspec/spec.py",
                "fsspec/implementations/local.py",
                "fsspec/implementations/memory.py",
                "fsspec/implementations/cached.py",
                "fsspec/implementations/cache_mapper.py",
                "fsspec/implementations/cache_metadata.py",
                "fsspec/core.py",
                "fsspec/tests/test_core.py",
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
        "fsspec/tests/test_registry.py",
        "fsspec/tests/test_utils.py",
        "fsspec/tests/test_compression.py",
        "fsspec/tests/test_core.py",
    )


def build_task_record(candidate_file: Path) -> TaskRecord:
    _load_candidate(candidate_file)
    return TaskRecord(
        task_id=FILESYSTEM_SPEC_TASK_ID,
        task_source="Commit0",
        upstream_version=FILESYSTEM_SPEC_STRIPPED_SHA,
        repository="commit0/filesystem_spec",
        source_materialization=(
            "git archive of the stripped Commit0-style filesystem_spec ref "
            f"origin/commit0_combined at {FILESYSTEM_SPEC_STRIPPED_SHA}, plus "
            "checksum-recorded import/bootstrap overlays in "
            "configs/tasks/commit0_curated_tasks.v0.3.json"
        ),
        problem_statement=FILESYSTEM_SPEC_TASK_STATEMENT,
        evaluator_command=_evaluator_command(),
        test_targets=(
            "fsspec/tests/test_registry.py",
            "fsspec/tests/test_utils.py",
            "fsspec/tests/test_compression.py",
            "fsspec/tests/test_core.py",
        ),
        publicly_implicated_modules=(
            "fsspec/__init__.py",
            "fsspec/_version.py",
            "fsspec/compression.py",
            "fsspec/core.py",
            "fsspec/registry.py",
            "fsspec/spec.py",
            "fsspec/utils.py",
            "fsspec/implementations/cache_mapper.py",
            "fsspec/implementations/cache_metadata.py",
            "fsspec/implementations/cached.py",
            "fsspec/implementations/local.py",
            "fsspec/implementations/memory.py",
        ),
        natural_subproblems={
            "registry_protocol_layer": (
                "fsspec/registry.py",
                "fsspec/__init__.py",
                "fsspec/tests/test_registry.py",
            ),
            "utility_compression_layer": (
                "fsspec/utils.py",
                "fsspec/compression.py",
                "fsspec/tests/test_utils.py",
                "fsspec/tests/test_compression.py",
            ),
            "core_open_path_layer": (
                "fsspec/core.py",
                "fsspec/tests/test_core.py",
            ),
            "filesystem_backend_layer": (
                "fsspec/spec.py",
                "fsspec/implementations/cache_mapper.py",
                "fsspec/implementations/cache_metadata.py",
                "fsspec/implementations/cached.py",
                "fsspec/implementations/local.py",
                "fsspec/implementations/memory.py",
                "fsspec/tests/test_core.py",
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
        quality_evidence_file=FILESYSTEM_SPEC_QUALITY_FILE,
        notes=(
            "Task source and tests are unchanged; only import/bootstrap overlays are applied.",
            (
                "The local commit0/default branch is complete. Benchmark "
                "workspaces must be materialized from origin/commit0_combined."
            ),
            (
                "The evaluator is scoped to core fsspec tests. It does not run "
                "backend-specific suites, but its public core tests do exercise "
                "the local, memory, and simple-cache support paths."
            ),
            (
                "Manifest revision v0.3.2 closes the writable dependency scope "
                "over the stripped filesystem abstractions and minimal backends "
                "already exercised by the unchanged public evaluator; it adds "
                "no implementation hints or reference code."
            ),
            (
                "The proposed label is a draft curation decision and not a "
                "final independent annotation."
            ),
        ),
    )


def _assignments(execution_mode: ExecutionMode) -> tuple[AgentAssignment, ...]:
    registry_paths = ("fsspec/registry.py", "fsspec/__init__.py")
    utility_paths = ("fsspec/utils.py", "fsspec/compression.py")
    backend_paths = (
        "fsspec/spec.py",
        "fsspec/implementations/cache_mapper.py",
        "fsspec/implementations/cache_metadata.py",
        "fsspec/implementations/cached.py",
        "fsspec/implementations/local.py",
        "fsspec/implementations/memory.py",
    )
    core_paths = ("fsspec/core.py",)
    if execution_mode is ExecutionMode.ITERATIVE_SINGLE:
        return (
            AgentAssignment(
                agent_id="integrator",
                role="iterative full-task coding agent",
                subproblem_id="full_task",
                writable_paths=(
                    registry_paths + utility_paths + backend_paths + core_paths
                ),
                primary_test_targets=_evaluator_command()[6:],
            ),
        )
    return (
        AgentAssignment(
            agent_id="registry_agent",
            role="protocol registry and filesystem lookup specialist",
            subproblem_id="registry_protocol_layer",
            writable_paths=registry_paths,
            primary_test_targets=("fsspec/tests/test_registry.py",),
        ),
        AgentAssignment(
            agent_id="utility_agent",
            role="URL/path utility and compression helper specialist",
            subproblem_id="utility_compression_layer",
            writable_paths=utility_paths,
            primary_test_targets=(
                "fsspec/tests/test_utils.py",
                "fsspec/tests/test_compression.py",
            ),
        ),
        AgentAssignment(
            agent_id="backend_agent",
            role=(
                "AbstractFileSystem plus local, memory, and cache backend "
                "contract specialist"
            ),
            subproblem_id="filesystem_backend_layer",
            writable_paths=backend_paths,
            primary_test_targets=(
                "fsspec/tests/test_core.py::test_openfile_api",
                "fsspec/tests/test_core.py::test_openfile_open",
                "fsspec/tests/test_core.py::test_open_local_w_cache",
                "fsspec/tests/test_core.py::test_open_expand",
                "fsspec/tests/test_core.py::test_automkdir_local",
            ),
        ),
        AgentAssignment(
            agent_id="core_agent",
            role="OpenFile, OpenFiles, path expansion, and URL-to-filesystem specialist",
            subproblem_id="core_open_path_layer",
            writable_paths=core_paths,
            primary_test_targets=("fsspec/tests/test_core.py",),
        ),
    )


def build_scenarios() -> tuple[ScenarioRecord, ...]:
    shared = {
        "task_id": FILESYSTEM_SPEC_TASK_ID,
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
            scenario_id="commit0-filesystem-spec.iterative-single.v0.3",
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
            scenario_id="commit0-filesystem-spec.serial-specialists.v0.3",
            execution_mode=ExecutionMode.SERIAL_SPECIALISTS,
            agent_count=4,
            assignments=_assignments(ExecutionMode.SERIAL_SPECIALISTS),
            information_profile="private-workspace",
            concurrent_execution=False,
            communication_condition="completed_artifact_handoff",
            message_delivery_policy=(
                "Specialists run with barrier synchronization. Core receives "
                "completed registry, utility/compression, and filesystem-backend "
                "artifacts before validation."
            ),
            integration_policy=(
                "Apply registry, utility/compression, and filesystem-backend "
                "artifacts before the core open/path artifact, then run the "
                "scoped evaluator."
            ),
        ),
        ScenarioRecord(
            **shared,
            scenario_id="commit0-filesystem-spec.async-private.v0.3",
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
            scenario_id="commit0-filesystem-spec.async-message.v0.3",
            execution_mode=ExecutionMode.ASYNC_MESSAGE,
            agent_count=4,
            assignments=_assignments(ExecutionMode.ASYNC_MESSAGE),
            information_profile="private-workspace",
            concurrent_execution=True,
            communication_condition="structured_message_and_artifact",
            message_delivery_policy=(
                "Workers may transfer protocol registry, compression, URL "
                "parsing, filesystem-backend, and path expansion assumptions "
                "while active."
            ),
            integration_policy=(
                "Integrate latest explicitly transferred artifacts and record "
                "stale registry, utility, or backend assumptions used by core "
                "open/path behavior."
            ),
        ),
    )


def build_quality_record() -> TaskQualityRecord:
    evaluator = _evaluator_command()
    environment = {"pytest": "9.0.3", "zstandard": "0.25.0"}
    return TaskQualityRecord(
        task_id=FILESYSTEM_SPEC_TASK_ID,
        quality_status=DatasetQualityStatus.QUALIFICATION_READY,
        coordination_structure_tags=(
            CoordinationStructureTag.INTERFACE_DEPENDENCY,
            CoordinationStructureTag.SHARED_ABSTRACTION,
        ),
        structure_rationale=(
            "The scoped fsspec task exposes natural async contracts from the "
            "registry, utility/compression, and filesystem-backend layers into "
            "core OpenFile/OpenFiles, URL-to-filesystem resolution, path expansion, "
            "compression selection, and local/cache behavior."
        ),
        public_statement_sources=(
            "README.md@origin/commit0_combined",
            "fsspec/*.py docstrings@origin/commit0_combined",
            "fsspec/tests/test_*.py@origin/commit0_combined",
            "manifests/candidates/commit0_async_screening_v0.3.json",
        ),
        environment_requirements=(
            "Python 3.10.12",
            "pytest==9.0.3",
            "zstandard==0.25.0",
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD=1",
            "Run from the repository root with PYTHONPATH=.",
            (
                "Use origin/commit0_combined plus bootstrap overlays from "
                "configs/tasks/commit0_curated_tasks.v0.3.json."
            ),
        ),
        test_groups=(
            TaskTestGroup(
                group_id="registry_protocol_local",
                purpose=TestGroupPurpose.SPECIALIST_LOCAL,
                owner_subproblem="registry_protocol_layer",
                command=(
                    "python",
                    "-m",
                    "pytest",
                    "-q",
                    "-o",
                    "addopts=",
                    "fsspec/tests/test_registry.py",
                ),
                description="Protocol registry, deferred imports, entry points, and filesystem lookup.",
            ),
            TaskTestGroup(
                group_id="utility_compression_local",
                purpose=TestGroupPurpose.SPECIALIST_LOCAL,
                owner_subproblem="utility_compression_layer",
                command=(
                    "python",
                    "-m",
                    "pytest",
                    "-q",
                    "-o",
                    "addopts=",
                    "fsspec/tests/test_utils.py",
                    "fsspec/tests/test_compression.py",
                ),
                description="URL/path helpers, read-block behavior, and compression inference/registration.",
            ),
            TaskTestGroup(
                group_id="filesystem_backend_local",
                purpose=TestGroupPurpose.SPECIALIST_LOCAL,
                owner_subproblem="filesystem_backend_layer",
                command=(
                    "python",
                    "-m",
                    "pytest",
                    "-q",
                    "-o",
                    "addopts=",
                    "fsspec/tests/test_core.py::test_openfile_api",
                    "fsspec/tests/test_core.py::test_openfile_open",
                    "fsspec/tests/test_core.py::test_open_local_w_cache",
                    "fsspec/tests/test_core.py::test_open_expand",
                    "fsspec/tests/test_core.py::test_automkdir_local",
                ),
                description=(
                    "Abstract filesystem and local, memory, and cache backend "
                    "behavior reached by the public core tests."
                ),
            ),
            TaskTestGroup(
                group_id="core_open_path_local",
                purpose=TestGroupPurpose.SPECIALIST_LOCAL,
                owner_subproblem="core_open_path_layer",
                command=(
                    "python",
                    "-m",
                    "pytest",
                    "-q",
                    "-o",
                    "addopts=",
                    "fsspec/tests/test_core.py",
                ),
                description="OpenFile/OpenFiles, path expansion, open_local, and URL-to-filesystem behavior.",
            ),
            TaskTestGroup(
                group_id="registry_core_cross_contract",
                purpose=TestGroupPurpose.CROSS_SUBPROBLEM,
                command=(
                    "python",
                    "-m",
                    "pytest",
                    "-q",
                    "-o",
                    "addopts=",
                    "fsspec/tests/test_registry.py::test_registry_readonly",
                    "fsspec/tests/test_core.py::test_automkdir_local",
                    "fsspec/tests/test_core.py::test_list",
                ),
                description="Core URL/open behavior after protocol registry lookup is integrated.",
                prerequisites=(
                    "registry_protocol_layer artifact is integrated",
                    "core_open_path_layer artifact is integrated",
                ),
            ),
            TaskTestGroup(
                group_id="utility_core_cross_contract",
                purpose=TestGroupPurpose.CROSS_SUBPROBLEM,
                command=(
                    "python",
                    "-m",
                    "pytest",
                    "-q",
                    "-o",
                    "addopts=",
                    "fsspec/tests/test_utils.py::test_get_protocol",
                    "fsspec/tests/test_compression.py::test_infer_custom_compression",
                    "fsspec/tests/test_core.py::test_expand_paths",
                ),
                description="Core path expansion and compression behavior after utility/compression helpers are integrated.",
                prerequisites=(
                    "utility_compression_layer artifact is integrated",
                    "core_open_path_layer artifact is integrated",
                ),
            ),
            TaskTestGroup(
                group_id="full_evaluator",
                purpose=TestGroupPurpose.FULL_EVALUATOR,
                command=evaluator,
                description="Scoped public core fsspec tests excluding optional backend and HTTP/Arrow paths.",
            ),
        ),
        evaluation_snapshots=(
            EvaluationSnapshot(
                snapshot_id="curated_commit0_initial_core_evaluator",
                source_ref=f"origin/commit0_combined:{FILESYSTEM_SPEC_STRIPPED_SHA}+bootstrap-overlays",
                evidence_scope="public_initial_state",
                command=evaluator,
                python_version="3.10.12",
                dependency_versions=environment,
                collected=140,
                passed=1,
                failed=128,
                errors=3,
                skipped=8,
                return_code=1,
                duration_seconds=1.64,
                notes=(
                    (
                        "Verified with PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 and "
                        "PYTHONPATH=. after applying only checksum-recorded bootstrap overlays."
                    ),
                    (
                        "Failures/errors are caused by unfinished registry, "
                        "utility, compression, core open/path, and memory-fixture behavior."
                    ),
                ),
            ),
            EvaluationSnapshot(
                snapshot_id="complete_commit0_core_evaluator_sanity",
                source_ref=f"commit0:{FILESYSTEM_SPEC_COMPLETE_SHA}",
                evidence_scope="evaluator_sanity_only",
                command=evaluator,
                python_version="3.10.12",
                dependency_versions=environment,
                collected=137,
                passed=129,
                failed=0,
                errors=0,
                skipped=8,
                return_code=0,
                duration_seconds=0.41,
                notes=(
                    (
                        "The complete/default local commit0 ref passes the "
                        "same scoped evaluator after the version bootstrap in the same environment."
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
                "The evaluator excludes fsspec/tests/test_spec.py because it "
                "imports HTTP/Arrow-dependent paths in the stripped source."
            ),
            (
                "The evaluator excludes implementation backend suites, callbacks "
                "requiring pytest-mock, and optional service/backend tests; the "
                "minimal local, memory, and cache paths reached by test_core remain "
                "part of the task."
            ),
            (
                "Bootstrap overlays expose only import-time symbols and do not "
                "implement fsspec behavior."
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


def _metric_definitions() -> dict[str, dict[str, str]]:
    return {
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
                "Interval during which a downstream worker acts on a contract "
                "assumption inconsistent with the latest upstream artifact."
            ),
        },
    }


def build_metric_labels() -> dict[str, Any]:
    return {
        "schema_version": "0.3-async-metrics",
        "task_id": FILESYSTEM_SPEC_TASK_ID,
        "metric_annotation_id": "commit0-filesystem-spec.async-metrics.v0.3.2",
        "source_task_record": (
            "manifests/pilot/v0.3/tasks/commit0_filesystem_spec.json"
        ),
        "source_quality_record": (
            "manifests/pilot/v0.3/quality/commit0_filesystem_spec.json"
        ),
        "purpose": (
            "Dependency-level labels for measuring whether asynchronous "
            "multi-agent coding resolves fsspec registry, utility, and backend "
            "contracts consumed by core open/path behavior."
        ),
        "metric_definitions": _metric_definitions(),
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
                "dependency_id": "filesystem_spec.registry_to_core.protocol_resolution_contract",
                "dependency_type": "interface_dependency",
                "producer_subproblem": "registry_protocol_layer",
                "consumer_subproblem": "core_open_path_layer",
                "producer_agent": "registry_agent",
                "consumer_agent": "core_agent",
                "producer_files": ["fsspec/registry.py", "fsspec/__init__.py"],
                "consumer_files": ["fsspec/core.py"],
                "contract_summary": (
                    "Protocol registry lookup, deferred implementation import, "
                    "and filesystem instantiation must be stable for url_to_fs, "
                    "open_files, and core list/open behavior."
                ),
                "stale_failure_mode": (
                    "The core agent may implement URL and open behavior around "
                    "stale registry lookup or class-instantiation assumptions."
                ),
                "upstream_probe_tests": [
                    "fsspec/tests/test_registry.py::test_registry_readonly",
                    "fsspec/tests/test_registry.py::test_register_cls",
                    "fsspec/tests/test_registry.py::test_register_str",
                ],
                "downstream_probe_tests": [
                    "fsspec/tests/test_core.py::test_automkdir_local",
                    "fsspec/tests/test_core.py::test_list",
                ],
                "integrated_probe_tests": [
                    "fsspec/tests/test_registry.py::test_registry_readonly",
                    "fsspec/tests/test_core.py::test_automkdir_local",
                    "fsspec/tests/test_core.py::test_list",
                ],
                "resolution_criteria": (
                    "Resolved when registry probes and core URL/open consumer "
                    "probes pass in the integrated workspace."
                ),
                "metrics_enabled": ["ADPR", "DRS", "CAIL", "SAD"],
                "primary_paper_probe": True,
            },
            {
                "dependency_id": "filesystem_spec.utils_to_core.path_compression_contract",
                "dependency_type": "shared_api_contract",
                "producer_subproblem": "utility_compression_layer",
                "consumer_subproblem": "core_open_path_layer",
                "producer_agent": "utility_agent",
                "consumer_agent": "core_agent",
                "producer_files": ["fsspec/utils.py", "fsspec/compression.py"],
                "consumer_files": ["fsspec/core.py"],
                "contract_summary": (
                    "URL/protocol parsing, path expansion helpers, read-block "
                    "utilities, and compression registration must support core "
                    "OpenFile/OpenFiles behavior."
                ),
                "stale_failure_mode": (
                    "The core agent may implement path expansion or compression "
                    "selection against stale utility/compression contracts."
                ),
                "upstream_probe_tests": [
                    "fsspec/tests/test_utils.py::test_get_protocol",
                    "fsspec/tests/test_utils.py::test_read_block",
                    "fsspec/tests/test_compression.py::test_infer_custom_compression",
                ],
                "downstream_probe_tests": [
                    "fsspec/tests/test_core.py::test_expand_paths",
                    "fsspec/tests/test_core.py::test_xz_lzma_compressions",
                ],
                "integrated_probe_tests": [
                    "fsspec/tests/test_utils.py::test_get_protocol",
                    "fsspec/tests/test_compression.py::test_infer_custom_compression",
                    "fsspec/tests/test_core.py::test_expand_paths",
                    "fsspec/tests/test_core.py::test_xz_lzma_compressions",
                ],
                "resolution_criteria": (
                    "Resolved when utility/compression probes and core path/"
                    "compression consumer probes pass after integration."
                ),
                "metrics_enabled": ["ADPR", "DRS", "CAIL", "SAD"],
            },
            {
                "dependency_id": "filesystem_spec.backends_to_core.open_contract",
                "dependency_type": "shared_api_contract",
                "producer_subproblem": "filesystem_backend_layer",
                "consumer_subproblem": "core_open_path_layer",
                "producer_agent": "backend_agent",
                "consumer_agent": "core_agent",
                "producer_files": [
                    "fsspec/spec.py",
                    "fsspec/implementations/local.py",
                    "fsspec/implementations/memory.py",
                    "fsspec/implementations/cached.py",
                    "fsspec/implementations/cache_mapper.py",
                    "fsspec/implementations/cache_metadata.py",
                ],
                "consumer_files": ["fsspec/core.py"],
                "contract_summary": (
                    "AbstractFileSystem and the local, memory, and cache backends "
                    "must provide the open, info, glob, parent, cache mapping, and "
                    "local-file behavior consumed by core OpenFile/open_local paths."
                ),
                "stale_failure_mode": (
                    "The core agent may implement OpenFile or open_local around "
                    "stale backend return values or filesystem method semantics."
                ),
                "upstream_probe_tests": [
                    "fsspec/tests/test_core.py::test_openfile_api",
                    "fsspec/tests/test_core.py::test_openfile_open",
                    "fsspec/tests/test_core.py::test_open_local_w_cache",
                ],
                "downstream_probe_tests": [
                    "fsspec/tests/test_core.py::test_open_expand",
                    "fsspec/tests/test_core.py::test_multi_context",
                ],
                "integrated_probe_tests": [
                    "fsspec/tests/test_core.py::test_openfile_api",
                    "fsspec/tests/test_core.py::test_open_local_w_cache",
                    "fsspec/tests/test_core.py::test_open_expand",
                    "fsspec/tests/test_core.py::test_multi_context",
                ],
                "resolution_criteria": (
                    "Resolved when backend open/cache probes and core OpenFile/"
                    "open_local consumer probes pass together after integration."
                ),
                "metrics_enabled": ["ADPR", "DRS", "CAIL", "SAD"],
            },
        ],
        "aggregate_metrics": {
            "dependency_point_count": 3,
            "primary_async_dependency_ids": [
                "filesystem_spec.registry_to_core.protocol_resolution_contract",
                "filesystem_spec.utils_to_core.path_compression_contract",
                "filesystem_spec.backends_to_core.open_contract",
            ],
            "primary_paper_dependency_id": (
                "filesystem_spec.registry_to_core.protocol_resolution_contract"
            ),
            "ADPR_denominator": (
                "All dependency_points unless a paper section explicitly "
                "reports primary_async_dependency_ids only."
            ),
            "minimum_success_condition_for_task_level_async_dependency_resolution": (
                "All primary_async_dependency_ids pass in the final integrated workspace."
            ),
        },
        "annotation_notes": [
            (
                "The registry_to_core dependency is the primary signal because "
                "core URL/open behavior is sensitive to stale protocol lookup and "
                "filesystem instantiation assumptions."
            ),
            (
                "The utils_to_core dependency captures stale assumptions around "
                "URL parsing, path expansion, read blocks, and compression lookup."
            ),
            (
                "The backends_to_core dependency captures the abstract filesystem "
                "and local, memory, and cache contracts exercised indirectly by "
                "the public core evaluator."
            ),
            (
                "Revision v0.3.2 closes the dependency graph over the stripped "
                "backend production files already exercised by public tests."
            ),
            "These labels identify public test-observable contracts, not solution code.",
        ],
    }


def build_annotation_forms(
    *, candidate_file: Path, task_record_file: Path
) -> tuple[AnnotationForm, AnnotationForm]:
    common = {
        "task_id": FILESYSTEM_SPEC_TASK_ID.replace("commit0:", "asyncodebench:", 1),
        "source_task_id": FILESYSTEM_SPEC_TASK_ID,
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
                "Explicitly assess whether the registry/utility/backend->core "
                "splits are natural AsynCodeBench dependencies rather than "
                "artificial file partitioning."
            ),
        ),
    }
    return (
        AnnotationForm(**common, annotator_id="annotator_a"),
        AnnotationForm(**common, annotator_id="annotator_b"),
    )


def build_adjudication_form() -> AdjudicationForm:
    return AdjudicationForm(
        task_id=FILESYSTEM_SPEC_TASK_ID.replace("commit0:", "asyncodebench:", 1),
        source_task_id=FILESYSTEM_SPEC_TASK_ID,
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
