"""Dry-run agent harness for the Commit0 cachetools pilot example.

This module is intentionally outside the release/evaluation path. It is for
testing whether a small Commit0 task exposes useful asynchronous multi-agent
coordination signals before the formal pilot manifest is frozen.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import shutil
import subprocess
import tarfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

Mode = Literal["single", "two_agent", "three_agent"]


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_REPO = PROJECT_ROOT / "data/repos/commit0/cachetools"
DEFAULT_BASE_URL = "http://localhost:8000/v1"


@dataclass(frozen=True)
class AgentSpec:
    name: str
    role: str
    focus: str
    files: tuple[str, ...]
    write_paths: tuple[str, ...]
    test_targets: tuple[str, ...]


KEY_AGENT = AgentSpec(
    name="key_agent",
    role="Implement the cache key construction layer.",
    focus=(
        "Implement src/cachetools/keys.py while preserving _HashedTuple "
        "semantics and typed/untyped key behavior."
    ),
    files=("src/cachetools/keys.py", "tests/test_keys.py"),
    write_paths=("src/cachetools/keys.py",),
    test_targets=("tests/test_keys.py",),
)

FUNC_AGENT = AgentSpec(
    name="func_agent",
    role="Implement the memoizing decorator layer.",
    focus=(
        "Implement src/cachetools/func.py by composing existing cache classes, "
        "cached(), key functions, RLock, and cache metadata methods."
    ),
    files=(
        "src/cachetools/func.py",
        "src/cachetools/keys.py",
        "tests/test_func.py",
    ),
    write_paths=("src/cachetools/func.py",),
    test_targets=("tests/test_func.py",),
)

INTEGRATOR_AGENT = AgentSpec(
    name="integrator_agent",
    role="Implement and integrate the full cachetools task.",
    focus=(
        "Implement both keys.py and func.py consistently. Preserve the public "
        "cachetools API and make the targeted tests pass."
    ),
    files=(
        "src/cachetools/keys.py",
        "src/cachetools/func.py",
        "tests/test_keys.py",
        "tests/test_func.py",
    ),
    write_paths=("src/cachetools/keys.py", "src/cachetools/func.py"),
    test_targets=("tests/test_keys.py", "tests/test_func.py"),
)

REVIEWER_AGENT = AgentSpec(
    name="reviewer_agent",
    role="Review two independently generated patches and produce one final patch.",
    focus=(
        "Resolve stale assumptions between key construction and decorator "
        "behavior, then produce one coherent integrated patch."
    ),
    files=(
        "src/cachetools/keys.py",
        "src/cachetools/func.py",
        "tests/test_keys.py",
        "tests/test_func.py",
    ),
    write_paths=("src/cachetools/keys.py", "src/cachetools/func.py"),
    test_targets=("tests/test_keys.py", "tests/test_func.py"),
)

CORE_EXCERPTS = {
    "src/cachetools/__init__.py": ((1, 220), (560, 840)),
}


def validate_repository(repository: Path) -> Path:
    repository = repository.expanduser().resolve()
    if not (repository / ".git").is_dir():
        raise ValueError(
            f"Commit0 cachetools repository is missing at {repository}. "
            "Run scripts/materialize_commit0_repositories.py cachetools first "
            "or pass --repo."
        )
    result = subprocess.run(
        ["git", "rev-parse", "--verify", "commit0^{commit}"],
        cwd=repository,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise ValueError(
            f"repository does not contain a valid commit0 ref: {repository}"
        )
    return repository


def git_show(repository: Path, path: str) -> str:
    result = subprocess.run(
        ["git", "show", f"commit0:{path}"],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def excerpt(
    repository: Path,
    path: str,
    ranges: tuple[tuple[int, int], ...],
) -> str:
    lines = git_show(repository, path).splitlines()
    chunks = []
    for start, end in ranges:
        selected = lines[start - 1 : end]
        numbered = "\n".join(
            f"{line_number:04d}: {line}"
            for line_number, line in enumerate(selected, start=start)
        )
        chunks.append(f"# {path} lines {start}-{end}\n{numbered}")
    return "\n\n".join(chunks)


def build_file_context(repository: Path, files: tuple[str, ...]) -> str:
    blocks = []
    for path, ranges in CORE_EXCERPTS.items():
        blocks.append(excerpt(repository, path, ranges))
    for path in files:
        blocks.append(f"# {path}\n{git_show(repository, path)}")
    return "\n\n".join(blocks)


def build_prompt(
    *,
    repository: Path,
    agent: AgentSpec,
    mode: Mode,
    peer_context: str = "",
) -> list[dict[str, str]]:
    system = (
        "You are a software-engineering agent in an AsynCodeBench dry run. "
        "Use only the provided Commit0 public evidence. Do not assume or use "
        "reference patches, hidden solutions, or future repository state. "
        "Return only the tagged response format requested by the user."
    )
    user = f"""
Task: Commit0 cachetools pilot dry run.
Mode: {mode}
Agent name: {agent.name}
Role: {agent.role}
Focus: {agent.focus}

Allowed tools in this dry run:
- read_file: already executed by the harness; the visible file contents are below.
- write_file: return complete replacement contents for allowed implementation files.
- run_tests: suggest pytest targets in tests_to_run; the harness will execute them.
- send_message: write a concise coordination note in message_to_teammates.

Output format:
<MESSAGE>
short coordination note
</MESSAGE>

<FILE path="src/cachetools/keys.py">
complete replacement file content, if you are allowed to edit this file
</FILE>

<FILE path="src/cachetools/func.py">
complete replacement file content, if you are allowed to edit this file
</FILE>

<TESTS>
one pytest target per line
</TESTS>

<RATIONALE>
brief explanation of design choices and coordination risks
</RATIONALE>

File-edit constraints:
- You may edit only these files:
{json.dumps(agent.write_paths, indent=2)}
- Do not edit tests.
- Return complete file contents, not a diff.
- Do not use placeholders such as "...", "# unchanged", or omitted sections.
- Do not wrap file contents in markdown fences.

Recommended tests for this role:
{json.dumps(agent.test_targets, indent=2)}

Peer context, if any:
{peer_context or "(none)"}

Visible Commit0 public files:
{build_file_context(repository, agent.files)}
"""
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def post_chat_completion(
    *,
    base_url: str,
    model: str,
    messages: list[dict[str, str]],
    temperature: float,
    top_p: float,
    top_k: int,
    min_p: float,
    presence_penalty: float,
    max_tokens: int,
    timeout: int,
) -> str:
    url = base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "top_p": top_p,
        "top_k": top_k,
        "min_p": min_p,
        "presence_penalty": presence_penalty,
        "max_tokens": max_tokens,
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise RuntimeError(f"OpenAI-compatible request failed: {exc}") from exc
    return body["choices"][0]["message"]["content"]


def _extract_tag(text: str, tag: str) -> str:
    match = re.search(rf"<{tag}>\s*(.*?)\s*</{tag}>", text, flags=re.DOTALL)
    return match.group(1).strip() if match else ""


def _strip_code_fence(content: str) -> str:
    stripped = content.strip()
    if stripped.startswith("```") and stripped.endswith("```"):
        lines = stripped.splitlines()
        return "\n".join(lines[1:-1]).rstrip() + "\n"
    return content.rstrip() + "\n"


def parse_tagged_response(
    text: str,
    *,
    allowed_write_paths: tuple[str, ...],
    default_tests: tuple[str, ...],
) -> dict[str, Any]:
    files: dict[str, str] = {}
    for match in re.finditer(
        r'<FILE\s+path="([^"]+)">\s*(.*?)\s*</FILE>',
        text,
        flags=re.DOTALL,
    ):
        path = match.group(1).strip()
        if path not in allowed_write_paths:
            raise ValueError(f"agent attempted to edit disallowed path: {path}")
        files[path] = _strip_code_fence(match.group(2))
    if not files:
        raise ValueError("model response did not include any <FILE> blocks")

    tests = tuple(
        line.strip().lstrip("- ").strip()
        for line in _extract_tag(text, "TESTS").splitlines()
        if line.strip()
    )
    if not tests:
        tests = default_tests
    return {
        "message_to_teammates": _extract_tag(text, "MESSAGE"),
        "files": files,
        "tests_to_run": tests,
        "rationale": _extract_tag(text, "RATIONALE"),
    }


def export_commit0_workspace(repository: Path, path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)
    archive = subprocess.run(
        ["git", "archive", "--format=tar", "commit0"],
        cwd=repository,
        check=True,
        capture_output=True,
    )
    with tarfile.open(fileobj=io.BytesIO(archive.stdout), mode="r:") as tar:
        tar.extractall(path)
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "pilot@example.invalid"],
        cwd=path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "AsynCodeBench Pilot"],
        cwd=path,
        check=True,
        capture_output=True,
    )
    subprocess.run(["git", "add", "."], cwd=path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "commit0 workspace"],
        cwd=path,
        check=True,
        capture_output=True,
    )


def apply_patch(workspace: Path, patch: str) -> dict[str, Any]:
    if not patch.strip():
        return {"ok": True, "stdout": "", "stderr": "", "empty_patch": True}
    result = subprocess.run(
        ["git", "apply", "--whitespace=nowarn", "-"],
        cwd=workspace,
        input=patch,
        capture_output=True,
        text=True,
        check=False,
    )
    return {
        "ok": result.returncode == 0,
        "return_code": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "empty_patch": False,
    }


def write_agent_files(workspace: Path, response: dict[str, Any]) -> dict[str, Any]:
    written: list[str] = []
    for relative_path, content in response["files"].items():
        target = workspace / relative_path
        if not target.resolve().is_relative_to(workspace.resolve()):
            raise ValueError(f"path escapes workspace: {relative_path}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        written.append(relative_path)
    return {"ok": True, "written_files": tuple(sorted(written))}


def git_diff(workspace: Path) -> str:
    result = subprocess.run(
        ["git", "diff", "--", "src/cachetools/keys.py", "src/cachetools/func.py"],
        cwd=workspace,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def materialize_agent_patch(
    *,
    repository: Path,
    response: dict[str, Any],
    workspace: Path,
    patch_path: Path,
) -> dict[str, Any]:
    export_commit0_workspace(repository, workspace)
    write_result = write_agent_files(workspace, response)
    patch = git_diff(workspace)
    patch_path.write_text(patch, encoding="utf-8")
    return {
        "ok": bool(patch.strip()),
        "empty_patch": not bool(patch.strip()),
        "written_files": write_result["written_files"],
        "patch_path": str(patch_path),
    }


def run_tests(workspace: Path, targets: tuple[str, ...]) -> dict[str, Any]:
    command = ["python", "-m", "pytest", "-q", *targets]
    env = os.environ.copy()
    env["PYTHONPATH"] = "src"
    env["PYTHONNOUSERSITE"] = "1"
    start = time.perf_counter()
    result = subprocess.run(
        command,
        cwd=workspace,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    return {
        "command": command,
        "return_code": result.returncode,
        "duration_seconds": time.perf_counter() - start,
        "stdout": result.stdout[-8000:],
        "stderr": result.stderr[-8000:],
    }


def call_agent(
    *,
    repository: Path,
    agent: AgentSpec,
    mode: Mode,
    base_url: str,
    model: str,
    output_dir: Path,
    peer_context: str = "",
    temperature: float,
    top_p: float,
    top_k: int,
    min_p: float,
    presence_penalty: float,
    max_tokens: int,
    timeout: int,
) -> dict[str, Any]:
    messages = build_prompt(
        repository=repository,
        agent=agent,
        mode=mode,
        peer_context=peer_context,
    )
    raw = post_chat_completion(
        base_url=base_url,
        model=model,
        messages=messages,
        temperature=temperature,
        top_p=top_p,
        top_k=top_k,
        min_p=min_p,
        presence_penalty=presence_penalty,
        max_tokens=max_tokens,
        timeout=timeout,
    )
    parsed = parse_tagged_response(
        raw,
        allowed_write_paths=agent.write_paths,
        default_tests=agent.test_targets,
    )
    agent_dir = output_dir / agent.name
    agent_dir.mkdir(parents=True, exist_ok=True)
    (agent_dir / "prompt.json").write_text(
        json.dumps(messages, indent=2) + "\n",
        encoding="utf-8",
    )
    (agent_dir / "response.raw.txt").write_text(raw, encoding="utf-8")
    (agent_dir / "response.json").write_text(
        json.dumps(parsed, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    files_dir = agent_dir / "files"
    if files_dir.exists():
        shutil.rmtree(files_dir)
    files_dir.mkdir(parents=True)
    for relative_path, content in parsed["files"].items():
        target = files_dir / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    return parsed


def run_mode(args: argparse.Namespace) -> dict[str, Any]:
    repository = validate_repository(args.repo)
    run_dir = args.output_dir / args.run_id
    if run_dir.exists() and not args.resume:
        shutil.rmtree(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)

    metadata = {
        "run_id": args.run_id,
        "mode": args.mode,
        "model": args.model,
        "base_url": args.base_url,
        "task_id": "commit0:cachetools",
        "repository": str(repository),
        "official_result": False,
        "purpose": "non-release agent dry run",
    }

    if args.mode == "single":
        response = call_agent(
            repository=repository,
            agent=INTEGRATOR_AGENT,
            mode=args.mode,
            base_url=args.base_url,
            model=args.model,
            output_dir=run_dir,
            temperature=args.temperature,
            top_p=args.top_p,
            top_k=args.top_k,
            min_p=args.min_p,
            presence_penalty=args.presence_penalty,
            max_tokens=args.max_tokens,
            timeout=args.request_timeout,
        )
        workspace = run_dir / "workspace_integrated"
        export_commit0_workspace(repository, workspace)
        write_agent_files(workspace, response)
        patch = git_diff(workspace)
        (run_dir / "integrator_agent" / "patch.diff").write_text(
            patch,
            encoding="utf-8",
        )
        patch_result = {
            "ok": bool(patch.strip()),
            "empty_patch": not bool(patch.strip()),
            "patch_path": str(run_dir / "integrator_agent" / "patch.diff"),
        }
        tests = (
            run_tests(workspace, tuple(response["tests_to_run"]))
            if patch_result["ok"]
            else None
        )
        metadata["agents"] = {"integrator_agent": response}
        metadata["integration"] = {"patch": patch_result, "tests": tests}

    elif args.mode == "two_agent":
        key_response = call_agent(
            repository=repository,
            agent=KEY_AGENT,
            mode=args.mode,
            base_url=args.base_url,
            model=args.model,
            output_dir=run_dir,
            temperature=args.temperature,
            top_p=args.top_p,
            top_k=args.top_k,
            min_p=args.min_p,
            presence_penalty=args.presence_penalty,
            max_tokens=args.max_tokens,
            timeout=args.request_timeout,
        )
        func_response = call_agent(
            repository=repository,
            agent=FUNC_AGENT,
            mode=args.mode,
            base_url=args.base_url,
            model=args.model,
            output_dir=run_dir,
            temperature=args.temperature,
            top_p=args.top_p,
            top_k=args.top_k,
            min_p=args.min_p,
            presence_penalty=args.presence_penalty,
            max_tokens=args.max_tokens,
            timeout=args.request_timeout,
        )
        workspace = run_dir / "workspace_integrated"
        export_commit0_workspace(repository, workspace)
        key_patch = materialize_agent_patch(
            repository=repository,
            response=key_response,
            workspace=run_dir / "key_agent" / "workspace_patch",
            patch_path=run_dir / "key_agent" / "patch.diff",
        )
        func_patch = materialize_agent_patch(
            repository=repository,
            response=func_response,
            workspace=run_dir / "func_agent" / "workspace_patch",
            patch_path=run_dir / "func_agent" / "patch.diff",
        )
        write_agent_files(workspace, key_response)
        write_agent_files(workspace, func_response)
        tests = None
        if key_patch["ok"] and func_patch["ok"]:
            tests = run_tests(
                workspace,
                ("tests/test_keys.py", "tests/test_func.py"),
            )
        metadata["agents"] = {
            "key_agent": key_response,
            "func_agent": func_response,
        }
        metadata["integration"] = {
            "key_patch": key_patch,
            "func_patch": func_patch,
            "tests": tests,
        }

    elif args.mode == "three_agent":
        key_response = call_agent(
            repository=repository,
            agent=KEY_AGENT,
            mode=args.mode,
            base_url=args.base_url,
            model=args.model,
            output_dir=run_dir,
            temperature=args.temperature,
            top_p=args.top_p,
            top_k=args.top_k,
            min_p=args.min_p,
            presence_penalty=args.presence_penalty,
            max_tokens=args.max_tokens,
            timeout=args.request_timeout,
        )
        func_response = call_agent(
            repository=repository,
            agent=FUNC_AGENT,
            mode=args.mode,
            base_url=args.base_url,
            model=args.model,
            output_dir=run_dir,
            temperature=args.temperature,
            top_p=args.top_p,
            top_k=args.top_k,
            min_p=args.min_p,
            presence_penalty=args.presence_penalty,
            max_tokens=args.max_tokens,
            timeout=args.request_timeout,
        )
        peer_context = json.dumps(
            {
                "key_agent_message": key_response["message_to_teammates"],
                "key_agent_files": key_response["files"],
                "func_agent_message": func_response["message_to_teammates"],
                "func_agent_files": func_response["files"],
            },
            indent=2,
        )
        reviewer_response = call_agent(
            repository=repository,
            agent=REVIEWER_AGENT,
            mode=args.mode,
            base_url=args.base_url,
            model=args.model,
            output_dir=run_dir,
            peer_context=peer_context,
            temperature=args.temperature,
            top_p=args.top_p,
            top_k=args.top_k,
            min_p=args.min_p,
            presence_penalty=args.presence_penalty,
            max_tokens=args.max_tokens,
            timeout=args.request_timeout,
        )
        workspace = run_dir / "workspace_integrated"
        export_commit0_workspace(repository, workspace)
        write_agent_files(workspace, reviewer_response)
        patch = git_diff(workspace)
        (run_dir / "reviewer_agent" / "patch.diff").write_text(
            patch,
            encoding="utf-8",
        )
        patch_result = {
            "ok": bool(patch.strip()),
            "empty_patch": not bool(patch.strip()),
            "patch_path": str(run_dir / "reviewer_agent" / "patch.diff"),
        }
        tests = (
            run_tests(workspace, tuple(reviewer_response["tests_to_run"]))
            if patch_result["ok"]
            else None
        )
        metadata["agents"] = {
            "key_agent": key_response,
            "func_agent": func_response,
            "reviewer_agent": reviewer_response,
        }
        metadata["integration"] = {"patch": patch_result, "tests": tests}
    else:
        raise ValueError(args.mode)

    (run_dir / "run_summary.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return metadata


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=("single", "two_agent", "three_agent"),
        required=True,
    )
    parser.add_argument("--model", required=True)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--run-id", required=True)
    parser.add_argument(
        "--repo",
        type=Path,
        default=DEFAULT_REPO,
        help=(
            "Local cachetools Git repository containing the commit0 ref. "
            "Defaults to data/repos/commit0/cachetools."
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs/pilot/cachetools_agents"),
    )
    parser.add_argument("--temperature", type=float, default=0.6)
    parser.add_argument("--top-p", type=float, default=0.95)
    parser.add_argument("--top-k", type=int, default=20)
    parser.add_argument("--min-p", type=float, default=0.0)
    parser.add_argument("--presence-penalty", type=float, default=0.0)
    parser.add_argument("--max-tokens", type=int, default=16384)
    parser.add_argument("--request-timeout", type=int, default=600)
    parser.add_argument("--resume", action="store_true")
    return parser.parse_args()


def main() -> int:
    summary = run_mode(parse_args())
    print(json.dumps(summary["integration"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
