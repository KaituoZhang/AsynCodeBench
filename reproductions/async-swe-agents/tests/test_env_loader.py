import subprocess
from pathlib import Path


RUNNER_ROOT = Path(__file__).resolve().parents[1]
ENV_SCRIPT = RUNNER_ROOT / "scripts" / "env.sh"


def test_explicit_override_survives_repeated_env_load(tmp_path):
    env_file = tmp_path / "model.env"
    env_file.write_text(
        "LLM_BASE_URL=http://127.0.0.1:8006/v1\n"
        "LLM_API_KEY=test-key\n"
        "LLM_MODEL=openai/test-model\n",
        encoding="utf-8",
    )
    command = """
export ENV_FILE="$2"
source "$1"
export LLM_BASE_URL=http://127.0.0.1:8009/v1
source "$1"
printf '%s' "$LLM_BASE_URL"
"""

    result = subprocess.run(
        ["bash", "-c", command, "bash", str(ENV_SCRIPT), str(env_file)],
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout == "http://127.0.0.1:8009/v1"


def test_changing_env_file_loads_new_configuration(tmp_path):
    first = tmp_path / "first.env"
    second = tmp_path / "second.env"
    common = "LLM_API_KEY=test-key\nLLM_MODEL=openai/test-model\n"
    first.write_text(
        "LLM_BASE_URL=http://127.0.0.1:8006/v1\n" + common,
        encoding="utf-8",
    )
    second.write_text(
        "LLM_BASE_URL=http://127.0.0.1:8009/v1\n" + common,
        encoding="utf-8",
    )
    command = """
export ENV_FILE="$2"
source "$1"
export ENV_FILE="$3"
source "$1"
printf '%s' "$LLM_BASE_URL"
"""

    result = subprocess.run(
        [
            "bash",
            "-c",
            command,
            "bash",
            str(ENV_SCRIPT),
            str(first),
            str(second),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout == "http://127.0.0.1:8009/v1"


def test_stale_root_is_replaced_by_runner_checkout(tmp_path):
    env_file = tmp_path / "model.env"
    env_file.write_text(
        "LLM_BASE_URL=http://127.0.0.1:8006/v1\n"
        "LLM_API_KEY=test-key\n"
        "LLM_MODEL=openai/test-model\n"
        f"ASYNCODEBENCH_ROOT={tmp_path}\n",
        encoding="utf-8",
    )
    command = 'export ENV_FILE="$2"; source "$1"; printf "%s" "$ASYNCODEBENCH_ROOT"'
    result = subprocess.run(
        ["bash", "-c", command, "bash", str(ENV_SCRIPT), str(env_file)],
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.stdout == str(RUNNER_ROOT.parents[1])
    assert "ignoring stale ASYNCODEBENCH_ROOT" in result.stderr


def test_external_runner_preserves_explicit_source_root(tmp_path):
    script = tmp_path / "installed" / "runner" / "scripts" / "env.sh"
    script.parent.mkdir(parents=True)
    script.write_text(ENV_SCRIPT.read_text(encoding="utf-8"), encoding="utf-8")
    source_root = tmp_path / "source"
    source_root.mkdir()
    env_file = tmp_path / "model.env"
    env_file.write_text(
        "LLM_BASE_URL=http://127.0.0.1:8006/v1\n"
        "LLM_API_KEY=test-key\n"
        "LLM_MODEL=openai/test-model\n"
        f"ASYNCODEBENCH_ROOT={source_root}\n",
        encoding="utf-8",
    )
    command = 'export ENV_FILE="$2"; source "$1"; printf "%s" "$ASYNCODEBENCH_ROOT"'
    result = subprocess.run(
        ["bash", "-c", command, "bash", str(script), str(env_file)],
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.stdout == str(source_root)


def test_repeated_load_repairs_inherited_root(tmp_path):
    env_file = tmp_path / "model.env"
    env_file.write_text(
        "LLM_BASE_URL=http://127.0.0.1:8006/v1\n"
        "LLM_API_KEY=test-key\n"
        "LLM_MODEL=openai/test-model\n",
        encoding="utf-8",
    )
    command = """
export ENV_FILE="$2"
source "$1"
export ASYNCODEBENCH_ROOT="$3"
source "$1"
printf '%s' "$ASYNCODEBENCH_ROOT"
"""
    result = subprocess.run(
        ["bash", "-c", command, "bash", str(ENV_SCRIPT), str(env_file), str(tmp_path)],
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.stdout == str(RUNNER_ROOT.parents[1])
    assert "ignoring stale ASYNCODEBENCH_ROOT" in result.stderr


def test_direct_cli_pins_checkout_root(tmp_path):
    import json
    import os
    import sys

    env = os.environ.copy()
    env["ASYNCODEBENCH_ROOT"] = str(tmp_path)
    env["PYTHONPATH"] = str(RUNNER_ROOT)
    result = subprocess.run(
        [sys.executable, "-m", "asyncodebench_harness.cli", "release-status", "--json"],
        cwd=RUNNER_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["task_count"] == 19
    assert "ignoring stale ASYNCODEBENCH_ROOT" in result.stderr
