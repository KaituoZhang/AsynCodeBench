# Historical CAID+Repair Ablation

This directory preserves the manager-writable CAID condition used by the
frozen Qwen3.6-27B campaign. It is an ablation of the current primary
`caid_manager` condition, whose manager is read-only.

## What this condition measures

In the historical `CAID+Repair` condition, the manager has the normal
OpenHands tool set, including the file editor. The manager can therefore
inspect specialist artifacts and directly repair the integrated repository
during final review. Specialist artifacts were intended to follow the declared
role assignments and the merge gates implemented by the historical harness.

This condition asks whether giving the coordination plane an additional repair
capability can mitigate failed handoffs and incomplete integration. It does not
isolate coordination alone: manager-authored implementation is an additional
source of coding work, context, and model tokens.

The current official `CAID-RO` condition instead permits the manager to plan,
inspect, test, provide feedback, reassign, and integrate accepted artifacts,
but not to author production changes. `CAID-RO` remains the primary condition.

## Frozen-result qualification

The selected historical campaign contains 20 task cells and is immutable. Its
canonical index is
[`docs/results/qwen36_27_frozen_result_index.v1.json`](../../docs/results/qwen36_27_frozen_result_index.v1.json).
The index pins the selected run paths and artifact checksums. When the local
raw-result collection is present, each selected `run_bundle.json` additionally
records the exact runner revision, model configuration, prompt hash, task
snapshot, scenario snapshot, evaluator, and artifact checksums. The large raw
output directories are not stored in GitHub; they remain a separately
archived result collection.

This is a historical ablation rather than a perfectly controlled 20-task
single-variable experiment:

- 19 task cells used a manager with write/repair access;
- `apache-tvm-20018` already used the task-specific read-only manager guard;
- the selected task cells span three runner revisions, as recorded in
  [`manifest.json`](manifest.json);
- all three revisions predate the later private-worktree and control-plane
  hardening, so current isolation guarantees must not be projected backward
  onto these trajectories.

Consequently, the frozen results may support the descriptive statement that
manager-side repair can mitigate some coordination failures. A causal
`CAID-RO` versus `CAID+Repair` claim requires matched reruns on one frozen
harness revision, with the same tasks, model, seed, budgets, and endpoint
configuration.

## Reconstructing the historical harness

Do not reset the current checkout. Create a detached Git worktree containing
the revision used by a selected task:

```bash
cd /path/to/AsyncCodeBench
./ablations/caid_manager_repair_v1/prepare_worktree.sh portalocker \
  ../AsyncCodeBench-caid-repair-portalocker
```

For a TVM example:

```bash
./ablations/caid_manager_repair_v1/prepare_worktree.sh apache-tvm-20153 \
  ../AsyncCodeBench-caid-repair-tvm20153
```

The helper resolves the exact task-specific runner revision from
`manifest.json`, verifies that the commit exists, and uses `git worktree add
--detach`. Existing directories are never overwritten. Follow the runbook at
that historical revision and always choose a new `RUN_VERSION`; frozen output
directories are immutable.

To remove only the detached source checkout after use:

```bash
git -C /path/to/AsyncCodeBench worktree remove \
  /path/to/AsyncCodeBench-caid-repair-portalocker
```

This does not remove Docker images, model caches, or frozen result bundles.

## Verification

From the repository root, verify the frozen index, per-task revision mapping,
and indexed artifact hashes:

```bash
python ablations/caid_manager_repair_v1/verify_frozen_runs.py
```

The verifier is read-only. In a normal GitHub clone it validates the canonical
index and its complete 20-task revision mapping. On the machine that contains
the raw result collection, require and hash-check every selected bundle with:

```bash
python ablations/caid_manager_repair_v1/verify_frozen_runs.py \
  --require-bundles
```

Strict verification fails if a selected CAID bundle is missing, if its
recorded runner revision disagrees with this manifest, or if an indexed
artifact checksum no longer matches.

## Recommended paper terminology

Use these distinct labels:

- **CAID-RO (primary):** read-only manager; specialist artifacts are the only
  source of production changes.
- **CAID+Repair (historical ablation):** manager may directly repair the
  integrated repository; 19 writable-manager cells plus the documented
  `apache-tvm-20018` read-only exception.

Do not merge the two result populations under an unqualified `CAID` label.
