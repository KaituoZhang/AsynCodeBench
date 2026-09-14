"""Process-local bridge from frozen scheduler checkpoints to online events.

The released scheduler remains untouched.  During an ``async_manager`` run
only, this context manager wraps its checkpoint writer.  Every specialist
integration checkpoint is written first, then offered to the persistent
manager.  A state-changing accepted intervention receives the next canonical
integrated-workspace checkpoint.
"""

from __future__ import annotations

from contextlib import contextmanager

import core.subagent as subagent_module

from protocols.async_manager import PROTOCOL
from protocols.async_manager.manager import OnlineManager


@contextmanager
def online_checkpoint_bridge():
    original = subagent_module.write_dependency_probe_checkpoint
    # The frozen CAID workflow constructs specialist adapters with its own
    # historical protocol ID. During this context only, relabel those requests
    # with the public protocol actually being executed. Built-in and third-party
    # adapters then receive the same first-class identity as the run bundle.
    import run_infer as workflow_module

    original_create_agent_runner = workflow_module.create_agent_runner
    extra_steps = 0

    def create_async_manager_runner(adapter, protocol, **kwargs):
        if protocol == "caid_manager":
            protocol = PROTOCOL
        return original_create_agent_runner(adapter, protocol=protocol, **kwargs)

    def write_with_intervention(**kwargs):
        nonlocal extra_steps
        adjusted = dict(kwargs)
        supplied_step = int(adjusted.get("logical_step", 0))
        adjusted["logical_step"] = supplied_step + extra_steps

        if adjusted.get("checkpoint_type") != "integration_after_merge":
            return original(**adjusted)

        specialist_checkpoint = original(**adjusted)
        manager = OnlineManager.active_instance
        if manager is None:
            raise RuntimeError(
                "Async-Manager checkpoint bridge has no active manager instance"
            )
        event = manager.consume_integration_event(specialist_checkpoint)
        if event is None:
            raise RuntimeError(
                "Specialist integration checkpoint has no pending manager event"
            )

        record = manager.intervene(event)
        manager_checkpoint = None
        if record.get("accepted"):
            extra_steps += 1
            refresh = getattr(manager.task, "refresh_source_build", None)
            source_build = (
                refresh(manager.workspace, manager.repo_dir)
                if refresh is not None
                else {"status": "not_required"}
            )
            manager_checkpoint = original(
                workspace=manager.workspace,
                output_dir=adjusted["output_dir"],
                repo_name=adjusted["repo_name"],
                workspace_path=manager.repo_dir,
                checkpoint_id=(
                    f"integration_after_manager_intervention:{record['sequence']}"
                ),
                checkpoint_type="integration_after_manager_intervention",
                logical_step=adjusted["logical_step"] + 1,
                agent_id="manager",
                task_id=adjusted.get("task_id"),
                workspace_kind="integrated_workspace",
                artifact_version=record.get("manager_commit"),
                visible_upstream_artifact_version=adjusted.get("artifact_version"),
                integrated_workspace_version=manager.current_head(),
                metrics_path=adjusted.get("metrics_path"),
                timeout=adjusted.get("timeout", 60),
                source_build=source_build,
            )
        manager.finalize_intervention_record(record, manager_checkpoint)
        return manager_checkpoint or specialist_checkpoint

    if getattr(
        subagent_module.write_dependency_probe_checkpoint,
        "_async_manager_bridge",
        False,
    ):
        raise RuntimeError("Async-Manager checkpoint bridge is already installed")
    write_with_intervention._async_manager_bridge = True
    subagent_module.write_dependency_probe_checkpoint = write_with_intervention
    workflow_module.create_agent_runner = create_async_manager_runner
    try:
        yield
    finally:
        subagent_module.write_dependency_probe_checkpoint = original
        workflow_module.create_agent_runner = original_create_agent_runner
        if OnlineManager.active_instance is not None:
            # A setup failure can occur before run_workflow reaches cleanup.
            OnlineManager.active_instance = None
