import json

from asyncodebench_harness import cli


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def test_online_doctor_checks_auth_completion_and_forced_tool_call(monkeypatch):
    requests = []

    def fake_urlopen(http_request, timeout):
        requests.append((http_request, timeout))
        if http_request.full_url.endswith("/models"):
            return FakeResponse({"data": [{"id": "Qwen/Qwen3.6-27B"}]})
        payload = json.loads(http_request.data)
        assert payload["model"] == "Qwen/Qwen3.6-27B"
        assert payload["tool_choice"]["function"]["name"] == (
            "asyncodebench_healthcheck"
        )
        return FakeResponse(
            {
                "choices": [
                    {
                        "message": {
                            "tool_calls": [
                                {
                                    "type": "function",
                                    "function": {
                                        "name": "asyncodebench_healthcheck",
                                        "arguments": '{"status":"ready"}',
                                    },
                                }
                            ]
                        }
                    }
                ]
            }
        )

    monkeypatch.setattr(cli.request, "urlopen", fake_urlopen)
    checks = cli._online_doctor_checks(
        base_url="http://127.0.0.1:8006/v1/",
        api_key="dummy-key",
        model="openai/Qwen/Qwen3.6-27B",
        timeout=12,
    )

    assert checks == [
        {"name": "model_api_auth", "ok": True},
        {"name": "model_completion", "ok": True},
        {"name": "model_tool_call", "ok": True},
    ]
    assert len(requests) == 2
    assert requests[0][0].get_header("Authorization") == "Bearer dummy-key"
    assert all(timeout == 12 for _, timeout in requests)


def test_api_model_id_strips_litellm_provider_prefix():
    assert (
        cli._api_model_id(
            "openrouter/qwen/qwen3-coder",
            {"data": [{"id": "qwen/qwen3-coder"}]},
        )
        == "qwen/qwen3-coder"
    )


def test_provider_prefix_check_rejects_bare_served_model_name():
    assert cli._has_litellm_provider_prefix("openai/Qwen/Qwen3.6-27B") is True
    assert cli._has_litellm_provider_prefix("openrouter/qwen/qwen3-coder") is True
    assert cli._has_litellm_provider_prefix("Qwen/Qwen3.6-27B") is False


def test_online_doctor_reports_missing_tool_call(monkeypatch):
    responses = iter(
        [
            FakeResponse({"data": [{"id": "model"}]}),
            FakeResponse({"choices": [{"message": {"content": "ready"}}]}),
        ]
    )
    monkeypatch.setattr(cli.request, "urlopen", lambda *_args, **_kwargs: next(responses))

    checks = cli._online_doctor_checks(
        base_url="https://example.test/v1",
        api_key="key",
        model="openai/model",
        timeout=1,
    )

    assert checks[-1] == {
        "name": "model_tool_call",
        "ok": False,
        "detail": "expected forced tool call missing",
    }
