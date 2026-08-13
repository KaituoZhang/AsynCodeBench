"""AsynCodeBench Docker workspace compatibility for host networking."""

from __future__ import annotations

import os
import threading
import uuid
from typing import Any

from openhands.sdk.logger import get_logger
from openhands.sdk.utils.command import execute_command
from openhands.sdk.workspace import RemoteWorkspace
from openhands.workspace import DockerDevWorkspace, DockerWorkspace
from openhands.workspace.docker.workspace import (
    check_port_available,
    find_available_tcp_port,
)

logger = get_logger(__name__)


class _HostNetworkPortMixin:
    """Bind the agent server itself to the selected port on host networking."""

    def _start_container(self, image: str, context: Any) -> None:
        if self.network != "host":
            return super()._start_container(image, context)

        self._image_name = image
        if self.host_port is None:
            self.host_port = find_available_tcp_port()
        else:
            self.host_port = int(self.host_port)
        if self.host_port < 1:
            raise RuntimeError("Could not allocate an agent-server port")
        if not check_port_available(self.host_port):
            raise RuntimeError(f"Port {self.host_port} is not available")
        if self.extra_ports:
            raise ValueError(
                "extra_ports is unsupported with host networking; "
                "AsynCodeBench disables VSCode and VNC"
            )

        docker_ver = execute_command(["docker", "version"]).returncode
        if docker_ver != 0:
            raise RuntimeError("Docker is unavailable")

        flags: list[str] = []
        for key in self.forward_env:
            if key in os.environ:
                flags += ["-e", f"{key}={os.environ[key]}"]
        for volume in self.volumes:
            flags += ["-v", volume]
            logger.info(f"Adding volume mount: {volume}")
        if self.enable_gpu:
            flags += ["--gpus", "all"]
        flags += ["--network", "host"]

        run_cmd = [
            "docker",
            "run",
            "-d",
            "--platform",
            self.platform,
            "--rm",
            "--ulimit",
            "nofile=65536:65536",
            "--name",
            f"agent-server-{uuid.uuid4()}",
            *flags,
            image,
            "--host",
            "0.0.0.0",
            "--port",
            str(self.host_port),
        ]
        proc = execute_command(run_cmd)
        if proc.returncode != 0:
            raise RuntimeError(f"Failed to run Docker container: {proc.stderr}")

        self._container_id = proc.stdout.strip()
        logger.info(
            f"Started host-network container {self._container_id} "
            f"on port {self.host_port}"
        )
        if self.detach_logs:
            self._logs_thread = threading.Thread(
                target=self._stream_docker_logs,
                daemon=True,
            )
            self._logs_thread.start()

        if not self.host:
            object.__setattr__(self, "host", f"http://127.0.0.1:{self.host_port}")
        object.__setattr__(self, "api_key", None)
        self._wait_for_health(timeout=self.health_check_timeout)
        logger.info(f"Docker workspace is ready at {self.host}")
        RemoteWorkspace.model_post_init(self, context)


class AsynCodeBenchDockerWorkspace(_HostNetworkPortMixin, DockerWorkspace):
    """DockerWorkspace with correct host-network port binding."""


class AsynCodeBenchDockerDevWorkspace(_HostNetworkPortMixin, DockerDevWorkspace):
    """DockerDevWorkspace with correct host-network port binding."""
