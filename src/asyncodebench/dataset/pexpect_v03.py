"""Constants for the v0.3 Commit0 pexpect task records."""

from __future__ import annotations

from pathlib import Path


PEXPECT_TASK_ID = "commit0:pexpect"
PEXPECT_STRIPPED_SHA = "21b5908ea5b9b38ca996fec50dc449bff5c2c82f"
PEXPECT_COMPLETE_SHA = "eb2820cec514c3ed5482e80ad3438cd31f2fa1ef"

PEXPECT_EVALUATOR_COMMAND = (
    "python3.10",
    "-m",
    "pytest",
    "-q",
    "-o",
    "addopts=",
    "tests/test_expect.py",
    "tests/test_popen_spawn.py",
    "tests/test_run.py",
    "tests/test_async.py",
)

PEXPECT_MANIFEST_FILES = (
    Path("manifests/pilot/v0.3/tasks/commit0_pexpect.json"),
    Path("manifests/pilot/v0.3/scenarios/commit0_pexpect.json"),
    Path("manifests/pilot/v0.3/quality/commit0_pexpect.json"),
    Path("manifests/pilot/v0.3/metrics/commit0_pexpect_async_metrics.json"),
)
