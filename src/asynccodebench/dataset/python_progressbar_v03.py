"""Constants for the v0.3 Commit0 python-progressbar task records."""

from __future__ import annotations

from pathlib import Path


PYTHON_PROGRESSBAR_TASK_ID = "commit0:python-progressbar"
PYTHON_PROGRESSBAR_STRIPPED_SHA = "afd18fd921caccca5f0c01576434869ddd7c0043"
PYTHON_PROGRESSBAR_COMPLETE_SHA = "edb9803924ab60ede3077dc72331c41d13e0c322"

PYTHON_PROGRESSBAR_EVALUATOR_COMMAND = (
    "python3.10",
    "-m",
    "pytest",
    "-q",
    "-o",
    "addopts=",
    "tests/test_algorithms.py",
    "tests/test_utils.py",
    "tests/test_wrappingio.py",
    "tests/test_stream.py",
    "tests/test_data_transfer_bar.py",
    "tests/test_progressbar.py::test_reuse",
    "tests/test_progressbar.py::test_dirty",
    "tests/test_progressbar.py::test_negative_maximum",
    "tests/test_widgets.py::test_create_wrapper",
    "tests/test_widgets.py::test_all_widgets_min_width",
    "tests/test_widgets.py::test_all_widgets_max_width",
)

PYTHON_PROGRESSBAR_MANIFEST_FILES = (
    Path("manifests/pilot/v0.3/tasks/commit0_python_progressbar.json"),
    Path("manifests/pilot/v0.3/scenarios/commit0_python_progressbar.json"),
    Path("manifests/pilot/v0.3/quality/commit0_python_progressbar.json"),
    Path("manifests/pilot/v0.3/metrics/commit0_python_progressbar_async_metrics.json"),
)
