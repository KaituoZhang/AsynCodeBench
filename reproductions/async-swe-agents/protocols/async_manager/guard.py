"""Fail-closed, phase-aware authorization for the online manager."""

from __future__ import annotations

import base64
import json
import shlex

from openhands.sdk.hooks import HookConfig, HookDefinition, HookMatcher

PROGRAM = r"""
import json
import os
import sys

root = os.path.realpath(sys.argv[1])
mode_file = os.path.realpath(sys.argv[2])
scopes = json.loads(sys.argv[3])
event = json.load(sys.stdin)
tool = str(event.get("tool_name") or "")
data = event.get("tool_input") or {}


def answer(ok, reason):
    print(json.dumps({"decision": "allow" if ok else "deny", "reason": reason}))
    raise SystemExit(0)


if tool == "terminal":
    answer(True, "Terminal authorization is delegated to the read-only terminal guard")
if tool in {"finish", "think"}:
    answer(True, "Non-mutating manager tool")
if tool != "file_editor":
    answer(False, "Tool is unavailable to the online manager")

path = data.get("path") or data.get("file_path")
if not isinstance(path, str) or not path:
    answer(False, "An explicit editor path is required")
target = os.path.realpath(path if os.path.isabs(path) else os.path.join(root, path))
try:
    inside = os.path.commonpath([root, target]) == root
except ValueError:
    inside = False
if not inside:
    answer(False, "Editor path escapes the private manager worktree")

relative = os.path.relpath(target, root)
parts = relative.split(os.sep)
if ".git" in parts:
    answer(False, "Git metadata is protected")

command = str(data.get("command") or "")
if command == "view":
    answer(True, "Read access inside the private manager worktree")
if command not in {"create", "str_replace", "insert", "undo_edit"}:
    answer(False, "Unrecognized file-editor mutation")

try:
    mode = open(mode_file, encoding="utf-8").read().strip()
except OSError:
    answer(False, "Manager authorization state is unavailable")
if mode != "intervene":
    answer(
        False,
        "Production edits are allowed only during an explicit intervention event",
    )

protected = {"tests", "test", "checkers", "manifests", "evaluators"}
if any(part in protected for part in parts):
    answer(False, "Benchmark control or evaluation path is protected")
in_scope = any(
    relative == scope.rstrip("/")
    or relative.startswith(scope.rstrip("/") + "/")
    for scope in scopes
)
if not in_scope:
    answer(False, "Path is outside the union of manifest-declared production scopes")
answer(True, "Authorized scoped online-manager intervention")
"""


def guard_command(root: str, mode_file: str, scopes: list[str]) -> str:
    encoded = base64.b64encode(PROGRAM.encode("utf-8")).decode("ascii")
    launcher = f"import base64;exec(base64.b64decode({encoded!r}))"
    return " ".join(
        map(
            shlex.quote,
            ["python", "-c", launcher, root, mode_file, json.dumps(scopes)],
        )
    )


def build_guard(root: str, mode_file: str, scopes: list[str]) -> HookConfig:
    return HookConfig(
        pre_tool_use=[
            HookMatcher(
                matcher="*",
                hooks=[
                    HookDefinition(
                        name="async-manager-online-scope-v1",
                        command=guard_command(root, mode_file, scopes),
                        timeout=10,
                    )
                ],
            )
        ]
    )
