#!/usr/bin/env python3
"""Build trajectory-aware Qwen3.6-27B analysis for the frozen 20-task suite.

The existing paper analysis reports terminal dependency pass rate (ADPR) and
first-passage timing (DRS/CAIL).  This script keeps those quantities separate
from trajectory properties that terminal or first-passage metrics cannot see:
stable closure, regression, recovery, and locally/producer-stranded progress.

Async-private logs contain repeated probes with the same checkpoint_id.  For
trajectory analysis, identical checkpoint identities are canonicalized by
keeping the last observation, sorting by logical_step/recorded_at, and then
assigning a dense canonical step.  Raw and canonical counts are both emitted.
"""

from __future__ import annotations

import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, median


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "docs" / "results"
FIGURES = RESULTS / "figures"
INDEX = RESULTS / "qwen36_27_frozen_result_index.v1.json"

EDGE_CSV = RESULTS / "qwen36_27_trajectory_per_edge.csv"
STATE_CSV = RESULTS / "qwen36_27_trajectory_states.csv"
SUMMARY_CSV = RESULTS / "qwen36_27_trajectory_protocol_summary.csv"
TYPE_CSV = RESULTS / "qwen36_27_trajectory_type_summary.csv"
REPORT = RESULTS / "QWEN36_27_TRAJECTORY_ANALYSIS.md"
PROFILE_FIGURE = FIGURES / "qwen36_27_trajectory_outcome_profile.svg"
CASE_FIGURE = FIGURES / "qwen36_27_trajectory_case_studies.svg"
PROVENANCE = RESULTS / "qwen36_27_trajectory_provenance.v1.json"

PROTOCOLS = ["single", "serial_specialists", "async_private", "caid_manager"]
PROTOCOL_LABEL = {
    "single": "Single",
    "serial_specialists": "Serial",
    "async_private": "Async private",
    "caid_manager": "CAID",
}
ARCHETYPE_LABEL = {
    "terminal_closed_only": "Terminally closed (no process visibility)",
    "progressive_stable_closure": "Stable closure before the final checkpoint",
    "final_checkpoint_closure": "Closed only at the final checkpoint",
    "regressed_then_recovered": "Regressed, then recovered",
    "regressed_and_unrecovered": "Regressed and remained open",
    "both_sides_seen_but_open": "Both sides passed somewhere, but integration stayed open",
    "stranded_producer": "Producer-ready, consumer never became ready",
    "consumer_only_progress": "Consumer-only progress",
    "capability_blocked": "Neither side became ready",
}
ARCHETYPE_COLOR = {
    "terminal_closed_only": "#8fc9ad",
    "progressive_stable_closure": "#2f8f68",
    "final_checkpoint_closure": "#73b7a1",
    "regressed_then_recovered": "#176b61",
    "regressed_and_unrecovered": "#9b3a4a",
    "both_sides_seen_but_open": "#7656a4",
    "stranded_producer": "#dc8b32",
    "consumer_only_progress": "#4f82bd",
    "capability_blocked": "#c8ccd3",
}
ARCHETYPE_ORDER = [
    "terminal_closed_only",
    "progressive_stable_closure",
    "final_checkpoint_closure",
    "regressed_then_recovered",
    "regressed_and_unrecovered",
    "both_sides_seen_but_open",
    "stranded_producer",
    "consumer_only_progress",
    "capability_blocked",
]


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path):
    rows = []
    for raw_index, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line.strip():
            row = json.loads(line)
            row["_raw_index"] = raw_index
            rows.append(row)
    return rows


def canonicalize(raw_rows):
    """Keep the last re-probe for a checkpoint identity and restore logical order."""
    by_id = {}
    for row in raw_rows:
        by_id[row["checkpoint_id"]] = row
    rows = sorted(
        by_id.values(),
        key=lambda row: (
            row.get("logical_step") if row.get("logical_step") is not None else 10 ** 9,
            row.get("recorded_at") or "",
            row["_raw_index"],
        ),
    )
    for step, row in enumerate(rows, 1):
        row["_canonical_step"] = step
    return rows


def conflicting_duplicate_count(raw_rows):
    grouped = defaultdict(list)
    for row in raw_rows:
        grouped[row["checkpoint_id"]].append(row)
    conflicts = 0
    for duplicates in grouped.values():
        signatures = {
            json.dumps(row["dependency_results"], sort_keys=True)
            for row in duplicates
        }
        conflicts += int(len(signatures) > 1)
    return conflicts


def group_pass(result, group):
    return bool(result.get("groups", {}).get(group, {}).get("passed", False))


def dependency_map(checkpoint):
    return {item["dependency_id"]: item for item in checkpoint["dependency_results"]}


def fmt_ratio(numerator, denominator):
    return "—" if not denominator else "{:.1%}".format(numerator / denominator)


def fmt_num(value, digits=2):
    return "—" if value is None else ("{:,.%df}" % digits).format(value)


def final_success(run_dir):
    report = read_json(run_dir / "report.json")
    summary = report.get("summary") or {}
    total = summary.get("total") or summary.get("collected") or 0
    # Pytest exit 0 is the benchmark's task-success rule.  Some suites contain
    # intentional skips/xfails, so passed == collected would undercount them.
    return bool(total and report.get("exitcode") == 0)


def analyze_edge(entry, metadata, raw_rows, rows, dep_id):
    states = []
    for checkpoint in rows:
        result = dependency_map(checkpoint).get(dep_id)
        if result is None:
            raise RuntimeError("missing dependency {} at {}".format(dep_id, checkpoint["checkpoint_id"]))
        state = {
            "step": checkpoint["_canonical_step"],
            "logical_step": checkpoint.get("logical_step"),
            "checkpoint_id": checkpoint["checkpoint_id"],
            "checkpoint_type": checkpoint.get("checkpoint_type"),
            "workspace_kind": checkpoint.get("workspace_kind"),
            "agent_id": checkpoint.get("agent_id"),
            "upstream": group_pass(result, "upstream"),
            "downstream": group_pass(result, "downstream"),
            "integrated": group_pass(result, "integrated"),
        }
        state["code"] = "{}{}{}".format(
            int(state["upstream"]), int(state["downstream"]), int(state["integrated"])
        )
        states.append(state)

    integrated_states = [s for s in states if s["workspace_kind"] == "integrated_workspace"]
    if not integrated_states:
        raise RuntimeError("no integrated checkpoint for {} / {}".format(entry["task"], dep_id))
    final = integrated_states[-1]
    upstream_steps = [s["step"] for s in states if s["upstream"]]
    downstream_steps = [s["step"] for s in states if s["downstream"]]
    closure_steps = [s["step"] for s in integrated_states if s["integrated"]]

    first_upstream = min(upstream_steps) if upstream_steps else None
    first_downstream = min(downstream_steps) if downstream_steps else None
    first_closure = min(closure_steps) if closure_steps else None
    stable_closure = None
    if final["integrated"]:
        for index, state in enumerate(integrated_states):
            if state["integrated"] and all(s["integrated"] for s in integrated_states[index:]):
                stable_closure = state["step"]
                break

    regression_count = 0
    recovery_count = 0
    awaiting_recovery = False
    for previous, current in zip(integrated_states, integrated_states[1:]):
        if previous["integrated"] and not current["integrated"]:
            regression_count += 1
            awaiting_recovery = True
        elif awaiting_recovery and current["integrated"]:
            recovery_count += 1
            awaiting_recovery = False

    upstream_ever = bool(upstream_steps)
    downstream_ever = bool(downstream_steps)
    local_integrated_ever = any(
        s["integrated"] for s in states if s["workspace_kind"] == "agent_workspace"
    )
    final_closed = final["integrated"]
    final_only = bool(first_closure and first_closure == final["step"])
    if final_closed:
        if regression_count:
            archetype = "regressed_then_recovered"
        elif len(integrated_states) == 1:
            archetype = "terminal_closed_only"
        elif final_only:
            archetype = "final_checkpoint_closure"
        else:
            archetype = "progressive_stable_closure"
    elif regression_count:
        archetype = "regressed_and_unrecovered"
    elif upstream_ever and downstream_ever:
        archetype = "both_sides_seen_but_open"
    elif upstream_ever:
        archetype = "stranded_producer"
    elif downstream_ever:
        archetype = "consumer_only_progress"
    else:
        archetype = "capability_blocked"

    closure_retention = None
    if first_closure is not None:
        suffix = [s for s in integrated_states if s["step"] >= first_closure]
        closure_retention = sum(s["integrated"] for s in suffix) / len(suffix)

    row = {
        "task": entry["task"],
        "protocol": entry["protocol"],
        "run_id": entry["run_id"],
        "dependency_id": dep_id,
        "dependency_type": metadata.get("dependency_type", ""),
        "producer_agent": metadata.get("producer_agent", ""),
        "consumer_agent": metadata.get("consumer_agent", ""),
        "raw_checkpoint_count": len(raw_rows),
        "canonical_checkpoint_count": len(rows),
        "duplicate_checkpoint_count": len(raw_rows) - len(rows),
        "integrated_checkpoint_count": len(integrated_states),
        "first_upstream_step": first_upstream,
        "first_downstream_step": first_downstream,
        "canonical_CAIL": (
            first_downstream - first_upstream
            if first_upstream is not None and first_downstream is not None else None
        ),
        "first_integrated_closure_step": first_closure,
        "stable_closure_step": stable_closure,
        "stable_closure_delay": (
            stable_closure - first_closure
            if stable_closure is not None and first_closure is not None else None
        ),
        "final_integrated_pass": final_closed,
        "upstream_ever_passed": upstream_ever,
        "downstream_ever_passed": downstream_ever,
        "agent_local_integrated_ever_passed": local_integrated_ever,
        "producer_stranded": upstream_ever and not final_closed,
        "consumer_progress_stranded": downstream_ever and not final_closed,
        "local_integrated_progress_stranded": local_integrated_ever and not final_closed,
        "integrated_open_after_producer_count": sum(
            s["upstream"] and not s["integrated"] for s in integrated_states
        ),
        "regression_count": regression_count,
        "recovery_count": recovery_count,
        "closure_retention": closure_retention,
        "trajectory_archetype": archetype,
        "integrated_trajectory": " > ".join(
            "{}:{}".format(s["step"], s["code"]) for s in integrated_states
        ),
        "full_trajectory": " > ".join(
            "{}:{}:{}".format(
                s["step"], "A" if s["workspace_kind"] == "agent_workspace" else "W", s["code"]
            ) for s in states
        ),
        "contract_summary": metadata.get("contract_summary", ""),
    }
    return row, states


def load_analysis():
    index = read_json(INDEX)
    if len(index["entries"]) != 80:
        raise RuntimeError("expected the frozen 20 x 4 = 80 run matrix")
    edge_rows = []
    state_rows = []
    run_rows = []
    for entry in index["entries"]:
        run_dir = ROOT / entry["run_dir"]
        raw_rows = read_jsonl(run_dir / "dependency_probe_checkpoints.jsonl")
        rows = canonicalize(raw_rows)
        snapshot = read_json(run_dir / "metrics_snapshot.json")
        metadata = {d["dependency_id"]: d for d in snapshot["dependency_points"]}
        observed = set(dependency_map(rows[0]))
        if observed != set(metadata):
            raise RuntimeError("dependency manifest/checkpoint mismatch in {}".format(run_dir))
        run_rows.append({
            "task": entry["task"],
            "protocol": entry["protocol"],
            "raw": len(raw_rows),
            "canonical": len(rows),
            "duplicates": len(raw_rows) - len(rows),
            "duplicate_conflicts": conflicting_duplicate_count(raw_rows),
            "final_success": final_success(run_dir),
        })
        for dep_id in metadata:
            edge, states = analyze_edge(entry, metadata[dep_id], raw_rows, rows, dep_id)
            edge_rows.append(edge)
            for state in states:
                state_rows.append({
                    "task": entry["task"],
                    "protocol": entry["protocol"],
                    "run_id": entry["run_id"],
                    "dependency_id": dep_id,
                    **state,
                })
    return edge_rows, state_rows, run_rows


def aggregate(edge_rows, run_rows):
    summaries = []
    for protocol in PROTOCOLS:
        edges = [row for row in edge_rows if row["protocol"] == protocol]
        runs = [row for row in run_rows if row["protocol"] == protocol]
        closed = [row for row in edges if row["final_integrated_pass"]]
        open_edges = [row for row in edges if not row["final_integrated_pass"]]
        first_closures = [row["first_integrated_closure_step"] for row in closed]
        stable_closures = [row["stable_closure_step"] for row in closed]
        retention = [row["closure_retention"] for row in closed if row["closure_retention"] is not None]
        counts = Counter(row["trajectory_archetype"] for row in edges)
        summary = {
            "protocol": protocol,
            "task_count": len(runs),
            "successful_tasks": sum(row["final_success"] for row in runs),
            "task_success_rate": mean(float(row["final_success"]) for row in runs),
            "edge_count": len(edges),
            "final_closed_edges": len(closed),
            "micro_ADPR": len(closed) / len(edges),
            "final_open_edges": len(open_edges),
            "producer_stranded_edges": sum(row["producer_stranded"] for row in edges),
            "producer_stranded_share_of_open": (
                sum(row["producer_stranded"] for row in edges) / len(open_edges) if open_edges else 0.0
            ),
            "consumer_progress_stranded_edges": sum(
                row["consumer_progress_stranded"] for row in edges
            ),
            "local_integrated_progress_stranded_edges": sum(
                row["local_integrated_progress_stranded"] for row in edges
            ),
            "regression_edges": sum(row["regression_count"] > 0 for row in edges),
            "regression_transitions": sum(row["regression_count"] for row in edges),
            "recovered_regression_edges": sum(
                row["regression_count"] > 0 and row["final_integrated_pass"] for row in edges
            ),
            "mean_raw_checkpoints_per_run": mean(row["raw"] for row in runs),
            "mean_canonical_checkpoints_per_run": mean(row["canonical"] for row in runs),
            "duplicate_checkpoint_records": sum(row["duplicates"] for row in runs),
            "median_first_closure_step": median(first_closures) if first_closures else None,
            "median_stable_closure_step": median(stable_closures) if stable_closures else None,
            "mean_closure_retention": mean(retention) if retention else None,
        }
        for archetype in ARCHETYPE_ORDER:
            summary["archetype_{}".format(archetype)] = counts[archetype]
        summaries.append(summary)
    return summaries


def aggregate_types(edge_rows):
    output = []
    dependency_types = [
        "interface_dependency", "shared_api_contract",
        "shared_state_contract", "integration_contract",
    ]
    for dependency_type in dependency_types:
        for protocol in PROTOCOLS:
            edges = [
                row for row in edge_rows
                if row["dependency_type"] == dependency_type and row["protocol"] == protocol
            ]
            open_edges = [row for row in edges if not row["final_integrated_pass"]]
            output.append({
                "dependency_type": dependency_type,
                "protocol": protocol,
                "edge_count": len(edges),
                "final_closed_edges": sum(row["final_integrated_pass"] for row in edges),
                "micro_ADPR": mean(float(row["final_integrated_pass"]) for row in edges),
                "final_open_edges": len(open_edges),
                "producer_stranded_edges": sum(row["producer_stranded"] for row in edges),
                "consumer_progress_stranded_edges": sum(
                    row["consumer_progress_stranded"] for row in edges
                ),
                "local_integrated_progress_stranded_edges": sum(
                    row["local_integrated_progress_stranded"] for row in edges
                ),
                "final_checkpoint_closure_edges": sum(
                    row["trajectory_archetype"] == "final_checkpoint_closure" for row in edges
                ),
                "regression_edges": sum(row["regression_count"] > 0 for row in edges),
            })
    return output


def write_csv(path, rows):
    if not rows:
        raise RuntimeError("refusing to write an empty CSV")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=list(rows[0]), lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)


def svg_text(x, y, value, size=14, fill="#253047", anchor="start", weight=400):
    return '<text x="{}" y="{}" font-family="Inter,Arial,sans-serif" font-size="{}" fill="{}" text-anchor="{}" font-weight="{}">{}</text>'.format(
        x, y, size, fill, anchor, weight, html.escape(str(value))
    )


def write_profile_figure(summaries):
    width, height = 1280, 570
    left, top, bar_w, bar_h, gap = 190, 100, 920, 54, 31
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="{}" height="{}" viewBox="0 0 {} {}">'.format(width, height, width, height),
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        svg_text(55, 43, "Qwen3.6-27B dependency trajectories (55 edges per protocol)", 23, weight=700),
        svg_text(55, 69, "Terminally identical outcomes are separated by closure timing, regression, and stranded progress.", 14, "#596579"),
    ]
    observed = [a for a in ARCHETYPE_ORDER if any(s["archetype_{}".format(a)] for s in summaries)]
    for row_index, summary in enumerate(summaries):
        y = top + row_index * (bar_h + gap)
        parts.append(svg_text(left - 18, y + 33, PROTOCOL_LABEL[summary["protocol"]], 15, anchor="end", weight=600))
        x = left
        for archetype in observed:
            count = summary["archetype_{}".format(archetype)]
            if not count:
                continue
            segment_w = bar_w * count / summary["edge_count"]
            parts.append('<rect x="{:.1f}" y="{}" width="{:.1f}" height="{}" fill="{}"/>'.format(
                x, y, segment_w, bar_h, ARCHETYPE_COLOR[archetype]
            ))
            if segment_w >= 28:
                parts.append(svg_text(x + segment_w / 2, y + 34, count, 14, "#ffffff" if archetype != "capability_blocked" else "#364153", anchor="middle", weight=700))
            x += segment_w
        parts.append(svg_text(left + bar_w + 17, y + 24, "ADPR {:.1%}".format(summary["micro_ADPR"]), 13, "#364153", weight=600))
        parts.append(svg_text(left + bar_w + 17, y + 43, "{} regressions".format(summary["regression_edges"]), 12, "#697386"))
    legend_y = top + 4 * (bar_h + gap) + 23
    x, row = 75, 0
    for archetype in observed:
        label = ARCHETYPE_LABEL[archetype]
        item_w = min(390, 39 + 7 * len(label))
        if x + item_w > width - 55:
            row += 1
            x = 75
        y = legend_y + row * 34
        parts.append('<rect x="{}" y="{}" width="18" height="18" rx="3" fill="{}"/>'.format(x, y - 14, ARCHETYPE_COLOR[archetype]))
        parts.append(svg_text(x + 26, y, label, 12, "#485469"))
        x += item_w
    parts.append(svg_text(55, height - 18, "State evidence is canonicalized by checkpoint identity; A = agent-local workspace, W = integrated workspace.", 11, "#7a8496"))
    parts.append("</svg>")
    PROFILE_FIGURE.write_text("\n".join(parts), encoding="utf-8")


def select_case(edge_rows, task, protocol, dependency_id):
    return next(
        row for row in edge_rows
        if row["task"] == task and row["protocol"] == protocol and row["dependency_id"] == dependency_id
    )


def parse_integrated_trajectory(value):
    result = []
    for item in value.split(" > "):
        step, code = item.split(":")
        result.append((int(step), code))
    return result


def write_case_figure(edge_rows):
    cases = [
        (
            "python-rsa · Serial",
            "First closure at step 4; regression at step 6; recovered by step 8",
            select_case(edge_rows, "python-rsa", "serial_specialists", "python_rsa.arithmetic_to_key_generation.inverse_prime_contract"),
        ),
        (
            "cookiecutter · CAID",
            "First closure at step 6; later regression; stable closure only at final step 11",
            select_case(edge_rows, "cookiecutter", "caid_manager", "cookiecutter.source_to_main.repo_dir_contract"),
        ),
        (
            "apache-tvm-20107 · CAID",
            "Producer remains ready, but the consumer contract never closes",
            select_case(edge_rows, "apache-tvm-20107", "caid_manager", "shared-core-to-relax-signature"),
        ),
    ]
    width, height = 1320, 700
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="{}" height="{}" viewBox="0 0 {} {}">'.format(width, height, width, height),
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        svg_text(55, 44, "Why final outcome and first-passage metrics are insufficient", 23, weight=700),
        svg_text(55, 71, "Each cell is an integrated-workspace state U/D/I: upstream, downstream, integrated contract.", 14, "#596579"),
    ]
    state_color = {"111": "#2f8f68", "110": "#7560a8", "100": "#dc8b32", "010": "#4f82bd", "000": "#c8ccd3"}
    for panel, (title, subtitle, row) in enumerate(cases):
        y = 115 + panel * 185
        parts.append('<rect x="45" y="{}" width="1230" height="155" rx="12" fill="#f8fafc" stroke="#dce2ea"/>'.format(y - 25))
        parts.append(svg_text(70, y + 4, title, 17, weight=700))
        parts.append(svg_text(70, y + 29, subtitle, 13, "#596579"))
        trajectory = parse_integrated_trajectory(row["integrated_trajectory"])
        cell_w = min(104, 850 / max(1, len(trajectory)))
        start_x = 365
        for index, (step, code) in enumerate(trajectory):
            x = start_x + index * (cell_w + 12)
            color = state_color.get(code, "#8b95a6")
            parts.append('<rect x="{:.1f}" y="{}" width="{:.1f}" height="58" rx="8" fill="{}"/>'.format(x, y + 45, cell_w, color))
            parts.append(svg_text(x + cell_w / 2, y + 70, code, 17, "#ffffff" if code != "000" else "#364153", anchor="middle", weight=700))
            parts.append(svg_text(x + cell_w / 2, y + 91, "step {}".format(step), 10, "#ffffff" if code != "000" else "#596579", anchor="middle"))
            if index < len(trajectory) - 1:
                parts.append(svg_text(x + cell_w + 6, y + 80, "→", 17, "#8590a2", anchor="middle"))
        parts.append(svg_text(70, y + 82, "final: {}".format("closed" if row["final_integrated_pass"] else "open"), 14, "#2f8f68" if row["final_integrated_pass"] else "#b05f22", weight=700))
        parts.append(svg_text(70, y + 105, "first / stable closure: {} / {}".format(
            row["first_integrated_closure_step"] if row["first_integrated_closure_step"] is not None else "—",
            row["stable_closure_step"] if row["stable_closure_step"] is not None else "—",
        ), 12, "#596579"))
    parts.append(svg_text(55, height - 22, "000 blocked · 100 producer-ready · 010 consumer-only · 110 both sides ready but integration open · 111 contract closed", 12, "#667085"))
    parts.append("</svg>")
    CASE_FIGURE.write_text("\n".join(parts), encoding="utf-8")


def markdown_table(headers, rows):
    output = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    output.extend("| " + " | ".join(map(str, row)) + " |" for row in rows)
    return "\n".join(output)


def write_report(edge_rows, summaries, type_summaries):
    by_protocol = {row["protocol"]: row for row in summaries}
    rsa = select_case(edge_rows, "python-rsa", "serial_specialists", "python_rsa.arithmetic_to_key_generation.inverse_prime_contract")
    cookie = select_case(edge_rows, "cookiecutter", "caid_manager", "cookiecutter.source_to_main.repo_dir_contract")
    tvm = select_case(edge_rows, "apache-tvm-20107", "caid_manager", "shared-core-to-relax-signature")
    summary_rows = []
    for protocol in PROTOCOLS:
        row = by_protocol[protocol]
        summary_rows.append([
            PROTOCOL_LABEL[protocol],
            "{}/20".format(row["successful_tasks"]),
            "{}/55 ({:.1%})".format(row["final_closed_edges"], row["micro_ADPR"]),
            "{}/{} ({})".format(
                row["producer_stranded_edges"], row["final_open_edges"],
                fmt_ratio(row["producer_stranded_edges"], row["final_open_edges"]),
            ),
            row["consumer_progress_stranded_edges"],
            row["local_integrated_progress_stranded_edges"],
            "{} / {}".format(row["regression_edges"], row["recovered_regression_edges"]),
        ])

    archetype_rows = []
    for protocol in PROTOCOLS:
        row = by_protocol[protocol]
        archetype_rows.append([
            PROTOCOL_LABEL[protocol],
            row["archetype_terminal_closed_only"],
            row["archetype_progressive_stable_closure"],
            row["archetype_final_checkpoint_closure"],
            row["archetype_regressed_then_recovered"],
            row["archetype_both_sides_seen_but_open"],
            row["archetype_stranded_producer"],
            row["archetype_consumer_only_progress"],
            row["archetype_capability_blocked"],
        ])
    type_by_key = {
        (row["dependency_type"], row["protocol"]): row for row in type_summaries
    }
    type_label = {
        "interface_dependency": "IF",
        "shared_api_contract": "API",
        "shared_state_contract": "STATE",
        "integration_contract": "INT",
    }
    type_rows = []
    for dependency_type in [
        "interface_dependency", "shared_api_contract",
        "shared_state_contract", "integration_contract",
    ]:
        async_row = type_by_key[(dependency_type, "async_private")]
        caid_row = type_by_key[(dependency_type, "caid_manager")]
        type_rows.append([
            type_label[dependency_type],
            async_row["edge_count"],
            "{}/{}".format(async_row["final_closed_edges"], async_row["edge_count"]),
            async_row["producer_stranded_edges"],
            async_row["local_integrated_progress_stranded_edges"],
            "{}/{}".format(caid_row["final_closed_edges"], caid_row["edge_count"]),
            caid_row["producer_stranded_edges"],
            caid_row["final_checkpoint_closure_edges"],
        ])

    text = r"""# Qwen3.6-27B Trajectory-Aware Analysis

## Main finding

Final test success and final ADPR substantially under-describe what happened during coordination. Across the frozen 20-task × 4-protocol matrix, trajectory evidence separates at least three phenomena that a terminal score merges: **capability failure**, **stranded local/producer progress**, and **non-monotonic integration with regression and recovery**.

The strongest result is the Async-private condition: it closes only **{async_closed}/55** dependency edges, while **{async_stranded}/{async_open} ({async_stranded_pct})** of its final-open edges had already shown a passing upstream contract somewhere in the trajectory. Moreover, **{async_local}/{async_open}** open edges had passed the complete dependency checker in at least one agent-local workspace. Thus, many failures cannot be summarized as producer-side incapability: contract-ready or locally viable artifacts were observed but were not converted into final integrated closure. CAID converts substantially more edges to closure (**{caid_closed}/55**) and reduces the absolute number of producer-stranded failures from **{async_stranded}** to **{caid_stranded}**. Of CAID's 45 closed edges, **{caid_final_only}/45** close only at the final checkpoint, exposing the importance of final reconciliation rather than merely independent local completion.

![Trajectory outcome profile](figures/qwen36_27_trajectory_outcome_profile.svg)

## Metrics

For dependency edge \(d\), checkpoint \(k\) records \((U_{{d,k}},D_{{d,k}},I_{{d,k}})\): upstream, downstream, and integrated checker pass states. Checkpoints additionally identify whether they evaluate an agent-local workspace or the integrated workspace.

- **Final closure (ADPR component):** whether \(I=1\) at the final integrated checkpoint.
- **First closure step:** first integrated checkpoint with \(I=1\). This is the trajectory-normalized counterpart of first-passage DRS.
- **Stable closure step (SCS):** earliest integrated checkpoint after which \(I\) remains 1 through the final checkpoint.
- **Regression count (RC):** number of integrated-workspace transitions \(I:1\\rightarrow0\).
- **Recovery:** a later \(I:0\\rightarrow1\) after a regression.
- **Producer-stranded edge:** upstream passes at least once, but final integrated closure is 0.
- **Consumer-progress-stranded edge:** downstream passes at least once, but final integrated closure is 0.
- **Local-integrated-progress-stranded edge:** the integrated checker passes in an agent-local workspace at least once, but the edge is open in the final integrated workspace.

These are complementary to ADPR/DRS/CAIL. ADPR is a terminal projection; first-passage DRS records when closure first occurs; neither indicates whether closure is durable. Strict SAD is **not** reported because the current traces do not provide complete structured visibility of agent assumptions.

## Protocol-level results

{summary_table}

“Regression edges / recovered” counts edges with at least one integrated \(1\\rightarrow0\) transition and the subset finally recovered. The stranded columns are inclusive indicators, whereas the archetypes below are mutually exclusive.

## Mutually exclusive trajectory archetypes

{archetype_table}

Single has only one final integrated checkpoint per task, so it provides terminal outcomes but cannot identify closure timing or regression. It should therefore be treated as an outcome baseline, not a process baseline.

## Dependency-type view

{type_table}

The type-level trajectory view sharpens the terminal result. Async-private closes **0/7 STATE** edges, while CAID closes **6/7**; five of those six CAID closures occur only at the final checkpoint. API exhibits a similar, though less extreme, pattern: CAID closes 14/17 edges and 10 close only at the final checkpoint. This is descriptive evidence that the advantage is concentrated in converting cross-artifact state/API obligations during reconciliation, not simply in producing more independently plausible patches.

## Cases hidden by point metrics

![Trajectory case studies](figures/qwen36_27_trajectory_case_studies.svg)

1. **python-rsa / Serial / inverse-prime contract.** Integrated states are `{rsa_trajectory}`. The edge first closes at step {rsa_first}, regresses at the serialization merge, and recovers later. Final ADPR marks it passed and first-passage DRS stops at step {rsa_first}; only the trajectory reveals the regression-recovery cycle.
2. **cookiecutter / CAID / repository-directory contract.** Integrated states are `{cookie_trajectory}`. It first closes at step {cookie_first}, falls back to producer-only state, and becomes stably closed only at step {cookie_stable}. A final-only evaluation reports success; first-passage timing overstates how early the contract was safely resolved.
3. **apache-tvm-20107 / CAID / symbolic-signature contract.** Integrated states are `{tvm_trajectory}`. The upstream remains ready, but the downstream never closes the contract. This is a persistent coordination boundary, not merely an undifferentiated failing test.

## What this supports in the paper

The defensible claim is not simply that multi-agent execution improves final accuracy. The evidence supports a more specific statement:

> AsyncCodeBench exposes whether independently useful implementation progress is converted into durable cross-agent contract closure. On Qwen3.6-27B, protocol choice changes not only how many tasks finish, but also whether producer progress becomes stranded and whether apparently resolved dependencies remain resolved.

This makes trajectory analysis the explanatory layer behind the final score. The main paper can use final success and ADPR as outcomes, then use stranded-progress and regression/stable-closure evidence to explain *why* protocols with similar-looking local progress diverge after integration.

## Canonicalization and scope

- Population: the frozen Qwen3.6-27B 20-task × 4-protocol matrix (80 runs; 55 dependency edges per protocol).
- Async-private logs contain **{duplicates}** repeated records sharing an existing checkpoint identity. The canonical trace keeps the last observation for each `checkpoint_id`, restores `logical_step` order, and assigns dense canonical steps. No test outcome is synthesized.
- All repeated identities have identical dependency-checker outcomes; canonicalization therefore changes trace length/order but not observed edge states.
- Canonical checkpoint counts are used only for this trajectory analysis. Existing frozen strict DRS/CAIL values remain unchanged in the earlier paper tables.
- This is a one-run-per-cell descriptive analysis; it establishes observed mechanisms, not population-level variance or statistical significance.

Machine-readable outputs: `qwen36_27_trajectory_per_edge.csv`, `qwen36_27_trajectory_states.csv`, `qwen36_27_trajectory_protocol_summary.csv`, `qwen36_27_trajectory_type_summary.csv`, and `qwen36_27_trajectory_provenance.v1.json`.
""".format(
        async_closed=by_protocol["async_private"]["final_closed_edges"],
        async_stranded=by_protocol["async_private"]["producer_stranded_edges"],
        async_open=by_protocol["async_private"]["final_open_edges"],
        async_stranded_pct=fmt_ratio(by_protocol["async_private"]["producer_stranded_edges"], by_protocol["async_private"]["final_open_edges"]),
        async_local=by_protocol["async_private"]["local_integrated_progress_stranded_edges"],
        caid_closed=by_protocol["caid_manager"]["final_closed_edges"],
        caid_stranded=by_protocol["caid_manager"]["producer_stranded_edges"],
        caid_open=by_protocol["caid_manager"]["final_open_edges"],
        caid_final_only=by_protocol["caid_manager"]["archetype_final_checkpoint_closure"],
        summary_table=markdown_table(
            ["Protocol", "Solved tasks", "Final closed edges", "Producer stranded / open", "Consumer progress stranded", "Local integrated progress stranded", "Regression edges / recovered"],
            summary_rows,
        ),
        archetype_table=markdown_table(
            ["Protocol", "Terminal closed", "Stable early closure", "Final-only closure", "Regressed + recovered", "Both sides but open", "Producer only", "Consumer only", "Neither side"],
            archetype_rows,
        ),
        type_table=markdown_table(
            ["Type", "Edges", "Async closed", "Async producer stranded", "Async local-checker stranded", "CAID closed", "CAID producer stranded", "CAID final-only closures"],
            type_rows,
        ),
        rsa_trajectory=rsa["integrated_trajectory"], rsa_first=rsa["first_integrated_closure_step"],
        cookie_trajectory=cookie["integrated_trajectory"], cookie_first=cookie["first_integrated_closure_step"], cookie_stable=cookie["stable_closure_step"],
        tvm_trajectory=tvm["integrated_trajectory"],
        duplicates=sum(row["duplicate_checkpoint_records"] for row in summaries),
    )
    REPORT.write_text(text, encoding="utf-8")


def validate(edge_rows, state_rows, run_rows, summaries):
    if len(run_rows) != 80 or len(edge_rows) != 220:
        raise RuntimeError("expected 80 runs and 4 x 55 edge trajectories")
    for protocol in PROTOCOLS:
        if sum(row["protocol"] == protocol for row in edge_rows) != 55:
            raise RuntimeError("expected 55 edges for {}".format(protocol))
    expected_closed = {"single": 25, "serial_specialists": 27, "async_private": 12, "caid_manager": 45}
    observed_closed = {row["protocol"]: row["final_closed_edges"] for row in summaries}
    if observed_closed != expected_closed:
        raise RuntimeError("terminal closure no longer matches frozen ADPR counts: {}".format(observed_closed))
    expected_success = {"single": 6, "serial_specialists": 5, "async_private": 2, "caid_manager": 14}
    observed_success = {row["protocol"]: row["successful_tasks"] for row in summaries}
    if observed_success != expected_success:
        raise RuntimeError("task outcomes no longer match frozen paper analysis: {}".format(observed_success))
    if sum(row["duplicates"] for row in run_rows) != 60:
        raise RuntimeError("unexpected checkpoint duplicate count")
    if sum(row["duplicate_conflicts"] for row in run_rows):
        raise RuntimeError("duplicate checkpoint identities disagree on dependency outcomes")
    if not state_rows:
        raise RuntimeError("empty state table")


def main():
    RESULTS.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)
    edge_rows, state_rows, run_rows = load_analysis()
    summaries = aggregate(edge_rows, run_rows)
    type_summaries = aggregate_types(edge_rows)
    validate(edge_rows, state_rows, run_rows, summaries)
    write_csv(EDGE_CSV, edge_rows)
    write_csv(STATE_CSV, state_rows)
    write_csv(SUMMARY_CSV, summaries)
    write_csv(TYPE_CSV, type_summaries)
    write_profile_figure(summaries)
    write_case_figure(edge_rows)
    write_report(edge_rows, summaries, type_summaries)
    provenance = {
        "schema_version": "qwen36-27-trajectory-analysis.v1",
        "source_index": str(INDEX.relative_to(ROOT)),
        "run_count": len(run_rows),
        "edge_trajectory_count": len(edge_rows),
        "state_observation_count": len(state_rows),
        "raw_checkpoint_record_count": sum(row["raw"] for row in run_rows),
        "canonical_checkpoint_count": sum(row["canonical"] for row in run_rows),
        "duplicate_checkpoint_record_count": sum(row["duplicates"] for row in run_rows),
        "conflicting_duplicate_checkpoint_identity_count": sum(
            row["duplicate_conflicts"] for row in run_rows
        ),
        "canonicalization": "keep last record per checkpoint_id; sort by logical_step, recorded_at, raw index; assign dense canonical step",
        "outputs": [
            str(path.relative_to(ROOT)) for path in
            [EDGE_CSV, STATE_CSV, SUMMARY_CSV, TYPE_CSV, REPORT, PROFILE_FIGURE, CASE_FIGURE]
        ],
    }
    PROVENANCE.write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
    print("wrote {} edge trajectories and {} state observations".format(len(edge_rows), len(state_rows)))
    print("report: {}".format(REPORT))


if __name__ == "__main__":
    main()
