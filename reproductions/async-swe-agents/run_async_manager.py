"""Additive entry point for the online Async-Manager protocol."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

if any(arg.startswith(("--dry_run", "--dry-run", "--validate")) for arg in sys.argv):
    os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")

import fire
from agents import load_agent_adapter
from async_manager_extension import BASE_PROTOCOL, POLICY, PROTOCOL
from async_manager_extension.checkpoint_bridge import online_checkpoint_bridge
from async_manager_extension.manager import OnlineManager, dump
from async_manager_extension.results import finalize, validate
from config import WorkflowConfig
from protocols.asyncodebench.metadata import (
    assert_harness_source_clean,
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

FROZEN_BASE_REVISION = "547a84e618a2338f3b7bd30cd976d582c42e661c"
FROZEN_PATHS = (
    "configs/evaluation",
    "configs/tasks",
    "manifests/pilot",
    "manifests/release",
    "reproductions/async-swe-agents/agents",
    "reproductions/async-swe-agents/asyncodebench_harness",
    "reproductions/async-swe-agents/core",
    "reproductions/async-swe-agents/prompts",
    "reproductions/async-swe-agents/protocols",
    "reproductions/async-swe-agents/tasks",
    "reproductions/async-swe-agents/config.py",
    "reproductions/async-swe-agents/run_infer.py",
    "reproductions/async-swe-agents/run_asyncodebench.py",
    "reproductions/async-swe-agents/run_pr_hard.py",
)


def extension_sources() -> list[Path]:
    root = Path(__file__).parent
    sources = [Path(__file__)]
    sources.extend(
        sorted(
            path
            for path in root.joinpath("async_manager_extension").iterdir()
            if path.is_file()
        )
    )
    sources.extend(sorted(root.joinpath("scripts").glob("run_async_manager*.sh")))
    return sources


def async_manager_profile() -> dict:
    path = Path(__file__).parent / "async_manager_extension" / "profile.json"
    profile = json.loads(path.read_text(encoding="utf-8"))
    if (
        profile.get("protocol") != PROTOCOL
        or profile.get("policy") != POLICY
        or profile.get("schema_version") != "async-manager-profile-v1"
    ):
        raise RuntimeError("Invalid online Async-Manager profile")
    return profile


def assert_extension_clean(repo_root: Path) -> None:
    sources = [str(path.relative_to(repo_root)) for path in extension_sources()]
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
            "Async-Manager extension is uncommitted; commit its exact source "
            "before a formal run:\n" + result.stdout
        )


def assert_frozen_base_unchanged(repo_root: Path) -> None:
    result = subprocess.run(
        [
            "git",
            "-C",
            str(repo_root),
            "diff",
            "--exit-code",
            FROZEN_BASE_REVISION,
            "--",
            *FROZEN_PATHS,
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "The online protocol must remain additive, but a frozen benchmark "
            "path differs from its pinned base revision:\n"
            + (result.stdout or result.stderr)
        )


def _snapshot_extension(output: Path, repo_root: Path, profile: dict) -> dict:
    profile_path = output / "async_manager_profile_snapshot.json"
    dump(profile_path, profile)
    source_hashes = {}
    for source in extension_sources():
        relative = source.relative_to(repo_root)
        destination = output / "extension_sources" / relative
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
    dry_run=False,
    validate_dir=None,
    runtime_root="",
    build_cache_root="",
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
            task_id, BASE_PROTOCOL
        )
        task = PrHardTask(
            PrHardConfig(
                task_id=task_id,
                runtime_root=runtime_root,
                build_cache_root=build_cache_root,
            )
        )
        candidate_lane = {
            "kind": "pr_hard_v0.4",
            "official_result_eligible": not failures,
            "remaining_gates": qualification.get("remaining_gates", []),
            "qualification_status": candidate["qualification_status"],
            "diagnostic_only": bool(failures),
        }
    else:
        task = AsynCodeBenchTask(AsynCodeBenchConfig(task_id=task_id))
    task.set_active_protocol(BASE_PROTOCOL)

    adapter = load_agent_adapter(agent="openhands")
    config = WorkflowConfig(
        model=model,
        subagent_model=subagent_model,
        manager_max_iterations=profile["manager_max_iterations_per_event"],
        subagent_max_iterations=profile["subagent_max_iterations"],
        max_rounds_chat=profile["max_rounds_chat"],
        max_subagents=int(task.scenario_for(BASE_PROTOCOL)["agent_count"]),
    )
    run_id = run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    lane = "pr_hard/v0.4" if candidate_lane else "asyncodebench/v0.3"
    output = (
        Path("outputs")
        / lane
        / _safe_component(model_tag or os.getenv("MODEL_TAG") or model)
    )
    output = (
        output / task.repository_name / PROTOCOL / _safe_component(run_id)
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
                            for assignment in task.scenario_for(BASE_PROTOCOL)[
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
    assert_harness_source_clean(repo_root)
    assert_extension_clean(repo_root)
    assert_frozen_base_unchanged(repo_root)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.mkdir(exist_ok=False)

    prompt_path = Path(__file__).parent / "prompts" / "asyncodebench.yaml"
    metadata = build_run_metadata(
        task,
        config,
        BASE_PROTOCOL,
        prompt_path,
        agent_adapter=adapter.public_metadata(),
    )
    metadata["protocol"] = PROTOCOL
    metadata["async_manager_extension"] = _snapshot_extension(
        output, repo_root, profile
    )
    if candidate_lane:
        metadata["candidate_lane"] = candidate_lane
    write_run_metadata(output, metadata)
    write_contract_snapshots(output, task, BASE_PROTOCOL)
    protocol = json.loads((output / "protocol.json").read_text(encoding="utf-8"))
    protocol.update(
        protocol=PROTOCOL,
        async_manager_extension=metadata["async_manager_extension"],
    )
    dump(output / "protocol.json", protocol)

    try:
        with online_checkpoint_bridge():
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
        finalize(output)
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
