#!/usr/bin/env python3
"""Verify that a TVM task image preserves its immutable backup contract."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "configs/environments/official_task_images.v0.4.json"
RUNTIME_ROOT = Path("/opt/asyncodebench/runtime")
TVM_TASKS = ("20018", "20073", "20107", "20153")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backup-root", type=Path, required=True)
    parser.add_argument("--task", action="append", choices=TVM_TASKS, dest="tasks")
    parser.add_argument(
        "--image",
        help="Explicit image for a single task (useful before publication)",
    )
    return parser.parse_args()


def run(*args: str | Path) -> str:
    completed = subprocess.run(
        [str(arg) for arg in args],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    return completed.stdout.strip()


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def image_record(pr_number: str) -> dict[str, Any]:
    task_id = f"asyncodebench:apache-tvm-{pr_number}"
    matches = [
        record for record in load(REGISTRY)["records"] if record["task_id"] == task_id
    ]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one image record for {task_id}")
    return matches[0]


def official_reference(record: dict[str, Any]) -> str:
    if record["status"] != "published" or not record.get("digest"):
        raise RuntimeError(f"Image is not published: {record['task_id']}")
    repository = record["image"].rsplit(":", 1)[0]
    return f"{repository}@{record['digest']}"


def inspect_labels(image: str) -> dict[str, str]:
    raw = run(
        "docker", "image", "inspect", image, "--format", "{{json .Config.Labels}}"
    )
    return json.loads(raw)


def validate_extracted_seed(seed: Path, manifest: dict[str, Any]) -> None:
    expected = {
        "commit": manifest["seed_commit"],
        "tree": manifest["seed_tree"],
    }
    observed = {
        "commit": run("git", "-C", seed, "rev-parse", "HEAD"),
        "tree": run("git", "-C", seed, "rev-parse", "HEAD^{tree}"),
    }
    if observed != expected:
        raise RuntimeError(f"Seed identity mismatch: {observed} != {expected}")
    if run("git", "-C", seed, "rev-list", "--all", "--count") != "1":
        raise RuntimeError("Image seed contains more than one visible commit")
    if run("git", "-C", seed, "remote"):
        raise RuntimeError("Image seed exposes a Git remote")
    if run("git", "-C", seed, "status", "--porcelain"):
        raise RuntimeError("Image seed is not clean")


def verify_one(backup_root: Path, pr_number: str, image: str) -> dict[str, Any]:
    backup = backup_root / f"apache-tvm-{pr_number}"
    manifest_path = backup / "container_backup_manifest.json"
    manifest = load(manifest_path)
    labels = inspect_labels(image)
    expected_labels = {
        "org.asyncodebench.task-id": manifest["public_task_id"],
        "org.asyncodebench.source-task-id": manifest["task_id"],
        "org.asyncodebench.base-sha": manifest["base_sha"],
        "org.asyncodebench.seed-commit": manifest["seed_commit"],
        "org.asyncodebench.seed-tree": manifest["seed_tree"],
        "org.asyncodebench.backup-manifest-sha256": sha256(manifest_path),
        "org.asyncodebench.model-visible-gold": "false",
        "org.asyncodebench.model-visible-history": "false",
    }
    observed_labels = {key: labels.get(key) for key in expected_labels}
    if observed_labels != expected_labels:
        raise RuntimeError(
            f"Image label mismatch for {pr_number}: "
            f"{observed_labels} != {expected_labels}"
        )

    container_id = run("docker", "create", image, "/bin/true")
    try:
        with tempfile.TemporaryDirectory(prefix=f"asyncodebench-{pr_number}-") as tmp:
            extracted = Path(tmp) / "seed"
            run("docker", "cp", f"{container_id}:{RUNTIME_ROOT / 'seed'}", extracted)
            validate_extracted_seed(extracted, manifest)
    finally:
        subprocess.run(
            ["docker", "rm", "-f", container_id],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    probe_code = (
        "import importlib.metadata as m,json,pathlib,sys;"
        "p=pathlib.Path('/opt/asyncodebench/runtime');"
        "x=json.loads((p/'container_backup_manifest.json').read_text());"
        "print(json.dumps({'manifest':x,'python':'.'.join(map(str,sys.version_info[:3])),"
        "'ffi_version':m.version('apache-tvm-ffi'),"
        "'cython':m.version('Cython'),"
        "'pytest_json_report':m.version('pytest-json-report')}))"
    )
    raw_probe = run(
        "docker",
        "run",
        "--rm",
        "--entrypoint",
        str(RUNTIME_ROOT / "env/bin/python"),
        image,
        "-c",
        probe_code,
    )
    probe = json.loads(raw_probe.splitlines()[-1])
    expected_environment = manifest["environment"]
    for key in ("python", "ffi_version", "cython", "pytest_json_report"):
        if probe[key] != expected_environment[key]:
            raise RuntimeError(
                f"Environment mismatch for {pr_number}/{key}: "
                f"{probe[key]} != {expected_environment[key]}"
            )
    if probe["manifest"] != manifest:
        raise RuntimeError(f"Embedded backup manifest mismatch for {pr_number}")
    return {
        "task_id": manifest["public_task_id"],
        "image": image,
        "base_sha": manifest["base_sha"],
        "seed_commit": manifest["seed_commit"],
        "seed_tree": manifest["seed_tree"],
        "python": probe["python"],
        "ffi_version": probe["ffi_version"],
        "equivalent": True,
    }


def main() -> int:
    args = parse_args()
    backup_root = args.backup_root.expanduser().resolve()
    tasks = tuple(args.tasks or TVM_TASKS)
    if args.image and len(tasks) != 1:
        raise ValueError("--image requires exactly one --task")
    if shutil.which("docker") is None or shutil.which("git") is None:
        raise RuntimeError("docker and git are required")
    results = []
    for pr_number in tasks:
        record = image_record(pr_number)
        image = args.image or official_reference(record)
        results.append(verify_one(backup_root, pr_number, image))
    print(json.dumps({"valid": True, "tasks": results}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
