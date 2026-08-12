# Custom Agent Adapter

AsynCodeBench supports bring-your-own-agent evaluation without allowing the
agent to redefine the benchmark. The native harness still owns source
materialization, task and scenario manifests, private worktrees, communication
conditions, dependency ordering, scope validation, probes, integration, and the
final evaluator.

An adapter owns only one model-facing assignment execution.

## Public Contract

Implement `agents.AgentAdapter` and its synchronous `execute` method:

```python
from agents import AgentAdapter, AgentRunResponse


class MyCodingAgent(AgentAdapter):
    name = "my-coding-agent"

    def execute(self, request):
        # Drive your controller here. Use request.workspace.execute_command(...)
        # for shell tools in the assigned Docker workspace.
        # Edit and commit only within request.workspace_path.
        result = my_controller.run(
            instruction=request.instruction,
            workspace=request.workspace,
            workspace_path=request.workspace_path,
            writable_paths=request.writable_paths,
            test_targets=request.primary_test_targets,
        )
        return AgentRunResponse(
            error=result.error,
            cost=result.cost,
            prompt_tokens=result.input_tokens,
            completion_tokens=result.output_tokens,
            iterations=result.iterations,
            events=result.events,
        )
```

`AgentRunRequest` also supplies the public task ID, protocol, scenario ID,
assignment ID, round, labeled dependency contracts, model identifier, budget,
and output directory. The live `workspace` and optional `llm` objects are not
serialized into result metadata.

The adapter must not run or report the official final score. It may run targeted
tests for repair, but the harness independently validates changed paths,
integrates the artifact, runs dependency probes, and executes the manifest
evaluator.

`async_private` and `caid_manager` may call the same adapter instance from
multiple worker threads. Stateful adapters must protect shared state or override
`create_runner()` to provide isolated per-worker state.

## Load An Adapter

The import path uses `python.module:ClassName`. The class constructor receives
one `config` dictionary.

Adapter configuration is not persisted automatically because it may contain
credentials. Override `public_metadata()` to add only non-secret decoding,
prompt, or controller settings required for reproduction.

When the runner is installed outside the repository checkout, set
`ASYNCODEBENCH_ROOT` to the checkout root. `scripts/env.sh` exports this
automatically for the supported fresh-clone workflow.

```bash
cd reproductions/async-swe-agents
source scripts/env.sh

uv run asyncodebench run \
  --task asyncodebench:cachetools \
  --protocol async_private \
  --model "$LLM_MODEL" \
  --agent-import-path my_agents.cache_agent:CacheAgent \
  --agent-config-json '{"controller":"local"}' \
  --run-id custom-agent-v01
```

For all four protocols, pass the same adapter through the wrapper:

```bash
ASYNCODEBENCH_AGENT_IMPORT_PATH=my_agents.cache_agent:CacheAgent \
ASYNCODEBENCH_AGENT_CONFIG_JSON='{"controller":"local"}' \
ENV_FILE="$PWD/.env" \
MODEL_TAG=my-agent-model \
RUN_VERSION=custom-agent-v01 \
WORKSPACE_PORT_STRATEGY=auto \
scripts/run_asyncodebench_all_protocols_env.sh cachetools
```

The CAID manager remains a benchmark-controlled coordination protocol. The
custom adapter executes its coding assignments; delegation, reassignment,
scope checks, merge decisions, and dependency checkpoints remain in the
harness. This keeps agent comparisons on the same protocol semantics.

## Wiring Smoke Test

The included diagnostic adapter checks workspace access but intentionally does
not solve or commit code:

```bash
uv run asyncodebench run \
  --task asyncodebench:cachetools \
  --protocol single \
  --model test/no-model-call \
  --agent-import-path examples.agents.diagnostic_adapter:DiagnosticAgentAdapter \
  --output-dir /tmp/asyncodebench-adapter-smoke
```

The resulting coding failure is expected. A valid wiring smoke should still
produce evaluator, probe, process-metric, and `run_bundle.json` artifacts.

## Enforcement And Provenance

- `single` receives the full task workspace.
- `serial_specialists` receives manifest assignments in dependency order and
  completed upstream handoffs.
- `async_private` receives concurrent private worktrees with no in-flight
  upstream visibility.
- `caid_manager` receives manager-issued assignments validated against the
  active scenario manifest.
- Multi-agent artifacts that change files outside `writable_paths` are rejected
  before merge and recorded in `scope_validation.jsonl` or the corresponding
  CAID validation record.
- `run_metadata.json` records the adapter class, while
  `agent_adapter_executions.jsonl` records each non-OpenHands adapter call.
- `run_bundle.json` freezes artifact checksums and instrumentation validity.

Validate a completed run with:

```bash
uv run asyncodebench validate-run outputs/asyncodebench/v0.3/.../run-id
```
