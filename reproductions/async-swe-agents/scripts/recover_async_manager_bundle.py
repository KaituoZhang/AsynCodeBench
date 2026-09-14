#!/usr/bin/env python3
"""Recover a bundle rejected by the missing source-state metadata bug.

The source run is never modified.  Recovery first proves that every recorded
Async-Manager source snapshot matches both its recorded SHA-256 and the Git
blob at the run's recorded revision.  It then copies the run to a new,
previously nonexistent directory, records that proof, and performs the normal
bundle finalization without rerunning either the model or the evaluator.
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
REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RUNNER_ROOT))

from protocols.async_manager import PROTOCOL  # noqa: E402
from protocols.async_manager.results import finalize, validate  # noqa: E402


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def json_sha256(value) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    return sha256_bytes(encoded)


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


def verify_recorded_sources(source: Path, metadata: dict, repo_root: Path) -> dict:
    if metadata.get("protocol") != PROTOCOL:
        raise RuntimeError(f"Expected protocol={PROTOCOL!r}")
    if "harness_source_state" in metadata:
        raise RuntimeError(
            "Run already contains harness_source_state; use normal validation"
        )

    revisions = metadata.get("code_revisions", {})
    revision = revisions.get("asyncodebench")
    if not revision or revision != revisions.get("async_swe_agents"):
        raise RuntimeError(
            "Recorded benchmark and runner revisions are missing or unequal"
        )

    source_hashes = metadata.get("async_manager_protocol", {}).get("sources", {})
    if not source_hashes:
        raise RuntimeError("Async-Manager source hash inventory is missing")

    runner_snapshot = source / "protocol_sources" / (
        "reproductions/async-swe-agents/run_async_manager.py"
    )
    runner_text = runner_snapshot.read_text(encoding="utf-8")
    clean_check = runner_text.find("assert_protocol_sources_clean(repo_root)")
    metadata_write = runner_text.find("write_run_metadata(output, metadata)")
    if clean_check < 0 or metadata_write < 0 or clean_check > metadata_write:
        raise RuntimeError(
            "Recorded runner does not prove preflight-before-metadata ordering"
        )

    verified = []
    for relative, expected_hash in sorted(source_hashes.items()):
        snapshot = source / "protocol_sources" / relative
        if not snapshot.is_file() or sha256_file(snapshot) != expected_hash:
            raise RuntimeError(f"Source snapshot checksum mismatch: {relative}")
        try:
            committed = subprocess.check_output(
                ["git", "-C", str(repo_root), "show", f"{revision}:{relative}"]
            )
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(
                f"Cannot resolve recorded source at {revision}:{relative}"
            ) from exc
        if sha256_bytes(committed) != expected_hash:
            raise RuntimeError(
                f"Recorded source does not match Git revision: {relative}"
            )
        verified.append(relative)

    return {
        "revision": revision,
        "checked_paths": verified,
        "source_hashes_sha256": json_sha256(source_hashes),
    }


def recover(source: Path, destination: Path, repo_root: Path) -> Path:
    source = source.resolve()
    destination = destination.resolve()
    repo_root = repo_root.resolve()
    if destination.exists():
        raise FileExistsError(f"Recovery destination already exists: {destination}")
    metadata_path = source / "run_metadata.json"
    original_metadata_bytes = metadata_path.read_bytes()
    metadata = json.loads(original_metadata_bytes)
    proof = verify_recorded_sources(source, metadata, repo_root)

    shutil.copytree(source, destination, copy_function=shutil.copy2)
    (destination / "run_bundle.json").unlink(missing_ok=True)
    recovery_directory = destination / "provenance_recovery"
    recovery_directory.mkdir()
    (recovery_directory / "original_run_metadata.json").write_bytes(
        original_metadata_bytes
    )

    recovery = {
        "schema_version": "async-manager-provenance-recovery-v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "reason": "missing_harness_source_state_in_runner_25152ad",
        "source_run_dir": str(source),
        "source_run_metadata_sha256": sha256_bytes(original_metadata_bytes),
        "recorded_revision": proof["revision"],
        "verified_source_count": len(proof["checked_paths"]),
        "source_hashes_sha256": proof["source_hashes_sha256"],
        "model_rerun": False,
        "evaluator_rerun": False,
    }
    recovery_path = destination / "provenance_recovery.json"
    recovery_path.write_text(
        json.dumps(recovery, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    metadata["harness_source_state"] = {
        "schema_version": "async-manager-harness-source-state-v1",
        "clean": True,
        "verification": "deterministic_posthoc_recovery_v1",
        **proof,
        "recovery_record_sha256": sha256_file(recovery_path),
    }
    (destination / "run_metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

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
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    arguments = parser.parse_args()
    bundle = recover(arguments.source, arguments.destination, arguments.repo_root)
    print(json.dumps({"valid": True, "run_bundle": str(bundle)}, indent=2))


if __name__ == "__main__":
    main()
