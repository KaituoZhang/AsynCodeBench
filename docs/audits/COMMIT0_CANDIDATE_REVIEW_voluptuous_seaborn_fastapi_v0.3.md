# Commit0 Candidate Review: voluptuous / seaborn / fastapi

Date: 2026-06-24  
Protocol: AsyncCodeBench v0.3, following `docs/protocols/COMMIT0_DATA_EXAMPLE_GUIDE_v0.3.md`

This audit reviews the next three locally available Commit0 repositories in config order:

- `commit0:voluptuous`
- `commit0:seaborn`
- `commit0:fastapi`

The goal is not to solve the repositories. The goal is to decide whether each repository contains a natural coding task that can support AsyncCodeBench: strong single-agent coding feasibility, but meaningful degradation under asynchronous multi-agent execution because agents act on stale teammate work, stale interfaces, or stale shared abstractions.

## Decision summary

| Repository | Decision | AsyncCodeBench fit | Main reason |
|---|---:|---:|---|
| `fastapi` | Promote to candidate construction queue | `partially_parallelizable` | Strong natural dependency chain across parameter declarations, routing/dependency handling, JSON encoding, and OpenAPI generation. Good stale-interface and shared-abstraction risk. |
| `seaborn` | Keep as secondary backlog | `partially_parallelizable` after narrow curation | The objects API has a real pipeline across data, plot spec, scales, stats, marks, and rendering, but the task is broad and visualization-heavy. It should not be prioritized before simpler coding-agent tasks. |
| `voluptuous` | Defer for v0.3 main set | Mostly `effectively_serial` | The repository centers on one schema compiler. There are dependent validator/error/humanize modules, but too much of the task bottlenecks through a single core abstraction. |

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
```

Recommended secondary backlog:

```text
babel
seaborn
```

Recommended defer/reject for v0.3 main set:

```text
geopandas
voluptuous
```

## `commit0:fastapi`

### Observed task shape

The stripped tree contains many implementation gaps in core FastAPI modules, including:

- `fastapi/params.py`
- `fastapi/param_functions.py`
- `fastapi/routing.py`
- `fastapi/applications.py`
- `fastapi/encoders.py`
- `fastapi/openapi/utils.py`
- `fastapi/openapi/models.py`
- `fastapi/security/api_key.py`
- `fastapi/security/oauth2.py`
- `fastapi/_compat.py`

The test suite is broad. Collection in the current local environment is blocked by missing dependencies such as `dirty_equals` and `starlette`, which is an environment-freezing issue rather than evidence that the task is unsuitable.

### Why it fits AsyncCodeBench

FastAPI is a strong candidate because its implementation naturally has multiple interacting layers:

1. Parameter declarations define the public API surface.
2. Routing consumes those declarations to build runtime route behavior.
3. Dependency/security handling adds another interface layer over request-time behavior.
4. JSON encoding and OpenAPI generation consume the same metadata from a different direction.

This creates the kind of stale-work risk AsyncCodeBench is meant to test:

- One agent may implement `Query`, `Path`, `Body`, `Depends`, or `Security` with one metadata format.
- Another agent may implement routing based on a different assumed metadata format.
- A third agent may implement OpenAPI generation based on stale assumptions from either side.
- The merged repository may have no textual conflict but fail hidden tests because the shared abstraction is semantically inconsistent.

This is a better async benchmark shape than a repository where agents merely edit independent files.

### Suggested task construction

Use a scoped FastAPI task rather than the full repository.

Recommended subproblem split:

- Agent A: parameter declaration layer
  - `params.py`
  - `param_functions.py`
  - selected `_compat.py` helpers
- Agent B: routing/dependency runtime layer
  - `routing.py`
  - selected dependency/security integration points
- Agent C: schema/serialization layer
  - `encoders.py`
  - `openapi/utils.py`
  - selected `applications.py` OpenAPI integration

Recommended evaluator focus:

- path/query/body parameter behavior
- parameter representation tests
- dependency override behavior
- JSON encoder behavior
- OpenAPI schema generation for the scoped features

Avoid using the entire FastAPI suite as the first benchmark instance. Full FastAPI includes many docs, security, compatibility, and response-model edge cases that could make the task too broad and noisy for v0.3.

### Recommendation

Promote `commit0:fastapi` to the candidate construction queue as a scoped task, likely named:

```text
commit0:fastapi_params_routing_openapi
```

This should be treated as a high-value candidate, but only after dependency freezing and evaluator scoping.

## `commit0:seaborn`

### Observed task shape

The stripped tree contains substantial implementation gaps in the objects/plotting stack, including:

- `seaborn/_core/plot.py`
- `seaborn/_core/data.py`
- `seaborn/_core/properties.py`
- `seaborn/_core/scales.py`
- `seaborn/_core/moves.py`
- `seaborn/_marks/base.py`
- `seaborn/_stats/base.py`
- `seaborn/_stats/counting.py`
- `seaborn/_stats/density.py`
- higher-level plotting modules such as `axisgrid.py`, `categorical.py`, `distributions.py`, and `regression.py`

Local test collection for selected tests is currently blocked by missing visualization dependencies such as `matplotlib`. That should be handled by an environment lock if this candidate is used.

### Why it partially fits

Seaborn has a real pipeline:

```text
data normalization
-> plot specification
-> scales/properties
-> statistical transforms
-> marks
-> rendering
```

This creates shared-abstraction risk. For example:

- One agent may define how variables are represented in `PlotData`.
- Another agent may implement scales or properties assuming a different variable schema.
- Another agent may implement marks or stats assuming different normalized data columns.

That is a legitimate AsyncCodeBench pattern.

### Why it should not be prioritized

The task is broad and domain-heavy. Failures may reflect plotting-library semantics, visual behavior, pandas/matplotlib/numpy compatibility, or test-environment issues rather than clean stale-interface failures.

For v0.3, this is less attractive than repositories where the async failure mode is easier to explain and evaluate.

### Recommendation

Keep `commit0:seaborn` in the secondary backlog. If used later, scope it narrowly around the objects API:

```text
commit0:seaborn_objects_pipeline_subset
```

Suggested subproblem split:

- Agent A: `PlotData` and variable normalization.
- Agent B: `Plot`, layer construction, and scale/property resolution.
- Agent C: marks/stats integration.

Do not use full Seaborn as a first-wave v0.3 task.

## `commit0:voluptuous`

### Observed task shape

The stripped tree has implementation gaps concentrated in:

- `voluptuous/schema_builder.py`
- `voluptuous/validators.py`
- `voluptuous/error.py`
- `voluptuous/humanize.py`
- `voluptuous/util.py`

Local test collection fails immediately because tests import `raises` from `voluptuous.schema_builder`, but that public helper is missing in the stripped implementation.

The natural dependency chain is:

```text
error model
-> schema compiler and markers
-> validators
-> humanized errors / utilities
```

### Why it is weak for AsyncCodeBench

The task is mostly centered on the schema compiler. The validators and humanized error reporting depend heavily on the same core semantics.

This makes it a poor main AsyncCodeBench candidate:

- The most important decisions are concentrated in one file/module.
- A strong implementation likely needs one coherent schema model before other parts can be completed.
- Splitting the work risks making an artificial multi-agent task rather than revealing natural async coordination failures.

It could be used as a small serial control task, but it should not consume one of the main v0.3 benchmark slots.

### Recommendation

Defer `commit0:voluptuous` for the v0.3 main set.

Possible label:

```text
effectively_serial
```

If revisited later, it should be treated as a serial-control or small-interface task, not as a primary async multi-agent benchmark instance.

## Next repositories to review

After this audit, the next unreviewed repositories in the current Commit0 config order are:

```text
click
python-rsa
statsmodels
```

