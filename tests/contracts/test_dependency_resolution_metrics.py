from __future__ import annotations

from asyncodebench.metrics.dependency_resolution import (
    analyze_dependency_resolution,
    final_evaluator_checkpoint,
)


def test_dependency_resolution_reports_strict_and_composed_iterations() -> None:
    metrics = {
        "task_id": "commit0:cachetools",
        "metric_annotation_id": "test",
        "dependency_points": [
            {
                "dependency_id": "dep.typed",
                "producer_subproblem": "keys",
                "consumer_subproblem": "func",
                "producer_files": ["src/cachetools/keys.py"],
                "consumer_files": ["src/cachetools/func.py"],
                "upstream_probe_tests": [
                    "tests/test_keys.py::CacheKeysTest::test_typedkey"
                ],
                "downstream_probe_tests": [
                    "tests/test_func.py::LRUDecoratorTest::test_decorator_typed"
                ],
                "integrated_probe_tests": [
                    "tests/test_keys.py::CacheKeysTest::test_typedkey",
                    "tests/test_func.py::LRUDecoratorTest::test_decorator_typed",
                ],
            }
        ],
    }
    events = [
        {
            "event_index": 1,
            "event_type": "ActionEvent",
            "llm_response_id": "iter-1",
            "action": {"type": "TerminalAction"},
            "thought": ["run all tests"],
        },
        {
            "event_index": 2,
            "event_type": "ObservationEvent",
            "llm_response_id": None,
            "timestamp": "t1",
            "engineer_id": "agent",
            "observation": {
                "type": "TerminalObservation",
                "exit_code": 1,
                "content": (
                    "tests/test_keys.py ..... [ 10%]\n"
                    "tests/test_func.py ....F [ 20%]\n"
                ),
            },
        },
        {
            "event_index": 3,
            "event_type": "ActionEvent",
            "llm_response_id": "iter-2",
            "action": {"type": "TerminalAction"},
            "thought": ["rerunning decorator tests"],
        },
        {
            "event_index": 4,
            "event_type": "ObservationEvent",
            "llm_response_id": None,
            "timestamp": "t2",
            "engineer_id": "agent",
            "observation": {
                "type": "TerminalObservation",
                "exit_code": 0,
                "content": "42 passed in 0.05s",
            },
        },
        {
            "event_index": 5,
            "event_type": "ActionEvent",
            "llm_response_id": "iter-3",
            "action": {"type": "TerminalAction"},
            "thought": ["run all tests"],
        },
        {
            "event_index": 6,
            "event_type": "ObservationEvent",
            "llm_response_id": None,
            "timestamp": "t3",
            "engineer_id": "agent",
            "observation": {
                "type": "TerminalObservation",
                "exit_code": 0,
                "content": (
                    "tests/test_keys.py ..... [ 10%]\n"
                    "tests/test_func.py .......................................... [ 20%]\n"
                ),
            },
        },
    ]

    report = analyze_dependency_resolution(metrics=metrics, events=events)
    result = report["dependency_results"][0]

    assert result["upstream_resolution"]["logical_iteration"] == 1
    assert result["downstream_resolution"]["logical_iteration"] == 2
    assert result["composed_resolution"]["logical_iteration"] == 2
    assert result["strict_integrated_resolution"]["logical_iteration"] == 3


def test_final_evaluator_output_can_supply_integrated_checkpoint() -> None:
    metrics = {
        "task_id": "commit0:cachetools",
        "metric_annotation_id": "test",
        "dependency_points": [
            {
                "dependency_id": "dep.typed",
                "producer_subproblem": "keys",
                "consumer_subproblem": "func",
                "producer_files": ["src/cachetools/keys.py"],
                "consumer_files": ["src/cachetools/func.py"],
                "upstream_probe_tests": [
                    "tests/test_keys.py::CacheKeysTest::test_typedkey"
                ],
                "downstream_probe_tests": [
                    "tests/test_func.py::LRUDecoratorTest::test_decorator_typed"
                ],
                "integrated_probe_tests": [
                    "tests/test_keys.py::CacheKeysTest::test_typedkey",
                    "tests/test_func.py::LRUDecoratorTest::test_decorator_typed",
                ],
            }
        ],
    }
    checkpoint = final_evaluator_checkpoint(
        metrics=metrics,
        output="215 passed, 15 warnings in 0.34s",
        checkpoint_id="runner-final-evaluator",
        logical_iteration=14,
    )

    report = analyze_dependency_resolution(
        metrics=metrics,
        events=[],
        extra_checkpoints=[checkpoint] if checkpoint else [],
    )
    result = report["dependency_results"][0]

    assert result["strict_integrated_resolution"]["checkpoint_id"] == (
        "runner-final-evaluator"
    )
    assert result["strict_integrated_resolution"]["logical_iteration"] == 14
    assert report["ADPR_strict"]["value"] == 1.0
