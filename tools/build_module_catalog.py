#!/usr/bin/env python3
"""Build a normalized Terra Invicta hab module catalog.

The generated catalog is intentionally data-only. It captures template stats
and simple derived tags; save-specific evaluation still belongs in the save
parser because mining, adviser, power, and faction effects depend on state.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import ti_save_parser as ti


SCHEMA_VERSION = 1
DEFAULT_JSON_OUTPUT = Path("data/module_catalog.json")
DEFAULT_MARKDOWN_OUTPUT = Path("docs/module_catalog.md")
RESOURCES = (
    "Money",
    "Influence",
    "Operations",
    "Research",
    "Projects",
    "Boost",
    "MissionControl",
    "Water",
    "Volatiles",
    "Metals",
    "NobleMetals",
    "Fissiles",
    "Antimatter",
    "Exotics",
)
BUILD_MATERIALS = (
    "money",
    "influence",
    "ops",
    "boost",
    "water",
    "volatiles",
    "metals",
    "nobleMetals",
    "fissiles",
    "antimatter",
    "exotics",
)
SUPPORT_FIELDS = {
    "Money": "money",
    "Boost": "boost",
    "Water": "water",
    "Volatiles": "volatiles",
    "Metals": "metals",
    "NobleMetals": "nobleMetals",
    "Fissiles": "fissiles",
    "Antimatter": "antimatter",
    "Exotics": "exotics",
}


def compact_number(value: Any, digits: int = 6) -> Any:
    if not isinstance(value, float):
        return value
    rounded = round(value, digits)
    if rounded == 0:
        return 0
    if rounded.is_integer():
        return int(rounded)
    return rounded


def nonzero_values(values: dict[str, Any]) -> dict[str, Any]:
    return {
        key: compact_number(value)
        for key, value in values.items()
        if isinstance(value, (int, float)) and value != 0
    }


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


def load_module_localizations(templates_dir: Path, languages: list[str]) -> dict[str, dict[str, dict[str, str]]]:
    root = templates_dir.parent / "Localization"
    localizations: dict[str, dict[str, dict[str, str]]] = {}
    for language in languages:
        loc_file = root / language / f"TIHabModuleTemplate.{language}"
        loc_values = read_localization_file(loc_file)
        modules: dict[str, dict[str, str]] = {}
        for key, value in loc_values.items():
            parts = key.split(".")
            if len(parts) != 3 or parts[0] != "TIHabModuleTemplate":
                continue
            _, field, data_name = parts
            modules.setdefault(data_name, {})[field] = value
        localizations[language] = modules
    return localizations


def crew_support(template: dict[str, Any], resource: str) -> float:
    crew = ti.as_float(template.get("crew"), 0.0)
    rules = template.get("specialRules") if isinstance(template.get("specialRules"), list) else []
    if resource == "Money":
        if "Stability" in rules:
            return 0.0
        return crew * ti.DEFAULT_GLOBAL_CONFIG["crewSalary_year"] / 12.0
    if resource == "Water":
        return (
            crew
            * ti.DEFAULT_GLOBAL_CONFIG["crewWaterConsumptionTons_year"]
            * ti.DEFAULT_GLOBAL_CONFIG["spaceResourceToTons"]
            / 12.0
        )
    if resource == "Volatiles":
        return (
            crew
            * ti.DEFAULT_GLOBAL_CONFIG["crewVolatilesConsumptionTons_year"]
            * ti.DEFAULT_GLOBAL_CONFIG["spaceResourceToTons"]
            / 12.0
        )
    return 0.0


def monthly_income(template: dict[str, Any], resource: str) -> float:
    field = ti.HAB_INCOME_FIELDS.get(resource)
    return ti.as_float(template.get(field), 0.0) if field else 0.0


def monthly_support(template: dict[str, Any], resource: str, include_crew: bool) -> float:
    support = template.get("supportMaterials_month")
    direct = 0.0
    if isinstance(support, dict):
        field = SUPPORT_FIELDS.get(resource)
        direct = ti.as_float(support.get(field), 0.0) if field else 0.0
    return direct + (crew_support(template, resource) if include_crew else 0.0)


def build_cost(template: dict[str, Any]) -> dict[str, Any]:
    raw = template.get("weightedBuildMaterials")
    if not isinstance(raw, dict):
        raw = template.get("weightBuildMaterials")
    if not isinstance(raw, dict):
        return {}
    return nonzero_values({key: ti.as_float(raw.get(key), 0.0) for key in BUILD_MATERIALS})


def tech_bonus_map(template: dict[str, Any]) -> dict[str, Any]:
    bonuses: dict[str, float] = {}
    for item in template.get("techBonuses") if isinstance(template.get("techBonuses"), list) else []:
        if not isinstance(item, dict):
            continue
        category = str(item.get("category"))
        bonuses[category] = bonuses.get(category, 0.0) + ti.as_float(item.get("bonus"), 0.0)
    return nonzero_values(bonuses)


def source_fingerprint(path: Path) -> dict[str, Any]:
    fingerprint = ti.file_fingerprint(path)
    if not fingerprint:
        return {"file": path.name}
    return {
        "file": path.name,
        "size": fingerprint["size"],
        "mtime_ns": fingerprint["mtime_ns"],
    }


def derive_tags(template: dict[str, Any], income: dict[str, Any], support: dict[str, Any]) -> list[str]:
    tags: set[str] = set()
    power = ti.as_float(template.get("power"), 0.0)
    mission_control = ti.as_float(template.get("missionControl"), 0.0)
    rules = template.get("specialRules") if isinstance(template.get("specialRules"), list) else []
    if template.get("coreModule"):
        tags.add("core")
    if template.get("mine"):
        tags.add("mine")
    if power > 0:
        tags.add("powerProducer")
    elif power < 0:
        tags.add("powerConsumer")
    if mission_control > 0:
        tags.add("mcProducer")
    elif mission_control < 0:
        tags.add("mcConsumer")
    if ti.as_float(template.get("controlPointCapacity"), 0.0) > 0:
        tags.add("controlPointCap")
    if template.get("allowsShipConstruction"):
        tags.add("shipyard")
    if template.get("allowsResupply"):
        tags.add("resupply")
    if "Efficiency" in rules:
        tags.add("efficiency")
    if "Farm" in rules:
        tags.add("farm")
    if "LEOControlPointCapacity" in rules:
        tags.add("leoOnlyCpCap")
    if "MoneyIfNotBuilding" in rules:
        tags.add("incomeStopsDuringConstruction")
    if any(resource in income for resource in ("Research", "Projects")):
        tags.add("research")
    if any(resource in income for resource in ("Money", "Influence", "Operations")):
        tags.add("economy")
    if support:
        tags.add("upkeep")
    if template.get("alienModule"):
        tags.add("alien")
    if template.get("noBuild") or template.get("destroyed") or template.get("disable"):
        tags.add("notNormallyBuildable")
    return sorted(tags)


def normalize_module(template: dict[str, Any], localizations: dict[str, dict[str, dict[str, str]]]) -> dict[str, Any]:
    data_name = str(template.get("dataName"))
    display_names = {
        language: entries.get(data_name, {}).get("displayName")
        for language, entries in localizations.items()
        if entries.get(data_name, {}).get("displayName")
    }
    descriptions = {
        language: entries.get(data_name, {}).get("description")
        for language, entries in localizations.items()
        if entries.get(data_name, {}).get("description")
    }

    income = nonzero_values({resource: monthly_income(template, resource) for resource in RESOURCES})
    support_without_crew = nonzero_values(
        {resource: monthly_support(template, resource, include_crew=False) for resource in RESOURCES}
    )
    support_with_crew = nonzero_values(
        {resource: monthly_support(template, resource, include_crew=True) for resource in RESOURCES}
    )
    net_before_hab = nonzero_values(
        {
            resource: monthly_income(template, resource) - monthly_support(template, resource, include_crew=True)
            for resource in RESOURCES
        }
    )

    flags = {
        "coreModule": bool(template.get("coreModule")),
        "onePerHab": bool(template.get("onePerHab")),
        "automated": bool(template.get("automated")),
        "allowsShipConstruction": bool(template.get("allowsShipConstruction")),
        "allowsResupply": bool(template.get("allowsResupply")),
        "mine": bool(template.get("mine")),
        "noBuild": bool(template.get("noBuild")),
        "destroyed": bool(template.get("destroyed")),
        "alienModule": bool(template.get("alienModule")),
        "objectiveModule": bool(template.get("objectiveModule")),
        "spaceCombatModule": bool(template.get("spaceCombatModule")),
        "disable": bool(template.get("disable")),
    }
    return {
        "dataName": data_name,
        "friendlyName": template.get("friendlyName"),
        "displayName": display_names,
        "description": descriptions,
        "tier": int(ti.as_float(template.get("tier"), 0.0)),
        "habType": template.get("habType") or "Any",
        "flags": flags,
        "requirements": {
            "requiredProjectName": template.get("requiredProjectName"),
            "upgradesFromName": template.get("upgradesFromName"),
            "unlocksProjectName": template.get("unlocksProjectName"),
        },
        "construction": {
            "buildTime_Days": compact_number(ti.as_float(template.get("buildTime_Days"), 0.0)),
            "baseMass_tons": compact_number(ti.as_float(template.get("baseMass_tons"), 0.0)),
            "weightedBuildMaterials": build_cost(template),
        },
        "operation": {
            "crew": int(ti.as_float(template.get("crew"), 0.0)),
            "power": int(ti.as_float(template.get("power"), 0.0)),
            "missionControl": int(ti.as_float(template.get("missionControl"), 0.0)),
            "controlPointCapacity": int(ti.as_float(template.get("controlPointCapacity"), 0.0)),
            "constructionTimeModifier": compact_number(ti.as_float(template.get("constructionTimeModifier"), 1.0)),
            "miningModifier": compact_number(ti.as_float(template.get("miningModifier"), 0.0)),
        },
        "monthlyIncome": income,
        "monthlySupport": {
            "withoutCrew": support_without_crew,
            "withCrew": support_with_crew,
        },
        "monthlyNetBeforeHabModifiers": net_before_hab,
        "bonuses": {
            "tech": tech_bonus_map(template),
            "specialRules": template.get("specialRules") if isinstance(template.get("specialRules"), list) else [],
            "specialRulesValue": compact_number(ti.as_float(template.get("specialRulesValue"), 0.0)),
        },
        "tags": derive_tags(template, income, support_with_crew),
    }


def module_sort_key(module: dict[str, Any]) -> tuple[Any, ...]:
    return (
        module.get("tier", 0),
        module.get("habType") or "",
        "alien" in module.get("tags", []),
        module.get("friendlyName") or module.get("dataName"),
    )


def build_catalog(templates_dir: Path, languages: list[str]) -> dict[str, Any]:
    module_templates = ti.load_named_templates(templates_dir, "TIHabModuleTemplate.json")
    localizations = load_module_localizations(templates_dir, languages)
    modules = [
        normalize_module(template, localizations)
        for template in module_templates.values()
        if not template.get("disable")
    ]
    modules.sort(key=module_sort_key)
    return {
        "schemaVersion": SCHEMA_VERSION,
        "source": {
            "templateRoot": "TerraInvicta_Data/StreamingAssets/Templates",
            "moduleTemplate": source_fingerprint(templates_dir / "TIHabModuleTemplate.json"),
            "localizationLanguages": languages,
        },
        "notes": [
            "monthlyIncome is template income only; mine site output requires hab-site resources and faction mining modifiers.",
            "monthlySupport.withCrew includes per-module crew salary, water, and volatiles support before farm discounts.",
            "monthlyNetBeforeHabModifiers excludes hab efficiency modules, Advise bonuses, power feasibility, and construction-state rules outside the module template.",
        ],
        "resources": list(RESOURCES),
        "modules": modules,
        "byDataName": {module["dataName"]: index for index, module in enumerate(modules)},
    }


def format_resource_map(values: dict[str, Any]) -> str:
    if not values:
        return ""
    return ", ".join(f"{key}:{value}" for key, value in values.items())


def markdown_table(title: str, modules: list[dict[str, Any]], language: str) -> list[str]:
    lines = [
        f"## {title}",
        "",
        "| Module | dataName | T | Type | Tags | Power | Crew | MC | CP | Income/mo | Support/mo | Project |",
        "| --- | --- | ---: | --- | --- | ---: | ---: | ---: | ---: | --- | --- | --- |",
    ]
    for module in modules:
        display = module.get("displayName", {}).get(language) or module.get("friendlyName") or module["dataName"]
        op = module["operation"]
        lines.append(
            "| "
            + " | ".join(
                [
                    str(display).replace("|", "/"),
                    module["dataName"],
                    str(module["tier"]),
                    str(module["habType"]),
                    ", ".join(module["tags"]),
                    str(op["power"]),
                    str(op["crew"]),
                    str(op["missionControl"]),
                    str(op["controlPointCapacity"]),
                    format_resource_map(module["monthlyIncome"]).replace("|", "/"),
                    format_resource_map(module["monthlySupport"]["withCrew"]).replace("|", "/"),
                    str(module["requirements"].get("requiredProjectName") or ""),
                ]
            )
            + " |"
        )
    lines.append("")
    return lines


def build_markdown(catalog: dict[str, Any], language: str) -> str:
    modules = catalog["modules"]
    buildable = [
        module
        for module in modules
        if "alien" not in module["tags"] and "notNormallyBuildable" not in module["tags"]
    ]
    key_modules = [
        module
        for module in buildable
        if any(
            tag in module["tags"]
            for tag in ("mine", "mcProducer", "mcConsumer", "controlPointCap", "powerProducer", "research", "shipyard")
        )
    ]
    key_modules.sort(key=module_sort_key)

    lines = [
        "# Terra Invicta Hab Module Catalog",
        "",
        f"Generated from `{catalog['source']['templateRoot']}/{catalog['source']['moduleTemplate']['file']}`.",
        "",
        "This file is generated. Rebuild it with:",
        "",
        "```powershell",
        "python .\\tools\\build_module_catalog.py",
        "```",
        "",
        "Important interpretation notes:",
        "",
        "- `Income/mo` is template income only. Mine output still needs the hab site's resource deposits and faction mining modifiers.",
        "- `Support/mo` includes module crew salary/water/volatiles support before hab-level farm discounts.",
        "- Actual recommendations must also evaluate available power, module slot legality, construction state, faction effects, and adviser bonuses from the save.",
        "",
        f"Module count: `{len(modules)}` total, `{len(buildable)}` normally buildable human modules.",
        "",
    ]
    lines.extend(markdown_table("High-Value Recommendation Inputs", key_modules, language))
    lines.extend(markdown_table("All Normally Buildable Human Modules", buildable, language))
    return "\n".join(lines).rstrip() + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a normalized Terra Invicta hab module catalog.")
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
            "modules": len(catalog["modules"]),
            "json": str(json_output),
            "markdown": str(markdown_output),
            "templatesDir": str(templates_dir),
        },
        compact=False,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
