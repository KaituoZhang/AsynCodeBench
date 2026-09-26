#!/usr/bin/env python3
"""Build, publish, pull, and verify official AsynCodeBench task images."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "configs/environments/official_task_images.v0.4.json"
DOCKERFILE = ROOT / "containers/pr_hard_tvm/Dockerfile"
TVM_TASKS = ("20018", "20073", "20107", "20153")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=REGISTRY)
    commands = parser.add_subparsers(dest="command", required=True)

    for name in ("list", "check", "pull"):
        command = commands.add_parser(name)
        command.add_argument("--task", action="append", dest="tasks")

    build = commands.add_parser("build")
    build.add_argument("--backup-root", type=Path, required=True)
    build.add_argument("--task", action="append", choices=TVM_TASKS, dest="tasks")
    build.add_argument("--push", action="store_true")
    build.add_argument(
        "--result-json",
        type=Path,
        help="Write local IDs/remote digests without modifying the registry",
    )
    return parser.parse_args()


def run(*args: str | Path, capture: bool = True) -> str:
    print("+", " ".join(str(arg) for arg in args), flush=True)
    completed = subprocess.run(
        [str(arg) for arg in args],
        check=True,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.STDOUT if capture else None,
    )
    output = completed.stdout.strip() if completed.stdout else ""
    if output:
        print(output)
    return output


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def image_reference(record: dict[str, Any], *, require_digest: bool) -> str:
    digest = record.get("digest")
    if require_digest and not digest:
        raise RuntimeError(f"Image is not published: {record['task_id']}")
    return (
        f"{record['image'].rsplit(':', 1)[0]}@{digest}" if digest else record["image"]
    )


def selected_records(
    registry: dict[str, Any], tasks: list[str] | None
) -> list[dict[str, Any]]:
    records = registry["records"]
    if not tasks:
        return records
    requested = set(tasks)
    selected = [
        record
        for record in records
        if record["task_id"] in requested
        or record["source_task_id"] in requested
        or record["task_id"].rsplit("-", 1)[-1] in requested
    ]
    found = {
        value
        for record in selected
        for value in (
            record["task_id"],
            record["source_task_id"],
            record["task_id"].rsplit("-", 1)[-1],
        )
    }
    missing = requested - found
    if missing:
        raise ValueError(f"Unknown task selectors: {sorted(missing)}")
    return selected


def remote_digest(image: str) -> str:
    raw = run("docker", "buildx", "imagetools", "inspect", image)
    for line in raw.splitlines():
        if line.strip().startswith("Digest:"):
            return line.split("Digest:", 1)[1].strip()
    raise RuntimeError(f"Could not resolve remote digest for {image}")


def check(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results = []
    for record in records:
        expected = record.get("digest")
        if not expected:
            results.append({"task_id": record["task_id"], "status": "unpublished"})
            continue
        observed = remote_digest(record["image"])
        if observed != expected:
            raise RuntimeError(
                f"Digest mismatch for {record['task_id']}: {observed} != {expected}"
            )
        results.append(
            {"task_id": record["task_id"], "status": "verified", "digest": observed}
        )
    return results


def build_one(
    backup_root: Path,
    record: dict[str, Any],
    revision: str,
    push: bool,
) -> dict[str, Any]:
    pr_number = record["task_id"].rsplit("-", 1)[-1]
    if pr_number not in TVM_TASKS:
        raise ValueError(f"Only TVM images can be built here: {record['task_id']}")
    context = backup_root / f"apache-tvm-{pr_number}"
    manifest_path = context / "container_backup_manifest.json"
    manifest = read_json(manifest_path)
    if manifest["public_task_id"] != record["task_id"]:
        raise RuntimeError(f"Backup/task mismatch: {context}")
    if manifest["model_visible_gold"] or manifest["model_visible_git_history"]:
        raise RuntimeError(f"Unsafe model-visible backup: {context}")

    build_args = {
        "TASK_ID": manifest["task_id"],
        "PUBLIC_TASK_ID": manifest["public_task_id"],
        "BASE_SHA": manifest["base_sha"],
        "SEED_COMMIT": manifest["seed_commit"],
        "SEED_TREE": manifest["seed_tree"],
        "BACKUP_MANIFEST_SHA256": sha256(manifest_path),
        "REVISION": revision,
    }
    command: list[str | Path] = [
        "docker",
        "build",
        "--platform",
        "linux/amd64",
        "--file",
        DOCKERFILE,
        "--tag",
        record["image"],
    ]
    for key, value in build_args.items():
        command.extend(("--build-arg", f"{key}={value}"))
    command.append(context)
    run(*command, capture=False)

    image_id = run("docker", "image", "inspect", record["image"], "--format", "{{.Id}}")
    size = int(
        run("docker", "image", "inspect", record["image"], "--format", "{{.Size}}")
    )
    probe = run(
        "docker",
        "run",
        "--rm",
        "--platform",
        "linux/amd64",
        "--entrypoint",
        "/opt/asyncodebench/runtime/env/bin/python",
        record["image"],
        "-c",
        (
            "import importlib.metadata as m,json,pathlib,sys;"
            "p=pathlib.Path('/opt/asyncodebench/runtime');"
            "x=json.loads((p/'container_backup_manifest.json').read_text());"
            "assert x['model_visible_gold'] is False;"
            "assert x['model_visible_git_history'] is False;"
            "print(json.dumps({'python':sys.version.split()[0],"
            "'ffi':m.version('apache-tvm-ffi'),'seed_commit':x['seed_commit']}))"
        ),
    )
    result: dict[str, Any] = {
        "task_id": record["task_id"],
        "image": record["image"],
        "image_id": image_id,
        "size_bytes": size,
        "backup_manifest_sha256": build_args["BACKUP_MANIFEST_SHA256"],
        "probe": json.loads(probe.splitlines()[-1]),
    }
    if push:
        run("docker", "push", record["image"], capture=False)
        result["digest"] = remote_digest(record["image"])
    return result


def main() -> int:
    args = parse_args()
    registry_path = args.registry.expanduser().resolve()
    registry = read_json(registry_path)
    records = selected_records(registry, getattr(args, "tasks", None))

    if args.command == "list":
        print(
            json.dumps(
                [
                    {
                        "task_id": record["task_id"],
                        "status": record["status"],
                        "reference": image_reference(record, require_digest=False),
                    }
                    for record in records
                ],
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    if args.command == "check":
        print(json.dumps(check(records), indent=2, sort_keys=True))
        return 0
    if args.command == "pull":
        for record in records:
            run(
                "docker",
                "pull",
                "--platform",
                registry["platform"],
                image_reference(record, require_digest=True),
                capture=False,
            )
        return 0

    backup_root = args.backup_root.expanduser().resolve()
    revision = run("git", "-C", ROOT, "rev-parse", "HEAD")
    tvm_records = [record for record in records if "apache-tvm" in record["task_id"]]
    results = [
        build_one(backup_root, record, revision, args.push) for record in tvm_records
    ]
    payload = {
        "schema_version": "asyncodebench-image-build-results-v1",
        "results": results,
    }
    if args.result_json:
        output = args.result_json.expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
