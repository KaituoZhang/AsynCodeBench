import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CURRENT_GUIDES = (
    ROOT / "README",
    ROOT / "docs" / "QUICKSTART.md",
    ROOT / "docs" / "MODEL_EXPERIMENT_RUNBOOK.md",
    ROOT / "docs" / "ASYNCODEBENCH_HARNESS_V2.md",
    ROOT / "docs" / "AGENT_ADAPTER.md",
    ROOT / "reproductions" / "async-swe-agents" / "README.md",
)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def shell_blocks(document: str) -> list[str]:
    return re.findall(r"```(?:bash|sh|shell)\n(.*?)\n```", document, re.DOTALL)


def test_readme_is_a_concise_community_entry_point():
    readme = read(ROOT / "README")

    assert readme.startswith("# AsynCodeBench\n")
    assert "19 repository-level tasks" in readme
    assert "five controlled single- and multi-agent" in readme
    assert "v0.4.1 community preview" in readme
    assert "## Quick Start" in readme
    assert "scripts/run_asyncodebench_five_protocols_env.sh" in readme
    assert "## Repository Map" in readme
    assert "docs/QUICKSTART.md" in readme
    assert "**Async-Manager-RO** (`caid_manager` in the CLI)" in readme


def test_current_guides_do_not_offer_legacy_execution_commands():
    forbidden = (
        "run_commit0_",
        "run_static_protocol.py",
        "run_infer.py",
        "outputs/repro_commit0",
        "--task commit0:",
        "--task_id commit0:",
    )
    for path in CURRENT_GUIDES:
        commands = "\n".join(shell_blocks(read(path)))
        for value in forbidden:
            assert value not in commands, f"{path.relative_to(ROOT)} exposes {value}"


def test_current_guides_use_canonical_protocol_and_brand_names():
    for path in CURRENT_GUIDES:
        document = read(path)
        assert "CAID_multi" not in document
        assert "AsyncCodeBench" not in document
        assert "Asynccodebench" not in document.replace(
            "https://github.com/KaituoZhang/Asynccodebench.git",
            "",
        )
    protocol_guide = read(
        ROOT
        / "reproductions"
        / "async-swe-agents"
        / "protocols"
        / "README.md"
    )
    for protocol in (
        "single",
        "serial_specialists",
        "async_private",
        "caid_manager",
        "async_manager",
    ):
        assert f"`{protocol}`" in protocol_guide


def test_result_validity_uses_canonical_derived_report_directory():
    document = read(ROOT / "docs" / "RESULT_VALIDITY.md")
    assert "--input-dir outputs/reports/<model-tag>" in document
    assert "--output-dir outputs/reports/<model-tag>" in document
    assert "reproductions/async-swe-agents/outputs/<model-tag>" not in document


def test_preview_installation_and_clean_checkout_validation_are_explicit():
    clone_command = "git clone https://github.com/KaituoZhang/AsynCodeBench.git"
    assert clone_command in read(ROOT / "docs" / "QUICKSTART.md")

    setup = read(ROOT / "scripts" / "setup_evaluation.sh")
    assert 'uv sync --frozen --extra dev --python "$PYTHON_BIN"' in setup
    assert "materialize_contract_test_repositories.py" in setup

    workflow = read(ROOT / ".github" / "workflows" / "ci.yml")
    materialize = "python scripts/materialize_contract_test_repositories.py"
    contracts = "python -m pytest -q tests/contracts"
    assert materialize in workflow
    assert workflow.index(materialize) < workflow.index(contracts)
