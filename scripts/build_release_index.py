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
EXPECTED_MODES = {
    "iterative_single": "single",
    "serial_specialists": "serial_specialists",
    "async_private": "async_private",
    "async_message": "caid_manager",
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
    return {
        "task": base / "tasks" / f"commit0_{stem}.json",
        "scenarios": base / "scenarios" / f"commit0_{stem}.json",
        "metrics": base / "metrics" / f"commit0_{stem}_async_metrics.json",
        "quality": base / "quality" / f"commit0_{stem}.json",
    }


def build_release_documents() -> tuple[dict, dict]:
    official_config = read_json(OFFICIAL_CONFIG)
    repositories = official_config["official_tasks"]
    if len(repositories) != 16 or len(set(repositories)) != 16:
        raise ValueError("The public release must contain exactly 16 unique tasks")

    curated_records = {
        record["repository"]: record
        for record in read_json(CURATED_CONFIG).get("tasks", [])
    }
    tasks = []
    total_scenarios = 0
    total_dependencies = 0

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
        curated = curated_records.get(repository)
        if curated is None:
            raise ValueError(f"Missing curated source record for {repository}")

        scenarios = scenario_document.get("scenarios", [])
        modes = {scenario.get("execution_mode") for scenario in scenarios}
        if modes != set(EXPECTED_MODES):
            raise ValueError(
                f"{repository} must define {sorted(EXPECTED_MODES)}, found {sorted(modes)}"
            )

        protocol_scenarios = {}
        for scenario in scenarios:
            mode = scenario["execution_mode"]
            protocol = EXPECTED_MODES[mode]
            protocol_scenarios[protocol] = {
                "scenario_id": scenario["scenario_id"],
                "execution_mode": mode,
                "agent_count": scenario["agent_count"],
                "concurrent_execution": scenario["concurrent_execution"],
                "communication_condition": scenario["communication_condition"],
            }

        dependency_points = metrics.get("dependency_points", [])
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
                    "overlay_count": len(curated.get("overlays", [])),
                },
                "parallelizability": task.get(
                    "proposed_parallelizability_label"
                ),
                "protocols": protocol_scenarios,
                "dependency_point_count": len(dependency_points),
                "artifacts": {
                    name: {"path": relative(path), "sha256": sha256(path)}
                    for name, path in paths.items()
                },
                "quality_status": quality.get("status")
                or quality.get("qualification_status"),
            }
        )

    official = {
        "schema_version": "asyncodebench-release-tasks-v1",
        "release": RELEASE,
        "release_version": RELEASE_VERSION,
        "task_namespace": "asyncodebench",
        "task_count": len(tasks),
        "official_task_ids": [task["task_id"] for task in tasks],
    }
    index = {
        "schema_version": "asyncodebench-task-index-v1",
        "release": RELEASE,
        "release_version": RELEASE_VERSION,
        "task_count": len(tasks),
        "scenario_count": total_scenarios,
        "dependency_point_count": total_dependencies,
        "protocols": list(EXPECTED_MODES.values()),
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
