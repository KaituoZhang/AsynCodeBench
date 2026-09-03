#!/usr/bin/env python3
"""Verify the immutable Qwen3.6 historical CAID+Repair ablation records."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST_PATH = HERE / "manifest.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fail(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--require-bundles",
        action="store_true",
        help=(
            "require the separately archived raw result directories and "
            "verify every indexed artifact checksum"
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    index_record = manifest["frozen_result_index"]
    index_path = ROOT / index_record["path"]
    if not index_path.is_file():
        fail(f"missing frozen result index: {index_path}")
    observed_index_hash = sha256(index_path)
    if observed_index_hash != index_record["sha256"]:
        fail(
            "frozen result index checksum mismatch: "
            f"expected {index_record['sha256']}, got {observed_index_hash}"
        )

    task_revisions: dict[str, str] = {}
    task_policies: dict[str, str] = {}
    for revision, record in manifest["runner_revisions"].items():
        for task in record["tasks"]:
            if task in task_revisions:
                fail(f"task appears under multiple revisions: {task}")
            task_revisions[task] = revision
            task_policies[task] = record.get("task_policy_overrides", {}).get(
                task, record["manager_policy"]
            )

    frozen_index = json.loads(index_path.read_text(encoding="utf-8"))
    caid_entries = [
        entry
        for entry in frozen_index["entries"]
        if entry.get("protocol") == "caid_manager"
    ]
    expected_cells = manifest["selected_task_cells"]
    if len(caid_entries) != expected_cells:
        fail(f"expected {expected_cells} CAID cells, found {len(caid_entries)}")

    seen: set[str] = set()
    verified_bundles = 0
    missing_bundles: list[str] = []
    for entry in caid_entries:
        task = entry["task"]
        seen.add(task)
        if task not in task_revisions:
            fail(f"frozen CAID task is absent from ablation manifest: {task}")
        run_dir = ROOT / entry["run_dir"]
        bundle_path = run_dir / "run_bundle.json"
        if not bundle_path.is_file():
            missing_bundles.append(task)
            if args.require_bundles:
                fail(f"missing run bundle for {task}: {bundle_path}")
            continue
        bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
        observed_revision = bundle["provenance"]["runner_revision"]
        expected_revision = task_revisions[task]
        if observed_revision != expected_revision:
            fail(
                f"runner revision mismatch for {task}: expected "
                f"{expected_revision}, got {observed_revision}"
            )
        for relative_path, expected_hash in entry["artifact_sha256"].items():
            artifact_path = run_dir / relative_path
            if not artifact_path.is_file():
                fail(f"missing indexed artifact for {task}: {artifact_path}")
            observed_hash = sha256(artifact_path)
            if observed_hash != expected_hash:
                fail(
                    f"artifact checksum mismatch for {task}/{relative_path}: "
                    f"expected {expected_hash}, got {observed_hash}"
                )
        verified_bundles += 1

    missing = sorted(set(task_revisions) - seen)
    if missing:
        fail(f"manifest tasks absent from frozen CAID index: {missing}")

    writable = sum(policy != "read_only" for policy in task_policies.values())
    read_only = sorted(
        task for task, policy in task_policies.items() if policy == "read_only"
    )
    if writable != manifest["writable_manager_task_cells"]:
        fail(
            "writable-manager cell count mismatch: expected "
            f"{manifest['writable_manager_task_cells']}, got {writable}"
        )
    if read_only != sorted(manifest["read_only_manager_exceptions"]):
        fail(
            "read-only exception mismatch: expected "
            f"{manifest['read_only_manager_exceptions']}, got {read_only}"
        )

    print(
        "Verified historical CAID+Repair ablation: "
        f"{len(caid_entries)} frozen cells, {writable} writable-manager cells, "
        f"{len(read_only)} documented read-only exception; "
        f"raw bundles verified {verified_bundles}/{len(caid_entries)}."
    )
    if missing_bundles:
        print(
            "Raw bundles are not part of the GitHub checkout; skipped: "
            + ", ".join(sorted(missing_bundles))
        )


if __name__ == "__main__":
    main()
