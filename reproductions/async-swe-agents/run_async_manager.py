"""Execution engine for the official online Async-Manager protocol."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import subprocess
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

if any(arg.startswith(("--dry_run", "--dry-run", "--validate")) for arg in sys.argv):
    os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")

import fire
from agents import load_agent_adapter
from asyncodebench_harness.protocol_registry import protocol_registry_path
from config import WorkflowConfig
from protocols.async_manager import BASE_PROTOCOL, POLICY, PROTOCOL
from protocols.async_manager.checkpoint_bridge import online_checkpoint_bridge
from protocols.async_manager.manager import OnlineManager, dump
from protocols.async_manager.results import finalize, validate
from protocols.asyncodebench.metadata import (
    build_run_metadata,
    write_contract_snapshots,
    write_run_metadata,
)
from run_asyncodebench import (
    _assert_openhands_runtime_consistency,
    _generate_process_metrics,
    _safe_component,
)
from run_infer import run_workflow
from tasks.asyncodebench import AsynCodeBenchConfig, AsynCodeBenchTask

FROZEN_BASE_REVISION = "73c9877315c920867ba72750826b66421be08bc0"
FROZEN_LEGACY_EXECUTION_PATHS = (
    "reproductions/async-swe-agents/core",
    "reproductions/async-swe-agents/protocols/asyncodebench/runner.py",
    "reproductions/async-swe-agents/protocols/static_commit0.py",
    "reproductions/async-swe-agents/run_infer.py",
)


@contextmanager
def prefer_worktree_python_for_pr_hard(task):
    """Give the new protocol the same worktree-aware Python semantics as v0.4.

    The packaged TVM images put their pinned environment at the front of
    ``PATH``.  PR-hard creates ``/usr/local/bin/python`` during repository
    setup so that every bare ``python`` command resolves imports and native
    libraries from the current Git worktree.  Prepending ``/usr/local/bin`` to
    the agent-server container PATH restores that intended behavior for the
    manager, specialists, dependency probes, and evaluator together.

    This is a process-local launch setting used only by ``async_manager``.  It
    does not modify the shared task adapter or any frozen protocol engine.
    """

    environment_path = getattr(task, "environment_path", None)
    if environment_path is None:
        yield
        return

    import core.workspace as workspace_module

    setting = workspace_module.NONINTERACTIVE_PAGER_ENV
    sentinel = object()
    previous = setting.get("PATH", sentinel)
    setting["PATH"] = ":".join(
        [
            "/usr/local/bin",
            f"{environment_path}/bin",
            "/usr/local/sbin",
            "/usr/sbin",
            "/usr/bin",
            "/sbin",
            "/bin",
        ]
    )
    try:
        yield
    finally:
        if previous is sentinel:
            setting.pop("PATH", None)
        else:
            setting["PATH"] = previous


def protocol_sources() -> list[Path]:
    root = Path(__file__).parent
    repo_root = root.parents[1]
    sources = [Path(__file__)]
    sources.extend(
        sorted(
            path
            for path in root.joinpath("protocols", "async_manager").iterdir()
            if path.is_file()
        )
    )
    sources.extend(sorted(root.joinpath("scripts").glob("run_async_manager*.sh")))
    sources.extend(
        [
            root / "scripts" / "run_asyncodebench_five_protocols_env.sh",
            root / "scripts" / "run_pr_hard_five_protocols_env.sh",
            root / "run_asyncodebench.py",
            root / "run_pr_hard.py",
            root / "asyncodebench_harness" / "protocol_registry.py",
            root / "asyncodebench_harness" / "results.py",
            root / "protocols" / "asyncodebench" / "metadata.py",
            root / "protocols" / "asyncodebench" / "profile.py",
            root / "tasks" / "asyncodebench.py",
            repo_root / "configs" / "evaluation" / "protocol_registry.v1.json",
            repo_root
            / "configs"
            / "evaluation"
            / "official_execution_profile.v3.json",
            repo_root / "schemas" / "release" / "agent_request.schema.json",
            repo_root / "schemas" / "release" / "run_bundle.schema.json",
        ]
    )
    return sorted(set(sources))


def async_manager_profile() -> dict:
    path = Path(__file__).parent / "protocols" / "async_manager" / "profile.json"
    profile = json.loads(path.read_text(encoding="utf-8"))
    if (
        profile.get("protocol") != PROTOCOL
        or profile.get("policy") != POLICY
        or profile.get("schema_version") != "async-manager-profile-v1"
    ):
        raise RuntimeError("Invalid online Async-Manager profile")
    return profile


def assert_protocol_sources_clean(repo_root: Path) -> None:
    sources = [str(path.relative_to(repo_root)) for path in protocol_sources()]
    result = subprocess.run(
        [
            "git",
            "-C",
            str(repo_root),
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
            "--",
            *sources,
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    if result.stdout.strip():
        raise RuntimeError(
            "Async-Manager protocol source is uncommitted; commit its exact source "
            "before a formal run:\n" + result.stdout
        )


def assert_legacy_execution_unchanged(repo_root: Path) -> None:
    result = subprocess.run(
        [
            "git",
            "-C",
            str(repo_root),
            "diff",
            "--exit-code",
            FROZEN_BASE_REVISION,
            "--",
            *FROZEN_LEGACY_EXECUTION_PATHS,
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "A frozen legacy-protocol execution path differs from its pinned "
            "base revision; the Async-Manager registration must not change the "
            "old four execution engines:\n"
            + (result.stdout or result.stderr)
        )


def _snapshot_protocol(output: Path, repo_root: Path, profile: dict) -> dict:
    profile_path = output / "async_manager_profile_snapshot.json"
    dump(profile_path, profile)
    source_hashes = {}
    for source in protocol_sources():
        relative = source.relative_to(repo_root)
        destination = output / "protocol_sources" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source.read_bytes())
        source_hashes[relative.as_posix()] = hashlib.sha256(
            source.read_bytes()
        ).hexdigest()
    return {
        "policy": POLICY,
        "base_protocol": BASE_PROTOCOL,
        "frozen_base_revision": FROZEN_BASE_REVISION,
        "profile_sha256": hashlib.sha256(profile_path.read_bytes()).hexdigest(),
        "sources": source_hashes,
        "scheduler": "process_local_checkpoint_bridge",
        "manager_identity": profile["manager_identity"],
    }


def main(
    task_id="asyncodebench:cachetools",
    model=None,
    subagent_model=None,
    run_id=None,
    model_tag=None,
    max_iterations=None,
    max_subagents=None,
    sub_iterations=None,
    rounds_of_chat=None,
    output_dir=None,
    release="v0.3",
    docker_image_prefix="docker.io/wentingzhao/",
    curated_config_path="",
    agent="openhands",
    agent_import_path=None,
    agent_config_json=None,
    dry_run=False,
    validate_dir=None,
    runtime_root="",
    build_cache_root="",
    runtime_backend="local",
    runtime_image="",
    allow_unqualified=False,
):
    if validate_dir:
        issues = validate(validate_dir)
        print(json.dumps({"valid": not issues, "issues": issues}, indent=2))
        if issues:
            raise RuntimeError("Invalid online Async-Manager bundle")
        return

    model = model or os.getenv("LLM_MODEL")
    if not model:
        raise ValueError("Set LLM_MODEL or --model")
    subagent_model = subagent_model or os.getenv("LLM_SUBAGENT_MODEL")
    profile = async_manager_profile()
    candidate_lane = None
    if task_id.startswith("pr-hard:"):
        from run_pr_hard import _candidate_preflight
        from tasks.pr_hard import PrHardConfig, PrHardTask

        candidate, qualification, failures = _candidate_preflight(
            task_id, PROTOCOL, allow_unqualified=bool(allow_unqualified)
        )
        task = PrHardTask(
            PrHardConfig(
                task_id=task_id,
                runtime_root=runtime_root,
                build_cache_root=build_cache_root,
                runtime_backend=runtime_backend,
                runtime_image=runtime_image,
            )
        )
        candidate_lane = {
            "kind": "pr_hard_v0.4",
            "official_result_eligible": (
                candidate.get("qualification_status") == "qualified"
                and qualification.get("automated_status") == "passed"
                and qualification.get("human_review", {}).get("status")
                == "complete_pass"
                and qualification.get("remaining_gates") == []
                and not failures
            ),
            "remaining_gates": qualification.get("remaining_gates", []),
            "qualification_status": candidate["qualification_status"],
            "diagnostic_only": bool(failures),
        }
    else:
        task = AsynCodeBenchTask(
            AsynCodeBenchConfig(
                task_id=task_id,
                release=release,
                docker_image_prefix=docker_image_prefix,
                curated_config_path=curated_config_path,
            )
        )
    task.set_active_protocol(PROTOCOL)

    adapter = load_agent_adapter(
        agent=agent,
        agent_import_path=agent_import_path,
        agent_config_json=agent_config_json,
    )
    declared_agents = int(task.scenario_for(PROTOCOL)["agent_count"])
    max_subagents = declared_agents if max_subagents is None else int(max_subagents)
    if max_subagents != declared_agents:
        raise ValueError(
            f"Async-Manager scenario declares {declared_agents} specialists, "
            f"got max_subagents={max_subagents}"
        )
    manager_iterations = int(
        profile["manager_max_iterations_per_event"]
        if max_iterations is None
        else max_iterations
    )
    specialist_iterations = int(
        profile["subagent_max_iterations"]
        if sub_iterations is None
        else sub_iterations
    )
    chat_rounds = int(
        profile["max_rounds_chat"]
        if rounds_of_chat is None
        else rounds_of_chat
    )
    config = WorkflowConfig(
        model=model,
        subagent_model=subagent_model,
        manager_max_iterations=manager_iterations,
        subagent_max_iterations=specialist_iterations,
        max_rounds_chat=chat_rounds,
        max_subagents=max_subagents,
    )
    run_id = run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    lane = "pr_hard/v0.4" if candidate_lane else "asyncodebench/v0.3"
    output = (
        Path(output_dir)
        if output_dir
        else Path("outputs")
        / lane
        / _safe_component(model_tag or os.getenv("MODEL_TAG") or model)
        / task.repository_name
        / PROTOCOL
        / _safe_component(run_id)
    ).resolve()
    config.output_dir = str(output)

    if dry_run:
        print(
            json.dumps(
                {
                    "protocol": PROTOCOL,
                    "policy": POLICY,
                    "base_protocol": BASE_PROTOCOL,
                    "task_id": task_id,
                    "output_dir": str(output),
                    "manager_max_iterations_per_event": config.manager_max_iterations,
                    "subagent_max_iterations": config.subagent_max_iterations,
                    "max_rounds_chat": config.max_rounds_chat,
                    "manager_scope": sorted(
                        {
                            path
                            for assignment in task.scenario_for(PROTOCOL)[
                                "assignments"
                            ]
                            for path in assignment["writable_paths"]
                        }
                    ),
                    "frozen_base_revision": FROZEN_BASE_REVISION,
                    "deny_agent_network": getattr(task, "deny_agent_network", False),
                },
                indent=2,
            )
        )
        return

    for name in (
        "ASYNCODEBENCH_DISABLE_PROBE_CHECKPOINTS",
        "ASYNCODEBENCH_DISABLE_AUTO_METRICS",
    ):
        if os.getenv(name) == "1":
            raise ValueError(f"{name} cannot be enabled for Async-Manager runs")

    _assert_openhands_runtime_consistency()
    repo_root = task._repo_root()
    assert_protocol_sources_clean(repo_root)
    assert_legacy_execution_unchanged(repo_root)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.mkdir(exist_ok=False)

    prompt_path = Path(__file__).parent / "prompts" / "asyncodebench.yaml"
    metadata = build_run_metadata(
        task,
        config,
        PROTOCOL,
        prompt_path,
        agent_adapter=adapter.public_metadata(),
    )
    metadata["protocol"] = PROTOCOL
    registry_path = protocol_registry_path()
    metadata["protocol_contract"] = {
        "path": registry_path.relative_to(repo_root).as_posix(),
        "sha256": hashlib.sha256(registry_path.read_bytes()).hexdigest(),
        "official": True,
    }
    metadata["async_manager_protocol"] = _snapshot_protocol(
        output, repo_root, profile
    )
    if candidate_lane:
        metadata["candidate_lane"] = candidate_lane
    write_run_metadata(output, metadata)
    write_contract_snapshots(output, task, PROTOCOL)
    protocol = json.loads((output / "protocol.json").read_text(encoding="utf-8"))
    protocol.update(
        protocol=PROTOCOL,
        protocol_contract=metadata["protocol_contract"],
        async_manager_protocol=metadata["async_manager_protocol"],
    )
    dump(output / "protocol.json", protocol)

    try:
        with prefer_worktree_python_for_pr_hard(task), online_checkpoint_bridge():
            result = asyncio.run(
                run_workflow(
                    "asyncodebench",
                    config,
                    task,
                    multi_agent=True,
                    agent_adapter=adapter,
                    manager_class=OnlineManager,
                )
            )
        _generate_process_metrics(task, output)
        finalize(output, task=task, agent_adapter=adapter)
        return result
    except BaseException as error:
        dump(
            output / "async_manager_execution_error.json",
            {"type": type(error).__name__, "detail": str(error)},
        )
        raise
    finally:
        if candidate_lane:
            task.cleanup_build_cache()


if __name__ == "__main__":
    fire.Fire(main)
