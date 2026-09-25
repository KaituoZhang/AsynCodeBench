# PR-Hard Task Pilot v0.4: Apache TVM

This packet records the construction provenance for recent, PR-derived Apache
TVM tasks. Four multi-agent tasks have now passed every promotion gate and are
included alongside the existing repository tasks in the unified AsynCodeBench
v0.4 community-preview release. Two single-agent calibration records and one
invalidated decomposition remain outside the released 20-task set.

## Current decision

| Candidate | Production files | Natural implementation roles | Four-condition candidate |
| --- | ---: | ---: | --- |
| `pr-hard:apache-tvm-20134` | 1 | 1 | No; single-agent calibration |
| `pr-hard:apache-tvm-20116` | 1 | 1 | No; single-agent calibration |
| `pr-hard:apache-tvm-19605` | 5 | 3 proposed | No; returned to `needs_revision` after execution audit |
| `pr-hard:apache-tvm-20153` | 6 | 3 | Yes; qualified and included in unified v0.4 |
| `pr-hard:apache-tvm-20107` | 22 | 3 | Yes; qualified and included in unified v0.4 |
| `pr-hard:apache-tvm-20073` | 9 | 3 | Yes; qualified and included in unified v0.4 |
| `pr-hard:apache-tvm-20018` | 28 | 3 | Yes; qualified and included in unified v0.4 |

The distinction is semantic, not a patch-size threshold. The first two PRs
change one production surface, so a second owner would be artificial. PR 20153
PR 20107, PR 20073, and PR 20018 have distinct producer and consumer surfaces
joined by public executable evidence. PR 19605 changes several surfaces, but the selected public evidence
does not establish that all proposed owners are necessary for evaluator
success; file count alone cannot make it a multi-agent benchmark task.

## Shared construction protocol

Each candidate workspace is constructed as

```text
pinned first parent of merged PR
        +
checksum-pinned selected upstream test changes
        +
source-build environment
        =
model-visible task state
```

The production portion of the merged PR is retained offline and is used only
for gold-green qualification. The exported workspace must not contain `.git`,
the gold production patch, PR discussion, commit messages, or a reachable gold
ref. Test comments may be sanitized to remove PR identifiers and direct
root-cause narration, but executable inputs and assertions may not be weakened
or strengthened. The registry records that sanitization and the resulting
overlay checksum.

The helper validates metadata and can stage public tests in a clean base
checkout:

```bash
python scripts/prepare_pr_hard_candidate.py

python scripts/prepare_pr_hard_candidate.py \
  --task-id pr-hard:apache-tvm-19605 \
  --workspace /path/to/tvm-at-base \
  --apply-public-tests
```

It refuses a wrong base SHA, a dirty tracked workspace, a checksum mismatch, or
a non-test overlay. If the offline gold object is present in a qualification
checkout, it also verifies that the recorded base is the gold commit's first
parent.

## Multi-agent candidate A: device compilation pipeline

### Source and task

- Candidate: `pr-hard:apache-tvm-19605`
- Base: `e159487b0e4131b6874622bf03c546e837ae84c6`
- Offline gold: `ec3171ab7a4c06fff4e9c1e441d28ef4e9a5831b`
- Public overlay: the upstream S-TIR dynamic-shared-memory regression file,
  with PR-specific commentary removed
- Environment: `tvm-cpu-llvm-source-build`

Model-visible statement:

> Refactor the TIRx device compilation sequence so dynamic shared-memory
> merging, device-region annotation and splitting, device-kernel launch
> lowering, packed-API construction, and storage legalization compose safely.
> Sibling device regions must receive independent merged dynamic-shared
> allocations, reused allocations must remain liveness-safe, and existing
> host/device calling conventions must remain valid.

### Natural decomposition

| Role | Owned production surface | Responsibility |
| --- | --- | --- |
| Shared-memory planning | `src/s_tir/transform/merge_shared_memory_allocations.cc` | liveness, reuse, and per-device-region allocation scope |
| Device-launch lowering | `src/tirx/transform/lower_device_kernel_launch.cc` | host/device ABI and launch lowering |
| Pipeline integration | three S-TIR/TIRx Python pipeline files | pass ordering across merge, split, packed API, and storage legalization |

The two directed contracts are:

1. `shared_memory_planning -> pipeline_integration`: merged buffers must be
   scoped per device region when merging precedes annotation and splitting.
2. `device_launch_lowering -> pipeline_integration`: lowering and pipeline
   order must agree on the calling convention around `MakePackedAPI`.

The focused evaluator runs `test_async_copy` and
`test_multi_thread_extent_blocks`. The latter is integrated evidence because it
applies shared-memory merging and then device-region annotation/splitting.
Broader regression evaluation covers the changed S-TIR test file, TIRx
transforms, and host/device codegen tests.

## Multi-agent candidate B: PTX immediate address expressions

### Source and task

- Candidate: `pr-hard:apache-tvm-20153`
- Base: `a35aca6a0ae5a61c486cb9a61c36b09be45f81af`
- Offline gold: `f20fa692d5dd71d875a9e310eae3e754169888fb`
- Public overlays: the upstream dedicated `test_ptx_addr.py` regression file
  plus the behavior-preserving PTX dialect and load/store regression updates;
  the unrelated kernel-registry compatibility hunk is not staged
- Environment: `tvm-cuda-codegen-source-build`

Model-visible statement:

> Add a pure `T.ptx.addr(base, byte_offset)` expression for PTX memory operands
> with signed compile-time byte displacements. The dialect schema must declare
> which address slots support offsets, lowering must validate and normalize
> operands and immediates, and rendering must produce collision-free helpers
> and correct PTX syntax while rejecting unsupported address classes.

### Natural decomposition

| Role | Owned production surface | Responsibility |
| --- | --- | --- |
| PTX dialect schema | `table.py`, `__init__.py`, `gen_stubs.py`, `tirx.pyi` | public expression, table capability, generated surface, and typing |
| Operand lowering | `engine.py` | coercion, validation, normalization, and metadata transfer |
| PTX rendering | `render.py` | helper names and final PTX address syntax |

The two directed contracts are:

1. `ptx_dialect_schema -> ptx_operand_lowering`: the table and public API
   declare the offset-capable logical slots and excluded address classes that
   lowering consumes.
2. `ptx_operand_lowering -> ptx_rendering`: lowering supplies normalized signed
   offsets and slot identities that rendering uses in helper names and memory
   operands.

The dedicated upstream test file contains separate schema, lowering, rendering,
and end-to-end assertions. These exact selectors form upstream, downstream,
and integrated Dependency Checker groups in the registry. The focused
evaluator runs the file; the regression evaluator also runs the existing PTX
dialect and load/store suites.

## Multi-agent candidate C: shared TVMScript type parameters

### Source and task

- Candidate: `pr-hard:apache-tvm-20107`
- Base: `0468e13a1450a4429758003612aa2b3d080c1f13`
- Offline gold: `bb9bc20a8294fb19a2a40f029fe57baa546a8206`
- Public overlay: selected upstream generic Script, Relax, and TIRx regression
  tests; production changes remain offline
- Environment: `tvm-cpu-llvm-source-build`

Model-visible statement:

> Add PEP 695-style function type-parameter syntax to TVMScript for symbolic
> variables shared by Relax and TIRx. The generic Script parser and document
> printer must preserve type parameters, each dialect must translate them to
> and from dependent signatures, and parse-print round trips must retain the
> declared symbolic-variable order and constraints. Do not modify public tests.

### Natural decomposition and fan-out graph

```text
shared Script AST/parser/printer core
          |                  |
          v                  v
Relax dependent signature   TIRx dependent signature
```

| Role | Owned production surface | Responsibility |
| --- | --- | --- |
| Shared Script signature core | generic Script AST, parser, document, Python/C++ printer surfaces | preserve ordered function type parameters across the shared representation |
| Relax dependent signature | Relax parser and printer surfaces | translate shared type parameters to and from Relax dependent signatures |
| TIRx dependent signature | TIRx parser and printer surfaces | translate shared type parameters to and from TIRx dependent signatures |

The two directed contracts are
`shared_script_signature_core -> relax_dependent_signature` and
`shared_script_signature_core -> tirx_dependent_signature`. This is a genuine
fan-out dependency rather than a file-count split: the shared-core-only state
passes exactly 1/3 focused selectors, while adding either consumer passes 2/3
and leaves the sibling consumer red. Only the fully integrated gold state
passes all 3/3 selectors.

## Matched execution conditions

Each execution-eligible multi-agent candidate materializes the same four
conditions used by the current benchmark:

| Condition | Agents | Scheduling and information |
| --- | ---: | --- |
| `iterative_single` | 1 | one agent owns all production surfaces |
| `serial_specialists` | 3 | producer artifacts and targeted results are handed to consumers in dependency order |
| `async_private` | 3 | specialists run concurrently; no in-flight information is delivered |
| `async_message` | 3 | specialists run concurrently and may exchange structured messages and explicit artifacts |

All conditions use the same base, public tests, final evaluator, editable-path
union, and scaffold. The scenario records preserve the original construction
budget provenance (24 steps, 60,000 tokens, 8 test actions, 1,800 seconds),
while executable comparison runs consume the frozen
`asyncodebench-v0.3-standard-100` profile: each model-facing run may stop early
through `FinishTool` and is capped at 100 responses. The candidate manifests keep
`official_result_eligible=true` for the four qualified tasks. The invalidated
19605 record remains ineligible, and historical run bundles retain the
eligibility metadata recorded when they were produced.

## Automated qualification results

PR 20153, PR 20107, PR 20073, and PR 20018 have completed every automated construction gate. PR 19605 initially
passed red-green and gold-state checks, but a subsequent role-local execution
audit invalidated its multi-agent qualification. The production gold remains
offline; qualification used isolated worktrees and the four approved tasks are
result-eligible only because their separate human-review gate is now complete.

| Candidate | Base focused | Gold focused | Gold regression | Required role/checker evidence | Remaining gate |
| --- | --- | --- | --- | --- | --- |
| `pr-hard:apache-tvm-19605` | 1 passed, 1 failed | 2 passed | 328 passed, 2 skipped, 8 xfailed, 1 xpassed | Invalidated: two roles are base-green and the integrated selector does not execute their surfaces | Role-local observability, integration necessity, evaluator coverage, human review |
| `pr-hard:apache-tvm-20153` | 1 passed, 11 failed as intended | 12 passed | 57 passed, 45 optional ptxas cases skipped | 6/6 exact role selectors passed | None; human approved |
| `pr-hard:apache-tvm-20107` | 0 passed, 3 failed as intended | 3 passed | 501 passed, 2 xfailed | 3/3 exact role selectors plus both fan-out ablations passed | None; human approved |
| `pr-hard:apache-tvm-20073` | 0 passed, 6 failed as intended | 6 passed | 28 passed | 6/6 exact role selectors plus both producer and no-consumer ablations passed | None; human approved |
| `pr-hard:apache-tvm-20018` | 0 passed, 8 failed as intended | 8 passed | 782 passed, 3 xfailed | Ordered chain ablation: core 3/8, core + Script 5/8, complete integration 8/8 | None; human approved |

For all five multi-agent candidates, the pinned base is the recorded gold commit's first parent, the
production diff exactly matches the proposed ownership union, and public
overlays apply in order and touch tests only. Gold-green evidence alone is not
sufficient for dependency qualification. In PR 19605, `test_async_copy` and
the device-launch selectors already pass on the base; the only focused base
failure occurs in the shared-memory pass, even though it was assigned to the
pipeline owner. The claimed integrated selector does not invoke
`LowerDeviceKernelLaunch` or any of the three Python compilation pipelines.
The registry therefore exposes no execution-eligible protocol for this
candidate. Machine-readable evidence is under
`manifests/candidates/pr_hard_v0.4/qualification/`.
The repository contract suite, including v0.4 overlay, ownership, scenario,
environment-lock, qualification-record, human-review, release-index, and
runnable-package checks, passes 164/164 tests (rechecked 2026-08-29).

## Environment preparation

The machine-readable templates are in
`configs/environments/pr_hard_tvm.v0.4.json`. Build TVM from the candidate's
pinned source and submodules; do not use a preinstalled TVM wheel because agent
edits include C++ sources. Both profiles use an LLVM-enabled CMake/Ninja build
with CUDA and GTest disabled. TVM still compiles its CUDA source generator in
this configuration, so the PTX focused evaluator can inspect generated source
without a CUDA toolkit or GPU. Optional upstream ptxas certification tests skip
and are not required Dependency Checker evidence.

Each task must install its own pinned `3rdparty/tvm-ffi` checkout with
`--no-build-isolation`; sharing one editable installation across task packages
can load an incompatible runtime and is forbidden by the environment contract.
PR 20107 and PR 20153 currently pin the same recursively verified submodule
tree, but still retain separate task-local environments and runtime packages.
PR 20073 and PR 20018 pin distinct `tvm-ffi` revisions and recursive submodule
manifests, which are installed and validated independently.

For PR 20107, PR 20153, PR 20073, or PR 20018, a fresh clone can reconstruct the complete
model-visible runtime without access to the offline gold:

```bash
.venv-benchmark/bin/python scripts/prepare_pr_hard_runtime.py \
  --task-id pr-hard:apache-tvm-20107

.venv-benchmark/bin/python scripts/prepare_pr_hard_runtime.py \
  --task-id pr-hard:apache-tvm-20107 \
  --check
```

The generated task-specific package under `.cache/pr_hard_runtime/v0.4/` is
local and ignored. It contains a one-commit, no-remote seed plus the locked
runtime; it does not contain the production gold. See
`docs/PR_HARD_20153_COLLABORATOR_RUNBOOK.md` for the detailed reconstruction
and validation workflow.

The checked-in explicit micromamba lock and pinned Python requirements freeze
the qualification toolchain: Ubuntu 22.04.4, GCC/G++ 11.4, LLVM 18.1.8, Python
3.11.16, CMake 4.4.2, Ninja 1.13.2, and pytest 9.1.1. Qualification records
also pin recursive submodule manifests, configure commands, cold-build timing,
and evaluator timing. The evaluator performs an incremental rebuild after
agent edits and imports the in-tree Python package against the freshly built
libraries.

The framework is evaluator-agnostic even though these upstream PRs provide
pytest files. A later candidate may bind the same contract abstraction to
CTest, `cargo test`, or a repository-specific command.

## Candidate execution

The runner performs qualification preflight before creating an output bundle
or starting a workspace. It refuses `needs_revision` candidates, non-passing
Dependency Checker groups, incomplete role-local base evidence, missing runtime
package validation, and deviations from the frozen standard-100 profile.

After loading the documented model environment, inspect the eligible package:

```bash
cd reproductions/async-swe-agents
uv run python run_pr_hard.py \
  --task_id pr-hard:apache-tvm-20107 \
  --protocol async_private \
  --model "$LLM_MODEL" \
  --subagent_model "$LLM_SUBAGENT_MODEL" \
  --dry_run
```

Run all four matched conditions with a fresh run ID:

```bash
RUN_ID="qwen36-27b-gpu1-standard100-$(date -u +%Y%m%dT%H%M%SZ)" \
  scripts/run_pr_hard_20107_all_protocols_env.sh
```

New runs for the four qualified tasks report
`official_result_eligible=true`. Frozen historical bundles are not rewritten;
their original metadata remains provenance for the execution-time release
state. The 19605 wrapper exits immediately with status 2 so invalidated results
cannot be generated accidentally.

## Promotion gates

A multi-agent candidate enters official results only after all gates pass:

1. **Base red:** public focused evidence fails on the base for the intended
   behavioral reason, not because of setup or collection failure.
2. **Gold green:** offline gold plus identical public evidence passes focused
   and regression evaluators.
3. **Role-local observability:** every specialist has executable local evidence
   and every dependency has non-empty upstream, downstream, and integrated
   groups.
4. **Integration necessity:** at least one integrated checker genuinely
   depends on artifacts from distinct owners.
5. **Environment freeze:** checksums, image/toolchain versions, source build,
   and timing are reproducible within the frozen budget.
6. **Integrity:** the model-visible image contains no production gold, hidden
   Git history, PR discussion, or answer-bearing test narration.
7. **Human review:** a reviewer approves the natural responsibilities,
   directionality, public evidence, editable paths, problem statement, and
   absence of manufactured work.
Difficulty pilots are a downstream reporting step, not a construction gate.
Model trajectories may estimate difficulty after the task is frozen, but they
may not define task statements, ownership, dependencies, or checkers.

Any future candidate that fails role-local observability or integration
necessity is demoted to calibration or revision rather than forcibly retained
as a multi-agent task.

## Checked-in assets

- Candidate registry: `configs/tasks/pr_hard_candidates.v0.4.json`
- Environment templates: `configs/environments/pr_hard_tvm.v0.4.json`
- Environment locks: `configs/environments/pr_hard_tvm.v0.4.*-lock.txt`
- Scenario manifests:
  `manifests/candidates/pr_hard_v0.4/scenarios/`
- Public test overlays: `data/overlays/pr_hard/`
- Registry schema: `schemas/v0.4/pr_hard_candidate_registry.schema.json`
- Automated qualification records and schema:
  `manifests/candidates/pr_hard_v0.4/qualification/` and
  `schemas/v0.4/pr_hard_qualification_record.schema.json`
- Human-review records: `manifests/annotations/pr_hard_v0.4/`
- Unified release index: `manifests/release/v0.4/`
- Human-review validator: `scripts/validate_pr_hard_human_reviews.py`
- Unified release-index builder: `scripts/build_v04_release_index.py`
- Preparation helper: `scripts/prepare_pr_hard_candidate.py`
- Portable PR 20107/20153/20073/20018 runtime builder: `scripts/prepare_pr_hard_runtime.py`
- Collaborator runbook: `docs/PR_HARD_20153_COLLABORATOR_RUNBOOK.md`

Source facts and test patches were verified against the merged Apache TVM pull
requests on 2026-08-23. PR labels are provenance metadata, not a substitute for
executable qualification.
