# Gemma 4 26B A4B Results on AsynCodeBench

## Scope

This document records the paper-facing summary of the validated Gemma 4 26B
A4B experiment completed with the community-ready AsynCodeBench harness.

- Model: `openai/google/gemma-4-26B-A4B-it`
- Model tag: `gemma4-26b-a4b-v2`
- Runner revision: `ddebb7d7b18c12eba63275df4c8b7350af392c69`
- OpenHands server revision: `944284310d9a5f1ccad0ef8c2d7c4c38342b9952`
- Execution profile: `asyncodebench-v0.3-standard-100`
- Protocols: `single`, `serial_specialists`, `async_private`, `caid_manager`
- Tasks: all 16 official AsynCodeBench tasks
- Runs: 64 task-protocol combinations

The 60 non-Portalocker runs use run ID
`oh1292_hostportfix_ddebb7d_r02`. The four Portalocker runs use the isolated
retry ID `oh1292_hostportfix_ddebb7d_portalocker_r03`.

All 64 bundles report valid instrumentation, a matched official execution
profile, complete provenance, and eligibility for the official aggregate.
None of the recorded agent attempts reached the 100-response limit, so the
observed failures are not explained by an insufficient iteration cap.

## Aggregate Results

The pass rate is macro-averaged over tasks. ADPR is the mean final integrated
dependency pass rate. Lower values are better for FSAR, SVR, DRS, CAIL,
tokens, and runtime. Unresolved DRS and CAIL values use the run-local `T + 1`
penalty. Raw DRS and CAIL means should be interpreted with their checkpoint
horizon because protocols expose different numbers of checkpoints.

| Protocol | Final success | Mean pass rate | Mean ADPR | Penalized DRS | Penalized CAIL | FSAR | SVR | Mean tokens | Mean runtime |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Single | 0/16 | 22.2% | 1.3% | 1.99 | 1.98 | 0.0% | N/A | 0.55M | 12.8 min |
| Serial specialists | 0/16 | 22.2% | 2.1% | 7.88 | 7.76 | 45.3% | 27.6% | 3.11M | 44.3 min |
| Async private | 0/16 | 15.6% | 1.3% | 10.93 | 10.90 | 62.0% | 29.7% | 3.07M | 26.5 min |
| CAID manager | 0/16 | 26.0% | 1.3% | 10.80 | 10.53 | 52.2% | 36.3% | 4.85M | 46.3 min |

Because the model is locally served, API cost is zero and is not a meaningful
efficiency comparison. Tokens, model calls, and wall-clock runtime are the
relevant efficiency measurements.

## Per-Task Functional and Dependency Results

Each cell reports `final pass rate / final ADPR`.

| Task | Single | Serial specialists | Async private | CAID manager |
| --- | ---: | ---: | ---: | ---: |
| cachetools | 80.5% / 20.0% | 71.2% / 0.0% | 80.5% / 20.0% | 82.8% / 20.0% |
| deprecated | 9.9% / 0.0% | 21.6% / 0.0% | 9.9% / 0.0% | 40.4% / 0.0% |
| portalocker | 27.5% / 0.0% | 27.5% / 0.0% | 20.0% / 0.0% | 27.5% / 0.0% |
| tinydb | 7.0% / 0.0% | 14.9% / 0.0% | 6.0% / 0.0% | 6.0% / 0.0% |
| wcwidth | 63.2% / 0.0% | collection failure / 0.0% | 0.0% / 0.0% | 63.2% / 0.0% |
| requests | 24.3% / 0.0% | 26.7% / 33.3% | 24.7% / 0.0% | 22.6% / 0.0% |
| simpy | 59.0% / 0.0% | 60.4% / 0.0% | evaluator timeout / 0.0% | 61.2% / 0.0% |
| parsel | 10.1% / 0.0% | 13.5% / 0.0% | 18.3% / 0.0% | 19.7% / 0.0% |
| filesystem_spec | 2.9% / 0.0% | 11.4% / 0.0% | 5.0% / 0.0% | 17.1% / 0.0% |
| marshmallow | 12.1% / 0.0% | 12.9% / 0.0% | 24.1% / 0.0% | collection failure / 0.0% |
| graphene | 22.4% / 0.0% | 17.2% / 0.0% | 19.0% / 0.0% | 17.2% / 0.0% |
| imapclient | 1.3% / 0.0% | 0.0% / 0.0% | 0.0% / 0.0% | 4.4% / 0.0% |
| pexpect | 18.2% / 0.0% | 19.5% / 0.0% | 18.2% / 0.0% | 18.2% / 0.0% |
| flask | 0.4% / 0.0% | 0.4% / 0.0% | 0.4% / 0.0% | 1.6% / 0.0% |
| python-rsa | 13.6% / 0.0% | 36.4% / 0.0% | 18.2% / 0.0% | 31.8% / 0.0% |
| cookiecutter | 3.0% / 0.0% | 20.8% / 0.0% | 5.9% / 0.0% | 3.0% / 0.0% |

For SimPy, the denominator excludes the 11 tests deselected by the canonical
evaluator command. Synthetic timeout or collection-failure summaries are not
interpreted as ordinary pass fractions.

## Main Findings

1. Final success alone has a complete floor effect: all four protocols score
   zero. The dependency and process metrics still expose different failure
   mechanisms.
2. Async private uses approximately the same number of tokens as serial
   specialists and reduces mean wall-clock time by about 40%, demonstrating
   real concurrency. This speedup is accompanied by a lower pass rate, a 62.0%
   failed-subagent-attempt rate, and more scope violations.
3. CAID manager obtains the highest partial pass rate but uses about 8.8 times
   the tokens of single-agent execution. It also has the highest scope
   violation rate and does not convert local progress into final dependency
   closure.
4. Across each protocol, only one of the 47 labeled dependency points passes
   at the final integrated checkpoint. Partial implementation therefore does
   not imply successful producer-consumer integration.
5. Relative to the recorded stripped-task initial states, the model increases
   the raw number of passing tests on 10 single, 11 serial, 9 async-private,
   and 11 CAID tasks. The model is making local coding progress, but that
   progress rarely closes the benchmark's cross-agent contracts.

## Exceptional Outcomes and Reporting Rules

- `simpy/async_private` is a valid model failure caused by a 900-second final
  evaluator timeout. Report final success as zero and evaluator timeout as
  one; do not treat its synthetic `0/1` report as an ordinary pass fraction.
- `marshmallow/caid_manager` is a valid model-induced collection failure.
- `wcwidth/serial_specialists` contains three collector errors caused by a
  missing `wcwidth/wcwidth.py`. The current bundle labels this as a generic
  failure because pytest omitted collector errors from its summary. The raw
  report is sufficient to classify it as a collection failure in derived
  analysis; no model rerun is required.
- Task-macro averages should be used in the paper. Micro-averaging raw tests
  would overweight large test suites and would be distorted by synthetic
  timeout and collection-failure reports.

## Paper Use

This batch is suitable as a validated local-model baseline and as evidence for
asynchronous coordination failure. It should not be the paper's only model:
zero final successes limit the discriminative value of final success rate.
Claims about protocol superiority should also remain descriptive until repeat
runs or additional models establish variance.

The immutable run artifacts are under:

```text
reproductions/async-swe-agents/outputs/asyncodebench/v0.3/
  gemma4-26b-a4b-v2/<task>/<protocol>/<run_id>/
```

Every selected run directory contains `run_bundle.json`, `report.json`,
`process_metrics_summary.json`, `strict_dependency_metrics.json`, manifest
snapshots, model event logs, and the final repository archive.
