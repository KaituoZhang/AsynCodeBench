# AsynCodeBench Model Experiment Runbook

This is the canonical procedure for evaluating a new model on the current
19-task AsynCodeBench v0.4.1 release. It uses the unified `asyncodebench` CLI.
Legacy source-specific task IDs are provenance only.

## 1. Experiment Contract

AsynCodeBench measures whether coding agents resolve labeled cross-agent
software dependencies under controlled execution and communication conditions.
It reports final tests together with dependency, coordination, and efficiency
evidence.

Every task is evaluated under the same five protocols:

| Protocol | Controlled condition |
| --- | --- |
| `single` | One iterative agent owns the complete task. |
| `serial_specialists` | Specialists run in dependency order and receive completed upstream handoffs. |
| `async_private` | Specialists run concurrently from the same base without in-flight communication. |
| `caid_manager` | A manager coordinates asynchronous private-worktree specialists. |
| `async_manager` | A persistent online manager coordinates specialists and may submit scope-validated production patches at explicit intervention checkpoints. |

The first four conditions use the unified scenario runner. The fifth uses the
budgeted Async-Manager wrapper documented in the repository README; together
they form the matched five-protocol matrix.

The benchmark harness, not the model or agent adapter, controls task selection,
source SHA, overlays, ownership, writable paths, protocol scheduling, artifact
integration, dependency probes, final evaluation, and result admission.

## 2. Official Tasks

The release contains exactly 19 tasks:

```text
cachetools       deprecated       portalocker       tinydb
wcwidth          requests         simpy              parsel
filesystem_spec  marshmallow      imapclient          pexpect
flask            python-rsa       cookiecutter
apache-tvm-20018 apache-tvm-20073 apache-tvm-20107 apache-tvm-20153
```

The scenario manifests declare these specialist counts:

| Specialists | Tasks |
| ---: | --- |
| 2 | `cachetools`, `deprecated`, `portalocker`, `tinydb`, `wcwidth` |
| 3 | `requests`, `parsel`, `filesystem_spec`, `marshmallow`, `imapclient`, `apache-tvm-20018`, `apache-tvm-20073`, `apache-tvm-20107`, `apache-tvm-20153` |
| 4 | `simpy`, `pexpect`, `flask`, `python-rsa`, `cookiecutter` |

Do not add `graphene`, `dulwich`, `fastapi`, `python-progressbar`, `fabric`, or
`chardet` to an official aggregate. Excluded-task artifacts are not distributed
in the clean community branch. The authoritative list is:

```text
manifests/release/v0.4/official_tasks.json
manifests/release/v0.4/task_index.json
configs/environments/official_task_images.v0.4.json
```

Check the machine-readable release status before a campaign:

```bash
cd reproductions/async-swe-agents
uv run asyncodebench release-status
uv run asyncodebench tasks
uv run asyncodebench images list
```

Automatic qualification and human review are separate. The command reports the
actual annotation completion state; do not infer completion from the presence
of blank annotator forms.

## 3. Required Files

The unified runner consumes these repository-owned artifacts:

```text
configs/tasks/commit0_official_tasks.v0.3.json
configs/tasks/commit0_curated_tasks.v0.3.json
configs/evaluation/official_execution_profile.v2.json
manifests/pilot/v0.3/tasks/
manifests/pilot/v0.3/scenarios/
manifests/pilot/v0.3/metrics/
manifests/pilot/v0.3/quality/
manifests/release/v0.3/task_index.json
manifests/candidates/pr_hard_v0.4/
manifests/release/v0.4/task_index.json
configs/environments/official_task_images.v0.4.json
schemas/release/run_bundle.schema.json
```

The v0.3 paths contain the 15 Commit0-derived source manifests; the v0.4.1
index composes those with the four compiler tasks to expose one 19-task release.
Source-specific filenames and IDs are provenance. The public runtime
ID is always `asyncodebench:<repository>`, and native runs do not read
`COMMIT0_DATASET_PATH`.

The runner is located at:

```text
reproductions/async-swe-agents/
```

## 4. Install From A Fresh Clone

Requirements: Linux `x86_64`, Git, Docker without `sudo`, `uv`, Python 3.12,
and an OpenAI-compatible model endpoint.

```bash
git clone --branch agent/community-ready-release-clean --single-branch \
  https://github.com/KaituoZhang/Asynccodebench.git AsynCodeBench
cd AsynCodeBench
bash scripts/setup_evaluation.sh
```

If needed, install the managed Python first:

```bash
uv python install 3.12
```

The setup script installs benchmark and runner environments, checks out the
pinned OpenHands SDK, checks Docker access, runs no-API tests, and creates an
untracked runner `.env` from `.env.example`.

## 5. Configure One Model

Create one environment file per model:

```bash
cd /absolute/path/to/AsynCodeBench/reproductions/async-swe-agents
cp .env.example .env.<model-tag>
```

Use a filesystem-safe `MODEL_TAG`, such as `qwen36-27` or
`gemma4-26b-a4b`. `LLM_MODEL` is the provider-facing model ID and may contain
slashes.

Minimum hosted-endpoint configuration:

```dotenv
LLM_BASE_URL=https://your-endpoint.example/v1
LLM_API_KEY=your-api-key
LLM_MODEL=openai/your-model-name
LLM_SUBAGENT_MODEL=
SDK_SOURCE_DIR=/absolute/path/to/AsynCodeBench/reproductions/software-agent-sdk
```

Record explicit generation settings whenever the model requires them:

```dotenv
LLM_MAX_INPUT_TOKENS=
LLM_MAX_OUTPUT_TOKENS=
LLM_TEMPERATURE=
LLM_TOP_P=
LLM_TOP_K=
LLM_TIMEOUT=
LLM_NUM_RETRIES=
LLM_EXTRA_BODY_JSON=
```

The harness records whether each setting came from the environment or from the
SDK/provider default. Secrets are excluded and nested credential-like JSON keys
are redacted.

Load the model environment in every new shell:

```bash
cd /absolute/path/to/AsynCodeBench/reproductions/async-swe-agents
export ENV_FILE="$PWD/.env.<model-tag>"
source scripts/env.sh
```

Do not set any `ASYNCODEBENCH_DISABLE_*` variable for an official run.

### Local vLLM

For local serving, the endpoint must be reachable from both the host and the
Docker workspace. With host networking, use:

```dotenv
LLM_BASE_URL=http://127.0.0.1:8006/v1
LLM_API_KEY=local-dummy-key
ASYNCODEBENCH_MODEL_SERVER_KIND=vllm
ASYNCODEBENCH_WORKSPACE_DOCKER_NETWORK=host
```

Also record the actual server flags, for example:

```bash
export ASYNCODEBENCH_VLLM_CONFIG_JSON='{"max_model_len":131000,"max_num_seqs":2,"max_num_batched_tokens":32768,"tool_call_parser":"qwen3_xml","reasoning_parser":"deepseek_r1"}'
```

Use `max_num_seqs` at least as large as the task's concurrent specialist count.
Keep model-serving and generation settings fixed across the four protocols of a
task. Use separate vLLM ports and disjoint workspace-port scan ranges when
running tasks in parallel terminals. Read
[`LOCAL_VLLM_EXPERIMENT_RUNBOOK.md`](LOCAL_VLLM_EXPERIMENT_RUNBOOK.md) for model
parser, context, Docker networking, and GPU-capacity checks.

## 6. Preflight Gates

Run these checks before spending API or GPU budget:

```bash
cd /absolute/path/to/AsynCodeBench/reproductions/async-swe-agents
export ENV_FILE="$PWD/.env.<model-tag>"
source scripts/env.sh

uv run asyncodebench doctor
uv run asyncodebench release-status
uv run asyncodebench tasks
uv run asyncodebench images list
curl -fsS "$LLM_BASE_URL/models"
```

For a local endpoint with host-networked workspaces, also test from Docker:

```bash
docker run --rm --network host curlimages/curl:8.10.1 \
  -fsS http://127.0.0.1:8006/v1/models
```

Then dry-run all four protocols:

```bash
ENV_FILE="$PWD/.env.<model-tag>" \
MODEL_TAG=<model-tag> \
RUN_VERSION=dry-run-v01 \
DRY_RUN=1 \
scripts/run_asyncodebench_all_protocols_env.sh cachetools
```

Confirm that the output reports:

- `task_id=asyncodebench:cachetools`;
- all four canonical protocol names;
- `official=True`;
- the curated base SHA and overlay count;
- manifest-defined agent assignments and writable paths;
- a matching official execution profile;
- the intended agent adapter.

Dry-run does not call the model or start a task container.

## 7. Low-Cost Real Smoke

Run a two-iteration cachetools smoke before a full campaign:

```bash
ENV_FILE="$PWD/.env.<model-tag>" \
MODEL_TAG=<model-tag> \
RUN_VERSION=smoke-v01 \
WORKSPACE_PORT_STRATEGY=auto \
SINGLE_ITERATIONS=2 \
SPECIALIST_ITERATIONS=2 \
CAID_MANAGER_ITERATIONS=2 \
CAID_SUB_ITERATIONS=2 \
ROUNDS_OF_CHAT=1 \
scripts/run_asyncodebench_all_protocols_env.sh cachetools
```

The model is not expected to solve cachetools in two iterations. The smoke is
successful when all four runs call the model and produce evaluator evidence,
dependency checkpoints, process metrics, snapshots, and a `run_bundle.json`.
These profile-deviating smoke runs are exploratory and must not enter the
official aggregate.

Validate each smoke directory:

```bash
for protocol in single serial_specialists async_private caid_manager; do
  uv run asyncodebench validate-run \
    "outputs/asyncodebench/v0.3/<model-tag>/cachetools/$protocol/smoke-v01" || true
done
```

Investigate any `invalid` result before the full campaign. A valid coding
failure is acceptable; a provider, parser, context, transport, workspace, or
instrumentation failure is not.

## 8. Run One Official Task

The released capability profile gives every model-facing agent run a hard cap
of 100 model responses and keeps two CAID chat rounds. Agents normally stop
earlier by invoking `FinishTool`; reaching 100 is recorded as an iteration-cap
termination. The wrapper reads `max_subagents` from each active scenario.

```bash
ENV_FILE="$PWD/.env.<model-tag>" \
MODEL_TAG=<model-tag> \
RUN_VERSION=official-v01 \
WORKSPACE_PORT_STRATEGY=auto \
scripts/run_asyncodebench_all_protocols_env.sh cachetools
```

The four protocols run sequentially. Never reuse an interrupted or completed
output directory. Retry an infrastructure-invalid run with a new
`RUN_VERSION`; retain the invalid evidence.

To run only one protocol:

```bash
RUN_SINGLE=0 \
RUN_SERIAL=0 \
RUN_ASYNC_PRIVATE=0 \
RUN_CAID=1 \
ENV_FILE="$PWD/.env.<model-tag>" \
MODEL_TAG=<model-tag> \
RUN_VERSION=official-caid-v01 \
WORKSPACE_PORT_STRATEGY=auto \
scripts/run_asyncodebench_all_protocols_env.sh portalocker
```

## 9. Run All 15 Non-Compiler Tasks

Start sequentially unless the endpoint has known concurrency capacity:

```bash
TASKS=(
  cachetools deprecated portalocker tinydb wcwidth requests simpy parsel
  filesystem_spec marshmallow imapclient pexpect flask python-rsa
  cookiecutter
)

for TASK in "${TASKS[@]}"; do
  ENV_FILE="$PWD/.env.<model-tag>" \
  MODEL_TAG=<model-tag> \
  RUN_VERSION=official-v01 \
  WORKSPACE_PORT_STRATEGY=auto \
  scripts/run_asyncodebench_all_protocols_env.sh "$TASK"
done
```

For parallel terminals, assign each terminal a different model endpoint and a
disjoint workspace-port range, for example:

```bash
WORKSPACE_PORT_SCAN_START=20000 WORKSPACE_PORT_SCAN_END=24999  # terminal 1
WORKSPACE_PORT_SCAN_START=25000 WORKSPACE_PORT_SCAN_END=29999  # terminal 2
WORKSPACE_PORT_SCAN_START=30000 WORKSPACE_PORT_SCAN_END=34999  # terminal 3
WORKSPACE_PORT_SCAN_START=35000 WORKSPACE_PORT_SCAN_END=39999  # terminal 4
```

Do not run more concurrent specialists than the local model server can serve.
Parallel execution changes throughput, not the benchmark protocol; serving
settings and endpoint assignment must be recorded.

## 10. Raw Output Layout

Each task-protocol run is immutable and stored at:

```text
reproductions/async-swe-agents/outputs/asyncodebench/v0.3/
  <model-tag>/<task>/<protocol>/<run-version>/
```

A formal run contains at least:

```text
run_metadata.json
task_snapshot.json
scenario_snapshot.json
scenario_manifest_snapshot.json
metrics_snapshot.json
quality_snapshot.json
execution_profile_snapshot.json
protocol.json
report.json
dependency_probe_checkpoints.jsonl
process_metrics_summary.json
cost.json
runtime.txt
run_bundle.json
```

Agent traces, scope decisions, handoffs, patches, and final repository archives
are recursively checksum-indexed when present. Do not edit or add files inside a
completed run directory.

## 11. Validate Every Run

Validate one formal run without calling the model:

```bash
uv run asyncodebench validate-run \
  outputs/asyncodebench/v0.3/<model-tag>/<task>/<protocol>/<run-version>
```

Use `inspect-run` only for historical directories that predate formal bundles:

```bash
uv run asyncodebench inspect-run <legacy-run-dir>
```

Formal status and score are separate:

- `valid`: trustworthy evidence, including a genuine coding failure;
- `review_required`: ambiguous evidence requiring adjudication;
- `invalid`: infrastructure, evaluator, identity, or integrity failure.

Only a run with `eligibility.official_aggregate=true` may enter an official
table. See [`RESULT_VALIDITY.md`](RESULT_VALIDITY.md).

## 12. Generate One Task Report

The native runner generates process metrics automatically. Generate derived
reports outside the immutable run directories:

```bash
cd /absolute/path/to/AsynCodeBench

TASK=cachetools
MODEL_TAG=<model-tag>
MODEL_ID=openai/your-model-name
RUN_VERSION=official-v01
RUN_ROOT="reproductions/async-swe-agents/outputs/asyncodebench/v0.3/${MODEL_TAG}/${TASK}"
REPORT_ROOT="outputs/reports/${MODEL_TAG}"
METRIC_STEM="${TASK//-/_}"

reproductions/async-swe-agents/.venv/bin/python \
  scripts/summarize_model_task_runs.py \
  --task "$TASK" \
  --model-tag "$MODEL_TAG" \
  --model "$MODEL_ID" \
  --metrics "manifests/pilot/v0.3/metrics/commit0_${METRIC_STEM}_async_metrics.json" \
  --output-dir "$REPORT_ROOT" \
  --run "single=${RUN_ROOT}/single/${RUN_VERSION}" \
  --run "serial_specialists=${RUN_ROOT}/serial_specialists/${RUN_VERSION}" \
  --run "async_private=${RUN_ROOT}/async_private/${RUN_VERSION}" \
  --run "caid_manager=${RUN_ROOT}/caid_manager/${RUN_VERSION}"
```

This writes:

```text
outputs/reports/<model-tag>/<task>.md
outputs/reports/<model-tag>/<task>_<model-tag>_metrics_table.csv
outputs/reports/<model-tag>/<task>_<model-tag>_artifact_index.json
```

The formal bundle's recorded adapter identity is authoritative. A reporting
argument cannot substitute a different adapter name.

## 13. Build The Model Aggregate

After generating all 19 task report sets:

```bash
reproductions/async-swe-agents/.venv/bin/python \
  scripts/aggregate_model_task_results.py \
  --input-dir "outputs/reports/<model-tag>" \
  --output-dir "outputs/reports/<model-tag>" \
  --model-tag <model-tag>
```

The default is fail-closed. It rejects missing or ineligible bundles, model or
adapter drift, execution-profile ID/SHA drift, and per-task cross-protocol
generation-configuration drift. It emits master, summary, pivot, display, and
Markdown tables plus a checksum-linked campaign manifest.

`--allow-ineligible` is only for explicitly exploratory migration analysis. Do
not use it for a paper's official result table.

## 14. Metrics And Direction

| Metric | Direction |
| --- | --- |
| Final success, pass rate, `ADPR`, dependency-resolution efficiency | Higher is better |
| `DRS`, `CAIL`, `FSAR`, `IFR`, `SVR`, cost, tokens, runtime | Lower is better |

Unresolved `DRS` and `CAIL` observations use the run's `T+1` penalty. They are
not discarded as missing data. Interpret dependency timing together with ADPR,
checkpoint count, final tests, and protocol condition. Definitions and formulas
are in [`EVALUATION_METRICS.md`](EVALUATION_METRICS.md).

## 15. Reporting And Retry Rules

For a public campaign:

1. predeclare repetitions per task-protocol cell;
2. label one-run tables as descriptive single-run evaluations;
3. never rerun a valid model failure to select a better trajectory;
4. rerun only infrastructure-invalid executions, with a new run ID;
5. retain or publish invalid-run health evidence;
6. publish every valid repetition when using repeated runs;
7. report exact model/subagent IDs, adapter identity, profile ID/SHA,
   generation-config SHA, benchmark/runner revisions, and campaign SHA;
8. keep raw bundles or publish them in checksum-verifiable storage.

## 16. Common Failure Modes

| Symptom | Interpretation and action |
| --- | --- |
| Public ID starts with `commit0:` | Wrong interface. Use `asyncodebench:<task>`. |
| `0 passed, 0 failed, 0 error` | Invalid evaluator evidence unless explicitly classified as a model-induced synthetic failure. Inspect the bundle. |
| Provider, connection, or authentication error | Infrastructure-invalid; fix endpoint or credentials and use a new run ID. |
| Context-window error | Model-server configuration failure; align input/output budgets with the served context. |
| Tool parser or reasoning parser error | Fix the model-specific vLLM parser/template before continuing. |
| Workspace port occupied | Use `WORKSPACE_PORT_STRATEGY=auto` or a disjoint scan range. The workspace port is not the vLLM port. |
| Scope rejection | Usually valid model/agent behavior evidence when instrumentation is healthy; do not silently merge the artifact. |
| Dependency `not_collected` | May be a model-induced import/syntax break; keep the status and inspect evaluator health. |
| Existing output directory | Do not delete or reuse it. Choose a new `RUN_VERSION`. |
| Missing `run_bundle.json` | Legacy or incomplete run; it cannot enter the official aggregate. |

Bootstrap overlays are checksum-pinned non-solution compatibility patches. They
make stripped source importable or testable; they do not implement the target
solution.

## 17. New Session Handoff

Give a collaborator or a new coding-agent session these documents in order:

1. repository `README`;
2. [`QUICKSTART.md`](QUICKSTART.md);
3. this runbook;
4. [`RESULT_VALIDITY.md`](RESULT_VALIDITY.md);
5. [`EVALUATION_METRICS.md`](EVALUATION_METRICS.md);
6. [`LOCAL_VLLM_EXPERIMENT_RUNBOOK.md`](LOCAL_VLLM_EXPERIMENT_RUNBOOK.md) for local models;
7. [`AGENT_ADAPTER.md`](AGENT_ADAPTER.md) for a custom coding agent.

Historical `outputs/repro_commit0/`, `run_commit0_*` scripts, and
`COMMIT0_DATASET_PATH` instructions remain only for reproducing earlier internal
experiments. They must not be mixed into a new native AsynCodeBench campaign.
