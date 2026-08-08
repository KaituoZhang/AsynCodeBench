# Commit0 Candidate Review: tornado / imbalanced-learn / python-progressbar

Date: 2026-06-24  
Protocol: AsynCodeBench v0.3, following `docs/protocols/COMMIT0_DATA_EXAMPLE_GUIDE_v0.3.md`

This audit reviews the next Commit0 repositories after the previous candidate-screening groups:

- `commit0:tornado`
- `commit0:imbalanced-learn`
- `commit0:python-progressbar`

The selection standard is strict: a repository should expose a natural incomplete coding task from public Commit0 evidence, and that task should have meaningful asynchronous multi-agent risk through stale interfaces or stale shared abstractions.

## Decision summary

| Repository | Decision | AsynCodeBench fit | Main reason |
|---|---:|---:|---|
| `tornado` | Backlog / conditional candidate | Structurally strong but too broad for current v0.3 construction | Excellent async/event-loop architecture, but many raw missing markers are overloads, protocols, or abstract methods; selected core tests collect, and full task risk is high due event-loop/network breadth. |
| `imbalanced-learn` | Reject/defer for v0.3 main set | Weak for current benchmark | Strong pipeline concept, but heavily coupled to `scikit-learn` internals and numerical/statistical behavior; local collection is dominated by missing dependency/version noise rather than a clean Commit0 gap. |
| `python-progressbar` | Add to candidate pool, lower priority than existing main queue | Moderate to good | Compact progress-rendering pipeline with natural shared state between `ProgressBar.data()`, widgets, smoothing/ETA logic, stream wrapping, and terminal behavior. |

Recommended main queue update:

```text
requests
simpy
dulwich
parsel
filesystem_spec
marshmallow
graphene
imapclient
pexpect
flask
fastapi
python-rsa
python-progressbar
```

Recommended backlog update:

```text
babel
seaborn
statsmodels
moviepy
loguru
cookiecutter
tornado
```

Recommended defer/reject for v0.3 main set:

```text
geopandas
voluptuous
click
more-itertools
attrs
mimesis
imbalanced-learn
```

## `commit0:tornado`

### Observed task shape

The automated screening reported:

- collection status: `collection_or_import_error`;
- many implicated modules;
- many dependency edges;
- many visible test targets.

Manual inspection shows a real high-level architecture:

```text
ioloop / asyncio integration
-> iostream / tcpserver
-> http1connection / httputil
-> httpserver / web / websocket
-> tests for request parsing, stream behavior, handlers, and websocket flow
```

Targeted collection for the core modules succeeds in the current environment:

```text
498 tests collected
```

The likely useful surface includes:

- `tornado/ioloop.py`
- `tornado/iostream.py`
- `tornado/http1connection.py`
- `tornado/httputil.py`
- `tornado/httpserver.py`
- `tornado/web.py`
- `tornado/websocket.py`

### Why it is structurally attractive

`tornado` has a natural asynchronous systems structure. A plausible AsynCodeBench task could split agents across:

- event-loop lifecycle and timeouts;
- stream read/write buffering;
- HTTP parsing and request metadata;
- web request handler behavior;
- websocket upgrade and message flow.

Natural stale-work failures would be meaningful:

- stream code changes callback/future semantics while HTTP code assumes the old contract;
- header parsing changes case-normalization or multi-value behavior while web handlers consume stale semantics;
- timeout/cancellation semantics change in `IOLoop`, but stream/server code continues with stale assumptions;
- websocket framing assumes stale stream close/error behavior.

This is a strong match to the benchmark story at the conceptual level.

### Why it should not enter the main set now

The repository is too large and risky for the current v0.3 construction pass.

Important raw markers are not necessarily missing implementation:

- many `pass` bodies are overload stubs;
- many classes are protocols or abstract bases;
- many `NotImplemented` returns are normal Python binary-operation or abstract-method behavior;
- the core selected tests collect, so the initial screening error is not enough evidence of a clean incomplete task.

The event-loop/network test surface also increases risk:

- flaky timing behavior;
- OS/event-loop differences;
- hidden dependency on network resources or low-level socket behavior;
- large patch surface that may make single-agent and async-agent results hard to interpret.

### Recommendation

Keep `commit0:tornado` as backlog or a conditional high-value candidate, not an immediate v0.3 main task.

Possible label:

```text
backlog_structurally_strong
```

If selected later, it should be heavily scoped to one narrow pipeline, for example:

```text
ioloop_timeout_and_stream_read_contract
```

or:

```text
httputil_header_contract_shared_by_http_and_web
```

## `commit0:imbalanced-learn`

### Observed task shape

The automated screening reported broad collection/import failure and implicated modules such as:

- `imblearn/base.py`
- `imblearn/pipeline.py`
- `imblearn/ensemble/_bagging.py`
- `imblearn/ensemble/_easy_ensemble.py`
- `imblearn/metrics/_classification.py`
- `imblearn/utils/_metadata_requests.py`
- `imblearn/utils/_param_validation.py`
- `imblearn/utils/_validation.py`

The visible collection blocker is:

```text
ModuleNotFoundError: No module named 'sklearn'
```

Some apparent parser problems in `base.py` and `pipeline.py` are caused by encoding/BOM handling in the screening script, not necessarily by broken repository source. The substantive issue is that the repository depends deeply on `scikit-learn`.

### Why it is theoretically attractive

There is a plausible shared-abstraction task:

```text
sampler base classes
-> fit_resample contract
-> pipeline composition
-> metadata routing
-> estimator checks / validation
```

Async stale-work failures would be possible:

- Agent A changes sampler output shape or metadata contract;
- Agent B implements pipeline composition using stale sampler assumptions;
- Agent C updates estimator validation against a different interpretation of the interface.

### Why it should not be selected now

For AsynCodeBench v0.3, this is not a clean candidate.

Main issues:

- correctness depends on a pinned `scikit-learn` version;
- failures may reflect dependency/API mismatch rather than model coding ability;
- many tests are numerical/statistical and may be slow or brittle;
- the natural task is more about conforming to external sklearn contracts than coordinating a self-contained repository abstraction;
- constructing a clean answer-free benchmark item would likely require too much dependency engineering.

### Recommendation

Reject/defer `commit0:imbalanced-learn` for the v0.3 main set.

Possible label:

```text
reject_or_defer_external_dependency_heavy
```

It can be reconsidered only if we intentionally add a “third-party framework integration” category later.

## `commit0:python-progressbar`

### Observed task shape

The automated screening reported collection/import error, but the direct blocker is a missing test dependency:

```text
ModuleNotFoundError: No module named 'freezegun'
```

The repository parses correctly under the AsynCodeBench Python 3.10 environment. Earlier syntax errors from `:=` were caused by running `py_compile` with an older default Python interpreter, not by broken source.

Relevant source modules include:

- `progressbar/bar.py`
- `progressbar/widgets.py`
- `progressbar/algorithms.py`
- `progressbar/utils.py`
- `progressbar/env.py`
- `progressbar/terminal/base.py`
- `progressbar/terminal/stream.py`
- `progressbar/terminal/os_specific/__init__.py`

Visible tests cover:

- progress-bar lifecycle;
- iterator behavior;
- widget formatting;
- ETA/timer/speed logic;
- stream wrapping and flushing;
- terminal behavior;
- colors;
- multibar behavior;
- unknown-length progress bars;
- data transfer bars.

### Why it fits AsynCodeBench

This repository has a compact but real shared-state pipeline:

```text
ProgressBar lifecycle and state
-> ProgressBar.data() snapshot
-> widgets consume snapshot keys and timing values
-> algorithms smooth speed/ETA values
-> terminal/stream layers render and flush output
```

This can naturally instantiate both target categories from v0.3:

1. Interface Dependency

   Agent A implements or changes the `ProgressBar` state/data contract.  
   Agent B implements widgets or ETA logic using stale assumptions about available keys, value semantics, or time fields.

2. Shared State / Shared Abstraction

   Multiple agents touch the shared progress state model: `value`, `previous_value`, `start_time`, `last_update_time`, `end_time`, `variables`, `percentage`, and unknown-length behavior.  
   Independently plausible patches can merge into semantic disagreement.

Example stale-work failures:

- `ProgressBar.data()` exposes `percentage=None` for unknown length, while a widget assumes a numeric value;
- `previous_value` or `updates` semantics change, but speed/ETA widgets compute deltas using stale assumptions;
- stream flushing expects one update/finish lifecycle, while bar lifecycle changes when `_started`, `_finished`, or `end_time` is set;
- terminal width/color rendering assumes stale output length behavior from widget formatting.

These failures are not just git conflicts. They are semantic interface and shared-state mismatches, which matches the AsynCodeBench target.

### Why it should be lower priority than the current main queue

`python-progressbar` is useful but not as strong as `cachetools`, `tinydb`, `portalocker`, or some of the current main candidates.

Limitations:

- it is a UI/terminal-rendering package, so output formatting can become brittle;
- some tests depend on time freezing or terminal behavior;
- task scope must avoid becoming a pure formatting exercise;
- the repository is compact, so the multi-agent split may be shallower than larger libraries.

### Recommended benchmark task shape

Suggested task id:

```text
commit0_python_progressbar_progress_state_widgets
```

Suggested agent split:

- Agent A: `ProgressBar` lifecycle and `data()` contract in `progressbar/bar.py`;
- Agent B: widget behavior in `progressbar/widgets.py`, especially ETA, percentage, bar rendering, and unknown-length behavior;
- Agent C: stream/terminal integration in `progressbar/utils.py`, `progressbar/terminal/base.py`, and `progressbar/terminal/stream.py`.

Required curation notes:

- pin Python to `>=3.10` or at least `>=3.8`, because the source uses walrus operator syntax;
- install `freezegun` for the visible test suite if this task is materialized;
- scope hidden tests to semantic consistency across progress state and widgets, not only exact terminal formatting;
- avoid using OS-specific terminal behavior as the main correctness signal.

### Recommendation

Add `commit0:python-progressbar` to the candidate pool as a lower-priority v0.3 task.

Possible label:

```text
partially_parallelizable
```

