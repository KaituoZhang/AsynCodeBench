"""Portable result contract for the additive online Async-Manager protocol."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from asyncodebench_harness.health import inspect_run
from asyncodebench_harness.results import (
    REQUIRED_ARTIFACTS,
    _cross_artifact_checks,
    _release_contract_checks,
    _sha256,
    build_run_bundle,
    validate_run_bundle,
)

from protocols.async_manager import POLICY, PROTOCOL

REQUIRED_EXTENSION_ARTIFACTS = (
    "async_manager_profile_snapshot.json",
    "manager_interventions.jsonl",
)


def dump(path, value) -> None:
    Path(path).write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _json_sha256(value) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _load_json(path: Path, issues: list[str], label: str) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        issues.append(f"invalid_{label}")
        return {}
    if not isinstance(value, dict):
        issues.append(f"invalid_{label}:not_object")
        return {}
    return value


def _load_interventions(directory: Path, issues: list[str]) -> list[dict]:
    path = directory / "manager_interventions.jsonl"
    records = []
    if not path.is_file():
        return records
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            issues.append("invalid_manager_interventions_jsonl")
            return []
        if not isinstance(record, dict):
            issues.append("invalid_manager_intervention:not_object")
            return []
        records.append(record)
    if not records:
        issues.append("empty_manager_interventions")
    return records


def validate(directory, verify_inventory=True):
    directory = Path(directory)
    issues: list[str] = []
    required = (*REQUIRED_ARTIFACTS, *REQUIRED_EXTENSION_ARTIFACTS)
    issues.extend(
        "missing_artifact:" + name
        for name in required
        if not (directory / name).is_file()
    )
    if issues:
        return sorted(set(issues))

    metadata = json.loads((directory / "run_metadata.json").read_text(encoding="utf-8"))
    expected = {
        key: metadata.get(key)
        for key in (
            "release",
            "task_id",
            "source_task_id",
            "protocol",
            "scenario_id",
            "source_scenario_id",
            "agent_adapter",
        )
    }
    if expected["protocol"] != PROTOCOL:
        issues.append("wrong_async_manager_protocol")
    cross, _, _, _ = _cross_artifact_checks(directory, expected)
    issues.extend(cross)

    release_issues, _ = _release_contract_checks(directory, expected, metadata)
    issues.extend(release_issues)
    health = inspect_run(directory)
    issues.extend(health["hard_failures"] + health["review_flags"])

    profile = json.loads(
        (directory / "async_manager_profile_snapshot.json").read_text(encoding="utf-8")
    )
    extension = metadata.get("async_manager_protocol", {})
    if profile.get("protocol") != PROTOCOL or profile.get("policy") != POLICY:
        issues.append("invalid_async_manager_profile")
    if extension.get("policy") != POLICY:
        issues.append("async_manager_policy_missing")
    if extension.get("profile_sha256") != _sha256(
        directory / "async_manager_profile_snapshot.json"
    ):
        issues.append("async_manager_profile_checksum_mismatch")
    if not metadata.get("execution_profile", {}).get("matched"):
        issues.append("base_execution_profile_mismatch")
    harness_state = metadata.get("harness_source_state", {})
    if not isinstance(harness_state, dict) or not harness_state.get("clean", False):
        issues.append("harness_source_not_clean")
    else:
        revision = metadata.get("code_revisions", {}).get("asyncodebench")
        if harness_state.get("revision") != revision:
            issues.append("harness_source_revision_mismatch")
        if harness_state.get("verification") not in {
            "runtime_preflight_v1",
            "deterministic_posthoc_recovery_v1",
        }:
            issues.append("harness_source_verification_invalid")
        source_hashes = extension.get("sources", {})
        if harness_state.get("source_hashes_sha256") != _json_sha256(source_hashes):
            issues.append("harness_source_hashes_mismatch")
        checked_paths = harness_state.get("checked_paths")
        if not isinstance(checked_paths, list) or sorted(checked_paths) != sorted(
            source_hashes
        ):
            issues.append("harness_source_checked_paths_mismatch")
        if harness_state.get("verification") == "deterministic_posthoc_recovery_v1":
            recovery_path = directory / "provenance_recovery.json"
            if not recovery_path.is_file():
                issues.append("provenance_recovery_record_missing")
            else:
                recovery = _load_json(recovery_path, issues, "provenance_recovery")
                original_metadata = (
                    directory
                    / "provenance_recovery"
                    / "original_run_metadata.json"
                )
                if harness_state.get("recovery_record_sha256") != _sha256(
                    recovery_path
                ):
                    issues.append("provenance_recovery_checksum_mismatch")
                if not original_metadata.is_file():
                    issues.append("provenance_recovery_original_metadata_missing")
                elif recovery.get("source_run_metadata_sha256") != _sha256(
                    original_metadata
                ):
                    issues.append("provenance_recovery_original_metadata_mismatch")
                if recovery.get("recorded_revision") != harness_state.get("revision"):
                    issues.append("provenance_recovery_revision_mismatch")
                if recovery.get("source_hashes_sha256") != harness_state.get(
                    "source_hashes_sha256"
                ):
                    issues.append("provenance_recovery_source_hashes_mismatch")

    checkpoints = [
        json.loads(line)
        for line in (directory / "dependency_probe_checkpoints.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    checkpoint_ids = {row.get("checkpoint_id") for row in checkpoints}
    records = _load_interventions(directory, issues)
    expected_sequences = list(range(1, len(records) + 1))
    if [row.get("sequence") for row in records] != expected_sequences:
        issues.append("manager_intervention_sequence_invalid")
    accepted = 0
    for record in records:
        if record.get("policy") != POLICY:
            issues.append("manager_intervention_policy_mismatch")
        if record.get("status") not in {
            "accepted",
            "no_change",
            "scope_rejected",
            "execution_error",
        }:
            issues.append("manager_intervention_status_invalid")
        if record.get("status") == "execution_error":
            issues.append("manager_intervention_execution_error")
        patch = directory / str(record.get("patch", ""))
        if not patch.is_file():
            issues.append("manager_intervention_patch_missing")
        elif record.get("patch_sha256") != _sha256(patch):
            issues.append("manager_intervention_patch_checksum_mismatch")
        specialist_checkpoint = record.get("specialist_checkpoint_id")
        if specialist_checkpoint not in checkpoint_ids:
            issues.append("manager_intervention_trigger_checkpoint_missing")
        if record.get("accepted"):
            accepted += 1
            manager_checkpoint = record.get("manager_checkpoint_id")
            if manager_checkpoint not in checkpoint_ids:
                issues.append("accepted_manager_checkpoint_missing")
        elif record.get("manager_checkpoint_id") is not None:
            issues.append("nonaccepted_manager_checkpoint_present")

    cost = json.loads((directory / "cost.json").read_text(encoding="utf-8"))
    operation = (
        cost.get("manager", {}).get("operations", {}).get("online_intervention", {})
    )
    if operation.get("policy") != POLICY:
        issues.append("online_intervention_cost_missing")
    if operation.get("events") != len(records):
        issues.append("online_intervention_cost_event_count_mismatch")
    if operation.get("accepted") != accepted:
        issues.append("online_intervention_cost_accept_count_mismatch")

    if verify_inventory:
        bundle_path = directory / "run_bundle.json"
        if not bundle_path.is_file():
            issues.append("bundle_missing")
        else:
            bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
            if (
                bundle.get("protocol") != PROTOCOL
                or bundle.get("schema_version") != "0.2"
            ):
                issues.append("bundle_identity_mismatch")
            expected_online_manager = {
                "policy": POLICY,
                "events": len(records),
                "accepted": accepted,
                "scope_rejected": sum(
                    row.get("status") == "scope_rejected" for row in records
                ),
            }
            if bundle.get("online_manager") != expected_online_manager:
                issues.append("online_manager_summary_mismatch")
            for name, info in bundle.get("artifacts", {}).items():
                path = directory / name
                if not path.is_file() or _sha256(path) != info["sha256"]:
                    issues.append("artifact_checksum_mismatch:" + name)
    return sorted(set(issues))


def finalize(directory, *, task, agent_adapter):
    directory = Path(directory)
    issues = validate(directory, verify_inventory=False)
    records = _load_interventions(directory, [])
    if issues:
        raise RuntimeError(
            "Async-Manager result validation failed: " + "; ".join(issues)
        )
    _, bundle = build_run_bundle(
        task,
        directory,
        PROTOCOL,
        agent_adapter,
        protocol_details={
            "policy": POLICY,
            "events": len(records),
            "accepted": sum(bool(row.get("accepted")) for row in records),
            "scope_rejected": sum(
                row.get("status") == "scope_rejected" for row in records
            ),
        },
    )
    validation = validate_run_bundle(directory)
    if not validation["valid"]:
        raise RuntimeError(
            "Async-Manager standard bundle validation failed: "
            + "; ".join(validation["issues"])
        )
    return bundle
