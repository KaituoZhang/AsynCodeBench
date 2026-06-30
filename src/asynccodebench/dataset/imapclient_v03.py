"""Constants for the v0.3 Commit0 imapclient task records."""

from __future__ import annotations

from pathlib import Path


IMAPCLIENT_TASK_ID = "commit0:imapclient"
IMAPCLIENT_STRIPPED_SHA = "7ca5a23640bcb0b102673eaaf5eaa6e7fcebd76b"
IMAPCLIENT_COMPLETE_SHA = "391cc6d66d35c16bed11292ff00835646cd50ae5"

IMAPCLIENT_EVALUATOR_COMMAND = (
    "python3.10",
    "-m",
    "pytest",
    "-q",
    "-o",
    "addopts=",
    "tests/test_response_lexer.py",
    "tests/test_response_parser.py",
    "tests/test_imapclient.py",
    "tests/test_search.py",
    "tests/test_folder_status.py",
    "tests/test_store.py",
    "tests/test_datetime_util.py",
    "tests/test_imap_utf7.py",
    "tests/test_util_functions.py",
)

IMAPCLIENT_MANIFEST_FILES = (
    Path("manifests/pilot/v0.3/tasks/commit0_imapclient.json"),
    Path("manifests/pilot/v0.3/scenarios/commit0_imapclient.json"),
    Path("manifests/pilot/v0.3/quality/commit0_imapclient.json"),
    Path("manifests/pilot/v0.3/metrics/commit0_imapclient_async_metrics.json"),
)
