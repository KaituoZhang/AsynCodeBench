"""Constants for the v0.3 Commit0 marshmallow task records."""

from __future__ import annotations

from pathlib import Path


MARSHMALLOW_TASK_ID = "commit0:marshmallow"
MARSHMALLOW_STRIPPED_SHA = "bd290d2b49f5030a2369aedc5538cffa4815982d"
MARSHMALLOW_COMPLETE_SHA = "947724c7391814a740b94239807eb964c9bf40d7"

MARSHMALLOW_EVALUATOR_COMMAND = (
    "python",
    "-m",
    "pytest",
    "-q",
    "-o",
    "addopts=",
    "tests/test_registry.py",
    "tests/test_validate.py",
    "tests/test_fields.py",
    "tests/test_schema.py",
    "tests/test_serialization.py",
    "tests/test_deserialization.py",
    "tests/test_decorators.py",
    "tests/test_exceptions.py",
    "tests/test_utils.py",
    "tests/test_options.py",
    "tests/test_error_store.py",
)

MARSHMALLOW_MANIFEST_FILES = (
    Path("manifests/pilot/v0.3/tasks/commit0_marshmallow.json"),
    Path("manifests/pilot/v0.3/scenarios/commit0_marshmallow.json"),
    Path("manifests/pilot/v0.3/quality/commit0_marshmallow.json"),
    Path("manifests/pilot/v0.3/metrics/commit0_marshmallow_async_metrics.json"),
)
