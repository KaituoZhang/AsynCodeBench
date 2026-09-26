import json
import shlex

from asyncodebench_harness.results import _final_test_payload
from tasks.commit0 import Commit0Task, normalize_evaluator_report


def test_split_pytest_command_supports_nonstandard_test_root():
    command = [
        "python",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "-o",
        "addopts=",
        "portalocker_tests",
        "--ignore=portalocker_tests/test_redis.py",
    ]

    test_cmd, targets = Commit0Task._split_pytest_command(command)

    assert shlex.split(test_cmd) == [
        "python",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "-o",
        "addopts=",
        "--ignore=portalocker_tests/test_redis.py",
    ]
    assert targets == ["portalocker_tests"]


def test_split_pytest_command_preserves_multiple_targets_and_option_values():
    command = (
        "python -m pytest -q tests/unit tests/integration "
        "--ignore tests/integration/test_slow.py -k smoke"
    )

    test_cmd, targets = Commit0Task._split_pytest_command(command)

    assert shlex.split(test_cmd) == [
        "python",
        "-m",
        "pytest",
        "-q",
        "--ignore",
        "tests/integration/test_slow.py",
        "-k",
        "smoke",
    ]
    assert targets == ["tests/unit", "tests/integration"]


def test_canonical_test_paths_strip_node_ids_and_reject_unsafe_paths():
    targets = [
        "tests/test_utils.py::test_flatten",
        "tests/test_utils.py",
        "tests/integration",
        "--ignore=tests/test_slow.py",
        "/tmp/not-a-task-test.py",
        "../outside.py",
    ]

    assert Commit0Task._canonical_test_paths(targets) == [
        "tests/test_utils.py",
        "tests/integration",
    ]


def test_missing_report_on_collection_failure_becomes_structured_error():
    report, counts = normalize_evaluator_report(
        "",
        exit_code=4,
        test_output=(
            "ImportError while loading conftest "
            "'/workspace/example_repo/tests/conftest.py'."
        ),
        work_dir="/workspace/example_repo",
        test_cmd="python -m pytest -q",
        test_targets=["tests"],
        evaluator_source="asyncodebench_manifest",
        timeout_seconds=900,
    )

    assert counts == {"passed": 0, "failed": 0, "error": 1}
    assert report["summary"] == {
        "passed": 0,
        "failed": 0,
        "error": 1,
        "total": 1,
    }
    assert report["asyncodebench"]["evaluation_failure_kind"] == (
        "collection_failed"
    )
    assert report["asyncodebench"]["collection_failed"] is True
    assert report["asyncodebench"]["synthetic_summary"] is True
    assert report["asyncodebench"]["report_was_missing"] is True


def test_pytest_usage_error_is_not_mislabeled_as_collection_failure():
    report, counts = normalize_evaluator_report(
        "",
        exit_code=4,
        test_output="ERROR: unrecognized arguments: --invalid-option",
        work_dir="/workspace/example_repo",
        test_cmd="python -m pytest -q",
        test_targets=["tests"],
        evaluator_source="asyncodebench_manifest",
        timeout_seconds=900,
    )

    assert counts == {"passed": 0, "failed": 0, "error": 1}
    assert report["asyncodebench"]["evaluation_failure_kind"] == (
        "pytest_usage_error"
    )
    assert report["asyncodebench"]["collection_failed"] is False


def test_invalid_report_with_zero_exit_is_not_misreported_as_success():
    report, counts = normalize_evaluator_report(
        "not-json",
        exit_code=0,
        work_dir="/workspace/example_repo",
        test_cmd="python -m pytest -q",
        test_targets=["tests"],
        evaluator_source="asyncodebench_manifest",
        timeout_seconds=900,
    )

    assert counts == {"passed": 0, "failed": 0, "error": 1}
    assert report["asyncodebench"]["evaluation_failure_kind"] == "missing_report"
    assert report["asyncodebench"]["report_was_invalid"] is True


def test_existing_pytest_summary_is_preserved_and_annotated():
    report, counts = normalize_evaluator_report(
        '{"summary":{"passed":7,"failed":2,"error":0,"total":9}}',
        exit_code=1,
        work_dir="/workspace/example_repo",
        test_cmd="python -m pytest -q",
        test_targets=["tests"],
        evaluator_source="asyncodebench_manifest",
        timeout_seconds=900,
        canonical_test_restore={"restored_paths": ["tests/test_api.py"]},
    )

    assert counts == {"passed": 7, "failed": 2, "error": 0}
    assert report["summary"]["total"] == 9
    assert report["asyncodebench"]["synthetic_summary"] is False
    assert report["asyncodebench"]["canonical_test_restore"] == {
        "restored_paths": ["tests/test_api.py"]
    }


def test_valid_json_report_with_failed_collectors_is_collection_failure():
    report, counts = normalize_evaluator_report(
        json.dumps(
            {
                "summary": {"total": 0, "collected": 0},
                "collectors": [
                    {"nodeid": "", "outcome": "passed"},
                    {
                        "nodeid": "tests/test_api.py",
                        "outcome": "failed",
                        "longrepr": "ImportError while importing test module",
                    },
                ],
            }
        ),
        exit_code=1,
        test_output="ERROR collecting tests/test_api.py",
        work_dir="/workspace/example_repo",
        test_cmd="python -m pytest -q",
        test_targets=["tests/test_api.py"],
        evaluator_source="asyncodebench_manifest",
        timeout_seconds=900,
    )

    assert counts == {"passed": 0, "failed": 0, "error": 1}
    assert report["summary"] == {"total": 1, "collected": 0, "error": 1}
    assert report["asyncodebench"]["synthetic_summary"] is False
    assert report["asyncodebench"]["evaluation_failure_kind"] == (
        "collection_failed"
    )
    assert report["asyncodebench"]["collection_failed"] is True
    assert report["asyncodebench"]["report_was_missing"] is False
    assert report["asyncodebench"]["report_was_invalid"] is False

    final_test = _final_test_payload(report)
    assert final_test["outcome"] == "model_failure:collection_failed"
    assert final_test["errors"] == 1
    assert final_test["evaluation_failure_kind"] == "collection_failed"


def test_timeout_without_report_keeps_timeout_classification():
    report, counts = normalize_evaluator_report(
        "{}",
        exit_code=124,
        work_dir="/workspace/example_repo",
        test_cmd="python -m pytest -q",
        test_targets=["tests"],
        evaluator_source="asyncodebench_manifest",
        timeout_seconds=900,
    )

    assert counts == {"passed": 0, "failed": 0, "error": 1}
    assert report["duration"] == 900
    assert report["asyncodebench"]["evaluation_failure_kind"] == "timeout"
    assert report["asyncodebench"]["timed_out"] is True
