#!/usr/bin/env python3
"""Plot presentation-ready summaries for the four-task TVM comparison."""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = (
    ROOT / "docs" / "results" / "tvm_four_task_all_model_per_run_20260904.csv"
)
DEFAULT_OUTPUT = ROOT / "docs" / "results" / "figures"

MODELS = (
    "Qwen3.6-27B",
    "DeepSeek-V4-Flash-0731 (OpenRouter)",
    "GLM-4.7-Flash",
    "Muse-Glimmer-30B",
    "Qwen3-Coder-Next-FP8",
    "NVIDIA Nemotron-3.5-Lightning",
    "Gemma-4-26B-A4B",
)
MODEL_LABELS = {
    "Qwen3.6-27B": "Qwen3.6-27B",
    "DeepSeek-V4-Flash-0731 (OpenRouter)": "DeepSeek V4 Flash",
    "GLM-4.7-Flash": "GLM-4.7-Flash",
    "Muse-Glimmer-30B": "Muse-Glimmer-30B",
    "Qwen3-Coder-Next-FP8": "Qwen3-Coder-Next",
    "NVIDIA Nemotron-3.5-Lightning": "Nemotron-3.5",
    "Gemma-4-26B-A4B": "Gemma 4 (N/R)",
}
MODEL_COLORS = {
    "Qwen3.6-27B": "#3B6FB6",
    "DeepSeek-V4-Flash-0731 (OpenRouter)": "#E45756",
    "GLM-4.7-Flash": "#54A24B",
    "Muse-Glimmer-30B": "#72B7B2",
    "Qwen3-Coder-Next-FP8": "#F2CF5B",
    "NVIDIA Nemotron-3.5-Lightning": "#B279A2",
    "Gemma-4-26B-A4B": "#9D9D9D",
}
PROTOCOLS = ("single", "serial_specialists", "async_private", "caid_manager")
PROTOCOL_LABELS = {
    "single": "Single",
    "serial_specialists": "Serial",
    "async_private": "Async private",
    "caid_manager": "CAID",
}
PROTOCOL_MARKERS = {
    "single": "o",
    "serial_specialists": "s",
    "async_private": "^",
    "caid_manager": "D",
}
TASKS = (
    "apache-tvm-20153",
    "apache-tvm-20107",
    "apache-tvm-20073",
    "apache-tvm-20018",
)
TASK_LABELS = {
    "apache-tvm-20153": "20153\nPTX chain",
    "apache-tvm-20107": "20107\nSignature fan-out",
    "apache-tvm-20073": "20073\nSpan join",
    "apache-tvm-20018": "20018\nReturn-IR chain",
}

FOOTNOTE = (
    "Four official TVM tasks; one selected run per model-task-protocol cell. "
    "CAID denotes the manager-mediated condition: historical local and current "
    "read-only OpenRouter action spaces differ. Gemma has no TVM run; Nemotron is "
    "missing three TVM-20018 multi-agent cells."
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    required = {"model", "task", "protocol", "success", "pass_rate", "ADPR"}
    if not rows or not required.issubset(rows[0]):
        raise ValueError(f"Missing required columns in {path}")
    return rows


def value(row: dict[str, str], field: str) -> float | None:
    raw = row.get(field, "").strip()
    return float(raw) if raw else None


def succeeded(row: dict[str, str]) -> float:
    return float(row["success"].strip().lower() == "true")


def mean(values: list[float | None]) -> float:
    present = [item for item in values if item is not None and np.isfinite(item)]
    return float(np.mean(present)) if present else np.nan


def configure_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "axes.titlesize": 14,
            "axes.titleweight": "bold",
            "axes.labelsize": 11,
            "axes.edgecolor": "#59636E",
            "axes.linewidth": 0.8,
            "xtick.labelsize": 10,
            "ytick.labelsize": 10,
            "legend.fontsize": 9,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "savefig.facecolor": "white",
        }
    )


def save(figure: plt.Figure, output_dir: Path, stem: str) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for extension, kwargs in (
        ("png", {"dpi": 240}),
        ("pdf", {}),
        ("svg", {}),
    ):
        figure.savefig(
            output_dir / f"{stem}.{extension}", bbox_inches="tight", **kwargs
        )
    svg_path = output_dir / f"{stem}.svg"
    svg_path.write_text(
        "\n".join(line.rstrip() for line in svg_path.read_text().splitlines())
        + "\n",
        encoding="utf-8",
    )
    plt.close(figure)


def add_footnote(figure: plt.Figure, text: str = FOOTNOTE) -> None:
    figure.text(
        0.5,
        0.012,
        text,
        ha="center",
        va="bottom",
        fontsize=8.2,
        color="#59636E",
        wrap=True,
    )


def matrix_for_protocol(
    rows: list[dict[str, str]], field: str
) -> tuple[np.ndarray, np.ndarray]:
    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[(row["model"], row["protocol"])].append(row)
    values = np.full((len(MODELS), len(PROTOCOLS)), np.nan)
    counts = np.zeros_like(values)
    for i, model in enumerate(MODELS):
        for j, protocol in enumerate(PROTOCOLS):
            selected = grouped.get((model, protocol), [])
            counts[i, j] = len(selected)
            if field == "success":
                values[i, j] = mean([succeeded(row) for row in selected])
            else:
                values[i, j] = mean([value(row, field) for row in selected])
    return values, counts


def draw_heatmap(
    axis: plt.Axes,
    data: np.ndarray,
    counts: np.ndarray,
    title: str,
    *,
    cmap: str,
) -> None:
    masked = np.ma.masked_invalid(data * 100)
    color_map = plt.get_cmap(cmap).copy()
    color_map.set_bad("#E8EAED")
    image = axis.imshow(masked, vmin=0, vmax=100, cmap=color_map, aspect="auto")
    axis.set_title(title, pad=12)
    axis.set_xticks(range(len(PROTOCOLS)), [PROTOCOL_LABELS[p] for p in PROTOCOLS])
    axis.set_yticks(range(len(MODELS)), [MODEL_LABELS[m] for m in MODELS])
    axis.tick_params(length=0)
    for i in range(len(MODELS)):
        for j in range(len(PROTOCOLS)):
            raw = data[i, j]
            if np.isnan(raw):
                label, color = "N/R", "#777777"
            else:
                label = f"{raw * 100:.1f}%\n(n={int(counts[i, j])})"
                color = "white" if raw >= 0.55 else "#17202A"
            axis.text(j, i, label, ha="center", va="center", fontsize=9, color=color)
    axis.set_xticks(np.arange(-0.5, len(PROTOCOLS), 1), minor=True)
    axis.set_yticks(np.arange(-0.5, len(MODELS), 1), minor=True)
    axis.grid(which="minor", color="white", linewidth=2)
    axis.tick_params(which="minor", bottom=False, left=False)
    for spine in axis.spines.values():
        spine.set_visible(False)
    plt.colorbar(image, ax=axis, fraction=0.035, pad=0.025).set_label("Percent")


def primary_metric_figure(rows: list[dict[str, str]], output_dir: Path) -> None:
    adpr, adpr_n = matrix_for_protocol(rows, "ADPR")
    fsr, fsr_n = matrix_for_protocol(rows, "success")
    figure, axes = plt.subplots(1, 2, figsize=(16.5, 6.4))
    draw_heatmap(axes[0], adpr, adpr_n, "Final dependency closure — ADPR ↑", cmap="Blues")
    draw_heatmap(axes[1], fsr, fsr_n, "Final task success — FSR ↑", cmap="Greens")
    figure.suptitle(
        "TVM primary outcomes by model and collaboration protocol",
        fontsize=19,
        fontweight="bold",
        y=1.01,
    )
    add_footnote(figure)
    figure.subplots_adjust(bottom=0.16, wspace=0.33)
    save(figure, output_dir, "tvm_model_protocol_primary_metrics")


def best_task_matrix(
    rows: list[dict[str, str]], field: str
) -> tuple[np.ndarray, list[list[str]]]:
    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[(row["model"], row["task"])].append(row)
    data = np.full((len(MODELS), len(TASKS)), np.nan)
    annotations = [["" for _ in TASKS] for _ in MODELS]
    for i, model in enumerate(MODELS):
        for j, task in enumerate(TASKS):
            selected = grouped.get((model, task), [])
            if not selected:
                annotations[i][j] = "N/R"
                continue
            scored = [
                (
                    succeeded(row) if field == "success" else value(row, field),
                    row,
                )
                for row in selected
            ]
            scored = [(score, row) for score, row in scored if score is not None]
            if not scored:
                annotations[i][j] = "N/A"
                continue
            score, best = max(scored, key=lambda item: item[0])
            data[i, j] = score
            short_protocol = {
                "single": "S",
                "serial_specialists": "SER",
                "async_private": "AP",
                "caid_manager": "MGR",
            }[best["protocol"]]
            star = " ★" if succeeded(best) else ""
            annotations[i][j] = f"{score * 100:.1f}%{star}\n{short_protocol}"
    return data, annotations


def draw_task_heatmap(
    axis: plt.Axes,
    data: np.ndarray,
    annotations: list[list[str]],
    title: str,
    cmap: str,
) -> None:
    masked = np.ma.masked_invalid(data * 100)
    color_map = plt.get_cmap(cmap).copy()
    color_map.set_bad("#E8EAED")
    image = axis.imshow(masked, vmin=0, vmax=100, cmap=color_map, aspect="auto")
    axis.set_title(title, pad=10)
    axis.set_xticks(range(len(TASKS)), [TASK_LABELS[t] for t in TASKS])
    axis.set_yticks(range(len(MODELS)), [MODEL_LABELS[m] for m in MODELS])
    axis.tick_params(length=0)
    for i in range(len(MODELS)):
        for j in range(len(TASKS)):
            raw = data[i, j]
            color = "#777777" if np.isnan(raw) else ("white" if raw >= 0.58 else "#17202A")
            axis.text(j, i, annotations[i][j], ha="center", va="center", fontsize=8.8, color=color)
    axis.set_xticks(np.arange(-0.5, len(TASKS), 1), minor=True)
    axis.set_yticks(np.arange(-0.5, len(MODELS), 1), minor=True)
    axis.grid(which="minor", color="white", linewidth=2)
    axis.tick_params(which="minor", bottom=False, left=False)
    for spine in axis.spines.values():
        spine.set_visible(False)
    plt.colorbar(image, ax=axis, fraction=0.035, pad=0.025).set_label("Percent")


def task_outcome_figure(rows: list[dict[str, str]], output_dir: Path) -> None:
    pass_data, pass_annotations = best_task_matrix(rows, "pass_rate")
    adpr_data, adpr_annotations = best_task_matrix(rows, "ADPR")
    figure, axes = plt.subplots(1, 2, figsize=(15.8, 6.6))
    draw_task_heatmap(
        axes[0], pass_data, pass_annotations, "Best final evaluator pass rate ↑", "YlGnBu"
    )
    draw_task_heatmap(
        axes[1], adpr_data, adpr_annotations, "Best final ADPR ↑", "OrRd"
    )
    figure.suptitle(
        "Best observed outcome for each TVM task",
        fontsize=19,
        fontweight="bold",
        y=1.01,
    )
    figure.text(
        0.5,
        0.055,
        "Cell suffix gives the best protocol: S=Single, SER=Serial, AP=Async private, MGR=Manager; ★ marks full task success.",
        ha="center",
        fontsize=8.8,
        color="#30363D",
    )
    add_footnote(figure)
    figure.subplots_adjust(bottom=0.18, wspace=0.30)
    save(figure, output_dir, "tvm_task_model_best_outcomes")


def pass_adpr_figure(rows: list[dict[str, str]], output_dir: Path) -> None:
    figure, axis = plt.subplots(figsize=(11.8, 7.4))
    axis.axvspan(90, 100, ymin=0.0, ymax=0.22, color="#FDE2E2", alpha=0.75, zorder=0)
    axis.text(
        99,
        5,
        "High pass rate\nbut unresolved\ndependencies",
        ha="right",
        va="bottom",
        color="#A33A3A",
        fontsize=9,
    )
    for model in MODELS:
        model_rows = [row for row in rows if row["model"] == model]
        for protocol in PROTOCOLS:
            selected = [row for row in model_rows if row["protocol"] == protocol]
            if not selected:
                continue
            xs = [100 * value(row, "pass_rate") for row in selected]
            ys = [100 * value(row, "ADPR") for row in selected]
            axis.scatter(
                xs,
                ys,
                s=65,
                marker=PROTOCOL_MARKERS[protocol],
                c=MODEL_COLORS[model],
                alpha=0.78,
                edgecolors="white",
                linewidths=0.7,
                zorder=3,
            )
            for x, y, row in zip(xs, ys, selected):
                if y <= 0:
                    continue
                task = row["task"].removeprefix("apache-tvm-")
                label = f"{MODEL_LABELS[model].split()[0]} {task} {PROTOCOL_LABELS[protocol]}"
                offset = (7, 7)
                if model.startswith("DeepSeek") and protocol == "caid_manager":
                    offset = (7, -15)
                axis.annotate(
                    label,
                    (x, y),
                    xytext=offset,
                    textcoords="offset points",
                    fontsize=8.2,
                    color="#30363D",
                )
            successes = [row for row in selected if succeeded(row)]
            if successes:
                axis.scatter(
                    [100 * value(row, "pass_rate") for row in successes],
                    [100 * value(row, "ADPR") for row in successes],
                    s=155,
                    marker="*",
                    facecolors="#FFD54F",
                    edgecolors="#202124",
                    linewidths=1.0,
                    zorder=5,
                )
    axis.axvline(90, color="#9AA0A6", linestyle="--", linewidth=1)
    axis.set_xlim(-2, 103)
    axis.set_ylim(-4, 108)
    axis.set_xlabel("Final evaluator pass rate (%) ↑")
    axis.set_ylabel("Final integrated ADPR (%) ↑")
    axis.set_title("Raw test pass rate and dependency closure are not interchangeable")
    axis.grid(color="#E3E7EA", linewidth=0.8)
    axis.set_axisbelow(True)
    axis.spines["top"].set_visible(False)
    axis.spines["right"].set_visible(False)
    model_handles = [
        Line2D(
            [0],
            [0],
            marker="o",
            linestyle="",
            markerfacecolor=MODEL_COLORS[m],
            markeredgecolor="white",
            markersize=8,
            label=MODEL_LABELS[m],
        )
        for m in MODELS
        if any(row["model"] == m for row in rows)
    ]
    protocol_handles = [
        Line2D(
            [0],
            [0],
            marker=PROTOCOL_MARKERS[p],
            linestyle="",
            color="#4A4A4A",
            markersize=7,
            label=PROTOCOL_LABELS[p],
        )
        for p in PROTOCOLS
    ]
    first_legend = axis.legend(
        handles=model_handles,
        title="Model",
        loc="upper left",
        bbox_to_anchor=(1.01, 1.0),
        frameon=False,
    )
    axis.add_artist(first_legend)
    axis.legend(
        handles=protocol_handles,
        title="Protocol",
        loc="lower left",
        bbox_to_anchor=(1.01, 0.0),
        frameon=False,
    )
    figure.suptitle(
        "TVM diagnostic value of ADPR",
        fontsize=19,
        fontweight="bold",
        y=0.99,
    )
    add_footnote(figure)
    figure.subplots_adjust(bottom=0.14, right=0.78)
    save(figure, output_dir, "tvm_pass_adpr_decoupling")


def coordination_cost_figure(rows: list[dict[str, str]], output_dir: Path) -> None:
    models = [
        model
        for model in MODELS
        if model != "Gemma-4-26B-A4B" and any(row["model"] == model for row in rows)
    ]
    protocols = ("serial_specialists", "async_private", "caid_manager")
    protocol_colors = {
        "serial_specialists": "#4C78A8",
        "async_private": "#F2B134",
        "caid_manager": "#59A14F",
    }
    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[(row["model"], row["protocol"])].append(row)

    metrics = (
        ("FSAR", 100.0, "Failed subagent attempts — FSAR ↓", "%"),
        ("tokens", 1e-6, "Mean model tokens per cell ↓", "M"),
        ("runtime_min", 1.0, "Mean wall-clock runtime per cell ↓", "min"),
    )
    figure, axes = plt.subplots(1, 3, figsize=(17.5, 6.4))
    positions = np.arange(len(models))
    width = 0.24
    for axis, (field, scale, title, unit) in zip(axes, metrics):
        for index, protocol in enumerate(protocols):
            vals = []
            for model in models:
                selected = grouped.get((model, protocol), [])
                vals.append(mean([value(row, field) for row in selected]) * scale)
            bars = axis.bar(
                positions + (index - 1) * width,
                vals,
                width,
                color=protocol_colors[protocol],
                label=PROTOCOL_LABELS[protocol],
                edgecolor="white",
                linewidth=0.6,
            )
            for bar, val in zip(bars, vals):
                if np.isnan(val):
                    continue
                label = f"{val:.0f}" if field in {"FSAR", "runtime_min"} else f"{val:.1f}"
                axis.annotate(
                    label,
                    (bar.get_x() + bar.get_width() / 2, val),
                    xytext=(0, 3 + index * 4),
                    textcoords="offset points",
                    ha="center",
                    va="bottom",
                    fontsize=7.3,
                    rotation=90 if field == "runtime_min" else 0,
                )
        axis.set_title(title)
        axis.set_ylabel(unit)
        axis.set_xticks(positions, [MODEL_LABELS[m] for m in models], rotation=30, ha="right")
        axis.grid(axis="y", color="#E3E7EA", linewidth=0.8)
        axis.set_axisbelow(True)
        axis.spines["top"].set_visible(False)
        axis.spines["right"].set_visible(False)
        axis.margins(y=0.15)
    handles, labels = axes[0].get_legend_handles_labels()
    figure.legend(
        handles,
        labels,
        loc="upper center",
        bbox_to_anchor=(0.5, 0.92),
        ncol=3,
        frameon=False,
    )
    figure.suptitle(
        "TVM coordination reliability and inference cost",
        fontsize=19,
        fontweight="bold",
        y=1.0,
    )
    add_footnote(figure)
    figure.subplots_adjust(bottom=0.26, top=0.82, wspace=0.28)
    save(figure, output_dir, "tvm_coordination_cost_profile")


def dashboard_matrix(
    rows: list[dict[str, str]], field: str, protocols: tuple[str, ...]
) -> tuple[np.ndarray, np.ndarray]:
    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[(row["model"], row["protocol"])].append(row)
    data = np.full((len(MODELS), len(protocols)), np.nan)
    counts = np.zeros_like(data)
    for i, model in enumerate(MODELS):
        for j, protocol in enumerate(protocols):
            selected = grouped.get((model, protocol), [])
            data[i, j] = mean([value(row, field) for row in selected])
            counts[i, j] = len(selected)
    return data, counts


def draw_dashboard_heatmap(
    axis: plt.Axes,
    rows: list[dict[str, str]],
    field: str,
    title: str,
    *,
    scale: float,
    vmax: float,
    cmap: str,
    percent: bool,
    show_ylabels: bool,
) -> None:
    protocols = ("serial_specialists", "async_private", "caid_manager")
    data, counts = dashboard_matrix(rows, field, protocols)
    plotted = data * scale
    masked = np.ma.masked_invalid(plotted)
    color_map = plt.get_cmap(cmap).copy()
    color_map.set_bad("#E8EAED")
    image = axis.imshow(masked, vmin=0, vmax=vmax, cmap=color_map, aspect="auto")
    axis.set_title(title, fontsize=12.5, pad=8)
    axis.set_xticks(range(len(protocols)), [PROTOCOL_LABELS[p] for p in protocols])
    if show_ylabels:
        axis.set_yticks(range(len(MODELS)), [MODEL_LABELS[m] for m in MODELS])
    else:
        axis.set_yticks(range(len(MODELS)), ["" for _ in MODELS])
    axis.tick_params(length=0)
    for i in range(len(MODELS)):
        for j in range(len(protocols)):
            raw = plotted[i, j]
            if np.isnan(raw):
                label, color = "N/A", "#777777"
            else:
                label = f"{raw:.1f}%" if percent else f"{raw:.2f}"
                label += f"\nn={int(counts[i, j])}"
                color = "white" if raw >= vmax * 0.55 else "#17202A"
            axis.text(j, i, label, ha="center", va="center", fontsize=7.8, color=color)
    axis.set_xticks(np.arange(-0.5, len(protocols), 1), minor=True)
    axis.set_yticks(np.arange(-0.5, len(MODELS), 1), minor=True)
    axis.grid(which="minor", color="white", linewidth=1.8)
    axis.tick_params(which="minor", bottom=False, left=False)
    for spine in axis.spines.values():
        spine.set_visible(False)
    plt.colorbar(image, ax=axis, fraction=0.045, pad=0.025)


def coordination_dashboard_figure(
    rows: list[dict[str, str]], output_dir: Path
) -> None:
    panels = (
        ("DRE", "Resolution efficiency — DRE ↑", 100.0, 100.0, "Greens", True),
        ("DRS_P", "Resolution step — DRS-P ↓", 1.0, 14.0, "OrRd", False),
        ("CAIL_P", "Integration lag — CAIL-P ↓", 1.0, 14.0, "OrRd", False),
        ("FSAR", "Failed attempts — FSAR ↓", 100.0, 100.0, "Reds", True),
        ("SVR", "Scope violations — SVR ↓", 100.0, 100.0, "Reds", True),
        ("MRR", "Manager recovery — MRR ↑*", 100.0, 100.0, "Purples", True),
    )
    figure, axes = plt.subplots(2, 3, figsize=(17.2, 10.2))
    for index, (axis, panel) in enumerate(zip(axes.flat, panels)):
        field, title, scale, vmax, cmap, percent = panel
        draw_dashboard_heatmap(
            axis,
            rows,
            field,
            title,
            scale=scale,
            vmax=vmax,
            cmap=cmap,
            percent=percent,
            show_ylabels=index % 3 == 0,
        )
    figure.suptitle(
        "TVM coordination metric dashboard",
        fontsize=20,
        fontweight="bold",
        y=0.995,
    )
    figure.text(
        0.5,
        0.052,
        "↑ higher is better; ↓ lower is better. MRR is conditional on recovery opportunities and must be read together with FSAR. "
        "IFR is omitted because every selected multi-agent aggregate is 100% under the current run-level definition.",
        ha="center",
        fontsize=8.7,
        color="#30363D",
    )
    add_footnote(figure)
    figure.subplots_adjust(bottom=0.13, top=0.93, hspace=0.28, wspace=0.24)
    save(figure, output_dir, "tvm_coordination_metric_dashboard")


def main() -> None:
    args = parse_args()
    configure_style()
    rows = load_rows(args.input)
    primary_metric_figure(rows, args.output_dir)
    task_outcome_figure(rows, args.output_dir)
    pass_adpr_figure(rows, args.output_dir)
    coordination_cost_figure(rows, args.output_dir)
    coordination_dashboard_figure(rows, args.output_dir)
    print(f"Wrote five TVM figure sets to {args.output_dir}")


if __name__ == "__main__":
    main()
