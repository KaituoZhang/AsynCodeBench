from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "configs/environments/official_task_images.v0.4.json"
SCHEMA = ROOT / "schemas/v0.4/official_task_images.schema.json"
OFFICIAL = ROOT / "manifests/release/v0.4/official_tasks.json"
TVM_TASKS = {
    "asyncodebench:apache-tvm-20018",
    "asyncodebench:apache-tvm-20073",
    "asyncodebench:apache-tvm-20107",
    "asyncodebench:apache-tvm-20153",
}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_official_task_image_registry_matches_schema_and_release() -> None:
    registry = load(REGISTRY)
    Draft202012Validator(load(SCHEMA)).validate(registry)

    records = registry["records"]
    official_ids = load(OFFICIAL)["official_task_ids"]
    assert len(records) == 20
    assert [record["task_id"] for record in records] == official_ids
    assert len({record["image"] for record in records}) == 20
    assert len({record["source_task_id"] for record in records}) == 20


def test_all_official_task_images_are_published_and_digest_pinned() -> None:
    records = load(REGISTRY)["records"]
    assert all(record["status"] == "published" for record in records)
    assert all(record["digest"].startswith("sha256:") for record in records)


def test_compiler_task_images_use_the_frozen_runtime_contract() -> None:
    records = {record["task_id"]: record for record in load(REGISTRY)["records"]}
    assert records.keys() >= TVM_TASKS
    for task_id in TVM_TASKS:
        record = records[task_id]
        assert record["source_task_id"] == task_id.replace(
            "asyncodebench:", "pr-hard:", 1
        )
        assert record["image"].startswith("ghcr.io/kaituozhang/asyncodebench-tvm-")
        assert record["runtime_root"] == "/opt/asyncodebench/runtime"
