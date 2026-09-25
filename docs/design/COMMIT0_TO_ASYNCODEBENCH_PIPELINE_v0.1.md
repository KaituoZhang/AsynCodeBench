# Commit0-to-AsynCodeBench Transformation Pipeline v0.1

Status: design draft  
Related specification: `SPECIFICATION_v0.3.md`  
Related protocol: `docs/protocols/COMMIT0_DATA_AND_METRIC_LABEL_GUIDE_v0.3.md`

## Thesis

AsynCodeBench should be presented as a benchmark transformation framework, not
only as a fixed list of hand-written tasks. Given a public coding task with
public tests, the pipeline converts it into a dependency-aware asynchronous
multi-agent benchmark instance.

The transformation does not modify the task answer or inspect gold patches. It
reconstructs the evaluation scenario around public, test-observable dependency
points, then generates standardized artifacts and validation gates for human
review.

## Methodology Story

The paper story is:

```text
public coding dataset
  -> dependency-aware task repartitioning
  -> async scenario recomposition
  -> standardized artifacts and validation gates
  -> independent human annotation and adjudication
  -> AsynCodeBench task
```

For v0.3, Commit0 is the first substrate. The same method should generalize to
other public coding datasets if they provide a public initial state, public
tests, provenance, and an evaluator sanity target.

## Pipeline Stages

### 1. Task Intake

Input:

- repository identifier and local path;
- public initial ref, normally `origin/commit0_combined` or `commit0`;
- complete/sanity ref used only to validate evaluator feasibility;
- candidate screening record;
- existing AsynCodeBench manifests and metrics.

Required checks:

- skip tasks that already have task and async metrics manifests;
- confirm public source and tests are present;
- confirm the task is not primarily packaging, dependency installation, or
  environment repair;
- record rejected, weak, or deferred cases to reduce selection-bias concerns.

Output:

- accepted candidate for transformation, or a documented skip/defer decision.

### 2. Evaluator Construction

The evaluator must be public-test based and answer-free.

Procedure:

1. Run candidate public tests against the stripped initial ref.
2. If collection/import fails, identify the smallest non-solution bootstrap
   overlay that exposes missing symbols or setup hooks.
3. Apply overlays in deterministic order, each with checksum and rationale.
4. Run the initial evaluator and record pass/fail/error/skipped counts.
5. Run the same evaluator on the complete/sanity ref and record feasibility.

Rules for bootstrap overlays:

- allowed: import stubs, setup hooks, mechanical syntax fixes, minimal class
  construction prerequisites;
- forbidden: implementing benchmark behavior, satisfying semantic tests, filling
  core algorithms, or pre-solving upstream dependency contracts;
- every overlay needs a rationale explaining why it is non-solution.

Output:

- evaluator command;
- selected test targets;
- bootstrap overlays and checksums;
- initial snapshot;
- complete sanity snapshot;
- known limitations.

### 3. Dependency Discovery

This is the central transformation step.

Procedure:

1. Identify natural subproblems from public modules and tests.
2. Identify producer and consumer relationships between subproblems.
3. Prefer dependencies whose failures are semantic integration failures, not
   only textual merge conflicts.
4. Attach public probe tests to each dependency point.

Dependency points must be public-test-observable. A valid dependency point has:

- producer subproblem and files;
- consumer subproblem and files;
- contract summary;
- stale failure mode;
- upstream probe tests;
- downstream probe tests;
- integrated probe tests;
- resolution criteria;
- enabled async metrics.

Output:

- `natural_subproblems`;
- `dependency_annotations`;
- async metrics `dependency_points`.

### 4. Scenario Recomposition

The original coding task is re-expressed as comparable execution scenarios:

- iterative single agent;
- serial specialists;
- async private workspaces;
- async message/artifact sharing.

The repartitioning target is agent ownership and scenario structure, not the
source code answer.

For each scenario, define:

- agent count;
- writable paths;
- primary test targets;
- information profile;
- communication policy;
- integration policy;
- dependency annotations.

Output:

- scenario manifest;
- agent assignments;
- specialist local and cross-subproblem test groups.

### 5. Artifact Generation

Every transformed task should emit:

```text
src/asyncodebench/dataset/<repo>_v03.py
scripts/build_<repo>_v03_data.py
manifests/pilot/v0.3/tasks/commit0_<repo>.json
manifests/pilot/v0.3/scenarios/commit0_<repo>.json
manifests/pilot/v0.3/quality/commit0_<repo>.json
manifests/pilot/v0.3/metrics/commit0_<repo>_async_metrics.json
manifests/annotations/asyncodebench_v0.3/<repo>/annotator_a.json
manifests/annotations/asyncodebench_v0.3/<repo>/annotator_b.json
manifests/annotations/asyncodebench_v0.3/<repo>/adjudication.template.json
tests/contracts/test_<repo>_dataset_v03.py
tests/contracts/test_<repo>_async_metrics_v03.py
configs/tasks/commit0_curated_tasks.v0.3.json entry
```

The generated task is `qualification_ready` at most. It is not `release_ready`
until annotation and release gates are complete.

### 6. Automatic Validation Gates

Required gates:

- JSON parse for all generated manifests and annotation forms;
- curated config contains the correct base ref and overlay checksums;
- overlays apply cleanly to the public initial ref;
- bootstrap-modified files parse or compile where appropriate;
- task/scenario/quality records are internally consistent;
- async metrics file exists for every transformed task;
- every probe selector resolves to a public test in the public initial ref;
- the primary dependency has upstream, downstream, and integrated probes;
- initial evaluator records meaningful unfinished behavior;
- complete sanity evaluator passes, or the limitation is explicitly documented.

Automatic gates prove structural validity. They do not prove task inclusion.

### 7. Human Review and Annotation

Independent annotators decide:

- include or exclude;
- parallelizability label;
- whether subproblems are natural;
- whether dependencies are real and public-test-observable;
- whether bootstrap overlays are non-solution;
- whether async difficulty is artificial.

Adjudication resolves disagreements. The annotation forms remain part of the
dataset provenance and should be reported in the paper methodology.

## Reusable Construction Workflow

The transformation protocol is maintained as public construction documentation,
deterministic scripts, schemas, and contract tests. This avoids coupling the
benchmark release to an agent-specific local skill package. The driver scripts
expose phase-specific commands such as:

```text
discover-next-task
materialize-task
run-evaluator-snapshots
generate-artifacts
validate-task-artifacts
summarize-task-status
```

## Paper Framing

The methodology contribution should be framed as:

> We operationalize AsynCodeBench construction as a protocol-guided
> transformation from public coding tasks to dependency-aware asynchronous
> benchmark instances. The pipeline generates standardized artifacts and
> validation gates, while human annotators retain authority over task inclusion
> and dependency validity.

Avoid claiming full automation. The stronger and more defensible claim is
agent-assisted, protocolized artifact generation with deterministic checks and
human adjudication.

## Main Risks and Controls

Risk: LLM-generated benchmark circularity.  
Control: the agent generates candidate artifacts only, uses public evidence
only, cannot inspect gold patches, and human annotation gates release.

Risk: artificial async difficulty.  
Control: dependencies must be natural, public-test-observable, and reviewed by
annotators.

Risk: bootstrap overlays leak solution behavior.  
Control: overlays are checksum-recorded, reviewed, and restricted to
collection/import prerequisites.

Risk: selection bias.  
Control: record skipped, weak, deferred, and rejected candidates, not only
successful transformations.

Risk: over-engineering without novelty.  
Control: present the formal transformation protocol and dependency-level
metrics as the contribution, with Commit0 tasks as an instantiation.
