# Reproductions

This directory contains the executable agent harness used to reproduce the
official AsynCodeBench protocol conditions.

## `async-swe-agents/`

This is the AsynCodeBench-native harness. It was derived from the CAID
`async-swe-agents` codebase at upstream commit `f364d9e`, then adapted to the
released 19-task manifests, five protocol definitions, immutable task images,
dependency probes, result bundles, and integrity checks in this repository.

Use its public `asyncodebench` CLI or the documented wrappers. Historical
Commit0 and PaperBench pilot launchers are not part of the community runtime.
See [`async-swe-agents/README.md`](async-swe-agents/README.md) for installation
and execution instructions.

`software-agent-sdk.lock` records the exact OpenHands SDK source revision used
by the harness. The SDK checkout itself is materialized locally by
`scripts/setup_evaluation.sh` and is intentionally not committed.
