#!/usr/bin/env python3
"""Build the Qwen3.6-27B Commit0 + TVM descriptive analysis.

This script deliberately uses only the Python standard library.  It reads the
already-selected official Commit0 run table and the explicitly selected TVM
candidate bundles, then writes CSV, Markdown, and presentation-ready SVG files.
"""

from __future__ import annotations

import csv
import hashlib
import html
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "docs" / "results"
FIGURES = RESULTS / "figures"
OFFICIAL_PER_RUN = RESULTS / "qwen36_27_standard100_per_run.csv"
OFFICIAL_SUMMARY = RESULTS / "qwen36_27_standard100_summary_by_protocol.csv"
TVM_OUTPUT_ROOT = (
    ROOT
    / "reproductions"
    / "async-swe-agents"
    / "outputs"
    / "pr_hard"
    / "v0.4"
    / "openai_Qwen_Qwen3.6-27B"
)
CURRENT_CANDIDATE_INDEX = ROOT / "configs" / "tasks" / "pr_hard_candidates.v0.4.json"
STATISTICAL_CORRECTIONS = (
    RESULTS / "qwen36_27_statistical_corrections.v1.json"
)

PER_RUN_OUT = RESULTS / "qwen36_27_commit0_tvm_per_run.csv"
SUMMARY_OUT = RESULTS / "qwen36_27_commit0_tvm_summary_by_protocol.csv"
TAXONOMY_OUT = RESULTS / "qwen36_27_task_taxonomy.csv"
FROZEN_INDEX_OUT = RESULTS / "qwen36_27_frozen_result_index.v1.json"
REPORT_OUT = RESULTS / "QWEN36_27_COMMIT0_TVM_ANALYSIS.md"
PROTOCOL_FIGURE = FIGURES / "qwen36_27_commit0_vs_tvm_protocol.svg"
TVM_FIGURE = FIGURES / "qwen36_27_tvm_task_protocol_heatmap.svg"
TAXONOMY_FIGURE = FIGURES / "asynccodebench_task_taxonomy.svg"

PROTOCOLS = ["single", "serial_specialists", "async_private", "caid_manager"]
PROTOCOL_LABELS = {
    "single": "Single",
    "serial_specialists": "Serial",
    "async_private": "Async private",
    "caid_manager": "CAID",
}

# Explicit selection avoids silently picking a rerun with different provenance.
TVM_SELECTION = {
    "apache-tvm-20073": {
        protocol: "pr-hard-20073-qwen36-27b-thinking-20260827T110040Z"
        for protocol in PROTOCOLS
    },
    "apache-tvm-20107": {
        protocol: "pr-hard-20107-qwen36-27b-thinking-20260826T180300Z"
        for protocol in PROTOCOLS
    },
    "apache-tvm-20153": {
        "single": "qwen36-27b-gpu1-tvm20153-fixed2-20260825T113252Z",
        "serial_specialists": "qwen36-27b-gpu1-tvm20153-fixed2-20260825T113252Z",
        "async_private": "qwen36-27b-gpu1-tvm20153-fixed2-20260825T113252Z",
        "caid_manager": "qwen36-27b-gpu1-tvm20153-caidretry1-20260825T224253Z",
    },
    "apache-tvm-20018": {
        "single": "pr-hard-20018-qwen36-full-20260828T160649Z",
        "serial_specialists": "pr-hard-20018-qwen36-full-20260828T160649Z",
        "async_private": "pr-hard-20018-qwen36-full-20260828T160649Z",
        "caid_manager": "pr-hard-20018-qwen36-caid-isolation-v2-20260829T125649Z",
    },
}


TASK_INFO = {
    "cachetools": ("General SWE / framework", "Caching and reusable utilities", "Python", 2),
    "deprecated": ("General SWE / framework", "Decorators and documentation compatibility", "Python", 2),
    "portalocker": ("Systems / runtime / storage", "OS file locking and concurrency", "Python", 2),
    "tinydb": ("Systems / runtime / storage", "Embedded database and persistence", "Python", 2),
    "wcwidth": ("Systems / runtime / storage", "Terminal and Unicode infrastructure", "Python", 2),
    "requests": ("Network / protocol", "HTTP client and transport", "Python", 3),
    "simpy": ("Systems / runtime / storage", "Discrete-event runtime", "Python", 4),
    "parsel": ("General SWE / framework", "Parsing and query processing", "Python", 3),
    "filesystem_spec": ("Systems / runtime / storage", "Filesystem and storage abstraction", "Python", 3),
    "marshmallow": ("General SWE / framework", "Schema and serialization framework", "Python", 3),
    "graphene": ("General SWE / framework", "Type-system and schema framework", "Python", 3),
    "imapclient": ("Network / protocol", "IMAP protocol client", "Python", 3),
    "pexpect": ("Systems / runtime / storage", "Process, PTY, and asynchronous I/O", "Python", 4),
    "flask": ("General SWE / framework", "Web application framework", "Python", 4),
    "python-rsa": ("Security / cryptography", "Public-key cryptography", "Python", 4),
    "cookiecutter": ("General SWE / framework", "Developer tooling and workflow automation", "Python", 4),
    "apache-tvm-20073": (
        "Compiler / IR engineering",
        "Source spans across IRBuilder, parser, evaluator, and TIRx",
        "Python + C++",
        3,
    ),
    "apache-tvm-20107": (
        "Compiler / IR engineering",
        "Generic Script signatures with Relax/TIRx parser-printer fan-out",
        "Python + C++",
        3,
    ),
    "apache-tvm-20153": (
        "Compiler / IR engineering",
        "PTX dialect schema, lowering, and rendering",
        "Python",
        3,
    ),
    "apache-tvm-20018": (
        "Compiler / IR engineering",
        "Return IR schema, TVMScript surface, lowering, and target emission",
        "Python + C++",
        3,
    ),
}

TVM_ARTIFACT_LANGUAGES = {
    "apache-tvm-20073": "TVMScript/TIRx IR and source-span metadata",
    "apache-tvm-20107": "TVMScript, Relax IR, and TIRx IR",
    "apache-tvm-20153": "TIRx IR and PTX assembly text",
    "apache-tvm-20018": "TIRx IR, TVMScript, LLVM IR, and C target code",
}


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_statistical_corrections() -> dict[tuple[str, str, str], dict]:
    payload = read_json(STATISTICAL_CORRECTIONS)
    return {
        (item["task"], item["protocol"], item["run_id"]): item
        for item in payload.get("corrections", [])
    }


def corrected_agent_termination(
    *, task: str, protocol: str, run_id: str, run_dir: Path, process: dict,
    corrections: dict[tuple[str, str, str], dict],
) -> tuple[dict, str | None]:
    termination = dict(process["process_metrics"]["agent_termination"])
    correction = corrections.get((task, protocol, run_id))
    if correction is None:
        return termination, None

    for filename, expected_sha in correction["source_sha256"].items():
        observed_sha = sha256_file(run_dir / filename)
        if observed_sha != expected_sha:
            raise RuntimeError(
                f"statistical correction source mismatch for {filename}: "
                f"expected {expected_sha}, observed {observed_sha}"
            )
    original = correction["original"]
    if termination.get("iteration_cap_hit_count") != original[
        "process_metrics.agent_termination.iteration_cap_hit_count"
    ]:
        raise RuntimeError("statistical correction original cap-hit value mismatch")
    if termination.get("reason_counts") != original[
        "process_metrics.agent_termination.reason_counts"
    ]:
        raise RuntimeError("statistical correction original reason-count value mismatch")

    corrected = correction["corrected"]
    termination["iteration_cap_hit_count"] = corrected[
        "process_metrics.agent_termination.iteration_cap_hit_count"
    ]
    termination["reason_counts"] = corrected[
        "process_metrics.agent_termination.reason_counts"
    ]
    termination["legacy_compatibility_inference_count"] = corrected[
        "process_metrics.agent_termination.legacy_compatibility_inference_count"
    ]
    return termination, correction["correction_id"]


def optional_float(value):
    if value in (None, ""):
        return None
    return float(value)


def fmt_csv(value):
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, float):
        return f"{value:.12g}"
    return value


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: fmt_csv(row.get(field)) for field in fields})


def read_official_runs() -> list[dict]:
    rows = []
    with OFFICIAL_PER_RUN.open(encoding="utf-8", newline="") as handle:
        for raw in csv.DictReader(handle):
            rows.append(
                {
                    "lane": "Commit0 official v0.3",
                    "task": raw["task"],
                    "protocol": raw["protocol"],
                    "run_id": raw["run_id"],
                    "run_dir": raw["run_dir"],
                    "bundle_generation_status": raw["bundle_status"],
                    "current_registry_match": "not_rechecked_here",
                    "official_result_eligible": raw["official_aggregate_eligible"] == "True",
                    "final_success": raw["final_success"] == "True",
                    "final_pass_rate": float(raw["final_pass_rate"]),
                    "final_tests_passed": int(raw["final_tests_passed"]),
                    "final_tests_collected": int(raw["final_tests_collected"]),
                    "final_tests_failed": None,
                    "final_test_errors_recorded": None,
                    "raw_pytest_summary": "",
                    "dependency_count": int(raw["dependency_count"]),
                    "resolved_dependency_count": int(raw["resolved_dependency_count"]),
                    "unresolved_dependency_count": int(raw["unresolved_dependency_count"]),
                    "ADPR": float(raw["ADPR"]),
                    "checkpoint_count": int(raw["checkpoint_count"]),
                    "penalized_DRS": float(raw["penalized_DRS"]),
                    "penalized_CAIL": float(raw["penalized_CAIL"]),
                    "DRE": float(raw["DRE"]),
                    "raw_strict_DRS_mean": None,
                    "raw_strict_DRS_observed_count": None,
                    "raw_strict_CAIL_mean": None,
                    "raw_strict_CAIL_observed_count": None,
                    "FSAR": optional_float(raw["FSAR"]),
                    "IFR": optional_float(raw["IFR"]),
                    "SVR": optional_float(raw["SVR"]),
                    "MRR": optional_float(raw["MRR"]),
                    "iteration_cap_hit_count": None,
                    "agent_attempt_count": None,
                    "iteration_cap_hit_rate": None,
                    "termination_reason_counts": "",
                    "statistics_correction_id": "",
                    "total_tokens": int(raw["total_tokens"]),
                    "runtime_seconds": float(raw["runtime_seconds"]),
                    "benchmark_revision": raw["benchmark_revision"],
                    "generation_configuration_sha256": raw["generation_configuration_sha256"],
                    "execution_profile": raw["execution_profile"],
                }
            )
    return rows


def raw_pytest_summary(run_dir: Path) -> str:
    candidates = sorted(run_dir.glob("*_test_output.txt"))
    if not candidates:
        return ""
    lines = candidates[0].read_text(encoding="utf-8", errors="replace").splitlines()
    summary_pattern = re.compile(r"=+\s+.*(?:passed|failed|error|skipped|xfailed).*\s+=+")
    for line in reversed(lines):
        if summary_pattern.search(line):
            return line.strip("= ")
    return ""


def penalized_dependency_metrics(strict: dict) -> tuple[float, float, float]:
    """Return mean DRS penalty, mean CAIL penalty, and mean DRE."""
    checkpoints = int(strict["checkpoint_count"])
    drs_values = []
    cail_values = []
    dre_values = []
    for item in strict["dependency_metrics"]:
        resolved = bool(item["final_integrated_pass"])
        raw_drs = item["strict_DRS"]
        drs = float(raw_drs) if resolved and raw_drs is not None else float(checkpoints + 1)
        drs_values.append(drs)
        if resolved:
            dre_values.append(1.0 - (drs - 1.0) / checkpoints)
        else:
            dre_values.append(0.0)

        upstream = item["upstream_resolution_step"]
        downstream = item["downstream_resolution_step"]
        if upstream is not None and downstream is not None:
            cail_values.append(float(max(0, downstream - upstream)))
        elif upstream is not None:
            cail_values.append(float(checkpoints + 1 - upstream))
        else:
            cail_values.append(float(checkpoints + 1))
    return mean(drs_values), mean(cail_values), mean(dre_values)


def read_tvm_runs() -> list[dict]:
    current_index_sha = hashlib.sha256(CURRENT_CANDIDATE_INDEX.read_bytes()).hexdigest()
    corrections = load_statistical_corrections()
    rows = []
    for task, protocols in TVM_SELECTION.items():
        for protocol in PROTOCOLS:
            run_id = protocols[protocol]
            run_dir = TVM_OUTPUT_ROOT / task / protocol / run_id
            bundle = read_json(run_dir / "run_bundle.json")
            strict = read_json(run_dir / "strict_dependency_metrics.json")
            process = read_json(run_dir / "process_metrics_summary.json")
            final = bundle["final_test"]
            formal = process["formal_metrics"]
            cost = process["cost_metrics"]
            termination, correction_id = corrected_agent_termination(
                task=task,
                protocol=protocol,
                run_id=run_id,
                run_dir=run_dir,
                process=process,
                corrections=corrections,
            )
            cap_hits = termination["iteration_cap_hit_count"]
            agent_attempts = termination["agent_attempt_count"]
            adpr = strict["final_integrated_ADPR"]
            drs_penalty, cail_penalty, dre = penalized_dependency_metrics(strict)
            recorded_index_sha = bundle["release_index"]["sha256"]
            rows.append(
                {
                    "lane": "TVM PR-hard candidate v0.4",
                    "task": task,
                    "protocol": protocol,
                    "run_id": run_id,
                    "run_dir": str(run_dir.relative_to(ROOT)),
                    "bundle_generation_status": bundle["status"],
                    "current_registry_match": recorded_index_sha == current_index_sha,
                    "official_result_eligible": bundle["eligibility"]["official_aggregate"],
                    "final_success": final["success"],
                    "final_pass_rate": final["passed"] / final["collected"] if final["collected"] else 0.0,
                    "final_tests_passed": final["passed"],
                    "final_tests_collected": final["collected"],
                    "final_tests_failed": final["failed"],
                    "final_test_errors_recorded": final["errors"],
                    "raw_pytest_summary": raw_pytest_summary(run_dir),
                    "dependency_count": adpr["total"],
                    "resolved_dependency_count": adpr["resolved"],
                    "unresolved_dependency_count": adpr["total"] - adpr["resolved"],
                    "ADPR": adpr["value"],
                    "checkpoint_count": strict["checkpoint_count"],
                    "penalized_DRS": drs_penalty,
                    "penalized_CAIL": cail_penalty,
                    "DRE": dre,
                    "raw_strict_DRS_mean": strict["strict_DRS"].get("mean"),
                    "raw_strict_DRS_observed_count": strict["strict_DRS"]["observed_count"],
                    "raw_strict_CAIL_mean": strict["strict_CAIL"]["mean"],
                    "raw_strict_CAIL_observed_count": strict["strict_CAIL"]["observed_count"],
                    "FSAR": formal["FSAR"]["value"],
                    "IFR": formal["IFR"]["value"],
                    "SVR": formal["SVR"]["value"],
                    "MRR": formal["MRR"]["value"],
                    "iteration_cap_hit_count": cap_hits,
                    "agent_attempt_count": agent_attempts,
                    "iteration_cap_hit_rate": (
                        cap_hits / agent_attempts if agent_attempts else None
                    ),
                    "termination_reason_counts": json.dumps(
                        termination["reason_counts"], sort_keys=True
                    ),
                    "statistics_correction_id": correction_id or "",
                    "total_tokens": cost["total_tokens"],
                    "runtime_seconds": cost["runtime_seconds"],
                    "benchmark_revision": bundle["provenance"]["benchmark_revision"],
                    "generation_configuration_sha256": bundle["provenance"][
                        "generation_configuration_sha256"
                    ],
                    "execution_profile": bundle["execution_profile"]["profile_id"],
                }
            )
    return rows


def official_summaries() -> list[dict]:
    rows = []
    with OFFICIAL_SUMMARY.open(encoding="utf-8", newline="") as handle:
        for raw in csv.DictReader(handle):
            rows.append(
                {
                    "lane": "Commit0 official v0.3",
                    "protocol": raw["protocol"],
                    "successful_tasks": int(raw["successful_tasks"]),
                    "task_count": int(raw["task_count"]),
                    "success_rate": float(raw["success_rate"]),
                    "mean_test_pass_rate": float(raw["mean_test_pass_rate"]),
                    "mean_ADPR": float(raw["mean_ADPR"]),
                    "mean_unresolved_dependencies": float(raw["mean_unresolved_dependencies"]),
                    "penalized_DRS": float(raw["penalized_DRS"]),
                    "penalized_CAIL": float(raw["penalized_CAIL"]),
                    "mean_DRE": float(raw["mean_DRE"]),
                    "FSAR": optional_float(raw["FSAR"]),
                    "IFR": optional_float(raw["IFR"]),
                    "SVR": optional_float(raw["SVR"]),
                    "MRR": optional_float(raw["MRR"]),
                    "iteration_cap_hits": None,
                    "agent_attempts": None,
                    "iteration_cap_hit_rate": None,
                    "mean_tokens": float(raw["mean_tokens"]),
                    "mean_runtime_seconds": float(raw["mean_runtime_seconds"]),
                    "result_status": "descriptive mixed-lineage; all selected bundles official-eligible",
                }
            )
    return rows


def aggregate_tvm(rows: list[dict]) -> list[dict]:
    result = []
    matching_tasks = sorted(
        task
        for task in TVM_SELECTION
        if all(row["current_registry_match"] for row in rows if row["task"] == task)
    )
    mismatching_tasks = sorted(set(TVM_SELECTION) - set(matching_tasks))
    registry_status = (
        f"current-registry match: {', '.join(matching_tasks) or 'none'}; "
        f"frozen-registry selection: {', '.join(mismatching_tasks) or 'none'}"
    )
    for protocol in PROTOCOLS:
        group = [row for row in rows if row["protocol"] == protocol]

        def mean_present(field):
            values = [row[field] for row in group if row[field] is not None]
            return mean(values) if values else None

        result.append(
            {
                "lane": "TVM PR-hard candidate v0.4",
                "protocol": protocol,
                "successful_tasks": sum(row["final_success"] for row in group),
                "task_count": len(group),
                "success_rate": mean(float(row["final_success"]) for row in group),
                "mean_test_pass_rate": mean(row["final_pass_rate"] for row in group),
                "mean_ADPR": mean(row["ADPR"] for row in group),
                "mean_unresolved_dependencies": mean(
                    row["unresolved_dependency_count"] for row in group
                ),
                "penalized_DRS": mean(row["penalized_DRS"] for row in group),
                "penalized_CAIL": mean(row["penalized_CAIL"] for row in group),
                "mean_DRE": mean(row["DRE"] for row in group),
                "FSAR": mean_present("FSAR"),
                "IFR": mean_present("IFR"),
                "SVR": mean_present("SVR"),
                "MRR": mean_present("MRR"),
                "iteration_cap_hits": sum(
                    row["iteration_cap_hit_count"] for row in group
                ),
                "agent_attempts": sum(row["agent_attempt_count"] for row in group),
                "iteration_cap_hit_rate": (
                    sum(row["iteration_cap_hit_count"] for row in group)
                    / sum(row["agent_attempt_count"] for row in group)
                    if sum(row["agent_attempt_count"] for row in group)
                    else None
                ),
                "mean_tokens": mean(row["total_tokens"] for row in group),
                "mean_runtime_seconds": mean(row["runtime_seconds"] for row in group),
                "result_status": (
                    f"candidate/descriptive; recorded generation-valid; {registry_status}"
                ),
            }
        )
    return result


def empirical_tier(successful_protocols: int) -> str:
    if successful_protocols >= 3:
        return "Easy"
    if successful_protocols >= 1:
        return "Medium"
    return "Hard"


def build_taxonomy(all_runs: list[dict]) -> list[dict]:
    per_task_successes = defaultdict(int)
    per_task_dependencies = {}
    for row in all_runs:
        per_task_successes[row["task"]] += int(row["final_success"])
        per_task_dependencies[row["task"]] = row["dependency_count"]
    rows = []
    for task, (domain, fine_domain, languages, specialists) in TASK_INFO.items():
        tvm = task.startswith("apache-tvm-")
        successes = per_task_successes[task]
        rows.append(
            {
                "task": task,
                "lane": "TVM candidate" if tvm else "Commit0 official",
                "release_status": (
                    "pending human review; official_result_eligible=false"
                    if tvm
                    else "official v0.3 community-preview"
                ),
                "broad_domain": domain,
                "fine_domain": fine_domain,
                "implementation_languages": languages,
                "generated_or_interpreted_artifacts": TVM_ARTIFACT_LANGUAGES.get(task, "Python library behavior"),
                "specialists": specialists,
                "dependency_points": per_task_dependencies[task],
                "successful_protocols_out_of_4": successes,
                "qwen_empirical_difficulty": empirical_tier(successes),
            }
        )
    return rows


def svg_text(x, y, value, size=18, weight=400, fill="#172033", anchor="start"):
    return (
        f'<text x="{x}" y="{y}" font-family="Inter,Arial,sans-serif" '
        f'font-size="{size}" font-weight="{weight}" fill="{fill}" '
        f'text-anchor="{anchor}">{html.escape(str(value))}</text>'
    )


def write_protocol_figure(summaries: list[dict]) -> None:
    by_lane = {(row["lane"], row["protocol"]): row for row in summaries}
    width, height = 1440, 780
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#f7f9fc"/>',
        svg_text(60, 58, "Qwen3.6-27B: Commit0 vs. TVM PR-hard Candidates", 30, 700),
        svg_text(60, 88, "Macro-average over tasks; one selected run per task-condition", 17, 400, "#596579"),
    ]
    panels = [
        ("Final success rate", "success_rate"),
        ("Async Dependency Pass Rate (ADPR)", "mean_ADPR"),
        ("Final evaluator pass rate", "mean_test_pass_rate"),
    ]
    colors = {"Commit0 official v0.3": "#2f6fed", "TVM PR-hard candidate v0.4": "#ed6a5a"}
    lane_labels = {
        "Commit0 official v0.3": "Commit0 official (n=16)",
        "TVM PR-hard candidate v0.4": f"TVM candidates (n={len(TVM_SELECTION)})",
    }
    panel_width = 410
    for panel_index, (title, field) in enumerate(panels):
        left = 55 + panel_index * 465
        top = 145
        chart_height = 470
        parts.append(f'<rect x="{left}" y="{top}" width="{panel_width}" height="545" rx="14" fill="#ffffff" stroke="#dce2ec"/>')
        parts.append(svg_text(left + 22, top + 38, title, 20, 650))
        chart_left = left + 62
        chart_top = top + 75
        chart_bottom = chart_top + chart_height
        for tick in range(0, 101, 25):
            y = chart_bottom - chart_height * tick / 100
            parts.append(f'<line x1="{chart_left}" y1="{y:.1f}" x2="{left + panel_width - 18}" y2="{y:.1f}" stroke="#e5e9f0"/>')
            parts.append(svg_text(chart_left - 10, y + 5, f"{tick}%", 13, 400, "#687386", "end"))
        group_width = 76
        bar_width = 25
        for i, protocol in enumerate(PROTOCOLS):
            center = chart_left + 34 + i * group_width
            for j, lane in enumerate(colors):
                value = by_lane[(lane, protocol)][field]
                x = center - 27 + j * 30
                bar_height = value * chart_height
                y = chart_bottom - bar_height
                parts.append(f'<rect x="{x}" y="{y:.1f}" width="{bar_width}" height="{bar_height:.1f}" rx="3" fill="{colors[lane]}"/>')
                parts.append(svg_text(x + bar_width / 2, y - 7, f"{value * 100:.0f}", 11, 600, colors[lane], "middle"))
            label = PROTOCOL_LABELS[protocol]
            parts.append(svg_text(center, chart_bottom + 24, label, 12, 500, "#4e596b", "middle"))
    legend_y = 737
    x = 380
    for lane in colors:
        parts.append(f'<rect x="{x}" y="{legend_y - 14}" width="18" height="18" rx="3" fill="{colors[lane]}"/>')
        parts.append(svg_text(x + 27, legend_y, lane_labels[lane], 15, 500, "#354052"))
        x += 350
    parts.append('</svg>')
    PROTOCOL_FIGURE.write_text("\n".join(parts) + "\n", encoding="utf-8")


def heat_color(value: float) -> str:
    # Light sand at zero through teal at one.
    low = (247, 228, 221)
    high = (47, 111, 122)
    rgb = tuple(round(low[i] + (high[i] - low[i]) * value) for i in range(3))
    return "#%02x%02x%02x" % rgb


def write_tvm_figure(tvm_runs: list[dict]) -> None:
    lookup = {(row["task"], row["protocol"]): row for row in tvm_runs}
    tasks = list(TVM_SELECTION)
    successes = sum(row["final_success"] for row in tvm_runs)
    resolved = sum(row["resolved_dependency_count"] for row in tvm_runs)
    edge_instances = sum(row["dependency_count"] for row in tvm_runs)
    width, height = 1440, 730
    left, top, cell_w, cell_h = 225, 160, 270, 108
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#f7f9fc"/>',
        svg_text(55, 55, "TVM PR-hard Outcomes: Test Progress vs. Dependency Closure", 29, 700),
        svg_text(55, 88, "Cell fill = final evaluator pass rate; outline = zero / partial / complete dependency closure", 17, 400, "#596579"),
    ]
    for col, protocol in enumerate(PROTOCOLS):
        parts.append(svg_text(left + col * cell_w + (cell_w - 12) / 2, 132, PROTOCOL_LABELS[protocol], 17, 650, "#303a4c", "middle"))
    for row_index, task in enumerate(tasks):
        y = top + row_index * cell_h
        task_id = task.rsplit("-", 1)[-1]
        parts.append(svg_text(left - 22, y + 42, f"TVM #{task_id}", 19, 700, "#253047", "end"))
        short = {
            "apache-tvm-20073": "source spans",
            "apache-tvm-20107": "signature fan-out",
            "apache-tvm-20153": "PTX pipeline",
            "apache-tvm-20018": "Return IR chain",
        }[task]
        parts.append(svg_text(left - 22, y + 67, short, 14, 400, "#687386", "end"))
        for col, protocol in enumerate(PROTOCOLS):
            item = lookup[(task, protocol)]
            x = left + col * cell_w
            fill = heat_color(item["final_pass_rate"])
            text_fill = "#ffffff" if item["final_pass_rate"] > 0.68 else "#182235"
            closure = item["resolved_dependency_count"] / item["dependency_count"]
            stroke = "#d84444" if closure == 0 else "#d18b28" if closure < 1 else "#3b8f5a"
            parts.append(f'<rect x="{x}" y="{y}" width="{cell_w - 12}" height="{cell_h - 12}" rx="10" fill="{fill}" stroke="{stroke}" stroke-width="3"/>')
            parts.append(svg_text(x + (cell_w - 12) / 2, y + 38, f'Pass {item["final_pass_rate"] * 100:.1f}%', 19, 700, text_fill, "middle"))
            parts.append(svg_text(x + (cell_w - 12) / 2, y + 67, f'ADPR {item["resolved_dependency_count"]}/{item["dependency_count"]}', 17, 650, text_fill, "middle"))
    note_y = 625
    parts.append(f'<rect x="55" y="{note_y}" width="1330" height="70" rx="12" fill="#fff4f1" stroke="#efb6aa"/>')
    parts.append(svg_text(78, note_y + 28, f"Result: {successes}/{len(tvm_runs)} final successes and {resolved}/{edge_instances} dependency-edge instances resolved.", 18, 700, "#714316"))
    parts.append(svg_text(78, note_y + 53, "#20018 Serial closes both edges; #20018 Async-private closes one. High pass rate alone still does not imply closure.", 16, 400, "#5c4635"))
    parts.append('</svg>')
    TVM_FIGURE.write_text("\n".join(parts) + "\n", encoding="utf-8")


def stacked_bar(parts, x, y, width, height, counts, colors, labels, total):
    cursor = x
    for key, count in counts:
        segment = width * count / total
        parts.append(f'<rect x="{cursor:.1f}" y="{y}" width="{segment:.1f}" height="{height}" fill="{colors[key]}"/>')
        if segment > 70:
            parts.append(svg_text(cursor + segment / 2, y + height / 2 + 6, str(count), 17, 700, "#ffffff", "middle"))
        cursor += segment
    legend_y = y + height + 31
    cursor = x
    for key, count in counts:
        parts.append(f'<rect x="{cursor}" y="{legend_y - 14}" width="16" height="16" rx="2" fill="{colors[key]}"/>')
        parts.append(svg_text(cursor + 23, legend_y, f"{labels.get(key, key)} ({count})", 14, 500, "#475268"))
        cursor += max(150, len(labels.get(key, key)) * 7.3 + 55)


def write_taxonomy_figure(taxonomy: list[dict]) -> None:
    width, height = 1440, 780
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#f7f9fc"/>',
        svg_text(55, 55, f"AsynCodeBench Task Composition (16 Official + {len(TVM_SELECTION)} Candidate)", 29, 700),
        svg_text(55, 86, "Domain diversity is broad; implementation-language diversity remains limited", 17, 400, "#596579"),
    ]
    panels = [(45, 125, 1350, 175), (45, 325, 1350, 175), (45, 525, 1350, 205)]
    for x, y, w, h in panels:
        parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="14" fill="#ffffff" stroke="#dce2ec"/>')

    domain_order = [
        "General SWE / framework",
        "Systems / runtime / storage",
        "Network / protocol",
        "Security / cryptography",
        "Compiler / IR engineering",
    ]
    domain_labels = {
        "General SWE / framework": "General SWE",
        "Systems / runtime / storage": "Systems/runtime/storage",
        "Network / protocol": "Network/protocol",
        "Security / cryptography": "Security/crypto",
        "Compiler / IR engineering": "Compiler/IR",
    }
    domain_colors = {
        "General SWE / framework": "#2f6fed",
        "Systems / runtime / storage": "#497a52",
        "Network / protocol": "#d18b28",
        "Security / cryptography": "#8c5fb3",
        "Compiler / IR engineering": "#d85848",
    }
    domain_counts = Counter(row["broad_domain"] for row in taxonomy)
    parts.append(svg_text(72, 160, f"Primary domain ({len(taxonomy)}-task descriptive view)", 20, 650))
    stacked_bar(parts, 72, 185, 1295, 45, [(key, domain_counts[key]) for key in domain_order], domain_colors, domain_labels, len(taxonomy))

    language_counts = Counter(row["implementation_languages"] for row in taxonomy)
    language_colors = {"Python": "#2f6fed", "Python + C++": "#d85848"}
    parts.append(svg_text(72, 360, "Owned implementation languages", 20, 650))
    stacked_bar(parts, 72, 385, 1295, 45, [(key, language_counts[key]) for key in ["Python", "Python + C++"]], language_colors, {}, len(taxonomy))
    mixed_tvm = sum(
        row["lane"] == "TVM candidate" and row["implementation_languages"] == "Python + C++"
        for row in taxonomy
    )
    parts.append(svg_text(72, 482, f"All 16 official Commit0 tasks are Python; TVM adds {mixed_tvm} mixed Python/C++ tasks.", 15, 500, "#687386"))

    difficulty_counts = Counter(row["qwen_empirical_difficulty"] for row in taxonomy)
    difficulty_colors = {"Easy": "#3b8f5a", "Medium": "#d49a2a", "Hard": "#c84c4c"}
    parts.append(svg_text(72, 560, "Qwen-relative empirical difficulty", 20, 650))
    stacked_bar(parts, 72, 585, 1295, 45, [(key, difficulty_counts[key]) for key in ["Easy", "Medium", "Hard"]], difficulty_colors, {}, len(taxonomy))
    parts.append(svg_text(72, 690, "Easy = success in 3–4 protocols; Medium = 1–2; Hard = 0. This is model/run-specific, not an intrinsic task label.", 15, 500, "#687386"))
    parts.append('</svg>')
    TAXONOMY_FIGURE.write_text("\n".join(parts) + "\n", encoding="utf-8")


def pct(value):
    return "N/A" if value is None else f"{value * 100:.1f}%"


def metric(value, digits=2):
    return "N/A" if value is None else f"{value:.{digits}f}"


def write_report(
    taxonomy: list[dict], summaries: list[dict], all_runs: list[dict], tvm_runs: list[dict]
) -> None:
    summary_lookup = {(row["lane"], row["protocol"]): row for row in summaries}
    domain_counts = Counter(row["broad_domain"] for row in taxonomy)
    language_counts = Counter(row["implementation_languages"] for row in taxonomy)
    difficulty_groups = defaultdict(list)
    for row in taxonomy:
        difficulty_groups[row["qwen_empirical_difficulty"]].append(row["task"])
    tvm_task_count = len(TVM_SELECTION)
    tvm_run_count = len(tvm_runs)
    tvm_successes = sum(row["final_success"] for row in tvm_runs)
    tvm_edge_instances = sum(row["dependency_count"] for row in tvm_runs)
    tvm_resolved_edges = sum(row["resolved_dependency_count"] for row in tvm_runs)
    tvm_observed_drs = sum(row["raw_strict_DRS_observed_count"] for row in tvm_runs)
    current_registry_runs = sum(row["current_registry_match"] for row in tvm_runs)
    current_registry_tasks = sorted(
        task
        for task in TVM_SELECTION
        if all(row["current_registry_match"] for row in tvm_runs if row["task"] == task)
    )
    stale_registry_tasks = sorted(set(TVM_SELECTION) - set(current_registry_tasks))
    official_successes = sum(
        row["successful_tasks"]
        for row in summaries
        if row["lane"] == "Commit0 official v0.3"
    )

    lines = [
        "# Qwen3.6-27B on AsynCodeBench Commit0 and TVM PR-hard Candidates",
        "",
        "## Bottom line",
        "",
        f"This analysis separates the **16 official Commit0 v0.3 tasks** from the **{tvm_task_count} non-official TVM PR-hard v0.4 candidates**. The latter remain pending mandatory human review and have `official_result_eligible=false`; the {len(taxonomy)}-task view below is therefore descriptive rather than a new official release composition.",
        "",
        f"- Domain coverage is broad: 7 general SWE/framework, 6 systems/runtime/storage, 2 network/protocol, 1 security/cryptography, and {domain_counts['Compiler / IR engineering']} compiler/IR candidates.",
        f"- The tasks do **not** use {len(taxonomy)} different languages. All 16 official tasks have Python-owned implementation surfaces. TVM #20073, #20107, and #20018 add mixed Python/C++ surfaces; TVM #20153 remains Python-owned while generating/interpreting TIRx and PTX artifacts.",
        f"- Commit0 contains 47 dependency edges (**2.94 per task**); the TVM candidates contain {sum(row['dependency_points'] for row in taxonomy if row['lane'] == 'TVM candidate')} (**2.0 per task**). The TVM edge count per task is lower, but each edge crosses deeper compiler layers such as Python/C++, FFI, parser, IR, and printer/code generation.",
        "- On Commit0, CAID is the strongest condition: **14/16 final successes (87.5%)**, **96.3%** mean evaluator pass rate, and **95.8% ADPR**.",
        f"- On the {tvm_task_count} TVM candidates, Qwen records **{tvm_successes}/{tvm_run_count} final successes** and resolves **{tvm_resolved_edges}/{tvm_edge_instances} dependency-edge instances** across four conditions. The only full success is #20018 under Serial; TVM remains substantially harder for this model under these runs.",
        "- The corrected #20018 CAID termination statistic is **5/5 specialist attempts hitting the fixed 100-iteration cap**. The correction is SHA-pinned to the immutable source bundle and raw outputs.",
        "- TVM #20107 is the key diagnostic example: async-private and CAID both pass **499/503 (99.2%)** evaluator tests but still have **ADPR 0/2** because the Relax and TIRx round-trip contracts remain unresolved.",
        "",
        "![Task taxonomy](figures/asynccodebench_task_taxonomy.svg)",
        "",
        "## Task taxonomy",
        "",
        "The primary domain is assigned by the scoped evaluator and owned implementation work, not by every feature of the upstream project.",
        "",
        "| Task | Lane | Primary domain | Fine-grained focus | Implementation language(s) | Edges | Specialists | Qwen tier |",
        "| --- | --- | --- | --- | --- | ---: | ---: | --- |",
    ]
    for row in taxonomy:
        lines.append(
            f'| {row["task"]} | {row["lane"]} | {row["broad_domain"]} | {row["fine_domain"]} | {row["implementation_languages"]} | {row["dependency_points"]} | {row["specialists"]} | {row["qwen_empirical_difficulty"]} ({row["successful_protocols_out_of_4"]}/4) |'
        )

    lines.extend(
        [
            "",
            "### Domain and language totals",
            "",
            f"| View | Category | Count | Share of {len(taxonomy)} |",
            "| --- | --- | ---: | ---: |",
        ]
    )
    for domain in [
        "General SWE / framework",
        "Systems / runtime / storage",
        "Network / protocol",
        "Security / cryptography",
        "Compiler / IR engineering",
    ]:
        lines.append(f"| Domain | {domain} | {domain_counts[domain]} | {domain_counts[domain] / len(taxonomy) * 100:.1f}% |")
    for language in ["Python", "Python + C++"]:
        lines.append(f"| Owned language | {language} | {language_counts[language]} | {language_counts[language] / len(taxonomy) * 100:.1f}% |")

    lines.extend(
        [
            "",
            "TIRx, Relax IR, TVMScript, and PTX are important compiler-stack artifacts, but they should not be counted as additional implementation languages in this table. The accurate claim is that TVM increases **cross-layer and cross-language depth**, while the benchmark remains Python-heavy.",
            "",
            "## Easy / medium / hard classification",
            "",
            "To avoid a subjective label, the table uses a Qwen-specific empirical rule based only on final evaluator success across the four matched conditions:",
            "",
            "- **Easy:** success in 3–4 protocols.",
            "- **Medium:** success in 1–2 protocols.",
            "- **Hard:** success in 0 protocols.",
            "",
            "This is **not an intrinsic benchmark difficulty label**. It depends on this model, these selected runs, and the protocol set. In particular, a task solved only by CAID is Medium rather than Easy.",
            "",
            "| Tier | Count | Tasks |",
            "| --- | ---: | --- |",
        ]
    )
    for tier in ["Easy", "Medium", "Hard"]:
        tasks = sorted(difficulty_groups[tier])
        lines.append(f"| {tier} | {len(tasks)} | {', '.join(tasks)} |")

    run_lookup = {(row["task"], row["protocol"]): row for row in all_runs}
    lines.extend(
        [
            "",
            "## Complete task-condition matrix",
            "",
            "Each cell reports `final success; evaluator pass rate; resolved edges / total edges`. A cross means the task is not solved even when its partial pass rate is high.",
            "",
            "| Task | Result provenance | Single | Serial | Async private | CAID |",
            "| --- | --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for task in TASK_INFO:
        task_rows = [run_lookup[(task, protocol)] for protocol in PROTOCOLS]
        if task.startswith("apache-tvm-"):
            provenance = (
                "candidate; current registry"
                if all(row["current_registry_match"] for row in task_rows)
                else "candidate; frozen registry"
            )
        else:
            provenance = "official selected bundle"
        cells = []
        for row in task_rows:
            mark = "✓" if row["final_success"] else "✗"
            cells.append(
                f'{mark}; {pct(row["final_pass_rate"])}; '
                f'{row["resolved_dependency_count"]}/{row["dependency_count"]}'
            )
        lines.append(f"| {task} | {provenance} | {' | '.join(cells)} |")

    lines.extend(
        [
            "",
            "## Qwen3.6-27B results by protocol",
            "",
            "![Protocol comparison](figures/qwen36_27_commit0_vs_tvm_protocol.svg)",
            "",
            "Each row is a macro-average over tasks, so the large TVM #20107 evaluator does not dominate the other TVM tasks.",
            "",
            "| Lane | Protocol | Final success | Pass | ADPR | Unresolved | DRS penalized ↓ | CAIL penalized ↓ | DRE ↑ | FSAR ↓ | IFR ↓ | SVR ↓ | MRR ↑ | Cap hits | Tokens | Runtime |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for lane in ["Commit0 official v0.3", "TVM PR-hard candidate v0.4"]:
        for protocol in PROTOCOLS:
            row = summary_lookup[(lane, protocol)]
            cap_hits = (
                "N/A"
                if row["iteration_cap_hits"] is None
                else f'{row["iteration_cap_hits"]}/{row["agent_attempts"]} '
                f'({pct(row["iteration_cap_hit_rate"])})'
            )
            lines.append(
                f'| {lane} | {PROTOCOL_LABELS[protocol]} | {row["successful_tasks"]}/{row["task_count"]} ({pct(row["success_rate"])}) | {pct(row["mean_test_pass_rate"])} | {pct(row["mean_ADPR"])} | {row["mean_unresolved_dependencies"]:.3f} | {row["penalized_DRS"]:.3f} | {row["penalized_CAIL"]:.3f} | {pct(row["mean_DRE"])} | {pct(row["FSAR"])} | {pct(row["IFR"])} | {pct(row["SVR"])} | {pct(row["MRR"])} | {cap_hits} | {row["mean_tokens"] / 1_000_000:.3f}M | {row["mean_runtime_seconds"] / 60:.1f} min |'
            )

    lines.extend(
        [
            "",
            "### How to read the proposed metrics",
            "",
            "- **Final success / pass rate** measures the final public evaluator. Pass rate captures partial progress but is not a solved-task criterion.",
            "- **ADPR** is resolved dependency points divided by all dependency points. It requires the integrated checker group for an edge to pass.",
            "- **DRS penalized** assigns unresolved edges checkpoint `T+1`; lower is better. **DRE** normalizes resolution timing; unresolved edges receive zero.",
            "- **CAIL penalized** measures consumer lag after producer behavior becomes available, and penalizes a consumer that never catches up; lower is better.",
            "- **FSAR, IFR, SVR, MRR** diagnose failed specialist artifacts, semantic/textual integration failure, ownership-scope violations, and manager recovery. For single-agent runs, SVR and MRR are structurally not applicable.",
            "- **Cap hits** counts specialist attempts that consume the fixed 100-iteration budget. It is a cost/capability diagnostic, not an infrastructure failure.",
            "",
            f"Strict raw DRS is observed for {tvm_observed_drs}/{tvm_edge_instances} TVM edge instances: both #20018 Serial edges and one #20018 Async-private edge. Penalized DRS/CAIL and DRE retain the remaining {tvm_edge_instances - tvm_observed_drs} unresolved instances in aggregate instead of dropping them as missing data.",
            "The TVM penalized values in this report are deterministically derived from each frozen `strict_dependency_metrics.json` using the current formulas in `docs/EVALUATION_METRICS.md`.",
            "",
            "## TVM candidate detail",
            "",
            "![TVM heatmap](figures/qwen36_27_tvm_task_protocol_heatmap.svg)",
            "",
            "| Task | Topology | Protocol | Final result | ADPR | DRS penalty | CAIL penalty | FSAR | IFR | SVR | MRR |",
            "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    topology = {
        "apache-tvm-20073": "2 producers → parser/evaluator consumer",
        "apache-tvm-20107": "shared Script core → Relax + TIRx fan-out",
        "apache-tvm-20153": "schema → lowering → rendering chain",
        "apache-tvm-20018": "Return IR → TVMScript → lowering/codegen chain",
    }
    for task in TVM_SELECTION:
        for row in [item for item in tvm_runs if item["task"] == task]:
            lines.append(
                f'| {task} | {topology[task]} | {PROTOCOL_LABELS[row["protocol"]]} | {row["final_tests_passed"]}/{row["final_tests_collected"]} ({pct(row["final_pass_rate"])}) | {row["resolved_dependency_count"]}/{row["dependency_count"]} | {row["penalized_DRS"]:.2f} | {row["penalized_CAIL"]:.2f} | {pct(row["FSAR"])} | {pct(row["IFR"])} | {pct(row["SVR"])} | {pct(row["MRR"])} |'
            )

    lines.extend(
        [
            "",
            "The four topologies are deliberately different: #20073 is a two-producer join, #20107 is a shared-core fan-out, and #20153 and #20018 are sequential compiler pipelines over different surfaces. All have two dependency edges, but edge count alone understates their Python/C++/FFI/parser/IR/printer/lowering depth.",
            "",
            "## Interpretation",
            "",
            f"1. **The TVM extension increases empirical difficulty for Qwen3.6-27B.** Commit0 has {official_successes} successful task-condition pairs out of 64, while TVM has {tvm_successes} out of {tvm_run_count}. TVM resolves only {tvm_resolved_edges}/{tvm_edge_instances} labeled edge instances.",
            "2. **The best coordination condition is task-dependent at TVM difficulty.** CAID dominates the Commit0 lane, but #20018 is solved only by Serial (2/2 edges); Async-private closes one edge and CAID closes none. The fixed 100-iteration cap is therefore exposing a real capability/cost limit rather than guaranteeing that more manager work succeeds.",
            "3. **Pass rate and dependency closure answer different questions.** The 99.2% pass rate on #20107 async/CAID looks nearly solved, yet both exact round-trip edges fail. Conversely, #20018 Async-private passes 778/785 tests and closes only one of two edges. ADPR prevents either near-pass from being reported as complete integration.",
            f"4. **Do not claim significance or universal model hardness yet.** There is one selected run per task-condition, only {tvm_task_count} TVM candidates, and no confidence intervals or repeated seeds.",
            "",
            "## Admission and data-quality caveats",
            "",
            "- The 64 selected Commit0 bundles are valid and official-aggregate eligible, but the aggregate is **mixed-lineage**: four benchmark revisions and three generation-configuration hashes. It is descriptive, not a lineage-homogeneous official campaign.",
            f"- All {tvm_run_count} selected TVM bundles recorded generation-valid status at creation and use the standard-100 profile, but all {tvm_task_count} tasks remain candidate-lane and pending mandatory human review.",
            f"- Current checksum validation passes {current_registry_runs}/{tvm_run_count} TVM bundles against the latest whole-registry hash: {', '.join('#' + task.rsplit('-', 1)[-1] for task in current_registry_tasks)}. The remaining bundles ({', '.join('#' + task.rsplit('-', 1)[-1] for task in stale_registry_tasks)}) report only `recorded_release_index_mismatch`; all other bundle checks pass. Because their run-relevant task/config/evaluator inputs were not changed, this report retains them as frozen-registry comparable results rather than treating the model measurements as invalid.",
            "- For #20107 single and serial, raw pytest summaries contain 2 and 1 collection errors respectively, while `run_bundle.json` records `errors=0`. Final success is still false, but the bundle error field should be repaired before release use. The reported pass rate follows the frozen bundle convention (`passed / collected`).",
            "- For #20018 CAID, all five raw specialist attempts reached the fixed 100-iteration cap. The frozen legacy summary recorded zero because it predates structured termination fields. This report applies `apache-tvm-20018-caid-legacy-cap-hit-v1`, a SHA-verified analysis-only correction; the source bundle is not rewritten and no model rerun is required.",
            "- Process diagnostics such as SAD/SAR remain proxy-level unless structured visibility evidence or human trajectory audit is available; they are not used for the headline conclusion here.",
            "",
            "## Reproduction",
            "",
            "```bash",
            "cd /home/kzhang42/AsyncCodeBench",
            "python scripts/build_qwen36_commit0_tvm_analysis.py",
            "```",
            "",
            "Generated data files:",
            "",
            "- `docs/results/qwen36_27_task_taxonomy.csv`",
            "- `docs/results/qwen36_27_commit0_tvm_per_run.csv`",
            "- `docs/results/qwen36_27_commit0_tvm_summary_by_protocol.csv`",
            "- `docs/results/qwen36_27_statistical_corrections.v1.json`",
            "- `docs/results/qwen36_27_frozen_result_index.v1.json`",
        ]
    )
    REPORT_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_frozen_result_index(all_runs: list[dict]) -> None:
    entries = []
    for row in all_runs:
        run_dir = ROOT / row["run_dir"]
        artifact_hashes = {}
        for filename in (
            "run_bundle.json",
            "process_metrics_summary.json",
            "strict_dependency_metrics.json",
            "report.json",
        ):
            path = run_dir / filename
            artifact_hashes[filename] = sha256_file(path) if path.is_file() else None
        entries.append(
            {
                "task": row["task"],
                "protocol": row["protocol"],
                "run_id": row["run_id"],
                "run_dir": row["run_dir"],
                "lane": row["lane"],
                "model": "Qwen3.6-27B",
                "artifact_sha256": artifact_hashes,
                "statistics_correction_id": row.get("statistics_correction_id") or None,
            }
        )
    payload = {
        "schema_version": "qwen36-frozen-result-index-v1",
        "model": "Qwen3.6-27B",
        "task_count": len({row["task"] for row in all_runs}),
        "protocol_count": len(PROTOCOLS),
        "result_cell_count": len(all_runs),
        "selection_policy": (
            "Explicit run IDs only; never select the best rerun. Whole-registry hash "
            "changes do not invalidate a frozen run when all run-relevant bundle checks pass."
        ),
        "statistical_corrections": {
            "path": str(STATISTICAL_CORRECTIONS.relative_to(ROOT)),
            "sha256": sha256_file(STATISTICAL_CORRECTIONS),
        },
        "entries": entries,
    }
    FROZEN_INDEX_OUT.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def main() -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)
    official_runs = read_official_runs()
    tvm_runs = read_tvm_runs()
    all_runs = official_runs + tvm_runs
    summaries = official_summaries() + aggregate_tvm(tvm_runs)
    taxonomy = build_taxonomy(all_runs)

    per_run_fields = [
        "lane", "task", "protocol", "run_id", "run_dir",
        "bundle_generation_status", "current_registry_match", "official_result_eligible",
        "final_success", "final_pass_rate", "final_tests_passed", "final_tests_collected",
        "final_tests_failed", "final_test_errors_recorded", "raw_pytest_summary",
        "dependency_count", "resolved_dependency_count", "unresolved_dependency_count", "ADPR",
        "checkpoint_count", "penalized_DRS", "penalized_CAIL", "DRE",
        "raw_strict_DRS_mean", "raw_strict_DRS_observed_count",
        "raw_strict_CAIL_mean", "raw_strict_CAIL_observed_count",
        "FSAR", "IFR", "SVR", "MRR", "total_tokens", "runtime_seconds",
        "iteration_cap_hit_count", "agent_attempt_count", "iteration_cap_hit_rate",
        "termination_reason_counts", "statistics_correction_id",
        "benchmark_revision", "generation_configuration_sha256", "execution_profile",
    ]
    summary_fields = [
        "lane", "protocol", "successful_tasks", "task_count", "success_rate",
        "mean_test_pass_rate", "mean_ADPR", "mean_unresolved_dependencies",
        "penalized_DRS", "penalized_CAIL", "mean_DRE", "FSAR", "IFR", "SVR", "MRR",
        "iteration_cap_hits", "agent_attempts", "iteration_cap_hit_rate",
        "mean_tokens", "mean_runtime_seconds", "result_status",
    ]
    taxonomy_fields = [
        "task", "lane", "release_status", "broad_domain", "fine_domain",
        "implementation_languages", "generated_or_interpreted_artifacts", "specialists",
        "dependency_points", "successful_protocols_out_of_4", "qwen_empirical_difficulty",
    ]
    write_csv(PER_RUN_OUT, all_runs, per_run_fields)
    write_csv(SUMMARY_OUT, summaries, summary_fields)
    write_csv(TAXONOMY_OUT, taxonomy, taxonomy_fields)
    write_frozen_result_index(all_runs)
    write_protocol_figure(summaries)
    write_tvm_figure(tvm_runs)
    write_taxonomy_figure(taxonomy)
    write_report(taxonomy, summaries, all_runs, tvm_runs)
    print(f"Wrote {REPORT_OUT.relative_to(ROOT)}")
    print(f"Wrote {PER_RUN_OUT.relative_to(ROOT)}")
    print(f"Wrote {SUMMARY_OUT.relative_to(ROOT)}")
    print(f"Wrote {TAXONOMY_OUT.relative_to(ROOT)}")
    print(f"Wrote {FROZEN_INDEX_OUT.relative_to(ROOT)}")
    print(f"Wrote {PROTOCOL_FIGURE.relative_to(ROOT)}")
    print(f"Wrote {TVM_FIGURE.relative_to(ROOT)}")
    print(f"Wrote {TAXONOMY_FIGURE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
