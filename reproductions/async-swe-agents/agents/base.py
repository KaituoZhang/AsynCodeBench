"""Stable execution contract for third-party coding agents.

The harness owns task materialization, worktree isolation, dependency ordering,
scope validation, integration, probes, and final evaluation. An adapter owns
only one model-facing assignment execution inside the workspace supplied here.
"""

import hashlib
import importlib.metadata
import inspect
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class AgentRunRequest:
    """One benchmark-controlled coding assignment passed to an agent adapter."""

    schema_version: str
    benchmark_task_id: str
    source_task_id: str
    protocol: str
    scenario_id: str
    agent_id: str
    assignment_id: str
    round_num: int
    instruction: str
    workspace_path: str
    writable_paths: tuple[str, ...]
    primary_test_targets: tuple[str, ...]
    dependency_annotations: tuple[dict[str, Any], ...]
    model: str | None
    max_iterations: int
    output_dir: str
    workspace: Any = field(repr=False, compare=False)
    llm: Any = field(default=None, repr=False, compare=False)

    def public_metadata(self):
        """Return the serializable, non-secret portion of the request."""

        return {
            "schema_version": self.schema_version,
            "benchmark_task_id": self.benchmark_task_id,
            "source_task_id": self.source_task_id,
            "protocol": self.protocol,
            "scenario_id": self.scenario_id,
            "agent_id": self.agent_id,
            "assignment_id": self.assignment_id,
            "round_num": self.round_num,
            "instruction": self.instruction,
            "workspace_path": self.workspace_path,
            "writable_paths": list(self.writable_paths),
            "primary_test_targets": list(self.primary_test_targets),
            "dependency_annotations": list(self.dependency_annotations),
            "model": self.model,
            "max_iterations": self.max_iterations,
            "output_dir": self.output_dir,
        }


@dataclass
class AgentRunResponse:
    """Execution telemetry returned by an adapter.

    Patch success is intentionally not reported by the adapter. The harness
    derives it from git state and the evaluator so an adapter cannot self-grade.
    """

    error: str | None = None
    cost: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    iterations: int = 0
    events: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def coerce(cls, value):
        if value is None:
            return cls()
        if isinstance(value, cls):
            return value
        if isinstance(value, dict):
            return cls(**value)
        raise TypeError(
            "AgentAdapter.execute() must return AgentRunResponse, dict, or None; "
            f"received {type(value).__name__}"
        )


class AgentAdapter(ABC):
    """Base class implemented by third-party coding-agent integrations."""

    name = "custom"
    uses_native_single_agent = False

    def __init__(self, config=None):
        self.config = dict(config or {})

    @abstractmethod
    def execute(self, request: AgentRunRequest) -> AgentRunResponse | dict | None:
        """Execute one assignment and modify only ``request.workspace_path``."""

    def create_runner(self, **kwargs):
        """Create the harness-owned lifecycle wrapper for this adapter."""

        from .runner import AdapterSubAgentRunner

        return AdapterSubAgentRunner(adapter=self, **kwargs)

    def public_metadata(self):
        """Return provenance that is safe to persist in benchmark outputs."""

        cls = type(self)
        module_name = cls.__module__
        import_package = module_name.split(".", 1)[0]
        distributions = importlib.metadata.packages_distributions().get(
            import_package, []
        )
        package_name = distributions[0] if distributions else import_package
        try:
            package_version = importlib.metadata.version(package_name)
        except importlib.metadata.PackageNotFoundError:
            package_version = None
        source_sha256 = None
        try:
            source_path = inspect.getsourcefile(cls)
            if source_path:
                with open(source_path, "rb") as stream:
                    source_sha256 = hashlib.sha256(stream.read()).hexdigest()
        except OSError:
            pass
        return {
            "name": self.name,
            "class": f"{module_name}:{cls.__qualname__}",
            "package": package_name,
            "package_version": package_version,
            "source_sha256": source_sha256,
        }
