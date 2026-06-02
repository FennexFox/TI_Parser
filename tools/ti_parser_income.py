"""Councilor and nation income helpers for the Terra Invicta save parser."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Callable, Mapping

from ti_parser_core import (
    IndexedState,
    apply_effect_modifiers,
    as_float,
    ref_id,
    resolve_ref,
    state_value_by_id,
    type_entries,
)


@dataclass(frozen=True)
class IncomeConfig:
    days_per_year: float
    financial_sector_funding_bonus: float
    knowledge_sector_research_bonus: float
    min_population_for_first_army_millions: float
    min_population_for_additional_armies_per_millions: float
    min_control_points_for_navy: int
    min_control_points_for_navy_exception: int
    pcgdp_for_navy_exception: float
    faction_ideology_by_template: Mapping[str, str]
    councilor_income_fields: Mapping[str, tuple[str | None, str | None, str | None]]


def _income_fields(config: IncomeConfig, resource: str) -> tuple[str | None, str | None, str | None] | None:
    return config.councilor_income_fields.get(resource)


def councilor_is_income_active(councilor: dict[str, Any]) -> bool:
    return not councilor.get("detained") and not councilor.get("isAlien")


def councilor_monthly_income(
    indexed: IndexedState,
    councilor: dict[str, Any],
    trait_templates: dict[str, dict[str, Any]],
    final_attributes: dict[str, Any],
    resource: str,
    config: IncomeConfig,
) -> float:
    if not councilor_is_income_active(councilor):
        return 0.0
    fields = _income_fields(config, resource)
    if not fields:
        return 0.0
    trait_field, org_field, attribute = fields

    positive = 0.0
    negative = 0.0
    trait_names = councilor.get("traitTemplateNames") if isinstance(councilor.get("traitTemplateNames"), list) else []
    for trait_name in trait_names:
        trait = trait_templates.get(trait_name)
        if not trait or not trait_field:
            continue
        value = as_float(trait.get(trait_field), 0.0)
        if value >= 0:
            positive += value
        else:
            negative += value

    org_refs = councilor.get("orgs") if isinstance(councilor.get("orgs"), list) else []
    for org_ref in org_refs:
        found = resolve_ref(indexed, org_ref)
        if not found:
            continue
        org = found[2]
        if not org.get("applyingBonuses"):
            continue
        value = as_float(org.get(org_field), 0.0) if org_field else 0.0
        if value >= 0:
            positive += value
        else:
            negative += value

    if attribute and positive > 0.0:
        positive *= 1.0 + as_float(final_attributes.get(attribute), 0.0) / 100.0
    return positive + negative


def councilor_yearly_income(
    indexed: IndexedState,
    councilor: dict[str, Any],
    trait_templates: dict[str, dict[str, Any]],
    final_attributes: dict[str, Any],
    resource: str,
    config: IncomeConfig,
) -> float:
    monthly = councilor_monthly_income(indexed, councilor, trait_templates, final_attributes, resource, config)
    if resource in {"Projects", "MissionControl"}:
        return monthly
    return monthly * 12.0


def councilor_resource_income(
    indexed: IndexedState,
    councilor: dict[str, Any],
    trait_templates: dict[str, dict[str, Any]],
    final_attributes: dict[str, Any],
    resource: str,
    config: IncomeConfig,
) -> float:
    return councilor_monthly_income(indexed, councilor, trait_templates, final_attributes, resource, config)


def councilor_research_and_mc(
    indexed: IndexedState,
    faction: dict[str, Any],
    trait_templates: dict[str, dict[str, Any]],
    councilor_by_id: dict[int, dict[str, Any]],
    faction_councilor_ids: Callable[[dict[str, Any]], list[int]],
    config: IncomeConfig,
) -> tuple[float, int, list[dict[str, Any]]]:
    daily_research = 0.0
    mission_control = 0
    details: list[dict[str, Any]] = []
    for councilor_id in faction_councilor_ids(faction):
        councilor = state_value_by_id(indexed, councilor_id)
        if not councilor:
            continue
        summary = councilor_by_id.get(councilor_id, {})
        final_attributes = summary.get("finalAttributes") if isinstance(summary.get("finalAttributes"), dict) else {}
        research_month = councilor_resource_income(
            indexed,
            councilor,
            trait_templates,
            final_attributes,
            "Research",
            config,
        )
        mc_capacity = int(
            councilor_resource_income(
                indexed,
                councilor,
                trait_templates,
                final_attributes,
                "MissionControl",
                config,
            )
        )
        research_day = research_month * 12.0 / config.days_per_year
        daily_research += research_day
        mission_control += mc_capacity
        details.append(
            {
                "id": councilor_id,
                "display": councilor.get("displayName"),
                "science": final_attributes.get("Science"),
                "researchMonth": research_month,
                "researchDay": research_day,
                "missionControl": mc_capacity,
            }
        )
    return daily_research, mission_control, details


def nation_control_points(indexed: IndexedState, nation: dict[str, Any]) -> list[dict[str, Any]]:
    refs = nation.get("controlPoints") if isinstance(nation.get("controlPoints"), list) else []
    points: list[dict[str, Any]] = []
    for cp_ref in refs:
        found = resolve_ref(indexed, cp_ref)
        if found:
            points.append(found[2])
    return points


def active_owned_control_points(indexed: IndexedState, nation: dict[str, Any], faction_id: int) -> list[dict[str, Any]]:
    return [
        cp
        for cp in nation_control_points(indexed, nation)
        if ref_id(cp.get("faction")) == faction_id and not cp.get("benefitsDisabled")
    ]


def nation_population_millions(indexed: IndexedState, nation: dict[str, Any]) -> float:
    total = 0.0
    refs = nation.get("regions") if isinstance(nation.get("regions"), list) else []
    for region_ref in refs:
        found = resolve_ref(indexed, region_ref)
        if not found:
            continue
        region = found[2]
        total += as_float(region.get("populationInMillions") or region.get("population_Millions"), 0.0)
    return total


def nation_non_colony_unoccupied_region_count(indexed: IndexedState, nation: dict[str, Any]) -> int:
    count = 0
    refs = nation.get("regions") if isinstance(nation.get("regions"), list) else []
    for region_ref in refs:
        found = resolve_ref(indexed, region_ref)
        if not found:
            continue
        region = found[2]
        if region.get("colonyRegion") or region.get("occupiedBy"):
            continue
        count += 1
    return count


def nation_allowed_armies(indexed: IndexedState, nation: dict[str, Any], population_millions: float, config: IncomeConfig) -> int:
    if (
        not nation.get("military")
        or population_millions < config.min_population_for_first_army_millions
    ):
        return 0
    population_limit = 1 + int(population_millions / config.min_population_for_additional_armies_per_millions)
    return min(nation_non_colony_unoccupied_region_count(indexed, nation), population_limit)


def nation_can_have_navy(nation: dict[str, Any], per_capita_gdp: float, config: IncomeConfig) -> bool:
    control_points = int(as_float(nation.get("numControlPoints"), 0.0))
    if control_points >= config.min_control_points_for_navy:
        return True
    return control_points >= config.min_control_points_for_navy_exception and per_capita_gdp >= config.pcgdp_for_navy_exception


def nation_current_mission_control(indexed: IndexedState, nation: dict[str, Any]) -> int:
    total = 0
    refs = nation.get("regions") if isinstance(nation.get("regions"), list) else []
    for region_ref in refs:
        found = resolve_ref(indexed, region_ref)
        if found:
            total += int(as_float(found[2].get("missionControl"), 0.0))
    return total


def nation_raw_boost_year(indexed: IndexedState, nation: dict[str, Any]) -> float:
    total = 0.0
    refs = nation.get("regions") if isinstance(nation.get("regions"), list) else []
    for region_ref in refs:
        found = resolve_ref(indexed, region_ref)
        if found:
            total += as_float(found[2].get("boostPerYear_dekatons"), 0.0)
    return total


def nation_current_boost_year(indexed: IndexedState, nation: dict[str, Any]) -> float:
    total = 0.0
    refs = nation.get("regions") if isinstance(nation.get("regions"), list) else []
    for region_ref in refs:
        found = resolve_ref(indexed, region_ref)
        if not found:
            continue
        region = found[2]
        if region.get("leadOccupier"):
            continue
        total += as_float(region.get("boostPerYear_dekatons"), 0.0)
    return total


def nation_federation_pooled_year(indexed: IndexedState, nation: dict[str, Any], resource: str) -> float:
    federation_ref = nation.get("federation")
    federation_id = ref_id(federation_ref)
    if federation_id is None:
        if resource == "Money":
            return as_float(nation.get("spaceFunding_year"), 0.0)
        if resource == "Boost":
            return nation_current_boost_year(indexed, nation)
        return 0.0

    federation = state_value_by_id(indexed, federation_id)
    member_refs = federation.get("members") if isinstance(federation, dict) and isinstance(federation.get("members"), list) else []
    members = [state_value_by_id(indexed, ref_id(member_ref)) for member_ref in member_refs]
    member_states = [member for member in members if isinstance(member, dict)]
    denominator = sum(int(as_float(member.get("numControlPoints"), 0.0)) ** 3 for member in member_states)
    own_points = int(as_float(nation.get("numControlPoints"), 0.0))
    if denominator <= 0 or own_points <= 0:
        return 0.0
    if resource == "Money":
        pooled = sum(as_float(member.get("spaceFunding_year"), 0.0) for member in member_states)
    elif resource == "Boost":
        pooled = sum(nation_current_boost_year(indexed, member) for member in member_states)
    else:
        pooled = 0.0
    return pooled * (own_points**3) / denominator


def faction_ideology_key(faction: dict[str, Any], config: IncomeConfig) -> str | None:
    template = faction.get("templateName")
    if isinstance(template, str):
        if template in config.faction_ideology_by_template:
            return config.faction_ideology_by_template[template]
        if template.endswith("Council"):
            return template.removesuffix("Council")
    return None


def faction_public_opinion(nation: dict[str, Any], faction: dict[str, Any], config: IncomeConfig) -> float:
    public_opinion = nation.get("publicOpinion") if isinstance(nation.get("publicOpinion"), dict) else {}
    ideology = faction_ideology_key(faction, config)
    return as_float(public_opinion.get(ideology), 0.0) if ideology else 0.0


def nation_financial_sector_owned(indexed: IndexedState, nation: dict[str, Any], faction_id: int) -> bool:
    return any(
        cp.get("controlPointType") == "FinancialSector"
        and ref_id(cp.get("faction")) == faction_id
        and not cp.get("benefitsDisabled")
        for cp in nation_control_points(indexed, nation)
    )


def nation_money_contribution_month(indexed: IndexedState, nation: dict[str, Any], faction_id: int, config: IncomeConfig) -> float:
    owned_points = active_owned_control_points(indexed, nation, faction_id)
    num_control_points = int(as_float(nation.get("numControlPoints"), len(nation_control_points(indexed, nation))))
    if not owned_points or num_control_points <= 0:
        return 0.0
    monthly = nation_federation_pooled_year(indexed, nation, "Money") / 12.0
    if nation_financial_sector_owned(indexed, nation, faction_id):
        monthly *= config.financial_sector_funding_bonus
    return monthly / num_control_points * len(owned_points)


def nation_boost_contribution_month(indexed: IndexedState, nation: dict[str, Any], faction_id: int) -> float:
    owned_points = active_owned_control_points(indexed, nation, faction_id)
    num_control_points = int(as_float(nation.get("numControlPoints"), len(nation_control_points(indexed, nation))))
    if not owned_points or num_control_points <= 0:
        return 0.0
    monthly = nation_federation_pooled_year(indexed, nation, "Boost") / 12.0
    return monthly / num_control_points * len(owned_points)


def nation_influence_contribution_month(indexed: IndexedState, nation: dict[str, Any], faction: dict[str, Any], config: IncomeConfig) -> float:
    population = nation_population_millions(indexed, nation)
    return population * faction_public_opinion(nation, faction, config) * 0.5 / 12.0


def nation_adviser_science_bonus(
    nation: dict[str, Any],
    councilor_by_id: dict[int, dict[str, Any]],
    extra_advisor: tuple[int, float] | None = None,
) -> float:
    sciences: list[float] = []
    existing_ids: set[int] = set()
    refs = nation.get("advisingCouncilors") if isinstance(nation.get("advisingCouncilors"), list) else []
    for councilor_ref in refs:
        councilor_id = ref_id(councilor_ref)
        if councilor_id is None:
            continue
        existing_ids.add(councilor_id)
        summary = councilor_by_id.get(councilor_id)
        if not summary:
            continue
        final_attributes = summary.get("finalAttributes") if isinstance(summary.get("finalAttributes"), dict) else {}
        sciences.append(as_float(final_attributes.get("Science"), 0.0))
    if extra_advisor and extra_advisor[0] not in existing_ids:
        sciences.append(extra_advisor[1])
    sciences.sort(reverse=True)
    return sum(science / 100.0 / (index + 1.0) for index, science in enumerate(sciences))


def state_adviser_attribute_bonus(
    state: dict[str, Any],
    councilor_by_id: dict[int, dict[str, Any]],
    attribute: str,
) -> float:
    values: list[float] = []
    refs = state.get("advisingCouncilors") if isinstance(state.get("advisingCouncilors"), list) else []
    for councilor_ref in refs:
        councilor_id = ref_id(councilor_ref)
        if councilor_id is None:
            continue
        summary = councilor_by_id.get(councilor_id)
        if not summary or not summary.get("active", True):
            continue
        final_attributes = summary.get("finalAttributes") if isinstance(summary.get("finalAttributes"), dict) else {}
        values.append(as_float(final_attributes.get(attribute), 0.0))
    values.sort(reverse=True)
    return sum(value / 100.0 / (index + 1.0) for index, value in enumerate(values))


def nation_monthly_research(
    indexed: IndexedState,
    nation: dict[str, Any],
    councilor_by_id: dict[int, dict[str, Any]],
    extra_advisor: tuple[int, float] | None = None,
) -> float:
    population_millions = nation_population_millions(indexed, nation)
    gdp = as_float(nation.get("GDP"), 0.0)
    education = as_float(nation.get("education"), 0.0)
    democracy = as_float(nation.get("democracy"), 0.0)
    cohesion = as_float(nation.get("cohesion"), 5.0)
    unrest = as_float(nation.get("unrest"), 0.0)
    num_control_points = int(as_float(nation.get("numControlPoints"), len(nation_control_points(indexed, nation))))

    per_capita_gdp = gdp / (population_millions * 1_000_000.0) if population_millions > 0 else 0.0
    if per_capita_gdp <= 0.0 or population_millions <= 0.0 or education <= 0.0:
        population_component = 0.0
    elif per_capita_gdp <= 30_000.0:
        population_component = (per_capita_gdp / 15_000.0) ** 0.6
    else:
        population_component = 1.5157166 + 0.90942997 * (math.log(per_capita_gdp / 15_000.0) - 0.6931472)

    base = (
        population_millions
        * population_component
        * education
        * min(education, 12.0)
        * max(democracy, 1.0) ** (1.0 / 6.0)
        * 0.0075
    )
    base += min(population_millions * 1_000_000.0 / 5000.0, num_control_points + education + democracy / 2.0)
    base *= 1.25 - abs(cohesion - 5.0) / 10.0
    base *= 1.0 - unrest * unrest * 0.01
    base *= 1.0 + nation_adviser_science_bonus(nation, councilor_by_id, extra_advisor)
    return base


def nation_has_owned_knowledge_sector(indexed: IndexedState, nation: dict[str, Any], faction_id: int) -> bool:
    return any(
        cp.get("controlPointType") == "KnowledgeSector"
        and ref_id(cp.get("faction")) == faction_id
        and not cp.get("benefitsDisabled")
        for cp in nation_control_points(indexed, nation)
    )


def nation_research_contribution_month(
    indexed: IndexedState,
    nation: dict[str, Any],
    faction_id: int,
    councilor_by_id: dict[int, dict[str, Any]],
    effect_contexts: dict[str, list[str]],
    effect_templates: dict[str, dict[str, Any]],
    config: IncomeConfig,
    extra_advisor: tuple[int, float] | None = None,
) -> float:
    owned_points = active_owned_control_points(indexed, nation, faction_id)
    num_control_points = int(as_float(nation.get("numControlPoints"), len(nation_control_points(indexed, nation))))
    if not owned_points or num_control_points <= 0:
        return 0.0
    monthly_research = nation_monthly_research(indexed, nation, councilor_by_id, extra_advisor)
    if nation_has_owned_knowledge_sector(indexed, nation, faction_id):
        monthly_research *= config.knowledge_sector_research_bonus
    monthly_research = apply_effect_modifiers(
        effect_contexts,
        effect_templates,
        "ControlPointResearch",
        monthly_research,
    )
    return monthly_research / num_control_points * len(owned_points)


def nation_mission_control_contribution(indexed: IndexedState, nation: dict[str, Any], faction_id: int) -> int:
    current_mc = nation_current_mission_control(indexed, nation)
    num_control_points = int(as_float(nation.get("numControlPoints"), len(nation_control_points(indexed, nation))))
    if current_mc <= 0 or num_control_points <= 0:
        return 0
    owned_points = active_owned_control_points(indexed, nation, faction_id)
    remainder = current_mc % num_control_points
    threshold = num_control_points - remainder
    total = 0
    for index, cp in enumerate(owned_points):
        position = cp.get("positionInNation")
        if not isinstance(position, int):
            position = index
        value = current_mc // num_control_points
        if position >= threshold:
            value += 1
        total += value
    return total
