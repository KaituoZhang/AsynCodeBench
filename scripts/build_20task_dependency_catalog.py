#!/usr/bin/env python3
"""Build the 20-task dependency catalog and one SVG graph per task.

The release task index is the source of truth for task membership and for the
location of each task's frozen async-metrics annotation.  The generated
artifacts deliberately preserve those frozen labels; a short paper-facing
audit section calls out labels that deserve reconsideration under the newer
IF/API/STATE/INT definitions.
"""

from __future__ import annotations

import csv
import hashlib
import html
import json
import textwrap
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TASK_INDEX = ROOT / "manifests" / "release" / "v0.4" / "task_index.json"
CATALOG = ROOT / "docs" / "design" / "ASYNCCODEBENCH_20TASK_DEPENDENCY_CATALOG.md"
CATALOG_CSV = ROOT / "docs" / "design" / "asynccodebench_20task_dependency_catalog.csv"
FIGURE_DIR = ROOT / "docs" / "results" / "figures" / "task_dependencies"

TYPE_META = {
    "interface_dependency": {
        "code": "IF",
        "name": "Interface Dependency",
        "color": "#2563EB",
        "light": "#EFF6FF",
    },
    "shared_api_contract": {
        "code": "API",
        "name": "Shared API Contract",
        "color": "#7C3AED",
        "light": "#F5F3FF",
    },
    "shared_state_contract": {
        "code": "STATE",
        "name": "Shared State Contract",
        "color": "#D97706",
        "light": "#FFFBEB",
    },
    "integration_contract": {
        "code": "INT",
        "name": "Integration Contract",
        "color": "#059669",
        "light": "#ECFDF5",
    },
}

EXPECTED_TASK_COUNT = 20
EXPECTED_DEPENDENCY_COUNT = 55
EXPECTED_TYPE_COUNTS = {
    "interface_dependency": 22,
    "shared_api_contract": 17,
    "shared_state_contract": 7,
    "integration_contract": 9,
}

# These are review prompts, not silent relabelings of frozen benchmark data.
# They follow directly from the sharper distinctions in the paper definitions.
AUDIT_NOTES = {
    "simpy.events_to_resources.request_trigger_contract": (
        "Frozen as API. Because the contract explicitly covers triggered/processed "
        "state, callbacks, and process resumption across time, STATE may be the "
        "cleaner label under the lifecycle rule."
    ),
    "imapclient.lexer_to_parser.token_literal_contract": (
        "Frozen as API. The parser directly consumes lexer tokens and literal "
        "semantics; if no second layer must reproduce the same public behavior, "
        "this is more naturally IF."
    ),
    "imapclient.utility_to_client.command_normalization_contract": (
        "Frozen as STATE. The registered probes exercise one-shot date/UTF-7 "
        "normalization, not a read-write-invalidate-reread lifecycle; IF is more "
        "natural unless additional persistent-state evidence is documented."
    ),
}


def load_tasks() -> list[dict]:
    index = json.loads(TASK_INDEX.read_text(encoding="utf-8"))
    tasks = []
    type_counts: Counter[str] = Counter()
    for task in index["tasks"]:
        metrics_rel = task["artifacts"]["metrics"]["path"]
        metrics_path = ROOT / metrics_rel
        expected_sha256 = task["artifacts"]["metrics"]["sha256"]
        observed_sha256 = hashlib.sha256(metrics_path.read_bytes()).hexdigest()
        if observed_sha256 != expected_sha256:
            raise RuntimeError(
                f"frozen metrics hash mismatch for {task['task_id']}: "
                f"expected {expected_sha256}, observed {observed_sha256}"
            )
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        dependencies = metrics["dependency_points"]
        for dependency in dependencies:
            dependency_type = dependency["dependency_type"]
            if dependency_type not in TYPE_META:
                raise RuntimeError(
                    f"unknown dependency type {dependency_type!r} in {metrics_rel}"
                )
            type_counts[dependency_type] += 1
        tasks.append(
            {
                "task_id": task["task_id"],
                "name": task["task_id"].split(":", 1)[1],
                "metrics_rel": metrics_rel,
                "dependencies": dependencies,
            }
        )
    if len(tasks) != EXPECTED_TASK_COUNT:
        raise RuntimeError(f"expected {EXPECTED_TASK_COUNT} tasks, found {len(tasks)}")
    dependency_count = sum(len(task["dependencies"]) for task in tasks)
    if dependency_count != EXPECTED_DEPENDENCY_COUNT:
        raise RuntimeError(
            f"expected {EXPECTED_DEPENDENCY_COUNT} dependencies, found {dependency_count}"
        )
    if dict(type_counts) != EXPECTED_TYPE_COUNTS:
        raise RuntimeError(
            f"unexpected dependency type counts: {dict(type_counts)}"
        )
    return tasks


def humanize(value: str) -> str:
    words = value.replace("-", " ").replace("_", " ").split()
    rendered = []
    for word in words:
        lowered = word.lower()
        if lowered in {"api", "ir", "ptx", "tirx", "tls", "url", "xpath", "css"}:
            rendered.append(lowered.upper())
        elif lowered == "tvmscript":
            rendered.append("TVMScript")
        else:
            rendered.append(word.capitalize())
    return " ".join(rendered)


def svg_text(
    x: float,
    y: float,
    lines: list[str],
    *,
    size: int,
    color: str,
    weight: int = 400,
    anchor: str = "start",
    line_height: int | None = None,
) -> list[str]:
    escaped = [html.escape(line) for line in lines]
    line_height = line_height or int(size * 1.35)
    result = [
        f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" '
        f'font-weight="{weight}" text-anchor="{anchor}">'
    ]
    for index, line in enumerate(escaped):
        dy = 0 if index == 0 else line_height
        result.append(f'<tspan x="{x}" dy="{dy}">{line}</tspan>')
    result.append("</text>")
    return result


def wrap(value: str, width: int) -> list[str]:
    return textwrap.wrap(
        value,
        width=width,
        break_long_words=False,
        break_on_hyphens=False,
    ) or [""]


def collect_node_info(task: dict) -> dict[str, dict[str, set[str]]]:
    nodes: dict[str, dict[str, set[str]]] = {}
    for dependency in task["dependencies"]:
        for role in ("producer", "consumer"):
            name = dependency[f"{role}_subproblem"]
            node = nodes.setdefault(name, {"files": set(), "agents": set()})
            node["files"].update(dependency.get(f"{role}_files", []))
            agent = dependency.get(f"{role}_agent")
            if agent:
                node["agents"].add(agent)
    return nodes


def strongly_connected_components(
    nodes: list[str], edges: list[tuple[str, str]]
) -> list[list[str]]:
    adjacency = {node: [] for node in nodes}
    for source, target in edges:
        if target not in adjacency[source]:
            adjacency[source].append(target)
    index = 0
    indices: dict[str, int] = {}
    lowlinks: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    components: list[list[str]] = []

    def visit(node: str) -> None:
        nonlocal index
        indices[node] = index
        lowlinks[node] = index
        index += 1
        stack.append(node)
        on_stack.add(node)
        for target in adjacency[node]:
            if target not in indices:
                visit(target)
                lowlinks[node] = min(lowlinks[node], lowlinks[target])
            elif target in on_stack:
                lowlinks[node] = min(lowlinks[node], indices[target])
        if lowlinks[node] == indices[node]:
            component = []
            while True:
                member = stack.pop()
                on_stack.remove(member)
                component.append(member)
                if member == node:
                    break
            components.append(component)

    for node in nodes:
        if node not in indices:
            visit(node)
    return components


def layout_task_graph(task: dict) -> tuple[dict[str, tuple[float, float]], int]:
    nodes = list(collect_node_info(task))
    edges = [
        (dependency["producer_subproblem"], dependency["consumer_subproblem"])
        for dependency in task["dependencies"]
    ]
    components = strongly_connected_components(nodes, edges)
    component_of = {
        node: component_index
        for component_index, component in enumerate(components)
        for node in component
    }
    component_edges: dict[int, set[int]] = {
        index: set() for index in range(len(components))
    }
    indegree = {index: 0 for index in range(len(components))}
    for source, target in edges:
        source_component = component_of[source]
        target_component = component_of[target]
        if (
            source_component != target_component
            and target_component not in component_edges[source_component]
        ):
            component_edges[source_component].add(target_component)
            indegree[target_component] += 1
    component_rank = {index: 0 for index in range(len(components))}
    queue = [index for index, degree in indegree.items() if degree == 0]
    while queue:
        component = queue.pop(0)
        for target in component_edges[component]:
            component_rank[target] = max(
                component_rank[target], component_rank[component] + 1
            )
            indegree[target] -= 1
            if indegree[target] == 0:
                queue.append(target)
    node_rank = {node: component_rank[component_of[node]] for node in nodes}
    rank_count = max(node_rank.values(), default=0) + 1
    columns: dict[int, list[str]] = {rank: [] for rank in range(rank_count)}
    for node in nodes:
        columns[node_rank[node]].append(node)

    # A left-to-right barycentric pass keeps fan-in/fan-out shapes readable and
    # avoids the crossing that would otherwise occur in cachetools.
    order_index = {node: index for index, node in enumerate(nodes)}
    for rank in range(1, rank_count):
        previous = columns[rank - 1]
        previous_index = {node: index for index, node in enumerate(previous)}

        def barycenter(node: str) -> tuple[float, int]:
            predecessors = [
                source
                for source, target in edges
                if target == node and node_rank[source] == rank - 1
            ]
            if predecessors:
                value = sum(previous_index[source] for source in predecessors) / len(
                    predecessors
                )
            else:
                value = float(order_index[node])
            return value, order_index[node]

        columns[rank].sort(key=barycenter)

    if rank_count == 1:
        x_centers = [800.0]
    elif rank_count == 2:
        x_centers = [300.0, 1300.0]
    elif rank_count == 3:
        x_centers = [230.0, 800.0, 1370.0]
    else:
        span = 1380.0
        x_centers = [110.0 + span * rank / (rank_count - 1) for rank in range(rank_count)]

    positions: dict[str, tuple[float, float]] = {}
    for rank, column in columns.items():
        count = len(column)
        if count == 1:
            y_centers = [390.0]
        elif count == 2:
            y_centers = [255.0, 525.0]
        elif count == 3:
            y_centers = [195.0, 390.0, 585.0]
        else:
            y_centers = [170.0 + 440.0 * index / (count - 1) for index in range(count)]
        for node, y_center in zip(column, y_centers):
            positions[node] = (x_centers[rank], y_center)
    return positions, rank_count


def shortened_path(path: str, width: int = 46) -> str:
    if len(path) <= width:
        return path
    return "…" + path[-(width - 1) :]


def node_file_lines(files: set[str]) -> list[str]:
    ordered = sorted(files)
    if not ordered:
        return ["No file mapping recorded"]
    if len(ordered) <= 2:
        return [shortened_path(path) for path in ordered]
    return [shortened_path(ordered[0]), f"+ {len(ordered) - 1} additional files"]


def build_task_svg(task: dict) -> str:
    width = 1600
    node_info = collect_node_info(task)
    positions, rank_count = layout_task_graph(task)
    node_width = 326 if rank_count >= 3 else 360
    node_height = 128
    graph_bottom = 680
    edge_rows = []
    row_y = 742
    for index, dependency in enumerate(task["dependencies"], 1):
        summary_lines = wrap(dependency["contract_summary"], 128)
        row_height = 66 + max(0, len(summary_lines) - 1) * 20
        edge_rows.append((index, dependency, row_y, row_height, summary_lines))
        row_y += row_height
    height = row_y + 42

    output = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" '
        f'aria-labelledby="title desc">',
        "<title id=\"title\">"
        + html.escape(f"{task['name']} dependency graph")
        + "</title>",
        "<desc id=\"desc\">Unique artifact nodes connected by all frozen dependency points.</desc>",
        "<defs>",
    ]
    for dependency_type, meta in TYPE_META.items():
        output.extend(
            [
                f'<marker id="arrow-{meta["code"].lower()}" markerWidth="12" '
                'markerHeight="12" refX="10" refY="6" orient="auto" '
                'markerUnits="strokeWidth">',
                f'<path d="M 0 0 L 12 6 L 0 12 z" fill="{meta["color"]}"/>',
                "</marker>",
            ]
        )
    output.extend(
        [
            "</defs>",
            f'<rect x="0" y="0" width="{width}" height="{height}" fill="#FFFFFF"/>',
        ]
    )
    output.extend(
        svg_text(
            62,
            48,
            [f"{task['name']} — dependency graph"],
            size=28,
            color="#101828",
            weight=700,
        )
    )
    output.extend(
        svg_text(
            62,
            77,
            [
                f"{len(node_info)} unique subproblem/artifact nodes · "
                f"{len(task['dependencies'])} directed dependency points"
            ],
            size=15,
            color="#667085",
        )
    )
    legend_x = 735
    for meta in TYPE_META.values():
        pill_width = 70 if meta["code"] != "STATE" else 92
        output.append(
            f'<rect x="{legend_x}" y="42" width="{pill_width}" height="29" rx="14.5" '
            f'fill="{meta["light"]}" stroke="{meta["color"]}"/>'
        )
        output.extend(
            svg_text(
                legend_x + pill_width / 2,
                62,
                [meta["code"]],
                size=13,
                color=meta["color"],
                weight=700,
                anchor="middle",
            )
        )
        legend_x += pill_width + 16

    output.append(
        f'<rect x="42" y="104" width="1516" height="{graph_bottom - 104}" '
        'rx="22" fill="#FCFCFD" stroke="#EAECF0"/>'
    )

    pair_members: dict[tuple[str, str], list[int]] = {}
    outgoing: dict[str, list[int]] = {node: [] for node in node_info}
    incoming: dict[str, list[int]] = {node: [] for node in node_info}
    for index, dependency in enumerate(task["dependencies"], 1):
        pair = (
            dependency["producer_subproblem"],
            dependency["consumer_subproblem"],
        )
        pair_members.setdefault(pair, []).append(index)
        outgoing[pair[0]].append(index)
        incoming[pair[1]].append(index)

    dependency_by_index = {
        index: dependency
        for index, dependency in enumerate(task["dependencies"], 1)
    }
    for node, edge_indices in outgoing.items():
        edge_indices.sort(
            key=lambda edge_index: (
                positions[
                    dependency_by_index[edge_index]["consumer_subproblem"]
                ][1],
                edge_index,
            )
        )
    for node, edge_indices in incoming.items():
        edge_indices.sort(
            key=lambda edge_index: (
                positions[
                    dependency_by_index[edge_index]["producer_subproblem"]
                ][1],
                edge_index,
            )
        )

    def port_offsets(edge_indices: list[int]) -> dict[int, float]:
        count = len(edge_indices)
        if count <= 1:
            return {edge_index: 0.0 for edge_index in edge_indices}
        return {
            edge_index: -45.0 + 90.0 * position / (count - 1)
            for position, edge_index in enumerate(edge_indices)
        }

    outgoing_ports = {
        node: port_offsets(edge_indices) for node, edge_indices in outgoing.items()
    }
    incoming_ports = {
        node: port_offsets(edge_indices) for node, edge_indices in incoming.items()
    }

    edge_paths = []
    edge_labels = []
    for index, dependency in enumerate(task["dependencies"], 1):
        meta = TYPE_META[dependency["dependency_type"]]
        source = dependency["producer_subproblem"]
        target = dependency["consumer_subproblem"]
        source_x, source_y = positions[source]
        target_x, target_y = positions[target]
        pair = (source, target)
        pair_index = pair_members[pair].index(index)
        source_rank_x = source_x
        target_rank_x = target_x
        stroke = (
            f'stroke="{meta["color"]}" stroke-width="3" fill="none" '
            f'marker-end="url(#arrow-{meta["code"].lower()})"'
        )
        if source_rank_x < target_rank_x:
            x1 = source_x + node_width / 2
            x2 = target_x - node_width / 2 - 12
            y1 = source_y + outgoing_ports[source][index]
            y2 = target_y + incoming_ports[target][index]
            rank_gap = len(
                {
                    x
                    for x, _ in positions.values()
                    if source_x < x <= target_x
                }
            )
            if rank_gap <= 1:
                control = max(80, (x2 - x1) * 0.42)
                path = (
                    f'M {x1} {y1} C {x1 + control} {y1}, '
                    f'{x2 - control} {y2}, {x2} {y2}'
                )
                label_x = (x1 + x2) / 2
                label_y = (y1 + y2) / 2
            else:
                route_y = 126 + pair_index * 38
                route_left = x1 + 105
                route_right = x2 - 105
                path = (
                    f'M {x1} {y1} C {x1 + 55} {y1}, {route_left - 30} {route_y}, '
                    f'{route_left} {route_y} L {route_right} {route_y} '
                    f'C {route_right + 30} {route_y}, {x2 - 55} {y2}, {x2} {y2}'
                )
                label_x = (route_left + route_right) / 2
                label_y = route_y
        else:
            # Same-column edges occur for mutually dependent layers (currently
            # marshmallow).  Route opposite directions on opposite sides.
            downward = source_y < target_y
            side = 1 if downward else -1
            x1 = source_x + side * node_width * 0.28
            x2 = target_x + side * node_width * 0.28
            y1 = source_y + (node_height / 2 if downward else -node_height / 2)
            y2 = target_y + (-node_height / 2 if downward else node_height / 2)
            outer_x = source_x + side * (node_width / 2 + 62)
            path = (
                f'M {x1} {y1} C {outer_x} {y1}, {outer_x} {y2}, {x2} {y2}'
            )
            label_x = outer_x
            label_y = (y1 + y2) / 2
        edge_paths.append(
            f'<path class="dependency-edge" data-edge="D{index}" '
            f'data-source="{html.escape(source)}" data-target="{html.escape(target)}" '
            f'd="{path}" {stroke}/>'
        )
        pill_text = f"D{index} · {meta['code']}"
        pill_width = 104 if meta["code"] != "STATE" else 120
        edge_labels.extend(
            [
                f'<rect class="edge-label" data-edge="D{index}" '
                f'x="{label_x - pill_width / 2}" y="{label_y - 16}" '
                f'width="{pill_width}" height="32" rx="16" fill="{meta["light"]}" '
                f'stroke="{meta["color"]}" stroke-width="1.5"/>',
                *svg_text(
                    label_x,
                    label_y + 5,
                    [pill_text],
                    size=13,
                    color=meta["color"],
                    weight=700,
                    anchor="middle",
                ),
            ]
        )

    output.extend(edge_paths)

    for node, (center_x, center_y) in positions.items():
        info = node_info[node]
        node_x = center_x - node_width / 2
        node_y = center_y - node_height / 2
        title_lines = wrap(humanize(node), 28 if rank_count >= 3 else 32)[:2]
        files = node_file_lines(info["files"])
        owner = ", ".join(sorted(info["agents"])) or "not recorded"
        output.append(
            f'<rect class="graph-node" data-node="{html.escape(node)}" '
            f'x="{node_x}" y="{node_y}" width="{node_width}" '
            f'height="{node_height}" rx="15" fill="#FFFFFF" stroke="#667085" '
            'stroke-width="1.8"/>'
        )
        output.extend(
            svg_text(
                node_x + 18,
                node_y + 28,
                title_lines,
                size=17,
                color="#101828",
                weight=700,
                line_height=19,
            )
        )
        output.extend(
            svg_text(
                node_x + 18,
                node_y + 70,
                files,
                size=12,
                color="#475467",
                line_height=16,
            )
        )
        output.extend(
            svg_text(
                node_x + 18,
                node_y + 116,
                [f"owner: {owner}"],
                size=11,
                color="#98A2B3",
            )
        )

    output.extend(edge_labels)
    output.extend(
        svg_text(
            62,
            716,
            ["Dependency contracts"],
            size=20,
            color="#101828",
            weight=700,
        )
    )
    for index, dependency, item_y, row_height, summary_lines in edge_rows:
        meta = TYPE_META[dependency["dependency_type"]]
        output.append(
            f'<line x1="62" y1="{item_y - 17}" x2="1538" y2="{item_y - 17}" '
            'stroke="#EAECF0"/>'
        )
        output.append(
            f'<rect x="62" y="{item_y}" width="92" height="30" rx="15" '
            f'fill="{meta["light"]}" stroke="{meta["color"]}"/>'
        )
        output.extend(
            svg_text(
                108,
                item_y + 20,
                [f"D{index} · {meta['code']}"],
                size=12,
                color=meta["color"],
                weight=700,
                anchor="middle",
            )
        )
        output.extend(
            svg_text(
                174,
                item_y + 16,
                [dependency["dependency_id"]],
                size=13,
                color="#475467",
                weight=600,
            )
        )
        output.extend(
            svg_text(
                174,
                item_y + 42,
                summary_lines,
                size=14,
                color="#344054",
                line_height=20,
            )
        )
    output.extend(
        svg_text(
            width - 48,
            height - 20,
            ["Source: AsynCodeBench v0.4 frozen async-metrics annotations"],
            size=12,
            color="#98A2B3",
            anchor="end",
        )
    )
    output.append("</svg>")
    return "\n".join(output) + "\n"


def probe_markdown(title: str, probes: list[str]) -> list[str]:
    lines = [f"**{title} ({len(probes)})**", ""]
    if probes:
        lines.extend(f"- `{probe}`" for probe in probes)
    else:
        lines.append("- None registered.")
    lines.append("")
    return lines


def build_markdown(tasks: list[dict]) -> str:
    counts = Counter(
        dependency["dependency_type"]
        for task in tasks
        for dependency in task["dependencies"]
    )
    lines = [
        "# AsynCodeBench 20-task dependency catalog",
        "",
        "This catalog enumerates the 55 frozen dependency points in the v0.4 "
        "20-task release. Direction is always `producer → consumer`; labels are "
        "preserved from each task's canonical async-metrics annotation.",
        "",
        "Each SVG is a node-based dependency graph: a canonical subproblem/artifact "
        "appears once, its owned file set is shown inside the node, and all contracts "
        "reuse that node. This makes fan-out, fan-in, chains, parallel contracts, and "
        "cycles visible without duplicating producer or consumer boxes.",
        "",
        "## Taxonomy and totals",
        "",
        "| Code | Frozen dependency type | Count |",
        "| --- | --- | ---: |",
    ]
    for dependency_type, meta in TYPE_META.items():
        lines.append(
            f"| {meta['code']} | {meta['name']} (`{dependency_type}`) | "
            f"{counts[dependency_type]} |"
        )
    lines.extend(
        [
            "| **Total** |  | **55** |",
            "",
            "Interpretation follows the paper distinction: IF is direct interface "
            "consumption; API is preservation of the same externally visible behavior "
            "across layers; STATE requires agreement about state representation or "
            "lifecycle across time; INT requires successful composition at an "
            "end-to-end boundary.",
            "",
            "## Task overview",
            "",
            "| # | Task | Edges | IF | API | STATE | INT |",
            "| ---: | --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for index, task in enumerate(tasks, 1):
        task_counts = Counter(
            dependency["dependency_type"] for dependency in task["dependencies"]
        )
        lines.append(
            f"| {index} | [{task['name']}](#{task['name'].replace('_', '-')}) | "
            f"{len(task['dependencies'])} | "
            f"{task_counts['interface_dependency']} | "
            f"{task_counts['shared_api_contract']} | "
            f"{task_counts['shared_state_contract']} | "
            f"{task_counts['integration_contract']} |"
        )

    lines.extend(
        [
            "",
            "## Paper-definition audit flags",
            "",
            "The release labels below remain unchanged. Before treating the four "
            "classes as a paper taxonomy, the following three edges deserve explicit "
            "adjudication against the sharper IF/API/STATE decision rules:",
            "",
        ]
    )
    for dependency_id, note in AUDIT_NOTES.items():
        lines.append(f"- `{dependency_id}` — {note}")
    lines.extend(
        [
            "",
            "Changing any frozen label requires rebuilding the affected metrics "
            "artifact and release hashes; this generated catalog does not do that.",
            "",
            "## Per-task dependencies",
            "",
        ]
    )

    for task_index, task in enumerate(tasks, 1):
        figure_rel = f"../results/figures/task_dependencies/{task['name']}.svg"
        metrics_rel = "../../" + task["metrics_rel"]
        lines.extend(
            [
                f"### {task_index}. {task['name']}",
                "",
                f"![{task['name']} dependency graph]({figure_rel})",
                "",
                f"Canonical annotation: [`{task['metrics_rel']}`]({metrics_rel})",
                "",
            ]
        )
        for dependency_index, dependency in enumerate(task["dependencies"], 1):
            meta = TYPE_META[dependency["dependency_type"]]
            producer_agent = dependency.get("producer_agent", "not recorded")
            consumer_agent = dependency.get("consumer_agent", "not recorded")
            lines.extend(
                [
                    f"#### D{dependency_index}. {dependency['dependency_id']} [{meta['code']}]",
                    "",
                    f"- Direction: `{dependency['producer_subproblem']}` → "
                    f"`{dependency['consumer_subproblem']}`",
                    f"- Ownership: `{producer_agent}` → `{consumer_agent}`",
                    f"- Contract: {dependency['contract_summary']}",
                    f"- Resolution: {dependency.get('resolution_criteria') or 'Not separately recorded.'}",
                ]
            )
            if dependency["dependency_id"] in AUDIT_NOTES:
                lines.append(f"- Audit flag: {AUDIT_NOTES[dependency['dependency_id']]}")
            lines.extend(
                [
                    "",
                    "<details>",
                    "<summary>Exact checker mapping</summary>",
                    "",
                ]
            )
            lines.extend(
                probe_markdown("Upstream", dependency.get("upstream_probe_tests", []))
            )
            lines.extend(
                probe_markdown("Downstream", dependency.get("downstream_probe_tests", []))
            )
            lines.extend(
                probe_markdown("Integrated", dependency.get("integrated_probe_tests", []))
            )
            lines.extend(["</details>", ""])
    lines.extend(
        [
            "## Rebuild",
            "",
            "```bash",
            "cd /home/kzhang42/AsyncCodeBench",
            "python scripts/build_20task_dependency_catalog.py",
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def write_csv(tasks: list[dict]) -> None:
    fields = [
        "task",
        "dependency_index",
        "dependency_id",
        "type_code",
        "dependency_type",
        "producer_subproblem",
        "consumer_subproblem",
        "producer_agent",
        "consumer_agent",
        "contract_summary",
        "upstream_probe_count",
        "downstream_probe_count",
        "integrated_probe_count",
        "classification_audit_note",
        "source_metrics",
    ]
    with CATALOG_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for task in tasks:
            for index, dependency in enumerate(task["dependencies"], 1):
                writer.writerow(
                    {
                        "task": task["name"],
                        "dependency_index": index,
                        "dependency_id": dependency["dependency_id"],
                        "type_code": TYPE_META[dependency["dependency_type"]]["code"],
                        "dependency_type": dependency["dependency_type"],
                        "producer_subproblem": dependency["producer_subproblem"],
                        "consumer_subproblem": dependency["consumer_subproblem"],
                        "producer_agent": dependency.get("producer_agent", ""),
                        "consumer_agent": dependency.get("consumer_agent", ""),
                        "contract_summary": dependency["contract_summary"],
                        "upstream_probe_count": len(
                            dependency.get("upstream_probe_tests", [])
                        ),
                        "downstream_probe_count": len(
                            dependency.get("downstream_probe_tests", [])
                        ),
                        "integrated_probe_count": len(
                            dependency.get("integrated_probe_tests", [])
                        ),
                        "classification_audit_note": AUDIT_NOTES.get(
                            dependency["dependency_id"], ""
                        ),
                        "source_metrics": task["metrics_rel"],
                    }
                )


def main() -> None:
    tasks = load_tasks()
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    for task in tasks:
        (FIGURE_DIR / f"{task['name']}.svg").write_text(
            build_task_svg(task), encoding="utf-8"
        )
    CATALOG.write_text(build_markdown(tasks), encoding="utf-8")
    write_csv(tasks)
    print(
        f"wrote {len(tasks)} task graphs and {EXPECTED_DEPENDENCY_COUNT} dependency rows"
    )


if __name__ == "__main__":
    main()
