from __future__ import annotations

import ast
import json
import subprocess
from pathlib import Path


METRICS_FILE = Path("manifests/pilot/v0.3/metrics/commit0_cookiecutter_async_metrics.json")
REPO_ROOT = Path("data/repos/commit0/cookiecutter")
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
        ["git", "-C", str(REPO_ROOT), "show", f"{SOURCE_REF}:{rel_path.as_posix()}"],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return result.stdout


def _test_names(rel_path: Path) -> set[tuple[str | None, str]]:
    tree = ast.parse(_source_at_ref(rel_path))
    names: set[tuple[str | None, str]] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test"):
            names.add((None, node.name))
        elif isinstance(node, ast.ClassDef):
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name.startswith("test"):
                    names.add((node.name, child.name))
    return names


def test_cookiecutter_async_metrics_manifest_is_well_formed() -> None:
    metrics = json.loads(METRICS_FILE.read_text(encoding="utf-8"))

    assert metrics["task_id"] == "commit0:cookiecutter"
    assert metrics["schema_version"] == "0.3-async-metrics"
    assert len(metrics["dependency_points"]) == 3
    assert metrics["aggregate_metrics"]["dependency_point_count"] == 3
    assert metrics["aggregate_metrics"]["primary_paper_dependency_id"] == (
        "cookiecutter.config_prompt_to_main.context_contract"
    )


def test_cookiecutter_async_metric_probe_selectors_reference_public_tests() -> None:
    metrics = json.loads(METRICS_FILE.read_text(encoding="utf-8"))

    by_file: dict[Path, list[tuple[str | None, str]]] = {}
    for selector in _all_probe_selectors(metrics):
        parts = selector.split("::")
        assert len(parts) in {2, 3}, selector
        rel_path = Path(parts[0])
        if len(parts) == 2:
            class_name = None
            function_name = parts[1]
        else:
            class_name = parts[1]
            function_name = parts[2]
        function_name = function_name.split("[", 1)[0]
        assert function_name.startswith("test_"), selector
        by_file.setdefault(rel_path, []).append((class_name, function_name))

    for rel_path, expected_names in by_file.items():
        names = _test_names(rel_path)
        for expected in expected_names:
            assert expected in names, f"{rel_path}::{expected}"


def test_cookiecutter_primary_dependency_has_upstream_and_downstream_probes() -> None:
    metrics = json.loads(METRICS_FILE.read_text(encoding="utf-8"))
    dependency = next(
        item
        for item in metrics["dependency_points"]
        if item["dependency_id"] == "cookiecutter.config_prompt_to_main.context_contract"
    )

    assert "tests/test_get_config.py::test_get_config" in dependency["upstream_probe_tests"]
    assert "tests/test_main.py::test_original_cookiecutter_options_preserved_in__cookiecutter" in dependency["downstream_probe_tests"]
    assert {"ADPR", "DRS", "CAIL", "SAD"}.issubset(set(dependency["metrics_enabled"]))
