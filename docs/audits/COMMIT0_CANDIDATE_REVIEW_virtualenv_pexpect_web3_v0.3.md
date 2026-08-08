# Commit0 candidate review: virtualenv, pexpect, web3.py — v0.3

Date: 2026-06-24  
Protocol: `docs/protocols/COMMIT0_DATA_EXAMPLE_GUIDE_v0.3.md`  
Purpose: continue the Commit0 candidate screen for AsynCodeBench v0.3.

This review only decides task-construction suitability. It is not a model
baseline, not a release annotation, and not a gold-patch analysis.

## Decision summary

| Candidate | Decision | AsynCodeBench fit | Main reason |
| --- | --- | --- | --- |
| `commit0:pexpect` | promote to conditional construction queue | `partially_parallelizable` | Strong interface dependency between core expect/search semantics and process transport implementations. Needs POSIX/dependency environment freeze and scoped evaluator selection. |
| `commit0:virtualenv` | backlog only | possible but high-cost | Real layered architecture, but raw task is broad, filesystem/interpreter/platform-heavy, and collection fails on low-level bootstrap helpers. |
| `commit0:web3.py` | backlog only / defer v0.3 main | possible but too broad | Strong sync/async/shared-base patterns exist, but raw task spans too many Ethereum/provider/contract/ENS layers and has heavy dependency/test setup cost. |

Recommended queue update:

```text
keep in formal/near-formal construction queue:
requests, simpy, dulwich, parsel, filesystem_spec, marshmallow, graphene,
imapclient, pexpect

keep as high-cost backlog:
virtualenv, web3.py
```

## Evidence used

Local repositories:

```text
data/repos/commit0/virtualenv
data/repos/commit0/pexpect
data/repos/commit0/web3.py
```

Public stripped ref inspected:

```text
origin/commit0_combined
```

Completed/default branches were used only for rough size sanity checks, not as
decomposition evidence.

## `commit0:pexpect`

### Observed task shape

The stripped task touches a compact but meaningful process-control stack:

```text
pexpect/expect.py
pexpect/spawnbase.py
pexpect/pty_spawn.py
pexpect/popen_spawn.py
pexpect/fdpexpect.py
pexpect/socket_pexpect.py
pexpect/run.py
pexpect/replwrap.py
pexpect/utils.py
```

There are also terminal-emulation side modules:

```text
pexpect/FSM.py
pexpect/ANSI.py
pexpect/screen.py
pexpect/pxssh.py
```

The core AsynCodeBench-relevant structure is:

```text
expect.py
  -> Expecter, searcher_string, searcher_re
  -> matching, EOF, TIMEOUT, buffer-window semantics

spawnbase.py
  -> compile_pattern_list, expect, expect_list, expect_exact, read/readline
  -> shared public API and state contract: before, after, match, buffer

pty_spawn.py / popen_spawn.py / fdpexpect.py / socket_pexpect.py
  -> transport-specific read_nonblocking, send, close, EOF/TIMEOUT behavior

run.py / replwrap.py
  -> high-level wrappers consuming spawn/expect behavior
```

This is a real interface dependency, not a file-count split.

### Test and environment observations

Public tests include:

```text
tests/test_expect.py
tests/test_popen_spawn.py
tests/test_run.py
tests/test_async.py
tests/test_filedescriptor.py
tests/test_socket.py
tests/test_replwrap.py
tests/test_FSM.py
tests/test_ansi.py
tests/test_screen.py
```

Temporary stripped collection in the current local environment failed because
`ptyprocess` is not installed:

```text
ModuleNotFoundError: No module named 'ptyprocess'
```

This is an environment dependency, not task leakage. The repository declares:

```text
setup.py: install_requires=['ptyprocess>=0.5']
requirements-testing.txt: ptyprocess, pytest, pytest-cov
```

If selected, the benchmark task must freeze a POSIX Python environment with
`ptyprocess` installed. The evaluator should avoid platform-fragile SSH,
interactive terminal, and visual-screen tests unless those are explicitly in
scope.

### Why it fits AsynCodeBench

`pexpect` is a good candidate for stale teammate work because the task exposes
a narrow but consequential contract:

```text
transport reads bytes
  -> core expecter searches buffers
  -> spawn API exposes before/after/match/EOF/TIMEOUT semantics
  -> high-level helpers depend on that contract
```

Likely async failure modes:

```text
transport returns str while expecter assumes bytes
freshlen/searchwindowsize semantics diverge between SpawnBase and Expecter
EOF/TIMEOUT handled as exceptions in one layer but match tokens in another
PopenSpawn queue behavior conflicts with SpawnBase buffering assumptions
encoding-aware pattern compilation mismatches transport output type
run() duplicates or bypasses SpawnBase semantics
```

These failures can be textually conflict-free but semantically invalid after
merge, which is exactly the benchmark target.

### Recommendation

Promote `pexpect` to conditional construction queue:

```text
task family: Interface Dependency
working task id: commit0:pexpect_expect_transport
qualification label: partially_parallelizable
status: candidate_construction_queue
release blockers:
  - freeze POSIX dependency environment with ptyprocess
  - select a scoped evaluator subset
  - avoid pxssh/ANSI/screen unless intentionally creating a second task
```

Suggested subproblem split:

```text
Agent A:
  pexpect/expect.py
  searcher_string
  searcher_re
  Expecter.expect_loop

Agent B:
  pexpect/spawnbase.py
  expect, expect_list, expect_exact, compile_pattern_list
  buffer/before/after/match state updates

Agent C or integration layer:
  pexpect/popen_spawn.py
  pexpect/pty_spawn.py
  pexpect/run.py
```

Suggested first evaluator focus:

```text
tests/test_expect.py
tests/test_popen_spawn.py
tests/test_run.py
selected tests from tests/test_async.py
```

Do not initially include:

```text
tests/test_pxssh.py
tests/test_screen.py
tests/test_ansi.py
tests/test_socket_pexpect.py
```

unless a later task is intentionally scoped around terminal emulation or socket
transport behavior.

## `commit0:virtualenv`

### Observed task shape

The stripped task spans many layers:

```text
src/virtualenv/discovery/*
src/virtualenv/create/*
src/virtualenv/seed/*
src/virtualenv/app_data/*
src/virtualenv/activation/*
src/virtualenv/run/session.py
src/virtualenv/util/path/*
src/virtualenv/util/lock.py
```

There is real dependency structure:

```text
discovery -> interpreter info
creator -> environment layout and pyenv_cfg
seeder -> wheel/bootstrap behavior
activators -> shell activation scripts
session/CLI -> integration contract
```

### Why it is not a good v0.3 main task

The current stripped collection fails before meaningful tests:

```text
ImportError: cannot import name 'make_exe' from 'virtualenv.util.path._permission'
```

This particular failure is a small bootstrap helper, but the broader task is
not small. A raw `virtualenv` benchmark would also involve:

```text
filesystem mutation
interpreter discovery
platform-specific executable permissions
embedded wheel/bootstrap behavior
shell activation templates
temporary directories and app-data caches
```

Those are valid software-engineering problems, but for the first
AsynCodeBench paper they would make failure attribution noisy. An async
failure could be caused by platform setup, filesystem behavior, seed package
handling, shell template differences, or actual stale teammate work.

### Recommendation

Do not promote raw `virtualenv` into the v0.3 main construction queue.

Keep as high-cost backlog:

```text
task family: Shared Abstraction / Interface Dependency
possible task id: commit0:virtualenv_discovery_creator_subset
qualification label: partially_parallelizable after heavy curation
status: high_cost_backlog
```

If revisited, scope it tightly around one of:

```text
discovery -> creator compatibility
app_data store -> seeder behavior
activation template generation
```

Do not start from the full raw repository task.

## `commit0:web3.py`

### Observed task shape

The stripped task is very large. Publicly implicated modules include:

```text
web3/_utils/abi.py
web3/_utils/contracts.py
web3/_utils/encoding.py
web3/_utils/events.py
web3/_utils/filters.py
web3/_utils/method_formatters.py
web3/_utils/normalizers.py
web3/contract/base_contract.py
web3/contract/contract.py
web3/contract/async_contract.py
web3/eth/base_eth.py
web3/eth/eth.py
web3/eth/async_eth.py
web3/providers/*
ens/*
```

There is a real and potentially valuable shared-abstraction structure:

```text
BaseContract / BaseContractFunction / BaseContractEvent
  -> synchronous Contract APIs
  -> asynchronous AsyncContract APIs

_utils/contracts / _utils/events / _utils/filters / _utils/normalizers
  -> shared ABI/event/filter semantics
  -> sync and async high-level contract behavior
```

### Why it is not a good v0.3 main task

The current environment cannot even collect a small targeted test subset
without extra dependencies:

```text
ModuleNotFoundError: No module named 'pytest_asyncio'
```

That dependency is fixable, but the bigger issue is task scope. The raw task
mixes:

```text
Ethereum ABI encoding
contract proxy APIs
sync and async APIs
provider behavior
ENS normalization
middleware/filter formatters
transaction defaults
integration tests with Ethereum tester / geth fixtures
large JSON normalization fixtures
```

This can produce genuine async-relevant failures, but it is too expensive and
too broad for the first curated Commit0 wave. It risks turning the benchmark
into a Web3 domain-knowledge test rather than a clean async multi-agent coding
test.

### Recommendation

Do not promote raw `web3.py` into the v0.3 main construction queue.

Keep as high-cost backlog:

```text
task family: Shared Abstraction / Interface Dependency
possible task id: commit0:web3_contract_sync_async_subset
qualification label: partially_parallelizable after heavy curation
status: high_cost_backlog
```

If revisited, the most defensible subset is:

```text
BaseContract shared ABI/function/event semantics
  -> Contract sync implementation
  -> AsyncContract async implementation
```

Avoid ENS normalization and full provider/integration tests in the first
benchmark release unless there is a separate task specifically scoped around
those modules.

## Next candidates to review

Continuing the current repository order, the next unreviewed group is:

```text
babel
geopandas
flask
```

