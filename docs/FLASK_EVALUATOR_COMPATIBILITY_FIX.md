# Flask Evaluator Compatibility Fix

> **Historical v1 compatibility note.** New official Flask runs use
> `asyncodebench:flask` through `run_asyncodebench.py` or
> `scripts/run_asyncodebench_all_protocols_env.sh`. The legacy commands below
> document the original evaluator investigation only.

This note records the Flask-specific evaluator issue we hit while running
AsynCodeBench with `gpt-5.4-mini`, so future runs do not waste API budget on
invalid Flask outputs.

## Scope

Task: `asyncodebench:flask`

Curated source:

- base ref: `origin/commit0_combined`
- base SHA: `af126af63a288df1d4edfe07e82a3b241aa4567a`
- curated overlay count after the fix: `11`

This fix is an evaluator/bootstrap compatibility change only. It does not
modify Flask implementation files and does not provide solution behavior.

## What Went Wrong

The Flask public tests use `tests/conftest.py` to reset environment variables
between tests. The original curated tree referenced pytest's private
`_pytest.monkeypatch.notset` package-level export.

Across pytest minor versions, that private export is unstable:

- some environments expose `_pytest.monkeypatch.notset`;
- others expose `_pytest.monkeypatch.NOTSET`;
- using a plain `object()` replacement is incorrect because
  `pytest.MonkeyPatch.undo()` expects pytest's real missing-value sentinel.

This caused invalid multi-agent runs:

- `v01`: setup failed with
  `AttributeError: module '_pytest.monkeypatch' has no attribute 'notset'`;
- `v02`: setup failed with `TypeError: str expected, not object`.

Both `v01` and `v02` Flask multi-agent results should be excluded from formal
analysis.

## Fix

The added overlay is:

```text
data/overlays/commit0/flask/0011-conftest-monkeypatch-sentinel-bootstrap.patch
```

It changes `tests/conftest.py` to import pytest's real sentinel with a
minor-version fallback:

```python
try:
    from _pytest.monkeypatch import notset as _missing_env
except ImportError:
    from _pytest.monkeypatch import NOTSET as _missing_env
```

Then the fixture uses `pytest.MonkeyPatch()` and `_missing_env`.

This keeps pytest's internal undo semantics intact while avoiding dependence on
one unstable private export name.

## Validation

Run the Flask contract gates from the repository root:

```bash
cd /absolute/path/to/AsynCodeBench
PYTHONPATH=/absolute/path/to/AsynCodeBench/src \
  /absolute/path/to/AsynCodeBench/reproductions/async-swe-agents/.venv/bin/python \
  -m pytest tests/contracts/test_flask_dataset_v03.py \
  tests/contracts/test_flask_async_metrics_v03.py -q
```

Expected result:

```text
7 passed
```

Dry-run should report `overlays=11`:

```bash
cd /absolute/path/to/AsynCodeBench/reproductions/async-swe-agents
source scripts/env.sh
unset ASYNCODEBENCH_DISABLE_CURATED_TASK_SOURCE

uv run python run_static_protocol.py \
  --task commit0 \
  --protocol serial_specialists \
  --repo flask \
  --model "$LLM_MODEL" \
  --max_subagents 4 \
  --sub_iterations 2 \
  --dataset_path "$COMMIT0_DATASET_PATH" \
  --output_dir outputs/repro_commit0/flask/smoke_serial_dryrun_v03 \
  --dry_run
```

## Valid Run Version

For formal Flask experiments, use `v03` or later. Do not use `v01` or `v02`.

Recommended run tags:

```bash
TASK=flask
RUN_TAG=gpt54mini
RUN_VERSION=v03
```

Use the standard four-mode commands:

```bash
MAX_ITERATIONS=30 \
OUTPUT_DIR="outputs/repro_commit0/${TASK}/${RUN_TAG}_single_i30_curated_${RUN_VERSION}" \
scripts/run_commit0_single_env.sh "$TASK"

MAX_SUBAGENTS=4 SUB_ITERATIONS=30 \
OUTPUT_DIR="outputs/repro_commit0/${TASK}/${RUN_TAG}_serial_4agents_s30_curated_${RUN_VERSION}" \
scripts/run_commit0_serial_env.sh "$TASK"

MAX_SUBAGENTS=4 SUB_ITERATIONS=30 \
OUTPUT_DIR="outputs/repro_commit0/${TASK}/${RUN_TAG}_async_private_4agents_s30_curated_${RUN_VERSION}" \
scripts/run_commit0_async_private_env.sh "$TASK"

MAX_ITERATIONS=30 \
MAX_SUBAGENTS=4 \
SUB_ITERATIONS=30 \
ROUNDS_OF_CHAT=2 \
OUTPUT_DIR="outputs/repro_commit0/${TASK}/${RUN_TAG}_caid_multi_4agents_m30_s30_curated_${RUN_VERSION}" \
scripts/run_commit0_multi_env.sh "$TASK"
```

## Interpreting Current v03 Results

The current `gpt-5.4-mini` Flask `v03` run is valid for analysis, but it is a
hard failure case for multi-agent modes:

- single: `241/244` tests pass, final ADPR is `1.0`;
- serial specialists: `42/244` tests pass, final ADPR is `0.0`;
- async private: `1/244` tests pass, final ADPR is `0.0`;
- CAID multi-agent: `1/244` tests pass, final ADPR is `0.0`.

This is not a pytest fixture failure anymore. It shows that the multi-agent
runs did not integrate the Flask producer-consumer dependency contracts, while
the single-agent run resolved all three dependency points despite one remaining
edge-case test failure.
