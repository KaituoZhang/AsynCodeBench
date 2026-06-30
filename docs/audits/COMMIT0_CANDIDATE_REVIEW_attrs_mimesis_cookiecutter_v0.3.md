# Commit0 Candidate Review: attrs / mimesis / cookiecutter

Date: 2026-06-24  
Protocol: AsyncCodeBench v0.3, following `docs/protocols/COMMIT0_DATA_EXAMPLE_GUIDE_v0.3.md`

This audit reviews the next Commit0 repositories after `more-itertools / moviepy / loguru`:

- `commit0:attrs`
- `commit0:mimesis`
- `commit0:cookiecutter`

The selection standard is strict: a repository should expose a natural incomplete coding task from public Commit0 evidence, and that task should have meaningful asynchronous multi-agent risk through stale interfaces or stale shared abstractions.

## Decision summary

| Repository | Decision | AsyncCodeBench fit | Main reason |
|---|---:|---:|---|
| `attrs` | Reject/defer for v0.3 main set | Weak | Collection is blocked only by missing test dependency `hypothesis`; precise source inspection finds no substantive raw missing implementation. |
| `mimesis` | Reject/defer for v0.3 main set | Weak | The screened unit is basically `payment.py`, which already passes its visible tests locally. The task is too narrow and not naturally async. |
| `cookiecutter` | Backlog only | Structurally strong, but not a natural Commit0 gap | The pipeline is excellent for async decomposition, but source inspection shows a mostly complete implementation with no clear raw missing-code surface. |

Recommended main queue remains unchanged:

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
```

Recommended backlog update:

```text
babel
seaborn
statsmodels
moviepy
loguru
cookiecutter
```

Recommended defer/reject for v0.3 main set:

```text
geopandas
voluptuous
click
more-itertools
attrs
mimesis
```

## `commit0:attrs`

### Observed task shape

The screening implicated a small set of modules:

- `src/attr/__init__.py`
- `src/attr/_make.py`
- `src/attr/_version_info.py`
- `src/attr/validators.py`

The local collection blocker is missing test dependency:

```text
ModuleNotFoundError: No module named 'hypothesis'
```

Precision source inspection found only one truly empty source class:

```text
src/attr/__init__.py: AttrsInstance(Protocol): pass
```

That is a typing/protocol declaration, not a missing implementation.

Other apparent markers are normal implementation patterns:

- generated class body strings containing `pass`;
- comparison methods returning `NotImplemented`;
- `VersionInfo` comparison helpers using `NotImplementedError` internally to return `NotImplemented`;
- validators intentionally suppressing exceptions to invert validity.

### Why it should not be selected

`attrs` has strong shared abstractions in principle: class generation, validators, converters, dunder generation, and version metadata. But the local Commit0 state does not expose a clean incomplete task.

To use this repository, we would need to invent missing-code regions or hidden-test difficulty. That would be outside the current v0.3 curation target.

### Recommendation

Reject/defer `commit0:attrs` for the v0.3 main set.

Possible label:

```text
reject_or_defer
```

## `commit0:mimesis`

### Observed task shape

The screening implicated only one implementation unit:

- `mimesis/providers/payment.py`

The visible tests cover payment-provider behavior:

- Bitcoin and Ethereum-looking addresses;
- CVV and CID generation;
- credit card number generation;
- expiration dates;
- PayPal addresses;
- owner records;
- seeded deterministic behavior.

With no user site packages and pytest plugin autoload disabled, the selected payment tests pass:

```text
22 passed
```

The broader selected schema/payment collection also succeeds when optional factory-boy plugin tests are not included.

### Why it should not be selected

This is too narrow for AsyncCodeBench:

- The implicated source surface is basically one provider module.
- The visible payment task already passes.
- There is no strong natural split between multiple agents.
- The broader `mimesis` schema system is real, but the screened raw gap does not point there as an incomplete task.

`mimesis` could be useful for a manually constructed provider/schema task, but it is not a good natural Commit0 candidate.

### Recommendation

Reject/defer `commit0:mimesis` for the v0.3 main set.

Possible label:

```text
reject_or_defer
```

## `commit0:cookiecutter`

### Observed task shape

`cookiecutter` has a strong end-to-end software pipeline:

```text
CLI / main entry point
-> config loading
-> repository resolution
-> prompt/context generation
-> file rendering
-> hooks
-> replay
-> VCS / zip handling
```

The screening implicated many modules:

- `cookiecutter/main.py`
- `cookiecutter/generate.py`
- `cookiecutter/prompt.py`
- `cookiecutter/repository.py`
- `cookiecutter/vcs.py`
- `cookiecutter/zipfile.py`
- `cookiecutter/hooks.py`
- `cookiecutter/config.py`
- `cookiecutter/replay.py`
- `cookiecutter/utils.py`

The local collection blocker is missing runtime/test dependencies:

```text
ModuleNotFoundError: No module named 'jinja2'
```

Earlier, without `PYTHONNOUSERSITE=1`, the failure was from a broken user-site `jinja2`/`markupsafe` pair. With `PYTHONNOUSERSITE=1`, the blocker becomes simply missing `jinja2`.

### Why it is structurally attractive

If we were allowed to construct a task, `cookiecutter` would be a good async benchmark shape:

- Agent A could implement repository resolution and archive/VCS loading.
- Agent B could implement context generation and prompt semantics.
- Agent C could implement file generation and hook execution.

Natural stale-work failures would be easy to explain:

- repository resolution returns a path shape that generation does not expect;
- context overwrite semantics differ from prompt assumptions;
- hook execution changes the repo directory but main flow uses stale paths;
- replay data and generated context disagree;
- zip/VCS cleanup expectations conflict with main cleanup logic.

This is exactly the kind of shared workflow state AsyncCodeBench wants to test.

### Why it should not enter the main set now

Despite the good architecture, the raw Commit0 source does not show clear missing implementation. Precise AST inspection found no empty functions/classes in the main package, and key modules appear to contain complete implementations.

Using `cookiecutter` would likely require one of the following:

- hidden-test-only task construction;
- manual code removal;
- synthetic bug injection;
- broader pipeline-generated task creation.

Those are valid future benchmark-construction strategies, but they are not the current v0.3 natural Commit0 curation path.

### Recommendation

Keep `commit0:cookiecutter` in backlog as a structurally strong candidate, but do not add it to the v0.3 main set unless we explicitly allow manually constructed or hidden-test-only tasks.

Possible future scoped task:

```text
commit0:cookiecutter_repo_context_generate_hooks
```

Possible label if used later:

```text
partially_parallelizable
```

## Next repositories to review

According to the current config order, the next unreviewed group is:

```text
tornado
imbalanced-learn
python-progressbar
```

