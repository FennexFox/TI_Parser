"""World population, environment, markets, wars and atrocities."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from ti_parser_config import (
    AEROSOL_TEMPERATURE_DIVISOR,
    CH4_RELATIVE_IMPACT,
    DEFAULT_GLOBAL_CONFIG,
    N2O_RELATIVE_IMPACT,
    SAFE_GREENHOUSE_GAS_LEVELS,
    TEMPERATURE_ANOMALY_FACTOR,
    WORLD_MARKET_RESOURCES,
    WORLD_SELLABLE_MARKET_RESOURCES,
)
from ti_parser_core import (
    IndexedState,
    as_float,
    campaign_code,
    clean_numbers,
    effect_modifier_delta,
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
from ti_parser_nation_ui import int_round
from ti_parser_runtime import (
    average,
    calculation_catalogs,
    extant_nation_states,
    faction_brief,
    faction_ideology_key,
    hab_core_module_record,
    hab_crew,
    hab_module_records,
    human_faction_entries,
    nation_control_points,
    nation_population_millions,
    ti_datetime,
)


def calculate_global_public_opinion(indexed: IndexedState) -> dict[str, Any]:
    factions = human_faction_entries(indexed)
    ideology_by_faction = [(faction_id, faction, faction_ideology_key(faction)) for faction_id, faction in factions]
    ideology_totals = {ideology: 0.0 for _, _, ideology in ideology_by_faction if ideology}
    total_population = 0.0
    for nation in extant_nation_states(indexed):
        population = nation_population_millions(indexed, nation)
        public_opinion = nation.get("publicOpinion") if isinstance(nation.get("publicOpinion"), dict) else {}
        total_population += population
        for ideology in ideology_totals:
            ideology_totals[ideology] += population * as_float(public_opinion.get(ideology), 0.0)

    rows: list[dict[str, Any]] = []
    known_total = 0.0
    for faction_id, faction, ideology in ideology_by_faction:
        proportion = ideology_totals.get(ideology, 0.0) / total_population if total_population > 0.0 else 0.0
        known_total += proportion
        rows.append(
            {
                "faction": faction_brief(faction_id, faction),
                "proportion": proportion,
                "percent": proportion * 100.0,
                "uiPercent": int_round(proportion * 100.0),
            }
        )
    undecided = max(1.0 - known_total, 0.0)
    rows.append(
        {
            "faction": None,
            "ideology": "Undecided",
            "display": "Undecided",
            "proportion": undecided,
            "percent": undecided * 100.0,
            "uiPercent": int_round(undecided * 100.0),
        }
    )
    return clean_numbers({"population_Millions": total_population, "rows": rows}, 6)


def hab_is_alien(indexed: IndexedState, hab: dict[str, Any], records: list[dict[str, Any]]) -> bool:
    core = hab_core_module_record(records)
    template = core.get("template", {}) if core else {}
    if template.get("alienModule"):
        return True
    faction = state_value_by_id(indexed, ref_id(hab.get("faction")))
    return bool(isinstance(faction, dict) and faction.get("templateName") == "AlienCouncil")


def world_space_population(indexed: IndexedState, templates_dir: Path | None) -> int:
    hab_module_templates = load_hab_module_catalog()
    total = 0
    for entry in type_entries(indexed, "TIHabState"):
        hab = entry.get("Value") or {}
        records = hab_module_records(indexed, hab, hab_module_templates)
        if not hab_is_alien(indexed, hab, records):
            total += hab_crew(records)
    return total


def world_global_data(indexed: IndexedState, templates_dir: Path | None) -> dict[str, Any]:
    earth_population = sum(
        as_float((entry.get("Value") or {}).get("populationInMillions"), 0.0)
        for entry in type_entries(indexed, "TIRegionState")
    ) * 1_000_000.0
    gdp = sum(as_float((entry.get("Value") or {}).get("GDP"), 0.0) for entry in type_entries(indexed, "TINationState"))
    per_capita_gdp = gdp / earth_population if earth_population > 0.0 else 0.0
    return clean_numbers(
        {
            "earthPopulation": earth_population,
            "earthPopulation_UI": f"{int_round(earth_population):,}",
            "spacePopulation": world_space_population(indexed, templates_dir),
            "GDP": gdp,
            "GDP_Trillions": gdp / 1_000_000_000_000.0,
            "GDP_UI": f"${gdp / 1_000_000_000_000.0:.1f}T",
            "perCapitaGDP": per_capita_gdp,
            "perCapitaGDP_UI": f"${int_round(per_capita_gdp):,}",
        },
        6,
    )


def temperature_anomaly_components(global_state: dict[str, Any]) -> dict[str, float]:
    co2 = as_float(global_state.get("earthAtmosphericCO2_ppm"), 0.0)
    ch4 = as_float(global_state.get("earthAtmosphericCH4_ppm"), 0.0)
    n2o = as_float(global_state.get("earthAtmosphericN2O_ppm"), 0.0)
    aerosols = as_float(global_state.get("stratosphericAerosols_ppm"), 0.0)
    components = {
        "CO2": max(0.0, (co2 - SAFE_GREENHOUSE_GAS_LEVELS["CO2"]) / TEMPERATURE_ANOMALY_FACTOR),
        "CH4": max(0.0, (ch4 - SAFE_GREENHOUSE_GAS_LEVELS["CH4"]) * CH4_RELATIVE_IMPACT / TEMPERATURE_ANOMALY_FACTOR),
        "N2O": max(0.0, (n2o - SAFE_GREENHOUSE_GAS_LEVELS["N2O"]) * N2O_RELATIVE_IMPACT / TEMPERATURE_ANOMALY_FACTOR),
        "StratosphericAerosols": max(-40.0, -aerosols / AEROSOL_TEMPERATURE_DIVISOR),
    }
    components["total"] = sum(components.values())
    components["total_F"] = components["total"] * 1.8
    return components


def mean_annual_gdp_damage(temp_anomaly_c: float, inequality: float) -> float:
    value = 0.0
    if temp_anomaly_c > 0.25:
        adjusted = temp_anomaly_c - 0.25
        value = 0.14577 * adjusted * adjusted + 0.31839 * adjusted
        value *= math.pow(1.14, inequality)
        if adjusted >= 5.0:
            value *= min(max((adjusted + inequality) / 10.0, 1.0), 1.5)
        value = -value / 100.0
    elif temp_anomaly_c < 0.0:
        adjusted = abs(temp_anomaly_c)
        value = adjusted * -0.04032
        if temp_anomaly_c < -7.0:
            value += (adjusted - 7.0) * -0.04032
            if temp_anomaly_c < -10.5:
                value += (adjusted - 10.5) * -0.04032 * 10.0
    return min(max(value, -0.99), 0.0)


def world_environment(indexed: IndexedState) -> dict[str, Any]:
    global_state = first_value(indexed, "TIGlobalValuesState") or {}
    time_state = first_value(indexed, "TITimeState") or {}
    current_date = time_state.get("currentDateTime") if isinstance(time_state.get("currentDateTime"), dict) else {}
    month_index = max(min(int(as_float(current_date.get("month"), 1.0)) - 1, 11), 0)
    components = temperature_anomaly_components(global_state)
    extant = extant_nation_states(indexed)
    mean_inequality = average([as_float(nation.get("inequality"), 0.0) for nation in extant]) or 0.0
    annual_gdp_damage = mean_annual_gdp_damage(components["total"], mean_inequality)

    def gas_row(key: str, field: str, past_field: str) -> dict[str, Any]:
        past_values = global_state.get(past_field) if isinstance(global_state.get(past_field), list) else []
        previous = as_float(past_values[month_index], 0.0) if month_index < len(past_values) else 0.0
        return {
            "current_ppm": as_float(global_state.get(field), 0.0),
            "safe_ppm": SAFE_GREENHOUSE_GAS_LEVELS[key],
            "oneYearAgo_ppm": previous,
            "temperature_C": components[key],
        }

    result = {
        "temperatureAnomaly_C": components["total"],
        "temperatureAnomaly_F": components["total_F"],
        "globalSeaLevelAnomaly_cm": as_float(global_state.get("globalSeaLevelAnomaly_cm"), 0.0),
        "meanAnnualGDPImpact": annual_gdp_damage,
        "meanAnnualGDPImpactPercent": annual_gdp_damage * 100.0,
        "meanInequality": mean_inequality,
        "greenhouseGases": {
            "CO2": gas_row("CO2", "earthAtmosphericCO2_ppm", "pastEarthAtmosphericCO2_ppm"),
            "CH4": gas_row("CH4", "earthAtmosphericCH4_ppm", "pastEarthAtmosphericCH4_ppm"),
            "N2O": gas_row("N2O", "earthAtmosphericN2O_ppm", "pastEarthAtmosphericN2O_ppm"),
            "StratosphericAerosols": {
                "current_ppm": as_float(global_state.get("stratosphericAerosols_ppm"), 0.0),
                "safe_ppm": SAFE_GREENHOUSE_GAS_LEVELS["StratosphericAerosols"],
                "temperature_C": components["StratosphericAerosols"],
            },
        },
    }
    return clean_numbers(result, 6)


def world_resource_market(
    indexed: IndexedState,
    templates_dir: Path | None,
    faction_name: str | None = None,
) -> dict[str, Any]:
    global_state = first_value(indexed, "TIGlobalValuesState") or {}
    market_values = global_state.get("resourceMarketValues") if isinstance(global_state.get("resourceMarketValues"), dict) else {}
    faction_id, faction = find_faction_state(indexed, faction_name)
    effect_templates = calculation_catalogs(indexed, "world-ui").effects
    effect_contexts = faction_effect_contexts(indexed, faction_id)
    sales_modifier = effect_modifier_delta(effect_contexts, effect_templates, "ResourceMarketSales", 0.0)
    sale_multiplier = min(2.0 / 3.0, DEFAULT_GLOBAL_CONFIG["baseEarthSaleInefficiency"] * (1.0 + sales_modifier))
    resources = {}
    for resource in WORLD_MARKET_RESOURCES:
        purchase = as_float(market_values.get(resource), 0.0)
        sellable = resource in WORLD_SELLABLE_MARKET_RESOURCES
        resources[resource] = clean_numbers(
            {
                "purchase": purchase,
                "sell": purchase * sale_multiplier if sellable else None,
                "sellable": sellable,
            },
            6,
        )
    return {
        "faction": faction_brief(faction_id, faction),
        "saleMultiplier": clean_numbers(sale_multiplier, 6),
        "resourceMarketSalesModifier": clean_numbers(sales_modifier, 6),
        "resources": resources,
    }


def nation_executive_faction(indexed: IndexedState, nation: dict[str, Any]) -> dict[str, Any] | None:
    control_points = nation_control_points(indexed, nation)
    if not control_points:
        return None
    executive = max(control_points, key=lambda cp: int(as_float(cp.get("positionInNation"), -1.0)))
    return ref_summary(indexed, executive.get("faction"))


def nation_army_count(indexed: IndexedState, nation: dict[str, Any]) -> int:
    count = 0
    for army_ref in nation.get("armies") if isinstance(nation.get("armies"), list) else []:
        army = state_value_by_id(indexed, ref_id(army_ref))
        if isinstance(army, dict) and not army.get("destroyed") and army.get("armyType") == "Human":
            count += 1
    return count


def nation_naval_score(indexed: IndexedState, nation: dict[str, Any]) -> float:
    score = 0.0
    for army_ref in nation.get("armies") if isinstance(nation.get("armies"), list) else []:
        army = state_value_by_id(indexed, ref_id(army_ref))
        if (
            isinstance(army, dict)
            and not army.get("destroyed")
            and army.get("armyType") == "Human"
            and army.get("deploymentType") == "Naval"
        ):
            score += as_float(army.get("techLevel"), as_float(nation.get("militaryTechLevel"), 0.0))
    return score


def war_alliance_states(indexed: IndexedState, war: dict[str, Any], field: str) -> list[dict[str, Any]]:
    states: list[dict[str, Any]] = []
    for nation_ref in war.get(field) if isinstance(war.get(field), list) else []:
        nation = state_value_by_id(indexed, ref_id(nation_ref))
        if isinstance(nation, dict):
            states.append(nation)
    return states


def nation_brief_from_state(indexed: IndexedState, nation: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": ref_id(nation.get("ID")),
        "template": nation.get("templateName"),
        "code": campaign_code(nation.get("templateName")),
        "display": nation.get("displayName"),
        "executiveFaction": nation_executive_faction(indexed, nation),
    }


def war_side_summary(
    indexed: IndexedState,
    alliance: list[dict[str, Any]],
    own_naval_score: float,
    enemy_naval_score: float,
) -> dict[str, Any]:
    leader = alliance[0] if alliance else {}
    return clean_numbers(
        {
            "leader": nation_brief_from_state(indexed, leader) if leader else None,
            "alliance": [nation_brief_from_state(indexed, nation) for nation in alliance],
            "armies": sum(nation_army_count(indexed, nation) for nation in alliance),
            "hasNuclearWeapons": sum(int(as_float(nation.get("numNuclearWeapons"), 0.0)) for nation in alliance) > 0,
            "navalScore": own_naval_score,
            "navalFreedom": own_naval_score >= enemy_naval_score,
        },
        6,
    )


def calculate_world_wars(indexed: IndexedState) -> list[dict[str, Any]]:
    time_state = first_value(indexed, "TITimeState") or {}
    current_time = ti_datetime(time_state.get("currentDateTime"))
    wars: list[dict[str, Any]] = []
    for entry in type_entries(indexed, "TIWarState"):
        war = entry.get("Value") or {}
        attacking = war_alliance_states(indexed, war, "_attackingAlliance")
        defending = war_alliance_states(indexed, war, "_defendingAlliance")
        attacking_naval = sum(nation_naval_score(indexed, nation) for nation in attacking)
        defending_naval = sum(nation_naval_score(indexed, nation) for nation in defending)
        start = ti_datetime(war.get("startDate"))
        duration_days = math.floor((current_time - start).total_seconds() / 86400.0) if current_time and start else None
        wars.append(
            clean_numbers(
                {
                    "id": raw_state_id(entry),
                    "display": war.get("displayName"),
                    "durationDays": duration_days,
                    "startDate": war.get("startDate"),
                    "attacker": ref_summary(indexed, war.get("attacker")),
                    "defender": ref_summary(indexed, war.get("defender")),
                    "attackingSide": war_side_summary(indexed, attacking, attacking_naval, defending_naval),
                    "defendingSide": war_side_summary(indexed, defending, defending_naval, attacking_naval),
                },
                6,
            )
        )
    return wars


def calculate_world_atrocities(indexed: IndexedState) -> list[dict[str, Any]]:
    rows = []
    for faction_id, faction in human_faction_entries(indexed):
        rows.append(
            {
                "faction": faction_brief(faction_id, faction),
                "atrocities": int(as_float(faction.get("atrocities"), 0.0)),
                "byCause": faction.get("numAtrocitiesByCause") if isinstance(faction.get("numAtrocitiesByCause"), dict) else {},
            }
        )
    rows.sort(key=lambda row: (-row["atrocities"], str((row["faction"] or {}).get("template"))))
    return rows


def calculate_world_ui(
    indexed: IndexedState,
    templates_dir: Path | None,
    faction_name: str | None = None,
) -> dict[str, Any]:
    return {
        "publicOpinion": calculate_global_public_opinion(indexed),
        "globalData": world_global_data(indexed, templates_dir),
        "resourceMarket": world_resource_market(indexed, templates_dir, faction_name),
        "environment": world_environment(indexed),
        "wars": calculate_world_wars(indexed),
        "atrocities": calculate_world_atrocities(indexed),
        "sourceNotes": [
            "World public opinion is population-weighted across extant nations, matching TIGlobalValuesState.GetGlobalPublicOpinionProportions.",
            "Space population is non-alien hab crew from okay modules; ships are not included by the Intel screen.",
            "Environmental temperature and GDP impact formulas mirror TIGlobalValuesState and TINationState UI helpers.",
        ],
    }
