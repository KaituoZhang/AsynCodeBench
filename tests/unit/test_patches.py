from __future__ import annotations

import pytest

from asynccodebench.contracts import ArtifactValidity
from asynccodebench.runtime import PatchApplicationError, apply_unified_diff

PATCH = """\
--- a/src/a.py
+++ b/src/a.py
@@ -1 +1 @@
-x = 1
+x = 2
"""


def test_patch_returns_updates_and_automatic_provenance() -> None:
    result = apply_unified_diff(
        {"src/a.py": "x = 1\n"},
        PATCH,
        producer="coder",
        source_workspace_version="workspace-source",
        start_event="event-start",
        finish_event="event-finish",
        allowed_paths=("src/a.py",),
        input_artifact_ids=("artifact-input",),
    )
    assert result.updates == {"src/a.py": "x = 2\n"}
    assert result.artifact.validity_status is ArtifactValidity.VALID
    assert result.artifact.source_workspace_version == "workspace-source"
    assert result.artifact.write_set == ("src/a.py",)
    assert result.artifact.input_artifact_ids == ("artifact-input",)


def test_patch_rejects_path_outside_editable_boundary() -> None:
    with pytest.raises(PatchApplicationError, match="editable boundary"):
        apply_unified_diff(
            {"src/a.py": "x = 1\n"},
            PATCH,
            producer="coder",
            source_workspace_version="workspace-source",
            start_event="event-start",
            finish_event="event-finish",
            allowed_paths=("src/other.py",),
        )


@pytest.mark.parametrize(
    "patch",
    [
        "",
        "not a patch",
        "--- a/../escape.py\n+++ b/../escape.py\n",
        "GIT binary patch\nliteral 0\n",
    ],
)
def test_patch_rejects_empty_malformed_or_unsafe_input(patch: str) -> None:
    with pytest.raises(PatchApplicationError):
        apply_unified_diff(
            {"src/a.py": "x = 1\n"},
            patch,
            producer="coder",
            source_workspace_version="workspace-source",
            start_event="event-start",
            finish_event="event-finish",
        )


def test_patch_rejects_configured_size_limit() -> None:
    with pytest.raises(PatchApplicationError, match="size limit"):
        apply_unified_diff(
            {"src/a.py": "x = 1\n"},
            PATCH,
            producer="coder",
            source_workspace_version="workspace-source",
            start_event="event-start",
            finish_event="event-finish",
            max_patch_bytes=10,
        )
