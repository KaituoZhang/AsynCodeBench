"""Apply text-only unified diffs with workspace and provenance safeguards."""

from __future__ import annotations

import hashlib
import re
import subprocess
import tempfile
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

from asynccodebench.contracts import ArtifactProvenance, ArtifactValidity
from asynccodebench.runtime.workspace import normalize_workspace_path

PATCH_HEADER = re.compile(r"^(?:---|\+\+\+) (.+?)(?:\t.*)?$")


class PatchApplicationError(RuntimeError):
    """Raised when a patch is unsafe or cannot be applied."""


@dataclass(frozen=True)
class PatchApplicationResult:
    updates: Mapping[str, str | None]
    artifact: ArtifactProvenance


def _patch_paths(patch: str) -> tuple[str, ...]:
    paths: set[str] = set()
    for line in patch.splitlines():
        match = PATCH_HEADER.match(line)
        if match is None:
            continue
        raw = match.group(1)
        if raw == "/dev/null":
            continue
        if raw.startswith(("a/", "b/")):
            raw = raw[2:]
        try:
            paths.add(normalize_workspace_path(raw))
        except ValueError as exc:
            raise PatchApplicationError(str(exc)) from exc
    if not paths:
        raise PatchApplicationError("Patch contains no text file headers")
    return tuple(sorted(paths))


def apply_unified_diff(
    files: Mapping[str, str],
    patch: str,
    *,
    producer: str,
    source_workspace_version: str,
    start_event: str,
    finish_event: str,
    allowed_paths: Iterable[str] | None = None,
    input_artifact_ids: tuple[str, ...] = (),
    timeout_seconds: float = 10.0,
    max_patch_bytes: int = 1_000_000,
) -> PatchApplicationResult:
    """Apply a bounded text patch and emit automatically derived provenance."""

    if not patch.strip():
        raise PatchApplicationError("Patch is empty")
    if len(patch.encode("utf-8")) > max_patch_bytes:
        raise PatchApplicationError("Patch exceeds the configured size limit")
    if "GIT binary patch" in patch or "\x00" in patch:
        raise PatchApplicationError("Binary patches are not supported")

    normalized_files = {
        normalize_workspace_path(path): content for path, content in files.items()
    }
    declared_paths = set(_patch_paths(patch))
    if allowed_paths is not None:
        allowed = {normalize_workspace_path(path) for path in allowed_paths}
        forbidden = declared_paths - allowed
        if forbidden:
            raise PatchApplicationError(
                f"Patch modifies paths outside the editable boundary: "
                f"{sorted(forbidden)}"
            )

    with tempfile.TemporaryDirectory(prefix="asynccodebench-patch-") as temp_dir:
        root = Path(temp_dir)
        for relative_path, content in normalized_files.items():
            destination = root / relative_path
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(content, encoding="utf-8")

        patch_path = root / "candidate.patch"
        patch_path.write_text(patch, encoding="utf-8")
        try:
            result = subprocess.run(
                [
                    "git",
                    "apply",
                    "--whitespace=nowarn",
                    "--recount",
                    "--",
                    patch_path.name,
                ],
                cwd=root,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise PatchApplicationError("Patch application timed out") from exc
        if result.returncode != 0:
            details = (result.stderr or result.stdout).strip()
            raise PatchApplicationError(
                f"git apply failed: {details or 'unknown error'}"
            )

        updated_files: dict[str, str] = {}
        for path in root.rglob("*"):
            if path == patch_path or not path.is_file() or path.is_symlink():
                continue
            relative_path = normalize_workspace_path(path.relative_to(root).as_posix())
            updated_files[relative_path] = path.read_text(encoding="utf-8")

    updates: dict[str, str | None] = {}
    for relative_path in sorted(set(normalized_files) | set(updated_files)):
        before = normalized_files.get(relative_path)
        after = updated_files.get(relative_path)
        if before != after:
            updates[relative_path] = after
    changed_paths = tuple(sorted(updates))
    if not changed_paths:
        raise PatchApplicationError("Patch produced no workspace changes")
    undeclared = set(changed_paths) - declared_paths
    if undeclared:
        raise PatchApplicationError(
            f"Patch changed undeclared paths: {sorted(undeclared)}"
        )

    artifact_id = "artifact-" + hashlib.sha256(
        (
            source_workspace_version
            + "\0"
            + producer
            + "\0"
            + patch
            + "\0"
            + "\0".join(changed_paths)
        ).encode("utf-8")
    ).hexdigest()
    artifact = ArtifactProvenance(
        artifact_id=artifact_id,
        artifact_type="unified-diff",
        producer=producer,
        source_workspace_version=source_workspace_version,
        input_artifact_ids=tuple(sorted(set(input_artifact_ids))),
        read_set=tuple(sorted(declared_paths & set(normalized_files))),
        write_set=changed_paths,
        tool_or_command=("git", "apply", "--whitespace=nowarn", "--recount"),
        start_event=start_event,
        finish_event=finish_event,
        validity_status=ArtifactValidity.VALID,
    )
    return PatchApplicationResult(updates=updates, artifact=artifact)
