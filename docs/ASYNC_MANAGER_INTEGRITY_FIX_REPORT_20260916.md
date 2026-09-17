# Async-Manager integrity repair for fresh reruns

Profile revision: `immutable-artifacts-event-safe-20260916`.
Policy remains `async-manager-online-v2-budgeted`; use a new campaign RUN_ID.

## Scope

Only the Async-Manager package, its entry point, dedicated tests and documentation
are changed. Frozen shared engines, other protocols, task adapters, manifests,
evaluation commands and historical results are not changed.

## Repairs

| Audited problem | New behavior |
| --- | --- |
| Inherited producer paths attributed to a consumer | Scope checks use the merge-base delta of an immutable commit, not cumulative `files_modified`. |
| Uncommitted scratch rejects a valid commit | Dirty state is archived separately. Only committed content is merged; unfinished scoped work can be recovered through an isolated index. |
| Moving branch checked and merged at different tips | One resolved commit SHA is used throughout validation and merge. |
| Checkpoint failure leaves a pending event | Consume before checkpoint I/O; journal the failure and allow subsequent results to proceed. Abandoned pending events are flushed explicitly. |
| Intervention exceptions create sequence gaps | Persist an explicit failure record. Failed or incomplete events remain ineligible, not fabricated as successful checkpoints. |
| Missing events admitted by result validation | New profiles require checkpoint/event/artifact coverage and reject harness-error records. |
| Invalid bundles pollute aggregate scores | Exclude them from metrics, preserve the issue list, and label validated subsets. Duplicate tasks and mixed profiles are not pooled into a score. |
| Refresh loses staged or untracked work | Archive all Git layers plus an untracked-file tarball and checksums before reset/clean. Archive failure prevents cleanup. |
| Accepted partial repair triggers a blind reset/retry | Preserve unmerged specialist work. Only passing manifest primary tests can mark manager-assisted delivery fulfilled and bypass automatic retry. Original merge outcome stays recorded. |
| Test worktree differs from staged candidate | Require a clean index/worktree relationship before and after validation; record and recheck the staged tree before commit. |
| Directory scopes omitted from affected dependencies | Use the same descendant-aware path matching as scope authorization. |
| TVM source and manager runtime diverge | Refresh native builds after synchronization and before manager test commands; candidate validation still builds independently. |
| Shell policy imported from another checkout | Vendor the policy inside Async-Manager; reject foreign runtime module origins and snapshot their hashes. |
| Manager timeout leaks to concurrent specialists | Use an execution-context-local override instead of process-global environment mutation. |
| Unknown remote state reported as stopped | Require an explicit terminal state; retain private work when shutdown is unconfirmed. |

## Verification

Final local verification: **278 tests passed**, including both real-pytest gate
cases; scoped Ruff checks and `git diff --check` also passed.

Run from `reproductions/async-swe-agents`:

```bash
LITELLM_LOCAL_MODEL_COST_MAP=True OPENHANDS_SUPPRESS_BANNER=1 \
  PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests
```

The two real-pytest gate tests additionally need `pytest-json-report`. Set
`ASYNC_MANAGER_AUDIT_PYTHON` to a benchmark runtime interpreter containing that
plugin if the host development environment does not have it. The remaining
tests need neither a model API nor a GPU. The repair was also checked with the
existing PR-hard interpreter, exercising real Git and pytest report parsing for
both an accepted candidate and a regressing candidate.

Startup dry-runs were checked for a core Python task and a TVM task. A local TVM
dry-run requires an explicit existing `--runtime_root`; a container-backed
launch uses the existing launcher settings instead.

The frozen execution paths were compared against
`73c9877315c920867ba72750826b66421be08bc0`, and task/evaluation/manifest paths
against the pre-repair `56c4ab5`, with no differences.

## Boundaries

- Manager limits remain 30 responses/event, 100/task, 6 interventions,
  7,200 active seconds/event, 21,600/task, and the existing 8M-token inter-event
  guard. These are not a promise of a fixed end-to-end wall-clock runtime.
- No model generation campaign was started and no old result was rewritten.
- CPU tests and startup checks do not establish real-model success rates or
  cover a full TVM compilation campaign. Run a small new-ID smoke experiment
  before allocating the entire rerun budget.
- Recovery cannot reconstruct a missed manager intervention or undo a past
  reasoning trajectory. Such runs must remain distinct from a fresh rerun.
