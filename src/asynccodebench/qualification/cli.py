"""Command-line interface for qualification manifest construction."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from asynccodebench.qualification.manifest import (
    build_manifest,
    write_manifest_csv,
    write_manifest_json,
)
from asynccodebench.qualification.models import QualificationBatchInput


def load_batch(path: Path) -> QualificationBatchInput:
    """Load one strict JSON object containing the complete input batch."""

    payload: Any = json.loads(path.read_text(encoding="utf-8"))
    return QualificationBatchInput.model_validate(payload)


def run(
    input_path: Path,
    json_output: Path,
    csv_output: Path,
) -> tuple[Path, Path]:
    manifest = build_manifest(load_batch(input_path))
    return (
        write_manifest_json(manifest, json_output),
        write_manifest_csv(manifest, csv_output),
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build validated AsyncCodeBench qualification manifests."
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--json-output", type=Path, required=True)
    parser.add_argument("--csv-output", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    for output_path in run(
        args.input,
        args.json_output,
        args.csv_output,
    ):
        print(output_path)
    return 0
