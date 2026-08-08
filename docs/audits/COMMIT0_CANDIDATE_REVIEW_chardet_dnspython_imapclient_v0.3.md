# Commit0 candidate review: chardet, dnspython, imapclient — v0.3

Date: 2026-06-24  
Protocol: `docs/protocols/COMMIT0_DATA_EXAMPLE_GUIDE_v0.3.md`  
Purpose: continue the Commit0 candidate screen for AsynCodeBench v0.3.

This review only decides task-construction suitability. It is not a model
baseline, not a release annotation, and not a gold-patch analysis.

## Decision summary

| Candidate | Decision | AsynCodeBench fit | Main reason |
| --- | --- | --- | --- |
| `commit0:imapclient` | promote to conditional construction queue | `partially_parallelizable` | Natural parser/typed-response contract consumed by high-level IMAP client APIs, with plausible stale interface assumptions. Needs a small import-bootstrap decision before release. |
| `commit0:chardet` | defer raw task; keep as conditional backlog subset | `partially_parallelizable` only after curation | There is a real prober/detector dependency chain, but the raw stripped task is dominated by charset model tables and detector/prober reconstruction. |
| `commit0:dnspython` | defer or reject for v0.3 main set | unclear / too broad | The task spans DNS message/rdata/resolver/async/DNSSEC/DoQ/zone layers and fails collection on a foundational immutable decorator. Too much protocol surface for the first benchmark slice. |

Recommended queue update:

```text
keep in formal/near-formal construction queue:
requests, simpy, dulwich, parsel, filesystem_spec, marshmallow, graphene, imapclient

keep as conditional backlog:
chardet

defer/reject for v0.3 main:
dnspython
```

## Evidence used

Local repositories:

```text
data/repos/commit0/chardet
data/repos/commit0/dnspython
data/repos/commit0/imapclient
```

Public stripped ref inspected:

```text
origin/commit0_combined
```

No candidate was qualified from a reference patch. Completed/default branches
were only used as a rough size sanity check, not as decomposition evidence.

## `commit0:imapclient`

### Observed task shape

The stripped tree has incomplete pieces in:

```text
imapclient/util.py
imapclient/datetime_util.py
imapclient/fixed_offset.py
imapclient/imap_utf7.py
imapclient/response_lexer.py
imapclient/response_parser.py
imapclient/response_types.py
imapclient/imapclient.py
```

Relevant public tests include:

```text
tests/test_response_lexer.py
tests/test_response_parser.py
tests/test_imapclient.py
tests/test_search.py
tests/test_folder_status.py
tests/test_store.py
tests/test_datetime_util.py
tests/test_imap_utf7.py
tests/test_util_functions.py
```

The key natural dependency is:

```text
response_lexer / response_parser / response_types
    -> typed parsed IMAP response contract
    -> IMAPClient high-level commands and response normalization
```

This is not an arbitrary file split. The upper-layer client code imports and
depends on parser behavior:

```text
parse_response
parse_message_list
parse_fetch_response
SearchIds
Envelope
Address
BodyData
```

### Why it fits AsynCodeBench

This task can test stale teammate work directly:

- One agent implements parser return shapes and typed response objects.
- Another agent implements high-level client methods against an assumed parser
  contract.
- If parser semantics change while the high-level implementation is in flight,
  the merge can be textually clean but semantically inconsistent.

Likely async failure modes:

```text
SearchIds list vs tuple behavior mismatch
FETCH response dict key mismatch: sequence id vs UID
bytes/str normalization mismatch
datetime timezone normalization mismatch
Address / Envelope object construction mismatch
high-level folder/search/store methods duplicating parser logic
```

This makes it a good candidate for the `Interface Dependency` class.

### Caveat: collection bootstrap

Raw stripped collection currently fails because `imapclient.util` lacks
`assert_imap_protocol`, which is imported by `response_lexer.py`.

Observed collection failure:

```text
ImportError: cannot import name 'assert_imap_protocol' from 'imapclient.util'
```

This does not make the candidate unusable, but it means release construction
must choose one of two paths:

1. include `util.py` as a small first subproblem in the task; or
2. apply a checksum-recorded import-bootstrap overlay containing only generic
   helpers required for collection.

The second path needs annotator review because `to_bytes`, `to_unicode`,
`assert_imap_protocol`, and `chunk` are small but still behavioral helpers.
They are probably acceptable as infrastructure only if the released task is
explicitly about parser/client integration rather than generic utility
implementation.

### Recommendation

Promote `imapclient` to the construction queue as:

```text
task family: Interface Dependency
working task id: commit0:imapclient_response_client
qualification label: partially_parallelizable
status: candidate_construction_queue
release blocker: import-bootstrap or util-subtask decision
```

Suggested subproblem split:

```text
Agent A:
  response_lexer.py
  response_parser.py
  response_types.py

Agent B:
  imapclient.py high-level methods consuming parsed responses
  search/fetch/folder/status/store behavior

Shared contract:
  parser output shapes, bytes/str normalization, SearchIds.modseq,
  Envelope/Address/BodyData construction, UID-vs-message-id semantics
```

## `commit0:chardet`

### Observed task shape

The stripped tree has a recognizable chain:

```text
charsetprober.py
  -> sbcharsetprober.py
  -> sbcsgroupprober.py
  -> universaldetector.py
```

The public tests collect cleanly:

```text
python -m pytest --collect-only -q
collected 381 items
```

The first observed raw failure is a missing detector property:

```text
AttributeError: 'UniversalDetector' object has no attribute 'input_state'
```

### Why raw `chardet` is not a good v0.3 main task

There is real dependency structure, but the full task is dominated by charset
model and distribution machinery:

```text
lang*model.py
*freq.py
chardistribution.py
charsetprober.py
sbcharsetprober.py
sbcsgroupprober.py
universaldetector.py
```

That makes the raw task likely to measure:

```text
statistical table reconstruction
encoding-specific heuristics
large detector/prober coverage
```

rather than asynchronous multi-agent coordination.

The task can be made useful only if curated into a smaller detector/prober
slice where the model tables are either already present or explicitly out of
scope. Without that curation, failures would be hard to attribute to stale
teammate work.

### Recommendation

Do not put raw `chardet` into the v0.3 main queue.

Keep as conditional backlog:

```text
task family: Interface Dependency
possible task id: commit0:chardet_detector_prober_subset
qualification label: partially_parallelizable after curation only
status: conditional_backlog
condition: construct a small answer-free subset around UniversalDetector and
           one or two prober families without making frequency-table recovery
           the main task
```

## `commit0:dnspython`

### Observed task shape

The stripped tree has many incomplete layers:

```text
dns/message.py
dns/rdata.py
dns/name.py
dns/resolver.py
dns/query.py
dns/asyncquery.py
dns/asyncresolver.py
dns/dnssec.py
dns/edns.py
dns/zone.py
dns/transaction.py
dns/quic/*
dns/dnssecalgs/*
```

Relevant public tests span:

```text
tests/test_async.py
tests/test_query.py
tests/test_resolver.py
tests/test_message.py
tests/test_rdata.py
tests/test_dnssec.py
tests/test_zone.py
tests/test_doh.py
tests/test_doq.py
```

Targeted collection on stripped state fails before reaching most functional
tests:

```text
ImportError: cannot import name 'immutable' from 'dns._immutable_ctx'
```

### Why it is weak for v0.3

`dnspython` has real layered architecture, but the candidate is too broad for
the first AsynCodeBench slice. It mixes:

```text
DNS wire-format parsing
rdata classes
resolver/query behavior
async backend behavior
DNSSEC and crypto-related algorithms
DoH/DoQ transport
zone/transaction behavior
```

This creates several problems:

- A small import-bootstrap overlay would not be enough; many foundational
  abstractions are stripped.
- Any async failure would be hard to attribute: it might come from protocol
  complexity, cryptography, transport behavior, or missing core immutable
  decorators.
- The task is likely to exceed the intended first-wave benchmark complexity.

### Recommendation

Defer or reject for v0.3 main construction:

```text
task family: not selected
qualification label: reject_or_defer
status: defer_or_reject_v0.3_main
```

A future highly curated subset might be possible, e.g.:

```text
commit0:dnspython_message_rdata_subset
commit0:dnspython_async_query_subset
```

but that would require substantial task-design work and should not be counted
as an immediate Commit0 candidate.

## Next candidates to review

Continuing the current repository order, the next unreviewed group is:

```text
virtualenv
pexpect
web3.py
```

