#!/usr/bin/env python
"""Re-evaluate a saved Commit0 run tarball with its task manifest command."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--task", required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--reason", required=True)
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def evaluator_args(manifest: Path) -> list[str]:
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    command = payload.get("evaluator_command")
    if isinstance(command, str):
        tokens = shlex.split(command)
    elif isinstance(command, list):
        tokens = [str(token) for token in command]
    else:
        raise ValueError(f"Missing evaluator_command in {manifest}")

    try:
        pytest_index = tokens.index("pytest")
    except ValueError as exc:
        raise ValueError(f"Evaluator is not a pytest command: {tokens}") from exc
    return tokens[pytest_index + 1 :]


def safe_extract(archive: Path, destination: Path) -> None:
    destination = destination.resolve()
    with tarfile.open(archive, "r:gz") as handle:
        for member in handle.getmembers():
            member_path = (destination / member.name).resolve()
            if destination not in member_path.parents and member_path != destination:
                raise ValueError(f"Unsafe archive member: {member.name}")
        handle.extractall(destination)


def preserve(path: Path) -> None:
    if not path.exists():
        return
    backup = path.with_name(f"{path.stem}.pre_manifest_retest{path.suffix}")
    if not backup.exists():
        shutil.copy2(path, backup)


def main() -> int:
    args = parse_args()
    run_dir = args.run_dir.resolve()
    manifest = args.manifest.resolve()
    archive = run_dir / "final_repo" / f"{args.task}.tar.gz"
    if not archive.exists():
        raise FileNotFoundError(archive)

    pytest_args = evaluator_args(manifest)
    with tempfile.TemporaryDirectory(prefix=f"{args.task}-manifest-retest-") as tmp:
        tmp_path = Path(tmp)
        safe_extract(archive, tmp_path)
        repo_dir = tmp_path / f"{args.task}_repo"
        if not repo_dir.is_dir():
            raise FileNotFoundError(repo_dir)

        report_path = tmp_path / "report.json"
        command = [
            sys.executable,
            "-m",
            "pytest",
            *pytest_args,
            "--json-report",
            f"--json-report-file={report_path}",
            "--continue-on-collection-errors",
        ]
        env = os.environ.copy()
        python_paths = [str(repo_dir / "src"), str(repo_dir)]
        if env.get("PYTHONPATH"):
            python_paths.append(env["PYTHONPATH"])
        env["PYTHONPATH"] = os.pathsep.join(python_paths)

        result = subprocess.run(
            command,
            cwd=repo_dir,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=args.timeout,
            check=False,
        )
        if not report_path.exists():
            raise RuntimeError(
                "pytest did not produce report.json:\n" + result.stdout[-4000:]
            )

        report = json.loads(report_path.read_text(encoding="utf-8"))
        report["asynccodebench"] = {
            "final_evaluator_source": "asynccodebench_manifest",
            "final_test_command": command,
            "manifest": str(manifest),
            "offline_saved_tarball_retest": True,
            "retest_reason": args.reason,
            "timed_out": False,
        }

        output_path = run_dir / f"{args.task}_test_output.txt"
        exit_path = run_dir / f"{args.task}_pytest_exit_code.txt"
        final_report_path = run_dir / "report.json"
        for path in (output_path, exit_path, final_report_path):
            preserve(path)

        output_path.write_text(result.stdout, encoding="utf-8")
        exit_path.write_text(str(result.returncode), encoding="utf-8")
        final_report_path.write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8"
        )

        summary = report.get("summary", {})
        metadata = {
            "archive": str(archive),
            "archive_sha256": sha256(archive),
            "command": command,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "exit_code": result.returncode,
            "manifest": str(manifest),
            "python": sys.version,
            "reason": args.reason,
            "summary": summary,
        }
        (run_dir / "manifest_retest_metadata.json").write_text(
            json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
        )

    print(
        f"{run_dir.name}: exit={result.returncode} "
        f"passed={summary.get('passed', 0)} failed={summary.get('failed', 0)} "
        f"errors={summary.get('error', 0)} total={summary.get('total', 0)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
