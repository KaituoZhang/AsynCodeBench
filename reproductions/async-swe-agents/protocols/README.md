# AsyncCodeBench Execution Protocols

This directory contains the additional static execution protocols used for AsyncCodeBench.

Existing CAID entrypoints are kept unchanged:

- Single-agent baseline: `scripts/run_commit0_single_env.sh`
- Manager-mediated CAID multi-agent: `scripts/run_commit0_multi_env.sh`

New manifest-driven static protocols:

- Synchronous specialist handoff: `scripts/run_commit0_serial_env.sh`
- Asynchronous private workspace: `scripts/run_commit0_async_private_env.sh`

Both new protocols read the AsyncCodeBench scenario manifest:

```text
../../../manifests/pilot/v0.3/scenarios/commit0_<repo>.json
```

The runner selects the scenario by `execution_mode`:

- `serial_specialists`: specialists run one at a time. Each downstream specialist starts from the merged upstream workspace.
- `async_private`: specialists start concurrently from the same base commit in isolated worktrees. Their patches are merged only after all specialists finish.

The new protocols reuse CAID's existing OpenHands subagent runner, worktree setup, merge logic, pytest evaluation, patch export, final repo tarball export, and cost logging. They do not call the CAID manager's scan/delegate/reassign loop.

Example dry runs:

```bash
uv run python run_static_protocol.py --protocol serial_specialists --repo cachetools --dry_run
uv run python run_static_protocol.py --protocol async_private --repo cachetools --dry_run
```

Example full runs:

```bash
scripts/run_commit0_serial_env.sh cachetools
scripts/run_commit0_async_private_env.sh cachetools
```

