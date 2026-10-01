#!/usr/bin/env python3
"""Validate and package one public core-task result as a v0.4 baseline."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from pathlib import Path

from build_v04_release_index import (
    BASELINES,
    OFFICIAL_TASKS,
    ROOT,
    TASK_INDEX,
    build_documents,
    load_json,
    render,
    sha256,
    validate_baselines,
)

RUNNER = ROOT / "reproductions/async-swe-agents"
sys.path.insert(0, str(RUNNER))
from asyncodebench_harness.results import validate_run_bundle  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--name", required=True, help="public baseline directory name")
    parser.add_argument("--check", action="store_true", help="validate without copying")
    args = parser.parse_args()
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", args.name) is None:
        parser.error("--name must contain only letters, digits, '.', '_' or '-'")

    os.environ["ASYNCODEBENCH_ROOT"] = str(ROOT)
    source = args.run_dir.expanduser().resolve()
    if not (source / "run_bundle.json").is_file():
        parser.error(f"run_bundle.json is missing in {source}")
    # The v0.4 registry changes the v0.4 index checksum. Core v0.3 bundles
    # reference the independent v0.3 index and avoid a circular checksum.
    bundle = load_json(source / "run_bundle.json")
    if bundle.get("release") != "v0.3":
        parser.error("only core v0.3 bundles can be registered in v0.4")
    if bundle.get("task_id") not in {
        task["task_id"] for task in load_json(ROOT / "manifests/release/v0.3/task_index.json")["tasks"]
    }:
        parser.error("bundle task is not in the released core task set")
    result = validate_run_bundle(source)
    if result.get("status") != "valid" or not result.get("eligibility", {}).get("official_aggregate"):
        parser.error(f"result failed official validation: {result.get('issues')}")
    print(f"Valid official result: {result['task_id']} / {result['protocol']}")
    if args.check:
        return 0

    destination = ROOT / "manifests/release/v0.4/baselines" / args.name
    if destination.exists():
        parser.error(f"baseline directory already exists: {destination}")
    original_registry = BASELINES.read_bytes()
    registry = json.loads(original_registry)
    shutil.copytree(source, destination)
    try:
        entry = {
            "path": (destination / "run_bundle.json").relative_to(ROOT).as_posix(),
            "sha256": sha256(destination / "run_bundle.json"),
        }
        registry["bundles"].append(entry)
        task_ids = {
            task["task_id"] for task in load_json(TASK_INDEX)["tasks"]
        }
        validate_baselines(ROOT, registry, task_ids)
        BASELINES.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        index, official = build_documents()
        TASK_INDEX.write_text(render(index), encoding="utf-8")
        OFFICIAL_TASKS.write_text(render(official), encoding="utf-8")
    except Exception:
        BASELINES.write_bytes(original_registry)
        shutil.rmtree(destination)
        raise
    print(f"Packaged baseline: {destination.relative_to(ROOT)}")
    print("Review the packaged artifacts before publishing this repository.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
