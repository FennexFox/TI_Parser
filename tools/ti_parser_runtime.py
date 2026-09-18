"""Configured snapshot, income and hab adapters plus shared save-state helpers."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import ti_parser_hab as hab_layer
import ti_parser_income as income_layer
import ti_parser_org as org_layer
import ti_parser_snapshot as snapshot_layer
from ti_parser_catalogs import (
    CatalogIntegrityError,
    RuntimeCatalogs,
    UnsupportedCatalogScenarioError,
    load_runtime_catalogs,
    resolve_required_definition,
)
from ti_parser_config import (
    DEFAULT_MAX_COUNCILOR_ATTRIBUTE,
    DEFAULT_SCENARIO_RULES,
    HAB_CONFIG,
    INCOME_CONFIG,
    SCENARIO_RULE_OVERRIDES,
    SNAPSHOT_CONFIG,
    ScenarioRules,
)
from ti_parser_core import (
    CalculationDependency,
    CalculationDependencyError,
    IndexedState,
    apply_effect_modifiers,
    as_float,
    faction_is_human_player,
    first_value,
    raw_state_id,
    ref_id,
    scenario_template_name,
    state_value_by_id,
    type_entries,
)


def calculation_catalogs(indexed: IndexedState, context: str) -> RuntimeCatalogs:
    """Load the validated package-only bundle for the save's exact scenario."""

    scenario = scenario_template_name(indexed)
    if not scenario:
        raise CalculationDependencyError(
            CalculationDependency(
                kind="scenario",
                name="scenarioMetaTemplateName",
                context=context,
                scenario=None,
                reason="save does not identify a canonical supported scenario",
            )
        )
    catalog_files = [
        "effect_catalog.json",
        "trait_catalog.json",
        "org_catalog.json",
        "research_catalog.json",
        "ship_catalog.json",
        "nation_claim_catalog.json",
    ]
    if context in {"nation-ui", "nation-projection"}:
        catalog_files.append("nation_development_catalog.json")
    try:
        return load_runtime_catalogs(
            scenario,
            catalog_files=catalog_files,
        )
    except UnsupportedCatalogScenarioError as exc:
        raise CalculationDependencyError(
            CalculationDependency(
                kind="scenario",
                name=exc.scenario,
                context=context,
                scenario=scenario,
                reason=str(exc),
            )
        ) from exc
    except CatalogIntegrityError as exc:
        raise CalculationDependencyError(
            CalculationDependency(
                kind="catalog-integrity",
                name="runtime bundle",
                context=context,
                scenario=scenario,
                reason=str(exc),
            )
        ) from exc


def required_catalog_row(
    indexed: IndexedState,
    rows: dict[str, dict[str, Any]],
    kind: str,
    name: Any,
    context: str,
    reason: str = "referenced definition cannot be resolved from runtime data",
) -> dict[str, Any]:
    """Resolve a referenced catalog row or stop the calculation as incomplete."""

    return resolve_required_definition(
        rows,
        name,
        kind,
        context,
        scenario_template_name(indexed),
        reason,
    )


def time_summary(indexed: IndexedState) -> dict[str, Any]:
    return snapshot_layer.time_summary(indexed)


def metadata_summary(indexed: IndexedState) -> dict[str, Any]:
    return snapshot_layer.metadata_summary(indexed)


def global_summary(indexed: IndexedState) -> dict[str, Any]:
    return snapshot_layer.global_summary(indexed)


def faction_key_from_ref(indexed: IndexedState, value: Any) -> str | None:
    return snapshot_layer.faction_key_from_ref(indexed, value)


def faction_display_from_ref(indexed: IndexedState, value: Any) -> str | None:
    return snapshot_layer.faction_display_from_ref(indexed, value)


def control_point_summary(indexed: IndexedState, cp_value: dict[str, Any]) -> dict[str, Any]:
    return snapshot_layer.control_point_summary(indexed, cp_value)


def summarize_regions(indexed: IndexedState, region_refs: list[Any]) -> dict[str, Any]:
    return snapshot_layer.summarize_regions(indexed, region_refs)


def summarize_nation(indexed: IndexedState, entry: dict[str, Any]) -> dict[str, Any]:
    return snapshot_layer.summarize_nation(indexed, entry)


def average(values: Any) -> float | None:
    return snapshot_layer.average(values)


def parse_modifier_number(value: Any) -> float | None:
    return snapshot_layer.parse_modifier_number(value)


def int_like(value: float) -> int:
    return snapshot_layer.int_like(value)


def trait_mod_has_condition(mod: dict[str, Any]) -> bool:
    return snapshot_layer.trait_mod_has_condition(mod)


def stat_mod_entry(trait_name: str, trait: dict[str, Any], mod: dict[str, Any], base_attributes: dict[str, int]) -> dict[str, Any] | None:
    return snapshot_layer.stat_mod_entry(trait_name, trait, mod, base_attributes, SNAPSHOT_CONFIG)


def sum_attr_mods(mods: list[dict[str, Any]]) -> dict[str, int]:
    return snapshot_layer.sum_attr_mods(mods, SNAPSHOT_CONFIG)


def org_attribute_mods(indexed: IndexedState, councilor: dict[str, Any]) -> tuple[dict[str, int], list[dict[str, Any]]]:
    return snapshot_layer.org_attribute_mods(indexed, councilor, SNAPSHOT_CONFIG)


def trait_attribute_mods(
    councilor: dict[str, Any],
    trait_templates: dict[str, dict[str, Any]],
    base_attributes: dict[str, int],
) -> tuple[dict[str, int], list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    return snapshot_layer.trait_attribute_mods(councilor, trait_templates, base_attributes, SNAPSHOT_CONFIG)


def clamp_attribute(value: int, max_value: int = DEFAULT_MAX_COUNCILOR_ATTRIBUTE) -> int:
    return snapshot_layer.clamp_attribute(value, max_value)


def councilor_attribute_breakdown(
    indexed: IndexedState,
    councilor: dict[str, Any],
    trait_templates: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    return snapshot_layer.councilor_attribute_breakdown(indexed, councilor, trait_templates, SNAPSHOT_CONFIG)


def summarize_faction(indexed: IndexedState, entry: dict[str, Any], nation_by_id: dict[int, dict[str, Any]]) -> dict[str, Any]:
    return snapshot_layer.summarize_faction(indexed, entry, nation_by_id, SNAPSHOT_CONFIG)


def summarize_councilors(indexed: IndexedState, trait_templates: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return snapshot_layer.summarize_councilors(indexed, trait_templates, SNAPSHOT_CONFIG)


def summarize_fleets(indexed: IndexedState) -> list[dict[str, Any]]:
    return snapshot_layer.summarize_fleets(indexed)


def build_snapshot(save_path: Path, data: dict[str, Any], templates_dir: Path | None) -> dict[str, Any]:
    return snapshot_layer.build_snapshot(save_path, data, templates_dir, SNAPSHOT_CONFIG)


def load_or_build_snapshot(
    save_path: Path,
    cache_dir: Path,
    templates_dir: Path | None,
    refresh: bool = False,
) -> tuple[dict[str, Any], Path, bool]:
    return snapshot_layer.load_or_build_snapshot(save_path, cache_dir, templates_dir, SNAPSHOT_CONFIG, refresh=refresh)


match_named = org_layer.match_named


parse_bool = org_layer.parse_bool


compare_condition = org_layer.compare_condition


find_faction_for_councilor = org_layer.find_faction_for_councilor


condition_eval_unknown = org_layer.condition_eval_unknown


condition_nation_summary = org_layer.condition_nation_summary


evaluate_condition = org_layer.evaluate_condition


apply_conditional_attribute_mods = org_layer.apply_conditional_attribute_mods


evaluate_councilor_conditionals = org_layer.evaluate_councilor_conditionals


councilor_summary_maps = org_layer.councilor_summary_maps


faction_councilor_ids = org_layer.faction_councilor_ids


org_attribute_values = org_layer.org_attribute_values


org_acquisition_cost = org_layer.org_acquisition_cost


org_plan_cost_affordable = org_layer.org_plan_cost_affordable


org_plan_normalize_focus = org_layer.org_plan_normalize_focus


org_plan_objective_score = org_layer.org_plan_objective_score


org_plan_final_attributes = org_layer.org_plan_final_attributes


org_plan_roster_summary = org_layer.org_plan_roster_summary


MAX_ORGS_PER_COUNCILOR = org_layer.MAX_ORGS_PER_COUNCILOR


org_plan_attribute_delta = org_layer.org_plan_attribute_delta


org_plan_org_row = org_layer.org_plan_org_row


org_plan_region_nation_id = org_layer.org_plan_region_nation_id


org_plan_controlled_nation_ids = org_layer.org_plan_controlled_nation_ids


org_plan_nation_interest = org_layer.org_plan_nation_interest


org_plan_requirement_summary = org_layer.org_plan_requirement_summary


org_plan_faction_eligibility = org_layer.org_plan_faction_eligibility


org_plan_councilor_faction = org_layer.org_plan_councilor_faction


org_plan_owner_eligibility = org_layer.org_plan_owner_eligibility


org_plan_candidate_row = org_layer.org_plan_candidate_row


org_plan_major_attributes = org_layer.org_plan_major_attributes


councilor_org_plan_profile = org_layer.councilor_org_plan_profile


org_plan_best_assignment = org_layer.org_plan_best_assignment


org_plan_committee_totals = org_layer.org_plan_committee_totals


org_plan_committee_score = org_layer.org_plan_committee_score


org_plan_state_key = org_layer.org_plan_state_key


search_org_committee_plan = org_layer.search_org_committee_plan


calculate_org_plan = org_layer.calculate_org_plan


def councilor_is_income_active(councilor: dict[str, Any]) -> bool:
    return income_layer.councilor_is_income_active(councilor)


def councilor_monthly_income(
    indexed: IndexedState,
    councilor: dict[str, Any],
    trait_templates: dict[str, dict[str, Any]],
    final_attributes: dict[str, Any],
    resource: str,
) -> float:
    return income_layer.councilor_monthly_income(indexed, councilor, trait_templates, final_attributes, resource, INCOME_CONFIG)


def councilor_yearly_income(
    indexed: IndexedState,
    councilor: dict[str, Any],
    trait_templates: dict[str, dict[str, Any]],
    final_attributes: dict[str, Any],
    resource: str,
) -> float:
    return income_layer.councilor_yearly_income(indexed, councilor, trait_templates, final_attributes, resource, INCOME_CONFIG)


def councilor_resource_income(
    indexed: IndexedState,
    councilor: dict[str, Any],
    trait_templates: dict[str, dict[str, Any]],
    final_attributes: dict[str, Any],
    resource: str,
) -> float:
    return income_layer.councilor_resource_income(indexed, councilor, trait_templates, final_attributes, resource, INCOME_CONFIG)


def councilor_research_and_mc(
    indexed: IndexedState,
    faction: dict[str, Any],
    trait_templates: dict[str, dict[str, Any]],
    councilor_by_id: dict[int, dict[str, Any]],
) -> tuple[float, int, list[dict[str, Any]]]:
    return income_layer.councilor_research_and_mc(
        indexed,
        faction,
        trait_templates,
        councilor_by_id,
        faction_councilor_ids,
        INCOME_CONFIG,
    )


def nation_control_points(indexed: IndexedState, nation: dict[str, Any]) -> list[dict[str, Any]]:
    return income_layer.nation_control_points(indexed, nation)


def active_owned_control_points(indexed: IndexedState, nation: dict[str, Any], faction_id: int) -> list[dict[str, Any]]:
    return income_layer.active_owned_control_points(indexed, nation, faction_id)


def nation_population_millions(indexed: IndexedState, nation: dict[str, Any]) -> float:
    return income_layer.nation_population_millions(indexed, nation)


def nation_non_colony_unoccupied_region_count(indexed: IndexedState, nation: dict[str, Any]) -> int:
    return income_layer.nation_non_colony_unoccupied_region_count(indexed, nation)


def nation_allowed_armies(indexed: IndexedState, nation: dict[str, Any], population_millions: float) -> int:
    return income_layer.nation_allowed_armies(indexed, nation, population_millions, INCOME_CONFIG)


def nation_can_have_navy(nation: dict[str, Any], per_capita_gdp: float) -> bool:
    return income_layer.nation_can_have_navy(nation, per_capita_gdp, INCOME_CONFIG)


def nation_current_mission_control(indexed: IndexedState, nation: dict[str, Any]) -> int:
    return income_layer.nation_current_mission_control(indexed, nation)


def nation_raw_boost_year(indexed: IndexedState, nation: dict[str, Any]) -> float:
    return income_layer.nation_raw_boost_year(indexed, nation)


def nation_current_boost_year(indexed: IndexedState, nation: dict[str, Any]) -> float:
    return income_layer.nation_current_boost_year(indexed, nation)


def nation_federation_pooled_year(indexed: IndexedState, nation: dict[str, Any], resource: str) -> float:
    return income_layer.nation_federation_pooled_year(indexed, nation, resource)


def faction_ideology_key(faction: dict[str, Any]) -> str | None:
    return income_layer.faction_ideology_key(faction, INCOME_CONFIG)


def faction_public_opinion(nation: dict[str, Any], faction: dict[str, Any]) -> float:
    return income_layer.faction_public_opinion(nation, faction, INCOME_CONFIG)


def nation_financial_sector_owned(indexed: IndexedState, nation: dict[str, Any], faction_id: int) -> bool:
    return income_layer.nation_financial_sector_owned(indexed, nation, faction_id)


def nation_money_contribution_month(indexed: IndexedState, nation: dict[str, Any], faction_id: int) -> float:
    return income_layer.nation_money_contribution_month(indexed, nation, faction_id, INCOME_CONFIG)


def nation_boost_contribution_month(indexed: IndexedState, nation: dict[str, Any], faction_id: int) -> float:
    return income_layer.nation_boost_contribution_month(indexed, nation, faction_id)


def nation_influence_contribution_month(
    indexed: IndexedState,
    nation: dict[str, Any],
    faction: dict[str, Any],
    effect_contexts: dict[str, list[str]] | None = None,
    effect_templates: dict[str, dict[str, Any]] | None = None,
) -> float:
    base = income_layer.nation_influence_contribution_month(indexed, nation, faction, INCOME_CONFIG)
    modifier = apply_effect_modifiers(
        effect_contexts or {},
        effect_templates or {},
        "PublicOpinionInfluence",
        1.0,
    )
    return base * modifier


def nation_adviser_science_bonus(
    nation: dict[str, Any],
    councilor_by_id: dict[int, dict[str, Any]],
    extra_advisor: tuple[int, float] | None = None,
) -> float:
    return income_layer.nation_adviser_science_bonus(nation, councilor_by_id, extra_advisor)


def state_adviser_attribute_bonus(
    state: dict[str, Any],
    councilor_by_id: dict[int, dict[str, Any]],
    attribute: str,
) -> float:
    return income_layer.state_adviser_attribute_bonus(state, councilor_by_id, attribute)


def nation_monthly_research(
    indexed: IndexedState,
    nation: dict[str, Any],
    councilor_by_id: dict[int, dict[str, Any]],
    extra_advisor: tuple[int, float] | None = None,
) -> float:
    return income_layer.nation_monthly_research(indexed, nation, councilor_by_id, extra_advisor)


def nation_has_owned_knowledge_sector(indexed: IndexedState, nation: dict[str, Any], faction_id: int) -> bool:
    return income_layer.nation_has_owned_knowledge_sector(indexed, nation, faction_id)


def nation_research_contribution_month(
    indexed: IndexedState,
    nation: dict[str, Any],
    faction_id: int,
    councilor_by_id: dict[int, dict[str, Any]],
    effect_contexts: dict[str, list[str]],
    effect_templates: dict[str, dict[str, Any]],
    extra_advisor: tuple[int, float] | None = None,
) -> float:
    return income_layer.nation_research_contribution_month(
        indexed,
        nation,
        faction_id,
        councilor_by_id,
        effect_contexts,
        effect_templates,
        INCOME_CONFIG,
        extra_advisor,
    )


def nation_mission_control_contribution(indexed: IndexedState, nation: dict[str, Any], faction_id: int) -> int:
    return income_layer.nation_mission_control_contribution(indexed, nation, faction_id)


def module_is_active(module: dict[str, Any]) -> bool:
    return hab_layer.module_is_active(module)


def faction_sector_states(indexed: IndexedState, faction: dict[str, Any]) -> list[dict[str, Any]]:
    return hab_layer.faction_sector_states(indexed, faction)


def active_modules_in_sectors(indexed: IndexedState, sectors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return hab_layer.active_modules_in_sectors(indexed, sectors)


def hab_sector_states(indexed: IndexedState, hab: dict[str, Any]) -> list[dict[str, Any]]:
    return hab_layer.hab_sector_states(indexed, hab)


def hab_module_records(
    indexed: IndexedState,
    hab: dict[str, Any],
    hab_module_templates: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    return hab_layer.hab_module_records(indexed, hab, hab_module_templates)


def hab_module_empty(record: dict[str, Any]) -> bool:
    return hab_layer.hab_module_empty(record)


def hab_slot_usable(record: dict[str, Any]) -> bool:
    return hab_layer.hab_slot_usable(record)


def hab_slot_summary(records: list[dict[str, Any]]) -> dict[str, int]:
    return hab_layer.hab_slot_summary(records)


def hab_module_counts(records: list[dict[str, Any]]) -> dict[str, int]:
    return hab_layer.hab_module_counts(records)


def hab_module_okay(record: dict[str, Any]) -> bool:
    return hab_layer.hab_module_okay(record)


def hab_module_functional(record: dict[str, Any]) -> bool:
    return hab_layer.hab_module_functional(record)


def hab_module_active_record(record: dict[str, Any]) -> bool:
    return hab_layer.hab_module_active_record(record)


def get_effective_module_state(record: dict[str, Any], at_date: datetime | None = None) -> dict[str, Any]:
    return hab_layer.get_effective_module_state(record, at_date)


def hab_module_current_mission_control(record: dict[str, Any]) -> int:
    return hab_layer.hab_module_current_mission_control(record)


def hab_module_projected_mission_control(record: dict[str, Any]) -> int:
    return hab_layer.hab_module_projected_mission_control(record)


def hab_core_module_record(records: list[dict[str, Any]]) -> dict[str, Any] | None:
    return hab_layer.hab_core_module_record(records)


def hab_template_special_rules(template: dict[str, Any]) -> list[str]:
    return hab_layer.hab_template_special_rules(template)


def hab_site_daily_production(hab_site: dict[str, Any] | None, resource: str) -> float:
    return hab_layer.hab_site_daily_production(hab_site, resource, config=HAB_CONFIG)


def faction_active_org_mining_bonus(indexed: IndexedState, faction: dict[str, Any]) -> float:
    return hab_layer.faction_active_org_mining_bonus(indexed, faction, faction_councilor_ids)


def faction_mining_multiplier(
    indexed: IndexedState,
    faction: dict[str, Any] | None,
    resource: str,
    effect_contexts: dict[str, list[str]],
    effect_templates: dict[str, dict[str, Any]],
) -> float:
    return hab_layer.faction_mining_multiplier(
        indexed,
        faction,
        resource,
        effect_contexts,
        effect_templates,
        config=HAB_CONFIG,
        faction_councilor_ids=faction_councilor_ids,
    )


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
) -> float:
    return hab_layer.hab_template_income(
        resource,
        template,
        hab_has_construction,
        indexed=indexed,
        faction=faction,
        hab_site=hab_site,
        effect_contexts=effect_contexts,
        effect_templates=effect_templates,
        mining_rate=mining_rate,
        config=HAB_CONFIG,
        faction_councilor_ids=faction_councilor_ids,
    )


def hab_template_direct_support(resource: str, template: dict[str, Any]) -> float:
    return hab_layer.hab_template_direct_support(resource, template, config=HAB_CONFIG)


def hab_template_crew_support(resource: str, template: dict[str, Any]) -> float:
    return hab_layer.hab_template_crew_support(resource, template, config=HAB_CONFIG)


def hab_template_support(resource: str, template: dict[str, Any], include_crew_support: bool = True) -> float:
    return hab_layer.hab_template_support(resource, template, include_crew_support, config=HAB_CONFIG)


def hab_crew(records: list[dict[str, Any]]) -> int:
    return hab_layer.hab_crew(records)


def hab_administration_modifier(records: list[dict[str, Any]], at_date: datetime | None = None) -> float:
    return hab_layer.hab_administration_modifier(records, at_date)


def hab_farm_crew_discount(records: list[dict[str, Any]], any_core_completed: bool) -> int:
    return hab_layer.hab_farm_crew_discount(records, any_core_completed)


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
    at_date: datetime | None = None,
) -> dict[str, float]:
    return hab_layer.hab_monthly_resource_income(
        hab,
        records,
        resource,
        administration_modifier,
        science_adviser_multiplier,
        administration_adviser_multiplier,
        indexed=indexed,
        faction=faction,
        effect_contexts=effect_contexts,
        effect_templates=effect_templates,
        mining_rate=mining_rate,
        at_date=at_date,
        config=HAB_CONFIG,
        faction_councilor_ids=faction_councilor_ids,
    )


def faction_is_active_human(indexed: IndexedState, faction: dict[str, Any]) -> bool:
    if faction.get("isAlien") or str(faction.get("templateName") or "") == "AlienCouncil":
        return False
    return faction_is_human_player(indexed, faction)


def scenario_customizations(indexed: IndexedState) -> dict[str, Any]:
    global_state = first_value(indexed, "TIGlobalValuesState") or {}
    customizations = global_state.get("scenarioCustomizations")
    return customizations if isinstance(customizations, dict) else {}


def active_scenario_rules(indexed: IndexedState) -> ScenarioRules:
    return SCENARIO_RULE_OVERRIDES.get(scenario_template_name(indexed), DEFAULT_SCENARIO_RULES)


def national_ip_multiplier(indexed: IndexedState) -> float:
    customizations = scenario_customizations(indexed)
    if not customizations.get("usingCustomizations"):
        return 1.0
    value = as_float(customizations.get("nationalIPMultiplier"), 1.0)
    return value if value > 0.0 else 1.0


def scenario_float(indexed: IndexedState, key: str, default: float = 1.0) -> float:
    return as_float(scenario_customizations(indexed).get(key), default)


def research_speed_modifier(indexed: IndexedState) -> float:
    value = scenario_float(indexed, "researchSpeedMultiplier", 1.0)
    return value if value > 0.0 else 1.0


def current_save_datetime(indexed: IndexedState) -> datetime | None:
    time_state = first_value(indexed, "TITimeState") or {}
    return ti_datetime(time_state.get("currentDateTime"))


def faction_is_player(indexed: IndexedState, faction: dict[str, Any]) -> bool:
    return faction_is_human_player(indexed, faction)


def faction_mining_rate(indexed: IndexedState, faction: dict[str, Any]) -> float:
    if faction_is_player(indexed, faction):
        return scenario_float(indexed, "miningRatePlayer", 1.0)
    if faction.get("templateName") == "AlienCouncil":
        return scenario_float(indexed, "miningRateAlien", 1.0)
    return scenario_float(indexed, "miningRateHumanAI", 1.0)


def faction_hab_states(indexed: IndexedState, faction: dict[str, Any]) -> list[tuple[int, dict[str, Any]]]:
    result: dict[int, dict[str, Any]] = {}
    for sector in faction_sector_states(indexed, faction):
        hab_id = ref_id(sector.get("hab"))
        hab = state_value_by_id(indexed, hab_id)
        if hab_id is not None and isinstance(hab, dict):
            result[hab_id] = hab
    return list(result.items())


def faction_ship_states(indexed: IndexedState, faction: dict[str, Any]) -> list[dict[str, Any]]:
    ships: list[dict[str, Any]] = []
    fleet_refs = faction.get("fleets") if isinstance(faction.get("fleets"), list) else []
    for fleet_ref in fleet_refs:
        fleet = state_value_by_id(indexed, ref_id(fleet_ref))
        if not isinstance(fleet, dict):
            continue
        for ship_ref in fleet.get("ships") if isinstance(fleet.get("ships"), list) else []:
            ship = state_value_by_id(indexed, ref_id(ship_ref))
            if isinstance(ship, dict):
                ships.append(ship)
    return ships


def faction_ship_designs(faction: dict[str, Any]) -> dict[str, dict[str, Any]]:
    designs = faction.get("shipDesigns") if isinstance(faction.get("shipDesigns"), list) else []
    return {str(item.get("dataName")): item for item in designs if isinstance(item, dict) and item.get("dataName")}


def ti_datetime(value: Any) -> datetime | None:
    if not isinstance(value, dict):
        return None
    try:
        return datetime(
            int(value.get("year", 1)),
            int(value.get("month", 1)),
            int(value.get("day", 1)),
            int(value.get("hour", 0)),
            int(value.get("minute", 0)),
            int(value.get("second", 0)),
            int(value.get("millisecond", 0)) * 1000,
        )
    except (TypeError, ValueError):
        return None


def human_faction_entries(indexed: IndexedState) -> list[tuple[int, dict[str, Any]]]:
    entries: list[tuple[int, dict[str, Any]]] = []
    for entry in type_entries(indexed, "TIFactionState"):
        faction = entry.get("Value") or {}
        state_id = raw_state_id(entry)
        if state_id is None or faction.get("templateName") == "AlienCouncil":
            continue
        entries.append((state_id, faction))
    return entries


def faction_brief(faction_id: int | None, faction: dict[str, Any] | None) -> dict[str, Any] | None:
    if not faction:
        return None
    return {
        "id": faction_id,
        "template": faction.get("templateName"),
        "display": faction.get("displayName"),
        "ideology": faction_ideology_key(faction),
    }


def extant_nation_states(indexed: IndexedState) -> list[dict[str, Any]]:
    return [
        entry.get("Value") or {}
        for entry in type_entries(indexed, "TINationState")
        if nation_population_millions(indexed, entry.get("Value") or {}) > 0.0
    ]
