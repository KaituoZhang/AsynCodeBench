# OpenHands Runtime Consistency

AsynCodeBench uses OpenHands on both sides of a remote conversation:

- the host-side runner imports `openhands-sdk`, `openhands-workspace`, and
  related client packages;
- each Docker workspace runs an OpenHands agent server built from the source
  checkout pinned by `reproductions/software-agent-sdk.lock`.

These components must use one source revision and one event schema. A nominally
working HTTP connection is not sufficient. For example, an OpenHands 1.29
server emits `SystemPromptEvent.dynamic_context`, while a 1.11 client rejects
that field with `Extra inputs are not permitted`. The model is never reached,
and the resulting zero-iteration run is infrastructure-invalid.

## Locked Runtime

The runner dependencies in
`reproductions/async-swe-agents/pyproject.toml` are resolved as editable path
dependencies from the exact checkout recorded in
`reproductions/software-agent-sdk.lock`. This keeps the host client and Docker
server on the same source revision, including development commits whose source
version may not uniquely identify the revision.

Run the supported setup command from the repository root:

```bash
bash scripts/setup_evaluation.sh
```

It performs three runtime gates before tests:

1. materializes the exact locked SDK commit and rejects a dirty checkout;
2. verifies declared, installed, and source package versions plus the actual
   host import path and `SDK_SOURCE_DIR` used to build the Docker server;
3. sends a `SystemPromptEvent` containing `dynamic_context` across a live local
   HTTP process boundary and validates it with the host client schema.

The same consistency check runs before every non-dry-run campaign wrapper and
in CI. Run the gates manually with:

```bash
reproductions/async-swe-agents/.venv/bin/python \
  scripts/check_openhands_runtime_consistency.py --require-clean

reproductions/async-swe-agents/.venv/bin/python \
  scripts/smoke_openhands_event_roundtrip.py
```

## Existing Or Modified SDK Checkout

Formal runs require a clean SDK checkout because unrecorded SDK patches would
change the agent implementation without changing the benchmark Git revision.
Do not reset or delete local SDK work. Preserve it, then materialize the lock:

```bash
cd /absolute/path/to/AsynCodeBench/reproductions
mv software-agent-sdk software-agent-sdk.local-patches-backup
cd ..
python3 scripts/materialize_openhands_sdk.py --require-clean

cd reproductions/async-swe-agents
uv sync --frozen --extra dev --python 3.12
```

Use a unique backup name if that path already exists. The backup is not used by
formal runs but preserves any local changes for later review.

## Result Admission

`inspect-run` and `validate-run` reject:

- `termination_reason=execution_error`;
- an observed run that records zero model iterations;
- the `dynamic_context` event-schema mismatch;
- the existing transport, provider, context-window, and evaluator
  instrumentation failures.

These are infrastructure-invalid attempts and may be rerun under a new run ID.
They are not coding failures and must not be included in aggregate scores.
