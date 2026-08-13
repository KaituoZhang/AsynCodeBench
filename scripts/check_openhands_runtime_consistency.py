#!/usr/bin/env python3
"""Verify that host OpenHands packages match the locked server source."""

from __future__ import annotations

import argparse
import importlib.metadata
import inspect
import json
import os
import subprocess
from pathlib import Path

import tomllib

ROOT = Path(__file__).resolve().parents[1]
LOCK_PATH = ROOT / "reproductions" / "software-agent-sdk.lock"
SDK_DIR = ROOT / "reproductions" / "software-agent-sdk"
RUNNER_PYPROJECT = ROOT / "reproductions" / "async-swe-agents" / "pyproject.toml"
PACKAGES = (
    "openhands-sdk",
    "openhands-workspace",
    "openhands-tools",
    "openhands-agent-server",
)

os.environ.setdefault("OPENHANDS_SUPPRESS_BANNER", "1")
os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")


def git(*args: str) -> str:
    return subprocess.run(
        ("git", "-C", str(SDK_DIR), *args),
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    ).stdout.strip()


def source_versions() -> dict[str, str]:
    versions = {}
    for package in PACKAGES:
        document = tomllib.loads(
            (SDK_DIR / package / "pyproject.toml").read_text(encoding="utf-8")
        )
        versions[package] = document["project"]["version"]
    return versions


def declared_versions() -> dict[str, str]:
    document = tomllib.loads(RUNNER_PYPROJECT.read_text(encoding="utf-8"))
    dependencies = document["project"]["dependencies"]
    declared = {}
    for dependency in dependencies:
        for package in PACKAGES:
            prefix = f"{package}=="
            if dependency.startswith(prefix):
                declared[package] = dependency.removeprefix(prefix)
    return declared


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--require-clean", action="store_true")
    args = parser.parse_args()
    issues = []

    lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    configured_source = Path(os.getenv("SDK_SOURCE_DIR", SDK_DIR)).expanduser().resolve()
    if configured_source != SDK_DIR.resolve():
        issues.append("sdk_source_dir_mismatch")
    actual_revision = git("rev-parse", "HEAD")
    if actual_revision != lock["commit"]:
        issues.append("sdk_revision_mismatch")
    dirty = git("status", "--porcelain")
    if dirty and args.require_clean:
        issues.append("sdk_checkout_dirty")

    expected_versions = source_versions()
    for package, version in expected_versions.items():
        if version != lock.get("package_version"):
            issues.append(f"lock_version_mismatch:{package}")
    declared = declared_versions()
    installed_versions = {}
    for package in PACKAGES:
        if declared.get(package) != expected_versions[package]:
            issues.append(f"declared_version_mismatch:{package}")
        try:
            installed_versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            issues.append(f"package_not_installed:{package}")
            continue
        if installed_versions[package] != expected_versions[package]:
            issues.append(f"package_version_mismatch:{package}")

    from openhands.sdk.event import SystemPromptEvent

    event_source = Path(inspect.getfile(SystemPromptEvent)).resolve()
    expected_source_root = (SDK_DIR / "openhands-sdk").resolve()
    try:
        event_source.relative_to(expected_source_root)
    except ValueError:
        issues.append("host_sdk_not_loaded_from_locked_source")
    if "dynamic_context" not in SystemPromptEvent.model_fields:
        issues.append("host_event_schema_missing_dynamic_context")

    payload = {
        "valid": not issues,
        "issues": issues,
        "locked_revision": lock["commit"],
        "actual_revision": actual_revision,
        "configured_sdk_source_dir": str(configured_source),
        "sdk_checkout_dirty": bool(dirty),
        "expected_versions": expected_versions,
        "declared_versions": declared,
        "installed_versions": installed_versions,
        "host_event_source": str(event_source),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
