"""Finalize v0.3 task qualification from independent human decisions."""

from __future__ import annotations

from asyncodebench.dataset.models import (
    AdjudicationForm,
    AnnotationForm,
    QualificationStatus,
    TaskRecord,
)


def finalize_task_record(
    task: TaskRecord,
    annotations: tuple[AnnotationForm, AnnotationForm],
    adjudication: AdjudicationForm | None = None,
) -> TaskRecord:
    """Return a finalized task after validating independent decisions."""

    source_namespace, separator, repository = task.task_id.partition(":")
    public_task_id = (
        f"asyncodebench:{repository}"
        if separator == ":" and source_namespace == "commit0"
        else task.task_id
    )

    def annotation_matches_task(form: AnnotationForm | AdjudicationForm) -> bool:
        if form.source_task_id is None:
            # Backward compatibility for in-memory v0.3 qualification tests.
            return form.task_id == task.task_id
        return (
            form.task_id == public_task_id
            and form.source_task_id == task.task_id
        )

    if task.qualification_status is QualificationStatus.FINALIZED:
        raise ValueError("task is already finalized")
    if len({form.annotator_id for form in annotations}) != 2:
        raise ValueError("two distinct annotators are required")
    if any(not annotation_matches_task(form) for form in annotations):
        raise ValueError("annotation task_id does not match task")
    if any(
        form.include is None
        or form.parallelizability_label is None
        or form.rationale is None
        for form in annotations
    ):
        raise ValueError("both annotations must be complete")

    first, second = annotations
    agreement = (
        first.include == second.include
        and first.parallelizability_label == second.parallelizability_label
    )
    provenance = (
        f"human-annotation:{first.annotator_id}",
        f"human-annotation:{second.annotator_id}",
    )
    if agreement:
        include = first.include
        label = first.parallelizability_label
    else:
        if adjudication is None:
            raise ValueError("annotation disagreement requires adjudication")
        if not annotation_matches_task(adjudication):
            raise ValueError("adjudication task_id does not match task")
        if set(adjudication.annotator_ids) != {
            first.annotator_id,
            second.annotator_id,
        }:
            raise ValueError("adjudication annotator_ids do not match")
        if (
            adjudication.include is None
            or adjudication.parallelizability_label is None
            or adjudication.rationale is None
        ):
            raise ValueError("adjudication must be complete")
        include = adjudication.include
        label = adjudication.parallelizability_label
        provenance += (f"human-adjudication:{adjudication.adjudicator_id}",)

    payload = task.model_dump()
    payload.update(
        {
            "qualification_status": QualificationStatus.FINALIZED,
            "qualification_label": label,
            "inclusion_decision": include,
            "annotation_provenance": provenance,
        }
    )
    return TaskRecord.model_validate(payload)
