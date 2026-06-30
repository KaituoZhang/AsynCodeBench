# Commit0 GPT Pilot Commands

This note records the recommended GPT-series pilot setup for running
`cachetools` and `tinydb` through the third-party `async-swe-agents`
reproduction code.

## Recommended model order

1. `openai/gpt-5.4-mini`
   - Default pilot model.
   - Use for initial single-agent and 2-agent multi-agent runs.

2. `openai/gpt-5.4-nano`
   - Cheapest smoke-test option.
   - Use only to verify environment, Docker, dataset path, and API wiring.

3. `openai/gpt-5.3-codex`
   - Stronger coding-oriented option.
   - Use after the cheaper models show that the pipeline is healthy.

4. Mixed multi-agent setup:
   - manager: `openai/gpt-5.4-mini`
   - subagents: `openai/gpt-5.4-nano`

## Setup

Copy one of the model configs:

```bash
cp .env.gpt54mini.example .env
```

Then edit `.env`:

```bash
nano .env
```

Replace:

```text
PUT_YOUR_OPENAI_API_KEY_HERE
```

with your real OpenAI API key.

## Smoke-test one repo

```bash
MAX_ITERATIONS=5 \
OUTPUT_DIR=outputs/repro_commit0/cachetools/gpt54mini_single_smoke \
./scripts/run_commit0_single_env.sh cachetools
```

## Full single-agent pilot

```bash
for repo in cachetools tinydb; do
  MAX_ITERATIONS=50 \
  OUTPUT_DIR="outputs/repro_commit0/${repo}/gpt54mini_single" \
  ./scripts/run_commit0_single_env.sh "$repo"
done
```

## 2-agent multi-agent pilot

```bash
for repo in cachetools tinydb; do
  MAX_ITERATIONS=30 \
  MAX_SUBAGENTS=2 \
  SUB_ITERATIONS=50 \
  ROUNDS_OF_CHAT=2 \
  OUTPUT_DIR="outputs/repro_commit0/${repo}/gpt54mini_multi_2agents" \
  ./scripts/run_commit0_multi_env.sh "$repo"
done
```

## Inspect outputs

```bash
find outputs/repro_commit0/cachetools outputs/repro_commit0/tinydb -maxdepth 3 -type f | sort
```

Key files:

```text
report.json
cost.json
runtime.txt
outputs.jsonl
*_test_output.txt
*_pytest_exit_code.txt
final_repo/*.tar.gz
```

