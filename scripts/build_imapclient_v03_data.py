"""Generate and validate the v0.3 Commit0 imapclient task records."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


TASK_ID = "commit0:imapclient"
STRIPPED_SHA = "7ca5a23640bcb0b102673eaaf5eaa6e7fcebd76b"
COMPLETE_SHA = "391cc6d66d35c16bed11292ff00835646cd50ae5"
BASE_REF = "origin/commit0_combined"
AUDIT = "docs/audits/COMMIT0_CANDIDATE_REVIEW_chardet_dnspython_imapclient_v0.3.md"

EVALUATOR_COMMAND = [
    "python3.10",
    "-m",
    "pytest",
    "-q",
    "-o",
    "addopts=",
    "tests/test_response_lexer.py",
    "tests/test_response_parser.py",
    "tests/test_imapclient.py",
    "tests/test_search.py",
    "tests/test_folder_status.py",
    "tests/test_store.py",
    "tests/test_datetime_util.py",
    "tests/test_imap_utf7.py",
    "tests/test_util_functions.py",
]
TEST_TARGETS = EVALUATOR_COMMAND[6:]
PUBLIC_MODULES = [
    "imapclient/datetime_util.py",
    "imapclient/fixed_offset.py",
    "imapclient/imap_utf7.py",
    "imapclient/imapclient.py",
    "imapclient/response_lexer.py",
    "imapclient/response_parser.py",
    "imapclient/response_types.py",
    "imapclient/util.py",
    "imapclient/version.py",
]
OVERLAY_RATIONALES = {
    "0001-util-import-bootstrap.patch": "Expose only util symbols imported by lexer/client modules and public tests: assert_imap_protocol, to_bytes, to_unicode, and chunk. The helper bodies remain unfinished placeholders.",
    "0002-class-import-bootstrap.patch": "Allow public class/module construction by making require_capability an identity decorator and exposing datetime_to_native as an unfinished placeholder. Capability checks and datetime normalization remain unfinished.",
    "0003-iteritems-import-bootstrap.patch": "Expose only the iteritems name used by _dict_bytes_normaliser during class construction. Dictionary normalization behavior remains unfinished.",
    "0004-public-helper-import-bootstrap.patch": "Expose version string, quota parsing, and search normalization helper names imported by public tests. The helper bodies remain unfinished placeholders.",
    "0005-text-helper-import-bootstrap.patch": "Expose text-list and parenthesized-string helper names imported by public utility tests. Text normalization behavior remains unfinished.",
}

DEPENDENCIES = [
    {
        "consumer_subproblem": "response_parser_layer",
        "dependency_type": "api_contract",
        "description": "Response parser behavior consumes lexer tokenization, literal handling, IMAP protocol assertion, and bytes/text utility contracts.",
        "evidence_paths": [
            "imapclient/response_lexer.py",
            "imapclient/util.py",
            "imapclient/response_parser.py",
            "tests/test_response_lexer.py",
            "tests/test_response_parser.py",
        ],
        "producer_subproblem": "utility_lexer_layer",
        "schema_version": "0.3",
    },
    {
        "consumer_subproblem": "client_command_layer",
        "dependency_type": "api_contract",
        "description": "High-level IMAPClient search, fetch, folder, status, and store behavior consumes typed parsed response shapes from response_parser and response_types.",
        "evidence_paths": [
            "imapclient/response_parser.py",
            "imapclient/response_types.py",
            "imapclient/imapclient.py",
            "tests/test_response_parser.py",
            "tests/test_search.py",
            "tests/test_folder_status.py",
            "tests/test_store.py",
            "tests/test_imapclient.py",
        ],
        "producer_subproblem": "response_parser_layer",
        "schema_version": "0.3",
    },
    {
        "consumer_subproblem": "client_command_layer",
        "dependency_type": "shared_state_contract",
        "description": "Client command construction and response normalization consume IMAP UTF-7, date formatting, bytes/text conversion, and fixed-offset datetime contracts.",
        "evidence_paths": [
            "imapclient/imap_utf7.py",
            "imapclient/datetime_util.py",
            "imapclient/fixed_offset.py",
            "imapclient/util.py",
            "imapclient/imapclient.py",
            "tests/test_imap_utf7.py",
            "tests/test_datetime_util.py",
            "tests/test_util_functions.py",
            "tests/test_search.py",
            "tests/test_imapclient.py",
        ],
        "producer_subproblem": "utility_lexer_layer",
        "schema_version": "0.3",
    },
]
NATURAL_SUBPROBLEMS = {
    "client_command_layer": [
        "imapclient/imapclient.py",
        "imapclient/testable_imapclient.py",
        "tests/test_imapclient.py",
        "tests/test_search.py",
        "tests/test_folder_status.py",
        "tests/test_store.py",
    ],
    "response_parser_layer": [
        "imapclient/response_parser.py",
        "imapclient/response_types.py",
        "tests/test_response_parser.py",
    ],
    "utility_lexer_layer": [
        "imapclient/datetime_util.py",
        "imapclient/fixed_offset.py",
        "imapclient/imap_utf7.py",
        "imapclient/response_lexer.py",
        "imapclient/util.py",
        "tests/test_response_lexer.py",
        "tests/test_datetime_util.py",
        "tests/test_imap_utf7.py",
        "tests/test_util_functions.py",
    ],
}


def _overlays() -> list[dict]:
    entries = []
    for path in sorted(Path("data/overlays/commit0/imapclient").glob("*.patch")):
        entries.append(
            {
                "path": path.as_posix(),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "rationale": OVERLAY_RATIONALES[path.name],
            }
        )
    return entries


def _assignment(agent_id: str, role: str, subproblem_id: str, writable_paths: list[str], tests: list[str]) -> dict:
    return {
        "agent_id": agent_id,
        "primary_test_targets": tests,
        "role": role,
        "schema_version": "0.3",
        "subproblem_id": subproblem_id,
        "writable_paths": writable_paths,
    }


ASSIGNMENTS = [
    _assignment(
        "utility_lexer_agent",
        "IMAP lexer, UTF-7, datetime, fixed-offset, and utility helper specialist",
        "utility_lexer_layer",
        [
            "imapclient/datetime_util.py",
            "imapclient/fixed_offset.py",
            "imapclient/imap_utf7.py",
            "imapclient/response_lexer.py",
            "imapclient/util.py",
        ],
        [
            "tests/test_response_lexer.py",
            "tests/test_datetime_util.py",
            "tests/test_imap_utf7.py",
            "tests/test_util_functions.py",
        ],
    ),
    _assignment(
        "parser_agent",
        "IMAP response parser and typed response object specialist",
        "response_parser_layer",
        [
            "imapclient/response_parser.py",
            "imapclient/response_types.py",
        ],
        ["tests/test_response_parser.py"],
    ),
    _assignment(
        "client_agent",
        "high-level IMAPClient command, folder, search, status, and store specialist",
        "client_command_layer",
        [
            "imapclient/imapclient.py",
            "imapclient/testable_imapclient.py",
        ],
        [
            "tests/test_imapclient.py",
            "tests/test_search.py",
            "tests/test_folder_status.py",
            "tests/test_store.py",
        ],
    ),
]


def _scenario(mode: str, communication: str, concurrent: bool, profile: str, integration: str, delivery: str) -> dict:
    assignments = ASSIGNMENTS
    agent_count = 3
    if mode == "iterative_single":
        assignments = [
            _assignment(
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
        "scenario_id": f"commit0-imapclient.{mode.replace('_', '-')}.v0.3",
        "schema_version": "0.3",
        "shared_agent_scaffold": "iterative-inspect-edit-test-repair",
        "step_budget_per_agent": 34,
        "task_id": TASK_ID,
        "test_budget_per_agent": 12,
        "token_budget_per_agent": 85000,
        "wall_clock_budget_seconds": 3000,
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
            "The evaluator is scoped to response lexer/parser, typed responses, and high-level IMAPClient command behavior.",
            "The proposed label is a draft curation decision and not a final independent annotation.",
        ],
        "problem_statement": (
            "Restore the scoped IMAPClient lexer, response parser, typed response, utility, and high-level client command behavior exercised by the public Commit0 tests without modifying the tests.\n\n"
            "The utility/lexer layer must implement tokenization, literal handling, IMAP UTF-7, datetime/fixed-offset conversion, bytes/text helpers, and command formatting helpers. "
            "The parser layer must consume lexer and utility contracts to implement parse_response, parse_message_list, parse_fetch_response, and typed Address/Envelope/BodyData/SearchIds outputs. "
            "The client command layer must consume those typed parser outputs and utility contracts to implement search, fetch-related normalization, folder/status/store behavior, quota helpers, capabilities, raw commands, and command argument construction.\n\n"
            "The initial benchmark source is the stripped Commit0-style ref origin/commit0_combined, plus checksum-recorded bootstrap overlays that only make public tests importable and collectable."
        ),
        "proposed_parallelizability_label": "partially_parallelizable",
        "publicly_implicated_modules": PUBLIC_MODULES,
        "qualification_label": None,
        "qualification_status": "pending_independent_annotation",
        "quality_evidence_file": "manifests/pilot/v0.3/quality/commit0_imapclient.json",
        "repository": "commit0/imapclient",
        "schema_version": "0.3",
        "source_materialization": (
            f"git archive of the stripped Commit0-style imapclient ref {BASE_REF} at {STRIPPED_SHA}, plus checksum-recorded import/bootstrap overlays in configs/tasks/commit0_curated_tasks.v0.3.json"
        ),
        "task_id": TASK_ID,
        "task_source": "Commit0",
        "test_targets": TEST_TARGETS,
        "upstream_version": STRIPPED_SHA,
    }


def scenario_record() -> dict:
    return {
        "scenarios": [
            _scenario("iterative_single", "not_applicable", False, "complete-task", "Agent submits its final workspace.", "No inter-agent messages."),
            _scenario("serial_specialists", "completed_artifact_handoff", False, "private-workspace", "Apply utility/lexer artifacts before parser artifacts, then client artifacts, then run the scoped evaluator.", "Specialists run with barrier synchronization. Parser receives utility/lexer artifacts; client receives parser and utility artifacts before final validation."),
            _scenario("async_private", "private_concurrent_workspaces", True, "private-workspace", "Integrate independently produced specialist artifacts at the end, then run dependency probes and the scoped evaluator.", "Agents work concurrently without messages while parser/client contract assumptions may become stale."),
            _scenario("async_message", "asynchronous_message_handoff", True, "message-passing", "Integrate independently produced specialist artifacts after asynchronous handoffs, then run dependency probes and the scoped evaluator.", "Agents may send artifact summaries asynchronously; downstream workers are not guaranteed to see the newest parser or utility contract before acting."),
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
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD=1",
            "Run from the repository root with PYTHONPATH=.",
            "Use origin/commit0_combined plus bootstrap overlays from configs/tasks/commit0_curated_tasks.v0.3.json.",
        ],
        "evaluation_snapshots": [
            {
                "collected": 229,
                "command": EVALUATOR_COMMAND,
                "dependency_versions": {"pytest": "9.0.3"},
                "duration_seconds": 3.95,
                "errors": 0,
                "evidence_scope": "public_initial_state",
                "failed": 229,
                "notes": [
                    "Verified with PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 and PYTHONPATH=<materialized-root> after applying only checksum-recorded bootstrap overlays.",
                    "Failures are caused by unfinished lexer, parser, typed response, datetime, UTF-7, utility, and client command behavior.",
                ],
                "passed": 0,
                "python_version": "3.10.12",
                "return_code": 1,
                "schema_version": "0.3",
                "skipped": 0,
                "snapshot_id": "curated_commit0_initial_response_client_evaluator",
                "source_ref": f"{BASE_REF}:{STRIPPED_SHA}+bootstrap-overlays",
            },
            {
                "collected": 229,
                "command": EVALUATOR_COMMAND,
                "dependency_versions": {"pytest": "9.0.3"},
                "duration_seconds": 0.44,
                "errors": 0,
                "evidence_scope": "evaluator_sanity_only",
                "failed": 0,
                "notes": [
                    "The complete local master/commit0 ref passes the same scoped evaluator in the same environment.",
                    "The complete ref is evaluator validation only and must not define decomposition, prompts, or agent-visible evidence.",
                ],
                "passed": 229,
                "python_version": "3.10.12",
                "return_code": 0,
                "schema_version": "0.3",
                "skipped": 0,
                "snapshot_id": "complete_commit0_response_client_evaluator_sanity",
                "source_ref": f"master:{COMPLETE_SHA}",
            },
        ],
        "known_limitations": [
            "The local master/commit0 branch is complete. Benchmark workspaces must be materialized from origin/commit0_combined.",
            "Raw origin/commit0_combined collection fails before bootstrap overlays because public imports need utility, decorator, datetime, iteritems, version, and helper symbols.",
            "Bootstrap overlays only make the public tests importable and collectable; they do not implement lexer, parser, UTF-7, datetime, command, quota, search, or store behavior.",
            "Several bootstrap symbols are directly tested utility helpers. Human review should explicitly verify that the released task scope remains parser/client integration rather than hidden utility implementation.",
            "Single-agent and multi-agent model results are evaluation outputs to report, not dataset qualification gates.",
        ],
        "public_statement_sources": [
            "README.rst@origin/commit0_combined",
            "imapclient/*.py docstrings@origin/commit0_combined",
            "tests/test_*.py@origin/commit0_combined",
            AUDIT,
        ],
        "quality_status": "qualification_ready",
        "remaining_gates": ["two independent human inclusion/exclusion annotations"],
        "schema_version": "0.3",
        "structure_rationale": "imapclient exposes semantic async dependencies between lexer/utility token contracts, typed parser outputs, and high-level client commands. Downstream client workers can make stale assumptions about SearchIds.modseq, fetch response keys, UID-vs-message-id semantics, bytes/str normalization, or date/UTF-7 conversion that only fail after parser and client tests integrate.",
        "task_id": TASK_ID,
        "test_groups": [
            {"command": EVALUATOR_COMMAND[:6] + ["tests/test_response_lexer.py", "tests/test_datetime_util.py", "tests/test_imap_utf7.py", "tests/test_util_functions.py"], "description": "Lexer, IMAP UTF-7, datetime/fixed-offset, and utility command formatting behavior.", "group_id": "utility_lexer_local", "owner_subproblem": "utility_lexer_layer", "prerequisites": [], "purpose": "specialist_local", "schema_version": "0.3"},
            {"command": EVALUATOR_COMMAND[:6] + ["tests/test_response_parser.py"], "description": "IMAP response parsing, typed response objects, message lists, and fetch response shape.", "group_id": "response_parser_local", "owner_subproblem": "response_parser_layer", "prerequisites": [], "purpose": "specialist_local", "schema_version": "0.3"},
            {"command": EVALUATOR_COMMAND[:6] + ["tests/test_imapclient.py", "tests/test_search.py", "tests/test_folder_status.py", "tests/test_store.py"], "description": "High-level IMAPClient command construction and response normalization behavior.", "group_id": "client_command_local", "owner_subproblem": "client_command_layer", "prerequisites": [], "purpose": "specialist_local", "schema_version": "0.3"},
            {"command": EVALUATOR_COMMAND[:6] + ["tests/test_response_lexer.py::TestTokenSource::test_literal", "tests/test_response_parser.py::TestParseResponse::test_literal"], "description": "Parser behavior after lexer literal-token contracts are integrated.", "group_id": "lexer_parser_cross_contract", "owner_subproblem": None, "prerequisites": ["utility_lexer_layer artifact is integrated", "response_parser_layer artifact is integrated"], "purpose": "cross_subproblem", "schema_version": "0.3"},
            {"command": EVALUATOR_COMMAND[:6] + ["tests/test_response_parser.py::TestParseMessageList::test_modseq", "tests/test_search.py::TestSearch::test_modseq"], "description": "Client search behavior after parser SearchIds/modseq contracts are integrated.", "group_id": "parser_client_search_cross_contract", "owner_subproblem": None, "prerequisites": ["response_parser_layer artifact is integrated", "client_command_layer artifact is integrated"], "purpose": "cross_subproblem", "schema_version": "0.3"},
            {"command": EVALUATOR_COMMAND, "description": "Full scoped response/client evaluator.", "group_id": "full_scoped_evaluator", "owner_subproblem": None, "prerequisites": ["utility_lexer_layer artifact is integrated", "response_parser_layer artifact is integrated", "client_command_layer artifact is integrated"], "purpose": "full_evaluator", "schema_version": "0.3"},
        ],
    }


def metrics_record() -> dict:
    dependency_points = [
        {
            "consumer_agent": "parser_agent",
            "consumer_files": ["imapclient/response_parser.py", "imapclient/response_types.py"],
            "consumer_subproblem": "response_parser_layer",
            "contract_summary": "Lexer tokenization, literal handling, and IMAP protocol assertion contracts must be stable before parser tuple and typed-object parsing can be correct.",
            "dependency_id": "imapclient.lexer_to_parser.token_literal_contract",
            "dependency_type": "shared_api_contract",
            "downstream_probe_tests": ["tests/test_response_parser.py::TestParseResponse::test_literal", "tests/test_response_parser.py::TestParseResponse::test_tuple"],
            "integrated_probe_tests": ["tests/test_response_lexer.py::TestTokenSource::test_literal", "tests/test_response_lexer.py::TestTokenSource::test_quoted_strings", "tests/test_response_parser.py::TestParseResponse::test_literal", "tests/test_response_parser.py::TestParseResponse::test_tuple"],
            "metrics_enabled": ["ADPR", "DRS", "CAIL", "SAD"],
            "producer_agent": "utility_lexer_agent",
            "producer_files": ["imapclient/response_lexer.py", "imapclient/util.py"],
            "producer_subproblem": "utility_lexer_layer",
            "resolution_criteria": "Resolved when lexer literal/string probes and parser literal/tuple probes pass in the integrated workspace.",
            "stale_failure_mode": "The parser agent may implement parsing around stale token boundary, literal, or protocol assertion behavior.",
            "upstream_probe_tests": ["tests/test_response_lexer.py::TestTokenSource::test_literal", "tests/test_response_lexer.py::TestTokenSource::test_quoted_strings"],
        },
        {
            "consumer_agent": "client_agent",
            "consumer_files": ["imapclient/imapclient.py"],
            "consumer_subproblem": "client_command_layer",
            "contract_summary": "High-level IMAPClient search/fetch/status/store behavior must consume SearchIds, fetch dictionaries, UID keys, and typed response objects from the parser consistently.",
            "dependency_id": "imapclient.parser_to_client.typed_response_contract",
            "dependency_type": "interface_dependency",
            "downstream_probe_tests": ["tests/test_search.py::TestSearch::test_modseq", "tests/test_imapclient.py::TestTimeNormalisation::test_pass_through"],
            "integrated_probe_tests": ["tests/test_response_parser.py::TestParseMessageList::test_modseq", "tests/test_response_parser.py::TestParseFetchResponse::test_UID", "tests/test_search.py::TestSearch::test_modseq", "tests/test_imapclient.py::TestTimeNormalisation::test_pass_through"],
            "metrics_enabled": ["ADPR", "DRS", "CAIL", "SAD"],
            "primary_paper_probe": True,
            "producer_agent": "parser_agent",
            "producer_files": ["imapclient/response_parser.py", "imapclient/response_types.py"],
            "producer_subproblem": "response_parser_layer",
            "resolution_criteria": "Resolved when parser typed response probes and client search/fetch consumer probes pass together after integration.",
            "stale_failure_mode": "The client agent may implement search or fetch normalization around stale parser output shapes, SearchIds.modseq, or UID-vs-message-id semantics.",
            "upstream_probe_tests": ["tests/test_response_parser.py::TestParseMessageList::test_modseq", "tests/test_response_parser.py::TestParseFetchResponse::test_UID"],
        },
        {
            "consumer_agent": "client_agent",
            "consumer_files": ["imapclient/imapclient.py"],
            "consumer_subproblem": "client_command_layer",
            "contract_summary": "Client command construction consumes date formatting, IMAP UTF-7 folder encoding, fixed-offset datetime behavior, and bytes/text helper contracts.",
            "dependency_id": "imapclient.utility_to_client.command_normalization_contract",
            "dependency_type": "shared_state_contract",
            "downstream_probe_tests": ["tests/test_search.py::TestSearch::test_with_date", "tests/test_imapclient.py::TestListFolders::test_utf7_decoding"],
            "integrated_probe_tests": ["tests/test_datetime_util.py::TestCriteriaDateFormatting::test_basic", "tests/test_imap_utf7.py::IMAP4UTF7TestCase::test_encode", "tests/test_search.py::TestSearch::test_with_date", "tests/test_imapclient.py::TestListFolders::test_utf7_decoding"],
            "metrics_enabled": ["ADPR", "DRS", "CAIL", "SAD"],
            "producer_agent": "utility_lexer_agent",
            "producer_files": ["imapclient/datetime_util.py", "imapclient/fixed_offset.py", "imapclient/imap_utf7.py", "imapclient/util.py"],
            "producer_subproblem": "utility_lexer_layer",
            "resolution_criteria": "Resolved when utility/date/UTF-7 probes and client command/folder probes pass after integration.",
            "stale_failure_mode": "The client agent may hard-code command argument or folder decoding assumptions that diverge from the utility layer.",
            "upstream_probe_tests": ["tests/test_datetime_util.py::TestCriteriaDateFormatting::test_basic", "tests/test_imap_utf7.py::IMAP4UTF7TestCase::test_encode"],
        },
    ]
    return {
        "aggregate_metrics": {
            "ADPR_denominator": "All dependency_points unless a paper section explicitly reports primary_async_dependency_ids only.",
            "dependency_point_count": 3,
            "minimum_success_condition_for_task_level_async_dependency_resolution": "All primary_async_dependency_ids pass in the final integrated workspace.",
            "primary_async_dependency_ids": [item["dependency_id"] for item in dependency_points],
            "primary_paper_dependency_id": "imapclient.parser_to_client.typed_response_contract",
        },
        "annotation_notes": [
            "The parser_to_client dependency is the primary signal because high-level IMAPClient commands are sensitive to stale typed parser return shapes.",
            "The lexer_to_parser dependency captures stale assumptions around token boundaries and IMAP literal handling.",
            "The utility_to_client dependency captures stale bytes/str, date, and IMAP UTF-7 normalization assumptions.",
            "These labels identify public test-observable contracts, not solution code.",
        ],
        "dependency_points": dependency_points,
        "evaluation_checkpoint_policy": {
            "checkpoint_record_fields": ["run_id", "scenario_id", "checkpoint_id", "logical_iteration", "agent_id", "visible_upstream_artifact_version", "integrated_workspace_version", "probe_test_results"],
            "minimum_policy": "Run probe tests after each agent final artifact and after final integration.",
            "recommended_policy": "Run probe tests after every committed patch, every explicit artifact transfer, and final integration.",
        },
        "metric_annotation_id": "commit0-imapclient.async-metrics.v0.3",
        "metric_definitions": {
            "ADPR": {"definition": "Fraction of registered dependency_points whose required integrated_probe_tests pass in the final integrated workspace.", "name": "Async Dependency Pass Rate", "unit": "fraction"},
            "CAIL": {"definition": "downstream_resolution_step minus upstream_resolution_step when both probe groups have been evaluated.", "name": "Cross-Agent Integration Lag", "unit": "agent iteration or evaluation checkpoint"},
            "DRS": {"definition": "First recorded checkpoint at which all required integrated_probe_tests for a dependency point pass.", "name": "Dependency Resolution Step", "unit": "agent iteration or evaluation checkpoint"},
            "SAD": {"definition": "Interval during which a downstream worker acts on a contract assumption inconsistent with the latest upstream artifact.", "name": "Stale Assumption Duration", "unit": "agent iteration or event interval"},
        },
        "purpose": "Dependency-level labels for measuring whether asynchronous multi-agent coding resolves IMAPClient lexer, parser, typed response, utility normalization, and high-level client command contracts.",
        "schema_version": "0.3-async-metrics",
        "source_quality_record": "manifests/pilot/v0.3/quality/commit0_imapclient.json",
        "source_task_record": "manifests/pilot/v0.3/tasks/commit0_imapclient.json",
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
            "Review the linked TaskQualityRecord, including the requirement to use origin/commit0_combined plus checksum-recorded bootstrap overlays.",
            "Do not inspect reference branches, solution patches, or diffs.",
            "Do not consult the other annotator before submitting.",
            "Explicitly assess whether the utility/lexer -> parser -> client split is a natural AsynCodeBench dependency rather than artificial file partitioning.",
            "Explicitly assess whether the bootstrap overlays are acceptable as non-solution collection prerequisites for the scoped response/client task.",
        ],
        "parallelizability_label": None,
        "rationale": None,
        "schema_version": "0.3",
        "source_task_id": TASK_ID,
        "task_id": TASK_ID.replace("commit0:", "asyncodebench:", 1),
        "task_record_file": "manifests/pilot/v0.3/tasks/commit0_imapclient.json",
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
        "source_task_id": TASK_ID,
        "task_id": TASK_ID.replace("commit0:", "asyncodebench:", 1),
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
            "repository": "imapclient",
            "base_ref": BASE_REF,
            "base_sha": STRIPPED_SHA,
            "overlays": _overlays(),
        }
    )
    write_json(path, payload)


def main() -> None:
    files = {
        Path("manifests/pilot/v0.3/tasks/commit0_imapclient.json"): task_record(),
        Path("manifests/pilot/v0.3/scenarios/commit0_imapclient.json"): scenario_record(),
        Path("manifests/pilot/v0.3/quality/commit0_imapclient.json"): quality_record(),
        Path("manifests/pilot/v0.3/metrics/commit0_imapclient_async_metrics.json"): metrics_record(),
        Path("manifests/annotations/asyncodebench_v0.3/imapclient/annotator_a.json"): annotation_form("annotator_a"),
        Path("manifests/annotations/asyncodebench_v0.3/imapclient/annotator_b.json"): annotation_form("annotator_b"),
        Path("manifests/annotations/asyncodebench_v0.3/imapclient/adjudication.template.json"): adjudication_template(),
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
