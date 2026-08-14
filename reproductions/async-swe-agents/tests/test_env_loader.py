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
