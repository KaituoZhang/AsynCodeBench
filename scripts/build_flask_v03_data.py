"""Generate and validate the v0.3 Commit0 Flask task records."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


TASK_ID = "commit0:flask"
STRIPPED_SHA = "af126af63a288df1d4edfe07e82a3b241aa4567a"
COMPLETE_SHA = "2fec0b206c6e83ea813ab26597e15c96fab08be7"
BASE_REF = "origin/commit0_combined"
AUDIT = "docs/audits/COMMIT0_CANDIDATE_REVIEW_babel_geopandas_flask_v0.3.md"

EVALUATOR_COMMAND = [
    "python3.10",
    "-m",
    "pytest",
    "-q",
    "-o",
    "addopts=",
    "tests/test_basic.py",
    "tests/test_reqctx.py",
    "tests/test_appctx.py",
    "tests/test_json.py",
    "tests/test_session_interface.py",
    "tests/test_templating.py",
    "tests/test_testing.py",
]
TEST_TARGETS = EVALUATOR_COMMAND[6:]
PUBLIC_MODULES = [
    "src/flask/app.py",
    "src/flask/config.py",
    "src/flask/ctx.py",
    "src/flask/json/provider.py",
    "src/flask/json/tag.py",
    "src/flask/sansio/app.py",
    "src/flask/sansio/scaffold.py",
    "src/flask/sessions.py",
    "src/flask/templating.py",
    "src/flask/testing.py",
]
NATURAL_SUBPROBLEMS = {
    "scaffold_app_layer": [
        "src/flask/sansio/scaffold.py",
        "src/flask/sansio/app.py",
        "src/flask/config.py",
        "tests/test_basic.py",
    ],
    "dispatch_context_layer": [
        "src/flask/app.py",
        "src/flask/ctx.py",
        "tests/test_basic.py",
        "tests/test_reqctx.py",
        "tests/test_appctx.py",
    ],
    "session_json_layer": [
        "src/flask/sessions.py",
        "src/flask/json/provider.py",
        "src/flask/json/tag.py",
        "tests/test_json.py",
        "tests/test_session_interface.py",
    ],
    "templating_testing_layer": [
        "src/flask/templating.py",
        "src/flask/testing.py",
        "tests/test_templating.py",
        "tests/test_testing.py",
    ],
}
DEPENDENCIES = [
    {
        "consumer_subproblem": "dispatch_context_layer",
        "dependency_type": "api_contract",
        "description": "Flask request dispatch consumes sansio scaffold route registration, endpoint naming, URL map, and callback registry semantics.",
        "evidence_paths": [
            "src/flask/sansio/scaffold.py",
            "src/flask/sansio/app.py",
            "src/flask/app.py",
            "tests/test_basic.py",
        ],
        "producer_subproblem": "scaffold_app_layer",
        "schema_version": "0.3",
    },
    {
        "consumer_subproblem": "dispatch_context_layer",
        "dependency_type": "shared_state_contract",
        "description": "Request and app context lifecycle code consumes session opening/saving, JSON provider response, and tagged session serialization contracts.",
        "evidence_paths": [
            "src/flask/app.py",
            "src/flask/ctx.py",
            "src/flask/sessions.py",
            "src/flask/json/provider.py",
            "tests/test_basic.py",
            "tests/test_json.py",
            "tests/test_session_interface.py",
        ],
        "producer_subproblem": "session_json_layer",
        "schema_version": "0.3",
    },
    {
        "consumer_subproblem": "templating_testing_layer",
        "dependency_type": "integration_contract",
        "description": "Template rendering and the test client consume current_app/request/session context state, URL defaults, JSON dumps, and response conversion behavior.",
        "evidence_paths": [
            "src/flask/ctx.py",
            "src/flask/templating.py",
            "src/flask/testing.py",
            "tests/test_templating.py",
            "tests/test_testing.py",
        ],
        "producer_subproblem": "dispatch_context_layer",
        "schema_version": "0.3",
    },
]


def overlays() -> list[dict]:
    records = []
    for path in sorted(Path("data/overlays/commit0/flask").glob("*.patch")):
        records.append(
            {
                "path": path.as_posix(),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "rationale": "Bootstrap-only patch that removes import, class construction, or syntax blockers so public Flask tests can collect; it does not implement scoped Flask runtime behavior.",
            }
        )
    return records


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
        "scaffold_agent",
        "sansio Scaffold/App route registration, config, URL map, and callback registry specialist",
        "scaffold_app_layer",
        ["src/flask/sansio/scaffold.py", "src/flask/sansio/app.py", "src/flask/config.py"],
        [
            "tests/test_basic.py::test_route_decorator_custom_endpoint",
            "tests/test_basic.py::test_url_mapping",
        ],
    ),
    assignment(
        "dispatch_agent",
        "Flask request dispatch, response conversion, error handling, and app/request context specialist",
        "dispatch_context_layer",
        ["src/flask/app.py", "src/flask/ctx.py"],
        [
            "tests/test_basic.py::test_request_dispatching",
            "tests/test_reqctx.py::test_context_binding",
            "tests/test_appctx.py::test_request_context_means_app_context",
        ],
    ),
    assignment(
        "session_json_agent",
        "session interface, tagged session serialization, and JSON provider specialist",
        "session_json_layer",
        ["src/flask/sessions.py", "src/flask/json/provider.py", "src/flask/json/tag.py"],
        [
            "tests/test_basic.py::test_session",
            "tests/test_json.py::test_jsonify_basic_types",
            "tests/test_session_interface.py::test_open_session_with_endpoint",
        ],
    ),
    assignment(
        "template_testing_agent",
        "templating context processors and test client environment/session behavior specialist",
        "templating_testing_layer",
        ["src/flask/templating.py", "src/flask/testing.py"],
        [
            "tests/test_templating.py::test_context_processing",
            "tests/test_testing.py::test_json_request_and_response",
        ],
    ),
]


def scenario(mode: str, communication: str, concurrent: bool, profile: str, integration: str, delivery: str) -> dict:
    assignments = ASSIGNMENTS
    agent_count = 4
    if mode == "iterative_single":
        assignments = [assignment("integrator", "iterative full-task coding agent", "full_task", PUBLIC_MODULES, TEST_TARGETS)]
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
        "scenario_id": f"commit0-flask.{mode.replace('_', '-')}.v0.3",
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
            "Task source and tests are unchanged; only import, syntax, and class-construction bootstrap overlays are applied.",
            "The local main/commit0 branch is complete. Benchmark workspaces must be materialized from origin/commit0_combined.",
            "The evaluator follows the audit recommendation to focus on basic dispatch, request/app context, JSON/session, templating, and testing behavior.",
            "CLI, async extra, dev-server behavior, and full blueprint edge cases are intentionally out of scope for this v0.3 task.",
            "The proposed label is a draft curation decision and not a final independent annotation.",
        ],
        "problem_statement": (
            "Restore the scoped Flask app, context, JSON/session, templating, and testing behavior exercised by the public Commit0 tests without modifying the tests.\n\n"
            "The scaffold/app layer must implement route registration, endpoint naming, URL map setup, config attributes, and callback registries. "
            "The dispatch/context layer must consume those contracts to implement request dispatch, response conversion, error handling, and app/request context lifecycle. "
            "The session/JSON layer must provide JSONProvider and tagged session serialization contracts consumed by request processing and test clients. "
            "The templating/testing layer must consume context state, JSON dumps, and response/session behavior in template rendering and FlaskClient helpers.\n\n"
            "The initial benchmark source is the stripped Commit0-style ref origin/commit0_combined, plus checksum-recorded bootstrap overlays that only make the public tests importable and collectable."
        ),
        "proposed_parallelizability_label": "partially_parallelizable",
        "publicly_implicated_modules": PUBLIC_MODULES,
        "qualification_label": None,
        "qualification_status": "pending_independent_annotation",
        "quality_evidence_file": "manifests/pilot/v0.3/quality/commit0_flask.json",
        "repository": "commit0/flask",
        "schema_version": "0.3",
        "source_materialization": (
            f"git archive of the stripped Commit0-style Flask ref {BASE_REF} at {STRIPPED_SHA}, plus checksum-recorded import/bootstrap overlays in configs/tasks/commit0_curated_tasks.v0.3.json"
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
            scenario("serial_specialists", "completed_artifact_handoff", False, "private-workspace", "Apply scaffold/app and session/JSON artifacts before dispatch/context integration, then templating/testing artifacts.", "Specialists run with barrier synchronization. Downstream specialists receive completed upstream artifacts before final validation."),
            scenario("async_private", "private_concurrent_workspaces", True, "private-workspace", "Integrate independently produced specialist artifacts at the end, then run dependency probes and the scoped evaluator.", "Agents work concurrently without messages while dispatch, session, JSON, templating, and testing assumptions may become stale."),
            scenario("async_message", "asynchronous_message_handoff", True, "message-passing", "Integrate independently produced specialist artifacts after asynchronous handoffs, then run dependency probes and the scoped evaluator.", "Agents may send artifact summaries asynchronously; downstream workers are not guaranteed to see the newest scaffold, dispatch, session, or JSON contract before acting."),
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
            "Werkzeug==3.0.4",
            "Jinja2==3.1.6",
            "itsdangerous==2.2.0",
            "click==8.4.2",
            "blinker==1.9.0",
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD=1",
            "Run from the repository root with PYTHONPATH=src.",
            "Use origin/commit0_combined plus bootstrap overlays from configs/tasks/commit0_curated_tasks.v0.3.json.",
        ],
        "evaluation_snapshots": [
            {
                "collected": 244,
                "command": EVALUATOR_COMMAND,
                "dependency_versions": {
                    "Werkzeug": "3.0.4",
                    "Jinja2": "3.1.6",
                    "itsdangerous": "2.2.0",
                    "click": "8.4.2",
                    "blinker": "1.9.0",
                    "pytest": "9.0.3",
                },
                "duration_seconds": 6.01,
                "errors": 211,
                "evidence_scope": "public_initial_state",
                "failed": 30,
                "notes": [
                    "Verified with PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 and PYTHONPATH=<materialized-root>/src after applying only checksum-recorded bootstrap overlays.",
                    "Failures and errors are caused by unfinished scaffold, app, context, JSON, session, templating, and testing behavior; there are no remaining collection errors.",
                ],
                "passed": 1,
                "python_version": "3.10.12",
                "return_code": 1,
                "schema_version": "0.3",
                "skipped": 2,
                "snapshot_id": "curated_commit0_initial_flask_app_context_evaluator",
                "source_ref": f"{BASE_REF}:{STRIPPED_SHA}+bootstrap-overlays",
            },
            {
                "collected": 244,
                "command": EVALUATOR_COMMAND,
                "dependency_versions": {
                    "Werkzeug": "3.0.4",
                    "Jinja2": "3.1.6",
                    "itsdangerous": "2.2.0",
                    "click": "8.4.2",
                    "blinker": "1.9.0",
                    "pytest": "9.0.3",
                },
                "duration_seconds": 1.11,
                "errors": 0,
                "evidence_scope": "evaluator_sanity_only",
                "failed": 0,
                "notes": [
                    "The complete local main/commit0 ref passes the same scoped evaluator in the same environment.",
                    "The complete ref is evaluator validation only and must not define decomposition, prompts, or agent-visible evidence.",
                ],
                "passed": 242,
                "python_version": "3.10.12",
                "return_code": 0,
                "schema_version": "0.3",
                "skipped": 2,
                "snapshot_id": "complete_commit0_flask_app_context_evaluator_sanity",
                "source_ref": f"main:{COMPLETE_SHA}",
            },
        ],
        "known_limitations": [
            "The local main/commit0 branch is complete. Benchmark workspaces must be materialized from origin/commit0_combined.",
            "Raw origin/commit0_combined collection fails before bootstrap overlays because several stripped class-level callbacks, decorators, and one f-string quote are missing.",
            "Bootstrap overlays are intentionally numerous for Flask; they only make public tests importable and collectable and do not implement scoped Flask runtime behavior.",
            "CLI, async extra, dev-server behavior, and full blueprint edge cases are excluded from this scoped task.",
            "Single-agent and multi-agent model results are evaluation outputs to report, not dataset qualification gates.",
        ],
        "public_statement_sources": [
            "README.md@origin/commit0_combined",
            "src/flask/*.py and src/flask/sansio/*.py docstrings@origin/commit0_combined",
            "tests/test_*.py@origin/commit0_combined",
            AUDIT,
        ],
        "quality_status": "qualification_ready",
        "remaining_gates": ["two independent human inclusion/exclusion annotations"],
        "schema_version": "0.3",
        "structure_rationale": "Flask exposes semantic async dependencies between shared sansio scaffold/app registries, Flask request dispatch and context lifecycle, JSON/session serialization, and templating/testing consumers. Downstream workers can make stale assumptions about endpoint registration, context stack state, session opening/saving, JSON response shape, or test-client environment construction even when patches merge textually.",
        "task_id": TASK_ID,
        "test_groups": [
            {"command": EVALUATOR_COMMAND[:6] + ["tests/test_basic.py"], "description": "Core app dispatch, route registration, response conversion, sessions, and error handling.", "group_id": "basic_dispatch_local", "owner_subproblem": "dispatch_context_layer", "prerequisites": [], "purpose": "specialist_local", "schema_version": "0.3"},
            {"command": EVALUATOR_COMMAND[:6] + ["tests/test_json.py", "tests/test_session_interface.py"], "description": "JSON provider, tagged serializer, and session interface behavior.", "group_id": "json_session_local", "owner_subproblem": "session_json_layer", "prerequisites": [], "purpose": "specialist_local", "schema_version": "0.3"},
            {"command": EVALUATOR_COMMAND[:6] + ["tests/test_reqctx.py", "tests/test_appctx.py"], "description": "Request and application context lifecycle behavior.", "group_id": "context_lifecycle_local", "owner_subproblem": "dispatch_context_layer", "prerequisites": [], "purpose": "specialist_local", "schema_version": "0.3"},
            {"command": EVALUATOR_COMMAND[:6] + ["tests/test_templating.py", "tests/test_testing.py"], "description": "Templating context and FlaskClient/EnvironBuilder behavior.", "group_id": "templating_testing_local", "owner_subproblem": "templating_testing_layer", "prerequisites": [], "purpose": "specialist_local", "schema_version": "0.3"},
            {"command": EVALUATOR_COMMAND[:6] + ["tests/test_basic.py::test_request_dispatching", "tests/test_basic.py::test_url_mapping"], "description": "Request dispatch after scaffold/app route and URL map contracts are integrated.", "group_id": "scaffold_dispatch_cross_contract", "owner_subproblem": None, "prerequisites": ["scaffold_app_layer artifact is integrated", "dispatch_context_layer artifact is integrated"], "purpose": "cross_subproblem", "schema_version": "0.3"},
            {"command": EVALUATOR_COMMAND[:6] + ["tests/test_json.py::test_jsonify_basic_types", "tests/test_basic.py::test_session"], "description": "Session and JSON behavior after dispatch/context integration.", "group_id": "session_json_dispatch_cross_contract", "owner_subproblem": None, "prerequisites": ["session_json_layer artifact is integrated", "dispatch_context_layer artifact is integrated"], "purpose": "cross_subproblem", "schema_version": "0.3"},
            {"command": EVALUATOR_COMMAND, "description": "Full scoped Flask app/context evaluator.", "group_id": "full_scoped_evaluator", "owner_subproblem": None, "prerequisites": ["scaffold_app_layer artifact is integrated", "dispatch_context_layer artifact is integrated", "session_json_layer artifact is integrated", "templating_testing_layer artifact is integrated"], "purpose": "full_evaluator", "schema_version": "0.3"},
        ],
    }


def metrics_record() -> dict:
    dependency_points = [
        {
            "consumer_agent": "dispatch_agent",
            "consumer_files": ["src/flask/app.py", "src/flask/ctx.py"],
            "consumer_subproblem": "dispatch_context_layer",
            "contract_summary": "Scaffold and sansio App route registration, endpoint naming, URL map, and callback registries must be stable for Flask request dispatch and URL generation.",
            "dependency_id": "flask.scaffold_to_dispatch.route_context_contract",
            "dependency_type": "interface_dependency",
            "downstream_probe_tests": ["tests/test_basic.py::test_request_dispatching", "tests/test_basic.py::test_url_generation"],
            "integrated_probe_tests": ["tests/test_basic.py::test_route_decorator_custom_endpoint", "tests/test_basic.py::test_request_dispatching", "tests/test_basic.py::test_url_mapping"],
            "metrics_enabled": ["ADPR", "DRS", "CAIL", "SAD"],
            "primary_paper_probe": True,
            "producer_agent": "scaffold_agent",
            "producer_files": ["src/flask/sansio/scaffold.py", "src/flask/sansio/app.py", "src/flask/config.py"],
            "producer_subproblem": "scaffold_app_layer",
            "resolution_criteria": "Resolved when route registration, request dispatch, and URL map probes pass together in the integrated workspace.",
            "stale_failure_mode": "The dispatch agent may assume stale endpoint naming, URL map, or callback registry semantics from the scaffold layer.",
            "upstream_probe_tests": ["tests/test_basic.py::test_route_decorator_custom_endpoint", "tests/test_basic.py::test_url_mapping"],
        },
        {
            "consumer_agent": "dispatch_agent",
            "consumer_files": ["src/flask/app.py", "src/flask/ctx.py"],
            "consumer_subproblem": "dispatch_context_layer",
            "contract_summary": "SessionInterface, SecureCookieSession, TaggedJSONSerializer, and JSONProvider response behavior must be stable for request context open/save and response conversion.",
            "dependency_id": "flask.session_json_to_context.cookie_response_contract",
            "dependency_type": "shared_state_contract",
            "downstream_probe_tests": ["tests/test_basic.py::test_session", "tests/test_reqctx.py::test_session_dynamic_cookie_name"],
            "integrated_probe_tests": ["tests/test_json.py::test_jsonify_basic_types", "tests/test_basic.py::test_session", "tests/test_session_interface.py::test_open_session_with_endpoint"],
            "metrics_enabled": ["ADPR", "DRS", "CAIL", "SAD"],
            "producer_agent": "session_json_agent",
            "producer_files": ["src/flask/sessions.py", "src/flask/json/provider.py", "src/flask/json/tag.py"],
            "producer_subproblem": "session_json_layer",
            "resolution_criteria": "Resolved when JSON provider, session cookie, and request-context session probes pass after integration.",
            "stale_failure_mode": "The dispatch/context agent may save sessions or convert responses against stale JSON serialization or cookie lifecycle assumptions.",
            "upstream_probe_tests": ["tests/test_json.py::test_jsonify_basic_types", "tests/test_json.py::test_jsonify_datetime"],
        },
        {
            "consumer_agent": "template_testing_agent",
            "consumer_files": ["src/flask/templating.py", "src/flask/testing.py"],
            "consumer_subproblem": "templating_testing_layer",
            "contract_summary": "Templating and test client helpers must consume current_app/request/session context, JSON dumps, and response/session behavior consistently.",
            "dependency_id": "flask.context_to_template_testing.client_context_contract",
            "dependency_type": "integration_contract",
            "downstream_probe_tests": ["tests/test_templating.py::test_context_processing", "tests/test_testing.py::test_json_request_and_response"],
            "integrated_probe_tests": ["tests/test_appctx.py::test_request_context_means_app_context", "tests/test_templating.py::test_context_processing", "tests/test_testing.py::test_session_transactions"],
            "metrics_enabled": ["ADPR", "DRS", "CAIL", "SAD"],
            "producer_agent": "dispatch_agent",
            "producer_files": ["src/flask/app.py", "src/flask/ctx.py"],
            "producer_subproblem": "dispatch_context_layer",
            "resolution_criteria": "Resolved when app/request context probes, templating context probes, and test-client session probes pass after integration.",
            "stale_failure_mode": "The templating/testing agent may build clients or render templates against stale context stack and JSON/session assumptions.",
            "upstream_probe_tests": ["tests/test_reqctx.py::test_context_binding", "tests/test_appctx.py::test_request_context_means_app_context"],
        },
    ]
    return {
        "aggregate_metrics": {
            "ADPR_denominator": "All dependency_points unless a paper section explicitly reports primary_async_dependency_ids only.",
            "dependency_point_count": 3,
            "minimum_success_condition_for_task_level_async_dependency_resolution": "All primary_async_dependency_ids pass in the final integrated workspace.",
            "primary_async_dependency_ids": [item["dependency_id"] for item in dependency_points],
            "primary_paper_dependency_id": "flask.scaffold_to_dispatch.route_context_contract",
        },
        "annotation_notes": [
            "The scaffold_to_dispatch dependency is the primary signal because Flask dispatch is highly sensitive to stale route, endpoint, URL map, and callback registry semantics.",
            "The session_json_to_context dependency captures stale assumptions around JSON response shape, tagged session serialization, and cookie lifecycle.",
            "The context_to_template_testing dependency captures stale context-stack assumptions consumed by templating and FlaskClient helpers.",
            "These labels identify public test-observable contracts, not solution code.",
        ],
        "dependency_points": dependency_points,
        "evaluation_checkpoint_policy": {
            "checkpoint_record_fields": ["run_id", "scenario_id", "checkpoint_id", "logical_iteration", "agent_id", "visible_upstream_artifact_version", "integrated_workspace_version", "probe_test_results"],
            "minimum_policy": "Run probe tests after each agent final artifact and after final integration.",
            "recommended_policy": "Run probe tests after every committed patch, every explicit artifact transfer, and final integration.",
        },
        "metric_annotation_id": "commit0-flask.async-metrics.v0.3",
        "metric_definitions": {
            "ADPR": {"definition": "Fraction of registered dependency_points whose required integrated_probe_tests pass in the final integrated workspace.", "name": "Async Dependency Pass Rate", "unit": "fraction"},
            "CAIL": {"definition": "downstream_resolution_step minus upstream_resolution_step when both probe groups have been evaluated.", "name": "Cross-Agent Integration Lag", "unit": "agent iteration or evaluation checkpoint"},
            "DRS": {"definition": "First recorded checkpoint at which all required integrated_probe_tests for a dependency point pass.", "name": "Dependency Resolution Step", "unit": "agent iteration or evaluation checkpoint"},
            "SAD": {"definition": "Interval during which a downstream worker acts on a contract assumption inconsistent with the latest upstream artifact.", "name": "Stale Assumption Duration", "unit": "agent iteration or event interval"},
        },
        "purpose": "Dependency-level labels for measuring whether asynchronous multi-agent coding resolves Flask scaffold/app, request context, JSON/session, templating, and testing-client contracts.",
        "schema_version": "0.3-async-metrics",
        "source_quality_record": "manifests/pilot/v0.3/quality/commit0_flask.json",
        "source_task_record": "manifests/pilot/v0.3/tasks/commit0_flask.json",
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
            "Review the linked TaskQualityRecord, including the dependency environment and checksum-recorded bootstrap overlays.",
            "Do not inspect reference branches, solution patches, or diffs.",
            "Do not consult the other annotator before submitting.",
            "Explicitly assess whether the scaffold/app -> dispatch/context -> session/JSON -> templating/testing split is a natural AsyncCodeBench dependency rather than artificial file partitioning.",
            "Explicitly assess whether excluding CLI, async extra, dev-server behavior, and full blueprint edge cases is appropriate for this scoped Flask task.",
        ],
        "parallelizability_label": None,
        "rationale": None,
        "schema_version": "0.3",
        "task_id": TASK_ID,
        "task_record_file": "manifests/pilot/v0.3/tasks/commit0_flask.json",
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
            "repository": "flask",
            "base_ref": BASE_REF,
            "base_sha": STRIPPED_SHA,
            "overlays": overlays(),
        }
    )
    write_json(path, payload)


def main() -> None:
    files = {
        Path("manifests/pilot/v0.3/tasks/commit0_flask.json"): task_record(),
        Path("manifests/pilot/v0.3/scenarios/commit0_flask.json"): scenario_record(),
        Path("manifests/pilot/v0.3/quality/commit0_flask.json"): quality_record(),
        Path("manifests/pilot/v0.3/metrics/commit0_flask_async_metrics.json"): metrics_record(),
        Path("manifests/annotations/commit0_v0.3/flask/annotator_a.json"): annotation_form("annotator_a"),
        Path("manifests/annotations/commit0_v0.3/flask/annotator_b.json"): annotation_form("annotator_b"),
        Path("manifests/annotations/commit0_v0.3/flask/adjudication.template.json"): adjudication_template(),
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
