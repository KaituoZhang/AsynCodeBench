from types import SimpleNamespace

import core.workspace as workspace_module
from core.workspace import AsynCodeBenchDockerWorkspace
from openhands.sdk.workspace import RemoteWorkspace


def test_host_network_workspace_binds_server_to_selected_port(monkeypatch):
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
        host_port=24567,
        network="host",
        detach_logs=False,
    )
    run_command = next(command for command in commands if command[:2] == ["docker", "run"])

    assert run_command[-4:] == ["--host", "0.0.0.0", "--port", "24567"]
    assert run_command[run_command.index("--network") + 1] == "host"
    assert "-p" not in run_command
    assert workspace.host == "http://127.0.0.1:24567"

    workspace._container_id = None
