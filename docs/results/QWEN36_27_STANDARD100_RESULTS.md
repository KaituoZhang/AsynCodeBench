# Qwen3.6-27B Results on AsynCodeBench

## Scope and admission

- Model: `openai/Qwen/Qwen3.6-27B`
- Tasks: 16 official tasks
- Runs: 64 selected task-protocol bundles
- Execution profile: `asyncodebench-v0.3-standard-100`
- Per-run validation: all selected bundles are valid and official-aggregate eligible
- Campaign status: **descriptive mixed-lineage aggregate**

The set is not a lineage-homogeneous official campaign because it spans 4 benchmark revisions and 3 generation-configuration hashes. The results can be used for descriptive analysis and figures, but the provenance caveat must remain visible.

## Aggregate results

| Protocol | Success | Pass | ADPR | Unresolved | DRE | DRS | CAIL | FSAR | IFR | SVR | MRR | Tokens | Runtime |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| single | 6/16 (37.5%) | 59.8% | 50.0% | 1.375 | 50.0% | 1.500 | 0.875 | 0.0% | 0.0% | N/A | N/A | 4.702M | 67.3 min |
| serial_specialists | 4/16 (25.0%) | 57.5% | 51.0% | 1.375 | 22.1% | 6.579 | 4.131 | 5.2% | 75.0% | 11.5% | 85.2% | 7.615M | 133.2 min |
| async_private | 2/16 (12.5%) | 44.6% | 20.8% | 2.250 | 13.6% | 9.850 | 5.756 | 17.7% | 87.5% | 31.8% | 40.9% | 7.576M | 109.5 min |
| caid_manager | 14/16 (87.5%) | 96.3% | 95.8% | 0.125 | 23.1% | 8.131 | 2.902 | 14.1% | 12.5% | 34.4% | 45.7% | 10.872M | 196.3 min |

## Per-task outcomes

Each cell is `success / pass rate / ADPR`.

| Task | Single | Serial | Async private | CAID |
| --- | ---: | ---: | ---: | ---: |
| cachetools | yes / 100.0% / 100.0% | yes / 100.0% / 100.0% | yes / 100.0% / 100.0% | yes / 100.0% / 100.0% |
| deprecated | yes / 100.0% / 100.0% | yes / 100.0% / 100.0% | no / 69.0% / 33.3% | yes / 100.0% / 100.0% |
| portalocker | yes / 100.0% / 100.0% | no / 72.5% / 66.7% | no / 20.0% / 0.0% | yes / 100.0% / 100.0% |
| tinydb | yes / 99.5% / 100.0% | no / 98.5% / 100.0% | no / 21.9% / 0.0% | yes / 99.5% / 100.0% |
| wcwidth | yes / 94.9% / 100.0% | yes / 94.9% / 100.0% | yes / 94.9% / 100.0% | yes / 94.9% / 100.0% |
| requests | no / 0.0% / 33.3% | no / 0.0% / 33.3% | no / 86.4% / 33.3% | yes / 94.7% / 100.0% |
| simpy | no / 71.3% / 33.3% | no / 90.0% / 100.0% | no / 56.0% / 0.0% | no / 82.0% / 66.7% |
| parsel | no / 19.2% / 0.0% | no / 11.5% / 0.0% | no / 18.8% / 0.0% | yes / 99.0% / 100.0% |
| filesystem_spec | no / 57.1% / 0.0% | no / 53.6% / 50.0% | no / 4.3% / 0.0% | yes / 95.7% / 100.0% |
| marshmallow | no / 27.3% / 0.0% | no / 26.0% / 0.0% | no / 0.0% / 0.0% | yes / 100.0% / 100.0% |
| graphene | no / 93.2% / 100.0% | no / 35.6% / 0.0% | no / 57.6% / 0.0% | yes / 98.3% / 100.0% |
| imapclient | no / 24.9% / 33.3% | no / 35.8% / 33.3% | no / 0.0% / 33.3% | yes / 100.0% / 100.0% |
| pexpect | no / 0.0% / 0.0% | no / 6.5% / 0.0% | no / 24.7% / 0.0% | yes / 100.0% / 100.0% |
| flask | no / 9.0% / 0.0% | no / 16.8% / 0.0% | no / 17.2% / 0.0% | no / 80.7% / 66.7% |
| python-rsa | yes / 100.0% / 100.0% | yes / 100.0% / 100.0% | no / 65.2% / 33.3% | yes / 100.0% / 100.0% |
| cookiecutter | no / 59.5% / 0.0% | no / 77.6% / 33.3% | no / 78.0% / 0.0% | yes / 96.6% / 100.0% |

## Provenance distribution

| Field | Value | Runs |
| --- | --- | ---: |
| Benchmark revision | `3d110b25df70adfe71b8ce06c259336691866377` | 54 |
| Benchmark revision | `6d2d1af74d09acd1376ca68d9df376c4fe5c0416` | 5 |
| Benchmark revision | `ddebb7d7b18c12eba63275df4c8b7350af392c69` | 4 |
| Benchmark revision | `e57a4a8f38908217d515a16af48048a7c1a61ede` | 1 |
| Generation configuration | `ca02abdfcddcd75f0802fd421972d3e05725fca174b6118dc64d1b8089c3c7ed` | 44 |
| Generation configuration | `14a6bec9d334f3678e6b0074e8144965a22d0c33ff4f99450962d4d8543e9021` | 16 |
| Generation configuration | `c502389667004bd9d7e04a8937c2cf08e7827905c212ce6274ade62690ad1d6b` | 4 |

## Exceptional evaluator outcomes

- `timeout`: 4 valid model-failure runs
- `collection_failed`: 1 valid model-failure runs
