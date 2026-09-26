"""Safe annotation-template writes for v0.3 build scripts."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel


def _has_completed_decision(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    return all(
        payload.get(field) is not None
        for field in ("include", "parallelizability_label", "rationale")
    )


def write_template_unless_completed(model: BaseModel, path: Path) -> None:
    """Write a blank template without overwriting completed human decisions."""

    if _has_completed_decision(path):
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(model.model_dump(mode="json"), indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
