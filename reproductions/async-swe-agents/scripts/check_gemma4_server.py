#!/usr/bin/env python3
"""Validate the vLLM metadata required by the Gemma 4 agent harness."""

from __future__ import annotations

import argparse
import json
import re
import urllib.request


def release_tuple(value: str) -> tuple[int, int, int]:
    parts = [int(item) for item in re.findall(r"\d+", value)[:3]]
    return tuple((parts + [0, 0, 0])[:3])


def server_root(base_url: str) -> str:
    normalized = base_url.rstrip("/")
    return normalized[:-3] if normalized.endswith("/v1") else normalized


def read_json(url: str, timeout: float = 30.0) -> dict:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.load(response)


def validate_server(
    base_url: str,
    expected_model: str,
    minimum_version: str,
    minimum_context: int | None = None,
) -> dict[str, object]:
    root = server_root(base_url)
    version_payload = read_json(f"{root}/version")
    version = str(version_payload.get("version") or "")
    if not version:
        raise RuntimeError("vLLM /version response did not contain a version")
    if release_tuple(version) < release_tuple(minimum_version):
        raise RuntimeError(
            f"Gemma 4 formal runs require vLLM >= {minimum_version}; "
            f"server reports {version}. The legacy split parser does not "
            "handle post-tool multi-turn state reliably."
        )

    models_payload = read_json(f"{base_url.rstrip('/')}/models")
    models = {
        str(item.get("id")): item
        for item in models_payload.get("data", [])
        if isinstance(item, dict)
    }
    if expected_model not in models:
        raise RuntimeError(
            f"Expected served model {expected_model!r}; found {sorted(models)}"
        )

    max_model_len = models[expected_model].get("max_model_len")
    if minimum_context is not None:
        if not isinstance(max_model_len, int) or max_model_len < minimum_context:
            raise RuntimeError(
                f"Gemma 4 server context is too small: found {max_model_len}, "
                f"require at least {minimum_context}. The client reserves "
                "131072 input tokens and 32768 output tokens."
            )

    return {
        "vllm_version": version,
        "model": expected_model,
        "max_model_len": max_model_len,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--minimum-version", default="0.24.0")
    parser.add_argument("--minimum-context", type=int)
    args = parser.parse_args()

    result = validate_server(
        base_url=args.base_url,
        expected_model=args.model,
        minimum_version=args.minimum_version,
        minimum_context=args.minimum_context,
    )
    print(
        "[Gemma4] server preflight passed: "
        f"vllm={result['vllm_version']} model={result['model']} "
        f"max_model_len={result['max_model_len']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
