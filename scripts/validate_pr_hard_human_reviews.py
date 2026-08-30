#!/usr/bin/env python3
"""Validate the four required PR-hard v0.4 human-review forms."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas/v0.3/annotation_form.schema.json"
TASKS = ("20018", "20073", "20107", "20153")
FORM_ROOT = ROOT / "manifests/annotations/pr_hard_v0.4"


def decision_errors(document: dict[str, object]) -> list[str]:
    errors: list[str] = []
    annotator_id = document.get("annotator_id")
    if not isinstance(annotator_id, str) or annotator_id.strip() in {"", "FILL_ME"}:
        errors.append("annotator_id is still a placeholder")

    include = document.get("include")
    if include is None:
        errors.append("include is not decided")

    rationale = document.get("rationale")
    if not isinstance(rationale, str) or len(rationale.strip()) < 80:
        errors.append("rationale must contain a concrete explanation of at least 80 characters")

    label = document.get("parallelizability_label")
    allowed = set(document.get("allowed_labels", []))
    exclusion_reason = document.get("exclusion_reason")
    if include is True:
        if label not in allowed:
            errors.append("an included task needs an allowed parallelizability_label")
        if exclusion_reason is not None:
            errors.append("an included task must keep exclusion_reason null")
    elif include is False:
        if not isinstance(exclusion_reason, str) or not exclusion_reason.strip():
            errors.append("an excluded task needs a non-empty exclusion_reason")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--allow-pending",
        action="store_true",
        help="validate JSON/schema structure without failing on unfilled decisions",
    )
    args = parser.parse_args()

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    failed = False
    complete = 0
    for task in TASKS:
        path = FORM_ROOT / f"apache_tvm_{task}" / "annotator_a.json"
        document = json.loads(path.read_text(encoding="utf-8"))
        schema_errors = sorted(validator.iter_errors(document), key=lambda error: list(error.path))
        review_errors = decision_errors(document)
        if schema_errors:
            failed = True
            print(f"FAIL {task}: schema errors")
            for error in schema_errors:
                print(f"  - {error.message}")
            continue
        if review_errors:
            print(f"PENDING {task}")
            for error in review_errors:
                print(f"  - {error}")
            if not args.allow_pending:
                failed = True
        else:
            complete += 1
            print(f"COMPLETE {task}")

    print(f"Human reviews complete: {complete}/{len(TASKS)}")
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
