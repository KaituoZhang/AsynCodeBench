"""Agent adapter loading and validation."""

import importlib
import inspect
import json

from .base import AgentAdapter
from .openhands import OpenHandsAgentAdapter


def parse_agent_config(value):
    if value in (None, ""):
        return {}
    if isinstance(value, dict):
        return dict(value)
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError(f"agent_config_json must be valid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ValueError("agent_config_json must decode to a JSON object")
    return parsed


def _import_symbol(import_path):
    module_name, separator, attribute_path = str(import_path).partition(":")
    if not separator or not module_name or not attribute_path:
        raise ValueError(
            "agent_import_path must use 'python.module:AdapterClass' format"
        )
    module = importlib.import_module(module_name)
    value = module
    for component in attribute_path.split("."):
        value = getattr(value, component)
    return value


def load_agent_adapter(
    agent="openhands",
    agent_import_path=None,
    agent_config_json=None,
):
    """Load a built-in or import-path adapter and enforce the public contract."""

    config = parse_agent_config(agent_config_json)
    if agent_import_path:
        symbol = _import_symbol(agent_import_path)
        adapter = symbol(config=config) if inspect.isclass(symbol) else symbol
    elif agent == "openhands":
        adapter = OpenHandsAgentAdapter(config=config)
    else:
        raise ValueError(
            f"Unknown built-in agent {agent!r}. Use agent='openhands' or provide "
            "agent_import_path='python.module:AdapterClass'."
        )

    if not isinstance(adapter, AgentAdapter):
        raise TypeError(
            "Loaded object must be an instance of agents.AgentAdapter; "
            f"received {type(adapter).__module__}:{type(adapter).__qualname__}"
        )
    return adapter


def create_agent_runner(agent_adapter, protocol, **runner_kwargs):
    """Route one harness assignment through the selected adapter factory."""

    if agent_adapter is None:
        from core.subagent import SubAgentRunner

        return SubAgentRunner(**runner_kwargs)
    return agent_adapter.create_runner(protocol=protocol, **runner_kwargs)
