import asyncio
import os
from datetime import datetime
from pathlib import Path

import fire

from config import WorkflowConfig
from core.utils import build_task_module
from protocols.static_commit0 import SUPPORTED_PROTOCOLS, StaticCommit0ProtocolRunner


def build_static_output_dir(task, repo, model, protocol, workflow_config):
    model_short = model.split("/")[-1] if "/" in model else model
    if workflow_config.subagent_model:
        sub_short = (
            workflow_config.subagent_model.split("/")[-1]
            if "/" in workflow_config.subagent_model
            else workflow_config.subagent_model
        )
        model_short = f"{model_short}+{sub_short}"

    params = (
        f"subagents={workflow_config.max_subagents}"
        f"_subiters={workflow_config.subagent_max_iterations}"
    )
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return str(Path("outputs") / task / model_short / repo / protocol / params / timestamp)


def main(
    task="commit0",
    protocol="serial_specialists",
    repo="cachetools",
    model=None,
    subagent_model=None,
    max_subagents=4,
    sub_iterations=50,
    output_dir=None,
    scenario_path=None,
    dry_run=False,
    **kwargs,
):
    if task != "commit0":
        raise ValueError("run_static_protocol.py currently supports task='commit0' only")
    if protocol not in SUPPORTED_PROTOCOLS:
        raise ValueError(
            f"Unsupported protocol={protocol!r}. "
            f"Available: {', '.join(sorted(SUPPORTED_PROTOCOLS))}"
        )

    model_name = model or os.getenv("LLM_MODEL", "litellm_proxy/neulab/gpt-5-mini")
    subagent_model_name = subagent_model or os.getenv("LLM_SUBAGENT_MODEL")

    workflow_config = WorkflowConfig(
        model=model_name,
        subagent_model=subagent_model_name,
        manager_max_iterations=0,
        max_subagents=max_subagents,
        subagent_max_iterations=sub_iterations,
        max_rounds_chat=1,
    )

    task_module = build_task_module(task, repo=repo, **kwargs)

    workflow_config.output_dir = output_dir or build_static_output_dir(
        task, repo, model_name, protocol, workflow_config
    )
    Path(workflow_config.output_dir).mkdir(parents=True, exist_ok=True)

    print(f"[Config] {workflow_config}")
    print(f"[Protocol] {protocol}")

    runner = StaticCommit0ProtocolRunner(
        task_module=task_module,
        workflow_config=workflow_config,
        protocol=protocol,
        scenario_path=scenario_path,
        task_name=task,
    )
    if dry_run:
        scenario = runner.load_scenario()
        print(f"[DryRun] scenario_id={scenario.get('scenario_id')}")
        print(f"[DryRun] concurrent_execution={scenario.get('concurrent_execution')}")
        print(f"[DryRun] communication_condition={scenario.get('communication_condition')}")
        for assignment in scenario.get("assignments", []):
            print(
                "[DryRun] "
                f"{assignment.get('agent_id')} "
                f"subproblem={assignment.get('subproblem_id')} "
                f"paths={assignment.get('writable_paths', [])} "
                f"tests={assignment.get('primary_test_targets', [])}"
            )
        return
    asyncio.run(runner.run())


if __name__ == "__main__":
    fire.Fire(main)
