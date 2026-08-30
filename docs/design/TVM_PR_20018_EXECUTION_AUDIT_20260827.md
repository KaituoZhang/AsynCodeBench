# TVM PR 20018 Base/Gold/Ablation Execution Audit

Date: 2026-08-27

Status: **automated construction gates passed; mandatory human review remains
pending**. This task is a v0.4 candidate and is not official-result eligible.

## Provenance and public evidence

- First-parent base: `302aaf9f961a6e0a2c5cc23dc87e51fbaabd1e42`
- Offline gold: `9bfefb7e4b2f13f92b59ed4755bc83d856369c40`
- Pinned `3rdparty/tvm-ffi`: `5411a642d98bba14d4cb1e19a793c5b6758be019`
- Production diff: 28 files, +180/-139
- Public test-only overlay:
  `data/overlays/pr_hard/apache_tvm_20018/0001-public-regression-tests.patch`
- Overlay SHA-256:
  `4d7f24a5fca3967028012742367c608f809f136536db797876976e3ca66eb7ab`

The overlay contains 14 upstream test modules and no production changes, PR
identifier, base SHA, gold SHA, or production patch. A comment-only CUDA hunk
that directly narrated the old implementation failure was excluded; no
executable behavior or assertion was changed by this sanitization.

## Natural decomposition

The verified ownership graph is a three-stage compiler chain:

```text
Return IR schema and visitors
            |
            v
TVMScript construction, parsing, and rendering
            |
            v
legality transforms, legacy-retirement, Relax clients, and C/LLVM emission
```

The 9-file IR role defines the first-class node, FFI/Python exposure, structural
behavior, and visitor dispatch. The 5-file Script role consumes that contract
to construct, parse, and print returns. The 14-file integration role consumes
Script-emitted returns, retires the legacy intrinsic, updates direct Relax
clients, enforces parallel/device legality, and emits target terminators.

The paths are pairwise disjoint and their union is exactly the 28-file upstream
production diff. The topology is a chain rather than a fan-out: retiring the
old return intrinsic before the Script producer migrates creates a real stale
contract and prevents collection/build. This is retained as expected ablation
evidence, not hidden as an environment error.

## Execution matrix

| Materialized state | Focused result | Interpretation |
| --- | ---: | --- |
| Base + public tests | 0/8 | nontrivial base-red; all selectors collect |
| Return IR core | 3/8 | schema, structural behavior, and visitors pass |
| Return IR core + Script | 5/8 | construction and rendering additionally pass |
| Complete upstream production state | 8/8 | transforms and compiled emission pass |

An attempted downstream-before-Script state failed at the retired legacy-return
contract in Python import or C++ consumers. This is the expected stale-contract
failure for the second edge and explains why the task must not be represented
as independent fan-out consumers.

The 14-module scoped gold regression collected 785 tests and returned:

```text
782 passed, 3 xfailed, 0 failed, 0 errors
```

The environment is CPU-only with LLVM 18.1.8; no GPU execution is required.

## Dependency classification and difficulty

1. `return_ir_core -> return_script_surface`: **interface dependency**. The
   Script layer consumes the node constructor, value shape, structural
   semantics, and visitor contract.
2. `return_script_surface -> return_lowering_codegen_integration`:
   **integration contract**. Script-emitted returns must survive legality
   transforms and become valid C/LLVM terminators while the legacy contract is
   retired coherently.

Difficulty is **hard**. The task spans Python, C++, FFI, IR reflection,
visitors, parser/printer behavior, compiler transforms, Relax call sites, and
two target-emission layers. Coordination depth is higher than a two-way file
split because the third role consumes a completed prefix of the chain.

## Remaining gate

Automated construction, environment, runtime-package, and runner evidence may
advance the candidate to human review, but automation is not semantic inclusion
authority. Until the mandatory human review is approved, keep:

```text
qualification_status=pending_human_review
official_result_eligible=false
```
