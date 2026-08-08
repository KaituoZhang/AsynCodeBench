# AsynCodeBench Specification v0.3

**Status:** Active first-paper specification  
**Date:** 2026-06-22  
**Scope:** Benchmark dataset, execution framework, and empirical evaluation  
**Supersedes for implementation:** `SPECIFICATION_v0.2.md`  
**Canonical location:** `SPECIFICATION_v0.3.md`

Version 0.3 narrows the first paper. Version 0.2 is retained as the long-term
measurement-science vision, but its full replay, oracle, intervention, and
runtime-factorization program is no longer required for the first release.

If a README, handoff, implementation note, or historical plan conflicts with
this document, v0.3 takes precedence for the first paper.

## 1. Project decision

The first AsynCodeBench paper will release:

1. a curated benchmark dataset of naturally decomposable coding tasks;
2. a reproducible asynchronous multi-agent execution framework;
3. evaluations of representative open-weight models and agent organizations;
4. trajectory-level failure analysis focused on stale assumptions,
   communication, testing, and semantic integration.

The first paper will not train FreshGRPO or another learned coordination
policy.

AsynCodeBench is not a new collection of synthetic coding problems. It
extends official or existing repository-level tasks with:

- qualification metadata;
- natural subproblem and dependency annotations;
- asynchronous multi-agent scenarios;
- private workspaces and controlled information visibility;
- reproducible prompts, tools, integration, and evaluation;
- process logs and software-specific collaboration metrics.

## 2. Motivation and positioning

Existing repository-level coding benchmarks primarily ask whether an agent can
produce a correct final patch. Existing multi-agent benchmarks primarily study
communication and collaboration in simulated, general, or embodied
environments.

AsynCodeBench targets the missing intersection:

```text
real repository-level coding tasks
+
asynchronous LLM agent teams
+
private and potentially stale local state
+
delayed communication, testing, review, and integration
```

The benchmark studies what happens when one agent continues working while
another agent's relevant semantic change or tool result is hidden and in
flight.

The defensible novelty is not "the first multi-agent coding benchmark." The
contribution is a standardized dataset and framework for evaluating
asynchronous coordination failures in real software-engineering tasks.

## 3. First-paper research questions

### RQ1 — Asynchronous degradation relative to single-agent and serial baselines

When the same coding scaffold is evaluated as a single agent, serial
specialists, and asynchronous specialists, how much task quality or efficiency
is lost when agents work concurrently from private state?

The minimum comparison is:

1. strong iterative single agent;
2. serial specialists with the same decomposition;
3. asynchronous private-workspace specialists;
4. asynchronous specialists with structured messages or artifact transfer.

The intended benchmark hypothesis is that asynchronous private-state execution
will often underperform the strong single-agent or serial-specialist controls
because of stale assumptions, delayed feedback, and integration mismatch.
This is a hypothesis to test, not a result to encode into the benchmark.

### RQ2 — Effects of model capacity and task structure

How do model capacity and task parallelizability affect asynchronous
degradation and recovery?

The minimum evaluation includes:

- two open-weight model capacities;
- `parallelizable`, `partially_parallelizable`, and `effectively_serial`
  tasks where available;
- single-agent and serial-specialist baseline reporting for every evaluated
  task;
- per-task and per-class reporting.

### RQ3 — Failure modes of asynchronous coding teams

Which failures recur across models, tasks, and agent organizations?

The initial taxonomy includes:

- local implementation failure;
- task-decomposition failure;
- stale assumption;
- missing or ineffective communication;
- duplicated or wasted work;
- delayed-test adaptation failure;
- semantic integration failure;
- textual patch conflict;
- reviewer/integrator failure;
- tool or environment failure.

The paper's main empirical contribution is a systematic account of these
failures, not a claim that every failure is proactive coordination failure.

## 3.1 Experimental principle: strong agents, weak asynchrony

AsynCodeBench must not obtain a negative asynchronous result by weakening the
worker agents.

The same iterative coding scaffold must be used for:

- the single agent;
- each serial specialist;
- each asynchronous specialist.

Each agent must be allowed to:

```text
inspect/search
-> edit
-> run targeted tests
-> read observations
-> repair
-> repeat
-> submit
```

The benchmark should expose weakness in the asynchronous organization, not in
an artificially single-shot agent interface.

A task is still a valid benchmark item when current models fail it. However,
when interpreting asynchronous degradation, the paper must report whether the
same model and scaffold also fail in the single-agent or serial-specialist
conditions. If all conditions fail locally, the result is a model/task
difficulty finding rather than evidence of asynchronous coordination failure.

## 4. First-paper contributions

The paper should make three primary contributions.

### C1 — Curated asynchronous coding dataset

A released dataset derived from Commit0 and qualified SWE-bench tasks,
including:

- upstream task identity and version;
- public task statement;
- relevant repository and evaluator metadata;
- qualification card;
- natural subproblems;
- dependency and integration annotations;
- recommended asynchronous scenarios;
- inclusion/exclusion decision and rationale.

### C2 — Reproducible execution framework

A framework that:

- creates isolated agent workspaces;
- supplies controlled task and role context;
- runs iterative single and multi-agent coding loops;
- supports file inspection and editing;
- returns test and command observations to agents for subsequent repair;
- executes concurrent model, test, and message jobs;
- transfers messages or artifacts according to the condition;
- integrates agent outputs;
- saves prompts, responses, files, patches, tests, timing, and costs.

### C3 — Model and organization evaluation

An evaluation across representative model capacities and agent organizations,
with:

- official task results;
- cost and latency;
- communication and integration statistics;
- failure taxonomy;
- qualitative trajectory examples.

## 5. Claims excluded from the first paper

The first paper must not claim:

- the first multi-agent coding system;
- the first asynchronous software-agent framework;
- the first coding benchmark;
- a learned coordination policy;
- GRPO, LoRA, or reinforcement learning;
- a causal state-oracle coordination gap;
- replay-to-live equivalence;
- that runtime consistency cannot eliminate coordination failures;
- that one communication policy is universally optimal;
- that every team failure is caused by asynchronous coordination.

These questions may be studied in later AsynCodeBench releases.

## 6. First-release benchmark assets

The minimum public release contains:

```text
tasks/
  qualification cards
  included and excluded task records
  upstream versions

scenarios/
  agent organizations
  natural subproblem assignments
  information visibility
  communication/review conditions

framework/
  workspace materialization
  model adapter
  file and test tools
  integration
  logging

runs/
  prompts
  responses
  edited files
  patches
  test results
  timing and token usage
  trajectory summaries

evaluation/
  official task metrics
  process metrics
  failure labels
  reporting scripts
```

The release is a benchmark only if tasks, scenarios, framework, evaluator, and
representative results are all reproducible.

## 7. Task sources

### 7.1 Commit0

Commit0 is the development and lightweight evaluation source.

It is used for:

- rapid task curation;
- cheap executable feedback;
- prompt and tool development;
- early multi-agent scenario validation;
- failure-taxonomy development.

Commit0 must not be the only reported task source.

### 7.2 Qualified SWE-bench

Qualified SWE-bench is the primary external task source.

AsynCodeBench must:

- preserve official repository snapshots;
- preserve official problem statements;
- preserve official test/evaluation semantics;
- publish selected task IDs and versions;
- publish filtering and exclusion reasons;
- avoid exposing hidden solution patches to agents.

### 7.3 Optional later sources

PaperBench Code-Dev, Multi-SWE-bench, SWE-bench Pro, other languages, and
multimodal tasks are future extensions. They are not first-release
requirements.

## 8. Dataset unit

AsynCodeBench distinguishes three records.

### 8.1 Task record

The task record preserves the upstream coding problem:

```text
task_id
task_source
upstream_version
repository
problem_statement
evaluator
test_targets
qualification_label
inclusion_decision
annotation_provenance
```

### 8.2 Scenario record

A scenario defines how the same task is executed:

```text
scenario_id
task_id
agent_count
agent_roles
subproblem_assignments
dependency_annotations
information_profile
execution_mode
communication_condition
message_delivery_policy
review_condition
integration_policy
model_configuration
tool_configuration
step_budget
token_budget
test_budget
wall_clock_budget
```

Task and scenario must remain separate. Different scenarios may reuse the same
upstream task without changing its success criteria.

### 8.3 Run record

A run records one execution:

```text
run_id
scenario_id
model
hardware
generation_parameters
prompts
responses
agent_steps
tool_actions
environment_observations
messages
edited_files
patches
test_commands
test_results
integration_results
event_timestamps
concurrency_intervals
timing
token_usage
final_score
failure_labels
```

## 9. Task qualification

Tasks receive one label:

- `parallelizable`;
- `partially_parallelizable`;
- `effectively_serial`.

Qualification uses public evidence:

- implicated modules;
- static dependency structure;
- task-described subproblems;
- test-target structure;
- test/build duration;
- implementation/testing/review overlap;
- cross-module contracts;
- expected integration surface.

At least two independent human annotators should label the final pilot tasks.
Disagreements must be recorded and adjudicated.

Gold patches and reference diffs must not define the primary label.

### 9.1 Natural decomposition requirement

AsynCodeBench must not create coordination difficulty by arbitrary file
splitting. A scenario decomposition is valid only when annotators can explain:

- why each subproblem is meaningful;
- what one subproblem assumes about another;
- what integration step is required;
- what delayed information may invalidate ongoing work.

### 9.2 Exploratory agent dry-runs

Agent dry-runs may support curation by revealing task structure, but must be
marked non-release until the task and scenario are frozen.

Dry-runs cannot replace independent human annotation.

## 10. Canonical vertical slice: `commit0:cachetools`

The first reference example is `commit0:cachetools`.

Natural subproblems:

```text
key construction:
  src/cachetools/keys.py
  tests/test_keys.py

decorator construction:
  src/cachetools/func.py
  tests/test_func.py

integration:
  typed/untyped key semantics
  existing cache classes and cached() API
  cache_parameters/cache_info/cache_clear
  maxsize, locking, warning, and cache-specific behavior
```

Reference conditions:

```text
iterative_single:
  one agent repeatedly inspects, edits, tests, repairs, and integrates both
  modules

serial_specialists:
  the key agent completes first;
  the decorator agent starts with the completed key artifact visible

async_private:
  the key and decorator agents run concurrently from private workspaces;
  in-flight edits and test results remain hidden until transfer/integration

async_message:
  the same concurrent workers may exchange structured status, assumptions,
  test results, or patch artifacts while work is in flight
```

The initial 4B/32B dry-run demonstrated the intended end-to-end workflow:

```text
public task materialization
-> agent prompt and tool context
-> complete file edits
-> generated patch
-> integrated workspace
-> pytest
-> saved trajectory and failure analysis
```

The initial implementation was single-shot and sequentially invoked the worker
models. It validated task materialization, file editing, patch generation,
integration, and evaluation, but it did not yet implement a strong coding-agent
loop or true concurrent execution. Its numerical results are exploratory and
must not be used as official RQ evidence.

The upgraded cachetools slice should report iterative single-agent, serial,
and genuinely concurrent specialist results under the same tool loop. These
are evaluation conditions, not dataset-admission gates.

## 11. Agent conditions

The minimum first-paper matrix includes four conditions.

### 11.1 Strong iterative single agent

One agent receives the complete public task and repeatedly uses the repository,
shell/file, and test tools until it submits or exhausts a frozen budget.

The loop must support multiple model calls and multiple edit-test-repair
rounds. This is the primary control for base-model task competence.

### 11.2 Serial specialists

Two or more role-specialized agents use the same iterative scaffold, but execute
serially. Each downstream specialist receives the completed upstream artifact
and relevant test output before starting.

This condition controls for decomposition while removing hidden in-flight
state. It is the primary comparator for the effect of asynchrony.

### 11.3 Asynchronous private-workspace team

Specialists use the same iterative scaffold and start concurrently in private
workspaces.

The framework must allow their model calls, edits, and test jobs to overlap in
wall-clock time. Teammate in-flight edits and outputs remain hidden unless the
scenario explicitly transfers them.

This is the primary asynchronous stress condition.

### 11.4 Asynchronous message/artifact team

The same concurrent specialists may send structured messages and transfer
artifacts while work is in flight.

Messages should communicate one or more of:

- current assumption or planned API;
- status and expected completion;
- targeted test result;
- changed file or symbol;
- patch or artifact readiness;
- request to wait, verify, or rebase.

Delivery and read times must be recorded.

### 11.5 Optional conditions

Post-hoc reviewer integration, manager-agent organization, periodic
synchronization, and additional communication policies may be added if the
minimum matrix is stable.

## 12. Information visibility

The minimum benchmark defines two profiles.

### 12.1 `private-workspace`

Each worker sees:

- the public task;
- its assigned subproblem;
- its local files and history;
- explicitly delivered messages or artifacts.

It does not see another worker's in-flight edits.

### 12.2 `shared-status`

Adds:

- teammate task status;
- whether a patch or test has completed;
- integrated workspace version;

but not hidden file content until it is explicitly transferred.

The first release may use `private-workspace` as the primary condition and a
small `shared-status` comparison if resources permit.

## 13. Tools

All evaluated agents must use a documented tool surface.

Minimum tools:

- inspect directory;
- read/search file;
- execute shell command;
- write or replace file;
- run targeted tests;
- run integration tests;
- send structured message;
- transfer artifact;
- review worker outputs;
- integrate or submit.

The framework should generate diffs from file edits rather than requiring
models to produce syntactically perfect unified diffs.

Prompts, tool inputs, tool outputs, and failures must be saved.

### 13.1 Iterative agent loop

All primary conditions use a shared coding-agent control loop:

```text
model query
-> one or more tool actions
-> environment observations
-> append observations to agent history
-> next model query
```

The loop continues until:

- the agent submits;
- the step/token/cost budget is exhausted;
- the wall-clock limit is reached;
- an unrecoverable tool/environment failure occurs.

The framework must record step count, model calls, actions, observations,
tests, edits, and submission state.

The initial implementation should follow a simple mini-SWE-agent-style linear
history rather than a specialized one-shot patch prompt.

## 14. Execution framework

The first-release framework is live-first and intentionally thin.

It must support:

1. materializing the upstream task state;
2. creating one workspace per agent or condition;
3. running a multi-step coding-agent loop;
4. invoking an OpenAI-compatible model endpoint;
5. exposing only scenario-permitted context;
6. executing shell, file, and test actions;
7. returning observations for subsequent model steps;
8. running multiple agent loops concurrently;
9. running asynchronous test/message/artifact jobs;
10. exchanging messages/artifacts where permitted;
11. integrating outputs;
12. running the official evaluator;
13. saving the complete run record.

The first release does not require a general operating-system simulator or a
fully deterministic replay engine.

Simple event timestamps should still be recorded for:

- model request start/finish;
- action start/finish;
- file edit creation;
- message send/delivery;
- test start/finish;
- integration start/finish.

This preserves an upgrade path to richer asynchronous replay.

### 14.1 True asynchrony requirement

An execution is not labeled asynchronous merely because agents have separate
roles or hidden prompts.

The asynchronous conditions must demonstrate at least one real overlap:

- concurrent model requests;
- one agent editing while another test is running;
- one agent continuing while another patch or message is in flight;
- a message or artifact delivered after the receiver has already taken
  additional actions.

The framework must record enough timestamps to verify the overlap.

### 14.2 Single-agent and serial baselines

For every evaluated task, report:

1. the iterative single-agent result under the official evaluator;
2. the serial-specialist result under the same decomposition;
3. the asynchronous private-workspace and asynchronous-message results;
4. whether failures are dominated by local coding errors, tool-format errors,
   environment errors, or integration/coordination errors.

The single-agent condition is the model/task ability baseline. The
serial-specialist condition is the decomposition baseline. They should be
reported as results, not used as preconditions for admitting a task to the
benchmark.

If a task is unsolved in all conditions, it may still be reported, but the
paper must not attribute the failure primarily to asynchrony without additional
evidence.

### 14.3 Budget controls

Report both:

- equal per-agent budget, representing additional team compute;
- approximately equal total team budget, controlling aggregate model usage.

At minimum, every comparison must publish step, token, model-call, test-call,
and wall-clock limits.

## 15. Model suite

The minimum evaluation uses two open-weight model capacities.

The initial development models are:

- `Qwen/Qwen3-4B-Thinking-2507`;
- `Qwen/Qwen3-32B` in thinking mode.

Model choice may change before release, but the final paper must publish:

- exact model identifier and revision;
- inference framework and version;
- hardware;
- context length;
- generation parameters;
- prompt and tool configuration;
- token and latency accounting.

The same model and coding-agent scaffold must be used across compared
conditions. Budget allocation may differ only under the explicitly named
per-agent versus total-team budget protocols.

## 16. Evaluation

### 16.1 Primary outcome

Use the upstream evaluator:

- Commit0 test pass counts or rates;
- SWE-bench official resolved status and tests.

### 16.2 Cost metrics

Report:

- wall-clock duration;
- model calls;
- input/output/reasoning tokens where available;
- test invocations and duration;
- message count and bytes/tokens;
- integration attempts.

### 16.3 Process metrics

The first release should implement a small interpretable set:

- patch/file generation success;
- textual patch conflict;
- semantic integration failure;
- tests passed before and after integration;
- duplicated file or function work;
- stale-assumption incident count;
- missing communication incident count;
- reviewer repair success;
- wasted model or test work after invalidation;
- asynchronous overlap duration;
- actions taken after a relevant but undelivered teammate update;
- serial-to-async performance delta under fixed decomposition.

These may initially include human-coded trajectory labels. Automated detection
is an optional improvement.

## 17. Failure analysis

Each failed run should receive one or more labels:

```text
local_execution
decomposition
stale_assumption
communication
delayed_feedback
semantic_integration
textual_conflict
review_failure
tool_environment
unknown
```

Labels must be assigned from observable trajectory evidence.

The paper must avoid attributing a coordination failure when:

- the single agent also fails for the same local reason;
- the model cannot implement the assigned subproblem;
- the tool protocol is broken;
- the task decomposition is artificial;
- the environment/evaluator is invalid.

## 18. Minimum evaluation matrix

The first-release target is:

```text
10–20 qualified tasks
x
2 model capacities
x
4 agent conditions
x
multiple independent seeds/generations
```

Where feasible, include:

- at least 3 Commit0 development tasks;
- at least 5 qualified SWE-bench tasks;
- examples from all three parallelizability classes.

The initial paper may report fewer tasks as a pilot only if it clearly labels
the release as a pilot benchmark.

Each run must be repeated with multiple seeds or independent generations when
stochastic decoding is used.

The key contrast is:

```text
serial specialists
vs
asynchronous private-workspace specialists
```

because task decomposition and worker scaffold are held constant.

## 19. Required controls

The first paper must control or report:

- same upstream task and evaluator;
- same model;
- same tool surface;
- same iterative agent scaffold;
- comparable model/token budget;
- fixed scenario decomposition;
- fixed prompts per condition;
- model generation parameters;
- task qualification label;
- whether communication is allowed;
- whether a reviewer sees worker outputs;
- whether worker execution is serial or concurrent;
- actual overlap and message delivery timestamps.

Single versus team comparisons alone do not prove a coordination gap. They
show condition-level performance differences that must be interpreted with
failure analysis.

## 20. Anti-leakage

The benchmark must prevent:

- reference/gold patch exposure;
- solution-bearing Git history;
- cross-agent private-workspace access;
- cached model outputs from prior runs;
- unrestricted retrieval of known solutions;
- evaluator artifacts visible before evaluation.

Commit0 agents should receive materialized `commit0` state only.
SWE-bench agents must not receive hidden `patch` or `test_patch` fields.

All task materialization and model prompts should be auditable.

## 21. MVP success criteria

Proceed with the first paper if:

1. task annotation identifies a stable set of naturally decomposable and
   serial/control tasks;
2. the iterative single-agent baseline is implemented and reported;
3. the same scaffold runs under serial and truly concurrent specialist
   conditions;
4. official task outcomes and trajectories are reproducible;
5. serial-to-async differences are observable under fixed decomposition;
6. failure labels reveal recurring software-specific asynchronous problems;
7. findings are not explained only by tool-format errors or universally weak
   model competence;
8. at least some conclusions reproduce across both model capacities and both
   task sources.

The strongest expected first-paper result is:

```text
strong iterative single/serial performance
+
systematic degradation under async-private execution
+
partial recovery from explicit messages or artifact transfer
```

This pattern is desirable evidence, but it must emerge from frozen conditions
and cannot be enforced by weakening the asynchronous agents.

Redesign if:

- most tasks are effectively serial;
- role assignments manufacture the observed difficulty;
- the framework is less reliable than the agents;
- all failures are local coding failures;
- the single-agent and serial baselines are not reported;
- the so-called async condition has no verified execution overlap;
- async workers use a weaker scaffold than the single agent;
- model conditions are incomparable;
- SWE-bench integration cannot preserve official evaluation semantics.

## 22. Deferred v0.2 extensions

The following remain valuable but are deferred:

- deterministic paired replay;
- logical snapshots and counterfactual interventions;
- state and clairvoyant oracles;
- runtime-protection by coordination-policy factorization;
- invalidation precision/recall;
- formal coordination regret;
- replay-to-live transfer;
- full shared-status and manager-mediated profile matrix;
- PaperBench external validation;
- learned coordination policies.

These extensions may be added after the benchmark dataset and live execution
framework are stable.

## 23. Implementation phases

### Phase A — task and scenario curation

- complete Commit0 annotation;
- select representative Commit0 tasks;
- qualify a small SWE-bench subset;
- create task and scenario schemas;
- freeze pilot task/scenario records.

### Phase B — framework generalization

- generalize the cachetools vertical slice;
- replace hard-coded task logic with task/scenario records;
- implement a shared iterative coding-agent loop;
- implement standardized shell, file, test, message, review, and integration
  interfaces;
- implement serial and concurrent specialist scheduling;
- save complete run records.

### Phase C — single-agent and serial baseline pilot

- run iterative 4B and 32B single agents;
- tune only generic scaffold/tool behavior, not task-specific answers;
- verify multi-round inspect/edit/test/repair trajectories;
- freeze prompts, budgets, and reporting thresholds.

### Phase D — asynchronous pilot evaluation

- run two model capacities;
- run serial specialists, async-private, and async-message conditions;
- verify real wall-clock overlap;
- verify upstream evaluators;
- develop and apply failure taxonomy;
- refine prompts and tools only through documented version changes.

### Phase E — benchmark release

- expand to 10–20 qualified tasks;
- freeze dataset and scenario versions;
- publish framework, configs, prompts, and evaluators;
- publish representative trajectories and aggregate results;
- document limitations and anti-leakage audit.

### Phase F — later research

- implement replay, richer event scheduling, oracles, runtime protection, and
  learned coordination methods.

## 24. Immediate next steps

1. implement a mini-SWE-agent-style iterative single-agent loop;
2. run the 32B and 4B single-agent baseline pilot on `commit0:cachetools`;
3. freeze generic tool, step, token, and test budgets;
4. implement serial specialists as the fixed-decomposition control;
5. implement truly concurrent private-workspace workers;
6. implement structured message/artifact delivery;
7. complete independent human annotation of the six Commit0 candidates;
8. define v0.3 task, scenario, and run schemas;
9. generalize the cachetools runner into a task-driven runner;
10. complete a small qualified SWE-bench subset;
11. run the repeated two-model by four-condition pilot.

FreshGRPO remains deferred until AsynCodeBench establishes a useful and
reproducible benchmark.
