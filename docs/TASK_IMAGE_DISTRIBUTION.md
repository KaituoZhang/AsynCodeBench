# Official Task Images

AsynCodeBench v0.4.1 distributes all 19 official tasks as Linux/AMD64 container
images. Historical Graphene source artifacts remain in the repository, but its
image is not part of the current official registry. The image layer is a
reproducibility and delivery mechanism only: it
does not change task statements, model-visible evidence, source states,
overlays, ownership, protocol schedules, Dependency Checkers, evaluators, or
execution budgets.

The authoritative inventory is
`configs/environments/official_task_images.v0.4.json`. Every official run uses
an immutable `repository@sha256:...` reference from that file. The familiar
version tags are discovery aliases, not reproducibility identifiers.

## User workflow

From a fresh checkout:

```bash
cd reproductions/async-swe-agents
uv run asyncodebench tasks
uv run asyncodebench images list
```

Pull one image before a run:

```bash
uv run asyncodebench images pull --task cachetools
uv run asyncodebench images pull --task apache-tvm-20018
```

Or prefetch all 19. This requires substantial disk space because the four
compiler tasks include a frozen native toolchain:

```bash
uv run asyncodebench images pull
```

All tasks use the same public namespace and CLI:

```bash
uv run asyncodebench run \
  --task asyncodebench:cachetools \
  --protocol all \
  --model "$LLM_MODEL"

uv run asyncodebench run \
  --task asyncodebench:apache-tvm-20018 \
  --protocol all \
  --model "$LLM_MODEL"
```

The harness still records source-specific provenance internally. Users do not
need to select a separate benchmark or dataset lane.

## Safe local cleanup

The benchmark CLI can remove downloaded task images without touching run
bundles or anything under `outputs/`. By default it also removes OpenHands
agent-server images derived from the selected task images, because those
derived images otherwise keep the task layers on disk.

Preview the exact matches first:

```bash
uv run asyncodebench images remove --all --dry-run
```

Remove one task and its matching OpenHands derived images:

```bash
uv run asyncodebench images remove --task apache-tvm-20018
```

Remove all 19 official task images after a campaign:

```bash
uv run asyncodebench images remove --all --yes
```

Use `--base-only` to leave OpenHands derived images in place. The command
matches only exact official registry references and OpenHands tags that encode
the complete selected source-image repository. It does not run `docker system
prune`, does not use forced removal, and Docker will refuse to delete an image
that is still required by a running container. Model-server images, unrelated
Docker projects, source checkouts, and experiment outputs are outside its
scope.

The four compiler task images occupy about 9.04 GB after shared-layer
deduplication. Allow at least 25--30 GB free for sequential compiler runs and
about 60 GB when running all four concurrently, because temporary native build
products and OpenHands derived images require additional working space.

## Why the four compiler images are safe

The compiler images are built only from a separate immutable snapshot made by
`scripts/snapshot_pr_hard_container_inputs.py`. Each snapshot contains:

- one clean, synthetic model-visible Git commit with no remote;
- checksum-recorded answer-free public test overlays already present in the
  qualified task;
- the task-local Python 3.11, LLVM 18, CMake, Ninja, Cython, and `tvm-ffi`
  runtime used during qualification;
- a provenance manifest recording the base SHA, seed commit and tree, lockfile
  hashes, and public overlay hashes.

It excludes the production fix, upstream Git history, transient build trees,
pytest caches, Python bytecode, model outputs, and prior experiment results.
The active `.cache/pr_hard_runtime` directories are never Docker build
contexts and are never modified by the snapshot or build commands.

Inside an image, the frozen runtime is located at:

```text
/opt/asyncodebench/runtime/
  seed/
  env/
  container_backup_manifest.json
```

The locked OpenHands `source-minimal` image is derived from this task image.
At run time, the harness copies `seed/` to a disposable workspace, creates a
new working branch, and keeps `env/` immutable. Native TVM build products go
to an isolated, per-run host cache and are deleted after the run.

## Compatibility with completed experiments

Container distribution is additive. In particular:

- the existing 16 image contents are unchanged; v0.4 records their current
  registry digests;
- the historical raw TVM entry point still defaults to `runtime_backend=local`;
- `PR_HARD_RUNTIME_BACKEND=local` keeps the previous reconstruction and mount
  behavior in all four TVM convenience scripts;
- no existing output directory, run bundle, task/scenario/metrics/quality
  manifest, evaluator, checker selector, prompt, or execution profile is
  rewritten;
- the v0.3 and v0.4 release indexes are not regenerated merely to add image
  distribution metadata, so old run-bundle checksum validation remains stable.

New official v0.4 runs default to the published container backend and record
the exact image digest in `run_metadata.json`. Results created with the earlier
local backend remain valid evidence of the same qualified task content; they
are not retroactively rewritten.

## Independent source reconstruction fallback

The image is the convenient default, while source reconstruction remains the
independent audit path:

```bash
python scripts/prepare_pr_hard_runtime.py \
  --task-id pr-hard:apache-tvm-20018 \
  --runtime-root .cache/pr_hard_runtime/v0.4/apache-tvm-20018

cd reproductions/async-swe-agents
PR_HARD_RUNTIME_BACKEND=local \
PR_HARD_RUNTIME_ROOT="$PWD/../../.cache/pr_hard_runtime/v0.4/apache-tvm-20018" \
scripts/run_pr_hard_20018_all_protocols_env.sh
```

This fallback rebuilds from the same pinned TVM SHA, lock files, and public
overlays; it does not download or reveal a gold patch.

## Maintainer publication workflow

Create a new snapshot in a destination that does not exist:

```bash
python scripts/snapshot_pr_hard_container_inputs.py \
  --source-root .cache/pr_hard_runtime/v0.4 \
  --backup-root /absolute/read-only/backup/container-release-YYYYMMDD
```

Build without modifying the registry:

```bash
python scripts/manage_task_images.py build \
  --backup-root /absolute/read-only/backup/container-release-YYYYMMDD \
  --result-json /absolute/path/build-results.json
```

Validate the local images against the immutable snapshot:

```bash
python scripts/verify_pr_hard_image_equivalence.py \
  --backup-root /absolute/read-only/backup/container-release-YYYYMMDD
```

After authenticating to GHCR, publish, record the returned remote digests in
the registry, and run both remote and repository checks:

```bash
python scripts/manage_task_images.py build \
  --backup-root /absolute/read-only/backup/container-release-YYYYMMDD \
  --push \
  --result-json /absolute/path/published-results.json

python scripts/manage_task_images.py check
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q tests/contracts
```

The four GHCR packages must be public so anonymous collaborators can pull by
digest. Publishing a new tag never permits changing an existing digest in a
released registry without a new benchmark patch release.

## Design precedent

This layout follows established benchmark practice: separate immutable task
environments from evaluation logic, prefer pulling prebuilt images, preserve a
local build fallback, and validate image identity before execution. It also
uses the registry digest—not a mutable tag—as the actual runtime contract.
