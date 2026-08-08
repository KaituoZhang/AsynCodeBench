"""Build v0.3 python-rsa task/scenario records from public Commit0 evidence."""

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

PYTHON_RSA_TASK_ID = "commit0:python-rsa"
PYTHON_RSA_STRIPPED_SHA = "228b947d61f06612107205ab369a017ff63f9a8f"
PYTHON_RSA_COMPLETE_SHA = "63772a68c3cd74b8714302f33d1ac13ec1a1fa52"
PYTHON_RSA_QUALITY_FILE = (
    "manifests/pilot/v0.3/quality/commit0_python_rsa.json"
)
PYTHON_RSA_TASK_STATEMENT = """
Restore the core python-rsa behavior exercised by the public Commit0 tests
without modifying the tests.

The arithmetic layer must implement integer sizing, modular inverses,
primality checks, and integer/byte codecs. The key layer must consume those
contracts to generate keys, calculate CRT exponents and blinding factors, and
load/save DER and PEM keys. The PKCS#1 layer must build on the key and codec
contracts to implement encryption/decryption and signing/verification.

Benchmark evaluation uses the public core-library tests for common arithmetic,
key generation, load/save, PEM, PKCS#1, primality, transforms, and string
round-trips. Peripheral CLI, parallel execution, mypy, and secondary PKCS#1 v2
tests are excluded from this v0.3 evaluator subset.
""".strip()


def _load_candidate(candidate_file: Path) -> dict[str, Any]:
    inventory = json.loads(candidate_file.read_text(encoding="utf-8"))
    records = inventory.get("records") or inventory.get("candidates") or []
    matches = [
        candidate
        for candidate in records
        if candidate["task_id"] == PYTHON_RSA_TASK_ID
    ]
    if len(matches) != 1:
        raise ValueError("expected exactly one commit0:python-rsa candidate")
    return matches[0]


def dependency_annotations() -> tuple[DependencyAnnotation, ...]:
    return (
        DependencyAnnotation(
            producer_subproblem="arithmetic_and_codec_core",
            consumer_subproblem="key_generation_and_model",
            dependency_type="api_contract",
            description=(
                "Key generation and PrivateKey/PublicKey helpers consume "
                "common arithmetic, modular inverse, primality, random-prime, "
                "and integer-size contracts. Stale assumptions about inverse "
                "or byte-size behavior cause key exponent, coefficient, and "
                "blinding failures."
            ),
            evidence_paths=(
                "rsa/common.py",
                "rsa/prime.py",
                "rsa/randnum.py",
                "rsa/transform.py",
                "rsa/key.py",
                "tests/test_common.py",
                "tests/test_prime.py",
                "tests/test_transform.py",
                "tests/test_key.py",
            ),
        ),
        DependencyAnnotation(
            producer_subproblem="key_generation_and_model",
            consumer_subproblem="serialization_contracts",
            dependency_type="integration",
            description=(
                "DER/PEM load-save behavior depends on the key model's "
                "field layout, CRT exponent/coefficient recalculation, "
                "equality semantics, and pyasn1 DER conversion contract."
            ),
            evidence_paths=(
                "rsa/key.py",
                "rsa/asn1.py",
                "rsa/pem.py",
                "tests/test_load_save_keys.py",
                "tests/test_pem.py",
            ),
        ),
        DependencyAnnotation(
            producer_subproblem="arithmetic_and_codec_core",
            consumer_subproblem="pkcs1_crypto_api",
            dependency_type="api_contract",
            description=(
                "PKCS#1 encryption, decryption, signing, verification, and "
                "padding validation consume integer/byte codecs, byte-size "
                "calculation, key generation, and key serialization behavior."
            ),
            evidence_paths=(
                "rsa/common.py",
                "rsa/core.py",
                "rsa/transform.py",
                "rsa/key.py",
                "rsa/pkcs1.py",
                "tests/test_pkcs1.py",
                "tests/test_strings.py",
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
        "tests/test_common.py",
        "tests/test_key.py",
        "tests/test_load_save_keys.py",
        "tests/test_pem.py",
        "tests/test_pkcs1.py",
        "tests/test_prime.py",
        "tests/test_transform.py",
        "tests/test_strings.py",
    )


def build_task_record(candidate_file: Path) -> TaskRecord:
    _load_candidate(candidate_file)
    return TaskRecord(
        task_id=PYTHON_RSA_TASK_ID,
        task_source="Commit0",
        upstream_version=PYTHON_RSA_STRIPPED_SHA,
        repository="commit0/python-rsa",
        source_materialization=(
            "git archive of the stripped Commit0-style python-rsa ref "
            f"origin/commit0_combined at {PYTHON_RSA_STRIPPED_SHA}"
        ),
        problem_statement=PYTHON_RSA_TASK_STATEMENT,
        evaluator_command=_evaluator_command(),
        test_targets=(
            "tests/test_common.py",
            "tests/test_key.py",
            "tests/test_load_save_keys.py",
            "tests/test_pem.py",
            "tests/test_pkcs1.py",
            "tests/test_prime.py",
            "tests/test_transform.py",
            "tests/test_strings.py",
        ),
        publicly_implicated_modules=(
            "rsa/common.py",
            "rsa/prime.py",
            "rsa/randnum.py",
            "rsa/transform.py",
            "rsa/core.py",
            "rsa/key.py",
            "rsa/asn1.py",
            "rsa/pem.py",
            "rsa/pkcs1.py",
        ),
        natural_subproblems={
            "arithmetic_and_codec_core": (
                "rsa/common.py",
                "rsa/prime.py",
                "rsa/randnum.py",
                "rsa/transform.py",
                "rsa/core.py",
                "tests/test_common.py",
                "tests/test_prime.py",
                "tests/test_transform.py",
            ),
            "key_generation_and_model": (
                "rsa/key.py",
                "tests/test_key.py",
            ),
            "serialization_contracts": (
                "rsa/asn1.py",
                "rsa/pem.py",
                "tests/test_load_save_keys.py",
                "tests/test_pem.py",
            ),
            "pkcs1_crypto_api": (
                "rsa/pkcs1.py",
                "tests/test_pkcs1.py",
                "tests/test_strings.py",
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
        quality_evidence_file=PYTHON_RSA_QUALITY_FILE,
        notes=(
            "Task source, tests, and stripped Commit0-style implementation are unchanged.",
            (
                "The local main/commit0 branch is complete; benchmark "
                "workspaces must be materialized from origin/commit0_combined."
            ),
            (
                "The evaluator subset focuses on the core library dependency "
                "chain and excludes CLI, parallel, mypy, and pkcs1_v2 tests."
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
                    "rsa/common.py",
                    "rsa/prime.py",
                    "rsa/randnum.py",
                    "rsa/transform.py",
                    "rsa/core.py",
                    "rsa/key.py",
                    "rsa/asn1.py",
                    "rsa/pem.py",
                    "rsa/pkcs1.py",
                ),
                primary_test_targets=_evaluator_command()[6:],
            ),
        )
    return (
        AgentAssignment(
            agent_id="arithmetic_agent",
            role="number theory and integer codec specialist",
            subproblem_id="arithmetic_and_codec_core",
            writable_paths=(
                "rsa/common.py",
                "rsa/prime.py",
                "rsa/randnum.py",
                "rsa/transform.py",
                "rsa/core.py",
            ),
            primary_test_targets=(
                "tests/test_common.py",
                "tests/test_prime.py",
                "tests/test_transform.py",
            ),
        ),
        AgentAssignment(
            agent_id="key_agent",
            role="RSA key generation and key model specialist",
            subproblem_id="key_generation_and_model",
            writable_paths=("rsa/key.py",),
            primary_test_targets=("tests/test_key.py",),
        ),
        AgentAssignment(
            agent_id="serialization_agent",
            role="DER and PEM serialization specialist",
            subproblem_id="serialization_contracts",
            writable_paths=("rsa/asn1.py", "rsa/pem.py"),
            primary_test_targets=(
                "tests/test_load_save_keys.py",
                "tests/test_pem.py",
            ),
        ),
        AgentAssignment(
            agent_id="pkcs1_agent",
            role="PKCS#1 encryption and signing API specialist",
            subproblem_id="pkcs1_crypto_api",
            writable_paths=("rsa/pkcs1.py",),
            primary_test_targets=(
                "tests/test_pkcs1.py",
                "tests/test_strings.py",
            ),
        ),
    )


def build_scenarios() -> tuple[ScenarioRecord, ...]:
    shared = {
        "task_id": PYTHON_RSA_TASK_ID,
        "dependency_annotations": dependency_annotations(),
        "shared_agent_scaffold": "iterative-inspect-edit-test-repair",
        "step_budget_per_agent": 24,
        "token_budget_per_agent": 65000,
        "test_budget_per_agent": 10,
        "wall_clock_budget_seconds": 2400,
    }
    return (
        ScenarioRecord(
            **shared,
            scenario_id="commit0-python-rsa.iterative-single.v0.3",
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
            scenario_id="commit0-python-rsa.serial-specialists.v0.3",
            execution_mode=ExecutionMode.SERIAL_SPECIALISTS,
            agent_count=4,
            assignments=_assignments(ExecutionMode.SERIAL_SPECIALISTS),
            information_profile="private-workspace",
            concurrent_execution=False,
            communication_condition="completed_artifact_handoff",
            message_delivery_policy=(
                "Specialists run with barrier synchronization. Key, "
                "serialization, and PKCS#1 workers receive completed upstream "
                "arithmetic/key artifacts and targeted test results before "
                "dependent work starts."
            ),
            integration_policy=(
                "Apply arithmetic/codec artifacts first, then key artifacts, "
                "then serialization and PKCS#1 artifacts before running the "
                "full evaluator."
            ),
        ),
        ScenarioRecord(
            **shared,
            scenario_id="commit0-python-rsa.async-private.v0.3",
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
            scenario_id="commit0-python-rsa.async-message.v0.3",
            execution_mode=ExecutionMode.ASYNC_MESSAGE,
            agent_count=4,
            assignments=_assignments(ExecutionMode.ASYNC_MESSAGE),
            information_profile="private-workspace",
            concurrent_execution=True,
            communication_condition="structured_message_and_artifact",
            message_delivery_policy=(
                "Workers may transfer arithmetic, key-model, serialization, "
                "and PKCS#1 contract assumptions while active."
            ),
            integration_policy=(
                "Integrate latest explicitly transferred artifacts and record "
                "stale arithmetic/key/serialization assumptions."
            ),
        ),
    )


def build_quality_record() -> TaskQualityRecord:
    evaluator = _evaluator_command()
    environment = {
        "pytest": "8.4.2",
        "pyasn1": "0.6.3",
    }
    return TaskQualityRecord(
        task_id=PYTHON_RSA_TASK_ID,
        quality_status=DatasetQualityStatus.QUALIFICATION_READY,
        coordination_structure_tags=(
            CoordinationStructureTag.INTERFACE_DEPENDENCY,
            CoordinationStructureTag.SHARED_ABSTRACTION,
        ),
        structure_rationale=(
            "The task exposes natural async contracts from arithmetic and "
            "integer codecs to key generation, then from key/serialization "
            "contracts to the PKCS#1 crypto API. Downstream agents can make "
            "plausible but stale assumptions about inverse behavior, key CRT "
            "fields, byte sizing, DER/PEM return types, or padding contracts."
        ),
        public_statement_sources=(
            "README.md@origin/commit0_combined",
            "rsa/*.py docstrings@origin/commit0_combined",
            "tests/test_*.py@origin/commit0_combined",
            "pyproject.toml@origin/commit0_combined",
        ),
        environment_requirements=(
            "Python 3.10.4",
            "pytest==8.4.2",
            "pyasn1==0.6.3",
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD=1",
            "Run from the repository root with PYTHONPATH=.",
            (
                "Use the stripped source ref origin/commit0_combined, not the "
                "local complete/default main or commit0 branch."
            ),
        ),
        test_groups=(
            TaskTestGroup(
                group_id="arithmetic_codec_local",
                purpose=TestGroupPurpose.SPECIALIST_LOCAL,
                owner_subproblem="arithmetic_and_codec_core",
                command=(
                    "python",
                    "-m",
                    "pytest",
                    "-q",
                    "-o",
                    "addopts=",
                    "tests/test_common.py",
                    "tests/test_prime.py",
                    "tests/test_transform.py",
                ),
                description=(
                    "Integer sizing, modular inverse, primality, random-prime "
                    "support, and integer/byte codec behavior."
                ),
            ),
            TaskTestGroup(
                group_id="key_model_local",
                purpose=TestGroupPurpose.SPECIALIST_LOCAL,
                owner_subproblem="key_generation_and_model",
                command=(
                    "python",
                    "-m",
                    "pytest",
                    "-q",
                    "-o",
                    "addopts=",
                    "tests/test_key.py",
                ),
                description=(
                    "RSA key generation, exponent/coefficient calculation, "
                    "blinding, and key hashability."
                ),
            ),
            TaskTestGroup(
                group_id="serialization_local",
                purpose=TestGroupPurpose.SPECIALIST_LOCAL,
                owner_subproblem="serialization_contracts",
                command=(
                    "python",
                    "-m",
                    "pytest",
                    "-q",
                    "-o",
                    "addopts=",
                    "tests/test_load_save_keys.py",
                    "tests/test_pem.py",
                ),
                description="DER and PEM load/save behavior for public and private keys.",
            ),
            TaskTestGroup(
                group_id="pkcs1_local",
                purpose=TestGroupPurpose.SPECIALIST_LOCAL,
                owner_subproblem="pkcs1_crypto_api",
                command=(
                    "python",
                    "-m",
                    "pytest",
                    "-q",
                    "-o",
                    "addopts=",
                    "tests/test_pkcs1.py",
                    "tests/test_strings.py",
                ),
                description="PKCS#1 encrypt/decrypt, sign/verify, and string round-trips.",
            ),
            TaskTestGroup(
                group_id="arithmetic_key_cross_contract",
                purpose=TestGroupPurpose.CROSS_SUBPROBLEM,
                command=(
                    "python",
                    "-m",
                    "pytest",
                    "-q",
                    "-o",
                    "addopts=",
                    "tests/test_common.py::TestInverse::test_normal",
                    "tests/test_prime.py::PrimeTest::test_is_prime",
                    "tests/test_key.py::KeyGenTest::test_default_exponent",
                    "tests/test_key.py::KeyGenTest::test_custom_exponent",
                ),
                description=(
                    "Key generation after modular inverse and primality "
                    "contracts are integrated."
                ),
                prerequisites=(
                    "arithmetic_and_codec_core artifact is integrated",
                    "key_generation_and_model artifact is integrated",
                ),
            ),
            TaskTestGroup(
                group_id="serialization_pkcs1_cross_contract",
                purpose=TestGroupPurpose.CROSS_SUBPROBLEM,
                command=(
                    "python",
                    "-m",
                    "pytest",
                    "-q",
                    "-o",
                    "addopts=",
                    "tests/test_load_save_keys.py::PemTest::test_load_private_key",
                    "tests/test_pem.py::TestMarkers::test_values",
                    "tests/test_pkcs1.py::SignatureTest::test_sign_verify",
                ),
                description=(
                    "PKCS#1 signing after key model and PEM/DER serialization "
                    "contracts are integrated."
                ),
                prerequisites=(
                    "key_generation_and_model artifact is integrated",
                    "serialization_contracts artifact is integrated",
                    "pkcs1_crypto_api artifact is integrated",
                ),
            ),
            TaskTestGroup(
                group_id="full_evaluator",
                purpose=TestGroupPurpose.FULL_EVALUATOR,
                command=evaluator,
                description=(
                    "Core public python-rsa tests for common arithmetic, key "
                    "generation, load/save, PEM, PKCS#1, primality, transforms, "
                    "and string round-trips."
                ),
            ),
        ),
        evaluation_snapshots=(
            EvaluationSnapshot(
                snapshot_id="commit0_combined_initial_evaluator",
                source_ref=f"origin/commit0_combined:{PYTHON_RSA_STRIPPED_SHA}",
                evidence_scope="public_initial_state",
                command=evaluator,
                python_version="3.10.4",
                dependency_versions=environment,
                collected=66,
                passed=2,
                failed=64,
                errors=0,
                skipped=0,
                return_code=1,
                duration_seconds=0.33,
                notes=(
                    (
                        "Verified in the AsynCodeBench conda environment "
                        "with PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 and PYTHONPATH=."
                    ),
                    (
                        "The command uses -o addopts= to disable the upstream "
                        "pytest-cov addopts requirement in this minimal "
                        "benchmark environment."
                    ),
                    (
                        "Failures are substantive unfinished implementation "
                        "failures across arithmetic, key generation, "
                        "serialization, and PKCS#1 behavior."
                    ),
                ),
            ),
            EvaluationSnapshot(
                snapshot_id="complete_commit0_evaluator_sanity",
                source_ref=f"commit0/main:{PYTHON_RSA_COMPLETE_SHA}",
                evidence_scope="evaluator_sanity_only",
                command=evaluator,
                python_version="3.10.4",
                dependency_versions=environment,
                collected=78,
                passed=78,
                failed=0,
                errors=0,
                skipped=0,
                return_code=0,
                duration_seconds=1.95,
                notes=(
                    (
                        "The local complete/default main branch passes the "
                        "same scoped evaluator after installing pyasn1, the "
                        "runtime dependency declared in pyproject.toml."
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
                "The local main/commit0 branch is complete. Benchmark "
                "workspaces must be materialized from origin/commit0_combined."
            ),
            (
                "CLI, parallel, mypy, and pkcs1_v2 tests are excluded because "
                "the v0.3 task targets the core library dependency chain."
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
        "task_id": PYTHON_RSA_TASK_ID,
        "metric_annotation_id": "commit0-python-rsa.async-metrics.v0.3",
        "source_task_record": "manifests/pilot/v0.3/tasks/commit0_python_rsa.json",
        "source_quality_record": (
            "manifests/pilot/v0.3/quality/commit0_python_rsa.json"
        ),
        "purpose": (
            "Dependency-level labels for measuring whether asynchronous "
            "multi-agent coding resolves python-rsa's arithmetic, key, "
            "serialization, and PKCS#1 contracts promptly."
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
                "dependency_id": "python_rsa.arithmetic_to_key_generation.inverse_prime_contract",
                "dependency_type": "interface_dependency",
                "producer_subproblem": "arithmetic_and_codec_core",
                "consumer_subproblem": "key_generation_and_model",
                "producer_agent": "arithmetic_agent",
                "consumer_agent": "key_agent",
                "producer_files": [
                    "rsa/common.py",
                    "rsa/prime.py",
                    "rsa/randnum.py",
                    "rsa/transform.py",
                ],
                "consumer_files": ["rsa/key.py"],
                "contract_summary": (
                    "Key generation must consume modular inverse, primality, "
                    "prime selection, byte-size, and integer codec behavior "
                    "with the same return types and exception semantics."
                ),
                "stale_failure_mode": (
                    "The key agent may implement gen_keys/newkeys or CRT "
                    "fields against stale inverse/prime/byte-size assumptions, "
                    "causing key tests and downstream PKCS#1 setup to fail."
                ),
                "upstream_probe_tests": [
                    "tests/test_common.py::TestInverse::test_normal",
                    "tests/test_prime.py::PrimeTest::test_is_prime",
                    "tests/test_transform.py::Test_int2bytes::test_codec_identity",
                ],
                "downstream_probe_tests": [
                    "tests/test_key.py::KeyGenTest::test_default_exponent",
                    "tests/test_key.py::KeyGenTest::test_custom_exponent",
                    "tests/test_key.py::KeyGenTest::test_exponents_coefficient_calculation",
                ],
                "integrated_probe_tests": [
                    "tests/test_common.py::TestInverse::test_normal",
                    "tests/test_prime.py::PrimeTest::test_is_prime",
                    "tests/test_key.py::KeyGenTest::test_default_exponent",
                    "tests/test_key.py::KeyGenTest::test_custom_exponent",
                ],
                "resolution_criteria": (
                    "Resolved when arithmetic probes and key-generation "
                    "consumer probes pass in the integrated workspace."
                ),
                "metrics_enabled": ["ADPR", "DRS", "CAIL", "SAD"],
                "primary_paper_probe": True,
            },
            {
                "dependency_id": "python_rsa.key_to_serialization.pem_der_contract",
                "dependency_type": "integration_contract",
                "producer_subproblem": "key_generation_and_model",
                "consumer_subproblem": "serialization_contracts",
                "producer_agent": "key_agent",
                "consumer_agent": "serialization_agent",
                "producer_files": ["rsa/key.py"],
                "consumer_files": ["rsa/asn1.py", "rsa/pem.py"],
                "contract_summary": (
                    "DER/PEM load-save functions must preserve the PublicKey "
                    "and PrivateKey field layout, CRT exponent/coefficient "
                    "recalculation, equality semantics, and byte return types."
                ),
                "stale_failure_mode": (
                    "The serialization agent may assume a stale key field "
                    "layout or malformed-key behavior, leading to clean file "
                    "edits that fail only in load/save integration tests."
                ),
                "upstream_probe_tests": [
                    "tests/test_key.py::KeyGenTest::test_exponents_coefficient_calculation",
                    "tests/test_key.py::HashTest::test_hash_possible",
                ],
                "downstream_probe_tests": [
                    "tests/test_load_save_keys.py::PemTest::test_load_private_key",
                    "tests/test_load_save_keys.py::DerTest::test_load_public_key",
                    "tests/test_pem.py::TestMarkers::test_values",
                ],
                "integrated_probe_tests": [
                    "tests/test_key.py::KeyGenTest::test_exponents_coefficient_calculation",
                    "tests/test_load_save_keys.py::PemTest::test_load_private_key",
                    "tests/test_load_save_keys.py::DerTest::test_load_public_key",
                    "tests/test_pem.py::TestMarkers::test_values",
                ],
                "resolution_criteria": (
                    "Resolved when key-field probes and public DER/PEM "
                    "load-save probes pass after integration."
                ),
                "metrics_enabled": ["ADPR", "DRS", "CAIL", "SAD"],
            },
            {
                "dependency_id": "python_rsa.codec_key_to_pkcs1.crypto_api_contract",
                "dependency_type": "shared_api_contract",
                "producer_subproblem": "arithmetic_and_codec_core",
                "consumer_subproblem": "pkcs1_crypto_api",
                "producer_agent": "arithmetic_agent",
                "consumer_agent": "pkcs1_agent",
                "producer_files": [
                    "rsa/common.py",
                    "rsa/core.py",
                    "rsa/transform.py",
                    "rsa/key.py",
                ],
                "consumer_files": ["rsa/pkcs1.py"],
                "contract_summary": (
                    "PKCS#1 encrypt/decrypt and sign/verify must consume "
                    "byte-size, int2bytes/bytes2int, raw encrypt/decrypt, and "
                    "key-generation behavior consistently."
                ),
                "stale_failure_mode": (
                    "The PKCS#1 agent may implement padding or signature "
                    "logic against stale byte-size or key assumptions, causing "
                    "late integrated failures in encryption or signature tests."
                ),
                "upstream_probe_tests": [
                    "tests/test_common.py::TestByteSize::test_values",
                    "tests/test_transform.py::Test_int2bytes::test_accuracy",
                    "tests/test_key.py::KeyGenTest::test_default_exponent",
                ],
                "downstream_probe_tests": [
                    "tests/test_pkcs1.py::BinaryTest::test_enc_dec",
                    "tests/test_pkcs1.py::SignatureTest::test_sign_verify",
                    "tests/test_strings.py::StringTest::test_enc_dec",
                ],
                "integrated_probe_tests": [
                    "tests/test_common.py::TestByteSize::test_values",
                    "tests/test_transform.py::Test_int2bytes::test_accuracy",
                    "tests/test_key.py::KeyGenTest::test_default_exponent",
                    "tests/test_pkcs1.py::BinaryTest::test_enc_dec",
                    "tests/test_pkcs1.py::SignatureTest::test_sign_verify",
                ],
                "resolution_criteria": (
                    "Resolved when codec/key probes and PKCS#1 encryption/"
                    "signature probes pass in the integrated workspace."
                ),
                "metrics_enabled": ["ADPR", "DRS", "CAIL", "SAD"],
            },
        ],
        "aggregate_metrics": {
            "dependency_point_count": 3,
            "primary_async_dependency_ids": [
                "python_rsa.arithmetic_to_key_generation.inverse_prime_contract",
                "python_rsa.codec_key_to_pkcs1.crypto_api_contract",
            ],
            "primary_paper_dependency_id": (
                "python_rsa.arithmetic_to_key_generation.inverse_prime_contract"
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
                "The arithmetic_to_key_generation dependency is the primary "
                "signal because key generation can appear locally plausible "
                "while consuming stale inverse, primality, or byte-size behavior."
            ),
            (
                "The codec_key_to_pkcs1 dependency captures the crypto API "
                "async risk: PKCS#1 logic depends on shared integer/byte and "
                "key contracts and can fail after clean patch integration."
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
        "task_id": PYTHON_RSA_TASK_ID,
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
                "Explicitly assess whether the arithmetic->key, key->serialization, "
                "and codec/key->PKCS#1 splits are natural AsynCodeBench "
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
        task_id=PYTHON_RSA_TASK_ID,
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
