# Commit0 Candidate Review: click / python-rsa / statsmodels

Date: 2026-06-24  
Protocol: AsynCodeBench v0.3, following `docs/protocols/COMMIT0_DATA_EXAMPLE_GUIDE_v0.3.md`

This audit reviews the next three locally available Commit0 repositories in config order after `voluptuous / seaborn / fastapi`:

- `commit0:click`
- `commit0:python-rsa`
- `commit0:statsmodels`

The screening goal is to find repositories that can become AsynCodeBench tasks: tasks should be feasible for a strong single coding agent, while naturally exposing asynchronous multi-agent failure modes such as stale teammate interfaces or inconsistent shared abstractions.

## Decision summary

| Repository | Decision | AsynCodeBench fit | Main reason |
|---|---:|---:|---|
| `click` | Reject/defer for v0.3 main set | Not suitable as raw Commit0 task | Raw Commit0 already passes the visible suite. The remaining markers are mostly intentional abstract methods, no-op callbacks, or platform fallbacks rather than substantive missing implementation. |
| `python-rsa` | Add to candidate pool, lower priority | Borderline `partially_parallelizable` | There is a real interface dependency between key objects/serialization and PKCS#1 encryption/signing behavior, but the task is compact and mostly concentrated in two modules. |
| `statsmodels` | Defer for v0.3 main set | Too broad/noisy | Huge dependency surface, many numerical subdomains, heavy environment requirements, and hundreds of implicated modules. Possible scoped task exists, but it is not a clean first-wave benchmark candidate. |

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
```

`python-rsa` should be treated as a compact candidate, not a top-priority anchor task.

Recommended secondary backlog:

```text
babel
seaborn
statsmodels
```

Recommended defer/reject for v0.3 main set:

```text
geopandas
voluptuous
click
```

## `commit0:click`

### Observed task shape

The repository has a strong test suite around:

- command and group execution
- option and argument parsing
- parser internals
- shell completion
- terminal UI
- testing utilities
- type conversion
- formatting and context behavior

However, the raw Commit0 screening result is:

```text
597 passed, 21 skipped
```

The static audit finds markers in modules such as:

- `src/click/core.py`
- `src/click/types.py`
- `src/click/shell_completion.py`
- `src/click/utils.py`
- `src/click/_compat.py`
- `src/click/_termui_impl.py`

But these are mostly intentional abstract methods, no-op error handling, platform fallbacks, or test fixtures. They are not strong evidence of missing implementation that visible tests are asking agents to complete.

### Why it should not be selected

`click` would force us to create extra hidden-test difficulty on top of a raw Commit0 repository that already passes the public suite. That is a different benchmark construction mode from our current v0.3 protocol.

It also weakens the story: if the public Commit0 task already passes, then failures under async multi-agent execution may reflect our artificial decomposition or hidden tests rather than a natural incomplete coding task.

### Recommendation

Do not include `commit0:click` in the v0.3 main set.

Possible label:

```text
reject_or_defer
```

It can be kept only as a future control candidate if we explicitly decide to study hidden-test-only tasks.

## `commit0:python-rsa`

### Observed task shape

The relevant implementation surface is compact:

- `rsa/key.py`
- `rsa/pkcs1.py`
- supporting modules such as `rsa/common.py`, `rsa/core.py`, `rsa/prime.py`, `rsa/transform.py`, and `rsa/pem.py`

The visible tests cover:

- key generation
- custom exponent behavior
- multiprime RSA behavior
- blinding and unblinding
- public/private key hashing
- PKCS#1 encryption/decryption
- signing and verification
- DER/PEM load-save behavior
- padding rejection and extra-zero handling

Collection is clean after disabling incompatible default pytest addopts. A local selected run collected 47 tests for `test_key.py`, `test_pkcs1.py`, and `test_load_save_keys.py`. Failures in the current environment are dominated by missing `pyasn1`, which is an environment-freezing issue rather than a benchmark-design blocker.

### Why it partially fits AsynCodeBench

`python-rsa` has a real interface-dependency structure:

```text
key generation / key object fields / multiprime state
-> low-level RSA operations
-> PKCS#1 encryption, decryption, signing, verification
-> PEM/DER serialization
```

The natural stale-work risks are:

- Agent A changes `PrivateKey` and `PublicKey` field semantics, especially for multiprime RSA.
- Agent B implements `pkcs1.decrypt`, `sign`, or `verify` using stale assumptions about `PrivateKey.blinded_decrypt`, key length, or multiprime fields.
- Agent C implements DER/PEM serialization using a different representation of multiprime key metadata.
- The merged code may compile and pass some unit tests but fail on edge cases such as extra-zero rejection, multiprime signing, or malformed key loading.

This is a legitimate AsynCodeBench pattern, especially for `Interface Dependency`.

### Weaknesses

The task is small and concentrated. The strongest dependencies are mostly between two files:

- `rsa/key.py`
- `rsa/pkcs1.py`

That means it may not expose as much asynchronous coordination complexity as repositories like `fastapi`, `requests`, `dulwich`, or `filesystem_spec`.

It is useful as a compact benchmark instance, but not as one of the main story-driving examples.

### Suggested task construction

Recommended scoped task name:

```text
commit0:python_rsa_key_pkcs1_multiprime
```

Recommended subproblem split:

- Agent A: key object semantics
  - `PublicKey`
  - `PrivateKey`
  - multiprime fields `rs`, `ds`, `ts`
  - blinding and `blinded_decrypt`
- Agent B: PKCS#1 operations
  - `encrypt`
  - `decrypt`
  - `sign`
  - `verify`
  - padding and extra-zero validation
- Agent C: serialization compatibility
  - PEM/DER load-save
  - public/private key round-trips
  - multiprime serialization behavior

Recommended evaluator focus:

- `tests/test_key.py`
- `tests/test_pkcs1.py`
- `tests/test_load_save_keys.py`
- optionally `tests/test_common.py`, `tests/test_prime.py`, and `tests/test_transform.py` as low-level guards

Environment requirements should include at least:

```text
pyasn1
pytest-cov or pytest addopts override
```

### Recommendation

Add `commit0:python-rsa` to the candidate pool as a compact, lower-priority task.

Possible label:

```text
partially_parallelizable
```

It is acceptable for v0.3 if we need more repository diversity, but it should not be prioritized over candidates with broader natural shared abstractions.

## `commit0:statsmodels`

### Observed task shape

`statsmodels` is extremely large:

- more than 1,000 Python files locally
- hundreds of test files
- 237 implicated modules in the screening output
- 564 static dependency edges in the screening output
- heavy runtime requirements including `numpy`, `scipy`, `pandas`, `patsy`, and packaging/build constraints

The largest implicated subsystems include:

- `statsmodels/tsa`
- `statsmodels/sandbox`
- `statsmodels/stats`
- `statsmodels/base`
- `statsmodels/discrete`
- `statsmodels/regression`
- `statsmodels/genmod`
- `statsmodels/gam`

The top implicated units include:

- `statsmodels/base/model.py`
- `statsmodels/base/data.py`
- `statsmodels/base/_prediction_inference.py`
- `statsmodels/regression/linear_model.py`
- `statsmodels/discrete/discrete_model.py`
- `statsmodels/genmod/generalized_linear_model.py`
- `statsmodels/stats/sandwich_covariance.py`

Local collection for even a small selected subset currently fails without dependencies such as `patsy`.

### Why it is risky for v0.3

There are real shared abstractions in `statsmodels`, especially:

```text
data handling
-> model base classes
-> result wrappers
-> prediction/inference helpers
-> regression / discrete / GLM consumers
```

This could support an AsynCodeBench task in principle.

However, it is not a clean v0.3 candidate:

- The repository is too broad to evaluate cheaply.
- Many failures would be numerical-library, data-shape, or dependency-version issues.
- Subtask boundaries are difficult to explain to non-domain annotators.
- Hidden failures may reflect statistical correctness rather than asynchronous stale-interface coordination.
- The environment lock would be much heavier than the rest of the benchmark.

### Possible future scoped task

If we revisit it later, the only plausible path is a very narrow scoped task, for example:

```text
commit0:statsmodels_base_model_data_prediction
```

Possible subproblem split:

- Agent A: `statsmodels/base/data.py`
- Agent B: `statsmodels/base/model.py` and result wrapper contracts
- Agent C: `statsmodels/base/_prediction_inference.py` and selected regression/discrete consumers

But this should be treated as a future domain-heavy candidate, not as a main v0.3 selection.

### Recommendation

Defer `commit0:statsmodels` for the v0.3 main set.

Possible label:

```text
manual_review_backlog
```

## Next repositories to review

After this audit, the next unreviewed repositories in the current Commit0 config order are:

```text
more-itertools
moviepy
loguru
```

