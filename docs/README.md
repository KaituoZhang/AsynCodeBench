# AsyncCodeBench Docs

Start here when onboarding a collaborator or a new Codex session.

## Main Entry Points

| Document | Use |
| --- | --- |
| `ASYNCCODEBENCH_HARNESS_V2.md` | Native `task_id`-based runner, protocol guarantees, dry-run, and four-protocol commands. |
| `EVALUATION_BRANCH_QUICKSTART.md` | Short clone-to-four-protocol guide for the reproducible evaluation branch. |
| `CODEX_ONBOARDING.md` | First-read guide for a new coding-agent session. |
| `GITHUB_COLLABORATOR_HANDOFF.md` | What to commit, what not to commit, and how collaborators should clone/setup. |
| `MODEL_EXPERIMENT_RUNBOOK.md` | Main guide for running another model across the official 17 tasks. |
| `LOCAL_VLLM_EXPERIMENT_RUNBOOK.md` | Main local-vLLM guide: capacity, networking, environment, smoke gates, and failure diagnosis. |
| `VLLM_QWEN_LOCAL_RUNBOOK.md` | Local vLLM/Qwen setup, Docker networking, tool calling, and smoke tests. |
| `GEMMA4_CAID_HARNESS_FIX.md` | Gemma 4 parser/version gate, CAID remote-lifecycle fix, and result-validity rules. |
| `COLLABORATOR_RUNBOOK.md` | General collaborator setup and repository release notes. |
| `AGENT_EXPERIMENT_RUNBOOK.md` | Lower-level agent runner commands and debugging checks. |
| `EVALUATION_METRICS.md` | Metric definitions and post-run analysis rules. |

## Task Construction And Methodology

| Document | Use |
| --- | --- |
| `protocols/COMMIT0_DATA_AND_METRIC_LABEL_GUIDE_v0.3.md` | How task and dependency labels are defined. |
| `protocols/README.md` | Protocol documents for v0.3 construction. |
| `design/COMMIT0_TO_ASYNCCODEBENCH_PIPELINE_v0.1.md` | Pipeline framing for converting public coding tasks. |
| `design/paper_structure_reference.md` | Paper-structure reference and evaluation framing. |

## Task-specific Runner Notes

| Document | Use |
| --- | --- |
| `COOKIECUTTER_RUNNER_EVALUATOR_FIX.md` | `cookiecutter` evaluator, dependency, and transient test-artifact notes. |
| `FLASK_EVALUATOR_COMPATIBILITY_FIX.md` | `flask` evaluator compatibility notes. |

## Official Experiment Set

The current official model-comparison set contains 17 tasks:

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

Excluded from the current official aggregate:

```text
fastapi
python-progressbar
fabric
chardet
```
