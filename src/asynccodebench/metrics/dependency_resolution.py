"""Post-hoc dependency-resolution analysis for agent event logs."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


_PASSED_RE = re.compile(r"(?P<count>\d+)\s+passed\b")
_FILE_PROGRESS_RE = re.compile(
    r"(?P<path>tests/[^\s]+\.py)\s+(?P<marks>[.FEFsxX]+)"
)
_EDITED_FILE_RE = re.compile(
    r"The file /workspace/[^/]+/(?P<path>[^ ]+) has been edited\."
)
_TEXT_CONTENT_RE = re.compile(r"text=(?P<quote>['\"])(?P<text>.*?)(?P=quote)", re.S)


@dataclass(frozen=True)
class Checkpoint:
    checkpoint_id: str
    event_index: int
    logical_iteration: int | None
    timestamp: str | None
    engineer_id: str | None
    exit_code: int | None
    action_event_index: int | None
    action_thought: str
    output: str
    covered_selectors: frozenset[str]
    scope: str
    evidence: str
    confidence: str
    file_versions: dict[str, int]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records


def write_json(payload: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _event_iterations(events: list[dict[str, Any]]) -> dict[str, int]:
    iterations: dict[str, int] = {}
    for event in events:
        response_id = event.get("llm_response_id")
        if response_id and response_id not in iterations:
            iterations[response_id] = len(iterations) + 1
    return iterations


def _plain_content(content: str) -> str:
    """Extract the readable text from OpenHands TextContent reprs."""

    match = _TEXT_CONTENT_RE.search(content)
    if not match:
        return content
    text = match.group("text")
    try:
        return bytes(text, "utf-8").decode("unicode_escape")
    except UnicodeDecodeError:
        return text


def _selector_index(metrics: dict[str, Any]) -> dict[str, set[str]]:
    selectors: set[str] = set()
    for dependency in metrics["dependency_points"]:
        for key in (
            "upstream_probe_tests",
            "downstream_probe_tests",
            "integrated_probe_tests",
        ):
            selectors.update(dependency.get(key, ()))

    by_file: dict[str, set[str]] = {}
    for selector in selectors:
        file_path = selector.split("::", 1)[0]
        by_file.setdefault(file_path, set()).add(selector)
    return by_file


def _selectors_for_file(selector_index: dict[str, set[str]], file_path: str) -> set[str]:
    return set(selector_index.get(file_path, set()))


def _infer_covered_selectors(
    *,
    output: str,
    action_thought: str,
    exit_code: int | None,
    selector_index: dict[str, set[str]],
) -> tuple[frozenset[str], str, str, str]:
    if exit_code != 0:
        covered = _passing_file_selectors(output, selector_index)
        evidence = "nonzero pytest run with passing per-file progress lines"
        return frozenset(covered), "partial_pytest_progress", evidence, "medium"

    covered: set[str] = set()
    passed_match = _PASSED_RE.search(output)
    passed_count = int(passed_match.group("count")) if passed_match else None

    if passed_count == 215 or "215 passed" in output:
        for selectors in selector_index.values():
            covered.update(selectors)
        return (
            frozenset(covered),
            "full_evaluator",
            "terminal output reports full Commit0 cachetools suite passed",
            "high",
        )

    covered.update(_passing_file_selectors(output, selector_index))
    if covered:
        return (
            frozenset(covered),
            "pytest_file_progress",
            "terminal output contains per-file all-pass pytest progress",
            "high",
        )

    thought = action_thought.lower()
    if passed_count == 42 and "decorator" in thought:
        covered.update(_selectors_for_file(selector_index, "tests/test_func.py"))
        return (
            frozenset(covered),
            "inferred_test_func",
            "42 passed after an action described as rerunning decorator tests",
            "medium",
        )

    return frozenset(), "unknown", "no dependency probe coverage inferred", "none"


def _passing_file_selectors(
    output: str,
    selector_index: dict[str, set[str]],
) -> set[str]:
    covered: set[str] = set()
    for match in _FILE_PROGRESS_RE.finditer(output):
        file_path = match.group("path")
        marks = match.group("marks")
        if marks and set(marks) <= {"."}:
            covered.update(_selectors_for_file(selector_index, file_path))
    return covered


def extract_checkpoints(
    *,
    metrics: dict[str, Any],
    events: list[dict[str, Any]],
) -> list[Checkpoint]:
    iterations = _event_iterations(events)
    selector_index = _selector_index(metrics)
    last_action: dict[str, Any] | None = None
    last_action_iteration: int | None = None
    file_versions: dict[str, int] = {}
    checkpoints: list[Checkpoint] = []

    for event in events:
        response_id = event.get("llm_response_id")
        iteration = iterations.get(response_id)
        event_type = event.get("event_type")

        if event_type == "ActionEvent":
            last_action = event
            last_action_iteration = iteration
            continue

        if event_type != "ObservationEvent":
            continue

        observation = event.get("observation") or {}
        raw_content = str(observation.get("content", ""))
        content = _plain_content(raw_content)
        effective_iteration = iteration or last_action_iteration

        if observation.get("type") == "FileEditorObservation":
            for match in _EDITED_FILE_RE.finditer(content):
                if effective_iteration is not None:
                    file_versions[match.group("path")] = effective_iteration
            continue

        if observation.get("type") != "TerminalObservation":
            continue

        thought = ""
        action_event_index = None
        if last_action is not None:
            action_event_index = last_action.get("event_index")
            thought_value = last_action.get("thought") or []
            if isinstance(thought_value, list):
                thought = " ".join(str(item) for item in thought_value)
            else:
                thought = str(thought_value)

        covered, scope, evidence, confidence = _infer_covered_selectors(
            output=content,
            action_thought=thought,
            exit_code=observation.get("exit_code"),
            selector_index=selector_index,
        )
        if not covered:
            continue

        checkpoints.append(
            Checkpoint(
                checkpoint_id=f"event-{event['event_index']}",
                event_index=event["event_index"],
                logical_iteration=effective_iteration,
                timestamp=event.get("timestamp"),
                engineer_id=event.get("engineer_id"),
                exit_code=observation.get("exit_code"),
                action_event_index=action_event_index,
                action_thought=thought,
                output=content,
                covered_selectors=covered,
                scope=scope,
                evidence=evidence,
                confidence=confidence,
                file_versions=dict(file_versions),
            )
        )

    return checkpoints


def final_evaluator_checkpoint(
    *,
    metrics: dict[str, Any],
    output: str,
    checkpoint_id: str,
    logical_iteration: int | None,
    exit_code: int = 0,
) -> Checkpoint | None:
    """Build a dependency checkpoint from a runner-level final test output."""

    covered, scope, evidence, confidence = _infer_covered_selectors(
        output=output,
        action_thought="runner final evaluator",
        exit_code=exit_code,
        selector_index=_selector_index(metrics),
    )
    if not covered:
        return None
    return Checkpoint(
        checkpoint_id=checkpoint_id,
        event_index=-1,
        logical_iteration=logical_iteration,
        timestamp=None,
        engineer_id="runner",
        exit_code=exit_code,
        action_event_index=None,
        action_thought="runner final evaluator",
        output=output,
        covered_selectors=covered,
        scope=f"runner_{scope}",
        evidence=f"runner final evaluator: {evidence}",
        confidence=confidence,
        file_versions={},
    )


def max_logical_iteration(events: list[dict[str, Any]]) -> int | None:
    iterations = _event_iterations(events)
    return max(iterations.values()) if iterations else None


def _first_covering(
    checkpoints: list[Checkpoint],
    selectors: set[str],
) -> Checkpoint | None:
    if not selectors:
        return None
    for checkpoint in checkpoints:
        if selectors.issubset(checkpoint.covered_selectors):
            return checkpoint
    return None


def _first_valid_covering(
    checkpoints: list[Checkpoint],
    selectors: set[str],
    files: set[str],
) -> Checkpoint | None:
    """Return first checkpoint whose evidence is after the latest known edit."""

    if not selectors:
        return None
    for checkpoint in checkpoints:
        if not selectors.issubset(checkpoint.covered_selectors):
            continue
        if checkpoint.logical_iteration is None:
            return checkpoint
        stale = False
        for file_path in files:
            last_edit_iteration = checkpoint.file_versions.get(file_path)
            if (
                last_edit_iteration is not None
                and last_edit_iteration > checkpoint.logical_iteration
            ):
                stale = True
                break
        if not stale:
            return checkpoint
    return None


def analyze_dependency_resolution(
    *,
    metrics: dict[str, Any],
    events: list[dict[str, Any]],
    dependency_id: str | None = None,
    extra_checkpoints: list[Checkpoint] | None = None,
) -> dict[str, Any]:
    checkpoints = extract_checkpoints(metrics=metrics, events=events)
    if extra_checkpoints:
        checkpoints.extend(extra_checkpoints)
        checkpoints.sort(
            key=lambda checkpoint: (
                checkpoint.logical_iteration
                if checkpoint.logical_iteration is not None
                else 10**12,
                checkpoint.event_index if checkpoint.event_index >= 0 else 10**9,
                checkpoint.checkpoint_id,
            )
        )
    dependencies = metrics["dependency_points"]
    if dependency_id:
        dependencies = [
            dependency
            for dependency in dependencies
            if dependency["dependency_id"] == dependency_id
        ]
        if not dependencies:
            raise ValueError(f"dependency_id not found: {dependency_id}")

    results = []
    resolved_count = 0
    for dependency in dependencies:
        upstream = set(dependency.get("upstream_probe_tests", ()))
        downstream = set(dependency.get("downstream_probe_tests", ()))
        integrated = set(dependency.get("integrated_probe_tests", ()))
        producer_files = set(dependency.get("producer_files", ()))
        consumer_files = set(dependency.get("consumer_files", ()))

        upstream_checkpoint = _first_valid_covering(
            checkpoints, upstream, producer_files
        )
        downstream_checkpoint = _first_valid_covering(
            checkpoints, downstream, consumer_files
        )
        strict_checkpoint = _first_covering(checkpoints, integrated)
        composed_iteration = None
        composed_confidence = "none"
        if upstream_checkpoint and downstream_checkpoint:
            iterations = [
                item.logical_iteration
                for item in (upstream_checkpoint, downstream_checkpoint)
                if item.logical_iteration is not None
            ]
            if len(iterations) == 2:
                composed_iteration = max(iterations)
                composed_confidence = _compose_confidence(
                    upstream_checkpoint.confidence,
                    downstream_checkpoint.confidence,
                )

        if strict_checkpoint is not None:
            resolved_count += 1

        results.append(
            {
                "dependency_id": dependency["dependency_id"],
                "producer_subproblem": dependency.get("producer_subproblem"),
                "consumer_subproblem": dependency.get("consumer_subproblem"),
                "strict_integrated_resolution": _checkpoint_summary(
                    strict_checkpoint
                ),
                "composed_resolution": {
                    "logical_iteration": composed_iteration,
                    "confidence": composed_confidence,
                    "definition": (
                        "max(upstream_resolution, downstream_resolution) "
                        "when both sides have observed passing probes"
                    ),
                },
                "upstream_resolution": _checkpoint_summary(upstream_checkpoint),
                "downstream_resolution": _checkpoint_summary(
                    downstream_checkpoint
                ),
                "covered_probe_counts": {
                    "upstream": len(upstream),
                    "downstream": len(downstream),
                    "integrated": len(integrated),
                },
            }
        )

    return {
        "task_id": metrics["task_id"],
        "metric_annotation_id": metrics.get("metric_annotation_id"),
        "dependency_id_filter": dependency_id,
        "checkpoint_count": len(checkpoints),
        "ADPR_strict": {
            "resolved": resolved_count,
            "total": len(dependencies),
            "value": resolved_count / len(dependencies) if dependencies else None,
        },
        "dependency_results": results,
        "checkpoints": [_checkpoint_detail(checkpoint) for checkpoint in checkpoints],
        "limitations": [
            (
                "This is post-hoc event-log analysis. It reports the first "
                "observed passing checkpoint, not necessarily the earliest "
                "workspace state where the dependency became correct."
            ),
            (
                "Exact per-iteration DRS requires runner instrumentation that "
                "runs the registered probe tests after every patch or checkpoint."
            ),
        ],
    }


def _compose_confidence(left: str, right: str) -> str:
    order = {"none": 0, "low": 1, "medium": 2, "high": 3}
    inverse = {value: key for key, value in order.items()}
    return inverse[min(order.get(left, 0), order.get(right, 0))]


def _checkpoint_summary(checkpoint: Checkpoint | None) -> dict[str, Any] | None:
    if checkpoint is None:
        return None
    return {
        "checkpoint_id": checkpoint.checkpoint_id,
        "event_index": checkpoint.event_index,
        "logical_iteration": checkpoint.logical_iteration,
        "timestamp": checkpoint.timestamp,
        "scope": checkpoint.scope,
        "confidence": checkpoint.confidence,
        "evidence": checkpoint.evidence,
        "action_thought": checkpoint.action_thought,
    }


def _checkpoint_detail(checkpoint: Checkpoint) -> dict[str, Any]:
    return {
        **(_checkpoint_summary(checkpoint) or {}),
        "engineer_id": checkpoint.engineer_id,
        "exit_code": checkpoint.exit_code,
        "action_event_index": checkpoint.action_event_index,
        "covered_selector_count": len(checkpoint.covered_selectors),
        "covered_selectors": sorted(checkpoint.covered_selectors),
    }
