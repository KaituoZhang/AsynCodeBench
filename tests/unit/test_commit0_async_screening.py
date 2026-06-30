from asynccodebench.qualification.commit0_async_screening import (
    parse_pytest_summary,
)


def test_parse_pytest_summary_from_failed_run() -> None:
    summary = parse_pytest_summary(
        "37 failed, 1 skipped, 1 deselected in 0.28s"
    )

    assert summary.collected == 39
    assert summary.failed == 37
    assert summary.skipped == 1
    assert summary.deselected == 1


def test_parse_pytest_summary_from_collection_error() -> None:
    summary = parse_pytest_summary(
        "collected 0 items / 1 error\nERROR tests/test_demo.py"
    )

    assert summary.collected == 0
    assert summary.errors == 1


def test_parse_pytest_summary_from_passing_run() -> None:
    summary = parse_pytest_summary("215 passed in 0.32s")

    assert summary.collected == 215
    assert summary.passed == 215
