from __future__ import annotations

from asynccodebench.qualification.annotation_packets import (
    build_annotation_packet,
)
from asynccodebench.qualification.models import (
    CandidateInventory,
    CandidateRecord,
)


def test_annotation_packet_removes_gold_secondary_labels() -> None:
    candidate = CandidateRecord(
        task_id="commit0:demo",
        task_source="Commit0",
        upstream_version="a" * 40,
        issue_summary="Public issue.",
        publicly_implicated_modules=("src/a.py",),
        public_module_count=1,
        dependency_separability="One module.",
        static_dependency_edges=(),
        test_targets=("tests/test_a.py",),
        test_target_independence="One target.",
        measured_test_and_build_duration=1.0,
        measurement_command=("python", "-m", "pytest"),
        measurement_return_code=1,
        measurement_timed_out=False,
        measurement_environment={"python_version": "3.10"},
        candidate_parallel_subproblems=("implementation", "testing"),
        cross_module_constraints=(),
        expected_overlap_surface=("implementation-test",),
        expected_shared_resource_contention="One test worker.",
        public_evidence_sources=("public issue",),
        gold_informed_secondary_label="must not be visible",
    )
    packet = build_annotation_packet(
        CandidateInventory(candidates=(candidate,)),
        annotator_id="annotator-a",
    )

    assert packet.annotator_id == "annotator-a"
    assert packet.candidates[0].gold_informed_secondary_label is None
    assert "must not be visible" not in packet.model_dump_json()
