# AsynCodeBench Execution Protocols

This directory implements the protocol layer used by the native
AsynCodeBench harness. The public runner is `../run_asyncodebench.py`; it
accepts only `asyncodebench:<task>` identifiers and loads each protocol's
assignment, scope, dependency, evaluator, and probe contracts from the release
manifests.

Use the model-neutral wrapper to run all four conditions:

```bash
MODEL_TAG=<model-tag> RUN_VERSION=official_v01 \
  ../scripts/run_asyncodebench_all_protocols_env.sh cachetools
```

The four `--protocol` values are:

- `single`: one iterative agent owns the complete task.
- `serial_specialists`: specialists run in dependency order and receive merged
  upstream handoffs.
- `async_private`: specialists begin from the same base in private worktrees;
  their artifacts are integrated after independent execution.
- `caid_manager`: a read-only manager delegates, reviews, and integrates
  scope-validated specialist artifacts under the AsynCodeBench manifest gates;
  only specialists may modify production code in their private worktrees.

`static_commit0.py` and the `run_commit0_*` scripts are retained only for
historical v1 reproduction. They are not public entry points for new official
AsynCodeBench results.
