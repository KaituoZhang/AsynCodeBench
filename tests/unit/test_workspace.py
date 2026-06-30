from __future__ import annotations

import pytest

from asynccodebench.contracts import WorkspaceKind
from asynccodebench.runtime import (
    WorkspaceConflictError,
    WorkspaceStore,
    content_digest,
    normalize_workspace_path,
)


def make_store() -> WorkspaceStore:
    return WorkspaceStore(
        {"src/a.py": "x = 1\n"},
        created_by_event_id="event-initial",
    )


def test_content_digest_is_order_independent() -> None:
    assert content_digest({"a": "1", "b": "2"}) == content_digest(
        {"b": "2", "a": "1"}
    )


@pytest.mark.parametrize(
    "path",
    [
        "",
        "/absolute.py",
        "../escape.py",
        "src/../escape.py",
        "src/./a.py",
        "src//a.py",
        ".git/config",
        "src\\a.py",
        "bad\x00name.py",
    ],
)
def test_workspace_path_rejects_unsafe_paths(path: str) -> None:
    with pytest.raises(ValueError):
        normalize_workspace_path(path)


def test_private_workspaces_are_isolated_and_content_addressed() -> None:
    store = make_store()
    initial = store.integrated_head
    assert store.create_private("coder") == initial
    assert store.create_private("reviewer") == initial

    coder = store.commit_private(
        "coder",
        {"src/a.py": "x = 2\n", "src/b.py": "y = 1\n"},
        author="coder",
        logical_time=1.0,
        created_by_event_id="event-coder-update",
        source_artifact_ids=("artifact-patch",),
    )

    assert coder.workspace_kind is WorkspaceKind.PRIVATE
    assert coder.version_id.startswith("workspace-")
    assert store.read(coder.version_id, "src/a.py") == "x = 2\n"
    assert store.read(store.private_head("reviewer"), "src/a.py") == "x = 1\n"
    assert store.integrated_head == initial
    assert store.is_ancestor(initial, coder.version_id)
    assert [delta.change_type for delta in store.diff(initial, coder.version_id)] == [
        "modified",
        "added",
    ]


def test_same_commit_inputs_produce_same_version_identifier() -> None:
    first = make_store()
    second = make_store()
    for store in (first, second):
        store.create_private("coder")

    first_version = first.commit_private(
        "coder",
        {"src/a.py": "x = 2\n"},
        author="coder",
        logical_time=1.0,
        created_by_event_id="event-update",
    )
    second_version = second.commit_private(
        "coder",
        {"src/a.py": "x = 2\n"},
        author="coder",
        logical_time=1.0,
        created_by_event_id="event-update",
    )
    assert first_version.version_id == second_version.version_id
    assert first_version.content_digest == second_version.content_digest


def test_integration_is_explicit_and_rejects_stale_compare_and_swap() -> None:
    store = make_store()
    initial = store.integrated_head
    store.create_private("coder")
    store.create_private("reviewer")
    store.commit_private(
        "coder",
        {"src/a.py": "x = 2\n"},
        author="coder",
        logical_time=1.0,
        created_by_event_id="event-coder-update",
    )
    integrated = store.integrate_private(
        "coder",
        expected_integrated_version_id=initial,
        author="integrator",
        logical_time=2.0,
        created_by_event_id="event-integrated",
    )
    assert integrated.workspace_kind is WorkspaceKind.INTEGRATED
    assert store.read(store.integrated_head, "src/a.py") == "x = 2\n"

    store.commit_private(
        "reviewer",
        {"src/a.py": "x = 3\n"},
        author="reviewer",
        logical_time=2.5,
        created_by_event_id="event-reviewer-update",
    )
    with pytest.raises(WorkspaceConflictError, match="advanced"):
        store.integrate_private(
            "reviewer",
            expected_integrated_version_id=initial,
            author="integrator",
            logical_time=3.0,
            created_by_event_id="event-stale-integration",
        )
    with pytest.raises(WorkspaceConflictError, match="not based"):
        store.integrate_private(
            "reviewer",
            expected_integrated_version_id=store.integrated_head,
            author="integrator",
            logical_time=3.0,
            created_by_event_id="event-stale-integration-current-cas",
        )


def test_integration_preserves_patch_artifact_lineage() -> None:
    store = make_store()
    initial = store.integrated_head
    store.create_private("coder")
    store.commit_private(
        "coder",
        {"src/a.py": "x = 2\n"},
        author="coder",
        logical_time=1.0,
        created_by_event_id="event-coder-update",
        source_artifact_ids=("artifact-patch",),
    )
    integrated = store.integrate_private(
        "coder",
        expected_integrated_version_id=initial,
        author="integrator",
        logical_time=2.0,
        created_by_event_id="event-integrated",
        source_artifact_ids=("artifact-review",),
    )
    assert integrated.source_artifact_ids == (
        "artifact-patch",
        "artifact-review",
    )


def test_workspace_fork_is_independent() -> None:
    store = make_store()
    store.create_private("coder")
    branch = store.fork()
    branch.commit_private(
        "coder",
        {"src/a.py": "x = 2\n"},
        author="coder",
        logical_time=1.0,
        created_by_event_id="event-update",
    )
    assert store.read(store.private_head("coder"), "src/a.py") == "x = 1\n"
    assert branch.read(branch.private_head("coder"), "src/a.py") == "x = 2\n"
