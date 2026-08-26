#!/usr/bin/env python3
"""Build or validate a portable model-visible runtime for PR-hard candidates.

The runtime is reconstructed exclusively from the public candidate registry,
the pinned Apache TVM base commit, recursive submodules, public test overlays,
and checked-in environment locks.  The offline production gold is never
fetched, copied, or mounted into the model-visible package.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import stat
import subprocess
import tempfile
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = PROJECT_ROOT / "configs/tasks/pr_hard_candidates.v0.4.json"
ENVIRONMENT_PATH = PROJECT_ROOT / "configs/environments/pr_hard_tvm.v0.4.json"
CONDA_LOCK = PROJECT_ROOT / "configs/environments/pr_hard_tvm.v0.4.conda-lock.txt"
REQUIREMENTS_LOCK = (
    PROJECT_ROOT / "configs/environments/pr_hard_tvm.v0.4.requirements-lock.txt"
)
SUPPORTED_TASK = "pr-hard:apache-tvm-20153"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build or validate the isolated PR-hard v0.4 runtime package"
    )
    parser.add_argument("--task-id", default=SUPPORTED_TASK, choices=[SUPPORTED_TASK])
    parser.add_argument(
        "--runtime-root",
        type=Path,
        help="Destination (default: .cache/pr_hard_runtime/v0.4/apache-tvm-20153)",
    )
    parser.add_argument(
        "--micromamba",
        default=os.environ.get("MICROMAMBA", "micromamba"),
        help="micromamba executable used with the checked-in explicit lock",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate an existing package without network access or modification",
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


def run(*args: str | Path, cwd: Path | None = None) -> str:
    command = [str(item) for item in args]
    print("+", " ".join(command), flush=True)
    completed = subprocess.run(
        command,
        cwd=cwd,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if completed.stdout.strip():
        print(completed.stdout.rstrip())
    return completed.stdout


def git(repo: Path, *args: str) -> str:
    return run("git", "-C", repo, *args).rstrip("\n")


def candidate_record(task_id: str) -> dict[str, Any]:
    registry = read_json(REGISTRY_PATH)
    matches = [item for item in registry["records"] if item["task_id"] == task_id]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one candidate record for {task_id}")
    return matches[0]


def qualification_record(record: dict[str, Any]) -> dict[str, Any]:
    path = PROJECT_ROOT / record["qualification_record"]
    return read_json(path)


def runtime_root_for(record: dict[str, Any], configured: Path | None) -> Path:
    if configured is not None:
        return configured.expanduser().resolve()
    suffix = record["task_id"].rsplit("-", 1)[-1]
    return (
        PROJECT_ROOT / ".cache" / "pr_hard_runtime" / "v0.4" / f"apache-tvm-{suffix}"
    ).resolve()


def overlay_specs(record: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        record["public_test_overlay"],
        *record.get("supplemental_public_test_overlays", []),
    ]


def validate_checked_in_inputs(
    record: dict[str, Any], qualification: dict[str, Any]
) -> None:
    environment = qualification["environment"]
    expected_locks = {
        CONDA_LOCK: environment["conda_lock_sha256"],
        REQUIREMENTS_LOCK: environment["requirements_lock_sha256"],
    }
    for path, expected in expected_locks.items():
        observed = sha256(path)
        if observed != expected:
            raise RuntimeError(
                "Environment lock checksum mismatch for "
                f"{path}: {observed} != {expected}"
            )
    for spec in overlay_specs(record):
        path = PROJECT_ROOT / spec["path"]
        observed = sha256(path)
        if observed != spec["sha256"]:
            raise RuntimeError(
                f"Public overlay checksum mismatch for {path}: {observed}"
            )


def assert_supported_host() -> None:
    if platform.system() != "Linux" or platform.machine() not in {"x86_64", "amd64"}:
        raise RuntimeError(
            "The frozen PR-hard environment is an explicit conda linux-64 lock; "
            f"got {platform.system()} {platform.machine()}"
        )


def recursive_submodule_manifest(source: Path) -> tuple[str, str]:
    manifest = git(source, "submodule", "status", "--recursive") + "\n"
    return manifest, hashlib.sha256(manifest.encode("utf-8")).hexdigest()


def validate_source(
    source: Path, record: dict[str, Any], qualification: dict[str, Any]
) -> str:
    source = source.resolve()
    if git(source, "rev-parse", "HEAD") != record["base_sha"]:
        raise RuntimeError(
            f"Source checkout is not at pinned base {record['base_sha']}"
        )
    status = git(source, "status", "--porcelain", "--untracked-files=all")
    if status:
        raise RuntimeError("Source checkout must be clean before overlays are applied")
    manifest, observed_hash = recursive_submodule_manifest(source)
    expected_hash = qualification["environment"]["recursive_submodule_manifest_sha256"]
    if observed_hash != expected_hash:
        raise RuntimeError(
            "Recursive submodule manifest mismatch; run "
            "'git submodule update --init --recursive' at the pinned base.\n"
            f"observed={observed_hash}\nexpected={expected_hash}\n{manifest}"
        )
    expected_ffi = qualification["environment"]["tvm_ffi_sha"]
    ffi_head = git(source / "3rdparty/tvm-ffi", "rev-parse", "HEAD")
    if ffi_head != expected_ffi:
        raise RuntimeError(f"tvm-ffi is {ffi_head}; expected {expected_ffi}")
    return manifest


def clone_source(destination: Path, record: dict[str, Any]) -> None:
    run(
        "git",
        "clone",
        "--filter=blob:none",
        "--no-checkout",
        record["repository_url"],
        destination,
    )
    git(destination, "checkout", "--detach", record["base_sha"])
    git(destination, "submodule", "update", "--init", "--recursive")


def apply_public_overlays(source: Path, record: dict[str, Any]) -> None:
    for spec in overlay_specs(record):
        overlay = (PROJECT_ROOT / spec["path"]).resolve()
        git(source, "apply", "--check", str(overlay))
        git(source, "apply", str(overlay))
    changed = set(git(source, "diff", "--name-only").splitlines())
    untracked = set(
        git(source, "ls-files", "--others", "--exclude-standard").splitlines()
    )
    observed = changed | untracked
    expected = set(record["public_test_paths"])
    if observed != expected:
        raise RuntimeError(
            "Model-visible source differs outside the declared public tests: "
            f"observed={sorted(observed)}, expected={sorted(expected)}"
        )


def copy_without_git(source: str, names: list[str]) -> set[str]:
    del source
    ignored = {name for name in names if name == ".git"}
    ignored.update(name for name in names if name in {"__pycache__", ".pytest_cache"})
    return ignored


def create_seed(source: Path, seed: Path) -> str:
    shutil.copytree(source, seed, symlinks=True, ignore=copy_without_git)
    run("git", "init", "--initial-branch=master", seed)
    git(seed, "config", "user.email", "asyncodebench@example.com")
    git(seed, "config", "user.name", "AsynCodeBench PR-hard")
    # Submodule sources contain their own ignore rules. Once flattened into the
    # one-commit seed, every copied public source file must remain tracked even
    # if an upstream nested .gitignore would otherwise hide it.
    git(seed, "add", "-f", "-A")
    commit_env = os.environ.copy()
    commit_env.update(
        {
            "GIT_AUTHOR_DATE": "2000-01-01T00:00:00Z",
            "GIT_COMMITTER_DATE": "2000-01-01T00:00:00Z",
        }
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(seed),
            "commit",
            "-m",
            "Sanitized PR-hard model-visible base",
        ],
        check=True,
        env=commit_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return git(seed, "rev-parse", "HEAD")


def build_environment(
    source: Path,
    environment: Path,
    micromamba: str,
) -> None:
    if shutil.which(micromamba) is None and not Path(micromamba).is_file():
        raise RuntimeError(
            f"Cannot find micromamba executable {micromamba!r}; install micromamba "
            "or pass --micromamba /absolute/path/to/micromamba"
        )
    run(micromamba, "create", "-y", "-p", environment, "--file", CONDA_LOCK)
    python = environment / "bin/python"
    run(python, "-m", "pip", "install", "--requirement", REQUIREMENTS_LOCK)
    run(
        python,
        "-m",
        "pip",
        "install",
        "--no-build-isolation",
        source / "3rdparty/tvm-ffi",
    )


def make_container_readable(path: Path) -> None:
    for item in [path, *path.rglob("*")]:
        if item.is_symlink():
            continue
        mode = item.stat().st_mode
        if item.is_dir():
            item.chmod(mode | stat.S_IRUSR | stat.S_IXUSR | stat.S_IROTH | stat.S_IXOTH)
        else:
            item.chmod(mode | stat.S_IRUSR | stat.S_IROTH)


def environment_probe(environment: Path) -> dict[str, str]:
    python = environment / "bin/python"
    code = (
        "import importlib.metadata as m, json, sys; "
        "d=m.distribution('apache-tvm-ffi'); "
        "u=json.loads(d.read_text('direct_url.json') or '{}'); "
        "print(json.dumps({'python': '.'.join(map(str, sys.version_info[:3])), "
        "'ffi_version': d.version, "
        "'ffi_editable': bool(u.get('dir_info', {}).get('editable')), "
        "'cython': m.version('Cython'), "
        "'pytest_json_report': m.version('pytest-json-report')}))"
    )
    payload = json.loads(run(python, "-c", code).splitlines()[-1])
    for tool in ("cmake", "ninja", "llvm-config"):
        executable = environment / "bin" / tool
        first_line = run(executable, "--version").splitlines()[0]
        payload[tool] = first_line
    return payload


def validate_runtime(
    runtime_root: Path,
    record: dict[str, Any],
    qualification: dict[str, Any],
) -> dict[str, Any]:
    seed = runtime_root / "seed"
    environment = runtime_root / "env"
    for path in (runtime_root, seed, environment):
        if not path.is_dir():
            raise RuntimeError(f"Missing runtime directory: {path}")
        mode = path.stat().st_mode
        if mode & (stat.S_IROTH | stat.S_IXOTH) != (stat.S_IROTH | stat.S_IXOTH):
            raise RuntimeError(f"Container cannot traverse {path}; run chmod a+rX")
    if git(seed, "rev-list", "--all", "--count") != "1":
        raise RuntimeError("Model-visible seed must contain exactly one commit")
    if git(seed, "remote"):
        raise RuntimeError("Model-visible seed must not contain Git remotes")
    if git(seed, "status", "--porcelain"):
        raise RuntimeError("Model-visible seed is dirty")
    nested_git = [path for path in seed.rglob(".git") if path != seed / ".git"]
    if nested_git:
        raise RuntimeError(
            f"Model-visible seed exposes nested Git metadata: {nested_git[:3]}"
        )
    for relative in record["public_test_paths"]:
        if not (seed / relative).is_file():
            raise RuntimeError(f"Model-visible public test is missing: {relative}")
    probe = environment_probe(environment)
    expected_ffi = qualification["runtime_package_validation"]["task_local_ffi_version"]
    if probe["ffi_version"] != expected_ffi:
        raise RuntimeError(
            "Runtime has apache-tvm-ffi "
            f"{probe['ffi_version']}; expected {expected_ffi}"
        )
    if probe["ffi_editable"]:
        raise RuntimeError("Runtime tvm-ffi installation must not be editable")
    if not probe["python"].startswith("3.11."):
        raise RuntimeError(f"Runtime Python must be 3.11.x; got {probe['python']}")
    return {
        "runtime_root": str(runtime_root),
        "seed_commit": git(seed, "rev-parse", "HEAD"),
        "seed_commit_count": 1,
        "seed_has_remotes": False,
        **probe,
    }


def build_runtime(
    runtime_root: Path,
    record: dict[str, Any],
    qualification: dict[str, Any],
    micromamba: str,
) -> dict[str, Any]:
    if runtime_root.exists():
        raise RuntimeError(
            f"Runtime destination already exists: {runtime_root}. "
            "Use --check, or move the existing directory aside before rebuilding."
        )
    runtime_root.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="pr-hard-20153-source-", dir=runtime_root.parent
    ) as temporary:
        source = Path(temporary) / "tvm"
        clone_source(source, record)
        submodule_manifest = validate_source(source, record, qualification)
        apply_public_overlays(source, record)
        runtime_root.mkdir(mode=0o755)
        try:
            seed_commit = create_seed(source, runtime_root / "seed")
            build_environment(source, runtime_root / "env", micromamba)
            manifest = {
                "schema_version": "pr-hard-runtime-package-v0.4",
                "task_id": record["task_id"],
                "base_sha": record["base_sha"],
                "seed_commit": seed_commit,
                "recursive_submodule_manifest_sha256": hashlib.sha256(
                    submodule_manifest.encode("utf-8")
                ).hexdigest(),
                "public_overlays": [
                    {"path": item["path"], "sha256": item["sha256"]}
                    for item in overlay_specs(record)
                ],
                "conda_lock_sha256": sha256(CONDA_LOCK),
                "requirements_lock_sha256": sha256(REQUIREMENTS_LOCK),
                "model_visible_gold": False,
                "model_visible_git_history": False,
            }
            (runtime_root / "runtime_manifest.json").write_text(
                json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            make_container_readable(runtime_root)
            return validate_runtime(runtime_root, record, qualification)
        except BaseException:
            shutil.rmtree(runtime_root, ignore_errors=True)
            raise


def main() -> int:
    args = parse_args()
    assert_supported_host()
    record = candidate_record(args.task_id)
    qualification = qualification_record(record)
    validate_checked_in_inputs(record, qualification)
    runtime_root = runtime_root_for(record, args.runtime_root)
    if args.check:
        result = validate_runtime(runtime_root, record, qualification)
    else:
        result = build_runtime(
            runtime_root,
            record,
            qualification,
            args.micromamba,
        )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
