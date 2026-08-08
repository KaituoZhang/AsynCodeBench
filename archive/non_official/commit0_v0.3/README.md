# Non-Official Commit0 v0.3 Artifacts

This directory stores task artifacts that were constructed during development
but are not part of the official AsynCodeBench v0.3 release set.

Archived tasks:

- `dulwich`: removed from the official v0.3 release after execution review;
  retained for audit and possible future revision.
- `chardet`: scratch/stress artifact that was not in the user-provided official
  candidate list.
- `python-progressbar`: excluded after suitability review for the current
  release.

The former Dulwich final-quality note is retained at
`docs/audits/COMMIT0_DULWICH_FINAL_QUALITY_CHECK_v0.3.md` inside this archive.

These files are retained for auditability only. Do not include them in official
v0.3 evaluation, model runs, aggregate metrics, or paper tables unless a later
release explicitly promotes them.

The official v0.3 task list is:

```text
configs/tasks/commit0_official_tasks.v0.3.json
```
