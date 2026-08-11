"""Unified native entry point for AsynCodeBench harness v2."""

import asyncio
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import fire
from config import WorkflowConfig
from core.asyncodebench_manager import AsynCodeBenchManager
from protocols.asyncodebench import AsynCodeBenchProtocolRunner
from protocols.asyncodebench.metadata import (
    build_run_metadata,
    write_contract_snapshots,
    write_run_metadata,
)
from protocols.asyncodebench.ordering import topological_assignments
from run_infer import run_workflow
from tasks.asyncodebench import AsynCodeBenchConfig, AsynCodeBenchTask

SUPPORTED_PROTOCOLS = {
    "single",
    "serial_specialists",
    "async_private",
    "caid_manager",
}


def _safe_component(value):
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value)).strip("_")


def _public_scenario_id(value):
    return re.sub(r"^commit0(?=[-_])", "asyncodebench", str(value), count=1)


def _default_output_dir(task, model, protocol, run_id=None):
    run_id = run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return (
        Path("outputs")
        / "asyncodebench"
        / "v0.3"
        / _safe_component(model)
        / _safe_component(task.config.repo_name)
        / protocol
        / _safe_component(run_id)
    )


def _assert_fresh_output(path):
    path = Path(path)
    if path.exists() and any(path.iterdir()):
        raise FileExistsError(
            f"Refusing to reuse non-empty output directory: {path}. "
            "Use a new run_id; interrupted run directories are immutable."
        )
    path.mkdir(parents=True, exist_ok=True)


def _generate_process_metrics(task, output_dir):
    if os.getenv("ASYNCODEBENCH_DISABLE_AUTO_METRICS") == "1":
        print("[AsynCodeBench] Automatic process metrics disabled by environment")
        return None
    repo_root = task._repo_root()
    script = repo_root / "scripts" / "analyze_run_process_metrics.py"
    output_path = Path(output_dir) / "process_metrics_summary.json"
    command = [
        sys.executable,
        str(script),
        "--run-dir",
        str(output_dir),
        "--metrics",
        str(task.manifest_paths["metrics"]),
        "--output",
        str(output_path),
        "--print-summary",
    ]
    result = subprocess.run(command, text=True, capture_output=True, check=False)
    log_path = Path(output_dir) / "process_metrics_generation.log"
    log_path.write_text(
        result.stdout + ("\n" + result.stderr if result.stderr else ""),
        encoding="utf-8",
    )
    if result.returncode != 0 or not output_path.exists():
        raise RuntimeError(
            f"Automatic process metric generation failed; see {log_path}"
        )
    print(f"[AsynCodeBench] Process metrics: {output_path}")
    return output_path


def _print_dry_run(task, protocol, workflow_config, output_dir):
    scenario = task.scenario_for(protocol)
    if protocol in {"serial_specialists", "async_private"}:
        assignments, cycle_nodes = topological_assignments(
            scenario.get("assignments", []),
            scenario.get("dependency_annotations", []),
        )
        integration_order = [item.get("agent_id") for item in assignments]
        path_owners = {}
        for assignment in assignments:
            for path in assignment.get("writable_paths", []):
                path_owners.setdefault(path, []).append(assignment.get("agent_id"))
        shared_writable_paths = {
            path: owners for path, owners in path_owners.items() if len(owners) > 1
        }
        display_assignments = assignments
    else:
        integration_order = [
            assignment.get("agent_id") for assignment in scenario.get("assignments", [])
        ]
        cycle_nodes = []
        shared_writable_paths = {}
        display_assignments = scenario.get("assignments", [])

    print("[DryRun] harness=asyncodebench-v2")
    print(f"[DryRun] task_id={task.task_id}")
    print(f"[DryRun] official=True release={task.asyncodebench_config.release}")
    print(f"[DryRun] protocol={protocol}")
    print(f"[DryRun] scenario_id={_public_scenario_id(scenario.get('scenario_id'))}")
    print(f"[DryRun] curated_base_sha={task.curated_task.get('base_sha')}")
    print(f"[DryRun] overlays={len(task.curated_task.get('overlays', []) or [])}")
    print(f"[DryRun] output_dir={output_dir}")
    print(f"[DryRun] integration_order={integration_order}")
    print(f"[DryRun] dependency_cycle_nodes={cycle_nodes}")
    print(f"[DryRun] shared_writable_paths={shared_writable_paths}")
    for assignment in display_assignments:
        print(
            "[DryRun] assignment "
            f"agent={assignment.get('agent_id')} "
            f"subproblem={assignment.get('subproblem_id')} "
            f"paths={assignment.get('writable_paths', [])} "
            f"tests={assignment.get('primary_test_targets', [])}"
        )


def main(
    task_id="asyncodebench:cachetools",
    protocol="single",
    model=None,
    subagent_model=None,
    max_iterations=30,
    max_subagents=None,
    sub_iterations=30,
    rounds_of_chat=2,
    output_dir=None,
    run_id=None,
    release="v0.3",
    docker_image_prefix="docker.io/wentingzhao/",
    curated_config_path="",
    dry_run=False,
):
    if protocol not in SUPPORTED_PROTOCOLS:
        choices = ", ".join(sorted(SUPPORTED_PROTOCOLS))
        raise ValueError(f"Unsupported protocol={protocol!r}; choose from: {choices}")
    model = model or os.getenv("LLM_MODEL")
    if not model:
        raise ValueError("A model is required via --model or LLM_MODEL")
    subagent_model = subagent_model or os.getenv("LLM_SUBAGENT_MODEL")

    task = AsynCodeBenchTask(
        AsynCodeBenchConfig(
            task_id=task_id,
            release=release,
            docker_image_prefix=docker_image_prefix,
            curated_config_path=curated_config_path,
        )
    )
    task.set_active_protocol(protocol)
    scenario = task.scenario_for(protocol)
    declared_agents = int(scenario.get("agent_count", 1))
    if max_subagents is None:
        max_subagents = declared_agents
    if int(max_subagents) != declared_agents:
        scenario_id = scenario.get("scenario_id")
        raise ValueError(
            f"Scenario {scenario_id} declares {declared_agents} agents, "
            f"but max_subagents={max_subagents}"
        )

    workflow_config = WorkflowConfig(
        model=model,
        subagent_model=subagent_model,
        manager_max_iterations=int(max_iterations),
        max_subagents=int(max_subagents),
        subagent_max_iterations=int(sub_iterations),
        max_rounds_chat=int(rounds_of_chat),
    )
    resolved_output = (
        Path(output_dir)
        if output_dir
        else _default_output_dir(task, model, protocol, run_id)
    )
    workflow_config.output_dir = str(resolved_output)

    if dry_run:
        _print_dry_run(task, protocol, workflow_config, resolved_output)
        return

    _assert_fresh_output(resolved_output)
    prompt_path = Path(__file__).resolve().parent / "prompts" / "asyncodebench.yaml"
    metadata = build_run_metadata(task, workflow_config, protocol, prompt_path)
    metadata_path = write_run_metadata(resolved_output, metadata)
    snapshot_paths = write_contract_snapshots(resolved_output, task, protocol)
    print(f"[AsynCodeBench] Run metadata: {metadata_path}")
    print("[AsynCodeBench] Contract snapshots: " + ", ".join(sorted(snapshot_paths)))

    if protocol in {"serial_specialists", "async_private"}:
        runner = AsynCodeBenchProtocolRunner(
            task_module=task,
            workflow_config=workflow_config,
            protocol=protocol,
        )
        result = asyncio.run(runner.run())
        _generate_process_metrics(task, resolved_output)
        return result

    workflow_kwargs = {}
    if protocol == "caid_manager":
        workflow_kwargs["manager_class"] = AsynCodeBenchManager
    result = asyncio.run(
        run_workflow(
            "asyncodebench",
            workflow_config,
            task,
            multi_agent=protocol == "caid_manager",
            **workflow_kwargs,
        )
    )
    _generate_process_metrics(task, resolved_output)
    return result


if __name__ == "__main__":
    fire.Fire(main)
