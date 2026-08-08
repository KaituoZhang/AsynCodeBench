# Commit0 Candidate Review: networkx, graphene, tlslite-ng

Date: 2026-06-24

Scope: sequential candidate review after `marshmallow`, `parsel`, and `pyjwt`. This review follows `docs/protocols/COMMIT0_DATA_EXAMPLE_GUIDE_v0.3.md`: use public candidate evidence, inspect the stripped Commit0 task state, identify natural subproblems before assigning roles, and reject tasks whose coordination difficulty is manufactured by arbitrary file count or excessive scope.

Reviewed repositories:

- `commit0:networkx`
- `commit0:graphene`
- `commit0:tlslite-ng`

Important ref note:

- Local `commit0` branches for these repositories point to complete/default upstream code.
- The stripped Commit0-style task state is at `origin/commit0_combined`.
- Review decisions below use `origin/commit0_combined` as the candidate initial state and complete/default upstream only as evaluator/reference sanity evidence.

## Summary decision

| Repository | Decision | Priority | Reason |
| --- | --- | --- | --- |
| `graphene` | Promote to candidate construction queue, not direct release task | Medium/high | Natural GraphQL type/schema decomposition, manageable external deps, but full stripped task is broader than needed and must be curated. |
| `networkx` | Defer/reject for v0.3 main queue | Low | Extremely broad stripped task: hundreds of modules and tens of thousands of lines; violates guide principle against manufacturing coordination by file count. |
| `tlslite-ng` | Defer for v0.3 main queue | Low/medium backlog | Real protocol-layer dependencies, but full task is security/crypto-heavy, very broad, and high-risk for evaluator complexity. |

## `commit0:graphene`

### Evidence inspected

- Stripped task ref: `origin/commit0_combined`
  - commit: `ec2d3f4`
  - changed files include:
    - `graphene/types/unmountedtype.py`
    - `graphene/types/scalars.py`
    - `graphene/types/definitions.py`
    - `graphene/types/inputobjecttype.py`
    - `graphene/types/objecttype.py`
    - `graphene/types/schema.py`
    - `graphene/relay/node.py`
    - `graphene/relay/connection.py`
    - `graphene/utils/dataloader.py`
    - `graphene/validation/depth_limit.py`
    - plus utility and scalar modules
- Diff size from stripped to complete/default:
  - 49 source files in stripped commit summary
  - about 253 insertions, 3438 deletions in stripped commit
  - about 2785 insertions, 1190 deletions from stripped to complete/default across repo state
- Current AsynCodeBench env collection blocker:
  - missing `graphql`
- Declared runtime dependencies:
  - `graphql-core>=3.1,<3.3`
  - `graphql-relay>=3.1,<3.3`
  - `aniso8601>=8,<10`

### Quality assessment

`graphene` is a plausible AsynCodeBench candidate, but not as a full stripped task.

It has a natural dependency structure:

- `graphene/types/unmountedtype.py` defines the mounting contract: converting unmounted Graphene types into `Field`, `InputField`, and `Argument`.
- `graphene/types/scalars.py` defines scalar type behavior and coercion.
- `graphene/types/inputobjecttype.py` and `graphene/types/objecttype.py` define class-to-field extraction, metadata, and container behavior.
- `graphene/types/definitions.py` wraps GraphQL-core types while preserving the original Graphene type.
- `graphene/types/schema.py` builds the GraphQL `TypeMap`, converts Graphene types into GraphQL-core objects, and executes/introspects schemas.
- `graphene/relay/node.py` and `graphene/relay/connection.py` implement Relay conventions on top of object/schema/type semantics.

This matches the guide's required structure:

- There are multiple implementation modules.
- There are clear API contracts across modules.
- Tests exercise separable but interacting behavior.
- Stale assumptions are plausible: e.g. a schema-building agent may assume a certain mounted type contract while another agent changes how `UnmountedType.Field/InputField/Argument` or scalar `get_type()` works.

### Recommended task shape

Do not admit the full stripped `graphene` task directly.

Recommended curated task id:

- `commit0:graphene_type_schema`

Recommended decomposition:

- Subproblem A: type mounting and scalar/input/object metadata
  - `graphene/types/unmountedtype.py`
  - `graphene/types/scalars.py`
  - `graphene/types/inputobjecttype.py`
  - `graphene/types/objecttype.py`
  - `graphene/types/definitions.py`
- Subproblem B: schema/type-map construction and execution surface
  - `graphene/types/schema.py`
  - selected `graphene/types/utils.py`
  - selected `graphene/types/field.py` / `argument.py` only if needed by evaluator
- Optional Subproblem C: Relay layer
  - `graphene/relay/node.py`
  - `graphene/relay/connection.py`

For v0.3, keep Relay optional. The type/schema core is already enough to expose async coordination risk.

Recommended evaluator:

- Freeze runtime dependencies:
  - `graphql-core`
  - `graphql-relay`
  - `aniso8601`
- Primary tests should start from:
  - `graphene/types/tests/test_definition.py`
  - `graphene/types/tests/test_objecttype.py`
  - `graphene/types/tests/test_inputobjecttype.py`
  - `graphene/types/tests/test_schema.py`
  - `graphene/types/tests/test_scalars_serialization.py`
- Avoid benchmark/snapshot-heavy example tests in the first release evaluator.

Admission status:

- Promote to candidate construction queue.
- Needs a curated TaskQualityRecord and scoped evaluator before it can be counted as a formal v0.3 release task.

## `commit0:networkx`

### Evidence inspected

- Stripped task ref: `origin/commit0_combined`
  - commit: `651b3dd35`
  - stripped commit summary: 252 source files changed, about 3597 insertions and 44334 deletions
- Diff from stripped to complete/default:
  - 426 files changed
  - about 47386 insertions and 5234 deletions
- Screening summary:
  - 68 publicly implicated modules
  - 260 test targets
  - timeout during raw screening
- Temporary stripped collection attempts fail before targeted class tests:
  - `networkx/utils/random_sequence.py` import fails with `TypeError: 'NoneType' object is not callable`, likely because a low-level decorator/helper has been stripped.

### Quality assessment

`networkx` should not be admitted into v0.3 main queue.

The full stripped task violates the guide's anti-pattern warnings:

- The difficulty is dominated by repository breadth and file count.
- Almost every area of the package is implicated: graph classes, algorithms, generators, drawing, linalg, read/write, utils, backends.
- A role split would be arbitrary unless we manually carve out a very small subtask.
- The stripped tree breaks at low-level import/decorator behavior, so many targeted tests cannot even collect without a substantive bootstrap.

There are real dependency structures inside NetworkX, but the raw Commit0 task is too broad to support a clean AsynCodeBench story. Using it directly would measure "large-library reconstruction" more than asynchronous coordination.

### Possible future use

If we later want a separate large-library tier, a small curated subset could be designed around:

- graph core API:
  - `networkx/classes/graph.py`
  - `networkx/classes/digraph.py`
  - `networkx/classes/reportviews.py`
  - `networkx/classes/function.py`
- or shortest-path stack:
  - `networkx/algorithms/shortest_paths/generic.py`
  - `weighted.py`
  - `unweighted.py`

But this would be a new curated benchmark construction effort, not admission of the raw Commit0 sample.

Admission status:

- Defer/reject for v0.3 main queue.
- Do not count toward the target 20 tasks.

## `commit0:tlslite-ng`

### Evidence inspected

- Stripped task ref: `origin/commit0_combined`
  - commit: `3a008c0`
  - stripped commit summary: 91 source files changed, about 1601 insertions and 18041 deletions
- Diff from stripped to complete/default:
  - 118 files changed
  - about 21629 insertions and 1893 deletions
- Screening summary:
  - 34 publicly implicated modules
  - 50 static dependency edges
  - 55 test targets
- Temporary stripped collection attempts fail due missing runtime dependency:
  - `ecdsa`
- Declared runtime dependency:
  - `ecdsa>=0.18.0b1`

### Quality assessment

`tlslite-ng` has real async-relevant structure but is not appropriate for the first v0.3 main queue.

Natural dependency layers exist:

- constants/codec/serialization utilities
- TLS extensions
- key exchange and crypto/key factories
- record layer
- message layer
- TLS connection/handshake orchestration
- integration wrappers

However, the raw task is too broad and security-sensitive:

- It touches a full TLS implementation, including cryptographic primitives, record handling, handshake settings, messages, connection state, and integration modules.
- Many modules are semantically coupled through protocol invariants.
- Mistakes in crypto/protocol code can create hidden correctness and security ambiguity beyond the benchmark's intended async-coordination focus.
- A full evaluator would be dependency- and environment-heavy.

This is not a good early-release task under the guide: the task would require substantial curation before it tests stale multi-agent coordination rather than full protocol reconstruction.

### Possible future use

If used later, narrow it to one explicitly scoped protocol subtask:

- `commit0:tlslite_extensions_messages`
  - `tlslite/extensions.py`
  - `tlslite/messages.py`
  - `tlslite/utils/codec.py`
  - selected constants
  - selected `unit_tests/test_tlslite_extensions.py`
  - selected `unit_tests/test_tlslite_messages.py`

Even this should be treated as a high-complexity backlog item, not a near-term release task.

Admission status:

- Defer for v0.3 main queue.
- Keep as low/medium backlog only if we later want a protocol/security tier.

## Updated candidate queue implication

After this review:

- Promote to candidate construction queue:
  - `graphene`
- Defer/reject for v0.3 main queue:
  - `networkx`
  - `tlslite-ng`

Recommended near-term construction queue remains:

1. `commit0:requests`
2. `commit0:simpy`
3. `commit0:dulwich`
4. `commit0:parsel`
5. `commit0:filesystem_spec`
6. `commit0:marshmallow`
7. `commit0:graphene`

