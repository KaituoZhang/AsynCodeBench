"""Resolve immutable container images from the official v0.4 registry."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REGISTRY_RELATIVE_PATH = Path("configs/environments/official_task_images.v0.4.json")


def load_image_registry(repo_root: Path) -> dict[str, Any]:
    path = repo_root / REGISTRY_RELATIVE_PATH
    if not path.is_file():
        raise FileNotFoundError(f"Missing official task image registry: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def image_record(repo_root: Path, task_id: str) -> dict[str, Any]:
    records = load_image_registry(repo_root).get("records", [])
    matches = [
        record
        for record in records
        if task_id in {record.get("task_id"), record.get("source_task_id")}
    ]
    if len(matches) != 1:
        raise ValueError(f"Expected one official image record for {task_id!r}")
    return matches[0]


def immutable_image_reference(record: dict[str, Any]) -> str:
    digest = record.get("digest")
    if record.get("status") != "published" or not digest:
        raise RuntimeError(f"Task image is not published: {record.get('task_id')}")
    repository = str(record["image"]).rsplit(":", 1)[0]
    return f"{repository}@{digest}"
