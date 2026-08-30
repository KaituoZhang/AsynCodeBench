# Scripts

This directory contains thin command-line entry points. Scripts parse
arguments, load configuration, call library or pipeline functions, and report
results. Reusable logic must live under `src/asyncodebench/`.

`prepare_pr_hard_runtime.py` is the candidate-package exception: it performs a
one-time, checksum-validated external-source and toolchain materialization for
the executable compiler/IR tasks 20018, 20073, 20107, and 20153. It can also
reconstruct compatible tasks from a local official TVM mirror when network
access is unavailable and the pinned recursive submodule contract matches.
Generated source and environments remain
under the ignored `.cache/pr_hard_runtime/` tree; only the reconstruction
recipe, manifests, locks, and public test overlays are checked in.
