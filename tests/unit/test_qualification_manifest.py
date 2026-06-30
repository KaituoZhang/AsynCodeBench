from __future__ import annotations

import csv
import json

import pytest

from asynccodebench.contracts import ParallelizabilityLabel
from asynccodebench.qualification import (
    AdjudicationDecision,
    AnnotatorDecision,
    CandidateRecord,
    QualificationBatchInput,
    QualificationProtocolError,
    build_manifest,
    write_manifest_csv,
    write_manifest_json,
)


def candidate(task_id: str) -> CandidateRecord:
    return CandidateRecord(
        task_id=task_id,
        task_source="Commit0",
        upstream_version=f"version-{task_id}",
        issue_summary="Public issue description.",
        publicly_implicated_modules=("src/module.py",),
        public_module_count=1,
        dependency_separability="Single public module plus independent tests.",
        static_dependency_edges=(),
        test_targets=("tests/test_module.py",),
        test_target_independence="One executable target.",
        measured_test_and_build_duration=1.0,
        measurement_command=("python", "-m", "pytest", "-q"),
        measurement_return_code=1,
        measurement_timed_out=False,
        measurement_environment={
            "python_version": "3.10.4",
            "platform": "linux",
        },
        candidate_parallel_subproblems=("implementation", "testing"),
        cross_module_constraints=(),
        expected_overlap_surface=("implementation-test",),
        expected_shared_resource_contention="Shared test worker.",
        public_evidence_sources=("public issue", "commit0 ref"),
    )


def decision(
    task_id: str,
    annotator: str,
    label: ParallelizabilityLabel,
) -> AnnotatorDecision:
    return AnnotatorDecision(
        task_id=task_id,
        annotator_id=annotator,
        parallelizability_label=label,
        rationale="Decision based on public task evidence.",
    )


def make_batch() -> QualificationBatchInput:
    parallel = ParallelizabilityLabel.PARALLELIZABLE
    partial = ParallelizabilityLabel.PARTIALLY_PARALLELIZABLE
    return QualificationBatchInput(
        candidates=(candidate("task-b"), candidate("task-a")),
        annotator_decisions=(
            decision("task-b", "ann-1", parallel),
            decision("task-b", "ann-2", partial),
            decision("task-a", "ann-1", partial),
            decision("task-a", "ann-2", partial),
        ),
        adjudications=(
            AdjudicationDecision(
                task_id="task-b",
                adjudicator_id="ann-3",
                parallelizability_label=partial,
                include=True,
                rationale="Cross-module constraint prevents full separation.",
            ),
        ),
    )


def test_manifest_is_sorted_and_counted() -> None:
    manifest = build_manifest(make_batch())

    assert [record.candidate.task_id for record in manifest.records] == [
        "task-a",
        "task-b",
    ]
    assert manifest.candidate_count == 2
    assert manifest.included_count == 2
    assert manifest.excluded_count == 0
    assert manifest.agreement.disagreement_task_ids == ("task-b",)


def test_manifest_rejects_unknown_decision_task() -> None:
    batch = make_batch()
    invalid = QualificationBatchInput(
        candidates=batch.candidates,
        annotator_decisions=(
            *batch.annotator_decisions,
            decision(
                "unknown",
                "ann-1",
                ParallelizabilityLabel.EFFECTIVELY_SERIAL,
            ),
        ),
        adjudications=batch.adjudications,
    )

    with pytest.raises(QualificationProtocolError, match="unknown tasks"):
        build_manifest(invalid)


def test_json_and_csv_outputs_are_deterministic(tmp_path) -> None:
    manifest = build_manifest(make_batch())
    json_path = tmp_path / "pilot.json"
    csv_path = tmp_path / "pilot.csv"

    write_manifest_json(manifest, json_path)
    first_json = json_path.read_bytes()
    write_manifest_json(manifest, json_path)
    assert json_path.read_bytes() == first_json

    write_manifest_csv(manifest, csv_path)
    first_csv = csv_path.read_bytes()
    write_manifest_csv(manifest, csv_path)
    assert csv_path.read_bytes() == first_csv

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["agreement"]["task_count"] == 2
    with csv_path.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert [row["task_id"] for row in rows] == ["task-a", "task-b"]
    assert json.loads(rows[1]["annotator_labels"]) == [
        "parallelizable",
        "partially_parallelizable",
    ]
