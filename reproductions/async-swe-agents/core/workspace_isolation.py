"""Per-specialist workspace views and tool-call isolation hooks."""

from __future__ import annotations

import base64
import shlex

from openhands.sdk.hooks import HookConfig, HookDefinition, HookMatcher
from openhands.sdk.workspace import RemoteWorkspace


WORKSPACE_ISOLATION_POLICY_VERSION = "private-worktree-v1"
WORKSPACE_ISOLATION_TASK_ID = "pr-hard:apache-tvm-20018"


def uses_task_specific_workspace_isolation(task_module) -> bool:
    """Keep the isolation repair scoped to 20018's CAID condition."""
    return (
        getattr(task_module, "task_id", None) == WORKSPACE_ISOLATION_TASK_ID
        and getattr(task_module, "active_protocol", None) == "caid_manager"
    )


_WORKSPACE_GUARD_PROGRAM = r'''
import json
import os
import re
import shlex
import sys

allowed = os.path.normpath(sys.argv[1])
integrated = os.path.normpath(sys.argv[2])
integrated_name = os.path.basename(integrated)


def iter_strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from iter_strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_strings(child)


def inside(path, root):
    path = os.path.normpath(path)
    root = os.path.normpath(root)
    return path == root or path.startswith(root + os.sep)


def resolved(path):
    if os.path.isabs(path):
        return os.path.normpath(path)
    return os.path.normpath(os.path.join(allowed, path))


def deny(reason):
    print(json.dumps({"decision": "deny", "reason": reason}))
    raise SystemExit(0)


try:
    event = json.load(sys.stdin)
except Exception as error:
    deny("AsynCodeBench workspace guard could not parse the tool request: " + str(error))

tool_name = str(event.get("tool_name") or "")
tool_input = event.get("tool_input") or {}

# File-editor paths are unambiguous and must always resolve below the private
# worktree.  Check every conventional path field so SDK schema additions remain
# fail-closed without constraining text payloads such as replacement content.
if tool_name == "file_editor":
    for key in ("path", "file_path", "source_path", "destination_path"):
        value = tool_input.get(key)
        if isinstance(value, str) and value and not inside(resolved(value), allowed):
            deny(
                "Benchmark isolation violation: file_editor may only access the "
                "assigned private worktree " + allowed + "; rejected " + value
            )

for value in iter_strings(tool_input):
    # Block the integrated repository by both canonical path and basename.  The
    # basename check also catches relative spellings such as ../<repo>.
    if integrated in value or (integrated_name and integrated_name in value):
        deny(
            "Benchmark isolation violation: specialist tools cannot access the "
            "integrated repository " + integrated + ". Use " + allowed + " instead."
        )

    # Any explicit /workspace path must stay in the assigned worktree.  System
    # toolchains and runtime paths outside /workspace remain available.
    for match in re.finditer(r"/workspace(?:/[^\s;&|<>()'\"]*)?", value):
        candidate = match.group(0).rstrip(".,:)")
        if candidate and not inside(candidate, allowed):
            deny(
                "Benchmark isolation violation: specialist tools are confined to "
                + allowed + "; rejected workspace path " + candidate
            )

    # A bare `cd ..` from the conversation root escapes the worktree.  Other
    # uses of `..` (for example revision ranges) are not rejected.
    if tool_name == "terminal":
        try:
            tokens = shlex.split(value, posix=True)
        except ValueError:
            tokens = []
        for index, token in enumerate(tokens[:-1]):
            if token == "cd" and tokens[index + 1] in {"..", "../"}:
                deny(
                    "Benchmark isolation violation: `cd ..` escapes the assigned "
                    "private worktree " + allowed
                )

print(json.dumps({"decision": "allow"}))
'''


def private_remote_workspace(workspace, worktree_path: str) -> RemoteWorkspace:
    """Connect to the same agent server with a specialist-local working dir."""
    if not worktree_path:
        raise ValueError("A private worktree path is required for a subagent")
    host = getattr(workspace, "host", None)
    if not host:
        raise TypeError("Subagent isolation requires a remote workspace host")
    return RemoteWorkspace(
        host=host,
        api_key=getattr(workspace, "api_key", None),
        working_dir=worktree_path,
        read_timeout=getattr(workspace, "read_timeout", 600.0),
        max_connections=getattr(workspace, "max_connections", None),
    )


def workspace_guard_command(worktree_path: str, integrated_repo_path: str) -> str:
    """Return a self-contained server-side hook command."""
    encoded = base64.b64encode(_WORKSPACE_GUARD_PROGRAM.encode("utf-8")).decode(
        "ascii"
    )
    launcher = f"import base64;exec(base64.b64decode({encoded!r}))"
    return " ".join(
        [
            "python",
            "-c",
            shlex.quote(launcher),
            shlex.quote(worktree_path),
            shlex.quote(integrated_repo_path),
        ]
    )


def build_workspace_guard_hook(
    worktree_path: str,
    integrated_repo_path: str,
) -> HookConfig:
    """Block specialist tool calls that escape their private worktree."""
    return HookConfig(
        pre_tool_use=[
            HookMatcher(
                matcher="*",
                hooks=[
                    HookDefinition(
                        name="asyncodebench-private-worktree-guard",
                        command=workspace_guard_command(
                            worktree_path,
                            integrated_repo_path,
                        ),
                        timeout=10,
                    )
                ],
            )
        ]
    )
