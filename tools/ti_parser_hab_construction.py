"""Hab construction requirements, materials, completion and economic deltas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from ti_parser_config import (
    DAYS_PER_YEAR,
    DEFAULT_GLOBAL_CONFIG,
    HAB_INCOME_FIELDS,
    HAB_MONTHLY_RESOURCES,
    WORLD_MARKET_RESOURCES,
)
from ti_parser_core import (
    IndexedState,
    LocationCatalogError,
    as_float,
    clean_numbers,
    first_value,
    ref_id,
    state_value_by_id,
)
from ti_parser_hab_ui import (
    hab_barycenter_state,
    hab_construction_surface_body,
    hab_module_construction_time_modifier,
    hab_module_power,
    natural_space_object_sun_distance_au,
    space_body_relative_energy_for_mining,
    space_body_template,
)
from ti_parser_runtime import (
    active_modules_in_sectors,
    current_save_datetime,
    faction_sector_states,
    hab_administration_modifier,
    hab_core_module_record,
    hab_module_empty,
    hab_monthly_resource_income,
    hab_template_special_rules,
    required_catalog_row,
    state_adviser_attribute_bonus,
    ti_datetime,
)


def hab_projected_power_summary(
    records: list[dict[str, Any]],
    *,
    indexed: IndexedState | None = None,
    hab: dict[str, Any] | None = None,
    body_templates: dict[str, dict[str, Any]] | None = None,
    orbit_templates: dict[str, dict[str, Any]] | None = None,
) -> dict[str, int]:
    generated = 0
    consumed = 0
    for record in records:
        if hab_module_empty(record) or record.get("destroyed") or record.get("decommissioning"):
            continue
        power = hab_module_power(
            record.get("template", {}),
            indexed=indexed,
            hab=hab,
            body_templates=body_templates,
            orbit_templates=orbit_templates,
        )
        if power > 0:
            generated += power
        elif power < 0:
            consumed += -power
    return {"consumed": consumed, "generated": generated, "net": generated - consumed}


def hab_upgrade_info(records: list[dict[str, Any]]) -> dict[str, Any]:
    core = hab_core_module_record(records)
    if not core:
        return {"isUpgrading": False, "targetTier": None}
    template = core.get("template") if isinstance(core.get("template"), dict) else {}
    prior_template = core.get("priorTemplate") if isinstance(core.get("priorTemplate"), dict) else {}
    target_tier = int(as_float(template.get("tier"), 0.0)) or None
    prior_tier = int(as_float(prior_template.get("tier"), 0.0)) or None
    is_upgrading = (
        not bool(core.get("completed"))
        and bool(core.get("priorTemplateName"))
        and target_tier is not None
        and (prior_tier is None or target_tier > prior_tier)
    )
    state = core.get("state") if isinstance(core.get("state"), dict) else {}
    return {
        "isUpgrading": is_upgrading,
        "targetTier": target_tier,
        "coreTemplate": core.get("templateName"),
        "priorCoreTemplate": core.get("priorTemplateName"),
        "priorTier": prior_tier,
        "completionDate": state.get("completionDate"),
        "baseBuildDuration_days": state.get("baseBuildDuration_days"),
        "appliedBuildConstructionBonus": state.get("appliedBuildConstructionBonus"),
    }


def hab_planned_empty_slots(slots: dict[str, int], upgrade: dict[str, Any], current_tier: int | None) -> dict[str, int]:
    current_empty = int(slots.get("empty", 0))
    future_unlocks = 0
    target_tier = upgrade.get("targetTier")
    if upgrade.get("isUpgrading") and target_tier is not None and current_tier is not None and int(target_tier) > current_tier:
        future_unlocks = int(slots.get("lockedEmpty", 0))
    return {
        "currentUsableEmpty": current_empty,
        "futureUnlockedEmpty": future_unlocks,
        "plannedEmpty": current_empty + future_unlocks,
    }


def module_is_relevant_to_hab_type(template: dict[str, Any], hab: dict[str, Any]) -> bool:
    hab_type = template.get("habType") or "Any"
    return hab_type == "Any" or hab_type == hab.get("habType")


def module_has_economic_planning_value(template: dict[str, Any]) -> bool:
    if as_float(template.get("power"), 0.0) > 0.0:
        return True
    if as_float(template.get("missionControl"), 0.0) != 0.0:
        return True
    if as_float(template.get("controlPointCapacity"), 0.0) != 0.0:
        return True
    if template.get("techBonuses"):
        return True
    if any(as_float(template.get(field), 0.0) != 0.0 for field in HAB_INCOME_FIELDS.values()):
        return True
    rules = set(hab_template_special_rules(template))
    return bool(rules & {"Efficiency", "Farm", "Shipyard", "CanFoundTier1Habs", "CanFoundTier2Habs", "CanFoundTier3Habs"})


def hab_body_site_states(indexed: IndexedState, body: dict[str, Any]) -> list[dict[str, Any]]:
    refs = body.get("habSites") if isinstance(body.get("habSites"), list) else []
    sites: list[dict[str, Any]] = []
    for site_ref in refs:
        site = state_value_by_id(indexed, ref_id(site_ref))
        if site:
            sites.append(site)
    return sites


def hab_body_is_colonized(indexed: IndexedState, hab: dict[str, Any]) -> bool:
    if hab.get("habSite"):
        return True
    body = hab_barycenter_state(indexed, hab)
    if str(body.get("templateName") or "") == "Earth":
        return True
    return any(site.get("hab") for site in hab_body_site_states(indexed, body))


def hab_body_is_inhabited(indexed: IndexedState, hab: dict[str, Any]) -> bool:
    body = hab_barycenter_state(indexed, hab)
    if str(body.get("templateName") or "") == "Earth":
        return True
    return hab_body_is_colonized(indexed, hab)


def hab_body_is_irradiated(
    indexed: IndexedState,
    hab: dict[str, Any],
    body_templates: dict[str, dict[str, Any]] | None = None,
) -> bool:
    body = hab_barycenter_state(indexed, hab)
    template_name = str(body.get("templateName") or "")
    body_template = (
        required_catalog_row(
            indexed,
            body_templates or {},
            "location-body",
            template_name,
            "hab-planner.irradiation",
            "hab location references a body absent from the packaged location catalog",
        )
        if template_name
        else {}
    )
    return max(
        as_float(body.get("irradiatedMultiplier"), 1.0),
        as_float(body_template.get("irradiatedMultiplier"), 1.0),
    ) > 1.0


def module_one_per_hab_conflict_names(
    template: dict[str, Any],
    hab_module_templates: dict[str, dict[str, Any]] | None = None,
) -> set[str]:
    template_name = str(template.get("dataName") or "")
    conflict_names = {template_name} if template_name else set()
    if not hab_module_templates:
        return conflict_names

    upgrade_links: dict[str, set[str]] = {}
    mining_templates: set[str] = set()
    for catalog_name, catalog_template in hab_module_templates.items():
        name = str(catalog_template.get("dataName") or catalog_name or "")
        if not name:
            continue
        if catalog_template.get("mine"):
            mining_templates.add(name)
        prior_name = str(catalog_template.get("upgradesFromName") or "")
        if not prior_name:
            continue
        upgrade_links.setdefault(name, set()).add(prior_name)
        upgrade_links.setdefault(prior_name, set()).add(name)

    pending = list(conflict_names)
    while pending:
        name = pending.pop()
        for related_name in upgrade_links.get(name, set()):
            if related_name not in conflict_names:
                conflict_names.add(related_name)
                pending.append(related_name)

    if template.get("mine"):
        conflict_names.update(mining_templates)
    return conflict_names


def module_unmet_requirements(
    indexed: IndexedState,
    template: dict[str, Any],
    hab: dict[str, Any],
    faction: dict[str, Any],
    target_tier: int,
    module_counts: dict[str, int],
    body_templates: dict[str, dict[str, Any]] | None = None,
    hab_module_templates: dict[str, dict[str, Any]] | None = None,
) -> list[str]:
    reasons: list[str] = []
    template_name = str(template.get("dataName"))
    if template.get("coreModule"):
        reasons.append("core module")
    if template.get("alienModule"):
        reasons.append("alien module")
    if template.get("disable") or template.get("noBuild") or template.get("destroyed"):
        reasons.append("not normally buildable")
    if template.get("spaceCombatModule"):
        reasons.append("combat module outside economic planner")
    if template.get("objectiveModule") and not module_has_economic_planning_value(template):
        reasons.append("objective-only module outside economic planner")
    if not module_is_relevant_to_hab_type(template, hab):
        reasons.append(f"habType {template.get('habType')} only")
    if int(as_float(template.get("tier"), 0.0)) > target_tier:
        reasons.append("above target tier")
    required_project = template.get("requiredProjectName")
    finished_projects = faction.get("finishedProjectNames") if isinstance(faction.get("finishedProjectNames"), list) else []
    if required_project and required_project not in finished_projects:
        reasons.append(f"missing project {required_project}")
    if template.get("onePerHab"):
        conflict_names = module_one_per_hab_conflict_names(template, hab_module_templates)
        if any(module_counts.get(name, 0) > 0 for name in conflict_names):
            reasons.append("one per hab already present")

    rules = hab_template_special_rules(template)
    if "EarthLEOOnly" in rules and not hab.get("inEarthLEO"):
        reasons.append("Earth LEO only")
    if "Requires_Interface_Orbit" in rules and not hab.get("interfaceOrbit"):
        reasons.append("requires interface orbit")
    if "Requires_GasGiant_Orbit" in rules:
        location = hab_barycenter_state(indexed, hab)
        body = str(location.get("templateName") or "")
        if "Jupiter" not in body and "Saturn" not in body and "Uranus" not in body and "Neptune" not in body:
            reasons.append("requires gas giant orbit")
    if "Requires_Colonized_Body" in rules and not hab_body_is_colonized(indexed, hab):
        reasons.append("requires colonized body")
    if "Requires_Inhabited_Body" in rules and not hab_body_is_inhabited(indexed, hab):
        reasons.append("requires inhabited body")
    if "NotInIrradiated" in rules and hab_body_is_irradiated(indexed, hab, body_templates):
        reasons.append("not buildable on irradiated body")
    return reasons


def module_build_cost_map(template: dict[str, Any]) -> dict[str, float]:
    raw = template.get("weightedBuildMaterials")
    if not isinstance(raw, dict):
        raw = template.get("weightBuildMaterials")
    if not isinstance(raw, dict):
        return {}
    resource_names = {
        "money": "Money",
        "influence": "Influence",
        "ops": "Operations",
        "boost": "Boost",
        "water": "Water",
        "volatiles": "Volatiles",
        "metals": "Metals",
        "nobleMetals": "NobleMetals",
        "fissiles": "Fissiles",
        "antimatter": "Antimatter",
        "exotics": "Exotics",
    }
    return {
        resource_names[key]: as_float(value, 0.0)
        for key, value in raw.items()
        if key in resource_names and as_float(value, 0.0) > 0.0
    }


def resource_market_purchase_values(indexed: IndexedState) -> dict[str, float]:
    global_state = first_value(indexed, "TIGlobalValuesState") or {}
    values = global_state.get("resourceMarketValues") if isinstance(global_state.get("resourceMarketValues"), dict) else {}
    return {resource: as_float(values.get(resource), 0.0) for resource in WORLD_MARKET_RESOURCES}


def hab_irradiated_multiplier(
    indexed: IndexedState,
    hab: dict[str, Any],
    body_templates: dict[str, dict[str, Any]],
    orbit_templates: dict[str, dict[str, Any]],
) -> float:
    if hab.get("habType") == "Base" or hab.get("habSite"):
        return max(as_float(space_body_template(hab_construction_surface_body(indexed, hab), body_templates).get("irradiatedMultiplier"), 1.0), 1.0)
    orbit = state_value_by_id(indexed, ref_id(hab.get("orbitState"))) or {}
    orbit_name = str(orbit.get("templateName") or "")
    if not orbit_name:
        return 1.0
    orbit_template = orbit_templates.get(orbit_name)
    if orbit_template is None:
        raise LocationCatalogError(f"Orbit template {orbit_name!r} is missing from the packaged location catalog")
    return max(as_float(orbit_template.get("irradiatedMultiplier"), 1.0), 1.0)


def hab_module_mass_tons(
    indexed: IndexedState,
    hab: dict[str, Any],
    faction: dict[str, Any],
    template: dict[str, Any],
    body_templates: dict[str, dict[str, Any]],
    *,
    irradiated_multiplier: float = 1.0,
) -> float:
    mass = as_float(template.get("baseMass_tons"), 0.0)
    rules = hab_template_special_rules(template)
    body = hab_construction_surface_body(indexed, hab)
    if "Cost_Scales_With_Gravity" in rules and body:
        relative_energy = space_body_relative_energy_for_mining(indexed, body, faction, body_templates)
        mass = mass * 0.5 + mass * 0.5 * relative_energy
    if irradiated_multiplier > 1.0:
        mass *= irradiated_multiplier
    if "SolarMirror" in rules:
        distance_au = natural_space_object_sun_distance_au(indexed, hab_barycenter_state(indexed, hab), body_templates) or 0.0
        mass *= distance_au * distance_au
    return mass


def faction_has_helium3_access(indexed: IndexedState, faction: dict[str, Any]) -> bool:
    return any(
        str(module.get("templateName") or "") == "Helium-3Mine"
        for module in active_modules_in_sectors(indexed, faction_sector_states(indexed, faction))
    )


def hab_module_build_materials(
    indexed: IndexedState,
    hab: dict[str, Any],
    faction: dict[str, Any],
    template: dict[str, Any],
    body_templates: dict[str, dict[str, Any]],
    orbit_templates: dict[str, dict[str, Any]],
    *,
    is_upgrade: bool = False,
) -> dict[str, float]:
    weights = module_build_cost_map(template)
    irradiated_multiplier = hab_irradiated_multiplier(indexed, hab, body_templates, orbit_templates)
    nominal_mass = hab_module_mass_tons(indexed, hab, faction, template, body_templates)
    actual_mass = hab_module_mass_tons(
        indexed,
        hab,
        faction,
        template,
        body_templates,
        irradiated_multiplier=irradiated_multiplier,
    )
    multiplier = 2.0 / 3.0 if is_upgrade else 1.0
    scale = DEFAULT_GLOBAL_CONFIG["spaceResourceToTons"] * multiplier
    uses_helium3 = "UsesHelium3" in hab_template_special_rules(template) and faction_has_helium3_access(indexed, faction)
    result = {
        resource: amount * nominal_mass * scale
        for resource, amount in weights.items()
        if resource in WORLD_MARKET_RESOURCES and amount > 0.0 and not (uses_helium3 and resource == "Fissiles")
    }
    if uses_helium3 and weights.get("Fissiles", 0.0) > 0.0:
        result["Water"] = result.get("Water", 0.0) + weights["Fissiles"] * nominal_mass * scale
    radiation_metals = max(actual_mass - nominal_mass, 0.0) * scale
    if radiation_metals > 0.0:
        result["Metals"] = result.get("Metals", 0.0) + radiation_metals
    return result


def resource_cost_market_equivalent(cost: dict[str, float], market_values: dict[str, float]) -> float:
    return sum(amount * market_values.get(resource, 0.0) for resource, amount in cost.items())


def monthly_delta_market_equivalent(
    monthly_delta: dict[str, dict[str, float]],
    market_values: dict[str, float],
) -> float:
    total = as_float(monthly_delta.get("Money", {}).get("net"), 0.0)
    return total + sum(
        as_float(monthly_delta.get(resource, {}).get("net"), 0.0) * market_values.get(resource, 0.0)
        for resource in WORLD_MARKET_RESOURCES
    )


def module_affordable_with_materials(materials: dict[str, float], faction: dict[str, Any]) -> bool:
    return all(faction_stockpile(faction, resource) >= amount for resource, amount in materials.items())


def completion_datetime(value: Any) -> datetime | None:
    if isinstance(value, dict):
        return ti_datetime(value)
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.rstrip("Z"))
    except ValueError:
        return None


def hab_core_completion_minimum_days(
    indexed: IndexedState,
    hab: dict[str, Any],
    records: list[dict[str, Any]],
    template: dict[str, Any],
) -> float:
    core = hab_core_module_record(records)
    if not core or core.get("completed"):
        return 0.0
    core_template = core.get("template") if isinstance(core.get("template"), dict) else {}
    prior_core_template = core.get("priorTemplate") if isinstance(core.get("priorTemplate"), dict) else {}
    current_tier = as_float(hab.get("tier"), 0.0)
    if current_tier <= 0.0:
        current_tier = as_float(prior_core_template.get("tier"), 0.0) or as_float(core_template.get("tier"), 0.0)
    if current_tier > as_float(template.get("tier"), 0.0):
        return 0.0
    state = core.get("state") if isinstance(core.get("state"), dict) else {}
    completion = completion_datetime(state.get("completionDate"))
    current = current_save_datetime(indexed)
    if completion is None or current is None:
        return 0.0
    return max((completion - current).total_seconds() / 86400.0, 0.0)


def hab_module_construction_analysis(
    indexed: IndexedState,
    hab: dict[str, Any],
    records: list[dict[str, Any]],
    faction: dict[str, Any],
    template: dict[str, Any],
    body_templates: dict[str, dict[str, Any]],
    orbit_templates: dict[str, dict[str, Any]],
    *,
    is_upgrade: bool = False,
) -> dict[str, Any]:
    irradiated_multiplier = hab_irradiated_multiplier(indexed, hab, body_templates, orbit_templates)
    nominal_mass = hab_module_mass_tons(indexed, hab, faction, template, body_templates)
    actual_mass = hab_module_mass_tons(
        indexed,
        hab,
        faction,
        template,
        body_templates,
        irradiated_multiplier=irradiated_multiplier,
    )
    upgrade_discount = 2.0 / 3.0 if is_upgrade else 1.0
    construction_modifier = hab_module_construction_time_modifier(records)
    base_days = as_float(template.get("buildTime_Days"), 0.0)
    local_construction_days = base_days * upgrade_discount * construction_modifier
    core_completion_minimum_days = hab_core_completion_minimum_days(indexed, hab, records, template)
    materials = hab_module_build_materials(
        indexed,
        hab,
        faction,
        template,
        body_templates,
        orbit_templates,
        is_upgrade=is_upgrade,
    )
    market_values = resource_market_purchase_values(indexed)
    return clean_numbers(
        {
            "isUpgrade": is_upgrade,
            "baseBuildTime_Days": base_days,
            "upgradeDiscount": upgrade_discount,
            "habConstructionTimeModifier": construction_modifier,
            "localConstructionTime_Days": local_construction_days,
            "coreCompletionMinimum_Days": core_completion_minimum_days,
            "constructionTime_Days": max(local_construction_days, core_completion_minimum_days),
            "materials": materials,
            "affordableByCurrentStockpile": module_affordable_with_materials(materials, faction),
            "marketEquivalentMoney": resource_cost_market_equivalent(materials, market_values),
            "mass": {
                "beforeRadiation_tons": nominal_mass,
                "afterRadiation_tons": actual_mass,
                "radiationAdded_tons": max(actual_mass - nominal_mass, 0.0),
            },
            "penalties": {
                "irradiatedMultiplier": irradiated_multiplier,
                "gravityMassMultiplier": (nominal_mass / as_float(template.get("baseMass_tons"), 1.0)) if as_float(template.get("baseMass_tons"), 0.0) > 0.0 else 1.0,
            },
        },
        6,
    )


def module_break_even_analysis(
    construction: dict[str, Any],
    monthly_delta: dict[str, dict[str, float]],
    market_values: dict[str, float],
) -> dict[str, Any]:
    cost = construction.get("materials") if isinstance(construction.get("materials"), dict) else {}
    cost_value = as_float(construction.get("marketEquivalentMoney"), 0.0)
    monthly_value = monthly_delta_market_equivalent(monthly_delta, market_values)
    payback_months = cost_value / monthly_value if cost_value > 0.0 and monthly_value > 0.0 else None
    construction_months = as_float(construction.get("constructionTime_Days"), 0.0) / (DAYS_PER_YEAR / 12.0)
    return clean_numbers(
        {
            "constructionMarketEquivalentMoney": cost_value,
            "monthlyNetMarketEquivalentMoney": monthly_value,
            "paybackAfterCompletion_months": payback_months,
            "breakEvenFromStart_months": construction_months + payback_months if payback_months is not None else None,
            "resourceRecoveryAfterCompletion_months": {
                resource: amount / as_float(monthly_delta.get(resource, {}).get("net"), 0.0)
                for resource, amount in cost.items()
                if amount > 0.0 and as_float(monthly_delta.get(resource, {}).get("net"), 0.0) > 0.0
            },
            "valuationScope": "Money plus purchasable space resources at current market purchase prices; MC, research, projects, influence, operations, and strategic unlocks are excluded",
        },
        6,
    )


def faction_stockpile(faction: dict[str, Any], resource: str) -> float:
    resources = faction.get("resources") if isinstance(faction.get("resources"), dict) else {}
    return as_float(resources.get(resource), 0.0)


def module_affordable_with_template_weights(template: dict[str, Any], faction: dict[str, Any]) -> bool:
    return all(faction_stockpile(faction, resource) >= amount for resource, amount in module_build_cost_map(template).items())


def resource_scarcity_weights(topbar: dict[str, Any]) -> dict[str, float]:
    weights: dict[str, float] = {}
    resource_rows = topbar.get("resources") if isinstance(topbar.get("resources"), dict) else {}
    for resource in ("Money", "Boost", "Water", "Volatiles", "Metals", "NobleMetals", "Fissiles", "Antimatter", "Exotics"):
        row = resource_rows.get(resource) if isinstance(resource_rows.get(resource), dict) else {}
        monthly = as_float(row.get("monthly"), 0.0)
        current = as_float(row.get("current"), 0.0)
        weight = 1.0
        if monthly < 0.0:
            weight += 2.0
            months_left = current / abs(monthly) if current > 0.0 else 0.0
            if months_left < 12.0:
                weight += 2.0
        if resource in {"NobleMetals", "Fissiles", "Antimatter", "Exotics"}:
            weight += 1.0
        if resource == "Money":
            weight *= 0.05
        elif resource == "Boost":
            weight *= 0.5
        weights[resource] = weight
    return weights


def hypothetical_completed_module_record(
    template: dict[str, Any],
    prior_record: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        **(prior_record or {}),
        "templateName": str(template.get("dataName") or ""),
        "template": template,
        "completed": True,
        "powered": True,
        "destroyed": False,
        "decommissioning": False,
    }


def candidate_module_monthly_delta(
    indexed: IndexedState,
    hab: dict[str, Any],
    records: list[dict[str, Any]],
    faction: dict[str, Any],
    template: dict[str, Any],
    effect_contexts: dict[str, list[str]],
    effect_templates: dict[str, dict[str, Any]],
    mining_rate: float,
    councilor_by_id: dict[int, dict[str, Any]],
    prior_record: dict[str, Any] | None = None,
) -> dict[str, dict[str, float]]:
    science_adviser_multiplier = 1.0 + state_adviser_attribute_bonus(hab, councilor_by_id, "Science")
    administration_adviser_multiplier = 1.0 + state_adviser_attribute_bonus(hab, councilor_by_id, "Administration")
    if prior_record is None:
        after_records = records + [hypothetical_completed_module_record(template)]
    else:
        after_records = [
            hypothetical_completed_module_record(template, record) if record is prior_record else record
            for record in records
        ]
    before_administration_modifier = hab_administration_modifier(records)
    after_administration_modifier = hab_administration_modifier(after_records)

    deltas: dict[str, dict[str, float]] = {}
    for resource in HAB_MONTHLY_RESOURCES:
        before = hab_monthly_resource_income(
            hab,
            records,
            resource,
            before_administration_modifier,
            science_adviser_multiplier=science_adviser_multiplier,
            administration_adviser_multiplier=administration_adviser_multiplier,
            indexed=indexed,
            faction=faction,
            effect_contexts=effect_contexts,
            effect_templates=effect_templates,
            mining_rate=mining_rate,
        )
        after = hab_monthly_resource_income(
            hab,
            after_records,
            resource,
            after_administration_modifier,
            science_adviser_multiplier=science_adviser_multiplier,
            administration_adviser_multiplier=administration_adviser_multiplier,
            indexed=indexed,
            faction=faction,
            effect_contexts=effect_contexts,
            effect_templates=effect_templates,
            mining_rate=mining_rate,
        )
        income = as_float(after.get("income"), 0.0) - as_float(before.get("income"), 0.0)
        support = as_float(after.get("support"), 0.0) - as_float(before.get("support"), 0.0)
        net = as_float(after.get("net"), 0.0) - as_float(before.get("net"), 0.0)
        if income or support or net:
            deltas[resource] = {"income": income, "support": support, "net": net}
    return deltas
