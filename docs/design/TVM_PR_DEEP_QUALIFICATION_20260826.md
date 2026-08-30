# Deep qualification of four Apache TVM PR-hard candidates

Status: automated source/build/ablation audit; no candidate in this report is
official-result eligible
Audit date: 2026-08-26
Repository: `apache/tvm`

## Outcome

The four raw candidates do not all survive the AsynCodeBench definition in
their original form. Two have clean, non-arbitrary multi-owner dependency
graphs and should proceed to runtime packaging and human review. Two need a
scope or evidence revision before scenario construction.

| PR | Strict decision | Natural topology | Evidence result | Next gate |
| --- | --- | --- | --- | --- |
| 20107 | proceed | shared Script core fans out to independent Relax and TIRx consumers | base 0/3, gold 3/3; core-only 1/3; core+Relax 2/3; core+TIRx 2/3 | packaged and automatically qualified; human review remains |
| 20073 | proceed | IRBuilder span state and source-coordinate mapping join in parser/evaluator propagation | base 0/6, gold 6/6; either producer alone 1/6; both producers without consumer 2/6 | package a one-commit runtime seed with the older pinned `tvm-ffi`, then human review |
| 20121 | revise to a narrower two-role task | prefill-kernel contract joins the C++ runtime/cache implementation | base 0/3, gold 3/3; either side alone 0/3; kernel+runtime 3/3 | remove the unsupported high-level frontend role or add public evidence that makes it necessary |
| 20168 | needs evidence revision | core Tuple IR -> TIRx traversal -> Script integration | core-only 1/5, core+traversal 4/5, all roles 5/5; two downstream test modules nevertheless fail during base collection | find public selectors that collect on the incomplete base; do not treat producer implementation as a bootstrap overlay |

This is deliberately not a four-out-of-four promotion result. A large PR and a
visually plausible graph are insufficient when a proposed role is not needed
by the evaluator or when the public evidence cannot execute on the incomplete
state.

## Provenance correction

The full upstream object graph was rechecked rather than relying on search
metadata. The merged production commit's first parent is the benchmark base.
This corrected two preliminary screening bases:

| PR | Pinned first parent | Offline gold |
| --- | --- | --- |
| 20121 | `ea0950abfe49031720171a931fc244c0fb2033e2` | `27c2e019d0ce6182158020c7534dda4a3ce981ae` |
| 20107 | `0468e13a1450a4429758003612aa2b3d080c1f13` | `bb9bc20a8294fb19a2a40f029fe57baa546a8206` |
| 20168 | `4e9a099d154d7c4644a40a1a9c00b8873226468e` | `2647a19cc39965e39033904f42e934a76d427d53` |
| 20073 | `62fb780bb0a8da62e3808f60a2343f6fd1d4b01f` | `ae99c3fd92ddb8cd5bb0cbda1dd9584b525b7a24` |

PRs 20107 and 20073 previously recorded a non-parent screening commit. The
screening report and machine-readable screening record now use the verified
first parents.

## Audit method

For each PR, the audit separated upstream tests from production changes,
applied only the test overlay to the first-parent base, built TVM with CPU LLVM,
and ran the same exact selectors on base and offline gold. It then reconstructed
role-partial production states from disjoint path groups. A dependency is
accepted only when upstream-only, downstream-only, and joined states behave as
predicted. Offline production gold was never added to the candidate overlays.

The generated test-only overlays are:

| PR | Overlay SHA-256 |
| --- | --- |
| 20121 | `ff3c61d2160dd2bbee1f4465bdb4fd658fef492e745f6e7d2831edb38546a054` |
| 20107 | `2bf2a42a33f4d71da3eab1b6508c14a1e0185aace965ecc74235db3391ee1684` |
| 20168 | `d1d2c1bda63c06c9005d44a04bffca12e72fde268ab5d0666b907abbc5f5403b` |
| 20073 | `9fdc39a78fdea5254633c73f11e87198b193bcaede742e2ac883bf0e947b1940` |

No overlay contains a PR number, base SHA, gold SHA, or production patch.

## PR 20107: accepted fan-out candidate

The natural ownership graph is:

```text
shared Script signature/doc core
          |             |
          v             v
 Relax type variables   TIRx type variables
```

The shared producer owns the generic Script parser, diagnostics, document
model, and Python document printer. The two consumers own the Relax and TIRx
dialect-specific parser/printer paths. These are normal compiler-framework
responsibilities, and their production paths are disjoint.

The ablation matrix is decisive:

| Production state | Core printer | Relax round-trip | TIRx round-trip |
| --- | ---: | ---: | ---: |
| base | fail | fail | fail |
| shared core only | pass | fail | fail |
| shared core + Relax | pass | pass | fail |
| shared core + TIRx | pass | fail | pass |
| all roles | pass | pass | pass |

Therefore the two directed contracts are independently observable rather than
two labels attached to one broad end-to-end failure:

1. `shared_signature_core -> relax_dependent_signature`
2. `shared_signature_core -> tirx_dependent_signature`

The candidate is genuinely multi-agent and has a useful fan-out graph. It is
not yet execution-eligible because the no-remote one-commit runtime seed,
task-local environment record, full regression run, and mandatory human review
have not been finalized.

## PR 20073: accepted join candidate

The original two-role hypothesis was too coarse. The production patch supports
three coherent owners:

```text
IRBuilder active-span state ----+
                                +--> parser/evaluator span propagation
source-coordinate mapping ------+
```

The IRBuilder owner defines and carries active span state. The source-mapping
owner converts Python coordinates into TVM spans. The parser/evaluator owner
must consume both contracts when emitting direct, inline, and tile-primitive
IR.

| Production state | Builder selector | Source-map selector | Four parser/integration selectors |
| --- | ---: | ---: | ---: |
| base | fail | fail | 0/4 pass |
| builder only | pass | fail | 0/4 pass |
| source map only | fail | pass | 0/4 pass |
| both producers, no consumer | pass | pass | 0/4 pass |
| all roles | pass | pass | 4/4 pass |

This is a stronger dependency shape than a simple file split. The consumer
cannot become correct from either producer alone, and both upstream contracts
remain independently testable. The accepted edges are:

1. `irbuilder_span_state -> parser_span_propagation`
2. `source_coordinate_mapping -> parser_span_propagation`

The audit initially left runtime packaging, broader regression, and human
review open. A subsequent 2026-08-26 packaging pass created a one-commit,
no-remote seed with the older pinned `tvm-ffi`, passed the 28-test selected
regression evaluator, and validated all four protocol dry-runs. Mandatory human
review remains open.

## PR 20121: original three-role claim rejected

The source patch suggests frontend API, generated kernels, and C++ runtime/cache
roles. Execution does not support that three-owner story.

| Production state | Focused CPU selectors |
| --- | ---: |
| base | 0/3 pass |
| kernel paths only | 0/3 pass |
| runtime/cache paths only | 0/3 pass |
| kernel + runtime/cache | 3/3 pass |
| full gold, including high-level `kv_cache.py` | 3/3 pass |

Because kernel+runtime already equals full gold on the evaluator, the proposed
high-level frontend owner is not necessary. Keeping it would manufacture a
third agent whose artifact has no observed effect. The defensible revision is
a narrower two-role candidate:

```text
prefill kernel/mask contract -> C++ runtime and paged-cache state
```

That revision must explicitly narrow the problem statement and editable paths,
or add public tests that require the high-level frontend changes. Until then,
the candidate remains `needs_revision` and has no four-condition scenarios.

## PR 20168: natural graph, inadmissible current evidence

The production organization is natural: core Tuple/Call IR definitions feed
TIRx visitors and equality, which feed parser/printer round-trip behavior. The
partial-state execution confirms the semantic chain once the core role exists:
core-only passes 1/5 selectors, core plus traversal passes 4/5, and all three
roles pass 5/5. However, on the actual incomplete base, the traversal test
modules import `Tuple` and `TupleGetItem` at module scope. Pytest therefore
exits during collection before those role-local selectors execute.

This is not an answer-free mechanical bootstrap issue. Adding the missing Tuple
API merely to make collection succeed would implement the producer role and
leak benchmark behavior into the initial state. Under the current
AsynCodeBench rule that public checker evidence must execute on the incomplete
task, the candidate cannot advance.

Acceptable repairs are limited to finding already-public selectors that collect
on base, or redefining the task around a smaller graph with complete public
evidence. Rewriting executable upstream tests or calling the producer patch a
bootstrap overlay is not acceptable.

## Promotion order

1. Complete mandatory human review for the packaged PR 20107 candidate. It has
   the cleanest hard-task fan-out among these four candidates.
2. Complete mandatory human review for the now-packaged PR 20073 candidate; its
   older submodule revision is preserved in a distinct task-local environment.
3. Reframe PR 20121 as a two-role medium/hard boundary task, then rerun all
   gates from base.
4. Keep PR 20168 out of scenarios until its base-collection evidence problem is
   solved without implementing task behavior.

None of these decisions changes the official v0.3 task or scenario counts.
