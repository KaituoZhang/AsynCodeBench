# AsynCodeBench v0.3 Annotator Guidance

This document explains how a human annotator should complete the v0.3
annotation templates under:

```text
manifests/annotations/commit0_v0.3/<task_name>/
```

The goal of annotation is not to solve the coding task. The goal is to decide
whether a candidate task is suitable for AsynCodeBench and how naturally it
supports multi-agent decomposition.

## 1. What annotators are judging

AsynCodeBench v0.3 focuses on LLM-based software-engineering agents under
different coordination conditions:

- single-agent iterative coding;
- synchronous or serial specialist collaboration;
- asynchronous multi-agent collaboration where teammate work, messages, or
  artifacts may be stale or unavailable.

An annotator should judge whether the task has enough structure to test this.
In particular, a useful task should have:

1. a real coding objective in an existing repository;
2. executable tests or evaluator commands;
3. at least two meaningful implementation surfaces or subproblems;
4. some dependency between those subproblems, such as API contract dependency,
   shared abstraction, shared state, or integration-test dependency;
5. enough difficulty that agent coordination matters, but not so much missing
   infrastructure that the task mainly tests environment setup.

## 2. Files to read before filling the template

For a task such as `commit0:cachetools`, read these files:

```text
manifests/pilot/v0.3/tasks/commit0_cachetools.json
manifests/pilot/v0.3/quality/commit0_cachetools.json
manifests/pilot/v0.3/scenarios/commit0_cachetools.json
manifests/annotations/commit0_v0.3/cachetools/annotator_a.json
```

If available, also read the worked example document:

```text
docs/protocols/COMMIT0_DATA_EXAMPLE_GUIDE_v0.3.md
docs/protocols/COMMIT0_<TASK>_DATA_EXAMPLE_v0.3.md
```

Do not inspect hidden solution patches, reference branches, or model-generated
answers. Annotation should be based on public repository state, task records,
quality records, and tests.

## 3. Which fields should be edited

In most cases, an annotator should only edit these four fields:

```json
"include": null,
"parallelizability_label": null,
"rationale": null,
"exclusion_reason": null
```

The other fields should usually remain unchanged:

```json
"schema_version"
"task_id"
"annotator_id"
"candidate_evidence_file"
"task_record_file"
"allowed_labels"
"independence_instructions"
```

These fields define the template identity and validation constraints.

## 4. `include`

Use:

```json
"include": true
```

if the task should be included in AsynCodeBench after the remaining engineering
or release gates are satisfied.

Use:

```json
"include": false
```

if the task should be excluded.

Common reasons to include:

- the repository has a real incomplete implementation;
- the evaluator is executable and meaningful;
- the task can be decomposed into natural agent-owned subproblems;
- the subproblems are not fully independent;
- asynchronous execution can plausibly create stale assumptions, interface
  mismatch, or shared-abstraction inconsistency.

Common reasons to exclude:

- no reliable evaluator exists;
- the task is mostly packaging, dependency installation, or environment repair;
- the task is effectively a single isolated function with no meaningful
  multi-agent structure;
- the task requires non-public solution knowledge to define;
- the task is too under-specified to fairly evaluate agents;
- the task depends on unavailable external services unless those services are
  explicitly part of the frozen benchmark environment.

## 5. `parallelizability_label`

Allowed labels are:

```json
"parallelizable"
"partially_parallelizable"
"effectively_serial"
```

### `parallelizable`

Use this when the task naturally splits into separate subproblems that can be
implemented mostly independently.

This is usually less interesting for AsynCodeBench unless there is still a
clear integration risk.

Example pattern:

```text
Agent A implements module X.
Agent B implements module Y.
X and Y share little or no API contract beyond stable public imports.
```

### `partially_parallelizable`

Use this when the task has natural subproblems, but the subproblems depend on
one another through an API contract, shared abstraction, shared state, or
integration tests.

This is the main target label for AsynCodeBench.

Example pattern:

```text
Agent A implements low-level key construction.
Agent B implements decorators that depend on key behavior.
If B assumes the wrong typed-key semantics before A's patch is visible, the
merged solution may fail even though each local patch looked reasonable.
```

### `effectively_serial`

Use this when the task must be solved in a mostly sequential order and splitting
it across agents would be artificial.

Example pattern:

```text
There is one core algorithm, and all other changes are trivial consequences of
that implementation. A second agent would mostly wait for the first agent's
decision.
```

## 6. `rationale`

The rationale should be a short but concrete paragraph. It should explain:

1. why the task should or should not be included;
2. what the natural subproblems are;
3. what dependency exists between the subproblems;
4. why this dependency is relevant to asynchronous multi-agent coding.

A good included-task rationale looks like:

```text
This task is suitable for AsynCodeBench because it has two natural but
dependent implementation surfaces: <subproblem A> and <subproblem B>.
<subproblem B> depends on <subproblem A> through <API/shared abstraction/test
contract>. This creates a realistic asynchronous-collaboration risk: if one
agent proceeds using a stale or incorrect assumption about the other agent's
contract, the final merged patch can fail integration tests even if each local
patch appears plausible.
```

A good excluded-task rationale looks like:

```text
This task should be excluded because the visible implementation work is
concentrated in one module and there is no natural dependent subproblem for a
second coding agent. The task would primarily measure single-agent coding
ability rather than asynchronous multi-agent coordination.
```

## 7. `exclusion_reason`

If:

```json
"include": true
```

then use:

```json
"exclusion_reason": null
```

If:

```json
"include": false
```

then `exclusion_reason` must be a non-empty string.

Example:

```json
"exclusion_reason": "The task has no reliable evaluator and primarily fails due to missing optional services rather than coding behavior."
```

## 8. Valid completed examples

### Include example

```json
{
  "include": true,
  "parallelizability_label": "partially_parallelizable",
  "rationale": "The task is suitable for AsynCodeBench because it has separable but dependent implementation surfaces: cache key construction and decorator/cache behavior. The decorator layer depends on typed-key semantics, cache parameter exposure, and shared public API contracts. This creates a realistic asynchronous-collaboration risk where one agent may proceed with a stale or incompatible assumption about the other agent's API.",
  "exclusion_reason": null
}
```

### Exclude example

```json
{
  "include": false,
  "parallelizability_label": "effectively_serial",
  "rationale": "The task should be excluded because the meaningful implementation work is concentrated in one core function and there is no natural dependent subproblem for a second agent. Splitting the task would be artificial and would not test asynchronous coordination.",
  "exclusion_reason": "No natural multi-agent decomposition with dependency structure."
}
```

## 9. Independence requirement

For release-quality annotation, two annotators must work independently:

```text
annotator_a.json
annotator_b.json
```

The two annotators should not discuss their decisions before both forms are
completed.

If both annotators agree on:

```text
include
parallelizability_label
```

then the task can be finalized without adjudication.

If they disagree on either field, an independent adjudicator must complete:

```text
adjudication.template.json
```

The adjudicator must not be either annotator.

## 10. Validation command

After both annotation files are complete, run:

```bash
cd /absolute/path/to/AsynCodeBench
PYTHONPATH=src python scripts/finalize_v03_task_annotation.py \
  --task manifests/pilot/v0.3/tasks/commit0_cachetools.json \
  --annotation-a manifests/annotations/commit0_v0.3/cachetools/annotator_a.json \
  --annotation-b manifests/annotations/commit0_v0.3/cachetools/annotator_b.json \
  --output manifests/pilot/v0.3/tasks/commit0_cachetools.finalized.json
```

If adjudication is needed:

```bash
cd /absolute/path/to/AsynCodeBench
PYTHONPATH=src python scripts/finalize_v03_task_annotation.py \
  --task manifests/pilot/v0.3/tasks/commit0_cachetools.json \
  --annotation-a manifests/annotations/commit0_v0.3/cachetools/annotator_a.json \
  --annotation-b manifests/annotations/commit0_v0.3/cachetools/annotator_b.json \
  --adjudication manifests/annotations/commit0_v0.3/cachetools/adjudication.template.json \
  --output manifests/pilot/v0.3/tasks/commit0_cachetools.finalized.json
```

Replace `cachetools` with `deprecated`, `tinydb`, or `portalocker` for other
tasks.

## 11. Practical checklist

Before marking `include: true`, confirm:

- [ ] The evaluator command is concrete and executable.
- [ ] The task is not mostly environment repair.
- [ ] There are at least two natural subproblems.
- [ ] The subproblems have an interface, shared-state, shared-abstraction, or
      integration-test dependency.
- [ ] The async setting can plausibly create stale assumptions or semantic
      conflicts.
- [ ] The task still has a strong single-agent baseline path.
- [ ] The rationale explains the dependency, not only that the task is
      difficult.

