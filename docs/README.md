# AsynCodeBench Docs

Start here when onboarding a collaborator or a new Codex session.

## Main Entry Points

| Document | Use |
| --- | --- |
| [`QUICKSTART.md`](QUICKSTART.md) | Canonical fresh-clone installation, model configuration, dry-run, and first task. |
| [`MODEL_EXPERIMENT_RUNBOOK.md`](MODEL_EXPERIMENT_RUNBOOK.md) | Main guide for running another model across the official 19 tasks. |
| [`TASK_IMAGE_DISTRIBUTION.md`](TASK_IMAGE_DISTRIBUTION.md) | Immutable Docker images, four compiler-task snapshots, pull/run commands, and source fallback. |
| [`RESULT_VALIDITY.md`](RESULT_VALIDITY.md) | Canonical run status, per-metric eligibility, official profile, bundle integrity, and legacy-result triage. |
| [`EVALUATION_METRICS.md`](EVALUATION_METRICS.md) | Metric definitions and post-run analysis rules. |
| [`ASYNCODEBENCH_HARNESS_V2.md`](ASYNCODEBENCH_HARNESS_V2.md) | Native `task_id`-based runner and protocol guarantees. |
| [`ASYNC_MANAGER_PROTOCOL_V1.md`](ASYNC_MANAGER_PROTOCOL_V1.md) | Online Async-Manager execution, intervention, and integrity contract. |
| [`ITERATION_BUDGET_AND_TERMINATION.md`](ITERATION_BUDGET_AND_TERMINATION.md) | Official 100-response capability profile and stop-reason semantics. |
| [`OPENHANDS_RUNTIME_CONSISTENCY.md`](OPENHANDS_RUNTIME_CONSISTENCY.md) | Locked host/server OpenHands runtime, event-schema smoke, and invalid-run policy. |
| [`LOCAL_VLLM_EXPERIMENT_RUNBOOK.md`](LOCAL_VLLM_EXPERIMENT_RUNBOOK.md) | Local-vLLM capacity, networking, smoke gates, and failure diagnosis. |
| [`AGENT_ADAPTER.md`](AGENT_ADAPTER.md) | Public bring-your-own-agent contract, loading commands, enforcement, and provenance. |
| [`HUMAN_REVIEW.md`](HUMAN_REVIEW.md) | Required one-human review fields, acceptance checklist, status, and validation. |
| [`PR_HARD_20153_COLLABORATOR_RUNBOOK.md`](PR_HARD_20153_COLLABORATOR_RUNBOOK.md) | Fresh-clone reconstruction, execution, and result validation for the qualified compiler/IR task 20153. |
| [`REPOSITORY_LAYOUT.md`](REPOSITORY_LAYOUT.md) | Maintained source, manifest, runner, test, and generated-data boundaries. |

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
| [`design/PR_HARD_TASK_PILOT_v0.4.md`](design/PR_HARD_TASK_PILOT_v0.4.md) | Construction evidence and promotion gates for the four compiler/IR tasks added to unified v0.4. |
| [`../skills/contribute-commit0-task/SKILL.md`](../skills/contribute-commit0-task/SKILL.md) | Optional agent guidance for preparing a new Commit0-derived task contribution without modifying the frozen release. |

## Official Experiment Set

The current unified v0.4.1 model-comparison set contains 19 tasks:

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
imapclient
pexpect
flask
python-rsa
cookiecutter
apache-tvm-20018
apache-tvm-20073
apache-tvm-20107
apache-tvm-20153
```

Excluded from the current official aggregate:

```text
graphene
fastapi
python-progressbar
fabric
chardet
dulwich
```
