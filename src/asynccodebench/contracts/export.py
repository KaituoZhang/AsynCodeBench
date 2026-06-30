"""Export public JSON Schemas for AsyncCodeBench contracts."""

from __future__ import annotations

import json
from pathlib import Path

from asynccodebench.contracts.models import (
    ActionRequest,
    ArtifactProvenance,
    BaselineSemanticCard,
    CapabilityCard,
    EventRecord,
    FileDeltaRecord,
    JobRecord,
    MessageProvenance,
    QualificationCard,
    ResourceRecord,
    WorkspaceStateRecord,
    WorkspaceVersionRecord,
)

PUBLIC_CONTRACTS = {
    "action": ActionRequest,
    "artifact_provenance": ArtifactProvenance,
    "baseline_semantic_card": BaselineSemanticCard,
    "capability_card": CapabilityCard,
    "event": EventRecord,
    "file_delta": FileDeltaRecord,
    "job": JobRecord,
    "message_provenance": MessageProvenance,
    "qualification_card": QualificationCard,
    "resource": ResourceRecord,
    "workspace_state": WorkspaceStateRecord,
    "workspace_version": WorkspaceVersionRecord,
}


def export_public_schemas(output_directory: Path | str) -> tuple[Path, ...]:
    """Write deterministic JSON Schema files for all public contracts."""

    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name, model in sorted(PUBLIC_CONTRACTS.items()):
        destination = output / f"{name}.schema.json"
        destination.write_text(
            json.dumps(
                model.model_json_schema(),
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        written.append(destination)
    return tuple(written)
