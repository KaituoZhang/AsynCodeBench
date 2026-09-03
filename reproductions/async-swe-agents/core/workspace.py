"""AsynCodeBench Docker workspace compatibility for host networking."""

from __future__ import annotations

import os
import signal
import subprocess
import tempfile
import threading
import uuid
from contextlib import suppress
from typing import Any

from openhands.sdk.logger import get_logger
from openhands.sdk.utils.command import execute_command
from openhands.sdk.workspace import PlatformType, RemoteWorkspace, TargetType
from openhands.workspace import DockerDevWorkspace, DockerWorkspace
from openhands.workspace.docker.workspace import (
    check_port_available,
    find_available_tcp_port,
)

logger = get_logger(__name__)


# Agent commands run without a human attached to their terminal.  Interactive
# pagers can therefore block a benchmark indefinitely (for example, pydoc's
# ``help()`` and ``git show`` both invoke a pager when they detect a TTY).
NONINTERACTIVE_PAGER_ENV = {
    "PAGER": "cat",
    "GIT_PAGER": "cat",
    "MANPAGER": "cat",
    "SYSTEMD_PAGER": "cat",
}


def _agent_server_build_timeout_seconds() -> float:
    """Bound agent-server image construction without changing task runtime."""
    raw_value = os.getenv("ASYNCODEBENCH_AGENT_SERVER_BUILD_TIMEOUT", "3600")
    try:
        timeout = float(raw_value)
    except ValueError as error:
        raise ValueError(
            "ASYNCODEBENCH_AGENT_SERVER_BUILD_TIMEOUT must be numeric"
        ) from error
    if timeout <= 0:
        raise ValueError(
            "ASYNCODEBENCH_AGENT_SERVER_BUILD_TIMEOUT must be positive"
        )
    return timeout


def _run_agent_server_build_command(
    command: list[str],
    cwd: str | None = None,
) -> subprocess.CompletedProcess:
    """Run an SDK image-build command without waiting on inherited pipes.

    BuildKit helpers can outlive the ``docker buildx`` client while retaining
    its stdout or stderr file descriptor. A pipe-pumping parent then waits for
    EOF forever even though Docker has already created the requested image.
    Regular temporary files preserve complete diagnostics but let us reap the
    direct child as soon as it exits.
    """
    logger.info("$ %s (cwd=%s)", " ".join(command), cwd)
    timeout = _agent_server_build_timeout_seconds()

    with (
        tempfile.TemporaryFile(mode="w+", encoding="utf-8") as stdout_file,
        tempfile.TemporaryFile(mode="w+", encoding="utf-8") as stderr_file,
    ):
        process = subprocess.Popen(
            command,
            cwd=cwd,
            text=True,
            stdout=stdout_file,
            stderr=stderr_file,
            start_new_session=True,
        )
        timed_out = False
        try:
            return_code = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            with suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                with suppress(ProcessLookupError):
                    os.killpg(process.pid, signal.SIGKILL)
                process.wait()
            return_code = 124

        stdout_file.flush()
        stderr_file.flush()
        stdout_file.seek(0)
        stderr_file.seek(0)
        stdout = stdout_file.read()
        stderr = stderr_file.read()

    if timed_out:
        stderr += (
            "\nAsynCodeBench agent-server image build timed out after "
            f"{timeout:g} seconds.\n"
        )

    for line in stdout.splitlines():
        logger.info("[build stdout] %s", line)
    for line in stderr.splitlines():
        logger.warning("[build stderr] %s", line)

    result = subprocess.CompletedProcess(
        command,
        return_code,
        stdout=stdout,
        stderr=stderr,
    )
    if return_code != 0:
        raise subprocess.CalledProcessError(
            return_code,
            command,
            output=stdout,
            stderr=stderr,
        )
    return result


class _HostNetworkPortMixin:
    """Bind the agent server itself to the selected port on host networking."""

    def _start_container(self, image: str, context: Any) -> None:
        # DockerWorkspace forwards named variables from the host environment.
        # Install deterministic noninteractive values only while constructing
        # the container, then restore the caller's environment.  Keeping the
        # names in forward_env also covers the upstream non-host-network path.
        previous = {key: os.environ.get(key) for key in NONINTERACTIVE_PAGER_ENV}
        for key, value in NONINTERACTIVE_PAGER_ENV.items():
            os.environ[key] = value
            if key not in self.forward_env:
                self.forward_env.append(key)

        try:
            return self._start_container_with_pager_env(image, context)
        finally:
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    def _start_container_with_pager_env(self, image: str, context: Any) -> None:
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

    @staticmethod
    def _build_image_from_base(
        *, base_image: str, target: TargetType, platform: PlatformType
    ) -> str:
        """Reuse a locked local image and harden the SDK build subprocess."""
        import importlib

        build_module = importlib.import_module(
            "openhands.agent_server.docker.build"
        )
        options = build_module.BuildOptions(
            base_image=base_image,
            target=target,
            platforms=[platform],
            push=False,
        )
        expected_tags = options.all_tags
        if not expected_tags:
            raise RuntimeError("Agent-server build produced no deterministic tag")
        expected_tag = expected_tags[0]

        force_rebuild = os.getenv(
            "ASYNCODEBENCH_REBUILD_AGENT_SERVER_IMAGE", "0"
        ) == "1"
        if not force_rebuild:
            inspection = execute_command(
                ["docker", "image", "inspect", "--format", "{{.Id}}", expected_tag]
            )
            if inspection.returncode == 0:
                logger.info("Reusing locked agent-server image: %s", expected_tag)
                return expected_tag

        original_run = build_module._run
        build_module._run = _run_agent_server_build_command
        try:
            tags = build_module.build(opts=options)
        finally:
            build_module._run = original_run
        if not tags:
            raise RuntimeError("Agent-server build returned no image tags")
        return tags[0]
