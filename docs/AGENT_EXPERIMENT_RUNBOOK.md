# AsyncCodeBench Agent Experiment Runbook

This document is the operational guide for running AsyncCodeBench agent
experiments. It explains how the runner uses AsyncCodeBench curated tasks rather
than raw Commit0 records, how to run the four protocol conditions, and what to
check before using a run in paper tables.

Use this with:

- `docs/COLLABORATOR_RUNBOOK.md` for repository setup.
- `docs/EVALUATION_METRICS.md` for metric definitions and post-run analysis.
- `docs/CODEX_ONBOARDING.md` when asking another Codex session to work on the
  repository.

## Core Principle

The executable runner still uses names such as `--task commit0` and
`run_commit0_*` because it reuses the Commit0 task interface. For official
AsyncCodeBench runs, the actual task input must come from AsyncCodeBench v0.3
curated artifacts:

```text
configs/tasks/commit0_curated_tasks.v0.3.json
manifests/pilot/v0.3/tasks/
manifests/pilot/v0.3/scenarios/
manifests/pilot/v0.3/metrics/
manifests/pilot/v0.3/quality/
data/overlays/commit0/
```

The runner should print:

```text
[AsyncCodeBench] Loaded curated v0.3 task record for <task>
[Commit0] Verified curated base SHA: <sha>
[Commit0] Applying <n> AsyncCodeBench bootstrap overlays
[Commit0] Using AsyncCodeBench scenario evaluator targets ...
```

If those lines are missing, stop the run before spending more API budget.

## Environment Setup

Start from the agent runner directory:

```bash
export REPO_ROOT="${REPO_ROOT:-$HOME/AsyncCodeBench}"
cd "$REPO_ROOT/reproductions/async-swe-agents"
```

Create one local env file per model or provider. Do not commit these files.

Example:

```bash
cp .env.example .env.gpt54mini
```

The env file must define:

```bash
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_API_KEY=YOUR_KEY
LLM_MODEL=openai/gpt-5.4-mini
LLM_SUBAGENT_MODEL=
COMMIT0_DATASET_PATH=$REPO_ROOT/data/external/commit0_combined
SDK_SOURCE_DIR=$REPO_ROOT/reproductions/software-agent-sdk
```

For a different model, create another env file, for example
`.env.deepseekv32` or `.env.claude46`, and change only `LLM_MODEL`,
`LLM_BASE_URL`, and `LLM_API_KEY` as needed.

Load the env:

```bash
export ENV_FILE="$PWD/.env.gpt54mini"
source scripts/env.sh
unset ASYNCCODEBENCH_DISABLE_CURATED_TASK_SOURCE
```

The `COMMIT0_DATASET_PATH` variable is still required by the inherited runner
API. For curated tasks, the runner should use the AsyncCodeBench curated record
first. The raw Commit0 dataset is only a fallback when curated loading is
disabled or no curated record exists.

Do not set this for official runs:

```bash
ASYNCCODEBENCH_DISABLE_CURATED_TASK_SOURCE=1
```

## Quick Task Dry Run

Before a full multi-agent run, perform dry runs for the static protocols. These
commands do not call the LLM and show the scenario assignments, writable paths,
test targets, base ref, and overlay count.

```bash
TASK=filesystem_spec
MAX_SUBAGENTS=3
SUB_ITERATIONS=2
```

```bash
uv run python run_static_protocol.py \
  --task commit0 \
  --protocol serial_specialists \
  --repo "$TASK" \
  --model "$LLM_MODEL" \
  --max_subagents "$MAX_SUBAGENTS" \
  --sub_iterations "$SUB_ITERATIONS" \
  --dataset_path "$COMMIT0_DATASET_PATH" \
  --output_dir "outputs/repro_commit0/${TASK}/smoke_serial_dryrun" \
  --dry_run
```

```bash
uv run python run_static_protocol.py \
  --task commit0 \
  --protocol async_private \
  --repo "$TASK" \
  --model "$LLM_MODEL" \
  --max_subagents "$MAX_SUBAGENTS" \
  --sub_iterations "$SUB_ITERATIONS" \
  --dataset_path "$COMMIT0_DATASET_PATH" \
  --output_dir "outputs/repro_commit0/${TASK}/smoke_async_private_dryrun" \
  --dry_run
```

Use the printed assignment count to set `MAX_SUBAGENTS`. For example,
`filesystem_spec` has three specialists: registry, utility/compression, and
core.

## Copy-Paste Experiment Template

Set these variables once per task/model/run version:

```bash
export REPO_ROOT="${REPO_ROOT:-$HOME/AsyncCodeBench}"
cd "$REPO_ROOT/reproductions/async-swe-agents"

export ENV_FILE="$PWD/.env.gpt54mini"
source scripts/env.sh
unset ASYNCCODEBENCH_DISABLE_CURATED_TASK_SOURCE

TASK=filesystem_spec
MODEL_TAG=gpt-5.4-mini
RUN_VERSION=v05

MAX_SUBAGENTS=3
SINGLE_ITERATIONS=30
SPECIALIST_ITERATIONS=30
CAID_MANAGER_ITERATIONS=40
CAID_SUB_ITERATIONS=50
ROUNDS_OF_CHAT=2
```

`MODEL_TAG` is only for filesystem paths and report names. Keep it
filesystem-safe; do not include `/`.

### 1. Single Agent

```bash
MAX_ITERATIONS="$SINGLE_ITERATIONS" \
OUTPUT_DIR="outputs/repro_commit0/${TASK}/${MODEL_TAG}_single_i${SINGLE_ITERATIONS}_curated_${RUN_VERSION}" \
scripts/run_commit0_single_env.sh "$TASK"
```

### 2. Serial Specialists

```bash
MAX_SUBAGENTS="$MAX_SUBAGENTS" SUB_ITERATIONS="$SPECIALIST_ITERATIONS" \
OUTPUT_DIR="outputs/repro_commit0/${TASK}/${MODEL_TAG}_serial_${MAX_SUBAGENTS}agents_s${SPECIALIST_ITERATIONS}_curated_${RUN_VERSION}" \
scripts/run_commit0_serial_env.sh "$TASK"
```

### 3. Async Private Specialists

```bash
MAX_SUBAGENTS="$MAX_SUBAGENTS" SUB_ITERATIONS="$SPECIALIST_ITERATIONS" \
OUTPUT_DIR="outputs/repro_commit0/${TASK}/${MODEL_TAG}_async_private_${MAX_SUBAGENTS}agents_s${SPECIALIST_ITERATIONS}_curated_${RUN_VERSION}" \
scripts/run_commit0_async_private_env.sh "$TASK"
```

### 4. CAID Multi-Agent

```bash
MAX_ITERATIONS="$CAID_MANAGER_ITERATIONS" \
MAX_SUBAGENTS="$MAX_SUBAGENTS" \
SUB_ITERATIONS="$CAID_SUB_ITERATIONS" \
ROUNDS_OF_CHAT="$ROUNDS_OF_CHAT" \
OUTPUT_DIR="outputs/repro_commit0/${TASK}/${MODEL_TAG}_caid_multi_${MAX_SUBAGENTS}agents_m${CAID_MANAGER_ITERATIONS}_s${CAID_SUB_ITERATIONS}_curated_${RUN_VERSION}" \
scripts/run_commit0_multi_env.sh "$TASK"
```

Run protocols sequentially unless you have confirmed enough API budget, Docker
capacity, and provider rate limits. Sequential runs are easier to debug and
avoid mixed logs.

## Expected Output Files

Each completed run directory should contain:

```text
cost.json
dependency_probe_checkpoints.jsonl
<task>_pytest_exit_code.txt
<task>_test_output.txt
outputs.jsonl
report.json
runtime.txt
run_*.log
```

Multi-agent runs should also contain:

```text
delegations.json
patch.diff
protocol.json        # static protocols only
agent_events/
```

The most important files are:

- `report.json`: final pytest summary and evaluator targets.
- `<task>_test_output.txt`: final pytest text output.
- `dependency_probe_checkpoints.jsonl`: strict dependency checkpoints for ADPR,
  DRS, and CAIL.
- `cost.json`: token, cost, and wall-clock metadata.
- `delegations.json`: who was assigned what.
- `patch.diff`: final patch applied by the protocol.

## Uploaded Example

The repository includes a checked-in summarized example for `cachetools` with
`gpt-5.4-mini`. Use it as the format reference for collaborator-side reports:

```text
reproductions/async-swe-agents/outputs/gpt-5.4-mini/cachetools.md
reproductions/async-swe-agents/outputs/gpt-5.4-mini/cachetools_gpt-5.4-mini_metrics_table.csv
reproductions/async-swe-agents/outputs/gpt-5.4-mini/cachetools_gpt-5.4-mini_artifact_index.json
```

The Markdown report shows the paper-facing summary table plus ADPR, DRS, CAIL,
SAD, cost, runtime, and artifact diagnostics. The CSV is the machine-readable
table used for later aggregation. The artifact index records the raw run
directories used to generate the report.

Raw run directories such as `outputs/repro_commit0/<task>/<run_id>/` are not
generally committed by default because they can be large and may contain verbose
model traces. They should be kept locally or in shared storage for auditability.

## Immediate Sanity Checks

Replace `RUN_DIR` and `TASK`:

```bash
export RUN_DIR="outputs/repro_commit0/filesystem_spec/gpt-5.4-mini_single_i30_curated_v05"
export TASK=filesystem_spec
```

Check the runner used AsyncCodeBench curated inputs:

```bash
rg -n "Loaded curated|Verified curated|Applying .*AsyncCodeBench|Using AsyncCodeBench|Installing AsyncCodeBench curated" "$RUN_DIR"/run_*.log
```

Check final evaluator:

```bash
cat "$RUN_DIR/${TASK}_pytest_exit_code.txt"
tail -n 40 "$RUN_DIR/${TASK}_test_output.txt"
```

Check strict dependency checkpoint summary:

```bash
python3 - <<'PY'
import json
import os
from pathlib import Path

run_dir = Path(os.environ["RUN_DIR"])
path = run_dir / "dependency_probe_checkpoints.jsonl"
for line in path.read_text().splitlines():
    rec = json.loads(line)
    resolved = sum(
        1
        for dep in rec.get("dependency_results", [])
        if dep["groups"]["integrated"]["passed"]
    )
    total = len(rec.get("dependency_results", []))
    print(rec["logical_step"], rec["checkpoint_id"], rec["pytest_summary"], f"ADPR={resolved}/{total}")
PY
```

If `dependency_probe_checkpoints.jsonl` has `not_collected`, inspect the
excerpt before interpreting metrics. `not_collected` can mean either:

- the model broke syntax/imports; this is a valid model failure, or
- the runner/worktree environment is incomplete; this is an instrumentation
  problem and should be fixed before reporting strict DRS/CAIL.

## Post-Run Metrics

From the repository root:

```bash
export REPO_ROOT="${REPO_ROOT:-$HOME/AsyncCodeBench}"
cd "$REPO_ROOT"
```

Set common variables:

```bash
TASK=filesystem_spec
METRIC_TASK="${TASK//-/_}"
MODEL_TAG=gpt-5.4-mini
MODEL_ID=openai/gpt-5.4-mini
RUN_VERSION=v05
BASE_DIR="reproductions/async-swe-agents/outputs/repro_commit0/${TASK}"
METRICS="manifests/pilot/v0.3/metrics/commit0_${METRIC_TASK}_async_metrics.json"
```

Run per-directory process summaries:

```bash
python scripts/analyze_run_process_metrics.py \
  --run-dir "${BASE_DIR}/${MODEL_TAG}_single_i30_curated_${RUN_VERSION}" \
  --metrics "$METRICS" \
  --output "${BASE_DIR}/${MODEL_TAG}_single_i30_curated_${RUN_VERSION}/process_metrics_summary.json" \
  --print-summary
```

For multi-agent runs, use the serial run as the baseline when helpful:

```bash
python scripts/analyze_run_process_metrics.py \
  --run-dir "${BASE_DIR}/${MODEL_TAG}_serial_3agents_s30_curated_${RUN_VERSION}" \
  --metrics "$METRICS" \
  --output "${BASE_DIR}/${MODEL_TAG}_serial_3agents_s30_curated_${RUN_VERSION}/process_metrics_summary.json" \
  --print-summary

python scripts/analyze_run_process_metrics.py \
  --run-dir "${BASE_DIR}/${MODEL_TAG}_async_private_3agents_s30_curated_${RUN_VERSION}" \
  --baseline-run-dir "${BASE_DIR}/${MODEL_TAG}_serial_3agents_s30_curated_${RUN_VERSION}" \
  --metrics "$METRICS" \
  --output "${BASE_DIR}/${MODEL_TAG}_async_private_3agents_s30_curated_${RUN_VERSION}/process_metrics_summary.json" \
  --print-summary

python scripts/analyze_run_process_metrics.py \
  --run-dir "${BASE_DIR}/${MODEL_TAG}_caid_multi_3agents_m40_s50_curated_${RUN_VERSION}" \
  --baseline-run-dir "${BASE_DIR}/${MODEL_TAG}_serial_3agents_s30_curated_${RUN_VERSION}" \
  --metrics "$METRICS" \
  --output "${BASE_DIR}/${MODEL_TAG}_caid_multi_3agents_m40_s50_curated_${RUN_VERSION}/process_metrics_summary.json" \
  --print-summary
```

After every run directory has `process_metrics_summary.json`, generate the
three model-task output documents:

```bash
python scripts/summarize_model_task_runs.py \
  --task "$TASK" \
  --model-tag "$MODEL_TAG" \
  --model "$MODEL_ID" \
  --runner-adapter native-strict-checkpoints \
  --metrics "$METRICS" \
  --output-dir "reproductions/async-swe-agents/outputs/${MODEL_TAG}" \
  --run single="${BASE_DIR}/${MODEL_TAG}_single_i30_curated_${RUN_VERSION}" \
  --run serial_specialists="${BASE_DIR}/${MODEL_TAG}_serial_3agents_s30_curated_${RUN_VERSION}" \
  --run async_private="${BASE_DIR}/${MODEL_TAG}_async_private_3agents_s30_curated_${RUN_VERSION}" \
  --run CAID_multi="${BASE_DIR}/${MODEL_TAG}_caid_multi_3agents_m40_s50_curated_${RUN_VERSION}"
```

This writes:

```text
reproductions/async-swe-agents/outputs/<model_tag>/<task>.md
reproductions/async-swe-agents/outputs/<model_tag>/<task>_<model_tag>_metrics_table.csv
reproductions/async-swe-agents/outputs/<model_tag>/<task>_<model_tag>_artifact_index.json
```

## Important Tensions And Resolutions

### The command says Commit0, but the data must be AsyncCodeBench.

This is expected. `commit0` is the inherited runner task adapter. Official
AsyncCodeBench runs are identified by curated source logs, pinned SHA checks,
bootstrap overlays, scenario evaluator targets, and metrics manifests.

### `COMMIT0_DATASET_PATH` is still required.

This is a legacy API requirement. It should not define the official task when a
curated v0.3 record is available. Keep it configured, but verify curated logs.

### Bootstrap overlays are not solutions.

Overlays repair import, syntax, or test-collection prerequisites in stripped
Commit0 states. They must be checksum-pinned and documented in
`configs/tasks/commit0_curated_tasks.v0.3.json`. They should not implement the
solution behavior being evaluated.

### Worktrees must inherit overlays.

Multi-agent protocols create git worktrees. If an overlay creates a file ignored
by upstream `.gitignore`, plain `git add .` may omit it from the bootstrap
commit. The runner uses `git add -f .` for bootstrap overlays so worktrees
inherit the complete curated state.

If agent artifact probes show a bootstrap import error such as
`No module named 'fsspec._version'`, treat strict artifact-level DRS/CAIL as
instrumentation-contaminated and rerun after fixing bootstrap tracking.

### Probe selectors must be stable.

Do not use optional-service or optional-package tests as dependency probes. A
probe that consistently skips because an optional dependency is absent will
understate ADPR and contaminate DRS/CAIL.

For `filesystem_spec`, `test_url_to_fs` depended on optional `pyftpdlib`, so the
registry-to-core probe was changed to `test_automkdir_local`, which still
observes `core.url_to_fs("file://")` and the registry/core contract without an
optional FTP server.

### Final pass/fail is not enough.

A run can:

- pass final pytest but use all iterations;
- fail final pytest after resolving some upstream probes;
- fail collection because an asynchronous private worker produced invalid
  syntax;
- locally pass a specialist probe but fail after integration.

Use final pass/fail as the conventional coding benchmark score. Use ADPR, DRS,
CAIL, and process diagnostics to explain asynchronous dependency behavior.

### `not_collected` requires classification.

`not_collected` can be a valid model failure if the model generated a syntax or
import error. It can also reveal a runner issue if a bootstrap file or evaluator
dependency is missing from agent worktrees. Inspect the excerpt before using the
metric.

### Version output directories.

Never overwrite a previous run after changing metrics labels, overlays, runner
setup, or iteration budgets. Use suffixes such as `curated_v04`,
`curated_v05`, and keep notes about what changed.

## Current Filesystem Spec Example

The current clean single-agent baseline is:

```text
outputs/repro_commit0/filesystem_spec/gpt54mini_single_i30_curated_v04
```

It passed:

```text
134 passed, 6 skipped, collected 140
ADPR = 2/2
```

The first multi-agent `v04` runs were useful for failure-structure analysis but
had artifact-level probe contamination from the worktree overlay issue. The
recommended rerun suffix after the fix is `v05`.
