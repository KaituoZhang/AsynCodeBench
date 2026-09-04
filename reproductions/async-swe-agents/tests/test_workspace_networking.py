import subprocess
import sys
import time
from types import SimpleNamespace

import core.workspace as workspace_module
import pytest
from core.workspace import (
    NONINTERACTIVE_PAGER_ENV,
    AsynCodeBenchDockerDevWorkspace,
    AsynCodeBenchDockerWorkspace,
)
from openhands.sdk.workspace import RemoteWorkspace
from openhands.workspace import DockerWorkspace


def test_host_network_workspace_binds_server_to_selected_port(monkeypatch):
    commands = []

    original_env = {
        key: f"original-{key.lower()}" for key in NONINTERACTIVE_PAGER_ENV
    }
    for key, value in original_env.items():
        monkeypatch.setenv(key, value)

    def fake_execute(command):
        commands.append(command)
        stdout = "container-id\n" if command[:2] == ["docker", "run"] else ""
        return SimpleNamespace(returncode=0, stdout=stdout, stderr="")

    monkeypatch.setattr(workspace_module, "execute_command", fake_execute)
    monkeypatch.setattr(workspace_module, "check_port_available", lambda _port: True)
    monkeypatch.setattr(
        AsynCodeBenchDockerWorkspace,
        "_wait_for_health",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        RemoteWorkspace,
        "model_post_init",
        lambda *_args, **_kwargs: None,
    )

    workspace = AsynCodeBenchDockerWorkspace(
        server_image="example/agent-server:test",
        host_port=24567,
        network="host",
        detach_logs=False,
    )
    run_command = next(
        command for command in commands if command[:2] == ["docker", "run"]
    )

    assert run_command[-4:] == ["--host", "0.0.0.0", "--port", "24567"]
    assert run_command[run_command.index("--network") + 1] == "host"
    assert "-p" not in run_command
    assert workspace.host == "http://127.0.0.1:24567"

    forwarded_env = {
        run_command[index + 1]
        for index, value in enumerate(run_command[:-1])
        if value == "-e"
    }
    assert {
        f"{key}={value}" for key, value in NONINTERACTIVE_PAGER_ENV.items()
    }.issubset(forwarded_env)
    assert workspace.forward_env[-4:] == list(NONINTERACTIVE_PAGER_ENV)
    for key, value in original_env.items():
        assert workspace_module.os.environ[key] == value

    workspace._container_id = None


def test_standard_network_workspace_forwards_noninteractive_pagers(monkeypatch):
    observed = {}
    original_env = {
        key: f"original-{key.lower()}" for key in NONINTERACTIVE_PAGER_ENV
    }
    for key, value in original_env.items():
        monkeypatch.setenv(key, value)

    def fake_parent_start(self, image, context):
        observed["image"] = image
        observed["forward_env"] = list(self.forward_env)
        observed["environment"] = {
            key: workspace_module.os.environ[key]
            for key in NONINTERACTIVE_PAGER_ENV
        }

    monkeypatch.setattr(DockerWorkspace, "_start_container", fake_parent_start)

    workspace = AsynCodeBenchDockerWorkspace(
        server_image="example/agent-server:test",
        network=None,
        detach_logs=False,
    )

    assert observed["image"] == "example/agent-server:test"
    assert observed["environment"] == NONINTERACTIVE_PAGER_ENV
    assert observed["forward_env"][-4:] == list(NONINTERACTIVE_PAGER_ENV)
    for key, value in original_env.items():
        assert workspace_module.os.environ[key] == value

    workspace._container_id = None


def test_cpu_limited_workspace_passes_docker_quota(monkeypatch):
    commands = []

    def fake_execute(command):
        commands.append(command)
        stdout = "container-id\n" if command[:2] == ["docker", "run"] else ""
        return SimpleNamespace(returncode=0, stdout=stdout, stderr="")

    monkeypatch.setattr(workspace_module, "execute_command", fake_execute)
    monkeypatch.setattr(workspace_module, "check_port_available", lambda _port: True)
    monkeypatch.setattr(
        AsynCodeBenchDockerWorkspace,
        "_wait_for_health",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        RemoteWorkspace,
        "model_post_init",
        lambda *_args, **_kwargs: None,
    )

    workspace = AsynCodeBenchDockerWorkspace(
        server_image="example/agent-server:test",
        host_port=24568,
        cpu_limit=28,
        detach_logs=False,
    )
    run_command = next(
        command for command in commands if command[:2] == ["docker", "run"]
    )

    assert run_command[run_command.index("--cpus") + 1] == "28"
    assert run_command[run_command.index("-p") + 1] == "24568:8000"
    assert run_command[-1] == "8000"
    workspace._container_id = None


def test_dev_workspace_reuses_locked_agent_server_image(monkeypatch):
    commands = []

    def fake_execute(command):
        commands.append(command)
        return SimpleNamespace(returncode=0, stdout="[]", stderr="")

    monkeypatch.setattr(workspace_module, "execute_command", fake_execute)
    monkeypatch.delenv("ASYNCODEBENCH_REBUILD_AGENT_SERVER_IMAGE", raising=False)

    image = AsynCodeBenchDockerDevWorkspace._build_image_from_base(
        base_image="docker.io/wentingzhao/graphene:v0",
        target="source-minimal",
        platform="linux/amd64",
    )

    assert commands == [
        ["docker", "image", "inspect", "--format", "{{.Id}}", image]
    ]
    assert image.startswith("ghcr.io/openhands/agent-server:")
    assert image.endswith("-source-minimal")


def test_build_command_does_not_wait_for_descendant_pipe_eof(monkeypatch):
    monkeypatch.setenv("ASYNCODEBENCH_AGENT_SERVER_BUILD_TIMEOUT", "10")
    child_code = (
        "import subprocess, sys; "
        "subprocess.Popen([sys.executable, '-c', "
        "'import time; time.sleep(2)']); "
        "print('direct child complete')"
    )

    started = time.monotonic()
    result = workspace_module._run_agent_server_build_command(
        [sys.executable, "-c", child_code]
    )
    elapsed = time.monotonic() - started

    assert result.returncode == 0
    assert result.stdout.strip() == "direct child complete"
    assert elapsed < 1.5


def test_build_command_has_bounded_timeout(monkeypatch):
    monkeypatch.setenv("ASYNCODEBENCH_AGENT_SERVER_BUILD_TIMEOUT", "0.1")

    with pytest.raises(subprocess.CalledProcessError) as exc_info:
        workspace_module._run_agent_server_build_command(
            [sys.executable, "-c", "import time; time.sleep(10)"]
        )

    assert exc_info.value.returncode == 124
    assert "timed out after 0.1 seconds" in exc_info.value.stderr
