import json
import subprocess

from core.network_guard import network_guard_command


def run_guard(command):
    return subprocess.run(
        network_guard_command(),
        input=json.dumps(
            {"tool_name": "terminal", "tool_input": {"command": command}}
        ),
        shell=True,
        capture_output=True,
        text=True,
        check=True,
    )


def test_network_guard_allows_local_build_and_tests():
    result = run_guard("cmake --build build --parallel 28 && pytest -q")
    assert json.loads(result.stdout)["decision"] == "allow"


def test_network_guard_denies_direct_download():
    result = run_guard("curl -L https://github.com/apache/tvm/pull/20153.patch")
    payload = json.loads(result.stdout)
    assert payload["decision"] == "deny"
    assert "offline-task policy" in payload["reason"]


def test_network_guard_denies_git_fetch():
    result = run_guard("git fetch origin pull/20153/head:solution")
    assert json.loads(result.stdout)["decision"] == "deny"
