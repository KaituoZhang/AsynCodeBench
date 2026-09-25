# Scripts

This directory contains the supported command-line tooling for the public
AsynCodeBench release. Reusable implementation logic lives under
`src/asyncodebench/`; scripts primarily validate inputs and invoke that logic.

## Installation and runtime integrity

- `setup_evaluation.sh` installs the benchmark and native agent harness.
- `materialize_openhands_sdk.py`, `check_openhands_runtime_consistency.py`, and
  `smoke_openhands_event_roundtrip.py` pin and validate the OpenHands runtime.
- `check_repository_hygiene.py` and `check_markdown_links.py` enforce public
  repository hygiene.

## Release and task construction

- `build_*_v03_data.py` reproduce the released records for the 15
  Commit0-derived tasks.
- `build_release_index.py` and `build_v04_release_index.py` assemble the frozen
  release indexes.
- `qualification_*`, `screen_commit0_async_candidates.py`, and the annotation
  utilities support the documented task qualification workflow.
- `materialize_commit0_repositories.py` and
  `materialize_contract_test_repositories.py` reconstruct pinned public source
  inputs used by builders and contract tests.

## PR-hard tasks and task images

`prepare_pr_hard_runtime.py` performs checksum-validated source and toolchain
materialization for compiler/IR tasks 20018, 20073, 20107, and 20153. The other
`*_pr_hard_*` tools prepare, snapshot, validate, and distribute their immutable
task images. Generated source and environments remain under ignored cache
directories; only recipes, manifests, locks, and answer-free public overlays
are committed.

## Result validation and aggregation

- `analyze_run_process_metrics.py` generates the canonical per-run process and
  dependency metrics.
- `summarize_model_task_runs.py` creates per-task records across protocols.
- `aggregate_model_task_results.py` admits eligible bundles and creates
  model-level aggregates.

Legacy experiment-specific CSV patching and model-specific result scripts are
not part of the community tool surface.
