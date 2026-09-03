"""Prevent agent terminal commands from terminating the workspace control plane."""

from __future__ import annotations

import base64
import shlex

from openhands.sdk.hooks import HookConfig, HookDefinition, HookMatcher

CONTROL_PLANE_GUARD_POLICY_VERSION = "workspace-control-plane-v1"


_CONTROL_PLANE_GUARD_PROGRAM = r"""
import json
import re
import shlex
import sys


def deny(reason):
    print(json.dumps({"decision": "deny", "reason": reason}))
    raise SystemExit(0)


try:
    event = json.load(sys.stdin)
except Exception as error:
    deny(
        "AsynCodeBench control-plane guard could not parse the tool request: "
        + str(error)
    )

if str(event.get("tool_name") or "") != "terminal":
    print(json.dumps({"decision": "allow"}))
    raise SystemExit(0)

tool_input = event.get("tool_input") or {}
command = tool_input.get("command")
if not isinstance(command, str):
    print(json.dumps({"decision": "allow"}))
    raise SystemExit(0)

# The OpenHands agent server and the model's shell share a container.  Pattern-
# based process termination can therefore kill the Python control plane along
# with a test command.  Require agents to identify and signal one exact PID.
for segment in re.split(r"(?:&&|\|\||[;|\n])", command):
    try:
        tokens = shlex.split(segment, posix=True)
    except ValueError:
        tokens = segment.split()
    lowered = [token.lower() for token in tokens]
    for index, token in enumerate(lowered):
        executable = token.rsplit("/", 1)[-1]
        if executable in {"pkill", "killall"}:
            deny(
                "AsynCodeBench control-plane protection: pkill and killall are "
                "disabled because the workspace agent server shares this container. "
                "Inspect the exact child PID and use `kill <PID>` instead."
            )
        if executable == "kill":
            targets = lowered[index + 1 :]
            if any(target in {"1", "-1"} for target in targets):
                deny(
                    "AsynCodeBench control-plane protection: signaling PID 1 or -1 "
                    "would terminate the workspace agent server. Signal only the "
                    "exact child PID."
                )

print(json.dumps({"decision": "allow"}))
"""


def control_plane_guard_command() -> str:
    """Return the self-contained command used by the server-side hook."""

    encoded = base64.b64encode(_CONTROL_PLANE_GUARD_PROGRAM.encode("utf-8")).decode(
        "ascii"
    )
    launcher = f"import base64;exec(base64.b64decode({encoded!r}))"
    return " ".join(["python", "-c", shlex.quote(launcher)])


def build_control_plane_guard_hook() -> HookConfig:
    """Build the mandatory guard installed on every native conversation."""

    return HookConfig(
        pre_tool_use=[
            HookMatcher(
                matcher="terminal",
                hooks=[
                    HookDefinition(
                        name="asyncodebench-control-plane-guard",
                        command=control_plane_guard_command(),
                        timeout=10,
                    )
                ],
            )
        ]
    )


def combine_hook_configs(*configs: HookConfig) -> HookConfig:
    """Combine benchmark-owned hooks without mutating their source configs."""

    fields = (
        "pre_tool_use",
        "post_tool_use",
        "user_prompt_submit",
        "session_start",
        "session_end",
        "stop",
    )
    return HookConfig(
        **{
            field: [item for config in configs for item in getattr(config, field)]
            for field in fields
        }
    )
