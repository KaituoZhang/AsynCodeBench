"""Immutable content-addressed workspaces with explicit branch ownership."""

from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import PurePosixPath

from asyncodebench.contracts import (
    FileDeltaRecord,
    WorkspaceKind,
    WorkspaceStateRecord,
    WorkspaceVersionRecord,
)


class WorkspaceConflictError(RuntimeError):
    """Raised when integration would overwrite a newer integrated version."""


def normalize_workspace_path(path: str) -> str:
    """Return a safe repository-relative POSIX path."""

    if "\x00" in path or "\\" in path:
        raise ValueError(f"Invalid workspace path: {path!r}")
    raw_parts = path.split("/")
    candidate = PurePosixPath(path)
    if not path or candidate.is_absolute():
        raise ValueError(f"Workspace paths must be relative: {path!r}")
    if any(part in {"", ".", ".."} for part in raw_parts):
        raise ValueError(f"Invalid workspace path: {path!r}")
    normalized = candidate.as_posix()
    if normalized == ".git" or normalized.startswith(".git/"):
        raise ValueError("Workspace content cannot modify Git metadata")
    return normalized


def content_digest(files: Mapping[str, str]) -> str:
    """Fingerprint a complete workspace independently of insertion order."""

    canonical = json.dumps(
        sorted(files.items()),
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def text_digest(content: str | None) -> str | None:
    if content is None:
        return None
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _version_id(
    *,
    parent_version_id: str | None,
    digest: str,
    workspace_kind: WorkspaceKind,
    owner: str,
    author: str,
    logical_time: float,
    changed_paths: tuple[str, ...],
    source_artifact_ids: tuple[str, ...],
    created_by_event_id: str,
    message: str,
) -> str:
    payload = {
        "parent_version_id": parent_version_id,
        "content_digest": digest,
        "workspace_kind": workspace_kind.value,
        "owner": owner,
        "author": author,
        "logical_time": logical_time,
        "changed_paths": changed_paths,
        "source_artifact_ids": source_artifact_ids,
        "created_by_event_id": created_by_event_id,
        "message": message,
    }
    encoded = json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return f"workspace-{hashlib.sha256(encoded.encode('utf-8')).hexdigest()}"


@dataclass(frozen=True)
class StoredWorkspaceVersion:
    record: WorkspaceVersionRecord
    files: Mapping[str, str]


class WorkspaceStore:
    """Store immutable snapshots and explicit integrated/private branch heads."""

    def __init__(
        self,
        initial_files: Mapping[str, str],
        *,
        created_by_event_id: str,
        logical_time: float = 0.0,
    ) -> None:
        files = self._normalize_files(initial_files)
        initial = self._build_version(
            files=files,
            parent_version_id=None,
            workspace_kind=WorkspaceKind.INTEGRATED,
            owner="integrated",
            author="system",
            logical_time=logical_time,
            changed_paths=tuple(sorted(files)),
            source_artifact_ids=(),
            created_by_event_id=created_by_event_id,
            message="initial",
        )
        self._versions = {initial.record.version_id: initial}
        self._integrated_head = initial.record.version_id
        self._private_heads: dict[str, str] = {}

    @staticmethod
    def _normalize_files(files: Mapping[str, str]) -> dict[str, str]:
        normalized: dict[str, str] = {}
        for raw_path, content in files.items():
            path = normalize_workspace_path(raw_path)
            if not isinstance(content, str):
                raise TypeError(f"Workspace file must be text: {path}")
            normalized[path] = content
        return normalized

    @staticmethod
    def _build_version(
        *,
        files: Mapping[str, str],
        parent_version_id: str | None,
        workspace_kind: WorkspaceKind,
        owner: str,
        author: str,
        logical_time: float,
        changed_paths: tuple[str, ...],
        source_artifact_ids: tuple[str, ...],
        created_by_event_id: str,
        message: str,
    ) -> StoredWorkspaceVersion:
        digest = content_digest(files)
        identifier = _version_id(
            parent_version_id=parent_version_id,
            digest=digest,
            workspace_kind=workspace_kind,
            owner=owner,
            author=author,
            logical_time=logical_time,
            changed_paths=changed_paths,
            source_artifact_ids=source_artifact_ids,
            created_by_event_id=created_by_event_id,
            message=message,
        )
        return StoredWorkspaceVersion(
            record=WorkspaceVersionRecord(
                version_id=identifier,
                content_digest=digest,
                parent_version_id=parent_version_id,
                workspace_kind=workspace_kind,
                owner=owner,
                author=author,
                logical_time=logical_time,
                changed_paths=changed_paths,
                source_artifact_ids=source_artifact_ids,
                created_by_event_id=created_by_event_id,
                message=message,
            ),
            files=copy.deepcopy(dict(files)),
        )

    @property
    def integrated_head(self) -> str:
        return self._integrated_head

    def state(self) -> WorkspaceStateRecord:
        return WorkspaceStateRecord(
            integrated_version_id=self._integrated_head,
            private_version_ids=dict(sorted(self._private_heads.items())),
        )

    def get(self, version_id: str) -> StoredWorkspaceVersion:
        try:
            return self._versions[version_id]
        except KeyError as exc:
            raise KeyError(f"Unknown workspace version: {version_id}") from exc

    def files(self, version_id: str) -> dict[str, str]:
        return dict(self.get(version_id).files)

    def read(self, version_id: str, path: str) -> str:
        normalized = normalize_workspace_path(path)
        try:
            return self.get(version_id).files[normalized]
        except KeyError as exc:
            raise FileNotFoundError(normalized) from exc

    def create_private(self, agent_id: str) -> str:
        if not agent_id:
            raise ValueError("agent_id must not be empty")
        self._private_heads.setdefault(agent_id, self._integrated_head)
        return self._private_heads[agent_id]

    def private_head(self, agent_id: str) -> str:
        try:
            return self._private_heads[agent_id]
        except KeyError as exc:
            raise KeyError(f"Agent has no private workspace: {agent_id}") from exc

    def commit_private(
        self,
        agent_id: str,
        updates: Mapping[str, str | None],
        *,
        author: str,
        logical_time: float,
        created_by_event_id: str,
        source_artifact_ids: tuple[str, ...] = (),
        message: str = "",
    ) -> WorkspaceVersionRecord:
        parent_id = self.private_head(agent_id)
        version = self._commit(
            base_version_id=parent_id,
            updates=updates,
            workspace_kind=WorkspaceKind.PRIVATE,
            owner=agent_id,
            author=author,
            logical_time=logical_time,
            created_by_event_id=created_by_event_id,
            source_artifact_ids=source_artifact_ids,
            message=message,
        )
        self._private_heads[agent_id] = version.version_id
        return version

    def _commit(
        self,
        *,
        base_version_id: str,
        updates: Mapping[str, str | None],
        workspace_kind: WorkspaceKind,
        owner: str,
        author: str,
        logical_time: float,
        created_by_event_id: str,
        source_artifact_ids: tuple[str, ...],
        message: str,
    ) -> WorkspaceVersionRecord:
        files = self.files(base_version_id)
        changed_paths: list[str] = []
        for raw_path, content in updates.items():
            path = normalize_workspace_path(raw_path)
            before = files.get(path)
            if content is None:
                if path in files:
                    del files[path]
                    changed_paths.append(path)
            elif not isinstance(content, str):
                raise TypeError(f"Workspace file must be text: {path}")
            elif before != content:
                files[path] = content
                changed_paths.append(path)
        stored = self._build_version(
            files=files,
            parent_version_id=base_version_id,
            workspace_kind=workspace_kind,
            owner=owner,
            author=author,
            logical_time=logical_time,
            changed_paths=tuple(sorted(changed_paths)),
            source_artifact_ids=tuple(sorted(set(source_artifact_ids))),
            created_by_event_id=created_by_event_id,
            message=message,
        )
        existing = self._versions.get(stored.record.version_id)
        if existing is not None and existing != stored:
            raise RuntimeError("Workspace version hash collision")
        self._versions[stored.record.version_id] = stored
        return stored.record

    def integrate_private(
        self,
        agent_id: str,
        *,
        expected_integrated_version_id: str,
        author: str,
        logical_time: float,
        created_by_event_id: str,
        source_artifact_ids: tuple[str, ...] = (),
        message: str = "",
    ) -> WorkspaceVersionRecord:
        if expected_integrated_version_id != self._integrated_head:
            raise WorkspaceConflictError("Integrated workspace advanced")
        private_id = self.private_head(agent_id)
        private = self.get(private_id)
        if not self.is_ancestor(self._integrated_head, private_id):
            raise WorkspaceConflictError(
                "Private workspace is not based on the integrated head"
            )
        integrated = self._commit(
            base_version_id=self._integrated_head,
            updates={
                delta.path: private.files.get(delta.path)
                for delta in self.diff(self._integrated_head, private_id)
            },
            workspace_kind=WorkspaceKind.INTEGRATED,
            owner="integrated",
            author=author,
            logical_time=logical_time,
            created_by_event_id=created_by_event_id,
            source_artifact_ids=(
                *private.record.source_artifact_ids,
                *source_artifact_ids,
            ),
            message=message,
        )
        self._integrated_head = integrated.version_id
        self._private_heads[agent_id] = integrated.version_id
        return integrated

    def synchronize_private(self, agent_id: str) -> str:
        self._private_heads[agent_id] = self._integrated_head
        return self._integrated_head

    def diff(
        self,
        from_version_id: str,
        to_version_id: str,
    ) -> tuple[FileDeltaRecord, ...]:
        before = self.get(from_version_id).files
        after = self.get(to_version_id).files
        changes: list[FileDeltaRecord] = []
        for path in sorted(set(before) | set(after)):
            if before.get(path) == after.get(path):
                continue
            if path not in before:
                change_type = "added"
            elif path not in after:
                change_type = "deleted"
            else:
                change_type = "modified"
            changes.append(
                FileDeltaRecord(
                    path=path,
                    change_type=change_type,
                    before_digest=text_digest(before.get(path)),
                    after_digest=text_digest(after.get(path)),
                )
            )
        return tuple(changes)

    def is_ancestor(self, ancestor_id: str, descendant_id: str) -> bool:
        self.get(ancestor_id)
        current = self.get(descendant_id)
        while True:
            if current.record.version_id == ancestor_id:
                return True
            parent = current.record.parent_version_id
            if parent is None:
                return False
            current = self.get(parent)

    def fork(self) -> WorkspaceStore:
        return copy.deepcopy(self)
