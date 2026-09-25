# PR-hard 20153 Collaborator Runbook

This runbook reconstructs and runs the AsynCodeBench task
`pr-hard:apache-tvm-20153` from a fresh GitHub clone. The public repository
contains the pinned base provenance, answer-free public test overlays,
environment locks, task/scenario/Dependency Checker manifests, and runner. It
does not contain the offline production gold, a prepared TVM checkout, model
outputs, credentials, or local caches.

PR 20153 is a qualified task in the unified v0.4 community-preview release.
Its automated qualification and mandatory human review have passed, so new
runs report `official_result_eligible=true`.

## Supported host

The frozen package currently supports Linux x86-64. Qualification used Ubuntu
22.04, Python 3.11.16 for TVM, LLVM 18.1.8, CMake 4.4.2, and Ninja 1.13.2. A
CUDA toolkit and GPU are not required: the evaluator compiles TVM's CUDA source
generator with `USE_CUDA=OFF` and inspects generated source without launching a
kernel.

Install these host prerequisites before starting:

- Git with submodule support
- Docker with permission to run `docker info`
- `uv` and Python 3.12 for the AsynCodeBench/OpenHands runner
- `micromamba` for the explicit Linux-64 TVM environment lock
- network access to GitHub, conda-forge, Python package indexes, and the chosen
  model endpoint
- approximately 20 GB of free disk for source/submodules, the frozen
  environment, Docker workspaces, builds, and result bundles

## 1. Clone and install the runner

```bash
git clone <ASYNCODEBENCH_GITHUB_URL> AsyncCodeBench
cd AsyncCodeBench

uv python install 3.12
bash scripts/setup_evaluation.sh
```

`setup_evaluation.sh` materializes the checksum-pinned OpenHands SDK revision,
creates the benchmark and runner environments, checks Docker, and runs the
contract suites. Do not substitute an arbitrary OpenHands checkout: host and
container event schemas must match the locked revision.

## 2. Reconstruct the model-visible 20153 runtime

```bash
.venv-benchmark/bin/python scripts/prepare_pr_hard_runtime.py \
  --task-id pr-hard:apache-tvm-20153
```

The command performs the following operations:

1. verifies the checked-in environment and overlay checksums;
2. clones Apache TVM and checks out base
   `a35aca6a0ae5a61c486cb9a61c36b09be45f81af`;
3. initializes the checksum-qualified recursive submodule revisions;
4. applies only the two public, test-only overlays;
5. creates a clean one-commit seed with no Git remotes or nested history;
6. recreates Python 3.11/LLVM/CMake/Ninja from the explicit micromamba lock;
7. builds and installs the task-local `tvm-ffi` non-editably; and
8. makes the read-only runtime paths traversable by the Docker container user.

The result is written under the ignored local directory:

```text
.cache/pr_hard_runtime/v0.4/apache-tvm-20153/
├── seed/                 # model-visible, one commit, no remotes
├── env/                  # frozen TVM build/test toolchain
└── runtime_manifest.json # local reconstruction provenance
```

Validate it at any time without network access:

```bash
.venv-benchmark/bin/python scripts/prepare_pr_hard_runtime.py \
  --task-id pr-hard:apache-tvm-20153 \
  --check
```

Do not upload this directory to GitHub. It is reproducible, roughly 2 GB on
disk before TVM workspace builds, and intentionally covered by `.gitignore`.

## 3. Configure the model endpoint

```bash
cd reproductions/async-swe-agents
cp .env.example .env
```

Edit `.env` and set at least:

```text
LLM_BASE_URL=<OpenAI-compatible endpoint>
LLM_API_KEY=<credential>
LLM_MODEL=<LiteLLM provider/model identifier>
SDK_SOURCE_DIR=<absolute clone>/reproductions/software-agent-sdk
```

Set `LLM_SUBAGENT_MODEL` only when the subagents intentionally use a different
model. Never commit `.env`; it is ignored because it contains credentials.

## 4. Preflight without calling a model

From `reproductions/async-swe-agents`:

```bash
ENV_FILE="$PWD/.env" \
DRY_RUN=1 \
RUN_SERIAL=0 RUN_ASYNC_PRIVATE=0 RUN_CAID=0 \
scripts/run_pr_hard_20153_all_protocols_env.sh
```

The output must report the candidate task, the `single` protocol, the frozen
standard-100 execution profile, the sanitized seed, and
`official_result_eligible=True`. A dry run still validates that the runtime
package exists and is isolated correctly.

## 5. Run one or all matched conditions

Run all four conditions with the same run identifier:

```bash
ENV_FILE="$PWD/.env" \
RUN_ID="my-model-20153-seed1-$(date -u +%Y%m%dT%H%M%SZ)" \
scripts/run_pr_hard_20153_all_protocols_env.sh
```

Run only CAID, for example:

```bash
ENV_FILE="$PWD/.env" \
RUN_ID="my-model-20153-caid-seed2-$(date -u +%Y%m%dT%H%M%SZ)" \
RUN_SINGLE=0 RUN_SERIAL=0 RUN_ASYNC_PRIVATE=0 RUN_CAID=1 \
scripts/run_pr_hard_20153_all_protocols_env.sh
```

Supported flags are `RUN_SINGLE`, `RUN_SERIAL`, `RUN_ASYNC_PRIVATE`, and
`RUN_CAID`; each is `0` or `1`. Every non-diagnostic comparison must retain the
frozen 100-response profile. A fresh run ID is required because completed or
interrupted output directories are immutable evidence.

## 6. Validate and interpret results

Each protocol writes under:

```text
reproductions/async-swe-agents/outputs/pr_hard/v0.4/
  <model>/apache-tvm-20153/<protocol>/<run-id>/
```

Validate checksums and cross-artifact consistency:

```bash
RUN_DIR=<absolute-path-to-one-protocol-run>
.venv/bin/asyncodebench validate-run "$RUN_DIR"
.venv/bin/python scripts/check_run_health.py "$RUN_DIR"
```

The result bundle is usable when it reports `status=valid`, even if the model's
final evaluator fails. Model coding failures, unresolved dependencies, or
scope-rejected artifacts are measured outcomes. Infrastructure failures,
missing reports, checksum mismatches, synthetic summaries, wrong evaluators,
or contaminated manager workspaces make a result invalid or review-required.

Use these artifacts together:

- `report.json`: final repository evaluator and exact test outcomes;
- `strict_dependency_metrics.json`: final ADPR and strict DRS/CAIL;
- `dependency_probe_checkpoints.jsonl`: upstream/downstream/integrated checker
  observations over time;
- `scope_validation.jsonl`: accepted and rejected specialist artifacts;
- `manager_workspace_validation.jsonl`: CAID manager isolation;
- `process_metrics_summary.json`: runtime, tokens, attempts, and process
  metrics;
- `run_bundle.json`: recursive checksums, provenance, and metric eligibility.

## 7. Share results without committing generated state

The source repository ignores runtime caches and outputs. To send a completed
run to another collaborator, validate it first, then create an external archive:

```bash
RUN_DIR=<absolute-path-to-one-protocol-run>
.venv/bin/asyncodebench validate-run "$RUN_DIR"
tar -C "$(dirname "$RUN_DIR")" -czf "$(basename "$RUN_DIR").tar.gz" \
  "$(basename "$RUN_DIR")"
sha256sum "$(basename "$RUN_DIR").tar.gz"
```

Use a GitHub Release asset, institutional storage, or another artifact store
for result archives. Do not force-add `.cache/`, `.env`, `outputs/`, TVM build
trees, model server logs, or the offline production gold to Git.

## Maintainer GitHub publication checklist

Before publishing the candidate implementation, run:

```bash
.venv-benchmark/bin/python scripts/build_release_index.py --check
.venv-benchmark/bin/python -m pytest -q tests/contracts
cd reproductions/async-swe-agents
.venv/bin/python -m pytest -q tests
```

Review staged content with `git diff --cached --check` and `git status --short`.
Use an explicit `git add` list; do not use `git add -f` on ignored caches or
outputs. A normal feature-branch flow is:

```bash
git switch -c pr-hard-20153-collaborator-runtime
git add \
  configs/environments/ \
  configs/tasks/pr_hard_candidates.v0.4.json \
  data/overlays/pr_hard/ \
  manifests/candidates/pr_hard_v0.4/ \
  schemas/v0.4/ schemas/README.md schemas/release/run_bundle.schema.json \
  scripts/prepare_pr_hard_candidate.py scripts/prepare_pr_hard_runtime.py \
  scripts/README.md \
  tests/contracts/test_pr_hard_candidates_v04.py \
  docs/PR_HARD_20153_COLLABORATOR_RUNBOOK.md \
  docs/design/PR_HARD_TASK_PILOT_v0.4.md docs/README.md \
  reproductions/async-swe-agents/README.md \
  reproductions/async-swe-agents/run_pr_hard.py \
  reproductions/async-swe-agents/tasks/pr_hard.py \
  reproductions/async-swe-agents/scripts/run_pr_hard_20153_all_protocols_env.sh \
  reproductions/async-swe-agents/asyncodebench_harness/health.py \
  reproductions/async-swe-agents/asyncodebench_harness/results.py \
  reproductions/async-swe-agents/core/asyncodebench_manager.py \
  reproductions/async-swe-agents/core/manager.py \
  reproductions/async-swe-agents/core/subagent.py \
  reproductions/async-swe-agents/prompts/asyncodebench.yaml \
  reproductions/async-swe-agents/protocols/asyncodebench/runner.py \
  reproductions/async-swe-agents/protocols/static_commit0.py \
  reproductions/async-swe-agents/run_infer.py \
  reproductions/async-swe-agents/tests/test_asyncodebench_harness_v2.py \
  reproductions/async-swe-agents/tests/test_dependency_checker_compat.py \
  reproductions/async-swe-agents/tests/test_pr_hard_runner_contract.py
git diff --cached --check
git diff --cached --stat
git commit -m "Add reproducible PR-hard 20153 collaborator runtime"
git push -u origin pr-hard-20153-collaborator-runtime
```

Open a pull request and require the contract suites before merging. Human
review of the benchmark semantics is a separate promotion gate; publishing the
candidate code did not by itself make 20153 result-eligible. That status was
granted only after automated qualification and mandatory human review passed.
