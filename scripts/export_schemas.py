#!/usr/bin/env python
"""Export the versioned public AsynCodeBench JSON Schemas."""

from __future__ import annotations

import argparse
from pathlib import Path

from asyncodebench.contracts.export import export_public_schemas


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("schemas/v0.2"),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    for path in export_public_schemas(args.output):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
