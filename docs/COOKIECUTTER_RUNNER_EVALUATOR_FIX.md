# Cookiecutter Runner And Evaluator Notes

This document records the runner/evaluator fixes needed for the
AsynCodeBench `commit0:cookiecutter` task. It is intended to prevent repeated
API-costly debugging by collaborators.

## Context

`cookiecutter` is an official AsynCodeBench v0.3 task. The runner command
still uses `--task commit0`, but the intended input is the curated
AsynCodeBench task source, not the raw Commit0 task.

Required environment convention:

```bash
cd /absolute/path/to/AsynCodeBench/reproductions/async-swe-agents
source scripts/env.sh

unset ASYNCODEBENCH_DISABLE_CURATED_TASK_SOURCE
unset ASYNCODEBENCH_DISABLE_CURATED_TASK_CONFIG
unset ASYNCODEBENCH_DISABLE_MANIFEST_EVALUATOR
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
AsynCodeBench task manifest evaluator command. For `cookiecutter`, the correct
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
  "final_evaluator_source": "asyncodebench_manifest",
  "final_test_cmd": "python -m pytest -q -p pytest_mock -o addopts="
}
```

If `final_evaluator_source` is not `asyncodebench_manifest`, do not treat the
run as official.

### 2. Missing curated Python dependencies

Symptom:

`pytest_mock` was unavailable in some integrated workspaces.

Root cause:

The curated task config did not list all Python dependencies needed by
`cookiecutter`'s AsynCodeBench evaluator.

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

Use these commands for the local `Qwen/Qwen3.6-27B` single-GPU profile. Start
vLLM first, then run the agent protocols strictly one at a time. With
`--max-num-seqs 2`, the server can schedule at least two in-flight sequences;
still do not run separate task protocols in parallel because they would compete
for the same GPU scheduler and OpenHands host port. See
`docs/LOCAL_VLLM_EXPERIMENT_RUNBOOK.md` for the authoritative serving profile.

First load the runner environment:

```bash
cd /absolute/path/to/AsynCodeBench/reproductions/async-swe-agents

export ENV_FILE="$PWD/.env.qwen36-27"
source scripts/env.sh

unset ASYNCODEBENCH_DISABLE_CURATED_TASK_SOURCE
unset ASYNCODEBENCH_DISABLE_CURATED_TASK_CONFIG
unset ASYNCODEBENCH_DISABLE_MANIFEST_EVALUATOR

export LLM_BASE_URL=http://127.0.0.1:8006/v1
export LLM_MODEL=openai/Qwen/Qwen3.6-27B
export LLM_SUBAGENT_MODEL=openai/Qwen/Qwen3.6-27B
export LLM_MAX_OUTPUT_TOKENS=4096
export LLM_TIMEOUT=600
export LLM_NUM_RETRIES=2
export LLM_EXTRA_BODY_JSON='{"chat_template_kwargs":{"enable_thinking":true}}'
export LLM_TEMPERATURE=0.6
export LLM_TOP_P=0.95
export LLM_TOP_K=20

curl -s "$LLM_BASE_URL/models"

TASK=cookiecutter
MODEL_TAG=qwen36-27
RUN_VERSION=curated_thinking_gpu1_65k_o4096_v01
MAX_SUBAGENTS=4
BASE_OUT=outputs/repro_commit0/${TASK}
```

The host ports below are intentionally distinct. The protocols are still meant
to run sequentially; separate ports make interrupted container cleanup easier to
reason about.

### Single agent

```bash
ASYNCODEBENCH_WORKSPACE_DOCKER_NETWORK=host \
ASYNCODEBENCH_WORKSPACE_HOST_PORT=8020 \
MAX_ITERATIONS=30 \
OUTPUT_DIR="${BASE_OUT}/${MODEL_TAG}_single_i30_${RUN_VERSION}" \
scripts/run_commit0_single_env.sh "$TASK"
```

### Serial specialists

```bash
ASYNCODEBENCH_WORKSPACE_DOCKER_NETWORK=host \
ASYNCODEBENCH_WORKSPACE_HOST_PORT=8021 \
MAX_SUBAGENTS=$MAX_SUBAGENTS \
SUB_ITERATIONS=30 \
OUTPUT_DIR="${BASE_OUT}/${MODEL_TAG}_serial_4agents_s30_${RUN_VERSION}" \
scripts/run_commit0_serial_env.sh "$TASK"
```

### Async private

```bash
ASYNCODEBENCH_WORKSPACE_DOCKER_NETWORK=host \
ASYNCODEBENCH_WORKSPACE_HOST_PORT=8022 \
MAX_SUBAGENTS=$MAX_SUBAGENTS \
SUB_ITERATIONS=30 \
OUTPUT_DIR="${BASE_OUT}/${MODEL_TAG}_async_private_4agents_s30_${RUN_VERSION}" \
scripts/run_commit0_async_private_env.sh "$TASK"
```

### CAID multi-agent

```bash
ASYNCODEBENCH_WORKSPACE_DOCKER_NETWORK=host \
ASYNCODEBENCH_WORKSPACE_HOST_PORT=8023 \
MAX_ITERATIONS=30 \
MAX_SUBAGENTS=$MAX_SUBAGENTS \
SUB_ITERATIONS=30 \
ROUNDS_OF_CHAT=2 \
OUTPUT_DIR="${BASE_OUT}/${MODEL_TAG}_caid_multi_4agents_m30_s30_${RUN_VERSION}" \
scripts/run_commit0_multi_env.sh "$TASK"
```

## Process Metrics Generation

Run from the repository root:

```bash
cd /absolute/path/to/AsynCodeBench

METRICS=manifests/pilot/v0.3/metrics/commit0_cookiecutter_async_metrics.json
MODEL_TAG=qwen36-27
MODEL_ID=openai/Qwen/Qwen3.6-27B
RUN_VERSION=curated_thinking_gpu1_65k_o4096_v01
BASE=reproductions/async-swe-agents/outputs/repro_commit0/cookiecutter

SINGLE=${BASE}/${MODEL_TAG}_single_i30_${RUN_VERSION}
SERIAL=${BASE}/${MODEL_TAG}_serial_4agents_s30_${RUN_VERSION}
ASYNC=${BASE}/${MODEL_TAG}_async_private_4agents_s30_${RUN_VERSION}
CAID=${BASE}/${MODEL_TAG}_caid_multi_4agents_m30_s30_${RUN_VERSION}

python3.10 scripts/analyze_run_process_metrics.py --run-dir "$SINGLE" --metrics "$METRICS" --output "$SINGLE/process_metrics_summary.json" --print-summary
python3.10 scripts/analyze_run_process_metrics.py --run-dir "$SERIAL" --metrics "$METRICS" --baseline-run-dir "$SINGLE" --output "$SERIAL/process_metrics_summary.json" --print-summary
python3.10 scripts/analyze_run_process_metrics.py --run-dir "$ASYNC" --metrics "$METRICS" --baseline-run-dir "$SINGLE" --output "$ASYNC/process_metrics_summary.json" --print-summary
python3.10 scripts/analyze_run_process_metrics.py --run-dir "$CAID" --metrics "$METRICS" --baseline-run-dir "$SINGLE" --output "$CAID/process_metrics_summary.json" --print-summary
```

Then generate the standard three artifacts:

```bash
python3.10 scripts/summarize_model_task_runs.py \
  --task cookiecutter \
  --model-tag "$MODEL_TAG" \
  --model "$MODEL_ID" \
  --runner-adapter native-strict-checkpoints \
  --metrics "$METRICS" \
  --output-dir "reproductions/async-swe-agents/outputs/${MODEL_TAG}" \
  --run single="$SINGLE" \
  --run serial_specialists="$SERIAL" \
  --run async_private="$ASYNC" \
  --run CAID_multi="$CAID"
```

Expected generated files:

```text
reproductions/async-swe-agents/outputs/qwen36-27/cookiecutter.md
reproductions/async-swe-agents/outputs/qwen36-27/cookiecutter_qwen36-27_metrics_table.csv
reproductions/async-swe-agents/outputs/qwen36-27/cookiecutter_qwen36-27_artifact_index.json
```

## Acceptance Checklist

Before using a `cookiecutter` run in the paper table, check:

- The run directory has exactly one `run_*.log`.
- `report.json` contains `final_evaluator_source:
  asyncodebench_manifest`.
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
AsynCodeBench dependency metrics explain the failure more precisely: all three
annotated cross-agent dependency contracts remain unresolved in the integrated
workspace, while the single-agent baseline resolves all three.
