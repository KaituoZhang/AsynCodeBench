from __future__ import annotations

import ast
import json
import subprocess
from pathlib import Path


METRICS_FILE = Path(
    "manifests/pilot/v0.3/metrics/commit0_filesystem_spec_async_metrics.json"
)
REPO_ROOT = Path("data/repos/commit0/filesystem_spec")
SOURCE_REF = "origin/commit0_combined"


def _all_probe_selectors(metrics: dict) -> set[str]:
    selectors: set[str] = set()
    for dependency in metrics["dependency_points"]:
        for field in (
            "upstream_probe_tests",
            "downstream_probe_tests",
            "integrated_probe_tests",
        ):
            selectors.update(dependency.get(field, ()))
    return selectors


def _source_at_ref(rel_path: Path) -> str:
    result = subprocess.run(
        [
            "git",
            "-C",
            str(REPO_ROOT),
            "show",
            f"{SOURCE_REF}:{rel_path.as_posix()}",
        ],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return result.stdout


def _function_names(rel_path: Path) -> set[str]:
    tree = ast.parse(_source_at_ref(rel_path))
    return {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test")
    }


def _base_test_name(node_id_part: str) -> str:
    return node_id_part.split("[", 1)[0]


def test_filesystem_spec_async_metrics_manifest_is_well_formed() -> None:
    metrics = json.loads(METRICS_FILE.read_text(encoding="utf-8"))

    assert metrics["task_id"] == "commit0:filesystem_spec"
    assert metrics["schema_version"] == "0.3-async-metrics"
    assert len(metrics["dependency_points"]) == 2
    assert (
        metrics["aggregate_metrics"]["primary_paper_dependency_id"]
        == "filesystem_spec.registry_to_core.protocol_resolution_contract"
    )


def test_filesystem_spec_async_metric_probe_selectors_reference_public_tests() -> None:
    metrics = json.loads(METRICS_FILE.read_text(encoding="utf-8"))

    by_file: dict[Path, list[str]] = {}
    for selector in _all_probe_selectors(metrics):
        parts = selector.split("::")
        assert len(parts) == 2, selector
        rel_path, function_name = parts
        assert _base_test_name(function_name).startswith("test_"), selector
        by_file.setdefault(Path(rel_path), []).append(function_name)

    for rel_path, function_names in by_file.items():
        names = _function_names(rel_path)
        for function_name in function_names:
            assert _base_test_name(function_name) in names, (
                f"{rel_path}::{function_name}"
            )


def test_filesystem_spec_primary_dependency_has_upstream_and_downstream_probes() -> None:
    metrics = json.loads(METRICS_FILE.read_text(encoding="utf-8"))
    dependency = next(
        item
        for item in metrics["dependency_points"]
        if item["dependency_id"]
        == "filesystem_spec.registry_to_core.protocol_resolution_contract"
    )

    assert (
        "fsspec/tests/test_registry.py::test_registry_readonly"
        in dependency["upstream_probe_tests"]
    )
    assert "fsspec/tests/test_core.py::test_automkdir_local" in dependency[
        "downstream_probe_tests"
    ]
    assert {"ADPR", "DRS", "CAIL", "SAD"}.issubset(
        set(dependency["metrics_enabled"])
    )
