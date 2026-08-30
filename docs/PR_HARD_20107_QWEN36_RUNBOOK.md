# PR-hard 20107 on Qwen3.6-27B

This runbook executes the packaged `pr-hard:apache-tvm-20107` task with the
tested Qwen3.6-27B thinking profile. Automated qualification and mandatory
human review have passed, so new results report
`official_result_eligible=true` in the unified v0.4 release.

## 1. Verify or reconstruct the runtime

From the AsynCodeBench repository root:

```bash
.venv-benchmark/bin/python scripts/prepare_pr_hard_runtime.py \
  --task-id pr-hard:apache-tvm-20107 \
  --check
```

If the package is absent, reconstruct it from the public pinned source and
test-only overlay, then check it:

```bash
.venv-benchmark/bin/python scripts/prepare_pr_hard_runtime.py \
  --task-id pr-hard:apache-tvm-20107

.venv-benchmark/bin/python scripts/prepare_pr_hard_runtime.py \
  --task-id pr-hard:apache-tvm-20107 \
  --check
```

The generated package is
`.cache/pr_hard_runtime/v0.4/apache-tvm-20107`. Its seed has one local commit,
no remotes, no production gold patch, and one checksum-validated public-test
overlay.

## 2. Start the tested Qwen server

The project previously smoke-tested Qwen3.6-27B with two sequence slots on one
A100 80GB. PR 20107 has three concurrent specialists, so a formal run must use
at least three slots:

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

Keep this command unchanged across the four protocols. The PR 20107 wrapper
rejects `max_num_seqs < 3` to prevent a two-slot capacity smoke from being
reported as a formal async comparison. If three 131K slots do not fit on the
available hardware, reduce the context in both the server and env profile and
record that serving profile, or use more capacity; do not silently fall back
to two slots. The runner enables
thinking explicitly and uses temperature 0.6, top-p 0.95, top-k 20, and a
32,768-token output cap.

## 3. Prepare the runner profile

In a second terminal:

```bash
cd /absolute/path/to/AsynCodeBench/reproductions/async-swe-agents
cp configs/model_profiles/qwen36-27b.env.example .env.qwen36-27b
```

Edit only the machine-specific `SDK_SOURCE_DIR` path. Then verify host and
container connectivity:

```bash
curl -fsS http://127.0.0.1:8006/v1/models
docker run --rm --network host curlimages/curl:8.10.1 \
  -fsS http://127.0.0.1:8006/v1/models
```

## 4. Dry-run the packaged task

```bash
ENV_FILE="$PWD/.env.qwen36-27b" \
DRY_RUN=1 \
RUN_SINGLE=1 RUN_SERIAL=1 RUN_ASYNC_PRIVATE=1 RUN_CAID=1 \
scripts/run_pr_hard_20107_all_protocols_env.sh
```

Dry-run performs package and qualification preflight but does not call the
model. Confirm that it reports three specialist roles, two fan-out dependency
points, the frozen standard-100 profile, and unified-release eligibility.

## 5. Run all four matched conditions

```bash
ENV_FILE="$PWD/.env.qwen36-27b" \
RUN_ID="pr-hard-20107-qwen36-27b-thinking-$(date -u +%Y%m%dT%H%M%SZ)" \
scripts/run_pr_hard_20107_all_protocols_env.sh
```

The wrapper runs `single`, `serial_specialists`, `async_private`, and
`caid_manager` sequentially against the same task, evaluator, model settings,
and frozen 100-response execution profile.

To run one condition only, set the other flags to zero. For example:

```bash
ENV_FILE="$PWD/.env.qwen36-27b" \
RUN_ID="pr-hard-20107-qwen36-27b-async-private-$(date -u +%Y%m%dT%H%M%SZ)" \
RUN_SINGLE=0 RUN_SERIAL=0 RUN_ASYNC_PRIVATE=1 RUN_CAID=0 \
scripts/run_pr_hard_20107_all_protocols_env.sh
```

Do not reuse an interrupted output directory or compare a partial protocol set
as if it were a complete matched four-condition experiment.
