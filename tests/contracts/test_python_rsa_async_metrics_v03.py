from __future__ import annotations

import ast
import json
import subprocess
from pathlib import Path


METRICS_FILE = Path(
    "manifests/pilot/v0.3/metrics/commit0_python_rsa_async_metrics.json"
)
REPO_ROOT = Path("data/repos/commit0/python-rsa")
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


def _class_method_names(rel_path: Path) -> set[tuple[str, str]]:
    tree = ast.parse(_source_at_ref(rel_path))
    names: set[tuple[str, str]] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for child in node.body:
                if isinstance(child, ast.FunctionDef):
                    names.add((node.name, child.name))
    return names


def _base_test_name(node_id_part: str) -> str:
    return node_id_part.split("[", 1)[0]


def test_python_rsa_async_metrics_manifest_is_well_formed() -> None:
    metrics = json.loads(METRICS_FILE.read_text(encoding="utf-8"))

    assert metrics["task_id"] == "commit0:python-rsa"
    assert metrics["schema_version"] == "0.3-async-metrics"
    assert len(metrics["dependency_points"]) == 3
    assert (
        metrics["aggregate_metrics"]["primary_paper_dependency_id"]
        == "python_rsa.arithmetic_to_key_generation.inverse_prime_contract"
    )


def test_python_rsa_async_metric_probe_selectors_reference_public_tests() -> None:
    metrics = json.loads(METRICS_FILE.read_text(encoding="utf-8"))

    by_file: dict[Path, list[tuple[str, str]]] = {}
    for selector in _all_probe_selectors(metrics):
        parts = selector.split("::")
        assert len(parts) == 3, selector
        rel_path, class_name, function_name = parts
        assert _base_test_name(function_name).startswith("test_"), selector
        by_file.setdefault(Path(rel_path), []).append(
            (class_name, _base_test_name(function_name))
        )

    for rel_path, class_methods in by_file.items():
        names = _class_method_names(rel_path)
        for class_name, function_name in class_methods:
            assert (class_name, function_name) in names, (
                f"{rel_path}::{class_name}::{function_name}"
            )


def test_python_rsa_primary_async_dependency_has_upstream_and_downstream_probes() -> None:
    metrics = json.loads(METRICS_FILE.read_text(encoding="utf-8"))
    dependency = next(
        item
        for item in metrics["dependency_points"]
        if item["dependency_id"]
        == "python_rsa.arithmetic_to_key_generation.inverse_prime_contract"
    )

    assert (
        "tests/test_common.py::TestInverse::test_normal"
        in dependency["upstream_probe_tests"]
    )
    assert (
        "tests/test_key.py::KeyGenTest::test_default_exponent"
        in dependency["downstream_probe_tests"]
    )
    assert {"ADPR", "DRS", "CAIL", "SAD"}.issubset(
        set(dependency["metrics_enabled"])
    )
