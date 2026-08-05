import shlex

from tasks.commit0 import Commit0Task


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
