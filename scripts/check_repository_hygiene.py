#!/usr/bin/env python3
"""Reject tracked secrets, private environments, datasets, and run outputs."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
SECRET_PATTERNS = {
    "private_key": re.compile(r"BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY"),
    "openai_style_key": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    "google_api_key": re.compile(r"\bAIza[0-9A-Za-z_-]{20,}\b"),
    "assigned_api_key": re.compile(
        r"(?:LLM_API_KEY|OPENAI_API_KEY)\s*=\s*(?!"
        r"(?:your|put_|YOUR|PUT_|local-|dummy|empty|EMPTY|<|\$\{|$))"
        # Stop at a literal backslash as well as real whitespace. Test fixtures
        # often embed ``KEY=test-key\n`` inside Python strings; without this
        # boundary the scanner consumes the following source text and reports
        # a false credential.
        r"[^\s#\\]{12,}",
        re.IGNORECASE,
    ),
}
TEXT_SUFFIXES = {
    ".cfg",
    ".cff",
    ".ini",
    ".jinja",
    ".json",
    ".md",
    ".patch",
    ".py",
    ".sh",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}


def tracked_files() -> list[Path]:
    output = subprocess.check_output(
        ["git", "-C", str(ROOT), "ls-files", "-z"]
    )
    return [
        ROOT / name.decode("utf-8")
        for name in output.split(b"\0")
        if name
    ]


def allowed_environment_example(path: PurePosixPath) -> bool:
    return path.name == ".env.example" or path.name.endswith(".example")


def path_issues(path: Path) -> list[str]:
    relative = PurePosixPath(path.relative_to(ROOT).as_posix())
    issues = []
    if (
        relative.name == ".env" or relative.name.startswith(".env.")
    ) and not allowed_environment_example(relative):
        issues.append("private_environment_file")
    parts = relative.parts
    if "outputs" in parts and relative.as_posix() != "outputs/README.md":
        issues.append("generated_output")
    if (
        len(parts) >= 2
        and parts[0] == "data"
        and parts[1] in {"external", "interim", "processed", "raw"}
        and relative.name != ".gitkeep"
    ):
        issues.append("generated_or_external_dataset")
    return issues


def secret_issues(path: Path) -> list[str]:
    if path.suffix.lower() not in TEXT_SUFFIXES and ".env" not in path.name:
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    return [name for name, pattern in SECRET_PATTERNS.items() if pattern.search(text)]


def main() -> int:
    findings = []
    for path in tracked_files():
        for issue in [*path_issues(path), *secret_issues(path)]:
            findings.append((path.relative_to(ROOT).as_posix(), issue))
    if findings:
        for path, issue in sorted(findings):
            print(f"{path}: {issue}", file=sys.stderr)
        return 1
    print("Repository hygiene check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
