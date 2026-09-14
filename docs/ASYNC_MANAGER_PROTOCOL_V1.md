# AsynCodeBench Online Async-Manager Protocol v1

## Status

`async_manager` is the fifth official protocol in the public AsynCodeBench
protocol registry. It is built additively on the frozen task and evaluation
contracts and does not replace or alter the four earlier protocol identifiers:

- `single`
- `serial_specialists`
- `async_private`
- `caid_manager` (reported in papers as **Async-RO-Manager**)

The earlier `caid_manager_repair` extension remains a post-hoc final-repair
ablation. It is not the online Async-Manager described here.

## Execution model

The online manager is one persistent logical manager. Under normal execution it
uses one model conversation; if a remote transport session becomes terminal,
the harness records and closes that session, then recovers the same manager over
the same private worktree. It first performs read-only analysis and
manifest-constrained delegation. Specialists then run in the same private
worktrees and under the same ownership rules as the released CAID condition.
After every specialist integration attempt:

1. the harness records the specialist integrated-workspace checkpoint;
2. the manager receives the artifact, merge, and checker evidence;
3. the manager may edit its private worktree within the union of production
   scopes;
4. the harness validates and commits the patch;
5. an accepted state-changing patch is fast-forwarded into the integrated
   workspace;
6. the harness records a manager integrated-workspace checkpoint; and
7. normal feedback, retry, and assignment scheduling resumes.

The manager never writes directly to the integrated repository or specialist
worktrees. This makes every accepted change attributable to a patch, base
commit, manager commit, and pair of integration checkpoints.

## Metric compatibility

Final Success Rate, final test pass rate, and ADPR use the unchanged evaluator,
dependency manifests, and final integrated workspace. DRS, SCS, and RC continue
to use ordered integrated-workspace checkpoints. Private drafts and no-change
manager decisions are excluded from that sequence; accepted manager patches
create genuine additional integration states.

Because this protocol can create more integration opportunities, publications
must report checkpoint count, normalized DRS/SCS/RC, total model calls, tokens,
and wall-clock runtime together. These trajectory metrics measure logical
protocol progress, not raw latency.

## Security and integrity boundaries

- Manager shell commands use an audited read-only allowlist.
- File-editor mutations require an explicit intervention phase.
- Writable paths are derived only from the frozen active scenario.
- Tests, checkers, manifests, evaluators, `.git`, and out-of-scope paths are
  protected.
- Model network access inherits the task's existing network policy.
- The harness owns commits and uses verified fast-forward integration.
- Existing output directories remain immutable.
- Formal runs require clean, committed execution sources.
- Frozen legacy execution engines are checked against base revision `73c9877`
  before execution.
- Costs and tokens are summed across all recovered manager transport sessions.

## Reproduction

See
`reproductions/async-swe-agents/protocols/async_manager/README.md` for the
single-task, sharded 20-task, validation, and campaign-summary commands. Every
completed bundle snapshots the protocol profile and exact source files with
SHA-256 hashes.

## Publication naming

Recommended display labels are:

| Internal ID | Display label | Role |
| --- | --- | --- |
| `caid_manager` | Async-RO-Manager | online coordination, no production edits |
| `caid_manager_repair` | Async-RO-Manager + Final Repair | post-hoc repair ablation |
| `async_manager` | Async-Manager | online coordination and scoped intervention |

`configs/evaluation/protocol_registry.v1.json` gives these five protocols equal
public status. The old four-protocol execution profile and release-index
checksums remain unchanged so historical bundles continue to validate. New
`async_manager` runs use `official_execution_profile.v3.json` and are eligible
for the official five-protocol aggregate when their standard run bundle passes.
The aggregate tool explicitly admits the registered v2/v3 profile pair: the
four frozen cells retain v2 provenance and only the new Async-Manager cell uses
v3, so adding this protocol does not require rerunning completed experiments.
