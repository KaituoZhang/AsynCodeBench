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
import tarfile
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
SUPPORTED_TASKS = (
    "pr-hard:apache-tvm-20153",
    "pr-hard:apache-tvm-20107",
    "pr-hard:apache-tvm-20073",
    "pr-hard:apache-tvm-20018",
)
DEFAULT_TASK = SUPPORTED_TASKS[0]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build or validate the isolated PR-hard v0.4 runtime package"
    )
    parser.add_argument("--task-id", default=DEFAULT_TASK, choices=SUPPORTED_TASKS)
    parser.add_argument(
        "--runtime-root",
        type=Path,
        help="Destination (default: task-specific path under .cache/pr_hard_runtime/v0.4)",
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
    parser.add_argument(
        "--offline-mirror",
        type=Path,
        help="Local bare TVM mirror used instead of a network clone",
    )
    parser.add_argument(
        "--template-runtime",
        type=Path,
        help="Validated runtime whose identical frozen submodules/environment are reused",
    )
    parser.add_argument(
        "--template-task-id",
        default="pr-hard:apache-tvm-20153",
        choices=SUPPORTED_TASKS,
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


def run(
    *args: str | Path,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> str:
    command = [str(item) for item in args]
    print("+", " ".join(command), flush=True)
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            env=env,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
    except subprocess.CalledProcessError as error:
        if error.stdout and error.stdout.strip():
            print(error.stdout.rstrip(), flush=True)
        raise
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
    raw_status = git(source, "submodule", "status", "--recursive")
    stable_entries = []
    for line in raw_status.splitlines():
        state = line[:1]
        if state != " ":
            raise RuntimeError(
                "Recursive submodule is uninitialized or not at its pinned commit: "
                f"{line}"
            )
        fields = line[1:].split()
        if len(fields) < 2:
            raise RuntimeError(f"Malformed recursive submodule status: {line}")
        stable_entries.append(f"{fields[0]} {fields[1]}")
    manifest = "\n".join(stable_entries) + "\n"
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


def initialize_staging_repository(source: Path) -> None:
    """Give an exported source tree a temporary baseline for overlay auditing."""
    run("git", "init", "--initial-branch=master", source)
    git(source, "config", "user.email", "asyncodebench@example.com")
    git(source, "config", "user.name", "AsynCodeBench PR-hard")
    git(source, "add", "-f", "-A")
    commit_env = os.environ.copy()
    commit_env.update(
        {
            "GIT_AUTHOR_DATE": "1999-01-01T00:00:00Z",
            "GIT_COMMITTER_DATE": "1999-01-01T00:00:00Z",
        }
    )
    subprocess.run(
        ["git", "-C", str(source), "commit", "-m", "Offline pinned source export"],
        check=True,
        env=commit_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


def build_runtime_from_template(
    runtime_root: Path,
    record: dict[str, Any],
    qualification: dict[str, Any],
    mirror: Path,
    template_root: Path,
    template_record: dict[str, Any],
    template_qualification: dict[str, Any],
) -> dict[str, Any]:
    """Build offline when source and environment identity match a validated package."""
    if runtime_root.exists():
        raise RuntimeError(
            f"Runtime destination already exists: {runtime_root}. Use --check instead."
        )
    mirror = mirror.expanduser().resolve()
    template_root = template_root.expanduser().resolve()
    if not mirror.is_dir():
        raise RuntimeError(f"Offline mirror is missing: {mirror}")

    validate_runtime(template_root, template_record, template_qualification)
    for key in ("recursive_submodule_manifest_sha256", "tvm_ffi_sha"):
        if qualification["environment"][key] != template_qualification["environment"][key]:
            raise RuntimeError(f"Offline template differs in frozen environment field {key}")
    parent = run(
        "git", "--git-dir", mirror, "rev-parse", f"{record['gold_sha']}^"
    ).strip()
    if parent != record["base_sha"]:
        raise RuntimeError("Offline mirror does not confirm gold first-parent provenance")
    changed_thirdparty = run(
        "git",
        "--git-dir",
        mirror,
        "diff",
        "--name-only",
        record["base_sha"],
        template_record["base_sha"],
        "--",
        ".gitmodules",
        "3rdparty",
    ).strip()
    if changed_thirdparty:
        raise RuntimeError(
            "Offline template submodule tree differs from the candidate base: "
            f"{changed_thirdparty}"
        )

    runtime_root.parent.mkdir(parents=True, exist_ok=True)
    task_suffix = record["task_id"].rsplit("-", 1)[-1]
    with tempfile.TemporaryDirectory(
        prefix=f"pr-hard-{task_suffix}-offline-", dir=runtime_root.parent
    ) as temporary:
        temporary_root = Path(temporary)
        source = temporary_root / "tvm"
        source.mkdir()
        archive = temporary_root / "source.tar"
        run(
            "git",
            "--git-dir",
            mirror,
            "archive",
            "--format=tar",
            f"--output={archive}",
            record["base_sha"],
        )
        with tarfile.open(archive) as stream:
            stream.extractall(source, filter="data")

        submodule_lines = run(
            "git", "config", "-f", source / ".gitmodules", "--get-regexp", "path"
        ).splitlines()
        for line in submodule_lines:
            relative = line.split(maxsplit=1)[1]
            template_submodule = template_root / "seed" / relative
            destination = source / relative
            if not template_submodule.is_dir():
                raise RuntimeError(
                    f"Validated template is missing flattened submodule {relative}"
                )
            if destination.exists():
                shutil.rmtree(destination)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(template_submodule, destination, symlinks=True)

        initialize_staging_repository(source)
        apply_public_overlays(source, record)
        runtime_root.mkdir(mode=0o755)
        try:
            seed_commit = create_seed(source, runtime_root / "seed")
            environment = runtime_root / "env"
            environment.mkdir()
            run(
                "cp",
                "-a",
                "--reflink=auto",
                f"{template_root / 'env'}/.",
                environment,
            )
            manifest = {
                "schema_version": "pr-hard-runtime-package-v0.4",
                "task_id": record["task_id"],
                "base_sha": record["base_sha"],
                "seed_commit": seed_commit,
                "recursive_submodule_manifest_sha256": qualification["environment"][
                    "recursive_submodule_manifest_sha256"
                ],
                "public_overlays": [
                    {"path": item["path"], "sha256": item["sha256"]}
                    for item in overlay_specs(record)
                ],
                "conda_lock_sha256": sha256(CONDA_LOCK),
                "requirements_lock_sha256": sha256(REQUIREMENTS_LOCK),
                "offline_template_task_id": template_record["task_id"],
                "offline_template_environment_identity_verified": True,
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
    build_env = os.environ.copy()
    build_env["PATH"] = f"{environment / 'bin'}:{build_env.get('PATH', '')}"
    run(
        python,
        "-m",
        "pip",
        "install",
        "--requirement",
        REQUIREMENTS_LOCK,
        env=build_env,
    )
    run(
        python,
        "-m",
        "pip",
        "install",
        "--no-build-isolation",
        source / "3rdparty/tvm-ffi",
        env=build_env,
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
    task_suffix = record["task_id"].rsplit("-", 1)[-1]
    with tempfile.TemporaryDirectory(
        prefix=f"pr-hard-{task_suffix}-source-", dir=runtime_root.parent
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
        if args.offline_mirror or args.template_runtime:
            raise ValueError("--check does not accept offline build inputs")
        result = validate_runtime(runtime_root, record, qualification)
    elif args.offline_mirror or args.template_runtime:
        if not args.offline_mirror or not args.template_runtime:
            raise ValueError(
                "--offline-mirror and --template-runtime must be provided together"
            )
        template_record = candidate_record(args.template_task_id)
        template_qualification = qualification_record(template_record)
        result = build_runtime_from_template(
            runtime_root,
            record,
            qualification,
            args.offline_mirror,
            args.template_runtime,
            template_record,
            template_qualification,
        )
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
