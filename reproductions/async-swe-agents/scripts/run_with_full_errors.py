#!/usr/bin/env python
"""Run async-swe-agents and print subprocess stdout/stderr on build failures."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import fire

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from run_infer import main


def _main(*args, **kwargs):
    try:
        return main(*args, **kwargs)
    except subprocess.CalledProcessError as exc:
        print("\n" + "=" * 80, file=sys.stderr)
        print("Subprocess failed with full captured output", file=sys.stderr)
        print("=" * 80, file=sys.stderr)
        print(f"returncode: {exc.returncode}", file=sys.stderr)
        print(f"cmd: {' '.join(map(str, exc.cmd))}", file=sys.stderr)
        if exc.output:
            print("\n--- stdout ---", file=sys.stderr)
            print(exc.output, file=sys.stderr)
        if exc.stderr:
            print("\n--- stderr ---", file=sys.stderr)
            print(exc.stderr, file=sys.stderr)
        print("=" * 80, file=sys.stderr)
        raise


if __name__ == "__main__":
    fire.Fire(_main)
