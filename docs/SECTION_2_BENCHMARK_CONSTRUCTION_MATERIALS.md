# Section 2 Materials: AsynCodeBench Benchmark Construction

> Historical construction snapshot: this document records the earlier
> 20-task candidate/review population. The executable v0.4.1 community and
> matched paper benchmark contains 19 tasks and excludes Graphene. Use
> `manifests/release/v0.4/task_index.json` for current release membership.

This document is a paper-writing source packet for the unified v0.4
community-preview release. It separates text that can be adapted directly into
the main paper from audit evidence and claims that require careful wording.

The statistics below were recomputed from the 20 task, scenario, quality,
metric, review, qualification, and release records on 2026-08-29. The unified
v0.4 release index was current, and the repository contract suite passed
164/164 tests.

## Evidence-backed snapshot

| Item | Current official value |
| --- | ---: |
| Adapted repository tasks | 20 |
| Execution scenarios | 80 = 20 tasks x 4 conditions |
| Manifested natural subproblems | 68 |
| Specialists in each multi-agent scenario | 2--4 |
| Directed dependency points | 56 |
| Dependency points per task | 2--5 (mean 2.80) |
| Dependency categories | 4 |
| Required checker groups | 168 = 56 upstream + 56 downstream + 56 integrated |
| Checker selector references | 546 |
| Task-qualified unique public test selectors | 294 |
| Public bootstrap/test overlays | 47 checksum-pinned patches across 14 tasks; 6 tasks use none |
| Qualification-ready task records | 20/20 |
| Required human reviews completed and approved | 20/20 |
| Separate automated audits completed and agreeing | 20/20 |
| Initial evaluators with observable unfinished behavior | 20/20 |
| Completed evaluator sanity runs with zero failures/errors | 20/20 |
| Repository contract tests, rechecked 2026-08-29 | 164/164 passed |

The release policy is **one required human approval per task plus one separate
automated audit**. The automated audit does not count as a second human. This
is the policy that should be reported. All 20 tasks satisfy this gate in the
unified v0.4 community-preview index.

### Four compiler and IR tasks added in v0.4

Four recent compiler/IR repository tasks passed the same construction gates and
are included in the 20-task population. Their incomplete state is the merged
change's first parent; only checksum-pinned, answer-free public test changes
are exposed, while the production completion remains offline for red-green
qualification.

| Task | Natural roles | Directed contracts | Human-review status |
| --- | ---: | ---: | --- |
| `asyncodebench:apache-tvm-20153` | PTX dialect schema; operand lowering; PTX rendering | 2-role chain | approved |
| `asyncodebench:apache-tvm-20107` | shared Script signature core; Relax dependent signature; TIRx dependent signature | 2-edge fan-out | approved |
| `asyncodebench:apache-tvm-20073` | IRBuilder span state; source-coordinate mapping; parser/evaluator propagation | 2-producer join | approved |
| `asyncodebench:apache-tvm-20018` | Return IR schema and visitors; TVMScript construction and rendering; lowering and target emission | 2-edge chain | approved |

The corresponding automated evidence includes exact role-local selectors,
dependency checkers, frozen source-build environments, and role-ablation
matrices. Human reviewer `pz0512` approved all four on 2026-08-29 as
`partially_parallelizable`; the v0.4 qualification records therefore have no
remaining construction gates and set `official_result_eligible=true`.
Screened tasks that remain calibration-only or `needs_revision` are retained
as audit provenance and do not enter the 20-task release index.

## 2 AsynCodeBench: Benchmark Construction

### 2.1 Task Formulation

#### Main-text draft

We define an AsynCodeBench instance as

\[
\mathcal{B}=(\mathcal{R},\mathcal{S},\mathcal{A},\mathcal{D},\mathcal{E}),
\]

where \(\mathcal{R}\) is a pinned incomplete repository together with its public
task evidence, \(\mathcal{S}\) is a set of specialist assignments,
\(\mathcal{A}\) maps those specialists to owned implementation surfaces,
\(\mathcal{D}\) is a set of directed producer--consumer
software contracts, and \(\mathcal{E}\) is the final public repository
evaluator. An execution condition determines scheduling, workspace visibility,
artifact transfer, and communication, while leaving \(\mathcal{R}\),
\(\mathcal{D}\), and \(\mathcal{E}\) unchanged. Thus, protocol comparisons
change how agents collaborate rather than what constitutes a correct solution.

AsynCodeBench v0.4 contains 20 adapted repository-reconstruction tasks. This
formulation is useful for studying asynchronous collaboration because the
target is a repository-wide implementation rather than an issue-local edit:
unfinished behavior spans multiple natural modules, while public
documentation, source, and tests expose real cross-module API and state
contracts. Each benchmark workspace is reconstructed from a SHA-pinned
incomplete source state plus checksum-recorded, answer-free public overlays
where necessary. A completed state is used only to establish evaluator
feasibility; it is not used to construct task statements, ownership,
dependency labels, or model-visible evidence.

#### Formal definitions

- \(\mathcal{R}=(U,c,O)\): public repository identity \(U\), pinned incomplete
  commit/materialization \(c\), and an ordered set \(O\) of checksum-recorded,
  answer-free bootstrap overlays. The overlays only remove syntax, import, or
  test-collection blockers.
- \(\mathcal{S}=\{s_1,\ldots,s_m\}\): specialist assignments, each pairing an
  agent role with a natural software responsibility and specialist-local public
  test targets. Responsibilities include key construction, request
  preparation, event scheduling, and schema metadata construction.
- \(\mathcal{A}:s_i\mapsto F_i\): the implementation paths \(F_i\) owned by
  specialist \(s_i\). Ownership constrains agent action; it is not itself
  evidence of a dependency.
- \(\mathcal{D}=\{d_1,\ldots,d_k\}\): directed contracts. Each \(d\) records a
  producer responsibility, a consumer responsibility, their code surfaces, a
  semantic contract, a plausible stale-contract failure mode, and executable
  upstream/downstream/integrated evidence.
- \(\mathcal{E}\): the final public evaluator over the integrated repository.
  Dependency Checkers are diagnostic slices of public tests; \(\mathcal{E}\)
  remains the task-level correctness authority.

The four execution conditions are iterative single agent, serial
specialists, asynchronous private workspaces, and asynchronous message/artifact
sharing. There are 20 instances of each condition, for 80 scenarios total.

#### Why adapted repository reconstruction

The defensible reasons are:

1. It preserves a real library objective and real public tests instead of
   inventing a coordination puzzle.
2. Repository-wide missing behavior exposes multiple natural responsibilities
   and cross-module contracts.
3. Public initial states, public tests, and pinned source provenance support
   reproducible reconstruction.
4. A completed state can verify evaluator feasibility without supplying a gold
   patch or defining dependency labels.
5. Fast, deterministic local evaluators make repeated checkpoint evaluation
   practical.

Source materialization differs by upstream history, but every released task
uses the same public contract: a SHA-pinned incomplete repository state,
ordered checksum-recorded overlays, no reachable production completion, and a
frozen evaluator. Branch names and upstream PR identifiers are retained only
as provenance metadata and do not define separate benchmark populations.

#### Historical source-screening disclosure

| Candidate | v0.3 decision | Recorded reason |
| --- | --- | --- |
| dulwich | Excluded | Removed after execution review; artifacts retained for audit/revision |
| fabric | Excluded | Failed current feasibility review; no official v0.3 artifacts |
| fastapi | Excluded | Still `needs_revision`; pinned-environment validation and human review incomplete |
| python-progressbar | Excluded | Removed after suitability review; historical artifacts retained |
| chardet | Non-official scratch only | Not in the original 20-candidate source pool |

This disclosure is useful in the appendix because it reports negative selection
decisions rather than presenting only successful transformations.

### 2.2 Natural Decomposition and Dependency Construction

#### Main-text draft

The central construction step converts repository structure into directed,
test-observable software contracts:

```text
Public repository reconstruction task
                  |
                  v
Natural software responsibilities
                  |
                  v
Producer / consumer ownership
                  |
                  v
Directed software contract
                  |
                  v
Role-specific public executable evidence
```

**We do not split files arbitrarily to create coordination failures.** Starting
from the public problem statement, source modules, documentation, and tests, we
first identify responsibilities that would exist in an ordinary implementation
workflow. We then retain a dependency only when one responsibility produces an
interface, shared API, shared state convention, or integration behavior that a
different responsibility must consume. File ownership operationalizes these
responsibilities in an agent run, but a file boundary alone is not sufficient
to define a benchmark dependency.

A dependency point is admissible only if it satisfies all of the following:

1. **Natural responsibility.** Producer and consumer correspond to coherent
   software responsibilities, not equal-sized or arbitrary file partitions.
2. **Directional contract.** The relationship has a defensible producer
   \(\rightarrow\) consumer direction and a concrete semantic contract.
3. **Public executable evidence.** Public, answer-free tests visible in the
   incomplete task state exercise producer, consumer, and integrated behavior.
4. **Genuine downstream dependence.** Downstream correctness depends on the
   upstream behavior or convention; mere textual overlap or independent test
   failure is insufficient.
5. **Trajectory-independent construction.** Reference patches, solution files,
   and model outputs are not admissible sources for selecting the contract or
   its checker tests. Exploratory model dry runs, when present, are non-release
   sanity evidence and cannot manufacture a failure condition or replace public
   evidence and human approval.

The construction protocol first runs public tests on the stripped initial
state. If import or collection is blocked, it applies the smallest ordered,
checksum-recorded bootstrap overlays that expose missing symbols or mechanical
class-construction prerequisites without implementing benchmark behavior. It
then records initial evaluator outcomes, checks the evaluator against a
completed sanity state, identifies natural responsibilities and directed
contracts, binds public tests to those contracts, constructs the four execution
conditions, runs deterministic validation, and finally requires human
acceptance.

#### Concrete examples from the released tasks

| Repository | Producer responsibility | Consumer responsibility | Natural contract |
| --- | --- | --- | --- |
| cachetools | key construction | decorator factories | typed decorators must consume `typedkey` semantics |
| wcwidth | Unicode version catalog | width algorithm | version matching must consume the ordered supported-version catalog |
| SimPy | environment scheduler | event/process layer | scheduling, callbacks, time, and exception behavior must agree |
| TinyDB | query contract layer | table/database state stack | query hashing/equality and cache behavior must support repeated search |
| Flask | route/scaffold layer | request dispatch | route registration and endpoint state must support dispatch and URL generation |
| Cookiecutter | config/prompt layer | top-level orchestration | context shape, defaults, replay, and `no_input` semantics must agree |

#### Suggested figure caption

> **Natural dependency construction.** We transform a public repository
> reconstruction task into natural software responsibilities, assign
> producer/consumer ownership, and retain only directed semantic contracts that
> can be bound to role-specific public executable evidence. The construction
> does not synthesize dependencies from arbitrary file splits or model failure
> trajectories.

### 2.3 Executable Dependency Checker

#### Main-text draft

For dependency \(d\), let \(P_d^{\mathrm{up}}\),
\(P_d^{\mathrm{down}}\), and \(P_d^{\mathrm{int}}\) denote the public test
selectors assigned to producer-side, consumer-side, and integrated evidence.
At repository state \(s_t\), each checker is one if every required selector in
the corresponding group passes, zero if any required selector fails, and
unobserved if the group has not been executed. We record

\[
C_d(s_t)=\left(
C_d^{\mathrm{up}}(s_t),
C_d^{\mathrm{down}}(s_t),
C_d^{\mathrm{int}}(s_t)
\right),
\]

and define integrated resolution as

\[
\operatorname{resolved}_d(t)
=\mathbb{1}\!\left[C_d^{\mathrm{int}}(s_t)=1\right].
\]

The three components distinguish a correct producer artifact, a consumer that
has adapted to the contract, and correctness after both artifacts are present
in the integrated workspace. Checkers run after subagent artifact production,
after integration, and after the final evaluator. Unobserved groups remain
unresolved rather than being imputed as passing.

**We bind natural software contracts to role-specific executable evidence.**
Public tests define executable evidence; annotations identify which software
contract those tests measure. The annotations therefore do not create new test
semantics, and the checker does not replace the final repository evaluator.

#### Implementation terminology

Use **Dependency Checker** in the paper. Some released filenames and JSON keys
still contain `probe` for backward compatibility. Avoid saying “we annotate
pytest tests,” which makes the contribution sound like test tagging. The
accurate claim is that human-identified natural contracts are bound to exact,
public, role-specific executable evidence.

#### Checker coverage in v0.4

- All 56 dependency points have non-empty upstream, downstream, and integrated
  checker groups: 168/168 required groups are present.
- The manifests contain 546 selector references: 136 upstream, 170 downstream,
  and 240 integrated.
- After de-duplicating repeated use of the same test within each task, these
  references cover 294 task-qualified public test selectors.
- The current repository contract suite, which includes manifest consistency,
  human-review provenance, release-index, and checker-selector validation,
  passes 164/164 tests.

### 2.4 Benchmark Quality and Composition

#### Main-text draft

Benchmark verification combines deterministic qualification with human
authority over semantic validity. For every candidate, we pin the public source
state, checksum and review any collection-only overlays, record the incomplete
initial evaluator, and verify that the corresponding completed sanity state can
pass the evaluator. Automated contract checks validate manifest consistency,
ownership coverage, dependency-point structure, and public checker selectors.
Automatic checks establish reproducibility and executability, but they do not
decide whether a decomposition is natural.

Each task therefore receives a mandatory human review of the public,
answer-free task, quality, scenario, metric, and overlay evidence. Reviewers
must confirm natural responsibilities, a cross-owner producer--consumer
contract, checker observability, non-solution overlays, and a plausible
asynchronous stale-assumption or integration risk. A separate automated audit
checks the same artifacts but is explicitly not counted as a second human. All
20 tasks passed the required human review and the automated audit; all were
labeled partially parallelizable. All 20 are qualification-ready, expose
unfinished behavior in the initial evaluator, and have a zero-failure,
zero-error completed evaluator sanity run.

#### Compact main-paper composition table

| Dimension | Composition / verification |
| --- | --- |
| Tasks | 20 adapted public repository reconstructions |
| Scenarios | 80; four matched execution conditions per task |
| Responsibilities | 68 manifested natural subproblems; 2--4 specialists per multi-agent scenario |
| Dependencies | 56 directed points; 2--5 per task (mean 2.80) |
| Dependency taxonomy | 22 interface, 18 shared API, 9 integration, 7 shared state |
| Executable evidence | 168/168 required checker groups; 294 unique public test selectors |
| Source reconstruction | SHA-pinned incomplete states; 47 checksum-recorded public overlays across 14 tasks |
| Evaluator qualification | 20/20 nontrivial initial evaluations; 20/20 completed sanity evaluators pass with zero failures/errors |
| Semantic review | 20/20 mandatory human approvals |
| Independent structural audit | 20/20 separate automated audits; automation does not count as human review |

#### Task-domain composition

All 20 tasks are software-engineering tasks in the broad sense. For benchmark
composition, a more informative mutually exclusive taxonomy classifies each
task by the primary software domain exercised by its **scoped evaluator**, not
by every feature offered by the upstream project.

| Broad task class | Count | Share | Official tasks |
| --- | ---: | ---: | --- |
| General SWE and framework engineering | 7 | 35.0% | cachetools, deprecated, parsel, marshmallow, graphene, flask, cookiecutter |
| Systems, runtime, and storage engineering | 6 | 30.0% | portalocker, tinydb, wcwidth, simpy, filesystem_spec, pexpect |
| Compiler and IR engineering | 4 | 20.0% | apache-tvm-20018, apache-tvm-20073, apache-tvm-20107, apache-tvm-20153 |
| Network and protocol software | 2 | 10.0% | requests, imapclient |
| Security and cryptography | 1 | 5.0% | python-rsa |

This five-way grouping is suitable for a compact main-paper composition table.
The following finer labels are better suited to an appendix or dataset card.

| Task | Broad class | Fine-grained domain | Dominant engineering work in the benchmark scope |
| --- | --- | --- | --- |
| cachetools | General SWE / framework | Caching and reusable utility library | key construction, cache decorators, API compatibility, locking, and TTL behavior |
| deprecated | General SWE / framework | Decorators and documentation compatibility | function/class decoration, warning semantics, metaclass compatibility, and Sphinx directives |
| portalocker | Systems / runtime / storage | OS file locking and concurrency | POSIX locking, OS-error translation, timeouts, reentrancy, and file lifecycle |
| tinydb | Systems / runtime / storage | Embedded database and persistence | query semantics, storage, table state, ID allocation, caching, and middleware lifecycle |
| wcwidth | Systems / runtime / storage | Terminal and Unicode infrastructure | interval lookup, Unicode-version matching, codepoint width, emoji, and control handling |
| requests | Network / protocol | HTTP client and transport | request preparation, sessions, redirects, proxies, TLS inputs, adapters, and responses |
| simpy | Systems / runtime / storage | Discrete-event runtime | scheduler stepping, event state machines, processes, interrupts, conditions, and resources |
| parsel | General SWE / framework | Parsing and query processing | CSS-to-XPath translation, selectors, regex/JMESPath queries, namespaces, and serialization |
| filesystem_spec | Systems / runtime / storage | Filesystem and storage abstraction | protocol registry, deferred backends, path expansion, compression, and multi-file I/O |
| marshmallow | General SWE / framework | Schema and serialization framework | field binding, conversion, validation, schema processing, hooks, nesting, and error handling |
| graphene | General SWE / framework | Type-system and schema framework | field/type mounting, metaprogramming, inheritance, GraphQL type maps, and schema construction |
| imapclient | Network / protocol | IMAP protocol client | tokenization, response parsing, typed protocol values, command normalization, and client APIs |
| pexpect | Systems / runtime / storage | Process, PTY, and asynchronous I/O | pattern matching, process state, buffers, EOF/TIMEOUT semantics, transports, and async wrappers |
| flask | General SWE / framework | Web application framework | routing, dispatch, request/app contexts, sessions, JSON, templates, and test clients |
| python-rsa | Security / cryptography | Public-key cryptography | arithmetic, prime/key generation, PKCS#1 operations, integer codecs, and PEM/DER serialization |
| cookiecutter | General SWE / framework | Developer tooling and workflow automation | configuration, prompting, repository acquisition, template rendering, hooks, and orchestration |
| apache-tvm-20018 | Compiler / IR | Return-statement IR and code generation | Return-node schema and visitors, TVMScript parsing/rendering, legality, lowering, and C/LLVM emission |
| apache-tvm-20073 | Compiler / IR | Source-location propagation | IRBuilder scoped span state, source-coordinate conversion, and parser/evaluator propagation |
| apache-tvm-20107 | Compiler / IR | Dependent Script signatures | shared type-parameter syntax and document model consumed by Relax and TIRx parsers/printers |
| apache-tvm-20153 | Compiler / IR | PTX address lowering | PTX dialect metadata, operand lowering, signed offsets, helper identity, and rendering |

The broad categories should not be interpreted as mutually exclusive skill
requirements. For example, Flask contains state-lifecycle work and Requests
contains general API engineering. The assigned class indicates the dominant
domain of the released task scope so that every task contributes once to the
composition statistics.

#### Alternative capability view

For analyses of *what agents must do*, use overlapping capability tags rather
than forcing a second mutually exclusive partition:

| Capability tag | Representative tasks | What it covers |
| --- | --- | --- |
| Public API and compatibility contracts | cachetools, deprecated, requests, marshmallow, flask | preserving signatures, metadata, edge cases, and cross-layer behavior |
| Algorithms and data structures | cachetools, tinydb, wcwidth, simpy, python-rsa | caches, query operations, interval lookup, scheduling, and number theory |
| State and lifecycle management | portalocker, tinydb, simpy, pexpect, flask | locks, persistence, event/process state, buffers, contexts, and sessions |
| Parsing, translation, and serialization | parsel, marshmallow, graphene, imapclient, python-rsa | CSS/XPath, schemas, protocol responses, typed values, and PEM/DER codecs |
| Systems, I/O, and transport integration | portalocker, requests, filesystem_spec, pexpect | OS primitives, adapters, storage protocols, processes, and asynchronous I/O |
| Workflow and component orchestration | requests, filesystem_spec, flask, cookiecutter | composing independently implemented layers into an end-to-end workflow |
| Compiler IR and lowering contracts | apache-tvm-20018, apache-tvm-20073, apache-tvm-20107, apache-tvm-20153 | preserving IR schemas, source metadata, dialect contracts, lowering order, and target emission |

These capability tags are descriptive and overlapping; they should not be
summed as task counts. The five broad domain classes above are the appropriate
taxonomy when the paper needs percentages that sum to 100%.

#### Dependency taxonomy

| Dependency type | Count | Share | Meaning | Released example |
| --- | ---: | ---: | --- | --- |
| Interface dependency | 22 | 40.0% | A consumer calls or interprets a producer-owned interface | cachetools `typedkey` semantics -> typed decorators |
| Shared API contract | 17 | 30.9% | Multiple layers must preserve the same public behavior | shared Script signature core -> Relax and TIRx signatures |
| Integration contract | 9 | 16.4% | Locally plausible artifacts must compose correctly | TVMScript Return surface -> lowering and target emission |
| Shared state contract | 7 | 12.7% | Components must agree on state shape or lifecycle | IRBuilder active span state -> parser/evaluator propagation |

#### Per-task composition

Abbreviations: IF = interface dependency, API = shared API contract, STATE =
shared state contract, INT = integration contract.

| Task | Natural subproblems | Specialists | Dependency points | Types | Representative contract |
| --- | ---: | ---: | ---: | --- | --- |
| cachetools | 5 | 2 | 5 | IF, API | typed keys -> typed decorators |
| deprecated | 3 | 2 | 3 | IF, INT | classic warning behavior -> Sphinx adapter |
| portalocker | 3 | 2 | 3 | IF, API, INT | platform lock exceptions/timeouts -> lock utilities |
| tinydb | 3 | 2 | 3 | IF, API, STATE | query equality/hash/cache -> table search |
| wcwidth | 3 | 2 | 2 | IF, INT | Unicode version catalog -> width matching |
| requests | 3 | 3 | 3 | IF, API | prepared request contract -> session/transport |
| simpy | 4 | 4 | 3 | IF, API | environment scheduling -> events/processes/resources |
| parsel | 3 | 3 | 2 | IF, API | CSS pseudo-elements -> selector behavior |
| filesystem_spec | 4 | 4 | 3 | IF, API | registry/protocol resolution and filesystem backends -> core open paths |
| marshmallow | 3 | 3 | 3 | IF, API, STATE | field semantics -> schema load/dump/validation |
| graphene | 3 | 3 | 3 | IF, API | object metadata -> GraphQL type map/schema |
| imapclient | 3 | 3 | 3 | IF, API, STATE | parsed typed responses -> high-level client |
| pexpect | 4 | 4 | 3 | IF, API, STATE | expect/search state -> spawn API and wrappers |
| flask | 4 | 4 | 3 | IF, STATE, INT | route registration/context -> dispatch |
| python-rsa | 4 | 4 | 3 | IF, API, INT | arithmetic/primes -> key generation/serialization |
| cookiecutter | 4 | 4 | 3 | IF, STATE, INT | config/prompt context -> orchestration |
| apache-tvm-20018 | 3 | 3 | 2 | IF, INT | Return IR core -> Script surface -> lowering/codegen |
| apache-tvm-20073 | 3 | 3 | 2 | IF, STATE | IRBuilder span state and source mapping -> propagation |
| apache-tvm-20107 | 3 | 3 | 2 | API | shared Script signature core -> Relax/TIRx fan-out |
| apache-tvm-20153 | 3 | 3 | 2 | API, INT | PTX dialect schema -> lowering -> rendering |

#### Verification stages suitable for a paper figure or appendix

1. **Candidate intake:** inspect public source, statements, and tests; record
   accept, reject, or defer decisions.
2. **Deterministic reconstruction:** pin the initial SHA and apply ordered,
   checksum-recorded non-solution overlays where collection requires them.
3. **Evaluator qualification:** record unfinished initial behavior and verify a
   clean completed-state sanity run.
4. **Natural decomposition:** identify coherent implementation
   responsibilities and ownership surfaces.
5. **Contract construction:** retain directed producer--consumer contracts with
   public upstream/downstream/integrated evidence.
6. **Automatic audit:** check schemas, checksums, source reconstruction,
   ownership, selector resolution, and release-index consistency.
7. **Human review:** approve only natural, answer-free, executable, genuinely
   dependent tasks; human judgment remains the inclusion authority.

#### Suggested quality figure caption

> **AsynCodeBench qualification pipeline.** Adapted public repository tasks pass
> source reconstruction and evaluator checks before natural responsibilities
> and directed contracts are constructed. Deterministic audits establish
> artifact consistency and executable evidence, while mandatory human review
> determines whether the decomposition and asynchronous dependency are
> semantically natural. Twenty tasks satisfy the unified v0.4 release gates.

## Appendix-ready source reconstruction table

The SHA below is the actual curated benchmark base SHA, not necessarily the
public repository's branch-head SHA.

| Task | Curated base ref | Curated base SHA | Overlays |
| --- | --- | --- | ---: |
| cachetools | `commit0` | `a0a7e2b73f9e146b8a8f2912948b17a918e5fe83` | 0 |
| deprecated | `commit0` | `b7e2114c046abb489e4e23ab9f829778b076650d` | 0 |
| portalocker | `commit0` | `300136afca11ea23c79ecfd110ed0d2819322f11` | 1 |
| tinydb | `commit0` | `ed761a72c8c1e1cb24ca4dbcc089f35c5264d357` | 1 |
| wcwidth | `commit0` | `0d0054189bdb0fc7b9de0456fc3cee2b67a6ceba` | 0 |
| requests | `origin/commit0_combined` | `0e5a01d0ed71fd20b6a72cafe92b9a917ce93d7b` | 3 |
| simpy | `origin/commit0_combined` | `25496719af798e5a276289279651873ea5b6e7d1` | 0 |
| parsel | `origin/commit0_combined` | `7e73d60665ef2e3ddfe3c1bb01eed981cd317c6f` | 1 |
| filesystem_spec | `origin/commit0_combined` | `0d34761c18d98009d76a1c19246606026c0e44a0` | 4 |
| marshmallow | `origin/commit0_combined` | `bd290d2b49f5030a2369aedc5538cffa4815982d` | 4 |
| graphene | `origin/commit0_combined` | `ec2d3f476a7fa94a7a2ffc3c145422b0c3b7e71a` | 11 |
| imapclient | `origin/commit0_combined` | `7ca5a23640bcb0b102673eaaf5eaa6e7fcebd76b` | 5 |
| pexpect | `origin/commit0_combined` | `21b5908ea5b9b38ca996fec50dc449bff5c2c82f` | 1 |
| flask | `origin/commit0_combined` | `af126af63a288df1d4edfe07e82a3b241aa4567a` | 11 |
| python-rsa | `origin/commit0_combined` | `228b947d61f06612107205ab369a017ff63f9a8f` | 0 |
| cookiecutter | `origin/commit0_combined` | `c7a8c70a666270053d848f5664413af1af7a987f` | 0 |
| apache-tvm-20018 | merged PR first parent | `302aaf9f961a6e0a2c5cc23dc87e51fbaabd1e42` | 1 |
| apache-tvm-20073 | merged PR first parent | `62fb780bb0a8da62e3808f60a2343f6fd1d4b01f` | 1 |
| apache-tvm-20107 | merged PR first parent | `0468e13a1450a4429758003612aa2b3d080c1f13` | 1 |
| apache-tvm-20153 | merged PR first parent | `a35aca6a0ae5a61c486cb9a61c36b09be45f81af` | 2 |

## Claims to avoid or qualify

1. Do not claim that all 20 tasks received two completed independent human
   annotations. The unified release gate is one human plus a separate
   automated audit; only cachetools has a completed optional second-human
   provenance record.
2. Do not claim that task construction is fully automated. Artifact generation
   and consistency checks are protocolized and automated, but semantic
   inclusion remains a human decision.
3. Do not present source-branch names as task categories. Historical source
   refs include `commit0`, `origin/commit0_combined`, and merged-PR first
   parents, but all 20 released items are uniformly adapted, pinned incomplete
   repository tasks.
4. Do not describe overlays as fixes. They are collection/bootstrap patches,
   are checksum-recorded, and are forbidden from implementing scoped benchmark
   behavior.
5. Do not say that dependency labels were derived from model failures. Model
   trajectories are not admissible for checker selection or failure
   construction; exploratory runs are non-release evidence only.
6. Do not call the current release stable. Construction and human-review gates
   are complete, but the release remains a community preview because the
   checksum-validated official baseline registry currently contains zero
   bundles.
7. Do not conflate Dependency Checkers with the final evaluator. Checkers expose
   contract-level state; the public full evaluator determines final task
   correctness.

## Canonical evidence locations

- Unified v0.4 release index: `manifests/release/v0.4/official_tasks.json`
- Unified per-task evidence: `manifests/release/v0.4/task_index.json`
- Added-task registry: `configs/tasks/pr_hard_candidates.v0.4.json`
- Added-task records: `manifests/candidates/pr_hard_v0.4/`
- Added-task human reviews: `manifests/annotations/pr_hard_v0.4/`
- Historical v0.3 task selection: `configs/tasks/commit0_official_tasks.v0.3.json`
- Pinned bases and overlays: `configs/tasks/commit0_curated_tasks.v0.3.json`
- Public source repositories: `configs/tasks/commit0_repositories_full.v0.3.json`
- Task records: `manifests/pilot/v0.3/tasks/`
- Scenario records: `manifests/pilot/v0.3/scenarios/`
- Evaluator and quality records: `manifests/pilot/v0.3/quality/`
- Dependency labels and checkers: `manifests/pilot/v0.3/metrics/`
- Human and automated review records: `manifests/annotations/asyncodebench_v0.3/`
- Generated official release index: `manifests/release/v0.3/official_tasks.json`
- Per-task release evidence: `manifests/release/v0.3/task_index.json`
- Construction protocol: `docs/design/COMMIT0_TO_ASYNCODEBENCH_PIPELINE_v0.1.md`
- Label rules: `docs/protocols/COMMIT0_DATA_AND_METRIC_LABEL_GUIDE_v0.3.md`
- Human-review policy: `docs/HUMAN_REVIEW.md`
- Dependency metric semantics: `docs/EVALUATION_METRICS.md`

## Reproduction checks used for this packet

```bash
.venv-benchmark/bin/python scripts/validate_pr_hard_human_reviews.py
.venv-benchmark/bin/python scripts/build_v04_release_index.py --check
.venv-benchmark/bin/python -m pytest -q tests/contracts
```

Observed results on 2026-08-29:

```text
Human review validation passed: 4/4 complete
v0.4 release index is current
164 passed
```
