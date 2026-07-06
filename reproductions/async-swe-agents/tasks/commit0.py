"""
python -m tasks.commit0
"""
import base64
import hashlib
import json
import os
import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .base import TaskModule


@dataclass
class Commit0Config:
    repo_name: str = "minitorch"
    base_branch: str = ""
    docker_image_prefix: str = "docker.io/wentingzhao/"
    dataset_path: str = "data/commit0/commit0_combined"
    curated_config_path: str = ""


class Commit0Task(TaskModule):
    def __init__(self, config):
        self.config = config
        self.task_data = None
        self.curated_task = self._load_curated_task_record()

    def get_docker_image(self):
        prefix = self.config.docker_image_prefix.rstrip("/")
        return f"{prefix}/{self.config.repo_name}:v0".lower()

    def get_work_dir(self):
        return f"/workspace/{self.config.repo_name}_repo"

    def get_workspace_config(self):
        return {
            "base_image": self.get_docker_image(),
            "target": "source-minimal",
        }

    def load_task_data(self):
        curated_data = self._curated_task_data()
        if curated_data is not None:
            self.task_data = curated_data
            print(
                "[AsyncCodeBench] Loaded curated v0.3 task record for "
                f"{self.config.repo_name}"
            )
            return self.task_data

        from datasets import load_from_disk

        dataset = load_from_disk(self.config.dataset_path)
        if hasattr(dataset, "to_pandas"):
            df = dataset.to_pandas()
        elif hasattr(dataset, "keys"):
            split_names = list(dataset.keys())
            preferred_splits = ("test", "train", "validation", "valid")
            split_name = next(
                (name for name in preferred_splits if name in dataset),
                split_names[0] if split_names else None,
            )
            if split_name is None:
                raise ValueError(
                    f"No dataset split found at {self.config.dataset_path}"
                )
            print(
                f"[Commit0] Loaded DatasetDict split '{split_name}' "
                f"from {self.config.dataset_path}"
            )
            df = dataset[split_name].to_pandas()
        else:
            raise TypeError(
                f"Unsupported dataset object loaded from {self.config.dataset_path}: "
                f"{type(dataset)!r}"
            )

        if "repo" not in df.columns:
            raise ValueError(
                f"Commit0 dataset at {self.config.dataset_path} does not contain "
                "a 'repo' column"
            )

        repo_data = df[
            df["repo"].astype(str).str.contains(
                self.config.repo_name, case=False, na=False
            )
        ]
        if repo_data.empty:
            raise ValueError(
                f"Repository '{self.config.repo_name}' not found in dataset "
                f"at {self.config.dataset_path}"
            )
        self.task_data = repo_data.iloc[0].to_dict()
        return self.task_data

    def _curated_task_data(self):
        if not self.curated_task or self._curated_task_source_disabled():
            return None

        repository = str(self.curated_task.get("repository", "")).strip()
        if not repository:
            return None

        manifest_command = self._manifest_evaluator_command()
        if manifest_command:
            test_cmd, test_targets = manifest_command
        else:
            test_cmd = "python -m pytest"
            test_targets = self._manifest_evaluator_targets() or ["tests/"]
        return {
            "repo": self._curated_repo_url(repository),
            "repo_name": repository,
            "task_id": self.curated_task.get("task_id", f"commit0:{repository}"),
            "source": "asynccodebench_curated_v0.3",
            "base_ref": self.curated_task.get("base_ref"),
            "base_sha": self.curated_task.get("base_sha"),
            "overlays": self.curated_task.get("overlays", []),
            "test": {
                "test_cmd": test_cmd,
                "test_dir": test_targets,
            },
        }

    @staticmethod
    def _curated_repo_url(repository):
        if "/" in repository:
            return repository
        return f"commit-0/{repository}"

    @staticmethod
    def _curated_task_source_disabled():
        raw_value = os.getenv("ASYNCCODEBENCH_DISABLE_CURATED_TASK_SOURCE", "")
        return raw_value.strip().lower() in {"1", "true", "yes", "on"}

    def setup_workspace(self, workspace):
        if self.task_data is None:
            raise RuntimeError("Call load_task_data() before setup_workspace()")

        work_dir = self.get_work_dir()
        repo = self.task_data["repo"]
        repo_url = f"https://github.com/{repo}.git"

        # Step 1: Clone Repository
        print("\n" + "-" * 60)
        print("Step 1: Clone Repository")
        print("-" * 60)
        base_ref = self._effective_base_ref()
        clone_branch = self._clone_branch_name(base_ref)
        print(f"[Commit0] Cloning {repo} at {base_ref}...")
        self._clone_repository(workspace, repo_url, clone_branch, work_dir)

        # Create a working branch (matches official OpenHands benchmark)
        branch_cmd = f"cd {work_dir} && git checkout -b openhands"
        result = workspace.execute_command(branch_cmd, timeout=600)
        if result.exit_code != 0:
            raise RuntimeError(f"Failed to create branch: {result.stderr}")

        self._verify_curated_base(workspace, work_dir)
        self._apply_curated_overlays(workspace, work_dir)

        # Step 2: Setup Repository
        print("\n" + "-" * 60)
        print("Step 2: Setup Repository")
        print("-" * 60)
        print(f"[Commit0] Installing {self.config.repo_name} in dev mode...")
        workspace.execute_command(
            f"python -m pip uninstall -y {self.config.repo_name} 2>&1 | tail -3",
            timeout=60,
        )
        result = workspace.execute_command(
            f"cd {work_dir} && python -m pip install -e . 2>&1", timeout=300
        )
        if result.exit_code != 0:
            print(f"[Commit0] Warning: pip install -e . failed: {result.stderr}")

        # Verify package import
        verify_cmd = (
            f"cd {work_dir} && "
            f"python -c 'import {self.config.repo_name}; "
            f'print("{self.config.repo_name} imported successfully")\''
        )
        verify_result = workspace.execute_command(verify_cmd, timeout=30)
        if verify_result.exit_code == 0:
            print(f"[Commit0] Package verification: {verify_result.stdout.strip()}")
        else:
            print("[Commit0] Warning: Package import verification failed")

        # Install commit0 + pytest plugins
        print("[Commit0] Installing commit0 and pytest plugins...")
        uv = workspace.execute_command(
            f"cd {work_dir} && /root/.cargo/bin/uv pip install commit0 2>&1 | tail -5",
            timeout=300,
        )
        if uv.exit_code != 0:
            workspace.execute_command(
                f"cd {work_dir} && python -m pip install commit0 2>&1 | tail -5",
                timeout=300,
            )
        workspace.execute_command(
            f"cd {work_dir} && python -m pip install pytest-json-report pytest-cov 2>&1 | tail -5",
            timeout=300,
        )
        self._install_curated_python_dependencies(workspace, work_dir)
        print("[Commit0] Workspace setup complete")

    def _clone_repository(self, workspace, repo_url, clone_branch, work_dir):
        target_dir = f"{self.config.repo_name}_repo"
        clone_cmd = (
            f"cd /workspace && "
            f"git clone --depth 1 -b {shlex.quote(clone_branch)} "
            f"{shlex.quote(repo_url)} {shlex.quote(target_dir)}"
        )
        result = workspace.execute_command(clone_cmd, timeout=600)
        if result.exit_code == 0:
            return

        expected_sha = (
            str((self.curated_task or {}).get("base_sha", "")).strip()
            if self.curated_task
            else ""
        )
        if not expected_sha:
            raise RuntimeError(f"Failed to clone repo: {result.stderr}")

        print(
            "[Commit0] Branch clone failed; falling back to default branch "
            f"and curated SHA {expected_sha}"
        )
        workspace.execute_command(f"rm -rf /workspace/{shlex.quote(target_dir)}", timeout=60)
        fallback = workspace.execute_command(
            f"cd /workspace && git clone --depth 1 "
            f"{shlex.quote(repo_url)} {shlex.quote(target_dir)}",
            timeout=600,
        )
        if fallback.exit_code != 0:
            raise RuntimeError(
                "Failed to clone repo by branch and by default branch:\n"
                f"branch clone stderr:\n{result.stderr}\n"
                f"default clone stderr:\n{fallback.stderr}"
            )

        head = workspace.execute_command(
            f"cd {work_dir} && git rev-parse HEAD",
            timeout=60,
        )
        if head.exit_code == 0 and head.stdout.strip() == expected_sha:
            print("[Commit0] Default branch matches curated base SHA")
            return

        checkout = workspace.execute_command(
            f"cd {work_dir} && "
            f"git fetch --depth 1 origin {shlex.quote(expected_sha)} && "
            f"git checkout --detach {shlex.quote(expected_sha)}",
            timeout=600,
        )
        if checkout.exit_code != 0:
            raise RuntimeError(
                "Failed to materialize curated base SHA after branch fallback:\n"
                f"expected SHA: {expected_sha}\n"
                f"default HEAD: {head.stdout.strip() if head.exit_code == 0 else head.stderr.strip()}\n"
                f"fetch/checkout stderr:\n{checkout.stderr}"
            )
        print("[Commit0] Checked out curated base SHA after fallback clone")

    def _load_curated_task_record(self):
        if self._curated_config_disabled():
            return None

        config_path = self._curated_config_path()
        if not config_path.exists():
            return None

        try:
            payload = json.loads(config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"[Commit0] Warning: could not read curated task config: {exc}")
            return None

        repo_name = self.config.repo_name
        normalized_repo = repo_name.replace("-", "_")
        for record in payload.get("tasks", []):
            repository = str(record.get("repository", ""))
            task_id = str(record.get("task_id", ""))
            if repository == repo_name or repository == normalized_repo:
                return record
            if task_id in {f"commit0:{repo_name}", f"commit0:{normalized_repo}"}:
                return record
        return None

    def _curated_config_path(self):
        raw_path = (
            self.config.curated_config_path
            or os.getenv("ASYNCCODEBENCH_CURATED_TASKS_CONFIG", "")
        )
        if raw_path:
            path = Path(raw_path)
            return path if path.is_absolute() else self._repo_root() / path
        return (
            self._repo_root()
            / "configs"
            / "tasks"
            / "commit0_curated_tasks.v0.3.json"
        )

    def _effective_base_ref(self):
        if self.config.base_branch:
            return self.config.base_branch
        if self.curated_task:
            return str(self.curated_task.get("base_ref", "") or "commit0_combined")
        return "commit0_combined"

    @staticmethod
    def _clone_branch_name(base_ref):
        return str(base_ref).removeprefix("origin/")

    def _verify_curated_base(self, workspace, work_dir):
        if not self.curated_task:
            return

        expected_sha = str(self.curated_task.get("base_sha", "")).strip()
        if not expected_sha:
            return

        result = workspace.execute_command(
            f"cd {work_dir} && git rev-parse HEAD",
            timeout=60,
        )
        actual_sha = result.stdout.strip() if result.exit_code == 0 else ""
        if actual_sha != expected_sha:
            raise RuntimeError(
                "AsyncCodeBench curated base SHA mismatch for "
                f"{self.config.repo_name}: expected {expected_sha}, found "
                f"{actual_sha or result.stderr.strip()}"
            )
        print(f"[Commit0] Verified curated base SHA: {actual_sha}")

    def _apply_curated_overlays(self, workspace, work_dir):
        if not self.curated_task:
            return

        overlays = self.curated_task.get("overlays", []) or []
        if not overlays:
            print("[Commit0] No AsyncCodeBench bootstrap overlays configured")
            return

        print(f"[Commit0] Applying {len(overlays)} AsyncCodeBench bootstrap overlays")
        for index, overlay in enumerate(overlays, start=1):
            overlay_path = self._resolve_overlay_path(str(overlay["path"]))
            self._verify_overlay_checksum(overlay_path, str(overlay["sha256"]))
            remote_path = f"/tmp/asynccodebench_overlay_{index:03d}.patch"
            self._write_overlay_to_workspace(workspace, overlay_path, remote_path)

            check = workspace.execute_command(
                f"cd {work_dir} && git apply --check {remote_path}",
                timeout=120,
            )
            if check.exit_code != 0:
                raise RuntimeError(
                    f"AsyncCodeBench overlay failed --check: {overlay_path}\n"
                    f"{check.stderr}"
                )

            apply = workspace.execute_command(
                f"cd {work_dir} && git apply {remote_path}",
                timeout=120,
            )
            if apply.exit_code != 0:
                raise RuntimeError(
                    f"AsyncCodeBench overlay failed to apply: {overlay_path}\n"
                    f"{apply.stderr}"
                )
            print(f"[Commit0] Applied overlay: {overlay_path}")

        workspace.execute_command(
            f"cd {work_dir} && "
            'git config user.email "asynccodebench@example.com" && '
            'git config user.name "AsyncCodeBench Bootstrap" && '
            "git add -f . && "
            'git commit -m "Apply AsyncCodeBench bootstrap overlays"',
            timeout=120,
        )

    def _resolve_overlay_path(self, raw_path):
        path = Path(raw_path)
        return path if path.is_absolute() else self._repo_root() / path

    @staticmethod
    def _verify_overlay_checksum(path, expected_sha256):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != expected_sha256:
            raise RuntimeError(
                f"AsyncCodeBench overlay checksum mismatch for {path}: "
                f"expected {expected_sha256}, found {digest}"
            )

    @staticmethod
    def _write_overlay_to_workspace(workspace, overlay_path, remote_path):
        encoded = base64.b64encode(overlay_path.read_bytes()).decode("ascii")
        script = (
            "import base64, pathlib\n"
            f"pathlib.Path({remote_path!r}).write_bytes("
            f"base64.b64decode({encoded!r}))\n"
        )
        result = workspace.execute_command(
            "python - <<'PY'\n" + script + "PY",
            timeout=120,
        )
        if result.exit_code != 0:
            raise RuntimeError(
                f"Failed to copy overlay into workspace: {overlay_path}\n"
                f"{result.stderr}"
            )

    @staticmethod
    def _curated_config_disabled():
        raw_value = os.getenv("ASYNCCODEBENCH_DISABLE_CURATED_TASK_CONFIG", "")
        return raw_value.strip().lower() in {"1", "true", "yes", "on"}

    def _install_curated_python_dependencies(self, workspace, work_dir):
        if not self.curated_task:
            return

        raw_dependencies = self.curated_task.get("python_dependencies", []) or []
        dependencies = []
        for dependency in raw_dependencies:
            dependency = str(dependency).strip()
            if dependency:
                dependencies.append(dependency)

        if not dependencies:
            return

        dependency_args = " ".join(shlex.quote(dep) for dep in dependencies)
        print(
            "[Commit0] Installing AsyncCodeBench curated Python dependencies: "
            f"{dependency_args}"
        )
        result = workspace.execute_command(
            f"cd {work_dir} && python -m pip install {dependency_args} 2>&1 | tail -20",
            timeout=300,
        )
        if result.exit_code != 0:
            raise RuntimeError(
                "Failed to install AsyncCodeBench curated Python dependencies "
                f"for {self.config.repo_name}: {result.stderr or result.stdout}"
            )

    def _clean_transient_test_artifacts(self, workspace, work_dir):
        if self.config.repo_name != "cookiecutter":
            return

        # Some cookiecutter tests create tests/test-hooks in the repository root.
        # It is a test fixture directory, not a model patch, and can poison later
        # hook tests if it survives subagent probe runs or merges.
        workspace.execute_command(
            f"cd {work_dir} && "
            "git rm -r -f --ignore-unmatch tests/test-hooks >/dev/null 2>&1 || true && "
            "rm -rf tests/test-hooks",
            timeout=60,
        )

    def evaluate(self, workspace):
        if self.task_data is None:
            raise RuntimeError("Call load_task_data() before evaluate()")

        work_dir = self.get_work_dir()

        # Commit any remaining changes
        print("[Commit0] Committing any remaining changes...")
        self._clean_transient_test_artifacts(workspace, work_dir)
        workspace.execute_command(f"cd {work_dir} && git add .", timeout=600)
        workspace.execute_command(
            f"cd {work_dir} && "
            'git config --global user.email "evaluation@openhands.dev" && '
            'git config --global user.name "OpenHands Evaluation" && '
            'git commit -m "final changes before test" || true',
            timeout=600,
        )

        test_cmd, test_targets, evaluator_source = self._resolve_evaluator()
        test_target_args = " ".join(shlex.quote(str(target)) for target in test_targets)

        eval_timeout = self._final_pytest_timeout_seconds()
        self._clean_transient_test_artifacts(workspace, work_dir)
        full_cmd = (
            f"cd {work_dir} && "
            f"export PYTHONPATH={work_dir}/src:{work_dir}:$PYTHONPATH && "
            f"timeout {eval_timeout}s {test_cmd} "
            f"--json-report --json-report-file=report.json "
            f"--continue-on-collection-errors "
            f"{test_target_args} > test_output.txt 2>&1"
        )
        print(
            f"[Commit0] Running: {test_cmd} {test_target_args} "
            f"(source={evaluator_source}, timeout={eval_timeout}s)"
        )
        pytest_result = workspace.execute_command(full_cmd, timeout=eval_timeout + 60)

        # Read results
        output_result = workspace.execute_command(
            f"cat {work_dir}/test_output.txt", timeout=60
        )
        test_output = output_result.stdout if output_result.exit_code == 0 else ""

        report_result = workspace.execute_command(
            f"cat {work_dir}/report.json", timeout=60
        )
        report_json = report_result.stdout if report_result.exit_code == 0 else "{}"

        timed_out = str(pytest_result.exit_code) == "124"
        if timed_out:
            timeout_message = (
                f"\n[AsyncCodeBench] Final pytest timed out after "
                f"{eval_timeout} seconds.\n"
            )
            if timeout_message not in test_output:
                test_output += timeout_message

        passed = failed = error = 0
        try:
            report_data = json.loads(report_json)
            summary = report_data.get("summary", {})
            passed = summary.get("passed", 0)
            failed = summary.get("failed", 0)
            error = summary.get("error", 0)
            self._annotate_report_evaluator(
                report_data,
                test_cmd=test_cmd,
                test_targets=test_targets,
                evaluator_source=evaluator_source,
                timeout_seconds=eval_timeout,
                timed_out=timed_out,
            )
            report_json = json.dumps(report_data, indent=2)
        except (json.JSONDecodeError, Exception) as e:
            print(f"[Commit0] Warning: could not parse report.json: {e}")
            report_data = {}

        if timed_out and not report_data.get("summary"):
            error = 1
            report_data = {
                "created": 0,
                "duration": eval_timeout,
                "exitcode": 124,
                "root": work_dir,
                "summary": {
                    "passed": 0,
                    "failed": 0,
                    "error": 1,
                    "total": 1,
                },
                "collectors": [],
                "tests": [],
                "warnings": [],
                "asynccodebench": {
                    "final_pytest_timeout_seconds": eval_timeout,
                    "final_evaluator_source": evaluator_source,
                    "final_test_cmd": test_cmd,
                    "final_test_targets": test_targets,
                    "timed_out": True,
                },
            }
            report_json = json.dumps(report_data, indent=2)

        print(f"[Commit0] Pytest results: {passed} passed, {failed} failed, {error} error")

        return {
            "exit_code": str(pytest_result.exit_code),
            "test_output": test_output,
            "report_json": report_json,
            "passed": passed,
            "failed": failed,
            "error": error,
            "evaluator_source": evaluator_source,
            "test_cmd": test_cmd,
            "test_targets": test_targets,
        }

    def _resolve_evaluator(self):
        test_cmd, dataset_targets = self._dataset_evaluator()
        manifest_command = self._manifest_evaluator_command()
        if manifest_command:
            manifest_test_cmd, manifest_targets = manifest_command
            return manifest_test_cmd, manifest_targets, "asynccodebench_manifest"

        manifest_targets = self._manifest_evaluator_targets()
        if manifest_targets:
            return test_cmd, manifest_targets, "asynccodebench_manifest"
        return test_cmd, dataset_targets, "commit0_dataset"

    def _dataset_evaluator(self):
        test_info = self.task_data.get("test", {}) if self.task_data else {}
        test_cmd = test_info.get(
            "test_cmd", self.task_data.get("test_cmd", "pytest")
        )
        test_dir = test_info.get(
            "test_dir", self.task_data.get("test_dir", "tests/")
        )
        if test_cmd.strip().startswith("pytest"):
            test_cmd = "python -m " + test_cmd.strip()
        return test_cmd, self._coerce_test_targets(test_dir)

    def _manifest_evaluator_targets(self):
        if self._manifest_evaluator_disabled():
            return None

        scenario_path = self._scenario_manifest_path()
        if not scenario_path.exists():
            return None

        try:
            payload = json.loads(scenario_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"[Commit0] Warning: could not read {scenario_path}: {exc}")
            return None

        scenario = self._select_evaluator_scenario(payload.get("scenarios", []))
        if not scenario:
            return None

        targets = []
        for assignment in scenario.get("assignments", []):
            targets.extend(assignment.get("primary_test_targets", []) or [])
        targets = self._dedupe_preserve_order(self._coerce_test_targets(targets))
        if not targets:
            return None

        print(
            "[Commit0] Using AsyncCodeBench scenario evaluator targets from "
            f"{scenario_path}"
        )
        return targets

    def _scenario_manifest_path(self):
        normalized = self.config.repo_name.replace("-", "_")
        return (
            self._repo_root()
            / "manifests"
            / "pilot"
            / "v0.3"
            / "scenarios"
            / f"commit0_{normalized}.json"
        )

    def _task_manifest_path(self):
        normalized = self.config.repo_name.replace("-", "_")
        return (
            self._repo_root()
            / "manifests"
            / "pilot"
            / "v0.3"
            / "tasks"
            / f"commit0_{normalized}.json"
        )

    def _manifest_evaluator_command(self):
        if self._manifest_evaluator_disabled():
            return None

        task_path = self._task_manifest_path()
        if not task_path.exists():
            return None

        try:
            payload = json.loads(task_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"[Commit0] Warning: could not read {task_path}: {exc}")
            return None

        command = payload.get("evaluator_command")
        if not command:
            return None

        test_cmd, targets = self._split_pytest_command(command)
        if not targets:
            return None

        print(
            "[Commit0] Using AsyncCodeBench task evaluator command from "
            f"{task_path}"
        )
        return test_cmd, targets

    @staticmethod
    def _repo_root():
        return Path(__file__).resolve().parents[3]

    @staticmethod
    def _select_evaluator_scenario(scenarios):
        for scenario in scenarios:
            if scenario.get("execution_mode") == "iterative_single":
                return scenario
        return scenarios[0] if scenarios else None

    @staticmethod
    def _manifest_evaluator_disabled():
        raw_value = os.getenv("ASYNCCODEBENCH_DISABLE_MANIFEST_EVALUATOR", "")
        return raw_value.strip().lower() in {"1", "true", "yes", "on"}

    @classmethod
    def _split_pytest_command(cls, command):
        if isinstance(command, str):
            tokens = shlex.split(command)
        elif isinstance(command, (list, tuple)):
            tokens = [str(token) for token in command]
        else:
            return None, []

        if not tokens:
            return None, []

        pytest_index = None
        for idx, token in enumerate(tokens):
            if token == "pytest":
                pytest_index = idx
                break
        if pytest_index is None:
            return None, []

        cmd_tokens = ["python", "-m", "pytest"]
        targets = []
        idx = pytest_index + 1
        option_tokens_with_values = {"-o", "-p"}
        while idx < len(tokens):
            token = tokens[idx]
            if token.startswith("tests/") or token.startswith("--deselect="):
                targets.extend(tokens[idx:])
                break
            cmd_tokens.append(token)
            if token in option_tokens_with_values and idx + 1 < len(tokens):
                idx += 1
                cmd_tokens.append(tokens[idx])
            idx += 1

        return " ".join(shlex.quote(token) for token in cmd_tokens), cls._coerce_test_targets(targets)

    @staticmethod
    def _coerce_test_targets(raw_targets):
        if isinstance(raw_targets, str):
            candidates = [raw_targets]
        elif isinstance(raw_targets, (list, tuple)):
            candidates = raw_targets
        else:
            return ["tests/"]

        targets = []
        for target in candidates:
            target = str(target).strip()
            if not target:
                continue
            # Several AsyncCodeBench manifests record the original pytest command
            # as ["python", "-m", "pytest", "-q", "-o", "addopts=", ...].
            # The runner already supplies its own pytest flags, so this token is
            # an option value, not a filesystem test target.
            if target == "addopts=":
                continue
            targets.append(target)
        return targets or ["tests/"]

    @staticmethod
    def _dedupe_preserve_order(items):
        seen = set()
        deduped = []
        for item in items:
            item = str(item).strip()
            if not item or item in seen:
                continue
            seen.add(item)
            deduped.append(item)
        return deduped

    @staticmethod
    def _annotate_report_evaluator(
        report_data,
        *,
        test_cmd,
        test_targets,
        evaluator_source,
        timeout_seconds,
        timed_out,
    ):
        report_data.setdefault("asynccodebench", {}).update(
            {
                "final_evaluator_source": evaluator_source,
                "final_test_cmd": test_cmd,
                "final_test_targets": test_targets,
                "final_pytest_timeout_seconds": timeout_seconds,
                "timed_out": timed_out,
            }
        )

    @staticmethod
    def _final_pytest_timeout_seconds():
        raw_value = os.getenv("ASYNCCODEBENCH_FINAL_PYTEST_TIMEOUT_SECONDS", "900")
        try:
            timeout = int(raw_value)
        except ValueError:
            print(
                "[Commit0] Warning: invalid "
                f"ASYNCCODEBENCH_FINAL_PYTEST_TIMEOUT_SECONDS={raw_value!r}; "
                "using 900"
            )
            timeout = 900
        return max(timeout, 60)

    def get_prompt_format_args(self, config):
        work_dir = self.get_work_dir()
        workspace_dir_name = work_dir.split("/")[-1]
        if self.task_data:
            test_cmd, test_targets, _ = self._resolve_evaluator()
        else:
            test_cmd, test_targets = "python -m pytest", ["tests/"]
        return {
            "max_agents": config.max_subagents,
            "max_rounds": config.max_rounds_chat,
            "workspace_dir_name": workspace_dir_name,
            "test_cmd": test_cmd,
            "test_dir": " ".join(str(target) for target in test_targets),
        }

    # ---- Manager integration methods ----

    def get_scan_log_kwargs(self, config):
        return {
            "repo_name": self.config.repo_name,
            "repo_path": self.get_work_dir(),
            "max_iterations": config.manager_max_iterations,
        }

    def build_subagent(self, engineer_id, primary_task, all_tasks):
        from config import SubAgent
        all_files = []
        all_functions = []
        all_instructions = []
        for t in all_tasks:
            all_files.append(t.file_path)
            all_functions.extend(t.functions_to_implement)
            all_instructions.append(f"File: {t.file_path}\n{t.instruction}")
        combined_instruction = "\n\n---\n\n".join(all_instructions)
        combined_file_path = ", ".join(all_files) if len(all_files) > 1 else all_files[0]
        subagent = SubAgent(
            engineer_id=engineer_id,
            task_id=primary_task.task_id,
            file_path=combined_file_path,
            functions_to_implement=all_functions,
            instruction=combined_instruction,
            estimated_complexity=primary_task.estimated_complexity,
        )
        combine_log = f"  (Combined {len(all_tasks)} tasks: {all_files})" if len(all_tasks) > 1 else None
        return subagent, combine_log

    def get_worktree_name(self, engineer_id):
        return f"{self.config.repo_name}_worktree_{engineer_id}"

    def get_subagent_log_lines(self, subagent):
        lines = [f"      Task: {subagent.file_path}"]
        funcs_str = ', '.join(subagent.functions_to_implement[:3])
        if len(subagent.functions_to_implement) > 3:
            funcs_str += f"... (+{len(subagent.functions_to_implement)-3})"
        lines.append(f"      Functions: {funcs_str}")
        return lines

    @property
    def should_stash_before_merge(self):
        return True

    @property
    def should_try_uncommitted_merge(self):
        return True

    def build_completed_task_summary(self, result, task_status):
        return (
            f"task_id: {result.task_id}\n"
            f"file: {result.file_path}\n"
            f"status: {task_status}\n"
            f"merged: {result.merged}\n"
            f"merge_method: {result.merge_method or 'none'}\n"
            f"commit: {result.commit_hash or 'none'}\n"
            f"commit_message: {result.commit_message or 'none'}"
        )

    def extract_assignments(self, assign_data):
        assignments = assign_data.get("assignments", [])
        if not assignments and "next_task" in assign_data:
            if assign_data.get("should_assign", False):
                assignments = [assign_data["next_task"]]
        return assignments

    def get_assign_context(self, all_completed, workspace, repo_dir):
        cmd_result = workspace.execute_command(
            f"cd {repo_dir} && git rev-parse HEAD", timeout=30
        )
        current_head = cmd_result.stdout.strip() if cmd_result.exit_code == 0 else ""

        completed_files = set()
        for completed in all_completed:
            if completed.merged and completed.file_path:
                completed_files.add(completed.file_path)
        progress_summary = ""
        if completed_files:
            files_list = "\n".join(f"  - {f}" for f in sorted(completed_files))
            progress_summary = f"Files completed by other agents:\n{files_list}"

        return {"current_head": current_head, "progress_summary": progress_summary}

    def update_subagent_for_assignment(self, subagent, context, workspace, log_fn):
        current_head = context.get("current_head", "")
        progress_summary = context.get("progress_summary", "")

        if current_head and subagent.file_path:
            worktree_name = self.get_worktree_name(subagent.engineer_id)
            subagent.worktree_path = f"/workspace/{worktree_name}"
            subagent.base_commit = current_head

            update_cmd = f"cd {subagent.worktree_path} && git reset --hard {current_head}"
            update_result = workspace.execute_command(update_cmd, timeout=60)

            if update_result.exit_code != 0:
                log_fn(f"Failed to update worktree for {subagent.engineer_id}: {update_result.stderr}")
                subagent.status = "failed"
            else:
                subagent.status = "ready"
                log_fn(f"Worktree for {subagent.engineer_id} updated to {current_head[:8]}")

            if progress_summary:
                subagent.instruction = f"{progress_summary}\n\n{subagent.instruction}"
        else:
            subagent.status = "ready"

    def get_single_agent_info(self, workspace, config, prompts):
        header = "Single Agent Mode - Implementing all functions"
        format_args = self.get_prompt_format_args(config)
        format_args["repo_path"] = self.get_work_dir()
        user_instruction = prompts.get("single_agent_instruction", "").format(**format_args)
        log_content = {
            "repo_name": self.config.repo_name,
            "repo_path": self.get_work_dir(),
            "max_iterations": config.manager_max_iterations,
        }
        return header, user_instruction, log_content

    def get_final_review_log_extras(self, subagent_results):
        merged_count = sum(1 for r in subagent_results if r.merged and r.file_path)
        return {"files_merged": merged_count}

    def get_collect_extra_log(self, subagent_result):
        if subagent_result.file_path:
            return f"  - File: {subagent_result.file_path}"
        return ""

    # ---- SubAgent runner integration methods ----

    def create_subagent_result(self, subagent):
        from config import SubAgentResult
        return SubAgentResult(
            engineer_id=subagent.engineer_id,
            task_id=subagent.task_id,
            task_node_id=subagent.task_node_id,
            branch_name=subagent.branch_name or "",
            worktree_path=subagent.worktree_path or "",
            file_path=subagent.file_path,
            functions_implemented=subagent.functions_to_implement.copy(),
            round_num=subagent.current_round,
        )

    def get_followup_prompt_args(self, subagent):
        return {
            "instruction": subagent.instruction,
            "file_path": subagent.file_path,
            "functions": ", ".join(subagent.functions_to_implement),
        }

    def get_run_start_log_lines(self, subagent):
        return [
            f"  - Task: {subagent.task_id}",
            f"  - File: {subagent.file_path}",
            f"  - Functions: {', '.join(subagent.functions_to_implement)}",
        ]

    @property
    def should_setup_on_retry(self):
        return True

    @property
    def should_resend_on_retry(self):
        return True

    def populate_no_commit_result(self, result):
        result.git_diff = ""

    def populate_success_result(self, result, runner, commit_info):
        result.success = True
        result.commit_hash = commit_info.get("hash", "")
        result.commit_message = commit_info.get("message", "")
        result.git_diff = runner.get_git_diff()
        result.files_modified = runner.get_modified_files()

    def get_event_serialization_extras(self, subagent):
        return {"file_path": subagent.file_path}

    def get_print_summary_lines(self, result, commit_info):
        lines = []
        if result.files_modified:
            lines.append(f"  Files Modified: {', '.join(result.files_modified)}")
        if result.git_diff:
            diff_preview = result.git_diff[:500]
            if len(result.git_diff) > 500:
                diff_preview += "\n... (truncated)"
            lines.append("  Diff Preview:")
            for line in diff_preview.split("\n")[:15]:
                lines.append(f"    {line}")
        return lines

    def prepare_reuse_subagent(self, new_subagent, old_runner):
        pass

    def get_new_task_print_lines(self, subagent):
        lines = [f"- New file: {subagent.file_path}"]
        funcs = ', '.join(subagent.functions_to_implement[:3])
        if len(subagent.functions_to_implement) > 3:
            funcs += f"... (+{len(subagent.functions_to_implement)-3})"
        lines.append(f"- Functions: {funcs}")
        return lines

    def get_onboard_names(self, engineer_id):
        repo_name = self.config.repo_name
        branch_name = f"agent_{engineer_id}"
        worktree_name = f"{repo_name}_worktree_{engineer_id}"
        return branch_name, worktree_name

    def post_onboard_subagent(self, subagent, repo_dir):
        pass

    def get_completion_print_lines(self, result):
        lines = []
        if result.commit_hash:
            lines.append(f"- Commit: {result.commit_hash}")
        return lines

    def get_log_agent_response_kwargs(self, result):
        from datetime import datetime
        return {
            "engineer_id": result.engineer_id,
            "task_id": result.task_id,
            "success": result.success,
            "commit_hash": result.commit_hash,
            "git_diff": result.git_diff,
            "files_modified": result.files_modified,
            "error": result.error,
            "duration_seconds": result.duration_seconds,
            "actual_iterations": result.actual_iterations,
            "max_iterations": result.max_iterations,
            "cost": result.cost,
            "prompt_tokens": result.prompt_tokens,
            "completion_tokens": result.completion_tokens,
            "total_tokens": result.total_tokens,
            "start_time": datetime.fromisoformat(result.start_time) if result.start_time else None,
            "end_time": datetime.fromisoformat(result.end_time) if result.end_time else None,
            "round_num": result.round_num,
        }

    def get_conflict_instruction_args(self, subagent, conflict_files, workspace, repo_dir):
        conflict_file_list = "\n".join(f"  - {f}" for f in conflict_files)
        return {"conflict_file_list": conflict_file_list}

    def get_auto_reassign_instruction_args(self, subagent):
        return {"original_instruction": subagent.instruction}

    def get_execution_summary_lines(self, results):
        lines = [
            f"\n{'=' * 70}",
            "[SubAgents] Execution Summary",
            f"{'=' * 70}",
            f"Total task completions: {len(results)}",
        ]
        merged_count = len([r for r in results if r.merged])
        committed_count = len([r for r in results if r.success])
        recovered_count = len([r for r in results if r.merged and not r.success])
        failed_count = len([r for r in results if not r.merged])
        lines.append(f"Merged: {merged_count} (committed: {committed_count}, recovered: {recovered_count})")
        lines.append(f"Failed: {failed_count}")

        agent_results = {}
        for result in results:
            if result.engineer_id not in agent_results:
                agent_results[result.engineer_id] = []
            agent_results[result.engineer_id].append(result)

        for engineer_id, agent_res in agent_results.items():
            lines.append(f"\n  {engineer_id}:")
            for res in agent_res:
                if res.merged and res.success:
                    status = "SUCCESS"
                elif res.merged and not res.success:
                    status = "RECOVERED"
                else:
                    status = "FAILED"
                lines.append(f"Round {res.round_num}: {status} - {res.task_id}")
                if res.commit_hash:
                    lines.append(f"      Commit: {res.commit_hash}")
                if res.merge_method:
                    lines.append(f"      Merge method: {res.merge_method}")
                if res.error and not res.merged:
                    lines.append(f"      Error: {res.error[:80]}")

        return lines


if __name__ == "__main__":
    config = Commit0Config(repo_name="minitorch")
    task = Commit0Task(config)

    print("=== Commit0 Task Prepare Test ===\n")

    # 1. Docker image
    image = task.get_docker_image()
    print(f"Docker image : {image}")
    assert image == "docker.io/wentingzhao/minitorch:v0", f"unexpected: {image}"

    # 2. Work dir
    work_dir = task.get_work_dir()
    print(f"Work dir     : {work_dir}")
    assert work_dir == "/workspace/minitorch_repo"

    # 3. Workspace config
    kwargs = task.get_workspace_config()
    assert kwargs["base_image"] == image
    assert kwargs["target"] == "source-minimal"

    # 4. Different repo names
    for repo in ["simpy", "portalocker", "flask"]:
        t = Commit0Task(Commit0Config(repo_name=repo))
        expected_image = f"docker.io/wentingzhao/{repo}:v0"
        assert t.get_docker_image() == expected_image, f"{repo}: {t.get_docker_image()}"
        assert t.get_work_dir() == f"/workspace/{repo}_repo"
        print(f"  {repo:15s} -> image={t.get_docker_image()}, work_dir={t.get_work_dir()}")

    # 5. task_data should be None before load
    assert task.task_data is None

    print("\nAll checks passed!")
