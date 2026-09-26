#!/usr/bin/env python3
"""Reject first-party identity leaks from the double-blind review artifact."""

from __future__ import annotations

import argparse
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_PREFIXES = (
    ".git/",
    ".venv/",
    ".cache/",
    "data/external/",
    "data/interim/",
    "data/processed/",
    "data/raw/",
    "outputs/",
    "reproductions/async-swe-agents/outputs/",
    "reproductions/async-swe-agents/.venv/",
)


@dataclass(frozen=True)
class Rule:
    name: str
    pattern: re.Pattern[str]


RULES = (
    Rule(
        "hard-coded anonymous mirror URL",
        re.compile(r"https?://anonymous\.4open\.science/(?:r|api/repo)/", re.I),
    ),
    Rule(
        "first-party GitHub repository URL",
        re.compile(r"https?://github\.com/[^/\s\"']+/async?codebench", re.I),
    ),
    Rule(
        "first-party personal GHCR namespace",
        re.compile(r"ghcr\.io/[^/\s\"']+/async?codebench", re.I),
    ),
    Rule(
        "identity-bearing project website",
        re.compile(r"https?://(?:www\.)?asyncodebench\.org", re.I),
    ),
    Rule(
        "first-party absolute home path",
        re.compile(r"/(?:home|Users)/[^/\s]+/Async?CodeBench", re.I),
    ),
    Rule(
        "author attribution phrase",
        re.compile(r"created and maintained by\s+[^\n<]+", re.I),
    ),
)

ANNOTATOR_ID = re.compile(r'"annotator_id"\s*:\s*"([^"]+)"')
ANONYMOUS_ANNOTATOR_ID = re.compile(
    r"(?:annotator_[ab]|reviewer_[a-z0-9_]+|"
    r"codex_ai_assisted_audit_[0-9]{8}|"
    r"your-stable-public-or-pseudonymous-id)\Z"
)


def repository_files(*, include_untracked: bool) -> list[Path]:
    command = ["git", "ls-files", "-z", "--cached"]
    if include_untracked:
        command.extend(("--others", "--exclude-standard"))
    result = subprocess.run(
        command,
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
    )
    paths = []
    for raw_path in result.stdout.split(b"\0"):
        if not raw_path:
            continue
        relative = raw_path.decode("utf-8", errors="surrogateescape")
        if relative.startswith(SKIP_PREFIXES):
            continue
        path = ROOT / relative
        if path.is_file():
            paths.append(path)
    return paths


def read_text(path: Path) -> str | None:
    data = path.read_bytes()
    if b"\0" in data:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def private_terms(path: Path | None) -> list[str]:
    if path is None or not path.exists():
        return []
    return [
        line.strip().casefold()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def audit(files: list[Path], terms: list[str]) -> list[str]:
    problems: list[str] = []
    for path in files:
        relative = path.relative_to(ROOT).as_posix()
        folded_path = relative.casefold()
        for index, term in enumerate(terms, start=1):
            if term in folded_path:
                problems.append(f"{relative}: private term #{index} appears in path")

        text = read_text(path)
        if text is None:
            continue

        for rule in RULES:
            for match in rule.pattern.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                problems.append(f"{relative}:{line}: {rule.name}")

        for match in ANNOTATOR_ID.finditer(text):
            if ANONYMOUS_ANNOTATOR_ID.fullmatch(match.group(1)) is None:
                line = text.count("\n", 0, match.start()) + 1
                problems.append(f"{relative}:{line}: non-anonymous annotator_id")

        folded_text = text.casefold()
        for index, term in enumerate(terms, start=1):
            offset = folded_text.find(term)
            if offset >= 0:
                line = text.count("\n", 0, offset) + 1
                problems.append(
                    f"{relative}:{line}: private term #{index} appears in content"
                )

    citation = ROOT / "CITATION.cff"
    citation_text = read_text(citation) or ""
    if "family-names: Anonymous" not in citation_text:
        problems.append("CITATION.cff: author family name is not anonymous")
    if "given-names: Authors" not in citation_text:
        problems.append("CITATION.cff: author given name is not anonymous")
    return problems


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--terms-file",
        type=Path,
        default=ROOT / ".anonymous-private-terms",
        help="untracked file containing one private literal per line",
    )
    parser.add_argument(
        "--include-untracked",
        action="store_true",
        help="also inspect untracked files that are not ignored",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    problems = audit(
        repository_files(include_untracked=args.include_untracked),
        private_terms(args.terms_file),
    )
    if problems:
        print("Anonymity audit failed:")
        for problem in problems:
            print(f"- {problem}")
        return 1
    print("Anonymity audit passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
