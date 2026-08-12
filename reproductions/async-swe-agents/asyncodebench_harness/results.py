"""Build and validate portable AsynCodeBench result bundles."""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

RUN_BUNDLE_SCHEMA_VERSION = "0.1"
REQUIRED_ARTIFACTS = (
    "run_metadata.json",
    "task_snapshot.json",
    "scenario_snapshot.json",
    "metrics_snapshot.json",
    "quality_snapshot.json",
    "protocol.json",
    "report.json",
    "dependency_probe_checkpoints.jsonl",
    "process_metrics_summary.json",
    "cost.json",
    "runtime.txt",
)


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path, issues, label):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        issues.append(f"invalid {label}: {exc}")
        return {}


def _nonempty_jsonl(path, issues, label):
    try:
        records = [
            json.loads(line)
            for line in Path(path).read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    except (OSError, json.JSONDecodeError) as exc:
        issues.append(f"invalid {label}: {exc}")
        return 0
    if not records:
        issues.append(f"{label} contains no records")
    return len(records)


def build_run_bundle(task, output_dir, protocol, agent_adapter):
    """Freeze artifact checksums and instrumentation validity after a run."""

    output_dir = Path(output_dir)
    issues = []
    missing = [name for name in REQUIRED_ARTIFACTS if not (output_dir / name).is_file()]
    if missing:
        issues.append("missing required artifacts: " + ", ".join(missing))

    report = (
        _read_json(output_dir / "report.json", issues, "report.json")
        if "report.json" not in missing
        else {}
    )
    report_metadata = report.get("asyncodebench", {})
    evaluator_source = report_metadata.get("final_evaluator_source")
    if evaluator_source != "asyncodebench_manifest":
        issues.append(
            "report.json final_evaluator_source must be asyncodebench_manifest"
        )

    checkpoint_count = 0
    checkpoint_name = "dependency_probe_checkpoints.jsonl"
    if checkpoint_name not in missing:
        checkpoint_count = _nonempty_jsonl(
            output_dir / checkpoint_name,
            issues,
            checkpoint_name,
        )

    artifact_names = sorted(
        path.name
        for path in output_dir.iterdir()
        if path.is_file() and path.name != "run_bundle.json"
    )
    artifacts = {
        name: {
            "sha256": _sha256(output_dir / name),
            "bytes": (output_dir / name).stat().st_size,
        }
        for name in artifact_names
    }
    summary = report.get("summary", {})
    payload = {
        "schema_version": RUN_BUNDLE_SCHEMA_VERSION,
        "benchmark": "AsynCodeBench",
        "release": task.asyncodebench_config.release,
        "task_id": task.task_id,
        "source_task_id": task.source_task_id,
        "protocol": protocol,
        "scenario_id": task.public_scenario_id(protocol),
        "source_scenario_id": task.scenario_for(protocol).get("scenario_id"),
        "agent_adapter": agent_adapter.public_metadata(),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "instrumentation": {
            "valid": not issues,
            "issues": issues,
            "evaluator_source": evaluator_source,
            "dependency_checkpoint_records": checkpoint_count,
        },
        "final_test": {
            "exit_code": report.get("exitcode"),
            "passed": summary.get("passed", 0),
            "failed": summary.get("failed", 0),
            "errors": summary.get("error", summary.get("errors", 0)),
            "collected": summary.get("collected", summary.get("total", 0)),
            "timed_out": report_metadata.get("timed_out", False),
        },
        "artifacts": artifacts,
    }
    path = output_dir / "run_bundle.json"
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return path, payload


def validate_run_bundle(run_dir, verify_checksums=True):
    """Validate one portable result bundle without rerunning the model."""

    run_dir = Path(run_dir)
    issues = []
    bundle_path = run_dir / "run_bundle.json"
    if not bundle_path.is_file():
        return {
            "valid": False,
            "issues": [f"missing run_bundle.json in {run_dir}"],
            "run_dir": str(run_dir),
        }
    bundle = _read_json(bundle_path, issues, "run_bundle.json")
    if bundle.get("schema_version") != RUN_BUNDLE_SCHEMA_VERSION:
        issues.append(
            f"unsupported run bundle schema: {bundle.get('schema_version')!r}"
        )
    if not str(bundle.get("task_id", "")).startswith("asyncodebench:"):
        issues.append("task_id must use the asyncodebench namespace")
    if not bundle.get("instrumentation", {}).get("valid", False):
        recorded = bundle.get("instrumentation", {}).get("issues", [])
        issues.append("bundle records invalid instrumentation: " + "; ".join(recorded))

    artifacts = bundle.get("artifacts", {})
    for name in REQUIRED_ARTIFACTS:
        record = artifacts.get(name)
        path = run_dir / name
        if not path.is_file():
            issues.append(f"missing required artifact: {name}")
            continue
        if not isinstance(record, dict):
            issues.append(f"artifact is not indexed: {name}")
            continue
        if verify_checksums and record.get("sha256") != _sha256(path):
            issues.append(f"artifact checksum mismatch: {name}")

    metadata = _read_json(run_dir / "run_metadata.json", issues, "run_metadata.json")
    protocol = _read_json(run_dir / "protocol.json", issues, "protocol.json")
    report = _read_json(run_dir / "report.json", issues, "report.json")
    _read_json(
        run_dir / "process_metrics_summary.json",
        issues,
        "process_metrics_summary.json",
    )
    for field in ("task_id", "protocol", "scenario_id"):
        expected = bundle.get(field)
        if metadata.get(field) != expected:
            issues.append(f"run_metadata.json {field} does not match run bundle")
        if protocol.get(field) != expected:
            issues.append(f"protocol.json {field} does not match run bundle")
    evaluator_source = report.get("asyncodebench", {}).get(
        "final_evaluator_source"
    )
    if evaluator_source != "asyncodebench_manifest":
        issues.append("report.json does not use the AsynCodeBench manifest evaluator")
    _nonempty_jsonl(
        run_dir / "dependency_probe_checkpoints.jsonl",
        issues,
        "dependency_probe_checkpoints.jsonl",
    )

    return {
        "valid": not issues,
        "issues": issues,
        "run_dir": str(run_dir),
        "task_id": bundle.get("task_id"),
        "protocol": bundle.get("protocol"),
        "final_test": bundle.get("final_test", {}),
    }
