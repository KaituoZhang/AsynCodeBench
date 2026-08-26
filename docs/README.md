# AsynCodeBench Docs

Start here when onboarding a collaborator or a new Codex session.

## Main Entry Points

| Document | Use |
| --- | --- |
| [`QUICKSTART.md`](QUICKSTART.md) | Canonical fresh-clone installation, model configuration, dry-run, and first task. |
| [`MODEL_EXPERIMENT_RUNBOOK.md`](MODEL_EXPERIMENT_RUNBOOK.md) | Main guide for running another model across the official 16 tasks. |
| [`RESULT_VALIDITY.md`](RESULT_VALIDITY.md) | Canonical run status, per-metric eligibility, official profile, bundle integrity, and legacy-result triage. |
| [`EVALUATION_METRICS.md`](EVALUATION_METRICS.md) | Metric definitions and post-run analysis rules. |
| [`ASYNCODEBENCH_HARNESS_V2.md`](ASYNCODEBENCH_HARNESS_V2.md) | Native `task_id`-based runner and protocol guarantees. |
| [`ITERATION_BUDGET_AND_TERMINATION.md`](ITERATION_BUDGET_AND_TERMINATION.md) | Official 100-response capability profile and stop-reason semantics. |
| [`OPENHANDS_RUNTIME_CONSISTENCY.md`](OPENHANDS_RUNTIME_CONSISTENCY.md) | Locked host/server OpenHands runtime, event-schema smoke, and invalid-run policy. |
| [`LOCAL_VLLM_EXPERIMENT_RUNBOOK.md`](LOCAL_VLLM_EXPERIMENT_RUNBOOK.md) | Local-vLLM capacity, networking, smoke gates, and failure diagnosis. |
| [`AGENT_ADAPTER.md`](AGENT_ADAPTER.md) | Public bring-your-own-agent contract, loading commands, enforcement, and provenance. |
| [`HUMAN_REVIEW.md`](HUMAN_REVIEW.md) | Required one-human review fields, acceptance checklist, status, and validation. |
| [`PR_HARD_20153_COLLABORATOR_RUNBOOK.md`](PR_HARD_20153_COLLABORATOR_RUNBOOK.md) | Fresh-clone reconstruction, execution, result validation, and GitHub handoff for the PR-hard 20153 candidate. |
| [`VLLM_QWEN_LOCAL_RUNBOOK.md`](VLLM_QWEN_LOCAL_RUNBOOK.md) | Qwen-specific local vLLM setup and tool calling. |
| [`GEMMA4_CAID_HARNESS_FIX.md`](GEMMA4_CAID_HARNESS_FIX.md) | Gemma 4 parser/version and CAID lifecycle notes. |

Historical internal references are retained for provenance but are not current
execution guides: `EVALUATION_BRANCH_QUICKSTART.md`, `CODEX_ONBOARDING.md`,
`GITHUB_COLLABORATOR_HANDOFF.md`, `COLLABORATOR_RUNBOOK.md`, and
`AGENT_EXPERIMENT_RUNBOOK.md`.

The official task directories contain one required human-review form, one
automated audit record, and optional secondary-review/adjudication forms. Form
presence is not evidence of completion. The automated audit never counts as a
human. `manifests/release/v0.3/task_index.json` reports the machine-readable
completion and approval state.

## Task Construction And Methodology

| Document | Use |
| --- | --- |
| [`protocols/COMMIT0_DATA_AND_METRIC_LABEL_GUIDE_v0.3.md`](protocols/COMMIT0_DATA_AND_METRIC_LABEL_GUIDE_v0.3.md) | How task and dependency labels are defined. |
| [`protocols/README.md`](protocols/README.md) | Protocol documents for v0.3 construction. |
| [`design/COMMIT0_TO_ASYNCODEBENCH_PIPELINE_v0.1.md`](design/COMMIT0_TO_ASYNCODEBENCH_PIPELINE_v0.1.md) | Pipeline framing for converting public coding tasks. |
| [`design/paper_structure_reference.md`](design/paper_structure_reference.md) | Paper-structure reference and evaluation framing. |
| [`design/PR_HARD_TASK_PILOT_v0.4.md`](design/PR_HARD_TASK_PILOT_v0.4.md) | Construction evidence and promotion gates for the Apache TVM PR-hard pilot. |

## Task-specific Runner Notes

| Document | Use |
| --- | --- |
| [`COOKIECUTTER_RUNNER_EVALUATOR_FIX.md`](COOKIECUTTER_RUNNER_EVALUATOR_FIX.md) | `cookiecutter` evaluator, dependency, and transient test-artifact notes. |
| [`FLASK_EVALUATOR_COMPATIBILITY_FIX.md`](FLASK_EVALUATOR_COMPATIBILITY_FIX.md) | `flask` evaluator compatibility notes. |

## Official Experiment Set

The current official model-comparison set contains 16 tasks:

```text
cachetools
deprecated
portalocker
tinydb
wcwidth
requests
simpy
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

Excluded from the current official aggregate:

```text
fastapi
python-progressbar
fabric
chardet
dulwich
```
