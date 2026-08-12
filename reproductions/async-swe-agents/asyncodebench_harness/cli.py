"""Command-line interface for running and validating AsynCodeBench."""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from .health import inspect_run
from .results import validate_run_bundle

PROTOCOL_ORDER = (
    "single",
    "serial_specialists",
    "async_private",
    "caid_manager",
)


def _repo_root():
    configured = os.getenv("ASYNCODEBENCH_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()
    return Path(__file__).resolve().parents[3]


def _release_index():
    path = _repo_root() / "manifests" / "release" / "v0.3" / "task_index.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _tasks(args):
    index = _release_index()
    tasks = index.get("tasks", [])
    if args.json:
        print(json.dumps(tasks, indent=2, sort_keys=True))
        return 0
    print("TASK ID\tAGENTS\tDEPENDENCIES")
    for task in tasks:
        counts = sorted(
            {
                protocol.get("agent_count", 0)
                for protocol in task.get("protocols", {}).values()
            }
        )
        print(
            f"{task['task_id']}\t{','.join(map(str, counts))}\t"
            f"{task.get('dependency_point_count', 0)}"
        )
    return 0


def _release_status(args):
    index = _release_index()
    tasks = index.get("tasks", [])
    pending_human_review = [
        task.get("task_id")
        for task in tasks
        if not task.get("annotation_status", {}).get("human_review_complete")
    ]
    payload = {
        "benchmark": "AsynCodeBench",
        "release": index.get("release"),
        "release_version": index.get("release_version"),
        "task_count": index.get("task_count", 0),
        "scenario_count": index.get("scenario_count", 0),
        "dependency_point_count": index.get("dependency_point_count", 0),
        "bootstrap_overlay_count": sum(
            task.get("source", {}).get("overlay_count", 0) for task in tasks
        ),
        "automated_audit_complete_task_count": index.get(
            "automated_audit_complete_task_count", 0
        ),
        "human_review_complete_task_count": index.get(
            "human_review_complete_task_count", 0
        ),
        "pending_human_review_task_ids": pending_human_review,
        "executable_release_complete": len(tasks) == 16
        and all(task.get("quality_status") == "qualification_ready" for task in tasks),
        "human_validation_complete": not pending_human_review,
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    print(f"AsynCodeBench {payload['release']} ({payload['release_version']})")
    print(
        f"tasks={payload['task_count']} scenarios={payload['scenario_count']} "
        f"dependencies={payload['dependency_point_count']} "
        f"overlays={payload['bootstrap_overlay_count']}"
    )
    print(
        "automated_audit="
        f"{payload['automated_audit_complete_task_count']}/{payload['task_count']} "
        "human_review="
        f"{payload['human_review_complete_task_count']}/{payload['task_count']}"
    )
    if pending_human_review:
        print("pending_human_review=" + ",".join(pending_human_review))
    return 0


def _run_one(args, protocol, output_dir, run_id):
    if args.dry_run:
        os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")
    from run_asyncodebench import main as run_benchmark

    return run_benchmark(
        task_id=args.task,
        protocol=protocol,
        model=args.model,
        subagent_model=args.subagent_model,
        max_iterations=args.max_iterations,
        sub_iterations=args.sub_iterations,
        rounds_of_chat=args.rounds_of_chat,
        output_dir=output_dir,
        run_id=run_id,
        release=args.release,
        agent=args.agent,
        agent_import_path=args.agent_import_path,
        agent_config_json=args.agent_config_json,
        dry_run=args.dry_run,
    )


def _run(args):
    if args.protocol != "all":
        return _run_one(args, args.protocol, args.output_dir, args.run_id)

    run_id = args.run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    for protocol in PROTOCOL_ORDER:
        output_dir = None
        if args.output_dir:
            output_dir = str(Path(args.output_dir) / protocol / run_id)
        _run_one(args, protocol, output_dir, run_id)
    return 0


def _validate(args):
    result = validate_run_bundle(args.run_dir, verify_checksums=not args.skip_checksums)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["valid"] else 1


def _inspect(args):
    results = [inspect_run(Path(run_dir)) for run_dir in args.run_dirs]
    payload = {
        "valid": all(result["status"] == "valid" for result in results),
        "runs": results,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["valid"] else 1


def _doctor(args):
    del args
    checks = []
    checks.append(
        {
            "name": "release_index",
            "ok": (_repo_root() / "manifests/release/v0.3/task_index.json").is_file(),
        }
    )
    checks.append(
        {
            "name": "official_execution_profile",
            "ok": (
                _repo_root() / "configs/evaluation/official_execution_profile.v1.json"
            ).is_file(),
        }
    )
    checks.append(
        {
            "name": "run_bundle_schema",
            "ok": (_repo_root() / "schemas/release/run_bundle.schema.json").is_file(),
        }
    )
    checks.append(
        {
            "name": "sdk_source_dir",
            "ok": Path(
                os.getenv(
                    "SDK_SOURCE_DIR",
                    _repo_root() / "reproductions" / "software-agent-sdk",
                )
            ).is_dir(),
        }
    )
    try:
        docker = subprocess.run(
            ["docker", "info"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        docker_ok = docker.returncode == 0
    except OSError:
        docker_ok = False
    checks.append({"name": "docker", "ok": docker_ok})
    checks.append({"name": "model", "ok": bool(os.getenv("LLM_MODEL"))})
    checks.append({"name": "model_base_url", "ok": bool(os.getenv("LLM_BASE_URL"))})
    print(json.dumps({"checks": checks}, indent=2, sort_keys=True))
    return 0 if all(item["ok"] for item in checks) else 1


def build_parser():
    parser = argparse.ArgumentParser(
        prog="asyncodebench",
        description="Run and validate the AsynCodeBench benchmark.",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    tasks = commands.add_parser("tasks", help="List official release tasks")
    tasks.add_argument("--json", action="store_true")
    tasks.set_defaults(handler=_tasks)

    release_status = commands.add_parser(
        "release-status", help="Show executable and human-review release status"
    )
    release_status.add_argument("--json", action="store_true")
    release_status.set_defaults(handler=_release_status)

    run = commands.add_parser("run", help="Run one task and protocol")
    run.add_argument("--task", required=True, help="asyncodebench:<repository>")
    run.add_argument("--protocol", choices=[*PROTOCOL_ORDER, "all"], required=True)
    run.add_argument("--model", default=os.getenv("LLM_MODEL"))
    run.add_argument("--subagent-model", default=os.getenv("LLM_SUBAGENT_MODEL"))
    run.add_argument("--max-iterations", type=int, default=30)
    run.add_argument("--sub-iterations", type=int, default=30)
    run.add_argument("--rounds-of-chat", type=int, default=2)
    run.add_argument("--output-dir")
    run.add_argument("--run-id")
    run.add_argument("--release", default="v0.3")
    run.add_argument("--agent", default="openhands")
    run.add_argument("--agent-import-path")
    run.add_argument("--agent-config-json")
    run.add_argument("--dry-run", action="store_true")
    run.set_defaults(handler=_run)

    validate = commands.add_parser("validate-run", help="Validate a result bundle")
    validate.add_argument("run_dir")
    validate.add_argument("--skip-checksums", action="store_true")
    validate.set_defaults(handler=_validate)

    inspect = commands.add_parser(
        "inspect-run",
        help="Classify old or new run directories without requiring a bundle",
    )
    inspect.add_argument("run_dirs", nargs="+")
    inspect.set_defaults(handler=_inspect)

    doctor = commands.add_parser("doctor", help="Check the local runtime")
    doctor.set_defaults(handler=_doctor)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.command == "run" and not args.model:
        raise SystemExit("--model or LLM_MODEL is required")
    result = args.handler(args)
    return int(result or 0)


if __name__ == "__main__":
    sys.exit(main())
