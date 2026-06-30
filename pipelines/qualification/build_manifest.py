"""Build a validated pilot qualification manifest from JSON inputs."""

from asynccodebench.qualification.cli import (
    load_batch,
    main,
    parse_args,
    run,
)

__all__ = ["load_batch", "main", "parse_args", "run"]


if __name__ == "__main__":
    raise SystemExit(main())
