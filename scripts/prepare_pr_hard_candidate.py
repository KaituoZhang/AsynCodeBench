#!/usr/bin/env python
"""Validate and stage a PR-hard candidate in an existing upstream checkout.

This helper deliberately does not clone repositories or expose the gold commit.
The caller supplies a clean checkout at the candidate's pinned base SHA.  The
script verifies provenance and can apply the checksum-pinned public test patch.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = PROJECT_ROOT / "configs/tasks/pr_hard_candidates.v0.4.json"
SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate or stage an AsynCodeBench PR-hard candidate"
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--task-id")
    parser.add_argument(
        "--workspace",
        type=Path,
        help="Clean apache/tvm checkout at the candidate base SHA",
    )
    parser.add_argument(
        "--apply-public-tests",
        action="store_true",
        help="Apply the checksum-pinned test-only patch after validation",
    )
    return parser.parse_args()


def run_git(workspace: Path, *args: str, check: bool = True) -> str:
    completed = subprocess.run(
        ["git", "-C", str(workspace), *args],
        check=check,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def load_config(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "pr-hard-candidates-v0.4":
        raise ValueError(f"unsupported candidate schema in {path}")
    return payload


def resolve_overlay(relative_path: str) -> Path:
    overlay = (PROJECT_ROOT / relative_path).resolve()
    if not overlay.is_relative_to(PROJECT_ROOT.resolve()):
        raise ValueError(f"overlay escapes the project root: {relative_path}")
    return overlay


def patch_targets(patch_text: str) -> set[str]:
    targets = set()
    for line in patch_text.splitlines():
        if line.startswith("+++ b/"):
            targets.add(line.removeprefix("+++ b/"))
    return targets


def overlay_specs(record: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        record["public_test_overlay"],
        *record.get("supplemental_public_test_overlays", []),
    ]


def validate_record(record: dict[str, Any]) -> list[Path]:
    for field in ("base_sha", "gold_sha"):
        value = record.get(field, "")
        if not SHA_RE.fullmatch(value):
            raise ValueError(f"{record.get('task_id')}: invalid {field}")

    overlays = []
    targets: set[str] = set()
    for overlay_spec in overlay_specs(record):
        overlay = resolve_overlay(overlay_spec["path"])
        patch_bytes = overlay.read_bytes()
        observed_hash = hashlib.sha256(patch_bytes).hexdigest()
        if observed_hash != overlay_spec["sha256"]:
            raise ValueError(
                f"{record['task_id']}: overlay checksum mismatch: {observed_hash}"
            )
        patch_target_set = patch_targets(patch_bytes.decode("utf-8"))
        if targets.intersection(patch_target_set):
            raise ValueError(
                f"{record['task_id']}: public overlays have duplicate targets"
            )
        targets.update(patch_target_set)
        overlays.append(overlay)

    declared_targets = set(record["public_test_paths"])
    if not targets or targets != declared_targets:
        raise ValueError(
            f"{record['task_id']}: patch targets {sorted(targets)} do not match "
            f"declared public tests {sorted(declared_targets)}"
        )
    if any(not path.startswith("tests/") for path in targets):
        raise ValueError(f"{record['task_id']}: public overlay is not test-only")
    return overlays


def select_record(config: dict[str, Any], task_id: str) -> dict[str, Any]:
    matches = [record for record in config["records"] if record["task_id"] == task_id]
    if len(matches) != 1:
        raise ValueError(f"expected exactly one candidate named {task_id!r}")
    return matches[0]


def validate_workspace(
    record: dict[str, Any], workspace: Path, overlays: list[Path], apply_tests: bool
) -> str:
    workspace = workspace.resolve()
    if not workspace.is_dir():
        raise ValueError(f"workspace is not a directory: {workspace}")

    head = run_git(workspace, "rev-parse", "HEAD")
    if head != record["base_sha"]:
        raise ValueError(
            f"workspace HEAD is {head}; expected pinned base {record['base_sha']}"
        )

    tracked_changes = run_git(
        workspace, "status", "--porcelain", "--untracked-files=no"
    )
    if tracked_changes:
        raise ValueError("workspace has tracked changes; use a clean base checkout")

    gold_known = (
        subprocess.run(
            [
                "git",
                "-C",
                str(workspace),
                "cat-file",
                "-e",
                f"{record['gold_sha']}^{{commit}}",
            ],
            check=False,
            capture_output=True,
        ).returncode
        == 0
    )
    if gold_known:
        gold_parent = run_git(workspace, "rev-parse", f"{record['gold_sha']}^")
        if gold_parent != record["base_sha"]:
            raise ValueError(
                f"gold parent is {gold_parent}; expected {record['base_sha']}"
            )

    for overlay in overlays:
        run_git(workspace, "apply", "--check", str(overlay))
    if apply_tests:
        for overlay in overlays:
            run_git(workspace, "apply", str(overlay))
        return f"{len(overlays)} public test overlay(s) applied"
    return f"{len(overlays)} public test overlay(s) apply cleanly"


def main() -> int:
    args = parse_args()
    config = load_config(args.config)
    for record in config["records"]:
        validate_record(record)

    if args.task_id is None:
        for record in config["records"]:
            print(
                f"{record['task_id']}\t{record['qualification_status']}\t"
                f"{','.join(record['execution_eligibility'])}"
            )
        return 0

    record = select_record(config, args.task_id)
    overlays = validate_record(record)
    if args.apply_public_tests and args.workspace is None:
        raise ValueError("--apply-public-tests requires --workspace")

    if args.workspace is not None:
        print(
            validate_workspace(
                record,
                args.workspace,
                overlays,
                apply_tests=args.apply_public_tests,
            )
        )

    print("focused evaluator:", " ".join(record["focused_evaluator"]))
    print("regression evaluator:", " ".join(record["regression_evaluator"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
