# Commit0 Candidate Review: dulwich and scrapy

Date: 2026-06-24

This note reviews whether `commit0:dulwich` and `commit0:scrapy` should enter
the AsyncCodeBench v0.3 candidate pool. The decision standard here is candidate
admission, not release readiness.

## Decision Summary

| Repository | Candidate-pool decision | Current status | Count toward the current 20-task target? |
| --- | --- | --- | --- |
| `commit0:dulwich` | Admit | strong candidate; valid local failure signal found | Yes, after task construction |
| `commit0:scrapy` | Conditional admit | high-value but dependency-heavy; evaluator not confirmed | Not yet |

## `commit0:dulwich`

### Screening evidence

Automatic screening:

```text
pytest_status: collection_or_import_error
curation_status: weak_or_unclear
implementation_units: 28
unit_dependencies: 95
incomplete_marker_total: 256
```

High-signal modules:

```text
dulwich/object_store.py
dulwich/repo.py
dulwich/pack.py
dulwich/client.py
dulwich/porcelain.py
dulwich/refs.py
dulwich/server.py
dulwich/config.py
dulwich/objectspec.py
dulwich/objects.py
dulwich/index.py
dulwich/diff_tree.py
dulwich/walk.py
```

Natural dependency patterns:

- `repo.py` consumes config, refs, object store, index, objects, and pack
  behavior.
- `porcelain.py` is a high-level API consumer over repo/client/index/objectspec.
- `object_store.py`, `pack.py`, and `objects.py` define shared Git object
  contracts.
- `refs.py` and `config.py` are shared state abstractions used by repo
  creation and mutation flows.

These patterns fit both AsyncCodeBench task categories:

- Interface Dependency
- Shared State / Shared Abstraction

### Environment / bootstrap findings

Full collection is blocked only by edge dependency tests:

```text
fuzzing/fuzz-targets/test_utils.py: missing atheris
tests/contrib/test_swift_smoke.py: missing gevent
```

These can be excluded in an answer-free evaluator subset. The main test suite
has substantial collection coverage:

```text
1578 tests collected before the edge dependency errors
```

Representative local subset:

```text
tests/test_object_store.py
tests/test_pack.py
tests/test_refs.py
tests/test_config.py
tests/test_objectspec.py
tests/test_objects.py
tests/test_diff_tree.py
tests/test_walk.py
```

Result:

```text
526 passed
2 failed
11 skipped
1 xfailed
```

The two failures are consistent and code-relevant:

```text
tests/test_refs.py::DiskRefsContainerTests::test_add_if_new_symbolic
tests/test_config.py::StackedConfigTests::test_default_backends
```

Both fail because the test base class intentionally sets:

```text
HOME=/nonexistent
GIT_CONFIG_NOSYSTEM=1
```

`StackedConfig.default_backends()` then tries to read:

```text
/nonexistent/.gitconfig
```

and raises `PermissionError`, whereas the intended behavior is to ignore an
unavailable global config backend. This is a valid local failure signal, not a
network/resource issue.

### Candidate decision

Admit `commit0:dulwich` as a strong AsyncCodeBench candidate. It can count
toward the 20-task target after task construction and quality records are
created.

Recommended candidate directions:

1. `dulwich_config_repo_refs`
   - Likely units: `config.py`, `repo.py`, `refs.py`.
   - Evaluator seed: repository creation and config-default behavior under
     unavailable global config.
   - Async risk: config producer behavior changes while repo/refs consumers
     assume stale exception semantics.

2. `dulwich_object_store_pack`
   - Likely units: `object_store.py`, `pack.py`, `objects.py`.
   - Async risk: object storage and pack iteration contracts diverge.

3. `dulwich_porcelain_repo_client`
   - Likely units: `porcelain.py`, `repo.py`, `client.py`, `objectspec.py`.
   - Async risk: high-level porcelain API assumes stale lower-level repo/client
     behavior.

Required next step before formal construction:

```text
Build a curated evaluator subset that excludes fuzzing and contrib/swift smoke
tests, then construct an answer-free task around config/repo/refs or
object-store/pack contracts.
```

## `commit0:scrapy`

### Screening evidence

Automatic screening:

```text
pytest_status: collection_or_import_error
curation_status: weak_or_unclear
implementation_units: 43
unit_dependencies: 76
incomplete_marker_total: 97
```

High-signal modules:

```text
scrapy/core/scheduler.py
scrapy/dupefilters.py
scrapy/statscollectors.py
scrapy/squeues.py
scrapy/exporters.py
scrapy/extensions/feedexport.py
scrapy/pipelines/media.py
scrapy/utils/defer.py
scrapy/core/scraper.py
scrapy/downloadermiddlewares/httpcompression.py
scrapy/http/cookies.py
```

Natural dependency patterns:

- Scheduler behavior combines queues, duplicate filtering, stats, crawler
  settings, and request serialization.
- Feed export combines exporters, storage backends, crawler settings, signals,
  and stats.
- Twisted/asyncio utilities bridge Deferreds, coroutines, and event-loop
  behavior.
- Downloader and spider middleware depend on shared request/response and stats
  contracts.

These are conceptually strong AsyncCodeBench targets, especially for Shared
State / Shared Abstraction and delayed/asynchronous behavior.

### Environment / bootstrap findings

Current collection is blocked at `conftest.py` by a missing core dependency:

```text
ModuleNotFoundError: No module named 'twisted'
```

The current AsyncCodeBench environment is missing most Scrapy runtime
dependencies:

```text
twisted
cryptography
cssselect
itemloaders
parsel
OpenSSL
queuelib
service_identity
w3lib
zope.interface
protego
itemadapter
tldextract
lxml
defusedxml
```

This means we cannot yet confirm stable local evaluator failures. Any Scrapy
judgment is currently structural rather than empirical.

### Candidate decision

Conditionally admit `commit0:scrapy` to the backlog, but do not count it toward
the current 20-task target until a dependency-frozen evaluator confirms stable,
offline failure signal.

Recommended candidate directions if dependency environment is frozen:

1. `scrapy_scheduler_dupefilter_stats`
   - Likely units: `core/scheduler.py`, `dupefilters.py`,
     `statscollectors.py`, `squeues.py`.
   - Async risk: scheduler and dupefilter agents disagree on stats and request
     queue contracts.

2. `scrapy_defer_asyncio_bridge`
   - Likely units: `utils/defer.py`, `utils/reactor.py`,
     async generator utilities.
   - Async risk: Deferred/Future conversion semantics diverge across async
     consumers.

3. `scrapy_feedexport_stats`
   - Likely units: `extensions/feedexport.py`, `exporters.py`,
     `statscollectors.py`.
   - Async risk: feed export storage state and stats accounting diverge.

Required next step before formal construction:

```text
Create a Scrapy-specific evaluator environment with official runtime
dependencies, then run targeted offline tests such as scheduler, dupefilter,
stats, queues, and defer utilities. Only then decide whether Scrapy should count
as a finalized v0.3 task.
```

## Practical Recommendation

For near-term dataset growth:

1. Promote `commit0:dulwich` into the formal construction queue.
2. Keep `commit0:scrapy` as a high-value but dependency-heavy backlog item.
3. Do not start Scrapy construction before the dependency environment is frozen;
   otherwise engineering time will be spent on environment repair rather than
   benchmark task design.

