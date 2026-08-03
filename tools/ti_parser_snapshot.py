"""Snapshot summary and cache helpers for the Terra Invicta save parser."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from ti_parser_core import (
    IndexedState,
    TemplateSource,
    build_index,
    cache_key,
    campaign_code,
    clean_numbers,
    first_value,
    load_save,
    load_trait_templates,
    ref_id,
    ref_summary,
    region_nation_summary,
    resolve_ref,
    save_fingerprint,
    short_type,
    snapshot_fingerprint,
    template_source_paths,
    type_entries,
)


@dataclass(frozen=True)
class SnapshotConfig:
    schema_version: int
    default_max_councilor_attribute: int
    councilor_attributes: tuple[str, ...]
    faction_resources: tuple[str, ...]
    org_attribute_fields: tuple[tuple[str, str], ...]


def time_summary(indexed: IndexedState) -> dict[str, Any]:
    time_state = first_value(indexed, "TITimeState") or {}
    current = time_state.get("currentDateTime") or {}
    return {
        "daysInCampaign": time_state.get("daysInCampaign"),
        "currentQuarterSinceStart": time_state.get("currentQuarterSinceStart"),
        "currentDateTime": current,
        "template": time_state.get("templateName"),
        "masterMetaTemplateName": time_state.get("masterMetaTemplateName"),
        "scenarioMetaTemplateName": time_state.get("scenarioMetaTemplateName"),
    }


def metadata_summary(indexed: IndexedState) -> dict[str, Any]:
    metadata = first_value(indexed, "TIMetadataState") or {}
    keys = (
        "playerFactionName",
        "gameTimeString",
        "difficulty",
        "playedWithMods",
        "customDifficulty",
        "researchSpeedMultiplier",
        "controlPointMaintenanceFreebieBonus",
        "missionControlBonus",
        "alienProgressionSpeed",
        "miningProductivityMultiplier",
        "nationalIPMultiplier",
        "averageMonthlyEvents",
    )
    return {key: metadata.get(key) for key in keys if key in metadata}


def global_summary(indexed: IndexedState) -> dict[str, Any]:
    global_state = first_value(indexed, "TIGlobalValuesState") or {}
    keys = (
        "difficulty",
        "campaignStartVersion",
        "latestSaveVersion",
        "realWorldCampaignStart",
        "controlPointMaintenanceFreebies",
        "moddingActive",
        "moddingUsedAnytime",
        "earthAtmosphericCO2_ppm",
        "earthAtmosphericCH4_ppm",
        "earthAtmosphericN2O_ppm",
        "globalSeaLevelAnomaly_cm",
        "looseNukes",
        "nuclearStrikes",
        "bestGlobalHumanMiltech",
        "maxGlobalExpectedHabSiteProduction_day",
    )
    return clean_numbers({key: global_state.get(key) for key in keys if key in global_state})


def faction_key_from_ref(indexed: IndexedState, value: Any) -> str | None:
    found = resolve_ref(indexed, value)
    if not found:
        return None
    state = found[2]
    return state.get("templateName") or state.get("displayName")


def faction_display_from_ref(indexed: IndexedState, value: Any) -> str | None:
    found = resolve_ref(indexed, value)
    if not found:
        return None
    state = found[2]
    return state.get("displayName") or state.get("templateName")


def control_point_summary(indexed: IndexedState, cp_value: dict[str, Any]) -> dict[str, Any]:
    faction = ref_summary(indexed, cp_value.get("faction"))
    return {
        "id": ref_id(cp_value.get("ID")),
        "position": cp_value.get("positionInNation"),
        "type": cp_value.get("controlPointType"),
        "faction": faction.get("template") if faction else None,
        "factionDisplay": faction.get("display") if faction else None,
        "defended": cp_value.get("defended"),
        "benefitsDisabled": cp_value.get("benefitsDisabled"),
        "priorities": clean_numbers(cp_value.get("controlPointPriorities") or {}),
    }


def summarize_regions(indexed: IndexedState, region_refs: list[Any]) -> dict[str, Any]:
    population = 0.0
    boost = 0.0
    mission_control = 0
    region_count = 0
    named_regions: list[str] = []
    for region_ref in region_refs:
        found = resolve_ref(indexed, region_ref)
        if not found:
            continue
        region = found[2]
        region_count += 1
        named_regions.append(region.get("displayName") or region.get("templateName") or str(ref_id(region_ref)))
        population += float(region.get("populationInMillions") or region.get("population_Millions") or 0.0)
        boost += float(region.get("boostPerYear_dekatons") or region.get("boostPerYear_tons") or 0.0)
        mission_control += int(region.get("missionControl") or 0)
    return {
        "count": region_count,
        "population_Millions": round(population, 3),
        "boostPerYear_dekatons": round(boost, 3),
        "missionControl": mission_control,
        "names": named_regions,
    }


def summarize_nation(indexed: IndexedState, entry: dict[str, Any]) -> dict[str, Any]:
    nation = entry.get("Value") or {}
    state_id = ref_id(entry.get("Key")) or ref_id(nation.get("ID"))
    region_refs = nation.get("regions") if isinstance(nation.get("regions"), list) else []
    region_summary = summarize_regions(indexed, region_refs)
    population = region_summary["population_Millions"]
    gdp = nation.get("GDP")
    per_capita = None
    if isinstance(gdp, (int, float)) and population:
        per_capita = gdp / (population * 1_000_000.0)

    cp_summaries: list[dict[str, Any]] = []
    cp_refs = nation.get("controlPoints") if isinstance(nation.get("controlPoints"), list) else []
    for cp_ref in cp_refs:
        found = resolve_ref(indexed, cp_ref)
        if found:
            cp_summaries.append(control_point_summary(indexed, found[2]))

    owner_counts: dict[str, int] = {}
    owner_display: dict[str, str] = {}
    executive_owner = None
    max_position = max((cp.get("position") for cp in cp_summaries if isinstance(cp.get("position"), int)), default=None)
    for cp in cp_summaries:
        owner = cp.get("faction")
        if not owner:
            continue
        owner_counts[owner] = owner_counts.get(owner, 0) + 1
        owner_display[owner] = cp.get("factionDisplay") or owner
        if cp.get("position") == max_position:
            executive_owner = owner

    return clean_numbers(
        {
            "id": state_id,
            "template": nation.get("templateName"),
            "code": campaign_code(nation.get("templateName")),
            "display": nation.get("displayName"),
            "GDP": gdp,
            "perCapitaGDP": per_capita,
            "population_Millions": population,
            "regions": region_summary["count"],
            "regionNames": region_summary["names"],
            "unrest": nation.get("unrest"),
            "cohesion": nation.get("cohesion"),
            "democracy": nation.get("democracy"),
            "education": nation.get("education"),
            "inequality": nation.get("inequality"),
            "militaryTechLevel": nation.get("militaryTechLevel"),
            "numNuclearWeapons": nation.get("numNuclearWeapons"),
            "baseInvestmentPoints_month": nation.get("baseInvestmentPoints_month"),
            "boostPerYear_dekatons": region_summary["boostPerYear_dekatons"],
            "missionControl": region_summary["missionControl"],
            "numControlPoints": nation.get("numControlPoints"),
            "numControlPoints_unclamped": nation.get("numControlPoints_unclamped"),
            "executiveOwner": executive_owner,
            "ownerCounts": owner_counts,
            "ownerDisplay": owner_display,
            "controlPoints": cp_summaries,
            "allies": [ref_summary(indexed, item) for item in nation.get("allies", [])],
            "rivals": [ref_summary(indexed, item) for item in nation.get("rivals", [])],
            "wars": [ref_summary(indexed, item) for item in nation.get("wars", [])],
        }
    )


def average(values: Any) -> float | None:
    if not isinstance(values, list) or not values:
        return None
    numeric = [float(value) for value in values if isinstance(value, (int, float))]
    if not numeric:
        return None
    return sum(numeric) / len(numeric)


def parse_modifier_number(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def int_like(value: float) -> int:
    return int(value)


def trait_mod_has_condition(mod: dict[str, Any]) -> bool:
    condition = mod.get("condition")
    return isinstance(condition, dict) and bool(condition)


def stat_mod_entry(
    trait_name: str,
    trait: dict[str, Any],
    mod: dict[str, Any],
    base_attributes: dict[str, int],
    config: SnapshotConfig,
) -> dict[str, Any] | None:
    attribute = mod.get("stat")
    if attribute not in config.councilor_attributes:
        return None
    operation = mod.get("operation")
    raw_value = mod.get("strValue")
    value = parse_modifier_number(raw_value)
    base_value = base_attributes.get(attribute, 0)
    contribution = None
    supported = True
    note = None

    if operation == "Additive" and value is not None:
        contribution = int_like(value)
    elif operation == "SetToFixedValue" and value is not None:
        contribution = int_like(value) - base_value
    elif operation == "Multiplicative" and value is not None:
        contribution = int_like(base_value * value - base_value)
    elif operation == "SetToAnotherAttribute" and isinstance(raw_value, str):
        contribution = base_attributes.get(raw_value, 0) - base_value
    elif operation in {"IncreaseToValue", "DecreaseToValue"}:
        contribution = 0
        note = "operation is displayed by traits but is not applied by TICouncilorState.ApplyTraitStatValue"
    else:
        supported = False
        note = "operation requires contextual game state and is not evaluated in base finalAttributes"

    return {
        "trait": trait_name,
        "traitDisplay": trait.get("friendlyName") or trait_name,
        "attribute": attribute,
        "operation": operation,
        "value": raw_value,
        "contribution": contribution,
        "conditional": trait_mod_has_condition(mod),
        "conditionType": (mod.get("condition") or {}).get("$type") if isinstance(mod.get("condition"), dict) else None,
        "condition": mod.get("condition"),
        "supported": supported,
        "note": note,
    }


def sum_attr_mods(mods: list[dict[str, Any]], config: SnapshotConfig) -> dict[str, int]:
    totals = {attribute: 0 for attribute in config.councilor_attributes}
    for mod in mods:
        contribution = mod.get("contribution")
        attribute = mod.get("attribute")
        if attribute in totals and isinstance(contribution, int):
            totals[attribute] += contribution
    return totals


def org_attribute_mods(
    indexed: IndexedState,
    councilor: dict[str, Any],
    config: SnapshotConfig,
) -> tuple[dict[str, int], list[dict[str, Any]]]:
    totals = {attribute: 0 for attribute in config.councilor_attributes}
    details: list[dict[str, Any]] = []
    org_refs = councilor.get("orgs") if isinstance(councilor.get("orgs"), list) else []
    for org_ref in org_refs:
        found = resolve_ref(indexed, org_ref)
        if not found:
            continue
        org = found[2]
        applying = bool(org.get("applyingBonuses"))
        mods = {}
        if applying:
            for attribute, field in config.org_attribute_fields:
                value = org.get(field)
                if isinstance(value, int) and value != 0:
                    totals[attribute] += value
                    mods[attribute] = value
        details.append(
            {
                "id": ref_id(org.get("ID")),
                "template": org.get("templateName"),
                "display": org.get("displayName"),
                "tier": org.get("tier"),
                "applyingBonuses": applying,
                "attributeMods": mods,
            }
        )
    return totals, details


def trait_attribute_mods(
    councilor: dict[str, Any],
    trait_templates: dict[str, dict[str, Any]],
    base_attributes: dict[str, int],
    config: SnapshotConfig,
) -> tuple[dict[str, int], list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    unconditional: list[dict[str, Any]] = []
    conditional: list[dict[str, Any]] = []
    warnings: list[str] = []
    trait_names = councilor.get("traitTemplateNames") if isinstance(councilor.get("traitTemplateNames"), list) else []
    for trait_name in trait_names:
        trait = trait_templates.get(trait_name)
        if not trait:
            warnings.append(f"missing trait template: {trait_name}")
            continue
        stat_mods = trait.get("statMods") if isinstance(trait.get("statMods"), list) else []
        for mod in stat_mods:
            if not isinstance(mod, dict) or not mod.get("stat"):
                continue
            entry = stat_mod_entry(trait_name, trait, mod, base_attributes, config)
            if entry is None:
                continue
            if entry["conditional"]:
                conditional.append(entry)
            else:
                unconditional.append(entry)
                if not entry["supported"]:
                    warnings.append(
                        f"unsupported unconditional trait mod: {trait_name} {entry['attribute']} {entry['operation']}"
                    )
    return sum_attr_mods(unconditional, config), unconditional, conditional, warnings


def clamp_attribute(value: int, max_value: int) -> int:
    return max(0, min(value, max_value))


def councilor_attribute_breakdown(
    indexed: IndexedState,
    councilor: dict[str, Any],
    trait_templates: dict[str, dict[str, Any]],
    config: SnapshotConfig,
) -> dict[str, Any]:
    raw_attributes = councilor.get("attributes") if isinstance(councilor.get("attributes"), dict) else {}
    base_attributes = {
        attribute: int(raw_attributes.get(attribute, 0))
        for attribute in config.councilor_attributes
    }
    trait_totals, trait_details, conditional_details, warnings = trait_attribute_mods(
        councilor,
        trait_templates,
        base_attributes,
        config,
    )
    org_totals, org_details = org_attribute_mods(indexed, councilor, config)

    final_attributes: dict[str, int] = {}
    unclamped_attributes: dict[str, int] = {}
    clamped_max_attributes: dict[str, int] = {}
    for attribute in config.councilor_attributes:
        unclamped = base_attributes[attribute] + trait_totals.get(attribute, 0) + org_totals.get(attribute, 0)
        negative_mods = min(0, trait_totals.get(attribute, 0)) + min(0, org_totals.get(attribute, 0))
        clamped_max = config.default_max_councilor_attribute + negative_mods
        unclamped_attributes[attribute] = unclamped
        clamped_max_attributes[attribute] = clamped_max
        final_attributes[attribute] = clamp_attribute(unclamped, clamped_max)

    conditional_potential = {attribute: final_attributes[attribute] for attribute in config.councilor_attributes}
    for mod in conditional_details:
        attribute = mod.get("attribute")
        contribution = mod.get("contribution")
        if attribute in conditional_potential and isinstance(contribution, int):
            conditional_potential[attribute] = clamp_attribute(
                conditional_potential[attribute] + contribution,
                clamped_max_attributes[attribute],
            )

    return {
        "baseAttributes": base_attributes,
        "traitAttributeMods": trait_totals,
        "orgAttributeMods": org_totals,
        "finalAttributes": final_attributes,
        "unclampedAttributes": unclamped_attributes,
        "clampedMaxAttributes": clamped_max_attributes,
        "conditionalPotentialAttributes": conditional_potential,
        "traitModDetails": trait_details,
        "conditionalTraitMods": conditional_details,
        "orgDetails": org_details,
        "calculationWarnings": warnings,
    }


def summarize_faction(
    indexed: IndexedState,
    entry: dict[str, Any],
    nation_by_id: dict[int, dict[str, Any]],
    config: SnapshotConfig,
) -> dict[str, Any]:
    faction = entry.get("Value") or {}
    state_id = ref_id(entry.get("Key")) or ref_id(faction.get("ID"))
    cp_refs = faction.get("controlPoints") if isinstance(faction.get("controlPoints"), list) else []
    nation_counts: dict[int, int] = {}
    for cp_ref in cp_refs:
        found = resolve_ref(indexed, cp_ref)
        if not found:
            continue
        cp_state = found[2]
        nation_ref = cp_state.get("nation")
        nation_id = ref_id(nation_ref)
        if nation_id is not None:
            nation_counts[nation_id] = nation_counts.get(nation_id, 0) + 1

    controlled_nations = []
    for nation_id, cp_count in nation_counts.items():
        nation = nation_by_id.get(nation_id)
        if not nation:
            continue
        controlled_nations.append(
            {
                "id": nation_id,
                "template": nation.get("template"),
                "code": nation.get("code"),
                "display": nation.get("display"),
                "ownedControlPoints": cp_count,
                "totalControlPoints": nation.get("numControlPoints"),
                "executiveOwner": nation.get("executiveOwner"),
                "GDP": nation.get("GDP"),
                "population_Millions": nation.get("population_Millions"),
                "unrest": nation.get("unrest"),
                "cohesion": nation.get("cohesion"),
            }
        )
    controlled_nations.sort(key=lambda item: (-item["ownedControlPoints"], str(item.get("display"))))

    resources = faction.get("resources") if isinstance(faction.get("resources"), dict) else {}
    base_incomes = faction.get("baseIncomes_year") if isinstance(faction.get("baseIncomes_year"), dict) else {}
    return clean_numbers(
        {
            "id": state_id,
            "template": faction.get("templateName"),
            "display": faction.get("displayName"),
            "player": ref_summary(indexed, faction.get("player")),
            "resources": {key: resources.get(key) for key in config.faction_resources if key in resources},
            "baseIncomes_year": {key: base_incomes.get(key) for key in config.faction_resources if key in base_incomes},
            "missionControlUsage": faction.get("missionControlUsage"),
            "resourceIncomeDeficiencies": faction.get("resourceIncomeDeficiencies"),
            "councilors": len(faction.get("councilors") or []),
            "controlPoints": len(cp_refs),
            "controlledNations": controlled_nations,
            "habSectors": len(faction.get("habSectors") or []),
            "fleets": len(faction.get("fleets") or []),
            "shipDesigns": len(faction.get("shipDesigns") or []),
            "finishedProjects": len(faction.get("finishedProjectNames") or []),
            "availableProjects": len(faction.get("availableProjectNames") or []),
            "assessedAlienHateOfMe": faction.get("assessedAlienHateOfMe"),
            "lastDateOfFixedAlienHate": faction.get("lastDateOfFixedAlienHate"),
            "cpOverageRecent": (faction.get("history_CPCapOverageByDay") or [None])[0],
            "cpOverageAverage32d": average(faction.get("history_CPCapOverageByDay")),
            "mcShortageRecent": (faction.get("history_MCCapOverageByDay") or [None])[0],
            "mcShortageAverage32d": average(faction.get("history_MCCapOverageByDay")),
        }
    )


def summarize_councilors(
    indexed: IndexedState,
    trait_templates: dict[str, dict[str, Any]],
    config: SnapshotConfig,
) -> list[dict[str, Any]]:
    result = []
    for entry in type_entries(indexed, "TICouncilorState"):
        councilor = entry.get("Value") or {}
        faction = ref_summary(indexed, councilor.get("faction"))
        home_region = ref_summary(indexed, councilor.get("homeRegion"))
        location = ref_summary(indexed, councilor.get("location"))
        attributes = councilor_attribute_breakdown(indexed, councilor, trait_templates, config)
        result.append(
            clean_numbers(
                {
                    "id": ref_id(entry.get("Key")) or ref_id(councilor.get("ID")),
                    "template": councilor.get("templateName"),
                    "display": councilor.get("displayName"),
                    "faction": faction.get("template") if faction else None,
                    "factionDisplay": faction.get("display") if faction else None,
                    "location": location,
                    "locationNation": region_nation_summary(indexed, councilor.get("location")),
                    "homeRegion": home_region,
                    "homeNation": region_nation_summary(indexed, councilor.get("homeRegion")),
                    "active": councilor.get("active"),
                    "detained": councilor.get("detained"),
                    "turned": councilor.get("turned"),
                    "personalName": councilor.get("personalName"),
                    "familyName": councilor.get("familyName"),
                    "typeTemplateName": councilor.get("typeTemplateName"),
                    "traits": councilor.get("traitTemplateNames") or [],
                    "orgCount": len(councilor.get("orgs") or []),
                    "baseAttributes": attributes["baseAttributes"],
                    "traitAttributeMods": attributes["traitAttributeMods"],
                    "orgAttributeMods": attributes["orgAttributeMods"],
                    "finalAttributes": attributes["finalAttributes"],
                    "unclampedAttributes": attributes["unclampedAttributes"],
                    "clampedMaxAttributes": attributes["clampedMaxAttributes"],
                    "conditionalPotentialAttributes": attributes["conditionalPotentialAttributes"],
                    "traitModDetails": attributes["traitModDetails"],
                    "conditionalTraitMods": attributes["conditionalTraitMods"],
                    "orgDetails": attributes["orgDetails"],
                    "calculationWarnings": attributes["calculationWarnings"],
                }
            )
        )
    return result


def summarize_fleets(indexed: IndexedState) -> list[dict[str, Any]]:
    result = []
    for entry in type_entries(indexed, "TISpaceFleetState"):
        fleet = entry.get("Value") or {}
        faction = ref_summary(indexed, fleet.get("faction"))
        ships = fleet.get("ships") if isinstance(fleet.get("ships"), list) else []
        result.append(
            clean_numbers(
                {
                    "id": ref_id(entry.get("Key")) or ref_id(fleet.get("ID")),
                    "template": fleet.get("templateName"),
                    "display": fleet.get("displayName"),
                    "faction": faction.get("template") if faction else None,
                    "factionDisplay": faction.get("display") if faction else None,
                    "location": ref_summary(indexed, fleet.get("location") or fleet.get("orbit")),
                    "ships": len(ships),
                    "spaceCombatValue": fleet.get("spaceCombatValue") or fleet.get("_spaceCombatValue"),
                    "inTransfer": fleet.get("inTransfer"),
                    "arrivalDate": fleet.get("arrivalDate"),
                }
            )
        )
    return result


def build_snapshot(
    save_path: Path,
    data: dict[str, Any],
    templates_dir: TemplateSource,
    config: SnapshotConfig,
) -> dict[str, Any]:
    indexed = build_index(data)
    trait_templates = load_trait_templates(templates_dir)
    type_counts = {
        short_type(full_type): len(entries) if isinstance(entries, list) else 1
        for full_type, entries in indexed.gamestates.items()
    }

    nations = [summarize_nation(indexed, entry) for entry in type_entries(indexed, "TINationState")]
    nation_by_id = {nation["id"]: nation for nation in nations if nation.get("id") is not None}
    factions = [summarize_faction(indexed, entry, nation_by_id, config) for entry in type_entries(indexed, "TIFactionState")]
    councilors = summarize_councilors(indexed, trait_templates, config)
    fleets = summarize_fleets(indexed)

    return {
        "schemaVersion": config.schema_version,
        "cacheFingerprint": snapshot_fingerprint(save_path, templates_dir),
        "source": save_fingerprint(save_path),
        "templateSource": template_source_paths(templates_dir),
        "currentID": (data.get("currentID") or {}).get("value"),
        "time": time_summary(indexed),
        "metadata": metadata_summary(indexed),
        "global": global_summary(indexed),
        "typeCounts": dict(sorted(type_counts.items(), key=lambda item: (-item[1], item[0]))),
        "factions": factions,
        "nations": nations,
        "councilors": councilors,
        "fleets": fleets,
    }


def load_or_build_snapshot(
    save_path: Path,
    cache_dir: Path,
    templates_dir: TemplateSource,
    config: SnapshotConfig,
    refresh: bool = False,
) -> tuple[dict[str, Any], Path, bool]:
    fingerprint = snapshot_fingerprint(save_path, templates_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / f"{cache_key(fingerprint)}.snapshot.json"
    if not refresh and path.is_file():
        with path.open("r", encoding="utf-8") as handle:
            cached = json.load(handle)
        if cached.get("schemaVersion") == config.schema_version and cached.get("cacheFingerprint") == fingerprint:
            return cached, path, True

    data = load_save(save_path)
    snapshot = build_snapshot(save_path, data, templates_dir, config)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(snapshot, handle, ensure_ascii=False, separators=(",", ":"))
    return snapshot, path, False
