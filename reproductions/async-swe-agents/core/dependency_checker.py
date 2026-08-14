"""Canonical public name for AsynCodeBench dependency-checker support.

The implementation remains in :mod:`core.dependency_probes` for backward
compatibility with existing runners and result artifacts.  This module is a
thin facade: it adds the public Dependency Checker terminology without
changing execution behavior.
"""

from core.dependency_probes import (  # noqa: F401
    default_metrics_path,
    load_metrics_manifest,
    next_checkpoint_step,
    probe_timeout_seconds,
    write_dependency_probe_checkpoint,
)

# New code may use the canonical name. Existing callers keep using the legacy
# symbol so old imports and run directories remain valid.
write_dependency_checker_checkpoint = write_dependency_probe_checkpoint

__all__ = [
    "default_metrics_path",
    "load_metrics_manifest",
    "next_checkpoint_step",
    "probe_timeout_seconds",
    "write_dependency_checker_checkpoint",
    "write_dependency_probe_checkpoint",
]
