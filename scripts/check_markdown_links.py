#!/usr/bin/env python3
"""Check relative Markdown links in selected public documentation files."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


LINK = re.compile(r"\[[^]]*\]\(([^)]+)\)")


def missing_links(path: Path) -> list[str]:
    missing = []
    for raw_target in LINK.findall(path.read_text(encoding="utf-8")):
        target = raw_target.strip().strip("<>").split("#", 1)[0]
        if not target or "://" in target or target.startswith(("mailto:", "#")):
            continue
        if not (path.parent / target).exists():
            missing.append(target)
    return missing


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+", type=Path)
    args = parser.parse_args()
    failures = []
    for path in args.paths:
        if not path.is_file():
            failures.append(f"{path}: file does not exist")
            continue
        failures.extend(f"{path}: {target}" for target in missing_links(path))
    if failures:
        parser.error("broken relative links:\n" + "\n".join(failures))
    print(f"Checked {len(args.paths)} Markdown files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
