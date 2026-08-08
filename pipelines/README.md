# Pipelines

Reproducible multi-stage workflows belong here. Planned groups are:

- `audit/`: predecessor-infrastructure and leakage audits;
- `qualification/`: candidate screening and task-card production;
- `trace/`: empirical latency and resource trace collection;
- `pilot/`: smoke, phenomenon, and locked Go/No-Go runs;
- `release/`: final benchmark materialization and evaluation.

Pipeline logic should call `asyncodebench` library APIs. It should not define
new event or evaluation semantics.
