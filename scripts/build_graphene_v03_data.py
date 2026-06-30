"""Generate and validate the v0.3 Commit0 graphene task records."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


TASK_ID = "commit0:graphene"
STRIPPED_SHA = "ec2d3f476a7fa94a7a2ffc3c145422b0c3b7e71a"
COMPLETE_SHA = "48678afba44fc6e43334133f92ea089613a29d93"
BASE_REF = "origin/commit0_combined"
BASE_MATERIALIZATION = (
    "git archive of the stripped Commit0-style graphene ref "
    f"{BASE_REF} at {STRIPPED_SHA}, plus checksum-recorded import/bootstrap "
    "overlays in configs/tasks/commit0_curated_tasks.v0.3.json"
)

EVALUATOR_COMMAND = [
    "python3.10",
    "-m",
    "pytest",
    "-q",
    "-o",
    "addopts=",
    "-k",
    "not test_objecttype_container_benchmark",
    "graphene/types/tests/test_definition.py",
    "graphene/types/tests/test_objecttype.py",
    "graphene/types/tests/test_inputobjecttype.py",
    "graphene/types/tests/test_schema.py",
    "graphene/types/tests/test_scalars_serialization.py",
]
TEST_TARGETS = [
    "graphene/types/tests/test_definition.py",
    "graphene/types/tests/test_objecttype.py",
    "graphene/types/tests/test_inputobjecttype.py",
    "graphene/types/tests/test_schema.py",
    "graphene/types/tests/test_scalars_serialization.py",
]
PUBLIC_MODULES = [
    "graphene/types/argument.py",
    "graphene/types/base.py",
    "graphene/types/definitions.py",
    "graphene/types/enum.py",
    "graphene/types/field.py",
    "graphene/types/inputfield.py",
    "graphene/types/inputobjecttype.py",
    "graphene/types/interface.py",
    "graphene/types/objecttype.py",
    "graphene/types/resolver.py",
    "graphene/types/scalars.py",
    "graphene/types/schema.py",
    "graphene/types/structures.py",
    "graphene/types/union.py",
    "graphene/types/unmountedtype.py",
    "graphene/types/utils.py",
]
OVERLAYS = [
    (
        "data/overlays/commit0/graphene/0001-types-utils-import-bootstrap.patch",
        "Expose only missing type utility symbols needed for package import and test class construction. Field extraction intentionally returns an empty structure, so object/input metadata behavior remains unfinished.",
    ),
    (
        "data/overlays/commit0/graphene/0002-subclass-meta-syntax-bootstrap.patch",
        "Repair a stripped f-string syntax placeholder in subclass_with_meta so public modules can parse. No metaclass behavior is supplied.",
    ),
    (
        "data/overlays/commit0/graphene/0003-props-import-bootstrap.patch",
        "Expose only the class-construction Meta attribute reader needed by public graphene type tests. This bootstrap is intentionally flagged for human review because it is less trivial than a pure pass stub.",
    ),
    (
        "data/overlays/commit0/graphene/0004-utils-import-bootstrap.patch",
        "Expose missing utility symbols imported by public modules. Helper bodies remain intentionally unfinished placeholders.",
    ),
    (
        "data/overlays/commit0/graphene/0005-scalars-class-bootstrap.patch",
        "Expose scalar coercion function names required by scalar class definitions. Scalar coercion and serialization behavior remains unfinished.",
    ),
    (
        "data/overlays/commit0/graphene/0006-base-options-bootstrap.patch",
        "Expose BaseOptions.freeze for metaclass construction. Option freezing behavior remains unfinished.",
    ),
    (
        "data/overlays/commit0/graphene/0007-enum-class-bootstrap.patch",
        "Expose enum helper functions needed for enum class construction. Enum value equality/hash behavior remains unfinished.",
    ),
    (
        "data/overlays/commit0/graphene/0008-argument-field-import-bootstrap.patch",
        "Expose to_arguments and warn_deprecation import-time symbols. Argument conversion and deprecation warning behavior remains unfinished.",
    ),
    (
        "data/overlays/commit0/graphene/0009-resolver-import-bootstrap.patch",
        "Expose resolver names imported by schema and field code. Default resolving behavior remains unfinished.",
    ),
    (
        "data/overlays/commit0/graphene/0010-relay-mutation-import-bootstrap.patch",
        "Expose ClientIDMutation.mutate so relay mutation subclasses can be constructed during package import. Mutation behavior remains unfinished.",
    ),
    (
        "data/overlays/commit0/graphene/0011-resolve-only-args-import-bootstrap.patch",
        "Expose resolve_only_args imported by relay mutation code. Resolver adaptation behavior remains unfinished.",
    ),
]

DEPENDENCIES = [
    {
        "consumer_subproblem": "object_input_metadata_layer",
        "dependency_type": "api_contract",
        "description": "ObjectType and InputObjectType metadata consume UnmountedType mounting into Field, InputField, Argument, and ordered field structures.",
        "evidence_paths": [
            "graphene/types/unmountedtype.py",
            "graphene/types/field.py",
            "graphene/types/inputfield.py",
            "graphene/types/argument.py",
            "graphene/types/objecttype.py",
            "graphene/types/inputobjecttype.py",
            "graphene/types/tests/test_scalars_serialization.py",
            "graphene/types/tests/test_objecttype.py",
            "graphene/types/tests/test_inputobjecttype.py",
        ],
        "producer_subproblem": "type_mounting_layer",
        "schema_version": "0.3",
    },
    {
        "consumer_subproblem": "schema_typemap_layer",
        "dependency_type": "api_contract",
        "description": "Schema and TypeMap conversion consume object, input object, interface, union, enum, field, and argument metadata contracts.",
        "evidence_paths": [
            "graphene/types/objecttype.py",
            "graphene/types/inputobjecttype.py",
            "graphene/types/interface.py",
            "graphene/types/union.py",
            "graphene/types/enum.py",
            "graphene/types/schema.py",
            "graphene/types/tests/test_definition.py",
            "graphene/types/tests/test_schema.py",
        ],
        "producer_subproblem": "object_input_metadata_layer",
        "schema_version": "0.3",
    },
    {
        "consumer_subproblem": "schema_typemap_layer",
        "dependency_type": "api_contract",
        "description": "Schema construction and GraphQL-core conversion consume scalar get_type, serialize, and coercion contracts.",
        "evidence_paths": [
            "graphene/types/scalars.py",
            "graphene/types/schema.py",
            "graphene/types/definitions.py",
            "graphene/types/tests/test_scalars_serialization.py",
            "graphene/types/tests/test_schema.py",
        ],
        "producer_subproblem": "type_mounting_layer",
        "schema_version": "0.3",
    },
]

NATURAL_SUBPROBLEMS = {
    "object_input_metadata_layer": [
        "graphene/types/base.py",
        "graphene/types/enum.py",
        "graphene/types/inputobjecttype.py",
        "graphene/types/interface.py",
        "graphene/types/objecttype.py",
        "graphene/types/union.py",
        "graphene/types/utils.py",
        "graphene/types/tests/test_objecttype.py",
        "graphene/types/tests/test_inputobjecttype.py",
    ],
    "schema_typemap_layer": [
        "graphene/types/definitions.py",
        "graphene/types/resolver.py",
        "graphene/types/schema.py",
        "graphene/types/tests/test_definition.py",
        "graphene/types/tests/test_schema.py",
    ],
    "type_mounting_layer": [
        "graphene/types/argument.py",
        "graphene/types/field.py",
        "graphene/types/inputfield.py",
        "graphene/types/scalars.py",
        "graphene/types/structures.py",
        "graphene/types/unmountedtype.py",
        "graphene/types/tests/test_scalars_serialization.py",
    ],
}


def _overlay_entries() -> list[dict]:
    entries = []
    for path_text, rationale in OVERLAYS:
        path = Path(path_text)
        entries.append(
            {
                "path": path_text,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "rationale": rationale,
            }
        )
    return entries


def _assignment(
    agent_id: str,
    role: str,
    subproblem_id: str,
    writable_paths: list[str],
    primary_test_targets: list[str],
) -> dict:
    return {
        "agent_id": agent_id,
        "primary_test_targets": primary_test_targets,
        "role": role,
        "schema_version": "0.3",
        "subproblem_id": subproblem_id,
        "writable_paths": writable_paths,
    }


SPECIALIST_ASSIGNMENTS = [
    _assignment(
        "mounting_agent",
        "field mounting, argument, scalar, and type wrapper specialist",
        "type_mounting_layer",
        [
            "graphene/types/argument.py",
            "graphene/types/field.py",
            "graphene/types/inputfield.py",
            "graphene/types/scalars.py",
            "graphene/types/structures.py",
            "graphene/types/unmountedtype.py",
        ],
        [
            "graphene/types/tests/test_scalars_serialization.py",
            "graphene/types/tests/test_definition.py::test_stringifies_simple_types",
        ],
    ),
    _assignment(
        "metadata_agent",
        "object, input object, interface, union, enum, and metadata specialist",
        "object_input_metadata_layer",
        [
            "graphene/types/base.py",
            "graphene/types/enum.py",
            "graphene/types/inputobjecttype.py",
            "graphene/types/interface.py",
            "graphene/types/objecttype.py",
            "graphene/types/union.py",
            "graphene/types/utils.py",
        ],
        [
            "graphene/types/tests/test_objecttype.py",
            "graphene/types/tests/test_inputobjecttype.py",
        ],
    ),
    _assignment(
        "schema_agent",
        "schema, TypeMap, definition conversion, and resolver specialist",
        "schema_typemap_layer",
        [
            "graphene/types/definitions.py",
            "graphene/types/resolver.py",
            "graphene/types/schema.py",
        ],
        [
            "graphene/types/tests/test_definition.py",
            "graphene/types/tests/test_schema.py",
        ],
    ),
]


def _scenario(
    execution_mode: str,
    communication_condition: str,
    concurrent_execution: bool,
    information_profile: str,
    integration_policy: str,
    message_delivery_policy: str,
) -> dict:
    if execution_mode == "iterative_single":
        assignments = [
            _assignment(
                "integrator",
                "iterative full-task coding agent",
                "full_task",
                PUBLIC_MODULES,
                EVALUATOR_COMMAND[5:],
            )
        ]
        agent_count = 1
    else:
        assignments = SPECIALIST_ASSIGNMENTS
        agent_count = 3
    return {
        "agent_count": agent_count,
        "assignments": assignments,
        "communication_condition": communication_condition,
        "concurrent_execution": concurrent_execution,
        "dependency_annotations": DEPENDENCIES,
        "execution_mode": execution_mode,
        "information_profile": information_profile,
        "integration_policy": integration_policy,
        "message_delivery_policy": message_delivery_policy,
        "scenario_id": f"commit0-graphene.{execution_mode.replace('_', '-')}.v0.3",
        "schema_version": "0.3",
        "shared_agent_scaffold": "iterative-inspect-edit-test-repair",
        "step_budget_per_agent": 34,
        "task_id": TASK_ID,
        "test_budget_per_agent": 12,
        "token_budget_per_agent": 85000,
        "wall_clock_budget_seconds": 3000,
    }


def _task_record() -> dict:
    return {
        "annotation_provenance": [],
        "candidate_evidence_file": "docs/audits/COMMIT0_CANDIDATE_REVIEW_networkx_graphene_tlslite_v0.3.md",
        "dependency_annotations": DEPENDENCIES,
        "evaluator_command": EVALUATOR_COMMAND,
        "inclusion_decision": None,
        "natural_subproblems": NATURAL_SUBPROBLEMS,
        "notes": [
            "Task source and tests are unchanged; only import/bootstrap overlays are applied.",
            "The local master branch is complete. Benchmark workspaces must be materialized from origin/commit0_combined.",
            "The evaluator follows the audit recommendation to scope Graphene to type/schema core behavior rather than full repository behavior.",
            "The evaluator excludes test_objecttype_container_benchmark because it requires the benchmark fixture and is benchmark-heavy rather than type/schema correctness evidence.",
            "The proposed label is a draft curation decision and not a final independent annotation.",
        ],
        "problem_statement": (
            "Restore the scoped Graphene type and schema behavior exercised by the public Commit0 tests without modifying the tests.\n\n"
            "The mounting layer must implement unmounted type conversion, Field/InputField/Argument construction, scalar serialization/coercion, and list/non-null wrapper behavior. "
            "The object/input metadata layer must implement ObjectType, InputObjectType, Interface, Union, Enum, options, field extraction, inheritance, ordering, and container behavior. "
            "The schema/type-map layer must consume those contracts to implement GraphQL-core definition conversion, TypeMap population, schema construction, introspection, get_type, and resolver defaults.\n\n"
            "The v0.3 evaluator intentionally scopes Graphene to the audit-recommended type/schema core and excludes the objecttype benchmark fixture. "
            "The initial benchmark source is the stripped Commit0-style ref origin/commit0_combined, plus checksum-recorded bootstrap overlays that only make public tests importable and collectable."
        ),
        "proposed_parallelizability_label": "partially_parallelizable",
        "publicly_implicated_modules": PUBLIC_MODULES,
        "qualification_label": None,
        "qualification_status": "pending_independent_annotation",
        "quality_evidence_file": "manifests/pilot/v0.3/quality/commit0_graphene.json",
        "repository": "commit0/graphene",
        "schema_version": "0.3",
        "source_materialization": BASE_MATERIALIZATION,
        "task_id": TASK_ID,
        "task_source": "Commit0",
        "test_targets": TEST_TARGETS,
        "upstream_version": STRIPPED_SHA,
    }


def _scenario_record() -> dict:
    return {
        "scenarios": [
            _scenario(
                "iterative_single",
                "not_applicable",
                False,
                "complete-task",
                "Agent submits its final workspace.",
                "No inter-agent messages.",
            ),
            _scenario(
                "serial_specialists",
                "completed_artifact_handoff",
                False,
                "private-workspace",
                "Apply mounting artifacts before object/input metadata artifacts, then schema/type-map artifacts, then run the scoped evaluator.",
                "Specialists run with barrier synchronization. Metadata receives mounting artifacts before final work; schema receives mounting and metadata artifacts before validation.",
            ),
            _scenario(
                "async_private",
                "private_concurrent_workspaces",
                True,
                "private-workspace",
                "Integrate independently produced specialist artifacts at the end, then run dependency probes and the scoped evaluator.",
                "Agents work concurrently without messages while their local tests and assumptions may become stale.",
            ),
            _scenario(
                "async_message",
                "asynchronous_message_handoff",
                True,
                "message-passing",
                "Integrate independently produced specialist artifacts after asynchronous handoffs, then run dependency probes and the scoped evaluator.",
                "Agents may send artifact summaries asynchronously; downstream workers are not guaranteed to see the newest upstream contract before acting.",
            ),
        ],
        "schema_version": "0.3",
        "task_id": TASK_ID,
    }


def _quality_record() -> dict:
    return {
        "coordination_structure_tags": [
            "interface_dependency",
            "shared_abstraction",
            "shared_state",
        ],
        "environment_requirements": [
            "Python 3.10.12",
            "pytest==9.0.3",
            "graphql-core==3.2.11",
            "graphql-relay==3.2.0",
            "aniso8601==9.0.1",
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD=1",
            "Run from the repository root with PYTHONPATH=.",
            "Use origin/commit0_combined plus bootstrap overlays from configs/tasks/commit0_curated_tasks.v0.3.json.",
        ],
        "evaluation_snapshots": [
            {
                "collected": 59,
                "command": EVALUATOR_COMMAND,
                "dependency_versions": {
                    "aniso8601": "9.0.1",
                    "graphql-core": "3.2.11",
                    "graphql-relay": "3.2.0",
                    "pytest": "9.0.3",
                },
                "deselected": 1,
                "duration_seconds": 0.53,
                "errors": 0,
                "evidence_scope": "public_initial_state",
                "failed": 48,
                "notes": [
                    "Verified with PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 and PYTHONPATH=<materialized-root> after applying only checksum-recorded bootstrap overlays.",
                    "Failures are caused by unfinished mounting, scalar, object/input metadata, TypeMap, schema, resolver, and GraphQL-core conversion behavior.",
                ],
                "passed": 10,
                "python_version": "3.10.12",
                "return_code": 1,
                "schema_version": "0.3",
                "skipped": 0,
                "snapshot_id": "curated_commit0_initial_type_schema_evaluator",
                "source_ref": f"{BASE_REF}:{STRIPPED_SHA}+bootstrap-overlays",
            },
            {
                "collected": 59,
                "command": EVALUATOR_COMMAND,
                "dependency_versions": {
                    "aniso8601": "9.0.1",
                    "graphql-core": "3.2.11",
                    "graphql-relay": "3.2.0",
                    "pytest": "9.0.3",
                },
                "deselected": 1,
                "duration_seconds": 0.15,
                "errors": 0,
                "evidence_scope": "evaluator_sanity_only",
                "failed": 0,
                "notes": [
                    "The complete local master ref passes the same scoped evaluator in the same environment.",
                    "The complete ref is evaluator validation only and must not define decomposition, prompts, or agent-visible evidence.",
                ],
                "passed": 58,
                "python_version": "3.10.12",
                "return_code": 0,
                "schema_version": "0.3",
                "skipped": 0,
                "snapshot_id": "complete_commit0_type_schema_evaluator_sanity",
                "source_ref": f"master:{COMPLETE_SHA}",
            },
        ],
        "known_limitations": [
            "The local master branch is complete. Benchmark workspaces must be materialized from origin/commit0_combined.",
            "Raw origin/commit0_combined collection fails before bootstrap overlays because public imports and class construction require missing utility, resolver, scalar, enum, relay, and argument symbols.",
            "Bootstrap overlays only make the public tests importable and collectable; they do not implement Graphene mounting, schema, TypeMap, resolver, scalar serialization, or metadata behavior.",
            "The props bootstrap exposes Meta attributes to allow public class definitions to collect. Human review should explicitly verify that this does not cross into solution behavior for the selected type/schema task.",
            "test_objecttype_container_benchmark is excluded because it requires pytest-benchmark and is not required for type/schema correctness.",
            "The full stripped Graphene repository is broader than the v0.3 instance; this task follows the audit recommendation to scope the benchmark to type/schema core behavior.",
            "Single-agent and multi-agent model results are evaluation outputs to report, not dataset qualification gates.",
        ],
        "public_statement_sources": [
            "README.md@origin/commit0_combined",
            "graphene/types/*.py docstrings@origin/commit0_combined",
            "graphene/types/tests/test_*.py@origin/commit0_combined",
            "docs/audits/COMMIT0_CANDIDATE_REVIEW_networkx_graphene_tlslite_v0.3.md",
        ],
        "quality_status": "qualification_ready",
        "remaining_gates": [
            "two independent human inclusion/exclusion annotations"
        ],
        "schema_version": "0.3",
        "structure_rationale": (
            "Graphene exposes semantic async dependencies between type mounting/scalar behavior, object/input metadata construction, and schema/type-map conversion. "
            "A downstream schema worker can make stale assumptions about mounted field shapes, metadata extraction, enum/input contracts, or scalar get_type behavior that only fail once definition and schema tests integrate."
        ),
        "task_id": TASK_ID,
        "test_groups": [
            {
                "command": EVALUATOR_COMMAND[:7]
                + [
                    "graphene/types/tests/test_scalars_serialization.py",
                    "graphene/types/tests/test_definition.py::test_stringifies_simple_types",
                ],
                "description": "Scalar serialization, unmounted type mounting, and basic type stringification.",
                "group_id": "type_mounting_local",
                "owner_subproblem": "type_mounting_layer",
                "prerequisites": [],
                "purpose": "specialist_local",
                "schema_version": "0.3",
            },
            {
                "command": EVALUATOR_COMMAND[:7]
                + [
                    "graphene/types/tests/test_objecttype.py",
                    "graphene/types/tests/test_inputobjecttype.py",
                ],
                "description": "ObjectType/InputObjectType metadata, options, inheritance, ordering, and container behavior.",
                "group_id": "object_input_metadata_local",
                "owner_subproblem": "object_input_metadata_layer",
                "prerequisites": [],
                "purpose": "specialist_local",
                "schema_version": "0.3",
            },
            {
                "command": EVALUATOR_COMMAND[:7]
                + [
                    "graphene/types/tests/test_definition.py",
                    "graphene/types/tests/test_schema.py",
                ],
                "description": "GraphQL-core definition conversion, TypeMap population, schema construction, introspection, and get_type behavior.",
                "group_id": "schema_typemap_local",
                "owner_subproblem": "schema_typemap_layer",
                "prerequisites": [],
                "purpose": "specialist_local",
                "schema_version": "0.3",
            },
            {
                "command": EVALUATOR_COMMAND[:7]
                + [
                    "graphene/types/tests/test_scalars_serialization.py::test_serializes_output_int",
                    "graphene/types/tests/test_definition.py::test_stringifies_simple_types",
                    "graphene/types/tests/test_objecttype.py::test_generate_objecttype_with_fields",
                    "graphene/types/tests/test_inputobjecttype.py::test_generate_inputobjecttype_with_fields",
                ],
                "description": "Object/input metadata after mounted field and scalar contracts are integrated.",
                "group_id": "mounting_metadata_cross_contract",
                "owner_subproblem": None,
                "prerequisites": [
                    "type_mounting_layer artifact is integrated",
                    "object_input_metadata_layer artifact is integrated",
                ],
                "purpose": "cross_subproblem",
                "schema_version": "0.3",
            },
            {
                "command": EVALUATOR_COMMAND[:7]
                + [
                    "graphene/types/tests/test_objecttype.py::test_generate_objecttype_with_meta",
                    "graphene/types/tests/test_inputobjecttype.py::test_generate_inputobjecttype_with_meta",
                    "graphene/types/tests/test_schema.py::test_schema",
                    "graphene/types/tests/test_definition.py::test_defines_a_query_only_schema",
                ],
                "description": "Schema/TypeMap behavior after object and input metadata contracts are integrated.",
                "group_id": "metadata_schema_cross_contract",
                "owner_subproblem": None,
                "prerequisites": [
                    "object_input_metadata_layer artifact is integrated",
                    "schema_typemap_layer artifact is integrated",
                ],
                "purpose": "cross_subproblem",
                "schema_version": "0.3",
            },
            {
                "command": EVALUATOR_COMMAND,
                "description": "Full scoped type/schema evaluator.",
                "group_id": "full_scoped_evaluator",
                "owner_subproblem": None,
                "prerequisites": [
                    "type_mounting_layer artifact is integrated",
                    "object_input_metadata_layer artifact is integrated",
                    "schema_typemap_layer artifact is integrated",
                ],
                "purpose": "full_evaluator",
                "schema_version": "0.3",
            },
        ],
    }


def _metrics_record() -> dict:
    metric_definitions = {
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
    }
    dependency_points = [
        {
            "consumer_agent": "metadata_agent",
            "consumer_files": [
                "graphene/types/objecttype.py",
                "graphene/types/inputobjecttype.py",
            ],
            "consumer_subproblem": "object_input_metadata_layer",
            "contract_summary": "Unmounted scalar/type mounting into Field, InputField, Argument, and ordered field structures must be stable before object/input metadata is assembled.",
            "dependency_id": "graphene.mounting_to_object.fields_contract",
            "dependency_type": "shared_api_contract",
            "downstream_probe_tests": [
                "graphene/types/tests/test_objecttype.py::test_generate_objecttype_with_fields",
                "graphene/types/tests/test_inputobjecttype.py::test_generate_inputobjecttype_with_fields",
            ],
            "integrated_probe_tests": [
                "graphene/types/tests/test_scalars_serialization.py::test_serializes_output_int",
                "graphene/types/tests/test_definition.py::test_stringifies_simple_types",
                "graphene/types/tests/test_objecttype.py::test_generate_objecttype_with_fields",
                "graphene/types/tests/test_inputobjecttype.py::test_generate_inputobjecttype_with_fields",
            ],
            "metrics_enabled": ["ADPR", "DRS", "CAIL", "SAD"],
            "producer_agent": "mounting_agent",
            "producer_files": [
                "graphene/types/argument.py",
                "graphene/types/field.py",
                "graphene/types/inputfield.py",
                "graphene/types/scalars.py",
                "graphene/types/structures.py",
                "graphene/types/unmountedtype.py",
            ],
            "producer_subproblem": "type_mounting_layer",
            "resolution_criteria": "Resolved when mounting/scalar probes and object/input field metadata probes pass in the integrated workspace.",
            "stale_failure_mode": "The metadata agent may implement ObjectType or InputObjectType around stale mounted-field shapes, ordering behavior, or scalar get_type assumptions.",
            "upstream_probe_tests": [
                "graphene/types/tests/test_scalars_serialization.py::test_serializes_output_int",
                "graphene/types/tests/test_definition.py::test_stringifies_simple_types",
            ],
        },
        {
            "consumer_agent": "schema_agent",
            "consumer_files": [
                "graphene/types/definitions.py",
                "graphene/types/schema.py",
                "graphene/types/resolver.py",
            ],
            "consumer_subproblem": "schema_typemap_layer",
            "contract_summary": "Object, input object, interface, union, enum, field, and argument metadata must be converted consistently into GraphQL-core TypeMap and Schema objects.",
            "dependency_id": "graphene.object_metadata_to_schema.typemap_contract",
            "dependency_type": "interface_dependency",
            "downstream_probe_tests": [
                "graphene/types/tests/test_schema.py::test_schema",
                "graphene/types/tests/test_definition.py::test_defines_a_query_only_schema",
            ],
            "integrated_probe_tests": [
                "graphene/types/tests/test_objecttype.py::test_generate_objecttype_with_meta",
                "graphene/types/tests/test_inputobjecttype.py::test_generate_inputobjecttype_with_meta",
                "graphene/types/tests/test_definition.py::test_includes_nested_input_objects_in_the_map",
                "graphene/types/tests/test_definition.py::test_includes_types_in_union",
                "graphene/types/tests/test_schema.py::test_schema_introspect",
            ],
            "metrics_enabled": ["ADPR", "DRS", "CAIL", "SAD"],
            "primary_paper_probe": True,
            "producer_agent": "metadata_agent",
            "producer_files": [
                "graphene/types/base.py",
                "graphene/types/enum.py",
                "graphene/types/inputobjecttype.py",
                "graphene/types/interface.py",
                "graphene/types/objecttype.py",
                "graphene/types/union.py",
                "graphene/types/utils.py",
            ],
            "producer_subproblem": "object_input_metadata_layer",
            "resolution_criteria": "Resolved when object/input metadata probes and schema/TypeMap conversion probes pass together after integration.",
            "stale_failure_mode": "The schema agent may construct GraphQL-core types around stale metadata, field, enum, union, or input object contracts that only fail after TypeMap population.",
            "upstream_probe_tests": [
                "graphene/types/tests/test_objecttype.py::test_generate_objecttype_with_meta",
                "graphene/types/tests/test_inputobjecttype.py::test_generate_inputobjecttype_with_meta",
            ],
        },
        {
            "consumer_agent": "schema_agent",
            "consumer_files": [
                "graphene/types/definitions.py",
                "graphene/types/schema.py",
            ],
            "consumer_subproblem": "schema_typemap_layer",
            "contract_summary": "Scalar get_type, serialize, and coercion contracts must agree with schema/type-map conversion and GraphQL execution-facing definitions.",
            "dependency_id": "graphene.scalars_to_schema.coercion_execution_contract",
            "dependency_type": "shared_api_contract",
            "downstream_probe_tests": [
                "graphene/types/tests/test_schema.py::test_schema_get_type",
                "graphene/types/tests/test_definition.py::test_defines_a_query_only_schema",
            ],
            "integrated_probe_tests": [
                "graphene/types/tests/test_scalars_serialization.py::test_serializes_output_int",
                "graphene/types/tests/test_scalars_serialization.py::test_serializes_output_float",
                "graphene/types/tests/test_scalars_serialization.py::test_serializes_output_string",
                "graphene/types/tests/test_schema.py::test_schema_get_type",
                "graphene/types/tests/test_definition.py::test_defines_a_query_only_schema",
            ],
            "metrics_enabled": ["ADPR", "DRS", "CAIL", "SAD"],
            "producer_agent": "mounting_agent",
            "producer_files": [
                "graphene/types/scalars.py",
                "graphene/types/unmountedtype.py",
            ],
            "producer_subproblem": "type_mounting_layer",
            "resolution_criteria": "Resolved when scalar serialization probes and schema get_type/query definition probes pass in the integrated workspace.",
            "stale_failure_mode": "The schema agent may assume scalar conversion or get_type behavior that differs from the mounting agent's scalar implementation.",
            "upstream_probe_tests": [
                "graphene/types/tests/test_scalars_serialization.py::test_serializes_output_int",
                "graphene/types/tests/test_scalars_serialization.py::test_serializes_output_float",
                "graphene/types/tests/test_scalars_serialization.py::test_serializes_output_string",
            ],
        },
    ]
    return {
        "aggregate_metrics": {
            "ADPR_denominator": "All dependency_points unless a paper section explicitly reports primary_async_dependency_ids only.",
            "dependency_point_count": 3,
            "minimum_success_condition_for_task_level_async_dependency_resolution": "All primary_async_dependency_ids pass in the final integrated workspace.",
            "primary_async_dependency_ids": [
                "graphene.mounting_to_object.fields_contract",
                "graphene.object_metadata_to_schema.typemap_contract",
                "graphene.scalars_to_schema.coercion_execution_contract",
            ],
            "primary_paper_dependency_id": "graphene.object_metadata_to_schema.typemap_contract",
        },
        "annotation_notes": [
            "The object_metadata_to_schema dependency is the primary signal because schema/TypeMap conversion is sensitive to stale object, input, enum, union, and field metadata contracts.",
            "The mounting_to_object dependency captures stale assumptions around mounted fields, input fields, arguments, scalar get_type, and ordering.",
            "The scalars_to_schema dependency captures stale assumptions around scalar serialization/coercion and schema conversion.",
            "These labels identify public test-observable contracts, not solution code.",
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
        "metric_annotation_id": "commit0-graphene.async-metrics.v0.3",
        "metric_definitions": metric_definitions,
        "purpose": "Dependency-level labels for measuring whether asynchronous multi-agent coding resolves Graphene mounting, object/input metadata, scalar, schema, and TypeMap contracts.",
        "schema_version": "0.3-async-metrics",
        "source_quality_record": "manifests/pilot/v0.3/quality/commit0_graphene.json",
        "source_task_record": "manifests/pilot/v0.3/tasks/commit0_graphene.json",
        "task_id": TASK_ID,
    }


def _annotation_form(annotator_id: str) -> dict:
    return {
        "allowed_labels": [
            "parallelizable",
            "partially_parallelizable",
            "effectively_serial",
        ],
        "annotator_id": annotator_id,
        "candidate_evidence_file": "docs/audits/COMMIT0_CANDIDATE_REVIEW_networkx_graphene_tlslite_v0.3.md",
        "exclusion_reason": None,
        "include": None,
        "independence_instructions": [
            "Use only public Commit0 evidence, the audit note, and the draft task record.",
            "Review the linked TaskQualityRecord, including the requirement to use origin/commit0_combined plus checksum-recorded bootstrap overlays.",
            "Do not inspect reference branches, solution patches, or diffs.",
            "Do not consult the other annotator before submitting.",
            "Explicitly assess whether the mounting/object-input/schema splits are natural AsyncCodeBench dependencies rather than artificial file partitioning.",
            "Explicitly assess whether the props bootstrap overlay is acceptable as a non-solution collection prerequisite for the scoped type/schema task.",
        ],
        "parallelizability_label": None,
        "rationale": None,
        "schema_version": "0.3",
        "task_id": TASK_ID,
        "task_record_file": "manifests/pilot/v0.3/tasks/commit0_graphene.json",
    }


def _adjudication_template() -> dict:
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


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _update_curated_config() -> None:
    path = Path("configs/tasks/commit0_curated_tasks.v0.3.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    tasks = [task for task in payload["tasks"] if task["task_id"] != TASK_ID]
    tasks.append(
        {
            "task_id": TASK_ID,
            "repository": "graphene",
            "base_ref": BASE_REF,
            "base_sha": STRIPPED_SHA,
            "overlays": _overlay_entries(),
        }
    )
    payload["tasks"] = tasks
    _write_json(path, payload)


def main() -> None:
    files = {
        Path("manifests/pilot/v0.3/tasks/commit0_graphene.json"): _task_record(),
        Path("manifests/pilot/v0.3/scenarios/commit0_graphene.json"): _scenario_record(),
        Path("manifests/pilot/v0.3/quality/commit0_graphene.json"): _quality_record(),
        Path("manifests/pilot/v0.3/metrics/commit0_graphene_async_metrics.json"): _metrics_record(),
        Path("manifests/annotations/commit0_v0.3/graphene/annotator_a.json"): _annotation_form("annotator_a"),
        Path("manifests/annotations/commit0_v0.3/graphene/annotator_b.json"): _annotation_form("annotator_b"),
        Path("manifests/annotations/commit0_v0.3/graphene/adjudication.template.json"): _adjudication_template(),
    }
    for path, payload in files.items():
        _write_json(path, payload)
    _update_curated_config()
    for path in files:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload["task_id"] != TASK_ID:
            raise ValueError(f"unexpected task_id in {path}: {payload['task_id']}")
    print(f"generated {TASK_ID} v0.3 manifest files")


if __name__ == "__main__":
    main()
