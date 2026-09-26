"""Canonical task-budgeted Async-Manager protocol for AsynCodeBench."""

PROTOCOL = "async_manager"
POLICY = "async-manager-online-v2-budgeted"
LEGACY_POLICY = "async-manager-online-v1"
BASE_PROTOCOL = LEGACY_POLICY

__all__ = ["BASE_PROTOCOL", "LEGACY_POLICY", "POLICY", "PROTOCOL"]
