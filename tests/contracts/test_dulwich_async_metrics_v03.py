from __future__ import annotations

import ast
import json
from pathlib import Path


METRICS_FILE = Path(
    "manifests/pilot/v0.3/metrics/commit0_dulwich_async_metrics.json"
)
REPO_ROOT = Path("data/repos/commit0/dulwich")


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


def _class_index(path: Path) -> dict[str, ast.ClassDef]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        node.name: node for node in tree.body if isinstance(node, ast.ClassDef)
    }


def _has_method(
    classes: dict[str, ast.ClassDef],
    class_name: str,
    method_name: str,
    seen: set[str] | None = None,
) -> bool:
    seen = set() if seen is None else seen
    if class_name in seen:
        return False
    seen.add(class_name)

    class_node = classes[class_name]
    if any(
        isinstance(node, ast.FunctionDef) and node.name == method_name
        for node in class_node.body
    ):
        return True

    for base in class_node.bases:
        if isinstance(base, ast.Name) and base.id in classes:
            if _has_method(classes, base.id, method_name, seen):
                return True
    return False


def test_dulwich_async_metrics_manifest_is_well_formed() -> None:
    metrics = json.loads(METRICS_FILE.read_text(encoding="utf-8"))

    assert metrics["task_id"] == "commit0:dulwich"
    assert metrics["schema_version"] == "0.3-async-metrics"
    assert len(metrics["dependency_points"]) == 2
    assert (
        metrics["aggregate_metrics"]["primary_paper_dependency_id"]
        == "dulwich.config_to_repo_refs.default_backend_contract"
    )


def test_dulwich_async_metric_probe_selectors_reference_public_tests() -> None:
    metrics = json.loads(METRICS_FILE.read_text(encoding="utf-8"))

    by_file: dict[Path, list[tuple[str, str]]] = {}
    for selector in _all_probe_selectors(metrics):
        parts = selector.split("::")
        assert len(parts) == 3, selector
        rel_path, class_name, method_name = parts
        assert method_name.startswith("test_"), selector
        by_file.setdefault(Path(rel_path), []).append((class_name, method_name))

    for rel_path, class_methods in by_file.items():
        test_file = REPO_ROOT / rel_path
        assert test_file.exists(), rel_path
        classes = _class_index(test_file)
        for class_name, method_name in class_methods:
            assert class_name in classes, f"{rel_path}::{class_name}"
            assert _has_method(
                classes, class_name, method_name
            ), f"{rel_path}::{class_name}::{method_name}"


def test_dulwich_primary_async_dependency_has_upstream_and_downstream_probes() -> None:
    metrics = json.loads(METRICS_FILE.read_text(encoding="utf-8"))
    dependency = next(
        item
        for item in metrics["dependency_points"]
        if item["dependency_id"]
        == "dulwich.config_to_repo_refs.default_backend_contract"
    )

    assert (
        "tests/test_config.py::StackedConfigTests::test_default_backends"
        in dependency["upstream_probe_tests"]
    )
    assert (
        "tests/test_refs.py::DiskRefsContainerTests::test_add_if_new_symbolic"
        in dependency["downstream_probe_tests"]
    )
    assert {"ADPR", "DRS", "CAIL", "SAD"}.issubset(
        set(dependency["metrics_enabled"])
    )
