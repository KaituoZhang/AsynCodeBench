"""Candidate-only entry point for multi-agent PR-hard v0.4 tasks."""

from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import fire

from agents import load_agent_adapter
from config import WorkflowConfig
from core.asyncodebench_manager import AsynCodeBenchManager
from protocols.asyncodebench import AsynCodeBenchProtocolRunner
from protocols.asyncodebench.metadata import (
    build_run_metadata,
    write_contract_snapshots,
    write_run_metadata,
)
from run_asyncodebench import (
    SUPPORTED_PROTOCOLS,
    _assert_fresh_output,
    _assert_openhands_runtime_consistency,
    _finalize_run_bundle,
    _generate_process_metrics,
    _safe_component,
)
from run_infer import run_workflow
from tasks.pr_hard import PrHardConfig, PrHardTask


PROTOCOL_ELIGIBILITY = {
    "single": "iterative_single",
    "serial_specialists": "serial_specialists",
    "async_private": "async_private",
    "caid_manager": "async_message",
}


def _repo_root():
    configured = os.getenv("ASYNCODEBENCH_ROOT")
    if configured:
        root = Path(configured).expanduser().resolve()
        if not (root / "manifests").is_dir():
            raise RuntimeError(
                "ASYNCODEBENCH_ROOT does not contain benchmark manifests: "
                f"{root}"
            )
        return root
    return Path(__file__).resolve().parents[2]


def _read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _candidate_preflight(task_id, protocol, allow_unqualified=False):
    root = _repo_root()
    registry = _read_json(root / "configs/tasks/pr_hard_candidates.v0.4.json")
    candidate = next(
        (record for record in registry.get("records", []) if record.get("task_id") == task_id),
        None,
    )
    if candidate is None:
        raise ValueError(f"Unknown PR-hard candidate: {task_id}")

    qualification_path = candidate.get("qualification_record")
    qualification = _read_json(root / qualification_path) if qualification_path else {}
    expected_eligibility = PROTOCOL_ELIGIBILITY[protocol]
    failures = []
    qualification_status = candidate.get("qualification_status")
    if qualification_status not in {"pending_human_review", "qualified"}:
        failures.append(
            f"qualification_status={qualification_status!r}"
        )
    expected_automated_status = (
        "passed" if qualification_status == "qualified"
        else "passed_pending_human_review"
    )
    if qualification.get("automated_status") != expected_automated_status:
        failures.append(f"automated_status={qualification.get('automated_status')!r}")
    expected_remaining_gates = [] if qualification_status == "qualified" else ["human_review"]
    if qualification.get("remaining_gates") != expected_remaining_gates:
        failures.append(f"remaining_gates={qualification.get('remaining_gates')!r}")
    if qualification_status == "qualified":
        human_review = qualification.get("human_review", {})
        if (
            human_review.get("status") != "complete_pass"
            or human_review.get("counts_as_completed_human_review") is not True
        ):
            failures.append("required human review is not complete and approved")
    runtime_validation = qualification.get("runtime_package_validation", {})
    if (
        runtime_validation.get("seed_commit_count") != 1
        or runtime_validation.get("seed_has_remotes") is not False
        or runtime_validation.get("task_local_ffi_editable") is not False
    ):
        failures.append("isolated runtime package validation is absent or invalid")
    if expected_eligibility not in candidate.get("execution_eligibility", []):
        failures.append(f"protocol {protocol!r} is not execution-eligible")
    role_statuses = {
        role.get("subproblem_id"): role.get("base_status")
        for role in qualification.get("role_local_observability", [])
    }
    expected_roles = {
        role.get("subproblem_id") for role in candidate.get("natural_subproblems", [])
    }
    if set(role_statuses) != expected_roles:
        failures.append("role-local base evidence does not cover every subproblem")
    for subproblem_id, status in role_statuses.items():
        if status != "base_red":
            failures.append(
                f"role {subproblem_id!r} has base observability status {status!r}"
            )
    for checker in qualification.get("dependency_checkers", []):
        bad_groups = [
            group
            for group in ("upstream", "downstream", "integrated")
            if checker.get(group) != "passed"
        ]
        if bad_groups:
            failures.append(
                f"checker {checker.get('dependency_id')!r} failed/unverified groups: "
                + ", ".join(bad_groups)
            )

    if failures and not allow_unqualified:
        detail = "\n  - ".join(failures)
        raise RuntimeError(
            "PR-hard qualification preflight refused to start this run:\n"
            f"  - {detail}\n"
            "This candidate may only be run with --allow_unqualified=True for "
            "explicitly non-official diagnostics."
        )
    return candidate, qualification, failures


def _execution_profile(protocol):
    profile = _read_json(
        _repo_root() / "configs/evaluation/official_execution_profile.v2.json"
    )
    return profile, profile["protocols"][protocol]


def _default_output_dir(task, model, protocol, run_id=None):
    run_id = run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return (
        Path("outputs")
        / "pr_hard"
        / "v0.4"
        / _safe_component(model)
        / _safe_component(task.repository_name)
        / protocol
        / _safe_component(run_id)
    )


def _write_candidate_status(
    output_dir,
    status,
    remaining_gates,
    official_result_eligible=False,
    detail=None,
):
    payload = {
        "schema_version": "pr-hard-run-status-v0.4",
        "status": status,
        "official_result_eligible": bool(official_result_eligible),
        "remaining_construction_gates": list(remaining_gates),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if detail:
        payload["detail"] = str(detail)
    path = Path(output_dir) / "candidate_status.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def main(
    task_id="pr-hard:apache-tvm-19605",
    protocol="single",
    model=None,
    subagent_model=None,
    max_iterations=None,
    max_subagents=None,
    sub_iterations=None,
    rounds_of_chat=None,
    output_dir=None,
    run_id=None,
    runtime_root="",
    build_cache_root="",
    agent="openhands",
    agent_import_path=None,
    agent_config_json=None,
    dry_run=False,
    allow_unqualified=False,
):
    if protocol not in SUPPORTED_PROTOCOLS:
        choices = ", ".join(sorted(SUPPORTED_PROTOCOLS))
        raise ValueError(f"Unsupported protocol={protocol!r}; choose from: {choices}")
    model = model or os.getenv("LLM_MODEL")
    if not model:
        raise ValueError("A model is required via --model or LLM_MODEL")
    subagent_model = subagent_model or os.getenv("LLM_SUBAGENT_MODEL")
    candidate, qualification, qualification_failures = _candidate_preflight(
        task_id, protocol, allow_unqualified=bool(allow_unqualified)
    )
    official_result_eligible = (
        candidate.get("qualification_status") == "qualified"
        and qualification.get("automated_status") == "passed"
        and qualification.get("human_review", {}).get("status") == "complete_pass"
        and qualification.get("remaining_gates") == []
        and not qualification_failures
    )
    execution_profile, protocol_profile = _execution_profile(protocol)
    agent_adapter = load_agent_adapter(
        agent=agent,
        agent_import_path=agent_import_path,
        agent_config_json=agent_config_json,
    )

    task = PrHardTask(
        PrHardConfig(
            task_id=task_id,
            runtime_root=runtime_root,
            build_cache_root=build_cache_root,
        )
    )
    task.set_active_protocol(protocol)
    scenario = task.scenario_for(protocol)
    declared_agents = int(scenario.get("agent_count", 1))
    if max_subagents is None:
        max_subagents = declared_agents
    if int(max_subagents) != declared_agents:
        raise ValueError(
            f"Scenario declares {declared_agents} agents, got {max_subagents}"
        )
    scenario_steps = int(scenario.get("step_budget_per_agent", 24))
    profile_manager_iterations = int(protocol_profile["manager_max_iterations"])
    profile_subagent_iterations = int(protocol_profile["subagent_max_iterations"])
    profile_rounds = int(protocol_profile["max_rounds_chat"])
    max_iterations = (
        profile_manager_iterations if max_iterations is None else int(max_iterations)
    )
    sub_iterations = (
        profile_subagent_iterations if sub_iterations is None else int(sub_iterations)
    )
    rounds_of_chat = profile_rounds if rounds_of_chat is None else int(rounds_of_chat)
    if not allow_unqualified:
        observed = (max_iterations, sub_iterations, rounds_of_chat)
        expected = (
            profile_manager_iterations,
            profile_subagent_iterations,
            profile_rounds,
        )
        if observed != expected:
            raise ValueError(
                "Benchmark runs must match the frozen execution profile: "
                f"manager={expected[0]}, subagent={expected[1]}, rounds={expected[2]}; "
                f"got manager={observed[0]}, subagent={observed[1]}, rounds={observed[2]}"
            )

    workflow_config = WorkflowConfig(
        model=model,
        subagent_model=subagent_model,
        manager_max_iterations=max_iterations,
        max_subagents=int(max_subagents),
        subagent_max_iterations=sub_iterations,
        max_rounds_chat=rounds_of_chat,
    )
    resolved_output = (
        Path(output_dir)
        if output_dir
        else _default_output_dir(task, model, protocol, run_id)
    ).resolve()
    workflow_config.output_dir = str(resolved_output)

    if dry_run:
        print("[DryRun] harness=asyncodebench-pr-hard-v0.4-candidate")
        print(f"[DryRun] task_id={task.task_id}")
        print(f"[DryRun] protocol={protocol}")
        print(f"[DryRun] scenario_id={scenario.get('scenario_id')}")
        print(f"[DryRun] declared_agents={declared_agents}")
        print(f"[DryRun] construction_step_budget_per_agent={scenario_steps}")
        print(f"[DryRun] execution_profile_id={execution_profile['profile_id']}")
        print(f"[DryRun] manager_max_iterations={max_iterations}")
        print(f"[DryRun] subagent_max_iterations={sub_iterations}")
        print(f"[DryRun] max_rounds_chat={rounds_of_chat}")
        print(f"[DryRun] model_visible_seed={task.seed_path}")
        print(f"[DryRun] output_dir={resolved_output}")
        print(f"[DryRun] qualification_status={candidate['qualification_status']}")
        print(f"[DryRun] remaining_gates={qualification.get('remaining_gates', [])}")
        if qualification_failures:
            print("[DryRun] diagnostic_only=True")
            for failure in qualification_failures:
                print(f"[DryRun] qualification_failure={failure}")
        print(f"[DryRun] official_result_eligible={official_result_eligible}")
        return

    _assert_openhands_runtime_consistency()
    _assert_fresh_output(resolved_output)
    prompt_path = Path(__file__).resolve().parent / "prompts" / "asyncodebench.yaml"
    metadata = build_run_metadata(
        task,
        workflow_config,
        protocol,
        prompt_path,
        agent_adapter=agent_adapter.public_metadata(),
    )
    metadata["candidate_lane"] = {
        "kind": "pr_hard_v0.4",
        "official_result_eligible": official_result_eligible,
        "remaining_gates": qualification.get("remaining_gates", []),
        "qualification_status": candidate.get("qualification_status"),
        "diagnostic_only": bool(qualification_failures),
        "model_visible_history": False,
        "model_visible_gold_patch": False,
    }
    write_run_metadata(resolved_output, metadata)
    write_contract_snapshots(resolved_output, task, protocol)
    remaining_gates = qualification.get("remaining_gates", [])
    _write_candidate_status(
        resolved_output,
        "running",
        remaining_gates,
        official_result_eligible=official_result_eligible,
    )

    try:
        if protocol in {"serial_specialists", "async_private"}:
            runner = AsynCodeBenchProtocolRunner(
                task_module=task,
                workflow_config=workflow_config,
                protocol=protocol,
                agent_adapter=agent_adapter,
            )
            result = asyncio.run(runner.run())
        else:
            workflow_kwargs = {}
            if protocol == "caid_manager":
                workflow_kwargs["manager_class"] = AsynCodeBenchManager
            result = asyncio.run(
                run_workflow(
                    "asyncodebench",
                    workflow_config,
                    task,
                    multi_agent=protocol == "caid_manager",
                    agent_adapter=agent_adapter,
                    **workflow_kwargs,
                )
            )
        try:
            _generate_process_metrics(task, resolved_output)
        except Exception as exc:
            (resolved_output / "process_metrics_generation_error.txt").write_text(
                str(exc) + "\n"
            )
            raise
        _write_candidate_status(
            resolved_output,
            "completed",
            remaining_gates,
            official_result_eligible=official_result_eligible,
        )
        _finalize_run_bundle(task, resolved_output, protocol, agent_adapter)
        return result
    except BaseException as exc:
        _write_candidate_status(
            resolved_output,
            "failed",
            remaining_gates,
            official_result_eligible=official_result_eligible,
            detail=exc,
        )
        raise
    finally:
        task.cleanup_build_cache()


if __name__ == "__main__":
    fire.Fire(main)
