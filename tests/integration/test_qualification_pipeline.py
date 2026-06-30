from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path


def test_qualification_cli_builds_json_and_csv(tmp_path: Path) -> None:
    input_path = tmp_path / "batch.json"
    json_output = tmp_path / "manifest.json"
    csv_output = tmp_path / "manifest.csv"
    input_path.write_text(
        json.dumps(
            {
                "protocol_version": "qualification-v0.2",
                "candidates": [
                    {
                        "task_id": "commit0:demo",
                        "task_source": "Commit0",
                        "upstream_version": "abc123",
                        "issue_summary": "Implement public behavior.",
                        "publicly_implicated_modules": ["src/demo.py"],
                        "public_module_count": 1,
                        "dependency_separability": "Implementation and tests.",
                        "static_dependency_edges": [],
                        "test_targets": ["tests/test_demo.py"],
                        "test_target_independence": "One executable target.",
                        "measured_test_and_build_duration": 1.5,
                        "measurement_command": [
                            "python",
                            "-m",
                            "pytest",
                            "-q"
                        ],
                        "measurement_return_code": 1,
                        "measurement_timed_out": False,
                        "measurement_environment": {
                            "python_version": "3.10.4",
                            "platform": "linux"
                        },
                        "candidate_parallel_subproblems": [
                            "implementation",
                            "tests",
                        ],
                        "cross_module_constraints": [],
                        "expected_overlap_surface": ["implementation-test"],
                        "expected_shared_resource_contention": (
                            "Shared pytest worker."
                        ),
                        "public_evidence_sources": [
                            "public issue",
                            "commit0 ref"
                        ],
                    }
                ],
                "annotator_decisions": [
                    {
                        "task_id": "commit0:demo",
                        "annotator_id": "annotator-a",
                        "parallelizability_label": (
                            "partially_parallelizable"
                        ),
                        "include": True,
                        "rationale": "Two natural activities overlap.",
                    },
                    {
                        "task_id": "commit0:demo",
                        "annotator_id": "annotator-b",
                        "parallelizability_label": (
                            "partially_parallelizable"
                        ),
                        "include": True,
                        "rationale": "Tests can proceed beside implementation.",
                    },
                ],
                "adjudications": [],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    repository_root = Path(__file__).resolve().parents[2]

    completed = subprocess.run(
        [
            sys.executable,
            str(repository_root / "scripts/qualification_build_manifest.py"),
            "--input",
            str(input_path),
            "--json-output",
            str(json_output),
            "--csv-output",
            str(csv_output),
        ],
        cwd=repository_root,
        check=True,
        capture_output=True,
        text=True,
    )

    assert str(json_output) in completed.stdout
    assert str(csv_output) in completed.stdout
    payload = json.loads(json_output.read_text(encoding="utf-8"))
    assert payload["candidate_count"] == 1
    assert payload["included_count"] == 1
    with csv_output.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert rows[0]["task_id"] == "commit0:demo"
