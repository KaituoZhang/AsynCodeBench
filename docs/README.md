# AsyncCodeBench Docs

Start here when onboarding a collaborator or a new Codex session.

## Main Entry Points

| Document | Use |
| --- | --- |
| `CODEX_ONBOARDING.md` | First-read guide for a new coding-agent session. |
| `GITHUB_COLLABORATOR_HANDOFF.md` | What to commit, what not to commit, and how collaborators should clone/setup. |
| `MODEL_EXPERIMENT_RUNBOOK.md` | Main guide for running another model across the official 17 tasks. |
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

