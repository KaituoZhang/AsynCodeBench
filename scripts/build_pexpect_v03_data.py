"""Generate and validate the v0.3 Commit0 pexpect task records."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


TASK_ID = "commit0:pexpect"
STRIPPED_SHA = "21b5908ea5b9b38ca996fec50dc449bff5c2c82f"
COMPLETE_SHA = "eb2820cec514c3ed5482e80ad3438cd31f2fa1ef"
BASE_REF = "origin/commit0_combined"
AUDIT = "docs/audits/COMMIT0_CANDIDATE_REVIEW_virtualenv_pexpect_web3_v0.3.md"

EVALUATOR_COMMAND = [
    "python3.10",
    "-m",
    "pytest",
    "-q",
    "-o",
    "addopts=",
    "tests/test_expect.py",
    "tests/test_popen_spawn.py",
    "tests/test_run.py",
    "tests/test_async.py",
]
TEST_TARGETS = EVALUATOR_COMMAND[6:]
PUBLIC_MODULES = [
    "pexpect/_async.py",
    "pexpect/_async_pre_await.py",
    "pexpect/_async_w_await.py",
    "pexpect/expect.py",
    "pexpect/popen_spawn.py",
    "pexpect/pty_spawn.py",
    "pexpect/replwrap.py",
    "pexpect/run.py",
    "pexpect/spawnbase.py",
]
DEPENDENCIES = [
    {
        "consumer_subproblem": "spawn_api_state_layer",
        "dependency_type": "api_contract",
        "description": "SpawnBase expect, expect_list, expect_exact, buffer, before, after, and match behavior consume Expecter and searcher matching semantics.",
        "evidence_paths": [
            "pexpect/expect.py",
            "pexpect/spawnbase.py",
            "tests/test_expect.py",
        ],
        "producer_subproblem": "expect_search_layer",
        "schema_version": "0.3",
    },
    {
        "consumer_subproblem": "spawn_api_state_layer",
        "dependency_type": "api_contract",
        "description": "SpawnBase and Expecter consume transport-specific read_nonblocking, send, close, EOF, TIMEOUT, and encoding behavior from pty and popen transports.",
        "evidence_paths": [
            "pexpect/spawnbase.py",
            "pexpect/pty_spawn.py",
            "pexpect/popen_spawn.py",
            "tests/test_expect.py",
            "tests/test_popen_spawn.py",
        ],
        "producer_subproblem": "transport_layer",
        "schema_version": "0.3",
    },
    {
        "consumer_subproblem": "wrapper_layer",
        "dependency_type": "shared_state_contract",
        "description": "run, replwrap, and async wrappers consume SpawnBase expect/read state, EOF/TIMEOUT behavior, and transport output normalization.",
        "evidence_paths": [
            "pexpect/spawnbase.py",
            "pexpect/run.py",
            "pexpect/replwrap.py",
            "pexpect/_async.py",
            "tests/test_run.py",
            "tests/test_async.py",
        ],
        "producer_subproblem": "spawn_api_state_layer",
        "schema_version": "0.3",
    },
]
NATURAL_SUBPROBLEMS = {
    "expect_search_layer": [
        "pexpect/expect.py",
        "tests/test_expect.py",
    ],
    "spawn_api_state_layer": [
        "pexpect/spawnbase.py",
        "tests/test_expect.py",
        "tests/test_popen_spawn.py",
    ],
    "transport_layer": [
        "pexpect/pty_spawn.py",
        "pexpect/popen_spawn.py",
        "pexpect/_async.py",
        "pexpect/_async_pre_await.py",
        "pexpect/_async_w_await.py",
        "tests/test_popen_spawn.py",
        "tests/test_async.py",
    ],
    "wrapper_layer": [
        "pexpect/run.py",
        "pexpect/replwrap.py",
        "tests/test_run.py",
        "tests/test_async.py",
    ],
}


def overlays() -> list[dict]:
    path = Path("data/overlays/commit0/pexpect/0001-spawnbase-buffer-property-bootstrap.patch")
    return [
        {
            "path": path.as_posix(),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "rationale": "Expose only SpawnBase._get_buffer and SpawnBase._set_buffer placeholders so the stripped class-level buffer property can bind during public test collection. Buffer semantics remain unfinished.",
        }
    ]


def assignment(agent_id: str, role: str, subproblem_id: str, writable_paths: list[str], tests: list[str]) -> dict:
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
        "expect_agent",
        "Expecter, searcher_string, searcher_re, and match-loop specialist",
        "expect_search_layer",
        ["pexpect/expect.py"],
        [
            "tests/test_expect.py::ExpectTestCase::test_expect_order",
            "tests/test_expect.py::ExpectTestCase::test_searchwindowsize",
        ],
    ),
    assignment(
        "spawn_agent",
        "SpawnBase public API, pattern compilation, buffer, before/after, and match-state specialist",
        "spawn_api_state_layer",
        ["pexpect/spawnbase.py"],
        [
            "tests/test_expect.py",
            "tests/test_popen_spawn.py",
        ],
    ),
    assignment(
        "transport_agent",
        "pty, popen, and async transport read/write/EOF/TIMEOUT specialist",
        "transport_layer",
        [
            "pexpect/_async.py",
            "pexpect/_async_pre_await.py",
            "pexpect/_async_w_await.py",
            "pexpect/popen_spawn.py",
            "pexpect/pty_spawn.py",
        ],
        [
            "tests/test_popen_spawn.py",
            "tests/test_async.py",
        ],
    ),
    assignment(
        "wrapper_agent",
        "run and replwrap high-level wrapper specialist",
        "wrapper_layer",
        [
            "pexpect/replwrap.py",
            "pexpect/run.py",
        ],
        [
            "tests/test_run.py",
            "tests/test_async.py::AsyncTests::test_async_replwrap",
            "tests/test_async.py::AsyncTests::test_async_replwrap_multiline",
        ],
    ),
]


def scenario(mode: str, communication: str, concurrent: bool, profile: str, integration: str, delivery: str) -> dict:
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
        "scenario_id": f"commit0-pexpect.{mode.replace('_', '-')}.v0.3",
        "schema_version": "0.3",
        "shared_agent_scaffold": "iterative-inspect-edit-test-repair",
        "step_budget_per_agent": 34,
        "task_id": TASK_ID,
        "test_budget_per_agent": 12,
        "token_budget_per_agent": 85000,
        "wall_clock_budget_seconds": 3600,
    }


def task_record() -> dict:
    return {
        "annotation_provenance": [],
        "candidate_evidence_file": AUDIT,
        "dependency_annotations": DEPENDENCIES,
        "evaluator_command": EVALUATOR_COMMAND,
        "inclusion_decision": None,
        "natural_subproblems": NATURAL_SUBPROBLEMS,
        "notes": [
            "Task source and tests are unchanged; only import/bootstrap overlays are applied.",
            "The local master/commit0 branch is complete. Benchmark workspaces must be materialized from origin/commit0_combined.",
            "The evaluator follows the audit recommendation to focus on expect/search semantics, SpawnBase state, pty/popen transports, run, and async wrappers.",
            "Terminal-emulation and pxssh tests are intentionally out of scope for this v0.3 task.",
            "The proposed label is a draft curation decision and not a final independent annotation.",
        ],
        "problem_statement": (
            "Restore the scoped Pexpect expect/search, SpawnBase, transport, run, and async wrapper behavior exercised by the public Commit0 tests without modifying the tests.\n\n"
            "The expect/search layer must implement Expecter, searcher_string, searcher_re, EOF/TIMEOUT matching, freshlen, searchwindowsize, and match-loop behavior. "
            "The SpawnBase layer must consume that contract to implement pattern compilation, expect, expect_list, expect_exact, read/readline, and before/after/match/buffer state. "
            "The transport layer must provide pty, popen, and async read/write/close behavior with consistent bytes/text and EOF/TIMEOUT semantics. "
            "The wrapper layer must consume SpawnBase and transport behavior in run and replwrap helpers.\n\n"
            "The initial benchmark source is the stripped Commit0-style ref origin/commit0_combined, plus a checksum-recorded bootstrap overlay that only makes the public tests importable and collectable."
        ),
        "proposed_parallelizability_label": "partially_parallelizable",
        "publicly_implicated_modules": PUBLIC_MODULES,
        "qualification_label": None,
        "qualification_status": "pending_independent_annotation",
        "quality_evidence_file": "manifests/pilot/v0.3/quality/commit0_pexpect.json",
        "repository": "commit0/pexpect",
        "schema_version": "0.3",
        "source_materialization": (
            f"git archive of the stripped Commit0-style pexpect ref {BASE_REF} at {STRIPPED_SHA}, plus checksum-recorded import/bootstrap overlays in configs/tasks/commit0_curated_tasks.v0.3.json"
        ),
        "task_id": TASK_ID,
        "task_source": "Commit0",
        "test_targets": TEST_TARGETS,
        "upstream_version": STRIPPED_SHA,
    }


def scenario_record() -> dict:
    return {
        "scenarios": [
            scenario("iterative_single", "not_applicable", False, "complete-task", "Agent submits its final workspace.", "No inter-agent messages."),
            scenario("serial_specialists", "completed_artifact_handoff", False, "private-workspace", "Apply expect/search and transport artifacts before SpawnBase integration, then wrapper artifacts, then run the scoped evaluator.", "Specialists run with barrier synchronization. Spawn receives expect/search and transport artifacts before final validation; wrappers receive SpawnBase artifacts."),
            scenario("async_private", "private_concurrent_workspaces", True, "private-workspace", "Integrate independently produced specialist artifacts at the end, then run dependency probes and the scoped evaluator.", "Agents work concurrently without messages while expect, transport, and wrapper assumptions may become stale."),
            scenario("async_message", "asynchronous_message_handoff", True, "message-passing", "Integrate independently produced specialist artifacts after asynchronous handoffs, then run dependency probes and the scoped evaluator.", "Agents may send artifact summaries asynchronously; downstream workers are not guaranteed to see the newest expect/search or transport contract before acting."),
        ],
        "schema_version": "0.3",
        "task_id": TASK_ID,
    }


def quality_record() -> dict:
    return {
        "coordination_structure_tags": ["interface_dependency", "shared_abstraction", "shared_state"],
        "environment_requirements": [
            "Python 3.10.12",
            "pytest==9.0.3",
            "ptyprocess==0.7.0",
            "POSIX-like environment with pty support",
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD=1",
            "Run from the repository root with PYTHONPATH=.",
            "Use origin/commit0_combined plus bootstrap overlays from configs/tasks/commit0_curated_tasks.v0.3.json.",
        ],
        "evaluation_snapshots": [
            {
                "collected": 77,
                "command": EVALUATOR_COMMAND,
                "dependency_versions": {"ptyprocess": "0.7.0", "pytest": "9.0.3"},
                "duration_seconds": 1.10,
                "errors": 0,
                "evidence_scope": "public_initial_state",
                "failed": 63,
                "notes": [
                    "Verified with PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 and PYTHONPATH=<materialized-root> after applying only checksum-recorded bootstrap overlays.",
                    "Failures are caused by unfinished Expecter/searcher, SpawnBase, transport, run, replwrap, and async behavior.",
                ],
                "passed": 14,
                "python_version": "3.10.12",
                "return_code": 1,
                "schema_version": "0.3",
                "skipped": 0,
                "snapshot_id": "curated_commit0_initial_expect_transport_evaluator",
                "source_ref": f"{BASE_REF}:{STRIPPED_SHA}+bootstrap-overlays",
            },
            {
                "collected": 77,
                "command": EVALUATOR_COMMAND,
                "dependency_versions": {"ptyprocess": "0.7.0", "pytest": "9.0.3"},
                "duration_seconds": 62.01,
                "errors": 0,
                "evidence_scope": "evaluator_sanity_only",
                "failed": 0,
                "notes": [
                    "The complete local master/commit0 ref passes the same scoped evaluator in the same environment.",
                    "The complete ref is evaluator validation only and must not define decomposition, prompts, or agent-visible evidence.",
                ],
                "passed": 77,
                "python_version": "3.10.12",
                "return_code": 0,
                "schema_version": "0.3",
                "skipped": 0,
                "snapshot_id": "complete_commit0_expect_transport_evaluator_sanity",
                "source_ref": f"master:{COMPLETE_SHA}",
            },
        ],
        "known_limitations": [
            "The local master/commit0 branch is complete. Benchmark workspaces must be materialized from origin/commit0_combined.",
            "Raw origin/commit0_combined collection fails before bootstrap overlays because SpawnBase.buffer references missing property accessors.",
            "The bootstrap overlay only makes the public tests importable and collectable; it does not implement SpawnBase buffer behavior.",
            "The evaluator uses POSIX process-control behavior and should be run in a frozen POSIX-like environment with ptyprocess installed.",
            "pxssh, ANSI, screen, socket_pexpect, and terminal-emulation tests are excluded from this scoped task.",
            "Single-agent and multi-agent model results are evaluation outputs to report, not dataset qualification gates.",
        ],
        "public_statement_sources": [
            "README.rst@origin/commit0_combined",
            "pexpect/*.py docstrings@origin/commit0_combined",
            "tests/test_*.py@origin/commit0_combined",
            AUDIT,
        ],
        "quality_status": "qualification_ready",
        "remaining_gates": ["two independent human inclusion/exclusion annotations"],
        "schema_version": "0.3",
        "structure_rationale": "pexpect exposes semantic async dependencies between searcher/Expecter matching, SpawnBase public state, transport read/write behavior, and high-level run/replwrap/async wrappers. Downstream workers can make stale assumptions about bytes/text matching, EOF/TIMEOUT as exceptions or patterns, buffer windows, before/after/match state, or transport output normalization.",
        "task_id": TASK_ID,
        "test_groups": [
            {"command": EVALUATOR_COMMAND[:6] + ["tests/test_expect.py"], "description": "Core expect/search, SpawnBase buffer, before/after/match, and pty-backed expect behavior.", "group_id": "expect_spawn_local", "owner_subproblem": "expect_search_layer", "prerequisites": [], "purpose": "specialist_local", "schema_version": "0.3"},
            {"command": EVALUATOR_COMMAND[:6] + ["tests/test_popen_spawn.py"], "description": "Popen transport read/write/EOF/TIMEOUT behavior through SpawnBase expect APIs.", "group_id": "popen_transport_local", "owner_subproblem": "transport_layer", "prerequisites": [], "purpose": "specialist_local", "schema_version": "0.3"},
            {"command": EVALUATOR_COMMAND[:6] + ["tests/test_run.py"], "description": "run helper behavior consuming SpawnBase and transport contracts.", "group_id": "run_wrapper_local", "owner_subproblem": "wrapper_layer", "prerequisites": [], "purpose": "specialist_local", "schema_version": "0.3"},
            {"command": EVALUATOR_COMMAND[:6] + ["tests/test_expect.py::ExpectTestCase::test_searchwindowsize", "tests/test_expect.py::ExpectTestCase::test_before_after"], "description": "SpawnBase state after expect/search window and buffer contracts are integrated.", "group_id": "expect_spawn_cross_contract", "owner_subproblem": None, "prerequisites": ["expect_search_layer artifact is integrated", "spawn_api_state_layer artifact is integrated"], "purpose": "cross_subproblem", "schema_version": "0.3"},
            {"command": EVALUATOR_COMMAND[:6] + ["tests/test_popen_spawn.py::ExpectTestCase::test_expect", "tests/test_run.py::RunFuncTestCase::test_run"], "description": "Wrapper behavior after SpawnBase and transport contracts are integrated.", "group_id": "transport_spawn_wrapper_cross_contract", "owner_subproblem": None, "prerequisites": ["transport_layer artifact is integrated", "spawn_api_state_layer artifact is integrated", "wrapper_layer artifact is integrated"], "purpose": "cross_subproblem", "schema_version": "0.3"},
            {"command": EVALUATOR_COMMAND, "description": "Full scoped expect/transport evaluator.", "group_id": "full_scoped_evaluator", "owner_subproblem": None, "prerequisites": ["expect_search_layer artifact is integrated", "spawn_api_state_layer artifact is integrated", "transport_layer artifact is integrated", "wrapper_layer artifact is integrated"], "purpose": "full_evaluator", "schema_version": "0.3"},
        ],
    }


def metrics_record() -> dict:
    dependency_points = [
        {
            "consumer_agent": "spawn_agent",
            "consumer_files": ["pexpect/spawnbase.py"],
            "consumer_subproblem": "spawn_api_state_layer",
            "contract_summary": "Expecter and searcher matching semantics must be stable for SpawnBase.expect, expect_exact, before/after/match, buffer, and searchwindowsize behavior.",
            "dependency_id": "pexpect.expect_to_spawn.match_state_contract",
            "dependency_type": "interface_dependency",
            "downstream_probe_tests": ["tests/test_expect.py::ExpectTestCase::test_before_after", "tests/test_expect.py::ExpectTestCase::test_searchwindowsize"],
            "integrated_probe_tests": ["tests/test_expect.py::ExpectTestCase::test_expect_order", "tests/test_expect.py::ExpectTestCase::test_before_after", "tests/test_expect.py::ExpectTestCase::test_searchwindowsize"],
            "metrics_enabled": ["ADPR", "DRS", "CAIL", "SAD"],
            "primary_paper_probe": True,
            "producer_agent": "expect_agent",
            "producer_files": ["pexpect/expect.py"],
            "producer_subproblem": "expect_search_layer",
            "resolution_criteria": "Resolved when expect/search ordering, buffer state, and search window probes pass in the integrated workspace.",
            "stale_failure_mode": "The SpawnBase agent may update before/after/match or buffer state around stale searcher return semantics or search window assumptions.",
            "upstream_probe_tests": ["tests/test_expect.py::ExpectTestCase::test_expect_order", "tests/test_expect.py::ExpectTestCase::test_ordering"],
        },
        {
            "consumer_agent": "spawn_agent",
            "consumer_files": ["pexpect/spawnbase.py"],
            "consumer_subproblem": "spawn_api_state_layer",
            "contract_summary": "pty and popen transports must present read_nonblocking, EOF, TIMEOUT, bytes/text, and CRLF behavior that SpawnBase and Expecter consume consistently.",
            "dependency_id": "pexpect.transport_to_spawn.read_timeout_contract",
            "dependency_type": "shared_api_contract",
            "downstream_probe_tests": ["tests/test_expect.py::ExpectTestCase::test_expect_timeout", "tests/test_expect.py::ExpectTestCase::test_unexpected_eof"],
            "integrated_probe_tests": ["tests/test_popen_spawn.py::ExpectTestCase::test_expect", "tests/test_popen_spawn.py::ExpectTestCase::test_crlf", "tests/test_expect.py::ExpectTestCase::test_expect_timeout", "tests/test_expect.py::ExpectTestCase::test_unexpected_eof"],
            "metrics_enabled": ["ADPR", "DRS", "CAIL", "SAD"],
            "producer_agent": "transport_agent",
            "producer_files": ["pexpect/popen_spawn.py", "pexpect/pty_spawn.py", "pexpect/_async.py"],
            "producer_subproblem": "transport_layer",
            "resolution_criteria": "Resolved when transport probes and SpawnBase EOF/TIMEOUT consumer probes pass together after integration.",
            "stale_failure_mode": "SpawnBase or Expecter code may assume stale transport output type, line ending, EOF, or timeout behavior.",
            "upstream_probe_tests": ["tests/test_popen_spawn.py::ExpectTestCase::test_expect", "tests/test_popen_spawn.py::ExpectTestCase::test_crlf"],
        },
        {
            "consumer_agent": "wrapper_agent",
            "consumer_files": ["pexpect/run.py", "pexpect/replwrap.py"],
            "consumer_subproblem": "wrapper_layer",
            "contract_summary": "run, replwrap, and async wrappers must consume SpawnBase expect/read behavior, EOF/TIMEOUT handling, callback events, and transport output normalization consistently.",
            "dependency_id": "pexpect.spawn_to_wrappers.run_async_contract",
            "dependency_type": "shared_state_contract",
            "downstream_probe_tests": ["tests/test_run.py::RunFuncTestCase::test_run", "tests/test_async.py::AsyncTests::test_async_replwrap"],
            "integrated_probe_tests": ["tests/test_expect.py::ExpectTestCase::test_expect", "tests/test_popen_spawn.py::ExpectTestCase::test_expect", "tests/test_run.py::RunFuncTestCase::test_run", "tests/test_async.py::AsyncTests::test_async_replwrap"],
            "metrics_enabled": ["ADPR", "DRS", "CAIL", "SAD"],
            "producer_agent": "spawn_agent",
            "producer_files": ["pexpect/spawnbase.py", "pexpect/popen_spawn.py", "pexpect/pty_spawn.py"],
            "producer_subproblem": "spawn_api_state_layer",
            "resolution_criteria": "Resolved when SpawnBase/transport expect probes and run/replwrap/async wrapper probes pass in the final integrated workspace.",
            "stale_failure_mode": "Wrapper code may duplicate or bypass stale SpawnBase semantics, causing callbacks or async wrappers to disagree with expect behavior.",
            "upstream_probe_tests": ["tests/test_expect.py::ExpectTestCase::test_expect", "tests/test_popen_spawn.py::ExpectTestCase::test_expect"],
        },
    ]
    return {
        "aggregate_metrics": {
            "ADPR_denominator": "All dependency_points unless a paper section explicitly reports primary_async_dependency_ids only.",
            "dependency_point_count": 3,
            "minimum_success_condition_for_task_level_async_dependency_resolution": "All primary_async_dependency_ids pass in the final integrated workspace.",
            "primary_async_dependency_ids": [item["dependency_id"] for item in dependency_points],
            "primary_paper_dependency_id": "pexpect.expect_to_spawn.match_state_contract",
        },
        "annotation_notes": [
            "The expect_to_spawn dependency is the primary signal because SpawnBase public state is highly sensitive to stale searcher and Expecter matching semantics.",
            "The transport_to_spawn dependency captures stale assumptions around read_nonblocking, EOF/TIMEOUT, CRLF, and output type behavior.",
            "The spawn_to_wrappers dependency captures stale assumptions in run, replwrap, and async wrappers.",
            "These labels identify public test-observable contracts, not solution code.",
        ],
        "dependency_points": dependency_points,
        "evaluation_checkpoint_policy": {
            "checkpoint_record_fields": ["run_id", "scenario_id", "checkpoint_id", "logical_iteration", "agent_id", "visible_upstream_artifact_version", "integrated_workspace_version", "probe_test_results"],
            "minimum_policy": "Run probe tests after each agent final artifact and after final integration.",
            "recommended_policy": "Run probe tests after every committed patch, every explicit artifact transfer, and final integration.",
        },
        "metric_annotation_id": "commit0-pexpect.async-metrics.v0.3",
        "metric_definitions": {
            "ADPR": {"definition": "Fraction of registered dependency_points whose required integrated_probe_tests pass in the final integrated workspace.", "name": "Async Dependency Pass Rate", "unit": "fraction"},
            "CAIL": {"definition": "downstream_resolution_step minus upstream_resolution_step when both probe groups have been evaluated.", "name": "Cross-Agent Integration Lag", "unit": "agent iteration or evaluation checkpoint"},
            "DRS": {"definition": "First recorded checkpoint at which all required integrated_probe_tests for a dependency point pass.", "name": "Dependency Resolution Step", "unit": "agent iteration or evaluation checkpoint"},
            "SAD": {"definition": "Interval during which a downstream worker acts on a contract assumption inconsistent with the latest upstream artifact.", "name": "Stale Assumption Duration", "unit": "agent iteration or event interval"},
        },
        "purpose": "Dependency-level labels for measuring whether asynchronous multi-agent coding resolves Pexpect expect/search, SpawnBase state, transport, run, and async wrapper contracts.",
        "schema_version": "0.3-async-metrics",
        "source_quality_record": "manifests/pilot/v0.3/quality/commit0_pexpect.json",
        "source_task_record": "manifests/pilot/v0.3/tasks/commit0_pexpect.json",
        "task_id": TASK_ID,
    }


def annotation_form(annotator_id: str) -> dict:
    return {
        "allowed_labels": ["parallelizable", "partially_parallelizable", "effectively_serial"],
        "annotator_id": annotator_id,
        "candidate_evidence_file": AUDIT,
        "exclusion_reason": None,
        "include": None,
        "independence_instructions": [
            "Use only public Commit0 evidence, the audit note, and the draft task record.",
            "Review the linked TaskQualityRecord, including the POSIX/ptyprocess environment requirement and checksum-recorded bootstrap overlay.",
            "Do not inspect reference branches, solution patches, or diffs.",
            "Do not consult the other annotator before submitting.",
            "Explicitly assess whether the expect/search -> SpawnBase -> transport/wrapper split is a natural AsynCodeBench dependency rather than artificial file partitioning.",
            "Explicitly assess whether excluding pxssh, ANSI, screen, socket_pexpect, and terminal-emulation tests is appropriate for this scoped expect/transport task.",
        ],
        "parallelizability_label": None,
        "rationale": None,
        "schema_version": "0.3",
        "task_id": TASK_ID,
        "task_record_file": "manifests/pilot/v0.3/tasks/commit0_pexpect.json",
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
            "repository": "pexpect",
            "base_ref": BASE_REF,
            "base_sha": STRIPPED_SHA,
            "overlays": overlays(),
        }
    )
    write_json(path, payload)


def main() -> None:
    files = {
        Path("manifests/pilot/v0.3/tasks/commit0_pexpect.json"): task_record(),
        Path("manifests/pilot/v0.3/scenarios/commit0_pexpect.json"): scenario_record(),
        Path("manifests/pilot/v0.3/quality/commit0_pexpect.json"): quality_record(),
        Path("manifests/pilot/v0.3/metrics/commit0_pexpect_async_metrics.json"): metrics_record(),
        Path("manifests/annotations/commit0_v0.3/pexpect/annotator_a.json"): annotation_form("annotator_a"),
        Path("manifests/annotations/commit0_v0.3/pexpect/annotator_b.json"): annotation_form("annotator_b"),
        Path("manifests/annotations/commit0_v0.3/pexpect/adjudication.template.json"): adjudication_template(),
    }
    for path, payload in files.items():
        write_json(path, payload)
    update_curated_config()
    for path in files:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload["task_id"] != TASK_ID:
            raise ValueError(f"unexpected task_id in {path}: {payload['task_id']}")
    print(f"generated {TASK_ID} v0.3 manifest files")


if __name__ == "__main__":
    main()
