import pytest

from scripts import check_gemma4_server


def test_release_tuple_handles_suffixes():
    assert check_gemma4_server.release_tuple("0.24.0.dev12") == (0, 24, 0)


def test_validate_server_accepts_unified_parser_release(monkeypatch):
    payloads = {
        "http://127.0.0.1:8006/version": {"version": "0.24.0"},
        "http://127.0.0.1:8006/v1/models": {
            "data": [
                {
                    "id": "google/gemma-4-26B-A4B-it",
                    "max_model_len": 135168,
                }
            ]
        },
    }
    monkeypatch.setattr(
        check_gemma4_server,
        "read_json",
        lambda url, timeout=30.0: payloads[url],
    )

    result = check_gemma4_server.validate_server(
        "http://127.0.0.1:8006/v1",
        "google/gemma-4-26B-A4B-it",
        "0.24.0",
    )

    assert result["vllm_version"] == "0.24.0"
    assert result["max_model_len"] == 135168


def test_validate_server_rejects_legacy_split_parser(monkeypatch):
    monkeypatch.setattr(
        check_gemma4_server,
        "read_json",
        lambda _url, timeout=30.0: {"version": "0.19.1"},
    )

    with pytest.raises(RuntimeError, match="require vLLM >= 0.24.0"):
        check_gemma4_server.validate_server(
            "http://127.0.0.1:8006/v1",
            "google/gemma-4-26B-A4B-it",
            "0.24.0",
        )
