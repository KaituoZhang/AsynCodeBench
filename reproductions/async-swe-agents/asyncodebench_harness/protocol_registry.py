"""Canonical public protocol identities and scenario aliases."""

from __future__ import annotations

import json
from pathlib import Path

PROTOCOL_ORDER = (
    "single",
    "serial_specialists",
    "async_private",
    "caid_manager",
    "async_manager",
)
SUPPORTED_PROTOCOLS = frozenset(PROTOCOL_ORDER)
SCENARIO_SOURCE_PROTOCOL = {"async_manager": "caid_manager"}
CURRENT_REGISTRY_RELATIVE_PATH = Path(
    "configs/evaluation/protocol_registry.v2.json"
)
HISTORICAL_REGISTRY_RELATIVE_PATHS = frozenset(
    {Path("configs/evaluation/protocol_registry.v1.json")}
)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def protocol_registry_path(relative_path: str | Path | None = None) -> Path:
    relative = (
        CURRENT_REGISTRY_RELATIVE_PATH
        if relative_path is None
        else Path(relative_path)
    )
    allowed = {CURRENT_REGISTRY_RELATIVE_PATH, *HISTORICAL_REGISTRY_RELATIVE_PATHS}
    if relative not in allowed:
        raise RuntimeError(f"Unsupported protocol registry: {relative}")
    return repo_root() / relative


def load_protocol_registry(relative_path: str | Path | None = None) -> dict:
    payload = json.loads(
        protocol_registry_path(relative_path).read_text(encoding="utf-8")
    )
    if tuple(payload.get("protocols", {})) != tuple(sorted(payload["protocols"])):
        # Stable JSON ordering makes the registry checksum reproducible.
        raise RuntimeError("Protocol registry entries must be sorted")
    if set(payload.get("protocols", {})) != SUPPORTED_PROTOCOLS:
        raise RuntimeError("Protocol registry does not match canonical protocols")
    return payload


def scenario_source_protocol(protocol: str) -> str:
    return SCENARIO_SOURCE_PROTOCOL.get(protocol, protocol)
