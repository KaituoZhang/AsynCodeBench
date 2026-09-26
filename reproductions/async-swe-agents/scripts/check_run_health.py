#!/usr/bin/env python3
"""Inspect AsynCodeBench runs without rerunning a model or evaluator."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from asyncodebench_harness.health import inspect_run


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Classify completed runs as valid, review-required, or invalid. "
            "Coding and dependency failures remain valid model outcomes."
        )
    )
    parser.add_argument("run_dirs", nargs="+", type=Path)
    parser.add_argument("--json-output", type=Path)
    args = parser.parse_args()

    results = [inspect_run(path) for path in args.run_dirs]
    payload = {
        "valid": all(item["status"] == "valid" for item in results),
        "runs": results,
    }
    rendered = json.dumps(payload, indent=2, sort_keys=True)
    print(rendered)
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(rendered + "\n", encoding="utf-8")
    return 0 if payload["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
