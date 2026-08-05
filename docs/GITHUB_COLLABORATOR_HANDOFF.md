# GitHub Collaborator Handoff

This document explains how to prepare the repository for collaborators and how
they should start running new-model AsyncCodeBench experiments after cloning.

## What This Branch Should Contain

Commit these project assets:

```text
README
SPECIFICATION_v0.3.md
configs/
data/README.md
data/overlays/
docs/
environment.yml
manifests/
pipelines/
pyproject.toml
reproductions/README.md
reproductions/async-swe-agents/
schemas/
scripts/
skills/
src/
tests/
```

Do not commit local/runtime assets:

```text
.env
.env.*
.venv/
outputs/
data/external/
data/interim/
data/processed/
data/raw/
data/repos/
reproductions/async-swe-agents/outputs/
reproductions/async-swe-agents/data/
reproductions/async-swe-agents/.venv/
reproductions/software-agent-sdk/
```

The checked-in `data/overlays/` directory is intentional. These files are
checksum-pinned non-solution bootstrap overlays needed by some curated tasks.

## Current Official Experiment Set

The current official v0.3 model-comparison set has 17 tasks:

```text
cachetools
deprecated
portalocker
tinydb
wcwidth
requests
simpy
dulwich
parsel
filesystem_spec
marshmallow
graphene
imapclient
pexpect
flask
python-rsa
cookiecutter
```

Do not include these in official aggregate tables:

```text
fastapi
python-progressbar
fabric
chardet
```

## Where The Dataset Lives

AsyncCodeBench's versioned dataset metadata lives in the repository:

```text
configs/tasks/commit0_curated_tasks.v0.3.json
manifests/pilot/v0.3/tasks/
manifests/pilot/v0.3/scenarios/
manifests/pilot/v0.3/metrics/
manifests/pilot/v0.3/quality/
data/overlays/commit0/
```

The large raw/local datasets are not committed. The agent runner still needs a
local HuggingFace `load_from_disk` Commit0 dataset path:

```text
COMMIT0_DATASET_PATH=/absolute/path/to/commit0_combined
```

For the current server, this has usually been:

```text
/home/kzhang42/AsyncCodeBench/data/external/commit0_combined
```

Collaborators should set their own local path in
`reproductions/async-swe-agents/.env.<model_tag>`.

## Where The Four Agent Modes Live

The runner source is:

```text
reproductions/async-swe-agents/
```

The four protocol entry points are:

| Protocol | Script |
| --- | --- |
| Single agent | `reproductions/async-swe-agents/scripts/run_commit0_single_env.sh` |
| Serial specialists | `reproductions/async-swe-agents/scripts/run_commit0_serial_env.sh` |
| Async private workspaces | `reproductions/async-swe-agents/scripts/run_commit0_async_private_env.sh` |
| CAID manager-mediated multi-agent | `reproductions/async-swe-agents/scripts/run_commit0_multi_env.sh` |

Static specialist implementation:

```text
reproductions/async-swe-agents/run_static_protocol.py
reproductions/async-swe-agents/protocols/static_commit0.py
```

Single-agent and CAID implementation:

```text
reproductions/async-swe-agents/run_infer.py
reproductions/async-swe-agents/core/manager.py
reproductions/async-swe-agents/tasks/commit0.py
```

## Collaborator Fresh Clone

```bash
git clone --branch agent/reproducible-model-evaluation --single-branch \
  https://github.com/KaituoZhang/Asynccodebench.git
cd Asynccodebench
```

Start with `docs/EVALUATION_BRANCH_QUICKSTART.md`. It is the concise operational
entry point; the longer runbooks linked there explain model-specific serving,
metrics, and failure classification.

Install the top-level validation environment:

```bash
conda create -n asynccodebench python=3.10 -y
conda activate asynccodebench
python -m pip install -U pip
python -m pip install -e ".[dev]"
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q tests/contracts
```

Install the agent runner:

```bash
cd reproductions/async-swe-agents
uv sync
```

The runner also requires:

```text
Docker access
OpenHands software-agent-sdk checkout
local Commit0 dataset path
LLM API credentials
```

If `software-agent-sdk` is not already available:

```bash
cd /path/to/Asynccodebench/reproductions
git clone https://github.com/OpenHands/software-agent-sdk.git
```

Then configure:

```bash
cd /path/to/Asynccodebench/reproductions/async-swe-agents
cp .env.example .env.<model_tag>
```

Required `.env.<model_tag>` fields:

```bash
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_API_KEY=YOUR_PROVIDER_KEY
LLM_MODEL=<provider/model-id>
LLM_SUBAGENT_MODEL=
COMMIT0_DATASET_PATH=/absolute/path/to/commit0_combined
SDK_SOURCE_DIR=/absolute/path/to/Asynccodebench/reproductions/software-agent-sdk
```

Load the model environment:

```bash
export ENV_FILE="$PWD/.env.<model_tag>"
source scripts/env.sh
unset ASYNCCODEBENCH_DISABLE_CURATED_TASK_SOURCE
unset ASYNCCODEBENCH_DISABLE_CURATED_TASK_CONFIG
unset ASYNCCODEBENCH_DISABLE_MANIFEST_EVALUATOR
```

## Main Runbook For New Models

After setup, use:

```text
docs/MODEL_EXPERIMENT_RUNBOOK.md
```

For a locally served OpenAI-compatible model, read this before starting vLLM:

```text
docs/LOCAL_VLLM_EXPERIMENT_RUNBOOK.md
```

That document contains:

- the official 17-task list;
- `MAX_SUBAGENTS` for each task;
- smoke-test commands;
- commands for all four agent modes;
- post-run metric commands;
- aggregate table guidance;
- official-result acceptance checks.

## Before Pushing To GitHub

Check for sensitive or oversized files:

```bash
git status --short
git ls-files | rg '(^|/)\\.env($|\\.)|(^|/)outputs/|data/external|data/raw|data/interim|data/processed|data/repos|software-agent-sdk' || true
```

The second command should not list API keys, raw data, runtime output
directories, local repositories, or external checkouts. If it does, remove the
file from the Git index before pushing.

Use the dedicated evaluation branch:

```bash
git switch -c agent/reproducible-model-evaluation
git add README data/README.md docs configs manifests schemas scripts skills src tests
git add reproductions/README.md reproductions/async-swe-agents
git status --short
git commit -m "Prepare collaborator model experiment runbook"
git push -u origin agent/reproducible-model-evaluation
```

If `reproductions/async-swe-agents/outputs/` was previously tracked, remove it
from the index while keeping local files:

```bash
git rm -r --cached reproductions/async-swe-agents/outputs
```

Do not use plain `rm -rf` for local outputs unless you intentionally want to
delete them from disk.
