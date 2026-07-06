# Codex Onboarding For AsyncCodeBench

This document is for a new Codex session or collaborator-side coding agent.
Read it before modifying files or running experiments.

## First Read These Files

Read in this order:

1. `README`
2. `SPECIFICATION_v0.3.md`
3. `docs/COLLABORATOR_RUNBOOK.md`
4. `docs/AGENT_EXPERIMENT_RUNBOOK.md`
5. `docs/EVALUATION_METRICS.md`
6. `docs/MODEL_EXPERIMENT_RUNBOOK.md`
7. `docs/GITHUB_COLLABORATOR_HANDOFF.md`
8. `docs/protocols/COMMIT0_DATA_AND_METRIC_LABEL_GUIDE_v0.3.md`
9. `docs/protocols/README.md`
10. `skills/commit0-to-asynccodebench/SKILL.md`
11. `reproductions/async-swe-agents/protocols/README.md`

If the task is about paper writing or methodology, also read:

```text
docs/design/paper_structure_reference.md
docs/design/COMMIT0_TO_ASYNCCODEBENCH_PIPELINE_v0.1.md
```

## Project Summary

AsyncCodeBench transforms public executable coding benchmark tasks into
dependency-aware asynchronous multi-agent benchmark instances.

The central transformation is:

```text
public coding task
-> natural subproblem identification
-> producer/consumer dependency labels
-> async scenario manifests
-> dependency-level metrics
-> automatic validation gates
-> human annotation and adjudication
```

The benchmark evaluates whether asynchronous software-agent teams can resolve
cross-agent implementation dependencies under private workspaces, delayed
visibility, stale assumptions, and late integration.

## Current Data Status

The current v0.3 release set contains:

- 17 official Commit0-derived tasks for current experiments;
- retained non-official artifacts under
  `archive/non_official/commit0_v0.3/` for audit/history;
- excluded candidates: `fabric`, `fastapi`, and `python-progressbar`;
- non-official scratch/stress candidate retained for audit: `chardet`.

The current qualification-ready experimental set is:

```text
cachetools
cookiecutter
deprecated
dulwich
filesystem_spec
flask
graphene
imapclient
marshmallow
parsel
pexpect
portalocker
python-rsa
requests
simpy
tinydb
wcwidth
```

Do not treat `chardet`, `fastapi`, `python-progressbar`, or `fabric` as
current release tasks without explicit human approval.

## Key Directories

```text
configs/tasks/                         # curated task metadata
data/overlays/commit0/                 # checksum-pinned bootstrap overlays
docs/protocols/                        # construction and annotation protocol
manifests/pilot/v0.3/tasks/            # task manifests
manifests/pilot/v0.3/scenarios/        # execution scenario manifests
manifests/pilot/v0.3/quality/          # quality records
manifests/pilot/v0.3/metrics/          # async metrics manifests
manifests/annotations/commit0_v0.3/    # human annotation forms
skills/commit0-to-asynccodebench/      # reusable construction skill
src/asynccodebench/                    # Python library code
tests/contracts/                       # artifact validation tests
reproductions/async-swe-agents/        # CAID-based agent runner
```

## Agent Runner Protocols

The executable agent protocols live under:

```text
reproductions/async-swe-agents/
```

There are four current experiment conditions:

| Protocol | Script |
| --- | --- |
| Single agent | `scripts/run_commit0_single_env.sh` |
| Serial specialists | `scripts/run_commit0_serial_env.sh` |
| Async private workspace | `scripts/run_commit0_async_private_env.sh` |
| CAID manager-mediated multi-agent | `scripts/run_commit0_multi_env.sh` |

The static specialist protocols are implemented in:

```text
reproductions/async-swe-agents/run_static_protocol.py
reproductions/async-swe-agents/protocols/static_commit0.py
```

The existing CAID/single-agent workflow is implemented in:

```text
reproductions/async-swe-agents/run_infer.py
reproductions/async-swe-agents/core/manager.py
reproductions/async-swe-agents/core/subagent.py
```

## LLM And API Configuration

The base LLM, API key, API endpoint, and optional subagent model are configured
only in the agent runner environment file:

```text
reproductions/async-swe-agents/.env
```

Do not commit `.env`. Commit only example files such as `.env.example`.

The template is:

```text
reproductions/async-swe-agents/.env.example
```

The scripts load `.env` through:

```text
reproductions/async-swe-agents/scripts/env.sh
```

Required variables:

```bash
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_API_KEY=YOUR_KEY
LLM_MODEL=openai/gpt-5.4-mini
LLM_SUBAGENT_MODEL=
COMMIT0_DATASET_PATH=/absolute/path/to/commit0_combined
SDK_SOURCE_DIR=/absolute/path/to/Asynccodebench/reproductions/software-agent-sdk
```

To change the base model, change:

```bash
LLM_MODEL=<provider/model-id>
```

Examples:

```bash
LLM_MODEL=openai/gpt-5.4-mini
LLM_MODEL=anthropic/claude-sonnet-4.6
LLM_MODEL=qwen/qwen3.7-plus
LLM_MODEL=z-ai/glm-4.5
```

To use a cheaper model for subagents while keeping a stronger manager model,
set:

```bash
LLM_MODEL=<manager-model>
LLM_SUBAGENT_MODEL=<subagent-model>
```

If `LLM_SUBAGENT_MODEL` is empty, the runner uses `LLM_MODEL` for all agents.

The Python code that consumes these values is:

```text
reproductions/async-swe-agents/core/utils.py::build_llm_kwargs
reproductions/async-swe-agents/run_infer.py
reproductions/async-swe-agents/run_static_protocol.py
```

## Environment Setup

Top-level AsyncCodeBench validation can use conda:

```bash
conda create -n asynccodebench python=3.10 -y
conda activate asynccodebench
python -m pip install -U pip
python -m pip install -e ".[dev]"
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q tests/contracts
```

The agent runner uses `uv` because `reproductions/async-swe-agents` has its own
`pyproject.toml` and `uv.lock`:

```bash
cd reproductions/async-swe-agents
uv sync
```

The agent runner also needs:

```text
Docker access
OpenHands software-agent-sdk checkout
Commit0 dataset path loadable by datasets.load_from_disk
LLM API credentials
```

See `docs/COLLABORATOR_RUNBOOK.md` for full installation commands.

## Smoke Tests

From `reproductions/async-swe-agents/`:

```bash
uv run python run_static_protocol.py --protocol serial_specialists --repo cachetools --dry_run
uv run python run_static_protocol.py --protocol async_private --repo cachetools --dry_run
```

Then run low-budget real tests:

```bash
MAX_ITERATIONS=5 SUB_ITERATIONS=5 scripts/run_commit0_single_env.sh cachetools
MAX_SUBAGENTS=2 SUB_ITERATIONS=5 scripts/run_commit0_serial_env.sh cachetools
MAX_SUBAGENTS=2 SUB_ITERATIONS=5 scripts/run_commit0_async_private_env.sh cachetools
MAX_ITERATIONS=5 MAX_SUBAGENTS=2 SUB_ITERATIONS=5 scripts/run_commit0_multi_env.sh cachetools
```

## Output Files

Agent outputs are written under:

```text
reproductions/async-swe-agents/outputs/
```

Important outputs:

```text
report.json
cost.json
runtime.txt
patch.diff
outputs.jsonl
agent_events/
final_repo/<repo>.tar.gz
```

Do not commit outputs.

## Editing Rules For Codex

Follow these rules unless the user explicitly says otherwise:

- Do not modify existing task artifacts unless the task is specifically about
  that artifact.
- Do not change already accepted task data while adding a new task.
- Do not add solution code into bootstrap overlays.
- Do not commit `.env`, outputs, materialized repos, or API keys.
- Prefer adding documentation or new runner files over changing working
  validated paths.
- If changing the agent runner, preserve existing single-agent and CAID
  behavior unless the user explicitly asks to alter it.
- Run validation after changes:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q tests/contracts
python3 -m py_compile reproductions/async-swe-agents/run_static_protocol.py \
  reproductions/async-swe-agents/protocols/static_commit0.py
```

## Common User Requests

If asked to process a new task, use:

```text
skills/commit0-to-asynccodebench/SKILL.md
```

If asked to run or debug experiments, start from:

```text
docs/COLLABORATOR_RUNBOOK.md
reproductions/async-swe-agents/protocols/README.md
```

If asked to explain the paper story, start from:

```text
docs/design/paper_structure_reference.md
```
