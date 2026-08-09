# Commit0 Deprecated data example — v0.3

Specification: `SPECIFICATION_v0.3.md`  
Status: qualification-ready candidate pending independent annotation  
Task: `commit0:deprecated`

This document records the public evidence and reasoning used to turn the
Deprecated Commit0 repository into the second AsynCodeBench dataset example.
It follows `COMMIT0_DATA_EXAMPLE_GUIDE_v0.3.md`.

It does not contain a gold solution, reference diff, final human label, or
official model result.

## 1. Immutable upstream task

```text
local repository: data/repos/commit0/deprecated
public origin: https://github.com/commit-0/deprecated.git
commit0 SHA: b7e2114c046abb489e4e23ab9f829778b076650d
```

AsynCodeBench does not modify the upstream implementation or tests. Scenario
records only define agent organization, visibility, execution order,
communication, integration, and budgets.

## 2. Public incomplete implementation surface

The public `commit0` tree contains incomplete implementation in:

```text
deprecated/classic.py
  ClassicAdapter.get_deprecated_msg(...)
  deprecated(...)

deprecated/sphinx.py
  SphinxAdapter.get_deprecated_msg(...)
  versionadded(...)
  versionchanged(...)
  deprecated(...)
```

The public static dependency is:

```text
deprecated/sphinx.py -> deprecated/classic.py
```

No reference branch, future source tree, solution patch, or
`commit0..reference` diff was used.

The released task statement is an answer-free synthesis of public evidence,
not the previously extracted documentation-table-of-contents fragment. It
identifies unfinished public APIs and externally visible behavior without
describing implementation code.

## 3. Natural subproblems

### Classic warning core

```text
implementation:
  deprecated/classic.py

primary tests:
  tests/test_deprecated.py
  tests/test_deprecated_class.py
  tests/test_deprecated_metaclass.py
  tests/test_sphinx_metaclass.py
```

This subproblem covers warning-message selection, bare and parameterized
decorator invocation, warning filters and categories, and function, method,
class, staticmethod, classmethod, and metaclass behavior.

### Sphinx directive layer

```text
implementation:
  deprecated/sphinx.py

primary tests:
  tests/test_sphinx.py
  tests/test_sphinx_adapter.py
  tests/test_sphinx_class.py
```

This subproblem covers directive factories, docstring insertion and wrapping,
Sphinx reference cleanup, class identity, and compatibility with inherited
ClassicAdapter warning behavior.

### Integration validation

```text
deprecated/__init__.py
tests/test.py
tests/test_sphinx_metaclass.py
```

The combined workspace must preserve the package API and ensure that the
Sphinx implementation remains compatible with the completed Classic layer.

`tests/test_sphinx_metaclass.py` is assigned to the Classic subproblem despite
its filename: its test bodies call `deprecated.classic.deprecated`.

## 4. Natural asynchronous risk

The modules expose distinct functionality and separate targeted test groups,
so both specialists can make meaningful progress independently. They are not
fully independent:

- `SphinxAdapter` inherits `ClassicAdapter`;
- the Sphinx deprecated path must preserve Classic warning semantics;
- both layers must agree on constructor fields, decorator invocation, wrapped
  object handling, warning filtering, and message formatting.

The possible freshness failure is:

```text
Classic worker implements or clarifies an adapter/decorator contract
-> Sphinx worker continues from the original commit0 assumption
-> both targeted patches appear locally plausible
-> integrated warning, class, or docstring behavior fails
```

The demonstrative proposal is `partially_parallelizable`. This is not the final
label; two independent humans must complete the stored annotation forms.

Cross-module failure alone is not labeled freshness harm. The quality record
separates Classic specialist-local tests, a Sphinx-local
`versionadded`/`versionchanged` slice, Classic–Sphinx cross-contract tests, and
the full evaluator.

## 5. Frozen scenario drafts

```text
iterative_single:
  one iterative agent owns classic.py and sphinx.py

serial_specialists:
  Classic completes and is tested before Sphinx starts

async_private:
  Classic and Sphinx run concurrently in private workspaces
  no in-flight messages or artifacts are delivered

async_message:
  concurrent workers may exchange structured assumptions, status,
  test results, and artifacts
```

Every condition uses the same iterative inspect/edit/test/repair scaffold,
24 steps per agent, 60,000 tokens per agent, eight tests per agent, and a
1,800-second wall-clock budget. Single-agent and serial-specialist outcomes
are evaluation baselines to be reported, not dataset-admission gates.

## 6. Evaluator quality evidence

The isolated public `commit0` workspace collects all 171 tests:

```text
17 passed
104 failed
50 errors
return code 1
```

Failures and errors are caused by unfinished public APIs, not missing
dependencies or collection failure.

An unchanged public completed tag was evaluated only as an evaluator sanity
check:

```text
171 passed
return code 0
```

That completed source is excluded from decomposition, annotation, prompts, and
agent-visible evidence. The validated environment is:

```text
Python 3.10.4
wrapt 1.17.3
pytest 9.0.3
setuptools 78.1.1
```

## 7. Generated dataset assets

```text
manifests/pilot/v0.3/tasks/commit0_deprecated.json
manifests/pilot/v0.3/scenarios/commit0_deprecated.json
manifests/pilot/v0.3/quality/commit0_deprecated.json
manifests/annotations/asyncodebench_v0.3/deprecated/annotator_a.json
manifests/annotations/asyncodebench_v0.3/deprecated/annotator_b.json
manifests/annotations/asyncodebench_v0.3/deprecated/adjudication.template.json
```

Regenerate deterministically with:

```bash
PYTHONPATH=src python scripts/build_deprecated_v03_data.py
```

The quality status is `qualification_ready`, not `release_ready`.

## 8. Remaining release tasks and pending evaluations

1. Complete two independent human annotations.
2. Adjudicate only if their decisions differ.
3. Record the environment requirements and evaluator command.
4. Run and report the single-agent baseline condition.
5. Run and report specialist-local, serial-specialist, and async conditions.
6. Attribute async degradation only after comparing against the single-agent
   and serial-specialist baselines.
