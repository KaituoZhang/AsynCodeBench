from __future__ import annotations

import json
import re
from pathlib import Path


TASKS = {
    "deprecated": {
        "metrics_file": Path(
            "manifests/pilot/v0.3/metrics/commit0_deprecated_async_metrics.json"
        ),
        "repo_root": Path("data/repos/commit0/deprecated"),
        "task_id": "commit0:deprecated",
        "dependency_count": 3,
        "primary_dependency_id": (
            "deprecated.classic_to_sphinx.warning_message_contract"
        ),
        "primary_upstream_probe": (
            "tests/test_deprecated.py::test_classic_deprecated_function__warns"
        ),
        "primary_downstream_probe": (
            "tests/test_sphinx.py::test_sphinx_deprecated_function__warns"
        ),
    },
    "portalocker": {
        "metrics_file": Path(
            "manifests/pilot/v0.3/metrics/commit0_portalocker_async_metrics.json"
        ),
        "repo_root": Path("data/processed/commit0_curated/v0.3/portalocker"),
        "task_id": "commit0:portalocker",
        "dependency_count": 3,
        "primary_dependency_id": (
            "portalocker.backend_to_utilities.exception_timeout_contract"
        ),
        "primary_upstream_probe": "portalocker_tests/tests.py::test_exceptions",
        "primary_downstream_probe": (
            "portalocker_tests/tests.py::test_with_timeout"
        ),
    },
    "tinydb": {
        "metrics_file": Path(
            "manifests/pilot/v0.3/metrics/commit0_tinydb_async_metrics.json"
        ),
        "repo_root": Path("data/processed/commit0_curated/v0.3/tinydb"),
        "task_id": "commit0:tinydb",
        "dependency_count": 3,
        "primary_dependency_id": "tinydb.query_to_table.search_cache_contract",
        "primary_upstream_probe": "tests/test_queries.py::test_eq",
        "primary_downstream_probe": "tests/test_tables.py::test_query_cache",
    },
    "wcwidth": {
        "metrics_file": Path(
            "manifests/pilot/v0.3/metrics/commit0_wcwidth_async_metrics.json"
        ),
        "repo_root": Path("data/repos/commit0/wcwidth"),
        "task_id": "commit0:wcwidth",
        "dependency_count": 2,
        "primary_dependency_id": (
            "wcwidth.unicode_versions_to_width.version_matching_contract"
        ),
        "primary_upstream_probe": "tests/test_ucslevel.py::test_latest",
        "primary_downstream_probe": "tests/test_ucslevel.py::test_nearest_505_str",
    },
}


def _load_metrics(task_name: str) -> dict:
    return json.loads(TASKS[task_name]["metrics_file"].read_text(encoding="utf-8"))


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


def _function_exists(test_file: Path, function_name: str) -> bool:
    source = test_file.read_text(encoding="utf-8")
    return re.search(rf"^def {re.escape(function_name)}\s*\(", source, re.M) is not None


def test_new_async_metrics_manifests_are_well_formed() -> None:
    for task_name, expected in TASKS.items():
        metrics = _load_metrics(task_name)

        assert metrics["task_id"] == expected["task_id"]
        assert metrics["schema_version"] == "0.3-async-metrics"
        assert len(metrics["dependency_points"]) == expected["dependency_count"]
        assert (
            metrics["aggregate_metrics"]["primary_paper_dependency_id"]
            == expected["primary_dependency_id"]
        )
        assert (
            metrics["aggregate_metrics"]["dependency_point_count"]
            == expected["dependency_count"]
        )


def test_new_async_metric_probe_selectors_reference_public_tests() -> None:
    for task_name, expected in TASKS.items():
        metrics = _load_metrics(task_name)
        repo_root = expected["repo_root"]

        for selector in _all_probe_selectors(metrics):
            parts = selector.split("::")
            assert len(parts) == 2, selector
            rel_path, function_name = parts
            assert function_name.startswith("test_"), selector
            test_file = repo_root / rel_path
            assert test_file.exists(), selector
            assert _function_exists(test_file, function_name), selector


def test_new_primary_async_dependencies_have_upstream_and_downstream_probes() -> None:
    for task_name, expected in TASKS.items():
        metrics = _load_metrics(task_name)
        dependency = next(
            item
            for item in metrics["dependency_points"]
            if item["dependency_id"] == expected["primary_dependency_id"]
        )

        assert expected["primary_upstream_probe"] in dependency["upstream_probe_tests"]
        assert (
            expected["primary_downstream_probe"]
            in dependency["downstream_probe_tests"]
        )
        assert {"ADPR", "DRS", "CAIL", "SAD"}.issubset(
            set(dependency["metrics_enabled"])
        )
