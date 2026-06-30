# AsyncCodeBench Paper Structure Reference

This note summarizes the paper organization style we want to borrow from:

- MLAgentBench: <https://arxiv.org/pdf/2310.03302>
- Multi-SWE-bench: <https://arxiv.org/pdf/2504.02605>

The goal is not to copy their content, but to adopt their benchmark-paper structure:

1. Define the benchmark and task format first.
2. Explain how the benchmark is constructed.
3. Describe the agent/environment/execution protocol.
4. Define evaluation metrics.
5. Present results with figures, tables, traces, and case studies.

For AsyncCodeBench, the central story should be:

> AsyncCodeBench transforms public executable coding benchmarks into dependency-aware asynchronous multi-agent benchmark instances. It evaluates whether agent teams can resolve cross-agent software dependencies under delayed visibility, private workspaces, and late integration.

## What We Like From The Reference Papers

### MLAgentBench

MLAgentBench is useful because it treats the **agent interaction process** as part of the benchmark, not just the final answer.

Key structural ideas to borrow:

- It defines each task with a task description, starter files, and evaluator.
- It defines a general environment with actions such as reading files, writing files, editing files, and executing code.
- It records interaction traces: actions, responses, observations, and workspace snapshots.
- It evaluates not only final success, but also efficiency and qualitative process behavior.
- It uses figures to show the agent loop and tables to define the action space.

How this maps to AsyncCodeBench:

- We should define each AsyncCodeBench task using standardized artifacts:
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

How this maps to AsyncCodeBench:

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
- AsyncCodeBench exposes these failures using public-test-observable dependency points.

Suggested contribution bullets:

- A benchmark transformation methodology that converts public coding tasks into dependency-aware asynchronous multi-agent tasks.
- A curated set of human-reviewed AsyncCodeBench instances.
- Standardized task, scenario, quality, and metric manifests.
- Execution protocols that isolate synchronous vs asynchronous coordination effects.
- Async-specific metrics that go beyond final success.

### 2. Background And Motivation

Purpose:

- Explain the gap between existing coding benchmarks and asynchronous multi-agent coding.
- Position AsyncCodeBench relative to SWE-bench, Commit0, Multi-SWE-bench, and agent benchmarks.

Main points:

- Public coding benchmarks provide executable tasks and final tests.
- They usually do not encode cross-agent dependencies.
- Multi-agent evaluation is often reduced to "more agents solve the same task", which does not isolate async coordination.
- AsyncCodeBench focuses on dependency resolution under delayed visibility and late integration.

This section should be short. The main technical content should start in Section 3.

### 3. AsyncCodeBench

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

> We do not synthesize toy tasks from scratch. AsyncCodeBench transforms public executable coding tasks into asynchronous multi-agent scenarios while preserving the original coding objective.

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

- stale assumption rate;
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

This section should be more formal than a plain list. Include formulas where possible.

#### 5.1 Final Correctness

Basic metric:

```text
FSR = (# successful runs) / (# total runs)
```

This is necessary but insufficient.

#### 5.2 Dependency Resolution Score

For task `i` with dependency probes `D_i`:

```text
DRS_i = (1 / |D_i|) * sum_{d in D_i} pass(d)
```

Meaning:

- measures whether dependency contracts are resolved;
- can reveal partial dependency success even when final tests fail;
- can reveal brittle final success when dependency probes fail.

#### 5.3 Stale Assumption Rate

For consumer-side attempts `A_c`:

```text
SAR_i = (# consumer attempts based on outdated producer contract) / |A_c|
```

Meaning:

- directly captures async delayed-visibility failure;
- especially important for async-private execution.

#### 5.4 Failed Subagent Attempt Rate

```text
FSAR_i = (# failed subagent attempts) / (# total subagent attempts)
```

Meaning:

- measures wasted work under decomposition;
- useful for comparing serial, async-private, and manager-mediated protocols.

#### 5.5 Integration Failure Rate

```text
IFR_i = (# runs with merge, import, or integration failure) / (# total runs)
```

Meaning:

- captures failures after text patches are combined;
- includes merge conflicts, import breakage, incompatible contracts, and late evaluator failures.

#### 5.6 Scope Violation Rate

```text
SVR_i = (# agents modifying out-of-scope files) / (# total agents)
```

Meaning:

- measures whether agents respect assigned ownership boundaries;
- important for validating task decomposition and protocol compliance.

#### 5.7 Manager Recovery Rate

For failures observed before manager repair:

```text
MRR_i = (# recovered dependency or integration failures) / (# detected dependency or integration failures)
```

Meaning:

- isolates the benefit of manager-mediated async coordination;
- should be reported only for protocols where manager repair is available.

#### 5.8 Cost And Runtime

Recommended metrics:

- wall-clock time;
- token count;
- API cost;
- number of agent turns;
- number of subagent attempts;
- number of merge/review cycles.

### 6. Experiments

The experiments should be organized around the async story, not only aggregate success.

#### 6.1 Overall Performance

Main comparison:

- single-agent;
- synchronous specialist handoff;
- asynchronous private workspace;
- manager-mediated async recovery.

Main table:

- final success rate;
- dependency resolution score;
- stale assumption rate;
- integration failure rate;
- cost.

#### 6.2 Does Async Visibility Loss Hurt?

Compare:

- synchronous specialist handoff vs asynchronous private workspace.

Expected analysis:

- if serial succeeds but async-private fails, the failure is likely coordination-related;
- report success drop and DRS drop;
- use task-level heatmap.

#### 6.3 Can Manager-Mediated Coordination Recover?

Compare:

- async-private vs manager-mediated async recovery.

Expected analysis:

- manager should reduce stale assumptions and integration failures;
- manager may increase cost and runtime;
- failures that remain are valuable case studies.

#### 6.4 Final Success vs Process Diagnostics

Purpose:

- show why final pass rate is incomplete.

Examples:

- final pass but low DRS;
- final fail but high DRS;
- same final result but different stale assumption and failed attempt rates;
- manager succeeds after detecting and repairing async failures.

#### 6.5 Cost And Efficiency

Report:

- token usage;
- wall-clock time;
- number of subagent attempts;
- manager review cycles;
- cost per successful run.

This mirrors MLAgentBench's efficiency analysis while adapting it to async coding.

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

> AsyncCodeBench is not primarily a new collection of coding tasks. It is a dependency-aware transformation and evaluation protocol for asynchronous multi-agent coding.

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
- AsyncCodeBench creates dependency-aware async instances from public coding tasks;
- execution protocols isolate synchronous vs asynchronous visibility conditions;
- metrics expose stale assumptions, integration failures, and manager recovery.

## Recommended Figures

### Figure 1: AsyncCodeBench Transformation Pipeline

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
  -> AsyncCodeBench Instance
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

- final success rate;
- dependency resolution score.

### Figure 6: Async Failure Heatmap

Rows:

- tasks.

Columns:

- stale assumption rate;
- failed subagent attempt rate;
- integration failure rate;
- scope violation rate;
- manager recovery rate.

Purpose:

- show that different tasks expose different async failure modes.

### Figure 7: Case Study Timeline

Purpose:

- show one concrete async failure from trace data.

Suggested sequence:

```text
T0: agents start from same base
T1: producer changes dependency contract
T2: consumer writes code assuming old contract
T3: patches merge cleanly
T4: dependency probe fails
T5: manager detects and repairs, or final evaluation fails
```

### Figure 8: Cost vs Success

Purpose:

- mirror MLAgentBench's efficiency analysis.

Plot:

- x-axis: cost or tokens;
- y-axis: final success or dependency resolution;
- points grouped by protocol.

## Recommended Tables

### Table 1: AsyncCodeBench Task Overview

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
- interpretation.

### Table 4: Main Results

Columns:

- protocol;
- final success rate;
- dependency resolution score;
- stale assumption rate;
- integration failure rate;
- cost;
- runtime.

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

| Paper | What It Does Well | What AsyncCodeBench Should Borrow |
| --- | --- | --- |
| MLAgentBench | Defines environment, actions, traces, evaluator, and agent loop | Define async execution protocols, trace evidence, and process metrics |
| Multi-SWE-bench | Presents systematic benchmark construction and validation | Present dependency-aware transformation pipeline and human validation |
| AsyncCodeBench | Converts public coding tasks into async dependency scenarios | Combine construction pipeline, execution protocols, and async metrics |

## One-Sentence Paper Thesis

> AsyncCodeBench is a dependency-aware transformation framework and benchmark for evaluating whether asynchronous software-agent teams can resolve cross-agent implementation contracts under delayed visibility, private workspaces, and late integration.

