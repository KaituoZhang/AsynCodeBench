"""Constants for the v0.3 Commit0 cookiecutter task records."""

from __future__ import annotations

from pathlib import Path


COOKIECUTTER_TASK_ID = "commit0:cookiecutter"
COOKIECUTTER_STRIPPED_SHA = "c7a8c70a666270053d848f5664413af1af7a987f"
COOKIECUTTER_COMPLETE_SHA = "b4451231809fb9e4fc2a1e95d433cb030e4b9e06"

COOKIECUTTER_EVALUATOR_COMMAND = (
    "python3.10",
    "-m",
    "pytest",
    "-q",
    "-p",
    "pytest_mock",
    "-o",
    "addopts=",
    "tests/test_get_config.py",
    "tests/test_generate_context.py",
    "tests/test_find.py",
    "tests/test_generate_file.py",
    "tests/test_generate_files.py",
    "tests/test_generate_hooks.py",
    "tests/test_hooks.py",
    "tests/test_pre_prompt_hooks.py",
    "tests/test_prompt.py",
    "tests/test_read_user_variable.py",
    "tests/test_read_user_choice.py",
    "tests/test_read_user_yes_no.py",
    "tests/repository/test_is_repo_url.py",
    "tests/repository/test_repository_has_cookiecutter_json.py",
    "tests/repository/test_determine_repository_should_use_local_repo.py",
    "tests/vcs/test_identify_repo.py",
    "tests/vcs/test_is_vcs_installed.py",
    "tests/zipfile/test_unzip.py",
    "tests/test_main.py",
    "--deselect=tests/test_prompt.py::TestPrompt::test_prompt_for_config_with_human_choices[context0]",
    "--deselect=tests/test_prompt.py::TestPrompt::test_prompt_for_config_with_human_choices[context1]",
    "--deselect=tests/test_prompt.py::TestPrompt::test_prompt_for_config_with_human_choices[context2]",
)

COOKIECUTTER_MANIFEST_FILES = (
    Path("manifests/pilot/v0.3/tasks/commit0_cookiecutter.json"),
    Path("manifests/pilot/v0.3/scenarios/commit0_cookiecutter.json"),
    Path("manifests/pilot/v0.3/quality/commit0_cookiecutter.json"),
    Path("manifests/pilot/v0.3/metrics/commit0_cookiecutter_async_metrics.json"),
)
