# Cookiecutter Runner And Evaluator Notes

This document records the runner/evaluator fixes needed for the
AsyncCodeBench `commit0:cookiecutter` task. It is intended to prevent repeated
API-costly debugging by collaborators.

## Context

`cookiecutter` is an official AsyncCodeBench v0.3 task. The runner command
still uses `--task commit0`, but the intended input is the curated
AsyncCodeBench task source, not the raw Commit0 task.

Required environment convention:

```bash
cd /home/kzhang42/AsyncCodeBench/reproductions/async-swe-agents
source scripts/env.sh

unset ASYNCCODEBENCH_DISABLE_CURATED_TASK_SOURCE
unset ASYNCCODEBENCH_DISABLE_CURATED_TASK_CONFIG
unset ASYNCCODEBENCH_DISABLE_MANIFEST_EVALUATOR
```

The official evaluator comes from:

```text
manifests/pilot/v0.3/tasks/commit0_cookiecutter.json
```

The metrics manifest comes from:

```text
manifests/pilot/v0.3/metrics/commit0_cookiecutter_async_metrics.json
```

## Problems We Hit

### 1. The runner ignored the task manifest evaluator command

Symptom:

```text
fixture 'mocker' not found
ImportError: Error importing plugin "pytest_mock": No module named 'pytest_mock'
```

Root cause:

The runner was using a generic Commit0 pytest command instead of the
AsyncCodeBench task manifest evaluator command. For `cookiecutter`, the correct
command includes `pytest_mock` and disables inherited addopts:

```bash
python -m pytest -q -p pytest_mock -o addopts=
```

Fix location:

```text
reproductions/async-swe-agents/tasks/commit0.py
```

Relevant implementation:

- `_task_manifest_path()`
- `_manifest_evaluator_command()`
- `_split_pytest_command()`
- `_resolve_evaluator()`
- `_curated_task_data()`

Expected final report metadata:

```json
{
  "final_evaluator_source": "asynccodebench_manifest",
  "final_test_cmd": "python -m pytest -q -p pytest_mock -o addopts="
}
```

If `final_evaluator_source` is not `asynccodebench_manifest`, do not treat the
run as official.

### 2. Missing curated Python dependencies

Symptom:

`pytest_mock` was unavailable in some integrated workspaces.

Root cause:

The curated task config did not list all Python dependencies needed by
`cookiecutter`'s AsyncCodeBench evaluator.

Fix location:

```text
configs/tasks/commit0_curated_tasks.v0.3.json
```

The `commit0:cookiecutter` record now includes:

```json
"python_dependencies": [
  "pytest-mock==3.15.1",
  "binaryornot==0.6.0",
  "python-slugify==8.0.4",
  "arrow==1.4.0"
]
```

### 3. Subagent worktrees generated unassigned test artifacts

Symptom:

Subagent recovery commits could accidentally pick up files such as:

```text
tests/test-hooks/
```

Root cause:

Some `cookiecutter` tests create fixture directories inside the repository.
If the runner stages all uncommitted files with `git add .`, these transient
test artifacts can be merged into the integrated workspace.

Fix location:

```text
reproductions/async-swe-agents/core/manager.py
```

Relevant implementation:

- `import shlex`
- `_split_assigned_file_paths()`
- `_is_under_assigned_path()`
- `commit_worktree_changes(..., allowed_file_paths=...)`

The recovery path now stages only files under the assigned writable paths.
This prevents unassigned test fixture directories from becoming model patches.

Expected log line when this protection is active:

```text
[Manager] Ignoring unassigned uncommitted files in worktree: ['tests/test-hooks/']
```

### 4. Cookiecutter hook tests can leave transient directories before final eval

Symptom:

Final pytest can report:

```text
FileExistsError: [Errno 17] File exists: 'tests/test-hooks'
```

Root cause:

`tests/test-hooks` is a test fixture directory produced by some hook-related
tests. It is not part of the model patch. If it survives into a later final
test invocation, hook tests can fail for the wrong reason.

Fix location:

```text
reproductions/async-swe-agents/tasks/commit0.py
```

Relevant implementation:

- `_clean_transient_test_artifacts()`
- called before final commit
- called again before final pytest

The cleanup is intentionally narrow and only applies when:

```python
self.config.repo_name == "cookiecutter"
```

It removes:

```text
tests/test-hooks
```

This does not change the model solution. It only prevents generated test
fixtures from contaminating final evaluation.

## Output Directory Rule

Never reuse an output directory after a crashed or interrupted run.

Bad example:

```text
gpt54mini_serial_4agents_s30_curated_v03
```

This directory had two run logs after a failed run was restarted in the same
location, which contaminated `dependency_probe_checkpoints.jsonl`.

Use a fresh versioned directory:

```text
gpt54mini_serial_4agents_s30_curated_v04
gpt54mini_async_private_4agents_s30_curated_v04
gpt54mini_caid_multi_4agents_m30_s30_curated_v04
```

Validity check:

```bash
ls -1 outputs/repro_commit0/cookiecutter/<RUN_DIR>/run_*.log
```

For a clean official run, there should be exactly one run log in each run
directory.

## Recommended Commands

Run from:

```bash
cd /home/kzhang42/AsyncCodeBench/reproductions/async-swe-agents
source scripts/env.sh

unset ASYNCCODEBENCH_DISABLE_CURATED_TASK_SOURCE
unset ASYNCCODEBENCH_DISABLE_CURATED_TASK_CONFIG
unset ASYNCCODEBENCH_DISABLE_MANIFEST_EVALUATOR
```

### Serial specialists

```bash
uv run python run_static_protocol.py \
  --task commit0 \
  --protocol serial_specialists \
  --repo cookiecutter \
  --model "$LLM_MODEL" \
  --max_subagents 4 \
  --sub_iterations 30 \
  --dataset_path "$COMMIT0_DATASET_PATH" \
  --output_dir outputs/repro_commit0/cookiecutter/gpt54mini_serial_4agents_s30_curated_v04
```

### Async private

```bash
uv run python run_static_protocol.py \
  --task commit0 \
  --protocol async_private \
  --repo cookiecutter \
  --model "$LLM_MODEL" \
  --max_subagents 4 \
  --sub_iterations 30 \
  --dataset_path "$COMMIT0_DATASET_PATH" \
  --output_dir outputs/repro_commit0/cookiecutter/gpt54mini_async_private_4agents_s30_curated_v04
```

### CAID multi-agent

```bash
MAX_ITERATIONS=30 MAX_SUBAGENTS=4 SUB_ITERATIONS=30 ROUNDS_OF_CHAT=2 \
OUTPUT_DIR=outputs/repro_commit0/cookiecutter/gpt54mini_caid_multi_4agents_m30_s30_curated_v04 \
scripts/run_commit0_multi_env.sh cookiecutter
```

## Process Metrics Generation

Run from the repository root:

```bash
cd /home/kzhang42/AsyncCodeBench

METRICS=manifests/pilot/v0.3/metrics/commit0_cookiecutter_async_metrics.json
SINGLE=reproductions/async-swe-agents/outputs/repro_commit0/cookiecutter/gpt54mini_single_i30_curated_v02
SERIAL=reproductions/async-swe-agents/outputs/repro_commit0/cookiecutter/gpt54mini_serial_4agents_s30_curated_v04
ASYNC=reproductions/async-swe-agents/outputs/repro_commit0/cookiecutter/gpt54mini_async_private_4agents_s30_curated_v04
CAID=reproductions/async-swe-agents/outputs/repro_commit0/cookiecutter/gpt54mini_caid_multi_4agents_m30_s30_curated_v04

python3 scripts/analyze_run_process_metrics.py --run-dir "$SINGLE" --metrics "$METRICS" --output "$SINGLE/process_metrics_summary.json" --print-summary
python3 scripts/analyze_run_process_metrics.py --run-dir "$SERIAL" --metrics "$METRICS" --baseline-run-dir "$SINGLE" --output "$SERIAL/process_metrics_summary.json" --print-summary
python3 scripts/analyze_run_process_metrics.py --run-dir "$ASYNC" --metrics "$METRICS" --baseline-run-dir "$SINGLE" --output "$ASYNC/process_metrics_summary.json" --print-summary
python3 scripts/analyze_run_process_metrics.py --run-dir "$CAID" --metrics "$METRICS" --baseline-run-dir "$SINGLE" --output "$CAID/process_metrics_summary.json" --print-summary
```

Then generate the standard three artifacts:

```bash
python3 scripts/summarize_model_task_runs.py \
  --task cookiecutter \
  --model-tag gpt-5.4-mini \
  --model openai/gpt-5.4-mini \
  --runner-adapter native-strict-checkpoints \
  --metrics "$METRICS" \
  --output-dir reproductions/async-swe-agents/outputs/gpt-5.4-mini \
  --run single="$SINGLE" \
  --run serial_specialists="$SERIAL" \
  --run async_private="$ASYNC" \
  --run CAID_multi="$CAID"
```

Expected generated files:

```text
reproductions/async-swe-agents/outputs/gpt-5.4-mini/cookiecutter.md
reproductions/async-swe-agents/outputs/gpt-5.4-mini/cookiecutter_gpt-5.4-mini_metrics_table.csv
reproductions/async-swe-agents/outputs/gpt-5.4-mini/cookiecutter_gpt-5.4-mini_artifact_index.json
```

## Acceptance Checklist

Before using a `cookiecutter` run in the paper table, check:

- The run directory has exactly one `run_*.log`.
- `report.json` contains `final_evaluator_source:
  asynccodebench_manifest`.
- `report.json` contains `final_test_cmd:
  python -m pytest -q -p pytest_mock -o addopts=`.
- `process_metrics_summary.json` exists.
- `dependency_probe_checkpoints.jsonl` has exactly one
  `final_integrated` checkpoint.
- `patch.diff` does not contain `diff --git a/tests`.
- The standard markdown, CSV, and artifact-index files have been regenerated.

## Current gpt-5.4-mini Cookiecutter Result

The clean `v04` run is usable as an official failure-case record.

Summary:

| Mode | Final tests | Final success | Final ADPR | Integrated dependencies |
| --- | ---: | --- | ---: | ---: |
| single | 198/202 | true | 1.0 | 3/3 |
| serial_specialists | 86/202 | false | 0.0 | 0/3 |
| async_private | 64/202 | false | 0.0 | 0/3 |
| CAID_multi | 85/202 | false | 0.0 | 0/3 |

Interpretation:

Traditional final tests show that all multi-agent protocols fail. The
AsyncCodeBench dependency metrics explain the failure more precisely: all three
annotated cross-agent dependency contracts remain unresolved in the integrated
workspace, while the single-agent baseline resolves all three.

