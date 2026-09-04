#!/usr/bin/env python3
"""Generate presentation figures for the three-model AsynCodeBench comparison."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "docs" / "results" / "asynccodebench_three_model_comparison.csv"
DEFAULT_OUTPUT = ROOT / "docs" / "results" / "figures"

MODELS = ("DeepSeek V4 Flash", "Qwen3.6-27B", "Gemma 4 26B-A4B")
PROTOCOLS = ("single", "serial_specialists", "async_private", "caid_manager")
PROTOCOL_LABELS = ("Single", "Serial", "Async private", "CAID")
MODEL_COLORS = {
    "DeepSeek V4 Flash": "#00796B",
    "Qwen3.6-27B": "#3B6FB6",
    "Gemma 4 26B-A4B": "#C44569",
}
MODEL_HATCHES = {
    "DeepSeek V4 Flash": "",
    "Qwen3.6-27B": "..",
    "Gemma 4 26B-A4B": "//",
}
PROTOCOL_COLORS = {
    "single": "#5B6573",
    "serial_specialists": "#3B6FB6",
    "async_private": "#D49A00",
    "caid_manager": "#2E8B57",
}
PROTOCOL_MARKERS = {
    "single": "o",
    "serial_specialists": "s",
    "async_private": "^",
    "caid_manager": "D",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def load_rows(path: Path) -> dict[tuple[str, str], dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    keyed = {(row["model"], row["protocol"]): row for row in rows}
    expected = {(model, protocol) for model in MODELS for protocol in PROTOCOLS}
    if set(keyed) != expected:
        missing = sorted(expected - set(keyed))
        extra = sorted(set(keyed) - expected)
        raise ValueError(f"Unexpected comparison rows: missing={missing}, extra={extra}")
    return keyed


def number(
    rows: dict[tuple[str, str], dict[str, str]],
    model: str,
    protocol: str,
    field: str,
) -> float:
    return float(rows[(model, protocol)][field])


def optional_number(
    rows: dict[tuple[str, str], dict[str, str]],
    model: str,
    protocol: str,
    field: str,
) -> float | None:
    raw = rows[(model, protocol)][field].strip()
    return float(raw) if raw else None


def configure_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 11,
            "axes.titlesize": 15,
            "axes.titleweight": "bold",
            "axes.labelsize": 12,
            "axes.edgecolor": "#59636E",
            "axes.linewidth": 0.8,
            "xtick.labelsize": 11,
            "ytick.labelsize": 10,
            "legend.fontsize": 11,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "savefig.facecolor": "white",
        }
    )


def clean_axis(axis: plt.Axes) -> None:
    axis.spines["top"].set_visible(False)
    axis.spines["right"].set_visible(False)
    axis.grid(axis="y", color="#DDE2E6", linewidth=0.8)
    axis.set_axisbelow(True)


def add_bar_labels(
    axis: plt.Axes, bars, *, suffix: str = "", y_offset: int = 4
) -> None:
    for bar in bars:
        value = bar.get_height()
        if not np.isfinite(value):
            axis.annotate(
                "N/R",
                (bar.get_x() + bar.get_width() / 2, 0),
                xytext=(0, y_offset),
                textcoords="offset points",
                ha="center",
                va="bottom",
                fontsize=7.5,
                color="#59636E",
            )
            continue
        label = f"{value:.1f}{suffix}" if value else f"0{suffix}"
        axis.annotate(
            label,
            (bar.get_x() + bar.get_width() / 2, value),
            xytext=(0, y_offset),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=8,
            color="#30363D",
        )


def save_figure(figure: plt.Figure, output_dir: Path, stem: str) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_dir / f"{stem}.png", dpi=220, bbox_inches="tight")
    figure.savefig(output_dir / f"{stem}.pdf", bbox_inches="tight")
    plt.close(figure)


def grouped_bars(
    axis: plt.Axes,
    rows: dict[tuple[str, str], dict[str, str]],
    field: str,
    title: str,
    ylabel: str,
    scale: float,
    ylim: tuple[float, float],
    suffix: str,
) -> None:
    positions = np.arange(len(PROTOCOLS))
    width = 0.78 / len(MODELS)
    for index, model in enumerate(MODELS):
        values = [
            value * scale if value is not None else np.nan
            for protocol in PROTOCOLS
            for value in [optional_number(rows, model, protocol, field)]
        ]
        bars = axis.bar(
            positions + (index - (len(MODELS) - 1) / 2) * width,
            values,
            width,
            label=model,
            color=MODEL_COLORS[model],
            hatch=MODEL_HATCHES[model],
            edgecolor="white",
            linewidth=0.7,
        )
        add_bar_labels(axis, bars, suffix=suffix, y_offset=4 + index * 5)
    axis.set_title(title)
    axis.set_ylabel(ylabel)
    axis.set_xticks(positions, PROTOCOL_LABELS)
    axis.set_ylim(*ylim)
    clean_axis(axis)


def performance_figure(
    rows: dict[tuple[str, str], dict[str, str]], output_dir: Path
) -> None:
    figure, axes = plt.subplots(1, 3, figsize=(17, 6.8))
    grouped_bars(
        axes[0],
        rows,
        "success_rate",
        "Final task success",
        "Tasks solved (%)",
        100,
        (0, 112),
        "%",
    )
    grouped_bars(
        axes[1],
        rows,
        "mean_test_pass_rate",
        "Partial functional progress",
        "Mean test pass (%)",
        100,
        (0, 112),
        "%",
    )
    grouped_bars(
        axes[2],
        rows,
        "mean_ADPR",
        "Final dependency closure",
        "Mean ADPR (%)",
        100,
        (0, 112),
        "%",
    )
    handles, labels = axes[0].get_legend_handles_labels()
    figure.legend(
        handles,
        labels,
        loc="upper center",
        bbox_to_anchor=(0.5, 0.91),
        ncol=3,
        frameon=False,
    )
    figure.suptitle(
        "Model capability and protocol outcomes on AsynCodeBench",
        fontsize=19,
        fontweight="bold",
        y=0.98,
    )
    figure.text(
        0.5,
        0.015,
        "16 official tasks; higher is better. One run per cell. Qwen is a valid-bundle mixed-lineage descriptive aggregate.",
        ha="center",
        fontsize=10,
        color="#59636E",
    )
    figure.subplots_adjust(top=0.76, bottom=0.15, wspace=0.28)
    save_figure(figure, output_dir, "model_protocol_performance")


def timing_figure(
    rows: dict[tuple[str, str], dict[str, str]], output_dir: Path
) -> None:
    figure, axes = plt.subplots(1, 2, figsize=(14.5, 6.8))
    grouped_bars(
        axes[0],
        rows,
        "penalized_DRS",
        "Dependency resolution step",
        "Mean penalized DRS",
        1,
        (0, 12.5),
        "",
    )
    grouped_bars(
        axes[1],
        rows,
        "penalized_CAIL",
        "Cross-agent integration lag",
        "Mean penalized CAIL",
        1,
        (0, 12.5),
        "",
    )
    handles, labels = axes[0].get_legend_handles_labels()
    figure.legend(
        handles,
        labels,
        loc="upper center",
        bbox_to_anchor=(0.5, 0.91),
        ncol=3,
        frameon=False,
    )
    figure.suptitle(
        "Asynchronous protocols delay dependency resolution",
        fontsize=19,
        fontweight="bold",
        y=0.98,
    )
    figure.text(
        0.5,
        0.015,
        "Lower is better; unresolved dependencies receive T + 1. Qwen is a valid-bundle mixed-lineage descriptive aggregate.",
        ha="center",
        fontsize=10,
        color="#59636E",
    )
    figure.subplots_adjust(top=0.76, bottom=0.15, wspace=0.25)
    save_figure(figure, output_dir, "dependency_timing")


def dependency_profile_figure(
    rows: dict[tuple[str, str], dict[str, str]], output_dir: Path
) -> None:
    figure, axes = plt.subplots(2, 2, figsize=(14.5, 10.5))
    panels = (
        ("mean_ADPR", "Final dependency closure ↑", "Mean ADPR (%)", 100, (0, 112), "%"),
        (
            "mean_unresolved_dependencies",
            "Dependencies left unresolved ↓",
            "Mean unresolved dependencies per task",
            1,
            (0, 3.4),
            "",
        ),
        (
            "penalized_DRS",
            "Dependency resolution step ↓",
            "Mean penalized DRS",
            1,
            (0, 12.5),
            "",
        ),
        (
            "penalized_CAIL",
            "Cross-agent integration lag ↓",
            "Mean penalized CAIL",
            1,
            (0, 12.5),
            "",
        ),
    )
    for axis, panel in zip(axes.flat, panels):
        grouped_bars(axis, rows, *panel)

    handles, labels = axes[0, 0].get_legend_handles_labels()
    figure.legend(
        handles,
        labels,
        loc="upper center",
        bbox_to_anchor=(0.5, 0.915),
        ncol=3,
        frameon=False,
    )
    figure.suptitle(
        "AsynCodeBench exposes dependency closure and coordination delay",
        fontsize=19,
        fontweight="bold",
        y=0.98,
    )
    figure.text(
        0.5,
        0.018,
        "ADPR: higher is better; unresolved count and penalized DRS/CAIL: lower is better. DRS unresolved = T + 1.\n"
        "CAIL = max(0, downstream - upstream) when observed; otherwise T + 1 - upstream or T + 1. "
        "Qwen is a valid-bundle mixed-lineage descriptive aggregate.",
        ha="center",
        fontsize=10,
        color="#59636E",
    )
    figure.subplots_adjust(top=0.80, bottom=0.12, hspace=0.40, wspace=0.24)
    save_figure(figure, output_dir, "asynccodebench_dependency_profile")


def coordination_diagnostics_figure(
    rows: dict[tuple[str, str], dict[str, str]], output_dir: Path
) -> None:
    models = ("Qwen3.6-27B", "Gemma 4 26B-A4B")
    protocols = PROTOCOLS[1:]
    labels = PROTOCOL_LABELS[1:]
    panels = (
        ("FSAR", "Failed subagent attempts", "FSAR (%)", "lower is better"),
        ("IFR", "Integration failure", "IFR (%)", "lower is better"),
        ("SVR", "Writable-scope violations", "SVR (%)", "lower is better"),
        (
            "MRR",
            "Manager recovery after failures",
            "MRR (%)",
            "conditional diagnostic",
        ),
    )
    figure, axes = plt.subplots(2, 2, figsize=(14.5, 10.5))
    for axis, (field, title, ylabel, direction) in zip(axes.flat, panels):
        positions = np.arange(len(protocols))
        width = 0.36
        for index, model in enumerate(models):
            values = [number(rows, model, protocol, field) * 100 for protocol in protocols]
            bars = axis.bar(
                positions + (index - 0.5) * width,
                values,
                width,
                label=model,
                color=MODEL_COLORS[model],
                hatch=MODEL_HATCHES[model],
                edgecolor="white",
                linewidth=0.8,
            )
            add_bar_labels(axis, bars, suffix="%", y_offset=4 + index * 5)
        axis.set_title(f"{title}\n({direction})")
        axis.set_ylabel(ylabel)
        axis.set_xticks(positions, labels)
        axis.set_ylim(0, 112)
        clean_axis(axis)

    figure.suptitle(
        "Coordination diagnostics separate local-model failure modes",
        fontsize=19,
        fontweight="bold",
        y=0.98,
    )
    figure.text(
        0.5,
        0.018,
        "Lower FSAR/IFR/SVR is cleaner; MRR is conditional. Qwen is a valid-bundle mixed-lineage descriptive aggregate.",
        ha="center",
        fontsize=10,
        color="#59636E",
    )
    handles, legend_labels = axes[0, 0].get_legend_handles_labels()
    figure.legend(
        handles,
        legend_labels,
        loc="upper center",
        bbox_to_anchor=(0.5, 0.91),
        ncol=2,
        frameon=False,
    )
    figure.subplots_adjust(top=0.80, bottom=0.10, hspace=0.42, wspace=0.24)
    save_figure(figure, output_dir, "local_model_coordination_diagnostics")


def tradeoff_figure(
    rows: dict[tuple[str, str], dict[str, str]], output_dir: Path
) -> None:
    figure, axes = plt.subplots(1, 3, figsize=(21, 6.8))
    for axis, model in zip(axes, MODELS):
        points = {}
        for protocol, label in zip(PROTOCOLS, PROTOCOL_LABELS):
            runtime_minutes = number(rows, model, protocol, "mean_runtime_seconds") / 60
            pass_rate = number(rows, model, protocol, "mean_test_pass_rate") * 100
            points[protocol] = (runtime_minutes, pass_rate)
            axis.scatter(
                runtime_minutes,
                pass_rate,
                s=130,
                marker=PROTOCOL_MARKERS[protocol],
                color=PROTOCOL_COLORS[protocol],
                edgecolor="white",
                linewidth=1.2,
                zorder=3,
                label=label,
            )
            offset = {
                "single": (7, 8),
                "serial_specialists": (7, -15),
                "async_private": (7, 8),
                "caid_manager": (7, 8),
            }[protocol]
            if model == "Qwen3.6-27B":
                offset = {
                    "single": (7, 8),
                    "serial_specialists": (7, 8),
                    "async_private": (7, -16),
                    "caid_manager": (7, 8),
                }[protocol]
            axis.annotate(
                label,
                (runtime_minutes, pass_rate),
                xytext=offset,
                textcoords="offset points",
                fontsize=10,
                color="#30363D",
            )

        serial = points["serial_specialists"]
        async_point = points["async_private"]
        axis.annotate(
            "",
            xy=async_point,
            xytext=serial,
            arrowprops={"arrowstyle": "->", "color": "#59636E", "lw": 1.6},
        )
        axis.text(
            (serial[0] + async_point[0]) / 2,
            (serial[1] + async_point[1]) / 2
            + (4.0 if model == "Qwen3.6-27B" else 2.0),
            f"{(serial[0] - async_point[0]) / serial[0] * 100:.1f}% faster",
            ha="center",
            fontsize=10,
            fontweight="bold",
            color="#59636E",
        )
        axis.set_title(model)
        axis.set_xlabel("Mean runtime (minutes)")
        axis.set_ylabel("Mean test pass (%)")
        x_values = [point[0] for point in points.values()]
        y_values = [point[1] for point in points.values()]
        axis.set_xlim(max(0, min(x_values) - 6), max(x_values) + 8)
        axis.set_ylim(max(0, min(y_values) - 10), min(105, max(y_values) + 12))
        clean_axis(axis)

    handles, labels = axes[0].get_legend_handles_labels()
    figure.legend(
        handles,
        labels,
        loc="upper center",
        bbox_to_anchor=(0.5, 0.91),
        ncol=4,
        frameon=False,
    )
    figure.suptitle(
        "Async private is faster, but not more effective",
        fontsize=19,
        fontweight="bold",
        y=0.98,
    )
    figure.text(
        0.5,
        0.015,
        "Compare within each model; serving differs across models. Qwen is a valid-bundle mixed-lineage descriptive aggregate.",
        ha="center",
        fontsize=10,
        color="#59636E",
    )
    figure.subplots_adjust(top=0.76, bottom=0.15, wspace=0.24)
    save_figure(figure, output_dir, "async_speed_quality_tradeoff")


def main() -> int:
    args = parse_args()
    configure_style()
    rows = load_rows(args.input)
    performance_figure(rows, args.output_dir)
    timing_figure(rows, args.output_dir)
    dependency_profile_figure(rows, args.output_dir)
    coordination_diagnostics_figure(rows, args.output_dir)
    tradeoff_figure(rows, args.output_dir)
    for path in sorted(args.output_dir.glob("*")):
        print(path.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
