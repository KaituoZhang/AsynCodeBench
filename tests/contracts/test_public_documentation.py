import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RELEASE_INDEX = ROOT / "manifests" / "release" / "v0.4" / "task_index.json"
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


def test_readme_release_facts_match_machine_readable_index():
    index = json.loads(read(RELEASE_INDEX))
    readme = read(ROOT / "README")
    flat_readme = readme.replace("\n", " ")
    official_block = re.search(
        r"## Official Tasks\s+```text\n(.*?)\n```",
        readme,
        re.DOTALL,
    )

    assert official_block is not None
    assert official_block.group(1).split() == [
        task["task_id"].removeprefix("asyncodebench:") for task in index["tasks"]
    ]
    assert f"**{index['task_count']} official repository-level tasks**" in readme
    assert f"**{index['scenario_count']} task-protocol scenarios**" in readme
    assert (
        f"**{index['dependency_point_count']} executable producer/consumer "
        "dependency points**"
    ) in flat_readme
    assert (
        f"automated audit is complete for "
        f"{index['automated_audit_complete_task_count']}/{index['task_count']} tasks"
    ) in flat_readme
    assert (
        f"required human approval is complete for "
        f"{index['human_review_passed_task_count']}/{index['task_count']} tasks"
    ) in flat_readme


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
    readme = read(ROOT / "README")
    for protocol in (
        "single",
        "serial_specialists",
        "async_private",
        "caid_manager",
    ):
        assert f"`{protocol}`" in readme


def test_result_validity_uses_canonical_derived_report_directory():
    document = read(ROOT / "docs" / "RESULT_VALIDITY.md")
    assert "--input-dir outputs/reports/<model-tag>" in document
    assert "--output-dir outputs/reports/<model-tag>" in document
    assert "reproductions/async-swe-agents/outputs/<model-tag>" not in document


def test_preview_installation_and_clean_checkout_validation_are_explicit():
    clone_command = (
        "git clone --branch agent/community-ready-release-clean --single-branch"
    )
    assert clone_command in read(ROOT / "README")
    assert clone_command in read(ROOT / "docs" / "QUICKSTART.md")

    setup = read(ROOT / "scripts" / "setup_evaluation.sh")
    assert 'uv sync --frozen --extra dev --python "$PYTHON_BIN"' in setup
    assert "materialize_contract_test_repositories.py" in setup

    workflow = read(ROOT / ".github" / "workflows" / "ci.yml")
    materialize = "python scripts/materialize_contract_test_repositories.py"
    contracts = "python -m pytest -q tests/contracts"
    assert materialize in workflow
    assert workflow.index(materialize) < workflow.index(contracts)
