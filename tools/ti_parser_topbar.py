"""Faction income aggregation, maintenance and resource forecasting."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from ti_parser_config import (
    BASIC_SPACE_RESOURCES,
    CP_MAINTENANCE_CAMPAIGN_START_GDP_FACTOR,
    DAYS_PER_YEAR,
    DEFAULT_CP_MAINTENANCE_GDP_SCALE,
    DEFAULT_GLOBAL_CONFIG,
    MINING_BONUS_CONTEXTS,
    TOPBAR_EFFECT_CONTEXTS,
    TOPBAR_RESOURCES,
)
from ti_parser_core import (
    IndexedState,
    apply_effect_modifiers,
    as_float,
    clean_numbers,
    effect_modifier_delta,
    faction_effect_contexts,
    find_faction_state,
    first_value,
    load_hab_module_catalog,
    load_location_catalog,
    location_catalog_diagnostics,
    module_catalog_diagnostics,
    raw_state_id,
    ref_id,
    state_value_by_id,
    type_entries,
)
from ti_parser_hab_construction import completion_datetime
from ti_parser_hab_ui import (
    hab_control_point_capacity,
    hab_power_summary,
)
from ti_parser_research import (
    ResearchTemplates,
    calculate_research_breakdown,
    faction_research_cache_key,
)
from ti_parser_runtime import (
    active_scenario_rules,
    calculation_catalogs,
    councilor_summary_maps,
    councilor_yearly_income,
    faction_active_org_mining_bonus,
    faction_councilor_ids,
    faction_hab_states,
    faction_is_player,
    faction_mining_multiplier,
    faction_mining_rate,
    faction_ship_designs,
    faction_ship_states,
    get_effective_module_state,
    hab_administration_modifier,
    hab_module_current_mission_control,
    hab_module_okay,
    hab_module_projected_mission_control,
    hab_module_records,
    hab_monthly_resource_income,
    hab_site_daily_production,
    nation_boost_contribution_month,
    nation_influence_contribution_month,
    nation_mission_control_contribution,
    nation_money_contribution_month,
    nation_research_contribution_month,
    required_catalog_row,
    scenario_float,
    state_adviser_attribute_bonus,
    ti_datetime,
)


def faction_yearly_income_from_ships(
    indexed: IndexedState,
    templates_dir: Path | None,
    faction: dict[str, Any],
    resource: str,
) -> float:
    if resource != "Money":
        return 0.0
    ships = faction_ship_states(indexed, faction)
    if not ships:
        return 0.0
    hull_templates = calculation_catalogs(indexed, "topbar.ship-income").ships["hulls"]
    designs = faction_ship_designs(faction)
    monthly = 0.0
    for ship in ships:
        design_name = str(ship.get("templateName") or "")
        design = required_catalog_row(indexed, designs, "ship-design", design_name, "topbar.ship-income")
        hull = required_catalog_row(indexed, hull_templates, "ship-hull", design.get("hullName"), "topbar.ship-income")
        monthly += as_float(hull.get("monthlyIncome_Money"), 0.0)
    return monthly * 12.0


def faction_yearly_income_from_diplomacy(indexed: IndexedState, faction_id: int, faction: dict[str, Any], resource: str) -> float:
    daily = 0.0
    for transfer in faction.get("dailyResourceTransfers") if isinstance(faction.get("dailyResourceTransfers"), list) else []:
        if not isinstance(transfer, dict):
            continue
        transfer_value = transfer.get("transfer") if isinstance(transfer.get("transfer"), dict) else transfer
        if transfer_value.get("resource") == resource:
            daily -= as_float(transfer_value.get("value"), 0.0)
    for entry in type_entries(indexed, "TIFactionState"):
        other = entry.get("Value") or {}
        other_id = raw_state_id(entry)
        if other_id == faction_id:
            continue
        for transfer in other.get("dailyResourceTransfers") if isinstance(other.get("dailyResourceTransfers"), list) else []:
            if not isinstance(transfer, dict) or ref_id(transfer.get("targetFaction")) != faction_id:
                continue
            transfer_value = transfer.get("transfer") if isinstance(transfer.get("transfer"), dict) else transfer
            if transfer_value.get("resource") == resource:
                daily += as_float(transfer_value.get("value"), 0.0)
    return daily * DAYS_PER_YEAR


def faction_negative_yearly_income_from_unassigned_orgs(indexed: IndexedState, faction: dict[str, Any], resource: str) -> float:
    if resource not in {"Money", "Influence", "Operations", "Boost", "MissionControl"}:
        return 0.0
    field = {
        "Money": "incomeMoney_month",
        "Influence": "incomeInfluence_month",
        "Operations": "incomeOps_month",
        "Boost": "incomeBoost_month",
        "MissionControl": "incomeMissionControl",
    }[resource]
    monthly = 0.0
    for org_ref in faction.get("unassignedOrgs") if isinstance(faction.get("unassignedOrgs"), list) else []:
        org = state_value_by_id(indexed, ref_id(org_ref))
        value = as_float(org.get(field), 0.0) if isinstance(org, dict) else 0.0
        if value < 0.0:
            monthly += value
    return monthly if resource == "MissionControl" else monthly * 12.0


def faction_yearly_income_from_councilors(
    indexed: IndexedState,
    faction: dict[str, Any],
    trait_templates: dict[str, dict[str, Any]],
    councilor_by_id: dict[int, dict[str, Any]],
    resource: str,
) -> float:
    total = 0.0
    for councilor_id in faction_councilor_ids(faction):
        councilor = state_value_by_id(indexed, councilor_id)
        if not councilor:
            continue
        summary = councilor_by_id.get(councilor_id, {})
        final_attributes = summary.get("finalAttributes") if isinstance(summary.get("finalAttributes"), dict) else {}
        total += councilor_yearly_income(indexed, councilor, trait_templates, final_attributes, resource)
    return total


def faction_yearly_income_from_nations(
    indexed: IndexedState,
    faction_id: int,
    faction: dict[str, Any],
    councilor_by_id: dict[int, dict[str, Any]],
    effect_contexts: dict[str, list[str]],
    effect_templates: dict[str, dict[str, Any]],
    resource: str,
) -> float:
    if resource not in {"Money", "Influence", "Boost", "Research", "MissionControl"}:
        return 0.0
    total_month = 0.0
    for entry in type_entries(indexed, "TINationState"):
        nation = entry.get("Value") or {}
        if resource == "Money":
            total_month += nation_money_contribution_month(indexed, nation, faction_id)
        elif resource == "Boost":
            total_month += nation_boost_contribution_month(indexed, nation, faction_id)
        elif resource == "Research":
            total_month += nation_research_contribution_month(
                indexed,
                nation,
                faction_id,
                councilor_by_id,
                effect_contexts,
                effect_templates,
            )
        elif resource == "MissionControl":
            total_month += nation_mission_control_contribution(indexed, nation, faction_id)
        elif resource == "Influence":
            total_month += nation_influence_contribution_month(
                indexed,
                nation,
                faction,
                effect_contexts,
                effect_templates,
            )
    return total_month if resource == "MissionControl" else total_month * 12.0


def faction_yearly_income_from_habs(
    indexed: IndexedState,
    templates_dir: Path | None,
    faction: dict[str, Any],
    effect_contexts: dict[str, list[str]],
    effect_templates: dict[str, dict[str, Any]],
    councilor_by_id: dict[int, dict[str, Any]],
    resource: str,
) -> float:
    hab_module_templates = load_hab_module_catalog()
    total_month = 0.0
    for _, hab in faction_hab_states(indexed, faction):
        records = hab_module_records(indexed, hab, hab_module_templates)
        administration_modifier = hab_administration_modifier(records)
        monthly = hab_monthly_resource_income(
            hab,
            records,
            resource,
            administration_modifier,
            science_adviser_multiplier=1.0 + state_adviser_attribute_bonus(hab, councilor_by_id, "Science"),
            administration_adviser_multiplier=1.0 + state_adviser_attribute_bonus(hab, councilor_by_id, "Administration"),
            indexed=indexed,
            faction=faction,
            effect_contexts=effect_contexts,
            effect_templates=effect_templates,
            mining_rate=faction_mining_rate(indexed, faction),
        )
        total_month += monthly["net"]
    return total_month if resource in {"Projects", "MissionControl"} else total_month * 12.0


def faction_max_mission_control_components(
    indexed: IndexedState,
    templates_dir: Path | None,
    faction_id: int,
    faction: dict[str, Any],
    trait_templates: dict[str, dict[str, Any]],
    councilor_by_id: dict[int, dict[str, Any]],
    effect_contexts: dict[str, list[str]],
    effect_templates: dict[str, dict[str, Any]],
    hab_module_templates: dict[str, dict[str, Any]] | None = None,
) -> dict[str, float]:
    base_incomes = faction.get("baseIncomes_year") if isinstance(faction.get("baseIncomes_year"), dict) else {}
    hq = as_float(base_incomes.get("MissionControl"), 0.0) + scenario_float(indexed, "missionControlBonus", 0.0)
    councilors = faction_yearly_income_from_councilors(indexed, faction, trait_templates, councilor_by_id, "MissionControl")
    nations = faction_yearly_income_from_nations(indexed, faction_id, faction, councilor_by_id, effect_contexts, effect_templates, "MissionControl")
    habs = 0.0
    hab_module_templates = hab_module_templates if hab_module_templates is not None else load_hab_module_catalog()
    for _, hab in faction_hab_states(indexed, faction):
        for record in hab_module_records(indexed, hab, hab_module_templates):
            value = hab_module_current_mission_control(record)
            if value > 0:
                habs += value
    pre_effect = hq + councilors + nations + habs
    total = apply_effect_modifiers(effect_contexts, effect_templates, "MissionControlDisruption_PCT", pre_effect)
    return {
        "HQ": hq,
        "councilors": councilors,
        "nations": nations,
        "habs": habs,
        "effects": total - pre_effect,
        "total": total,
    }


def faction_queued_mission_control_changes(
    indexed: IndexedState,
    faction: dict[str, Any],
    hab_module_templates: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    capacity_change = 0
    usage_change = 0
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for _, hab in faction_hab_states(indexed, faction):
        for record in hab_module_records(indexed, hab, hab_module_templates):
            if record.get("completed") or not hab_module_okay(record):
                continue
            current = hab_module_current_mission_control(record)
            projected = hab_module_projected_mission_control(record)
            record_capacity_change = max(projected, 0) - max(current, 0)
            record_usage_change = max(-projected, 0) - max(-current, 0)
            if record_capacity_change == 0 and record_usage_change == 0:
                continue
            template_name = str(record.get("templateName") or "")
            prior_template_name = str(record.get("priorTemplateName") or "")
            row = grouped.setdefault(
                (template_name, prior_template_name),
                {
                    "template": template_name,
                    "priorTemplate": prior_template_name or None,
                    "count": 0,
                    "capacityChange": 0,
                    "usageChange": 0,
                    "headroomChange": 0,
                },
            )
            row["count"] += 1
            row["capacityChange"] += record_capacity_change
            row["usageChange"] += record_usage_change
            row["headroomChange"] += record_capacity_change - record_usage_change
            capacity_change += record_capacity_change
            usage_change += record_usage_change
    return {
        "capacityChange": capacity_change,
        "usageChange": usage_change,
        "headroomChange": capacity_change - usage_change,
        "moduleChanges": sorted(
            grouped.values(),
            key=lambda row: (str(row.get("template") or ""), str(row.get("priorTemplate") or "")),
        ),
    }


def mission_control_available_for_planning(topbar: dict[str, Any]) -> float:
    resources = topbar.get("resources") if isinstance(topbar.get("resources"), dict) else {}
    mission_control = resources.get("MissionControl") if isinstance(resources.get("MissionControl"), dict) else {}
    projected = (
        mission_control.get("projectedAfterCurrentQueue")
        if isinstance(mission_control.get("projectedAfterCurrentQueue"), dict)
        else {}
    )
    return as_float(projected.get("available", mission_control.get("available")), 0.0)


def faction_excess_mission_control_yearly_income(
    mc_components: dict[str, float],
    faction: dict[str, Any],
    resource: str,
) -> float:
    if resource not in {"Money", "Research"}:
        return 0.0
    max_buildable = mc_components.get("councilors", 0.0) + mc_components.get("nations", 0.0) + mc_components.get("habs", 0.0)
    available = max(mc_components.get("total", 0.0) - as_float(faction.get("missionControlUsage"), 0.0), 0.0)
    excess = min(max_buildable, available)
    conversion = (
        DEFAULT_GLOBAL_CONFIG["ExcessMCToMoneyConversion_Day"]
        if resource == "Money"
        else DEFAULT_GLOBAL_CONFIG["ExcessMCToResearchConversion_Day"]
    )
    return excess * DAYS_PER_YEAR * conversion


def control_point_maintenance_gdp_scale(indexed: IndexedState) -> float:
    global_state = first_value(indexed, "TIGlobalValuesState") or {}
    fixed_scale = as_float(global_state.get("fixedPCGDPToRaiseBaseCPMaintenanceCostBy1"), 0.0)
    if fixed_scale > 0.0:
        return fixed_scale
    campaign_start_gdp = as_float(global_state.get("globalGDP_CampaignStart"), 0.0)
    if campaign_start_gdp > 0.0:
        return campaign_start_gdp * CP_MAINTENANCE_CAMPAIGN_START_GDP_FACTOR
    return DEFAULT_CP_MAINTENANCE_GDP_SCALE


def nation_control_point_maintenance_cost(
    nation: dict[str, Any],
    scenario_multiplier: float = 1.0,
    gdp_scale: float = DEFAULT_CP_MAINTENANCE_GDP_SCALE,
) -> float:
    control_points = max(int(as_float(nation.get("numControlPoints"), 0.0)), 1)
    gdp = as_float(nation.get("GDP"), 0.0)
    if gdp <= 0.0:
        return 0.0
    resolved_gdp_scale = gdp_scale if gdp_scale > 0.0 else DEFAULT_CP_MAINTENANCE_GDP_SCALE
    scaled_gdp = gdp / resolved_gdp_scale
    return scenario_multiplier * (scaled_gdp ** DEFAULT_GLOBAL_CONFIG["controlPointCostScaling"]) / (
        DEFAULT_GLOBAL_CONFIG["controlPointMaintenanceDivisor"] * control_points
    )


def faction_control_point_maintenance(
    indexed: IndexedState,
    templates_dir: Path | None,
    faction_id: int,
    faction: dict[str, Any],
    councilor_by_id: dict[int, dict[str, Any]],
    effect_contexts: dict[str, list[str]],
    effect_templates: dict[str, dict[str, Any]],
) -> dict[str, float]:
    scenario_rules = active_scenario_rules(indexed)
    gdp_scale = control_point_maintenance_gdp_scale(indexed)
    baseline = 0.0
    for cp_ref in faction.get("controlPoints") if isinstance(faction.get("controlPoints"), list) else []:
        cp = state_value_by_id(indexed, ref_id(cp_ref))
        if not isinstance(cp, dict) or cp.get("benefitsDisabled"):
            continue
        nation = state_value_by_id(indexed, ref_id(cp.get("nation")))
        if isinstance(nation, dict):
            baseline += nation_control_point_maintenance_cost(
                nation,
                scenario_rules.control_point_maintenance_multiplier,
                gdp_scale,
            )

    global_state = first_value(indexed, "TIGlobalValuesState") or {}
    global_freebies = as_float(global_state.get("controlPointMaintenanceFreebies"), 125.0)
    councilors = 0.0
    for councilor_id in faction_councilor_ids(faction):
        summary = councilor_by_id.get(councilor_id, {})
        final_attributes = summary.get("finalAttributes") if isinstance(summary.get("finalAttributes"), dict) else {}
        councilors += (
            as_float(final_attributes.get("Persuasion"), 0.0)
            + as_float(final_attributes.get("Command"), 0.0)
            + as_float(final_attributes.get("Administration"), 0.0)
        )

    habs = 0.0
    hab_module_templates = load_hab_module_catalog()
    for _, hab in faction_hab_states(indexed, faction):
        habs += hab_control_point_capacity(hab, hab_module_records(indexed, hab, hab_module_templates))

    cp_effect_names = effect_contexts.get("ControlPointMaintenance", [])
    missing_effects = sorted({name for name in cp_effect_names if name not in effect_templates})
    if missing_effects:
        raise RuntimeError(
            "Control-point capacity effects are missing template data: " + ", ".join(missing_effects)
        )
    effect_delta = effect_modifier_delta(effect_contexts, effect_templates, "ControlPointMaintenance", global_freebies)
    cap = global_freebies + councilors + habs - effect_delta
    breakdown = {
        "base": global_freebies,
        "councilors": councilors,
        "projectFactionEffects": -effect_delta,
        "habModules": habs,
        "scenarioModifiers": 0.0,
        "difficultyModifiers": 0.0,
    }
    overage = max(baseline - cap, 0.0)
    return {
        "usage": baseline,
        "cap": cap,
        "overage": overage,
        "annualInfluenceCost": overage * overage,
        "missionPenaltyRecent": (faction.get("history_CPCapOverageByDay") or [0.0])[0],
        "missionPenaltyCurrent": overage * DEFAULT_GLOBAL_CONFIG["TIMissionModifier_ControlPointOverage_Multiplier"],
        "breakdown": breakdown,
        "effectProvenance": [
            {
                "name": name,
                "operation": effect_templates[name].get("operation"),
                "value": as_float(effect_templates[name].get("value"), 0.0),
            }
            for name in cp_effect_names
        ],
        "components": {
            "scenarioMultiplier": scenario_rules.control_point_maintenance_multiplier,
            "gdpScale": gdp_scale,
            "globalFreebies": global_freebies,
            "councilors": councilors,
            "habs": habs,
            "effects": -effect_delta,
        },
    }


def faction_resource_components_yearly(
    indexed: IndexedState,
    templates_dir: Path | None,
    faction_id: int,
    faction: dict[str, Any],
    trait_templates: dict[str, dict[str, Any]],
    effect_contexts: dict[str, list[str]],
    effect_templates: dict[str, dict[str, Any]],
    councilor_by_id: dict[int, dict[str, Any]],
    mc_components: dict[str, float],
    cp_maintenance: dict[str, float],
    resource: str,
) -> dict[str, float]:
    base_incomes = faction.get("baseIncomes_year") if isinstance(faction.get("baseIncomes_year"), dict) else {}
    components = {
        "HQ": as_float(base_incomes.get(resource), 0.0),
        "nations": faction_yearly_income_from_nations(indexed, faction_id, faction, councilor_by_id, effect_contexts, effect_templates, resource),
        "councilors": faction_yearly_income_from_councilors(indexed, faction, trait_templates, councilor_by_id, resource),
        "habs": faction_yearly_income_from_habs(indexed, templates_dir, faction, effect_contexts, effect_templates, councilor_by_id, resource),
        "ships": faction_yearly_income_from_ships(indexed, templates_dir, faction, resource),
        "diplomacy": faction_yearly_income_from_diplomacy(indexed, faction_id, faction, resource),
        "unassignedOrgs": faction_negative_yearly_income_from_unassigned_orgs(indexed, faction, resource),
        "excessMissionControl": faction_excess_mission_control_yearly_income(mc_components, faction, resource),
    }
    if resource == "Influence":
        components["controlPointMaintenance"] = -as_float(cp_maintenance.get("annualInfluenceCost"), 0.0)
    return components


def faction_hab_resource_at_date(
    indexed: IndexedState,
    faction: dict[str, Any],
    hab_module_templates: dict[str, dict[str, Any]],
    effect_contexts: dict[str, list[str]],
    effect_templates: dict[str, dict[str, Any]],
    councilor_by_id: dict[int, dict[str, Any]],
    resource: str,
    at_date: datetime,
) -> dict[str, float]:
    production = 0.0
    consumption = 0.0
    for _, hab in faction_hab_states(indexed, faction):
        records = hab_module_records(indexed, hab, hab_module_templates)
        monthly = hab_monthly_resource_income(
            hab,
            records,
            resource,
            hab_administration_modifier(records, at_date),
            science_adviser_multiplier=1.0 + state_adviser_attribute_bonus(hab, councilor_by_id, "Science"),
            administration_adviser_multiplier=1.0 + state_adviser_attribute_bonus(hab, councilor_by_id, "Administration"),
            indexed=indexed,
            faction=faction,
            effect_contexts=effect_contexts,
            effect_templates=effect_templates,
            mining_rate=faction_mining_rate(indexed, faction),
            at_date=at_date,
        )
        production += as_float(monthly.get("income"), 0.0)
        consumption += as_float(monthly.get("support"), 0.0)
    return {"production": production, "consumption": consumption, "net": production - consumption}


def first_sustained_surplus_date(events: list[dict[str, Any]]) -> str | None:
    for index, event in enumerate(events):
        if as_float(event.get("net"), 0.0) > 0.0 and all(
            as_float(later.get("net"), 0.0) > 0.0 for later in events[index:]
        ):
            return str(event.get("date"))
    return None


def faction_mining_calculation_samples(
    indexed: IndexedState,
    faction: dict[str, Any],
    hab_module_templates: dict[str, dict[str, Any]],
    effect_contexts: dict[str, list[str]],
    effect_templates: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    org_bonus = faction_active_org_mining_bonus(indexed, faction)
    mining_rate = faction_mining_rate(indexed, faction)
    for _, hab in faction_hab_states(indexed, faction):
        site = state_value_by_id(indexed, ref_id(hab.get("habSite")))
        if not isinstance(site, dict):
            continue
        for record in hab_module_records(indexed, hab, hab_module_templates):
            effective = get_effective_module_state(record)
            template = effective.get("operationalTemplate")
            if not isinstance(template, dict) or not template.get("mine"):
                continue
            module_multiplier = as_float(template.get("miningModifier"), 1.0)
            for resource in BASIC_SPACE_RESOURCES:
                site_yield = hab_site_daily_production(site, resource)
                if site_yield <= 0.0:
                    continue
                faction_multiplier = faction_mining_multiplier(
                    indexed,
                    faction,
                    resource,
                    effect_contexts,
                    effect_templates,
                )
                final_daily = site_yield * module_multiplier * faction_multiplier * mining_rate
                samples.append(
                    {
                        "hab": hab.get("displayName") or hab.get("templateName"),
                        "resource": resource,
                        "siteYieldPerDay": site_yield,
                        "module": effective.get("templateName"),
                        "moduleMultiplier": module_multiplier,
                        "activeOrgBonus": org_bonus,
                        "factionEffectNames": (
                            effect_contexts.get("SpaceMiningBonus", [])
                            + effect_contexts.get(MINING_BONUS_CONTEXTS.get(resource, ""), [])
                        ),
                        "factionMultiplier": faction_multiplier,
                        "scenarioMiningRate": mining_rate,
                        "finalPerDay": final_daily,
                        "monthly": final_daily * DAYS_PER_YEAR / 12.0,
                    }
                )
    selected: list[dict[str, Any]] = []
    for resource in BASIC_SPACE_RESOURCES:
        candidates = [row for row in samples if row["resource"] == resource]
        if candidates:
            selected.append(max(candidates, key=lambda row: as_float(row.get("monthly"), 0.0)))
    return clean_numbers(selected, 6)


def forecast_faction_hab_resource(
    indexed: IndexedState,
    faction: dict[str, Any],
    hab_module_templates: dict[str, dict[str, Any]],
    effect_contexts: dict[str, list[str]],
    effect_templates: dict[str, dict[str, Any]],
    councilor_by_id: dict[int, dict[str, Any]],
    resource: str,
    *,
    body_templates: dict[str, dict[str, Any]] | None = None,
    orbit_templates: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    time_state = first_value(indexed, "TITimeState") or {}
    current = ti_datetime(time_state.get("currentDateTime"))
    if current is None:
        raise RuntimeError("Cannot forecast module completions: TITimeState.currentDateTime is missing or invalid.")

    grouped: dict[datetime, list[dict[str, Any]]] = {}
    hab_by_id: dict[int, dict[str, Any]] = {}
    records_by_hab: dict[int, list[dict[str, Any]]] = {}
    for hab_id, hab in faction_hab_states(indexed, faction):
        hab_by_id[hab_id] = hab
        records = hab_module_records(indexed, hab, hab_module_templates)
        records_by_hab[hab_id] = records
        for record in records:
            if not hab_module_okay(record) or record.get("completed"):
                continue
            completion = completion_datetime((record.get("state") or {}).get("completionDate"))
            if completion is None or completion <= current:
                continue
            grouped.setdefault(completion, []).append({"habId": hab_id, "record": record})

    rows: list[dict[str, Any]] = []
    previous = faction_hab_resource_at_date(
        indexed,
        faction,
        hab_module_templates,
        effect_contexts,
        effect_templates,
        councilor_by_id,
        resource,
        current,
    )
    rows.append(
        {
            "date": current.isoformat(),
            **previous,
            "changeFromPrior": 0.0,
            "moduleCompletions": [],
        }
    )

    for event_date in sorted(grouped):
        current_values = faction_hab_resource_at_date(
            indexed,
            faction,
            hab_module_templates,
            effect_contexts,
            effect_templates,
            councilor_by_id,
            resource,
            event_date,
        )
        completions: list[dict[str, Any]] = []
        power_rows: list[dict[str, Any]] = []
        impacted_habs = sorted({int(item["habId"]) for item in grouped[event_date]})
        for item in grouped[event_date]:
            record = item["record"]
            hab = hab_by_id[int(item["habId"])]
            completions.append(
                {
                    "hab": hab.get("displayName") or hab.get("templateName") or item["habId"],
                    "module": record.get("display") or record.get("templateName"),
                    "template": record.get("templateName"),
                    "priorTemplate": record.get("priorTemplateName") or None,
                }
            )
        for hab_id in impacted_habs:
            hab = hab_by_id[hab_id]
            power_rows.append(
                {
                    "hab": hab.get("displayName") or hab.get("templateName") or hab_id,
                    **hab_power_summary(
                        records_by_hab[hab_id],
                        indexed=indexed,
                        hab=hab,
                        body_templates=body_templates,
                        orbit_templates=orbit_templates,
                        at_date=event_date,
                    ),
                }
            )
        power_warnings = [
            f"Projected powered module set exceeds generation at {row['hab']} by {-int(row['net'])}."
            for row in power_rows
            if int(row.get("net", 0)) < 0
        ]
        rows.append(
            {
                "date": event_date.isoformat(),
                **current_values,
                "changeFromPrior": current_values["net"] - previous["net"],
                "moduleCompletions": completions,
                "powerAfterEvent": power_rows,
                "status": "incomplete" if power_warnings else "complete",
                "warnings": power_warnings,
            }
        )
        previous = current_values

    incomplete = any(row.get("status") == "incomplete" for row in rows)
    return {
        "resource": resource,
        "scope": "faction hab production and consumption only",
        "status": "incomplete" if incomplete else "complete",
        "events": clean_numbers(rows, 6),
        "firstSustainedSurplusDate": first_sustained_surplus_date(rows),
        "warnings": [
            warning
            for row in rows
            for warning in row.get("warnings", [])
        ],
    }


def calculate_topbar(
    indexed: IndexedState,
    templates_dir: Path | None,
    faction_name: str | None = None,
    include_details: bool = False,
    *,
    research_templates: ResearchTemplates | None = None,
    base_daily_cache: dict[int, float] | None = None,
    include_diagnostics: bool = False,
    forecast_resource: str | None = None,
) -> dict[str, Any]:
    runtime_catalogs = calculation_catalogs(indexed, "topbar") if research_templates is None else None
    trait_templates = research_templates.traits if research_templates else runtime_catalogs.traits
    effect_templates = research_templates.effects if research_templates else runtime_catalogs.effects
    hab_module_templates = research_templates.hab_modules if research_templates else load_hab_module_catalog()
    faction_id, faction = find_faction_state(indexed, faction_name)
    effect_contexts = faction_effect_contexts(indexed, faction_id)
    for context in sorted(TOPBAR_EFFECT_CONTEXTS):
        for name in effect_contexts.get(context, []):
            required_catalog_row(indexed, effect_templates, "effect", name, f"topbar.{context}")
    _, councilor_by_id = councilor_summary_maps(indexed, trait_templates)
    mc_components = faction_max_mission_control_components(
        indexed,
        templates_dir,
        faction_id,
        faction,
        trait_templates,
        councilor_by_id,
        effect_contexts,
        effect_templates,
        hab_module_templates,
    )
    queued_mc = faction_queued_mission_control_changes(indexed, faction, hab_module_templates)
    cp_maintenance = faction_control_point_maintenance(
        indexed,
        templates_dir,
        faction_id,
        faction,
        councilor_by_id,
        effect_contexts,
        effect_templates,
    )

    resources = faction.get("resources") if isinstance(faction.get("resources"), dict) else {}
    rows: dict[str, Any] = {}
    for resource in TOPBAR_RESOURCES:
        if resource == "MissionControl":
            usage = as_float(faction.get("missionControlUsage"), 0.0)
            capacity = as_float(mc_components.get("total"), 0.0)
            hab_capacity_change = as_float(queued_mc.get("capacityChange"), 0.0)
            pre_effect_capacity = capacity - as_float(mc_components.get("effects"), 0.0)
            projected_capacity = apply_effect_modifiers(
                effect_contexts,
                effect_templates,
                "MissionControlDisruption_PCT",
                pre_effect_capacity + hab_capacity_change,
            )
            projected_usage = usage + as_float(queued_mc.get("usageChange"), 0.0)
            effective_capacity_change = projected_capacity - capacity
            projected = {
                "capacity": projected_capacity,
                "usage": projected_usage,
                "available": max(projected_capacity - projected_usage, 0.0),
                "capacityChange": effective_capacity_change,
                "habCapacityChange": hab_capacity_change,
                "effectsChange": effective_capacity_change - hab_capacity_change,
                "usageChange": queued_mc.get("usageChange", 0),
                "headroomChange": effective_capacity_change - as_float(queued_mc.get("usageChange"), 0.0),
                "moduleChanges": queued_mc.get("moduleChanges", []) if include_details else None,
            }
            if not include_details:
                projected.pop("moduleChanges")
            rows[resource] = clean_numbers(
                {
                    "usage": usage,
                    "capacity": capacity,
                    "available": max(capacity - usage, 0.0),
                    "projectedAfterCurrentQueue": projected,
                    "components": mc_components if include_details else None,
                },
                6,
            )
            if not include_details:
                rows[resource].pop("components", None)
            continue
        if resource == "Research":
            research = calculate_research_breakdown(
                indexed,
                templates_dir,
                faction_name,
                include_details=include_details,
                templates=research_templates,
            )
            if base_daily_cache is not None:
                base_daily_cache[faction_research_cache_key(faction)] = as_float(
                    research["daily"]["beforeDistribution"],
                    0.0,
                )
            rows[resource] = {
                "current": as_float(resources.get(resource), 0.0),
                "daily": research["daily"]["total"],
                "monthly": research["monthly"]["total"],
                "yearly": research["annual"]["total"],
                "beforeDistributionDaily": research["daily"]["beforeDistribution"],
                "distributionBonusDaily": research["daily"]["distributionBonus"],
            }
            if include_details:
                rows[resource]["componentsDaily"] = research["daily"]["bySource"]
            rows[resource] = clean_numbers(rows[resource], 6)
            continue

        components = faction_resource_components_yearly(
            indexed,
            templates_dir,
            faction_id,
            faction,
            trait_templates,
            effect_contexts,
            effect_templates,
            councilor_by_id,
            mc_components,
            cp_maintenance,
            resource,
        )
        yearly = sum(components.values())
        row = {
            "current": as_float(resources.get(resource), 0.0),
            "daily": yearly / DAYS_PER_YEAR,
            "monthly": yearly / 12.0,
            "yearly": yearly,
        }
        if include_details:
            row["componentsYearly"] = components
        rows[resource] = clean_numbers(row, 6)

    output = {
        "faction": {
            "id": faction_id,
            "template": faction.get("templateName"),
            "display": faction.get("displayName"),
            "player": faction_is_player(indexed, faction),
        },
        "showMonthlyIncomes": bool(faction.get("showMonthlyIncomesInTopBarAndIntel")),
        "resources": rows,
        "controlPointMaintenance": clean_numbers(cp_maintenance, 6),
        "resourceIncomeDeficiencies": faction.get("resourceIncomeDeficiencies") or [],
        "valueProvenance": {
            "saveNative": [
                "resources.*.current",
                "resources.MissionControl.usage",
                "resourceIncomeDeficiencies",
            ],
            "calculated": [
                "resources.*.daily/monthly/yearly",
                "resources.MissionControl.capacity/available/projectedAfterCurrentQueue",
                "controlPointMaintenance",
                "forecast",
            ],
        },
        "sourceNotes": [
            "Top-bar stockpiles are raw TIFactionState.resources.",
            "Top-bar non-research deltas use TIFactionState.GetMonthlyIncome-equivalent yearly components divided by 12 when monthly display is enabled.",
            "Research row includes the distribution-slot bonus, matching GeneralControlsController.ResourceReportString.",
        ],
    }
    if forecast_resource:
        location_catalog = load_location_catalog()
        output["forecast"] = forecast_faction_hab_resource(
            indexed,
            faction,
            hab_module_templates,
            effect_contexts,
            effect_templates,
            councilor_by_id,
            forecast_resource,
            body_templates=location_catalog.body_templates,
            orbit_templates=location_catalog.orbit_templates,
        )
    if include_diagnostics:
        output["calculationDiagnostics"] = (
            runtime_catalogs.calculation_diagnostics()
            if runtime_catalogs is not None
            else {"source": "explicitly injected ResearchTemplates"}
        )
        output["diagnostics"] = {
            "faction": {
                "selection": "override" if faction_name else "save human-player metadata/TIPlayerState",
                "id": faction_id,
                "template": faction.get("templateName"),
                "display": faction.get("displayName"),
                "player": faction_is_player(indexed, faction),
            },
            "catalog": module_catalog_diagnostics(),
            "locationCatalog": location_catalog_diagnostics(),
            "unknownTemplates": [],
            "unknownEffects": [],
            "miningSamples": faction_mining_calculation_samples(
                indexed,
                faction,
                hab_module_templates,
                effect_contexts,
                effect_templates,
            ),
            "calculationAssumptions": [
                "Installed game TIHabState.GetNetCurrentMonthlyIncome charges target-module crew during construction but no direct support or production.",
                "Installed game active-module paths exclude under-construction upgrades from power/production/bonuses; priorModuleCompleted is retained for current MC only.",
                "Forecast completion events assume the completed target module becomes powered; per-event hab power balance is reported.",
                "Daily-to-monthly space mining conversion is DAYS_PER_YEAR / 12.",
            ],
        }
    return output
