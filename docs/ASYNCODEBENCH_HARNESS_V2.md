# AsynCodeBench Native Harness v2

The public name for the executable cross-agent dependency validation mechanism
is **Dependency Checker**. Legacy runtime symbols and persisted artifact names
containing `probe` remain unchanged for compatibility with existing runs.

## Purpose

The native harness makes AsynCodeBench, rather than the source Commit0 dataset,
the executable experiment interface. Commit0 remains provenance and source-code
material, but a run is now selected by an AsynCodeBench `task_id`, validated
against the official release, and configured by the task, scenario, metrics, and
quality manifests.

The legacy commands remain available for reproducing existing results. Harness
v2 is additive and does not rewrite old run directories or v1 runner code.

## Runtime Architecture

Harness v2 is **OpenHands-powered and AsynCodeBench-native**:

1. AsynCodeBench selects the released task and freezes task, scenario, metric,
   quality, source, scope, and evaluator contracts.
2. OpenHands SDK provides the agent conversation loop, coding tools, isolated
   worktrees, remote agent server, and Docker workspace.
3. AsynCodeBench regains control at delegation, integration, probing,
   evaluation, and artifact generation gates.

Therefore “native” does not mean that this repository reimplements an agent
runtime. It means models are evaluated through the AsynCodeBench contract rather
than through the raw Commit0 task interface. A user supplies an
OpenAI-compatible model configuration; the benchmark owns the rest.

## Entry Point

Run all new experiments from:

```text
reproductions/async-swe-agents/run_asyncodebench.py
```

The four supported protocols are:

- `single`: one iterative full-task agent;
- `serial_specialists`: manifest-defined specialists execute in dependency order
  and receive structured completed-artifact handoffs;
- `async_private`: specialists execute concurrently from the same base without
  in-flight communication, then artifacts are integrated in dependency order;
- `caid_manager`: the CAID manager coordinates multiple private-worktree agents
  using the AsynCodeBench task specification and dependency context.

## What Is Native

The public task identifier is `asyncodebench:<repository>`. The `commit0_*`
manifest filenames and internal `commit0:<repository>` fields are retained as
source/provenance identifiers; they do not change the public benchmark
namespace.

The task adapter is
`reproductions/async-swe-agents/tasks/asyncodebench.py`. It requires all of the
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
`reproductions/async-swe-agents/protocols/asyncodebench/`:

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
5. Dependency Checkers still run at agent-artifact, integration, and final
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
cd /absolute/path/to/AsynCodeBench/reproductions/async-swe-agents
export ENV_FILE="$PWD/.env.<model-tag>"
source scripts/env.sh

unset ASYNCODEBENCH_DISABLE_CURATED_TASK_SOURCE
unset ASYNCODEBENCH_DISABLE_CURATED_TASK_CONFIG
unset ASYNCODEBENCH_DISABLE_MANIFEST_EVALUATOR
```

All new environment variables use the `ASYNCODEBENCH_*` prefix. `scripts/env.sh`
temporarily maps the former `ASYNCCODEBENCH_*` prefix for local backward
compatibility and emits a warning; release examples and new configurations must
use the canonical prefix.

For a local vLLM endpoint, `LLM_BASE_URL` must be reachable from both the host
runner and the Docker workspace. With host networking this is normally:

```bash
export LLM_BASE_URL=http://127.0.0.1:8006/v1
export ASYNCODEBENCH_MODEL_SERVER_KIND=vllm
export ASYNCODEBENCH_VLLM_CONFIG_JSON='{"max_model_len":131000,"max_num_seqs":2,"tool_call_parser":"qwen3_xml","reasoning_parser":"deepseek_r1"}'
export ASYNCODEBENCH_WORKSPACE_DOCKER_NETWORK=host
# Optional. Omit this variable to let OpenHands choose a free port.
# export ASYNCODEBENCH_WORKSPACE_HOST_PORT=<free-agent-server-port>
```

The workspace host port is the OpenHands agent-server port, not the vLLM port.
They must not be the same. If the variable is omitted, the harness lets
OpenHands choose a free port from its dynamic port range; this is recommended
when several terminals run concurrently. If it is set, the port must be free
before each run.
`ASYNCODEBENCH_VLLM_CONFIG_JSON` should mirror the actual server launch flags;
`LLM_EXTRA_BODY_JSON` records thinking/chat-template request arguments. When a
custom chat template is used, set `ASYNCODEBENCH_CHAT_TEMPLATE_PATH` so its
path and SHA-256 are frozen in `run_metadata.json`.

## Dry Run

Always validate a task before spending model tokens:

```bash
.venv/bin/python run_asyncodebench.py \
  --task_id asyncodebench:cachetools \
  --protocol serial_specialists \
  --model "$LLM_MODEL" \
  --dry_run
```

The dry-run reports the official release status, curated base ref and SHA,
overlay count, scenario, writable paths, targeted tests, dependency integration
order, any dependency cycle, and whether the requested settings match the
official execution profile. It does not start Docker or call the model.

## Full Four-Protocol Example

Use a unique `run_id` for every attempt. Failed and interrupted directories are
immutable evidence and cannot be reused.

```bash
TASK_ID=asyncodebench:cachetools
MODEL_TAG=qwen36-27
VERSION=curated_v2_01

.venv/bin/python run_asyncodebench.py \
  --task_id "$TASK_ID" --protocol single --model "$LLM_MODEL" \
  --max_iterations 30 --run_id "${MODEL_TAG}_${VERSION}"

.venv/bin/python run_asyncodebench.py \
  --task_id "$TASK_ID" --protocol serial_specialists --model "$LLM_MODEL" \
  --sub_iterations 30 --run_id "${MODEL_TAG}_${VERSION}"

.venv/bin/python run_asyncodebench.py \
  --task_id "$TASK_ID" --protocol async_private --model "$LLM_MODEL" \
  --sub_iterations 30 --run_id "${MODEL_TAG}_${VERSION}"

.venv/bin/python run_asyncodebench.py \
  --task_id "$TASK_ID" --protocol caid_manager --model "$LLM_MODEL" \
  --max_iterations 30 --sub_iterations 30 --rounds_of_chat 2 \
  --run_id "${MODEL_TAG}_${VERSION}"
```

For every protocol, `max_subagents` defaults to the exact `agent_count` in the
active scenario. Supplying a different number is rejected so protocol capacity
cannot silently diverge from the benchmark contract.

The recommended interface runs the same four commands with automatic agent
counts and collision-resistant workspace ports:

```bash
ENV_FILE="$PWD/.env.<model-tag>" \
MODEL_TAG=<model-tag> \
RUN_VERSION=official_v01 \
WORKSPACE_PORT_STRATEGY=auto \
scripts/run_asyncodebench_all_protocols_env.sh cachetools
```

## Low-cost End-to-end Smoke

After dry-run, use the provided two-iteration smoke script before a full model
campaign:

```bash
cd /absolute/path/to/AsynCodeBench/reproductions/async-swe-agents
export ENV_FILE="$PWD/.env.<model-tag>"
source scripts/env.sh
scripts/run_asyncodebench_v2_smoke.sh
```

The script runs all four protocols sequentially on `cachetools`. Failure to
solve the coding task in two iterations is expected; the gate is whether Docker,
model calls, private worktrees, evaluation, checkpoints, snapshots, scope logs,
and automatic process metrics all complete without instrumentation failure.

## Outputs

Default v2 outputs are isolated from legacy results:

```text
outputs/asyncodebench/v0.3/<model>/<task>/<protocol>/<run_id>/
```

In addition to existing patches, reports, costs, events, runtime, tarballs, and
dependency checkpoints, v2 writes:

- `run_metadata.json`: model and budget settings, code revisions, source SHA,
  overlay records, package versions, GPU hardware, local vLLM version/model
  metadata, context limits, generation settings, and SHA-256 hashes;
- `task_snapshot.json`, `scenario_manifest_snapshot.json`,
  `metrics_snapshot.json`, and `quality_snapshot.json`: byte-exact copies of
  the released benchmark inputs;
- `scenario_snapshot.json`: the active protocol scenario selected from the
  full scenario manifest for this run;
- `execution_profile_snapshot.json`: exact official budget and instrumentation
  contract used to determine aggregate eligibility;
- `protocol.json`: resolved dependency integration order and scope policy;
- `scope_validation.jsonl`: changed paths and any rejected scope violations;
- `delegation_validation.json`: CAID initial-assignment validation and fallback
  decision;
- `artifact_handoffs.jsonl`: serial upstream artifact, targeted test result, and
  dependency-probe evidence delivered to downstream specialists;
- `process_metrics_summary.json`: automatically generated formal and process
  metrics for the completed run.
- `run_bundle.json`: schema-validated status, per-metric and provenance
  eligibility, and recursive checksums for every run artifact.

API keys are deliberately excluded from `run_metadata.json`.

Inspect any historical run and validate any new formal bundle with:

```bash
uv run asyncodebench inspect-run outputs/asyncodebench/v0.3/.../<run_id>
uv run asyncodebench validate-run outputs/asyncodebench/v0.3/.../<run_id>
```

The exact distinction between valid coding failure and invalid infrastructure
failure is defined in `docs/RESULT_VALIDITY.md`.

## Post-run Metrics

The native runner automatically invokes the metric pipeline before freezing the
run bundle. Do not regenerate a summary inside a bundled run directory. For an
analysis-code audit, write the derivative to a separate path:

```bash
cd /absolute/path/to/AsynCodeBench
reproductions/async-swe-agents/.venv/bin/python \
  scripts/analyze_run_process_metrics.py \
  --run-dir reproductions/async-swe-agents/outputs/asyncodebench/v0.3/<model>/<task>/<protocol>/<run_id> \
  --metrics manifests/pilot/v0.3/metrics/commit0_<task>_async_metrics.json \
  --output reproductions/async-swe-agents/outputs/derived-audits/<model>/<task>/<protocol>_process_metrics_summary.json \
  --print-summary
```

The audit output is not part of the frozen run and must be labeled as a derived
analysis. Editing any indexed run artifact invalidates its bundle checksum.

Then use `scripts/summarize_model_task_runs.py` with four `--run` arguments to
create the task Markdown report, metrics CSV, and artifact-index JSON. Metric
definitions and unresolved-value policy remain in `docs/EVALUATION_METRICS.md`.

## Validation

Run the harness contract tests without rebuilding the environment:

```bash
cd /absolute/path/to/AsynCodeBench/reproductions/async-swe-agents
.venv/bin/python -m pytest -q tests/test_asyncodebench_harness_v2.py
```

The tests check the 16-task official set, required manifests, curated source
records, four scenario types, dependency ordering, active CAID fallback,
initial and follow-up delegation validation, real git worktree isolation,
committed-patch rejection and merge behavior, snapshots, scope matching, and
metadata secret exclusion.

## Methodological Boundary

Harness v2 does not claim that Commit0 disappeared. The repository snapshots and
public tests retain Commit0 provenance. The contribution is the transformation
and execution protocol: AsynCodeBench defines the task statement, natural
subproblem ownership, observable cross-agent dependencies, communication
condition, integration semantics, process checkpoints, and acceptance gates.
This distinction should be stated explicitly in the paper and release notes.
