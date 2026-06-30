# Commit0 Candidate Review: python-prompt-toolkit and pydantic

Date: 2026-06-24

This note reviews whether `commit0:python-prompt-toolkit` and
`commit0:pydantic` should enter the AsyncCodeBench v0.3 candidate pool. The
decision standard here is candidate admission, not release readiness.

## Decision Summary

| Repository | Candidate-pool decision | Current status | Count toward the current 20-task target? |
| --- | --- | --- | --- |
| `commit0:python-prompt-toolkit` | Admit | confirmed structural candidate; evaluator signal still needs a real dependency environment | Not yet |
| `commit0:pydantic` | Admit as heavy candidate | high-value but environment-blocked; requires exact dependency freeze | Not yet |

Both repositories are worth keeping in the candidate pool. Neither should be
counted as a finalized AsyncCodeBench v0.3 task until we confirm a stable,
offline, non-environment failure signal on a properly frozen evaluator.

## `commit0:python-prompt-toolkit`

### Screening evidence

Automatic screening:

```text
pytest_status: collection_or_import_error
curation_status: weak_or_unclear
implementation_units: 50
unit_dependencies: 95
incomplete_marker_total: 176
```

High-signal modules:

```text
src/prompt_toolkit/document.py
src/prompt_toolkit/buffer.py
src/prompt_toolkit/completion/base.py
src/prompt_toolkit/key_binding/key_bindings.py
src/prompt_toolkit/key_binding/key_processor.py
src/prompt_toolkit/application/application.py
src/prompt_toolkit/renderer.py
src/prompt_toolkit/output/vt100.py
src/prompt_toolkit/styles/style.py
```

Natural dependency patterns:

- `Buffer` depends on `Document`, completion, validation, history, and utility
  behavior.
- `Application` depends on buffer, layout, key binding, renderer, input, output,
  and utility behavior.
- `KeyProcessor` depends on key binding registries and the current application.
- Rendering/output code depends on width calculation and formatted text.

These are good candidates for both AsyncCodeBench task types:

- Interface Dependency
- Shared State / Shared Abstraction

### Environment / bootstrap findings

The original collection error was mostly not a code failure:

```text
ModuleNotFoundError: No module named 'prompt_toolkit'
```

This is fixed by evaluating with:

```text
PYTHONPATH=src
```

The next blocker is a normal runtime dependency:

```text
ModuleNotFoundError: No module named 'wcwidth'
```

Important: using AsyncCodeBench's local `commit0/wcwidth` repository as this
dependency is invalid for prompt-toolkit evaluation, because that repository is
itself a benchmark skeleton. It caused false failures such as:

```text
TypeError: '>' not supported between instances of 'NoneType' and 'int'
```

Using a normal `wcwidth` implementation or equivalent dependency behavior,
representative prompt-toolkit tests passed:

```text
tests/test_cli.py tests/test_shortcuts.py tests/test_widgets.py
38 passed
```

A broader stable subset also passed:

```text
tests/test_buffer.py: 9 passed
tests/test_completion.py: 18 passed
tests/test_document.py: 11 passed
tests/test_filter.py: 11 passed
tests/test_formatted_text.py: 13 passed
tests/test_inputstream.py: 11 passed
tests/test_key_binding.py: 6 passed
tests/test_layout.py: 2 passed
tests/test_print_formatted_text.py: 4 passed
tests/test_regular_languages.py: 4 passed
tests/test_style.py: 5 passed
tests/test_style_transformation.py: 1 passed
tests/test_utils.py: 1 passed
tests/test_vt100_output.py: 1 passed
tests/test_yank_nth_arg.py: 10 passed
```

Some files timed out or are not yet stable evaluator targets:

```text
tests/test_async_generator.py: timeout
tests/test_history.py: timeout
full tests/: timeout
```

These need targeted review before use.

### Candidate decision

Admit `commit0:python-prompt-toolkit` to the candidate pool, but do not count it
as a finalized v0.3 task yet.

Recommended candidate directions:

1. `prompt_toolkit_document_buffer`
   - Likely units: `document.py`, `buffer.py`, `completion/base.py`,
     `history.py`.
   - Async risk: a consumer agent changes buffer editing behavior while another
     assumes stale document cursor/line semantics.

2. `prompt_toolkit_key_binding_processor`
   - Likely units: `key_binding/key_bindings.py`,
     `key_binding/key_processor.py`, `application/application.py`.
   - Async risk: key sequence resolution, timeout behavior, and application
     state assumptions diverge across agents.

3. `prompt_toolkit_render_width`
   - Likely units: `utils.py`, `layout/screen.py`, `renderer.py`,
     `output/vt100.py`.
   - Requires a real `wcwidth` dependency, not the local benchmark skeleton.

Required next step before formal task construction:

```text
Freeze a normal prompt-toolkit test environment with a real wcwidth dependency,
then find a stable local evaluator subset that fails for code reasons rather
than dependency or timeout reasons.
```

## `commit0:pydantic`

### Screening evidence

Automatic screening:

```text
pytest_status: collection_or_import_error
curation_status: weak_or_unclear
implementation_units: 50
unit_dependencies: 163
incomplete_marker_total: 139
```

High-signal modules:

```text
pydantic/main.py
pydantic/fields.py
pydantic/config.py
pydantic/_internal/_generate_schema.py
pydantic/_internal/_fields.py
pydantic/_internal/_dataclasses.py
pydantic/json_schema.py
pydantic/functional_validators.py
pydantic/functional_serializers.py
pydantic/types.py
pydantic/v1/*
```

Natural dependency patterns:

- Model fields, config, validators, serializers, and schema generation share
  global behavioral contracts.
- JSON schema generation depends on core schema generation and field metadata.
- Dataclass and BaseModel behavior share configuration and field construction
  paths.
- v1 compatibility layers interact with v2 internals and public APIs.

These are strong candidates for AsyncCodeBench's Shared State / Shared
Abstraction category. They also provide Interface Dependency cases between
schema producers and API consumers.

### Environment / bootstrap findings

Current collection is environment-blocked:

```text
ModuleNotFoundError: No module named 'jsonschema'
```

Additional test dependencies missing from the isolated AsyncCodeBench
environment include:

```text
dirty_equals
pytest-mock
pytest-benchmark
```

More importantly, the local environment has an incompatible `pydantic-core`
relative to this repository:

```text
project requirement: pydantic-core==2.24.0
observed issue: cannot import name 'validate_core_schema' from pydantic_core
```

This means we cannot treat current test failures as benchmark evidence. The
repository needs an exact dependency freeze before evaluator conclusions are
valid.

### Candidate decision

Admit `commit0:pydantic` as a high-value heavy candidate, but do not count it as
a finalized v0.3 task yet.

Recommended candidate directions:

1. `pydantic_model_fields_config`
   - Likely units: `main.py`, `fields.py`, `_internal/_fields.py`,
     `_internal/_config.py`.
   - Async risk: one agent changes field/config interpretation while another
     assumes stale model construction semantics.

2. `pydantic_schema_generation`
   - Likely units: `_internal/_generate_schema.py`, `json_schema.py`,
     `functional_validators.py`, `functional_serializers.py`.
   - Async risk: schema producer and JSON-schema consumer disagree on metadata,
     validators, or serialization contracts.

3. `pydantic_dataclasses`
   - Likely units: `dataclasses.py`, `_internal/_dataclasses.py`,
     `_internal/_generate_schema.py`, `fields.py`.
   - Async risk: dataclass construction and schema generation evolve
     independently and conflict after merge.

Required next step before formal task construction:

```text
Create a pydantic-specific evaluator environment with the repository-pinned
pydantic-core and test dependencies. Only after that should we select stable
offline tests and decide whether the task has valid public failure signal.
```

## Practical Recommendation

For near-term dataset growth:

1. Prioritize already-clean candidates such as `requests` and
   `filesystem_spec`.
2. Keep `python-prompt-toolkit` in the next wave because its bootstrap is light
   and its module graph is task-friendly.
3. Keep `pydantic` as a valuable but heavier candidate. It should be handled
   after the pipeline for dependency-specific evaluator environments is more
   stable.

