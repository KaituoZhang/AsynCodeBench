# PR-hard 20073 on Qwen3.6-27B

This runbook executes the packaged `pr-hard:apache-tvm-20073` task with the
tested Qwen3.6-27B thinking profile. The package has passed automated
qualification and mandatory human review, so new results report
`official_result_eligible=true` in the unified v0.4 release.

## 1. Verify or reconstruct the runtime

From the AsynCodeBench repository root:

```bash
.venv-benchmark/bin/python scripts/prepare_pr_hard_runtime.py \
  --task-id pr-hard:apache-tvm-20073 \
  --check
```

If the package is absent, reconstruct it from the public pinned source,
recursive submodules, frozen dependency locks, and test-only overlay:

```bash
.venv-benchmark/bin/python scripts/prepare_pr_hard_runtime.py \
  --task-id pr-hard:apache-tvm-20073

.venv-benchmark/bin/python scripts/prepare_pr_hard_runtime.py \
  --task-id pr-hard:apache-tvm-20073 \
  --check
```

The generated package is
`.cache/pr_hard_runtime/v0.4/apache-tvm-20073`. Its model-visible seed has one
local commit, no remotes, no production gold patch, and one checksum-validated
public-test overlay. This candidate pins its own older `tvm-ffi`; do not reuse
another task's environment.

## 2. Start Qwen3.6-27B

PR 20073 has three concurrent specialists. A formal matched run therefore
requires at least three vLLM sequence slots:

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

Keep the serving profile unchanged across all four protocols. If three 131K
slots do not fit, reduce context in both the server and env profile and record
that serving profile; do not report a two-slot smoke run as the formal async
comparison.

## 3. Prepare the runner profile

In a second terminal:

```bash
cd /absolute/path/to/AsynCodeBench/reproductions/async-swe-agents
cp configs/model_profiles/qwen36-27b.env.example .env.qwen36-27b
```

Edit the machine-specific `SDK_SOURCE_DIR`, then verify host and container
connectivity:

```bash
curl -fsS http://127.0.0.1:8006/v1/models
docker run --rm --network host curlimages/curl:8.10.1 \
  -fsS http://127.0.0.1:8006/v1/models
```

## 4. Dry-run all matched conditions

```bash
ENV_FILE="$PWD/.env.qwen36-27b" \
DRY_RUN=1 \
RUN_SINGLE=1 RUN_SERIAL=1 RUN_ASYNC_PRIVATE=1 RUN_CAID=1 \
scripts/run_pr_hard_20073_all_protocols_env.sh
```

Confirm that preflight reports three roles, two incoming join dependencies,
the frozen standard-100 execution profile, and unified-release eligibility.

## 5. Run all four conditions

```bash
ENV_FILE="$PWD/.env.qwen36-27b" \
RUN_ID="pr-hard-20073-qwen36-27b-thinking-$(date -u +%Y%m%dT%H%M%SZ)" \
scripts/run_pr_hard_20073_all_protocols_env.sh
```

The wrapper runs `single`, `serial_specialists`, `async_private`, and
`caid_manager` sequentially against the same task, evaluator, model settings,
and frozen 100-response execution profile.

To run only one condition, set the other flags to zero. For example:

```bash
ENV_FILE="$PWD/.env.qwen36-27b" \
RUN_ID="pr-hard-20073-qwen36-27b-async-private-$(date -u +%Y%m%dT%H%M%SZ)" \
RUN_SINGLE=0 RUN_SERIAL=0 RUN_ASYNC_PRIVATE=1 RUN_CAID=0 \
scripts/run_pr_hard_20073_all_protocols_env.sh
```

Do not reuse an interrupted output directory or compare a partial protocol set
as if it were a complete matched four-condition experiment.
