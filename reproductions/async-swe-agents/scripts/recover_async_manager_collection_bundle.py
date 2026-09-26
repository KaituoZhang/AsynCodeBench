#!/usr/bin/env python3
"""Recover a completed run rejected by duplicate collection bookkeeping.

The source run remains immutable.  This tool accepts only the narrow failure
shape produced when a specialist response was recorded, artifact collection
timed out before its scope record was written, and the outer timeout handler
then emitted a second synthetic ``agent_response`` for the same logical
completion.  It preserves the original evidence, reclassifies that synthetic
record as a collection error, adds an explicitly failed scope-collection
record, and invokes the normal v2 finalizer.  Neither model nor evaluator is
rerun, and result-bearing artifacts are required to remain byte-identical.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

RUNNER_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNNER_ROOT))

from asyncodebench_harness.results import REQUIRED_ARTIFACTS  # noqa: E402
from protocols.async_manager import POLICY, PROTOCOL  # noqa: E402
from protocols.async_manager.results import finalize, validate  # noqa: E402

EXPECTED_ERROR = (
    "Budgeted Async-Manager result validation failed: "
    "specialist_result_collection_coverage_mismatch"
)
STATUS_EVIDENCE_FILES = (
    "partial_run_bundle.json",
    "async_manager_execution_error.json",
    "run_status.json",
)
RESULT_BEARING_FILES = (
    "report.json",
    "patch.diff",
    "process_metrics_summary.json",
    "strict_dependency_metrics.json",
)
REQUIRED_ASYNC_MANAGER_ARTIFACTS = (
    "async_manager_profile_snapshot.json",
    "delegation_validation.json",
    "manager_budget.json",
    "manager_shutdown.json",
    "manager_workspace_validation.jsonl",
    "outputs.jsonl",
    "scope_validation.jsonl",
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


def read_jsonl(path: Path) -> list[dict]:
    try:
        rows = [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Invalid JSONL artifact: {path.name}") from exc
    if not all(isinstance(row, dict) for row in rows):
        raise RuntimeError(f"Expected JSON objects in: {path.name}")
    return rows


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def logical_key(row: dict) -> tuple[object, object, object]:
    return (
        row.get("source"),
        row.get("content", {}).get("task_id"),
        row.get("round_num"),
    )


def scope_key(row: dict) -> tuple[object, object, object]:
    return (
        row.get("agent_id"),
        row.get("task_assignment_id"),
        row.get("round_num"),
    )


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


def verify_partial_inventory(source: Path, partial: dict) -> int:
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
    return len(inventory)


def verify_source(source: Path) -> dict:
    source = source.resolve()
    if (source / "run_bundle.json").exists():
        raise RuntimeError("Source already contains run_bundle.json")

    partial = read_json(source / "partial_run_bundle.json")
    error = read_json(source / "async_manager_execution_error.json")
    status = read_json(source / "run_status.json")
    metadata = read_json(source / "run_metadata.json")
    if error.get("detail") != EXPECTED_ERROR:
        raise RuntimeError("Partial was not caused by the known collection bug")
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
        for name in (*REQUIRED_ARTIFACTS, *REQUIRED_ASYNC_MANAGER_ARTIFACTS)
        if not (source / name).is_file()
    ]
    final_archives = sorted((source / "final_repo").glob("*.tar.gz"))
    if missing or len(final_archives) != 1:
        detail = missing + ([] if len(final_archives) == 1 else ["final_repo/*.tar.gz"])
        raise RuntimeError(
            "Missing or ambiguous completed-run artifacts: " + ", ".join(detail)
        )

    verified_artifact_count = verify_partial_inventory(source, partial)
    report = read_json(source / "report.json")
    process = read_json(source / "process_metrics_summary.json")
    shutdown = read_json(source / "manager_shutdown.json")
    workspace_rows = read_jsonl(source / "manager_workspace_validation.jsonl")
    if (
        not isinstance(report.get("summary"), dict)
        or "collected" not in report["summary"]
    ):
        raise RuntimeError("Final evaluator report is incomplete")
    if not isinstance(process.get("primary_outcome"), dict):
        raise RuntimeError("Final process outcome is missing")
    if not shutdown.get("confirmed"):
        raise RuntimeError("Manager shutdown is not confirmed")
    if not workspace_rows or not workspace_rows[-1].get("passed"):
        raise RuntimeError("Final manager workspace validation did not pass")
    if workspace_rows[-1].get("main_workspace_status"):
        raise RuntimeError("Final manager workspace was not clean")

    output_rows = read_jsonl(source / "outputs.jsonl")
    scope_rows = read_jsonl(source / "scope_validation.jsonl")
    response_rows = [
        row
        for row in output_rows
        if row.get("event_type") == "agent_response"
        and row.get("target") == "manager"
    ]
    completed = Counter(logical_key(row) for row in response_rows)
    collected = Counter(scope_key(row) for row in scope_rows)
    differing = set(completed) | set(collected)
    differing = {key for key in differing if completed[key] != collected[key]}
    if len(differing) != 1:
        raise RuntimeError(
            f"Expected one collection mismatch, found {sorted(differing)!r}"
        )
    key = next(iter(differing))
    if completed[key] != 2 or collected[key] != 0:
        raise RuntimeError(
            "Collection mismatch is not the supported duplicate-plus-missing shape: "
            f"completed={completed[key]}, collected={collected[key]}"
        )
    duplicates = [row for row in response_rows if logical_key(row) == key]
    rich = [
        row
        for row in duplicates
        if isinstance(row.get("content", {}).get("actual_iterations"), int)
        and row.get("content", {}).get("total_tokens") is not None
    ]
    synthetic = [
        row
        for row in duplicates
        if row.get("content", {}).get("error") == "timed out"
        and row.get("content", {}).get("actual_iterations") is None
        and row.get("content", {}).get("submission_exists") is False
    ]
    if len(rich) != 1 or len(synthetic) != 1:
        raise RuntimeError(
            "Duplicate responses do not match the supported timeout signature"
        )
    if synthetic[0].get("event_id", -1) <= rich[0].get("event_id", -1):
        raise RuntimeError(
            "Synthetic timeout does not follow the real specialist response"
        )

    matching_templates = [
        row
        for row in scope_rows
        if row.get("agent_id") == key[0]
        and row.get("task_assignment_id") == key[1]
    ]
    if matching_templates:
        scope_template = matching_templates[-1]
        template_source = "earlier_specialist_scope_record"
    else:
        # A first-round collection timeout has no earlier scope record for
        # this specialist.  Anchor its identity and writable paths to the
        # immutable scenario and delegation snapshots, rather than borrowing
        # another specialist's authority or guessing from the response.
        scenario = read_json(source / "scenario_snapshot.json")
        delegations = read_json(source / "delegations.json")
        assignments = [
            assignment
            for assignment in scenario.get("assignments", [])
            if assignment.get("subproblem_id") == key[1]
        ]
        delegated = [
            task
            for task in delegations.get("delegation_plan", {})
            .get("first_round", {})
            .get("tasks", [])
            if task.get("engineer_id") == key[0]
            and task.get("task_id") == key[1]
        ]
        if (
            len(assignments) != 1
            or len(delegated) != 1
            or key[2] != 1
            or not scope_rows
        ):
            raise RuntimeError("No verified first-round assignment can anchor recovery")
        allowed_paths = assignments[0].get("writable_paths")
        delegated_paths = [
            path.strip()
            for path in delegated[0].get("file_path", "").split(",")
            if path.strip()
        ]
        if (
            not isinstance(allowed_paths, list)
            or not allowed_paths
            or len(set(allowed_paths)) != len(allowed_paths)
            or set(delegated_paths) != set(allowed_paths)
            or any(
                row.get("scenario_id") != scenario.get("scenario_id")
                for row in scope_rows
            )
        ):
            raise RuntimeError("Delegation and scenario scope do not agree")
        scope_template = dict(scope_rows[0])
        scope_template.update(
            agent_id=key[0],
            task_assignment_id=key[1],
            manifest_subproblem_id=key[1],
            writable_paths=allowed_paths,
        )
        template_source = "verified_scenario_and_first_round_delegation"

    protected = [
        *RESULT_BEARING_FILES,
        final_archives[0].relative_to(source).as_posix(),
    ]
    return {
        "metadata": metadata,
        "output_rows": output_rows,
        "scope_rows": scope_rows,
        "logical_key": key,
        "rich_event_id": rich[0]["event_id"],
        "synthetic_event_id": synthetic[0]["event_id"],
        "scope_template": scope_template,
        "scope_template_source": template_source,
        "accepted_head": workspace_rows[-1].get("accepted_head"),
        "verified_artifact_count": verified_artifact_count,
        "source_hashes": {
            relative: sha256_file(source / relative) for relative in protected
        },
        "status_hashes": {
            name: sha256_file(source / name) for name in STATUS_EVIDENCE_FILES
        },
        "outputs_sha256": sha256_file(source / "outputs.jsonl"),
        "scope_sha256": sha256_file(source / "scope_validation.jsonl"),
    }


def recover(source: Path, destination: Path) -> Path:
    source = source.resolve()
    destination = destination.resolve()
    if destination.exists():
        raise FileExistsError(f"Recovery destination already exists: {destination}")
    proof = verify_source(source)

    shutil.copytree(source, destination, copy_function=shutil.copy2)
    evidence = destination / "collection_recovery"
    evidence.mkdir()
    shutil.copy2(destination / "outputs.jsonl", evidence / "original_outputs.jsonl")
    shutil.copy2(
        destination / "scope_validation.jsonl",
        evidence / "original_scope_validation.jsonl",
    )
    for name in STATUS_EVIDENCE_FILES:
        (destination / name).replace(evidence / name)

    output_rows = proof["output_rows"]
    for row in output_rows:
        if row.get("event_id") == proof["synthetic_event_id"]:
            row["event_type"] = "specialist_result_collection_error"
            row["recovery_classification"] = (
                "synthetic_timeout_after_recorded_specialist_response"
            )
            row["original_event_type"] = "agent_response"
            break
    write_jsonl(destination / "outputs.jsonl", output_rows)

    scope_record = dict(proof["scope_template"])
    scope_record.update(
        {
            "artifact_commit": None,
            "changed_paths": [],
            "head_before": proof["accepted_head"],
            "main_workspace_status_before_merge": [],
            "passed": False,
            "reasons": [
                "artifact collection timed out after specialist response; "
                "record reconstructed from immutable execution evidence"
            ],
            "round_num": proof["logical_key"][2],
            "uncommitted_archive": None,
            "violations": ["artifact_collection_timeout"],
            "recovered_from_execution_evidence": True,
            "source_response_event_id": proof["rich_event_id"],
            "source_timeout_event_id": proof["synthetic_event_id"],
        }
    )
    scope_rows = [*proof["scope_rows"], scope_record]
    write_jsonl(destination / "scope_validation.jsonl", scope_rows)

    record = {
        "schema_version": "async-manager-collection-recovery-v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "reason": "duplicate_timeout_response_and_missing_scope_collection_record",
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
        "logical_completion": {
            "agent_id": proof["logical_key"][0],
            "task_assignment_id": proof["logical_key"][1],
            "round_num": proof["logical_key"][2],
            "retained_response_event_id": proof["rich_event_id"],
            "reclassified_timeout_event_id": proof["synthetic_event_id"],
        },
        "scope_template_source": proof["scope_template_source"],
        "source_outputs_sha256": proof["outputs_sha256"],
        "source_scope_validation_sha256": proof["scope_sha256"],
        "source_status_artifact_sha256": proof["status_hashes"],
        "protected_result_artifact_sha256": proof["source_hashes"],
        "model_rerun": False,
        "evaluator_rerun": False,
        "score_changed": False,
    }
    (destination / "collection_recovery.json").write_text(
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
    for relative, expected in proof["source_hashes"].items():
        if sha256_file(destination / relative) != expected:
            raise RuntimeError(f"Protected result artifact changed: {relative}")
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
