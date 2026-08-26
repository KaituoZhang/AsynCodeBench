# Scripts

This directory contains thin command-line entry points. Scripts parse
arguments, load configuration, call library or pipeline functions, and report
results. Reusable logic must live under `src/asyncodebench/`.

`prepare_pr_hard_runtime.py` is the candidate-package exception: it performs a
one-time, checksum-validated external-source and toolchain materialization for
`pr-hard:apache-tvm-20153`. Generated source and environments remain under the
ignored `.cache/pr_hard_runtime/` tree; only the reconstruction recipe,
manifests, locks, and public test overlays are checked in.
