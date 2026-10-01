#!/usr/bin/env python3
"""Build the unified 19-task AsynCodeBench v0.4 community-preview index."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
V03_INDEX = ROOT / "manifests/release/v0.3/task_index.json"
REGISTRY = ROOT / "configs/tasks/pr_hard_candidates.v0.4.json"
BASELINES = ROOT / "manifests/release/v0.4/validated_baselines.json"
OUTPUT_DIR = ROOT / "manifests/release/v0.4"
TASK_INDEX = OUTPUT_DIR / "task_index.json"
OFFICIAL_TASKS = OUTPUT_DIR / "official_tasks.json"
ADDED_TASK_IDS = (
    "pr-hard:apache-tvm-20018",
    "pr-hard:apache-tvm-20073",
    "pr-hard:apache-tvm-20107",
    "pr-hard:apache-tvm-20153",
)
PROTOCOL_NAMES = {
    "iterative_single": "single",
    "serial_specialists": "serial_specialists",
    "async_private": "async_private",
    "async_message": "caid_manager",
}
HUMAN_POLICY = {
    "policy_id": "single-human-plus-automated-audit-v1",
    "required_human_review_count_per_task": 1,
    "required_human_annotation_artifact": "annotation_a",
    "secondary_human_annotation_required": False,
    "adjudication_required": False,
    "automated_audit_required": True,
    "automated_audit_counts_as_human": False,
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def artifact(path: Path) -> dict[str, str]:
    return {
        "path": str(path.relative_to(ROOT)),
        "sha256": sha256(path),
    }


def validate_baselines(root: Path, registry: dict, task_ids: set[str], validate_fn=None) -> int:
    """Count only in-tree bundles that pass the official result validator."""
    if registry.get("schema_version") != "asyncodebench-validated-baselines-v1" or registry.get("release") != "v0.4":
        raise ValueError("invalid v0.4 baseline registry header")
    bundles = registry.get("bundles")
    if not isinstance(bundles, list):
        raise ValueError("baseline registry bundles must be a list")
    if bundles and validate_fn is None:
        runner = root / "reproductions/async-swe-agents"
        sys.path.insert(0, str(runner))
        from asyncodebench_harness.results import validate_run_bundle

        validate_fn = validate_run_bundle
    seen = set()
    baseline_dir = (root / "manifests/release/v0.4/baselines").resolve()
    for entry in bundles:
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
            raise ValueError("baseline entry requires a repository-relative path")
        name = entry["path"]
        path = (root / name).resolve()
        if Path(name).is_absolute() or path.name != "run_bundle.json" or not path.is_relative_to(baseline_dir) or name in seen:
            raise ValueError(f"invalid or duplicate baseline path: {name}")
        seen.add(name)
        digest = entry.get("sha256")
        if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
            raise ValueError(f"invalid baseline checksum: {name}")
        if not path.is_file() or sha256(path) != digest:
            raise ValueError(f"baseline bundle checksum mismatch: {name}")
        previous_root = os.environ.get("ASYNCODEBENCH_ROOT")
        os.environ["ASYNCODEBENCH_ROOT"] = str(root.resolve())
        try:
            result = validate_fn(path.parent)
        finally:
            if previous_root is None:
                os.environ.pop("ASYNCODEBENCH_ROOT", None)
            else:
                os.environ["ASYNCODEBENCH_ROOT"] = previous_root
        if result.get("status") != "valid" or not result.get("eligibility", {}).get("official_aggregate"):
            raise ValueError(f"baseline does not pass official validation: {name}: {result.get('issues')}")
        if result.get("task_id") not in task_ids:
            raise ValueError(f"baseline task is outside the v0.4 release: {name}")
    return len(bundles)


def added_entry(record: dict) -> dict:
    source_id = record["task_id"]
    slug = source_id.removeprefix("pr-hard:")
    stem = slug.replace("-", "_")
    public_task_id = f"asyncodebench:{slug}"
    task_path = ROOT / "manifests/candidates/pr_hard_v0.4/tasks" / f"{stem}.json"
    scenario_path = ROOT / record["scenario_manifest"]
    metrics_path = (
        ROOT
        / "manifests/candidates/pr_hard_v0.4/metrics"
        / f"{stem}_async_metrics.json"
    )
    qualification_path = ROOT / record["qualification_record"]
    annotation_path = (
        ROOT
        / "manifests/annotations/pr_hard_v0.4"
        / stem
        / "annotator_a.json"
    )
    task = load_json(task_path)
    scenario_manifest = load_json(scenario_path)
    metrics = load_json(metrics_path)
    qualification = load_json(qualification_path)
    annotation = load_json(annotation_path)

    if record["qualification_status"] != "qualified":
        raise ValueError(f"{source_id} is not qualified")
    if task["official_result_eligible"] is not True:
        raise ValueError(f"{source_id} is not result eligible")
    if qualification["automated_status"] != "passed":
        raise ValueError(f"{source_id} automated qualification has not passed")
    if qualification["human_review"]["status"] != "complete_pass":
        raise ValueError(f"{source_id} human review has not passed")
    if annotation["include"] is not True:
        raise ValueError(f"{source_id} annotation does not approve inclusion")

    protocols = {}
    for scenario in scenario_manifest["scenarios"]:
        if scenario["official_result_eligible"] is not True:
            raise ValueError(f"{scenario['scenario_id']} is not result eligible")
        protocol = PROTOCOL_NAMES[scenario["execution_mode"]]
        protocols[protocol] = {
            "agent_count": scenario["agent_count"],
            "communication_condition": scenario["communication_condition"],
            "concurrent_execution": scenario["concurrent_execution"],
            "execution_mode": scenario["execution_mode"],
            "scenario_id": scenario["scenario_id"],
            "source_scenario_id": scenario["scenario_id"],
        }

    overlays = [
        record["public_test_overlay"],
        *record.get("supplemental_public_test_overlays", []),
    ]
    return {
        "annotation_status": {
            "adjudication_complete": False,
            "adjudication_required": False,
            "annotator_a_complete": True,
            "annotator_b_complete": False,
            "automated_audit_complete": True,
            "automated_audit_counts_as_human": False,
            "completed_human_review_count": 1,
            "human_annotations_agree": None,
            "human_automated_audit_agree": True,
            "human_review_complete": True,
            "human_review_passed": True,
            "policy_id": HUMAN_POLICY["policy_id"],
            "required_human_annotation_artifact": "annotation_a",
            "required_human_review_count": 1,
            "secondary_human_annotation_required": False,
            "status": "complete_pass",
        },
        "artifacts": {
            "annotation_a": artifact(annotation_path),
            "metrics": artifact(metrics_path),
            "qualification": artifact(qualification_path),
            "scenarios": artifact(scenario_path),
            "task": artifact(task_path),
        },
        "dependency_point_count": len(metrics["dependency_points"]),
        "official_result_eligible": True,
        "parallelizability": annotation["parallelizability_label"],
        "protocols": protocols,
        "quality_status": "qualification_ready",
        "repository": record["repository"],
        "source": {
            "base_sha": record["base_sha"],
            "overlay_count": len(overlays),
            "overlays": overlays,
            "repository": record["repository"],
            "transformation": "pinned incomplete repository plus answer-free public test overlays",
        },
        "source_task_id": source_id,
        "task_id": public_task_id,
    }


def build_documents() -> tuple[dict, dict]:
    v03 = load_json(V03_INDEX)
    registry = load_json(REGISTRY)
    records = {record["task_id"]: record for record in registry["records"]}
    tasks = []
    for entry in v03["tasks"]:
        copied = dict(entry)
        copied["official_result_eligible"] = True
        tasks.append(copied)
    tasks.extend(added_entry(records[task_id]) for task_id in ADDED_TASK_IDS)

    baseline_registry = artifact(BASELINES)
    baseline_count = validate_baselines(
        ROOT, load_json(BASELINES), {task["task_id"] for task in tasks}
    )
    community_preview_ready = all(
        task["quality_status"] == "qualification_ready"
        and task["annotation_status"]["automated_audit_complete"]
        for task in tasks
    )
    stable_release_ready = (
        community_preview_ready
        and all(task["annotation_status"]["human_review_passed"] for task in tasks)
        and baseline_count > 0
    )
    execution_profile = dict(v03["execution_profile"])
    common = {
        "automated_audit_complete_task_count": sum(
            bool(task["annotation_status"]["automated_audit_complete"])
            for task in tasks
        ),
        "community_preview_ready": community_preview_ready,
        "execution_profile": execution_profile,
        "human_review_complete_task_count": sum(
            bool(task["annotation_status"]["human_review_complete"])
            for task in tasks
        ),
        "human_review_passed_task_count": sum(
            bool(task["annotation_status"]["human_review_passed"])
            for task in tasks
        ),
        "human_review_policy": HUMAN_POLICY,
        "release": "v0.4",
        "release_stage": "stable" if stable_release_ready else "community_preview",
        "release_version": "0.4.1",
        "stable_release_ready": stable_release_ready,
        "task_count": len(tasks),
        "validated_baseline_bundle_count": baseline_count,
        "validated_baseline_registry": baseline_registry,
    }
    index = {
        **common,
        "dependency_point_count": sum(
            task["dependency_point_count"] for task in tasks
        ),
        "protocols": list(v03["protocols"]),
        "scenario_count": sum(len(task["protocols"]) for task in tasks),
        "online_protocols": ["async_manager"],
        "online_scenario_count": len(tasks),
        "total_protocol_condition_count": sum(
            len(task["protocols"]) for task in tasks
        )
        + len(tasks),
        "schema_version": "asyncodebench-task-index-v1",
        "tasks": tasks,
    }
    official = {
        **common,
        "official_task_ids": [task["task_id"] for task in tasks],
        "schema_version": "asyncodebench-release-tasks-v1",
        "task_namespace": "asyncodebench",
    }
    if (len(tasks), index["scenario_count"], index["dependency_point_count"]) != (
        19,
        76,
        53,
    ):
        raise ValueError("unexpected unified v0.4 release composition")
    return index, official


def render(document: dict) -> str:
    return json.dumps(document, indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    index, official = build_documents()
    expected = {TASK_INDEX: render(index), OFFICIAL_TASKS: render(official)}
    if args.check:
        stale = [path for path, text in expected.items() if not path.exists() or path.read_text(encoding="utf-8") != text]
        if stale:
            for path in stale:
                print(f"stale: {path.relative_to(ROOT)}")
            return 1
        print("AsynCodeBench v0.4 release index is current")
        return 0
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for path, text in expected.items():
        path.write_text(text, encoding="utf-8")
        print(f"Wrote {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
