from __future__ import annotations

import ast
import json
import subprocess
from pathlib import Path


METRICS_FILE = Path(
    "manifests/pilot/v0.3/metrics/commit0_parsel_async_metrics.json"
)
REPO_ROOT = Path("data/repos/commit0/parsel")
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


def _test_node_names(rel_path: Path) -> set[str]:
    tree = ast.parse(_source_at_ref(rel_path))
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test"):
            names.add(node.name)
        elif isinstance(node, ast.ClassDef):
            for child in node.body:
                if isinstance(child, ast.FunctionDef) and child.name.startswith(
                    "test"
                ):
                    names.add(f"{node.name}::{child.name}")
    return names


def _base_test_node(parts: list[str]) -> str:
    return "::".join(parts[1:]).split("[", 1)[0]


def test_parsel_async_metrics_manifest_is_well_formed() -> None:
    metrics = json.loads(METRICS_FILE.read_text(encoding="utf-8"))

    assert metrics["task_id"] == "commit0:parsel"
    assert metrics["schema_version"] == "0.3-async-metrics"
    assert len(metrics["dependency_points"]) == 2
    assert (
        metrics["aggregate_metrics"]["primary_paper_dependency_id"]
        == "parsel.css_to_selector.pseudo_element_contract"
    )


def test_parsel_async_metric_probe_selectors_reference_public_tests() -> None:
    metrics = json.loads(METRICS_FILE.read_text(encoding="utf-8"))

    by_file: dict[Path, list[str]] = {}
    for selector in _all_probe_selectors(metrics):
        parts = selector.split("::")
        assert len(parts) in (2, 3), selector
        rel_path = parts[0]
        node_name = _base_test_node(parts)
        assert node_name.split("::")[-1].startswith("test_"), selector
        by_file.setdefault(Path(rel_path), []).append(node_name)

    for rel_path, node_names in by_file.items():
        names = _test_node_names(rel_path)
        for node_name in node_names:
            assert node_name in names, f"{rel_path}::{node_name}"


def test_parsel_primary_async_dependency_has_upstream_and_downstream_probes() -> None:
    metrics = json.loads(METRICS_FILE.read_text(encoding="utf-8"))
    dependency = next(
        item
        for item in metrics["dependency_points"]
        if item["dependency_id"]
        == "parsel.css_to_selector.pseudo_element_contract"
    )

    assert (
        "tests/test_selector_csstranslator.py::TranslatorTestMixin::test_text_pseudo_element"
        in dependency["upstream_probe_tests"]
    )
    assert (
        "tests/test_selector.py::SelectorTestCase::test_select_on_text_nodes"
        in dependency["downstream_probe_tests"]
    )
    assert {"ADPR", "DRS", "CAIL", "SAD"}.issubset(
        set(dependency["metrics_enabled"])
    )
