# Commit0 chardet final quality check — v0.3

Task id: `commit0:chardet`  
Status: `qualification_ready`  
Initial source ref: `origin/commit0_combined:5539fa5e09e6084d478d7bfc5dd6b8d38c62540b`  
Complete sanity ref: `commit0/main:98b2acd5505e02c3d53e8e53053af34c8e17cb9d`

## Decision

`chardet` is suitable for AsyncCodeBench v0.3 as a curated detector/prober
dependency-chain task.

The raw stripped repository is broad and includes many encoding-specific model
tables. The released task therefore does not claim to evaluate full-library
reconstruction. It uses the public deterministic corpus evaluator
`test.py::test_encoding_detection` to measure whether agents restore the shared
contract between:

- public `detect()` / `detect_all()` and `UniversalDetector`;
- prober base/group orchestration;
- multi-byte state/distribution probers;
- single-byte and Unicode probers.

This is a clean functional-failure task: the public test collects in the
stripped state, the stripped state fails functionally, and the complete/default
state passes the same deterministic evaluator.

## Evaluator

```bash
PYTHONNOUSERSITE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=. \
python -m pytest -q test.py::test_encoding_detection
```

The evaluator intentionally excludes optional Hypothesis property tests, which
may appear in environments where Hypothesis is installed. The benchmark uses
the deterministic public corpus test only.

## Observed evaluator behavior

Initial stripped ref:

```text
381 collected
1 passed
374 failed
6 xfailed
```

Complete/default sanity ref:

```text
382 collected
377 passed
5 xfailed
```

`TaskQualityRecord` accounts for xfailed parametrized corpus cases as skipped
because the current v0.3 schema does not have a separate xfail field.

## AsyncCodeBench structure

Natural subproblems:

1. `public_api_and_detector_state`
   - `chardet/__init__.py`
   - `chardet/universaldetector.py`
   - `chardet/enums.py`
2. `prober_base_and_grouping`
   - `chardet/charsetprober.py`
   - `chardet/charsetgroupprober.py`
   - `chardet/sbcharsetprober.py`
   - `chardet/sbcsgroupprober.py`
   - `chardet/mbcharsetprober.py`
   - `chardet/mbcsgroupprober.py`
3. `multibyte_state_and_distribution`
   - `chardet/chardistribution.py`
   - `chardet/codingstatemachine.py`
   - selected multi-byte probers and state-machine/model modules
4. `singlebyte_unicode_probers`
   - `chardet/utf8prober.py`
   - `chardet/utf1632prober.py`
   - `chardet/latin1prober.py`
   - `chardet/hebrewprober.py`
   - `chardet/sbcharsetprober.py`

Primary dependency labels:

- `chardet.probers_to_detector.input_state_confidence_contract`
- `chardet.multibyte_to_group.distribution_state_contract`
- `chardet.singlebyte_unicode_to_detector.result_contract`

This is a valid async task because downstream detector/public-API code can make
stale assumptions about prober state, confidence thresholds, charset labels,
and active-prober routing. These assumptions can merge textually cleanly but
fail semantically on the public corpus.

## Rejected/deferred alternatives in this pass

Two other candidates were checked before finalizing `chardet`:

- `requests`: initial `origin/commit0_combined` fails import with an
  `IndentationError` in `src/requests/adapters.py`. This is a syntax bootstrap
  blocker, not a clean functional-failure state.
- `pexpect`: after installing the declared dependency `ptyprocess`, the
  complete scoped evaluator passes, but the stripped initial state fails
  collection on `SpawnBase.buffer = property(_get_buffer, _set_buffer)`.
  `_get_buffer/_set_buffer` are core SpawnBase state-contract methods, not
  environment-only bootstrap. This candidate should remain deferred/extended
  unless we explicitly include bootstrap-heavy tasks.

## Created assets

```text
src/asynccodebench/dataset/chardet_v03.py
scripts/build_chardet_v03_data.py
manifests/pilot/v0.3/tasks/commit0_chardet.json
manifests/pilot/v0.3/scenarios/commit0_chardet.json
manifests/pilot/v0.3/quality/commit0_chardet.json
manifests/pilot/v0.3/metrics/commit0_chardet_async_metrics.json
manifests/annotations/commit0_v0.3/chardet/annotator_a.json
manifests/annotations/commit0_v0.3/chardet/annotator_b.json
manifests/annotations/commit0_v0.3/chardet/adjudication.template.json
tests/contracts/test_chardet_dataset_v03.py
tests/contracts/test_chardet_async_metrics_v03.py
```

## Validation

Generated assets:

```bash
PYTHONNOUSERSITE=1 PYTHONPATH=src \
python scripts/build_chardet_v03_data.py
```

Task-specific contract tests:

```text
7 passed in 0.24s
```

All v0.3 dataset/async-metric contract tests:

```text
44 passed in 0.60s
```

## Remaining gate

The only remaining gate is:

```text
two independent human inclusion/exclusion annotations
```

Single-agent and multi-agent model results should be reported as benchmark
outputs, not used as dataset qualification gates.
