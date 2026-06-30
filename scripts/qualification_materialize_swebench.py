#!/usr/bin/env python
"""Materialize public base-commit evidence for screened SWE-bench tasks."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from asynccodebench.qualification.swebench_materialization import (
    materialize_screening_inventory,
    write_materialization_inventory,
)
from asynccodebench.qualification.swebench_screening import (
    SWEbenchScreeningInventory,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--screening", type=Path, required=True)
    parser.add_argument("--repos-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    screening = SWEbenchScreeningInventory.model_validate(
        json.loads(args.screening.read_text(encoding="utf-8"))
    )
    inventory = materialize_screening_inventory(screening, args.repos_root)
    print(write_materialization_inventory(inventory, args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
