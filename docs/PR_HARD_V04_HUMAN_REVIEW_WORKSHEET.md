# Human Review Worksheet for the Four Added Tasks

## What the reviewer fills

The original 16 tasks already have the required human approval. The four forms
below are the only pending human decisions for the unified 20-task analysis:

- `manifests/annotations/pr_hard_v0.4/apache_tvm_20018/annotator_a.json`
- `manifests/annotations/pr_hard_v0.4/apache_tvm_20073/annotator_a.json`
- `manifests/annotations/pr_hard_v0.4/apache_tvm_20107/annotator_a.json`
- `manifests/annotations/pr_hard_v0.4/apache_tvm_20153/annotator_a.json`

In each file, edit only these five fields:

```json
{
  "annotator_id": "your-stable-public-or-pseudonymous-id",
  "include": true,
  "parallelizability_label": "partially_parallelizable",
  "rationale": "Your independent, concrete review rationale.",
  "exclusion_reason": null
}
```

Allowed labels are `parallelizable`, `partially_parallelizable`, and
`effectively_serial`. If `include` is `false`, provide a non-empty
`exclusion_reason`. Do not copy the suggested evidence summaries below as the
rationale: the rationale must record your own judgment after reviewing the
listed public artifacts.

## Common acceptance checklist

For every task, independently confirm all of the following:

- [ ] The public statement describes real repository-level implementation.
- [ ] The source state and public overlays are answer-free.
- [ ] The incomplete state is meaningfully red and the completed sanity state
      is green for the scoped evaluator.
- [ ] The responsibilities are natural software roles, not arbitrary file
      partitions.
- [ ] Writable ownership covers the intended implementation surfaces without
      manufacturing overlap.
- [ ] At least one producer-consumer dependency genuinely crosses owners.
- [ ] Upstream, downstream, and integrated Dependency Checker groups execute
      and observe the claimed contract.
- [ ] Private asynchronous work can plausibly create stale assumptions,
      delayed adaptation, or integration failure.
- [ ] The task is not mainly environment repair or package installation.
- [ ] You did not inspect a gold production patch, reference solution, hidden
      tests, or model-generated implementation while deciding inclusion.

## Task 20018: first-class Return across the compiler pipeline

Review these files:

- Task: `manifests/candidates/pr_hard_v0.4/tasks/apache_tvm_20018.json`
- Scenarios and ownership:
  `manifests/candidates/pr_hard_v0.4/scenarios/apache_tvm_20018.json`
- Dependencies and checker selectors:
  `manifests/candidates/pr_hard_v0.4/metrics/apache_tvm_20018_async_metrics.json`
- Automated evidence:
  `manifests/candidates/pr_hard_v0.4/qualification/apache_tvm_20018.json`
- Public test-only overlay:
  `data/overlays/pr_hard/apache_tvm_20018/0001-public-regression-tests.patch`

Human questions:

- Are Return IR schema/visitors, TVMScript construction/rendering, and
  lowering/target emission three coherent responsibilities?
- Is the ordered chain `IR core -> Script surface -> lowering/codegen` genuine,
  rather than a split chosen merely because the upstream change touches many
  files?
- Do the 0/8, 3/8, 5/8, and 8/8 ablations establish both dependency points?
- Do the legality and CPU/LLVM emission tests adequately cover the scoped task,
  given that the comment-only CUDA hunk and fully skipped GPU module are
  excluded?

## Task 20073: source-span propagation join

Review these files:

- Task: `manifests/candidates/pr_hard_v0.4/tasks/apache_tvm_20073.json`
- Scenarios and ownership:
  `manifests/candidates/pr_hard_v0.4/scenarios/apache_tvm_20073.json`
- Dependencies and checker selectors:
  `manifests/candidates/pr_hard_v0.4/metrics/apache_tvm_20073_async_metrics.json`
- Automated evidence:
  `manifests/candidates/pr_hard_v0.4/qualification/apache_tvm_20073.json`
- Public test-only overlay:
  `data/overlays/pr_hard/apache_tvm_20073/0001-public-regression-tests.patch`

Human questions:

- Are scoped IRBuilder state and AST-coordinate mapping independent, natural
  producers for parser/evaluator propagation?
- Does the two-producer join represent a real semantic contract rather than
  three independent span utilities?
- Does the ablation matrix (each producer 1/6, both without consumer 2/6,
  complete 6/6) demonstrate genuine downstream dependence?
- Are 28 selected regression tests sufficient for the claimed scoped behavior?

## Task 20107: shared type-parameter core with two dialect consumers

Review these files:

- Task: `manifests/candidates/pr_hard_v0.4/tasks/apache_tvm_20107.json`
- Scenarios and ownership:
  `manifests/candidates/pr_hard_v0.4/scenarios/apache_tvm_20107.json`
- Dependencies and checker selectors:
  `manifests/candidates/pr_hard_v0.4/metrics/apache_tvm_20107_async_metrics.json`
- Automated evidence:
  `manifests/candidates/pr_hard_v0.4/qualification/apache_tvm_20107.json`
- Public test-only overlay:
  `data/overlays/pr_hard/apache_tvm_20107/0001-public-regression-tests.patch`

Human questions:

- Is the shared Script AST/document model a natural producer for the Relax and
  TIRx dependent-signature consumers?
- Are the two consumers sufficiently independent to justify a three-role
  fan-out rather than one combined downstream role?
- Do the core-only, core-plus-Relax, and core-plus-TIRx ablations establish both
  directed contracts?
- Do the 501 passing selected regression tests adequately protect parser,
  printer, ordering, and round-trip behavior?

## Task 20153: PTX address schema, lowering, and rendering chain

Review these files:

- Task: `manifests/candidates/pr_hard_v0.4/tasks/apache_tvm_20153.json`
- Scenarios and ownership:
  `manifests/candidates/pr_hard_v0.4/scenarios/apache_tvm_20153.json`
- Dependencies and checker selectors:
  `manifests/candidates/pr_hard_v0.4/metrics/apache_tvm_20153_async_metrics.json`
- Automated evidence:
  `manifests/candidates/pr_hard_v0.4/qualification/apache_tvm_20153.json`
- Public test-only overlays:
  `data/overlays/pr_hard/apache_tvm_20153/0001-public-regression-tests.patch`
  and `0002-public-regression-updates.patch`

Human questions:

- Are dialect schema, operand lowering, and PTX rendering natural owners with
  stable producer-consumer contracts?
- Does the schema-to-lowering-to-rendering chain expose realistic stale
  metadata, normalized-offset, or helper-name integration failures?
- Is a base result of 1/12 still meaningfully incomplete for the scoped task?
- Is CPU-only structural/code-generation validation sufficient when 45
  optional `ptxas` certification cases skip because the CUDA toolkit is absent?

## Validation commands

Before filling, this command should report four pending reviews while verifying
that all JSON forms conform to the annotation schema:

```bash
.venv-benchmark/bin/python scripts/validate_pr_hard_human_reviews.py --allow-pending
```

After filling all four forms, run:

```bash
.venv-benchmark/bin/python scripts/validate_pr_hard_human_reviews.py
```

The expected final line is:

```text
Human reviews complete: 4/4
```

Do not manually change the qualification records from `pending` to `complete`
until the forms pass this validator. Promotion and release-index updates are a
separate mechanical step after the human decisions are recorded.
