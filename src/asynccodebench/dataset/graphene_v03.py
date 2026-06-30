"""Constants for the v0.3 Commit0 graphene task records."""

from __future__ import annotations

from pathlib import Path


GRAPHENE_TASK_ID = "commit0:graphene"
GRAPHENE_STRIPPED_SHA = "ec2d3f476a7fa94a7a2ffc3c145422b0c3b7e71a"
GRAPHENE_COMPLETE_SHA = "48678afba44fc6e43334133f92ea089613a29d93"

GRAPHENE_EVALUATOR_COMMAND = (
    "python3.10",
    "-m",
    "pytest",
    "-q",
    "-o",
    "addopts=",
    "-k",
    "not test_objecttype_container_benchmark",
    "graphene/types/tests/test_definition.py",
    "graphene/types/tests/test_objecttype.py",
    "graphene/types/tests/test_inputobjecttype.py",
    "graphene/types/tests/test_schema.py",
    "graphene/types/tests/test_scalars_serialization.py",
)

GRAPHENE_MANIFEST_FILES = (
    Path("manifests/pilot/v0.3/tasks/commit0_graphene.json"),
    Path("manifests/pilot/v0.3/scenarios/commit0_graphene.json"),
    Path("manifests/pilot/v0.3/quality/commit0_graphene.json"),
    Path("manifests/pilot/v0.3/metrics/commit0_graphene_async_metrics.json"),
)
