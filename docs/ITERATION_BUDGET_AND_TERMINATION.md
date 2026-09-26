# Iteration Budget and Termination

AsynCodeBench measures one iteration as one model response, identified by a
unique `llm_response_id`. A response may contain multiple tool calls; tool calls
are not counted as separate iterations.

## Official Capability Profile

The current official profile is
[`official_execution_profile.v2.json`](../configs/evaluation/official_execution_profile.v2.json):

- hard cap: 100 model responses per model-facing agent run;
- normal completion: the agent invokes OpenHands `FinishTool`;
- safety completion: OpenHands stuck detection stops repetitive trajectories;
- hard-limit completion: `MaxIterationsReached` stops a run at 100 responses;
- CAID chat rounds: at most two rounds.

The cap is an upper bound, not a required trajectory length. A capable agent
that finishes in 18 responses stops at 18. The final evaluator is deliberately
not used as a continuous stopping oracle: exposing repeated hidden benchmark
evaluation during coding would change the task and leak evaluation feedback.

For CAID, the budget applies to each model-facing manager phase and each
specialist round. The run bundle records the exact protocol, phase, round, and
observed iteration counts so compute remains auditable. Public comparisons must
use the same profile for all models and protocols.

The preserved
[`official_execution_profile.v1.json`](../configs/evaluation/official_execution_profile.v1.json)
is the historical 30-response low-budget profile. Results produced under v1 are
valid historical evidence, but they must not be mixed into a v2 official
aggregate without reporting the profile difference.

## Recorded Stop Reasons

Native runs record `termination_reason` and `iteration_cap_hit` in completion
events and subagent results. Stable reasons include:

| Reason | Meaning | Valid model outcome? |
| --- | --- | --- |
| `agent_finish` | Agent invoked the normal finish mechanism | Yes |
| `iteration_limit` | Hard response cap was reached | Yes |
| `stuck_detected` | OpenHands detected a repetitive trajectory | Yes |
| `context_window_error` | Context configuration or condensation failed | No |
| `wall_clock_timeout` | Harness deadline expired | Usually no |
| `provider_or_transport_error` | API/server connection failed | No |
| `execution_error` | Another conversation execution error occurred | Review |
| `adapter_completed` | Third-party adapter returned normally | Yes |

A coding failure after a healthy model run remains benchmark evidence. A
provider, context, transport, or instrumentation failure must be rerun in a new
output directory and excluded from the official aggregate.

## Why the Default Is 100

Thirty responses was useful as a low-cost pilot but frequently truncated local
models before they could inspect, edit, test, and repair a repository. The
100-response capability profile reduces this truncation while preserving a
finite, reproducible compute ceiling. Early finish and stuck detection prevent
successful or clearly repetitive trajectories from consuming the full budget.
