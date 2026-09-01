from types import SimpleNamespace

import core.workspace as workspace_module
from core.workspace import AsynCodeBenchDockerWorkspace, NONINTERACTIVE_PAGER_ENV
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
    run_command = next(command for command in commands if command[:2] == ["docker", "run"])

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
