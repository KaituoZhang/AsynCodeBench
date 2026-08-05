# Evaluation Branch Quickstart

This is the shortest path for a collaborator to reproduce AsyncCodeBench model
evaluation from the dedicated evaluation branch. Detailed explanations remain
in `MODEL_EXPERIMENT_RUNBOOK.md`, `LOCAL_VLLM_EXPERIMENT_RUNBOOK.md`, and
`EVALUATION_METRICS.md`.

## 1. Clone The Evaluation Branch

```bash
git clone --branch agent/reproducible-model-evaluation --single-branch \
  https://github.com/KaituoZhang/Asynccodebench.git
cd Asynccodebench
```

The repository contains the versioned AsyncCodeBench manifests, dependency
labels, scenarios, quality records, curated task configuration, bootstrap
overlays, four agent protocols, evaluators, and metric scripts. It intentionally
does not contain API keys, local virtual environments, generated outputs, the
external Commit0 checkout, or the large local `load_from_disk` dataset.

## 2. Install The Two Environments

Top-level validation and metric environment:

```bash
conda create -n asynccodebench python=3.10 -y
conda activate asynccodebench
python -m pip install -U pip
python -m pip install -e ".[dev]"
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q tests/contracts
```

Agent runner:

```bash
cd reproductions/async-swe-agents
uv sync
cd ..
git clone https://github.com/OpenHands/software-agent-sdk.git
cd async-swe-agents
```

Docker must work without `sudo` in the terminal or tmux server used for the
experiment:

```bash
docker run --rm hello-world
```

## 3. Provide The External Task Source

Set `COMMIT0_DATASET_PATH` to a local Hugging Face dataset created with
`save_to_disk`. AsyncCodeBench does not evaluate raw Commit0 directly: the
runner selects the curated v0.3 source record, verifies its base SHA, applies
checksum-pinned non-solution overlays, and uses the AsyncCodeBench task and
metric manifests.

Create an untracked model environment:

```bash
cp .env.example .env.<model_tag>
```

At minimum, fill in:

```bash
LLM_BASE_URL=<OpenAI-compatible endpoint>
LLM_API_KEY=<secret or non-empty local dummy key>
LLM_MODEL=<LiteLLM provider/model name>
LLM_SUBAGENT_MODEL=<same model or empty>
COMMIT0_DATASET_PATH=/absolute/path/to/commit0_combined
SDK_SOURCE_DIR=/absolute/path/to/Asynccodebench/reproductions/software-agent-sdk
```

Never commit `.env.<model_tag>`.

## 4. Run The Harness Gates

```bash
export ENV_FILE="$PWD/.env.<model_tag>"
source scripts/env.sh

unset ASYNCCODEBENCH_DISABLE_CURATED_TASK_SOURCE
unset ASYNCCODEBENCH_DISABLE_CURATED_TASK_CONFIG
unset ASYNCCODEBENCH_DISABLE_MANIFEST_EVALUATOR

docker info >/dev/null
test -d "$COMMIT0_DATASET_PATH"
test -d "$SDK_SOURCE_DIR"
printf 'model=%s\nendpoint=%s\n' "$LLM_MODEL" "$LLM_BASE_URL"
```

For a local vLLM model, complete all three connectivity/tool gates in
`LOCAL_VLLM_EXPERIMENT_RUNBOOK.md`. Qwen and Gemma have model-specific guides:

```text
docs/VLLM_QWEN_LOCAL_RUNBOOK.md
docs/GEMMA4_CAID_HARNESS_FIX.md
```

## 5. Run All Four Protocols

The official default is 30 iterations for single, specialists, CAID manager,
and CAID subagents, with two CAID chat rounds. The wrapper assigns the official
specialist count for the selected task and runs protocols sequentially.

```bash
cd /absolute/path/to/Asynccodebench/reproductions/async-swe-agents

ENV_FILE="$PWD/.env.<model_tag>" \
MODEL_TAG=<filesystem-safe-model-tag> \
RUN_VERSION=curated_v01 \
WORKSPACE_PORT_STRATEGY=auto \
RUN_SINGLE=1 \
RUN_SERIAL=1 \
RUN_ASYNC_PRIVATE=1 \
RUN_CAID=1 \
scripts/run_gemma4_task_env.sh cachetools
```

`run_gemma4_task_env.sh` is only for the validated Gemma 4 profile. For any
other API or local model, use the model-neutral wrapper:

```bash
ENV_FILE="$PWD/.env.<model_tag>" \
MODEL_TAG=<filesystem-safe-model-tag> \
MAX_SUBAGENTS=2 \
RUN_VERSION=curated_v01 \
WORKSPACE_PORT_STRATEGY=auto \
scripts/run_commit0_all_protocols_env.sh cachetools
```

Official specialist counts are:

```text
2: cachetools deprecated portalocker tinydb wcwidth
3: requests parsel filesystem_spec marshmallow graphene imapclient
4: simpy dulwich pexpect flask python-rsa cookiecutter
```

`WORKSPACE_PORT_STRATEGY=auto` finds four consecutive free host ports. It does
not change the model endpoint port. Every retry must use a new `RUN_VERSION`;
failed and interrupted run directories are immutable evidence.

## 6. Compute Strict Process Metrics

From the repository root, define the four fresh run directories and metric
manifest as shown in `MODEL_EXPERIMENT_RUNBOOK.md`. Then run
`analyze_run_process_metrics.py` once per protocol and summarize the task:

```bash
python3 scripts/analyze_run_process_metrics.py \
  --run-dir "$RUN_DIR" \
  --metrics "manifests/pilot/v0.3/metrics/commit0_${TASK//-/_}_async_metrics.json" \
  --output "$RUN_DIR/process_metrics_summary.json" \
  --print-summary
```

```bash
python3 scripts/summarize_model_task_runs.py \
  --task "$TASK" \
  --model-tag "$MODEL_TAG" \
  --model "$LLM_MODEL" \
  --runner-adapter native-strict-checkpoints \
  --metrics "manifests/pilot/v0.3/metrics/commit0_${TASK//-/_}_async_metrics.json" \
  --output-dir "reproductions/async-swe-agents/outputs/$MODEL_TAG" \
  --run single="$SINGLE" \
  --run serial_specialists="$SERIAL" \
  --run async_private="$ASYNC_PRIVATE" \
  --run CAID_multi="$CAID"
```

The three per-task products are a Markdown report, metrics CSV, and artifact
index JSON. Use `scripts/aggregate_model_task_results.py` after all 17 tasks.

## 7. Accept Or Reject A Run

A formal run must have:

- a fresh directory and exactly one `run_*.log`;
- nonzero model iterations;
- `report.json` with evaluator source `asynccodebench_manifest`;
- `dependency_probe_checkpoints.jsonl` and `process_metrics_summary.json`;
- no provider, transport, parser, context, or instrumentation failure;
- the same model-serving profile across all four protocols.

Coding failure is valid benchmark evidence. Infrastructure failure is not.
Unresolved dependencies remain in aggregate statistics using the documented
`T + 1` DRS/CAIL penalties; they are never dropped as missing values.

The official v0.3 aggregate has exactly 17 tasks. Exclude `fastapi`,
`python-progressbar`, `fabric`, and `chardet`.
