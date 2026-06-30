"""Create answer-free work packets for genuinely independent annotators."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from asynccodebench.qualification.models import (
    CandidateInventory,
    CandidateRecord,
)

ANNOTATION_PACKET_VERSION = "annotation-packet-v0.2"


class AnnotationPacket(BaseModel):
    model_config = ConfigDict(extra="forbid")

    packet_version: Literal["annotation-packet-v0.2"] = (
        ANNOTATION_PACKET_VERSION
    )
    specification_version: Literal["v0.2"] = "v0.2"
    annotator_id: str = Field(min_length=1)
    independence_instructions: tuple[str, ...]
    allowed_labels: tuple[str, ...] = (
        "parallelizable",
        "partially_parallelizable",
        "effectively_serial",
    )
    candidates: tuple[CandidateRecord, ...]


def build_annotation_packet(
    inventory: CandidateInventory,
    *,
    annotator_id: str,
) -> AnnotationPacket:
    sanitized = tuple(
        candidate.model_copy(update={"gold_informed_secondary_label": None})
        for candidate in inventory.candidates
    )
    return AnnotationPacket(
        annotator_id=annotator_id,
        independence_instructions=(
            "Do not consult another annotator's labels or rationale.",
            "Use only evidence included in this packet.",
            "Do not inspect solution refs, gold patches, or reference diffs.",
            "Record one label, include/exclude decision, rationale, and "
            "exclusion reason when excluded.",
        ),
        candidates=sanitized,
    )


def write_annotation_packet(
    packet: AnnotationPacket,
    output_path: Path | str,
) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(packet.model_dump(mode="json"), indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    return output
