# Model Experiment Runbook

This document is the main operational guide for running AsyncCodeBench on a
new base model. It is written for a fresh session or collaborator who needs to
repeat the `gpt-5.4-mini` workflow with another model family.

Use this together with:

- `docs/AGENT_EXPERIMENT_RUNBOOK.md` for lower-level runner details.
- `docs/EVALUATION_METRICS.md` for metric definitions.
- `docs/COOKIECUTTER_RUNNER_EVALUATOR_FIX.md` for `cookiecutter` pitfalls.
- `docs/FLASK_EVALUATOR_COMPATIBILITY_FIX.md` for `flask` evaluator notes.

## Benchmark Goal

AsyncCodeBench evaluates whether asynchronous coding agents can resolve
cross-agent software dependencies, not just whether the final repository passes
tests.

Traditional coding benchmarks mainly report final pass/fail. AsyncCodeBench
adds dependency-aware process metrics:

- `ADPR`: fraction of labeled dependency contracts resolved in the final
  integrated workspace. Higher is better.
- `DRS`: dependency resolution step. Lower is better.
- `CAIL`: cross-agent integration lag. Lower is better.
- `FSAR`: failed subagent attempt rate. Lower is better.
- `IFR`: integration failure rate. Lower is better.
- `Cost`, `Tokens`, and `Runtime`: lower is better, conditional on quality.

The dependency labels are produced during the AsyncCodeBench transformation
pipeline. They are not post-hoc observations. Each ADPR/DRS/CAIL value is tied
to a labeled producer-consumer contract in:

```text
manifests/pilot/v0.3/metrics/
```

## Required Files And Locations

Benchmark artifacts:

```text
configs/tasks/commit0_curated_tasks.v0.3.json
manifests/pilot/v0.3/tasks/
manifests/pilot/v0.3/scenarios/
manifests/pilot/v0.3/metrics/
manifests/pilot/v0.3/quality/
data/overlays/commit0/
```

Agent runner:

```text
reproductions/async-swe-agents/
```

Raw run outputs:

```text
reproductions/async-swe-agents/outputs/repro_commit0/<task>/<run_id>/
```

Per-model summarized outputs:

```text
reproductions/async-swe-agents/outputs/<model_tag>/
```

Reference output format from the completed `gpt-5.4-mini` run:

```text
reproductions/async-swe-agents/outputs/gpt-5.4-mini/
```

## Official 17-task Set

Use exactly these official v0.3 tasks for the current aggregate tables:

```text
cachetools
deprecated
portalocker
tinydb
wcwidth
requests
simpy
dulwich
parsel
filesystem_spec
marshmallow
graphene
imapclient
pexpect
flask
python-rsa
cookiecutter
```

Do not include these in official 17-task aggregates:

```text
fastapi
python-progressbar
fabric
chardet
```

Specialist counts:

| Task | MAX_SUBAGENTS |
| --- | ---: |
| cachetools | 2 |
| deprecated | 2 |
| portalocker | 2 |
| tinydb | 2 |
| wcwidth | 2 |
| requests | 3 |
| parsel | 3 |
| filesystem_spec | 3 |
| marshmallow | 3 |
| graphene | 3 |
| imapclient | 3 |
| simpy | 4 |
| dulwich | 4 |
| pexpect | 4 |
| flask | 4 |
| python-rsa | 4 |
| cookiecutter | 4 |

## Environment Setup

Start from the runner directory:

```bash
export REPO_ROOT="${REPO_ROOT:-/home/kzhang42/AsyncCodeBench}"
cd "$REPO_ROOT/reproductions/async-swe-agents"
```

Create one env file per model. Do not commit these files.

```bash
cp .env.example .env.qwen37plus
```

Required fields:

```bash
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_API_KEY=YOUR_PROVIDER_KEY
LLM_MODEL=qwen/qwen3.7-plus
LLM_SUBAGENT_MODEL=
COMMIT0_DATASET_PATH=/home/kzhang42/AsyncCodeBench/data/external/commit0_combined
SDK_SOURCE_DIR=/home/kzhang42/AsyncCodeBench/reproductions/software-agent-sdk
```

`MODEL_ID` is the real provider model name used by the API, for example:

```text
qwen/qwen3.7-plus
anthropic/claude-sonnet-4.6
z-ai/glm-4.5
openai/gpt-5.4-mini
```

`MODEL_TAG` is the filesystem-safe output name, for example:

```text
qwen3.7-plus
claude-sonnet-4.6
glm-4.5
gpt-5.4-mini
```

Load the environment:

```bash
export ENV_FILE="$PWD/.env.qwen37plus"
source scripts/env.sh

unset ASYNCCODEBENCH_DISABLE_CURATED_TASK_SOURCE
unset ASYNCCODEBENCH_DISABLE_CURATED_TASK_CONFIG
unset ASYNCCODEBENCH_DISABLE_MANIFEST_EVALUATOR
```

For official runs, never set:

```bash
ASYNCCODEBENCH_DISABLE_CURATED_TASK_SOURCE=1
```

The runner command still says `commit0` because it reuses the inherited Commit0
adapter. Official AsyncCodeBench runs must show curated-source logs.

## Smoke Test Before Full Runs

For every new model, start with `cachetools`.

```bash
cd /home/kzhang42/AsyncCodeBench/reproductions/async-swe-agents
source scripts/env.sh

TASK=cachetools
MODEL_TAG=qwen3.7-plus
RUN_VERSION=smoke_v01
MAX_SUBAGENTS=2
```

Static dry-runs do not call the LLM:

```bash
uv run python run_static_protocol.py \
  --task commit0 \
  --protocol serial_specialists \
  --repo "$TASK" \
  --model "$LLM_MODEL" \
  --max_subagents "$MAX_SUBAGENTS" \
  --sub_iterations 2 \
  --dataset_path "$COMMIT0_DATASET_PATH" \
  --output_dir "outputs/repro_commit0/${TASK}/${MODEL_TAG}_serial_dryrun_${RUN_VERSION}" \
  --dry_run
```

```bash
uv run python run_static_protocol.py \
  --task commit0 \
  --protocol async_private \
  --repo "$TASK" \
  --model "$LLM_MODEL" \
  --max_subagents "$MAX_SUBAGENTS" \
  --sub_iterations 2 \
  --dataset_path "$COMMIT0_DATASET_PATH" \
  --output_dir "outputs/repro_commit0/${TASK}/${MODEL_TAG}_async_private_dryrun_${RUN_VERSION}" \
  --dry_run
```

Then run one low-budget real smoke:

```bash
MAX_ITERATIONS=5 \
OUTPUT_DIR="outputs/repro_commit0/${TASK}/${MODEL_TAG}_single_i5_curated_${RUN_VERSION}" \
scripts/run_commit0_single_env.sh "$TASK"
```

The smoke output directory should contain:

```text
report.json
cost.json
dependency_probe_checkpoints.jsonl
run_*.log
```

Check curated source usage:

```bash
RUN_DIR="outputs/repro_commit0/${TASK}/${MODEL_TAG}_single_i5_curated_${RUN_VERSION}"
rg -n "Loaded curated|Verified curated|Applying .*AsyncCodeBench|Using AsyncCodeBench|asynccodebench_manifest" "$RUN_DIR"/run_*.log "$RUN_DIR"/report.json
```

Stop and debug before full runs if curated-source lines are missing.

## Full Experiment Commands

Use these defaults for new models:

```bash
SINGLE_ITERATIONS=30
SPECIALIST_ITERATIONS=30
CAID_MANAGER_ITERATIONS=30
CAID_SUB_ITERATIONS=30
ROUNDS_OF_CHAT=2
```

Set task/model variables:

```bash
cd /home/kzhang42/AsyncCodeBench/reproductions/async-swe-agents
source scripts/env.sh

TASK=cachetools
MODEL_ID="$LLM_MODEL"
MODEL_TAG=qwen3.7-plus
RUN_VERSION=curated_v01
MAX_SUBAGENTS=2
```

### Single Agent

```bash
MAX_ITERATIONS="$SINGLE_ITERATIONS" \
OUTPUT_DIR="outputs/repro_commit0/${TASK}/${MODEL_TAG}_single_i${SINGLE_ITERATIONS}_${RUN_VERSION}" \
scripts/run_commit0_single_env.sh "$TASK"
```

### Serial Specialists

```bash
MAX_SUBAGENTS="$MAX_SUBAGENTS" \
SUB_ITERATIONS="$SPECIALIST_ITERATIONS" \
OUTPUT_DIR="outputs/repro_commit0/${TASK}/${MODEL_TAG}_serial_${MAX_SUBAGENTS}agents_s${SPECIALIST_ITERATIONS}_${RUN_VERSION}" \
scripts/run_commit0_serial_env.sh "$TASK"
```

### Async Private

```bash
MAX_SUBAGENTS="$MAX_SUBAGENTS" \
SUB_ITERATIONS="$SPECIALIST_ITERATIONS" \
OUTPUT_DIR="outputs/repro_commit0/${TASK}/${MODEL_TAG}_async_private_${MAX_SUBAGENTS}agents_s${SPECIALIST_ITERATIONS}_${RUN_VERSION}" \
scripts/run_commit0_async_private_env.sh "$TASK"
```

### CAID Multi-agent

```bash
MAX_ITERATIONS="$CAID_MANAGER_ITERATIONS" \
MAX_SUBAGENTS="$MAX_SUBAGENTS" \
SUB_ITERATIONS="$CAID_SUB_ITERATIONS" \
ROUNDS_OF_CHAT="$ROUNDS_OF_CHAT" \
OUTPUT_DIR="outputs/repro_commit0/${TASK}/${MODEL_TAG}_caid_multi_${MAX_SUBAGENTS}agents_m${CAID_MANAGER_ITERATIONS}_s${CAID_SUB_ITERATIONS}_${RUN_VERSION}" \
scripts/run_commit0_multi_env.sh "$TASK"
```

### 17-task Loop Template

Run in small batches first. The full loop can spend substantial API budget.

```bash
cd /home/kzhang42/AsyncCodeBench/reproductions/async-swe-agents
source scripts/env.sh

MODEL_TAG=qwen3.7-plus
RUN_VERSION=curated_v01
SINGLE_ITERATIONS=30
SPECIALIST_ITERATIONS=30
CAID_MANAGER_ITERATIONS=30
CAID_SUB_ITERATIONS=30
ROUNDS_OF_CHAT=2

for TASK in \
  cachetools deprecated portalocker tinydb wcwidth \
  requests parsel filesystem_spec marshmallow graphene imapclient \
  simpy dulwich pexpect flask python-rsa cookiecutter
do
  case "$TASK" in
    cachetools|deprecated|portalocker|tinydb|wcwidth)
      MAX_SUBAGENTS=2
      ;;
    requests|parsel|filesystem_spec|marshmallow|graphene|imapclient)
      MAX_SUBAGENTS=3
      ;;
    simpy|dulwich|pexpect|flask|python-rsa|cookiecutter)
      MAX_SUBAGENTS=4
      ;;
  esac

  MAX_ITERATIONS="$SINGLE_ITERATIONS" \
  OUTPUT_DIR="outputs/repro_commit0/${TASK}/${MODEL_TAG}_single_i${SINGLE_ITERATIONS}_${RUN_VERSION}" \
  scripts/run_commit0_single_env.sh "$TASK"

  MAX_SUBAGENTS="$MAX_SUBAGENTS" SUB_ITERATIONS="$SPECIALIST_ITERATIONS" \
  OUTPUT_DIR="outputs/repro_commit0/${TASK}/${MODEL_TAG}_serial_${MAX_SUBAGENTS}agents_s${SPECIALIST_ITERATIONS}_${RUN_VERSION}" \
  scripts/run_commit0_serial_env.sh "$TASK"

  MAX_SUBAGENTS="$MAX_SUBAGENTS" SUB_ITERATIONS="$SPECIALIST_ITERATIONS" \
  OUTPUT_DIR="outputs/repro_commit0/${TASK}/${MODEL_TAG}_async_private_${MAX_SUBAGENTS}agents_s${SPECIALIST_ITERATIONS}_${RUN_VERSION}" \
  scripts/run_commit0_async_private_env.sh "$TASK"

  MAX_ITERATIONS="$CAID_MANAGER_ITERATIONS" \
  MAX_SUBAGENTS="$MAX_SUBAGENTS" \
  SUB_ITERATIONS="$CAID_SUB_ITERATIONS" \
  ROUNDS_OF_CHAT="$ROUNDS_OF_CHAT" \
  OUTPUT_DIR="outputs/repro_commit0/${TASK}/${MODEL_TAG}_caid_multi_${MAX_SUBAGENTS}agents_m${CAID_MANAGER_ITERATIONS}_s${CAID_SUB_ITERATIONS}_${RUN_VERSION}" \
  scripts/run_commit0_multi_env.sh "$TASK"
done
```

## Post-run Evaluation

Run evaluation from the repository root:

```bash
cd /home/kzhang42/AsyncCodeBench

TASK=cachetools
METRIC_TASK="${TASK//-/_}"
MODEL_TAG=qwen3.7-plus
MODEL_ID=qwen/qwen3.7-plus
RUN_VERSION=curated_v01
MAX_SUBAGENTS=2

BASE_DIR="reproductions/async-swe-agents/outputs/repro_commit0/${TASK}"
METRICS="manifests/pilot/v0.3/metrics/commit0_${METRIC_TASK}_async_metrics.json"

SINGLE="${BASE_DIR}/${MODEL_TAG}_single_i30_${RUN_VERSION}"
SERIAL="${BASE_DIR}/${MODEL_TAG}_serial_${MAX_SUBAGENTS}agents_s30_${RUN_VERSION}"
ASYNC="${BASE_DIR}/${MODEL_TAG}_async_private_${MAX_SUBAGENTS}agents_s30_${RUN_VERSION}"
CAID="${BASE_DIR}/${MODEL_TAG}_caid_multi_${MAX_SUBAGENTS}agents_m30_s30_${RUN_VERSION}"
```

Generate per-run process summaries:

```bash
python3 scripts/analyze_run_process_metrics.py \
  --run-dir "$SINGLE" \
  --metrics "$METRICS" \
  --output "$SINGLE/process_metrics_summary.json" \
  --print-summary
```

```bash
python3 scripts/analyze_run_process_metrics.py \
  --run-dir "$SERIAL" \
  --metrics "$METRICS" \
  --baseline-run-dir "$SINGLE" \
  --output "$SERIAL/process_metrics_summary.json" \
  --print-summary
```

```bash
python3 scripts/analyze_run_process_metrics.py \
  --run-dir "$ASYNC" \
  --metrics "$METRICS" \
  --baseline-run-dir "$SINGLE" \
  --output "$ASYNC/process_metrics_summary.json" \
  --print-summary
```

```bash
python3 scripts/analyze_run_process_metrics.py \
  --run-dir "$CAID" \
  --metrics "$METRICS" \
  --baseline-run-dir "$SINGLE" \
  --output "$CAID/process_metrics_summary.json" \
  --print-summary
```

Generate the per-task three-file summary:

```bash
python3 scripts/summarize_model_task_runs.py \
  --task "$TASK" \
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

Expected files:

```text
reproductions/async-swe-agents/outputs/<model_tag>/<task>.md
reproductions/async-swe-agents/outputs/<model_tag>/<task>_<model_tag>_metrics_table.csv
reproductions/async-swe-agents/outputs/<model_tag>/<task>_<model_tag>_artifact_index.json
```

## Aggregate Tables

After all 17 tasks have per-task summaries, aggregate them into the same shapes
used for the completed `gpt-5.4-mini` experiment.

Reference files:

```text
reproductions/async-swe-agents/outputs/gpt-5.4-mini/gpt-5.4-mini_17task_task_mode_metrics_penalized.csv
reproductions/async-swe-agents/outputs/gpt-5.4-mini/gpt-5.4-mini_17task_per_task_pivot_penalized.csv
reproductions/async-swe-agents/outputs/gpt-5.4-mini/gpt-5.4-mini_17task_grouped_display_table.xlsx
reproductions/async-swe-agents/outputs/gpt-5.4-mini/gpt-5.4-mini_17task_result_analysis_report.md
```

For a new model, produce equivalent files under:

```text
reproductions/async-swe-agents/outputs/<model_tag>/
```

Current recommended aggregate outputs:

```text
<model_tag>_17task_task_mode_metrics_penalized.csv
<model_tag>_17task_summary_by_mode_penalized.csv
<model_tag>_17task_per_task_pivot_penalized.csv
<model_tag>_17task_cost_tokens_runtime_by_task_mode.csv
<model_tag>_17task_grouped_display_table.csv
<model_tag>_17task_grouped_display_table.xlsx
<model_tag>_17task_result_analysis_report.md
```

If a universal aggregation script has not yet been checked in, ask the new
session to reproduce the aggregation logic from the existing `gpt-5.4-mini`
outputs and save the new-model files with the same schema.

## Metric Direction And Acceptance Criteria

Metric direction:

| Metric | Direction |
| --- | --- |
| Success Rate | Higher is better |
| Mean Pass | Higher is better |
| Mean ADPR | Higher is better |
| Mean CAIL | Lower is better |
| Mean DRS | Lower is better |
| Cost | Lower is better, conditional on quality |
| Tokens | Lower is better, conditional on quality |
| Runtime | Lower is better, conditional on quality |

`Mean DRS` is dependency resolution step, so lower means earlier resolution.

Unresolved dependency handling:

```text
DRS_penalized(d) = DRS_raw(d), if dependency d is resolved
DRS_penalized(d) = T + 1, otherwise

CAIL_penalized(d) = max(CAIL_raw(d), 0), if observed
CAIL_penalized(d) = T + 1, otherwise
```

`T` is the number of dependency-probe checkpoints in the run.

Official-result checklist:

- The run directory is fresh and was not reused after a crash.
- The run directory has exactly one `run_*.log`.
- `report.json` records `final_evaluator_source` as
  `asynccodebench_manifest`.
- `dependency_probe_checkpoints.jsonl` exists.
- `process_metrics_summary.json` exists.
- The per-task artifact index points to the intended run directories.
- No obvious instrumentation failure is present.
- Any `not_collected` failure has been classified as model failure or runner
  issue before being used in a paper table.

Useful checks:

```bash
ls -1 "$RUN_DIR"/run_*.log
python3 -m json.tool "$RUN_DIR/report.json" | rg "final_evaluator_source|final_test_cmd|timed_out"
test -f "$RUN_DIR/dependency_probe_checkpoints.jsonl"
test -f "$RUN_DIR/process_metrics_summary.json"
```

## Common Pitfalls

### The command says `commit0`, but the data must be AsyncCodeBench.

This is expected. `commit0` is the inherited runner adapter. Official runs must
use curated v0.3 task records, manifests, base SHA checks, overlays, and
metrics manifests.

### Do not disable curated task source.

Do not use:

```bash
ASYNCCODEBENCH_DISABLE_CURATED_TASK_SOURCE=1
```

unless intentionally debugging raw Commit0 fallback behavior.

### Do not run excluded tasks into the official aggregate.

Do not include:

```text
fastapi
chardet
python-progressbar
fabric
```

### Do not reuse output directories.

If a run crashes or the runner code changes, use a new `RUN_VERSION`.
Reusing a directory can append checkpoint logs and contaminate DRS/CAIL.

### Docker permissions can differ between terminal and tmux.

If Docker works in a new terminal but not in tmux, the tmux server may have
started before group permissions changed. Start a new tmux server after saving
important command history.

### Classify `not_collected`.

`not_collected` can be a valid model failure if the model introduced syntax or
import errors. It can also indicate instrumentation problems such as missing
bootstrap files or evaluator dependencies. Inspect the traceback before using
strict DRS/CAIL in aggregate tables.

### Bootstrap overlays are not solutions.

Overlays are checksum-pinned non-solution patches that make stripped Commit0
states runnable or testable. They should not implement the behavior being
evaluated.

### Cookiecutter and Flask have extra notes.

Read:

```text
docs/COOKIECUTTER_RUNNER_EVALUATOR_FIX.md
docs/FLASK_EVALUATOR_COMPATIBILITY_FIX.md
```

before rerunning or debugging those tasks.

