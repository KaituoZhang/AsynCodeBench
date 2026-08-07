# AsyncCodeBench Native Harness v2

## Purpose

The native harness makes AsyncCodeBench, rather than the source Commit0 dataset,
the executable experiment interface. Commit0 remains provenance and source-code
material, but a run is now selected by an AsyncCodeBench `task_id`, validated
against the official release, and configured by the task, scenario, metrics, and
quality manifests.

The legacy commands remain available for reproducing existing results. Harness
v2 is additive and does not rewrite old run directories or v1 runner code.

## Entry Point

Run all new experiments from:

```text
reproductions/async-swe-agents/run_asynccodebench.py
```

The four supported protocols are:

- `single`: one iterative full-task agent;
- `serial_specialists`: manifest-defined specialists execute in dependency order
  and receive structured completed-artifact handoffs;
- `async_private`: specialists execute concurrently from the same base without
  in-flight communication, then artifacts are integrated in dependency order;
- `caid_manager`: the CAID manager coordinates multiple private-worktree agents
  using the AsyncCodeBench task specification and dependency context.

## What Is Native

The task adapter is
`reproductions/async-swe-agents/tasks/asynccodebench.py`. It requires all of the
following artifacts:

```text
configs/tasks/commit0_official_tasks.v0.3.json
configs/tasks/commit0_curated_tasks.v0.3.json
manifests/pilot/v0.3/tasks/commit0_<task>.json
manifests/pilot/v0.3/scenarios/commit0_<task>.json
manifests/pilot/v0.3/metrics/commit0_<task>_async_metrics.json
manifests/pilot/v0.3/quality/commit0_<task>.json
```

The adapter refuses non-official tasks and refuses fallback to the raw Commit0
dataset. It reuses `Commit0Task` only as the low-level source materialization,
overlay, canonical-test restoration, and evaluator backend.

## Protocol Guarantees

Harness v2 adds runner-enforced behavior in
`reproductions/async-swe-agents/protocols/asynccodebench/`:

1. A stable producer-before-consumer order is derived from
   `dependency_annotations`. Cyclic contracts are reported explicitly and use
   stable manifest order because no strict topological order exists.
2. Serial specialists receive the integrated upstream artifact plus its targeted
   test and dependency-probe evidence.
3. Async-private workers do not receive in-flight artifacts, but their final
   patches are integrated in the same deterministic dependency order.
4. Every multi-agent artifact passes a pre-merge writable-path and main-workspace
   cleanliness gate. Out-of-scope committed or uncommitted changes are recorded
   and rejected rather than silently merged.
5. Dependency probes still run at agent-artifact, integration, and final
   checkpoints, preserving strict DRS and CAIL observability.
6. CAID remains manager-mediated, but both its initial delegation and later
   reassignment decisions must map exactly to the active `async_message`
   scenario. Invalid manager output is rejected or replaced by a provenance-
   recorded manifest fallback.

The dry-run also reports `shared_writable_paths`. This matters for the current
`marshmallow` manifest, where two assignments own `src/marshmallow/schema.py`
and two dependency nodes form a cycle. Harness v2 records these properties in
`protocol.json` rather than silently attributing every resulting integration
conflict to the model. The released task artifacts are not rewritten by the
runner.

## Environment

Load the same model environment used by the existing runner:

```bash
cd /home/kzhang42/AsyncCodeBench/reproductions/async-swe-agents
export ENV_FILE="$PWD/.env.<model-tag>"
source scripts/env.sh

unset ASYNCCODEBENCH_DISABLE_CURATED_TASK_SOURCE
unset ASYNCCODEBENCH_DISABLE_CURATED_TASK_CONFIG
unset ASYNCCODEBENCH_DISABLE_MANIFEST_EVALUATOR
```

For a local vLLM endpoint, `LLM_BASE_URL` must be reachable from both the host
runner and the Docker workspace. With host networking this is normally:

```bash
export LLM_BASE_URL=http://127.0.0.1:8006/v1
export ASYNCCODEBENCH_MODEL_SERVER_KIND=vllm
export ASYNCCODEBENCH_VLLM_CONFIG_JSON='{"max_model_len":131000,"max_num_seqs":2,"tool_call_parser":"qwen3_xml","reasoning_parser":"deepseek_r1"}'
export ASYNCCODEBENCH_WORKSPACE_DOCKER_NETWORK=host
export ASYNCCODEBENCH_WORKSPACE_HOST_PORT=<free-agent-server-port>
```

The workspace host port is the OpenHands agent-server port, not the vLLM port.
They must not be the same and the host port must be free before each run.
`ASYNCCODEBENCH_VLLM_CONFIG_JSON` should mirror the actual server launch flags;
`LLM_EXTRA_BODY_JSON` records thinking/chat-template request arguments. When a
custom chat template is used, set `ASYNCCODEBENCH_CHAT_TEMPLATE_PATH` so its
path and SHA-256 are frozen in `run_metadata.json`.

## Dry Run

Always validate a task before spending model tokens:

```bash
.venv/bin/python run_asynccodebench.py \
  --task_id commit0:cachetools \
  --protocol serial_specialists \
  --model "$LLM_MODEL" \
  --dry_run
```

The dry-run reports the official release status, curated base ref and SHA,
overlay count, scenario, writable paths, targeted tests, dependency integration
order, and any dependency cycle. It does not start Docker or call the model.

## Full Four-Protocol Example

Use a unique `run_id` for every attempt. Failed and interrupted directories are
immutable evidence and cannot be reused.

```bash
TASK_ID=commit0:cachetools
MODEL_TAG=qwen36-27
VERSION=curated_v2_01

.venv/bin/python run_asynccodebench.py \
  --task_id "$TASK_ID" --protocol single --model "$LLM_MODEL" \
  --max_iterations 30 --run_id "${MODEL_TAG}_${VERSION}"

.venv/bin/python run_asynccodebench.py \
  --task_id "$TASK_ID" --protocol serial_specialists --model "$LLM_MODEL" \
  --sub_iterations 30 --run_id "${MODEL_TAG}_${VERSION}"

.venv/bin/python run_asynccodebench.py \
  --task_id "$TASK_ID" --protocol async_private --model "$LLM_MODEL" \
  --sub_iterations 30 --run_id "${MODEL_TAG}_${VERSION}"

.venv/bin/python run_asynccodebench.py \
  --task_id "$TASK_ID" --protocol caid_manager --model "$LLM_MODEL" \
  --max_iterations 30 --sub_iterations 30 --rounds_of_chat 2 \
  --run_id "${MODEL_TAG}_${VERSION}"
```

For every protocol, `max_subagents` defaults to the exact `agent_count` in the
active scenario. Supplying a different number is rejected so protocol capacity
cannot silently diverge from the benchmark contract.

## Low-cost End-to-end Smoke

After dry-run, use the provided two-iteration smoke script before a full model
campaign:

```bash
cd /home/kzhang42/AsyncCodeBench/reproductions/async-swe-agents
export ENV_FILE="$PWD/.env.<model-tag>"
source scripts/env.sh
scripts/run_asynccodebench_v2_smoke.sh
```

The script runs all four protocols sequentially on `cachetools`. Failure to
solve the coding task in two iterations is expected; the gate is whether Docker,
model calls, private worktrees, evaluation, checkpoints, snapshots, scope logs,
and automatic process metrics all complete without instrumentation failure.

## Outputs

Default v2 outputs are isolated from legacy results:

```text
outputs/asynccodebench/v0.3/<model>/<task>/<protocol>/<run_id>/
```

In addition to existing patches, reports, costs, events, runtime, tarballs, and
dependency checkpoints, v2 writes:

- `run_metadata.json`: model and budget settings, code revisions, source SHA,
  overlay records, package versions, GPU hardware, local vLLM version/model
  metadata, context limits, generation settings, and SHA-256 hashes;
- `task_snapshot.json`, `scenario_snapshot.json`, `metrics_snapshot.json`, and
  `quality_snapshot.json`: immutable copies of the active benchmark inputs;
- `protocol.json`: resolved dependency integration order and scope policy;
- `scope_validation.jsonl`: changed paths and any rejected scope violations;
- `delegation_validation.json`: CAID initial-assignment validation and fallback
  decision;
- `artifact_handoffs.jsonl`: serial upstream artifact, targeted test result, and
  dependency-probe evidence delivered to downstream specialists;
- `process_metrics_summary.json`: automatically generated formal and process
  metrics for the completed run.

API keys are deliberately excluded from `run_metadata.json`.

## Post-run Metrics

The native runner automatically invokes the existing metric pipeline after a
completed run. The following command is only needed to audit or regenerate a
summary:

```bash
cd /home/kzhang42/AsyncCodeBench
python3 scripts/analyze_run_process_metrics.py \
  --run-dir reproductions/async-swe-agents/outputs/asynccodebench/v0.3/<model>/<task>/<protocol>/<run_id> \
  --metrics manifests/pilot/v0.3/metrics/commit0_<task>_async_metrics.json \
  --output reproductions/async-swe-agents/outputs/asynccodebench/v0.3/<model>/<task>/<protocol>/<run_id>/process_metrics_summary.json \
  --print-summary
```

Then use `scripts/summarize_model_task_runs.py` with four `--run` arguments to
create the task Markdown report, metrics CSV, and artifact-index JSON. Metric
definitions and unresolved-value policy remain in `docs/EVALUATION_METRICS.md`.

## Validation

Run the harness contract tests without rebuilding the environment:

```bash
cd /home/kzhang42/AsyncCodeBench/reproductions/async-swe-agents
.venv/bin/python -m pytest -q tests/test_asynccodebench_harness_v2.py
```

The tests check the 17-task official set, required manifests, curated source
records, four scenario types, dependency ordering, active CAID fallback,
initial and follow-up delegation validation, real git worktree isolation,
committed-patch rejection and merge behavior, snapshots, scope matching, and
metadata secret exclusion.

## Methodological Boundary

Harness v2 does not claim that Commit0 disappeared. The repository snapshots and
public tests retain Commit0 provenance. The contribution is the transformation
and execution protocol: AsyncCodeBench defines the task statement, natural
subproblem ownership, observable cross-agent dependencies, communication
condition, integration semantics, process checkpoints, and acceptance gates.
This distinction should be stated explicitly in the paper and release notes.
