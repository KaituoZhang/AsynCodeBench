#!/usr/bin/env python

"""Build the audited v0.3 TinyDB candidate assets."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from asynccodebench.dataset.annotation_io import (
    write_template_unless_completed,
)
from asynccodebench.dataset.export import export_dataset_schemas
from asynccodebench.dataset.tinydb_v03 import (
    build_adjudication_form,
    build_annotation_forms,
    build_quality_record,
    build_scenarios,
    build_task_record,
    write_json,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--candidate-file",
        type=Path,
        default=Path(
            "manifests/candidates/commit0_public_candidates_v0.2.json"
        ),
    )
    parser.add_argument(
        "--task-output",
        type=Path,
        default=Path("manifests/pilot/v0.3/tasks/commit0_tinydb.json"),
    )
    parser.add_argument(
        "--scenario-output",
        type=Path,
        default=Path("manifests/pilot/v0.3/scenarios/commit0_tinydb.json"),
    )
    parser.add_argument(
        "--quality-output",
        type=Path,
        default=Path("manifests/pilot/v0.3/quality/commit0_tinydb.json"),
    )
    parser.add_argument(
        "--annotation-dir",
        type=Path,
        default=Path("manifests/annotations/commit0_v0.3/tinydb"),
    )
    parser.add_argument(
        "--schema-dir",
        type=Path,
        default=Path("schemas/v0.3"),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    task = build_task_record(args.candidate_file)
    scenarios = build_scenarios()
    quality = build_quality_record()
    forms = build_annotation_forms(
        candidate_file=args.candidate_file,
        task_record_file=args.task_output,
    )

    write_json(task, args.task_output)
    write_json(quality, args.quality_output)
    args.scenario_output.parent.mkdir(parents=True, exist_ok=True)
    args.scenario_output.write_text(
        json.dumps(
            {
                "schema_version": "0.3",
                "task_id": task.task_id,
                "scenarios": [
                    scenario.model_dump(mode="json")
                    for scenario in scenarios
                ],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    for form in forms:
        write_template_unless_completed(
            form, args.annotation_dir / f"{form.annotator_id}.json"
        )
    write_template_unless_completed(
        build_adjudication_form(),
        args.annotation_dir / "adjudication.template.json",
    )
    export_dataset_schemas(args.schema_dir)

    print(args.task_output)
    print(args.scenario_output)
    print(args.quality_output)
    print(args.annotation_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
