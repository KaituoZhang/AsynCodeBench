"""Harness-owned incremental native builds before a manager test command."""

import base64
import shlex

from openhands.sdk.hooks import HookConfig, HookDefinition, HookMatcher

PROGRAM = r"""
import json, shlex, subprocess, sys
root, build = sys.argv[1:]
event = json.load(sys.stdin)
command = (event.get('tool_input') or {}).get('command', '')
try:
    tokens = shlex.split(command)
    tests = any(token.rsplit('/', 1)[-1] in {'pytest', 'py.test', 'unittest'}
                for token in tokens)
    if event.get('tool_name') != 'terminal' or not tests:
        print(json.dumps({'decision': 'allow'}))
    else:
        result = subprocess.run(build, cwd=root, shell=True, capture_output=True,
                                text=True, timeout=1800)
        if result.returncode:
            reason = 'Current-source native build failed: '
            print(json.dumps({'decision': 'deny', 'reason': reason
                              + (result.stdout + result.stderr)[-3000:]}))
        else:
            print(json.dumps({'decision': 'allow'}))
except Exception as error:
    reason = 'Native build could not be verified: ' + str(error)
    print(json.dumps({'decision': 'deny', 'reason': reason}))
"""


def runtime_command(root, build):
    encoded = base64.b64encode(PROGRAM.encode()).decode()
    return " ".join(
        map(
            shlex.quote,
            [
                "python",
                "-c",
                f"import base64;exec(base64.b64decode({encoded!r}))",
                root,
                build,
            ],
        )
    )


def build_runtime_hook(root, build):
    return HookConfig(
        pre_tool_use=[
            HookMatcher(
                matcher="terminal",
                hooks=[
                    HookDefinition(
                        name="async-manager-current-source-runtime",
                        command=runtime_command(root, build),
                        timeout=1830,
                    )
                ],
            )
        ]
    )
