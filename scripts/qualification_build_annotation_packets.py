#!/usr/bin/env python
"""Build two answer-free annotation packets from a candidate inventory."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from asynccodebench.qualification.annotation_packets import (
    build_annotation_packet,
    write_annotation_packet,
)
from asynccodebench.qualification.models import CandidateInventory


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--annotators", nargs=2, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    inventory = CandidateInventory.model_validate(
        json.loads(args.inventory.read_text(encoding="utf-8"))
    )
    for annotator_id in args.annotators:
        output = args.output_dir / f"{annotator_id}.json"
        packet = build_annotation_packet(
            inventory,
            annotator_id=annotator_id,
        )
        print(write_annotation_packet(packet, output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
