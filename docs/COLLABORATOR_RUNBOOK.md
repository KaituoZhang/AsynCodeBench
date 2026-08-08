# AsynCodeBench Collaborator Runbook

This document explains what to upload to GitHub and how collaborators can run
AsynCodeBench agent experiments from a fresh machine.

Repository target:

```text
https://github.com/KaituoZhang/Asynccodebench
```

If a collaborator uses Codex or another coding agent, ask that agent to read
`docs/CODEX_ONBOARDING.md` first. That file explains the project structure,
which files to inspect first, and where LLM/API configuration lives.

For copy-paste commands to run a new model across the current official task
set, use `docs/MODEL_EXPERIMENT_RUNBOOK.md` and
`docs/ASYNCODEBENCH_HARNESS_V2.md`. `docs/AGENT_EXPERIMENT_RUNBOOK.md` is a
historical v1 reference only. New runs must use the native
`run_asyncodebench.py` entry point rather than raw Commit0 fallback paths.

For evaluation metrics and post-run analysis, ask collaborators to read
`docs/EVALUATION_METRICS.md`. That document defines the current first-round
AsynCodeBench metrics, the required run artifacts, and the analysis commands.

## What Should Be Versioned

Include these project assets:

- `README`
- `LICENSE`
- `THIRD_PARTY_NOTICES.md`
- `CITATION.cff`
- `SPECIFICATION_v0.3.md`
- `configs/`
- `data/overlays/`
- `docs/`
- `manifests/`
- `pipelines/`
- `schemas/`
- `scripts/`
- `skills/`
- `src/`
- `tests/`
- `reproductions/async-swe-agents/` source code and scripts
- `pyproject.toml`
- `environment.yml`
- `.gitignore`

Do not version these local/runtime assets:

- `.env`
- `.venv/`
- `outputs/`
- `data/repos/`
- `data/raw/`
- `data/interim/`
- `data/processed/`
- `data/external/`
- `__pycache__/`
- `.pytest_cache/`
- `.ruff_cache/`
- `*.egg-info/`

The checked-in `data/overlays/` directory is intentional. It contains
checksum-pinned non-solution bootstrap patches required by some tasks.

## Important Git Warning

`reproductions/async-swe-agents/` is currently a cloned repository with its own
`.git` directory. If you run `git add .` from the AsynCodeBench root while that
nested `.git` directory still exists, Git may record it as an embedded repo or
submodule instead of uploading the actual source files.

For a simple single-repository release, back up and remove the nested git
metadata before the first top-level commit:

```bash
export REPO_ROOT="${REPO_ROOT:-$HOME/AsynCodeBench}"
cd "$REPO_ROOT"
tar -C reproductions/async-swe-agents -czf ~/async-swe-agents-local-git-backup.tgz .git
rm -rf reproductions/async-swe-agents/.git
```

Use a real Git submodule only if you plan to maintain
`reproductions/async-swe-agents` as a separate public fork with its own remote.
For this project, the simple one-repo release is easier for collaborators.

## Upload To GitHub

From the server:

```bash
export REPO_ROOT="${REPO_ROOT:-$HOME/AsynCodeBench}"
cd "$REPO_ROOT"

# Only if this directory is not already a git repo.
git init
git branch -M main

git remote add origin https://github.com/KaituoZhang/Asynccodebench.git

git status --short
git add .gitignore README SPECIFICATION_v0.3.md pyproject.toml environment.yml
git add configs data/overlays docs manifests pipelines schemas scripts skills src tests
git add reproductions/README.md reproductions/async-swe-agents

git status --short
git commit -m "Release AsynCodeBench data and agent runners"
git push -u origin main
```

If `origin` already exists:

```bash
git remote set-url origin https://github.com/KaituoZhang/Asynccodebench.git
```

If Git warns about an embedded repository under
`reproductions/async-swe-agents`, stop and handle the nested `.git` issue above.

## Fresh Clone Setup

On a collaborator machine:

```bash
git clone https://github.com/KaituoZhang/Asynccodebench.git AsynCodeBench
cd AsynCodeBench
```

Install the AsynCodeBench validation environment:

Option A: conda:

```bash
conda create -n asyncodebench python=3.10 -y
conda activate asyncodebench
python -m pip install -U pip
python -m pip install -e ".[dev]"
```

Option B: Python venv:

```bash
python3.10 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e ".[dev]"
```

The top-level benchmark validation code does not require conda specifically.
Use conda if that is how your lab manages Python environments.

Run the artifact contract tests:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q tests/contracts
```

Expected result in the current workspace:

```text
141 passed
```

## Agent Runner Setup

The agent runner lives here:

```text
reproductions/async-swe-agents/
```

It uses `uv`, Docker, OpenHands, and provider-compatible LLM APIs.

This is separate from the top-level AsynCodeBench conda environment. The
`async-swe-agents` reproduction repository has its own `pyproject.toml` and
`uv.lock`, so `uv sync` is the most reproducible way to install the exact agent
runner dependencies.

Install `uv` if needed:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Install Docker and make sure the user can run:

```bash
docker ps
```

Then install the runner environment:

```bash
cd reproductions/async-swe-agents
uv sync
```

The runner expects OpenHands' `software-agent-sdk` next to
`async-swe-agents`:

```bash
cd ..
git clone https://github.com/OpenHands/software-agent-sdk.git
cd async-swe-agents
```

If your checkout uses a different path, set `SDK_SOURCE_DIR` in `.env`.

## LLM Configuration

Create a local `.env` file in `reproductions/async-swe-agents/`.

```bash
cd reproductions/async-swe-agents
cp .env.example .env
```

For OpenRouter:

```bash
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_API_KEY=YOUR_OPENROUTER_KEY
LLM_MODEL=openai/gpt-5.4-mini
LLM_SUBAGENT_MODEL=
COMMIT0_DATASET_PATH=data/commit0/commit0_combined
SDK_SOURCE_DIR=/absolute/path/to/AsynCodeBench/reproductions/software-agent-sdk
```

Alternative OpenRouter model IDs:

```text
openai/gpt-5.4-mini
anthropic/claude-sonnet-4.6
qwen/qwen3.7-plus
z-ai/glm-4.5
```

Always confirm current model IDs and pricing on the provider page before a
large run.

## Commit0 Dataset Path

The CAID runner currently expects a local HuggingFace `load_from_disk` Commit0
dataset path:

```text
reproductions/async-swe-agents/data/commit0/commit0_combined
```

Set it explicitly in `.env`:

```bash
COMMIT0_DATASET_PATH=/absolute/path/to/commit0_combined
```

Do not commit the dataset directory unless the license and size make that
appropriate. Keep large raw datasets outside git and document the download or
materialization step.

## Smoke Tests

Validate scenario parsing without Docker or LLM calls:

```bash
cd reproductions/async-swe-agents
MODEL_TAG=smoke RUN_VERSION=dryrun_v01 DRY_RUN=1 \
  scripts/run_asyncodebench_all_protocols_env.sh cachetools
```

Expected dry-run output should include:

```text
scenario_id=commit0-cachetools.serial-specialists.v0.3
key_agent subproblem=key_construction
decorator_agent subproblem=decorator_factories
```

Then run a small real smoke test with low iteration budgets:

```bash
MODEL_TAG=<model-tag> RUN_VERSION=smoke_v01 \
SINGLE_ITERATIONS=5 SPECIALIST_ITERATIONS=5 \
CAID_MANAGER_ITERATIONS=5 CAID_SUB_ITERATIONS=5 \
  scripts/run_asyncodebench_all_protocols_env.sh cachetools
```

## Full Experiment Commands

Run the four protocols for one task:

```bash
cd reproductions/async-swe-agents

MODEL_TAG=<model-tag> RUN_VERSION=official_v01 \
  scripts/run_asyncodebench_all_protocols_env.sh cachetools
```

Recommended current experimental task set:

```text
cachetools
cookiecutter
deprecated
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

Excluded or needs-revision candidates:

```text
chardet
dulwich
fastapi
python-progressbar
fabric
```

Historical artifacts for `chardet`, `dulwich`, and `python-progressbar` are archived under
`archive/non_official/commit0_v0.3/` for audit only. Do not include archived
tasks in official v0.3 runs or aggregate reports.

Run all four protocols for the recommended task set:

```bash
cd reproductions/async-swe-agents

for repo in \
  cachetools cookiecutter deprecated filesystem_spec flask \
  graphene imapclient marshmallow parsel pexpect portalocker python-rsa \
  requests simpy tinydb wcwidth
do
  MODEL_TAG=<model-tag> RUN_VERSION=official_v01 \
    scripts/run_asyncodebench_all_protocols_env.sh "$repo"
done
```

To run with a different model, edit `.env` or override variables inline:

```bash
LLM_MODEL=qwen/qwen3.7-plus MODEL_TAG=qwen3.7-plus RUN_VERSION=v01 \
  scripts/run_asyncodebench_all_protocols_env.sh cachetools
```

## Output Files

Each run writes to `reproductions/async-swe-agents/outputs/`.

Important files:

```text
outputs/.../outputs.jsonl
outputs/.../agent_events/
outputs/.../delegations.json
outputs/.../protocol.json              # static protocols only
outputs/.../cost.json
outputs/.../runtime.txt
outputs/.../patch.diff
outputs/.../report.json
outputs/.../<repo>_pytest_exit_code.txt
outputs/.../<repo>_test_output.txt
outputs/.../final_repo/<repo>.tar.gz
```

Use these artifacts for downstream metric extraction:

- final success from `report.json` and pytest exit code;
- cost/runtime from `cost.json` and `runtime.txt`;
- agent process traces from `outputs.jsonl` and `agent_events/`;
- integration and final patch behavior from `patch.diff`;
- reproducible final state from `final_repo/<repo>.tar.gz`.

## Current Protocols

The runner supports four experimental conditions:

| Protocol | Script | Meaning |
| --- | --- | --- |
| Single agent | `run_asyncodebench.py --protocol single` | One agent solves the full task. |
| Serial specialists | `run_asyncodebench.py --protocol serial_specialists` | Specialists run one at a time; downstream starts after upstream merge. |
| Async private | `run_asyncodebench.py --protocol async_private` | Specialists start from the same base in private worktrees; merge happens after all finish. |
| CAID manager | `run_asyncodebench.py --protocol caid_manager` | Manager scans, delegates, reviews, merges, and can recover. |

For new official experiments, use
`scripts/run_asyncodebench_all_protocols_env.sh <task>` rather than the
historical `run_commit0_*` scripts. The native wrapper enforces
`asyncodebench:<task>` IDs and loads the correct agent count from the scenario
manifest.

## Reproducibility Checklist

Before collaborators run experiments:

- `docker ps` works.
- `uv sync` succeeds under `reproductions/async-swe-agents`.
- `.env` has valid `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`,
  `COMMIT0_DATASET_PATH`, and `SDK_SOURCE_DIR`.
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q tests/contracts` passes
  from the top-level repository.
- Static protocol dry-runs pass for `cachetools`.
- One low-budget smoke test produces `report.json`, `cost.json`, and
  `patch.diff`.
