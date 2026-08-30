# Apache TVM PR candidate screening for the AsynCodeBench extension

Status: static source-and-test screening, not benchmark qualification
Screening date: 2026-08-26
Repository: `apache/tvm`

## Outcome

This screening found **nine primary raw-task candidates** and **five
conditional candidates** for a larger PR-derived AsynCodeBench extension. The
primary candidates have a plausible natural multi-owner decomposition,
directed producer--consumer contracts, and separate or end-to-end public test
changes. None is yet execution-eligible: the next stage must reconstruct the
merged PR's first parent, expose only answer-free upstream tests, and execute
base-red, gold-green, role-local, integrated-edge, regression, environment, and
human-review gates.

The search examined 200 merged-PR search results at title/body level: the 100
most recently updated merged PRs since 2025 and 100 PRs merged during calendar
year 2025. Forty-two PRs received changed-file inspection, and 18 high-potential
or ambiguous PRs received test-patch inspection. Existing pilot PRs 20116,
20134, 19605, and 20153 are not counted as newly found candidates.

Follow-up execution has now been completed for the first four entries. See
`docs/design/TVM_PR_DEEP_QUALIFICATION_20260826.md`. PRs 20107 and 20073
advance to runtime packaging; PR 20121 requires a two-role rescope, and PR
20168 requires base-collectable public checker evidence. The execution audit
also corrected the preliminary base SHAs for PRs 20107 and 20073 to the actual
first parents of their merged production commits.

## Strict interpretation of AsynCodeBench

A PR is retained as a raw multi-agent candidate only when static public
evidence supports all of the following hypotheses:

1. There are at least two coherent implementation responsibilities that would
   exist in an ordinary compiler/runtime workflow.
2. At least one responsibility produces a semantic interface, state shape,
   lowering convention, or integration artifact consumed by another.
3. The PR includes public executable evidence that plausibly observes the
   producer, consumer, and integrated behavior. File count and one broad
   end-to-end failure are insufficient.
4. The production patch can plausibly be partitioned by non-overlapping owned
   paths without inventing work or requiring two agents to edit one central
   file.
5. The task looks solvable under the frozen AsynCodeBench budget and can be
   evaluated in a reproducible environment.
6. The task statement and checker selection can be constructed from the base,
   public PR tests, public source, and documentation without model trajectories
   or the production gold.

Static screening cannot establish base-red, role-local red, or integrated-edge
necessity. Those are execution gates. In particular, a test name that sounds
integrated does not count unless coverage or instrumentation shows that it
executes both claimed production surfaces.

## Primary materialization queue

| Priority | PR | Proposed natural graph | Why it survives static screening | Main qualification risk |
| ---: | --- | --- | --- | --- |
| 1 | [#20121](https://github.com/apache/tvm/pull/20121) | frontend KV API/kernels -> runtime ABI -> paged-cache state machine | Three cross-language surfaces; CPU shared-KV and sliding-window tests exercise public calls through runtime implementation | Confirm each role is base-red and that FFI-only ownership is substantive |
| 2 | [#20107](https://github.com/apache/tvm/pull/20107) | shared signature syntax -> Relax/TIRx parser fan-out -> portable printer round-trip | Separate Relax, TIRx, and printer tests; CPU-only and deterministic | Core parser/printer files may need a carefully balanced ownership split |
| 3 | [#20168](https://github.com/apache/tvm/pull/20168) | core tuple IR -> visitor/functor fan-out -> parser/printer round-trip | Core schema, traversal, equality, and script tests are independently observable | Six-commit patch; verify all changed production paths belong to one coherent task |
| 4 | [#20073](https://github.com/apache/tvm/pull/20073) | source coordinates -> IRBuilder span stack -> parser/inline expansion | Direct builder test plus parser, inline-call, tile-call, and structural-identity tests | Likely two strong roles rather than three; classify medium, not hard, if confirmed |
| 5 | [#20018](https://github.com/apache/tvm/pull/20018) | Return IR schema -> script/functors -> legality transforms -> C/LLVM codegen | Natural compiler pipeline with schema, visitor, transform, and target consumers | Forty-three files; ensure fixed-budget solvability and exact role-local base failures |
| 6 | [#18421](https://github.com/apache/tvm/pull/18421) | stepped-loop IR/script -> loop canonicalization -> multi-target codegen | Parser, canonicalization, C/LLVM, and CUDA evidence provides a clean chain | Forty-seven files and nine commits; many mechanical propagation edits may dominate |
| 7 | [#20076](https://github.com/apache/tvm/pull/20076) | physical local-buffer view -> printer + register-copy + reduction consumers | A natural fan-out graph with parser/printer, copy, and reduction evidence | Numerical consumer tests may require CUDA; establish a device-free required core |
| 8 | [#20075](https://github.com/apache/tvm/pull/20075) | datapath-B layout -> allocation/builder -> TMEM transfer + GEMM consumers | Layout mapping, validation, codegen, round-trip, and GEMM tests form fan-out/join structure | CUDA architecture/toolchain requirements may make the environment expensive |
| 9 | [#20133](https://github.com/apache/tvm/pull/20133) | scan routing/axis normalization -> generic WebGPU cumsum implementation | Structural dispatch tests and numerical coverage observe routing and implementation | Determine whether registration is a real owner and freeze a device-free evaluator |

These nine entries are raw task candidates, not nine promised benchmark tasks.
The first execution audit may legitimately reject most of them.

## Primary candidate details

### PR 20121: shared-KV attention and per-layer sliding windows

- Pinned screening base: `ea0950abfe49031720171a931fc244c0fb2033e2`
- Offline-gold candidate: `27c2e019d0ce6182158020c7534dda4a3ce981ae`
- Scale: 8 files, +422/-64, 2 commits
- Proposed roles:
  1. frontend KV-cache API and generated prefill kernels;
  2. abstract runtime/FFI contract;
  3. paged-cache window and shared-KV state implementation.
- Proposed edges:
  `frontend_api -> runtime_abi -> paged_cache_state`, plus
  `prefill_mask_contract -> paged_cache_state`.
- Upstream test evidence to audit:
  - `tests/python/relax/test_runtime_builtin_paged_attention_kv_cache_cpu.py::test_per_layer_sliding_window`
  - `tests/python/relax/test_runtime_builtin_paged_attention_kv_cache_cpu.py::test_attention_with_shared_kv`
  - `tests/python/relax/test_runtime_builtin_paged_attention_kv_cache_tir.py::test_paged_prefill_layer_sliding_window_mask`

### PR 20107: PEP 695 symbolic variables in Relax and TIRx

- Pinned screening base: `0468e13a1450a4429758003612aa2b3d080c1f13`
- Offline-gold candidate: `bb9bc20a8294fb19a2a40f029fe57baa546a8206`
- Scale: 27 files, +588/-61, 3 commits
- Proposed roles:
  1. shared parser/signature and function-document support;
  2. Relax dependent-signature parser/printer;
  3. TIRx dependent-signature parser/printer.
- Proposed topology: one shared producer fans out to two dialect consumers;
  portable round-trip tests join parser and printer behavior.
- Upstream test evidence to audit:
  - `tests/python/relax/test_tvmscript_type_vars.py::test_type_vars_roundtrip`
  - `tests/python/tirx/test_tvmscript_type_vars.py::test_type_vars_roundtrip`
  - `tests/python/tvmscript/test_tvmscript_printer_python_doc_printer.py::test_print_function_doc_with_type_params`

### PR 20168: first-class tuple expressions

- Pinned screening base: `4e9a099d154d7c4644a40a1a9c00b8873226468e`
- Offline-gold candidate: `2647a19cc39965e39033904f42e934a76d427d53`
- Scale: 23 files, +439/-195, 6 commits
- Proposed roles:
  1. core IR tuple schema and Relax compatibility aliases;
  2. TIRx traversal, mutation, equality, and path support;
  3. TIRx builder/parser/printer integration.
- Proposed edges: `core_tuple_schema -> traversal` and
  `core_tuple_schema -> script_integration`; parser/printer round-trip joins
  schema and traversal behavior.
- Upstream test evidence to audit:
  - `tests/python/tirx-base/test_tir_expr_functor.py::test_tuple`
  - `tests/python/tirx-base/test_tir_expr_functor.py::test_tuple_get_item`
  - `tests/python/tirx-transform/test_tir_functor.py::test_tuple_default_traversal_and_mutation`
  - `tests/python/tirx/test_parser_printer.py::test_tuple_let_binding_and_traversal`

### PR 20073: parser source spans

- Pinned screening base: `62fb780bb0a8da62e3808f60a2343f6fd1d4b01f`
- Offline-gold candidate: `ae99c3fd92ddb8cd5bb0cbda1dd9584b525b7a24`
- Scale: 9 files, +330/-15, 1 commit
- Proposed roles:
  1. IRBuilder active-span state and emitted-node attachment;
  2. parser source-coordinate propagation and inline expansion history.
- Proposed edge: `source_coordinate_contract -> active_span_stack -> emitted_IR_span`.
- Upstream test evidence to audit:
  - `tests/python/tvmscript/test_tvmscript_ir_builder_tir.py::test_ir_builder_source_span_applies_to_emitted_stmt`
  - `tests/python/tvmscript/test_tvmscript_parser_source.py::test_parser_attaches_span_to_direct_call`
  - `tests/python/tvmscript/test_tvmscript_parser_source.py::test_parser_retains_inline_call_site_and_definition_spans`
  - `tests/python/tvmscript/test_tvmscript_parser_source.py::test_parser_attaches_span_to_tile_primitive_call`

### PR 20018: first-class Return statement

- Verified first-parent base: `302aaf9f961a6e0a2c5cc23dc87e51fbaabd1e42`
- Offline-gold candidate: `9bfefb7e4b2f13f92b59ed4755bc83d856369c40`
- Scale: 43 files, +328/-195, 1 commit
- Execution-qualified roles:
  1. Return node schema, reflection, and statement functors;
  2. TVMScript builder/parser/printer surface;
  3. legacy-return retirement, Relax consumers, legality transforms, and
     C/LLVM target emission.
- Verified topology: a three-stage chain. The upstream patch deletes the
  legacy return intrinsic, so the third role must consume the completed Script
  migration; skipping that producer produces the expected stale-contract
  build/import failure.
- Upstream test evidence to audit:
  - `tests/python/tirx-base/test_tir_base.py::test_return_const`
  - `tests/python/tirx-base/test_tir_base.py::test_return_accepts_expr_and_roundtrips`
  - `tests/python/tirx-base/test_tir_base.py::test_return_stmt_functor_traversal_and_mutation`
  - `tests/python/tvmscript/test_tvmscript_syntax_sugar.py::test_return_statement`
  - `tests/python/tvmscript/test_tvmscript_printer_tir.py::test_return_statement`
  - `tests/python/tirx-transform/test_tir_transform_make_packed_api.py::test_return_from_parallel_scope_is_rejected`
  - `tests/python/tirx-transform/test_tir_transform_split_host_device.py::test_device_kernel_nonzero_return_is_rejected`
- Execution audit: base 0/8, IR core 3/8, IR core plus Script 5/8,
  complete gold 8/8; scoped gold regression 782 passed and 3 xfailed.
- Remaining gate: mandatory human review. The candidate remains
  `official_result_eligible=false`.

### PR 18421: stepped loops

- Pinned screening base: `33fa9262faf085ec0ad2d7ef0d843c7e4c2ba148`
- Offline-gold candidate: `13ea9dc10436836e9654a897cf6f8f87813dc8a4`
- Scale: 47 files, +619/-126, 9 commits
- Proposed roles:
  1. `ForNode.step` schema and TVMScript surface;
  2. loop canonicalization and pass-preservation logic;
  3. C/LLVM code generation;
  4. CUDA/other target code generation.
- Proposed edge chain: `loop_step_schema -> canonicalized_loop_contract -> target_codegen`.
- Upstream test evidence to audit:
  - `tests/python/tvmscript/test_tvmscript_parser_tir.py::test_tir_loop_steps`
  - `tests/python/tir-transform/test_tir_transform_canonicalize_loop.py::test_canonicalize_loop`
  - `tests/python/tir-transform/test_tir_transform_canonicalize_loop.py::test_canonicalize_nested_loop`
  - `tests/python/codegen/test_target_codegen.py::test_codegen_loop_step`
  - `tests/python/codegen/test_target_codegen_cuda.py::test_cuda_loop_step`

### PR 20076: physical-order local buffer views

- Pinned screening base: `1b992163b03522fb061c3f86b9dd7388f58a73f9`
- Offline-gold candidate: `6e13371b6602f50cbce9e733f6b4479ae4fc4a01`
- Scale: 12 files, +561/-110, 2 commits
- Proposed roles:
  1. local-buffer physical view and layout contract;
  2. parser/printer preservation;
  3. register-copy lowering;
  4. reduction/GEMM consumers.
- Proposed topology: fan-out from one view contract to printer, copy, and
  compute consumers.
- Upstream test evidence to audit:
  - `tests/python/tirx/test_parser_printer.py::test_buffer_local_physical_order`
  - `tests/python/tirx/test_parser_printer.py::test_buffer_local_physical_span_includes_gaps_and_offset`
  - `tests/python/tirx/operator/tile_primitive/cuda/copy/test_reg.py::test_reg_roundtrip_gapped_permuted_storage`
  - `tests/python/tirx/operator/tile_primitive/cuda/reduction/test_reduction.py::test_reduction_op_warp_shuffle_gapped_permuted_storage`

### PR 20075: TMEM datapath B

- Pinned screening base: `115029b3ab44c177bfca56c2c1bcf65566450d26`
- Offline-gold candidate: `771193a5c26188713b2ec01f5bcd937bf7966fae`
- Scale: 11 files, +664/-54, 1 commit
- Proposed roles:
  1. datapath-B layout and validation;
  2. allocation/builder support;
  3. TMEM load/store transfer;
  4. asynchronous GEMM consumer.
- Proposed topology: layout producer fans out to transfer and GEMM, with
  end-to-end GEMM readback joining both.
- Upstream test evidence to audit:
  - `tests/python/tirx/operator/tile_primitive/cuda/copy_async/test_tmem_16xnb.py::test_tmem_datapath_layout_B_col_split_mapping`
  - `tests/python/tirx/operator/tile_primitive/cuda/copy_async/test_tmem_16xnb.py::test_datapath_B_codegen`
  - `tests/python/tirx/operator/tile_primitive/cuda/copy_async/test_tmem_16xnb.py::test_datapath_B_ld_st_roundtrip`
  - `tests/python/tirx/operator/tile_primitive/cuda/gemm_async/test_gemm_async.py::test_gemm_tcgen05_cta_group_2_datapath_b_readback`

### PR 20133: non-contiguous WebGPU cumsum

- Pinned screening base: `6734aa22568bdce3da2d95008e8486d97e1250a7`
- Offline-gold candidate: `1f352bf9c1af19b9f43584a5d27e9a14c30b468b`
- Scale: 4 files, +266/-27, 1 commit
- Proposed roles:
  1. sort/scan dispatch, axis normalization, and dtype contract;
  2. generic GPU non-contiguous cumsum implementation and registration.
- Proposed edge: `dispatch_contract -> gpu_cumsum_kernel`.
- Upstream test evidence to audit:
  - `tests/python/relax/test_backend_dispatch_sort_scan.py::test_dispatch_cumsum_webgpu_axes_and_dtypes`
  - `tests/python/relax/test_backend_dispatch_sort_scan.py::test_dispatch_cumsum_webgpu_symbolic_non_contiguous_axis`
  - `tests/python/relax/test_backend_dispatch_sort_scan.py::test_gpu_axis_1_cumsum_numerical`

## Conditional queue

| PR | Why it remains interesting | Why it is not in the primary queue |
| --- | --- | --- |
| [#20035](https://github.com/apache/tvm/pull/20035) | Deterministic CPU checkpoint metadata, page export/import, and round-trip state tests | Most behavior is concentrated in one +1,000-line `paged_kv_cache.cc` change; the API owner may be too small and path ownership too imbalanced |
| [#20180](https://github.com/apache/tvm/pull/20180) | Elegant `cluster scope -> launch tags -> runtime launch attribute` chain with transform and C++ tests | Added tests do not visibly execute the final `CUDAWrappedFunc` branch; integrated-edge observability may fail exactly as PR 19605 did |
| [#20097](https://github.com/apache/tvm/pull/20097) | Analyzer clone/context lifetime and Z3 memo-pool tests are deterministic and compact | The two proposed owners may be one tightly coupled prover responsibility rather than natural collaborators |
| [#17599](https://github.com/apache/tvm/pull/17599) | Rich Adreno graph across custom storage annotation, vdevice folding, specialization, legalization, and scheduling; many structural tests | 46 files, +4,250 lines, 31 commits, and Adreno environment requirements may exceed the frozen budget; treat as a long-horizon stretch task |
| [#19998](https://github.com/apache/tvm/pull/19998) | Pattern support, region merging, codegen, and TensorRT runtime form a potential join graph | Thirteen commits bundle several fixes and require TensorRT; risk of heterogeneous subproblems and non-frozen external dependencies |

## Screened-out or calibration-only PRs

These negative decisions are part of the audit trail.

| PR | Decision | Reason |
| --- | --- | --- |
| #20136 | single-agent calibration only | One production file (`tvmjs.py`) |
| #20132 | single-agent calibration only | One WebGPU codegen implementation surface plus its header/target registration |
| #20159 | reject multi-agent task | Register-cap codegen and non-portable cluster runtime support are parallel features, not one directed dependency |
| #20140 | reject multi-agent task | Bundles four independent missing PTX capabilities |
| #20120 | reject multi-agent task | Refactor plus several independent PTX fixes in five commits |
| #20110 | reject multi-agent task | Explicitly contains three independent changes |
| #20103 | reject fixed-budget task | 141 files and roughly 27k changed lines; migration scale overwhelms the collaboration variable |
| #20101 | single-agent calibration only | Metal codegen implementation and header are one natural responsibility |
| #20086 | reject fixed-budget task | 98-file repository-wide buffer-parameter migration |
| #20080 | reject fixed-budget task | 199-file consolidated fork delta with heterogeneous features |
| #20079 | reject fixed-budget task | 266-file typed-buffer migration |
| #20074 | single-agent calibration only | One production file (`pipeline.py`) |
| #20059 | single-agent calibration only | One production TypeScript file (`webgpu.ts`) |
| #20028 | reject under current public-evidence policy | No upstream test file changed; static screening found no answer-free regression overlay candidate |
| #20019 | reject benchmark task | 65-file removal/refactor dominated by mechanical deletions and removed tests |
| #20016 | reject benchmark task | 102-file mechanical field rename with only narrow reflection tests |
| #19923 | reject | Test-only PR with no production behavior to reconstruct |
| #18604 | reject under current public-evidence policy | Runtime launch changes without an upstream test patch |
| #18418 | single-agent calibration only | Schedule API/trace wiring and one core primitive implementation form one schedule responsibility |
| #18528 | reject multi-agent task | Two root-cause fixes share one broad MMA test but do not establish a directional cross-owner contract |
| #18511 | reject multi-agent task | DumpIR is one pass-instrument responsibility; unrelated cleanup should not become another owner |
| #18465 | single-agent calibration only | Macro suffixing is one parser/IRBuilder responsibility |
| #18467 | single-agent calibration only | One runtime implementation file; lockfile is not an implementation role |
| #18544 | single-agent calibration only | Three frontend translator files implement one converter-registration responsibility |
| #18499 | single-agent calibration only | One frontend translator implementation file |

## Required next-stage protocol

For each primary candidate, perform these steps in order and stop immediately
when a gate fails:

1. Verify that the recorded base is the first parent of the merged production
   commit and recursively pin all submodules.
2. Separate production and test diffs. Stage only upstream tests; sanitize only
   comments that reveal PR identity or implementation answers; checksum every
   overlay.
3. Build a no-remote, no-`.git`, no-gold model-visible workspace.
4. Run exact focused tests on the base. Reject setup/collection failures and
   reject candidates where only one proposed role is behaviorally red.
5. Run the same tests on offline gold and a broader regression evaluator.
6. Define non-overlapping owned production paths and run every role-local
   selector on base and gold.
7. Instrument or trace each proposed integrated selector. Reject any edge whose
   selector does not execute both producer and consumer surfaces.
8. Freeze a task-specific build/runtime profile. Required checkers should avoid
   a physical GPU when source, structural IR, or CPU execution gives equivalent
   evidence.
9. Construct the four matched AsynCodeBench conditions with the same base,
   public tests, evaluator, editable union, and budget.
10. Require human review of naturalness, answer-freedom, ownership, executable
    dependence, and plausible stale-assumption risk.

Recommended first batch: PRs **20121, 20107, 20168, and 20073**. They provide
three-role chain/fan-out examples and one compact two-role medium task, while
remaining largely CPU-testable. PRs 20076 and 20075 should follow as graph-rich
CUDA candidates after a device-free required evaluator is demonstrated.

Machine-readable screening records are in
`manifests/candidates/pr_hard_v0.4/discovery/apache_tvm_pr_screening_20260826.json`.
