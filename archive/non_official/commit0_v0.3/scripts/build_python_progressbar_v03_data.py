"""Generate and validate the v0.3 Commit0 python-progressbar task records."""

from __future__ import annotations

import json
from pathlib import Path


TASK_ID = "commit0:python-progressbar"
STRIPPED_SHA = "afd18fd921caccca5f0c01576434869ddd7c0043"
COMPLETE_SHA = "edb9803924ab60ede3077dc72331c41d13e0c322"
BASE_REF = "origin/commit0_combined"
CANDIDATE_EVIDENCE = "manifests/candidates/commit0_async_screening_v0.3.json"

EVALUATOR_COMMAND = [
    "python3.10",
    "-m",
    "pytest",
    "-q",
    "-o",
    "addopts=",
    "tests/test_algorithms.py",
    "tests/test_utils.py",
    "tests/test_wrappingio.py",
    "tests/test_stream.py",
    "tests/test_data_transfer_bar.py",
    "tests/test_progressbar.py::test_reuse",
    "tests/test_progressbar.py::test_dirty",
    "tests/test_progressbar.py::test_negative_maximum",
    "tests/test_widgets.py::test_create_wrapper",
    "tests/test_widgets.py::test_all_widgets_min_width",
    "tests/test_widgets.py::test_all_widgets_max_width",
]
TEST_TARGETS = EVALUATOR_COMMAND[6:]
PUBLIC_MODULES = [
    "progressbar/algorithms.py",
    "progressbar/bar.py",
    "progressbar/base.py",
    "progressbar/env.py",
    "progressbar/terminal/base.py",
    "progressbar/terminal/os_specific/__init__.py",
    "progressbar/terminal/os_specific/posix.py",
    "progressbar/terminal/stream.py",
    "progressbar/utils.py",
    "progressbar/widgets.py",
]
DEPENDENCIES = [
    {
        "consumer_subproblem": "progressbar_core_layer",
        "dependency_type": "api_contract",
        "description": "ProgressBar output, resizing, and fd handling consume terminal environment detection, color capability, and line stream wrapper contracts.",
        "evidence_paths": [
            "progressbar/env.py",
            "progressbar/terminal/base.py",
            "progressbar/terminal/stream.py",
            "progressbar/bar.py",
            "tests/test_utils.py",
            "tests/test_stream.py",
        ],
        "producer_subproblem": "environment_terminal_layer",
        "schema_version": "0.3",
    },
    {
        "consumer_subproblem": "widget_formatting_layer",
        "dependency_type": "api_contract",
        "description": "Widget formatting and ETA/speed calculations consume ProgressBar data shape, value/max_value state, elapsed timing, percentage, and width allocation.",
        "evidence_paths": [
            "progressbar/bar.py",
            "progressbar/widgets.py",
            "progressbar/algorithms.py",
            "tests/test_progressbar.py",
            "tests/test_widgets.py",
            "tests/test_data_transfer_bar.py",
        ],
        "producer_subproblem": "progressbar_core_layer",
        "schema_version": "0.3",
    },
    {
        "consumer_subproblem": "progressbar_core_layer",
        "dependency_type": "integration",
        "description": "ProgressBar stream redirection and live output consume WrappingIO and StreamWrapper read/write/flush/listener behavior from utilities.",
        "evidence_paths": [
            "progressbar/utils.py",
            "progressbar/bar.py",
            "tests/test_wrappingio.py",
            "tests/test_stream.py",
        ],
        "producer_subproblem": "stream_utility_layer",
        "schema_version": "0.3",
    },
]
NATURAL_SUBPROBLEMS = {
    "environment_terminal_layer": [
        "progressbar/env.py",
        "progressbar/terminal/base.py",
        "progressbar/terminal/os_specific/__init__.py",
        "progressbar/terminal/os_specific/posix.py",
        "progressbar/terminal/stream.py",
        "tests/test_utils.py",
        "tests/test_stream.py",
    ],
    "progressbar_core_layer": [
        "progressbar/bar.py",
        "progressbar/base.py",
        "tests/test_progressbar.py",
        "tests/test_data_transfer_bar.py",
        "tests/test_stream.py",
    ],
    "widget_formatting_layer": [
        "progressbar/widgets.py",
        "progressbar/algorithms.py",
        "tests/test_algorithms.py",
        "tests/test_widgets.py",
    ],
    "stream_utility_layer": [
        "progressbar/utils.py",
        "tests/test_utils.py",
        "tests/test_wrappingio.py",
        "tests/test_stream.py",
    ],
}


def assignment(
    agent_id: str,
    role: str,
    subproblem_id: str,
    writable_paths: list[str],
    tests: list[str],
) -> dict:
    return {
        "agent_id": agent_id,
        "primary_test_targets": tests,
        "role": role,
        "schema_version": "0.3",
        "subproblem_id": subproblem_id,
        "writable_paths": writable_paths,
    }


ASSIGNMENTS = [
    assignment(
        "terminal_agent",
        "terminal environment, ANSI/color capability, cursor/line stream, and platform input specialist",
        "environment_terminal_layer",
        [
            "progressbar/env.py",
            "progressbar/terminal/base.py",
            "progressbar/terminal/os_specific/__init__.py",
            "progressbar/terminal/os_specific/posix.py",
            "progressbar/terminal/stream.py",
        ],
        [
            "tests/test_utils.py::test_env_flag",
            "tests/test_utils.py::test_is_terminal",
            "tests/test_stream.py::test_last_line_stream_methods",
        ],
    ),
    assignment(
        "core_bar_agent",
        "ProgressBar lifecycle, update, percentage, output line, and data-state specialist",
        "progressbar_core_layer",
        ["progressbar/bar.py", "progressbar/base.py"],
        [
            "tests/test_progressbar.py::test_reuse",
            "tests/test_progressbar.py::test_dirty",
            "tests/test_progressbar.py::test_negative_maximum",
            "tests/test_data_transfer_bar.py",
        ],
    ),
    assignment(
        "widget_agent",
        "widgets, smoothing algorithms, ETA/speed, min/max width, and formatting specialist",
        "widget_formatting_layer",
        ["progressbar/algorithms.py", "progressbar/widgets.py"],
        [
            "tests/test_algorithms.py",
            "tests/test_widgets.py::test_create_wrapper",
            "tests/test_widgets.py::test_all_widgets_min_width",
            "tests/test_widgets.py::test_all_widgets_max_width",
        ],
    ),
    assignment(
        "stream_agent",
        "WrappingIO, StreamWrapper, stdout/stderr redirection, flush, and listener utility specialist",
        "stream_utility_layer",
        ["progressbar/utils.py"],
        [
            "tests/test_wrappingio.py",
            "tests/test_stream.py::test_nowrap",
            "tests/test_stream.py::test_wrap",
            "tests/test_stream.py::test_fd_as_io_stream",
        ],
    ),
]


def scenario(
    mode: str,
    communication: str,
    concurrent: bool,
    profile: str,
    integration: str,
    delivery: str,
) -> dict:
    assignments = ASSIGNMENTS
    agent_count = 4
    if mode == "iterative_single":
        assignments = [
            assignment(
                "integrator",
                "iterative full-task coding agent",
                "full_task",
                PUBLIC_MODULES,
                TEST_TARGETS,
            )
        ]
        agent_count = 1
    return {
        "agent_count": agent_count,
        "assignments": assignments,
        "communication_condition": communication,
        "concurrent_execution": concurrent,
        "dependency_annotations": DEPENDENCIES,
        "execution_mode": mode,
        "information_profile": profile,
        "integration_policy": integration,
        "message_delivery_policy": delivery,
        "scenario_id": f"commit0-python-progressbar.{mode.replace('_', '-')}.v0.3",
        "schema_version": "0.3",
        "shared_agent_scaffold": "iterative-inspect-edit-test-repair",
        "step_budget_per_agent": 30,
        "task_id": TASK_ID,
        "test_budget_per_agent": 10,
        "token_budget_per_agent": 75000,
        "wall_clock_budget_seconds": 3600,
    }


def task_record() -> dict:
    return {
        "annotation_provenance": [],
        "candidate_evidence_file": CANDIDATE_EVIDENCE,
        "dependency_annotations": DEPENDENCIES,
        "evaluator_command": EVALUATOR_COMMAND,
        "inclusion_decision": None,
        "natural_subproblems": NATURAL_SUBPROBLEMS,
        "notes": [
            "Task source and tests are unchanged.",
            "Candidate screening labeled this task weak_or_unclear because the stripped ref has raw import and collection blockers.",
            "The complete develop/commit0 ref passes the scoped evaluator, but the stripped initial ref currently needs bootstrap design before it can collect.",
            "The proposed dependency structure is a draft curation decision and not a final independent annotation.",
        ],
        "problem_statement": (
            "Restore the scoped python-progressbar behavior exercised by the public Commit0 tests without modifying the tests.\n\n"
            "The terminal/environment layer must expose environment flags, terminal/color capability, platform input hooks, and line stream wrappers consumed by ProgressBar output behavior. "
            "The core bar layer must implement ProgressBar lifecycle, update, finish, percentage, current value, data state, and output formatting contracts. "
            "The widget layer must consume ProgressBar data and timing state to implement smoothing algorithms, ETA/speed widgets, width filtering, and wrapper construction. "
            "The stream utility layer must provide WrappingIO and StreamWrapper behavior consumed by redirected stdout/stderr progress output.\n\n"
            "The initial benchmark source is the stripped Commit0-style ref origin/commit0_combined. This candidate is marked needs_revision because a minimal answer-free bootstrap overlay still needs to be designed and validated."
        ),
        "proposed_parallelizability_label": "partially_parallelizable",
        "publicly_implicated_modules": PUBLIC_MODULES,
        "qualification_label": None,
        "qualification_status": "pending_independent_annotation",
        "quality_evidence_file": "manifests/pilot/v0.3/quality/commit0_python_progressbar.json",
        "repository": "commit0/python-progressbar",
        "schema_version": "0.3",
        "source_materialization": (
            f"git archive of the stripped Commit0-style python-progressbar ref {BASE_REF} at {STRIPPED_SHA}. "
            "No bootstrap overlay is currently accepted for this needs_revision candidate."
        ),
        "task_id": TASK_ID,
        "task_source": "Commit0",
        "test_targets": TEST_TARGETS,
        "upstream_version": STRIPPED_SHA,
    }


def scenario_record() -> dict:
    return {
        "scenarios": [
            scenario(
                "iterative_single",
                "not_applicable",
                False,
                "complete-task",
                "Agent submits its final workspace.",
                "No inter-agent messages.",
            ),
            scenario(
                "serial_specialists",
                "completed_artifact_handoff",
                False,
                "private-workspace",
                "Apply terminal and stream utility artifacts before core ProgressBar integration, then integrate widgets and run dependency probes.",
                "Specialists run with barrier synchronization; downstream agents receive completed upstream artifacts before final validation.",
            ),
            scenario(
                "async_private",
                "none_in_flight",
                True,
                "private-workspace",
                "Integrate independently produced specialist artifacts at the end, then run dependency probes and the scoped evaluator.",
                "Agents work concurrently without messages while core and widget assumptions about terminal, stream, and data contracts may become stale.",
            ),
            scenario(
                "async_message",
                "structured_message_and_artifact",
                True,
                "private-workspace",
                "Integrate independently produced specialist artifacts after asynchronous handoffs, then run dependency probes and the scoped evaluator.",
                "Agents may send artifact summaries asynchronously; downstream workers are not guaranteed to see the newest terminal, stream, or ProgressBar data contract before acting.",
            ),
        ],
        "schema_version": "0.3",
        "task_id": TASK_ID,
    }


def quality_record() -> dict:
    return {
        "coordination_structure_tags": [
            "interface_dependency",
            "shared_abstraction",
        ],
        "environment_requirements": [
            "Python 3.10.12",
            "pytest",
            "freezegun>=0.3.11",
            "python-utils>=3.8.1",
            "dill>=0.3.6 for broader public tests",
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD=1",
            "Run from the repository root with PYTHONPATH=.",
        ],
        "evaluation_snapshots": [
            {
                "collected": 1,
                "command": EVALUATOR_COMMAND,
                "dependency_versions": {
                    "freezegun": "1.5.5",
                    "python-utils": "3.9.1",
                },
                "duration_seconds": 0.20,
                "errors": 1,
                "evidence_scope": "public_initial_state",
                "failed": 0,
                "notes": [
                    "Verified from a git archive of origin/commit0_combined with public test dependencies installed.",
                    "Collection stops during tests/conftest.py import because progressbar/env.py has a stripped f-string syntax blocker.",
                    "A temporary probe showed further import-time blockers after the syntax fix, including missing terminal os_specific.getch, Colors.interpolate, and StreamWrapper.flush.",
                ],
                "passed": 0,
                "python_version": "3.10.12",
                "return_code": 4,
                "schema_version": "0.3",
                "skipped": 0,
                "snapshot_id": "curated_commit0_initial_progressbar_evaluator_collection",
                "source_ref": f"{BASE_REF}:{STRIPPED_SHA}",
            },
            {
                "collected": 90,
                "command": EVALUATOR_COMMAND,
                "dependency_versions": {
                    "freezegun": "1.5.5",
                    "python-utils": "3.9.1",
                },
                "duration_seconds": 0.93,
                "errors": 0,
                "evidence_scope": "evaluator_sanity_only",
                "failed": 0,
                "notes": [
                    "The complete develop/commit0 ref passes the same scoped evaluator in the same environment.",
                    "The complete ref is evaluator validation only and must not define decomposition, prompts, or agent-visible evidence.",
                ],
                "passed": 90,
                "python_version": "3.10.12",
                "return_code": 0,
                "schema_version": "0.3",
                "skipped": 0,
                "snapshot_id": "complete_commit0_progressbar_evaluator_sanity",
                "source_ref": f"develop:{COMPLETE_SHA}",
            },
        ],
        "known_limitations": [
            "The task is not qualification_ready because origin/commit0_combined does not yet collect under the scoped evaluator.",
            "Bootstrap design is nontrivial: at least one syntax repair and multiple import/class construction placeholders are needed before tests execute.",
            "Any future bootstrap overlay must be reviewed to ensure it does not implement terminal color, stream wrapper, or ProgressBar semantics.",
            "The evaluator is scoped away from the slowest example and timing tests while retaining dependency probes for terminal, stream, core bar, and widget contracts.",
            "Single-agent and multi-agent model results are evaluation outputs to report, not dataset qualification gates.",
        ],
        "public_statement_sources": [
            "README.rst@origin/commit0_combined",
            "progressbar/*.py@origin/commit0_combined",
            "progressbar/terminal/*.py@origin/commit0_combined",
            "tests/test_*.py@origin/commit0_combined",
            CANDIDATE_EVIDENCE,
        ],
        "quality_status": "needs_revision",
        "remaining_gates": [
            "Design the smallest answer-free bootstrap overlay for syntax/import/class-construction blockers.",
            "Run git apply --check and checksum validation for any accepted bootstrap overlay.",
            "Rerun the stripped initial scoped evaluator after bootstrap overlays and record pass/fail counts.",
            "Have human reviewers decide whether bootstrap width is acceptable or whether the task should be excluded.",
            "Two independent human inclusion/exclusion annotations.",
        ],
        "schema_version": "0.3",
        "structure_rationale": (
            "python-progressbar has natural async dependencies across terminal capability detection, stream wrapping, ProgressBar state, and widget formatting. "
            "In asynchronous collaboration, the core bar agent can write output and data-state behavior against stale terminal/stream assumptions, while widget code can consume an outdated ProgressBar data shape or timing contract."
        ),
        "task_id": TASK_ID,
        "test_groups": [
            {
                "command": EVALUATOR_COMMAND[:6] + ["tests/test_utils.py"],
                "description": "Environment flag and terminal capability probes.",
                "group_id": "environment_terminal_local",
                "owner_subproblem": "environment_terminal_layer",
                "prerequisites": [],
                "purpose": "specialist_local",
                "schema_version": "0.3",
            },
            {
                "command": EVALUATOR_COMMAND[:6] + ["tests/test_wrappingio.py"],
                "description": "WrappingIO stream protocol probes.",
                "group_id": "stream_utility_local",
                "owner_subproblem": "stream_utility_layer",
                "prerequisites": [],
                "purpose": "specialist_local",
                "schema_version": "0.3",
            },
            {
                "command": EVALUATOR_COMMAND[:6]
                + [
                    "tests/test_progressbar.py::test_reuse",
                    "tests/test_progressbar.py::test_dirty",
                    "tests/test_progressbar.py::test_negative_maximum",
                    "tests/test_data_transfer_bar.py",
                ],
                "description": "Core ProgressBar lifecycle, state, and data-transfer bar probes.",
                "group_id": "core_bar_local",
                "owner_subproblem": "progressbar_core_layer",
                "prerequisites": [],
                "purpose": "specialist_local",
                "schema_version": "0.3",
            },
            {
                "command": EVALUATOR_COMMAND[:6]
                + [
                    "tests/test_algorithms.py",
                    "tests/test_widgets.py::test_create_wrapper",
                    "tests/test_widgets.py::test_all_widgets_min_width",
                    "tests/test_widgets.py::test_all_widgets_max_width",
                ],
                "description": "Smoothing algorithm and widget width/formatting probes.",
                "group_id": "widget_formatting_local",
                "owner_subproblem": "widget_formatting_layer",
                "prerequisites": [],
                "purpose": "specialist_local",
                "schema_version": "0.3",
            },
            {
                "command": EVALUATOR_COMMAND[:6]
                + [
                    "tests/test_stream.py::test_fd_as_io_stream",
                    "tests/test_progressbar.py::test_reuse",
                ],
                "description": "ProgressBar output behavior after terminal and stream wrapper contracts are integrated.",
                "group_id": "terminal_stream_core_cross_contract",
                "owner_subproblem": None,
                "prerequisites": [
                    "environment_terminal_layer artifact is integrated",
                    "stream_utility_layer artifact is integrated",
                    "progressbar_core_layer artifact is integrated",
                ],
                "purpose": "cross_subproblem",
                "schema_version": "0.3",
            },
            {
                "command": EVALUATOR_COMMAND,
                "description": "Full scoped progressbar evaluator.",
                "group_id": "full_scoped_evaluator",
                "owner_subproblem": None,
                "prerequisites": [
                    "environment_terminal_layer artifact is integrated",
                    "stream_utility_layer artifact is integrated",
                    "progressbar_core_layer artifact is integrated",
                    "widget_formatting_layer artifact is integrated",
                ],
                "purpose": "full_evaluator",
                "schema_version": "0.3",
            },
        ],
    }


def metrics_record() -> dict:
    dependency_points = [
        {
            "consumer_agent": "core_bar_agent",
            "consumer_files": ["progressbar/bar.py", "progressbar/base.py"],
            "consumer_subproblem": "progressbar_core_layer",
            "contract_summary": "Terminal and environment helpers must expose stable is_terminal/is_ansi_terminal, color support, line wrapper, and platform getch behavior consumed by ProgressBar output handling.",
            "dependency_id": "python_progressbar.terminal_to_core.output_contract",
            "dependency_type": "interface_dependency",
            "downstream_probe_tests": [
                "tests/test_stream.py::test_fd_as_io_stream",
                "tests/test_progressbar.py::test_reuse",
            ],
            "integrated_probe_tests": [
                "tests/test_utils.py::test_is_terminal",
                "tests/test_stream.py::test_last_line_stream_methods",
                "tests/test_stream.py::test_fd_as_io_stream",
                "tests/test_progressbar.py::test_reuse",
            ],
            "metrics_enabled": ["ADPR", "DRS", "CAIL", "SAD"],
            "primary_paper_probe": True,
            "producer_agent": "terminal_agent",
            "producer_files": [
                "progressbar/env.py",
                "progressbar/terminal/base.py",
                "progressbar/terminal/stream.py",
            ],
            "producer_subproblem": "environment_terminal_layer",
            "resolution_criteria": "Resolved when terminal detection, line stream, and ProgressBar fd/output probes pass in the integrated workspace.",
            "stale_failure_mode": "The core bar agent may implement output clearing, fd handling, or terminal refresh behavior against stale terminal capability or line wrapper assumptions.",
            "upstream_probe_tests": [
                "tests/test_utils.py::test_env_flag",
                "tests/test_utils.py::test_is_terminal",
                "tests/test_stream.py::test_last_line_stream_methods",
            ],
        },
        {
            "consumer_agent": "widget_agent",
            "consumer_files": ["progressbar/widgets.py", "progressbar/algorithms.py"],
            "consumer_subproblem": "widget_formatting_layer",
            "contract_summary": "Widgets must consume ProgressBar data dictionaries, value/max_value state, elapsed timing, percentage, and terminal width allocation consistently.",
            "dependency_id": "python_progressbar.core_to_widgets.data_shape_contract",
            "dependency_type": "shared_state_contract",
            "downstream_probe_tests": [
                "tests/test_widgets.py::test_all_widgets_min_width",
                "tests/test_widgets.py::test_all_widgets_max_width",
            ],
            "integrated_probe_tests": [
                "tests/test_progressbar.py::test_reuse",
                "tests/test_data_transfer_bar.py::test_known_length",
                "tests/test_widgets.py::test_all_widgets_min_width",
                "tests/test_widgets.py::test_all_widgets_max_width",
            ],
            "metrics_enabled": ["ADPR", "DRS", "CAIL", "SAD"],
            "producer_agent": "core_bar_agent",
            "producer_files": ["progressbar/bar.py", "progressbar/base.py"],
            "producer_subproblem": "progressbar_core_layer",
            "resolution_criteria": "Resolved when core ProgressBar lifecycle/data probes and widget width/formatting probes pass after integration.",
            "stale_failure_mode": "The widget agent may format against an outdated ProgressBar data dictionary, value/max_value convention, elapsed timing, or width allocation contract.",
            "upstream_probe_tests": [
                "tests/test_progressbar.py::test_reuse",
                "tests/test_progressbar.py::test_dirty",
                "tests/test_data_transfer_bar.py::test_known_length",
            ],
        },
        {
            "consumer_agent": "core_bar_agent",
            "consumer_files": ["progressbar/bar.py"],
            "consumer_subproblem": "progressbar_core_layer",
            "contract_summary": "ProgressBar live output must consume WrappingIO and StreamWrapper read/write/flush/listener semantics consistently for stdout/stderr redirection.",
            "dependency_id": "python_progressbar.stream_utils_to_core.redirection_contract",
            "dependency_type": "shared_abstraction",
            "downstream_probe_tests": [
                "tests/test_stream.py::test_nowrap",
                "tests/test_stream.py::test_wrap",
                "tests/test_stream.py::test_fd_as_io_stream",
            ],
            "integrated_probe_tests": [
                "tests/test_wrappingio.py::test_wrappingio",
                "tests/test_wrappingio.py::test_wrapping_stringio",
                "tests/test_stream.py::test_wrap",
                "tests/test_stream.py::test_fd_as_io_stream",
            ],
            "metrics_enabled": ["ADPR", "DRS", "CAIL", "SAD"],
            "producer_agent": "stream_agent",
            "producer_files": ["progressbar/utils.py"],
            "producer_subproblem": "stream_utility_layer",
            "resolution_criteria": "Resolved when WrappingIO protocol probes and ProgressBar redirected stream probes pass together.",
            "stale_failure_mode": "The core bar agent may assume stale stream wrapper behavior around flushing, listener notification, or stdout/stderr replacement.",
            "upstream_probe_tests": [
                "tests/test_wrappingio.py::test_wrappingio",
                "tests/test_wrappingio.py::test_wrapping_stringio",
            ],
        },
    ]
    return {
        "aggregate_metrics": {
            "ADPR_denominator": "All dependency_points unless a paper section explicitly reports primary_async_dependency_ids only.",
            "dependency_point_count": 3,
            "minimum_success_condition_for_task_level_async_dependency_resolution": "All primary_async_dependency_ids pass in the final integrated workspace.",
            "primary_async_dependency_ids": [
                item["dependency_id"] for item in dependency_points
            ],
            "primary_paper_dependency_id": "python_progressbar.terminal_to_core.output_contract",
        },
        "annotation_notes": [
            "The terminal_to_core dependency is the primary async signal because terminal detection and line stream behavior define how ProgressBar updates are rendered.",
            "The core_to_widgets dependency captures stale assumptions around ProgressBar data shape, timing, max_value, and width allocation.",
            "The stream_utils_to_core dependency captures stale assumptions in stdout/stderr redirection and live output.",
            "These labels identify public test-observable contracts, not solution code.",
            "The task remains needs_revision until the bootstrap overlay is accepted or the candidate is excluded.",
        ],
        "dependency_points": dependency_points,
        "evaluation_checkpoint_policy": {
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
            "minimum_policy": "Run probe tests after each agent final artifact and after final integration.",
            "recommended_policy": "Run probe tests after every committed patch, every explicit artifact transfer, and final integration.",
        },
        "metric_annotation_id": "commit0-python-progressbar.async-metrics.v0.3",
        "metric_definitions": {
            "ADPR": {
                "definition": "Fraction of registered dependency_points whose required integrated_probe_tests pass in the final integrated workspace.",
                "name": "Async Dependency Pass Rate",
                "unit": "fraction",
            },
            "CAIL": {
                "definition": "downstream_resolution_step minus upstream_resolution_step when both probe groups have been evaluated.",
                "name": "Cross-Agent Integration Lag",
                "unit": "agent iteration or evaluation checkpoint",
            },
            "DRS": {
                "definition": "First recorded checkpoint at which all required integrated_probe_tests for a dependency point pass.",
                "name": "Dependency Resolution Step",
                "unit": "agent iteration or evaluation checkpoint",
            },
            "SAD": {
                "definition": "Interval during which a downstream worker acts on a contract assumption inconsistent with the latest upstream artifact.",
                "name": "Stale Assumption Duration",
                "unit": "agent iteration or event interval",
            },
        },
        "purpose": "Dependency-level labels for measuring whether asynchronous multi-agent coding resolves python-progressbar terminal, stream, core bar, and widget contracts.",
        "schema_version": "0.3-async-metrics",
        "source_quality_record": "manifests/pilot/v0.3/quality/commit0_python_progressbar.json",
        "source_task_record": "manifests/pilot/v0.3/tasks/commit0_python_progressbar.json",
        "task_id": TASK_ID,
    }


def annotation_form(annotator_id: str) -> dict:
    return {
        "allowed_labels": [
            "parallelizable",
            "partially_parallelizable",
            "effectively_serial",
        ],
        "annotator_id": annotator_id,
        "candidate_evidence_file": CANDIDATE_EVIDENCE,
        "exclusion_reason": None,
        "include": None,
        "independence_instructions": [
            "Use only public Commit0 evidence, the screening record, and the draft task record.",
            "Review the linked TaskQualityRecord, especially the weak_or_unclear screening label and bootstrap-width risk.",
            "Do not inspect reference branches, solution patches, or diffs.",
            "Do not consult the other annotator before submitting.",
            "Explicitly assess whether the terminal/stream -> ProgressBar -> widget split is a natural AsynCodeBench dependency rather than artificial file partitioning.",
            "Explicitly decide whether a future bootstrap overlay for syntax/import/class construction blockers would be answer-free enough for inclusion.",
        ],
        "parallelizability_label": None,
        "rationale": None,
        "schema_version": "0.3",
        "task_id": TASK_ID,
        "task_record_file": "manifests/pilot/v0.3/tasks/commit0_python_progressbar.json",
    }


def adjudication_template() -> dict:
    return {
        "adjudicator_id": "independent_adjudicator",
        "annotator_ids": ["annotator_a", "annotator_b"],
        "exclusion_reason": None,
        "include": None,
        "parallelizability_label": None,
        "rationale": None,
        "schema_version": "0.3",
        "task_id": TASK_ID,
    }


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def update_curated_config() -> None:
    path = Path("configs/tasks/commit0_curated_tasks.v0.3.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["tasks"] = [task for task in payload["tasks"] if task["task_id"] != TASK_ID]
    payload["tasks"].append(
        {
            "task_id": TASK_ID,
            "repository": "python-progressbar",
            "base_ref": BASE_REF,
            "base_sha": STRIPPED_SHA,
            "overlays": [],
        }
    )
    write_json(path, payload)


def main() -> int:
    files = {
        Path("manifests/pilot/v0.3/tasks/commit0_python_progressbar.json"): task_record(),
        Path("manifests/pilot/v0.3/scenarios/commit0_python_progressbar.json"): scenario_record(),
        Path("manifests/pilot/v0.3/quality/commit0_python_progressbar.json"): quality_record(),
        Path("manifests/pilot/v0.3/metrics/commit0_python_progressbar_async_metrics.json"): metrics_record(),
        Path("manifests/annotations/commit0_v0.3/python_progressbar/annotator_a.json"): annotation_form("annotator_a"),
        Path("manifests/annotations/commit0_v0.3/python_progressbar/annotator_b.json"): annotation_form("annotator_b"),
        Path("manifests/annotations/commit0_v0.3/python_progressbar/adjudication.template.json"): adjudication_template(),
    }
    for path, payload in files.items():
        write_json(path, payload)
    update_curated_config()
    for path in files:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload["task_id"] != TASK_ID:
            raise ValueError(f"unexpected task_id in {path}: {payload['task_id']}")
    print(f"generated {TASK_ID} v0.3 manifest files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
