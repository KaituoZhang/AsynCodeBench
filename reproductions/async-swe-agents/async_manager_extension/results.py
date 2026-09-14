"""Portable result contract for the additive online Async-Manager protocol."""

from __future__ import annotations

import json
from pathlib import Path

from asyncodebench_harness.health import inspect_run
from asyncodebench_harness.results import (
    REQUIRED_ARTIFACTS,
    _artifact_inventory,
    _cross_artifact_checks,
    _final_test_payload,
    _provenance,
    _release_contract_checks,
    _sha256,
)

from async_manager_extension import POLICY, PROTOCOL

REQUIRED_EXTENSION_ARTIFACTS = (
    "async_manager_profile_snapshot.json",
    "manager_interventions.jsonl",
)


def dump(path, value) -> None:
    Path(path).write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


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

    # Task content and specialist decomposition are exactly the released CAID
    # scenario.  The new protocol intentionally remains outside the old index.
    release_contract = dict(expected, protocol="caid_manager")
    release_issues, _ = _release_contract_checks(directory, release_contract, metadata)
    issues.extend(release_issues)
    health = inspect_run(directory)
    issues.extend(health["hard_failures"] + health["review_flags"])

    profile = json.loads(
        (directory / "async_manager_profile_snapshot.json").read_text(encoding="utf-8")
    )
    extension = metadata.get("async_manager_extension", {})
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
    if not metadata.get("harness_source_state", {}).get("clean", False):
        issues.append("harness_source_not_clean")

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
                or bundle.get("schema_version") != POLICY
            ):
                issues.append("bundle_identity_mismatch")
            for name, info in bundle.get("artifacts", {}).items():
                path = directory / name
                if not path.is_file() or _sha256(path) != info["sha256"]:
                    issues.append("artifact_checksum_mismatch:" + name)
    return sorted(set(issues))


def finalize(directory):
    directory = Path(directory)
    issues = validate(directory, verify_inventory=False)
    metadata = json.loads((directory / "run_metadata.json").read_text(encoding="utf-8"))
    profile = json.loads(
        (directory / "execution_profile_snapshot.json").read_text(encoding="utf-8")
    )
    report = (
        json.loads((directory / "report.json").read_text(encoding="utf-8"))
        if (directory / "report.json").exists()
        else {}
    )
    records = _load_interventions(directory, [])
    bundle = {
        "schema_version": POLICY,
        "benchmark": "AsynCodeBench",
        **{key: metadata[key] for key in ("task_id", "release", "protocol", "model")},
        "status": "invalid" if issues else "valid",
        "instrumentation": {"valid": not issues, "issues": issues},
        "eligibility": {
            "official_aggregate": False,
            "async_manager_comparison": not issues,
        },
        "online_manager": {
            "policy": POLICY,
            "events": len(records),
            "accepted": sum(bool(row.get("accepted")) for row in records),
            "scope_rejected": sum(
                row.get("status") == "scope_rejected" for row in records
            ),
        },
        "provenance": _provenance(metadata, profile),
        "final_test": _final_test_payload(report),
        "artifacts": _artifact_inventory(directory),
    }
    dump(directory / "run_bundle.json", bundle)
    if issues:
        raise RuntimeError(
            "Async-Manager result validation failed: " + "; ".join(issues)
        )
    return bundle
