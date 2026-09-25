#!/usr/bin/env python3
"""Build the public AsynCodeBench release index from frozen task artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RELEASE = "v0.3"
RELEASE_VERSION = "0.3.0"
RELEASE_DIR = ROOT / "manifests" / "release" / RELEASE
OFFICIAL_CONFIG = ROOT / "configs" / "tasks" / "commit0_official_tasks.v0.3.json"
CURATED_CONFIG = ROOT / "configs" / "tasks" / "commit0_curated_tasks.v0.3.json"
EXECUTION_PROFILE = (
    ROOT / "configs" / "evaluation" / "official_execution_profile.v2.json"
)
VALIDATED_BASELINES = RELEASE_DIR / "validated_baselines.json"
EXPECTED_MODES = {
    "iterative_single": "single",
    "serial_specialists": "serial_specialists",
    "async_private": "async_private",
    "async_message": "caid_manager",
}
HUMAN_REVIEW_POLICY = {
    "policy_id": "single-human-plus-automated-audit-v1",
    "required_human_review_count_per_task": 1,
    "required_human_annotation_artifact": "annotation_a",
    "automated_audit_required": True,
    "automated_audit_counts_as_human": False,
    "secondary_human_annotation_required": False,
    "adjudication_required": False,
}
ALLOWED_PARALLELIZABILITY_LABELS = {
    "parallelizable",
    "partially_parallelizable",
    "effectively_serial",
}
PLACEHOLDER_ANNOTATOR_IDS = {
    "annotator_a",
    "annotator_b",
    "human_annotator",
    "independent_annotator",
}


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def artifact_paths(repository: str) -> dict[str, Path]:
    stem = repository.replace("-", "_")
    base = ROOT / "manifests" / "pilot" / "v0.3"
    annotation_base = (
        ROOT / "manifests" / "annotations" / "asyncodebench_v0.3" / stem
    )
    return {
        "task": base / "tasks" / f"commit0_{stem}.json",
        "scenarios": base / "scenarios" / f"commit0_{stem}.json",
        "metrics": base / "metrics" / f"commit0_{stem}_async_metrics.json",
        "quality": base / "quality" / f"commit0_{stem}.json",
        "annotation_a": annotation_base / "annotator_a.json",
        "annotation_b": annotation_base / "annotator_b.json",
        "annotation_audit": annotation_base / "annotator_codex_audit.json",
        "adjudication_template": annotation_base / "adjudication.template.json",
    }


def public_scenario_id(source_scenario_id: str) -> str:
    if source_scenario_id.startswith("commit0-"):
        return "asyncodebench-" + source_scenario_id[len("commit0-") :]
    return source_scenario_id


def annotation_decision_complete(document: dict, *, require_human_id=False) -> bool:
    include = document.get("include")
    label = document.get("parallelizability_label")
    rationale = document.get("rationale")
    exclusion_reason = document.get("exclusion_reason")
    annotator_id = str(document.get("annotator_id", "")).strip()
    if not isinstance(include, bool):
        return False
    if label not in ALLOWED_PARALLELIZABILITY_LABELS:
        return False
    if not isinstance(rationale, str) or not rationale.strip():
        return False
    if include and exclusion_reason not in {None, ""}:
        return False
    if not include and (
        not isinstance(exclusion_reason, str) or not exclusion_reason.strip()
    ):
        return False
    if not annotator_id:
        return False
    return not (
        require_human_id and annotator_id.lower() in PLACEHOLDER_ANNOTATOR_IDS
    )


def build_release_documents() -> tuple[dict, dict]:
    official_config = read_json(OFFICIAL_CONFIG)
    execution_profile = read_json(EXECUTION_PROFILE)
    validated_baselines = read_json(VALIDATED_BASELINES)
    baseline_bundles = validated_baselines.get("bundles", [])
    if validated_baselines.get("release") != RELEASE:
        raise ValueError("validated baseline registry targets the wrong release")
    for baseline in baseline_bundles:
        bundle_path = ROOT / baseline["path"]
        if not bundle_path.is_file() or sha256(bundle_path) != baseline["sha256"]:
            raise ValueError(f"invalid validated baseline bundle: {baseline['path']}")
    repositories = official_config["official_tasks"]
    if len(repositories) != 15 or len(set(repositories)) != 15:
        raise ValueError("The core release must contain exactly 15 unique tasks")

    curated_records = {
        record["repository"]: record
        for record in read_json(CURATED_CONFIG).get("tasks", [])
    }
    tasks = []
    total_scenarios = 0
    total_dependencies = 0
    human_review_complete_tasks = 0
    human_review_passed_tasks = 0
    automated_audit_complete_tasks = 0

    for repository in repositories:
        paths = artifact_paths(repository)
        missing = [relative(path) for path in paths.values() if not path.is_file()]
        if missing:
            raise FileNotFoundError(
                f"Missing release artifacts for {repository}: {', '.join(missing)}"
            )

        task = read_json(paths["task"])
        scenario_document = read_json(paths["scenarios"])
        metrics = read_json(paths["metrics"])
        quality = read_json(paths["quality"])
        annotation_a = read_json(paths["annotation_a"])
        annotation_b = read_json(paths["annotation_b"])
        annotation_audit = read_json(paths["annotation_audit"])
        adjudication = read_json(paths["adjudication_template"])
        curated = curated_records.get(repository)
        if curated is None:
            raise ValueError(f"Missing curated source record for {repository}")

        overlay_records = []
        for overlay in curated.get("overlays", []) or []:
            overlay_path = ROOT / overlay["path"]
            if not overlay_path.is_file():
                raise FileNotFoundError(
                    f"Missing release overlay for {repository}: {overlay['path']}"
                )
            actual_sha = sha256(overlay_path)
            if actual_sha != overlay.get("sha256"):
                raise ValueError(
                    f"Overlay checksum mismatch for {repository}: "
                    f"{overlay['path']}"
                )
            overlay_records.append(
                {
                    "path": relative(overlay_path),
                    "sha256": actual_sha,
                    "rationale": overlay.get("rationale"),
                }
            )

        scenarios = scenario_document.get("scenarios", [])
        modes = {scenario.get("execution_mode") for scenario in scenarios}
        if modes != set(EXPECTED_MODES):
            raise ValueError(
                f"{repository} must define {sorted(EXPECTED_MODES)}, "
                f"found {sorted(modes)}"
            )

        protocol_scenarios = {}
        for scenario in scenarios:
            mode = scenario["execution_mode"]
            protocol = EXPECTED_MODES[mode]
            protocol_scenarios[protocol] = {
                "scenario_id": public_scenario_id(scenario["scenario_id"]),
                "source_scenario_id": scenario["scenario_id"],
                "execution_mode": mode,
                "agent_count": scenario["agent_count"],
                "concurrent_execution": scenario["concurrent_execution"],
                "communication_condition": scenario["communication_condition"],
            }

        dependency_points = metrics.get("dependency_points", [])
        annotator_a_complete = annotation_decision_complete(
            annotation_a, require_human_id=True
        )
        annotator_b_complete = annotation_decision_complete(
            annotation_b, require_human_id=True
        )
        automated_audit_complete = annotation_decision_complete(annotation_audit)
        human_annotations_agree = annotator_a_complete and annotator_b_complete and (
            annotation_a.get("include"),
            annotation_a.get("parallelizability_label"),
        ) == (
            annotation_b.get("include"),
            annotation_b.get("parallelizability_label"),
        )
        adjudication_complete = annotation_decision_complete(adjudication)
        human_review_complete = annotator_a_complete
        human_review_passed = human_review_complete and bool(
            annotation_a.get("include")
        )
        human_automated_audit_agree = (
            human_review_complete
            and automated_audit_complete
            and (
                annotation_a.get("include"),
                annotation_a.get("parallelizability_label"),
            )
            == (
                annotation_audit.get("include"),
                annotation_audit.get("parallelizability_label"),
            )
        )
        if human_review_complete:
            human_review_complete_tasks += 1
        if human_review_passed:
            human_review_passed_tasks += 1
        if automated_audit_complete:
            automated_audit_complete_tasks += 1

        if not human_review_complete:
            human_review_status = "pending_required_human_review"
        elif human_review_passed:
            human_review_status = "complete_pass"
        else:
            human_review_status = "complete_reject"

        total_scenarios += len(scenarios)
        total_dependencies += len(dependency_points)
        tasks.append(
            {
                "task_id": f"asyncodebench:{repository}",
                "source_task_id": task["task_id"],
                "repository": repository,
                "source": {
                    "benchmark": task.get("task_source", "Commit0"),
                    "repository": curated["repository"],
                    "base_ref": curated["base_ref"],
                    "base_sha": curated["base_sha"],
                    "overlay_count": len(overlay_records),
                    "overlays": overlay_records,
                },
                "parallelizability": (
                    annotation_a.get("parallelizability_label")
                    if human_review_complete
                    else task.get("proposed_parallelizability_label")
                ),
                "annotation_status": {
                    "policy_id": HUMAN_REVIEW_POLICY["policy_id"],
                    "required_human_review_count": 1,
                    "completed_human_review_count": int(annotator_a_complete),
                    "required_human_annotation_artifact": "annotation_a",
                    "annotator_a_complete": annotator_a_complete,
                    "annotator_b_complete": annotator_b_complete,
                    "secondary_human_annotation_required": False,
                    "automated_audit_complete": automated_audit_complete,
                    "automated_audit_counts_as_human": False,
                    "human_automated_audit_agree": human_automated_audit_agree,
                    "human_annotations_agree": human_annotations_agree,
                    "adjudication_required": False,
                    "adjudication_complete": adjudication_complete,
                    "human_review_complete": human_review_complete,
                    "human_review_passed": human_review_passed,
                    "status": human_review_status,
                },
                "protocols": protocol_scenarios,
                "dependency_point_count": len(dependency_points),
                "artifacts": {
                    name: {"path": relative(path), "sha256": sha256(path)}
                    for name, path in paths.items()
                },
                "quality_status": quality.get("quality_status")
                or quality.get("status")
                or quality.get("qualification_status"),
            }
        )

    community_preview_ready = automated_audit_complete_tasks == len(tasks) and all(
        task["quality_status"] == "qualification_ready" for task in tasks
    )
    stable_release_ready = (
        community_preview_ready
        and human_review_passed_tasks == len(tasks)
        and bool(baseline_bundles)
    )
    release_stage = "stable" if stable_release_ready else "community_preview"

    common_status = {
        "release_stage": release_stage,
        "community_preview_ready": community_preview_ready,
        "stable_release_ready": stable_release_ready,
        "human_review_policy": HUMAN_REVIEW_POLICY,
        "validated_baseline_bundle_count": len(baseline_bundles),
        "validated_baseline_registry": {
            "path": relative(VALIDATED_BASELINES),
            "sha256": sha256(VALIDATED_BASELINES),
        },
    }
    official = {
        "schema_version": "asyncodebench-release-tasks-v1",
        "release": RELEASE,
        "release_version": RELEASE_VERSION,
        "task_namespace": "asyncodebench",
        "task_count": len(tasks),
        "human_review_complete_task_count": human_review_complete_tasks,
        "human_review_passed_task_count": human_review_passed_tasks,
        "automated_audit_complete_task_count": automated_audit_complete_tasks,
        "official_task_ids": [task["task_id"] for task in tasks],
        "execution_profile": {
            "profile_id": execution_profile["profile_id"],
            "path": relative(EXECUTION_PROFILE),
            "sha256": sha256(EXECUTION_PROFILE),
        },
        **common_status,
    }
    index = {
        "schema_version": "asyncodebench-task-index-v1",
        "release": RELEASE,
        "release_version": RELEASE_VERSION,
        "task_count": len(tasks),
        "scenario_count": total_scenarios,
        "dependency_point_count": total_dependencies,
        "human_review_complete_task_count": human_review_complete_tasks,
        "human_review_passed_task_count": human_review_passed_tasks,
        "automated_audit_complete_task_count": automated_audit_complete_tasks,
        "protocols": list(EXPECTED_MODES.values()),
        "execution_profile": {
            "profile_id": execution_profile["profile_id"],
            "path": relative(EXECUTION_PROFILE),
            "sha256": sha256(EXECUTION_PROFILE),
        },
        **common_status,
        "tasks": tasks,
    }
    return official, index


def encoded(document: dict) -> str:
    return json.dumps(document, indent=2, sort_keys=True) + "\n"


def output_documents() -> dict[Path, str]:
    official, index = build_release_documents()
    return {
        RELEASE_DIR / "official_tasks.json": encoded(official),
        RELEASE_DIR / "task_index.json": encoded(index),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail when checked-in release files differ from generated content.",
    )
    args = parser.parse_args()

    documents = output_documents()
    if args.check:
        stale = [
            relative(path)
            for path, content in documents.items()
            if not path.is_file() or path.read_text(encoding="utf-8") != content
        ]
        if stale:
            parser.error(
                "release index is missing or stale: "
                + ", ".join(stale)
                + "; run scripts/build_release_index.py"
            )
        print("Release index is current")
        return 0

    RELEASE_DIR.mkdir(parents=True, exist_ok=True)
    for path, content in documents.items():
        path.write_text(content, encoding="utf-8")
        print(relative(path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
