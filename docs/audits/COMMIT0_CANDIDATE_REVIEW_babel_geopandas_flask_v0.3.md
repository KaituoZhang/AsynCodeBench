# Commit0 candidate review: babel, geopandas, flask — v0.3

Date: 2026-06-24  
Protocol: `docs/protocols/COMMIT0_DATA_EXAMPLE_GUIDE_v0.3.md`  
Purpose: continue the Commit0 candidate screen for AsynCodeBench v0.3.

This review only decides task-construction suitability. It is not a model
baseline, not a release annotation, and not a gold-patch analysis.

## Decision summary

| Candidate | Decision | AsynCodeBench fit | Main reason |
| --- | --- | --- | --- |
| `commit0:flask` | promote to conditional construction queue | `partially_parallelizable` | Strong shared-abstraction structure around `sansio.App`, `Flask`, routing/contexts/sessions/JSON. Collection blocker is dependency installation, not task structure. |
| `commit0:babel` | secondary backlog / possible curated subset | `partially_parallelizable` after curation | Message extraction/catalog/frontend has good interface dependencies, but raw stripped state has a syntax-level bootstrap failure in `babel.core` and the full task is broad. |
| `commit0:geopandas` | defer for v0.3 main | too heavy / noisy | Real shared abstraction exists, but raw task depends on pandas extension arrays, shapely, CRS, spatial index, IO, plotting, and geospatial domain behavior. |

Recommended queue update:

```text
keep in formal/near-formal construction queue:
requests, simpy, dulwich, parsel, filesystem_spec, marshmallow, graphene,
imapclient, pexpect, flask

keep as secondary backlog:
babel

defer for v0.3 main:
geopandas
```

## Evidence used

Local repositories:

```text
data/repos/commit0/babel
data/repos/commit0/geopandas
data/repos/commit0/flask
```

Public stripped ref inspected:

```text
origin/commit0_combined
```

Completed/default branches were used only for rough size sanity checks, not as
decomposition evidence.

## `commit0:flask`

### Observed task shape

The stripped task has a compact and meaningful core:

```text
src/flask/sansio/scaffold.py
src/flask/sansio/app.py
src/flask/app.py
src/flask/ctx.py
src/flask/config.py
src/flask/json/provider.py
src/flask/json/tag.py
src/flask/sessions.py
src/flask/templating.py
src/flask/testing.py
src/flask/cli.py
```

The static dependency screen shows a useful shared-abstraction graph:

```text
sansio.scaffold
  -> common route, hook, error-handler, template-registration behavior

sansio.app
  -> config, JSON provider, URL map, blueprint registry, template loader

app.Flask
  -> request dispatch, response conversion, error handling, async adapter,
     testing client, context lifecycle

ctx / sessions / json.provider / templating
  -> runtime state and serialization contracts consumed by Flask
```

This is a natural `Shared Abstraction` task. It is not an arbitrary file split.

### Test and environment observations

Targeted collection in the current local environment fails because Flask's
runtime dependencies are not installed:

```text
ModuleNotFoundError: No module named 'werkzeug'
```

The repository declares these dependencies publicly:

```text
Werkzeug>=3.0.0
Jinja2>=3.1.2
itsdangerous>=2.1.2
click>=8.1.3
blinker>=1.6.2
pytest==8.3.2
```

This is an environment freeze issue, not a structural rejection reason.

Relevant public tests include:

```text
tests/test_basic.py
tests/test_reqctx.py
tests/test_appctx.py
tests/test_json.py
tests/test_session_interface.py
tests/test_templating.py
tests/test_testing.py
tests/test_config.py
tests/test_blueprints.py
tests/test_async.py
```

### Why it fits AsynCodeBench

`flask` is a strong candidate because many agents can independently make
plausible local progress while depending on a shared runtime contract:

```text
route registration and endpoint naming
  -> URL matching/building
  -> request dispatch
  -> context/session lifecycle
  -> response/JSON conversion
```

Likely async failure modes:

```text
Scaffold.add_url_rule records endpoint metadata differently from Flask.dispatch_request expectations
RequestContext push/pop session lifecycle diverges from Flask full_dispatch_request
JSONProvider.response behavior diverges from Flask.make_response handling of dict/list
SessionInterface save/open semantics conflict with request context teardown timing
template/context processors registered in Scaffold are not consumed consistently by Flask/templating
async ensure_sync behavior differs from dispatch expectations
```

These are exactly the kind of textually clean but semantically inconsistent
integration failures that AsynCodeBench should expose.

### Recommendation

Promote `flask` to the construction queue:

```text
task family: Shared Abstraction
working task id: commit0:flask_app_context_dispatch
qualification label: partially_parallelizable
status: candidate_construction_queue
release blockers:
  - freeze dependency environment from public requirements
  - choose a scoped evaluator subset
  - avoid full CLI/dev-server behavior in the first task unless explicitly scoped
```

Suggested subproblem split:

```text
Agent A:
  src/flask/sansio/scaffold.py
  src/flask/sansio/app.py
  route registration, config, URL map, callback registries

Agent B:
  src/flask/app.py
  request dispatch, make_response, error handling, async adapter, test client

Agent C or integration layer:
  src/flask/ctx.py
  src/flask/sessions.py
  src/flask/json/provider.py
  context/session/json contracts used by App and Flask
```

Suggested first evaluator focus:

```text
tests/test_basic.py
tests/test_reqctx.py
tests/test_appctx.py
tests/test_json.py
tests/test_session_interface.py
tests/test_templating.py
tests/test_testing.py
```

Defer initially:

```text
tests/test_cli.py
tests/test_async.py
full blueprint edge cases
dev-server behavior
```

unless the task is intentionally scoped to those features.

## `commit0:babel`

### Observed task shape

The raw task spans both locale formatting and message extraction:

```text
babel/core.py
babel/dates.py
babel/numbers.py
babel/lists.py
babel/localedata.py
babel/plural.py
babel/messages/catalog.py
babel/messages/extract.py
babel/messages/jslexer.py
babel/messages/pofile.py
babel/messages/frontend.py
babel/messages/checkers.py
babel/util.py
```

There is a plausible async-relevant subgraph in the messages subsystem:

```text
messages.jslexer
  -> JavaScript token stream

messages.extract
  -> Python/JS extraction results and keyword/comment semantics

messages.catalog / pofile
  -> Message and Catalog representation, PO serialization

messages.frontend
  -> CLI/config integration over extract/catalog/pofile
```

This could become an `Interface Dependency` task.

### Raw-state problem

Targeted collection currently fails before tests run because the stripped
`babel/core.py` contains a syntax error:

```text
SyntaxError: f-string: expecting '}'
return f'Locale({self.language!r}{', '.join(parameters)})'
```

This is likely a mechanical stripped-state quality problem, not a meaningful
agent task. However, fixing it as an overlay must be handled carefully because
`babel.core.Locale` is also substantive behavior used by many modules.

Additional targeted collection also needs test dependencies such as:

```text
freezegun
```

### Why it is not immediate v0.3 main material

The full raw task is broad and may measure localization domain coverage rather
than async coding coordination:

```text
locale parsing and negotiation
date/time formatting
number/currency formatting
plural rules
CLDR/localedata behavior
message extraction and PO serialization
frontend/config integration
```

The messages subsystem is promising, but the raw repository should not be
included without curation because failure attribution would be noisy.

### Recommendation

Do not promote raw `babel` into the main construction queue yet.

Keep as secondary backlog:

```text
task family: Interface Dependency
possible task id: commit0:babel_messages_extract_catalog
qualification label: partially_parallelizable after curation
status: secondary_backlog
release blockers:
  - decide whether a syntax-only bootstrap overlay is acceptable
  - isolate messages subsystem from broad locale/date/number formatting
  - freeze test dependencies
```

If revisited, scope the first task around:

```text
messages.extract
messages.jslexer
messages.catalog
messages.pofile
messages.frontend
```

and avoid the full `dates/numbers/localedata` surface.

## `commit0:geopandas`

### Observed task shape

The stripped task spans the main GeoPandas stack:

```text
geopandas/_config.py
geopandas/array.py
geopandas/base.py
geopandas/geoseries.py
geopandas/geodataframe.py
geopandas/sindex.py
geopandas/tools/overlay.py
geopandas/tools/sjoin.py
geopandas/tools/clip.py
geopandas/io/file.py
geopandas/io/arrow.py
geopandas/plotting.py
```

The dependency graph has real shared abstraction:

```text
GeometryArray
  -> GeoSeries
  -> GeoDataFrame
  -> tools: overlay/sjoin/clip
  -> IO and plotting
```

### Raw-state problem

Targeted collection fails during package import:

```text
NameError: name '_validate_display_precision' is not defined
```

This comes from `geopandas/_config.py`, before tests reach geometry behavior.

### Why it is weak for v0.3

Even after a config bootstrap, the full task depends on a heavy domain stack:

```text
pandas extension arrays
numpy object-array semantics
shapely geometry operations
pyproj / CRS behavior
spatial index behavior
file/arrow IO
plotting
geospatial topology edge cases
```

This is not impossible, but it is a poor fit for the first AsynCodeBench wave
because failures would be hard to attribute cleanly. They may reflect geospatial
domain knowledge or dependency behavior rather than stale multi-agent work.

### Recommendation

Defer `geopandas` for v0.3 main:

```text
task family: Shared Abstraction, but too heavy
possible task id: commit0:geopandas_geometryarray_geoseries_subset
qualification label: partially_parallelizable only after heavy curation
status: defer_v0.3_main
```

If revisited, the only reasonable subset is:

```text
GeometryArray construction/conversion
  -> GeoSeries/GeoDataFrame geometry-column semantics
```

Do not include spatial join, overlay, IO, CRS transformation, and plotting in
the first release task.

## Next candidates to review

Continuing the current repository order, the next unreviewed group is:

```text
pyquery
python-rsa
pycryptodome
```

