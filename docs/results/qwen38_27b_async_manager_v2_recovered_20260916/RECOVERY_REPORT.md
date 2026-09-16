# Qwen3.8-27B Async-Manager Recovery Report

Recovery completed on 2026-09-16 after all 20 selected task executions reached
a terminal state.

## Outcome

- Selected tasks: 20/20
- Standard bundle validation: 20/20 valid
- Final task success: 9/20 (45.0%)
- Macro ADPR: 55.83%
- Micro ADPR: 60.00%
- Mean final evaluator pass rate: 76.99%
- Mean tokens per task: 14.21M
- Mean runtime per task: 3.94 hours

The machine-readable campaign validator completed with `valid=true` and
`--require-complete`.

## Finalizer recovery

Eleven revision-`6b5a2fe` runs completed model execution, final evaluation,
manager shutdown, and process/dependency metric generation, but the v2
finalizer delegated bundle construction to the legacy v1 helper. The helper
rejected the valid v2-only `budget_exhausted` intervention status and the
runner wrote a partial bundle with:

```text
Async-Manager result validation failed: manager_intervention_status_invalid
```

The fix is commit `d0164e7` (`Fix budgeted Async-Manager bundle
finalization`). The v2 finalizer now calls the shared policy-neutral bundle
builder after v2 validation; the legacy validator remains unchanged.

Before recovery, every source partial was required to satisfy all of the
following:

- the error exactly matched the known finalizer failure;
- every partial-inventory size and SHA-256 matched;
- all standard, manager-budget, shutdown, evaluator, and dependency artifacts
  were present;
- manager shutdown was confirmed;
- manager usage satisfied the recorded limits and ended at the task-level
  iteration cap.

Recovery copied each source into a new `_recovered` directory. Original
partial directories were not edited. Each recovered directory preserves its
original partial bundle, execution error, and run status under
`finalizer_recovery/`, and records `model_rerun=false` and
`evaluator_rerun=false` in `finalizer_recovery.json`.

Recovered tasks:

- requests
- flask
- graphene
- imapclient
- marshmallow
- pexpect
- python-rsa
- apache-tvm-20018
- apache-tvm-20073
- apache-tvm-20107
- apache-tvm-20153

All 11 recovered bundles passed an independent standard-bundle validation.
The relevant regression suite completed with 66 tests passing.

## Provenance scope

This is a valid selected/recovered 20-task result set, but it is not a
lineage-homogeneous v2 campaign. Per the predeclared reuse decision, four
already completed tasks retain policy `async-manager-online-v1`:

- deprecated
- tinydb
- simpy
- parsel

The remaining 16 tasks record policy `async-manager-online-v2-budgeted`.
Consequently, the aggregate is suitable for the planned mixed-lineage
descriptive comparison, but it must not be labeled as a homogeneous v2 causal
campaign unless those four retained tasks are rerun under v2.

## Generated artifacts

- `async_manager_campaign_summary.json`: complete machine-readable summary and
  source directory selection
- `async_manager_task_metrics.csv`: task-level metrics
- `async_manager_campaign_summary.md`: compact aggregate table
