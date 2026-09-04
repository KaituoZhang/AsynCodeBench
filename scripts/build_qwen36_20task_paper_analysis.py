#!/usr/bin/env python3
"""Build paper-facing metrics for the unified 20-task AsynCodeBench suite.

The benchmark's dependency metrics are primary. Conventional coding outcomes
and resource usage are supporting measurements. All 20 adapted repository
tasks are analyzed as one benchmark population in every paper-facing
aggregate, table, figure, and claim.
"""

from __future__ import annotations

import csv
import hashlib
import html
import json
from pathlib import Path
from statistics import mean


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "docs" / "results"
FIGURES = RESULTS / "figures"
PER_RUN_SOURCE = RESULTS / "qwen36_27_commit0_tvm_per_run.csv"
TAXONOMY_SOURCE = RESULTS / "qwen36_27_task_taxonomy.csv"
FROZEN_INDEX_SOURCE = RESULTS / "qwen36_27_frozen_result_index.v1.json"

PROTOCOL_TABLE = RESULTS / "qwen36_27_paper_protocol_table.csv"
TASK_TABLE = RESULTS / "qwen36_27_paper_task_table.csv"
CONTRAST_TABLE = RESULTS / "qwen36_27_paper_protocol_contrasts.csv"
REPORT = RESULTS / "QWEN36_27_20TASK_PAPER_ANALYSIS.md"
OUTCOME_FIGURE = FIGURES / "qwen36_27_20task_outcome_heatmap.svg"
DEPENDENCY_FIGURE = FIGURES / "qwen36_27_dependency_coordination_profile.svg"
PROCESS_FIGURE = FIGURES / "qwen36_27_20task_coordination_diagnostics.svg"
CONTRAST_FIGURE = FIGURES / "qwen36_27_20task_async_effects.svg"
PROVENANCE = RESULTS / "qwen36_27_paper_analysis_provenance.v1.json"

PROTOCOLS = ["single", "serial_specialists", "async_private", "caid_manager"]
PROTOCOL_LABEL = {
    "single": "Single",
    "serial_specialists": "Serial",
    "async_private": "Async private",
    "caid_manager": "CAID",
}
PROTOCOL_COLOR = {
    "single": "#667085",
    "serial_specialists": "#3366ad",
    "async_private": "#d2872c",
    "caid_manager": "#268368",
}
TASK_ORDER = [
    "cachetools", "deprecated", "portalocker", "tinydb", "wcwidth",
    "requests", "simpy", "parsel", "filesystem_spec", "marshmallow",
    "graphene", "imapclient", "pexpect", "flask", "python-rsa",
    "cookiecutter", "apache-tvm-20073", "apache-tvm-20107",
    "apache-tvm-20153", "apache-tvm-20018",
]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def optional_float(value: str) -> float | None:
    return None if value == "" else float(value)


def load_rows() -> list[dict]:
    with PER_RUN_SOURCE.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    numeric = [
        "final_pass_rate", "dependency_count", "resolved_dependency_count",
        "unresolved_dependency_count", "ADPR", "checkpoint_count",
        "penalized_DRS", "penalized_CAIL", "DRE", "FSAR", "IFR", "SVR",
        "MRR", "total_tokens", "runtime_seconds", "iteration_cap_hit_count",
        "agent_attempt_count", "iteration_cap_hit_rate",
    ]
    for row in rows:
        row["final_success"] = row["final_success"] == "True"
        for field in numeric:
            row[field] = optional_float(row[field])
        process_path = ROOT / row["run_dir"] / "process_metrics_summary.json"
        process = json.loads(process_path.read_text(encoding="utf-8"))
        stale = process["process_metrics"]["stale_assumption_incident_count"]
        sar = process["formal_metrics"]["SAR"]
        row["SAD_proxy_candidate_count"] = int(stale["automatic_proxy_count"])
        row["SAD_proxy_run_indicator"] = float(sar["run_level_proxy_indicator"])
        row["strict_SAD_value"] = sar["value"]
        row["strict_SAD_status"] = sar["status"]
    return rows


def load_taxonomy() -> dict[str, dict]:
    with TAXONOMY_SOURCE.open(encoding="utf-8", newline="") as handle:
        return {row["task"]: row for row in csv.DictReader(handle)}


def validate_frozen_selection(rows: list[dict]) -> None:
    frozen = json.loads(FROZEN_INDEX_SOURCE.read_text(encoding="utf-8"))
    cells = {(row["task"], row["protocol"], row["run_id"]) for row in rows}
    indexed = {
        (entry["task"], entry["protocol"], entry["run_id"])
        for entry in frozen["entries"]
    }
    if len(rows) != 80 or len(cells) != 80 or cells != indexed:
        raise RuntimeError("expected 80 CSV cells identical to the frozen index")
    if {row["task"] for row in rows} != set(TASK_ORDER):
        raise RuntimeError("unexpected 20-task set")
    for task in TASK_ORDER:
        observed = {row["protocol"] for row in rows if row["task"] == task}
        if observed != set(PROTOCOLS):
            raise RuntimeError(f"incomplete protocol matrix for {task}")
    for entry in frozen["entries"]:
        run_dir = ROOT / entry["run_dir"]
        for filename, expected in entry["artifact_sha256"].items():
            if expected is None:
                continue
            if sha256_file(run_dir / filename) != expected:
                raise RuntimeError(
                    f"frozen artifact mismatch: {entry['task']} / "
                    f"{entry['protocol']} / {filename}"
                )
    statuses = {row["strict_SAD_status"] for row in rows}
    if statuses != {"requires_human_or_structured_visibility_audit"}:
        raise RuntimeError(f"unexpected SAD/SAR evidence status: {statuses}")
    if any(row["strict_SAD_value"] is not None for row in rows):
        raise RuntimeError("strict SAD/SAR unexpectedly populated")
    corrected = [row for row in rows if row["statistics_correction_id"]]
    if len(corrected) != 1 or (
        corrected[0]["task"], corrected[0]["protocol"]
    ) != ("apache-tvm-20018", "caid_manager"):
        raise RuntimeError("unexpected statistical-correction scope")


def mean_present(rows: list[dict], field: str) -> float | None:
    values = [row[field] for row in rows if row[field] is not None]
    return mean(values) if values else None


def aggregate_protocol(rows: list[dict], protocol: str) -> dict:
    group = [row for row in rows if row["protocol"] == protocol]
    resolved = sum(row["resolved_dependency_count"] for row in group)
    edges = sum(row["dependency_count"] for row in group)
    cap_rows = [row for row in group if row["agent_attempt_count"] is not None]
    cap_hits = sum(row["iteration_cap_hit_count"] for row in cap_rows)
    cap_attempts = sum(row["agent_attempt_count"] for row in cap_rows)
    return {
        "protocol": protocol,
        "task_count": len(group),
        "successful_tasks": sum(row["final_success"] for row in group),
        "success_rate": mean(float(row["final_success"]) for row in group),
        "mean_test_pass_rate": mean(row["final_pass_rate"] for row in group),
        "macro_ADPR": mean(row["ADPR"] for row in group),
        "resolved_edge_instances": resolved,
        "edge_instances": edges,
        "micro_ADPR": resolved / edges,
        "mean_unresolved_dependencies": mean(
            row["unresolved_dependency_count"] for row in group
        ),
        "full_ADPR_task_count": sum(row["ADPR"] == 1.0 for row in group),
        "positive_ADPR_task_count": sum(row["ADPR"] > 0.0 for row in group),
        "mean_checkpoint_count": mean(row["checkpoint_count"] for row in group),
        "penalized_DRS": mean(row["penalized_DRS"] for row in group),
        "penalized_CAIL": mean(row["penalized_CAIL"] for row in group),
        "mean_DRE": mean(row["DRE"] for row in group),
        "strict_SAD": None,
        "strict_SAR": None,
        "SAD_SAR_status": "not estimable from current visibility traces",
        "SAD_proxy_candidate_count": sum(
            row["SAD_proxy_candidate_count"] for row in group
        ),
        "SAD_proxy_run_indicator_rate": mean(
            row["SAD_proxy_run_indicator"] for row in group
        ),
        "FSAR": mean_present(group, "FSAR"),
        "IFR": mean_present(group, "IFR"),
        "SVR": mean_present(group, "SVR"),
        "MRR": mean_present(group, "MRR"),
        "mean_tokens": mean(row["total_tokens"] for row in group),
        "mean_runtime_seconds": mean(row["runtime_seconds"] for row in group),
        "observed_iteration_cap_hits": cap_hits if cap_rows else None,
        "observed_termination_attempts": cap_attempts if cap_rows else None,
        "termination_instrumented_task_count": len(cap_rows),
    }


def build_protocol_table(rows: list[dict]) -> list[dict]:
    return [aggregate_protocol(rows, protocol) for protocol in PROTOCOLS]


def build_task_table(rows: list[dict], taxonomy: dict[str, dict]) -> list[dict]:
    output = []
    for task in TASK_ORDER:
        group = {row["protocol"]: row for row in rows if row["task"] == task}
        record = {
            "task": task,
            "broad_domain": taxonomy[task]["broad_domain"],
            "specialists": int(taxonomy[task]["specialists"]),
            "dependency_points": int(taxonomy[task]["dependency_points"]),
        }
        for protocol in PROTOCOLS:
            row = group[protocol]
            prefix = protocol
            record.update(
                {
                    f"{prefix}_success": row["final_success"],
                    f"{prefix}_pass_rate": row["final_pass_rate"],
                    f"{prefix}_ADPR": row["ADPR"],
                    f"{prefix}_resolved_dependencies": int(
                        row["resolved_dependency_count"]
                    ),
                    f"{prefix}_unresolved_dependencies": int(
                        row["unresolved_dependency_count"]
                    ),
                    f"{prefix}_DRS_penalized": row["penalized_DRS"],
                    f"{prefix}_CAIL_penalized": row["penalized_CAIL"],
                    f"{prefix}_DRE": row["DRE"],
                    f"{prefix}_FSAR": row["FSAR"],
                    f"{prefix}_IFR": row["IFR"],
                    f"{prefix}_SVR": row["SVR"],
                    f"{prefix}_MRR": row["MRR"],
                    f"{prefix}_tokens": int(row["total_tokens"]),
                    f"{prefix}_runtime_seconds": row["runtime_seconds"],
                }
            )
        output.append(record)
    return output


def direction_delta(comparison: dict, baseline: dict, field: str) -> float:
    return comparison[field] - baseline[field]


def build_contrasts(protocol_rows: list[dict], run_rows: list[dict]) -> list[dict]:
    lookup = {row["protocol"]: row for row in protocol_rows}
    by_cell = {(row["task"], row["protocol"]): row for row in run_rows}
    specs = [
        ("serial_specialists", "async_private", "Async visibility loss"),
        ("async_private", "caid_manager", "CAID recovery"),
        ("single", "caid_manager", "CAID versus single"),
    ]
    output = []
    for base_id, comparison_id, question in specs:
        base = lookup[base_id]
        comparison = lookup[comparison_id]
        adpr_cmp = []
        pass_cmp = []
        for task in TASK_ORDER:
            a = by_cell[(task, base_id)]
            b = by_cell[(task, comparison_id)]
            adpr_cmp.append((b["ADPR"] > a["ADPR"]) - (b["ADPR"] < a["ADPR"]))
            pass_cmp.append(
                (b["final_pass_rate"] > a["final_pass_rate"])
                - (b["final_pass_rate"] < a["final_pass_rate"])
            )
        record = {
            "research_question": question,
            "baseline_protocol": base_id,
            "comparison_protocol": comparison_id,
            "success_rate_delta": direction_delta(comparison, base, "success_rate"),
            "test_pass_rate_delta": direction_delta(
                comparison, base, "mean_test_pass_rate"
            ),
            "ADPR_delta": direction_delta(comparison, base, "macro_ADPR"),
            "ADPR_task_wins": sum(value > 0 for value in adpr_cmp),
            "ADPR_task_ties": sum(value == 0 for value in adpr_cmp),
            "ADPR_task_losses": sum(value < 0 for value in adpr_cmp),
            "pass_task_wins": sum(value > 0 for value in pass_cmp),
            "pass_task_ties": sum(value == 0 for value in pass_cmp),
            "pass_task_losses": sum(value < 0 for value in pass_cmp),
            "unresolved_dependency_delta": direction_delta(
                comparison, base, "mean_unresolved_dependencies"
            ),
            "DRE_delta": direction_delta(comparison, base, "mean_DRE"),
            "DRS_penalized_delta": direction_delta(
                comparison, base, "penalized_DRS"
            ),
            "CAIL_penalized_delta": direction_delta(
                comparison, base, "penalized_CAIL"
            ),
            "FSAR_delta": direction_delta(comparison, base, "FSAR"),
            "IFR_delta": direction_delta(comparison, base, "IFR"),
            "SVR_delta": (
                None
                if base["SVR"] is None or comparison["SVR"] is None
                else direction_delta(comparison, base, "SVR")
            ),
            "MRR_delta": (
                None
                if base["MRR"] is None or comparison["MRR"] is None
                else direction_delta(comparison, base, "MRR")
            ),
            "token_ratio": comparison["mean_tokens"] / base["mean_tokens"],
            "runtime_ratio": (
                comparison["mean_runtime_seconds"] / base["mean_runtime_seconds"]
            ),
        }
        output.append(record)
    return output


def csv_value(value):
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, float):
        return f"{value:.12g}"
    return value


def write_csv(path: Path, rows: list[dict]) -> None:
    fields = list(rows[0])
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: csv_value(row[field]) for field in fields})


def svg_text(x, y, value, size=16, weight=400, fill="#172033", anchor="start"):
    return (
        f'<text x="{x}" y="{y}" font-family="Inter,Arial,sans-serif" '
        f'font-size="{size}" font-weight="{weight}" fill="{fill}" '
        f'text-anchor="{anchor}">{html.escape(str(value))}</text>'
    )


def heat_color(value: float) -> str:
    low = (247, 231, 225)
    high = (37, 125, 108)
    value = max(0.0, min(1.0, value))
    rgb = tuple(round(low[i] + (high[i] - low[i]) * value) for i in range(3))
    return "#%02x%02x%02x" % rgb


def write_dependency_figure(protocol_rows: list[dict]) -> None:
    lookup = {row["protocol"]: row for row in protocol_rows}
    panels = [
        ("ADPR ↑", "macro_ADPR", 1.0, "percent"),
        ("Unresolved ↓", "mean_unresolved_dependencies", 2.5, "number"),
        ("DRE ↑", "mean_DRE", 1.0, "percent"),
        ("DRS-P ↓", "penalized_DRS", 12.0, "number"),
        ("CAIL-P ↓", "penalized_CAIL", 8.0, "number"),
    ]
    width, height = 1860, 720
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#f7f9fc"/>',
        svg_text(48, 50, "AsynCodeBench Dependency Metrics on the Unified 20-Task Suite", 29, 700),
        svg_text(48, 80, "Task-macro ADPR and strict-checkpoint timing; unresolved dependencies receive run-local T+1-based penalties", 16, 400, "#596579"),
    ]
    panel_w = 348
    for panel_index, (title, field, scale, value_kind) in enumerate(panels):
        x = 40 + panel_index * 362
        parts.append(f'<rect x="{x}" y="115" width="{panel_w}" height="525" rx="13" fill="#ffffff" stroke="#dce2ec"/>')
        parts.append(svg_text(x + 22, 153, title, 20, 700))
        for row_index, protocol in enumerate(PROTOCOLS):
            row = lookup[protocol]
            value = row[field]
            y = 205 + row_index * 98
            parts.append(svg_text(x + 22, y, PROTOCOL_LABEL[protocol], 14, 650, PROTOCOL_COLOR[protocol]))
            bar_w = 280 * min(value / scale, 1.0)
            parts.append(f'<rect x="{x + 22}" y="{y + 14}" width="280" height="27" rx="5" fill="#edf0f5"/>')
            parts.append(f'<rect x="{x + 22}" y="{y + 14}" width="{bar_w}" height="27" rx="5" fill="{PROTOCOL_COLOR[protocol]}"/>')
            label = f"{value * 100:.1f}%" if value_kind == "percent" else f"{value:.2f}"
            parts.append(svg_text(x + 312, y + 35, label, 14, 700, "#263247", "end"))
        direction = "higher is better" if "↑" in title else "lower is better"
        parts.append(svg_text(x + 22, 605, direction, 13, 500, "#687386"))
    parts.append(svg_text(48, 683, "DRS-P and CAIL-P must be read with ADPR, DRE, and checkpoint count because protocols observe different numbers of checkpoints.", 14, 500, "#596579"))
    parts.append('</svg>')
    DEPENDENCY_FIGURE.write_text("\n".join(parts) + "\n", encoding="utf-8")


def write_process_figure(protocol_rows: list[dict]) -> None:
    lookup = {row["protocol"]: row for row in protocol_rows}
    panels = [
        ("FSAR ↓", "FSAR", "Failed subagent attempts"),
        ("IFR ↓", "IFR", "Runs with integration failure"),
        ("SVR ↓", "SVR", "Out-of-scope attempts"),
        ("MRR†", "MRR", "Conditional manager recovery"),
    ]
    width, height = 1540, 700
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#f7f9fc"/>',
        svg_text(48, 50, "Coordination Diagnostics on the Unified 20-Task Suite", 29, 700),
        svg_text(48, 80, "These process metrics explain dependency outcomes; they do not replace ADPR or final evaluation", 16, 400, "#596579"),
    ]
    for panel_index, (title, field, subtitle) in enumerate(panels):
        x = 40 + panel_index * 375
        parts.append(f'<rect x="{x}" y="115" width="360" height="500" rx="13" fill="#ffffff" stroke="#dce2ec"/>')
        parts.append(svg_text(x + 22, 153, title, 20, 700))
        parts.append(svg_text(x + 22, 178, subtitle, 13, 400, "#687386"))
        for row_index, protocol in enumerate(PROTOCOLS):
            value = lookup[protocol][field]
            y = 225 + row_index * 88
            parts.append(svg_text(x + 22, y, PROTOCOL_LABEL[protocol], 14, 650, PROTOCOL_COLOR[protocol]))
            if value is None:
                parts.append(svg_text(x + 325, y + 27, "N/A", 14, 650, "#718096", "end"))
                parts.append(f'<rect x="{x + 22}" y="{y + 12}" width="290" height="25" rx="5" fill="#edf0f5"/>')
            else:
                parts.append(f'<rect x="{x + 22}" y="{y + 12}" width="290" height="25" rx="5" fill="#edf0f5"/>')
                parts.append(f'<rect x="{x + 22}" y="{y + 12}" width="{290 * value}" height="25" rx="5" fill="{PROTOCOL_COLOR[protocol]}"/>')
                parts.append(svg_text(x + 325, y + 30, f"{value * 100:.1f}%", 14, 700, "#263247", "end"))
    parts.append(svg_text(48, 660, "† MRR is conditional on detected failure/repair opportunities; high MRR is not evidence of a clean trajectory.", 14, 500, "#596579"))
    parts.append('</svg>')
    PROCESS_FIGURE.write_text("\n".join(parts) + "\n", encoding="utf-8")


def write_contrast_figure(contrasts: list[dict]) -> None:
    selected = {row["research_question"]: row for row in contrasts}
    specs = [
        ("Async visibility loss", "Serial → Async private"),
        ("CAID recovery", "Async private → CAID"),
    ]
    metrics = [
        ("ADPR", "ADPR_delta", True, "pp"),
        ("DRE", "DRE_delta", True, "pp"),
        ("Unresolved", "unresolved_dependency_delta", False, "number"),
        ("DRS-P", "DRS_penalized_delta", False, "number"),
        ("CAIL-P", "CAIL_penalized_delta", False, "number"),
        ("FSAR", "FSAR_delta", False, "pp"),
        ("IFR", "IFR_delta", False, "pp"),
        ("Runtime", "runtime_ratio", False, "ratio"),
    ]
    width, height = 1540, 800
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#f7f9fc"/>',
        svg_text(48, 50, "Protocol Effects through AsynCodeBench Metrics", 29, 700),
        svg_text(48, 80, "Green = movement in the favorable direction; red = degradation", 16, 400, "#596579"),
    ]
    for panel_index, (key, label) in enumerate(specs):
        row = selected[key]
        x = 45 + panel_index * 750
        parts.append(f'<rect x="{x}" y="115" width="715" height="610" rx="14" fill="#ffffff" stroke="#dce2ec"/>')
        parts.append(svg_text(x + 28, 158, label, 23, 700))
        for metric_index, (metric_name, field, higher_better, kind) in enumerate(metrics):
            value = row[field]
            if kind == "ratio":
                delta = value - 1.0
                display = f"{delta * 100:+.1f}%"
            elif kind == "pp":
                delta = value
                display = f"{value * 100:+.1f} pp"
            else:
                delta = value
                display = f"{value:+.2f}"
            favorable = delta > 0 if higher_better else delta < 0
            neutral = abs(delta) < 1e-12
            color = "#687386" if neutral else "#23845d" if favorable else "#c44848"
            y = 212 + metric_index * 59
            parts.append(svg_text(x + 32, y, metric_name, 16, 600, "#344054"))
            parts.append(svg_text(x + 670, y, display, 18, 700, color, "end"))
            parts.append(f'<line x1="{x + 32}" y1="{y + 17}" x2="{x + 670}" y2="{y + 17}" stroke="#edf0f5"/>')
        if key == "Async visibility loss":
            note = "Faster runtime accompanies weaker dependency closure and later integration."
        else:
            note = "CAID recovers dependency closure and integration lag at substantially higher runtime."
        parts.append(svg_text(x + 28, 690, note, 14, 500, "#596579"))
    parts.append(svg_text(48, 768, "All deltas are macro-averaged across the same 20 tasks; comparison minus baseline.", 14, 500, "#596579"))
    parts.append('</svg>')
    CONTRAST_FIGURE.write_text("\n".join(parts) + "\n", encoding="utf-8")


def write_outcome_figure(rows: list[dict]) -> None:
    lookup = {(row["task"], row["protocol"]): row for row in rows}
    width, height = 1800, 1425
    left, top, cell_w, cell_h = 300, 145, 365, 58
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#f7f9fc"/>',
        svg_text(48, 48, "Per-Task Dependency Resolution across the Unified 20-Task Suite", 28, 700),
        svg_text(48, 78, "Fill = ADPR; each cell reports ADPR, DRE, penalized DRS, and penalized CAIL", 16, 400, "#596579"),
    ]
    for col, protocol in enumerate(PROTOCOLS):
        parts.append(svg_text(left + col * cell_w + 170, 121, PROTOCOL_LABEL[protocol], 17, 650, "#303a4c", "middle"))
    for index, task in enumerate(TASK_ORDER):
        y = top + index * cell_h
        parts.append(svg_text(left - 20, y + 34, task, 15, 650, "#253047", "end"))
        for col, protocol in enumerate(PROTOCOLS):
            row = lookup[(task, protocol)]
            x = left + col * cell_w
            fill = heat_color(row["ADPR"])
            text_fill = "#ffffff" if row["ADPR"] >= 0.62 else "#182235"
            mark = "✓" if row["final_success"] else "×"
            stroke = "#247a55" if row["final_success"] else "#c7ced9"
            parts.append(f'<rect x="{x}" y="{y}" width="345" height="49" rx="7" fill="{fill}" stroke="{stroke}" stroke-width="2"/>')
            parts.append(svg_text(x + 11, y + 21, f'{mark} ADPR {row["ADPR"] * 100:.0f}%  DRE {row["DRE"] * 100:.0f}%', 13, 700, text_fill))
            parts.append(svg_text(x + 11, y + 40, f'DRS-P {row["penalized_DRS"]:.1f}  CAIL-P {row["penalized_CAIL"]:.1f}', 12, 500, text_fill))
    parts.append(svg_text(48, 1350, "A check mark denotes final evaluator success; dependency metrics remain the primary cell content.", 14, 500, "#596579"))
    parts.append(svg_text(48, 1380, "All 20 tasks are evaluated in the same four-condition matrix.", 14, 500, "#596579"))
    parts.append('</svg>')
    OUTCOME_FIGURE.write_text("\n".join(parts) + "\n", encoding="utf-8")


def pct(value: float | None, digits: int = 1) -> str:
    return "N/A" if value is None else f"{value * 100:.{digits}f}%"


def core_table_markdown(protocol_rows: list[dict]) -> list[str]:
    lines = [
        "| Protocol | Macro ADPR ↑ | Micro ADPR ↑ | Full ADPR tasks | Unresolved/task ↓ | DRE ↑ | DRS-P ↓ | CAIL-P ↓ | Checkpoints | SAD/SAR |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in protocol_rows:
        lines.append(
            f'| {PROTOCOL_LABEL[row["protocol"]]} | {pct(row["macro_ADPR"])} | '
            f'{pct(row["micro_ADPR"])} ({int(row["resolved_edge_instances"])}/{int(row["edge_instances"])}) | '
            f'{row["full_ADPR_task_count"]}/20 | {row["mean_unresolved_dependencies"]:.2f} | '
            f'{pct(row["mean_DRE"])} | {row["penalized_DRS"]:.2f} | '
            f'{row["penalized_CAIL"]:.2f} | {row["mean_checkpoint_count"]:.2f} | N/A† |'
        )
    return lines


def process_table_markdown(protocol_rows: list[dict]) -> list[str]:
    lines = [
        "| Protocol | FSAR ↓ | IFR ↓ | SVR ↓ | MRR‡ | SAD proxy candidates§ | Proxy-positive runs§ |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in protocol_rows:
        lines.append(
            f'| {PROTOCOL_LABEL[row["protocol"]]} | {pct(row["FSAR"])} | '
            f'{pct(row["IFR"])} | {pct(row["SVR"])} | {pct(row["MRR"])} | '
            f'{row["SAD_proxy_candidate_count"]} | {pct(row["SAD_proxy_run_indicator_rate"])} |'
        )
    return lines


def conventional_table_markdown(protocol_rows: list[dict]) -> list[str]:
    lines = [
        "| Protocol | Solved tasks | Mean pass | Mean tokens | Mean runtime |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for row in protocol_rows:
        lines.append(
            f'| {PROTOCOL_LABEL[row["protocol"]]} | {row["successful_tasks"]}/20 '
            f'({pct(row["success_rate"])}) | {pct(row["mean_test_pass_rate"])} | '
            f'{row["mean_tokens"] / 1e6:.3f}M | {row["mean_runtime_seconds"] / 60:.1f} min |'
        )
    return lines


def task_cell(row: dict, protocol: str) -> str:
    mark = "✓" if row[f"{protocol}_success"] else "×"
    return (
        f'{mark}; A={pct(row[f"{protocol}_ADPR"], 0)}; '
        f'E={pct(row[f"{protocol}_DRE"], 0)}; '
        f'R={row[f"{protocol}_DRS_penalized"]:.1f}; '
        f'L={row[f"{protocol}_CAIL_penalized"]:.1f}'
    )


def write_report(
    protocol_rows: list[dict], task_rows: list[dict], contrasts: list[dict]
) -> None:
    lookup = {row["protocol"]: row for row in protocol_rows}
    contrast_lookup = {row["research_question"]: row for row in contrasts}
    async_loss = contrast_lookup["Async visibility loss"]
    recovery = contrast_lookup["CAID recovery"]
    caid = lookup["caid_manager"]
    control_protocols = ("single", "serial_specialists", "async_private")
    caid_only_tasks = [
        row["task"]
        for row in task_rows
        if row["caid_manager_success"]
        and not any(row[f"{protocol}_success"] for protocol in control_protocols)
    ]
    caid_regressions = [
        row["task"]
        for row in task_rows
        if not row["caid_manager_success"]
        and any(row[f"{protocol}_success"] for protocol in control_protocols)
    ]
    lines = [
        "# Qwen3.6-27B: Unified 20-Task AsynCodeBench Analysis",
        "",
        "## Scope",
        "",
        "This report treats the benchmark as one unified suite of 20 repository-engineering tasks produced through the AsynCodeBench transformation and qualification pipeline. Every task enters the same four-condition analysis and the same aggregate population.",
        "",
        "The analysis contains 80 frozen task-condition cells: Single, Serial specialists, Async private, and CAID for each task. There is one selected run per cell, so solved-task fractions are descriptive and are not repeated-seed FSR estimates.",
        "",
        "## Metric hierarchy",
        "",
        "| Level | Metrics | Paper role |",
        "| --- | --- | --- |",
        "| Core dependency outcomes | ADPR, unresolved dependencies | Primary benchmark result |",
        "| Dependency timing | strict-checkpoint DRS-P, CAIL-P, DRE | When and how efficiently dependencies close |",
        "| Stale-information behavior | strict SAD/SAR | Primary concept, reported only with sufficient visibility evidence |",
        "| Coordination diagnostics | FSAR, IFR, SVR, MRR | Explain artifact, integration, ownership, and recovery behavior |",
        "| Conventional outcomes | final success, pass rate, tokens, runtime | Supporting context only |",
        "",
        "Macro ADPR averages task-level dependency pass rates so that every task has equal weight. Micro ADPR pools all labeled dependency edges. A dependency is resolved only when its required integrated checker group passes in the final integrated workspace.",
        "",
        "Strict DRS is the first integrated-workspace checkpoint at which the dependency's integrated checker passes. DRS-P assigns an unresolved dependency step `T+1`. CAIL is the downstream resolution step minus the upstream resolution step; CAIL-P uses the benchmark's run-local piecewise penalty when either side remains unresolved. DRE normalizes penalized DRS by the number of observed checkpoints (`T`) so that step counts from protocols with different checkpoint schedules are more comparable.",
        "",
        "## Table 1. Core AsynCodeBench dependency metrics",
        "",
        *core_table_markdown(protocol_rows),
        "",
        "† Strict SAD/SAR is not estimable for these runs because the traces do not provide complete producer-artifact version visibility for consumer attempts. Heuristic candidates are reported separately and are not substituted for strict SAD/SAR.",
        "",
        "DRS-P and CAIL-P apply the benchmark's run-local `T+1`-based unresolved penalties. Since protocols have different checkpoint counts, cross-protocol timing must be interpreted with ADPR, unresolved count, DRE, and checkpoints rather than DRS-P alone.",
        "",
        "![Core dependency metrics](figures/qwen36_27_dependency_coordination_profile.svg)",
        "",
        "## Table 2. Coordination diagnostics",
        "",
        *process_table_markdown(protocol_rows),
        "",
        "‡ MRR is conditional on detected failure or repair opportunities. A high recovery rate does not imply a clean trajectory and must be read with FSAR.",
        "",
        "§ SAD proxy counts are conservative heuristic candidates requiring trajectory audit. They are sensitive to the number of attempts and must not be interpreted as strict SAD or SAR.",
        "",
        "![Coordination diagnostics](figures/qwen36_27_20task_coordination_diagnostics.svg)",
        "",
        "## CAID-centered outcome summary",
        "",
        f'CAID is the strongest complete condition in these selected runs: it solves {caid["successful_tasks"]}/20 tasks and resolves {int(caid["resolved_edge_instances"])}/{int(caid["edge_instances"])} dependency edges. It uniquely solves {len(caid_only_tasks)} tasks that none of the three controls solve: {", ".join(f"`{task}`" for task in caid_only_tasks)}.',
        "",
        f'CAID has one observed regression against the controls: {", ".join(f"`{task}`" for task in caid_regressions)}. This effectiveness--boundary pattern should organize the paper results; the following pairwise contrasts are supporting analyses rather than standalone paper RQs.',
        "",
        "## Supporting contrast A. Serial versus Async private",
        "",
        f'Compared with Serial, Async private changes ADPR by {async_loss["ADPR_delta"] * 100:+.1f} percentage points, DRE by {async_loss["DRE_delta"] * 100:+.1f} points, unresolved dependencies by {async_loss["unresolved_dependency_delta"]:+.2f}, DRS-P by {async_loss["DRS_penalized_delta"]:+.2f}, and CAIL-P by {async_loss["CAIL_penalized_delta"]:+.2f}. FSAR rises by {async_loss["FSAR_delta"] * 100:+.1f} points and IFR by {async_loss["IFR_delta"] * 100:+.1f} points.',
        "",
        f'Async private uses {async_loss["runtime_ratio"]:.2f}× the Serial runtime ({(async_loss["runtime_ratio"] - 1) * 100:+.1f}%) but closes dependencies less reliably and later. The speed benefit is therefore accompanied by a measurable coordination penalty.',
        "",
        "## Supporting contrast B. Async private versus CAID",
        "",
        f'Compared with Async private, CAID changes ADPR by {recovery["ADPR_delta"] * 100:+.1f} percentage points, reduces unresolved dependencies by {-recovery["unresolved_dependency_delta"]:.2f}, changes DRE by {recovery["DRE_delta"] * 100:+.1f} points, DRS-P by {recovery["DRS_penalized_delta"]:+.2f}, and CAIL-P by {recovery["CAIL_penalized_delta"]:+.2f}. IFR falls by {-recovery["IFR_delta"] * 100:.1f} points.',
        "",
        f'This recovery costs {recovery["token_ratio"]:.2f}× tokens and {recovery["runtime_ratio"]:.2f}× runtime. CAID reaches {pct(caid["macro_ADPR"])} macro ADPR and resolves {int(caid["resolved_edge_instances"])}/{int(caid["edge_instances"])} edge instances, but increased cost and nonzero FSAR/SVR show that recovery is not free.',
        "",
        "![Protocol effects](figures/qwen36_27_20task_async_effects.svg)",
        "",
        "## Table 3. Conventional outcomes and resources",
        "",
        *conventional_table_markdown(protocol_rows),
        "",
        "These conventional measures are necessary context, but they are not the benchmark contribution. In particular, a high evaluator pass rate can coexist with low ADPR and unresolved producer-consumer contracts.",
        "",
        "## Table 4. Per-task dependency matrix",
        "",
        "Each cell is `final success; A=ADPR; E=DRE; R=DRS-P; L=CAIL-P`.",
        "",
        "| Task | Single | Serial | Async private | CAID |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in task_rows:
        lines.append(
            f'| {row["task"]} | {task_cell(row, "single")} | '
            f'{task_cell(row, "serial_specialists")} | '
            f'{task_cell(row, "async_private")} | '
            f'{task_cell(row, "caid_manager")} |'
        )
    lines.extend(
        [
            "",
            "![Per-task dependency matrix](figures/qwen36_27_20task_outcome_heatmap.svg)",
            "",
            "## Paper-ready findings",
            "",
            f'1. CAID is the strongest overall condition: {caid["successful_tasks"]}/20 solved tasks, {int(caid["resolved_edge_instances"])}/{int(caid["edge_instances"])} resolved edges, and {len(caid_only_tasks)} CAID-only task successes.',
            "2. The CAID gain is conditional rather than universal: it resolves 45/47 edges on the 16 non-compiler tasks but 0/8 compiler/IR edges, while Serial alone solves `apache-tvm-20018`.",
            "3. Final pass rate alone is insufficient: ADPR identifies whether labeled cross-agent contracts close, while DRS/CAIL/DRE reveal when and how efficiently they close.",
            "4. Serial versus Async private and Async private versus CAID remain useful controlled contrasts, but they support the overall effectiveness analysis rather than defining separate paper RQs.",
            "5. Strict SAD/SAR remains unreported rather than imputed. This is an instrumentation limitation, not evidence of zero stale assumptions.",
            "6. In task `apache-tvm-20018`, all five CAID specialist attempts reach the fixed 100-iteration cap without solving the task, providing a concrete capability/cost-boundary case study.",
            "",
            "Do not claim seed-level statistical significance or strict SAD/SAR values from these single selected runs. Use the heuristic stale-assumption candidates only for audited case studies.",
            "",
            "## Reproduction",
            "",
            "```bash",
            "cd /home/kzhang42/AsyncCodeBench",
            "python scripts/build_qwen36_20task_paper_analysis.py",
            "```",
            "",
            "The builder verifies all frozen artifact hashes before computing the unified metrics.",
        ]
    )
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_provenance() -> None:
    generated = [
        REPORT, PROTOCOL_TABLE, TASK_TABLE, CONTRAST_TABLE, OUTCOME_FIGURE,
        DEPENDENCY_FIGURE, PROCESS_FIGURE, CONTRAST_FIGURE,
    ]
    payload = {
        "schema_version": "qwen36-unified-20task-paper-analysis-v2",
        "model": "Qwen3.6-27B",
        "scope": {
            "adapted_repository_tasks": 20,
            "protocols": PROTOCOLS,
            "result_cells": 80,
            "aggregation_population": "all 20 adapted repository tasks",
        },
        "metric_policy": {
            "primary": ["ADPR", "unresolved", "DRS_penalized", "CAIL_penalized", "DRE"],
            "coordination_diagnostics": ["FSAR", "IFR", "SVR", "MRR"],
            "supporting": ["final_success", "test_pass_rate", "tokens", "runtime"],
            "SAD_SAR": "not estimable; heuristic proxy candidates are audit-only",
        },
        "source_sha256": {
            str(path.relative_to(ROOT)): sha256_file(path)
            for path in (PER_RUN_SOURCE, TAXONOMY_SOURCE, FROZEN_INDEX_SOURCE)
        },
        "generated_sha256": {
            str(path.relative_to(ROOT)): sha256_file(path) for path in generated
        },
    }
    PROVENANCE.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def main() -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)
    rows = load_rows()
    validate_frozen_selection(rows)
    taxonomy = load_taxonomy()
    protocol_rows = build_protocol_table(rows)
    task_rows = build_task_table(rows, taxonomy)
    contrasts = build_contrasts(protocol_rows, rows)
    write_csv(PROTOCOL_TABLE, protocol_rows)
    write_csv(TASK_TABLE, task_rows)
    write_csv(CONTRAST_TABLE, contrasts)
    write_dependency_figure(protocol_rows)
    write_process_figure(protocol_rows)
    write_contrast_figure(contrasts)
    write_outcome_figure(rows)
    write_report(protocol_rows, task_rows, contrasts)
    write_provenance()
    for path in (
        REPORT, PROTOCOL_TABLE, TASK_TABLE, CONTRAST_TABLE, OUTCOME_FIGURE,
        DEPENDENCY_FIGURE, PROCESS_FIGURE, CONTRAST_FIGURE, PROVENANCE,
    ):
        print(f"Wrote {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
