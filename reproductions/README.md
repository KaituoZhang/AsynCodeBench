# Reproductions

This directory keeps third-party repositories used for reproduction studies,
separate from AsyncCodeBench's own benchmark code, data manifests, and runner
implementations.

## Current repositories

### `async-swe-agents/`

- Upstream: <https://github.com/JiayiGeng/async-swe-agents>
- Local path: `reproductions/async-swe-agents/`
- Checked commit at clone time: `f364d9e`
- Purpose: reproduce CAID single-agent and multi-agent experiments on
  Commit0/Commit0-Lite first, then evaluate whether its workflow can be reused
  or adapted for AsyncCodeBench.

Notes:

- This is a standalone third-party repository with its own `pyproject.toml`,
  `uv.lock`, scripts, prompts, and task modules.
- Do not mix AsyncCodeBench-native source files into this directory.
- If we need adapters for AsyncCodeBench, place them in AsyncCodeBench-native
  folders first and only patch this third-party repo when necessary for a
  clearly documented reproduction or compatibility reason.

