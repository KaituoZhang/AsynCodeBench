#!/usr/bin/env python

"""Finalize one v0.3 task after independent human annotation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from asynccodebench.dataset.annotation import finalize_task_record
from asynccodebench.dataset.cachetools_v03 import write_json
from asynccodebench.dataset.models import (
    AdjudicationForm,
    AnnotationForm,
    TaskRecord,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", type=Path, required=True)
    parser.add_argument("--annotation-a", type=Path, required=True)
    parser.add_argument("--annotation-b", type=Path, required=True)
    parser.add_argument("--adjudication", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def _load(model, path: Path):
    return model.model_validate(json.loads(path.read_text(encoding="utf-8")))


def main() -> int:
    args = parse_args()
    task = _load(TaskRecord, args.task)
    annotations = (
        _load(AnnotationForm, args.annotation_a),
        _load(AnnotationForm, args.annotation_b),
    )
    adjudication = (
        _load(AdjudicationForm, args.adjudication)
        if args.adjudication
        else None
    )
    finalized = finalize_task_record(task, annotations, adjudication)
    write_json(finalized, args.output)
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
