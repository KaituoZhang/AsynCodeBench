# TVM task containers

These images are distribution snapshots for the four compiler-scale tasks in
the AsynCodeBench v0.4 official task set.  They do not change task content.

Build contexts must be created with
`scripts/snapshot_pr_hard_container_inputs.py`; the Dockerfile never reads or
modifies the active runtime.  Each context contains a clean one-commit seed,
the frozen task-local toolchain, and an answer-free provenance manifest.

The published images are base images for the locked OpenHands
`source-minimal` agent-server target.  At run time the harness copies
`/opt/asyncodebench/runtime/seed` into a disposable workspace and keeps
`/opt/asyncodebench/runtime/env` immutable.

Use `scripts/manage_task_images.py` to build, validate, push, pull, or check
the image registry.  Local source reconstruction remains available as the
independent audit fallback.
