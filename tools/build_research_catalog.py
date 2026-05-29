#!/usr/bin/env python3
"""Build a normalized Terra Invicta research dependency catalog.

Global techs and faction projects are template data, so they can be normalized
once and reused across save-specific planning views. Save-derived state should
only decide which nodes are completed, available, or blocked.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import ti_save_parser as ti


SCHEMA_VERSION = 1
DEFAULT_JSON_OUTPUT = Path("data/research_catalog.json")
DEFAULT_MARKDOWN_OUTPUT = Path("docs/research_catalog.md")
RESEARCH_TEMPLATE_FILES = {
    "tech": "TITechTemplate.json",
    "project": "TIProjectTemplate.json",
}
LOCALIZATION_FILES = {
    "tech": "TITechTemplate",
    "project": "TIProjectTemplate",
}
LOCALIZATION_FIELDS = ("displayName",)


def compact_number(value: Any, digits: int = 6) -> Any:
    if not isinstance(value, float):
        return value
    rounded = round(value, digits)
    if rounded == 0:
        return 0
    if rounded.is_integer():
        return int(rounded)
    return rounded


def clean_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): clean_value(item) for key, item in value.items() if item is not None}
    if isinstance(value, list):
        return [clean_value(item) for item in value if item is not None]
    return compact_number(value)


def nonempty_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def read_localization_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    with path.open("r", encoding="utf-8-sig") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    return values


def load_research_localizations(
    templates_dir: Path,
    languages: list[str],
) -> dict[str, dict[str, dict[str, dict[str, str]]]]:
    root = templates_dir.parent / "Localization"
    localizations: dict[str, dict[str, dict[str, dict[str, str]]]] = {"tech": {}, "project": {}}
    for kind, prefix in LOCALIZATION_FILES.items():
        for language in languages:
            loc_file = root / language / f"{prefix}.{language}"
            loc_values = read_localization_file(loc_file)
            entries: dict[str, dict[str, str]] = {}
            for key, value in loc_values.items():
                parts = key.split(".")
                if len(parts) != 3 or parts[0] != prefix or parts[1] not in LOCALIZATION_FIELDS:
                    continue
                _, field, data_name = parts
                entries.setdefault(data_name, {})[field] = value
            localizations[kind][language] = entries
    return localizations


def source_fingerprint(path: Path) -> dict[str, Any]:
    fingerprint = ti.file_fingerprint(path)
    if not fingerprint:
        return {"file": path.name}
    return {
        "file": path.name,
        "size": fingerprint["size"],
        "mtime_ns": fingerprint["mtime_ns"],
    }


def infer_node_kind(data_name: str) -> str:
    return "project" if data_name.startswith("Project_") else "tech"


def node_requirement(data_name: str) -> dict[str, str]:
    return {"node": data_name, "kind": infer_node_kind(data_name)}


def normalize_string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if item]
    if isinstance(value, str) and value:
        return [value]
    return []


def normalize_requirements(template: dict[str, Any]) -> dict[str, Any]:
    """Convert raw template gates into an explicit boolean requirement tree.

    `prereqs` are AND requirements. Terra Invicta's `altPrereq0` is an OR
    alternative for the first prereq slot, so `[A, B] + alt C` means
    `(A OR C) AND B`, not `A AND B AND C`.
    """

    groups: list[dict[str, Any]] = []
    prereqs = normalize_string_list(template.get("prereqs"))
    alt_prereq = template.get("altPrereq0")
    if prereqs:
        first_group = [node_requirement(prereqs[0])]
        if alt_prereq:
            first_group.append(node_requirement(str(alt_prereq)))
        groups.append({"any": first_group} if len(first_group) > 1 else first_group[0])
        groups.extend(node_requirement(name) for name in prereqs[1:])
    elif alt_prereq:
        groups.append(node_requirement(str(alt_prereq)))

    objectives = [
        name
        for name in (template.get("requiredObjectiveName"), template.get("altRequiredObjectiveName"))
        if name
    ]
    if objectives:
        objective_group = [{"objective": str(name)} for name in objectives]
        groups.append({"any": objective_group} if len(objective_group) > 1 else objective_group[0])

    required_milestone = template.get("requiredMilestone")
    if required_milestone:
        groups.append({"milestone": str(required_milestone)})

    factions = normalize_string_list(template.get("factionPrereq"))
    if factions:
        groups.append({"factionAny": factions})

    required_nation = template.get("requiresNation")
    if required_nation:
        groups.append({"nation": str(required_nation)})

    return {"all": groups}


def requirement_nodes(requirement: dict[str, Any]) -> list[str]:
    nodes: set[str] = set()

    def visit(item: Any) -> None:
        if not isinstance(item, dict):
            return
        node = item.get("node")
        if isinstance(node, str):
            nodes.add(node)
        for child in nonempty_list(item.get("all")) + nonempty_list(item.get("any")):
            visit(child)

    visit(requirement)
    return sorted(nodes)


def context_values(context: dict[str, Any] | None, *keys: str) -> set[str]:
    if not context:
        return set()
    values: set[str] = set()
    for key in keys:
        raw = context.get(key)
        if isinstance(raw, str) and raw:
            values.add(raw)
        elif isinstance(raw, Iterable) and not isinstance(raw, (str, bytes, dict)):
            values.update(str(item) for item in raw if item)
    return values


def requirement_satisfied(
    requirement: dict[str, Any],
    completed_nodes: Iterable[str],
    context: dict[str, Any] | None = None,
) -> bool:
    completed = set(completed_nodes)

    def satisfied(item: Any) -> bool:
        if not isinstance(item, dict):
            return True
        if "all" in item:
            return all(satisfied(child) for child in nonempty_list(item.get("all")))
        if "any" in item:
            return any(satisfied(child) for child in nonempty_list(item.get("any")))
        if "node" in item:
            return str(item["node"]) in completed
        if "objective" in item:
            objectives = context_values(context, "objectives", "completedObjectives")
            return str(item["objective"]) in objectives
        if "milestone" in item:
            milestones = context_values(context, "milestones", "completedMilestones")
            return str(item["milestone"]) in milestones
        if "factionAny" in item:
            factions = set(normalize_string_list(item.get("factionAny")))
            current = context_values(context, "faction", "factionTemplate", "template")
            return bool(factions & current)
        if "nation" in item:
            nations = context_values(context, "nations", "availableNations", "controlledNations")
            return str(item["nation"]) in nations
        return False

    return satisfied(requirement)


def unmet_requirements(
    requirement: dict[str, Any],
    completed_nodes: Iterable[str],
    context: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    if requirement_satisfied(requirement, completed_nodes, context):
        return []

    def collect(item: Any) -> list[dict[str, Any]]:
        if not isinstance(item, dict) or requirement_satisfied(item, completed_nodes, context):
            return []
        if "all" in item:
            missing: list[dict[str, Any]] = []
            for child in nonempty_list(item.get("all")):
                missing.extend(collect(child))
            return missing
        if "any" in item:
            return [{"any": [clean_value(child) for child in nonempty_list(item.get("any"))]}]
        return [clean_value(item)]

    return collect(requirement)


def localized_fields(
    localizations: dict[str, dict[str, dict[str, dict[str, str]]]],
    kind: str,
    data_name: str,
    field: str,
) -> dict[str, str]:
    values: dict[str, str] = {}
    for language, entries in localizations.get(kind, {}).items():
        value = entries.get(data_name, {}).get(field)
        if value:
            values[language] = value
    return values


def normalize_research_node(
    template: dict[str, Any],
    kind: str,
    localizations: dict[str, dict[str, dict[str, dict[str, str]]]],
) -> dict[str, Any]:
    data_name = str(template.get("dataName"))
    requirements = normalize_requirements(template)
    node = {
        "dataName": data_name,
        "kind": kind,
        "friendlyName": template.get("friendlyName"),
        "displayName": localized_fields(localizations, kind, data_name, "displayName"),
        "category": template.get("techCategory"),
        "ai": {
            "techRole": template.get("AI_techRole"),
            "projectRole": template.get("AI_projectRole"),
            "critical": bool(template.get("AI_criticalTech")),
        },
        "researchCost": compact_number(ti.as_float(template.get("researchCost"), 0.0)),
        "requirements": requirements,
        "prerequisiteNodes": requirement_nodes(requirements),
        "effects": normalize_string_list(template.get("effects")),
    }
    if kind == "tech":
        node["flags"] = {
            "endGameTech": bool(template.get("endGameTech")),
        }
    else:
        node["flags"] = {
            "oneTimeGlobally": bool(template.get("oneTimeGlobally")),
            "repeatable": bool(template.get("repeatable")),
            "disable": bool(template.get("disable")),
        }
        node["availability"] = clean_value(
            {
                "factionAvailableChance": template.get("factionAvailableChance"),
                "initialUnlockChance": template.get("initialUnlockChance"),
                "deltaUnlockChance": template.get("deltaUnlockChance"),
                "maxUnlockChance": template.get("maxUnlockChance"),
                "factionAlways": template.get("factionAlways"),
            }
        )
        node["grants"] = clean_value(
            {
                "org": template.get("orgGranted"),
                "resources": template.get("resourcesGranted") if isinstance(template.get("resourcesGranted"), list) else [],
            }
        )
    return clean_value(node)


def node_sort_key(node: dict[str, Any]) -> tuple[Any, ...]:
    return (
        0 if node.get("kind") == "tech" else 1,
        node.get("category") or "",
        node.get("researchCost") if isinstance(node.get("researchCost"), (int, float)) else 0,
        node.get("friendlyName") or node.get("dataName"),
    )


def build_graph_links(nodes: list[dict[str, Any]]) -> tuple[list[dict[str, str]], dict[str, list[str]], list[str]]:
    known = {str(node["dataName"]) for node in nodes}
    edges: list[dict[str, str]] = []
    children: dict[str, list[str]] = {}
    unknown: set[str] = set()
    for node in nodes:
        target = str(node["dataName"])
        for prereq in node.get("prerequisiteNodes", []):
            if prereq not in known:
                unknown.add(str(prereq))
            edge = {"from": str(prereq), "to": target}
            edges.append(edge)
            children.setdefault(str(prereq), []).append(target)
    for values in children.values():
        values.sort()
    edges.sort(key=lambda item: (item["from"], item["to"]))
    return edges, dict(sorted(children.items())), sorted(unknown)


def build_catalog(templates_dir: Path, languages: list[str]) -> dict[str, Any]:
    localizations = load_research_localizations(templates_dir, languages)
    nodes: list[dict[str, Any]] = []
    for kind, filename in RESEARCH_TEMPLATE_FILES.items():
        templates = ti.load_named_templates(templates_dir, filename)
        for template in templates.values():
            if kind == "project" and template.get("disable"):
                continue
            nodes.append(normalize_research_node(template, kind, localizations))
    nodes.sort(key=node_sort_key)
    edges, children, unknown_prerequisites = build_graph_links(nodes)
    by_data_name = {str(node["dataName"]): index for index, node in enumerate(nodes)}
    counts_by_kind = {
        "tech": sum(1 for node in nodes if node.get("kind") == "tech"),
        "project": sum(1 for node in nodes if node.get("kind") == "project"),
    }
    counts_by_category: dict[str, int] = {}
    for node in nodes:
        category = str(node.get("category") or "None")
        counts_by_category[category] = counts_by_category.get(category, 0) + 1
    return {
        "schemaVersion": SCHEMA_VERSION,
        "source": {
            "templateRoot": "TerraInvicta_Data/StreamingAssets/Templates",
            "techTemplate": source_fingerprint(templates_dir / RESEARCH_TEMPLATE_FILES["tech"]),
            "projectTemplate": source_fingerprint(templates_dir / RESEARCH_TEMPLATE_FILES["project"]),
            "localizationLanguages": languages,
        },
        "notes": [
            "Nodes are static template data; save-specific completion and availability should be evaluated separately.",
            "`requirements` is a boolean tree. `all` means every child is required; `any` means at least one child is required.",
            "`prerequisiteNodes`, `edges`, and `childrenByPrereq` are graph indexes derived from node requirements only.",
            "Objective, milestone, faction, and nation requirements are state gates, not research graph edges.",
        ],
        "counts": {
            "total": len(nodes),
            "byKind": counts_by_kind,
            "byCategory": dict(sorted(counts_by_category.items())),
            "edges": len(edges),
            "unknownPrerequisites": len(unknown_prerequisites),
        },
        "nodes": nodes,
        "byDataName": by_data_name,
        "edges": edges,
        "childrenByPrereq": children,
        "unknownPrerequisites": unknown_prerequisites,
    }


def requirement_text(requirement: Any) -> str:
    if not isinstance(requirement, dict):
        return ""
    if "all" in requirement:
        return " + ".join(filter(None, (requirement_text(item) for item in nonempty_list(requirement.get("all")))))
    if "any" in requirement:
        text = " OR ".join(filter(None, (requirement_text(item) for item in nonempty_list(requirement.get("any")))))
        return f"({text})" if text else ""
    if "node" in requirement:
        return str(requirement["node"])
    if "objective" in requirement:
        return f"objective:{requirement['objective']}"
    if "milestone" in requirement:
        return f"milestone:{requirement['milestone']}"
    if "factionAny" in requirement:
        return "faction:" + "/".join(normalize_string_list(requirement.get("factionAny")))
    if "nation" in requirement:
        return f"nation:{requirement['nation']}"
    return ""


def markdown_safe(value: Any) -> str:
    return str(value if value is not None else "").replace("|", "/").replace("\n", " ")


def markdown_table(title: str, nodes: list[dict[str, Any]], language: str) -> list[str]:
    lines = [
        f"## {title}",
        "",
        "| Name | dataName | Kind | Category | Cost | Requirements |",
        "| --- | --- | --- | --- | ---: | --- |",
    ]
    for node in nodes:
        display = node.get("displayName", {}).get(language) or node.get("friendlyName") or node["dataName"]
        lines.append(
            "| "
            + " | ".join(
                [
                    markdown_safe(display),
                    markdown_safe(node["dataName"]),
                    markdown_safe(node["kind"]),
                    markdown_safe(node.get("category")),
                    markdown_safe(node.get("researchCost")),
                    markdown_safe(requirement_text(node.get("requirements"))),
                ]
            )
            + " |"
        )
    lines.append("")
    return lines


def build_markdown(catalog: dict[str, Any], language: str) -> str:
    nodes = catalog["nodes"]
    techs = [node for node in nodes if node.get("kind") == "tech"]
    projects = [node for node in nodes if node.get("kind") == "project"]
    counts = catalog["counts"]
    lines = [
        "# Terra Invicta Research Catalog",
        "",
        f"Generated from `{catalog['source']['templateRoot']}`.",
        "",
        "This file is generated. Rebuild it with:",
        "",
        "```powershell",
        "python .\\tools\\build_research_catalog.py",
        "```",
        "",
        "Important interpretation notes:",
        "",
        "- `requirements` in the JSON is the canonical source for prerequisite logic.",
        "- `prerequisiteNodes` and `edges` are derived from research-node leaves only and intentionally omit objective, milestone, faction, and nation gates.",
        "- `altPrereq0` is represented as an OR alternative for the first `prereqs` entry.",
        "",
        f"Node count: `{counts['total']}` total, `{counts['byKind']['tech']}` global techs, `{counts['byKind']['project']}` projects.",
        f"Graph edge count: `{counts['edges']}`.",
        "",
    ]
    lines.extend(markdown_table("Global Techs", techs, language))
    lines.extend(markdown_table("Faction Projects", projects, language))
    return "\n".join(lines).rstrip() + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a normalized Terra Invicta research dependency catalog.")
    parser.add_argument("--templates-dir", help="Path to TerraInvicta_Data\\StreamingAssets\\Templates.")
    parser.add_argument("--languages", default="kor,en", help="Comma-separated localization languages to include.")
    parser.add_argument("--json-output", default=str(DEFAULT_JSON_OUTPUT), help="Generated JSON output path.")
    parser.add_argument("--markdown-output", default=str(DEFAULT_MARKDOWN_OUTPUT), help="Generated Markdown output path.")
    parser.add_argument("--markdown-language", default="kor", help="Localization language used for Markdown names.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    templates_dir = ti.resolve_templates_dir(args.templates_dir)
    if templates_dir is None:
        raise SystemExit("Templates directory not found. Pass --templates-dir.")
    languages = [item.strip() for item in args.languages.split(",") if item.strip()]
    catalog = build_catalog(templates_dir, languages)

    json_output = Path(args.json_output)
    json_output.parent.mkdir(parents=True, exist_ok=True)
    json_output.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")

    markdown_output = Path(args.markdown_output)
    markdown_output.parent.mkdir(parents=True, exist_ok=True)
    markdown_output.write_text(build_markdown(catalog, args.markdown_language), encoding="utf-8")

    ti.print_json(
        {
            "nodes": catalog["counts"]["total"],
            "techs": catalog["counts"]["byKind"]["tech"],
            "projects": catalog["counts"]["byKind"]["project"],
            "edges": catalog["counts"]["edges"],
            "unknownPrerequisites": catalog["counts"]["unknownPrerequisites"],
            "json": str(json_output),
            "markdown": str(markdown_output),
            "templatesDir": str(templates_dir),
        },
        compact=False,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
