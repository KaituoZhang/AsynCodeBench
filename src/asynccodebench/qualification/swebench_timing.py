"""Official SWE-bench environment timing without recording hidden test content."""

from __future__ import annotations

import hashlib
import json
import re
import traceback
from pathlib import Path, PurePosixPath
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from asynccodebench.qualification.swebench_materialization import (
    SWEbenchMaterializationInventory,
)

TIMING_PROTOCOL_VERSION = "swebench-official-timing-v0.2"
EXIT_CODE_PATTERN = re.compile(r"__ASYNCCODEBENCH_EXIT_CODE__:(-?\d+)")


class SWEbenchTimingModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timing_protocol_version: Literal["swebench-official-timing-v0.2"] = (
        TIMING_PROTOCOL_VERSION
    )


class SWEbenchOfficialTimingRecord(SWEbenchTimingModel):
    """One official-harness timing observation.

    The record intentionally excludes official hidden test patches, generated
    eval scripts, and raw test output. It records only metadata required for
    qualification and reproducibility.
    """

    instance_id: str
    repo: str
    base_commit: str
    dataset_id: str
    dataset_revision: str
    run_id: str
    namespace: str | None
    timeout_seconds: int = Field(gt=0)
    completed: bool
    timed_out: bool
    duration_seconds: float = Field(ge=0.0)
    return_code: int | None
    output_sha256: str | None
    output_bytes: int = Field(ge=0)
    log_dir: str
    status: Literal["completed", "timed_out", "error"]
    error_type: str | None = None
    error_summary: str | None = None


class SWEbenchOfficialTimingInventory(SWEbenchTimingModel):
    dataset_id: str
    dataset_revision: str
    run_id: str
    records: tuple[SWEbenchOfficialTimingRecord, ...]


def _load_official_instances(
    *,
    dataset_id: str,
    dataset_revision: str,
    split: str,
    instance_ids: set[str],
) -> dict[str, dict]:
    from datasets import load_dataset

    dataset = load_dataset(dataset_id, split=split, revision=dataset_revision)
    instances = {
        row["instance_id"]: dict(row)
        for row in dataset
        if row["instance_id"] in instance_ids
    }
    missing = sorted(instance_ids - set(instances))
    if missing:
        raise ValueError(f"Official dataset missing instances: {missing}")
    return instances


def _parse_return_code(output: str) -> int | None:
    matches = EXIT_CODE_PATTERN.findall(output)
    if not matches:
        return None
    return int(matches[-1])


def _output_digest(output: str) -> tuple[str, int]:
    encoded = output.encode("utf-8", errors="replace")
    return hashlib.sha256(encoded).hexdigest(), len(encoded)


def time_official_instance(
    *,
    official_instance: dict,
    dataset_id: str,
    dataset_revision: str,
    run_id: str,
    namespace: str | None,
    timeout_seconds: int,
    log_root: Path,
) -> SWEbenchOfficialTimingRecord:
    import docker
    from swebench.harness.docker_build import (
        build_container,
        close_logger,
        setup_logger,
    )
    from swebench.harness.docker_utils import (
        cleanup_container,
        exec_run_with_timeout,
        write_to_container,
    )
    from swebench.harness.test_spec.test_spec import make_test_spec

    instance_id = official_instance["instance_id"]
    log_dir = log_root / run_id / instance_id
    logger = setup_logger(instance_id, log_dir / "timing.log")
    client = docker.from_env()
    container = None
    try:
        test_spec = make_test_spec(official_instance, namespace=namespace)
        container = build_container(
            test_spec,
            client,
            run_id,
            logger,
            False,
            False,
        )
        container.start()
        write_to_container(container, test_spec.eval_script, PurePosixPath("/eval.sh"))
        command = (
            "bash -lc '/bin/bash /eval.sh; "
            "code=$?; "
            'echo "__ASYNCCODEBENCH_EXIT_CODE__:${code}"; '
            "exit ${code}'"
        )
        output, timed_out, duration = exec_run_with_timeout(
            container,
            command,
            timeout_seconds,
        )
        output_sha256, output_bytes = _output_digest(output)
        return_code = _parse_return_code(output)
        status: Literal["completed", "timed_out", "error"]
        if timed_out:
            status = "timed_out"
        elif return_code is None:
            status = "error"
        else:
            status = "completed"
        return SWEbenchOfficialTimingRecord(
            instance_id=instance_id,
            repo=official_instance["repo"],
            base_commit=official_instance["base_commit"],
            dataset_id=dataset_id,
            dataset_revision=dataset_revision,
            run_id=run_id,
            namespace=namespace,
            timeout_seconds=timeout_seconds,
            completed=status == "completed",
            timed_out=timed_out,
            duration_seconds=duration,
            return_code=return_code,
            output_sha256=output_sha256,
            output_bytes=output_bytes,
            log_dir=str(log_dir),
            status=status,
        )
    except Exception as exc:  # pragma: no cover - exercised by Docker smoke runs
        logger.info(traceback.format_exc())
        return SWEbenchOfficialTimingRecord(
            instance_id=instance_id,
            repo=official_instance["repo"],
            base_commit=official_instance["base_commit"],
            dataset_id=dataset_id,
            dataset_revision=dataset_revision,
            run_id=run_id,
            namespace=namespace,
            timeout_seconds=timeout_seconds,
            completed=False,
            timed_out=False,
            duration_seconds=0.0,
            return_code=None,
            output_sha256=None,
            output_bytes=0,
            log_dir=str(log_dir),
            status="error",
            error_type=type(exc).__name__,
            error_summary=str(exc)[:500],
        )
    finally:
        cleanup_container(client, container, logger)
        close_logger(logger)


def build_official_timing_inventory(
    *,
    materialized: SWEbenchMaterializationInventory,
    split: str,
    run_id: str,
    namespace: str | None,
    timeout_seconds: int,
    log_root: Path,
    instance_ids: tuple[str, ...] = (),
    limit: int | None = None,
) -> SWEbenchOfficialTimingInventory:
    selected_ids = tuple(record.instance_id for record in materialized.records)
    if instance_ids:
        requested = set(instance_ids)
        unknown = sorted(requested - set(selected_ids))
        if unknown:
            raise ValueError(f"Unknown materialized instances: {unknown}")
        selected_ids = tuple(
            task_id for task_id in selected_ids if task_id in requested
        )
    if limit is not None:
        selected_ids = selected_ids[:limit]
    official_instances = _load_official_instances(
        dataset_id=materialized.dataset_id,
        dataset_revision=materialized.dataset_revision,
        split=split,
        instance_ids=set(selected_ids),
    )
    records = tuple(
        time_official_instance(
            official_instance=official_instances[instance_id],
            dataset_id=materialized.dataset_id,
            dataset_revision=materialized.dataset_revision,
            run_id=run_id,
            namespace=namespace,
            timeout_seconds=timeout_seconds,
            log_root=log_root,
        )
        for instance_id in selected_ids
    )
    return SWEbenchOfficialTimingInventory(
        dataset_id=materialized.dataset_id,
        dataset_revision=materialized.dataset_revision,
        run_id=run_id,
        records=records,
    )


def write_official_timing_inventory(
    inventory: SWEbenchOfficialTimingInventory,
    path: Path,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            inventory.model_dump(mode="json"),
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
