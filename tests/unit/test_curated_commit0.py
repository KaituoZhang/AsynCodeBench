import subprocess
from pathlib import Path

from asyncodebench.qualification.curated_commit0 import (
    CuratedCommit0Task,
    CuratedOverlay,
    file_sha256,
    load_curated_tasks,
    materialize_curated_task,
)


def test_tinydb_curated_overlay_is_versioned_and_verified() -> None:
    project_root = Path.cwd()
    tasks = load_curated_tasks(
        Path("configs/tasks/commit0_curated_tasks.v0.3.json"),
        project_root=project_root,
    )

    tinydb = next(task for task in tasks if task.task_id == "commit0:tinydb")
    assert tinydb.base_sha == (
        "ed761a72c8c1e1cb24ca4dbcc089f35c5264d357"
    )
    assert len(tinydb.overlays) == 1
    assert file_sha256(tinydb.overlays[0].path) == tinydb.overlays[0].sha256
    assert tinydb.overlays[0].sha256 == (
        "fa0d43a64a64d6bcd085661328bfca566f678f384ac4bf6c8bf2b79b0c01a464"
    )

    portalocker = next(
        task for task in tasks if task.task_id == "commit0:portalocker"
    )
    assert portalocker.base_sha == (
        "300136afca11ea23c79ecfd110ed0d2819322f11"
    )
    assert len(portalocker.overlays) == 1
    assert file_sha256(portalocker.overlays[0].path) == (
        portalocker.overlays[0].sha256
    )
    assert portalocker.overlays[0].sha256 == (
        "b6b2f2c7fdbce4200774804a49d410648e17a573b42ca007e9471e5e8fa4c96c"
    )

    overlay = portalocker.overlays[0].path.read_text(encoding="utf-8")
    for source in (
        "portalocker/__about__.py",
        "portalocker/constants.py",
        "portalocker/exceptions.py",
        "portalocker/portalocker.py",
        "portalocker/redis.py",
        "portalocker/utils.py",
    ):
        assert f"diff --git a/{source} b/{source}" in overlay
    assert overlay.count("\\ No newline at end of file") == 6


def test_materialize_curated_task_applies_overlay_without_mutating_base(
    tmp_path: Path,
) -> None:
    # The production destination is nested below the AsynCodeBench checkout.
    # Reproduce that parent-repository layout so Git must not skip the overlay.
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)

    repository = tmp_path / "repository"
    repository.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repository, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repository,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=repository,
        check=True,
    )
    source = repository / "module.py"
    source.write_text("VALUE = 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "module.py"], cwd=repository, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "base"],
        cwd=repository,
        check=True,
    )
    base_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    subprocess.run(
        ["git", "branch", "commit0", base_sha],
        cwd=repository,
        check=True,
    )

    overlay_path = tmp_path / "overlay.patch"
    overlay_path.write_text(
        (
            "diff --git a/module.py b/module.py\n"
            "--- a/module.py\n"
            "+++ b/module.py\n"
            "@@ -1 +1 @@\n"
            "-VALUE = 1\n"
            "+VALUE = 2\n"
        ),
        encoding="utf-8",
    )
    task = CuratedCommit0Task(
        task_id="commit0:test",
        repository="test",
        base_ref="commit0",
        base_sha=base_sha,
        overlays=(
            CuratedOverlay(
                path=overlay_path,
                sha256=file_sha256(overlay_path),
                rationale="test overlay",
            ),
        ),
    )

    destination = tmp_path / "curated"
    materialize_curated_task(
        task,
        repository_path=repository,
        destination=destination,
    )

    assert source.read_text(encoding="utf-8") == "VALUE = 1\n"
    assert (destination / "module.py").read_text(encoding="utf-8") == (
        "VALUE = 2\n"
    )
