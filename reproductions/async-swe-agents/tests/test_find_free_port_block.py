from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SCRIPT = Path(__file__).parents[1] / "scripts" / "find_free_port_block.py"
SPEC = importlib.util.spec_from_file_location("find_free_port_block", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_find_free_port_block_skips_an_occupied_port(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        MODULE,
        "block_is_available",
        lambda base, count: base == 5002 and count == 2,
    )
    assert MODULE.find_free_port_block(start=5000, end=5010, count=2) == 5002


def test_find_free_port_block_rejects_invalid_range() -> None:
    try:
        MODULE.find_free_port_block(start=5000, end=5001, count=3)
    except ValueError as exc:
        assert "smaller" in str(exc)
    else:
        raise AssertionError("expected ValueError")
