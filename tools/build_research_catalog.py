#!/usr/bin/env python3
"""Build a normalized Terra Invicta research dependency catalog.

Global techs and faction projects are template data, so they can be normalized
once and reused across save-specific planning views. Save-derived state should
only decide which nodes are completed, available, or blocked.
"""

from __future__ import annotations

import argparse
from collections.abc import Iterable
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any

import ti_save_parser as ti
from catalog_utils import (
    compact_number,
    parse_languages,
    read_localization_file,
    write_json_output,
    write_text_output,
)
from ti_parser_core import SCENARIO_DLC_TEMPLATE_HINTS, game_root_from_templates_dir


SCHEMA_VERSION = 2
GENERATOR_NAME = "build_research_catalog"
GENERATOR_VERSION = "2"
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
DEFAULT_SUPPORTED_SCENARIOS = (
    "2026Scenario",
    "2030Scenario",
    "2070Scenario",
    "FullScenario",
    "ModernScenario",
    "SkirmishModeScenario",
    "SkirmishScenario",
    "TestScenario",
)
COMMON_RUNTIME_FIELDS = (
    "dataName",
    "friendlyName",
    "_displayName",
    "techCategory",
    "researchCost",
    "prereqs",
    "altPrereq0",
    "effects",
    "factionPrereq",
    "requiredMilestone",
    "requiredObjectiveName",
    "altRequiredObjectiveName",
    "requiresNation",
    "AI_techRole",
    "AI_projectRole",
    "AI_criticalTech",
)
TECH_RUNTIME_FIELDS = COMMON_RUNTIME_FIELDS + ("endGameTech",)
PROJECT_RUNTIME_FIELDS = COMMON_RUNTIME_FIELDS + (
    "repeatable",
    "oneTimeGlobally",
    "disable",
    "factionAvailableChance",
    "initialUnlockChance",
    "deltaUnlockChance",
    "maxUnlockChance",
    "factionAlways",
    "orgGranted",
    "resourcesGranted",
)


class ResearchCatalogError(ValueError):
    """The generated or packaged research catalog violates its runtime contract."""


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def value_fingerprint(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_with_hash(path: Path) -> dict[str, Any]:
    result: dict[str, Any] = {"file": path.name}
    if path.is_file():
        result.update({"size": path.stat().st_size, "sha256": file_sha256(path)})
    return result


def source_file_entry(path: Path, name: str) -> dict[str, str]:
    return {"name": name.replace("\\", "/"), "sha256": file_sha256(path)}


def clean_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): clean_value(item) for key, item in value.items() if item is not None}
    if isinstance(value, list):
        return [clean_value(item) for item in value if item is not None]
    return compact_number(value)


def nonempty_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def load_template_rows(path: Path) -> dict[str, dict[str, Any]]:
    """Load one generator input without hiding duplicate or malformed rows."""

    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ResearchCatalogError(f"Unable to read research template file {path}: {exc}") from exc
    if not isinstance(raw, list):
        raise ResearchCatalogError(f"Research template file must contain an array: {path}")
    rows: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ResearchCatalogError(f"Research template row {index} is not an object: {path}")
        data_name = item.get("dataName")
        if not isinstance(data_name, str) or not data_name:
            raise ResearchCatalogError(f"Research template row {index} has no dataName: {path}")
        if data_name in rows:
            raise ResearchCatalogError(f"Duplicate research dataName {data_name!r}: {path}")
        rows[data_name] = item
    return rows


def discover_supported_scenarios(templates_dir: Path) -> list[str]:
    meta_path = templates_dir / "TIMetaTemplate.json"
    discovered: set[str] = set()
    if meta_path.is_file():
        try:
            text = meta_path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError) as exc:
            raise ResearchCatalogError(f"Unable to read scenario metadata {meta_path}: {exc}") from exc
        # TIMetaTemplate is Unity JSON-like data and currently contains both
        # trailing commas and // comments. dataName extraction is sufficient
        # here and avoids accepting that relaxed syntax for calculation rows.
        discovered.update(re.findall(r'"dataName"\s*:\s*"([^"\r\n]*Scenario)"', text))
    discovered.update(DEFAULT_SUPPORTED_SCENARIOS)
    discovered.update(SCENARIO_DLC_TEMPLATE_HINTS)
    return sorted(discovered)


def discover_scenario_template_dirs(templates_dir: Path) -> dict[str, Path]:
    game_root = game_root_from_templates_dir(templates_dir)
    if game_root is None:
        return {}
    return {
        scenario: candidate
        for scenario, relative in SCENARIO_DLC_TEMPLATE_HINTS.items()
        for candidate in (game_root / relative,)
        if candidate.is_dir()
    }


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


def normalize_resource_grants(value: Any) -> list[dict[str, Any]]:
    grants: list[dict[str, Any]] = []
    for item in value if isinstance(value, list) else []:
        if not isinstance(item, dict) or not item.get("resource"):
            continue
        raw_value = item.get("value", item.get("amount"))
        grant = {"resource": str(item["resource"])}
        if raw_value is not None:
            grant["value"] = compact_number(ti.as_float(raw_value, math.nan))
        grants.append(grant)
    return grants


def normalize_runtime_row(
    template: dict[str, Any],
    kind: str,
    localizations: dict[str, dict[str, dict[str, dict[str, str]]]],
    *,
    partial: bool = False,
) -> dict[str, Any]:
    """Keep only fields read by research runtime calculations.

    Base rows are complete, self-validating records. Scenario rows are sparse
    overlays so an omitted DLC field never erases the corresponding base value.
    """

    if kind not in {"tech", "project"}:
        raise ResearchCatalogError(f"Unknown research row kind: {kind!r}")
    data_name = template.get("dataName")
    if not isinstance(data_name, str) or not data_name:
        raise ResearchCatalogError(f"Research {kind} row has no dataName")
    fields = TECH_RUNTIME_FIELDS if kind == "tech" else PROJECT_RUNTIME_FIELDS
    row = {
        field: clean_value(template[field])
        for field in fields
        if field in template and template[field] is not None
    }
    row["dataName"] = data_name
    row["kind"] = kind
    localized = localized_fields(localizations, kind, data_name, "displayName")
    if localized:
        row["displayName"] = localized

    requirement_fields = {
        "prereqs",
        "altPrereq0",
        "requiredObjectiveName",
        "altRequiredObjectiveName",
        "requiredMilestone",
        "factionPrereq",
        "requiresNation",
    }
    if not partial or requirement_fields & set(template):
        requirements = normalize_requirements(template)
        row["requirements"] = requirements
        row["prerequisiteNodes"] = requirement_nodes(requirements)
    if not partial:
        row.setdefault("prereqs", [])
        row.setdefault("effects", [])
        row.setdefault("factionPrereq", [])
        row["AI_criticalTech"] = bool(template.get("AI_criticalTech"))
        if kind == "tech":
            row["endGameTech"] = bool(template.get("endGameTech"))
        else:
            row["repeatable"] = bool(template.get("repeatable"))
            row["oneTimeGlobally"] = bool(template.get("oneTimeGlobally"))
            row["disable"] = bool(template.get("disable"))
            row.setdefault("factionAlways", [])
            row["resourcesGranted"] = normalize_resource_grants(template.get("resourcesGranted"))
    elif kind == "project" and "resourcesGranted" in template:
        row["resourcesGranted"] = normalize_resource_grants(template.get("resourcesGranted"))
    return clean_value(row)


def _merge_overlay(base: Any, overlay: Any) -> Any:
    if not isinstance(base, dict) or not isinstance(overlay, dict):
        return deepcopy(overlay)
    result = deepcopy(base)
    for key, value in overlay.items():
        result[key] = _merge_overlay(result[key], value) if key in result else deepcopy(value)
    return result


def validate_runtime_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ResearchCatalogError("Research runtime payload must be an object")
    for collection, kind in (("techs", "tech"), ("projects", "project")):
        rows = payload.get(collection)
        if not isinstance(rows, dict):
            raise ResearchCatalogError(f"Research runtime payload has no {collection} index")
        for name, row in rows.items():
            if not isinstance(name, str) or not name or not isinstance(row, dict):
                raise ResearchCatalogError(f"Invalid {collection} runtime row {name!r}")
            if row.get("dataName") != name or row.get("kind") != kind:
                raise ResearchCatalogError(f"Mismatched {collection} runtime row {name!r}")
            missing = {
                "researchCost",
                "techCategory",
                "requirements",
                "prerequisiteNodes",
                "effects",
            } - set(row)
            if missing:
                raise ResearchCatalogError(f"Research runtime row {name!r} is missing {sorted(missing)}")
            cost = row.get("researchCost")
            if isinstance(cost, bool) or not isinstance(cost, (int, float)) or not math.isfinite(float(cost)):
                raise ResearchCatalogError(f"Research runtime row {name!r} has invalid researchCost")
            if not isinstance(row.get("techCategory"), str) or not row["techCategory"]:
                raise ResearchCatalogError(f"Research runtime row {name!r} has invalid techCategory")
            if not isinstance(row.get("requirements"), dict):
                raise ResearchCatalogError(f"Research runtime row {name!r} has invalid requirements")
            if not isinstance(row.get("prerequisiteNodes"), list) or not isinstance(row.get("effects"), list):
                raise ResearchCatalogError(f"Research runtime row {name!r} has invalid list fields")
    return payload


def select_runtime_payload(catalog: dict[str, Any], scenario: str) -> dict[str, Any]:
    supported = catalog.get("supportedScenarios")
    if not isinstance(supported, list) or scenario not in supported:
        raise ResearchCatalogError(f"Unsupported research scenario {scenario!r}")
    expected = value_fingerprint(
        {"base": catalog.get("base"), "scenarioOverrides": catalog.get("scenarioOverrides")}
    )
    if catalog.get("payloadFingerprint") != expected:
        raise ResearchCatalogError("Research catalog payload fingerprint mismatch")
    base = catalog.get("base")
    overrides = catalog.get("scenarioOverrides")
    if not isinstance(base, dict) or not isinstance(overrides, dict):
        raise ResearchCatalogError("Research catalog has invalid base or scenarioOverrides")
    override = overrides.get(scenario, {})
    if not isinstance(override, dict):
        raise ResearchCatalogError(f"Research scenario override {scenario!r} must be an object")
    return validate_runtime_payload(_merge_overlay(base, override))


def require_runtime_row(
    catalog: dict[str, Any],
    scenario: str,
    kind: str,
    data_name: str,
) -> dict[str, Any]:
    payload = select_runtime_payload(catalog, scenario)
    collection = {"tech": "techs", "project": "projects"}.get(kind)
    if collection is None:
        raise ResearchCatalogError(f"Unknown research row kind {kind!r}")
    row = payload[collection].get(data_name)
    if not isinstance(row, dict):
        raise ResearchCatalogError(f"Missing required {kind} row {data_name!r} for {scenario}")
    return row


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


def build_catalog(
    templates_dir: Path,
    languages: list[str],
    *,
    scenario_template_dirs: dict[str, Path] | None = None,
    supported_scenarios: Iterable[str] | None = None,
) -> dict[str, Any]:
    localizations = load_research_localizations(templates_dir, languages)
    templates_by_kind = {
        kind: load_template_rows(templates_dir / filename)
        for kind, filename in RESEARCH_TEMPLATE_FILES.items()
    }
    for kind, templates in templates_by_kind.items():
        if not templates:
            raise ResearchCatalogError(
                f"No {kind} templates found in {templates_dir / RESEARCH_TEMPLATE_FILES[kind]}"
            )

    nodes: list[dict[str, Any]] = []
    for kind, templates in templates_by_kind.items():
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

    base_payload = validate_runtime_payload(
        {
            "techs": {
                name: normalize_runtime_row(template, "tech", localizations)
                for name, template in sorted(templates_by_kind["tech"].items())
            },
            "projects": {
                name: normalize_runtime_row(template, "project", localizations)
                for name, template in sorted(templates_by_kind["project"].items())
            },
        }
    )

    scenario_dirs = (
        {str(name): Path(path) for name, path in scenario_template_dirs.items()}
        if scenario_template_dirs is not None
        else discover_scenario_template_dirs(templates_dir)
    )
    scenario_overrides: dict[str, dict[str, Any]] = {}
    for scenario, directory in sorted(scenario_dirs.items()):
        override_payload: dict[str, Any] = {}
        for kind, collection in (("tech", "techs"), ("project", "projects")):
            path = directory / RESEARCH_TEMPLATE_FILES[kind]
            templates = load_template_rows(path)
            if templates:
                override_payload[collection] = {
                    name: normalize_runtime_row(
                        template,
                        kind,
                        localizations,
                        partial=name in base_payload[collection],
                    )
                    for name, template in sorted(templates.items())
                }
        if override_payload:
            scenario_overrides[scenario] = override_payload

    scenarios = set(supported_scenarios or discover_supported_scenarios(templates_dir))
    scenarios.update(scenario_dirs)
    supported = sorted(scenarios)
    source_files = [
        source_file_entry(templates_dir / filename, f"base/{filename}")
        for filename in RESEARCH_TEMPLATE_FILES.values()
    ]
    meta_path = templates_dir / "TIMetaTemplate.json"
    if meta_path.is_file():
        source_files.append(source_file_entry(meta_path, "base/TIMetaTemplate.json"))
    localization_root = templates_dir.parent / "Localization"
    for kind, prefix in sorted(LOCALIZATION_FILES.items()):
        for language in languages:
            path = localization_root / language / f"{prefix}.{language}"
            if path.is_file():
                source_files.append(
                    source_file_entry(path, f"base/Localization/{language}/{prefix}.{language}")
                )
    for scenario, directory in sorted(scenario_dirs.items()):
        for filename in RESEARCH_TEMPLATE_FILES.values():
            path = directory / filename
            if path.is_file():
                source_files.append(source_file_entry(path, f"{scenario}/{filename}"))
    source_files.sort(key=lambda item: item["name"])

    envelope_payload = {
        "base": base_payload,
        "scenarioOverrides": scenario_overrides,
    }
    catalog = {
        "schemaVersion": SCHEMA_VERSION,
        "generator": {"name": GENERATOR_NAME, "version": GENERATOR_VERSION},
        "sourceFiles": source_files,
        "supportedScenarios": supported,
        **envelope_payload,
        "payloadFingerprint": value_fingerprint(envelope_payload),
        "source": {
            "templateRoot": "TerraInvicta_Data/StreamingAssets/Templates",
            "techTemplate": source_with_hash(templates_dir / RESEARCH_TEMPLATE_FILES["tech"]),
            "projectTemplate": source_with_hash(templates_dir / RESEARCH_TEMPLATE_FILES["project"]),
            "localizationLanguages": languages,
            "scenarioTemplateRoots": {
                scenario: SCENARIO_DLC_TEMPLATE_HINTS.get(scenario, Path(directory.name)).as_posix()
                for scenario, directory in sorted(scenario_dirs.items())
                if scenario in scenario_overrides
            },
        },
        "notes": [
            "Nodes are static template data; save-specific completion and availability should be evaluated separately.",
            "`requirements` is a boolean tree. `all` means every child is required; `any` means at least one child is required.",
            "`prerequisiteNodes`, `edges`, and `childrenByPrereq` are graph indexes derived from node requirements only.",
            "Objective, milestone, faction, and nation requirements are state gates, not research graph edges.",
            "Runtime calculations resolve exact names through base.techs/base.projects and scenarioOverrides; disabled project rows remain available for strict dependency resolution.",
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
    for scenario in supported:
        select_runtime_payload(catalog, scenario)
    return catalog


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
        f"- Schema version `{catalog['schemaVersion']}` packages strict runtime rows under `base.techs` and `base.projects` while retaining the legacy graph views below.",
        f"- Payload fingerprint: `{catalog['payloadFingerprint']}`.",
        "- Supported scenarios: " + ", ".join(f"`{name}`" for name in catalog["supportedScenarios"]) + ".",
        "- Scenario overrides are sparse row maps merged only after an exact supported-scenario match; unsupported scenarios do not inherit base data.",
        "- `requirements` in the JSON is the canonical source for prerequisite logic.",
        "- `prerequisiteNodes` and `edges` are derived from research-node leaves only and intentionally omit objective, milestone, faction, and nation gates.",
        "- `altPrereq0` is represented as an OR alternative for the first `prereqs` entry.",
        "- Disabled projects are excluded from the legacy candidate graph but retained in `base.projects` for strict save-reference diagnostics.",
        "",
        f"Node count: `{counts['total']}` total, `{counts['byKind']['tech']}` global techs, `{counts['byKind']['project']}` projects.",
        f"Runtime row count: `{len(catalog['base']['techs'])}` techs, `{len(catalog['base']['projects'])}` projects.",
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
    languages = parse_languages(args.languages)
    catalog = build_catalog(templates_dir, languages)

    json_output = Path(args.json_output)
    write_json_output(json_output, catalog)

    markdown_output = Path(args.markdown_output)
    write_text_output(markdown_output, build_markdown(catalog, args.markdown_language))

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
