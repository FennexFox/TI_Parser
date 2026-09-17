"""Research income, modifiers, distribution and current research UI."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any

from ti_parser_config import (
    DAYS_PER_YEAR,
    DEFAULT_GLOBAL_CONFIG,
)
from ti_parser_core import (
    IndexedState,
    apply_effect_modifiers,
    as_float,
    campaign_code,
    clean_numbers,
    faction_effect_contexts,
    find_faction_state,
    first_value,
    load_hab_module_catalog,
    raw_state_id,
    ref_id,
    ref_summary,
    state_value_by_id,
    type_entries,
)
from ti_parser_hab_ui import hab_research_and_mc
from ti_parser_runtime import (
    active_modules_in_sectors,
    active_owned_control_points,
    calculation_catalogs,
    councilor_research_and_mc,
    councilor_summary_maps,
    current_save_datetime,
    faction_brief,
    faction_councilor_ids,
    faction_sector_states,
    faction_ship_designs,
    human_faction_entries,
    nation_mission_control_contribution,
    nation_research_contribution_month,
    required_catalog_row,
    research_speed_modifier,
    scenario_float,
)


def research_distribution(faction: dict[str, Any]) -> tuple[int, float]:
    weights = faction.get("researchWeights") if isinstance(faction.get("researchWeights"), list) else []
    slots = 0
    for slot, weight in enumerate(weights[:6]):
        if as_float(weight, 0.0) <= 0.0:
            continue
        if slot <= 3 or faction_project_allowed(faction, slot):
            slots += 1
    return slots, slots * DEFAULT_GLOBAL_CONFIG["researchBonusPerSlotInUse"]


@dataclass(frozen=True)
class ResearchTemplates:
    traits: dict[str, dict[str, Any]]
    effects: dict[str, dict[str, Any]]
    orgs: dict[str, dict[str, Any]]
    hab_modules: dict[str, dict[str, Any]]
    utility_modules: dict[str, dict[str, Any]]
    techs: dict[str, dict[str, Any]]
    projects: dict[str, dict[str, Any]]


def load_research_templates(indexed: IndexedState, templates_dir: Path | None = None) -> ResearchTemplates:
    runtime_catalogs = calculation_catalogs(indexed, "research")
    research = runtime_catalogs.research
    ships = runtime_catalogs.ships
    return ResearchTemplates(
        traits=runtime_catalogs.traits,
        effects=runtime_catalogs.effects,
        orgs=runtime_catalogs.orgs,
        hab_modules=load_hab_module_catalog(),
        utility_modules=ships["utilities"],
        techs=research["techs"],
        projects=research["projects"],
    )


def faction_research_cache_key(faction: dict[str, Any]) -> int:
    return ref_id(faction.get("ID")) or id(faction)


def calculate_research_breakdown(
    indexed: IndexedState,
    templates_dir: Path | None,
    faction_name: str | None = None,
    include_details: bool = False,
    templates: ResearchTemplates | None = None,
) -> dict[str, Any]:
    templates = templates or load_research_templates(indexed, templates_dir)
    trait_templates = templates.traits
    effect_templates = templates.effects
    hab_module_templates = templates.hab_modules
    faction_id, faction = find_faction_state(indexed, faction_name)
    effect_contexts = faction_effect_contexts(indexed, faction_id)
    _, councilor_by_id = councilor_summary_maps(indexed, trait_templates)

    base_incomes = faction.get("baseIncomes_year") if isinstance(faction.get("baseIncomes_year"), dict) else {}
    hq_daily = as_float(base_incomes.get("Research"), 0.0) / DAYS_PER_YEAR
    hq_mission_control = as_float(base_incomes.get("MissionControl"), 0.0) + scenario_float(
        indexed,
        "missionControlBonus",
        0.0,
    )

    councilor_daily, councilor_mc, councilor_details = councilor_research_and_mc(
        indexed,
        faction,
        trait_templates,
        councilor_by_id,
    )

    nation_research_month = 0.0
    nation_mc = 0
    nation_details: list[dict[str, Any]] = []
    for entry in type_entries(indexed, "TINationState"):
        nation = entry.get("Value") or {}
        contribution_month = nation_research_contribution_month(
            indexed,
            nation,
            faction_id,
            councilor_by_id,
            effect_contexts,
            effect_templates,
        )
        mc = nation_mission_control_contribution(indexed, nation, faction_id)
        nation_research_month += contribution_month
        nation_mc += mc
        if include_details and (contribution_month or mc):
            nation_details.append(
                {
                    "id": raw_state_id(entry),
                    "template": nation.get("templateName"),
                    "code": campaign_code(nation.get("templateName")),
                    "display": nation.get("displayName"),
                    "ownedControlPoints": len(active_owned_control_points(indexed, nation, faction_id)),
                    "totalControlPoints": nation.get("numControlPoints"),
                    "researchMonth": contribution_month,
                    "researchDay": contribution_month * 12.0 / DAYS_PER_YEAR,
                    "missionControl": mc,
                }
            )
    nation_details.sort(key=lambda item: -item["researchDay"])
    nations_daily = nation_research_month * 12.0 / DAYS_PER_YEAR

    hab_research_month, hab_mc, hab_details = hab_research_and_mc(
        indexed,
        faction,
        hab_module_templates,
        councilor_by_id,
    )
    hab_research_year = apply_effect_modifiers(
        effect_contexts,
        effect_templates,
        "HabResearchProduction",
        hab_research_month * 12.0,
    )
    habs_daily = hab_research_year / DAYS_PER_YEAR

    max_buildable_mc = councilor_mc + nation_mc + hab_mc
    pre_effect_mc = hq_mission_control + max_buildable_mc
    max_mc = apply_effect_modifiers(
        effect_contexts,
        effect_templates,
        "MissionControlDisruption_PCT",
        pre_effect_mc,
    )
    usage_mc = int(as_float(faction.get("missionControlUsage"), 0.0))
    available_mc = max(max_mc - usage_mc, 0)
    excess_mc_used = min(max_buildable_mc, available_mc)
    excess_mc_daily = excess_mc_used * DEFAULT_GLOBAL_CONFIG["ExcessMCToResearchConversion_Day"]

    source_daily = {
        "HQ": hq_daily,
        "councilors": councilor_daily,
        "nations": nations_daily,
        "habs": habs_daily,
        "ships": 0.0,
        "diplomacy": 0.0,
        "unassignedOrgs": 0.0,
        "excessMissionControl": excess_mc_daily,
    }
    before_distribution = sum(source_daily.values())
    distribution_slots, distribution_percent = research_distribution(faction)
    distribution_daily = before_distribution * distribution_percent
    total_daily = before_distribution + distribution_daily

    result: dict[str, Any] = {
        "faction": {
            "id": faction_id,
            "template": faction.get("templateName"),
            "display": faction.get("displayName"),
        },
        "daily": {
            "total": total_daily,
            "beforeDistribution": before_distribution,
            "distributionBonus": distribution_daily,
            "bySource": source_daily,
        },
        "monthly": {
            "total": total_daily * DAYS_PER_YEAR / 12.0,
        },
        "annual": {
            "total": total_daily * DAYS_PER_YEAR,
        },
        "distribution": {
            "slots": distribution_slots,
            "percent": distribution_percent,
        },
        "missionControl": {
            "usage": usage_mc,
            "max": max_mc,
            "available": available_mc,
            "excessUsedForResearch": excess_mc_used,
            "components": {
                "HQ": hq_mission_control,
                "councilorOrgs": councilor_mc,
                "nations": nation_mc,
                "habs": hab_mc,
                "effects": max_mc - pre_effect_mc,
                "buildableSources": max_buildable_mc,
            },
        },
        "notes": [
            "Research values are daily. Monthly/annual values are derived from daily using 365.2422 days per year.",
            "Ships, diplomacy and unassigned org research are included as zero; this matches the current save but is not yet a general implementation.",
        ],
    }
    if include_details:
        result["details"] = {
            "councilors": councilor_details,
            "nations": nation_details,
            "habs": hab_details,
            "effects": {
                "ControlPointResearch": effect_contexts.get("ControlPointResearch", []),
                "HabResearchProduction": effect_contexts.get("HabResearchProduction", []),
            },
        }
    return clean_numbers(result, 6)


def template_display(template_name: str | None, template: dict[str, Any]) -> str | None:
    if not template_name and not template:
        return None
    return template.get("_displayName") or template.get("friendlyName") or template_name


def tech_template_cost(indexed: IndexedState, template: dict[str, Any]) -> float:
    cost = as_float(template.get("researchCost"), 0.0)
    if template.get("endGameTech"):
        global_research = first_value(indexed, "TIGlobalResearchState") or {}
        category = template.get("techCategory")
        completed_by_category = global_research.get("endGameTechsCompletedByCategory")
        completed = as_float(completed_by_category.get(category), 0.0) if isinstance(completed_by_category, dict) else 0.0
        cost *= 1.0 + completed
    return cost / research_speed_modifier(indexed)


def project_template_cost(indexed: IndexedState, template: dict[str, Any], faction: dict[str, Any]) -> float:
    cost = as_float(template.get("researchCost"), 0.0)
    if template.get("repeatable"):
        template_name = template.get("dataName")
        finished = faction.get("finishedProjectNames") if isinstance(faction.get("finishedProjectNames"), list) else []
        cost *= 1.0 + sum(1 for name in finished if name == template_name)
    return cost / research_speed_modifier(indexed)


def eta_from_daily(indexed: IndexedState, remaining: float, daily: float) -> dict[str, Any]:
    if remaining <= 0.0:
        days = 0.0
    elif daily > 0.0:
        days = remaining / daily
    else:
        return {"days": None, "date": None}
    current = current_save_datetime(indexed)
    eta_date = None
    if current is not None:
        try:
            eta_date = (current + timedelta(days=days)).date().isoformat()
        except OverflowError:
            eta_date = None
    return {"days": days, "date": eta_date}


def faction_project_allowed(faction: dict[str, Any], slot: int) -> bool:
    if slot == 3:
        return True
    if slot == 4:
        return bool(faction.get("orgProjectSlotUnlocked"))
    if slot == 5:
        return bool(faction.get("habProjectSlotUnlocked"))
    return False


def faction_project_slots(faction: dict[str, Any]) -> list[int]:
    return [slot for slot in range(3, 6) if faction_project_allowed(faction, slot)]


def faction_research_weights(faction: dict[str, Any]) -> list[float]:
    raw = faction.get("researchWeights") if isinstance(faction.get("researchWeights"), list) else []
    return [as_float(raw[index], 0.0) if index < len(raw) else 0.0 for index in range(6)]


def faction_total_research_weights(faction: dict[str, Any]) -> float:
    weights = faction_research_weights(faction)
    return (
        weights[0]
        + weights[1]
        + weights[2]
        + weights[3]
        + (weights[4] if faction_project_allowed(faction, 4) else 0.0)
        + (weights[5] if faction_project_allowed(faction, 5) else 0.0)
    )


def faction_fraction_weight_in_slot(faction: dict[str, Any], slot: int) -> float:
    weights = faction_research_weights(faction)
    total = faction_total_research_weights(faction)
    if slot < 0 or slot >= len(weights) or total <= 0.0:
        return 0.0
    return weights[slot] / total


def project_progress_by_slot(faction: dict[str, Any]) -> dict[int, dict[str, Any]]:
    projects = faction.get("currentProjectProgress") if isinstance(faction.get("currentProjectProgress"), list) else []
    result: dict[int, dict[str, Any]] = {}
    for project in projects:
        if not isinstance(project, dict):
            continue
        slot = int(as_float(project.get("slot"), -1.0))
        if slot >= 0:
            result[slot] = project
    return result


def tech_bonus_sum(bonuses: Any, category: str | None) -> float:
    if not category or not isinstance(bonuses, list):
        return 0.0
    total = 0.0
    for bonus in bonuses:
        if isinstance(bonus, dict) and bonus.get("category") == category:
            total += as_float(bonus.get("bonus"), 0.0)
    return total


def diminishing_research_modifier(value: float) -> float:
    if value > 0.5:
        overage = value - 0.5
        return 0.5 + 0.5 * (overage / (overage + 2.0))
    return value


def active_faction_councilors(indexed: IndexedState, faction: dict[str, Any]) -> list[dict[str, Any]]:
    councilors: list[dict[str, Any]] = []
    for councilor_id in faction_councilor_ids(faction):
        councilor = state_value_by_id(indexed, councilor_id)
        if isinstance(councilor, dict):
            councilors.append(councilor)
    return councilors


def faction_hab_category_modifier(
    indexed: IndexedState,
    faction: dict[str, Any],
    hab_module_templates: dict[str, dict[str, Any]],
    category: str | None,
) -> float:
    if not category:
        return 0.0
    total = 0.0
    for module in active_modules_in_sectors(indexed, faction_sector_states(indexed, faction)):
        template = required_catalog_row(
            indexed,
            hab_module_templates,
            "hab-module",
            module.get("templateName"),
            "research.category.hab",
        )
        total += tech_bonus_sum(template.get("techBonuses"), category)
    return diminishing_research_modifier(total)


def faction_org_category_modifier(
    indexed: IndexedState,
    faction: dict[str, Any],
    org_templates: dict[str, dict[str, Any]],
    category: str | None,
) -> float:
    if not category:
        return 0.0
    total = 0.0
    for councilor in active_faction_councilors(indexed, faction):
        for org_ref in councilor.get("orgs") if isinstance(councilor.get("orgs"), list) else []:
            org = state_value_by_id(indexed, ref_id(org_ref))
            if not isinstance(org, dict) or not org.get("applyingBonuses"):
                continue
            template = required_catalog_row(
                indexed,
                org_templates,
                "org",
                org.get("templateName"),
                "research.category.org",
            )
            bonuses = org.get("techBonuses")
            if not isinstance(bonuses, list) or not bonuses:
                bonuses = template.get("techBonuses")
            total += tech_bonus_sum(bonuses, category)
    return diminishing_research_modifier(total)


def faction_trait_category_modifier(
    indexed: IndexedState,
    faction: dict[str, Any],
    trait_templates: dict[str, dict[str, Any]],
    category: str | None,
) -> float:
    if not category:
        return 0.0
    total = 0.0
    for councilor in active_faction_councilors(indexed, faction):
        for trait_name in councilor.get("traitTemplateNames") if isinstance(councilor.get("traitTemplateNames"), list) else []:
            template = required_catalog_row(
                indexed,
                trait_templates,
                "trait",
                trait_name,
                "research.category.trait",
            )
            total += tech_bonus_sum(template.get("techBonuses"), category)
    return diminishing_research_modifier(total)


def faction_investigations_modifier(faction: dict[str, Any], category: str | None) -> float:
    return as_float(faction.get("alienInvestigations"), 0.0) / 100.0 if category == "Xenology" else 0.0


def fleet_in_earth_system(indexed: IndexedState, fleet: dict[str, Any]) -> bool:
    body_refs = []
    orbit = state_value_by_id(indexed, ref_id(fleet.get("orbitState")))
    if isinstance(orbit, dict):
        body_refs.append(orbit.get("barycenter"))
    body_refs.append(fleet.get("barycenter"))
    trajectory = fleet.get("trajectory") if isinstance(fleet.get("trajectory"), dict) else {}
    body_refs.append(trajectory.get("commonBarycenter"))
    for body_ref in body_refs:
        body = state_value_by_id(indexed, ref_id(body_ref))
        if isinstance(body, dict) and body.get("templateName") in {"Earth", "Luna"}:
            return True
    return False


def faction_fleet_category_modifier(
    indexed: IndexedState,
    faction: dict[str, Any],
    utility_module_templates: dict[str, dict[str, Any]],
    category: str | None,
) -> float:
    if category != "SpaceScience":
        return 0.0
    designs = faction_ship_designs(faction)
    total = 0.0
    for fleet_ref in faction.get("fleets") if isinstance(faction.get("fleets"), list) else []:
        fleet = state_value_by_id(indexed, ref_id(fleet_ref))
        if not isinstance(fleet, dict) or fleet.get("dockedLocation") or fleet_in_earth_system(indexed, fleet):
            continue
        for ship_ref in fleet.get("ships") if isinstance(fleet.get("ships"), list) else []:
            ship = state_value_by_id(indexed, ref_id(ship_ref))
            if not isinstance(ship, dict):
                continue
            design = required_catalog_row(
                indexed,
                designs,
            "ship-design",
            ship.get("templateName"),
            "research.category.fleet-design",
            "ship references a saved design that cannot be resolved",
            )
            for entry in design.get("moduleTemplateEntries") if isinstance(design.get("moduleTemplateEntries"), list) else []:
                if not isinstance(entry, dict):
                    continue
                module_name = str(entry.get("moduleName") or "")
                if not module_name or module_name == "Empty":
                    continue
                module = required_catalog_row(
                    indexed,
                    utility_module_templates,
                    "ship-utility",
                    module_name,
                    "research.category.fleet-utility",
                )
                special_rules = module.get("specialModuleRules") if isinstance(module.get("specialModuleRules"), list) else []
                if "GenerateSpaceScienceBonus" in special_rules:
                    total += as_float(module.get("specialModuleValue"), 0.0)
    return diminishing_research_modifier(total)


def faction_category_modifier_components(
    indexed: IndexedState,
    faction: dict[str, Any],
    trait_templates: dict[str, dict[str, Any]],
    org_templates: dict[str, dict[str, Any]],
    hab_module_templates: dict[str, dict[str, Any]],
    utility_module_templates: dict[str, dict[str, Any]],
    category: str | None,
) -> dict[str, float]:
    components = {
        "habs": faction_hab_category_modifier(indexed, faction, hab_module_templates, category),
        "orgs": faction_org_category_modifier(indexed, faction, org_templates, category),
        "traits": faction_trait_category_modifier(indexed, faction, trait_templates, category),
        "investigations": faction_investigations_modifier(faction, category),
        "fleets": faction_fleet_category_modifier(indexed, faction, utility_module_templates, category),
    }
    components["sum"] = sum(components.values())
    return components


def project_facility_counts(
    indexed: IndexedState,
    faction: dict[str, Any],
    trait_templates: dict[str, dict[str, Any]],
    hab_module_templates: dict[str, dict[str, Any]],
    org_templates: dict[str, dict[str, Any]] | None = None,
) -> dict[str, float]:
    base_incomes = faction.get("baseIncomes_year") if isinstance(faction.get("baseIncomes_year"), dict) else {}
    trait_projects = 0.0
    org_projects = 0.0
    for councilor in active_faction_councilors(indexed, faction):
        for trait_name in councilor.get("traitTemplateNames") if isinstance(councilor.get("traitTemplateNames"), list) else []:
            template = required_catalog_row(
                indexed,
                trait_templates,
                "trait",
                trait_name,
                "project.facilities.trait",
            )
            trait_projects += as_float(template.get("incomeProjects"), 0.0)
        for org_ref in councilor.get("orgs") if isinstance(councilor.get("orgs"), list) else []:
            org = state_value_by_id(indexed, ref_id(org_ref))
            if isinstance(org, dict) and org.get("applyingBonuses"):
                required_catalog_row(
                    indexed,
                    org_templates or {},
                    "org",
                    org.get("templateName"),
                    "project.facilities.org",
                )
                org_projects += as_float(org.get("projectCapacityGranted"), 0.0)

    hab_projects = 0.0
    for module in active_modules_in_sectors(indexed, faction_sector_states(indexed, faction)):
        template = required_catalog_row(
            indexed,
            hab_module_templates,
            "hab-module",
            module.get("templateName"),
            "project.facilities.hab",
        )
        hab_projects += as_float(template.get("incomeProjects"), 0.0)

    return {
        "base": as_float(base_incomes.get("Projects"), 0.0),
        "traits": trait_projects,
        "orgs": org_projects,
        "habs": hab_projects,
    }


def multiple_facilities_multiplier(counts: dict[str, float]) -> float:
    facilities = (
        counts.get("base", 0.0)
        + counts.get("traits", 0.0)
        + max(0.0, counts.get("orgs", 0.0) - 1.0)
        + max(0.0, counts.get("habs", 0.0) - 1.0)
    )
    if facilities <= 0.0:
        return 0.0
    return (
        min(facilities, 20.0) * DEFAULT_GLOBAL_CONFIG["first20ExtraProjectBonusPct"]
        + min(max(facilities - 20.0, 0.0), 20.0) * DEFAULT_GLOBAL_CONFIG["second20ExtraProjectBonusPct"]
        + max(facilities - 40.0, 0.0) * DEFAULT_GLOBAL_CONFIG["overageExtraProjectBonusPct"]
    )


def active_slots_with_category(
    indexed: IndexedState,
    faction: dict[str, Any],
    tech_templates: dict[str, dict[str, Any]],
    project_templates: dict[str, dict[str, Any]],
    category: str | None,
) -> int:
    if not category:
        return 0
    weights = faction_research_weights(faction)
    count = 0
    global_research = first_value(indexed, "TIGlobalResearchState") or {}
    tech_progress = global_research.get("techProgress") if isinstance(global_research.get("techProgress"), list) else []
    for slot in range(3):
        if weights[slot] <= 0.0 or slot >= len(tech_progress):
            continue
        progress = tech_progress[slot] if isinstance(tech_progress[slot], dict) else {}
        template_name = progress.get("techTemplateName")
        if not template_name:
            continue
        template = required_catalog_row(
            indexed,
            tech_templates,
            "research-tech",
            template_name,
            "research.category.active-tech",
        )
        if template.get("techCategory") == category:
            count += 1

    projects = project_progress_by_slot(faction)
    for slot in range(3, 6):
        if weights[slot] <= 0.0 or not faction_project_allowed(faction, slot):
            continue
        progress = projects.get(slot)
        template_name = progress.get("projectTemplateName") if isinstance(progress, dict) else None
        if not template_name:
            continue
        template = required_catalog_row(
            indexed,
            project_templates,
            "research-project",
            template_name,
            "research.category.active-project",
        )
        if template.get("techCategory") == category:
            count += 1
    return count


def distributed_category_modifier(
    indexed: IndexedState,
    faction: dict[str, Any],
    trait_templates: dict[str, dict[str, Any]],
    org_templates: dict[str, dict[str, Any]],
    hab_module_templates: dict[str, dict[str, Any]],
    utility_module_templates: dict[str, dict[str, Any]],
    tech_templates: dict[str, dict[str, Any]],
    project_templates: dict[str, dict[str, Any]],
    category: str | None,
) -> dict[str, Any]:
    components = faction_category_modifier_components(
        indexed,
        faction,
        trait_templates,
        org_templates,
        hab_module_templates,
        utility_module_templates,
        category,
    )
    active_same_category = active_slots_with_category(indexed, faction, tech_templates, project_templates, category)
    penalty_power = max(active_same_category - 1, 0)
    distributed = components["sum"] * (DEFAULT_GLOBAL_CONFIG["categoryBonusPenaltyPerExtraSlot"] ** penalty_power)
    return {
        "category": category,
        "components": components,
        "activeSlotsWithCategory": active_same_category,
        "extraSlotPenaltyPower": penalty_power,
        "distributed": distributed,
    }


def research_points_to_slot(
    indexed: IndexedState,
    faction: dict[str, Any],
    slot: int,
    base_daily: float,
    tech_templates: dict[str, dict[str, Any]],
    project_templates: dict[str, dict[str, Any]],
    trait_templates: dict[str, dict[str, Any]],
    org_templates: dict[str, dict[str, Any]],
    hab_module_templates: dict[str, dict[str, Any]],
    utility_module_templates: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    weights = faction_research_weights(faction)
    total_weights = faction_total_research_weights(faction)
    if (
        slot < 0
        or slot >= len(weights)
        or total_weights <= 0.0
        or weights[slot] <= 0.0
        or (slot >= 3 and not faction_project_allowed(faction, slot))
    ):
        return {"daily": 0.0, "weight": 0.0, "weightFraction": 0.0, "modifiers": None}

    is_project = slot >= 3
    template: dict[str, Any] = {}
    if is_project:
        progress = project_progress_by_slot(faction).get(slot)
        template_name = progress.get("projectTemplateName") if isinstance(progress, dict) else None
        if not template_name:
            return {
                "daily": 0.0,
                "weight": weights[slot],
                "weightFraction": weights[slot] / total_weights,
                "category": None,
                "modifiers": None,
            }
        template = required_catalog_row(
            indexed,
            project_templates,
            "research-project",
            template_name,
            "research.slot.active-project",
        )
    else:
        global_research = first_value(indexed, "TIGlobalResearchState") or {}
        tech_progress = global_research.get("techProgress") if isinstance(global_research.get("techProgress"), list) else []
        progress = tech_progress[slot] if slot < len(tech_progress) and isinstance(tech_progress[slot], dict) else None
        template_name = progress.get("techTemplateName") if isinstance(progress, dict) else None
        if not template_name:
            return {
                "daily": 0.0,
                "weight": weights[slot],
                "weightFraction": weights[slot] / total_weights,
                "category": None,
                "modifiers": None,
            }
        template = required_catalog_row(
            indexed,
            tech_templates,
            "research-tech",
            template_name,
            "research.slot.active-tech",
        )

    category = template.get("techCategory")
    category_modifier = distributed_category_modifier(
        indexed,
        faction,
        trait_templates,
        org_templates,
        hab_module_templates,
        utility_module_templates,
        tech_templates,
        project_templates,
        category,
    )
    project_facilities = (
        project_facility_counts(
            indexed,
            faction,
            trait_templates,
            hab_module_templates,
            org_templates=org_templates,
        )
        if is_project
        else None
    )
    project_bonus = multiple_facilities_multiplier(project_facilities or {}) if is_project else 0.0
    effective_daily = base_daily * (1.0 + as_float(category_modifier["distributed"], 0.0) + project_bonus)
    weight_fraction = weights[slot] / total_weights
    return {
        "daily": effective_daily * weight_fraction,
        "weight": weights[slot],
        "weightFraction": weight_fraction,
        "category": category,
        "modifiers": {
            "category": category_modifier,
            "projectFacilities": project_facilities,
            "projectFacilityBonus": project_bonus if is_project else None,
            "effectiveMultiplier": 1.0 + as_float(category_modifier["distributed"], 0.0) + project_bonus,
        },
    }


def faction_base_research_daily(
    indexed: IndexedState,
    templates_dir: Path | None,
    faction: dict[str, Any],
    *,
    templates: ResearchTemplates | None = None,
    cache: dict[int, float] | None = None,
) -> float:
    name = faction.get("templateName") or faction.get("displayName")
    if not name or faction.get("templateName") == "AlienCouncil":
        return 0.0
    cache_key_value = faction_research_cache_key(faction)
    if cache is not None and cache_key_value in cache:
        return cache[cache_key_value]
    value = as_float(
        calculate_research_breakdown(
            indexed,
            templates_dir,
            str(name),
            include_details=False,
            templates=templates,
        )["daily"]["beforeDistribution"],
        0.0,
    )
    if cache is not None:
        cache[cache_key_value] = value
    return value


def global_research_contributions(indexed: IndexedState, progress: dict[str, Any]) -> list[dict[str, Any]]:
    contributions = []
    for pair in progress.get("factionContributions") if isinstance(progress.get("factionContributions"), list) else []:
        if not isinstance(pair, dict):
            continue
        faction_id = ref_id(pair.get("Key"))
        faction = state_value_by_id(indexed, faction_id)
        amount = as_float(pair.get("Value"), 0.0)
        contributions.append(
            {
                "faction": faction_brief(faction_id, faction) if isinstance(faction, dict) else {"id": faction_id},
                "amount": amount,
            }
        )
    contributions.sort(key=lambda item: -as_float(item.get("amount"), 0.0))
    return contributions


def research_progress_row(
    indexed: IndexedState,
    template_name: str | None,
    template: dict[str, Any],
    accumulated: float,
    cost: float,
) -> dict[str, Any]:
    remaining = max(cost - accumulated, 0.0)
    return {
        "template": template_name,
        "display": template_display(template_name, template),
        "category": template.get("techCategory"),
        "progress": accumulated,
        "cost": cost,
        "remaining": remaining,
        "progressFraction": accumulated / cost if cost > 0.0 else None,
    }


def calculate_research_ui(
    indexed: IndexedState,
    templates_dir: Path | None,
    faction_name: str | None = None,
    *,
    templates: ResearchTemplates | None = None,
    base_daily_cache: dict[int, float] | None = None,
) -> dict[str, Any]:
    templates = templates or load_research_templates(indexed, templates_dir)
    base_daily_cache = base_daily_cache if base_daily_cache is not None else {}
    trait_templates = templates.traits
    org_templates = templates.orgs
    hab_module_templates = templates.hab_modules
    utility_module_templates = templates.utility_modules
    tech_templates = templates.techs
    project_templates = templates.projects

    faction_id, faction = find_faction_state(indexed, faction_name)
    selected_base_daily = faction_base_research_daily(
        indexed,
        templates_dir,
        faction,
        templates=templates,
        cache=base_daily_cache,
    )
    all_human_factions = [
        (
            other_id,
            other,
            faction_base_research_daily(
                indexed,
                templates_dir,
                other,
                templates=templates,
                cache=base_daily_cache,
            ),
        )
        for other_id, other in human_faction_entries(indexed)
    ]

    global_research = first_value(indexed, "TIGlobalResearchState") or {}
    tech_progress = global_research.get("techProgress") if isinstance(global_research.get("techProgress"), list) else []
    global_slots = []
    for slot, progress in enumerate(tech_progress[:3]):
        if not isinstance(progress, dict):
            continue
        template_name = progress.get("techTemplateName")
        template = required_catalog_row(indexed, tech_templates, "research-tech", template_name, "research-ui.global")
        accumulated = as_float(progress.get("accumulatedResearch"), 0.0)
        cost = tech_template_cost(indexed, template)
        row = research_progress_row(indexed, template_name, template, accumulated, cost)
        selected_slot = research_points_to_slot(
            indexed,
            faction,
            slot,
            selected_base_daily,
            tech_templates,
            project_templates,
            trait_templates,
            org_templates,
            hab_module_templates,
            utility_module_templates,
        )
        total_daily = 0.0
        faction_daily = []
        for other_id, other, other_base_daily in all_human_factions:
            points = research_points_to_slot(
                indexed,
                other,
                slot,
                other_base_daily,
                tech_templates,
                project_templates,
                trait_templates,
                org_templates,
                hab_module_templates,
                utility_module_templates,
            )
            total_daily += as_float(points.get("daily"), 0.0)
            faction_daily.append(
                {
                    "faction": faction_brief(other_id, other),
                    "daily": points.get("daily"),
                    "weightFraction": points.get("weightFraction"),
                }
            )
        faction_daily.sort(key=lambda item: -as_float(item.get("daily"), 0.0))
        row.update(
            {
                "slot": slot,
                "selector": ref_summary(indexed, progress.get("selector")),
                "selectedFactionDaily": selected_slot["daily"],
                "selectedFactionWeight": selected_slot["weight"],
                "selectedFactionWeightFraction": selected_slot["weightFraction"],
                "totalDaily": total_daily,
                "eta": eta_from_daily(indexed, as_float(row["remaining"], 0.0), total_daily),
                "selectedFactionModifiers": selected_slot["modifiers"],
                "contributions": global_research_contributions(indexed, progress),
                "dailyByFaction": faction_daily,
            }
        )
        global_slots.append(clean_numbers(row, 6))

    project_slots = []
    paused_projects = []
    projects_by_slot = project_progress_by_slot(faction)
    for slot in faction_project_slots(faction):
        progress = projects_by_slot.get(slot)
        if not progress:
            project_slots.append({"slot": slot, "empty": True})
            continue
        template_name = progress.get("projectTemplateName")
        template = required_catalog_row(indexed, project_templates, "research-project", template_name, "research-ui.project")
        accumulated = as_float(progress.get("accumulatedResearch"), 0.0)
        cost = project_template_cost(indexed, template, faction)
        row = research_progress_row(indexed, template_name, template, accumulated, cost)
        selected_slot = research_points_to_slot(
            indexed,
            faction,
            slot,
            selected_base_daily,
            tech_templates,
            project_templates,
            trait_templates,
            org_templates,
            hab_module_templates,
            utility_module_templates,
        )
        row.update(
            {
                "slot": slot,
                "daily": selected_slot["daily"],
                "weight": selected_slot["weight"],
                "weightFraction": selected_slot["weightFraction"],
                "eta": eta_from_daily(indexed, as_float(row["remaining"], 0.0), as_float(selected_slot["daily"], 0.0)),
                "modifiers": selected_slot["modifiers"],
            }
        )
        project_slots.append(clean_numbers(row, 6))

    active_project_slots = set(faction_project_slots(faction))
    for slot, progress in sorted(projects_by_slot.items()):
        if slot in active_project_slots:
            continue
        template_name = progress.get("projectTemplateName")
        template = required_catalog_row(indexed, project_templates, "research-project", template_name, "research-ui.paused-project")
        cost = project_template_cost(indexed, template, faction)
        accumulated = as_float(progress.get("accumulatedResearch"), 0.0)
        row = research_progress_row(indexed, template_name, template, accumulated, cost)
        row.update({"slot": slot, "paused": True, "reason": "slot>=6 or project slot not currently unlocked"})
        paused_projects.append(clean_numbers(row, 6))

    weights = faction_research_weights(faction)
    fractions = {str(slot): faction_fraction_weight_in_slot(faction, slot) for slot in range(6)}
    return clean_numbers(
        {
            "faction": faction_brief(faction_id, faction),
            "date": (first_value(indexed, "TITimeState") or {}).get("currentDateTime"),
            "researchIncome": {
                "baseDailyBeforeDistribution": selected_base_daily,
                "note": "Research screen slot rates use TIFactionState.GetDailyIncome(Research) before distribution-slot bonus.",
            },
            "slotAllocation": {
                "weights": weights,
                "totalActiveWeights": faction_total_research_weights(faction),
                "fractions": fractions,
                "activeProjectSlots": faction_project_slots(faction),
                "orgProjectSlotUnlocked": bool(faction.get("orgProjectSlotUnlocked")),
                "habProjectSlotUnlocked": bool(faction.get("habProjectSlotUnlocked")),
            },
            "globalResearch": global_slots,
            "projects": {
                "active": project_slots,
                "pausedOrStored": paused_projects,
            },
            "sourceNotes": [
                "Global research progress comes from TIGlobalResearchState.techProgress.",
                "Faction projects come from TIFactionState.currentProjectProgress; only slots 3, 4, and 5 can be currently active.",
                "Displayed slot rates follow ResearchPanelController: PointsToSlot(slot, GetDailyIncome(Research), TotalResearchWeights).",
                "Global tech ETA follows TIGlobalResearchState.TechCompletionDate by summing all human factions' slot output.",
            ],
        },
        6,
    )
