"""Result validation for the canonical budgeted Async-Manager policy."""

from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path

import protocols.async_manager.legacy_results as v1_results
from protocols.async_manager import POLICY


@contextmanager
def _v2_policy():
    previous = v1_results.POLICY
    v1_results.POLICY = POLICY
    try:
        yield
    finally:
        v1_results.POLICY = previous


def _budget_issues(directory: Path) -> list[str]:
    issues = []
    budget_path = directory / "manager_budget.json"
    shutdown_path = directory / "manager_shutdown.json"
    if not budget_path.is_file():
        issues.append("missing_artifact:manager_budget.json")
        return issues
    if not shutdown_path.is_file():
        issues.append("missing_artifact:manager_shutdown.json")
    else:
        try:
            shutdown = json.loads(shutdown_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            issues.append("invalid_manager_shutdown")
        else:
            if not shutdown.get("confirmed"):
                issues.append("manager_shutdown_unconfirmed")
    try:
        budget = json.loads(budget_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        issues.append("invalid_manager_budget")
        return issues
    limits = budget.get("limits", {})
    usage = budget.get("usage", {})
    try:
        profile = json.loads(
            (directory / "async_manager_profile_snapshot.json").read_text(
                encoding="utf-8"
            )
        )
    except (json.JSONDecodeError, OSError):
        issues.append("invalid_or_missing_async_manager_profile_snapshot")
        profile = {}
    time_tolerance = float(
        profile.get("active_time_overrun_tolerance_seconds", 0)
    )
    if budget.get("policy") != POLICY:
        issues.append("manager_budget_policy_mismatch")
    for field in (
        "manager_iterations_total",
        "manager_active_seconds_total",
        "manager_interventions",
    ):
        limit = limits.get(field)
        used = usage.get(field)
        if not isinstance(limit, (int, float)) or not isinstance(used, (int, float)):
            issues.append("invalid_manager_budget_field:" + field)
        elif used > limit + (
            time_tolerance if field == "manager_active_seconds_total" else 0
        ):
            issues.append("manager_budget_limit_exceeded:" + field)
    token_limit = limits.get("manager_tokens_total")
    token_usage = usage.get("manager_tokens_total")
    if not isinstance(token_limit, int) or not isinstance(token_usage, int):
        issues.append("invalid_manager_budget_field:manager_tokens_total")
    return issues


def validate(directory, verify_inventory=True):
    directory = Path(directory)
    with _v2_policy():
        issues = v1_results.validate(directory, verify_inventory=verify_inventory)
    # v1 only knows its four statuses and reports a non-specific issue for the
    # v2 budget terminal status. Recompute this check from every record below
    # so one valid budget record cannot hide an unrelated invalid status.
    issues = [
        issue for issue in issues if issue != "manager_intervention_status_invalid"
    ]
    issues.extend(_budget_issues(directory))
    records = v1_results._load_interventions(directory, [])
    allowed_statuses = {
        "accepted",
        "no_change",
        "scope_rejected",
        "execution_error",
        "budget_exhausted",
        "validation_rejected",
    }
    try:
        profile = json.loads(
            (directory / "async_manager_profile_snapshot.json").read_text(
                encoding="utf-8"
            )
        )
    except (json.JSONDecodeError, OSError):
        profile = {}
    validation_required = bool(
        profile.get("candidate_patch_validation", {}).get("enabled")
    )
    for record in records:
        if record.get("status") not in allowed_statuses:
            issues.append("manager_intervention_status_invalid")
        if record.get("status") == "budget_exhausted" and (
            record.get("accepted") or record.get("changed_paths")
        ):
            issues.append("invalid_budget_exhausted_intervention")
        validation = record.get("candidate_validation")
        if (
            validation_required
            and record.get("accepted")
            and (
                not isinstance(validation, dict) or not validation.get("passed")
                or not validation.get("required")
                or validation.get("mode")
                != profile["candidate_patch_validation"].get("mode")
            )
        ):
            issues.append("accepted_candidate_validation_missing_or_failed")
        if record.get("status") == "validation_rejected" and (
            record.get("accepted")
            or not isinstance(validation, dict)
            or validation.get("passed") is not False
        ):
            issues.append("invalid_validation_rejected_intervention")
        if isinstance(validation, dict) and validation.get("required"):
            artifact = directory / str(validation.get("artifact", ""))
            if not artifact.is_file():
                issues.append("candidate_validation_artifact_missing")
            elif validation.get("artifact_sha256") != v1_results._sha256(artifact):
                issues.append("candidate_validation_artifact_checksum_mismatch")
    return sorted(set(issues))


def finalize(directory, *, task, agent_adapter):
    directory = Path(directory)
    (directory / "run_status.json").write_text(
        json.dumps(
            {
                "schema_version": "async-manager-run-status-v1",
                "policy": POLICY,
                "status": "completed",
                "evaluation_complete": True,
                "metrics_eligible": True,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    issues = validate(directory, verify_inventory=False)
    if issues:
        raise RuntimeError(
            "Budgeted Async-Manager result validation failed: " + "; ".join(issues)
        )
    with _v2_policy():
        return v1_results.finalize(
            directory,
            task=task,
            agent_adapter=agent_adapter,
        )


__all__ = ["finalize", "validate", "_budget_issues"]
