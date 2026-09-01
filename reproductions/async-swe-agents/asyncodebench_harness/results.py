"""Build and validate portable, evidence-backed AsynCodeBench run bundles."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from jsonschema import Draft202012Validator

from .health import inspect_run

RUN_BUNDLE_SCHEMA_VERSION = "0.2"
REQUIRED_ARTIFACTS = (
    "run_metadata.json",
    "task_snapshot.json",
    "scenario_snapshot.json",
    "scenario_manifest_snapshot.json",
    "metrics_snapshot.json",
    "quality_snapshot.json",
    "execution_profile_snapshot.json",
    "protocol.json",
    "report.json",
    "dependency_probe_checkpoints.jsonl",
    "process_metrics_summary.json",
    "cost.json",
    "runtime.txt",
)
PROTOCOLS = {
    "single",
    "serial_specialists",
    "async_private",
    "caid_manager",
}
SNAPSHOT_TO_METADATA_KEY = {
    "task_snapshot.json": "task",
    "scenario_manifest_snapshot.json": "scenario",
    "metrics_snapshot.json": "metrics",
    "quality_snapshot.json": "quality",
}


def _repo_root() -> Path:
    configured = os.getenv("ASYNCODEBENCH_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()
    return Path(__file__).resolve().parents[3]


def _schema_path() -> Path:
    return _repo_root() / "schemas" / "release" / "run_bundle.schema.json"


def _release_index_path(release: str) -> Path:
    release_name = str(release)
    if Path(release_name).name != release_name:
        raise ValueError(f"Invalid release identifier: {release_name!r}")
    return _repo_root() / "manifests" / "release" / release_name / "task_index.json"


def _candidate_registry_path() -> Path:
    return _repo_root() / "configs" / "tasks" / "pr_hard_candidates.v0.4.json"


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_sha256(value):
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _read_json(path, issues, label):
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        issues.append(f"invalid_{label}:{type(exc).__name__}")
        return {}
    if not isinstance(value, dict):
        issues.append(f"invalid_{label}:not_object")
        return {}
    return value


def _dedupe(values):
    return list(dict.fromkeys(values))


def _status(hard_failures, review_flags):
    if hard_failures:
        return "invalid"
    if review_flags:
        return "review_required"
    return "valid"


def _schema_errors(payload):
    schema_path = _schema_path()
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"run_bundle_schema_unavailable:{type(exc).__name__}"]
    validator = Draft202012Validator(schema)
    errors = []
    for error in sorted(
        validator.iter_errors(payload), key=lambda item: list(item.path)
    ):
        location = ".".join(str(item) for item in error.path) or "$"
        errors.append(f"run_bundle_schema:{location}:{error.message}")
    return errors


def _artifact_inventory(output_dir):
    output_dir = Path(output_dir)
    names = sorted(
        path.relative_to(output_dir).as_posix()
        for path in output_dir.rglob("*")
        if path.is_file() and path.name != "run_bundle.json"
    )
    return {
        name: {
            "sha256": _sha256(output_dir / name),
            "bytes": (output_dir / name).stat().st_size,
        }
        for name in names
    }


def _cross_artifact_checks(run_dir, expected):
    issues = []
    metadata = _read_json(run_dir / "run_metadata.json", issues, "run_metadata")
    protocol = _read_json(run_dir / "protocol.json", issues, "protocol")
    report = _read_json(run_dir / "report.json", issues, "report")
    profile = _read_json(
        run_dir / "execution_profile_snapshot.json",
        issues,
        "execution_profile_snapshot",
    )
    active_scenario = _read_json(
        run_dir / "scenario_snapshot.json", issues, "scenario_snapshot"
    )
    source_documents = {
        name: _read_json(run_dir / filename, issues, name)
        for name, filename in {
            "task_snapshot": "task_snapshot.json",
            "scenario_manifest_snapshot": "scenario_manifest_snapshot.json",
            "metrics_snapshot": "metrics_snapshot.json",
            "quality_snapshot": "quality_snapshot.json",
        }.items()
    }

    for field in (
        "task_id",
        "source_task_id",
        "protocol",
        "scenario_id",
        "source_scenario_id",
    ):
        expected_value = expected.get(field)
        if metadata.get(field) != expected_value:
            issues.append(f"run_metadata_identity_mismatch:{field}")
        if protocol.get(field) != expected_value:
            issues.append(f"protocol_identity_mismatch:{field}")

    if metadata.get("release") != expected.get("release"):
        issues.append("run_metadata_identity_mismatch:release")
    if metadata.get("agent_adapter") != expected.get("agent_adapter"):
        issues.append("run_metadata_identity_mismatch:agent_adapter")
    if active_scenario.get("scenario_id") != expected.get("source_scenario_id"):
        issues.append("scenario_snapshot_identity_mismatch:source_scenario_id")
    scenario_manifest = source_documents["scenario_manifest_snapshot"]
    if active_scenario not in (scenario_manifest.get("scenarios", []) or []):
        issues.append("active_scenario_not_in_scenario_manifest")

    for name, document in source_documents.items():
        if document.get("task_id") != expected.get("source_task_id"):
            issues.append(f"source_manifest_task_id_mismatch:{name}")

    report_source = report.get("asyncodebench", {}).get("final_evaluator_source")
    expected_evaluator = (
        "pr_hard_v0.4_manifest"
        if metadata.get("candidate_lane", {}).get("kind") == "pr_hard_v0.4"
        else "asyncodebench_manifest"
    )
    if report_source != expected_evaluator:
        issues.append(f"wrong_evaluator:{report_source}")

    profile_metadata = metadata.get("execution_profile", {})
    if profile_metadata.get("profile_id") != profile.get("profile_id"):
        issues.append("execution_profile_id_mismatch")
    profile_path = run_dir / "execution_profile_snapshot.json"
    if profile_path.is_file() and profile_metadata.get("sha256") != _sha256(
        profile_path
    ):
        issues.append("execution_profile_checksum_mismatch")

    budgets = metadata.get("budgets", {})
    observed = profile_metadata.get("observed", {})
    for field in (
        "manager_max_iterations",
        "max_subagents",
        "subagent_max_iterations",
        "max_rounds_chat",
    ):
        if observed.get(field) != budgets.get(field):
            issues.append(f"execution_profile_observation_mismatch:{field}")

    for snapshot_name, metadata_key in SNAPSHOT_TO_METADATA_KEY.items():
        snapshot_path = run_dir / snapshot_name
        recorded = metadata.get("artifacts", {}).get(metadata_key, {})
        if snapshot_path.is_file() and recorded.get("sha256") != _sha256(snapshot_path):
            issues.append(f"manifest_snapshot_checksum_mismatch:{snapshot_name}")

    return _dedupe(issues), metadata, report, profile


def _release_contract_checks(run_dir, expected, metadata):
    """Verify frozen runtime inputs against the released benchmark inventory."""

    if metadata.get("candidate_lane", {}).get("kind") == "pr_hard_v0.4":
        return _candidate_contract_checks(run_dir, expected, metadata)

    issues = []
    release = expected.get("release")
    try:
        index_path = _release_index_path(release)
    except ValueError:
        return ["invalid_release_identifier"], {}
    index = _read_json(index_path, issues, "release_index")
    try:
        recorded_index_path = index_path.relative_to(_repo_root()).as_posix()
    except ValueError:
        recorded_index_path = str(index_path)
    release_record = {
        "path": recorded_index_path,
        "sha256": _sha256(index_path) if index_path.is_file() else None,
        "release_version": index.get("release_version"),
    }
    if index.get("release") != release:
        issues.append("release_index_release_mismatch")

    task_record = next(
        (
            item
            for item in index.get("tasks", []) or []
            if item.get("task_id") == expected.get("task_id")
        ),
        None,
    )
    if not isinstance(task_record, dict):
        issues.append("task_not_in_release_index")
        return _dedupe(issues), release_record

    if task_record.get("source_task_id") != expected.get("source_task_id"):
        issues.append("release_source_task_id_mismatch")

    protocol_record = task_record.get("protocols", {}).get(expected.get("protocol"))
    if not isinstance(protocol_record, dict):
        issues.append("protocol_not_in_release_index")
    else:
        if protocol_record.get("scenario_id") != expected.get("scenario_id"):
            issues.append("release_scenario_id_mismatch")
        if protocol_record.get("source_scenario_id") != expected.get(
            "source_scenario_id"
        ):
            issues.append("release_source_scenario_id_mismatch")

    snapshot_artifacts = {
        "task_snapshot.json": "task",
        "scenario_manifest_snapshot.json": "scenarios",
        "metrics_snapshot.json": "metrics",
        "quality_snapshot.json": "quality",
    }
    release_artifacts = task_record.get("artifacts", {})
    for snapshot_name, artifact_name in snapshot_artifacts.items():
        snapshot_path = run_dir / snapshot_name
        expected_sha = release_artifacts.get(artifact_name, {}).get("sha256")
        if not expected_sha or not snapshot_path.is_file():
            issues.append(f"release_snapshot_unverifiable:{snapshot_name}")
        elif _sha256(snapshot_path) != expected_sha:
            issues.append(f"release_snapshot_checksum_mismatch:{snapshot_name}")

    recorded_source = metadata.get("source", {})
    release_source = task_record.get("source", {})
    for field in ("repository", "base_ref", "base_sha"):
        if recorded_source.get(field) != release_source.get(field):
            issues.append(f"release_source_mismatch:{field}")
    if recorded_source.get("overlays", []) != release_source.get("overlays", []):
        issues.append("release_source_mismatch:overlays")

    release_profile = index.get("execution_profile", {})
    profile_snapshot = run_dir / "execution_profile_snapshot.json"
    if metadata.get("execution_profile", {}).get("profile_id") != release_profile.get(
        "profile_id"
    ):
        issues.append("release_execution_profile_id_mismatch")
    if (
        not profile_snapshot.is_file()
        or not release_profile.get("sha256")
        or _sha256(profile_snapshot) != release_profile.get("sha256")
    ):
        issues.append("release_execution_profile_checksum_mismatch")

    return _dedupe(issues), release_record


def _candidate_contract_checks(run_dir, expected, metadata):
    """Verify PR-hard inputs against the frozen candidate registry.

    Construction records remain portable and checksum-verifiable. Qualified
    records enter the unified release; incomplete records remain diagnostic.
    """
    issues = []
    registry_path = _candidate_registry_path()
    registry = _read_json(registry_path, issues, "candidate_registry")
    try:
        recorded_path = registry_path.relative_to(_repo_root()).as_posix()
    except ValueError:
        recorded_path = str(registry_path)
    registry_record = {
        "path": recorded_path,
        "sha256": _sha256(registry_path) if registry_path.is_file() else None,
        "release_version": registry.get("schema_version"),
    }
    record = next(
        (
            item
            for item in registry.get("records", []) or []
            if item.get("task_id") == expected.get("task_id")
        ),
        None,
    )
    if not isinstance(record, dict):
        issues.append("task_not_in_candidate_registry")
        return _dedupe(issues), registry_record

    lane = metadata.get("candidate_lane", {})
    expected_official_eligibility = record.get("qualification_status") == "qualified"
    if lane.get("official_result_eligible") is not expected_official_eligibility:
        issues.append("candidate_official_eligibility_mismatch")
    if lane.get("qualification_status") != record.get("qualification_status"):
        issues.append("candidate_qualification_status_mismatch")
    recorded_source = metadata.get("source", {})
    if recorded_source.get("repository") != record.get("repository"):
        issues.append("candidate_source_mismatch:repository")
    if recorded_source.get("base_sha") != record.get("base_sha"):
        issues.append("candidate_source_mismatch:base_sha")
    return _dedupe(issues), registry_record


def _final_test_payload(report):
    summary = report.get("summary", {})
    metadata = report.get("asyncodebench", {})
    failed_collectors = [
        collector
        for collector in report.get("collectors", []) or []
        if isinstance(collector, dict) and collector.get("outcome") == "failed"
    ]
    passed = int(summary.get("passed", 0) or 0)
    failed = int(summary.get("failed", 0) or 0)
    errors = int(summary.get("error", summary.get("errors", 0)) or 0)
    collected = int(summary.get("collected", summary.get("total", 0)) or 0)
    synthetic = bool(metadata.get("synthetic_summary"))
    failure_kind = metadata.get("evaluation_failure_kind")
    if failed_collectors:
        errors = max(errors, len(failed_collectors))
        failure_kind = failure_kind or "collection_failed"
    success = (
        report.get("exitcode") == 0
        and collected > 0
        and failed == 0
        and errors == 0
        and not synthetic
    )
    if success:
        outcome = "passed"
    elif failure_kind:
        outcome = f"model_failure:{failure_kind}"
    else:
        outcome = "failed"
    return {
        "outcome": outcome,
        "success": success,
        "exit_code": report.get("exitcode"),
        "passed": passed,
        "failed": failed,
        "errors": errors,
        "collected": collected,
        "timed_out": bool(metadata.get("timed_out")),
        "synthetic_summary": synthetic,
        "evaluation_failure_kind": failure_kind,
    }


def _provenance(metadata, profile):
    revisions = metadata.get("code_revisions", {})
    generation_configuration = metadata.get("generation_configuration")
    model_server = metadata.get("model_server")
    required_fields = profile.get("required_provenance", []) or []
    missing_required_fields = []
    for field in required_fields:
        value = metadata.get(field)
        invalid_mapping = field in {
            "agent_adapter",
            "generation_configuration",
            "model_server",
            "prompt",
            "code_revisions",
            "source",
            "artifacts",
        } and (not isinstance(value, dict) or not value)
        invalid_scalar = isinstance(value, str) and not value.strip()
        if value is None or invalid_mapping or invalid_scalar:
            missing_required_fields.append(field)

    required_revisions = (
        "asyncodebench",
        "async_swe_agents",
        "software_agent_sdk",
    )
    if "code_revisions" in required_fields and not all(
        revisions.get(name) for name in required_revisions
    ):
        missing_required_fields.append("code_revisions.required_revisions")

    source = metadata.get("source", {})
    if "source" in required_fields and not all(
        source.get(name) for name in ("repository", "base_ref", "base_sha")
    ):
        missing_required_fields.append("source.repository_base_ref_sha")

    artifacts = metadata.get("artifacts", {})
    if "artifacts" in required_fields and not all(
        artifacts.get(name, {}).get("sha256")
        for name in ("task", "scenario", "metrics", "quality")
    ):
        missing_required_fields.append("artifacts.manifest_checksums")

    prompt = metadata.get("prompt", {})
    if "prompt" in required_fields and not prompt.get("sha256"):
        missing_required_fields.append("prompt.sha256")

    agent_adapter = metadata.get("agent_adapter", {})
    if "agent_adapter" in required_fields:
        if not all(agent_adapter.get(name) for name in ("name", "class")):
            missing_required_fields.append("agent_adapter.name_class")
        if not (
            agent_adapter.get("package_version")
            or agent_adapter.get("source_sha256")
        ):
            missing_required_fields.append(
                "agent_adapter.package_version_or_source_sha256"
            )
        required_adapter_fields = profile.get(
            "required_agent_adapter_fields", []
        ) or []
        if (
            "config_sha256" in required_adapter_fields
            and not agent_adapter.get("config_sha256")
        ):
            missing_required_fields.append("agent_adapter.config_sha256")

    missing_required_fields = _dedupe(missing_required_fields)
    return {
        "model": metadata.get("model"),
        "subagent_model": metadata.get("subagent_model"),
        "benchmark_revision": revisions.get("asyncodebench"),
        "runner_revision": revisions.get("async_swe_agents"),
        "sdk_revision": revisions.get("software_agent_sdk"),
        "prompt_sha256": prompt.get("sha256"),
        "generation_configuration_recorded": bool(
            isinstance(generation_configuration, dict) and generation_configuration
        ),
        "generation_configuration_sha256": (
            _json_sha256(generation_configuration)
            if isinstance(generation_configuration, dict)
            and generation_configuration
            else None
        ),
        "model_server_recorded": bool(
            isinstance(model_server, dict) and model_server
        ),
        "model_server_sha256": (
            _json_sha256(model_server)
            if isinstance(model_server, dict) and model_server
            else None
        ),
        "required_fields_complete": not missing_required_fields,
        "missing_required_fields": missing_required_fields,
    }


def _eligibility(health, profile_metadata, provenance, candidate_lane=None):
    values = dict(health.get("eligibility", {}))
    values["official_profile"] = bool(profile_metadata.get("matched"))
    values["provenance_complete"] = bool(provenance.get("required_fields_complete"))
    values["official_aggregate"] = (
        health.get("status") == "valid"
        and values.get("functional_metrics", False)
        and values.get("dependency_metrics", False)
        and values.get("efficiency_metrics", False)
        and values["official_profile"]
        and values["provenance_complete"]
        and not candidate_lane
    )
    return values


def build_run_bundle(task, output_dir, protocol, agent_adapter):
    """Freeze artifact checksums and strict result eligibility after a run."""

    output_dir = Path(output_dir)
    hard_failures = []
    missing = [name for name in REQUIRED_ARTIFACTS if not (output_dir / name).is_file()]
    hard_failures.extend(f"missing_artifact:{name}" for name in missing)

    report = (
        _read_json(output_dir / "report.json", hard_failures, "report")
        if "report.json" not in missing
        else {}
    )
    metadata = (
        _read_json(output_dir / "run_metadata.json", hard_failures, "run_metadata")
        if "run_metadata.json" not in missing
        else {}
    )
    expected = {
        "release": task.asyncodebench_config.release,
        "task_id": task.task_id,
        "source_task_id": task.source_task_id,
        "protocol": protocol,
        "scenario_id": task.public_scenario_id(protocol),
        "source_scenario_id": task.scenario_for(protocol).get("scenario_id"),
        "agent_adapter": agent_adapter.public_metadata(),
    }
    cross_issues, checked_metadata, checked_report, profile = _cross_artifact_checks(
        output_dir, expected
    )
    hard_failures.extend(cross_issues)
    metadata = checked_metadata or metadata
    report = checked_report or report
    release_issues, release_index = _release_contract_checks(
        output_dir, expected, metadata
    )
    hard_failures.extend(release_issues)

    health = inspect_run(output_dir)
    hard_failures.extend(health["hard_failures"])
    review_flags = list(health["review_flags"])
    observations = list(health["observations"])
    hard_failures = _dedupe(hard_failures)
    profile_metadata = metadata.get("execution_profile", {})
    provenance = _provenance(metadata, profile)
    eligibility = _eligibility(
        health, profile_metadata, provenance, metadata.get("candidate_lane")
    )
    if hard_failures or review_flags:
        eligibility["official_aggregate"] = False

    status = _status(hard_failures, review_flags)
    artifacts = _artifact_inventory(output_dir)
    payload = {
        "schema_version": RUN_BUNDLE_SCHEMA_VERSION,
        "benchmark": "AsynCodeBench",
        "release": task.asyncodebench_config.release,
        "task_id": task.task_id,
        "source_task_id": task.source_task_id,
        "protocol": protocol,
        "scenario_id": task.public_scenario_id(protocol),
        "source_scenario_id": task.scenario_for(protocol).get("scenario_id"),
        "release_index": release_index,
        "agent_adapter": agent_adapter.public_metadata(),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "eligibility": eligibility,
        "execution_profile": profile_metadata,
        "provenance": provenance,
        "instrumentation": {
            "valid": status == "valid",
            "status": status,
            "issues": hard_failures + review_flags,
            "hard_failures": hard_failures,
            "review_flags": review_flags,
            "observations": observations,
            "evaluator_source": health.get("evaluator_source"),
            "dependency_checkpoint_records": health.get("checkpoint_records", 0),
            "model_execution": health.get("model_execution", {}),
        },
        "final_test": _final_test_payload(report),
        "artifacts": artifacts,
    }

    schema_issues = _schema_errors(payload)
    if schema_issues:
        hard_failures = _dedupe(hard_failures + schema_issues)
        payload["status"] = "invalid"
        payload["eligibility"]["official_aggregate"] = False
        payload["instrumentation"].update(
            {
                "valid": False,
                "status": "invalid",
                "issues": hard_failures + review_flags,
                "hard_failures": hard_failures,
            }
        )

    path = output_dir / "run_bundle.json"
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return path, payload


def validate_run_bundle(run_dir, verify_checksums=True):
    """Validate a result bundle without rerunning the model or evaluator."""

    run_dir = Path(run_dir)
    issues = []
    bundle_path = run_dir / "run_bundle.json"
    if not bundle_path.is_file():
        return {
            "valid": False,
            "status": "invalid",
            "issues": [f"missing_run_bundle:{run_dir}"],
            "run_dir": str(run_dir),
        }

    bundle = _read_json(bundle_path, issues, "run_bundle")
    issues.extend(_schema_errors(bundle))
    if bundle.get("schema_version") != RUN_BUNDLE_SCHEMA_VERSION:
        issues.append(f"unsupported_run_bundle_schema:{bundle.get('schema_version')}")
    if not str(bundle.get("task_id", "")).startswith(
        ("asyncodebench:", "pr-hard:")
    ):
        issues.append("noncanonical_task_id")
    if bundle.get("protocol") not in PROTOCOLS:
        issues.append("noncanonical_protocol")

    artifacts = bundle.get("artifacts", {})
    for name in REQUIRED_ARTIFACTS:
        record = artifacts.get(name)
        path = run_dir / name
        if not path.is_file():
            issues.append(f"missing_artifact:{name}")
            continue
        if not isinstance(record, dict):
            issues.append(f"unindexed_artifact:{name}")
            continue
        if verify_checksums and record.get("sha256") != _sha256(path):
            issues.append(f"artifact_checksum_mismatch:{name}")

    indexed_names = set(artifacts)
    actual_names = {
        path.relative_to(run_dir).as_posix()
        for path in run_dir.rglob("*")
        if path.is_file() and path.name != "run_bundle.json"
    }
    for name in sorted(actual_names - indexed_names):
        issues.append(f"unindexed_artifact:{name}")
    for name in sorted(indexed_names - actual_names):
        issues.append(f"missing_indexed_artifact:{name}")
    if verify_checksums:
        for name in sorted(indexed_names & actual_names):
            record = artifacts.get(name, {})
            if record.get("sha256") != _sha256(run_dir / name):
                issues.append(f"artifact_checksum_mismatch:{name}")

    expected = {
        "release": bundle.get("release"),
        "task_id": bundle.get("task_id"),
        "source_task_id": bundle.get("source_task_id"),
        "protocol": bundle.get("protocol"),
        "scenario_id": bundle.get("scenario_id"),
        "source_scenario_id": bundle.get("source_scenario_id"),
        "agent_adapter": bundle.get("agent_adapter"),
    }
    cross_issues, metadata, report, profile = _cross_artifact_checks(
        run_dir, expected
    )
    issues.extend(cross_issues)
    release_issues, current_release_index = _release_contract_checks(
        run_dir, expected, metadata
    )
    issues.extend(release_issues)
    if bundle.get("release_index") != current_release_index:
        issues.append("recorded_release_index_mismatch")

    health = inspect_run(run_dir)
    profile_metadata = metadata.get("execution_profile", {})
    current_provenance = _provenance(metadata, profile)
    current_eligibility = _eligibility(
        health,
        profile_metadata,
        current_provenance,
        metadata.get("candidate_lane"),
    )
    current_hard_failures = _dedupe(
        list(cross_issues)
        + list(release_issues)
        + list(health.get("hard_failures", []))
    )
    current_review_flags = list(health.get("review_flags", []))
    current_status = _status(current_hard_failures, current_review_flags)
    if current_hard_failures or current_review_flags:
        current_eligibility["official_aggregate"] = False
    current_instrumentation = {
        "valid": current_status == "valid",
        "status": current_status,
        "issues": current_hard_failures + current_review_flags,
        "hard_failures": current_hard_failures,
        "review_flags": current_review_flags,
        "observations": list(health.get("observations", [])),
        "evaluator_source": health.get("evaluator_source"),
        "dependency_checkpoint_records": health.get("checkpoint_records", 0),
        "model_execution": health.get("model_execution", {}),
    }
    if bundle.get("status") != current_status:
        issues.append("recorded_health_status_mismatch")
    if bundle.get("eligibility") != current_eligibility:
        issues.append("recorded_eligibility_mismatch")
    if bundle.get("provenance") != current_provenance:
        issues.append("recorded_provenance_mismatch")
    if bundle.get("execution_profile") != profile_metadata:
        issues.append("recorded_execution_profile_mismatch")
    if bundle.get("final_test") != _final_test_payload(report):
        issues.append("recorded_final_test_mismatch")
    if bundle.get("instrumentation") != current_instrumentation:
        issues.append("recorded_instrumentation_mismatch")

    issues = _dedupe(issues)
    recorded_status = bundle.get("status")
    validation_status = "invalid" if issues else recorded_status
    return {
        "valid": validation_status == "valid",
        "status": validation_status,
        "issues": issues,
        "recorded_hard_failures": health.get("hard_failures", []),
        "review_flags": health.get("review_flags", []),
        "observations": health.get("observations", []),
        "eligibility": current_eligibility,
        "run_dir": str(run_dir),
        "task_id": bundle.get("task_id"),
        "protocol": bundle.get("protocol"),
        "final_test": bundle.get("final_test", {}),
    }
