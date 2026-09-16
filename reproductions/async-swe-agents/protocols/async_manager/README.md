# Task-budgeted Async-Manager protocol

This directory contains the only executable implementation of the fifth
official protocol in `configs/evaluation/protocol_registry.v2.json`. New runs
use policy `async-manager-online-v2-budgeted`. The frozen task, specialist,
checker, evaluator, and Docker contracts are reused from `caid_manager`.
Registry v1, profile v3, `legacy_profile.v1.json`, and `legacy_results.py` are
retained only to validate historical bundles; there is no v1 execution entry.

## Task-level manager budget

The persistent manager is one logical agent across all interventions. It has a
100-response task cap, a 30-response per-event cap, an 8,000,000-token guard,
a 21,600-second total active-time guard, a 7,200-second per-event guard, and at
most six executed interventions. Budget exhaustion preserves the integrated
specialist state and continues to final evaluation.

## Live progress logging

Each online intervention prints its triggering specialist/checkpoint, explains
that integration processing is serialized at that boundary, emits a periodic
heartbeat while the remote manager turn is running, and reports the final
status, iteration count, and changed/rejected path counts. This logging is
observability-only: it does not poll or mutate the conversation and does not
change prompts, scheduling, budgets, integration, checkpoints, or metrics.

The default heartbeat interval is 60 seconds. Operators may change only the
display frequency, for example:

```bash
export ASYNCODEBENCH_MANAGER_HEARTBEAT_SECONDS=30
```

## Semantics

One persistent logical manager analyzes the task, delegates specialists,
observes each specialist integration checkpoint, and may produce a scoped
production patch before scheduling continues. It normally retains one model
conversation. A terminal remote transport session is recorded and replaced,
but the logical manager, event history, accounting, and private Git worktree
remain continuous. Its terminal is read-only. File-editor writes are enabled
only while the harness is processing an explicit intervention event.

The writable manager scope is the union of the active scenario's specialist
production scopes. Tests, checkers, manifests, evaluators, Git metadata, and
paths outside that union are fail-closed. The harness stages the candidate
patch and checks all changed paths. Before creating a commit it runs the
affected integrated dependency selectors in one harness-owned pytest process
with a 600-second total timeout. Every selector must be collected and no
selector that passed at the triggering specialist checkpoint may regress.
The staged patch must also remain byte-identical throughout validation. A
passing candidate is committed and fast-forwarded into the integrated
workspace; a rejected candidate remains archived but is never merged.

`agent_finish` is recorded as a completion signal, not trusted as proof of
correctness. A candidate stopped by the 30-iteration event limit may still be
accepted when the same deterministic gate passes, preventing useful completed
edits from being discarded merely because the model did not emit a final
finish action. Both normally finished and iteration-limited candidates fail
closed on build failure, probe timeout, missing baseline evidence, collection
failure, dependency regression, or post-validation mutation.

Every specialist integration remains a canonical checkpoint. A manager
checkpoint is added only when a validated patch changes the integrated state.
Private manager drafts and no-op decisions are recorded in
`manager_interventions.jsonl` but never enter ADPR/DRS/SCS/RC trajectories.

## Run one task

```bash
cd reproductions/async-swe-agents
export ENV_FILE="$PWD/.env.my-model"
export MODEL_TAG=my-model
export RUN_ID=async_manager_v2_s1
bash scripts/run_async_manager_env.sh cachetools
```

TVM uses the same entry point:

```bash
bash scripts/run_async_manager_env.sh pr-hard:apache-tvm-20153
```

To run all five official protocols on a TVM task instead:

```bash
ENV_FILE="$PWD/.env.my-model" RUN_ID=tvm-five-v01 \
  scripts/run_pr_hard_five_protocols_env.sh apache-tvm-20153
```

The canonical public CLI is equivalent:

```bash
./.venv/bin/python run_asyncodebench.py \
  --task_id asyncodebench:cachetools \
  --protocol async_manager \
  --model "$LLM_MODEL" \
  --run_id async-manager-v01
```

Output directories are immutable. Use a new `RUN_ID` after any interruption.

## Run the unified suite

```bash
export TASK_GROUP=all        # core, tvm, or all
export CONTINUE_ON_ERROR=1
bash scripts/run_async_manager_20tasks_env.sh
```

The suite has stable zero-based sharding. Four foreground terminals can share
one campaign `RUN_ID`, while each terminal points at its own model endpoint via
an environment file:

```bash
# terminal 1
SHARD_COUNT=4 SHARD_INDEX=0 ENV_FILE="$PWD/.env.port-8006" \
  RUN_ID=async_manager_v2_s1 bash scripts/run_async_manager_20tasks_env.sh

# terminals 2--4: use SHARD_INDEX=1, 2, 3 and their corresponding ENV_FILE.
```

Tasks occupy distinct immutable output directories, so sharing the campaign ID
across shards does not create output collisions.

## Dry-run and validate

```bash
./.venv/bin/python run_async_manager.py \
  --task_id=asyncodebench:cachetools \
  --model=openai/example \
  --model_tag=example \
  --run_id=dry \
  --dry_run

./.venv/bin/python run_async_manager.py \
  --validate_dir=/absolute/path/to/completed/run
```

Validate and summarize a complete 20-task campaign:

```bash
./.venv/bin/python -m protocols.async_manager.campaign \
  --root outputs \
  --run-id async_manager_v2_s1 \
  --output-dir ../../docs/results/async_manager_v2_s1 \
  --require-complete
```

This writes JSON, CSV, and Markdown with FSR, macro/micro ADPR, normalized
penalized DRS/SCS, normalized RC, tokens, runtime, and intervention counts. The
direction of every paper-facing aggregate is included in the output.

Formal execution rejects uncommitted execution sources, any dirty
execution-critical harness source, or any difference in frozen legacy
execution engines relative to commit
`73c9877315c920867ba72750826b66421be08bc0`.

### Bundle recovery for the 25152ad metadata omission

Runs started from revision `25152ad` can complete model execution, evaluation,
and trajectory instrumentation but fail finalization because that runner did
not copy its successful source preflight into `run_metadata.json`. The raw run
must not be edited or rerun. Recover it into a new directory with:

```bash
python scripts/recover_async_manager_bundle.py SOURCE_RUN NEW_RUN_DIRECTORY
```

Recovery verifies every saved protocol-source checksum against the recorded
Git revision, preserves the original metadata as evidence, records that neither
the model nor evaluator was rerun, and then applies the normal bundle
validator. It refuses an existing destination or a run whose source proof does
not match. New runs record the source preflight directly and do not need this
recovery path.

### Bundle recovery for the v2 budget-status finalizer bug

Revision `6b5a2fe` completed model execution and final evaluation correctly,
but its v2 finalizer delegated bundle construction to the legacy v1 helper.
The legacy helper rejected the valid v2-only `budget_exhausted` terminal status
and the runner consequently wrote a partial bundle. Preserve the source run
and recover it into a new directory with:

```bash
python scripts/recover_async_manager_budget_bundle.py SOURCE_RUN NEW_RUN_DIRECTORY
```

This recovery is accepted only when the error exactly matches the known
finalizer failure, every partial-inventory checksum matches, the manager budget
and shutdown records are valid, and final evaluator artifacts are present. It
records that neither model nor evaluator was rerun and validates the newly
constructed bundle with the canonical v2 validator.

## Result contract

The standard run artifacts remain present. Additional evidence includes:

- `async_manager_profile_snapshot.json`
- `manager_interventions.jsonl`
- `manager_interventions/NNNN.prompt.txt`
- `manager_interventions/NNNN.patch`
- `manager_candidate_validations/NNNN/validation.json`
- `protocol_sources/`

New bundles use the standard run-bundle schema with protocol `async_manager`,
policy `async-manager-online-v2-budgeted`, and execution profile v4. The common
validator dispatches historical policy `async-manager-online-v1` to the
validation-only compatibility layer, so those bundles remain independently
verifiable without being relabeled or rerun.
