from __future__ import annotations

import json
from pathlib import Path

from asyncodebench.contracts.export import (
    PUBLIC_CONTRACTS,
    export_public_schemas,
)


def test_export_public_schemas(tmp_path: Path) -> None:
    written = export_public_schemas(tmp_path)

    assert len(written) == len(PUBLIC_CONTRACTS)
    assert {path.stem.removesuffix(".schema") for path in written} == set(
        PUBLIC_CONTRACTS
    )
    for path in written:
        schema = json.loads(path.read_text(encoding="utf-8"))
        assert schema["type"] == "object"
        assert "schema_version" in schema["properties"]
