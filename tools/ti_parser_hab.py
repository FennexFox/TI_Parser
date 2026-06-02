"""Hab-related helpers for the Terra Invicta save parser."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from ti_parser_core import (
    IndexedState,
    apply_effect_modifiers,
    as_float,
    ref_id,
    ref_summary,
    resolve_ref,
    state_value_by_id,
)


@dataclass(frozen=True)
class HabConfig:
    days_per_year: float
    default_global_config: Mapping[str, float]
    hab_income_fields: Mapping[str, str]
    hab_support_fields: Mapping[str, str]
    hab_site_production_fields: Mapping[str, str]
    basic_space_resources: tuple[str, ...]
    mining_bonus_contexts: Mapping[str, str]
    hab_admin_adviser_resources: frozenset[str]
    hab_leo_priority_rules: Mapping[str, str]


def module_is_active(module: dict[str, Any]) -> bool:
    return (
        bool(module.get("templateName"))
        and bool(module.get("constructionCompleted"))
        and bool(module.get("powered"))
        and not module.get("destroyed")
        and not module.get("decommissioning")
    )


def faction_sector_states(indexed: IndexedState, faction: dict[str, Any]) -> list[dict[str, Any]]:
    refs = faction.get("habSectors") if isinstance(faction.get("habSectors"), list) else []
    sectors: list[dict[str, Any]] = []
    for sector_ref in refs:
        found = resolve_ref(indexed, sector_ref)
        if found:
            sectors.append(found[2])
    return sectors


def active_modules_in_sectors(indexed: IndexedState, sectors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    modules: list[dict[str, Any]] = []
    for sector in sectors:
        refs = sector.get("habModules") if isinstance(sector.get("habModules"), list) else []
        for module_ref in refs:
            found = resolve_ref(indexed, module_ref)
            if found and module_is_active(found[2]):
                modules.append(found[2])
    return modules


def hab_sector_states(indexed: IndexedState, hab: dict[str, Any]) -> list[dict[str, Any]]:
    refs = hab.get("sectors") if isinstance(hab.get("sectors"), list) else []
    sectors: list[dict[str, Any]] = []
    for sector_ref in refs:
        found = resolve_ref(indexed, sector_ref)
        if found:
            sectors.append(found[2])
    return sectors


def hab_module_records(
    indexed: IndexedState,
    hab: dict[str, Any],
    hab_module_templates: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    hab_faction_id = ref_id(hab.get("faction"))
    for sector in hab_sector_states(indexed, hab):
        sector_faction_id = ref_id(sector.get("faction"))
        sector_owned_by_hab = hab_faction_id is not None and sector_faction_id == hab_faction_id
        refs = sector.get("habModules") if isinstance(sector.get("habModules"), list) else []
        for slot, module_ref in enumerate(refs):
            found = resolve_ref(indexed, module_ref)
            if not found:
                continue
            module = found[2]
            template_name = module.get("templateName")
            template = hab_module_templates.get(template_name, {}) if template_name else {}
            prior_template_name = module.get("priorModuleTemplateName")
            prior_template = hab_module_templates.get(prior_template_name, {}) if prior_template_name else {}
            records.append(
                {
                    "id": ref_id(module.get("ID")),
                    "sectorId": ref_id(sector.get("ID")),
                    "sectorNum": sector.get("sectorNum"),
                    "sectorFaction": ref_summary(indexed, sector.get("faction")),
                    "sectorFactionId": sector_faction_id,
                    "habFactionId": hab_faction_id,
                    "sectorOwnedByHabFaction": sector_owned_by_hab,
                    "slot": slot,
                    "state": module,
                    "templateName": template_name,
                    "template": template,
                    "priorTemplateName": prior_template_name,
                    "priorTemplate": prior_template,
                    "display": module.get("displayName") or template.get("friendlyName") or template_name,
                    "completed": bool(module.get("constructionCompleted")),
                    "powered": bool(module.get("powered")),
                    "destroyed": bool(module.get("destroyed")),
                    "decommissioning": bool(module.get("decommissioning")),
                }
            )
    return records


def hab_module_empty(record: dict[str, Any]) -> bool:
    return not bool(record.get("templateName"))


def hab_slot_usable(record: dict[str, Any]) -> bool:
    return bool(record.get("sectorOwnedByHabFaction"))


def hab_slot_summary(records: list[dict[str, Any]]) -> dict[str, int]:
    raw = len(records)
    usable = sum(1 for record in records if hab_slot_usable(record))
    occupied = sum(1 for record in records if hab_slot_usable(record) and not hab_module_empty(record))
    empty = sum(1 for record in records if hab_slot_usable(record) and hab_module_empty(record))
    locked_empty = sum(1 for record in records if not hab_slot_usable(record) and hab_module_empty(record))
    return {
        "raw": raw,
        "usable": usable,
        "occupied": occupied,
        "empty": empty,
        "locked": raw - usable,
        "lockedEmpty": locked_empty,
    }


def hab_module_counts(records: list[dict[str, Any]]) -> dict[str, int]:
    module_counts: dict[str, int] = {}
    for record in records:
        if hab_module_okay(record):
            template_name = str(record.get("templateName"))
            module_counts[template_name] = module_counts.get(template_name, 0) + 1
    return module_counts


def hab_module_okay(record: dict[str, Any]) -> bool:
    return (
        not hab_module_empty(record)
        and not record.get("destroyed")
        and not record.get("decommissioning")
    )


def hab_module_functional(record: dict[str, Any]) -> bool:
    return bool(record.get("completed")) and not record.get("destroyed") and not record.get("decommissioning")


def hab_module_active_record(record: dict[str, Any]) -> bool:
    return hab_module_functional(record) and bool(record.get("powered"))


def hab_core_module_record(records: list[dict[str, Any]]) -> dict[str, Any] | None:
    for record in records:
        template = record.get("template") if isinstance(record.get("template"), dict) else {}
        if template.get("coreModule"):
            return record
    return records[0] if records else None


def hab_template_special_rules(template: dict[str, Any]) -> list[str]:
    return template.get("specialRules") if isinstance(template.get("specialRules"), list) else []


def hab_site_daily_production(
    hab_site: dict[str, Any] | None,
    resource: str,
    *,
    config: HabConfig,
) -> float:
    if not hab_site:
        return 0.0
    field = config.hab_site_production_fields.get(resource)
    return as_float(hab_site.get(field), 0.0) if field else 0.0


def faction_active_org_mining_bonus(
    indexed: IndexedState,
    faction: dict[str, Any],
    faction_councilor_ids: Callable[[dict[str, Any]], list[int]],
) -> float:
    total = 0.0
    for councilor_id in faction_councilor_ids(faction):
        councilor = state_value_by_id(indexed, councilor_id)
        if not councilor or councilor.get("detained") or councilor.get("isAlien"):
            continue
        org_refs = councilor.get("orgs") if isinstance(councilor.get("orgs"), list) else []
        for org_ref in org_refs:
            org = state_value_by_id(indexed, ref_id(org_ref))
            if isinstance(org, dict) and org.get("applyingBonuses"):
                total += as_float(org.get("miningBonus"), 0.0)
    return total


def faction_mining_multiplier(
    indexed: IndexedState,
    faction: dict[str, Any] | None,
    resource: str,
    effect_contexts: dict[str, list[str]],
    effect_templates: dict[str, dict[str, Any]],
    *,
    config: HabConfig,
    faction_councilor_ids: Callable[[dict[str, Any]], list[int]],
) -> float:
    if not faction:
        return 1.0
    value = 1.0 + faction_active_org_mining_bonus(indexed, faction, faction_councilor_ids)
    value = apply_effect_modifiers(effect_contexts, effect_templates, "SpaceMiningBonus", value)
    resource_context = config.mining_bonus_contexts.get(resource)
    if resource_context:
        value = apply_effect_modifiers(effect_contexts, effect_templates, resource_context, value)
    return value


def hab_template_income(
    resource: str,
    template: dict[str, Any],
    hab_has_construction: bool = False,
    *,
    indexed: IndexedState | None = None,
    faction: dict[str, Any] | None = None,
    hab_site: dict[str, Any] | None = None,
    effect_contexts: dict[str, list[str]] | None = None,
    effect_templates: dict[str, dict[str, Any]] | None = None,
    mining_rate: float = 1.0,
    config: HabConfig,
    faction_councilor_ids: Callable[[dict[str, Any]], list[int]],
) -> float:
    if "MoneyIfNotBuilding" in hab_template_special_rules(template) and hab_has_construction:
        return 0.0
    field = config.hab_income_fields.get(resource)
    income = as_float(template.get(field), 0.0) if field else 0.0
    if (
        resource in config.basic_space_resources
        and template.get("mine")
        and indexed is not None
        and faction is not None
        and hab_site is not None
    ):
        mining_multiplier = faction_mining_multiplier(
            indexed,
            faction,
            resource,
            effect_contexts or {},
            effect_templates or {},
            config=config,
            faction_councilor_ids=faction_councilor_ids,
        )
        income += (
            hab_site_daily_production(hab_site, resource, config=config)
            * as_float(template.get("miningModifier"), 1.0)
            * mining_multiplier
            * mining_rate
            * config.days_per_year
            / 12.0
        )
    return income


def hab_template_direct_support(
    resource: str,
    template: dict[str, Any],
    *,
    config: HabConfig,
) -> float:
    support = template.get("supportMaterials_month")
    if not isinstance(support, dict):
        return 0.0
    field = config.hab_support_fields.get(resource)
    return as_float(support.get(field), 0.0) if field else 0.0


def hab_template_crew_support(
    resource: str,
    template: dict[str, Any],
    *,
    config: HabConfig,
) -> float:
    crew = as_float(template.get("crew"), 0.0)
    rules = hab_template_special_rules(template)
    if resource == "Money":
        if "Stability" in rules:
            return 0.0
        return crew * config.default_global_config["crewSalary_year"] / 12.0
    if resource == "Water":
        return (
            crew
            * config.default_global_config["crewWaterConsumptionTons_year"]
            * config.default_global_config["spaceResourceToTons"]
            / 12.0
        )
    if resource == "Volatiles":
        return (
            crew
            * config.default_global_config["crewVolatilesConsumptionTons_year"]
            * config.default_global_config["spaceResourceToTons"]
            / 12.0
        )
    return 0.0


def hab_template_support(
    resource: str,
    template: dict[str, Any],
    include_crew_support: bool = True,
    *,
    config: HabConfig,
) -> float:
    total = hab_template_direct_support(resource, template, config=config)
    if include_crew_support:
        total += hab_template_crew_support(resource, template, config=config)
    return total


def hab_crew(records: list[dict[str, Any]]) -> int:
    return int(sum(as_float(record.get("template", {}).get("crew"), 0.0) for record in records if hab_module_okay(record)))


def hab_administration_modifier(records: list[dict[str, Any]]) -> float:
    modifier = 1.0
    for record in records:
        template = record.get("template") if isinstance(record.get("template"), dict) else {}
        if hab_module_active_record(record) and "Efficiency" in hab_template_special_rules(template):
            modifier *= 1.0 + as_float(template.get("specialRulesValue"), 0.0)
    return modifier


def hab_farm_crew_discount(records: list[dict[str, Any]], any_core_completed: bool) -> int:
    if not any_core_completed:
        return 0
    return int(
        sum(
            as_float(record.get("template", {}).get("specialRulesValue"), 0.0)
            for record in records
            if hab_module_active_record(record)
            and "Farm" in hab_template_special_rules(record.get("template", {}))
        )
    )


def hab_monthly_resource_income(
    hab: dict[str, Any],
    records: list[dict[str, Any]],
    resource: str,
    administration_modifier: float,
    science_adviser_multiplier: float = 1.0,
    administration_adviser_multiplier: float = 1.0,
    indexed: IndexedState | None = None,
    faction: dict[str, Any] | None = None,
    effect_contexts: dict[str, list[str]] | None = None,
    effect_templates: dict[str, dict[str, Any]] | None = None,
    mining_rate: float = 1.0,
    *,
    config: HabConfig,
    faction_councilor_ids: Callable[[dict[str, Any]], list[int]],
) -> dict[str, float]:
    income = 0.0
    support = 0.0
    farm_discount = 0
    crew = hab_crew(records)
    any_core_completed = bool(hab.get("anyCoreCompleted"))
    core_record = hab_core_module_record(records)
    core_id = core_record.get("id") if core_record else None
    has_construction = any(hab_module_okay(record) and not record.get("completed") for record in records)
    hab_site = state_value_by_id(indexed, ref_id(hab.get("habSite"))) if indexed is not None else None

    for record in records:
        if not hab_module_okay(record):
            continue
        template = record.get("template") if isinstance(record.get("template"), dict) else {}
        include_income_and_support = (
            (any_core_completed and hab_module_active_record(record))
            or (resource == "MissionControl" and record.get("id") == core_id)
        )
        if include_income_and_support:
            income += hab_template_income(
                resource,
                template,
                has_construction,
                indexed=indexed,
                faction=faction,
                hab_site=hab_site,
                effect_contexts=effect_contexts,
                effect_templates=effect_templates,
                mining_rate=mining_rate,
                config=config,
                faction_councilor_ids=faction_councilor_ids,
            )
            support += hab_template_support(resource, template, include_crew_support=True, config=config)
            if "Farm" in hab_template_special_rules(template):
                farm_discount += int(as_float(template.get("specialRulesValue"), 0.0))
        else:
            support += hab_template_crew_support(resource, template, config=config)

    if resource == "Water":
        covered_crew = min(farm_discount, crew)
        support -= (
            covered_crew
            * config.default_global_config["crewWaterConsumptionTons_year"]
            * config.default_global_config["spaceResourceToTons"]
            / 12.0
        )
    elif resource == "Volatiles":
        covered_crew = min(farm_discount, crew)
        support -= (
            covered_crew
            * config.default_global_config["crewVolatilesConsumptionTons_year"]
            * config.default_global_config["spaceResourceToTons"]
            / 12.0
        )

    if resource in config.hab_admin_adviser_resources:
        income *= administration_adviser_multiplier
        income *= administration_modifier
    elif resource == "Research":
        income *= science_adviser_multiplier
        income *= administration_modifier
    elif resource in {"Influence", "Operations", "Exotics"}:
        income *= administration_modifier

    support = max(support, 0.0)
    return {"income": income, "support": support, "net": income - support}


def hab_power_summary(records: list[dict[str, Any]]) -> dict[str, int]:
    generated = 0
    consumed = 0
    for record in records:
        if not hab_module_active_record(record):
            continue
        power = int(as_float(record.get("template", {}).get("power"), 0.0))
        if power > 0:
            generated += power
        elif power < 0:
            consumed += -power
    return {"consumed": consumed, "generated": generated, "net": generated - consumed}


def hab_tech_bonuses(records: list[dict[str, Any]]) -> dict[str, float]:
    bonuses: dict[str, float] = {}
    for record in records:
        if not hab_module_active_record(record):
            continue
        template = record.get("template") if isinstance(record.get("template"), dict) else {}
        for bonus in template.get("techBonuses") if isinstance(template.get("techBonuses"), list) else []:
            if not isinstance(bonus, dict):
                continue
            category = str(bonus.get("category"))
            bonuses[category] = bonuses.get(category, 0.0) + as_float(bonus.get("bonus"), 0.0)
    return bonuses


def hab_leo_priority_bonuses(
    hab: dict[str, Any],
    records: list[dict[str, Any]],
    *,
    config: HabConfig,
) -> dict[str, float]:
    if not hab.get("inEarthLEO"):
        return {}
    bonuses: dict[str, float] = {}
    for record in records:
        if not hab_module_active_record(record):
            continue
        template = record.get("template") if isinstance(record.get("template"), dict) else {}
        rules = hab_template_special_rules(template)
        for rule, priority in config.hab_leo_priority_rules.items():
            if rule in rules:
                bonuses[priority] = bonuses.get(priority, 0.0) + as_float(template.get("specialRulesValue"), 0.0)
    return bonuses


def hab_control_point_capacity(hab: dict[str, Any], records: list[dict[str, Any]]) -> int:
    total = 0
    for record in records:
        if not hab_module_active_record(record):
            continue
        template = record.get("template") if isinstance(record.get("template"), dict) else {}
        if not hab.get("inEarthLEO") and "LEOControlPointCapacity" in hab_template_special_rules(template):
            continue
        total += int(as_float(template.get("controlPointCapacity"), 0.0))
    return total
