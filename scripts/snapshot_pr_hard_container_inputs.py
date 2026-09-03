#!/usr/bin/env python3
"""Create immutable, answer-free snapshots for PR-hard container builds.

The snapshot is deliberately separate from the active runtime.  It copies the
validated model-visible seed and frozen toolchain, omits transient build/cache
files, and records enough provenance to prove which task state was packaged.
No source runtime file is modified.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import stat
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "configs/tasks/pr_hard_candidates.v0.4.json"
CONDA_LOCK = ROOT / "configs/environments/pr_hard_tvm.v0.4.conda-lock.txt"
REQUIREMENTS_LOCK = ROOT / "configs/environments/pr_hard_tvm.v0.4.requirements-lock.txt"
SUPPORTED_IDS = ("20018", "20073", "20107", "20153")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Snapshot validated TVM runtimes without modifying them"
    )
    parser.add_argument(
        "--source-root",
        type=Path,
        default=ROOT / ".cache/pr_hard_runtime/v0.4",
    )
    parser.add_argument(
        "--backup-root",
        type=Path,
        required=True,
        help="New destination; existing snapshots are never overwritten",
    )
    parser.add_argument(
        "--task-id",
        action="append",
        choices=SUPPORTED_IDS,
        dest="task_ids",
        help="PR number to snapshot; repeat as needed (default: all four)",
    )
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def command(*args: str | Path) -> str:
    completed = subprocess.run(
        [str(arg) for arg in args],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    return completed.stdout.strip()


def record_for(pr_number: str) -> dict[str, Any]:
    task_id = f"pr-hard:apache-tvm-{pr_number}"
    records = read_json(REGISTRY)["records"]
    matches = [record for record in records if record["task_id"] == task_id]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one candidate record for {task_id}")
    return matches[0]


def validate_seed(seed: Path, record: dict[str, Any]) -> dict[str, Any]:
    if command("git", "-C", seed, "rev-list", "--all", "--count") != "1":
        raise RuntimeError(f"Seed must contain exactly one commit: {seed}")
    if command("git", "-C", seed, "remote"):
        raise RuntimeError(f"Seed must not expose Git remotes: {seed}")
    if command("git", "-C", seed, "status", "--porcelain"):
        raise RuntimeError(f"Seed is dirty: {seed}")
    nested = [path for path in seed.rglob(".git") if path != seed / ".git"]
    if nested:
        raise RuntimeError(f"Seed contains nested Git metadata: {nested[:3]}")
    for relative in record["public_test_paths"]:
        if not (seed / relative).is_file():
            raise RuntimeError(f"Missing public test {relative} in {seed}")
    return {
        "commit": command("git", "-C", seed, "rev-parse", "HEAD"),
        "tree": command("git", "-C", seed, "rev-parse", "HEAD^{tree}"),
    }


def probe_environment(environment: Path) -> dict[str, Any]:
    python = environment / "bin/python"
    probe = (
        "import importlib.metadata as m,json,sys;"
        "d=m.distribution('apache-tvm-ffi');"
        "u=json.loads(d.read_text('direct_url.json') or '{}');"
        "print(json.dumps({'python':'.'.join(map(str,sys.version_info[:3])),"
        "'ffi_version':d.version,'ffi_editable':bool(u.get('dir_info',{}).get('editable')),"
    )
    probe += (
        "'cython':m.version('Cython'),"
        "'pytest_json_report':m.version('pytest-json-report')}))"
    )
    payload = json.loads(command(python, "-c", probe).splitlines()[-1])
    if payload["ffi_editable"]:
        raise RuntimeError(f"Editable tvm-ffi is not publishable: {environment}")
    if not payload["python"].startswith("3.11."):
        raise RuntimeError(f"Unexpected Python version: {payload['python']}")
    for tool in ("cmake", "ninja", "llvm-config"):
        payload[tool] = command(environment / "bin" / tool, "--version").splitlines()[0]
    return payload


def copy_runtime(source: Path, destination: Path) -> None:
    destination.mkdir(mode=0o755)
    subprocess.run(
        [
            "rsync",
            "-a",
            "--exclude=/build",
            "--exclude=/.pytest_cache",
            "--exclude=__pycache__",
            "--exclude=*.pyc",
            f"{source / 'seed'}/",
            str(destination / "seed"),
        ],
        check=True,
    )
    (destination / "env").mkdir(mode=0o755)
    subprocess.run(
        [
            "cp",
            "-a",
            "--reflink=auto",
            f"{source / 'env'}/.",
            str(destination / "env"),
        ],
        check=True,
    )


def make_read_only(root: Path) -> None:
    for path in [*root.rglob("*"), root]:
        if path.is_symlink():
            continue
        mode = path.stat().st_mode
        if path.is_dir():
            readable_directory = (
                mode
                | stat.S_IRUSR
                | stat.S_IRGRP
                | stat.S_IROTH
                | stat.S_IXUSR
                | stat.S_IXGRP
                | stat.S_IXOTH
            )
            path.chmod(readable_directory & ~0o222)
        else:
            path.chmod((mode | stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH) & ~0o222)


def snapshot_one(
    source_root: Path, backup_root: Path, pr_number: str
) -> dict[str, Any]:
    record = record_for(pr_number)
    source = source_root / f"apache-tvm-{pr_number}"
    destination = backup_root / f"apache-tvm-{pr_number}"
    if destination.exists():
        raise FileExistsError(f"Refusing to overwrite immutable backup: {destination}")
    if not (source / "seed").is_dir() or not (source / "env").is_dir():
        raise FileNotFoundError(f"Incomplete source runtime: {source}")

    seed = validate_seed(source / "seed", record)
    environment = probe_environment(source / "env")
    copy_runtime(source, destination)
    copied_seed = validate_seed(destination / "seed", record)
    copied_environment = probe_environment(destination / "env")
    if copied_seed != seed or copied_environment != environment:
        raise RuntimeError(f"Snapshot validation differs from source for {pr_number}")

    overlays = [
        record["public_test_overlay"],
        *record.get("supplemental_public_test_overlays", []),
    ]
    manifest = {
        "schema_version": "asyncodebench-pr-hard-container-backup-v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "task_id": record["task_id"],
        "public_task_id": f"asyncodebench:apache-tvm-{pr_number}",
        # Do not leak a maintainer-specific host path into the public image.
        "source_runtime": f".cache/pr_hard_runtime/v0.4/apache-tvm-{pr_number}",
        "base_sha": record["base_sha"],
        "seed_commit": seed["commit"],
        "seed_tree": seed["tree"],
        "environment": environment,
        "locks": {
            "conda": {
                "path": str(CONDA_LOCK.relative_to(ROOT)),
                "sha256": sha256(CONDA_LOCK),
            },
            "python": {
                "path": str(REQUIREMENTS_LOCK.relative_to(ROOT)),
                "sha256": sha256(REQUIREMENTS_LOCK),
            },
        },
        "public_overlays": [
            {"path": item["path"], "sha256": item["sha256"]} for item in overlays
        ],
        "model_visible_gold": False,
        "model_visible_git_history": False,
        "transient_paths_omitted": [
            "seed/build",
            "**/.pytest_cache",
            "**/__pycache__",
            "**/*.pyc",
        ],
    }
    manifest_path = destination / "container_backup_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    make_read_only(destination)
    return {**manifest, "backup": str(destination.resolve())}


def main() -> int:
    args = parse_args()
    source_root = args.source_root.expanduser().resolve()
    backup_root = args.backup_root.expanduser().resolve()
    if backup_root.exists():
        raise FileExistsError(
            f"Backup root already exists; choose a new immutable path: {backup_root}"
        )
    backup_root.mkdir(parents=True, mode=0o755)
    task_ids = tuple(args.task_ids or SUPPORTED_IDS)
    try:
        results = [
            snapshot_one(source_root, backup_root, pr_number) for pr_number in task_ids
        ]
        index = {
            "schema_version": "asyncodebench-pr-hard-container-backup-index-v1",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source_root": str(source_root),
            "tasks": results,
        }
        index_path = backup_root / "backup_index.json"
        index_path.write_text(
            json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        make_read_only(backup_root)
        print(json.dumps(index, indent=2, sort_keys=True))
    except BaseException:
        # Preserve any completed snapshots for forensic inspection.  The caller
        # must choose a new backup root on retry; nothing is overwritten.
        raise
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
