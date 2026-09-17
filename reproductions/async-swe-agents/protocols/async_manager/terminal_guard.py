"""Read-only shell policy for an otherwise writable online manager.

The released CAID guard already implements the audited shell parser.  This
protocol reuses that pinned parser while changing its policy identity so a
denial cannot be mistaken for the Async-RO-Manager protocol.  Production edits
remain available through the separately phase-gated file editor.
"""

from __future__ import annotations

import base64
import shlex

from protocols.async_manager.shell_policy import _READ_ONLY_MANAGER_GUARD_PROGRAM
from openhands.sdk.hooks import HookConfig, HookDefinition, HookMatcher

POLICY = "async-manager-terminal-read-only-v1"
PROGRAM = _READ_ONLY_MANAGER_GUARD_PROGRAM.replace(
    'POLICY_VERSION = "caid-manager-read-only-v2"',
    f'POLICY_VERSION = "{POLICY}"',
).replace(
    "AsynCodeBench read-only manager policy (",
    "AsynCodeBench online-manager terminal policy (",
)


def command() -> str:
    encoded = base64.b64encode(PROGRAM.encode("utf-8")).decode("ascii")
    launcher = f"import base64;exec(base64.b64decode({encoded!r}))"
    return " ".join(["python", "-c", shlex.quote(launcher)])


def build_terminal_guard() -> HookConfig:
    return HookConfig(
        pre_tool_use=[
            HookMatcher(
                matcher="terminal",
                hooks=[
                    HookDefinition(
                        name=POLICY,
                        command=command(),
                        timeout=10,
                    )
                ],
            )
        ]
    )
