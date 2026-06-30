# Commit0 wcwidth data example — v0.3

Specification: `SPECIFICATION_v0.3.md`  
Guide: `docs/protocols/COMMIT0_DATA_EXAMPLE_GUIDE_v0.3.md`  
Task: `commit0:wcwidth`  
Status: qualification-ready draft, pending independent annotation and
baseline evaluations

## Summary

`commit0:wcwidth` is a small interface-dependency task. The public Commit0
state leaves two implementation files unfinished:

```text
wcwidth/unicode_versions.py
wcwidth/wcwidth.py
```

The natural producer subproblem is the Unicode version catalog. The natural
consumer subproblem is the terminal-width algorithm, which imports
`list_versions()` and depends on the supported version ordering and string
format while implementing `_wcmatch_version()`, `wcwidth()`, `wcswidth()`, and
binary interval lookup.

This task is smaller than TinyDB or Portalocker. Its role in the v0.3 pilot is
to provide a compact interface-dependency case where asynchronous workers can
make stale or incompatible assumptions about the version catalog API.

## Public evidence used

Only public Commit0 evidence was used for task structure:

```text
spec.pdf.bz2@commit0
wcwidth/unicode_versions.py@commit0
wcwidth/wcwidth.py@commit0
tests/test_core.py@commit0
tests/test_emojis.py@commit0
tests/test_table_integrity.py@commit0
tests/test_ucslevel.py@commit0
```

The completed public branch was used only for evaluator sanity checking, not
for decomposition, prompt construction, or agent-visible context.

## Evaluator

The evaluator intentionally excludes one packaging metadata test:

```bash
python -m pytest -q -p no:cacheprovider -o addopts= tests -k 'not test_package_version'
```

`tests/test_core.py::test_package_version` checks installed distribution
metadata via `importlib.metadata.version("wcwidth")`. In our repository-root
evaluation setup, that test measures editable-install state rather than the
unfinished implementation. The benchmark keeps a separate environment-control
test group documenting this exclusion.

## Quality evidence

Recorded snapshots:

```text
commit0 initial core evaluator:
  38 selected/active tests
  0 passed
  37 failed
  1 skipped

completed public evaluator sanity:
  38 selected/active tests
  37 passed
  0 failed
  1 skipped
```

The skipped test is the upstream narrow-build guard. It is not implementation
progress.

## Natural subproblems

### `unicode_version_catalog`

Writable file:

```text
wcwidth/unicode_versions.py
```

Primary evidence:

```text
tests/test_ucslevel.py
```

This layer must return the supported Unicode version strings in ascending
order.

### `width_algorithm`

Writable file:

```text
wcwidth/wcwidth.py
```

Primary evidence:

```text
tests/test_core.py
tests/test_emojis.py
tests/test_table_integrity.py
```

This layer must implement:

- binary interval lookup;
- Unicode version matching;
- single-codepoint width;
- whole-string width;
- control-character behavior;
- zero-width and combining behavior;
- East-Asian wide behavior;
- VS-16 emoji presentation behavior.

## Dependency structure

The main dependency is:

```text
unicode_version_catalog -> width_algorithm
```

`wcwidth.py` imports and consumes `list_versions()` from
`unicode_versions.py`. The consumer must know whether the catalog returns
ascending strings, how versions are formatted, and what the lowest/latest
supported values are.

This makes the task useful for AsyncCodeBench because an asynchronous
`width_agent` can proceed with a stale or incorrect assumption about the
version catalog while the `version_agent` is still working privately.

## Scenarios

The generated scenario record contains:

```text
iterative_single
serial_specialists
async_private
async_message
```

Specialist assignment:

```text
version_agent -> wcwidth/unicode_versions.py
width_agent   -> wcwidth/wcwidth.py
```

## Limitations

- This is a small task. It should not carry the paper alone.
- The version local test group is not perfectly isolated because
  `tests/test_ucslevel.py` also exercises `_wcmatch_version()` in
  `wcwidth.py`.
- The evaluator excludes one packaging metadata test; this must be reported
  transparently.

## Generated assets

```text
src/asynccodebench/dataset/wcwidth_v03.py
scripts/build_wcwidth_v03_data.py
manifests/pilot/v0.3/tasks/commit0_wcwidth.json
manifests/pilot/v0.3/scenarios/commit0_wcwidth.json
manifests/pilot/v0.3/quality/commit0_wcwidth.json
manifests/annotations/commit0_v0.3/wcwidth/
```
