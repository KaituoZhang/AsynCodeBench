# PR-hard 20018 on Qwen3.6-27B

This runbook executes the packaged `pr-hard:apache-tvm-20018` task with the
tested Qwen3.6-27B thinking profile. Automated qualification and mandatory
human review have passed. New results therefore report
`official_result_eligible=true` in the unified v0.4 release.

## 1. Verify or reconstruct the runtime

From the AsynCodeBench repository root:

```bash
.venv-benchmark/bin/python scripts/prepare_pr_hard_runtime.py \
  --task-id pr-hard:apache-tvm-20018 \
  --check
```

If the package is absent, reconstruct it from the pinned public source and
checksum-validated test-only overlay, then check it:

```bash
.venv-benchmark/bin/python scripts/prepare_pr_hard_runtime.py \
  --task-id pr-hard:apache-tvm-20018

.venv-benchmark/bin/python scripts/prepare_pr_hard_runtime.py \
  --task-id pr-hard:apache-tvm-20018 \
  --check
```

The generated package is
`.cache/pr_hard_runtime/v0.4/apache-tvm-20018`. Its model-visible seed contains
one local commit, no Git remote or upstream history, no production gold patch,
and one checksum-validated public-test overlay.

## 2. Start Qwen3.6-27B

PR 20018 has three specialist roles. A formal async comparison therefore
requires at least three sequence slots:

```bash
PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
TRANSFORMERS_NO_TF=1 USE_TF=0 CUDA_VISIBLE_DEVICES=1 \
/home/kzhang42/anaconda3/envs/vllm_qwen3_128k/bin/vllm serve Qwen/Qwen3.6-27B \
  --served-model-name Qwen/Qwen3.6-27B \
  --trust-remote-code \
  --host 0.0.0.0 \
  --max-model-len 131000 \
  --gpu-memory-utilization 0.90 \
  --max-num-seqs 3 \
  --max-num-batched-tokens 32768 \
  --port 8006 \
  --reasoning-parser deepseek_r1 \
  --enable-auto-tool-choice \
  --tool-call-parser qwen3_xml
```

Keep the serving profile fixed across all four conditions. If three 131K
slots do not fit, reduce the context consistently in the server and runner
profile and record the changed serving configuration; do not report a
two-slot smoke test as the formal three-specialist comparison.

## 3. Prepare the runner

In a second terminal:

```bash
cd /absolute/path/to/AsyncCodeBench/reproductions/async-swe-agents
cp configs/model_profiles/qwen36-27b.env.example .env.qwen36-27b
```

Set the machine-specific SDK path in `.env.qwen36-27b`, for example:

```dotenv
SDK_SOURCE_DIR=/home/kzhang42/AsyncCodeBench/reproductions/software-agent-sdk
```

Verify both host and container connectivity:

```bash
curl -fsS http://127.0.0.1:8006/v1/models
docker run --rm --network host curlimages/curl:8.10.1 \
  -fsS http://127.0.0.1:8006/v1/models
```

## 4. Dry-run all four conditions

TVM build products are placed in the host-backed default cache
`.cache/pr_hard_builds/v0.4`, rather than Docker's root filesystem. Every
protocol run and worktree receives an isolated build directory. The runner
removes these transient products on normal completion or failure. Set
`PR_HARD_BUILD_CACHE_ROOT` only when a different host filesystem is desired;
set `ASYNCODEBENCH_PR_HARD_PRESERVE_BUILD_CACHE=1` only for explicit build
debugging.

```bash
ENV_FILE="$PWD/.env.qwen36-27b" \
DRY_RUN=1 \
RUN_SINGLE=1 RUN_SERIAL=1 RUN_ASYNC_PRIVATE=1 RUN_CAID=1 \
scripts/run_pr_hard_20018_all_protocols_env.sh
```

The preflight should report three ordered specialist roles, two chain
dependency points, the frozen standard-100 budget, and unified-release
eligibility. Dry-run does not call the model.

## 5. Run the matched experiment

```bash
ENV_FILE="$PWD/.env.qwen36-27b" \
RUN_ID="pr-hard-20018-qwen36-27b-thinking-$(date -u +%Y%m%dT%H%M%SZ)" \
scripts/run_pr_hard_20018_all_protocols_env.sh
```

The wrapper runs `single`, `serial_specialists`, `async_private`, and
`caid_manager` (the manifest's `async_message` condition) sequentially against
the same task, evaluator, model settings, and frozen execution budget.

For this C++ task, the runner prepares a source-matched build for every private
worktree and rebuilds the exact source tree before dependency checkpoints and
integrated handoff tests. Deterministic worktree preparation is recorded in
`infrastructure_timing.json` and excluded from the reported protocol runtime,
matching the single-agent condition whose initial build is also setup work. If
an agent produces code that does not compile, checkpoints record a source-build
failure and leave selectors unresolved instead of probing a stale shared
library or terminating with an object-registration traceback.

Do not reuse an interrupted output directory or report a partial protocol set
as a complete matched four-condition experiment.
