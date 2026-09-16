#!/usr/bin/env python3
"""Recover v2 bundles rejected by the legacy budget-status validator.

The source run is immutable. Recovery verifies the complete partial artifact
inventory and proves that model execution, final evaluation, manager shutdown,
and task-level budget accounting all completed. It then copies the run to a new
directory, preserves the original partial-status records as recovery evidence,
and invokes the fixed v2 finalizer. Neither model nor evaluator is rerun.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

RUNNER_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNNER_ROOT))

from asyncodebench_harness.results import REQUIRED_ARTIFACTS  # noqa: E402
from protocols.async_manager import POLICY, PROTOCOL  # noqa: E402
from protocols.async_manager.results import (  # noqa: E402
    _budget_issues,
    finalize,
    validate,
)

EXPECTED_ERROR = (
    "Async-Manager result validation failed: "
    "manager_intervention_status_invalid"
)
RECOVERY_EVIDENCE_FILES = (
    "partial_run_bundle.json",
    "async_manager_execution_error.json",
    "run_status.json",
)
REQUIRED_V2_ARTIFACTS = (
    "async_manager_profile_snapshot.json",
    "manager_interventions.jsonl",
    "manager_budget.json",
    "manager_shutdown.json",
    "strict_dependency_metrics.json",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Invalid JSON artifact: {path.name}") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"Expected JSON object: {path.name}")
    return value


def git_revision() -> str:
    return subprocess.check_output(
        ["git", "-C", str(RUNNER_ROOT), "rev-parse", "HEAD"], text=True
    ).strip()


class RecordedTask:
    def __init__(self, metadata: dict):
        self.asyncodebench_config = SimpleNamespace(release=metadata["release"])
        self.task_id = metadata["task_id"]
        self.source_task_id = metadata["source_task_id"]
        self._scenario_id = metadata["scenario_id"]
        self._source_scenario_id = metadata["source_scenario_id"]

    def public_scenario_id(self, _protocol: str) -> str:
        return self._scenario_id

    def scenario_for(self, _protocol: str) -> dict:
        return {"scenario_id": self._source_scenario_id}


class RecordedAdapter:
    def __init__(self, metadata: dict):
        self._metadata = metadata["agent_adapter"]

    def public_metadata(self) -> dict:
        return self._metadata


def verify_source(source: Path) -> dict:
    source = source.resolve()
    if (source / "run_bundle.json").exists():
        raise RuntimeError("Source already contains run_bundle.json")

    partial_path = source / "partial_run_bundle.json"
    error_path = source / "async_manager_execution_error.json"
    status_path = source / "run_status.json"
    partial = read_json(partial_path)
    error = read_json(error_path)
    status = read_json(status_path)
    metadata = read_json(source / "run_metadata.json")

    if error.get("detail") != EXPECTED_ERROR:
        raise RuntimeError("Partial was not caused by the known finalizer bug")
    if error.get("classification") != "execution_error":
        raise RuntimeError("Unexpected partial error classification")
    if status.get("status") != "execution_error":
        raise RuntimeError("Unexpected partial run status")
    if partial.get("status") != "execution_error":
        raise RuntimeError("Unexpected partial bundle status")
    if partial.get("policy") != POLICY:
        raise RuntimeError("Partial bundle policy mismatch")
    if metadata.get("protocol") != PROTOCOL:
        raise RuntimeError("Run protocol mismatch")
    if metadata.get("async_manager_protocol", {}).get("policy") != POLICY:
        raise RuntimeError("Run policy mismatch")

    missing = [
        name
        for name in (*REQUIRED_ARTIFACTS, *REQUIRED_V2_ARTIFACTS)
        if not (source / name).is_file()
    ]
    if missing:
        raise RuntimeError("Missing completed-run artifacts: " + ", ".join(missing))

    inventory = partial.get("artifacts")
    if not isinstance(inventory, dict) or not inventory:
        raise RuntimeError("Partial artifact inventory is empty or invalid")
    actual = {
        path.relative_to(source).as_posix()
        for path in source.rglob("*")
        if path.is_file() and path.name != "partial_run_bundle.json"
    }
    recorded = set(inventory)
    if actual != recorded:
        raise RuntimeError(
            "Partial artifact inventory membership mismatch: "
            f"missing={sorted(recorded - actual)!r}, "
            f"unexpected={sorted(actual - recorded)!r}"
        )
    for relative, information in sorted(inventory.items()):
        path = source / relative
        if path.stat().st_size != information.get("size"):
            raise RuntimeError(f"Partial artifact size mismatch: {relative}")
        if sha256_file(path) != information.get("sha256"):
            raise RuntimeError(f"Partial artifact checksum mismatch: {relative}")

    budget = read_json(source / "manager_budget.json")
    shutdown = read_json(source / "manager_shutdown.json")
    process = read_json(source / "process_metrics_summary.json")
    budget_issues = _budget_issues(source)
    if budget_issues:
        raise RuntimeError("Invalid manager budget: " + "; ".join(budget_issues))
    if not budget.get("exhausted") or "manager_iterations_total" not in (
        budget.get("exhaustion_reasons") or []
    ):
        raise RuntimeError("Run did not reach the expected manager iteration cap")
    if not shutdown.get("confirmed"):
        raise RuntimeError("Manager shutdown is not confirmed")
    if not isinstance(process.get("primary_outcome"), dict):
        raise RuntimeError("Final evaluator outcome is missing")

    return {
        "metadata": metadata,
        "verified_artifact_count": len(inventory),
        "partial_bundle_sha256": sha256_file(partial_path),
        "execution_error_sha256": sha256_file(error_path),
        "original_run_status_sha256": sha256_file(status_path),
    }


def recover(source: Path, destination: Path) -> Path:
    source = source.resolve()
    destination = destination.resolve()
    if destination.exists():
        raise FileExistsError(f"Recovery destination already exists: {destination}")
    proof = verify_source(source)

    shutil.copytree(source, destination, copy_function=shutil.copy2)
    evidence_directory = destination / "finalizer_recovery"
    evidence_directory.mkdir()
    for name in RECOVERY_EVIDENCE_FILES:
        (destination / name).replace(evidence_directory / name)

    record = {
        "schema_version": "async-manager-finalizer-recovery-v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "reason": "v2_budget_status_rejected_by_legacy_finalizer",
        "source_run_dir": str(source),
        "source_run_revision": proof["metadata"]
        .get("code_revisions", {})
        .get("async_swe_agents"),
        "recovery_code_revision": git_revision(),
        "recovery_finalizer_sha256": sha256_file(
            RUNNER_ROOT / "protocols/async_manager/results.py"
        ),
        "recovery_tool_sha256": sha256_file(Path(__file__)),
        "verified_artifact_count": proof["verified_artifact_count"],
        "source_partial_bundle_sha256": proof["partial_bundle_sha256"],
        "source_execution_error_sha256": proof["execution_error_sha256"],
        "source_run_status_sha256": proof["original_run_status_sha256"],
        "model_rerun": False,
        "evaluator_rerun": False,
    }
    (destination / "finalizer_recovery.json").write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    metadata = proof["metadata"]
    finalize(
        destination,
        task=RecordedTask(metadata),
        agent_adapter=RecordedAdapter(metadata),
    )
    issues = validate(destination)
    if issues:
        raise RuntimeError("Recovered bundle is invalid: " + "; ".join(issues))
    return destination / "run_bundle.json"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    arguments = parser.parse_args()
    bundle = recover(arguments.source, arguments.destination)
    print(json.dumps({"valid": True, "run_bundle": str(bundle)}, indent=2))


if __name__ == "__main__":
    main()
