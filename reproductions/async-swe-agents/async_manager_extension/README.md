# Online Async-Manager protocol v1

This directory contains an additive protocol extension. It does not edit or
register itself in the released `single`, `serial_specialists`,
`async_private`, or `caid_manager` implementations. The frozen task,
specialist, checker, evaluator, and Docker contracts are reused from
`caid_manager`; only the manager execution policy is new.

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
patch, checks all changed paths, creates the commit, fast-forwards the current
integrated workspace, and verifies the resulting HEAD.

Every specialist integration remains a canonical checkpoint. A manager
checkpoint is added only when a validated patch changes the integrated state.
Private manager drafts and no-op decisions are recorded in
`manager_interventions.jsonl` but never enter ADPR/DRS/SCS/RC trajectories.

## Run one task

```bash
cd reproductions/async-swe-agents
export ENV_FILE="$PWD/.env.my-model"
export MODEL_TAG=my-model
export RUN_ID=async_manager_v1_s1
bash scripts/run_async_manager_env.sh cachetools
```

TVM uses the same entry point:

```bash
bash scripts/run_async_manager_env.sh pr-hard:apache-tvm-20153
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
  RUN_ID=async_manager_v1_s1 bash scripts/run_async_manager_20tasks_env.sh

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
./.venv/bin/python -m async_manager_extension.campaign \
  --root outputs \
  --run-id async_manager_v1_s1 \
  --output-dir ../../docs/results/async_manager_v1_s1 \
  --require-complete
```

This writes JSON, CSV, and Markdown with FSR, macro/micro ADPR, normalized
penalized DRS/SCS, normalized RC, tokens, runtime, and intervention counts. The
direction of every paper-facing aggregate is included in the output.

Formal execution rejects an uncommitted extension, any dirty execution-critical
harness source, or any difference in frozen protocol paths relative to commit
`547a84e618a2338f3b7bd30cd976d582c42e661c`.

## Result contract

The standard run artifacts remain present. Additional evidence includes:

- `async_manager_profile_snapshot.json`
- `manager_interventions.jsonl`
- `manager_interventions/NNNN.prompt.txt`
- `manager_interventions/NNNN.patch`
- `extension_sources/`

Bundles use protocol `async_manager`, policy `async-manager-online-v1`, and are
excluded from the frozen four-protocol aggregate. They are eligible for the
separate Async-Manager comparison when validation succeeds.
