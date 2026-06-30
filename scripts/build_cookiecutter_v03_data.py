"""Generate and validate the v0.3 Commit0 cookiecutter task records."""

from __future__ import annotations

import json
from pathlib import Path


TASK_ID = "commit0:cookiecutter"
STRIPPED_SHA = "c7a8c70a666270053d848f5664413af1af7a987f"
COMPLETE_SHA = "b4451231809fb9e4fc2a1e95d433cb030e4b9e06"
BASE_REF = "origin/commit0_combined"
CANDIDATE_EVIDENCE = "manifests/candidates/commit0_async_screening_v0.3.json"

EVALUATOR_COMMAND = [
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
]
TEST_TARGETS = EVALUATOR_COMMAND[8:]
PUBLIC_MODULES = [
    "cookiecutter/cli.py",
    "cookiecutter/config.py",
    "cookiecutter/environment.py",
    "cookiecutter/exceptions.py",
    "cookiecutter/extensions.py",
    "cookiecutter/find.py",
    "cookiecutter/generate.py",
    "cookiecutter/hooks.py",
    "cookiecutter/log.py",
    "cookiecutter/main.py",
    "cookiecutter/prompt.py",
    "cookiecutter/replay.py",
    "cookiecutter/repository.py",
    "cookiecutter/utils.py",
    "cookiecutter/vcs.py",
    "cookiecutter/zipfile.py",
]
DEPENDENCIES = [
    {
        "consumer_subproblem": "orchestration_layer",
        "dependency_type": "api_contract",
        "description": "The main cookiecutter workflow consumes user config, replay, prompting, no_input, and extra_context contracts before repository resolution and generation.",
        "evidence_paths": [
            "cookiecutter/config.py",
            "cookiecutter/prompt.py",
            "cookiecutter/replay.py",
            "cookiecutter/main.py",
            "tests/test_get_config.py",
            "tests/test_prompt.py",
            "tests/test_main.py",
        ],
        "producer_subproblem": "config_prompt_layer",
        "schema_version": "0.3",
    },
    {
        "consumer_subproblem": "orchestration_layer",
        "dependency_type": "api_contract",
        "description": "The main workflow consumes repository, vcs, and zipfile source resolution contracts: local path vs URL vs archive, cache reuse, password prompting, and cleanup ownership.",
        "evidence_paths": [
            "cookiecutter/repository.py",
            "cookiecutter/vcs.py",
            "cookiecutter/zipfile.py",
            "cookiecutter/main.py",
            "tests/repository/test_is_repo_url.py",
            "tests/vcs/test_identify_repo.py",
            "tests/zipfile/test_unzip.py",
            "tests/test_main.py",
        ],
        "producer_subproblem": "repository_source_layer",
        "schema_version": "0.3",
    },
    {
        "consumer_subproblem": "orchestration_layer",
        "dependency_type": "integration",
        "description": "The top-level workflow consumes generation output, project directory, undefined-variable behavior, overwrite/skip semantics, and hook cleanup behavior.",
        "evidence_paths": [
            "cookiecutter/generate.py",
            "cookiecutter/hooks.py",
            "cookiecutter/environment.py",
            "cookiecutter/main.py",
            "tests/test_generate_files.py",
            "tests/test_generate_hooks.py",
            "tests/test_main.py",
        ],
        "producer_subproblem": "generation_hook_layer",
        "schema_version": "0.3",
    },
]
NATURAL_SUBPROBLEMS = {
    "config_prompt_layer": [
        "cookiecutter/config.py",
        "cookiecutter/prompt.py",
        "cookiecutter/replay.py",
        "tests/test_get_config.py",
        "tests/test_generate_context.py",
        "tests/test_prompt.py",
        "tests/test_read_user_variable.py",
        "tests/test_read_user_choice.py",
        "tests/test_read_user_yes_no.py",
    ],
    "repository_source_layer": [
        "cookiecutter/repository.py",
        "cookiecutter/vcs.py",
        "cookiecutter/zipfile.py",
        "tests/repository/test_is_repo_url.py",
        "tests/repository/test_repository_has_cookiecutter_json.py",
        "tests/repository/test_determine_repository_should_use_local_repo.py",
        "tests/vcs/test_identify_repo.py",
        "tests/vcs/test_is_vcs_installed.py",
        "tests/zipfile/test_unzip.py",
    ],
    "generation_hook_layer": [
        "cookiecutter/environment.py",
        "cookiecutter/extensions.py",
        "cookiecutter/find.py",
        "cookiecutter/generate.py",
        "cookiecutter/hooks.py",
        "cookiecutter/utils.py",
        "tests/test_find.py",
        "tests/test_generate_file.py",
        "tests/test_generate_files.py",
        "tests/test_generate_hooks.py",
        "tests/test_hooks.py",
        "tests/test_pre_prompt_hooks.py",
    ],
    "orchestration_layer": [
        "cookiecutter/cli.py",
        "cookiecutter/log.py",
        "cookiecutter/main.py",
        "tests/test_main.py",
    ],
}


def assignment(
    agent_id: str,
    role: str,
    subproblem_id: str,
    writable_paths: list[str],
    tests: list[str],
) -> dict:
    return {
        "agent_id": agent_id,
        "primary_test_targets": tests,
        "role": role,
        "schema_version": "0.3",
        "subproblem_id": subproblem_id,
        "writable_paths": writable_paths,
    }


ASSIGNMENTS = [
    assignment(
        "config_prompt_agent",
        "configuration, replay, prompt rendering, choice, yes/no, and no-input specialist",
        "config_prompt_layer",
        [
            "cookiecutter/config.py",
            "cookiecutter/prompt.py",
            "cookiecutter/replay.py",
        ],
        [
            "tests/test_get_config.py",
            "tests/test_generate_context.py::test_generate_context",
            "tests/test_prompt.py::TestRenderVariable::test_convert_to_str",
            "tests/test_read_user_choice.py",
        ],
    ),
    assignment(
        "source_agent",
        "repository URL/path/archive, vcs identification, clone/cache, and zip extraction specialist",
        "repository_source_layer",
        [
            "cookiecutter/repository.py",
            "cookiecutter/vcs.py",
            "cookiecutter/zipfile.py",
        ],
        [
            "tests/repository/test_is_repo_url.py",
            "tests/repository/test_repository_has_cookiecutter_json.py",
            "tests/vcs/test_identify_repo.py",
            "tests/zipfile/test_unzip.py",
        ],
    ),
    assignment(
        "generation_agent",
        "Jinja environment, template discovery, file rendering, overwrite, and hook execution specialist",
        "generation_hook_layer",
        [
            "cookiecutter/environment.py",
            "cookiecutter/extensions.py",
            "cookiecutter/find.py",
            "cookiecutter/generate.py",
            "cookiecutter/hooks.py",
            "cookiecutter/utils.py",
        ],
        [
            "tests/test_find.py",
            "tests/test_generate_file.py",
            "tests/test_generate_files.py",
            "tests/test_generate_hooks.py",
            "tests/test_hooks.py",
        ],
    ),
    assignment(
        "orchestration_agent",
        "top-level cookiecutter workflow, CLI handoff, main orchestration, and logging specialist",
        "orchestration_layer",
        [
            "cookiecutter/cli.py",
            "cookiecutter/log.py",
            "cookiecutter/main.py",
        ],
        [
            "tests/test_main.py",
        ],
    ),
]


def scenario(
    mode: str,
    communication: str,
    concurrent: bool,
    profile: str,
    integration: str,
    delivery: str,
) -> dict:
    assignments = ASSIGNMENTS
    agent_count = 4
    if mode == "iterative_single":
        assignments = [
            assignment(
                "integrator",
                "iterative full-task coding agent",
                "full_task",
                PUBLIC_MODULES,
                TEST_TARGETS,
            )
        ]
        agent_count = 1
    return {
        "agent_count": agent_count,
        "assignments": assignments,
        "communication_condition": communication,
        "concurrent_execution": concurrent,
        "dependency_annotations": DEPENDENCIES,
        "execution_mode": mode,
        "information_profile": profile,
        "integration_policy": integration,
        "message_delivery_policy": delivery,
        "scenario_id": f"commit0-cookiecutter.{mode.replace('_', '-')}.v0.3",
        "schema_version": "0.3",
        "shared_agent_scaffold": "iterative-inspect-edit-test-repair",
        "step_budget_per_agent": 34,
        "task_id": TASK_ID,
        "test_budget_per_agent": 12,
        "token_budget_per_agent": 85000,
        "wall_clock_budget_seconds": 3600,
    }


def task_record() -> dict:
    return {
        "annotation_provenance": [],
        "candidate_evidence_file": CANDIDATE_EVIDENCE,
        "dependency_annotations": DEPENDENCIES,
        "evaluator_command": EVALUATOR_COMMAND,
        "inclusion_decision": None,
        "natural_subproblems": NATURAL_SUBPROBLEMS,
        "notes": [
            "Task source and tests are unchanged; no bootstrap overlay is configured.",
            "Candidate screening labeled this task weak_or_unclear because the full raw suite had collection/import risk and many implicated modules.",
            "The v0.3 scoped evaluator avoids three Click-version-sensitive prompt tests but keeps repository, config, prompt, generation, hook, zip, vcs, and main workflow probes.",
            "The proposed label is a draft curation decision and not a final independent annotation.",
        ],
        "problem_statement": (
            "Restore the scoped Cookiecutter behavior exercised by the public Commit0 tests without modifying the tests.\n\n"
            "The config/prompt layer must load user configuration, merge defaults, generate context from cookiecutter.json, render variables, and handle choices and yes/no prompts. "
            "The repository source layer must classify local paths, repository URLs, and zip archives, expand abbreviations, identify VCS types, and locate or unpack template repositories. "
            "The generation/hook layer must construct Jinja environments, discover templates, render files and directories, preserve overwrite/skip semantics, and run pre/post hooks with cleanup behavior. "
            "The orchestration layer must compose those contracts in the top-level cookiecutter workflow.\n\n"
            "The initial benchmark source is the stripped Commit0-style ref origin/commit0_combined. No answer-providing bootstrap overlay is used."
        ),
        "proposed_parallelizability_label": "partially_parallelizable",
        "publicly_implicated_modules": PUBLIC_MODULES,
        "qualification_label": None,
        "qualification_status": "pending_independent_annotation",
        "quality_evidence_file": "manifests/pilot/v0.3/quality/commit0_cookiecutter.json",
        "repository": "commit0/cookiecutter",
        "schema_version": "0.3",
        "source_materialization": (
            f"git archive of the stripped Commit0-style cookiecutter ref {BASE_REF} at {STRIPPED_SHA}. "
            "No bootstrap overlay is configured."
        ),
        "task_id": TASK_ID,
        "task_source": "Commit0",
        "test_targets": TEST_TARGETS,
        "upstream_version": STRIPPED_SHA,
    }


def scenario_record() -> dict:
    return {
        "scenarios": [
            scenario(
                "iterative_single",
                "not_applicable",
                False,
                "complete-task",
                "Agent submits its final workspace.",
                "No inter-agent messages.",
            ),
            scenario(
                "serial_specialists",
                "completed_artifact_handoff",
                False,
                "private-workspace",
                "Apply config/prompt and repository source artifacts before generation and top-level workflow validation.",
                "Specialists run with barrier synchronization. Orchestration receives completed config, source, and generation artifacts before final validation.",
            ),
            scenario(
                "async_private",
                "none_in_flight",
                True,
                "private-workspace",
                "Integrate independently produced specialist artifacts at the end, then run dependency probes and the scoped evaluator.",
                "Agents work concurrently without messages while orchestration and generation assumptions may become stale.",
            ),
            scenario(
                "async_message",
                "structured_message_and_artifact",
                True,
                "private-workspace",
                "Integrate independently produced specialist artifacts after asynchronous handoffs, then run dependency probes and the scoped evaluator.",
                "Agents may send artifact summaries asynchronously; downstream workers are not guaranteed to see the newest config, repository, or generation contract before acting.",
            ),
        ],
        "schema_version": "0.3",
        "task_id": TASK_ID,
    }


def quality_record() -> dict:
    return {
        "coordination_structure_tags": [
            "interface_dependency",
            "shared_abstraction",
            "control",
        ],
        "environment_requirements": [
            "Python 3.10.12",
            "pytest==9.0.3",
            "pytest-mock==3.15.1",
            "binaryornot==0.6.0",
            "python-slugify==8.0.4",
            "arrow==1.4.0",
            "click 8.x, Jinja2, PyYAML, requests, rich",
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 with explicit -p pytest_mock",
            "Run from the repository root with PYTHONPATH=.",
        ],
        "evaluation_snapshots": [
            {
                "collected": 202,
                "command": EVALUATOR_COMMAND,
                "dependency_versions": {
                    "arrow": "1.4.0",
                    "binaryornot": "0.6.0",
                    "pytest": "9.0.3",
                    "pytest-mock": "3.15.1",
                    "python-slugify": "8.0.4",
                },
                "duration_seconds": 2.52,
                "errors": 23,
                "evidence_scope": "public_initial_state",
                "failed": 169,
                "notes": [
                    "Verified from a git archive of origin/commit0_combined without bootstrap overlays.",
                    "The scoped evaluator collected and executed; failures are caused by unfinished config, prompt, repository, vcs, zip, generate, hook, and main workflow behavior.",
                    "Three Click-version-sensitive human-choice prompt tests are deselected in both initial and complete snapshots.",
                ],
                "passed": 6,
                "python_version": "3.10.12",
                "return_code": 1,
                "schema_version": "0.3",
                "skipped": 4,
                "snapshot_id": "curated_commit0_initial_cookiecutter_workflow_evaluator",
                "source_ref": f"{BASE_REF}:{STRIPPED_SHA}",
            },
            {
                "collected": 216,
                "command": EVALUATOR_COMMAND,
                "dependency_versions": {
                    "arrow": "1.4.0",
                    "binaryornot": "0.6.0",
                    "pytest": "9.0.3",
                    "pytest-mock": "3.15.1",
                    "python-slugify": "8.0.4",
                },
                "duration_seconds": 1.52,
                "errors": 0,
                "evidence_scope": "evaluator_sanity_only",
                "failed": 0,
                "notes": [
                    "The complete main/commit0 ref passes the same scoped evaluator in the same environment.",
                    "The complete ref is evaluator validation only and must not define decomposition, prompts, or agent-visible evidence.",
                    "Three Click-version-sensitive prompt tests are intentionally deselected.",
                ],
                "passed": 212,
                "python_version": "3.10.12",
                "return_code": 0,
                "schema_version": "0.3",
                "skipped": 4,
                "snapshot_id": "complete_commit0_cookiecutter_workflow_evaluator_sanity",
                "source_ref": f"main:{COMPLETE_SHA}",
            },
        ],
        "known_limitations": [
            "The candidate screening record is weak_or_unclear because Cookiecutter has a broad module surface and full-suite environment sensitivity.",
            "The evaluator excludes three Click-version-sensitive human-choice prompt tests that fail on the local Click version even on the complete ref.",
            "The evaluator is scoped to public tests covering config, prompt, source resolution, VCS, zip, generation, hooks, and top-level workflow behavior.",
            "No bootstrap overlay is configured; any future overlay would require checksum and apply-check validation.",
            "Single-agent and multi-agent model results are evaluation outputs to report, not dataset qualification gates.",
        ],
        "public_statement_sources": [
            "README.md@origin/commit0_combined",
            "cookiecutter/*.py@origin/commit0_combined",
            "tests/test_*.py@origin/commit0_combined",
            "tests/repository/test_*.py@origin/commit0_combined",
            "tests/vcs/test_*.py@origin/commit0_combined",
            "tests/zipfile/test_*.py@origin/commit0_combined",
            CANDIDATE_EVIDENCE,
        ],
        "quality_status": "qualification_ready",
        "remaining_gates": [
            "two independent human inclusion/exclusion annotations",
            "human review of weak_or_unclear screening risk and scoped evaluator exclusions",
        ],
        "schema_version": "0.3",
        "structure_rationale": (
            "Cookiecutter exposes public-test-observable async dependencies from config/prompt contracts and repository source resolution into the top-level workflow, and from generation/hook behavior into project creation cleanup and replay behavior. "
            "An asynchronous orchestration agent can write against stale context shapes, repo_dir cleanup ownership, hook failure semantics, or generation output contracts even when final patches merge cleanly."
        ),
        "task_id": TASK_ID,
        "test_groups": [
            {
                "command": EVALUATOR_COMMAND[:8] + ["tests/test_get_config.py", "tests/test_prompt.py"],
                "description": "Config loading, context generation, prompt rendering, choices, and no-input behavior.",
                "group_id": "config_prompt_local",
                "owner_subproblem": "config_prompt_layer",
                "prerequisites": [],
                "purpose": "specialist_local",
                "schema_version": "0.3",
            },
            {
                "command": EVALUATOR_COMMAND[:8]
                + [
                    "tests/repository/test_is_repo_url.py",
                    "tests/repository/test_repository_has_cookiecutter_json.py",
                    "tests/vcs/test_identify_repo.py",
                    "tests/zipfile/test_unzip.py",
                ],
                "description": "Repository URL/path/archive, VCS, and zip source resolution behavior.",
                "group_id": "repository_source_local",
                "owner_subproblem": "repository_source_layer",
                "prerequisites": [],
                "purpose": "specialist_local",
                "schema_version": "0.3",
            },
            {
                "command": EVALUATOR_COMMAND[:8]
                + [
                    "tests/test_find.py",
                    "tests/test_generate_file.py",
                    "tests/test_generate_files.py",
                    "tests/test_generate_hooks.py",
                    "tests/test_hooks.py",
                ],
                "description": "Template discovery, Jinja environment, file rendering, overwrite semantics, and hook execution behavior.",
                "group_id": "generation_hook_local",
                "owner_subproblem": "generation_hook_layer",
                "prerequisites": [],
                "purpose": "specialist_local",
                "schema_version": "0.3",
            },
            {
                "command": EVALUATOR_COMMAND[:8] + ["tests/test_main.py"],
                "description": "Top-level cookiecutter workflow consuming config, repository, replay, generation, and hook contracts.",
                "group_id": "orchestration_local",
                "owner_subproblem": "orchestration_layer",
                "prerequisites": [],
                "purpose": "specialist_local",
                "schema_version": "0.3",
            },
            {
                "command": EVALUATOR_COMMAND[:8]
                + [
                    "tests/test_generate_context.py::test_generate_context",
                    "tests/repository/test_determine_repository_should_use_local_repo.py::test_finds_local_repo",
                    "tests/test_generate_files.py::test_generate_files",
                    "tests/test_main.py::test_original_cookiecutter_options_preserved_in__cookiecutter",
                ],
                "description": "Integrated workflow after config, source resolution, generation, and orchestration contracts are combined.",
                "group_id": "workflow_cross_contract",
                "owner_subproblem": None,
                "prerequisites": [
                    "config_prompt_layer artifact is integrated",
                    "repository_source_layer artifact is integrated",
                    "generation_hook_layer artifact is integrated",
                    "orchestration_layer artifact is integrated",
                ],
                "purpose": "cross_subproblem",
                "schema_version": "0.3",
            },
            {
                "command": EVALUATOR_COMMAND,
                "description": "Full scoped Cookiecutter workflow evaluator.",
                "group_id": "full_scoped_evaluator",
                "owner_subproblem": None,
                "prerequisites": [
                    "config_prompt_layer artifact is integrated",
                    "repository_source_layer artifact is integrated",
                    "generation_hook_layer artifact is integrated",
                    "orchestration_layer artifact is integrated",
                ],
                "purpose": "full_evaluator",
                "schema_version": "0.3",
            },
        ],
    }


def metrics_record() -> dict:
    dependency_points = [
        {
            "consumer_agent": "orchestration_agent",
            "consumer_files": ["cookiecutter/main.py", "cookiecutter/cli.py"],
            "consumer_subproblem": "orchestration_layer",
            "contract_summary": "Configuration, replay, and prompt code must provide stable context shape, default merging, no_input, choices, and extra_context behavior consumed by the top-level workflow.",
            "dependency_id": "cookiecutter.config_prompt_to_main.context_contract",
            "dependency_type": "shared_state_contract",
            "downstream_probe_tests": [
                "tests/test_main.py::test_original_cookiecutter_options_preserved_in__cookiecutter",
                "tests/test_main.py::test_replay_load_template_name",
            ],
            "integrated_probe_tests": [
                "tests/test_get_config.py::test_get_config",
                "tests/test_generate_context.py::test_generate_context",
                "tests/test_prompt.py::TestRenderVariable::test_convert_to_str",
                "tests/test_main.py::test_original_cookiecutter_options_preserved_in__cookiecutter",
            ],
            "metrics_enabled": ["ADPR", "DRS", "CAIL", "SAD"],
            "primary_paper_probe": True,
            "producer_agent": "config_prompt_agent",
            "producer_files": [
                "cookiecutter/config.py",
                "cookiecutter/prompt.py",
                "cookiecutter/replay.py",
            ],
            "producer_subproblem": "config_prompt_layer",
            "resolution_criteria": "Resolved when config/context/prompt probes and main workflow context preservation probes pass in the integrated workspace.",
            "stale_failure_mode": "The orchestration agent may preserve, replay, or pass context using stale assumptions about config defaults, extra_context overwrites, choices, or no_input prompt behavior.",
            "upstream_probe_tests": [
                "tests/test_get_config.py::test_get_config",
                "tests/test_generate_context.py::test_generate_context",
                "tests/test_prompt.py::TestRenderVariable::test_convert_to_str",
            ],
        },
        {
            "consumer_agent": "orchestration_agent",
            "consumer_files": ["cookiecutter/main.py"],
            "consumer_subproblem": "orchestration_layer",
            "contract_summary": "Repository, VCS, and zipfile source resolution must return stable repo_dir, cleanup, URL/archive classification, and cache reuse semantics consumed by cookiecutter().",
            "dependency_id": "cookiecutter.source_to_main.repo_dir_contract",
            "dependency_type": "interface_dependency",
            "downstream_probe_tests": [
                "tests/test_main.py::test_replay_dump_template_name",
                "tests/test_main.py::test_custom_replay_file",
            ],
            "integrated_probe_tests": [
                "tests/repository/test_is_repo_url.py::test_is_repo_url_for_remote_urls",
                "tests/repository/test_determine_repository_should_use_local_repo.py::test_finds_local_repo",
                "tests/vcs/test_identify_repo.py::test_identify_known_repo",
                "tests/zipfile/test_unzip.py::test_unzip_local_file",
                "tests/test_main.py::test_custom_replay_file",
            ],
            "metrics_enabled": ["ADPR", "DRS", "CAIL", "SAD"],
            "producer_agent": "source_agent",
            "producer_files": [
                "cookiecutter/repository.py",
                "cookiecutter/vcs.py",
                "cookiecutter/zipfile.py",
            ],
            "producer_subproblem": "repository_source_layer",
            "resolution_criteria": "Resolved when source resolution probes and top-level workflow probes pass after integration.",
            "stale_failure_mode": "The orchestration agent may use stale assumptions about whether a source path must be cloned, unzipped, reused, prompted for deletion, or cleaned up.",
            "upstream_probe_tests": [
                "tests/repository/test_is_repo_url.py::test_is_repo_url_for_remote_urls",
                "tests/repository/test_repository_has_cookiecutter_json.py::test_valid_repository",
                "tests/vcs/test_identify_repo.py::test_identify_known_repo",
                "tests/zipfile/test_unzip.py::test_unzip_local_file",
            ],
        },
        {
            "consumer_agent": "orchestration_agent",
            "consumer_files": ["cookiecutter/main.py"],
            "consumer_subproblem": "orchestration_layer",
            "contract_summary": "Generation and hooks must provide stable project directory creation, overwrite/skip behavior, hook execution, failure cleanup, and undefined-variable semantics consumed by the workflow.",
            "dependency_id": "cookiecutter.generate_hooks_to_main.project_contract",
            "dependency_type": "integration_contract",
            "downstream_probe_tests": [
                "tests/test_main.py::test_original_cookiecutter_options_preserved_in__cookiecutter",
                "tests/test_main.py::test_replay_dump_template_name",
            ],
            "integrated_probe_tests": [
                "tests/test_find.py::test_find_template",
                "tests/test_generate_files.py::test_generate_files",
                "tests/test_generate_hooks.py::test_run_python_hooks",
                "tests/test_hooks.py::TestExternalHooks::test_run_hook",
                "tests/test_main.py::test_original_cookiecutter_options_preserved_in__cookiecutter",
            ],
            "metrics_enabled": ["ADPR", "DRS", "CAIL", "SAD"],
            "producer_agent": "generation_agent",
            "producer_files": [
                "cookiecutter/environment.py",
                "cookiecutter/find.py",
                "cookiecutter/generate.py",
                "cookiecutter/hooks.py",
                "cookiecutter/utils.py",
            ],
            "producer_subproblem": "generation_hook_layer",
            "resolution_criteria": "Resolved when template discovery, file generation, hook execution, and main workflow probes pass together.",
            "stale_failure_mode": "The orchestration agent may call generation or cleanup code using stale assumptions about generated project paths, hook failure behavior, overwrite flags, or undefined-variable exceptions.",
            "upstream_probe_tests": [
                "tests/test_find.py::test_find_template",
                "tests/test_generate_files.py::test_generate_files",
                "tests/test_generate_hooks.py::test_run_python_hooks",
                "tests/test_hooks.py::TestExternalHooks::test_run_hook",
            ],
        },
    ]
    return {
        "aggregate_metrics": {
            "ADPR_denominator": "All dependency_points unless a paper section explicitly reports primary_async_dependency_ids only.",
            "dependency_point_count": 3,
            "minimum_success_condition_for_task_level_async_dependency_resolution": "All primary_async_dependency_ids pass in the final integrated workspace.",
            "primary_async_dependency_ids": [
                item["dependency_id"] for item in dependency_points
            ],
            "primary_paper_dependency_id": "cookiecutter.config_prompt_to_main.context_contract",
        },
        "annotation_notes": [
            "The config_prompt_to_main dependency is the primary signal because top-level workflow behavior is sensitive to stale context, prompt, and replay contracts.",
            "The source_to_main dependency captures stale assumptions around local path, URL, VCS, zip, cache reuse, and cleanup behavior.",
            "The generate_hooks_to_main dependency captures stale assumptions around project directory creation, hook failure cleanup, and generation exceptions.",
            "These labels identify public test-observable contracts, not solution code.",
        ],
        "dependency_points": dependency_points,
        "evaluation_checkpoint_policy": {
            "checkpoint_record_fields": [
                "run_id",
                "scenario_id",
                "checkpoint_id",
                "logical_iteration",
                "agent_id",
                "visible_upstream_artifact_version",
                "integrated_workspace_version",
                "probe_test_results",
            ],
            "minimum_policy": "Run probe tests after each agent final artifact and after final integration.",
            "recommended_policy": "Run probe tests after every committed patch, every explicit artifact transfer, and final integration.",
        },
        "metric_annotation_id": "commit0-cookiecutter.async-metrics.v0.3",
        "metric_definitions": {
            "ADPR": {
                "definition": "Fraction of registered dependency_points whose required integrated_probe_tests pass in the final integrated workspace.",
                "name": "Async Dependency Pass Rate",
                "unit": "fraction",
            },
            "CAIL": {
                "definition": "downstream_resolution_step minus upstream_resolution_step when both probe groups have been evaluated.",
                "name": "Cross-Agent Integration Lag",
                "unit": "agent iteration or evaluation checkpoint",
            },
            "DRS": {
                "definition": "First recorded checkpoint at which all required integrated_probe_tests for a dependency point pass.",
                "name": "Dependency Resolution Step",
                "unit": "agent iteration or evaluation checkpoint",
            },
            "SAD": {
                "definition": "Interval during which a downstream worker acts on a contract assumption inconsistent with the latest upstream artifact.",
                "name": "Stale Assumption Duration",
                "unit": "agent iteration or event interval",
            },
        },
        "purpose": "Dependency-level labels for measuring whether asynchronous multi-agent coding resolves Cookiecutter config/prompt, source resolution, generation/hook, and main workflow contracts.",
        "schema_version": "0.3-async-metrics",
        "source_quality_record": "manifests/pilot/v0.3/quality/commit0_cookiecutter.json",
        "source_task_record": "manifests/pilot/v0.3/tasks/commit0_cookiecutter.json",
        "task_id": TASK_ID,
    }


def annotation_form(annotator_id: str) -> dict:
    return {
        "allowed_labels": [
            "parallelizable",
            "partially_parallelizable",
            "effectively_serial",
        ],
        "annotator_id": annotator_id,
        "candidate_evidence_file": CANDIDATE_EVIDENCE,
        "exclusion_reason": None,
        "include": None,
        "independence_instructions": [
            "Use only public Commit0 evidence, the screening record, and the draft task record.",
            "Review the linked TaskQualityRecord, especially the weak_or_unclear screening label and scoped evaluator exclusions.",
            "Do not inspect reference branches, solution patches, or diffs.",
            "Do not consult the other annotator before submitting.",
            "Explicitly assess whether the config/prompt + repository source + generation/hooks + orchestration split is a natural AsyncCodeBench dependency rather than artificial file partitioning.",
            "Explicitly assess whether excluding the three Click-version-sensitive prompt tests is appropriate for this scoped workflow task.",
        ],
        "parallelizability_label": None,
        "rationale": None,
        "schema_version": "0.3",
        "task_id": TASK_ID,
        "task_record_file": "manifests/pilot/v0.3/tasks/commit0_cookiecutter.json",
    }


def adjudication_template() -> dict:
    return {
        "adjudicator_id": "independent_adjudicator",
        "annotator_ids": ["annotator_a", "annotator_b"],
        "exclusion_reason": None,
        "include": None,
        "parallelizability_label": None,
        "rationale": None,
        "schema_version": "0.3",
        "task_id": TASK_ID,
    }


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def update_curated_config() -> None:
    path = Path("configs/tasks/commit0_curated_tasks.v0.3.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["tasks"] = [task for task in payload["tasks"] if task["task_id"] != TASK_ID]
    payload["tasks"].append(
        {
            "task_id": TASK_ID,
            "repository": "cookiecutter",
            "base_ref": BASE_REF,
            "base_sha": STRIPPED_SHA,
            "overlays": [],
        }
    )
    write_json(path, payload)


def main() -> int:
    files = {
        Path("manifests/pilot/v0.3/tasks/commit0_cookiecutter.json"): task_record(),
        Path("manifests/pilot/v0.3/scenarios/commit0_cookiecutter.json"): scenario_record(),
        Path("manifests/pilot/v0.3/quality/commit0_cookiecutter.json"): quality_record(),
        Path("manifests/pilot/v0.3/metrics/commit0_cookiecutter_async_metrics.json"): metrics_record(),
        Path("manifests/annotations/commit0_v0.3/cookiecutter/annotator_a.json"): annotation_form("annotator_a"),
        Path("manifests/annotations/commit0_v0.3/cookiecutter/annotator_b.json"): annotation_form("annotator_b"),
        Path("manifests/annotations/commit0_v0.3/cookiecutter/adjudication.template.json"): adjudication_template(),
    }
    for path, payload in files.items():
        write_json(path, payload)
    update_curated_config()
    for path in files:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload["task_id"] != TASK_ID:
            raise ValueError(f"unexpected task_id in {path}: {payload['task_id']}")
    print(f"generated {TASK_ID} v0.3 manifest files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
