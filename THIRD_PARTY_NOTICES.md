# Third-Party and Data Provenance Notices

## Scope of the AsynCodeBench License

The repository-level `LICENSE` applies to original AsynCodeBench source code,
documentation, schemas, manifests, evaluation scripts, harness adapters, and
non-solution bootstrap overlays, except where a file states otherwise.

## External Task Sources

AsynCodeBench v0.3 derives task metadata from the public Commit0 benchmark and
from the public upstream repositories referenced by that benchmark. The raw
Commit0 `load_from_disk` dataset and upstream repository checkouts are not
redistributed in this repository. Users must obtain those inputs separately
and comply with their applicable licenses, terms, and attribution notices.

AsynCodeBench metadata does not transfer ownership of, or supersede the
license for, upstream source code, tests, package data, or third-party
dependencies. The provenance fields in the curated task configuration identify
the source benchmark and repository revision used by each task.

## Bootstrap Overlays

Files in `data/overlays/commit0/` are checksum-pinned, non-solution bootstrap
artifacts authored for reproducible task setup. They are not intended to
provide a task solution. When an overlay is applied to an external repository,
the license obligations of that repository remain in effect.

## OpenHands Runtime

The evaluation harness uses the OpenHands software-agent SDK as an external
runtime dependency. It is obtained separately under
`reproductions/software-agent-sdk/` and is governed by its own license and
notices.
