# AsynCodeBench v0.3 Ownership and Qualification Audit

Date: 2026-08-09
Release set: 16 official tasks
Reviewer: `codex_ai_assisted_audit_20260809`

## Status and limitation

This is an AI-assisted audit of public benchmark artifacts. It is useful for
finding structural and semantic inconsistencies, but it is not one of the two
independent human annotations required by the v0.3 qualification protocol.
The existing `annotator_a.json`, `annotator_b.json`, and adjudication templates
remain the release authority.

The review used only current task, scenario, quality, metric, overlay, curated
source, and public-test evidence. It did not inspect reference implementations,
solution patches, hidden tests, or model-generated solutions.

## Audit questions

For each task, the review checked whether:

1. the task has at least two natural implementation surfaces;
2. the surfaces are connected by a public-test-observable dependency;
3. each assignment has existing writable paths and public test targets;
4. ownership is consistent across serial, async-private, and async-message;
5. writable scopes are exclusive, or shared ownership is explicitly justified;
6. metric producer and consumer files agree with scenario ownership;
7. the scoped evaluator fails on the initial source and passes on evaluator-only
   completed-source sanity evidence;
8. bootstrap overlays are disclosed and do not silently provide the main task
   solution.

## Automated validation

- Official task count: 16.
- All 16 tasks provide the four required execution scenarios.
- Multi-agent assignment signatures are consistent across all three protocols.
- Every declared writable path exists in the curated public initial source.
- Every assignment test-target file exists.
- Dataset contract suite: 121 passed.
- Native harness contract suite: 31 passed.
- Fifteen tasks have exclusive writable paths.
- Marshmallow has one shared path: `src/marshmallow/schema.py`.

## Per-task decisions

| Task | Include | Label | Ownership | Metric alignment | Release note |
|---|---:|---|---|---|---|
| cachetools | yes | partially parallelizable | pass | conditional | Only the two keys-to-func points are true cross-worker dependencies; secondary integrator points should not enter cross-worker CAIL or SAD. |
| deprecated | yes | partially parallelizable | pass | pass | ClassicAdapter to SphinxAdapter is a natural public API dependency. |
| portalocker | yes | partially parallelizable | pass | pass | Backend and utility ownership is explicit; utility edits to `portalocker.py` are genuine scope violations under this protocol. |
| tinydb | yes | partially parallelizable | pass | pass | Query contracts feed a larger but natural database-state stack. |
| wcwidth | yes | partially parallelizable | pass | pass | Valid small interface-dependency task; test isolation and workload are asymmetric. |
| requests | yes | partially parallelizable | pass | pass | Natural preparation-to-transport dependency; disclose the small amount of behavior supplied by bootstrap overlays. |
| simpy | yes | partially parallelizable | pass | pass | Scheduler, event, resource, and realtime boundaries follow existing modules. |
| parsel | yes, conditional | partially parallelizable | pass | pass | The task split is strong, but the one-line `setup()` registration conflicts with an older strict bootstrap review and needs human policy adjudication. |
| filesystem_spec | yes | partially parallelizable | pass | pass | Valid scoped core task; excluded backend and AbstractFileSystem surfaces are documented. |
| marshmallow | yes, conditional | partially parallelizable | revise or formalize shared scope | pass | Registry and schema agents both own `schema.py`; strict exclusive Worker-SVR is not justified until shared ownership is explicitly modeled or repartitioned. |
| graphene | yes, conditional | partially parallelizable | pass | pass | Natural type-mounting-to-schema chain; the `props` overlay is non-trivial and needs human acceptance. |
| imapclient | yes, conditional | partially parallelizable | pass | pass | Strong lexer-parser-client chain; workload is asymmetric and the capability decorator/helper overlays need human acceptance. |
| pexpect | yes | partially parallelizable | pass | revise | `spawn_to_wrappers` attributes transport files to the spawn producer; split or correct the composite dependency. |
| flask | yes, conditional | partially parallelizable | pass | pass | Natural registry/context/session consumer chain; numerous identity/helper overlays require explicit human acceptance. |
| python-rsa | yes | partially parallelizable | pass | revise | The PKCS#1 metric lists `rsa/key.py` under the arithmetic producer; model it as a second producer or split the dependency. |
| cookiecutter | yes | partially parallelizable | pass | pass | Natural workflow dependencies and no bootstrap overlay; retain evaluator exclusion and screening caveats. |

## Aggregate decision

The AI-assisted task-suitability decision is `include=true` and
`partially_parallelizable` for all 16 tasks. This means every task has a
defensible asynchronous software-dependency structure after its documented
release gates are satisfied. It does not mean all 16 artifacts are already
release-final.

The stricter readiness results are:

- 15/16 ownership maps are suitable for direct exclusive-scope enforcement;
- 1/16, Marshmallow, requires a shared-ownership decision or repartition;
- 12/16 are clean across ownership and dependency-metric attribution;
- Cachetools, Pexpect, and python-rsa need metric interpretation or mapping
  corrections, while Marshmallow needs an ownership-policy correction;
- Parsel, Graphene, IMAPClient, Flask, Marshmallow, and Requests have bootstrap
  details that should be explicitly accepted or rejected by human reviewers;
- no task becomes formally human-validated from this AI audit.

## Required human annotation

Two independent humans should complete the existing `annotator_a.json` and
`annotator_b.json` forms without seeing each other's decisions. In addition to
the current include and parallelizability fields, reviewers should record:

- whether every worker can complete its role without editing another worker's
  exclusive scope;
- whether every shared path is necessary and explicitly justified;
- whether each metric's producer and consumer files belong to the declared
  producer and consumer assignments;
- whether bootstrap overlays are limited enough to remain answer-free;
- whether evaluator exclusions preserve the claimed dependency structure.

If the reviewers disagree, an independent adjudicator must complete the task's
adjudication file. Only then should a task move from `qualification_ready` to
`release_ready` or be described as human validated in a paper.

## Impact on existing experiment runs

Metric-only corrections do not change model behavior, prompts, or patches, but
strict dependency summaries may need regeneration from retained checkpoint and
probe evidence. Declaring Marshmallow's existing `schema.py` path as explicitly
shared preserves the executed protocol; changing its owner or repartitioning
the task changes the protocol and requires rerunning Marshmallow. Changing any
bootstrap overlay changes the initial task source and also requires rerunning
that task.
