"""Isolated task adapter for multi-agent PR-hard v0.4 candidates."""

from __future__ import annotations

import base64
import hashlib
import os
import re
import shlex
import shutil
import stat
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path

from .asyncodebench import AsynCodeBenchConfig, AsynCodeBenchTask
from .commit0 import Commit0Config, Commit0Task
from .task_images import image_record, immutable_image_reference


def validate_container_mount_root(path: Path) -> None:
    """Require a read-only runtime mount to be traversable by the container user."""
    if not path.is_dir():
        raise FileNotFoundError(f"Missing isolated PR-hard runtime input: {path}")
    mode = path.stat().st_mode
    required = stat.S_IROTH | stat.S_IXOTH
    if mode & required != required:
        raise PermissionError(
            "PR-hard runtime input is not readable by the container user: "
            f"{path} (mode={stat.S_IMODE(mode):04o}). "
            f"Run: chmod 0755 {shlex.quote(str(path))}"
        )


def build_python_wrapper(base_work_dir: str, environment_path: Path) -> str:
    """Build a launcher that imports Python from the active git worktree.

    Prefer the source-matched worktree build and use the immutable base C++
    build only when no local build exists.  The Python package must always come
    from the active worktree; otherwise role-local tests would exercise the
    integrated workspace instead of the specialist artifact.
    """
    return "\n".join(
        [
            "#!/bin/sh",
            'repo_root="$(git -C "$PWD" rev-parse --show-toplevel 2>/dev/null || pwd)"',
            'library_root="$repo_root/build/lib"',
            'if [ ! -d "$library_root" ]; then',
            f"  library_root={shlex.quote(base_work_dir)}/build/lib",
            "fi",
            'if [ ! -d "$library_root" ]; then',
            f"  library_root={shlex.quote(base_work_dir)}/build",
            "fi",
            'export PYTHONPATH="$repo_root/python${PYTHONPATH:+:$PYTHONPATH}"',
            'export TVM_LIBRARY_PATH="$library_root"',
            "export LD_LIBRARY_PATH=\"$library_root"
            "${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}\"",
            f'exec {shlex.quote(str(environment_path))}/bin/python "$@"',
            "",
        ]
    )


@dataclass
class PrHardConfig:
    task_id: str = "pr-hard:apache-tvm-19605"
    release: str = "pr-hard-v0.4"
    runtime_root: str = ""
    build_cache_root: str = ""
    base_image: str = "ubuntu:22.04"
    runtime_backend: str = "local"
    runtime_image: str = ""


class PrHardTask(AsynCodeBenchTask):
    """Run a PR-hard task from a sanitized, one-commit model-visible seed."""

    PUBLIC_NAMESPACE = "pr-hard"
    save_final_tarball = False
    manager_must_be_read_only = True
    deny_agent_network = True
    agent_network_policy = "agent-terminal-egress-v1"
    workspace_cpu_limit = 28
    build_parallel_jobs = 28
    worktree_build_command = (
        f"cmake --build build --parallel {build_parallel_jobs}"
    )
    container_build_cache_root = Path(
        "/workspace/.asyncodebench-pr-hard-build-cache"
    )

    def __init__(self, config: PrHardConfig):
        source, candidate_name = str(config.task_id).split(":", 1)
        repository, separator, pr_number = candidate_name.rpartition("-")
        if (
            source != self.PUBLIC_NAMESPACE
            or repository != "apache-tvm"
            or not separator
            or not pr_number.isdigit()
        ):
            raise ValueError(
                "This adapter currently supports pr-hard:apache-tvm-<number>"
            )
        self.pr_hard_config = config
        self.manager_must_be_read_only = True
        self.asyncodebench_config = AsynCodeBenchConfig(
            task_id=config.task_id,
            release=config.release,
            enforce_official=False,
        )
        self.repository_name = f"apache-tvm-{pr_number}"
        self.public_task_id = config.task_id
        self.release_root = (
            self._repo_root() / "manifests" / "candidates" / "pr_hard_v0.4"
        )
        normalized = f"apache_tvm_{pr_number}"
        self.manifest_paths = {
            "task": self.release_root / "tasks" / f"{normalized}.json",
            "scenario": self.release_root / "scenarios" / f"{normalized}.json",
            "metrics": self.release_root
            / "metrics"
            / f"{normalized}_async_metrics.json",
            "quality": self.release_root / "qualification" / f"{normalized}.json",
        }
        self.task_manifest = self._read_json(self.manifest_paths["task"])
        self.scenario_manifest = self._read_json(self.manifest_paths["scenario"])
        self.metrics_manifest = self._read_json(self.manifest_paths["metrics"])
        self.quality_manifest = self._read_json(self.manifest_paths["quality"])
        self.candidate_record = self._load_candidate_record(config.task_id)
        self.official_manifest = {"official_tasks": []}
        self.active_protocol = "single"
        self.last_assignment_rejections = []

        Commit0Task.__init__(
            self,
            Commit0Config(repo_name=self.repository_name),
        )
        overlays = [
            self.candidate_record["public_test_overlay"],
            *self.candidate_record.get("supplemental_public_test_overlays", []),
        ]
        self.curated_task = {
            "task_id": config.task_id,
            "repository": self.candidate_record["repository"],
            "base_ref": self.candidate_record["base_sha"],
            "base_sha": self.candidate_record["base_sha"],
            "overlays": overlays,
        }
        self.runtime_backend = str(config.runtime_backend).strip().lower()
        if self.runtime_backend not in {"local", "container"}:
            raise ValueError("runtime_backend must be 'local' or 'container'")
        self.image_record = None
        self.runtime_image = None
        if self.runtime_backend == "container":
            self.image_record = image_record(self._repo_root(), config.task_id)
            self.runtime_image = str(
                config.runtime_image
            ).strip() or immutable_image_reference(self.image_record)
            self.runtime_root = Path(
                self.image_record.get("runtime_root", "/opt/asyncodebench/runtime")
            )
        else:
            self.runtime_root = Path(
                config.runtime_root
                or self._repo_root()
                / ".cache"
                / "pr_hard_runtime"
                / "v0.4"
                / self.repository_name
            ).resolve()
        self.seed_path = self.runtime_root / "seed"
        self.environment_path = self.runtime_root / "env"
        self.build_cache_root = (
            Path(
                config.build_cache_root
                or os.getenv("ASYNCODEBENCH_PR_HARD_BUILD_CACHE_ROOT", "")
                or self._repo_root() / ".cache" / "pr_hard_builds" / "v0.4"
            )
            .expanduser()
            .resolve()
        )
        self.build_cache_run_root = None
        self._validate_runtime_inputs()

    def _load_candidate_record(self, task_id):
        registry = self._read_json(
            self._repo_root() / "configs" / "tasks" / "pr_hard_candidates.v0.4.json"
        )
        for candidate in registry.get("records", []):
            if candidate.get("task_id") == task_id:
                return candidate
        raise ValueError(f"Unknown PR-hard candidate: {task_id}")

    def _validate_runtime_inputs(self):
        if self.runtime_backend == "container":
            if not self.runtime_image:
                raise RuntimeError("Container runtime requires an image reference")
            return
        for path in (self.seed_path, self.environment_path):
            validate_container_mount_root(path)

    @property
    def task_id(self):
        return self.public_task_id

    @property
    def source_task_id(self):
        return self.public_task_id

    def get_work_dir(self):
        return f"/workspace/{self.repository_name}_repo"

    def get_workspace_config(self):
        build_cache_run_root = self._ensure_build_cache_run_root()
        base_image = self.runtime_image or self.pr_hard_config.base_image
        volumes = [
            f"{build_cache_run_root}:{self.container_build_cache_root}:rw",
        ]
        if self.runtime_backend == "local":
            volumes[:0] = [
                f"{self.seed_path}:{self.seed_path}:ro",
                f"{self.environment_path}:{self.environment_path}:ro",
            ]
        return {
            "base_image": base_image,
            "target": "source-minimal",
            "cpu_limit": self.workspace_cpu_limit,
            "volumes": volumes,
        }

    def runtime_distribution(self):
        if self.runtime_backend == "local":
            return {
                "backend": "local_reconstruction",
                "runtime_root": str(self.runtime_root),
                "official_image": None,
            }
        return {
            "backend": "container_image",
            "runtime_root": str(self.runtime_root),
            "official_image": self.runtime_image,
            "registry_task_id": self.image_record["task_id"],
            "digest_pinned": "@sha256:" in str(self.runtime_image),
        }

    def _ensure_build_cache_run_root(self) -> Path:
        """Allocate one host-backed build-cache directory for this container run."""
        if self.build_cache_run_root is not None:
            return self.build_cache_run_root
        task_root = self.build_cache_root / self.repository_name
        task_root.mkdir(parents=True, exist_ok=True)
        run_root = task_root / f"{os.getpid()}-{uuid.uuid4().hex}"
        run_root.mkdir(mode=0o777)
        run_root.chmod(0o777)
        self.build_cache_run_root = run_root
        print(
            "[PR-hard] Host-backed worktree build cache: "
            f"{run_root} -> {self.container_build_cache_root}"
        )
        return run_root

    def _build_cache_target(self, workspace_path) -> Path:
        raw_path = str(workspace_path)
        basename = Path(raw_path).name or "workspace"
        safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "-", basename).strip("-.")
        digest = hashlib.sha256(raw_path.encode("utf-8")).hexdigest()[:12]
        return self.container_build_cache_root / f"{safe_name or 'workspace'}-{digest}"

    def _attach_build_cache_command(self, workspace_path) -> str:
        """Return a shell fragment that gives one source tree its own build dir."""
        target = shlex.quote(str(self._build_cache_target(workspace_path)))
        return (
            f"mkdir -p {target} && "
            "if [ ! -L build ] || "
            f'[ "$(readlink -f build 2>/dev/null || true)" != {target} ]; then '
            "rm -rf build && "
            f"ln -s {target} build; "
            "fi"
        )

    def cleanup_build_cache(self) -> bool:
        """Remove transient host build products, including container-owned files."""
        run_root = self.build_cache_run_root
        if run_root is None or not run_root.exists():
            return True
        if os.getenv("ASYNCODEBENCH_PR_HARD_PRESERVE_BUILD_CACHE") == "1":
            print(f"[PR-hard] Preserving build cache: {run_root}")
            return True

        try:
            shutil.rmtree(run_root)
        except OSError:
            try:
                cleanup = subprocess.run(
                    [
                        "docker",
                        "run",
                        "--rm",
                        "-v",
                        f"{run_root}:/asyncodebench-build-cache",
                        "--entrypoint",
                        "/bin/sh",
                        self.runtime_image or self.pr_hard_config.base_image,
                        "-c",
                        "find /asyncodebench-build-cache -mindepth 1 -delete",
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                )
            except OSError as exc:
                print(
                    "[PR-hard] Warning: could not start Docker build-cache "
                    f"cleanup for {run_root}: {exc}"
                )
                return False
            if cleanup.returncode != 0:
                print(
                    "[PR-hard] Warning: could not clean host build cache "
                    f"{run_root}: {cleanup.stderr or cleanup.stdout}"
                )
                return False
            try:
                run_root.rmdir()
            except FileNotFoundError:
                pass
            except OSError as exc:
                print(
                    "[PR-hard] Warning: build cache is empty but its run directory "
                    f"could not be removed: {run_root}: {exc}"
                )
                return False

        self.build_cache_run_root = None
        print(f"[PR-hard] Removed transient host build cache: {run_root}")
        return True

    def load_task_data(self):
        self.task_data = {
            "repo": self.candidate_record["repository"],
            "repo_name": self.repository_name,
            "task_id": self.task_id,
            "source": "pr_hard_v0.4_sanitized_snapshot",
            "base_ref": self.candidate_record["base_sha"],
            "base_sha": self.candidate_record["base_sha"],
            "overlays": self.curated_task["overlays"],
            "test": {
                "test_cmd": "python -m pytest -q",
                "test_dir": self.task_manifest["test_targets"],
            },
        }
        return self.task_data

    def _resolve_evaluator(self):
        command = self.task_manifest["evaluator_command"]
        test_cmd, targets = self._split_pytest_command(command)
        return test_cmd, targets, "pr_hard_v0.4_manifest"

    def setup_workspace(self, workspace):
        if self.task_data is None:
            raise RuntimeError("Call load_task_data() before setup_workspace()")
        work_dir = self.get_work_dir()
        seed = shlex.quote(str(self.seed_path))
        env = shlex.quote(str(self.environment_path))
        quoted_work = shlex.quote(work_dir)

        materialize = workspace.execute_command(
            f"test ! -e {quoted_work} && cp -a {seed} {quoted_work} && "
            f"cd {quoted_work} && git checkout -b openhands && "
            "git config user.email asyncodebench@example.com && "
            "git config user.name 'AsynCodeBench PR-hard' && "
            'test "$(git rev-list --all --count)" = 1 && '
            'test -z "$(git remote)"',
            timeout=300,
        )
        if materialize.exit_code != 0:
            raise RuntimeError(
                "Failed to materialize sanitized PR-hard seed: "
                f"{materialize.stderr or materialize.stdout}"
            )

        python_wrapper = build_python_wrapper(work_dir, self.environment_path)
        encoded_wrapper = base64.b64encode(python_wrapper.encode("utf-8")).decode(
            "ascii"
        )
        install_tools = workspace.execute_command(
            f"printf %s {shlex.quote(encoded_wrapper)} | base64 -d | "
            "sudo tee /usr/local/bin/python >/dev/null && "
            "sudo chmod 0755 /usr/local/bin/python && "
            + f"sudo ln -sf {env}/bin/cmake /usr/local/bin/cmake && "
            + f"sudo ln -sf {env}/bin/ninja /usr/local/bin/ninja && "
            + f"sudo ln -sf {env}/bin/llvm-config /usr/local/bin/llvm-config",
            timeout=120,
        )
        if install_tools.exit_code != 0:
            raise RuntimeError(
                "Failed to expose isolated PR-hard toolchain: "
                f"{install_tools.stderr or install_tools.stdout}"
            )

        self._capture_canonical_test_ref(workspace, work_dir)
        self._install_transient_test_artifact_excludes(workspace, work_dir)
        workspace.execute_command(
            f"cd {quoted_work} && "
            "exclude_file=$(git rev-parse --git-path info/exclude) && "
            "printf '\nbuild\nbuild/\n3rdparty/tvm-ffi/build/\n' >> \"$exclude_file\"",
            timeout=60,
        )

        attach_build_cache = self._attach_build_cache_command(work_dir)
        configure = workspace.execute_command(
            f"cd {quoted_work} && {attach_build_cache} && "
            "cmake -S . -B build -G Ninja "
            "-DCMAKE_BUILD_TYPE=RelWithDebInfo "
            "-DUSE_LLVM=llvm-config -DUSE_CUDA=OFF -DUSE_GTEST=OFF",
            timeout=600,
        )
        if configure.exit_code != 0:
            raise RuntimeError(
                f"PR-hard TVM configure failed: {configure.stderr or configure.stdout}"
            )
        build = workspace.execute_command(
            f"cd {quoted_work} && cmake --build build "
            f"--parallel {self.build_parallel_jobs}",
            timeout=1800,
        )
        if build.exit_code != 0:
            raise RuntimeError(
                f"PR-hard TVM cold build failed: {build.stderr or build.stdout}"
            )
        status = workspace.execute_command(
            f"cd {quoted_work} && git status --porcelain", timeout=60
        )
        if status.exit_code != 0 or status.stdout.strip():
            raise RuntimeError(
                "PR-hard workspace is not clean before model execution:\n"
                f"{status.stdout}{status.stderr}"
            )
        print("[PR-hard] Sanitized one-commit workspace built and verified clean")

    def validate_worktree_runtime(self, workspace, worktree_path):
        """Prove that ``python`` resolves TVM from the requested worktree."""
        quoted_worktree = shlex.quote(str(worktree_path))
        script = (
            "import pathlib, tvm; "
            "root=pathlib.Path.cwd().resolve(); "
            "loaded=pathlib.Path(tvm.__file__).resolve(); "
            "expected=(root/'python').resolve(); "
            "assert loaded.is_relative_to(expected), "
            "f'loaded {loaded}, expected beneath {expected}'; "
            "print(loaded)"
        )
        result = workspace.execute_command(
            f"cd {quoted_worktree} && python -c {shlex.quote(script)}",
            timeout=120,
        )
        if result.exit_code != 0:
            raise RuntimeError(
                "PR-hard worktree runtime isolation check failed for "
                f"{worktree_path}: {result.stderr or result.stdout}"
            )

    def refresh_source_build(self, workspace, workspace_path):
        """Configure when needed and build TVM against this exact source tree.

        A PR-hard worktree may contain C++ and Python changes that must be
        evaluated together.  Falling back to another worktree's ``build/lib``
        can otherwise load a stale object registry and turn a model artifact
        into a harness-level import failure.
        """
        quoted_worktree = shlex.quote(str(workspace_path))
        configure_timeout = max(
            60,
            int(os.getenv("ASYNCODEBENCH_PR_HARD_CONFIGURE_TIMEOUT_SECONDS", "600")),
        )
        build_timeout = max(
            60,
            int(os.getenv("ASYNCODEBENCH_PR_HARD_BUILD_TIMEOUT_SECONDS", "1800")),
        )
        attach_build_cache = self._attach_build_cache_command(workspace_path)
        configure = workspace.execute_command(
            f"cd {quoted_worktree} && "
            f"{attach_build_cache} && "
            "if [ ! -f build/CMakeCache.txt ]; then "
            "cmake -S . -B build -G Ninja "
            "-DCMAKE_BUILD_TYPE=RelWithDebInfo "
            "-DUSE_LLVM=llvm-config -DUSE_CUDA=OFF -DUSE_GTEST=OFF; "
            "fi",
            timeout=configure_timeout,
        )
        if configure.exit_code != 0:
            return {
                "status": "configure_failed",
                "exit_code": configure.exit_code,
                "workspace_path": str(workspace_path),
                "output_excerpt": (configure.stderr or configure.stdout or "")[-4000:],
            }
        build = workspace.execute_command(
            f"cd {quoted_worktree} && {self.worktree_build_command}",
            timeout=build_timeout,
        )
        return {
            "status": "passed" if build.exit_code == 0 else "build_failed",
            "exit_code": build.exit_code,
            "workspace_path": str(workspace_path),
            "output_excerpt": (build.stderr or build.stdout or "")[-4000:],
        }

    def prepare_worktree_runtime(self, workspace, worktree_path):
        """Materialize a worktree-local build before a specialist starts."""
        build = self.refresh_source_build(workspace, worktree_path)
        if build["status"] != "passed":
            raise RuntimeError(
                "PR-hard worktree source build failed for "
                f"{worktree_path} ({build['status']}):\n{build['output_excerpt']}"
            )
        self.validate_worktree_runtime(workspace, worktree_path)
        return build

    def evaluate(self, workspace):
        work_dir = self.get_work_dir()
        if self.active_protocol != "single":
            status = workspace.execute_command(
                f"cd {shlex.quote(work_dir)} && git status --porcelain",
                timeout=60,
            )
            if status.exit_code != 0 or status.stdout.strip():
                raise RuntimeError(
                    "PR-hard integrated workspace is dirty before final evaluation; "
                    "refusing to commit unreviewed direct writes:\n"
                    f"{status.stdout}{status.stderr}"
                )
        build = workspace.execute_command(
            f"cd {shlex.quote(work_dir)} && cmake --build build "
            f"--parallel {self.build_parallel_jobs}",
            timeout=1800,
        )
        if build.exit_code != 0:
            print("[PR-hard] Incremental build failed; evaluator will record failures")
        return super().evaluate(workspace)
