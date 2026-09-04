"""Deny agent-initiated network clients in offline benchmark tasks."""

from __future__ import annotations

import base64
import shlex

from openhands.sdk.hooks import HookConfig, HookDefinition, HookMatcher

AGENT_NETWORK_POLICY_VERSION = "agent-terminal-egress-v1"


_NETWORK_GUARD_PROGRAM = r'''
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
    deny("AsynCodeBench network guard could not parse the tool request: " + str(error))

if str(event.get("tool_name") or "") != "terminal":
    print(json.dumps({"decision": "allow"}))
    raise SystemExit(0)

tool_input = event.get("tool_input") or {}
command = tool_input.get("command")
if not isinstance(command, str):
    print(json.dumps({"decision": "allow"}))
    raise SystemExit(0)

network_clients = {
    "curl", "wget", "aria2c", "ftp", "sftp", "ssh", "scp", "rsync",
    "nc", "ncat", "netcat", "telnet", "socat",
}
package_managers = {
    "apt", "apt-get", "pip", "pip3", "conda", "mamba", "npm", "yarn",
    "pnpm", "gem", "cargo", "go",
}
git_network_actions = {"clone", "fetch", "pull", "ls-remote", "remote", "submodule"}

if re.search(r"(?:https?|ftp|ssh|git)://", command, re.IGNORECASE):
    deny("AsynCodeBench offline-task policy: URL access is disabled for agent tools.")

for segment in re.split(r"(?:&&|\|\||[;|\n])", command):
    try:
        tokens = shlex.split(segment, posix=True)
    except ValueError:
        tokens = segment.split()
    lowered = [token.lower() for token in tokens]
    for index, token in enumerate(lowered):
        executable = token.rsplit("/", 1)[-1]
        if executable in network_clients:
            deny(
                "AsynCodeBench offline-task policy: network client "
                + executable + " is disabled."
            )
        if executable in package_managers and any(
            action in lowered[index + 1 :] for action in {"install", "update", "upgrade"}
        ):
            deny(
                "AsynCodeBench offline-task policy: dependency downloads are disabled."
            )
        if executable == "git" and any(
            action in lowered[index + 1 :] for action in git_network_actions
        ):
            deny("AsynCodeBench offline-task policy: Git network operations are disabled.")

print(json.dumps({"decision": "allow"}))
'''


def network_guard_command() -> str:
    encoded = base64.b64encode(_NETWORK_GUARD_PROGRAM.encode("utf-8")).decode("ascii")
    launcher = f"import base64;exec(base64.b64decode({encoded!r}))"
    return " ".join(["python", "-c", shlex.quote(launcher)])


def build_network_guard_hook() -> HookConfig:
    return HookConfig(
        pre_tool_use=[
            HookMatcher(
                matcher="terminal",
                hooks=[
                    HookDefinition(
                        name="asyncodebench-agent-network-guard",
                        command=network_guard_command(),
                        timeout=10,
                    )
                ],
            )
        ]
    )
