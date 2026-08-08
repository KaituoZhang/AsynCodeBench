"""Static metadata for the v0.3 Commit0 FastAPI task."""

from __future__ import annotations

FASTAPI_TASK_ID = "commit0:fastapi"
FASTAPI_STRIPPED_REF = "origin/commit0_combined"
FASTAPI_STRIPPED_SHA = "0ee9d513da2f664b076c13a5f0969ecd1bfd25dd"
FASTAPI_COMPLETE_SHA = "847296e885ed83bc333b6cc0a3000d6242083b87"

FASTAPI_EVALUATOR_COMMAND = (
    "/home/kzhang42/AsynCodeBench/reproductions/async-swe-agents/.venv/bin/python",
    "-m",
    "pytest",
    "-q",
    "-o",
    "addopts=",
    "-W",
    "ignore::DeprecationWarning",
    "tests/test_jsonable_encoder.py",
)

FASTAPI_TEST_TARGETS = FASTAPI_EVALUATOR_COMMAND[7:]
