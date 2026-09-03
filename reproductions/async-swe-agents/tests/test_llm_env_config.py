from types import SimpleNamespace

from core.manager import Manager
from core.subagent import condenser_max_tokens
from core.utils import build_llm_kwargs
from pydantic import SecretStr


def test_build_llm_kwargs_includes_explicit_context_window(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("LLM_BASE_URL", "http://127.0.0.1:8006/v1")
    monkeypatch.setenv("LLM_MAX_INPUT_TOKENS", "131072")
    monkeypatch.setenv("LLM_MAX_OUTPUT_TOKENS", "32768")

    kwargs = build_llm_kwargs("openai/google/gemma-4-26B-A4B-it")

    assert kwargs["api_key"] == SecretStr("test-key")
    assert kwargs["max_input_tokens"] == 131072
    assert kwargs["max_output_tokens"] == 32768


def test_build_llm_kwargs_rejects_invalid_context_window(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("LLM_BASE_URL", "http://127.0.0.1:8006/v1")
    monkeypatch.setenv("LLM_MAX_INPUT_TOKENS", "not-an-integer")

    try:
        build_llm_kwargs("openai/test-model")
    except ValueError as exc:
        assert str(exc) == "LLM_MAX_INPUT_TOKENS must be an integer"
    else:
        raise AssertionError("invalid LLM_MAX_INPUT_TOKENS was accepted")


def test_condenser_budget_reserves_output_window_and_safety_margin(monkeypatch):
    monkeypatch.delenv("ASYNCODEBENCH_CONDENSER_MAX_TOKENS", raising=False)
    llm = SimpleNamespace(max_input_tokens=131072, max_output_tokens=32768)

    assert condenser_max_tokens(llm) == 88473


def test_explicit_condenser_budget_must_be_positive(monkeypatch):
    monkeypatch.setenv("ASYNCODEBENCH_CONDENSER_MAX_TOKENS", "0")

    try:
        condenser_max_tokens(SimpleNamespace())
    except ValueError as exc:
        assert "must be positive" in str(exc)
    else:
        raise AssertionError("non-positive condenser threshold was accepted")


def test_single_agent_uses_history_condenser(monkeypatch):
    captured = {}
    condenser = object()

    class FakeLLM:
        max_input_tokens = 131072
        max_output_tokens = 32768

        def model_copy(self, update):
            assert update == {"usage_id": "condenser"}
            return self

    monkeypatch.setattr("core.manager.get_default_tools", lambda **_: [])
    monkeypatch.setattr(
        "core.manager.LLMSummarizingCondenser", lambda **_: condenser
    )
    monkeypatch.setattr(
        "core.manager.Agent", lambda **kwargs: captured.update(kwargs) or object()
    )
    monkeypatch.setattr("core.manager.Conversation", lambda **_: object())
    monkeypatch.setattr("core.manager.PanelVisualizer", lambda: object())

    task = SimpleNamespace(
        get_work_dir=lambda: "/workspace/repo",
        get_prompt_format_args=lambda config: {},
    )
    config = SimpleNamespace(manager_max_iterations=100)
    manager = Manager(FakeLLM(), object(), task, config, None, prompts={})

    manager.setup(mode="single_agent")

    assert captured["condenser"] is condenser


def test_read_only_multi_agent_manager_has_no_file_editor(monkeypatch):
    captured = {}
    condenser = object()
    tools = [
        SimpleNamespace(name="terminal"),
        SimpleNamespace(name="file_editor"),
    ]

    class FakeLLM:
        max_input_tokens = 131072
        max_output_tokens = 32768

        def model_copy(self, update):
            assert update == {"usage_id": "condenser"}
            return self

    monkeypatch.setattr("core.manager.get_default_tools", lambda **_: tools)
    monkeypatch.setattr(
        "core.manager.LLMSummarizingCondenser", lambda **_: condenser
    )
    monkeypatch.setattr(
        "core.manager.Agent", lambda **kwargs: captured.update(kwargs) or object()
    )
    monkeypatch.setattr("core.manager.Conversation", lambda **_: object())
    monkeypatch.setattr("core.manager.PanelVisualizer", lambda: object())

    task = SimpleNamespace(
        manager_must_be_read_only=True,
        active_protocol="caid_manager",
        get_work_dir=lambda: "/workspace/repo",
        get_prompt_format_args=lambda config: {},
    )
    config = SimpleNamespace(manager_max_iterations=100)
    manager = Manager(
        FakeLLM(),
        object(),
        task,
        config,
        None,
        prompts={"user_instruction": ""},
    )

    manager.setup(mode="multi_agent")

    assert [tool.name for tool in captured["tools"]] == ["terminal"]
