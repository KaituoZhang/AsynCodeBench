# Commit0 Candidate Review: marshmallow, parsel, pyjwt

Date: 2026-06-24

Scope: sequential candidate review after `minitorch`, `simpy`, and `bitstring`. This review inspects whether each repository can become an AsyncCodeBench v0.3 task: a strong single-agent coding task with natural multi-agent decomposition and measurable async coordination risk.

Reviewed repositories:

- `commit0:marshmallow`
- `commit0:parsel`
- `commit0:pyjwt`

Important ref note:

- Local `commit0` branches for these repositories point to complete/default upstream code.
- The stripped Commit0-style task state is at `origin/commit0_combined`.
- Review decisions below use `origin/commit0_combined` as the candidate initial state and complete/default upstream as validation/reference evidence only.

## Summary decision

| Repository | Decision | Priority | Reason |
| --- | --- | --- | --- |
| `parsel` | Promote to formal construction queue | High | Compact source scope, clear `csstranslator -> selector` interface dependency, strong async-stale risk, and realistic coding-agent task. |
| `marshmallow` | Promote to candidate construction queue | Medium/high | Strong field/schema/validator dependency structure and manageable dependencies, but larger task scope than `parsel`; should be curated into a focused subset. |
| `pyjwt` | Defer for v0.3 main queue | Medium backlog | Natural utility/algorithm/JWS/JWT dependency exists, but full stripped task is broad, crypto/security-sensitive, and import breaks at low-level utilities; needs a non-crypto subset if used. |

## `commit0:parsel`

### Evidence inspected

- Stripped task ref: `origin/commit0_combined`
  - commit: `7e73d60`
  - changed files:
    - `parsel/csstranslator.py`
    - `parsel/selector.py`
    - `parsel/utils.py`
    - `parsel/xpathfuncs.py`
    - `spec.pdf.bz2`
- Diff size from stripped to complete/default:
  - 5 files
  - about 710 insertions, 93 deletions
- Stripped-state collection in the current AsyncCodeBench env fails due missing dependencies:
  - `lxml`
  - `cssselect`
  - `psutil`
  - `sybil`
  - plus declared runtime dependencies `jmespath`, `packaging`, `w3lib`

### Quality assessment

`parsel` is a strong AsyncCodeBench candidate.

It has a compact and natural interface dependency:

- `parsel/csstranslator.py` translates CSS selectors and pseudo-elements into XPath expressions.
- `parsel/selector.py` exposes the high-level public API: `Selector`, `SelectorList`, `.css()`, `.xpath()`, `.re()`, `.get()`, `.getall()`, namespace operations, and node removal/drop behavior.
- `parsel/utils.py` supplies helper behavior used by selectors, such as flattening and regex extraction.
- `parsel/xpathfuncs.py` registers custom XPath functions.

This is exactly the kind of decomposition AsyncCodeBench wants:

- Agent A can own selector translation and utility primitives.
- Agent B can own high-level selector/list behavior.
- If B proceeds with stale assumptions about A's XPath shape, pseudo-element representation, regex behavior, or return types, the merged implementation can fail tests without necessarily producing a textual git conflict.

### Recommended task shape

Proposed task id:

- `commit0:parsel_selector_pipeline`

Recommended decomposition:

- Subproblem A: selector expression layer
  - `parsel/csstranslator.py`
  - selected parts of `parsel/utils.py`
- Subproblem B: selector execution and result API
  - `parsel/selector.py`
  - `parsel/xpathfuncs.py`

Recommended evaluator:

- Freeze runtime dependencies:
  - `lxml`
  - `cssselect`
  - `jmespath`
  - `packaging`
  - `w3lib`
- Primary tests:
  - `tests/test_selector.py`
  - `tests/test_selector_csstranslator.py`
  - `tests/test_utils.py`
  - `tests/test_xpathfuncs.py`
- Avoid docs/sybil tests in the primary evaluator unless docs dependencies are explicitly frozen.
- Treat `tests/test_xml_attacks.py` as optional/security-stress tier because it brings `psutil` and environment-sensitive checks.

Admission status:

- Promote to formal construction queue.
- Good next target after `requests`, `simpy`, and `dulwich`.

## `commit0:marshmallow`

### Evidence inspected

- Stripped task ref: `origin/commit0_combined`
  - commit: `bd290d2`
  - changed files include:
    - `src/marshmallow/fields.py`
    - `src/marshmallow/schema.py`
    - `src/marshmallow/validate.py`
    - `src/marshmallow/utils.py`
    - `src/marshmallow/class_registry.py`
    - `src/marshmallow/decorators.py`
    - `src/marshmallow/error_store.py`
    - `src/marshmallow/exceptions.py`
    - `src/marshmallow/orderedset.py`
    - `src/marshmallow/base.py`
    - `src/marshmallow/warnings.py`
- Diff size from stripped to complete/default:
  - 20 files
  - about 3019 insertions, 389 deletions
- Stripped-state collection in the current AsyncCodeBench env fails first due missing `simplejson`.
- Declared test dependencies are modest:
  - `pytest`
  - `pytz`
  - `simplejson`

### Quality assessment

`marshmallow` is a good candidate, but it should be curated rather than admitted as the full stripped task.

It has a strong natural dependency graph:

- `validate.py` defines reusable validation contracts and error behavior.
- `fields.py` defines serialization/deserialization field behavior and calls validators/utilities.
- `schema.py` orchestrates declared fields, load/dump behavior, partial/unknown handling, nested options, hooks, and error storage.
- `class_registry.py` and nested fields connect schema lookup and nested serialization.
- `decorators.py` and hook resolution influence schema preprocessing/postprocessing.

The async risk is strong:

- A field-specialist agent may change deserialization return semantics, missing-value behavior, `allow_none`, or validation error shape.
- A schema-specialist agent may concurrently implement load/dump orchestration based on stale expectations about field behavior.
- The merged code can fail nested schema, partial load, unknown-field, or error-store tests without a textual conflict.

### Recommended task shape

Do not use the full stripped task as one release task.

Proposed curated task id:

- `commit0:marshmallow_field_schema`

Recommended decomposition:

- Subproblem A: field and validation semantics
  - `src/marshmallow/fields.py`
  - `src/marshmallow/validate.py`
  - selected `src/marshmallow/utils.py`
- Subproblem B: schema orchestration and nested binding
  - `src/marshmallow/schema.py`
  - `src/marshmallow/class_registry.py`
  - `src/marshmallow/error_store.py`
  - selected `src/marshmallow/decorators.py`

Recommended evaluator:

- Use `PYTHONPATH=src`.
- Freeze:
  - `simplejson`
  - `pytz`
  - `packaging`
- Primary tests should start from:
  - `tests/test_fields.py`
  - `tests/test_schema.py`
  - `tests/test_validate.py`
  - `tests/test_deserialization.py`
  - `tests/test_serialization.py`
  - `tests/test_registry.py`
- Treat version/package metadata tests as controls unless the task explicitly includes package metadata.

Admission status:

- Promote to candidate construction queue.
- Recommended after compact candidates because the task is larger and requires careful evaluator scoping.

## `commit0:pyjwt`

### Evidence inspected

- Stripped task ref: `origin/commit0_combined`
  - commit: `e2d0890`
  - changed files include:
    - `jwt/utils.py`
    - `jwt/algorithms.py`
    - `jwt/api_jws.py`
    - `jwt/api_jwt.py`
    - `jwt/api_jwk.py`
    - `jwt/jwks_client.py`
    - `jwt/jwk_set_cache.py`
    - `jwt/exceptions.py`
    - `jwt/help.py`
    - `jwt/warnings.py`
- Diff size from stripped to complete/default:
  - 33 files
  - about 2109 insertions, 248 deletions
- Stripped-state collection fails immediately because low-level `jwt.utils` stubs break imports:
  - missing `base64url_decode`
  - missing `base64url_encode`
  - missing `force_bytes`
  - missing `from_base64url_uint`
  - related imports in `jwt.algorithms`, `jwt.api_jws`, and `jwt.api_jwt`
- Optional crypto stack is substantial:
  - `cryptography` is required for RSA/EC/EdDSA tests and algorithms.

### Quality assessment

`pyjwt` has a real interface-dependency structure, but it is not a good next v0.3 mainline task.

The dependency chain is natural:

- `jwt/utils.py` provides base64url, byte conversion, key/signature conversion, PEM/SSH key detection.
- `jwt/algorithms.py` implements algorithm registration and signing/verification primitives.
- `jwt/api_jws.py` builds JWS encode/decode/signature logic over algorithms and utilities.
- `jwt/api_jwt.py` adds JWT claims validation and payload semantics over JWS.

This could produce async-stale failures, but the full task is broad and security-sensitive. Early import failure also means any multi-agent setup would require either:

- a bootstrap/control overlay for utility imports, or
- a staged task where low-level utilities are completed before higher-level agents begin.

That staging weakens the clean async story unless carefully designed.

### Possible future task shape

If included later, use a narrow non-crypto subset:

- `commit0:pyjwt_hmac_jws`

Recommended scope:

- `jwt/utils.py`
- `jwt/algorithms.py`
  - only `NoneAlgorithm` and `HMACAlgorithm`
- `jwt/api_jws.py`
- selected `jwt/exceptions.py`

Avoid for v0.3 main queue:

- RSA/EC/EdDSA algorithm scope
- JWK/JWKS client scope
- network/client tests
- full crypto-dependent evaluator

Admission status:

- Defer for v0.3 main queue.
- Keep as medium-priority backlog only if we later want a security/token task tier.

## Updated candidate queue implication

After this review:

- Promote:
  - `parsel`
  - `marshmallow`
- Defer/backlog:
  - `pyjwt`

Recommended near-term construction queue:

1. `commit0:requests`
2. `commit0:simpy`
3. `commit0:dulwich`
4. `commit0:parsel`
5. `commit0:filesystem_spec`
6. `commit0:marshmallow`

