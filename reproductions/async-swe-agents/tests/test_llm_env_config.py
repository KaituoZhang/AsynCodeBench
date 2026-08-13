from types import SimpleNamespace

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


def test_condenser_budget_reserves_output_window(monkeypatch):
    monkeypatch.delenv("ASYNCODEBENCH_CONDENSER_MAX_TOKENS", raising=False)
    llm = SimpleNamespace(max_input_tokens=131072, max_output_tokens=32768)

    assert condenser_max_tokens(llm) == 98304


def test_explicit_condenser_budget_must_be_positive(monkeypatch):
    monkeypatch.setenv("ASYNCODEBENCH_CONDENSER_MAX_TOKENS", "0")

    try:
        condenser_max_tokens(SimpleNamespace())
    except ValueError as exc:
        assert "must be positive" in str(exc)
    else:
        raise AssertionError("non-positive condenser threshold was accepted")
