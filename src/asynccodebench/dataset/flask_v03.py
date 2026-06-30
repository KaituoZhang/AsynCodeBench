"""Static metadata for the v0.3 Commit0 Flask task."""

from __future__ import annotations

FLASK_TASK_ID = "commit0:flask"
FLASK_STRIPPED_REF = "origin/commit0_combined"
FLASK_STRIPPED_SHA = "af126af63a288df1d4edfe07e82a3b241aa4567a"
FLASK_COMPLETE_SHA = "2fec0b206c6e83ea813ab26597e15c96fab08be7"

FLASK_EVALUATOR_COMMAND = (
    "python3.10",
    "-m",
    "pytest",
    "-q",
    "-o",
    "addopts=",
    "tests/test_basic.py",
    "tests/test_reqctx.py",
    "tests/test_appctx.py",
    "tests/test_json.py",
    "tests/test_session_interface.py",
    "tests/test_templating.py",
    "tests/test_testing.py",
)

FLASK_TEST_TARGETS = FLASK_EVALUATOR_COMMAND[6:]
