"""Nation display values and shared priority-validity presentation."""

from __future__ import annotations

from ti_parser_errors import UserInputError

import math
from pathlib import Path
from typing import Any

from ti_parser_config import (
    NATION_INACTIVE_PRIORITY_KEYS,
    NATION_PRIORITY_ROWS,
    SCENARIO_RULE_OVERRIDES,
)
from ti_parser_core import (
    IndexedState,
    as_float,
    campaign_code,
    clean_numbers,
    faction_effect_contexts,
    find_faction_state,
    match_raw_state,
    ref_id,
    ref_summary,
    resolve_ref,
    scenario_template_name,
    state_value_by_id,
)
from ti_parser_nation_validity import (
    MIN_CONTROL_POINTS_FOR_NAVY,
    MIN_CONTROL_POINTS_FOR_NAVY_EXCEPTION,
    PCGDP_FOR_NAVY_EXCEPTION,
    PriorityValidityResult,
    can_build_navy,
    evaluate_priority_validity,
)
from ti_parser_runtime import (
    active_owned_control_points,
    active_scenario_rules,
    calculation_catalogs,
    councilor_summary_maps,
    nation_allowed_armies,
    nation_can_have_navy,
    nation_control_points,
    nation_current_mission_control,
    nation_federation_pooled_year,
    nation_mission_control_contribution,
    nation_monthly_research,
    nation_population_millions,
    nation_raw_boost_year,
    nation_research_contribution_month,
    national_ip_multiplier,
)


def int_round(value: float) -> int:
    return int(math.floor(value + 0.5))


def display_one_decimal(value: float) -> float:
    return round(value, 1)


def democracy_label(value: float) -> str:
    if value >= 9.0:
        return "완전한 민주주의"
    if value >= 7.0:
        return "민주주의"
    if value >= 4.0:
        return "무정부/혼합 체제"
    return "권위주의"


def unrest_label(value: float) -> str:
    if value <= 0.5:
        return "평화"
    if value <= 2.0:
        return "낮은 불안"
    if value <= 5.0:
        return "불안"
    return "심각한 불안"


def education_label(value: float) -> str:
    if value >= 11.0:
        return "진보적"
    if value >= 9.0:
        return "높음"
    if value >= 6.0:
        return "보통"
    return "낮음"


def inequality_label(value: float) -> str:
    if value <= 2.0:
        return "매우 낮음"
    if value <= 4.0:
        return "낮음"
    if value <= 6.0:
        return "보통"
    return "높음"


def cohesion_label(value: float) -> str:
    distance = abs(value - 5.0)
    if distance <= 1.0:
        return "다양성"
    if value < 5.0:
        return "분열"
    return "단결"


def miltech_label(value: float) -> str:
    if value >= 5.0:
        return "로봇/미래전 시대"
    if value >= 4.0:
        return "정보화 시대"
    if value >= 3.0:
        return "원자력 시대"
    return "산업 시대"


def display_public_opinion(public_opinion: dict[str, Any]) -> dict[str, float]:
    return {
        str(key): round(as_float(value, 0.0) * 100.0, 1)
        for key, value in public_opinion.items()
    }


def nation_army_details(indexed: IndexedState, nation: dict[str, Any], military_tech_level: float) -> dict[str, Any]:
    refs = nation.get("armies") if isinstance(nation.get("armies"), list) else []
    armies: list[dict[str, Any]] = []
    navies = 0
    naval_score = 0.0
    for army_ref in refs:
        found = resolve_ref(indexed, army_ref)
        if not found:
            continue
        army = found[2]
        if army.get("destroyed"):
            continue
        if army.get("deploymentType") == "Naval":
            navies += 1
            naval_score += as_float(army.get("techLevel"), military_tech_level)
        armies.append(
            {
                "id": ref_id(army.get("ID")),
                "display": army.get("displayName"),
                "deploymentType": army.get("deploymentType"),
                "strength": army.get("strength"),
                "faction": ref_summary(indexed, army.get("faction")),
                "homeRegion": ref_summary(indexed, army.get("homeRegion")),
                "currentRegion": ref_summary(indexed, army.get("currentRegion")),
            }
        )
    return {
        "count": len(armies),
        "navies": navies,
        "standardArmies": len(armies) - navies,
        "navalScore": naval_score,
        "armies": armies,
    }


def first_control_point(indexed: IndexedState, nation: dict[str, Any]) -> dict[str, Any] | None:
    points = nation_control_points(indexed, nation)
    return points[0] if points else None


def federation_space_program(indexed: IndexedState, nation: dict[str, Any]) -> bool | None:
    """TIFederationState.SetSpaceProgramValue: any member has spaceflight."""
    reference = nation.get("federation")
    if reference is None:
        return False
    federation = state_value_by_id(indexed, ref_id(reference))
    if not isinstance(federation, dict) or not isinstance(federation.get("members"), list):
        return None
    values = []
    for member_ref in federation["members"]:
        member = state_value_by_id(indexed, ref_id(member_ref))
        values.append(member.get("spaceFlightProgram") if isinstance(member, dict) else None)
    if any(value is True for value in values):
        return True
    return False if all(value is False for value in values) else None


def _nation_ui_priority_validity(
    indexed: IndexedState,
    nation: dict[str, Any],
    development: dict[str, Any],
    *,
    population: float,
    allowed_armies: int,
    current_armies: int,
    army_count: int | None = None,
    navy_count: int | None = None,
    per_capita_gdp: float | None = None,
) -> dict[str, PriorityValidityResult]:
    priorities = development.get("priorities") if isinstance(development.get("priorities"), dict) else {}
    global_config = development.get("globalConfig") if isinstance(development.get("globalConfig"), dict) else {}
    region_values: list[dict[str, Any]] = []
    region_refs = nation.get("regions") if isinstance(nation.get("regions"), list) else None
    regions_complete = region_refs is not None
    for region_ref in region_refs or []:
        found = resolve_ref(indexed, region_ref)
        if found is None:
            regions_complete = False
            continue
        region_values.append(found[2])

    def config_number(name: str) -> float | None:
        row = global_config.get(name)
        value = row.get("value") if isinstance(row, dict) else None
        return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None

    mission_capacity: bool | None = None
    required_config = {
        name: config_number(name)
        for name in ("coreEcoRegionGDPModifier", "coreResourceRegionGDPModifier", "colonyRegionGDPModifier")
    }
    required_region_fields = (
        "populationInMillions", "coreEconomicRegion", "resourceRegion", "oilRegion", "colonyRegion", "missionControl",
    )
    if regions_complete and region_values and all(value is not None for value in required_config.values()) and all(
        all(field in region for field in required_region_fields) for region in region_values
    ):
        weights: list[float] = []
        for region in region_values:
            weight = float(region["populationInMillions"])
            if region["coreEconomicRegion"]:
                weight *= float(required_config["coreEcoRegionGDPModifier"])
            if region["resourceRegion"] or region["oilRegion"]:
                weight *= float(required_config["coreResourceRegionGDPModifier"])
            if region["colonyRegion"]:
                weight *= float(required_config["colonyRegionGDPModifier"])
            weights.append(weight)
        total_weight = sum(weights)
        education = nation.get("education")
        gdp = nation.get("GDP")
        if total_weight > 0 and isinstance(education, (int, float)) and isinstance(gdp, (int, float)):
            divisor = max(200.0, 300.0 - 6.0 * float(education))
            mission_capacity = any(
                int(region["missionControl"]) < max(
                    int(region["missionControl"]),
                    1 + int(((float(gdp) * weight / total_weight) / 1_000_000_000.0) / divisor),
                )
                for region, weight in zip(region_values, weights)
            )

    hostile = nation.get("hostileClaims")
    hostile_known = isinstance(hostile, list)
    boost_known = regions_complete and bool(region_values) and all(
        isinstance(region.get("boostPerYear_dekatons"), (int, float)) for region in region_values
    )
    ocean_types = [region.get("oceanType") for region in region_values]
    coastal_regions = (
        sum(ocean_type in {"Yes", "Seasonal"} for ocean_type in ocean_types)
        if regions_complete and all(isinstance(ocean_type, str) and ocean_type in {"No", "None", "Yes", "Seasonal"} for ocean_type in ocean_types)
        else None
    )
    build_navy = can_build_navy({
        "military": nation.get("military") if isinstance(nation.get("military"), bool) else None,
        "armyCount": army_count,
        "navyCount": navy_count,
        "coastalRegions": coastal_regions,
        "controlPointCount": nation.get("numControlPoints"),
        "perCapitaGDP": per_capita_gdp,
        "minControlPointsForNavy": MIN_CONTROL_POINTS_FOR_NAVY,
        "minControlPointsForNavyException": MIN_CONTROL_POINTS_FOR_NAVY_EXCEPTION,
        "pcgdpForNavyException": PCGDP_FOR_NAVY_EXCEPTION,
    })
    view = {
        "democracy": nation.get("democracy"),
        "hasHostileRegion": bool(hostile) if hostile_known else None,
        "fundingYear": nation.get("spaceFunding_year"),
        "gdp": nation.get("GDP"),
        "spaceFlightProgram": nation.get("spaceFlightProgram") if isinstance(nation.get("spaceFlightProgram"), bool) else None,
        "missionControlHasCapacity": mission_capacity,
        "federationSpaceProgram": federation_space_program(indexed, nation),
        "allowedArmies": allowed_armies if regions_complete else None,
        "currentArmies": current_armies,
        "canBuildNavy": build_navy,
        "military": nation.get("military") if isinstance(nation.get("military"), bool) else None,
        "nuclearProgram": nation.get("nuclearProgram") if isinstance(nation.get("nuclearProgram"), bool) else None,
        "canBuildSpaceDefenses": nation.get("canBuildSpaceDefenses") if isinstance(nation.get("canBuildSpaceDefenses"), bool) else None,
        "canBuildSTO": nation.get("canBuildSTOSquadrons") if isinstance(nation.get("canBuildSTOSquadrons"), bool) else None,
        "hasBoostRegion": any(float(region["boostPerYear_dekatons"]) > 0 for region in region_values) if boost_known else None,
    }
    raw_names = {
        str(priority)
        for cp in nation_control_points(indexed, nation)
        for priority in ((cp.get("controlPointPriorities") or {}) if isinstance(cp.get("controlPointPriorities"), dict) else {})
    }
    return {
        name: evaluate_priority_validity(name, view)
        for name in sorted(set(priorities) | raw_names)
    }


def _nation_ui_control_point_weights(
    control_points: list[dict[str, Any]],
    validity: dict[str, PriorityValidityResult],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, cp in enumerate(control_points):
        raw = cp.get("controlPointPriorities") if isinstance(cp.get("controlPointPriorities"), dict) else {}
        raw_weights = {str(name): int(as_float(value, 0.0)) for name, value in raw.items()}
        effective = {
            name: value for name, value in raw_weights.items()
            if value > 0 and validity.get(name, PriorityValidityResult(None, "missing validity result")).valid is True
        }
        unknown = sorted(
            name for name, value in raw_weights.items()
            if value > 0 and validity.get(name, PriorityValidityResult(None, "missing validity result")).valid is None
        )
        serialized = int(as_float(cp.get("totalWeightsForControlPoint"), 0.0))
        recomputed = sum(effective.values())
        rows.append({
            "id": ref_id(cp.get("ID")),
            "position": int(as_float(cp.get("positionInNation"), index)),
            "rawWeights": raw_weights,
            "effectiveWeights": effective,
            "serializedTotalWeight": serialized,
            "recomputedTotalWeight": recomputed,
            "serializedNumPrioritiesWithWeight": cp.get("numPrioritiesWithWeight"),
            "recomputedNumPrioritiesWithWeight": len(effective),
            "consistent": None if unknown else serialized == recomputed,
            "unknownPriorities": unknown,
        })
    return rows


def nation_priority_rows(
    indexed: IndexedState,
    nation: dict[str, Any],
    validity: dict[str, PriorityValidityResult] | None = None,
) -> list[dict[str, Any]]:
    scenario_rules = active_scenario_rules(indexed)
    ip_multiplier = national_ip_multiplier(indexed)
    control_points = nation_control_points(indexed, nation)
    representative = control_points[0] if control_points else {}
    priorities = representative.get("controlPointPriorities") if isinstance(representative.get("controlPointPriorities"), dict) else {}
    accumulated = nation.get("_accumulatedInvestmentPoints") if isinstance(nation.get("_accumulatedInvestmentPoints"), dict) else {}
    total_weight = int(as_float(representative.get("totalWeightsForControlPoint"), 0.0))
    rows: list[dict[str, Any]] = []
    for key, label, priority_key, accumulated_key, cost in NATION_PRIORITY_ROWS:
        base_cost = scenario_rules.build_army_priority_cost if key == "BuildArmy" else cost
        required_cost = base_cost / ip_multiplier if ip_multiplier != 1.0 else base_cost
        weight = int(as_float(priorities.get(priority_key), 0.0))
        share_percent = int_round(weight / total_weight * 100.0) if total_weight > 0 else 0
        rows.append(
            {
                "key": key,
                "label": label,
                "priorityKey": priority_key,
                "weightPerControlPoint": weight,
                "sharePercent": share_percent,
                "accumulated": as_float(accumulated.get(accumulated_key), 0.0),
                "cost": required_cost,
            }
        )
    inactive_with_weights = ({
        key: int(as_float(value, 0.0))
        for key, value in priorities.items()
        if int(as_float(value, 0.0)) > 0 and validity.get(key, PriorityValidityResult(None, "missing validity result")).valid is False
    } if validity is not None else {
        key: int(as_float(priorities.get(key), 0.0))
        for key in NATION_INACTIVE_PRIORITY_KEYS
        if int(as_float(priorities.get(key), 0.0)) > 0
    })
    if inactive_with_weights:
        rows.append(
            {
                "key": "_inactiveRawWeights",
                "label": "UI 비활성 원시 weight",
                "weights": inactive_with_weights,
                "note": "Raw save keeps these requested weights, but live shared validity marks them unavailable.",
            }
        )
    return rows


def calculate_nation_ui(
    indexed: IndexedState,
    templates_dir: Path | None,
    nation_name: str,
    faction_name: str | None = None,
) -> dict[str, Any]:
    found = match_raw_state(indexed, "TINationState", nation_name)
    if not found:
        raise UserInputError(f"Nation not found: {nation_name}")
    nation_id, nation = found
    faction_id, faction = find_faction_state(indexed, faction_name)
    runtime_catalogs = calculation_catalogs(indexed, "nation-ui")
    development_catalog = runtime_catalogs.nation_development
    trait_templates = runtime_catalogs.traits
    effect_templates = runtime_catalogs.effects
    effect_contexts = faction_effect_contexts(indexed, faction_id)
    _, councilor_by_id = councilor_summary_maps(indexed, trait_templates)

    population = nation_population_millions(indexed, nation)
    gdp = as_float(nation.get("GDP"), 0.0)
    pc_gdp = gdp / (population * 1_000_000.0) if population else 0.0
    military_tech_level = as_float(nation.get("militaryTechLevel"), 0.0)
    raw_research_month = nation_monthly_research(indexed, nation, councilor_by_id)
    faction_research_month = nation_research_contribution_month(
        indexed,
        nation,
        faction_id,
        councilor_by_id,
        effect_contexts,
        effect_templates,
    )
    raw_boost_year = nation_raw_boost_year(indexed, nation)
    funding_income_month = nation_federation_pooled_year(indexed, nation, "Money") / 12.0
    boost_income_month = nation_federation_pooled_year(indexed, nation, "Boost") / 12.0
    owned_cp_count = len(active_owned_control_points(indexed, nation, faction_id))
    cp_denominator = max(as_float(nation.get("numControlPoints"), 1.0), 1.0)
    faction_funding_month = funding_income_month / cp_denominator * owned_cp_count
    faction_boost_month = boost_income_month / cp_denominator * owned_cp_count
    current_mc = nation_current_mission_control(indexed, nation)
    faction_mc = nation_mission_control_contribution(indexed, nation, faction_id)
    capital = ref_summary(indexed, nation.get("capital"))
    armies = nation_army_details(indexed, nation, military_tech_level)
    allowed_armies = nation_allowed_armies(indexed, nation, population)
    control_points = nation_control_points(indexed, nation)
    priority_validity = _nation_ui_priority_validity(
        indexed,
        nation,
        development_catalog,
        population=population,
        allowed_armies=allowed_armies,
        current_armies=armies["count"],
        army_count=armies["count"],
        navy_count=armies["navies"],
        per_capita_gdp=pc_gdp,
    )
    navy_validity = priority_validity.get("Military_BuildNavy")
    can_have_navy = nation_can_have_navy(nation, pc_gdp)
    max_navies = allowed_armies if can_have_navy else 0
    can_build = navy_validity.valid if navy_validity is not None else None
    navies_can_build = max(0, armies["count"] - armies["navies"]) if can_build else (0 if can_build is False else None)
    control_point_weights = _nation_ui_control_point_weights(control_points, priority_validity)
    representative_cp = first_control_point(indexed, nation) or {}
    total_weight = int(as_float(representative_cp.get("totalWeightsForControlPoint"), 0.0))
    scenario_name = scenario_template_name(indexed)
    scenario_rules = active_scenario_rules(indexed)

    output = {
        "scenario": {
            "template": scenario_name,
            "ruleProfile": scenario_name if scenario_name in SCENARIO_RULE_OVERRIDES else "default",
            "nationalIPMultiplier": national_ip_multiplier(indexed),
            "controlPointMaintenanceMultiplier": scenario_rules.control_point_maintenance_multiplier,
        },
        "identity": {
            "id": nation_id,
            "template": nation.get("templateName"),
            "code": campaign_code(nation.get("templateName")),
            "display": nation.get("displayName"),
            "capital": capital,
            "regions": len(nation.get("regions") or []),
            "controlPoints": len(control_points),
            "executiveOwner": ref_summary(indexed, control_points[-1].get("faction")) if control_points else None,
        },
        "overview": {
            "democracy": as_float(nation.get("democracy"), 0.0),
            "democracyLabel": democracy_label(as_float(nation.get("democracy"), 0.0)),
            "unrest": as_float(nation.get("unrest"), 0.0),
            "unrestLabel": unrest_label(as_float(nation.get("unrest"), 0.0)),
            "GDP_Billions": gdp / 1_000_000_000.0,
            "GDP_UI": f"${int_round(gdp / 1_000_000_000.0):,}십억",
        },
        "development": {
            "investmentPointsMonth": as_float(nation.get("baseInvestmentPoints_month"), 0.0),
            "fundingMonth": as_float(nation.get("spaceFunding_year"), 0.0) / 12.0,
            "fundingIncomeMonth": funding_income_month,
            "factionFundingMonth": faction_funding_month,
            "rawResearchMonth": raw_research_month,
            "factionResearchMonth": faction_research_month,
            "boostMonth": raw_boost_year / 12.0,
            "boostIncomeMonth": boost_income_month,
            "factionBoostMonth": faction_boost_month,
            "missionControl": current_mc,
            "factionMissionControl": faction_mc,
        },
        "people": {
            "population_Millions": population,
            "population_UI": f"{display_one_decimal(population)}백만",
            "perCapitaGDP": pc_gdp,
            "perCapitaGDP_UI": f"${int_round(pc_gdp):,}",
            "inequality": as_float(nation.get("inequality"), 0.0),
            "inequalityLabel": inequality_label(as_float(nation.get("inequality"), 0.0)),
            "education": as_float(nation.get("education"), 0.0),
            "educationLabel": education_label(as_float(nation.get("education"), 0.0)),
            "cohesion": as_float(nation.get("cohesion"), 0.0),
            "cohesionLabel": cohesion_label(as_float(nation.get("cohesion"), 0.0)),
            "publicOpinionPercent": display_public_opinion(
                nation.get("publicOpinion") if isinstance(nation.get("publicOpinion"), dict) else {}
            ),
        },
        "military": {
            "militaryTechLevel": military_tech_level,
            "militaryTechLabel": miltech_label(military_tech_level),
            "armies": armies["count"],
            "allowedArmies": allowed_armies,
            "navies": armies["navies"],
            "naviesCanBuild": navies_can_build,
            "maxNavies": max_navies,
            "navalFreedom": not bool(nation.get("wars")),
            "navalScore": armies["navalScore"],
            "numNuclearWeapons": nation.get("numNuclearWeapons"),
            "armyDetails": armies["armies"],
        },
        "priorities": {
            "totalWeightPerControlPoint": total_weight,
            "numPrioritiesWithWeight": representative_cp.get("numPrioritiesWithWeight"),
            "rows": nation_priority_rows(indexed, nation, priority_validity),
            "validityByPriority": {
                name: result.output() for name, result in sorted(priority_validity.items())
            },
            "controlPoints": control_point_weights,
        },
        "diplomacy": {
            "allies": [ref_summary(indexed, item) for item in nation.get("allies", [])],
            "rivals": [ref_summary(indexed, item) for item in nation.get("rivals", [])],
            "wars": [ref_summary(indexed, item) for item in nation.get("wars", [])],
        },
        "factionContext": {
            "id": faction_id,
            "template": faction.get("templateName"),
            "display": faction.get("displayName"),
            "controlPointResearchEffects": effect_contexts.get("ControlPointResearch", []),
        },
    }
    return clean_numbers(output, 6)
