"""Built-in adapter preserving the existing OpenHands agent implementation."""

from .base import AgentAdapter


class OpenHandsAgentAdapter(AgentAdapter):
    name = "openhands"
    uses_native_single_agent = True

    def execute(self, request):
        raise RuntimeError(
            "OpenHandsAgentAdapter executes through its native SubAgentRunner"
        )

    def create_runner(self, **kwargs):
        from core.subagent import SubAgentRunner

        kwargs.pop("protocol", None)
        return SubAgentRunner(**kwargs)
