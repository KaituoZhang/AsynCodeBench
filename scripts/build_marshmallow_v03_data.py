"""Validate that the generated v0.3 marshmallow records are present."""

from __future__ import annotations

import json
from pathlib import Path

MARSHMALLOW_TASK_ID = "commit0:marshmallow"
MARSHMALLOW_MANIFEST_FILES = (
    Path("manifests/pilot/v0.3/tasks/commit0_marshmallow.json"),
    Path("manifests/pilot/v0.3/scenarios/commit0_marshmallow.json"),
    Path("manifests/pilot/v0.3/quality/commit0_marshmallow.json"),
    Path("manifests/pilot/v0.3/metrics/commit0_marshmallow_async_metrics.json"),
)


def main() -> None:
    for path in MARSHMALLOW_MANIFEST_FILES:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload["task_id"] != MARSHMALLOW_TASK_ID:
            raise ValueError(f"unexpected task_id in {path}: {payload['task_id']}")
    print(f"validated {MARSHMALLOW_TASK_ID} v0.3 manifest files")


if __name__ == "__main__":
    main()
