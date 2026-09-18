"""Regenerate graphify-out/GRAPH_REPORT.md from persisted graph artifacts.

Run this with the interpreter recorded by graphify, for example in PowerShell:

    & (Get-Content graphify-out/.graphify_python -Raw).Trim() `
        tools/generate_graph_report.py

The graphify report API receives the repository name rather than its absolute
checkout path so the generated report is portable between clones.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from networkx.readwrite import json_graph

from graphify.analyze import god_nodes, suggest_questions, surprising_connections
from graphify.cluster import score_all
from graphify.report import generate


_UNMEASURED_TOKEN_LINE = "- Token cost: unmeasured (host-agent usage is unavailable)"
_REPOSITORY_LABEL = "TI_Parser"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_detection(root: Path, output_dir: Path) -> dict[str, Any]:
    sidecar = output_dir / ".graphify_detect.json"
    if sidecar.exists():
        return _read_json(sidecar)

    # The detect sidecar is normally produced by graphify and ignored by this
    # repository. Recompute it when a clean checkout has no local sidecar.
    from graphify.detect import detect

    detection = detect(root)
    return detection


def _load_analysis(graph, analysis_path: Path) -> tuple[dict[int, list[str]], dict[int, float], list[dict], list[dict], list[dict]]:
    if analysis_path.exists():
        analysis = _read_json(analysis_path)
        return (
            {int(k): v for k, v in analysis["communities"].items()},
            {int(k): v for k, v in analysis["cohesion"].items()},
            analysis["gods"],
            analysis["surprises"],
            analysis["questions"],
        )

    # graph.json persists each node's community. Sort both levels so the
    # fallback remains stable when the ignored analysis sidecar is absent.
    grouped: dict[int, list[str]] = {}
    for node_id, data in graph.nodes(data=True):
        if data.get("community") is not None:
            grouped.setdefault(int(data["community"]), []).append(str(node_id))
    communities = {cid: sorted(nodes) for cid, nodes in sorted(grouped.items())}
    cohesion = score_all(graph, communities)
    labels = {}
    gods = god_nodes(graph)
    surprises = surprising_connections(graph, communities)
    questions = suggest_questions(graph, communities, labels)
    return communities, cohesion, gods, surprises, questions


def generate_report(root: Path, graph_path: Path, output_path: Path) -> None:
    raw_graph = _read_json(graph_path)
    graph = json_graph.node_link_graph(raw_graph, edges="links")
    output_dir = graph_path.parent
    labels_path = output_dir / ".graphify_labels.json"
    labels = ({int(k): v for k, v in _read_json(labels_path).items()} if labels_path.exists() else {})
    analysis_path = output_dir / ".graphify_analysis.json"
    communities, cohesion, gods, surprises, questions = _load_analysis(graph, analysis_path)
    if not questions or not analysis_path.exists():
        questions = suggest_questions(graph, communities, labels)

    report = generate(
        graph,
        communities,
        cohesion,
        labels,
        gods,
        surprises,
        _load_detection(root, output_dir),
        {"input": 0, "output": 0},
        _REPOSITORY_LABEL,
        suggested_questions=questions,
    )
    # Host-agent semantic extraction cost is unavailable. Keep the existing
    # truthful marker instead of presenting graphify's zero default as a cost.
    report = report.replace("- Token cost: 0 input · 0 output", _UNMEASURED_TOKEN_LINE)
    output_path.write_text(report, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--graph", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    root = args.root.resolve()
    graph_path = (args.graph or root / "graphify-out" / "graph.json").resolve()
    output_path = (args.output or graph_path.parent / "GRAPH_REPORT.md").resolve()
    generate_report(root, graph_path, output_path)
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
