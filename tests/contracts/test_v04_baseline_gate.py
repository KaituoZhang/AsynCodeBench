"""The stable gate admits only checksum-pinned official result bundles."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "build_v04_release_index", ROOT / "scripts/build_v04_release_index.py"
)
BUILDER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILDER)


def fixture_registry(root: Path):
    path = root / "manifests/release/v0.4/baselines/example/run_bundle.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"task_id": "asyncodebench:wcwidth"}), encoding="utf-8")
    entry = {
        "path": path.relative_to(root).as_posix(),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }
    return {
        "schema_version": "asyncodebench-validated-baselines-v1",
        "release": "v0.4",
        "bundles": [entry],
    }


def official_result(_):
    return {
        "status": "valid",
        "eligibility": {"official_aggregate": True},
        "task_id": "asyncodebench:wcwidth",
    }


def test_official_bundle_counts_toward_stable_gate(tmp_path):
    registry = fixture_registry(tmp_path)
    assert BUILDER.validate_baselines(
        tmp_path, registry, {"asyncodebench:wcwidth"}, official_result
    ) == 1


def test_checksum_mismatch_rejected(tmp_path):
    registry = fixture_registry(tmp_path)
    registry["bundles"][0]["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="checksum mismatch"):
        BUILDER.validate_baselines(
            tmp_path, registry, {"asyncodebench:wcwidth"}, official_result
        )


@pytest.mark.parametrize(
    "result",
    [
        {"status": "invalid", "eligibility": {"official_aggregate": False}},
        {"status": "valid", "eligibility": {"official_aggregate": False}},
    ],
)
def test_invalid_or_ineligible_bundle_rejected(tmp_path, result):
    registry = fixture_registry(tmp_path)
    with pytest.raises(ValueError, match="official validation"):
        BUILDER.validate_baselines(
            tmp_path, registry, {"asyncodebench:wcwidth"}, lambda _: result
        )


def test_unreleased_task_rejected(tmp_path):
    registry = fixture_registry(tmp_path)
    with pytest.raises(ValueError, match="outside the v0.4 release"):
        BUILDER.validate_baselines(tmp_path, registry, set(), official_result)


def test_path_outside_published_baselines_rejected(tmp_path):
    registry = fixture_registry(tmp_path)
    registry["bundles"][0]["path"] = "../../run_bundle.json"
    with pytest.raises(ValueError, match="invalid or duplicate baseline path"):
        BUILDER.validate_baselines(
            tmp_path, registry, {"asyncodebench:wcwidth"}, official_result
        )


def test_release_stage_uses_verified_baseline_count(monkeypatch):
    monkeypatch.setattr(BUILDER, "validate_baselines", lambda *_: 1)
    index, official = BUILDER.build_documents()
    assert index["validated_baseline_bundle_count"] == 1
    assert index["stable_release_ready"] is True
    assert index["release_stage"] == "stable"
    assert official["stable_release_ready"] is True
    assert official["release_stage"] == "stable"
