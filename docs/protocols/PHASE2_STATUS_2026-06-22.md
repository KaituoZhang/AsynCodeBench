# Phase 2 qualification status — 2026-06-22

Specification: AsynCodeBench v0.2
Status: historical v0.2 phase record; superseded for implementation by
`SPECIFICATION_v0.3.md`

## Candidate pool

The current Phase 2 pool contains 24 tasks:

- 6 Commit0 candidates with complete public-ref evidence and local baseline
  measurements;
- 18 SWE-bench Verified candidates across 11 repositories with base-commit
  public evidence materialized.

Canonical index:

`manifests/candidates/phase2_candidate_index_v0.2.json`

## Commit0

Status: ready for genuinely independent annotation.

Answer-free work packets:

- `manifests/candidates/annotation_packets/commit0_v0.2/annotator_a.json`
- `manifests/candidates/annotation_packets/commit0_v0.2/annotator_b.json`

The files are templates for two different annotators. The same person or model
must not complete both packets.

## SWE-bench Verified

Official dataset:

`princeton-nlp/SWE-bench_Verified`

Frozen dataset revision:

`c104f840cc67f8b6eec6f759ebc8b2693d585d4a`

The local public metadata snapshot contains 500 tasks and structurally excludes
solution patch, test patch, hints, and PASS_TO_PASS content from every task
record.

Some official `problem_statement` values contain code suggestions or diffs
written in the public issue itself. These remain because they are part of the
official task statement. They are provenance-distinct from the dataset's
hidden `patch` and `test_patch` fields, which are not copied into task records.

The 18-task screen is preregistered as:

- official difficulty `15 min - 1 hour` or `1-4 hours`;
- public problem statement length at least 200 characters;
- 1–20 FAIL_TO_PASS targets;
- at most two tasks per repository;
- deterministic ranking by target count, issue length, and instance ID.

Status: base-commit materialization complete; pending official-environment
timing. The 11 official GitHub repositories have been partial-cloned locally,
and the 18 selected tasks are materialized at:

`manifests/candidates/swebench_verified_materialized18_v0.2.json`

The official SWE-bench harness is installed from the upstream repository under
`data/external/SWE-bench` and wrapped by:

`scripts/qualification_time_swebench_official.py`

The wrapper reuses the official Docker test specification and eval script for
timing, but writes only metadata, return code, duration, output digest, and
byte count. It does not copy official `patch`, `test_patch`, `hints_text`, raw
test output, or eval scripts into candidate manifests.

Current blocker: the active shell cannot access `/var/run/docker.sock`, even
with external execution approval. A Docker-enabled shell must run the timing
command before SWE-bench tasks can become `CandidateRecord` objects.

Smoke-test command:

```bash
PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
python scripts/qualification_time_swebench_official.py \
  --materialized manifests/candidates/swebench_verified_materialized18_v0.2.json \
  --output manifests/candidates/swebench_verified_timing_smoke_v0.2.json \
  --run-id phase2-swebench-timing-smoke-v0.2 \
  --limit 1
```

Full timing command after the smoke test passes:

```bash
PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
python scripts/qualification_time_swebench_official.py \
  --materialized manifests/candidates/swebench_verified_materialized18_v0.2.json \
  --output manifests/candidates/swebench_verified_timing18_v0.2.json \
  --run-id phase2-swebench-timing18-v0.2
```

## Phase 2 completion conditions

Phase 2 remains incomplete until:

1. SWE-bench base-commit evidence and official timing are recorded;
2. both sources have schema-valid candidate cards;
3. two genuinely independent annotators submit decisions;
4. disagreements are adjudicated;
5. agreement is reported;
6. a 10–20 task pilot manifest is frozen.

No simulator, baseline, oracle, replay, or model-serving work should proceed
before these conditions are satisfied.

This final restriction is retained only as a record of the v0.2 plan. Under
v0.3, the cachetools live vertical slice and task-driven framework
generalization may proceed alongside task/scenario curation; replay, oracles,
and learned policies remain deferred.
