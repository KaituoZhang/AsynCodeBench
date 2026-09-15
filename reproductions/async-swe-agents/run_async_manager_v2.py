"""Entry point for the budgeted online Async-Manager policy."""

from __future__ import annotations

import hashlib
import json
import signal
import traceback
from datetime import datetime, timezone
from pathlib import Path

import fire
import protocols.async_manager.checkpoint_bridge as v1_bridge
import protocols.async_manager.manager as v1_manager
import protocols.async_manager.results as v1_results
import protocols.asyncodebench.profile as execution_profile
import run_async_manager as v1_runner
from protocols.async_manager_v2 import BASE_PROTOCOL, POLICY, PROTOCOL
from protocols.async_manager_v2.manager import BudgetedOnlineManager, load_profile
from protocols.async_manager_v2.results import finalize, validate


_V1_PROTOCOL_SOURCES = v1_runner.protocol_sources


class OperatorCancelled(KeyboardInterrupt):
    """Raised when the operator sends SIGTERM to a formal v2 run."""


def protocol_sources() -> list[Path]:
    # Keep the import-time reference: _install_v2_policy replaces the v1
    # module global because its preflight resolves protocol_sources there.
    # Looking it up dynamically here would recurse back into this function.
    sources = list(_V1_PROTOCOL_SOURCES())
    root = Path(__file__).parent
    sources.append(Path(__file__))
    sources.extend(
        path
        for path in (root / "protocols" / "async_manager_v2").iterdir()
        if path.is_file()
    )
    sources.extend((root / "scripts").glob("run_async_manager_v2*.sh"))
    sources.append(
        root.parents[1]
        / "configs"
        / "evaluation"
        / "official_execution_profile.v4.json"
    )
    return sorted(set(sources))


def _install_v2_policy() -> None:
    """Select v2 inside this process without modifying the v1 entry point."""
    v1_runner.POLICY = POLICY
    v1_runner.BASE_PROTOCOL = BASE_PROTOCOL
    v1_runner.OnlineManager = BudgetedOnlineManager
    v1_runner.async_manager_profile = load_profile
    v1_runner.protocol_sources = protocol_sources
    v1_runner.online_checkpoint_bridge = v1_bridge.online_checkpoint_bridge
    v1_runner.finalize = finalize
    v1_runner.validate = validate
    v1_manager.POLICY = POLICY
    v1_manager.OnlineManager = BudgetedOnlineManager
    v1_bridge.OnlineManager = BudgetedOnlineManager
    v1_results.POLICY = POLICY
    execution_profile.ASYNC_MANAGER_PROFILE_RELATIVE_PATH = Path(
        "configs/evaluation/official_execution_profile.v4.json"
    )


def _output_path(task_id: str, model_tag: str, model: str, run_id: str, output_dir):
    if output_dir:
        return Path(output_dir).resolve()
    lane = "pr_hard/v0.4" if task_id.startswith("pr-hard:") else "asyncodebench/v0.3"
    repository = task_id.split(":", 1)[-1]
    tag = v1_runner._safe_component(model_tag or model)
    return (Path("outputs") / lane / tag / repository / PROTOCOL / run_id).resolve()


def _error_classification(error: BaseException) -> str:
    detail = str(error).lower()
    if isinstance(error, (KeyboardInterrupt, OperatorCancelled)):
        return "operator_cancelled"
    if "connection refused" in detail or "remote status polling failed" in detail:
        return "infrastructure_agent_server_unavailable"
    if "timed out" in detail:
        return "infrastructure_or_remote_timeout"
    return "execution_error"


def _write_partial_result(output: Path, error: BaseException) -> None:
    output.mkdir(parents=True, exist_ok=True)
    error_record = {
        "schema_version": "async-manager-execution-error-v2",
        "policy": POLICY,
        "classification": _error_classification(error),
        "type": type(error).__name__,
        "detail": str(error),
        "traceback": traceback.format_exc(),
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "evaluation_complete": False,
    }
    (output / "async_manager_execution_error.json").write_text(
        json.dumps(error_record, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    status = {
        "schema_version": "async-manager-run-status-v1",
        "policy": POLICY,
        "status": error_record["classification"],
        "evaluation_complete": False,
        "metrics_eligible": False,
        "recorded_at": error_record["recorded_at"],
    }
    (output / "run_status.json").write_text(
        json.dumps(status, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    artifacts = {}
    for path in sorted(output.rglob("*")):
        if not path.is_file() or path.name == "partial_run_bundle.json":
            continue
        relative = path.relative_to(output).as_posix()
        artifacts[relative] = {
            "size": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
    partial = {
        "schema_version": "async-manager-partial-bundle-v1",
        "policy": POLICY,
        "status": status["status"],
        "evaluation_complete": False,
        "artifacts": artifacts,
    }
    (output / "partial_run_bundle.json").write_text(
        json.dumps(partial, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


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
    _install_v2_policy()
    if validate_dir:
        return v1_runner.main(validate_dir=validate_dir)
    model = model or v1_runner.os.getenv("LLM_MODEL")
    if not model:
        raise ValueError("Set LLM_MODEL or --model")
    run_id = run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    output = _output_path(task_id, model_tag, model, run_id, output_dir)
    profile = load_profile()
    fixed_parameters = {
        "max_iterations": (
            max_iterations,
            profile["manager_max_iterations_per_event"],
        ),
        "sub_iterations": (
            sub_iterations,
            profile["subagent_max_iterations"],
        ),
        "rounds_of_chat": (
            rounds_of_chat,
            profile["max_rounds_chat"],
        ),
    }
    for name, (requested, expected) in fixed_parameters.items():
        if requested is not None and int(requested) != int(expected):
            raise ValueError(
                f"{name}={requested} conflicts with the frozen v2 profile "
                f"value {expected}"
            )

    previous_sigterm = signal.getsignal(signal.SIGTERM)

    def cancel_on_sigterm(_signum, _frame):
        raise OperatorCancelled("operator requested SIGTERM")

    signal.signal(signal.SIGTERM, cancel_on_sigterm)
    try:
        result = v1_runner.main(
            task_id=task_id,
            model=model,
            subagent_model=subagent_model,
            run_id=run_id,
            model_tag=model_tag,
            max_iterations=max_iterations,
            max_subagents=max_subagents,
            sub_iterations=sub_iterations,
            rounds_of_chat=rounds_of_chat,
            output_dir=str(output),
            release=release,
            docker_image_prefix=docker_image_prefix,
            curated_config_path=curated_config_path,
            agent=agent,
            agent_import_path=agent_import_path,
            agent_config_json=agent_config_json,
            dry_run=dry_run,
            runtime_root=runtime_root,
            build_cache_root=build_cache_root,
            runtime_backend=runtime_backend,
            runtime_image=runtime_image,
            allow_unqualified=allow_unqualified,
        )
        if dry_run:
            print(
                json.dumps(
                    {
                        "async_manager_v2_task_budget": {
                            key: value
                            for key, value in profile.items()
                            if key.startswith("manager_max_")
                        }
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
        return result
    except BaseException as error:
        if not dry_run:
            _write_partial_result(output, error)
        raise
    finally:
        signal.signal(signal.SIGTERM, previous_sigterm)


if __name__ == "__main__":
    fire.Fire(main)
