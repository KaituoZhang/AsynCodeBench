"""Protocol-local immutable artifact integration and lossless workspace archives."""

from __future__ import annotations

import hashlib
import json
import shlex
import uuid
from datetime import datetime
from pathlib import Path

# Run inside the isolated workspace: no network or Git mutations. Archive bytes
# are downloaded through the workspace file API instead of being expanded into
# base64 command output.
ARCHIVE_PROGRAM = r"""
import hashlib, io, json, os, subprocess, sys, tarfile
root, base, output = sys.argv[1:]
def git(*args):
    return subprocess.check_output(['git', '-C', root, *args])
os.mkdir(output)
parts = {
    'patch': git('diff', '--binary', base),
    'committed.patch': git('diff', '--binary', base + '..HEAD'),
    'staged.patch': git('diff', '--binary', '--cached', 'HEAD'),
    'unstaged.patch': git('diff', '--binary'),
    'status': git('status', '--porcelain=v1', '-z', '--untracked-files=all'),
}
names = git('ls-files', '--others', '--exclude-standard', '-z').split(b'\0')
archive = io.BytesIO()
with tarfile.open(fileobj=archive, mode='w:gz', dereference=False) as stream:
    for raw in names:
        if raw:
            name = raw.decode('utf-8', 'surrogateescape')
            stream.add(root + '/' + name, arcname=name, recursive=False)
parts['untracked.tar.gz'] = archive.getvalue()
metadata = {}
for name, data in parts.items():
    path = os.path.join(output, name)
    with open(path, 'xb') as stream:
        stream.write(data)
    metadata[name] = {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
print(json.dumps(metadata))
"""


def archive_worktree(manager, worktree: str, base: str, stem: Path) -> dict:
    """Write and verify every layer before the caller may reset/clean anything."""
    remote_dir = f"/tmp/async-manager-archive-{uuid.uuid4().hex}"
    try:
        payload = manager._command(
            "python -c "
            + shlex.quote(ARCHIVE_PROGRAM)
            + " "
            + shlex.quote(worktree)
            + " "
            + shlex.quote(base)
            + " "
            + shlex.quote(remote_dir),
            timeout=120,
        )
        remote_parts = json.loads(payload)
        required = {
            "patch",
            "committed.patch",
            "staged.patch",
            "unstaged.patch",
            "status",
            "untracked.tar.gz",
        }
        if set(remote_parts) != required:
            raise RuntimeError("Incomplete private-worktree archive")
        stem.parent.mkdir(parents=True, exist_ok=True)
        artifacts = {}
        for suffix, remote_metadata in remote_parts.items():
            path = Path(str(stem) + "." + suffix)
            download = manager.workspace.file_download(f"{remote_dir}/{suffix}", path)
            if not download.success:
                raise RuntimeError(
                    f"Private-worktree archive download failed: {download.error}"
                )
            data = path.read_bytes()
            digest = hashlib.sha256(data).hexdigest()
            expected_digest = remote_metadata.get("sha256")
            expected_bytes = remote_metadata.get("bytes")
            if digest != expected_digest or len(data) != expected_bytes:
                raise RuntimeError(
                    "Private-worktree archive transfer verification failed"
                )
            artifacts[suffix] = {
                "path": path.relative_to(manager.config.output_dir).as_posix(),
                "sha256": digest,
                "bytes": len(data),
            }
    finally:
        # This UUID-scoped directory contains only copies. Cleanup failure must
        # never make a verified local archive unusable or mask the root error.
        manager.workspace.execute_command(
            f"rm -rf -- {shlex.quote(remote_dir)}", timeout=60
        )
    manifest = {"base": base, "worktree": worktree, "artifacts": artifacts}
    Path(str(stem) + ".archive.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


RECOVER_PROGRAM = r"""
import json, os, subprocess, sys, tempfile
root, base, paths_json = sys.argv[1:]
fd, index = tempfile.mkstemp(prefix='async-manager-index-')
os.close(fd)
os.unlink(index)
env = dict(os.environ, GIT_INDEX_FILE=index)
def git(*args):
    return subprocess.check_output(['git', '-C', root, *args], env=env).decode().strip()
try:
    git('read-tree', base)
    git('add', '-A', '--', *json.loads(paths_json))
    tree = git('write-tree')
    if tree == git('rev-parse', base + '^{tree}'):
        print(base)
    else:
        print(git('-c', 'user.name=AsynCodeBench',
                  '-c', 'user.email=benchmark@localhost',
                  'commit-tree', tree, '-p', base,
                  '-m', 'Recover scoped specialist artifact'))
finally:
    if os.path.exists(index): os.unlink(index)
"""


class ArtifactSafetyMixin:
    _MERGE_USER_NAME = "AsynCodeBench"
    _MERGE_USER_EMAIL = "benchmark@localhost"

    def _run_artifact_merge(self, ref: str, *extra_args: str):
        """Merge an immutable artifact without relying on ambient Git identity."""
        root = shlex.quote(self.repo_dir)
        command = [
            "git",
            "-c",
            f"user.name={self._MERGE_USER_NAME}",
            "-c",
            f"user.email={self._MERGE_USER_EMAIL}",
            "merge",
            ref,
            "--no-edit",
            *extra_args,
        ]
        rendered = " ".join(shlex.quote(part) for part in command)
        return self.workspace.execute_command(f"cd {root} && {rendered}", timeout=60)

    def merge_branch(self, branch_name, force_theirs=False):
        """Protocol-local merge with deterministic committer identity.

        The shared manager implementation intentionally remains untouched so
        frozen protocols retain their released behavior.  Command-scoped Git
        configuration also avoids depending on model-created repository config
        or mutating host/container global configuration.
        """
        self.log(f"Merging branch {branch_name}...")

        stashed = False
        if self.task.should_stash_before_merge:
            stashed = self.stash_if_dirty()

        result = self._run_artifact_merge(branch_name)
        if result.exit_code == 0:
            self.log(f"Successfully merged {branch_name}")
            if stashed:
                self.unstash()
            return True, "Merged successfully", []

        error_msg = result.stderr or result.stdout or "Unknown error"
        is_conflict = "CONFLICT" in error_msg or "conflict" in error_msg.lower()
        if is_conflict:
            root = shlex.quote(self.repo_dir)
            conflict_result = self.workspace.execute_command(
                f"cd {root} && git diff --name-only --diff-filter=U", timeout=30
            )
            conflict_files = (
                [
                    path.strip()
                    for path in conflict_result.stdout.strip().split("\n")
                    if path.strip()
                ]
                if conflict_result.exit_code == 0
                else []
            )
            self.log(
                f"Merge conflict detected for {branch_name}, files: {conflict_files}"
            )
            self.workspace.execute_command(
                f"cd {root} && git merge --abort", timeout=30
            )

            if force_theirs:
                self.log(
                    "Force-resolving with --strategy-option theirs "
                    "(engineer has no rounds left)..."
                )
                result = self._run_artifact_merge(branch_name, "-X", "theirs")
                if result.exit_code == 0:
                    self.log(f"Successfully merged {branch_name} using theirs strategy")
                    if stashed:
                        self.unstash()
                    return (
                        True,
                        "Merged successfully (used theirs strategy for conflicts)",
                        [],
                    )
                error_msg = result.stderr or result.stdout or "Unknown error"
                self.log(f"Merge with theirs strategy also failed: {error_msg[:200]}")
                self.workspace.execute_command(
                    f"cd {root} && git merge --abort", timeout=30
                )
                if stashed:
                    self.unstash()
                return (
                    False,
                    f"Merge failed even with conflict resolution: {error_msg[:200]}",
                    [],
                )

            if stashed:
                self.unstash()
            return (
                False,
                f"Merge conflict in files: {', '.join(conflict_files)}",
                conflict_files,
            )

        self.log(f"Warning: Merge failed for {branch_name}: {error_msg[:200]}")
        if stashed:
            self.unstash()
        return False, f"Merge failed: {error_msg[:200]}", []

    def _artifact_paths(self, commit):
        root = shlex.quote(self.repo_dir)
        base = self._command(
            f"git -C {root} merge-base HEAD {shlex.quote(commit)}"
        ).strip()
        paths = self._command(
            f"git -C {root} diff --no-renames --name-only -z "
            f"{shlex.quote(base)} {shlex.quote(commit)}"
        )
        return sorted(p for p in paths.split("\0") if p)

    def _resolve_artifact(self, result, assignment):
        """Pin once. Never merge a moving branch or incidental dirty files."""
        root = shlex.quote(self.repo_dir)
        ref = result.commit_hash or result.branch_name
        if not ref:
            return None
        commit = self._command(
            f"git -C {root} rev-parse --verify --end-of-options "
            f"{shlex.quote(ref + '^{commit}')}"
        ).strip()
        if (
            result.commit_hash
            or self._artifact_paths(commit)
            or not result.worktree_path
        ):
            return commit
        # Preserve the released partial-artifact recovery, but stage only allowed
        # paths in a separate index. The specialist's real index is never touched.
        status = self._command(
            f"git -C {shlex.quote(result.worktree_path)} status --porcelain=v1 "
            "-z --untracked-files=all"
        )
        dirty = self._porcelain_paths(status)
        scopes = (assignment or {}).get("writable_paths", [])
        from protocols.async_manager.manager import safe_production_path

        paths = [p for p in dirty if safe_production_path(p, scopes)]
        if not paths:
            return None
        return self._command(
            "python -c "
            + shlex.quote(RECOVER_PROGRAM)
            + " "
            + shlex.quote(result.worktree_path)
            + " "
            + shlex.quote(commit)
            + " "
            + shlex.quote(json.dumps(paths))
        ).strip()

    @staticmethod
    def _porcelain_paths(status):
        entries = iter(status.split("\0"))
        paths = set()
        for entry in entries:
            if len(entry) < 4:
                continue
            paths.add(entry[3:])
            if "R" in entry[:2] or "C" in entry[:2]:
                source = next(entries, "")
                if source:
                    paths.add(source)
        return sorted(paths)

    def collect_and_merge(self, result, output_logger=None):
        started = datetime.now()
        assignment = self.assignment_for_result(result)
        scopes = assignment.get("writable_paths", []) if assignment else []
        before = self.current_head()
        commit = self._resolve_artifact(result, assignment)
        paths = self._artifact_paths(commit) if commit else []
        dirty = self.main_workspace_status()
        from protocols.async_manager.manager import safe_production_path

        violations = [p for p in paths if not safe_production_path(p, scopes)]
        if commit:
            tree = self._command(
                f"git -C {shlex.quote(self.repo_dir)} ls-tree -r -z "
                f"{shlex.quote(commit)}"
            )
            for entry in tree.split("\0"):
                if "\t" in entry:
                    mode, path = entry.split("\t", 1)
                    if path in paths and mode.split()[0] in {"120000", "160000"}:
                        violations.append(path)
            violations = sorted(set(violations))
        reasons = []
        if assignment is None:
            reasons.append("result does not map to an active manifest assignment")
        if dirty:
            reasons.append(f"main workspace dirty before merge: {dirty}")
        if violations:
            reasons.append(f"out-of-scope committed changes: {violations}")
        archived = None
        if result.worktree_path:
            status = self._command(
                f"git -C {shlex.quote(result.worktree_path)} "
                "status --porcelain=v1 -z --untracked-files=all"
            )
            if status:
                stem = (
                    Path(self.config.output_dir)
                    / "specialist_archives"
                    / f"{len(getattr(self, 'artifact_records', [])) + 1:04d}"
                )
                archived = archive_worktree(self, result.worktree_path, before, stem)
        record = {
            "schema_version": "0.1",
            "artifact_schema_version": "async-manager-artifact-v2",
            "protocol": "async_manager",
            "scenario_id": self.active_scenario().get("scenario_id"),
            "manifest_subproblem_id": (assignment or {}).get("subproblem_id"),
            "agent_id": result.engineer_id,
            "task_assignment_id": result.task_id,
            "round_num": result.round_num,
            "artifact_commit": commit,
            "head_before": before,
            "writable_paths": scopes,
            "changed_paths": paths,
            "violations": violations,
            "main_workspace_status_before_merge": dirty,
            "passed": not reasons,
            "reasons": reasons,
            "uncommitted_archive": archived,
            "policy": "immutable_committed_artifact_only",
        }
        self.record_scope_validation(record)
        self.artifact_records = [*getattr(self, "artifact_records", []), record]
        if reasons:
            return self.rejected_review(
                result, "; ".join(reasons), paths, output_logger
            )
        review = {
            "engineer_id": result.engineer_id,
            "task_id": result.task_id,
            "subagent_success": result.success,
            "merged": False,
            "merge_method": "no_artifact",
            "conflict_files": [],
            "merge_message": "No scoped artifact available",
            "review_notes": "",
        }
        if commit:
            if self.current_head() != before or self.main_workspace_status():
                raise RuntimeError(
                    "Integrated workspace moved during artifact validation"
                )
            merged, message, conflicts = self.merge_branch(commit)
            review.update(
                merged=merged,
                merge_message=message,
                review_notes=message,
                conflict_files=conflicts,
                merge_method="conflict"
                if conflicts
                else ("branch_merge" if merged else "merge_failed"),
            )
            result.commit_hash = commit
            self.log(
                f"Immutable specialist artifact {commit[:12]}: {review['merge_method']}"
            )
        if output_logger:
            output_logger.log_manager_review(
                engineer_id=result.engineer_id,
                task_id=result.task_id,
                merged=review["merged"],
                review_reason=review["merge_message"],
                commit_hash=commit,
                files_modified=paths,
                round_num=result.round_num,
                start_time=started,
                end_time=datetime.now(),
            )
        return review
