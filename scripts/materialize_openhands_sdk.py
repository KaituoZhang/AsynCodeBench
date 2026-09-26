#!/usr/bin/env python3
"""Materialize the exact OpenHands source revision used by the harness."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCK_PATH = ROOT / "reproductions" / "software-agent-sdk.lock"
SDK_DIR = ROOT / "reproductions" / "software-agent-sdk"


def run(*args: str, capture: bool = False) -> str:
    result = subprocess.run(
        args,
        check=True,
        text=True,
        stdout=subprocess.PIPE if capture else None,
    )
    return result.stdout.strip() if capture else ""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--require-clean", action="store_true")
    args = parser.parse_args()

    lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    expected = lock["commit"]
    if not (SDK_DIR / ".git").is_dir():
        SDK_DIR.parent.mkdir(parents=True, exist_ok=True)
        run("git", "clone", lock["repository"], str(SDK_DIR))
        run("git", "-C", str(SDK_DIR), "checkout", "--detach", expected)

    actual = run("git", "-C", str(SDK_DIR), "rev-parse", "HEAD", capture=True)
    if actual != expected:
        raise SystemExit(
            "OpenHands SDK revision mismatch:\n"
            f"  expected: {expected}\n"
            f"  actual:   {actual}"
        )

    dirty = run(
        "git", "-C", str(SDK_DIR), "status", "--porcelain", capture=True
    )
    if dirty and args.require_clean:
        raise SystemExit(
            "OpenHands SDK checkout has unrecorded changes:\n" + dirty
        )
    if dirty:
        print("[OpenHands] WARNING: SDK checkout contains unrecorded changes")
    print(f"[OpenHands] source revision: {actual}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
