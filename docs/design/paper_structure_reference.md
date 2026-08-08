# AsynCodeBench Paper Structure Reference

This note summarizes the paper organization style we want to borrow from:

- MLAgentBench: <https://arxiv.org/pdf/2310.03302>
- Multi-SWE-bench: <https://arxiv.org/pdf/2504.02605>

The goal is not to copy their content, but to adopt their benchmark-paper structure:

1. Define the benchmark and task format first.
2. Explain how the benchmark is constructed.
3. Describe the agent/environment/execution protocol.
4. Define evaluation metrics.
5. Present results with figures, tables, traces, and case studies.

For AsynCodeBench, the central story should be:

> AsynCodeBench transforms public executable coding benchmarks into dependency-aware asynchronous multi-agent benchmark instances. It evaluates whether agent teams can resolve cross-agent software dependencies under delayed visibility, private workspaces, and late integration.

## What We Like From The Reference Papers

### MLAgentBench

MLAgentBench is useful because it treats the **agent interaction process** as part of the benchmark, not just the final answer.

Key structural ideas to borrow:

- It defines each task with a task description, starter files, and evaluator.
- It defines a general environment with actions such as reading files, writing files, editing files, and executing code.
- It records interaction traces: actions, responses, observations, and workspace snapshots.
- It evaluates not only final success, but also efficiency and qualitative process behavior.
- It uses figures to show the agent loop and tables to define the action space.

How this maps to AsynCodeBench:

- We should define each AsynCodeBench task using standardized artifacts:
  - source public coding task;
  - dependency labels;
  - scenario manifest;
  - quality manifest;
  - async metrics manifest;
  - optional bootstrap overlays;
  - human annotation.
- We should treat execution traces as benchmark outputs:
  - agent actions;
  - subagent patches;
  - merge events;
  - failed attempts;
  - dependency probe outcomes;
  - final evaluator results.
- We should include an execution protocol diagram, not only result tables.

### Multi-SWE-bench

Multi-SWE-bench is useful because it presents itself as a serious benchmark construction paper.

Key structural ideas to borrow:

- It has a clear benchmark construction pipeline.
- It explains task selection, filtering, environment construction, and manual verification.
- It reports dataset statistics and task categories.
- It evaluates several agent methods under a shared benchmark.
- It uses many figures beyond tables: construction pipeline, dataset statistics, complexity analysis, and performance breakdowns.

How this maps to AsynCodeBench:

- We should emphasize the transformation pipeline:
  - public coding task selection;
  - dependency point identification;
  - producer/consumer repartitioning;
  - async scenario generation;
  - metric manifest generation;
  - validation gates;
  - human annotation and adjudication.
- We should report not only final pass rates, but also async-specific process metrics.
- We should show dataset statistics for the 18 ready tasks:
  - dependency types;
  - number of agents;
  - number of dependency probes;
  - writable path boundaries;
  - overlay usage;
  - task status.

## Recommended Paper Structure

### 1. Introduction

Purpose:

- Introduce the limitation of existing coding benchmarks.
- Explain why final pass rate is insufficient for asynchronous multi-agent coding.
- State the core contribution: a dependency-aware transformation pipeline and benchmark for asynchronous agent teams.

Main points:

- Existing coding benchmarks evaluate whether a final patch passes tests.
- Multi-agent coding introduces additional failure modes:
  - stale assumptions;
  - delayed dependency visibility;
  - private workspace divergence;
  - late integration failures;
  - duplicated or conflicting work;
  - insufficient manager recovery.
- AsynCodeBench exposes these failures using public-test-observable dependency points.

Suggested contribution bullets:

- A benchmark transformation methodology that converts public coding tasks into dependency-aware asynchronous multi-agent tasks.
- A curated set of human-reviewed AsynCodeBench instances.
- Standardized task, scenario, quality, and metric manifests.
- Execution protocols that isolate synchronous vs asynchronous coordination effects.
- Async-specific metrics that go beyond final success.

### 2. Background And Motivation

Purpose:

- Explain the gap between existing coding benchmarks and asynchronous multi-agent coding.
- Position AsynCodeBench relative to SWE-bench, Commit0, Multi-SWE-bench, and agent benchmarks.

Main points:

- Public coding benchmarks provide executable tasks and final tests.
- They usually do not encode cross-agent dependencies.
- Multi-agent evaluation is often reduced to "more agents solve the same task", which does not isolate async coordination.
- AsynCodeBench focuses on dependency resolution under delayed visibility and late integration.

This section should be short. The main technical content should start in Section 3.

### 3. AsynCodeBench

This should be the main benchmark-construction section, similar in role to the benchmark sections in MLAgentBench and Multi-SWE-bench.

#### 3.1 Source Task Selection

Explain the input requirements:

- public coding benchmark task;
- executable repository;
- test-backed evaluation;
- identifiable base and target states;
- task has natural cross-module or cross-component dependencies;
- no private oracle or hidden manual solution needed for construction.

Important phrasing:

> We do not synthesize toy tasks from scratch. AsynCodeBench transforms public executable coding tasks into asynchronous multi-agent scenarios while preserving the original coding objective.

#### 3.2 Dependency-Aware Transformation Pipeline

This is the methodological core.

Pipeline:

1. Start from a public coding task.
2. Inspect original tests, target implementation, and code structure.
3. Identify public-test-observable dependency points.
4. Label producer and consumer responsibilities.
5. Split writable paths and task instructions by agent role.
6. Define dependency probes and final evaluation targets.
7. Generate standardized manifests.
8. Run automatic validation gates.
9. Send artifacts to human annotation and adjudication.

Important phrasing:

> The repartitioning changes the evaluation scenario and agent ownership boundaries, not the underlying task objective.

#### 3.3 Public-Test-Observable Dependency Points

This should be a named concept.

Definition:

> A dependency point is public-test-observable when a producer-side implementation decision creates a contract that downstream consumer code must respect, and the correctness of that contract can be checked by public tests, probe tests, or evaluator evidence.

Examples:

- parser output shapes consumed by high-level APIs;
- normalization utilities consumed by core logic;
- registry/schema contracts consumed by nested behavior;
- shared type or state contracts consumed by downstream modules;
- cache key or serialization contracts consumed across files.

Why this matters:

- It prevents arbitrary or artificial task splitting.
- It makes async failures measurable.
- It supports human validation.

#### 3.4 Artifact Standardization

List the artifacts produced for each task:

- task manifest;
- scenario manifest;
- quality manifest;
- async metrics manifest;
- optional bootstrap overlay metadata;
- annotation form;
- curated config entry.

Explain what each artifact does:

- task manifest: provenance, repo, commit, evaluator targets;
- scenario manifest: agent roles, writable paths, dependency edges;
- quality manifest: validation status and inclusion decision;
- metrics manifest: dependency probes and async process metrics;
- annotation form: human judgment about dependency validity and scenario quality.

#### 3.5 Validation Gates

Separate automatic validation from human annotation.

Automatic gates:

- JSON schema validation;
- file existence checks;
- repo provenance checks;
- overlay checksum checks;
- initial and complete evaluator sanity checks;
- dependency probe existence;
- metrics manifest completeness;
- curated config consistency.

Human review:

- dependency is real, not artificial;
- producer/consumer split is natural;
- writable boundaries are reasonable;
- probes actually test the dependency;
- overlays are non-solution bootstrap patches;
- task is suitable for asynchronous evaluation.

#### 3.6 Dataset Summary

Report the current dataset.

Current intended status:

- 18 qualification-ready tasks.
- FastAPI and python-progressbar are excluded or marked needs revision.
- Fabric is excluded.
- Chardet is included after metadata integration.

Use a table here.

Recommended columns:

- task;
- source repo;
- dependency type;
- number of agents;
- dependency edges;
- probe count;
- overlay count;
- status.

### 4. Execution Protocols

This section should correspond to MLAgentBench's environment/agent sections, but focused on asynchronous coding.

Important framing:

> These protocols are not merely competing agent products. They are controlled visibility and synchronization conditions designed to isolate where asynchronous dependency failures arise.

#### 4.1 Single-Agent Coding

Purpose:

- ability baseline;
- one agent sees the full task and can modify all relevant files;
- no cross-agent coordination required.

What it tells us:

- whether the base model can solve the coding task at all;
- whether failures are due to coding difficulty rather than multi-agent coordination.

#### 4.2 Synchronous Specialist Handoff

Purpose:

- controlled specialist decomposition without async staleness;
- agents run in dependency order;
- downstream agents see upstream changes before starting.

What it tells us:

- whether the scenario split is feasible;
- whether specialist decomposition itself causes loss;
- what happens when dependency visibility is immediate.

#### 4.3 Asynchronous Private Workspace

Purpose:

- core async stress condition;
- agents start from the same base state;
- each agent works in a private workspace;
- no in-flight visibility;
- final integration happens after independent work.

What it tells us:

- stale assumption duration or proxy;
- dependency resolution failure;
- duplicated work;
- merge or integration failure;
- final success drop relative to synchronous handoff.

This is the most important protocol for the paper's async story.

#### 4.4 Manager-Mediated Async Recovery

Purpose:

- evaluate whether a manager can recover from async coordination problems;
- manager can inspect, delegate, review, merge, and request fixes;
- based on CAID-style centralized asynchronous isolated delegation.

What it tells us:

- manager recovery rate;
- whether coordination mechanisms reduce async-private failures;
- remaining failure modes after manager intervention.

### 5. Evaluation Metrics

This section should be formal, but it should keep the dependency-level metrics
front and center. The main paper should not replace the original v0.3 metrics
with generic agent-log statistics. The core evaluation unit is the labeled
cross-agent dependency, and the core question is:

> When did the run resolve the dependency that makes asynchronous coordination
> hard, and what coordination cost was required to get there?

The first-round AsynCodeBench metrics are the main evaluation metrics:

1. Traditional coding metrics: final tests, cost, tokens, and runtime.
2. Dependency-level metrics: `ADPR`, `DRS`, strict/composed `DRS`, upstream
   resolution, downstream resolution, `CAIL`, and `SAD`.
3. Coordination-level diagnostics: failed subagent rate, merge conflicts,
   scope violations, and manager recovery required.

Robotouille-style ideas such as budgeted success, progress-to-go, and repeated
failure can be discussed as optional extensions, but they should not replace
the v0.3 dependency metrics in the main evaluation.

#### 5.1 Traditional Coding Metrics

Final correctness:

```text
Final Pass = (# final evaluator tests passed) / (# final evaluator tests run)
```

For repeated runs:

```text
FSR = (# successful runs) / (# total runs)
```

Efficiency:

- `Cost`: API cost in dollars;
- `Tokens`: total input plus output tokens;
- `Runtime`: agent runtime and end-to-end wall-clock time.

These metrics are necessary anchors because they let readers compare
AsynCodeBench runs to traditional coding-agent benchmarks. Their limitation is
that they do not explain asynchronous dependency behavior. For example,
single-agent and multi-agent runs may both pass all final tests while resolving
cross-agent dependencies at very different times and costs.

#### 5.2 Async Dependency Pass Rate

For task `i` with labeled dependency points `D_i`:

```text
ADPR_i = (# resolved dependency points in D_i) / |D_i|
```

A dependency point is resolved when its required integrated probe tests pass in
the final integrated workspace. In task-level tables, `ADPR` may be reported
over all dependency points or over `primary_async_dependency_ids`; the
denominator must be stated.

Why this matters:

- uses the dependency labels directly;
- shows whether public-test-observable cross-agent contracts are ultimately
  satisfied;
- can distinguish partial dependency success from complete task failure;
- can expose brittle final success if final tests pass but dependency probes do
  not.

#### 5.3 Dependency Resolution Step

For dependency point `d`:

```text
DRS_d = first checkpoint or logical iteration where integrated_probe_tests(d) pass
```

`DRS` is one of the central AsynCodeBench metrics. It answers when a critical
cross-agent dependency was first observed to be resolved.

Report two variants when possible:

```text
strict DRS_d =
  first integrated checkpoint where upstream and downstream probes for d pass
  in the same integrated workspace
```

```text
composed DRS_d =
  max(upstream_resolution_step_d, downstream_resolution_step_d)
```

`strict DRS` is more conservative and should be preferred in main tables.
`composed DRS` is useful when upstream and downstream probes are observed at
different checkpoints.

#### 5.4 Upstream And Downstream Resolution

```text
upstream_resolution_step_d =
  first checkpoint where upstream_probe_tests(d) pass

downstream_resolution_step_d =
  first checkpoint where downstream_probe_tests(d) pass
```

These metrics use the producer/consumer labels in the metrics manifest. They
answer two separate questions:

- when the producer-side contract became correct;
- when the consumer-side code correctly adapted to that contract.

They are especially useful for case studies because they show whether a run was
blocked by the upstream implementation, the downstream adaptation, or the final
integration between them.

#### 5.5 Cross-Agent Integration Lag

```text
CAIL_d = downstream_resolution_step_d - upstream_resolution_step_d
```

`CAIL` measures how long downstream behavior lagged behind the producer-side
contract. A positive value indicates delayed downstream adaptation; a value
near zero can mean clean synchronization, or simply that the runner only
observed both sides at a final checkpoint. The paper should state the
checkpoint policy used for each experiment.

#### 5.6 Stale Assumption Duration

```text
SAD_d =
  duration or iteration interval where the consumer continues acting on a
  producer-contract assumption that has become stale
```

`SAD` is the primary stale-information metric in the v0.3 guide. It is better
aligned with the first-round cachetools analysis than a rate-only metric,
because it captures how long a downstream worker continued under an outdated
or unavailable producer contract.

Evidence can include:

- consumer edits to `consumer_files` before receiving the relevant producer
  artifact;
- consumer work after a producer update that is not visible to it;
- downstream probe failures after upstream probes already pass;
- duplicated implementation of a producer-side contract inside a consumer file.

Strict automatic `SAD` requires dependency-version visibility logs. Without
those logs, runs should report `SAD-proxy` and send candidate incidents to
human audit. A rate version can be added later:

```text
SAR_d = (# stale dependency-sensitive consumer attempts for d)
        / (# dependency-sensitive consumer attempts for d)
```

`SAR` is an extension of `SAD`, not a replacement.

#### 5.7 Coordination-Level Diagnostics

These metrics explain how a protocol reached its final result.

Failed subagent rate:

```text
Failed Subagent Rate =
  (# subagent attempts without a usable committed or merged artifact)
  / (# total subagent attempts)
```

Merge conflict count:

```text
Merge Conflict Count =
  # textual merge conflicts observed during integration
```

Scope violation count:

```text
Scope Violation Count =
  # agents modifying files outside their assigned writable paths
```

Manager recovery required:

```text
Manager Recovery Required =
  true if final success depends on manager review, merge repair, reassignment,
  or final recovery after failed subagent artifacts
```

These diagnostics are not generic bookkeeping. They are important because they
identify asynchronous collaboration burdens that final pass rate hides:
failed workers, conflicting artifacts, boundary drift, and recovery dependence.

#### 5.8 Evidence Support In Current Labels

Current AsynCodeBench v0.3 labels already support several core metrics, but
some async-specific measurements require improved execution traces.

| Metric | Current label support | What is already present | Extra trace needed |
| --- | --- | --- | --- |
| Final Pass / FSR | Strong | final evaluator and report files | none |
| Cost / tokens / runtime | Strong | cost/runtime logs | none |
| `ADPR` | Strong | `dependency_points`, integrated probes, resolution criteria | probe execution at final workspace |
| strict `DRS` | Strong if integrated checkpoints exist | integrated probes and checkpoint policy | probe results after each patch/artifact/checkpoint |
| composed `DRS` | Strong if upstream/downstream checkpoints exist | upstream/downstream probes | aligned logical turn IDs |
| upstream/downstream resolution | Strong if checkpoints exist | upstream and downstream probe groups | aligned checkpoint schedule |
| `CAIL` | Strong if upstream/downstream checkpoints exist | upstream and downstream probe groups | aligned logical turn IDs |
| `SAD` | Conceptual support | `stale_failure_mode`, producer/consumer files, message policies | contract versions, visible dependency versions, consumer attempt labels |
| Failed subagent rate | Strong | subagent result logs | none |
| Merge conflict count | Strong | manager review and merge logs | standardized conflict event type helps |
| Scope violation count | Strong | assignments and modified-file logs | none |
| Manager recovery required | Partial | manager review/final merge logs | explicit detected-failure and recovery links |

This table is important for the paper and the release. It shows that the
benchmark labels are not cosmetic: they directly support `ADPR`, `DRS`,
upstream/downstream resolution, and `CAIL`, while motivating the next
trace-instrumentation step needed for strict `SAD`.

Current v0.3 label inventory:

- 20 Commit0 metric manifests exist, including candidates that are currently
  excluded or revision-only.
- These manifests contain 58 dependency points.
- Every dependency point has producer/consumer subproblems, producer/consumer
  files, a contract summary, a stale-failure-mode description, upstream probes,
  downstream probes, integrated probes, and resolution criteria.
- 58/58 dependency points enable `ADPR`, `DRS`, and `CAIL`.
- 51/58 dependency points enable stale-assumption tracking (`SAD` in the
  manifest, reported as strict `SAD` when visibility logs exist or `SAD-proxy`
  when they do not).
- Paper experiments should filter to the curated qualification-ready set rather
  than blindly counting all metric manifests.

#### 5.9 Optional Extensions

These can be used later, but should not replace the first-round metrics:

- Budgeted Final Pass: final success under a fixed cost, call, or integration
  budget.
- Normalized Dependency Gap: `1 - ADPR`, useful for failed runs.
- Stale Assumption Rate: rate version of `SAD`.
- Repeated Failure Rate: repeated same-class probe, test, or integration
  failures during recovery.

### 6. Experiments

The experiments should be organized around the async story, not only aggregate success.

#### 6.1 Overall Performance

Main comparison:

- single-agent;
- synchronous specialist handoff;
- asynchronous private workspace;
- manager-mediated async recovery.

Main table:

- final tests / final pass;
- cost, tokens, and runtime;
- async dependency pass rate (`ADPR`);
- strict and composed dependency resolution step (`DRS`);
- upstream/downstream resolution and `CAIL`;
- stale assumption duration (`SAD`) or audited `SAD-proxy`;
- failed subagent rate, merge conflicts, scope violations, and manager recovery required.

#### 6.2 Does Async Visibility Loss Hurt?

Compare:

- synchronous specialist handoff vs asynchronous private workspace.

Expected analysis:

- if serial succeeds but async-private fails, the failure is likely coordination-related;
- report `ADPR`, strict/composed `DRS`, upstream/downstream resolution, `CAIL`, and `SAD` changes;
- use a task-level heatmap keyed by dependency points, not only by final success.

#### 6.3 Can Manager-Mediated Coordination Recover?

Compare:

- async-private vs manager-mediated async recovery.

Expected analysis:

- manager should reduce stale assumptions and integration failures;
- manager may increase cost and runtime;
- failed subagent rate, merge conflicts, scope violations, and manager recovery required should be reported as manager-specific diagnostics;
- failures that remain are valuable case studies.

#### 6.4 Final Success vs Process Diagnostics

Purpose:

- show why final pass rate is incomplete.

Examples:

- final pass but late strict `DRS` or nonzero `SAD`;
- final fail but high `ADPR`, showing partial dependency completion;
- same final result but different stale assumptions, merge conflicts, failed subagents, or scope violations;
- manager succeeds after detecting and repairing async failures.

#### 6.5 Cost And Efficiency

Report:

- token usage;
- wall-clock time;
- number of subagent attempts;
- manager review cycles;
- cost per successful run.

This mirrors MLAgentBench's efficiency analysis while adapting it to async coding.

Efficiency should be presented as a tradeoff against dependency quality, for
example cost versus `ADPR` or cost versus strict `DRS`, rather than as a standalone
leaderboard.

### 7. Case Studies

Use case studies to make async failures concrete.

Recommended case study types:

1. Successful async dependency resolution.
2. Stale consumer assumption after producer contract changes.
3. Late integration failure despite clean textual merge.
4. Manager-mediated recovery.
5. Scope violation or duplicated work.

Each case study should include:

- task name;
- dependency graph;
- agent assignment;
- timeline;
- final result;
- metric values;
- short explanation of the failure or recovery.

### 8. Related Work

Suggested organization:

- coding benchmarks: SWE-bench, Commit0, Multi-SWE-bench;
- agent benchmarks: MLAgentBench, AgentBench, WebArena;
- multi-agent collaboration benchmarks;
- software engineering coordination and integration;
- asynchronous/distributed agent systems.

Key distinction:

> AsynCodeBench is not primarily a new collection of coding tasks. It is a dependency-aware transformation and evaluation protocol for asynchronous multi-agent coding.

### 9. Limitations

Be explicit.

Likely limitations:

- current dataset size is modest;
- human annotation is required;
- dependency labels may require expert judgment;
- tasks are Python-heavy if the current set comes from Commit0;
- async protocols are controlled approximations of real development;
- metrics depend on trace quality and probe design.

Frame these as benchmark limitations, not fatal weaknesses.

### 10. Conclusion

Restate:

- existing final-test coding benchmarks miss async coordination failures;
- AsynCodeBench creates dependency-aware async instances from public coding tasks;
- execution protocols isolate synchronous vs asynchronous visibility conditions;
- metrics expose stale assumptions, integration failures, and manager recovery.

## Recommended Figures

### Figure 1: AsynCodeBench Transformation Pipeline

Purpose:

- show benchmark construction at a glance;
- analogous to construction pipeline figures in Multi-SWE-bench.

Suggested flow:

```text
Public Coding Benchmark
  -> Candidate Task Selection
  -> Dependency Point Identification
  -> Producer/Consumer Repartitioning
  -> Async Scenario Generation
  -> Metrics Manifest Generation
  -> Automatic Validation Gates
  -> Human Annotation
  -> AsynCodeBench Instance
```

### Figure 2: Execution Protocol Timeline

Purpose:

- visually distinguish single-agent, synchronous handoff, async-private, and manager-mediated execution.

Suggested rows:

- time axis;
- manager;
- producer agent;
- consumer agent;
- workspace visibility;
- merge/evaluation point.

This figure is essential because it makes the "async" contribution concrete.

### Figure 3: Dependency Graph Example

Purpose:

- show one task's producer/consumer dependency structure.

Recommended example:

- cachetools;
- requests;
- parsel;
- graphene.

The graph should label:

- producer files;
- consumer files;
- dependency point;
- probe tests;
- final evaluator tests.

### Figure 4: Dataset Statistics

Possible plots:

- dependency type distribution;
- number of agents per task;
- dependency probes per task;
- overlay count distribution;
- writable path count distribution.

### Figure 5: Main Performance Comparison

Grouped bars:

- single-agent;
- synchronous handoff;
- async-private;
- manager-mediated async recovery.

Metrics:

- final pass / final tests;
- async dependency pass rate;
- strict and composed dependency resolution step;
- upstream/downstream resolution and CAIL;
- stale assumption duration when available.

### Figure 6: Async Failure Heatmap

Rows:

- tasks.

Columns:

- async dependency pass rate;
- strict dependency resolution step;
- cross-agent integration lag;
- stale assumption duration or proxy;
- failed subagent rate;
- merge conflict count;
- scope violation count.

Purpose:

- show that different tasks expose different async failure modes.

### Figure 7: Case Study Timeline

Purpose:

- show one concrete async failure from trace data.

Suggested sequence:

```text
T0: agents start from same base
T1: producer exposes or changes dependency contract
T2: consumer writes dependency-sensitive code with stale or missing visibility
T3: patches merge cleanly
T4: dependency probe fails
T5: manager detects and repairs, or final evaluation fails
```

### Figure 8: Cost vs Success

Purpose:

- mirror MLAgentBench's efficiency analysis.

Plot:

- x-axis: cost or tokens;
- y-axis: final pass, async dependency pass rate, or strict dependency resolution step;
- points grouped by protocol.

## Recommended Tables

### Table 1: AsynCodeBench Task Overview

Columns:

- task;
- source benchmark;
- repository;
- dependency type;
- producer role;
- consumer role;
- number of probes;
- overlay count;
- status.

### Table 2: Execution Protocol Comparison

Columns:

- protocol;
- number of agents;
- workspace visibility;
- communication;
- merge timing;
- manager intervention;
- primary diagnostic purpose.

Example rows:

- single-agent;
- synchronous specialist handoff;
- async private workspace;
- manager-mediated async recovery.

### Table 3: Metric Definitions

Columns:

- metric;
- formula;
- required evidence;
- interpretation;
- current v0.3 support level.

### Table 4: Main Results

Columns:

- protocol;
- final pass / final tests;
- cost;
- tokens;
- runtime;
- async dependency pass rate;
- strict dependency resolution step;
- composed dependency resolution step;
- upstream resolution;
- downstream resolution;
- cross-agent integration lag;
- stale assumption duration or proxy;
- failed subagent rate;
- merge conflict count;
- scope violation count;
- manager recovery required.

### Table 5: Human Annotation And Validation

Columns:

- task;
- dependency validity;
- split naturalness;
- probe validity;
- overlay acceptability;
- adjudication result.

## Suggested Writing Emphasis

Use this framing repeatedly:

> The benchmark is not about whether multiple agents can be launched in parallel. It is about whether asynchronous agent teams can preserve and resolve cross-agent software dependencies when their work is hidden, delayed, and integrated late.

Avoid weak framing:

- "We split coding tasks into multiple agents."
- "We evaluate multi-agent coding."
- "We use Commit0 tasks."

Use stronger framing:

- "We transform public executable coding tasks into dependency-aware asynchronous benchmark instances."
- "We isolate visibility and synchronization as experimental variables."
- "We evaluate final correctness together with dependency-level and coordination-level process metrics."
- "We combine automatic validation gates with human annotation to control benchmark quality."

## Relation To The Two Reference Papers

| Paper | What It Does Well | What AsynCodeBench Should Borrow |
| --- | --- | --- |
| MLAgentBench | Defines environment, actions, traces, evaluator, and agent loop | Define async execution protocols, trace evidence, and process metrics |
| Multi-SWE-bench | Presents systematic benchmark construction and validation | Present dependency-aware transformation pipeline and human validation |
| AsynCodeBench | Converts public coding tasks into async dependency scenarios | Combine construction pipeline, execution protocols, and async metrics |

## One-Sentence Paper Thesis

> AsynCodeBench is a dependency-aware transformation framework and benchmark for evaluating whether asynchronous software-agent teams can resolve cross-agent implementation contracts under delayed visibility, private workspaces, and late integration.
