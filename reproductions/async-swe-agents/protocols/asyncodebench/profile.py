"""Official execution-profile loading and comparison helpers."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

LEGACY_PROFILE_RELATIVE_PATH = Path(
    "configs/evaluation/official_execution_profile.v2.json"
)
ASYNC_MANAGER_PROFILE_RELATIVE_PATH = Path(
    "configs/evaluation/official_execution_profile.v4.json"
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def profile_relative_path(protocol: str | None = None) -> Path:
    if protocol == "async_manager":
        return ASYNC_MANAGER_PROFILE_RELATIVE_PATH
    return LEGACY_PROFILE_RELATIVE_PATH


def profile_path(protocol: str | None = None) -> Path:
    return _repo_root() / profile_relative_path(protocol)


def load_official_execution_profile(protocol: str | None = None) -> dict:
    path = profile_path(protocol)
    try:
        profile = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"Missing official execution profile: {path}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid official execution profile {path}: {exc}") from exc
    if profile.get("benchmark") != "AsynCodeBench":
        raise RuntimeError(f"Unexpected benchmark in execution profile: {path}")
    return profile


def profile_sha256(protocol: str | None = None) -> str:
    return hashlib.sha256(profile_path(protocol).read_bytes()).hexdigest()


def _timeout_value(name: str, default: int, minimum: int) -> int:
    raw_value = os.getenv(name, str(default))
    try:
        value = int(raw_value)
    except ValueError:
        value = default
    return max(value, minimum)


def observed_execution_settings(workflow_config, scenario: dict) -> dict:
    return {
        "manager_max_iterations": int(workflow_config.manager_max_iterations),
        "max_subagents": int(workflow_config.max_subagents),
        "subagent_max_iterations": int(workflow_config.subagent_max_iterations),
        "max_rounds_chat": int(workflow_config.max_rounds_chat),
        "final_pytest_timeout_seconds": _timeout_value(
            "ASYNCODEBENCH_FINAL_PYTEST_TIMEOUT_SECONDS", 900, 60
        ),
        "probe_timeout_seconds": _timeout_value(
            "ASYNCODEBENCH_PROBE_TIMEOUT_SECONDS", 60, 30
        ),
        "final_evaluator_source": "asyncodebench_manifest",
        "scenario_declared_agents": int(scenario.get("agent_count", 1)),
    }


def execution_profile_metadata(task, workflow_config, protocol: str) -> dict:
    profile = load_official_execution_profile(protocol)
    scenario = task.scenario_for(protocol)
    observed = observed_execution_settings(workflow_config, scenario)
    expected = dict(profile["protocols"][protocol])
    expected.update(profile.get("instrumentation", {}))

    deviations = []
    for field, expected_value in expected.items():
        resolved_expected = (
            observed["scenario_declared_agents"]
            if expected_value == "scenario_declared"
            else expected_value
        )
        observed_value = observed.get(field)
        if observed_value != resolved_expected:
            deviations.append(
                {
                    "field": field,
                    "expected": resolved_expected,
                    "observed": observed_value,
                }
            )

    return {
        "profile_id": profile["profile_id"],
        "schema_version": profile["schema_version"],
        "path": profile_relative_path(protocol).as_posix(),
        "sha256": profile_sha256(protocol),
        "matched": not deviations,
        "deviations": deviations,
        "observed": observed,
    }
