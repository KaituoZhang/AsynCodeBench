# AsynCodeBench Result Validity

This document defines when a completed run may enter a public AsynCodeBench
aggregate. Result admission is separate from task scoring: a model may fail the
coding task and still produce valid benchmark evidence.

## Two Validation Commands

Use `inspect-run` for any old or new run directory. It checks the evaluator,
model-execution evidence, traces, dependency probes, cost, runtime, and known
infrastructure errors without requiring a bundle:

```bash
cd reproductions/async-swe-agents
uv run asyncodebench inspect-run \
  outputs/asyncodebench/v0.3/<model>/<task>/<protocol>/<run-id>
```

Use `validate-run` for a new formal result. In addition to the health checks,
it validates `run_bundle.json` against the public JSON Schema, verifies every
indexed file checksum, rejects unindexed late files, and checks identity and
snapshot consistency:

```bash
uv run asyncodebench validate-run \
  outputs/asyncodebench/v0.3/<model>/<task>/<protocol>/<run-id>
```

Neither command calls the model or reruns the evaluator.

## Run Status

Every formal bundle has one status:

| Status | Meaning | Public aggregate |
| --- | --- | --- |
| `valid` | Execution and instrumentation evidence is complete. | Eligible if every metric, profile, and provenance flag is also true. |
| `review_required` | Evidence is complete enough to inspect, but an ambiguous condition requires adjudication. | Not eligible until reviewed. |
| `invalid` | Infrastructure, evaluator, trace, identity, or integrity evidence is broken. | Not eligible. |

The following are valid model outcomes, not infrastructure failures:

- final public tests fail;
- the agent reaches its iteration limit;
- an agent makes no commit;
- a specialist artifact is rejected for a writable-scope violation;
- merge or semantic integration fails because of the generated patch;
- dependencies remain unresolved;
- model-generated code causes test collection failure or evaluator timeout.

The following invalidate a formal run:

- provider, authentication, transport, or remote-run failure;
- OpenHands client/server version or event-schema mismatch;
- `termination_reason=execution_error` or an observed zero-iteration run;
- context-window or model-server configuration failure;
- no evidence that the model executed;
- wrong evaluator source;
- missing or malformed evaluator evidence;
- a final evaluator that silently reports zero collected tests;
- missing, malformed, or incomplete dependency checkpoints;
- multiple run logs from a reused output directory;
- manifest, profile, identity, schema, or artifact checksum mismatch.

## Metric-Specific Eligibility

`run_bundle.json` records six independent flags:

| Flag | Required evidence |
| --- | --- |
| `functional_metrics` | The manifest evaluator ran and produced a classifiable outcome. |
| `dependency_metrics` | Probe records are valid and include the complete final selector set. |
| `efficiency_metrics` | Runtime, cost/process telemetry, and model-execution evidence are available. |
| `official_profile` | Recorded settings match the released execution profile. |
| `provenance_complete` | Required model, adapter, prompt checksum, model-server descriptor, generation configuration, code revision, source SHA, and manifest checksums are recorded. |
| `official_aggregate` | The run is valid and every evidence, profile, and provenance flag above is true. |

This prevents one missing metric family from being silently treated as a zero
or from contaminating unrelated statistics.

## Aggregate Admission

The per-task summarizer revalidates each native bundle's schema, checksums,
identity, and health before copying its status and six eligibility flags into
CSV and artifact-index records. The checked-in model aggregator then fails
closed: it rejects a row unless `official_aggregate_eligible=true`.

```bash
reproductions/async-swe-agents/.venv/bin/python \
  scripts/aggregate_model_task_results.py \
  --input-dir outputs/reports/<model-tag> \
  --output-dir outputs/reports/<model-tag> \
  --model-tag <model-tag>
```

For migration analysis only, `--allow-ineligible` permits legacy or exploratory
rows and labels the generated Markdown as exploratory. Do not use that flag to
produce a paper's official result table.

The analysis layer also requires a positive collected-test count before it can
set `final_success=true`. Consequently, an evaluator process that exits zero
but silently collects no tests cannot appear as a successful coding run.

The model-level aggregator also checks campaign lineage. For an official table,
the model ID, bundle-recorded agent-adapter class, code/version, configuration
SHA, and execution-profile ID and SHA256 must be consistent, and the four
protocols for each task must share one recorded
generation-configuration SHA. The adapter recorded by the harness is
authoritative; a reporting command cannot replace it with an arbitrary label.
The aggregator emits `<model>_<N>task_campaign_manifest.json`, which links every
row to its run-bundle, per-task CSV, and artifact-index checksums. A task subset
is labeled `official_profile_subset`, never presented as a complete 16-task
score.

## Minimum Public Result Package

Publish enough evidence for another researcher to verify the table without
rerunning the model:

1. the benchmark release tag and release-index checksum;
2. every selected `run_bundle.json` and its indexed raw artifacts, or a
   checksum-verifiable archive containing them;
3. the generated campaign manifest and aggregate tables;
4. the declared repetition count and aggregation policy;
5. a ledger of infrastructure-invalid attempts that were rerun, including the
   replacement run IDs;
6. model and effective subagent IDs, adapter identity/configuration SHA,
   execution-profile ID/SHA, and generation-configuration SHA;
7. the release's automated-audit and independent-human-review completion
   counts.

Do not publish only a copied CSV. The campaign manifest proves which validated
runs produced each row; the run bundles prove the underlying evaluator,
dependency, efficiency, and provenance evidence.

## Reporting And Retry Policy

The current aggregator selects one run for each task-protocol cell and produces
descriptive statistics over tasks. It does not turn one stochastic run into a
confidence interval or significance claim.

For a public campaign:

1. declare the number of repetitions per cell before reporting results;
2. when using one run per cell, label the table as a single-run evaluation;
3. do not rerun a valid model failure to select a better trajectory;
4. rerun only `invalid` infrastructure/evaluator executions, use a new run ID,
   and retain the invalid directory or its health record;
5. if repeated runs are used, publish every valid repetition and report the
   aggregation method and uncertainty separately from the one-run table;
6. report exact model/subagent IDs, adapter, profile ID, generation-config SHA,
   benchmark/runner revisions, and the campaign-manifest checksum.

When `LLM_SUBAGENT_MODEL` is empty, the runner uses the manager model for all
assignments and records that effective model ID in `subagent_model`. An empty
recorded subagent identity is therefore invalid for a new formal aggregate.

These rules are methodological declarations rather than claims that the local
filesystem can prevent deletion or selective disclosure. Public raw bundles
and immutable campaign manifests provide the evidence needed to audit them.

## Official Execution Profile

The authoritative profile is
[`configs/evaluation/official_execution_profile.v2.json`](../configs/evaluation/official_execution_profile.v2.json).
It fixes a 100-model-response hard cap for each model-facing agent run and the
probe/evaluator timeouts used by the official aggregate. `FinishTool` remains
the normal early-completion signal; hitting the cap is a distinct termination
outcome. The preserved v1 file defines the historical 30-response profile.
Each run stores:

- the profile ID and SHA256;
- an exact `execution_profile_snapshot.json`;
- observed settings;
- any deviations from the profile.

A healthy run with a budget deviation remains useful exploratory evidence, but
`official_profile` and `official_aggregate` are false. Model-specific serving
settings are not forced to be identical across model families; they must be
fully recorded in `run_metadata.json` and held fixed across the four protocols
being compared for one model-task pair.

Generation parameters in `run_metadata.json` state whether each value came
from the environment or was left to the SDK/provider default. Explicit values
are preferable for a public campaign. When a provider default is unavoidable,
keep the endpoint/model revision fixed and disclose that source instead of
inventing an effective value the harness cannot verify.

API keys are never recorded. Common credential fields nested inside optional
JSON generation/server configuration are recursively replaced with
`[REDACTED]`; do not place secrets in benchmark configuration fields even with
this defense in place.

Historical scenario fields such as `step_budget_per_agent` remain construction
provenance. The released execution profile is the public comparison contract.

## Immutable Bundle

New native runs contain the following required evidence:

```text
run_metadata.json
task_snapshot.json
scenario_snapshot.json
scenario_manifest_snapshot.json
metrics_snapshot.json
quality_snapshot.json
execution_profile_snapshot.json
protocol.json
report.json
dependency_probe_checkpoints.jsonl
process_metrics_summary.json
cost.json
runtime.txt
run_bundle.json
```

The bundle recursively indexes run logs, agent traces, handoffs, scope records,
patches, and final-repository archives when present. `patch.diff` and
`final_repo/` are useful model artifacts, but they are not required when a
valid failure produces no patch.

Do not add derived tables or edit artifacts inside a bundled run directory.
Write post-processing outputs elsewhere; otherwise checksum validation will
correctly treat the run directory as changed.

`scenario_manifest_snapshot.json` is the exact released four-scenario source
document. `scenario_snapshot.json` is the one active scenario selected for this
run. Keeping both makes the source checksum verifiable without obscuring the
actual execution contract.

Task-level annotations and bootstrap overlays are frozen separately in
`manifests/release/v0.3/task_index.json`. Runtime bundles snapshot only the
contracts actually consumed during execution; the release index supplies the
complete dataset and label lineage.

Automatic task qualification, automated annotation audit, and independent
human review are distinct states. The release index reports each separately;
an executable run bundle does not by itself certify that human annotation and
adjudication are complete.

The machine-readable release stage is exposed by:

```bash
uv run asyncodebench release-status --require preview
uv run asyncodebench release-status --require stable
```

The preview gate requires all released tasks to pass automatic qualification.
The stable gate additionally requires 16/16 independent human reviews and at
least one checksum-registered public baseline bundle. Missing evidence remains
an explicit nonzero gate rather than being inferred from prose.

## Existing Results

Do not rerun an old campaign blindly. First run `inspect-run` over every
task-protocol directory:

1. retain `valid` coding failures and successes as legacy evidence;
2. exclude or rerun only infrastructure-invalid runs;
3. review ambiguous runs separately;
4. label runs created before the execution-profile snapshot as legacy rather
   than claiming new-bundle compliance.

A new official public aggregate should use bundles created by the current
harness. Historical results can remain in an appendix or migration analysis as
long as their harness revision and validity tier are explicit.
