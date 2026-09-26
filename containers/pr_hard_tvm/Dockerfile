# syntax=docker/dockerfile:1.7

# Keep the qualified host ABI while pinning the mutable Ubuntu tag by digest.
FROM ubuntu:22.04@sha256:2edbbc5dc405e9612ba3584ce95480277e3eb374407b5505fe26f17df77c7dbc

ARG TASK_ID
ARG PUBLIC_TASK_ID
ARG BASE_SHA
ARG SEED_COMMIT
ARG SEED_TREE
ARG BACKUP_MANIFEST_SHA256
ARG SOURCE_URL=https://anonymous.invalid/AsynCodeBench
ARG REVISION=unknown

LABEL org.opencontainers.image.title="AsynCodeBench ${PUBLIC_TASK_ID}" \
      org.opencontainers.image.description="Answer-free Apache TVM task runtime for AsynCodeBench v0.4" \
      org.opencontainers.image.source="${SOURCE_URL}" \
      org.opencontainers.image.revision="${REVISION}" \
      org.opencontainers.image.version="0.4.0" \
      org.opencontainers.image.licenses="Apache-2.0" \
      org.asyncodebench.task-id="${PUBLIC_TASK_ID}" \
      org.asyncodebench.source-task-id="${TASK_ID}" \
      org.asyncodebench.base-sha="${BASE_SHA}" \
      org.asyncodebench.seed-commit="${SEED_COMMIT}" \
      org.asyncodebench.seed-tree="${SEED_TREE}" \
      org.asyncodebench.backup-manifest-sha256="${BACKUP_MANIFEST_SHA256}" \
      org.asyncodebench.model-visible-gold="false" \
      org.asyncodebench.model-visible-history="false"

ENV ASYNCODEBENCH_PR_HARD_RUNTIME_ROOT=/opt/asyncodebench/runtime \
    PATH=/opt/asyncodebench/runtime/env/bin:${PATH}

# The build context is an immutable snapshot produced by
# scripts/snapshot_pr_hard_container_inputs.py.  Numeric ownership matches the
# OpenHands user created by the locked agent-server build (uid/gid 10001).
COPY --chown=10001:10001 seed/ /opt/asyncodebench/runtime/seed/
COPY --chown=10001:10001 env/ /opt/asyncodebench/runtime/env/
COPY --chown=10001:10001 container_backup_manifest.json \
    /opt/asyncodebench/runtime/container_backup_manifest.json

# The snapshot itself is read-only.  The image copy may be made writable for
# the OpenHands user because setup_workspace copies it to a disposable task
# worktree.  The frozen environment remains immutable.
RUN chmod -R u+w /opt/asyncodebench/runtime/seed \
    && test -x /opt/asyncodebench/runtime/env/bin/python \
    && test -x /opt/asyncodebench/runtime/env/bin/cmake \
    && test -x /opt/asyncodebench/runtime/env/bin/ninja \
    && test -x /opt/asyncodebench/runtime/env/bin/llvm-config \
    && /opt/asyncodebench/runtime/env/bin/python -c \
       "import importlib.metadata as m; assert m.version('pytest-json-report') == '1.5.0'; assert m.distribution('apache-tvm-ffi')" \
    && /opt/asyncodebench/runtime/env/bin/llvm-config --version | grep -Fx 18.1.8

WORKDIR /
