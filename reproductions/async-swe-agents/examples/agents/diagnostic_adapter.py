"""Non-solving adapter used to verify custom-agent wiring without an API key.

This adapter intentionally makes no code change and is not suitable for an
official result. Copy its structure when integrating an agent controller.
"""

from agents import AgentAdapter, AgentRunResponse


class DiagnosticAgentAdapter(AgentAdapter):
    name = "diagnostic-noop"

    def execute(self, request):
        result = request.workspace.execute_command(
            f"cd {request.workspace_path} && git status --short", timeout=30
        )
        error = None
        if result.exit_code != 0:
            error = result.stderr or result.stdout or "git status failed"
        return AgentRunResponse(
            error=error,
            iterations=1,
            events=[
                {
                    "event_type": "diagnostic_workspace_status",
                    "content": {
                        "exit_code": result.exit_code,
                        "status": (result.stdout or "").strip(),
                    },
                }
            ],
            metadata={"purpose": "adapter wiring smoke test only"},
        )
