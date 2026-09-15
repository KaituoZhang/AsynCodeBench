"""Result validation extensions for the budgeted Async-Manager policy."""

from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path

import protocols.async_manager.results as v1_results
from protocols.async_manager_v2 import POLICY


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
    }
    for record in records:
        if record.get("status") not in allowed_statuses:
            issues.append("manager_intervention_status_invalid")
        if record.get("status") == "budget_exhausted":
            if record.get("accepted") or record.get("changed_paths"):
                issues.append("invalid_budget_exhausted_intervention")
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


__all__ = ["finalize", "validate"]
