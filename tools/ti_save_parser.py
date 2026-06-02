#!/usr/bin/env python3
"""Compact Terra Invicta save parser.

The goal is to avoid repeatedly sending the full decompressed save through an
LLM context. The CLI parses the local save, builds a small indexed snapshot, and
prints only the requested slice.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from types import MappingProxyType
from typing import Any

from ti_parser_core import (
    DEFAULT_CACHE_DIR,
    SAVE_GLOB,
    IndexedState,
    apply_effect_modifiers,
    as_float,
    build_index,
    cache_key,
    campaign_code,
    candidate_save_dirs,
    candidate_templates_dirs,
    clean_number,
    clean_numbers,
    effect_modifier_delta,
    faction_effect_contexts,
    file_fingerprint,
    find_faction_state,
    find_latest_save,
    first_value,
    json_default,
    load_named_templates,
    load_save,
    load_trait_templates,
    match_raw_state,
    print_json,
    raw_name_values,
    raw_state_id,
    ref_id,
    ref_summary,
    region_nation_summary,
    resolve_ref,
    resolve_save_path,
    resolve_templates_dir,
    save_fingerprint,
    short_type,
    snapshot_fingerprint,
    state_value_by_id,
    type_entries,
)
import ti_parser_snapshot as snapshot_layer
import ti_parser_income as income_layer
import ti_parser_hab as hab_layer
import ti_parser_org as org_layer
from ti_parser_snapshot import SnapshotConfig


SCHEMA_VERSION = 4
DEFAULT_MAX_COUNCILOR_ATTRIBUTE = 25
DAYS_PER_YEAR = 365.2422
DEFAULT_GLOBAL_CONFIG = {
    "baseEarthSaleInefficiency": 0.05,
    "ExcessMCToMoneyConversion_Day": 0.2,
    "ExcessMCToResearchConversion_Day": 0.075,
    "TIMissionModifier_ControlPointOverage_Multiplier": 1.0 / 3.0,
    "controlPointCostScaling": 0.6,
    "controlPointMaintenanceDivisor": 2.0,
    "financialSectorFundingBonus": 1.05,
    "knowledgeSectorResearchBonus": 1.05,
    "researchBonusPerSlotInUse": 0.05,
    "categoryBonusPenaltyPerExtraSlot": 0.9,
    "first20ExtraProjectBonusPct": 0.05,
    "second20ExtraProjectBonusPct": 0.03,
    "overageExtraProjectBonusPct": 0.01,
    "spaceMineFreebies": 0,
    "spaceResourceToTons": 0.1,
    "crewWaterConsumptionTons_year": 3.5,
    "crewVolatilesConsumptionTons_year": 3.5,
    "crewSalary_year": 0.1,
}
MIN_POPULATION_FOR_FIRST_ARMY_MILLIONS = 5.0
MIN_POPULATION_FOR_ADDITIONAL_ARMIES_PER_MILLIONS = 25.0
MIN_CONTROL_POINTS_FOR_NAVY = 4
MIN_CONTROL_POINTS_FOR_NAVY_EXCEPTION = 3
PCGDP_FOR_NAVY_EXCEPTION = 40000.0
STANDARD_GRAVITY_MPS2 = 9.806650161743164
GRAVITATIONAL_CONSTANT = 6.67384e-11
NATION_PRIORITY_ROWS = (
    ("Economy", "경제", "Economy", "Economy", 1),
    ("Welfare", "복지", "Welfare", "Welfare", 1),
    ("Environment", "환경", "Environment", "Environment", 1),
    ("Knowledge", "지식", "Knowledge", "Knowledge", 1),
    ("Unity", "통합", "Unity", "Unity", 2),
    ("Oppression", "억압", "Oppression", "Oppression", 1),
    ("Funding", "기금", "Funding", "Funding", 1),
    ("Spoils", "이권", "Spoils", "Spoils", 1),
    ("Boost", "부스트", "LaunchFacilities", "LaunchFacilities", 2),
    ("Military", "군사", "Military", "Military", 1),
    ("BuildArmy", "군대 창설", "Military_BuildArmy", "Military_BuildArmy", 60),
    ("BuildNavy", "해군 건설", "Military_BuildNavy", "Military_BuildNavy", 100),
    ("BuildNuclearWeapons", "핵무기", "Military_BuildNuclearWeapons", "Military_BuildNuclearWeapons", 40),
)
NATION_INACTIVE_PRIORITY_KEYS = (
    "Government",
    "Civilian_InitiateSpaceflightProgram",
    "MissionControl",
    "Military_FoundMilitary",
    "Military_InitiateNuclearProgram",
    "Military_BuildSpaceDefenses",
    "Military_BuildSTOSquadron",
)
HAB_MONTHLY_RESOURCES = (
    "MissionControl",
    "Money",
    "Research",
    "Boost",
    "Water",
    "Volatiles",
    "Metals",
    "NobleMetals",
    "Fissiles",
    "Antimatter",
    "Exotics",
    "Influence",
    "Operations",
    "Projects",
)
HAB_INCOME_FIELDS = {
    "Money": "incomeMoney_month",
    "Influence": "incomeInfluence_month",
    "Operations": "incomeOps_month",
    "Research": "incomeResearch_month",
    "Projects": "incomeProjects",
    "Boost": "incomeBoost_month",
    "MissionControl": "missionControl",
    "Water": "incomeWater_month",
    "Volatiles": "incomeVolatiles_month",
    "Metals": "incomeMetals_month",
    "NobleMetals": "incomeNobles_month",
    "Fissiles": "incomeFissiles_month",
    "Antimatter": "incomeAntimatter_month",
    "Exotics": "incomeExotics_month",
}
HAB_SUPPORT_FIELDS = {
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
HAB_ADMIN_ADVISER_RESOURCES = {"Money", "Water", "Volatiles", "Metals", "NobleMetals", "Fissiles"}
HAB_EFFICIENCY_RESOURCES = {"Money", "Water", "Volatiles", "Metals", "NobleMetals", "Fissiles", "Research", "Influence", "Operations", "Exotics"}
TOPBAR_RESOURCES = (
    "Money",
    "Influence",
    "Operations",
    "Boost",
    "MissionControl",
    "Research",
    "Water",
    "Volatiles",
    "Metals",
    "NobleMetals",
    "Fissiles",
    "Antimatter",
    "Exotics",
)
WORLD_MARKET_RESOURCES = ("Water", "Volatiles", "Metals", "NobleMetals", "Fissiles", "Antimatter", "Exotics")
WORLD_SELLABLE_MARKET_RESOURCES = {"Metals", "NobleMetals", "Fissiles", "Antimatter", "Exotics"}
SAFE_GREENHOUSE_GAS_LEVELS = {
    "CO2": 325.68,
    "CH4": 1.3,
    "N2O": 0.29,
    "StratosphericAerosols": 0.0,
}
TEMPERATURE_ANOMALY_FACTOR = 94.5
CH4_RELATIVE_IMPACT = 21.0
N2O_RELATIVE_IMPACT = 289.0
AEROSOL_TEMPERATURE_DIVISOR = 0.03885
BASIC_SPACE_RESOURCES = ("Water", "Volatiles", "Metals", "NobleMetals", "Fissiles")
MINING_BONUS_CONTEXTS = {
    "Water": "MiningWaterBonus",
    "Volatiles": "MiningVolatilesBonus",
    "Metals": "MiningMetalsBonus",
    "NobleMetals": "MiningNoblesBonus",
    "Fissiles": "MiningFissilesBonus",
}
HAB_SITE_PRODUCTION_FIELDS = {
    "Water": "water_day",
    "Volatiles": "volatiles_day",
    "Metals": "metals_day",
    "NobleMetals": "nobles_day",
    "Fissiles": "fissiles_day",
}
COUNCILOR_INCOME_FIELDS = {
    "Money": ("incomeMoney", "incomeMoney_month", "Administration"),
    "Influence": ("incomeInfluence", "incomeInfluence_month", "Persuasion"),
    "Operations": ("incomeOps", "incomeOps_month", "Command"),
    "Boost": ("incomeBoost", "incomeBoost_month", None),
    "Research": ("incomeResearch", "incomeResearch_month", "Science"),
    "MissionControl": (None, "incomeMissionControl", None),
    "Projects": ("incomeProjects", "projectCapacityGranted", None),
}
FACTION_IDEOLOGY_BY_TEMPLATE = {
    "ResistCouncil": "Resist",
    "DestroyCouncil": "Destroy",
    "ExploitCouncil": "Exploit",
    "SubmitCouncil": "Submit",
    "AppeaseCouncil": "Appease",
    "CooperateCouncil": "Cooperate",
    "EscapeCouncil": "Escape",
    "AlienCouncil": "Alien",
}
INCOME_CONFIG = income_layer.IncomeConfig(
    days_per_year=DAYS_PER_YEAR,
    financial_sector_funding_bonus=DEFAULT_GLOBAL_CONFIG["financialSectorFundingBonus"],
    knowledge_sector_research_bonus=DEFAULT_GLOBAL_CONFIG["knowledgeSectorResearchBonus"],
    min_population_for_first_army_millions=MIN_POPULATION_FOR_FIRST_ARMY_MILLIONS,
    min_population_for_additional_armies_per_millions=MIN_POPULATION_FOR_ADDITIONAL_ARMIES_PER_MILLIONS,
    min_control_points_for_navy=MIN_CONTROL_POINTS_FOR_NAVY,
    min_control_points_for_navy_exception=MIN_CONTROL_POINTS_FOR_NAVY_EXCEPTION,
    pcgdp_for_navy_exception=PCGDP_FOR_NAVY_EXCEPTION,
    faction_ideology_by_template=MappingProxyType(FACTION_IDEOLOGY_BY_TEMPLATE),
    councilor_income_fields=MappingProxyType(COUNCILOR_INCOME_FIELDS),
)
HAB_LEO_PRIORITY_RULES = {
    "LEOBonusEconomy": "Economy",
    "LEOBonusWelfare": "Welfare",
    "LEOBonusKnowledge": "Knowledge",
    "LEOBonusUnity": "Unity",
    "LEOBonusMiltech": "Military",
    "LEOBonusLaunchFacilities": "LaunchFacilities",
    "LEOBonusMissionControl": "MissionControl",
    "LEOBonusOppression": "Oppression",
    "LEOBonusEnvironment": "Environment",
    "LEOBonusGovernment": "Government",
}
HAB_CONFIG = hab_layer.HabConfig(
    days_per_year=DAYS_PER_YEAR,
    default_global_config=MappingProxyType(DEFAULT_GLOBAL_CONFIG),
    hab_income_fields=MappingProxyType(HAB_INCOME_FIELDS),
    hab_support_fields=MappingProxyType(HAB_SUPPORT_FIELDS),
    hab_site_production_fields=MappingProxyType(HAB_SITE_PRODUCTION_FIELDS),
    basic_space_resources=BASIC_SPACE_RESOURCES,
    mining_bonus_contexts=MappingProxyType(MINING_BONUS_CONTEXTS),
    hab_admin_adviser_resources=frozenset(HAB_ADMIN_ADVISER_RESOURCES),
    hab_leo_priority_rules=MappingProxyType(HAB_LEO_PRIORITY_RULES),
)
FACTION_RESOURCES = (
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
COUNCILOR_ATTRIBUTES = (
    "Persuasion",
    "Investigation",
    "Espionage",
    "Command",
    "Administration",
    "Science",
    "Security",
    "Loyalty",
    "ApparentLoyalty",
)
ORG_ATTRIBUTE_FIELDS = {
    "Persuasion": "persuasion",
    "Investigation": "investigation",
    "Espionage": "espionage",
    "Command": "command",
    "Administration": "administration",
    "Science": "science",
    "Security": "security",
}
ORG_PLAN_SCORE_ATTRIBUTES = tuple(ORG_ATTRIBUTE_FIELDS)
ORG_PLAN_FOCUS_CHOICES = ("balanced", *(attribute.casefold() for attribute in ORG_PLAN_SCORE_ATTRIBUTES))
ORG_PLAN_COST_FIELDS = {
    "Money": "costMoney",
    "Influence": "costInfluence",
    "Operations": "costOps",
    "Boost": "costBoost",
}
NATION_CONDITION_FIELDS = {
    "TINationCondition_fCohesion": "cohesion",
    "TINationCondition_fDemocracy": "democracy",
    "TINationCondition_fEducation": "education",
    "TINationCondition_fInequality": "inequality",
    "TINationCondition_fUnrest": "unrest",
}

SNAPSHOT_CONFIG = SnapshotConfig(
    schema_version=SCHEMA_VERSION,
    default_max_councilor_attribute=DEFAULT_MAX_COUNCILOR_ATTRIBUTE,
    councilor_attributes=COUNCILOR_ATTRIBUTES,
    faction_resources=FACTION_RESOURCES,
    org_attribute_fields=tuple(ORG_ATTRIBUTE_FIELDS.items()),
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


def command_org_plan(save_path: Path, templates_dir: Path | None, args: argparse.Namespace) -> None:
    data = load_save(save_path)
    indexed = build_index(data)
    result = calculate_org_plan(
        indexed,
        templates_dir,
        faction_name=args.faction,
        focus=args.focus,
        top=args.top,
        include_unassigned=not args.market_only,
        max_actions=args.max_actions,
        beam_width=args.beam_width,
        include_all_candidates=args.all_candidates,
    )
    print_json(result, compact=args.compact)


# Keep the public org-plan API on this module while delegating implementation
# to the dedicated org parser module.
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
org_plan_attribute_delta = org_layer.org_plan_attribute_delta
org_plan_org_row = org_layer.org_plan_org_row
org_plan_region_nation_id = org_layer.org_plan_region_nation_id
org_plan_owner_eligibility = org_layer.org_plan_owner_eligibility
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


def nation_influence_contribution_month(indexed: IndexedState, nation: dict[str, Any], faction: dict[str, Any]) -> float:
    return income_layer.nation_influence_contribution_month(indexed, nation, faction, INCOME_CONFIG)


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


def hab_administration_modifier(records: list[dict[str, Any]]) -> float:
    return hab_layer.hab_administration_modifier(records)


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
        config=HAB_CONFIG,
        faction_councilor_ids=faction_councilor_ids,
    )


def hab_power_summary(records: list[dict[str, Any]]) -> dict[str, int]:
    return hab_layer.hab_power_summary(records)


def hab_tech_bonuses(records: list[dict[str, Any]]) -> dict[str, float]:
    return hab_layer.hab_tech_bonuses(records)


def hab_leo_priority_bonuses(hab: dict[str, Any], records: list[dict[str, Any]]) -> dict[str, float]:
    return hab_layer.hab_leo_priority_bonuses(hab, records, config=HAB_CONFIG)


def hab_control_point_capacity(hab: dict[str, Any], records: list[dict[str, Any]]) -> int:
    return hab_layer.hab_control_point_capacity(hab, records)


def hab_module_construction_time_modifier(records: list[dict[str, Any]]) -> float:
    modifiers = sorted(
        as_float(record.get("template", {}).get("constructionTimeModifier"), 1.0)
        for record in records
        if hab_module_active_record(record)
        and as_float(record.get("template", {}).get("constructionTimeModifier"), 1.0) != 1.0
        and not record.get("template", {}).get("allowsShipConstruction")
    )
    result = 1.0
    modifier_index = 1.0
    for modifier in modifiers:
        if modifier <= 0.0:
            continue
        if modifier < 1.0:
            result *= 1.0 - ((1.0 - modifier) / (modifier_index * modifier_index))
            modifier_index += 1.0
        else:
            result *= modifier
    return result


def hab_location_summary(
    indexed: IndexedState,
    templates_dir: Path | None,
    hab: dict[str, Any],
) -> dict[str, Any]:
    orbit = ref_summary(indexed, hab.get("orbitState"))
    site = ref_summary(indexed, hab.get("habSite"))
    barycenter = ref_summary(indexed, hab.get("barycenter"))
    summary = {
        "orbit": orbit,
        "site": site,
        "barycenter": barycenter,
        "gravity_mg": None,
        "maxTier": None,
    }
    if not templates_dir or not orbit or not barycenter:
        return summary

    orbit_templates = load_named_templates(templates_dir, "TIOrbitTemplate.json")
    body_templates = load_named_templates(templates_dir, "TISpaceBodyTemplate.json")
    orbit_template = orbit_templates.get(str(orbit.get("template")), {})
    body_template = body_templates.get(str(barycenter.get("template")), {})
    max_hab_size = int(as_float(body_template.get("maxHabSize"), 0.0))
    if max_hab_size:
        summary["maxTier"] = max(1, min(max_hab_size, 3))
    altitude_km = as_float(orbit_template.get("altitude_km"), 0.0)
    mean_radius_km = as_float(body_template.get("meanRadius_km"), 0.0)
    mass_kg = as_float(body_template.get("mass_kg"), 0.0)
    if altitude_km and mean_radius_km and mass_kg:
        semi_major_axis_m = (mean_radius_km + altitude_km) * 1000.0
        gravity_mps2 = GRAVITATIONAL_CONSTANT * mass_kg / (semi_major_axis_m * semi_major_axis_m)
        summary["gravity_mg"] = gravity_mps2 / STANDARD_GRAVITY_MPS2 * 1000.0
        summary["altitude_km"] = altitude_km
    return summary


def calculate_hab_ui(
    indexed: IndexedState,
    templates_dir: Path | None,
    hab_name: str,
) -> dict[str, Any]:
    found = match_raw_state(indexed, "TIHabState", hab_name)
    if not found:
        raise SystemExit(f"Hab not found: {hab_name}")
    hab_id, hab = found
    hab_module_templates = load_named_templates(templates_dir, "TIHabModuleTemplate.json")
    trait_templates = load_trait_templates(templates_dir)
    effect_templates = load_named_templates(templates_dir, "TIEffectTemplate.json")
    faction_ref = resolve_ref(indexed, hab.get("faction"))
    faction = faction_ref[2] if faction_ref else {}
    faction_id = ref_id(hab.get("faction"))
    effect_contexts = faction_effect_contexts(indexed, faction_id) if faction_id is not None else {}
    _, councilor_by_id = councilor_summary_maps(indexed, trait_templates)
    records = hab_module_records(indexed, hab, hab_module_templates)
    active_records = [record for record in records if hab_module_active_record(record)]
    okay_records = [record for record in records if hab_module_okay(record)]
    administration_modifier = hab_administration_modifier(records)
    location = hab_location_summary(indexed, templates_dir, hab)
    monthly = {
        resource: hab_monthly_resource_income(
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
            mining_rate=faction_mining_rate(indexed, faction) if faction else 1.0,
        )
        for resource in HAB_MONTHLY_RESOURCES
    }
    construction_time_modifier = hab_module_construction_time_modifier(records)
    output = {
        "identity": {
            "id": hab_id,
            "display": hab.get("displayName"),
            "habType": hab.get("habType"),
            "tier": hab.get("tier"),
            "maxTier": location.get("maxTier"),
            "faction": ref_summary(indexed, hab.get("faction")),
            "location": location,
        },
        "status": {
            "crew": hab_crew(records),
            "power": hab_power_summary(records),
            "missionControlCost": max(int(-monthly["MissionControl"]["net"]), 0),
            "controlPointCapacity": hab_control_point_capacity(hab, records),
            "anyCoreCompleted": bool(hab.get("anyCoreCompleted")),
            "underConstructionModules": sum(1 for record in records if hab_module_okay(record) and not record.get("completed")),
            "farmCrewDiscount": hab_farm_crew_discount(records, bool(hab.get("anyCoreCompleted"))),
            "administrationModuleModifier": administration_modifier,
            "moduleConstructionTimeModifier": construction_time_modifier,
            "moduleConstructionSpeedBonus": 1.0 - construction_time_modifier,
        },
        "monthlyResources": monthly,
        "bonuses": {
            "tech": hab_tech_bonuses(records),
            "leoPriority": hab_leo_priority_bonuses(hab, records),
        },
        "modules": {
            "active": len(active_records),
            "okay": len(okay_records),
            "slots": hab_slot_summary(records),
            "counts": hab_module_counts(records),
            "records": [
                {
                    "id": record.get("id"),
                    "sectorId": record.get("sectorId"),
                    "sectorNum": record.get("sectorNum"),
                    "sectorFaction": record.get("sectorFaction"),
                    "sectorFactionId": record.get("sectorFactionId"),
                    "habFactionId": record.get("habFactionId"),
                    "sectorOwnedByHabFaction": record.get("sectorOwnedByHabFaction"),
                    "slot": record.get("slot"),
                    "display": record.get("display"),
                    "template": record.get("templateName"),
                    "priorTemplate": record.get("priorTemplateName"),
                    "completed": record.get("completed"),
                    "powered": record.get("powered"),
                    "active": hab_module_active_record(record),
                    "crew": record.get("template", {}).get("crew"),
                    "power": record.get("template", {}).get("power"),
                }
                for record in records
                if hab_module_okay(record)
            ],
        },
    }
    return clean_numbers(output, 6)


def command_hab_ui(save_path: Path, templates_dir: Path | None, args: argparse.Namespace) -> None:
    data = load_save(save_path)
    indexed = build_index(data)
    result = calculate_hab_ui(indexed, templates_dir, args.name)
    print_json(result, compact=args.compact)


def summarize_hab_slots(
    indexed: IndexedState,
    templates_dir: Path | None,
    hab_id: int,
    hab: dict[str, Any],
    hab_module_templates: dict[str, dict[str, Any]],
    include_module_counts: bool = False,
) -> dict[str, Any]:
    records = hab_module_records(indexed, hab, hab_module_templates)
    result = {
        "id": hab_id,
        "display": hab.get("displayName"),
        "habType": hab.get("habType"),
        "tier": hab.get("tier"),
        "location": hab_location_summary(indexed, templates_dir, hab),
        "slots": hab_slot_summary(records),
    }
    if include_module_counts:
        result["moduleCounts"] = hab_module_counts(records)
    return result


def calculate_hab_slots(
    indexed: IndexedState,
    templates_dir: Path | None,
    faction_name: str | None = None,
    include_all: bool = False,
    include_module_counts: bool = False,
) -> dict[str, Any]:
    faction_id, faction = find_faction_state(indexed, faction_name)
    hab_module_templates = load_named_templates(templates_dir, "TIHabModuleTemplate.json")
    rows_all = [
        summarize_hab_slots(indexed, templates_dir, hab_id, hab, hab_module_templates, include_module_counts)
        for hab_id, hab in faction_hab_states(indexed, faction)
    ]
    totals = {
        key: sum(int(row["slots"][key]) for row in rows_all)
        for key in ("raw", "usable", "occupied", "empty", "locked", "lockedEmpty")
    }
    rows = rows_all
    if not include_all:
        rows = [row for row in rows if row["slots"]["empty"] > 0]
    rows.sort(key=lambda row: (-int(row["slots"]["empty"]), str(row.get("display") or "")))
    return {
        "faction": {
            "id": faction_id,
            "template": faction.get("templateName"),
            "display": faction.get("displayName"),
        },
        "filters": {
            "includeAll": include_all,
            "moduleCounts": include_module_counts,
            "returnedHabs": len(rows),
            "totalHabs": len(rows_all),
        },
        "totals": totals,
        "habs": rows,
        "sourceNotes": [
            "Raw save sectors can include locked future placeholder sectors.",
            "Only slots in sectors owned by the hab's current faction are counted as currently usable build slots.",
        ],
    }


def command_hab_slots(save_path: Path, templates_dir: Path | None, args: argparse.Namespace) -> None:
    data = load_save(save_path)
    indexed = build_index(data)
    result = calculate_hab_slots(
        indexed,
        templates_dir,
        faction_name=args.faction,
        include_all=args.all,
        include_module_counts=args.module_counts,
    )
    print_json(clean_numbers(result, 6), compact=args.compact)


def hab_projected_power_summary(records: list[dict[str, Any]]) -> dict[str, int]:
    generated = 0
    consumed = 0
    for record in records:
        if hab_module_empty(record) or record.get("destroyed") or record.get("decommissioning"):
            continue
        power = int(as_float(record.get("template", {}).get("power"), 0.0))
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


def hab_barycenter_state(indexed: IndexedState, hab: dict[str, Any]) -> dict[str, Any]:
    return state_value_by_id(indexed, ref_id(hab.get("barycenter"))) or {}


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
    body_template = (body_templates or {}).get(template_name, {})
    return max(
        as_float(body.get("irradiatedMultiplier"), 1.0),
        as_float(body_template.get("irradiatedMultiplier"), 1.0),
    ) > 1.0


def module_unmet_requirements(
    indexed: IndexedState,
    template: dict[str, Any],
    hab: dict[str, Any],
    faction: dict[str, Any],
    target_tier: int,
    module_counts: dict[str, int],
    body_templates: dict[str, dict[str, Any]] | None = None,
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
    if template.get("onePerHab") and module_counts.get(template_name, 0) > 0:
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


def hypothetical_completed_module_record(template: dict[str, Any]) -> dict[str, Any]:
    return {
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
) -> dict[str, dict[str, float]]:
    science_adviser_multiplier = 1.0 + state_adviser_attribute_bonus(hab, councilor_by_id, "Science")
    administration_adviser_multiplier = 1.0 + state_adviser_attribute_bonus(hab, councilor_by_id, "Administration")
    after_records = records + [hypothetical_completed_module_record(template)]
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


HAB_PLAN_TECH_BONUS_CATEGORIES = (
    "Energy",
    "InformationScience",
    "LifeScience",
    "Materials",
    "MilitaryScience",
    "SocialScience",
    "SpaceScience",
    "Xenology",
)

HAB_PLAN_FOCUS_CHOICES = ("balanced", "research", "projects", "category-bonus", "resources")
PROJECT_ANALYSIS_SORT_CHOICES = (
    "research-sustainable",
    "research-raw",
    "resource-recovery",
    "module-unlock",
    "short-horizon",
    "long-horizon",
    "low-cost",
)
PROJECT_ANALYSIS_MODULE_SAMPLE_COUNTS = (1, 2, 4)


def module_research_score(monthly_delta: dict[str, dict[str, float]]) -> float:
    return as_float(monthly_delta.get("Research", {}).get("net"), 0.0)


def module_project_score(monthly_delta: dict[str, dict[str, float]]) -> float:
    return as_float(monthly_delta.get("Projects", {}).get("net"), 0.0)


def module_category_bonus_score(template: dict[str, Any]) -> float:
    return sum(tech_bonus_sum(template.get("techBonuses"), category) for category in HAB_PLAN_TECH_BONUS_CATEGORIES)


def module_balanced_score(research_score: float, resource_score: float) -> float:
    return research_score + resource_score


def module_resource_score(monthly_delta: dict[str, dict[str, float]], scarcity_weights: dict[str, float]) -> float:
    return sum(
        as_float(row.get("net"), 0.0) * scarcity_weights.get(resource, 1.0)
        for resource, row in monthly_delta.items()
        if resource in scarcity_weights
    )


def module_candidate_row(
    indexed: IndexedState,
    hab: dict[str, Any],
    records: list[dict[str, Any]],
    faction: dict[str, Any],
    template: dict[str, Any],
    projected_power: dict[str, int],
    mission_control_available: float,
    effect_contexts: dict[str, list[str]],
    effect_templates: dict[str, dict[str, Any]],
    mining_rate: float,
    scarcity_weights: dict[str, float],
    councilor_by_id: dict[int, dict[str, Any]],
) -> dict[str, Any]:
    monthly_delta = candidate_module_monthly_delta(
        indexed,
        hab,
        records,
        faction,
        template,
        effect_contexts,
        effect_templates,
        mining_rate,
        councilor_by_id,
    )
    power = int(as_float(template.get("power"), 0.0))
    mission_control = int(as_float(template.get("missionControl"), 0.0))
    research_score = module_research_score(monthly_delta)
    project_score = module_project_score(monthly_delta)
    category_bonus_score = module_category_bonus_score(template)
    resource_score = module_resource_score(monthly_delta, scarcity_weights)
    return {
        "template": template.get("dataName"),
        "display": template_display(str(template.get("dataName")), template),
        "tier": int(as_float(template.get("tier"), 0.0)),
        "habType": template.get("habType") or "Any",
        "power": power,
        "projectedPowerAfterOne": projected_power.get("net", 0) + power,
        "missionControl": mission_control,
        "onePerHab": bool(template.get("onePerHab")),
        "fitsCurrentProjectedPower": projected_power.get("net", 0) + power >= 0,
        "fitsCurrentMissionControl": mission_control >= 0 or mission_control_available + mission_control >= 0,
        "crew": int(as_float(template.get("crew"), 0.0)),
        "buildTime_Days": as_float(template.get("buildTime_Days"), 0.0),
        "buildCostTemplateWeights": module_build_cost_map(template),
        "affordableByTemplateWeights": module_affordable_with_template_weights(template, faction),
        "monthlyDelta": monthly_delta,
        "techBonuses": tech_bonus_map_for_template(template),
        "specialRules": hab_template_special_rules(template),
        "scores": {
            "research": research_score,
            "projects": project_score,
            "category-bonus": category_bonus_score,
            "resources": resource_score,
            "balanced": module_balanced_score(research_score, resource_score),
        },
        "scoreComponents": {
            "researchMonthlyNet": research_score,
            "projectsMonthlyNet": project_score,
            "categoryBonusSum": category_bonus_score,
            "resourceScarcityWeightedNet": resource_score,
        },
    }


def tech_bonus_map_for_template(template: dict[str, Any]) -> dict[str, float]:
    bonuses: dict[str, float] = {}
    for item in template.get("techBonuses") if isinstance(template.get("techBonuses"), list) else []:
        if not isinstance(item, dict):
            continue
        category = str(item.get("category"))
        bonuses[category] = bonuses.get(category, 0.0) + as_float(item.get("bonus"), 0.0)
    return bonuses


def hab_module_candidate_rows(
    indexed: IndexedState,
    templates_dir: Path | None,
    hab: dict[str, Any],
    records: list[dict[str, Any]],
    faction_id: int,
    faction: dict[str, Any],
    target_tier: int,
    projected_power: dict[str, int],
    mission_control_available: float,
    topbar: dict[str, Any],
) -> list[dict[str, Any]]:
    hab_module_templates = load_named_templates(templates_dir, "TIHabModuleTemplate.json")
    body_templates = load_named_templates(templates_dir, "TISpaceBodyTemplate.json")
    effect_templates = load_named_templates(templates_dir, "TIEffectTemplate.json")
    trait_templates = load_trait_templates(templates_dir)
    _, councilor_by_id = councilor_summary_maps(indexed, trait_templates)
    effect_contexts = faction_effect_contexts(indexed, faction_id)
    mining_rate = faction_mining_rate(indexed, faction)
    scarcity_weights = resource_scarcity_weights(topbar)
    module_counts = hab_module_counts(records)
    rows: list[dict[str, Any]] = []
    for template in hab_module_templates.values():
        reasons = module_unmet_requirements(indexed, template, hab, faction, target_tier, module_counts, body_templates)
        if reasons:
            continue
        row = module_candidate_row(
            indexed,
            hab,
            records,
            faction,
            template,
            projected_power,
            mission_control_available,
            effect_contexts,
            effect_templates,
            mining_rate,
            scarcity_weights,
            councilor_by_id,
        )
        has_score = any(abs(as_float(value, 0.0)) > 0.0 for value in row.get("scores", {}).values())
        if not has_score and row["power"] <= 0 and row["missionControl"] <= 0:
            continue
        rows.append(clean_numbers(row, 6))
    return rows


def sorted_candidates(candidates: list[dict[str, Any]], focus: str, top: int) -> list[dict[str, Any]]:
    return sorted(
        candidates,
        key=lambda row: (
            not bool(row.get("affordableByTemplateWeights")),
            -as_float((row.get("scores") or {}).get(focus), 0.0),
            not bool(row.get("fitsCurrentProjectedPower")),
            -int(as_float(row.get("tier"), 0.0)),
            -as_float((row.get("scores") or {}).get("balanced"), 0.0),
            str(row.get("display") or row.get("template")),
        ),
    )[:top]


def candidate_focus_score(candidate: dict[str, Any] | None, focus: str) -> float:
    if not candidate:
        return 0.0
    return as_float((candidate.get("scores") or {}).get(focus), 0.0)


def opportunity_cost_baseline(candidates: list[dict[str, Any]], focus: str) -> dict[str, Any]:
    affordable = [candidate for candidate in candidates if candidate_affordable(candidate)]
    if not affordable:
        return {"template": None, "display": None, "score": 0.0}
    best = max(
        affordable,
        key=lambda candidate: (
            candidate_focus_score(candidate, focus),
            candidate_focus_score(candidate, "balanced"),
            int(as_float(candidate.get("tier"), 0.0)),
            str(candidate.get("display") or candidate.get("template")),
        ),
    )
    score = max(candidate_focus_score(best, focus), 0.0)
    if score <= 0.0:
        return {"template": None, "display": None, "score": 0.0}
    return {
        "template": best.get("template"),
        "display": best.get("display"),
        "score": score,
    }


def opportunity_cost_for_score(score: float, baseline_score: float) -> float:
    return max(baseline_score - score, 0.0)


def opportunity_costs_for_candidate(candidate: dict[str, Any], baselines: dict[str, dict[str, Any]]) -> dict[str, Any]:
    costs: dict[str, Any] = {}
    for focus, baseline in baselines.items():
        baseline_score = as_float(baseline.get("score"), 0.0)
        score = candidate_focus_score(candidate, focus)
        cost = opportunity_cost_for_score(score, baseline_score)
        costs[focus] = {
            "bestAlternative": baseline,
            "score": score,
            "cost": cost,
            "scoreAfterOpportunityCost": score - cost,
        }
    return costs


def annotate_candidate_opportunity_costs(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    baselines = {focus: opportunity_cost_baseline(candidates, focus) for focus in HAB_PLAN_FOCUS_CHOICES}
    for candidate in candidates:
        candidate["opportunityCosts"] = clean_numbers(opportunity_costs_for_candidate(candidate, baselines), 6)
    return candidates


def power_candidates(candidates: list[dict[str, Any]], top: int) -> list[dict[str, Any]]:
    return sorted(
        [candidate for candidate in candidates if as_float(candidate.get("power"), 0.0) > 0.0],
        key=lambda row: (
            not bool(row.get("affordableByTemplateWeights")),
            -as_float(row.get("power"), 0.0),
            -int(as_float(row.get("tier"), 0.0)),
            str(row.get("display") or row.get("template")),
        ),
    )[:top]


def candidate_affordable(row: dict[str, Any]) -> bool:
    return bool(row.get("affordableByTemplateWeights", True))


def monthly_delta_times(delta: dict[str, dict[str, float]], count: int) -> dict[str, dict[str, float]]:
    result: dict[str, dict[str, float]] = {}
    for resource, row in delta.items():
        if not isinstance(row, dict):
            continue
        result[resource] = {
            key: as_float(value, 0.0) * count
            for key, value in row.items()
            if key in {"income", "support", "net"}
        }
    return result


def add_monthly_delta(target: dict[str, dict[str, float]], delta: dict[str, dict[str, float]], count: int = 1) -> None:
    for resource, row in monthly_delta_times(delta, count).items():
        target_row = target.setdefault(resource, {"income": 0.0, "support": 0.0, "net": 0.0})
        for key, value in row.items():
            target_row[key] = as_float(target_row.get(key), 0.0) + value


def suggested_fill_entry(
    candidate: dict[str, Any],
    count: int,
    reason: str,
    focus: str,
    baseline_score: float,
) -> dict[str, Any]:
    score_each = candidate_focus_score(candidate, focus)
    opportunity_cost_each = opportunity_cost_for_score(score_each, baseline_score)
    return {
        "count": count,
        "template": candidate.get("template"),
        "display": candidate.get("display"),
        "reason": reason,
        "tier": candidate.get("tier"),
        "powerEach": candidate.get("power"),
        "powerTotal": int(as_float(candidate.get("power"), 0.0)) * count,
        "missionControlEach": candidate.get("missionControl"),
        "missionControlTotal": int(as_float(candidate.get("missionControl"), 0.0)) * count,
        "monthlyDeltaTotal": monthly_delta_times(candidate.get("monthlyDelta") or {}, count),
        "scoresEach": candidate.get("scores"),
        "opportunityCost": {
            "focus": focus,
            "scoreEach": score_each,
            "bestAlternativeScoreEach": baseline_score,
            "costEach": opportunity_cost_each,
            "costTotal": opportunity_cost_each * count,
            "scoreAfterOpportunityCostTotal": (score_each - opportunity_cost_each) * count,
        },
    }


def suggested_hab_fill(
    candidates: list[dict[str, Any]],
    slots: int,
    focus: str,
    projected_power: int,
    mc_available: float,
) -> dict[str, Any]:
    if slots <= 0:
        return {
            "slotsRequested": slots,
            "slotsFilled": 0,
            "unfilledSlots": 0,
            "projectedPowerNetAfter": projected_power,
            "missionControlAvailableAfter": mc_available,
            "monthlyDeltaTotal": {},
            "moduleCounts": [],
            "method": "no planned empty slots",
        }

    affordable_candidates = [candidate for candidate in candidates if candidate_affordable(candidate)]
    focus_pool = sorted_candidates(affordable_candidates, focus, len(affordable_candidates))
    support_pool = power_candidates(affordable_candidates, len(affordable_candidates))
    opportunity_baseline = opportunity_cost_baseline(affordable_candidates, focus)
    baseline_score = as_float(opportunity_baseline.get("score"), 0.0)
    best_plan: dict[str, Any] | None = None

    for focus_candidate in focus_pool[:20]:
        focus_limit = 1 if focus_candidate.get("onePerHab") else slots
        focus_power = int(as_float(focus_candidate.get("power"), 0.0))
        focus_mc = int(as_float(focus_candidate.get("missionControl"), 0.0))
        focus_score = as_float((focus_candidate.get("scores") or {}).get(focus), 0.0)
        for focus_count in range(1, focus_limit + 1):
            remaining_slots = slots - focus_count
            support_options: list[tuple[dict[str, Any] | None, int]] = [(None, 0)]
            for support_candidate in support_pool[:20]:
                if support_candidate.get("template") == focus_candidate.get("template"):
                    continue
                support_limit = 1 if support_candidate.get("onePerHab") else remaining_slots
                support_options.extend((support_candidate, count) for count in range(1, support_limit + 1))

            for support_candidate, support_count in support_options:
                if support_count > remaining_slots:
                    continue
                support_power = int(as_float((support_candidate or {}).get("power"), 0.0))
                support_mc = int(as_float((support_candidate or {}).get("missionControl"), 0.0))
                power_after = projected_power + focus_power * focus_count + support_power * support_count
                mc_after = mc_available + focus_mc * focus_count + support_mc * support_count
                if power_after < 0 or mc_after < 0:
                    continue
                slots_filled = focus_count + support_count
                support_score = as_float(((support_candidate or {}).get("scores") or {}).get(focus), 0.0)
                plan_score = (
                    focus_score * focus_count
                    + support_score * support_count
                )
                opportunity_cost = max(baseline_score * slots_filled - plan_score, 0.0)
                unfilled_opportunity_cost = baseline_score * max(slots - slots_filled, 0)
                score_after_opportunity_cost = plan_score - opportunity_cost
                plan = {
                    "score": plan_score,
                    "opportunityCost": opportunity_cost,
                    "unfilledOpportunityCost": unfilled_opportunity_cost,
                    "scoreAfterOpportunityCost": score_after_opportunity_cost,
                    "slotsFilled": slots_filled,
                    "powerAfter": power_after,
                    "mcAfter": mc_after,
                    "focusCandidate": focus_candidate,
                    "focusCount": focus_count,
                    "supportCandidate": support_candidate,
                    "supportCount": support_count,
                }
                if best_plan is None or (
                    plan["scoreAfterOpportunityCost"],
                    plan["score"],
                    plan["focusCount"],
                    -plan["supportCount"],
                    plan["powerAfter"],
                ) > (
                    best_plan["scoreAfterOpportunityCost"],
                    best_plan["score"],
                    best_plan["focusCount"],
                    -best_plan["supportCount"],
                    best_plan["powerAfter"],
                ):
                    best_plan = plan

    if best_plan is None:
        return {
            "slotsRequested": slots,
            "slotsFilled": 0,
            "unfilledSlots": slots,
            "projectedPowerNetAfter": projected_power,
            "missionControlAvailableAfter": mc_available,
            "monthlyDeltaTotal": {},
            "moduleCounts": [],
            "method": "no feasible candidate set under projected power and MC",
        }

    monthly_total: dict[str, dict[str, float]] = {}
    entries = [
        suggested_fill_entry(
            best_plan["focusCandidate"],
            best_plan["focusCount"],
            f"top {focus} score",
            focus,
            baseline_score,
        ),
    ]
    add_monthly_delta(monthly_total, best_plan["focusCandidate"].get("monthlyDelta") or {}, best_plan["focusCount"])
    if best_plan["supportCandidate"] and best_plan["supportCount"]:
        entries.append(
            suggested_fill_entry(
                best_plan["supportCandidate"],
                best_plan["supportCount"],
                "power support for selected fill",
                focus,
                baseline_score,
            )
        )
        add_monthly_delta(monthly_total, best_plan["supportCandidate"].get("monthlyDelta") or {}, best_plan["supportCount"])

    return clean_numbers(
        {
            "slotsRequested": slots,
            "slotsFilled": best_plan["slotsFilled"],
            "unfilledSlots": slots - best_plan["slotsFilled"],
            "projectedPowerNetAfter": best_plan["powerAfter"],
            "missionControlAvailableAfter": best_plan["mcAfter"],
            "monthlyDeltaTotal": monthly_total,
            "moduleCounts": entries,
            "score": {
                "focus": focus,
                "gross": best_plan["score"],
                "opportunityCost": best_plan["opportunityCost"],
                "unfilledSlotOpportunityCost": best_plan["unfilledOpportunityCost"],
                "totalOpportunityCostIncludingUnfilledSlots": (
                    best_plan["opportunityCost"] + best_plan["unfilledOpportunityCost"]
                ),
                "afterOpportunityCost": best_plan["scoreAfterOpportunityCost"],
                "afterOpportunityCostIncludingUnfilledSlots": (
                    best_plan["scoreAfterOpportunityCost"] - best_plan["unfilledOpportunityCost"]
                ),
                "bestAlternativePerSlot": opportunity_baseline,
            },
            "method": "single focus module type plus optional single power-support type, ranked by focus score after slot opportunity cost",
        },
        6,
    )


def hab_plan_row(
    indexed: IndexedState,
    templates_dir: Path | None,
    hab_id: int,
    hab: dict[str, Any],
    faction_id: int,
    faction: dict[str, Any],
    focus: str,
    top: int,
    topbar: dict[str, Any],
) -> dict[str, Any]:
    hab_module_templates = load_named_templates(templates_dir, "TIHabModuleTemplate.json")
    records = hab_module_records(indexed, hab, hab_module_templates)
    slots = hab_slot_summary(records)
    upgrade = hab_upgrade_info(records)
    current_tier = int(as_float(hab.get("tier"), 0.0)) or None
    target_tier = int(as_float(upgrade.get("targetTier"), 0.0)) or current_tier or 1
    planned_slots = hab_planned_empty_slots(slots, upgrade, current_tier)
    projected_power = hab_projected_power_summary(records)
    topbar_mc = topbar.get("resources", {}).get("MissionControl", {}) if isinstance(topbar.get("resources"), dict) else {}
    mc_available = as_float(topbar_mc.get("available"), 0.0)
    candidates = hab_module_candidate_rows(
        indexed,
        templates_dir,
        hab,
        records,
        faction_id,
        faction,
        target_tier,
        projected_power,
        mc_available,
        topbar,
    )
    annotate_candidate_opportunity_costs(candidates)
    return {
        "id": hab_id,
        "display": hab.get("displayName"),
        "habType": hab.get("habType"),
        "tier": current_tier,
        "targetTier": target_tier,
        "location": hab_location_summary(indexed, templates_dir, hab),
        "upgrade": upgrade,
        "slots": {
            "current": slots,
            "planning": planned_slots,
        },
        "power": {
            "active": hab_power_summary(records),
            "projectedAfterCurrentQueue": projected_power,
        },
        "moduleCounts": hab_module_counts(records),
        "underConstruction": [
            {
                "sectorNum": record.get("sectorNum"),
                "slot": record.get("slot"),
                "template": record.get("templateName"),
                "display": record.get("display"),
                "priorTemplate": record.get("priorTemplateName"),
                "completionDate": (record.get("state") or {}).get("completionDate"),
            }
            for record in records
            if hab_module_okay(record) and not record.get("completed")
        ],
        "candidateSummary": {
            "count": len(candidates),
            "topBalanced": sorted_candidates(candidates, "balanced", top),
            "topResearch": sorted_candidates(candidates, "research", top),
            "topProjects": sorted_candidates(candidates, "projects", top),
            "topCategoryBonus": sorted_candidates(candidates, "category-bonus", top),
            "topResources": sorted_candidates(candidates, "resources", top),
            "topPower": power_candidates(candidates, top),
        },
        "suggestedFill": suggested_hab_fill(
            candidates,
            int(planned_slots.get("plannedEmpty", 0)),
            focus,
            int(projected_power.get("net", 0)),
            mc_available,
        ),
    }


def calculate_hab_plan(
    indexed: IndexedState,
    templates_dir: Path | None,
    faction_name: str | None = None,
    hab_name: str | None = None,
    upgrading_to_tier: int | None = None,
    include_all: bool = False,
    focus: str = "balanced",
    top: int = 8,
) -> dict[str, Any]:
    faction_id, faction = find_faction_state(indexed, faction_name)
    topbar = calculate_topbar(indexed, templates_dir, faction.get("templateName"), include_details=False)
    if hab_name:
        found = match_raw_state(indexed, "TIHabState", hab_name)
        if not found or found[0] is None:
            raise SystemExit(f"Hab not found: {hab_name}")
        habs = [(found[0], found[1])]
    else:
        habs = faction_hab_states(indexed, faction)

    rows = [
        hab_plan_row(indexed, templates_dir, hab_id, hab, faction_id, faction, focus, top, topbar)
        for hab_id, hab in habs
        if ref_id(hab.get("faction")) == faction_id
    ]
    if upgrading_to_tier is not None:
        rows = [row for row in rows if int(as_float(row.get("targetTier"), 0.0)) == upgrading_to_tier and row["upgrade"].get("isUpgrading")]
    if not include_all:
        rows = [row for row in rows if int(row["slots"]["planning"].get("plannedEmpty", 0)) > 0]
    rows.sort(
        key=lambda row: (
            -int(row["slots"]["planning"].get("plannedEmpty", 0)),
            str(row.get("display") or ""),
        )
    )

    return clean_numbers(
        {
            "faction": faction_brief(faction_id, faction),
            "focus": focus,
            "filters": {
                "hab": hab_name,
                "upgradingToTier": upgrading_to_tier,
                "includeAll": include_all,
                "top": top,
                "returnedHabs": len(rows),
            },
            "scoreModel": {
                "research": "monthly Research net only; Projects and tech category bonuses are not folded into this score",
                "projects": "monthly Projects net only",
                "category-bonus": "raw sum of techBonuses across research categories",
                "resources": "monthly resource net weighted by current scarcity heuristic",
                "balanced": {
                    "formula": "research + resources",
                    "weights": {"research": 1.0, "resources": 1.0, "projects": 0.0, "category-bonus": 0.0},
                },
                "opportunityCost": {
                    "formula": "max(max(best affordable candidate score for focus, 0) - candidate score for focus, 0) per occupied slot",
                    "suggestedFill": "plans are ranked by gross focus score minus slot opportunity cost",
                    "unfilledSlots": "reported separately as foregone best-alternative score, but not charged when ranking occupied-module choices",
                },
            },
            "factionConstraints": {
                "missionControl": topbar.get("resources", {}).get("MissionControl") if isinstance(topbar.get("resources"), dict) else None,
                "monthlyResourceDeltas": {
                    resource: row.get("monthly")
                    for resource, row in (topbar.get("resources") or {}).items()
                    if isinstance(row, dict) and resource in {"Money", "Boost", "Water", "Volatiles", "Metals", "NobleMetals", "Fissiles"}
                },
            },
            "habs": rows,
            "sourceNotes": [
                "This is a planning model, not an exact in-game optimizer.",
                "plannedEmpty includes currently usable empty slots plus locked empty placeholders only when the core is upgrading to a higher tier.",
                "Candidates are filtered by known project unlocks, target tier, hab type, one-per-hab rules, and simple location-only special rules.",
                "Scores are separated by output type: research is Research/month, projects is Projects/month, category-bonus is raw tech bonus sum, resources is scarcity-weighted net resource flow.",
                "Template build materials are relative template weights, not exact final construction costs at location.",
            ],
        },
        6,
    )


def command_hab_plan(save_path: Path, templates_dir: Path | None, args: argparse.Namespace) -> None:
    data = load_save(save_path)
    indexed = build_index(data)
    result = calculate_hab_plan(
        indexed,
        templates_dir,
        faction_name=args.faction,
        hab_name=args.name,
        upgrading_to_tier=args.upgrading_to_tier,
        include_all=args.all,
        focus=args.focus,
        top=args.top,
    )
    print_json(result, compact=args.compact)


def project_progress_entries_by_name(faction: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for progress in faction.get("currentProjectProgress") if isinstance(faction.get("currentProjectProgress"), list) else []:
        if not isinstance(progress, dict):
            continue
        template_name = progress.get("projectTemplateName")
        if template_name:
            result.setdefault(str(template_name), []).append(progress)
    return result


def active_project_names(faction: dict[str, Any]) -> set[str]:
    active_slots = set(faction_project_slots(faction))
    names: set[str] = set()
    for slot, progress in project_progress_by_slot(faction).items():
        if slot in active_slots and progress.get("projectTemplateName"):
            names.add(str(progress.get("projectTemplateName")))
    return names


def project_analysis_candidate_names(
    faction: dict[str, Any],
    project_templates: dict[str, dict[str, Any]],
    include_active: bool = False,
) -> list[str]:
    available = faction.get("availableProjectNames") if isinstance(faction.get("availableProjectNames"), list) else []
    names = {str(name) for name in available if name}
    active_names = active_project_names(faction)
    for name, entries in project_progress_entries_by_name(faction).items():
        if include_active or name not in active_names:
            names.add(name)
    if include_active:
        names.update(active_names)

    finished = set(faction.get("finishedProjectNames") if isinstance(faction.get("finishedProjectNames"), list) else [])
    filtered = []
    for name in names:
        template = project_templates.get(name, {})
        if not template or template.get("disable"):
            continue
        if name in finished and not template.get("repeatable"):
            continue
        if name in active_names and not include_active:
            continue
        filtered.append(name)
    return sorted(filtered, key=lambda item: str(template_display(item, project_templates.get(item, {})) or item))


def project_candidate_status(faction: dict[str, Any], project_name: str) -> dict[str, Any]:
    active_slots = set(faction_project_slots(faction))
    entries = project_progress_entries_by_name(faction).get(project_name, [])
    slots = [int(as_float(entry.get("slot"), -1.0)) for entry in entries]
    active = [slot for slot in slots if slot in active_slots]
    stored = [slot for slot in slots if slot not in active_slots]
    accumulated = max((as_float(entry.get("accumulatedResearch"), 0.0) for entry in entries), default=0.0)
    if active:
        status = "active"
    elif stored:
        status = "stored"
    else:
        status = "available"
    return {
        "status": status,
        "slots": slots,
        "activeSlots": active,
        "storedSlots": stored,
        "accumulatedResearch": accumulated,
    }


def default_project_analysis_slot(faction: dict[str, Any]) -> int | None:
    slots = faction_project_slots(faction)
    return slots[-1] if slots else None


def active_slots_with_hypothetical_project_category(
    indexed: IndexedState,
    faction: dict[str, Any],
    tech_templates: dict[str, dict[str, Any]],
    project_templates: dict[str, dict[str, Any]],
    category: str | None,
    project_slot: int,
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
        template = tech_templates.get((tech_progress[slot] or {}).get("techTemplateName"), {})
        if template.get("techCategory") == category:
            count += 1

    projects = project_progress_by_slot(faction)
    for slot in range(3, 6):
        if weights[slot] <= 0.0 or not faction_project_allowed(faction, slot):
            continue
        slot_category = category if slot == project_slot else project_templates.get(projects.get(slot, {}).get("projectTemplateName"), {}).get("techCategory")
        if slot_category == category:
            count += 1
    return count


def hypothetical_project_category_modifier(
    indexed: IndexedState,
    faction: dict[str, Any],
    trait_templates: dict[str, dict[str, Any]],
    org_templates: dict[str, dict[str, Any]],
    hab_module_templates: dict[str, dict[str, Any]],
    utility_module_templates: dict[str, dict[str, Any]],
    tech_templates: dict[str, dict[str, Any]],
    project_templates: dict[str, dict[str, Any]],
    category: str | None,
    project_slot: int,
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
    active_same_category = active_slots_with_hypothetical_project_category(
        indexed,
        faction,
        tech_templates,
        project_templates,
        category,
        project_slot,
    )
    penalty_power = max(active_same_category - 1, 0)
    distributed = components["sum"] * (DEFAULT_GLOBAL_CONFIG["categoryBonusPenaltyPerExtraSlot"] ** penalty_power)
    return {
        "category": category,
        "components": components,
        "activeSlotsWithCategory": active_same_category,
        "extraSlotPenaltyPower": penalty_power,
        "distributed": distributed,
    }


def hypothetical_project_points_to_slot(
    indexed: IndexedState,
    faction: dict[str, Any],
    project_template: dict[str, Any],
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
    if slot < 0 or slot >= len(weights) or total_weights <= 0.0 or not faction_project_allowed(faction, slot):
        return {"daily": 0.0, "weight": 0.0, "weightFraction": 0.0, "category": project_template.get("techCategory"), "modifiers": None}

    category = project_template.get("techCategory")
    category_modifier = hypothetical_project_category_modifier(
        indexed,
        faction,
        trait_templates,
        org_templates,
        hab_module_templates,
        utility_module_templates,
        tech_templates,
        project_templates,
        category,
        slot,
    )
    project_facilities = project_facility_counts(indexed, faction, trait_templates, hab_module_templates)
    project_bonus = multiple_facilities_multiplier(project_facilities)
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
            "projectFacilityBonus": project_bonus,
            "effectiveMultiplier": 1.0 + as_float(category_modifier["distributed"], 0.0) + project_bonus,
        },
    }


def module_template_static_monthly_delta(template: dict[str, Any]) -> dict[str, dict[str, float]]:
    delta: dict[str, dict[str, float]] = {}
    for resource in HAB_MONTHLY_RESOURCES:
        income = hab_template_income(resource, template)
        support = hab_template_support(resource, template, include_crew_support=True)
        net = income - support
        if income or support or net:
            delta[resource] = {"income": income, "support": support, "net": net}
    return delta


def project_resource_grant_map(template: dict[str, Any]) -> dict[str, float]:
    grants: dict[str, float] = {}
    for grant in template.get("resourcesGranted") if isinstance(template.get("resourcesGranted"), list) else []:
        if not isinstance(grant, dict):
            continue
        resource = grant.get("resource")
        if not resource:
            continue
        grants[str(resource)] = grants.get(str(resource), 0.0) + as_float(grant.get("value"), 0.0)
    return grants


def resource_grant_score(grants: dict[str, float], scarcity_weights: dict[str, float]) -> float:
    return sum(amount * scarcity_weights.get(resource, 1.0) for resource, amount in grants.items())


def project_finished_faction_view(faction: dict[str, Any], project_name: str) -> dict[str, Any]:
    result = dict(faction)
    finished = list(faction.get("finishedProjectNames") if isinstance(faction.get("finishedProjectNames"), list) else [])
    if project_name not in finished:
        finished.append(project_name)
    result["finishedProjectNames"] = finished
    return result


def project_unlocked_module_templates(
    project_name: str,
    hab_module_templates: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    modules = [
        template
        for template in hab_module_templates.values()
        if template.get("requiredProjectName") == project_name and not template.get("disable")
    ]
    modules.sort(key=lambda template: str(template_display(str(template.get("dataName")), template) or template.get("dataName")))
    return modules


def module_static_analysis(template: dict[str, Any], scarcity_weights: dict[str, float]) -> dict[str, Any]:
    monthly_delta = module_template_static_monthly_delta(template)
    research_score = module_research_score(monthly_delta)
    project_score = module_project_score(monthly_delta)
    category_bonus_score = module_category_bonus_score(template)
    resource_score = module_resource_score(monthly_delta, scarcity_weights)
    return clean_numbers(
        {
            "template": template.get("dataName"),
            "display": template_display(str(template.get("dataName")), template),
            "tier": int(as_float(template.get("tier"), 0.0)),
            "habType": template.get("habType") or "Any",
            "power": int(as_float(template.get("power"), 0.0)),
            "crew": int(as_float(template.get("crew"), 0.0)),
            "missionControl": int(as_float(template.get("missionControl"), 0.0)),
            "buildTime_Days": as_float(template.get("buildTime_Days"), 0.0),
            "buildCostTemplateWeights": module_build_cost_map(template),
            "monthlyDeltaBeforeHabModifiers": monthly_delta,
            "techBonuses": tech_bonus_map_for_template(template),
            "specialRules": hab_template_special_rules(template),
            "scores": {
                "research": research_score,
                "projects": project_score,
                "category-bonus": category_bonus_score,
                "resources": resource_score,
                "balanced": module_balanced_score(research_score, resource_score),
            },
        },
        6,
    )


def module_count_sample(candidate: dict[str, Any] | None, count: int, planned_slots: int) -> dict[str, Any]:
    if not candidate:
        return {"count": count, "possibleWithPlannedSlots": False}
    scores = candidate.get("scores") if isinstance(candidate.get("scores"), dict) else {}
    return clean_numbers(
        {
            "count": count,
            "possibleWithPlannedSlots": count <= planned_slots,
            "assumption": "repeats the best current hab option and does not reserve extra power-support modules",
            "powerTotal": int(as_float(candidate.get("power"), 0.0)) * count,
            "missionControlTotal": int(as_float(candidate.get("missionControl"), 0.0)) * count,
            "buildTime_Days": candidate.get("buildTime_Days"),
            "monthlyDeltaTotal": monthly_delta_times(candidate.get("monthlyDelta") or {}, count),
            "scoresTotal": {name: as_float(value, 0.0) * count for name, value in scores.items()},
        },
        6,
    )


def prospective_module_unlocks_for_project(
    indexed: IndexedState,
    templates_dir: Path | None,
    faction_id: int,
    faction: dict[str, Any],
    project_name: str,
    hab_module_templates: dict[str, dict[str, Any]],
    topbar: dict[str, Any],
    top: int,
) -> list[dict[str, Any]]:
    unlocked_modules = project_unlocked_module_templates(project_name, hab_module_templates)
    if not unlocked_modules:
        return []

    body_templates = load_named_templates(templates_dir, "TISpaceBodyTemplate.json")
    effect_templates = load_named_templates(templates_dir, "TIEffectTemplate.json")
    trait_templates = load_trait_templates(templates_dir)
    _, councilor_by_id = councilor_summary_maps(indexed, trait_templates)
    effect_contexts = faction_effect_contexts(indexed, faction_id)
    mining_rate = faction_mining_rate(indexed, faction)
    scarcity_weights = resource_scarcity_weights(topbar)
    topbar_mc = topbar.get("resources", {}).get("MissionControl", {}) if isinstance(topbar.get("resources"), dict) else {}
    mc_available = as_float(topbar_mc.get("available"), 0.0)
    faction_with_project = project_finished_faction_view(faction, project_name)
    habs = [(hab_id, hab) for hab_id, hab in faction_hab_states(indexed, faction) if ref_id(hab.get("faction")) == faction_id]

    analyses: list[dict[str, Any]] = []
    for template in unlocked_modules:
        rows: list[dict[str, Any]] = []
        blocked_reasons: dict[str, int] = {}
        eligible_habs = 0
        planned_slots = 0
        current_slots = 0
        power_fit_slots = 0
        for hab_id, hab in habs:
            records = hab_module_records(indexed, hab, hab_module_templates)
            slots = hab_slot_summary(records)
            upgrade = hab_upgrade_info(records)
            current_tier = int(as_float(hab.get("tier"), 0.0)) or None
            target_tier = int(as_float(upgrade.get("targetTier"), 0.0)) or current_tier or 1
            planning = hab_planned_empty_slots(slots, upgrade, current_tier)
            reasons = module_unmet_requirements(
                indexed,
                template,
                hab,
                faction_with_project,
                target_tier,
                hab_module_counts(records),
                body_templates,
            )
            if reasons:
                for reason in reasons:
                    blocked_reasons[reason] = blocked_reasons.get(reason, 0) + 1
                continue
            eligible_habs += 1
            hab_planned_slots = int(planning.get("plannedEmpty", 0))
            hab_current_slots = int(planning.get("currentUsableEmpty", 0))
            planned_slots += hab_planned_slots
            current_slots += hab_current_slots
            if hab_planned_slots <= 0:
                continue
            projected_power = hab_projected_power_summary(records)
            row = module_candidate_row(
                indexed,
                hab,
                records,
                faction_with_project,
                template,
                projected_power,
                mc_available,
                effect_contexts,
                effect_templates,
                mining_rate,
                scarcity_weights,
                councilor_by_id,
            )
            row["hab"] = {"id": hab_id, "display": hab.get("displayName"), "plannedEmptySlots": hab_planned_slots}
            row["location"] = hab_location_summary(indexed, templates_dir, hab)
            rows.append(clean_numbers(row, 6))
            if row.get("fitsCurrentProjectedPower"):
                power_fit_slots += hab_planned_slots

        rows.sort(
            key=lambda row: (
                not bool(row.get("affordableByTemplateWeights")),
                not bool(row.get("fitsCurrentProjectedPower")),
                -as_float((row.get("scores") or {}).get("balanced"), 0.0),
                -as_float((row.get("scores") or {}).get("research"), 0.0),
                str((row.get("hab") or {}).get("display") or ""),
            )
        )
        best = rows[0] if rows else None
        analyses.append(
            clean_numbers(
                {
                    "template": template.get("dataName"),
                    "display": template_display(str(template.get("dataName")), template),
                    "static": module_static_analysis(template, scarcity_weights),
                    "currentBuildOptions": {
                        "eligibleHabs": eligible_habs,
                        "currentUsableEmptySlotsOnEligibleHabs": current_slots,
                        "plannedEmptySlotsOnEligibleHabs": planned_slots,
                        "powerFitPlannedSlots": power_fit_slots,
                        "blockedReasonCounts": blocked_reasons,
                        "bestOptions": rows[:top],
                    },
                    "countSamples": [
                        module_count_sample(best, count, planned_slots)
                        for count in PROJECT_ANALYSIS_MODULE_SAMPLE_COUNTS
                    ],
                },
                6,
            )
        )
    return analyses


def resource_bottlenecks(topbar: dict[str, Any]) -> list[dict[str, Any]]:
    bottlenecks: list[dict[str, Any]] = []
    resources = topbar.get("resources") if isinstance(topbar.get("resources"), dict) else {}
    for resource, row in resources.items():
        if resource == "MissionControl" or not isinstance(row, dict):
            continue
        monthly = as_float(row.get("monthly"), 0.0)
        current = as_float(row.get("current"), 0.0)
        if monthly >= 0.0:
            continue
        months_left = current / abs(monthly) if current > 0.0 else 0.0
        if months_left < 3.0:
            severity = "critical"
        elif months_left < 12.0:
            severity = "tight"
        else:
            severity = "deficit"
        bottlenecks.append(
            {
                "resource": resource,
                "current": current,
                "monthly": monthly,
                "monthsToZero": months_left,
                "severity": severity,
            }
        )
    bottlenecks.sort(key=lambda item: (as_float(item.get("monthsToZero"), 999.0), str(item.get("resource"))))

    mc = resources.get("MissionControl") if isinstance(resources.get("MissionControl"), dict) else {}
    mc_available = as_float(mc.get("available"), 0.0)
    if mc and mc_available <= 5.0:
        bottlenecks.insert(
            0,
            {
                "resource": "MissionControl",
                "available": mc_available,
                "usage": as_float(mc.get("usage"), 0.0),
                "capacity": as_float(mc.get("capacity"), 0.0),
                "severity": "critical" if mc_available <= 0.0 else "tight",
            },
        )
    return clean_numbers(bottlenecks, 6)


def project_module_aggregate(module_unlocks: list[dict[str, Any]]) -> dict[str, Any]:
    aggregate = {
        "unlockedModuleCount": len(module_unlocks),
        "bestSampleResearch": 0.0,
        "bestSampleResources": 0.0,
        "bestSampleCategoryBonus": 0.0,
        "bestSampleBalanced": None,
        "bestSampleMonthlyDelta": {},
        "bestPowerFitPlannedSlots": 0,
        "plannedEmptySlots": 0,
    }
    for unlock in module_unlocks:
        options = unlock.get("currentBuildOptions") if isinstance(unlock.get("currentBuildOptions"), dict) else {}
        aggregate["plannedEmptySlots"] += int(as_float(options.get("plannedEmptySlotsOnEligibleHabs"), 0.0))
        aggregate["bestPowerFitPlannedSlots"] = max(
            int(aggregate["bestPowerFitPlannedSlots"]),
            int(as_float(options.get("powerFitPlannedSlots"), 0.0)),
        )
        samples = unlock.get("countSamples") if isinstance(unlock.get("countSamples"), list) else []
        candidate_samples = [sample for sample in samples if isinstance(sample, dict) and sample.get("possibleWithPlannedSlots")]
        if not candidate_samples:
            candidate_samples = [sample for sample in samples if isinstance(sample, dict) and sample.get("scoresTotal")]
        if not candidate_samples:
            continue
        sample = max(candidate_samples, key=lambda item: as_float((item.get("scoresTotal") or {}).get("balanced"), 0.0))
        scores = sample.get("scoresTotal") if isinstance(sample.get("scoresTotal"), dict) else {}
        balanced = as_float(scores.get("balanced"), 0.0)
        current_balanced = aggregate.get("bestSampleBalanced")
        if current_balanced is None or balanced > as_float(current_balanced, 0.0):
            aggregate["bestSampleBalanced"] = balanced
            aggregate["bestSampleResearch"] = as_float(scores.get("research"), 0.0)
            aggregate["bestSampleResources"] = as_float(scores.get("resources"), 0.0)
            aggregate["bestSampleCategoryBonus"] = as_float(scores.get("category-bonus"), 0.0)
            aggregate["bestSampleMonthlyDelta"] = sample.get("monthlyDeltaTotal") or {}
    if aggregate["bestSampleBalanced"] is None:
        aggregate["bestSampleBalanced"] = 0.0
    return clean_numbers(aggregate, 6)


def bottleneck_penalty_from_delta(
    monthly_delta: dict[str, dict[str, float]],
    bottlenecks: list[dict[str, Any]],
    scarcity_weights: dict[str, float],
) -> float:
    bottleneck_resources = {
        str(row.get("resource"))
        for row in bottlenecks
        if row.get("resource") and row.get("severity") in {"critical", "tight"}
    }
    penalty = 0.0
    for resource, row in monthly_delta.items():
        if resource not in bottleneck_resources or not isinstance(row, dict):
            continue
        net = as_float(row.get("net"), 0.0)
        if net < 0.0:
            penalty += abs(net) * scarcity_weights.get(resource, 1.0)
    return penalty


def project_analysis_flags(
    candidate: dict[str, Any],
    bottlenecks: list[dict[str, Any]],
) -> list[str]:
    flags: list[str] = []
    eta_days = as_float((candidate.get("research") or {}).get("eta", {}).get("days"), 0.0)
    if eta_days > 180.0:
        flags.append("long project ETA")
    elif eta_days > 90.0:
        flags.append("medium project ETA")
    if not candidate.get("moduleUnlocks") and not (candidate.get("direct") or {}).get("effects") and not (candidate.get("direct") or {}).get("resourcesGranted"):
        flags.append("no quantified direct payoff in this analysis")
    module = candidate.get("moduleAggregate") if isinstance(candidate.get("moduleAggregate"), dict) else {}
    if as_float(module.get("unlockedModuleCount"), 0.0) and as_float(module.get("plannedEmptySlots"), 0.0) <= 0.0:
        flags.append("unlocked modules have no currently planned empty slots")
    if as_float(module.get("unlockedModuleCount"), 0.0) and as_float(module.get("bestPowerFitPlannedSlots"), 0.0) <= 0.0:
        flags.append("best unlocked module options likely need power support")

    bottleneck_resources = {
        str(row.get("resource"))
        for row in bottlenecks
        if row.get("resource") and row.get("severity") in {"critical", "tight"}
    }
    monthly_delta = module.get("bestSampleMonthlyDelta") if isinstance(module.get("bestSampleMonthlyDelta"), dict) else {}
    for resource, row in monthly_delta.items():
        if resource in bottleneck_resources and isinstance(row, dict) and as_float(row.get("net"), 0.0) < 0.0:
            flags.append(f"best unlocked module sample worsens {resource}")
    if candidate.get("repeatable") and (candidate.get("direct") or {}).get("resourcesGranted"):
        flags.append("repeatable one-time resource project")
    return flags


def project_candidate_analysis(
    indexed: IndexedState,
    templates_dir: Path | None,
    faction_id: int,
    faction: dict[str, Any],
    project_name: str,
    project_template: dict[str, Any],
    analysis_slot: int,
    base_daily: float,
    topbar: dict[str, Any],
    bottlenecks: list[dict[str, Any]],
    tech_templates: dict[str, dict[str, Any]],
    project_templates: dict[str, dict[str, Any]],
    trait_templates: dict[str, dict[str, Any]],
    org_templates: dict[str, dict[str, Any]],
    hab_module_templates: dict[str, dict[str, Any]],
    utility_module_templates: dict[str, dict[str, Any]],
    top: int,
) -> dict[str, Any]:
    status = project_candidate_status(faction, project_name)
    cost = project_template_cost(indexed, project_template, faction)
    remaining = max(cost - as_float(status.get("accumulatedResearch"), 0.0), 0.0)
    slot_points = hypothetical_project_points_to_slot(
        indexed,
        faction,
        project_template,
        analysis_slot,
        base_daily,
        tech_templates,
        project_templates,
        trait_templates,
        org_templates,
        hab_module_templates,
        utility_module_templates,
    )
    eta = eta_from_daily(indexed, remaining, as_float(slot_points.get("daily"), 0.0))
    scarcity_weights = resource_scarcity_weights(topbar)
    module_unlocks = prospective_module_unlocks_for_project(
        indexed,
        templates_dir,
        faction_id,
        faction,
        project_name,
        hab_module_templates,
        topbar,
        top=min(top, 5),
    )
    module_aggregate = project_module_aggregate(module_unlocks)
    grants = project_resource_grant_map(project_template)
    raw_effects = project_template.get("effects")
    effects = [str(effect) for effect in raw_effects] if isinstance(raw_effects, list) else []
    direct_grant_score = resource_grant_score(grants, scarcity_weights)
    direct_effect_score = len(effects) * 20.0
    module_research = as_float(module_aggregate.get("bestSampleResearch"), 0.0)
    module_resources = as_float(module_aggregate.get("bestSampleResources"), 0.0)
    module_category = as_float(module_aggregate.get("bestSampleCategoryBonus"), 0.0)
    module_balanced = as_float(module_aggregate.get("bestSampleBalanced"), 0.0)
    bottleneck_penalty = bottleneck_penalty_from_delta(
        module_aggregate.get("bestSampleMonthlyDelta") if isinstance(module_aggregate.get("bestSampleMonthlyDelta"), dict) else {},
        bottlenecks,
        scarcity_weights,
    )
    eta_days = as_float(eta.get("days"), 0.0)
    eta_months = eta_days / (DAYS_PER_YEAR / 12.0) if eta_days > 0.0 else 0.0
    research_raw = module_research + module_category * 100.0 + direct_effect_score
    research_sustainable = research_raw + module_resources - bottleneck_penalty
    resource_recovery = direct_grant_score + max(module_resources, 0.0)
    module_unlock_value = module_balanced + module_category * 100.0
    short_horizon = (resource_recovery + direct_effect_score + max(module_research, 0.0)) / max(eta_months + 1.0, 1.0)
    long_horizon = research_sustainable + module_unlock_value - eta_days * 0.05
    low_cost = 10000.0 / max(remaining, 100.0)
    candidate: dict[str, Any] = {
        "template": project_name,
        "display": template_display(project_name, project_template),
        "category": project_template.get("techCategory"),
        "repeatable": bool(project_template.get("repeatable")),
        "aiRole": {
            "project": project_template.get("AI_projectRole"),
            "tech": project_template.get("AI_techRole"),
        },
        "status": status,
        "research": {
            "slot": analysis_slot,
            "cost": cost,
            "remaining": remaining,
            "slotDailyEstimate": slot_points.get("daily"),
            "slotModel": slot_points,
            "eta": eta,
        },
        "direct": {
            "effects": effects,
            "resourcesGranted": grants,
            "resourceGrantScarcityScore": direct_grant_score,
        },
        "moduleUnlocks": module_unlocks,
        "moduleAggregate": module_aggregate,
        "scoreComponents": {
            "directEffectScore": direct_effect_score,
            "directResourceGrantScarcityScore": direct_grant_score,
            "moduleBestSampleResearch": module_research,
            "moduleBestSampleResources": module_resources,
            "moduleBestSampleCategoryBonus": module_category,
            "moduleBestSampleBalanced": module_balanced,
            "bottleneckPenalty": bottleneck_penalty,
            "etaDays": eta_days,
        },
        "heuristicScores": {
            "research-raw": research_raw,
            "research-sustainable": research_sustainable,
            "resource-recovery": resource_recovery,
            "module-unlock": module_unlock_value,
            "short-horizon": short_horizon,
            "long-horizon": long_horizon,
            "low-cost": low_cost,
        },
    }
    candidate["flags"] = project_analysis_flags(candidate, bottlenecks)
    return clean_numbers(candidate, 6)


def project_ranking_brief(candidate: dict[str, Any], axis: str) -> dict[str, Any]:
    return {
        "template": candidate.get("template"),
        "display": candidate.get("display"),
        "category": candidate.get("category"),
        "score": (candidate.get("heuristicScores") or {}).get(axis),
        "etaDays": ((candidate.get("research") or {}).get("eta") or {}).get("days"),
        "moduleUnlocks": [
            unlock.get("template")
            for unlock in (candidate.get("moduleUnlocks") or [])
            if isinstance(unlock, dict)
        ],
        "flags": candidate.get("flags"),
    }


def calculate_project_analysis(
    indexed: IndexedState,
    templates_dir: Path | None,
    faction_name: str | None = None,
    top: int = 10,
    sort_axis: str = "research-sustainable",
    slot: int | None = None,
    include_active: bool = False,
    include_all: bool = False,
) -> dict[str, Any]:
    faction_id, faction = find_faction_state(indexed, faction_name)
    research_templates = load_research_templates(templates_dir)
    base_daily_cache: dict[int, float] = {}
    project_templates = research_templates.projects
    tech_templates = research_templates.techs
    trait_templates = research_templates.traits
    org_templates = research_templates.orgs
    hab_module_templates = research_templates.hab_modules
    utility_module_templates = research_templates.utility_modules
    analysis_slot = slot if slot is not None else default_project_analysis_slot(faction)
    if analysis_slot is None:
        raise SystemExit("Faction has no unlocked project research slot.")
    if analysis_slot not in faction_project_slots(faction):
        raise SystemExit(f"Project slot {analysis_slot} is not currently unlocked for this faction.")
    if sort_axis not in PROJECT_ANALYSIS_SORT_CHOICES:
        raise SystemExit(f"Unknown project-analysis sort axis: {sort_axis}")

    topbar = calculate_topbar(
        indexed,
        templates_dir,
        faction.get("templateName"),
        include_details=False,
        research_templates=research_templates,
        base_daily_cache=base_daily_cache,
    )
    bottlenecks = resource_bottlenecks(topbar)
    base_daily = faction_base_research_daily(
        indexed,
        templates_dir,
        faction,
        templates=research_templates,
        cache=base_daily_cache,
    )
    names = project_analysis_candidate_names(faction, project_templates, include_active=include_active)
    candidates = [
        project_candidate_analysis(
            indexed,
            templates_dir,
            faction_id,
            faction,
            name,
            project_templates[name],
            analysis_slot,
            base_daily,
            topbar,
            bottlenecks,
            tech_templates,
            project_templates,
            trait_templates,
            org_templates,
            hab_module_templates,
            utility_module_templates,
            top,
        )
        for name in names
    ]
    candidates.sort(
        key=lambda candidate: (
            -as_float((candidate.get("heuristicScores") or {}).get(sort_axis), 0.0),
            as_float(((candidate.get("research") or {}).get("eta") or {}).get("days"), 999999.0),
            str(candidate.get("display") or candidate.get("template")),
        )
    )
    ranking_axes = ("research-sustainable", "research-raw", "resource-recovery", "module-unlock", "short-horizon", "long-horizon")
    rankings = {
        axis: [
            project_ranking_brief(candidate, axis)
            for candidate in sorted(
                candidates,
                key=lambda item: (
                    -as_float((item.get("heuristicScores") or {}).get(axis), 0.0),
                    as_float(((item.get("research") or {}).get("eta") or {}).get("days"), 999999.0),
                    str(item.get("display") or item.get("template")),
                ),
            )[:top]
        ]
        for axis in ranking_axes
    }
    research_ui = calculate_research_ui(
        indexed,
        templates_dir,
        faction.get("templateName"),
        templates=research_templates,
        base_daily_cache=base_daily_cache,
    )
    return clean_numbers(
        {
            "faction": faction_brief(faction_id, faction),
            "date": (first_value(indexed, "TITimeState") or {}).get("currentDateTime"),
            "filters": {
                "top": top,
                "sort": sort_axis,
                "analysisSlot": analysis_slot,
                "includeActive": include_active,
                "includeAll": include_all,
                "candidateCount": len(candidates),
            },
            "constraints": {
                "missionControl": (topbar.get("resources") or {}).get("MissionControl"),
                "bottlenecks": bottlenecks,
                "resourceScarcityWeights": resource_scarcity_weights(topbar),
            },
            "activeProjects": research_ui.get("projects", {}).get("active"),
            "scoreModel": {
                "purpose": "explainable shortlist generation for LLM/human synthesis, not an automatic final recommendation",
                "research-raw": "best unlocked-module sample Research/month + 100 * category-bonus sample + 20 per direct project effect",
                "research-sustainable": "research-raw + scarcity-weighted module resource score - critical/tight bottleneck worsening penalty",
                "resource-recovery": "one-time resources granted weighted by current scarcity + positive unlocked-module resource score",
                "module-unlock": "best unlocked-module balanced score + 100 * best category-bonus sample",
                "short-horizon": "(resource-recovery + direct-effect score + positive module research) divided by ETA months + 1",
                "long-horizon": "research-sustainable + module-unlock - 0.05 * ETA days",
                "low-cost": "10000 / remaining research cost, floored at 100 cost",
            },
            "rankings": rankings,
            "candidates": candidates if include_all else candidates[:top],
            "sourceNotes": [
                "This command ranks candidates on multiple transparent heuristic axes; it intentionally does not choose a final project.",
                "Hypothetical project ETA uses the chosen project slot's current research weight and current category/project-facility modifiers.",
                "Module unlock samples pretend the project is finished, scan current/planned empty slots, and repeat the best current hab option for 1/2/4-module samples.",
                "Negative support in module deltas means the hypothetical module reduces existing upkeep.",
                "Module samples do not solve a global construction queue, global MC allocation, or extra power-support placement.",
            ],
        },
        6,
    )


def command_project_analysis(save_path: Path, templates_dir: Path | None, args: argparse.Namespace) -> None:
    data = load_save(save_path)
    indexed = build_index(data)
    result = calculate_project_analysis(
        indexed,
        templates_dir,
        faction_name=args.faction,
        top=args.top,
        sort_axis=args.sort,
        slot=args.slot,
        include_active=args.include_active,
        include_all=args.all,
    )
    print_json(result, compact=args.compact)


def hab_research_and_mc(
    indexed: IndexedState,
    faction: dict[str, Any],
    hab_module_templates: dict[str, dict[str, Any]],
    councilor_by_id: dict[int, dict[str, Any]],
) -> tuple[float, int, list[dict[str, Any]]]:
    sectors_by_hab: dict[int, list[dict[str, Any]]] = {}
    for sector in faction_sector_states(indexed, faction):
        hab_id = ref_id(sector.get("hab"))
        if hab_id is not None:
            sectors_by_hab.setdefault(hab_id, []).append(sector)

    total_research_month = 0.0
    total_mission_control = 0
    details: list[dict[str, Any]] = []
    for hab_id, sectors in sectors_by_hab.items():
        hab = state_value_by_id(indexed, hab_id) or {}
        active_modules = active_modules_in_sectors(indexed, sectors)
        raw_research_month = 0.0
        admin_modifier = 1.0
        module_counts: dict[str, int] = {}
        for module in active_modules:
            template_name = module.get("templateName")
            template = hab_module_templates.get(template_name, {})
            module_counts[str(template_name)] = module_counts.get(str(template_name), 0) + 1
            raw_research_month += as_float(template.get("incomeResearch_month"), 0.0)
            mission_control = int(as_float(template.get("missionControl"), 0.0))
            if mission_control > 0:
                total_mission_control += mission_control
            special_rules = template.get("specialRules") if isinstance(template.get("specialRules"), list) else []
            if "Efficiency" in special_rules:
                admin_modifier *= 1.0 + as_float(template.get("specialRulesValue"), 0.0)

        adviser_bonus = nation_adviser_science_bonus(hab, councilor_by_id)
        research_month = raw_research_month * (1.0 + adviser_bonus) * admin_modifier
        total_research_month += research_month
        if research_month:
            details.append(
                {
                    "id": hab_id,
                    "display": hab.get("displayName"),
                    "rawResearchMonth": raw_research_month,
                    "adminModifier": admin_modifier,
                    "adviserBonus": adviser_bonus,
                    "researchMonth": research_month,
                    "researchDay": research_month * 12.0 / DAYS_PER_YEAR,
                    "moduleCounts": module_counts,
                }
            )
    details.sort(key=lambda item: -item["researchDay"])
    return total_research_month, total_mission_control, details


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


def load_research_templates(templates_dir: Path | None) -> ResearchTemplates:
    return ResearchTemplates(
        traits=load_trait_templates(templates_dir),
        effects=load_named_templates(templates_dir, "TIEffectTemplate.json"),
        orgs=load_named_templates(templates_dir, "TIOrgTemplate.json"),
        hab_modules=load_named_templates(templates_dir, "TIHabModuleTemplate.json"),
        utility_modules=load_named_templates(templates_dir, "TIUtilityModuleTemplate.json"),
        techs=load_named_templates(templates_dir, "TITechTemplate.json"),
        projects=load_named_templates(templates_dir, "TIProjectTemplate.json"),
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
    templates = templates or load_research_templates(templates_dir)
    trait_templates = templates.traits
    effect_templates = templates.effects
    hab_module_templates = templates.hab_modules
    faction_id, faction = find_faction_state(indexed, faction_name)
    effect_contexts = faction_effect_contexts(indexed, faction_id)
    _, councilor_by_id = councilor_summary_maps(indexed, trait_templates)

    base_incomes = faction.get("baseIncomes_year") if isinstance(faction.get("baseIncomes_year"), dict) else {}
    hq_daily = as_float(base_incomes.get("Research"), 0.0) / DAYS_PER_YEAR
    hq_mission_control = int(as_float(base_incomes.get("MissionControl"), 0.0))

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
    max_mc = hq_mission_control + max_buildable_mc
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


def command_research(save_path: Path, templates_dir: Path | None, args: argparse.Namespace) -> None:
    data = load_save(save_path)
    indexed = build_index(data)
    result = calculate_research_breakdown(indexed, templates_dir, args.faction, include_details=args.details)
    print_json(result, compact=args.compact)


def scenario_customizations(indexed: IndexedState) -> dict[str, Any]:
    global_state = first_value(indexed, "TIGlobalValuesState") or {}
    customizations = global_state.get("scenarioCustomizations")
    return customizations if isinstance(customizations, dict) else {}


def scenario_float(indexed: IndexedState, key: str, default: float = 1.0) -> float:
    return as_float(scenario_customizations(indexed).get(key), default)


def research_speed_modifier(indexed: IndexedState) -> float:
    value = scenario_float(indexed, "researchSpeedMultiplier", 1.0)
    return value if value > 0.0 else 1.0


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


def current_save_datetime(indexed: IndexedState) -> datetime | None:
    time_state = first_value(indexed, "TITimeState") or {}
    return ti_datetime(time_state.get("currentDateTime"))


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
    total = 0.0
    for module in active_modules_in_sectors(indexed, faction_sector_states(indexed, faction)):
        template = hab_module_templates.get(module.get("templateName"), {})
        total += tech_bonus_sum(template.get("techBonuses"), category)
    return diminishing_research_modifier(total)


def faction_org_category_modifier(
    indexed: IndexedState,
    faction: dict[str, Any],
    org_templates: dict[str, dict[str, Any]],
    category: str | None,
) -> float:
    total = 0.0
    for councilor in active_faction_councilors(indexed, faction):
        for org_ref in councilor.get("orgs") if isinstance(councilor.get("orgs"), list) else []:
            org = state_value_by_id(indexed, ref_id(org_ref))
            if not isinstance(org, dict) or not org.get("applyingBonuses"):
                continue
            template = org_templates.get(org.get("templateName"), {})
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
    total = 0.0
    for councilor in active_faction_councilors(indexed, faction):
        for trait_name in councilor.get("traitTemplateNames") if isinstance(councilor.get("traitTemplateNames"), list) else []:
            total += tech_bonus_sum(trait_templates.get(trait_name, {}).get("techBonuses"), category)
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
            design = designs.get(str(ship.get("templateName")), {})
            for entry in design.get("moduleTemplateEntries") if isinstance(design.get("moduleTemplateEntries"), list) else []:
                if not isinstance(entry, dict):
                    continue
                module = utility_module_templates.get(str(entry.get("moduleName")), {})
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
) -> dict[str, float]:
    base_incomes = faction.get("baseIncomes_year") if isinstance(faction.get("baseIncomes_year"), dict) else {}
    trait_projects = 0.0
    org_projects = 0.0
    for councilor in active_faction_councilors(indexed, faction):
        for trait_name in councilor.get("traitTemplateNames") if isinstance(councilor.get("traitTemplateNames"), list) else []:
            trait_projects += as_float(trait_templates.get(trait_name, {}).get("incomeProjects"), 0.0)
        for org_ref in councilor.get("orgs") if isinstance(councilor.get("orgs"), list) else []:
            org = state_value_by_id(indexed, ref_id(org_ref))
            if isinstance(org, dict) and org.get("applyingBonuses"):
                org_projects += as_float(org.get("projectCapacityGranted"), 0.0)

    hab_projects = 0.0
    for module in active_modules_in_sectors(indexed, faction_sector_states(indexed, faction)):
        template = hab_module_templates.get(module.get("templateName"), {})
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
        template = tech_templates.get((tech_progress[slot] or {}).get("techTemplateName"), {})
        if template.get("techCategory") == category:
            count += 1

    projects = project_progress_by_slot(faction)
    for slot in range(3, 6):
        if weights[slot] <= 0.0 or not faction_project_allowed(faction, slot):
            continue
        template = project_templates.get(projects.get(slot, {}).get("projectTemplateName"), {})
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
    if slot < 0 or slot >= len(weights) or total_weights <= 0.0:
        return {"daily": 0.0, "weight": 0.0, "weightFraction": 0.0, "modifiers": None}

    is_project = slot >= 3
    template: dict[str, Any] = {}
    if is_project:
        template = project_templates.get(project_progress_by_slot(faction).get(slot, {}).get("projectTemplateName"), {})
    else:
        global_research = first_value(indexed, "TIGlobalResearchState") or {}
        tech_progress = global_research.get("techProgress") if isinstance(global_research.get("techProgress"), list) else []
        if slot < len(tech_progress):
            template = tech_templates.get((tech_progress[slot] or {}).get("techTemplateName"), {})

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
    project_facilities = project_facility_counts(indexed, faction, trait_templates, hab_module_templates) if is_project else None
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
    templates = templates or load_research_templates(templates_dir)
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
        template = tech_templates.get(template_name, {})
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
        template = project_templates.get(template_name, {})
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
        template = project_templates.get(template_name, {})
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


def command_research_ui(save_path: Path, templates_dir: Path | None, args: argparse.Namespace) -> None:
    data = load_save(save_path)
    indexed = build_index(data)
    result = calculate_research_ui(indexed, templates_dir, args.faction)
    print_json(result, compact=args.compact)


RESEARCH_PLAN_SCORE_AXES = (
    "fastCompletion",
    "factionSynergy",
    "unlockBreadth",
    "criticalTemplate",
    "resourceReliefCoverage",
    "currentProgress",
)


def string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if item]
    if isinstance(value, str) and value:
        return [value]
    return []


def research_template_prereqs(template: dict[str, Any]) -> list[str]:
    prereqs = string_list(template.get("prereqs"))
    for key in ("altPrereq0",):
        for name in string_list(template.get(key)):
            if name not in prereqs:
                prereqs.append(name)
    return prereqs


def research_template_effects(template: dict[str, Any]) -> list[str]:
    return string_list(template.get("effects"))


def research_template_resources_granted(template: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for item in template.get("resourcesGranted") if isinstance(template.get("resourcesGranted"), list) else []:
        if not isinstance(item, dict):
            continue
        resource = item.get("resource")
        if not resource:
            continue
        rows.append({"resource": str(resource), "value": as_float(item.get("value"), 0.0)})
    return rows


def active_global_research_names(indexed: IndexedState) -> set[str]:
    global_research = first_value(indexed, "TIGlobalResearchState") or {}
    progress = global_research.get("techProgress") if isinstance(global_research.get("techProgress"), list) else []
    return {
        str(row.get("techTemplateName"))
        for row in progress
        if isinstance(row, dict) and row.get("techTemplateName")
    }


def finished_global_research_names(indexed: IndexedState) -> set[str]:
    global_research = first_value(indexed, "TIGlobalResearchState") or {}
    return set(string_list(global_research.get("finishedTechsNames")))


def available_global_research_templates(
    indexed: IndexedState,
    tech_templates: dict[str, dict[str, Any]],
) -> list[tuple[str, dict[str, Any]]]:
    finished = finished_global_research_names(indexed)
    active = active_global_research_names(indexed)
    rows = []
    for name, template in tech_templates.items():
        if name in finished or name in active:
            continue
        if as_float(template.get("researchCost"), 0.0) <= 0.0:
            continue
        prereqs = research_template_prereqs(template)
        if all(prereq in finished for prereq in prereqs):
            rows.append((name, template))
    rows.sort(key=lambda item: (as_float(item[1].get("researchCost"), 0.0), item[1].get("friendlyName") or item[0]))
    return rows


def project_progress_records_by_template(faction: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    progress = faction.get("currentProjectProgress") if isinstance(faction.get("currentProjectProgress"), list) else []
    for item in progress:
        if not isinstance(item, dict) or not item.get("projectTemplateName"):
            continue
        name = str(item.get("projectTemplateName"))
        existing = rows.get(name)
        if existing is None or as_float(item.get("accumulatedResearch"), 0.0) > as_float(existing.get("accumulatedResearch"), 0.0):
            rows[name] = item
    return rows


def active_project_research_names(faction: dict[str, Any]) -> set[str]:
    progress_by_slot = project_progress_by_slot(faction)
    names = set()
    for slot in faction_project_slots(faction):
        progress = progress_by_slot.get(slot)
        if progress and progress.get("projectTemplateName"):
            names.add(str(progress.get("projectTemplateName")))
    return names


def available_project_research_templates(
    faction: dict[str, Any],
    project_templates: dict[str, dict[str, Any]],
) -> list[tuple[str, dict[str, Any]]]:
    available = string_list(faction.get("availableProjectNames"))
    active = active_project_research_names(faction)
    rows = []
    for name in available:
        if name in active:
            continue
        template = project_templates.get(name)
        if not template:
            continue
        if as_float(template.get("researchCost"), 0.0) <= 0.0:
            continue
        rows.append((name, template))
    rows.sort(key=lambda item: (as_float(item[1].get("researchCost"), 0.0), item[1].get("friendlyName") or item[0]))
    return rows


def research_plan_reference_weight_fraction(faction: dict[str, Any], kind: str) -> float:
    weights = faction_research_weights(faction)
    total = faction_total_research_weights(faction)
    if total <= 0.0:
        return 0.0
    slots = range(0, 3) if kind == "global" else faction_project_slots(faction)
    fractions = [weights[slot] / total for slot in slots if slot < len(weights) and weights[slot] > 0.0]
    return max(fractions) if fractions else 0.0


def direct_unlocks_for_template(
    template_name: str,
    tech_templates: dict[str, dict[str, Any]],
    project_templates: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    techs = [
        {"template": name, "display": template_display(name, template), "category": template.get("techCategory")}
        for name, template in tech_templates.items()
        if template_name in research_template_prereqs(template)
    ]
    projects = [
        {"template": name, "display": template_display(name, template), "category": template.get("techCategory")}
        for name, template in project_templates.items()
        if template_name in research_template_prereqs(template)
    ]
    techs.sort(key=lambda row: str(row.get("display") or row.get("template")))
    projects.sort(key=lambda row: str(row.get("display") or row.get("template")))
    return {"globalTechs": techs, "projects": projects, "count": len(techs) + len(projects)}


def research_plan_keyword_tags(template: dict[str, Any]) -> list[str]:
    text = " ".join(
        [
            str(template.get("dataName") or ""),
            str(template.get("friendlyName") or ""),
            str(template.get("AI_techRole") or ""),
            str(template.get("AI_projectRole") or ""),
            " ".join(research_template_effects(template)),
        ]
    ).casefold()
    rules = {
        "alien-xeno": ("alien", "xeno", "hydra", "pherocyte", "salamander"),
        "ship-combat": ("ship", "weapon", "laser", "missile", "torpedo", "armor", "navy", "fleet", "combat"),
        "space-economy": ("hab", "mining", "colony", "outpost", "space", "missioncontrol", "shipbuilding"),
        "earth-economy": ("economy", "funding", "welfare", "climate", "gdp", "development"),
        "council-ops": ("council", "ops", "investigation", "espionage", "security", "administration"),
        "research-infrastructure": ("research", "lab", "science", "university", "institute"),
        "resources": ("resource", "water", "volatile", "metals", "fissile", "antimatter", "exotic"),
    }
    return [tag for tag, needles in rules.items() if any(needle in text for needle in needles)]


def research_plan_category_context(
    indexed: IndexedState,
    faction: dict[str, Any],
    category: str | None,
    kind: str,
    trait_templates: dict[str, dict[str, Any]],
    org_templates: dict[str, dict[str, Any]],
    hab_module_templates: dict[str, dict[str, Any]],
    utility_module_templates: dict[str, dict[str, Any]],
    tech_templates: dict[str, dict[str, Any]],
    project_templates: dict[str, dict[str, Any]],
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
    current_active = active_slots_with_category(indexed, faction, tech_templates, project_templates, category)
    added_penalty_power = current_active
    category_bonus_if_added = as_float(components.get("sum"), 0.0) * (
        DEFAULT_GLOBAL_CONFIG["categoryBonusPenaltyPerExtraSlot"] ** added_penalty_power
    )
    project_facilities = project_facility_counts(indexed, faction, trait_templates, hab_module_templates) if kind == "project" else None
    project_bonus = multiple_facilities_multiplier(project_facilities or {}) if kind == "project" else 0.0
    return clean_numbers(
        {
            "category": category,
            "components": components,
            "currentActiveSlotsWithCategory": current_active,
            "addedSlotPenaltyPower": added_penalty_power,
            "categoryBonusIfAddedToCurrentMix": category_bonus_if_added,
            "projectFacilities": project_facilities,
            "projectFacilityBonus": project_bonus if kind == "project" else None,
            "effectiveMultiplierIfAddedToCurrentMix": 1.0 + category_bonus_if_added + project_bonus,
        },
        6,
    )


def research_plan_resource_grant_maps(
    resources_granted: list[dict[str, Any]],
    cost_remaining: float,
    deficient_resources: set[str],
) -> dict[str, Any]:
    by_resource = {row["resource"]: row["value"] for row in resources_granted}
    per_research = {
        resource: value / cost_remaining
        for resource, value in by_resource.items()
        if cost_remaining > 0.0
    }
    deficient = {resource: value for resource, value in by_resource.items() if resource in deficient_resources}
    return clean_numbers(
        {
            "byResource": by_resource,
            "perRemainingResearch": per_research,
            "currentlyDeficientResourcesGranted": deficient,
            "deficientResourceTypesCovered": len(deficient),
        },
        6,
    )


def research_plan_candidate_row(
    indexed: IndexedState,
    faction: dict[str, Any],
    template_name: str,
    template: dict[str, Any],
    kind: str,
    base_daily: float,
    reference_weight_fraction: float,
    progress: dict[str, Any] | None,
    topbar: dict[str, Any],
    trait_templates: dict[str, dict[str, Any]],
    org_templates: dict[str, dict[str, Any]],
    hab_module_templates: dict[str, dict[str, Any]],
    utility_module_templates: dict[str, dict[str, Any]],
    tech_templates: dict[str, dict[str, Any]],
    project_templates: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    category = template.get("techCategory")
    cost = tech_template_cost(indexed, template) if kind == "global" else project_template_cost(indexed, template, faction)
    accumulated = as_float((progress or {}).get("accumulatedResearch"), 0.0)
    remaining = max(cost - accumulated, 0.0)
    category_context = research_plan_category_context(
        indexed,
        faction,
        category,
        kind,
        trait_templates,
        org_templates,
        hab_module_templates,
        utility_module_templates,
        tech_templates,
        project_templates,
    )
    estimated_daily = base_daily * reference_weight_fraction * as_float(category_context.get("effectiveMultiplierIfAddedToCurrentMix"), 0.0)
    effects = research_template_effects(template)
    resources_granted = research_template_resources_granted(template)
    deficient_resources = set(string_list(topbar.get("resourceIncomeDeficiencies")))
    grants = research_plan_resource_grant_maps(resources_granted, remaining, deficient_resources)
    unlocks = direct_unlocks_for_template(template_name, tech_templates, project_templates)
    eta = eta_from_daily(indexed, remaining, estimated_daily)
    progress_fraction = accumulated / cost if cost > 0.0 else None
    return clean_numbers(
        {
            "kind": kind,
            "template": template_name,
            "display": template_display(template_name, template),
            "category": category,
            "classification": {
                "aiTechRole": template.get("AI_techRole"),
                "aiProjectRole": template.get("AI_projectRole"),
                "aiCriticalTech": bool(template.get("AI_criticalTech")),
                "keywordTags": research_plan_keyword_tags(template),
            },
            "research": {
                "cost": cost,
                "accumulated": accumulated,
                "remaining": remaining,
                "progressFraction": progress_fraction,
                "referenceWeightFraction": reference_weight_fraction,
                "estimatedDailyAtReferenceWeight": estimated_daily,
                "etaAtReferenceWeight": eta,
                "progressSlot": (progress or {}).get("slot"),
                "repeatable": bool(template.get("repeatable")) if kind == "project" else None,
                "oneTimeGlobally": bool(template.get("oneTimeGlobally")) if kind == "project" else None,
            },
            "requirements": {
                "prereqs": research_template_prereqs(template),
                "factionPrereq": string_list(template.get("factionPrereq")),
                "requiredMilestone": template.get("requiredMilestone"),
                "requiredObjectiveName": template.get("requiredObjectiveName"),
                "altRequiredObjectiveName": template.get("altRequiredObjectiveName"),
                "requiresNation": template.get("requiresNation"),
            },
            "effects": effects,
            "resourcesGranted": grants,
            "orgGranted": template.get("orgGranted"),
            "unlocks": unlocks,
            "categoryContext": category_context,
            "scoreEvidence": {
                "estimatedDaysAtReferenceWeight": eta.get("days"),
                "categoryEffectiveMultiplier": category_context.get("effectiveMultiplierIfAddedToCurrentMix"),
                "directUnlockCount": unlocks.get("count"),
                "aiCriticalTech": bool(template.get("AI_criticalTech")),
                "deficientResourceTypesCovered": grants.get("deficientResourceTypesCovered"),
                "progressFraction": progress_fraction or 0.0,
            },
        },
        6,
    )


def score_research_plan_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    positive_days = [
        as_float((candidate.get("scoreEvidence") or {}).get("estimatedDaysAtReferenceWeight"), 0.0)
        for candidate in candidates
        if as_float((candidate.get("scoreEvidence") or {}).get("estimatedDaysAtReferenceWeight"), 0.0) > 0.0
    ]
    min_days = min(positive_days) if positive_days else 0.0
    max_category = max(
        [as_float((candidate.get("scoreEvidence") or {}).get("categoryEffectiveMultiplier"), 0.0) for candidate in candidates]
        or [0.0]
    )
    max_unlocks = max(
        [as_float((candidate.get("scoreEvidence") or {}).get("directUnlockCount"), 0.0) for candidate in candidates]
        or [0.0]
    )
    max_deficient = max(
        [as_float((candidate.get("scoreEvidence") or {}).get("deficientResourceTypesCovered"), 0.0) for candidate in candidates]
        or [0.0]
    )
    for candidate in candidates:
        evidence = candidate.get("scoreEvidence") if isinstance(candidate.get("scoreEvidence"), dict) else {}
        days = as_float(evidence.get("estimatedDaysAtReferenceWeight"), 0.0)
        category = as_float(evidence.get("categoryEffectiveMultiplier"), 0.0)
        unlocks = as_float(evidence.get("directUnlockCount"), 0.0)
        deficient = as_float(evidence.get("deficientResourceTypesCovered"), 0.0)
        progress = as_float(evidence.get("progressFraction"), 0.0)
        scores = {
            "fastCompletion": 100.0 * min_days / days if min_days > 0.0 and days > 0.0 else 0.0,
            "factionSynergy": 100.0 * category / max_category if max_category > 0.0 else 0.0,
            "unlockBreadth": 100.0 * unlocks / max_unlocks if max_unlocks > 0.0 else 0.0,
            "criticalTemplate": 100.0 if evidence.get("aiCriticalTech") else 0.0,
            "resourceReliefCoverage": 100.0 * deficient / max_deficient if max_deficient > 0.0 else 0.0,
            "currentProgress": min(max(progress * 100.0, 0.0), 100.0),
        }
        candidate["objectiveScores"] = clean_numbers(scores, 6)
    return candidates


def research_plan_goal_views(candidates: list[dict[str, Any]], top: int) -> dict[str, list[dict[str, Any]]]:
    views: dict[str, list[dict[str, Any]]] = {}
    for axis in RESEARCH_PLAN_SCORE_AXES:
        rows = sorted(
            candidates,
            key=lambda candidate: (
                -as_float((candidate.get("objectiveScores") or {}).get(axis), 0.0),
                as_float((candidate.get("scoreEvidence") or {}).get("estimatedDaysAtReferenceWeight"), 1_000_000_000.0),
                str(candidate.get("display") or candidate.get("template")),
            ),
        )
        views[axis] = [
            {
                "template": row.get("template"),
                "display": row.get("display"),
                "kind": row.get("kind"),
                "category": row.get("category"),
                "score": (row.get("objectiveScores") or {}).get(axis),
                "scoreEvidence": row.get("scoreEvidence"),
            }
            for row in rows[:top]
            if as_float((row.get("objectiveScores") or {}).get(axis), 0.0) > 0.0
        ]
    return views


def research_plan_shortlist(candidates: list[dict[str, Any]], top: int) -> list[dict[str, Any]]:
    selected: dict[tuple[str, str], dict[str, Any]] = {}
    for rows in research_plan_goal_views(candidates, top).values():
        for row in rows:
            key = (str(row.get("kind")), str(row.get("template")))
            found = next(
                (
                    candidate
                    for candidate in candidates
                    if candidate.get("kind") == row.get("kind") and candidate.get("template") == row.get("template")
                ),
                None,
            )
            if found:
                selected[key] = found
    return sorted(
        selected.values(),
        key=lambda candidate: (
            str(candidate.get("kind")),
            str(candidate.get("category")),
            as_float((candidate.get("scoreEvidence") or {}).get("estimatedDaysAtReferenceWeight"), 1_000_000_000.0),
            str(candidate.get("display") or candidate.get("template")),
        ),
    )


def calculate_research_plan(
    indexed: IndexedState,
    templates_dir: Path | None,
    faction_name: str | None = None,
    top: int = 8,
    mode: str = "all",
    include_all_candidates: bool = False,
) -> dict[str, Any]:
    research_templates = load_research_templates(templates_dir)
    base_daily_cache: dict[int, float] = {}
    trait_templates = research_templates.traits
    org_templates = research_templates.orgs
    hab_module_templates = research_templates.hab_modules
    utility_module_templates = research_templates.utility_modules
    tech_templates = research_templates.techs
    project_templates = research_templates.projects

    faction_id, faction = find_faction_state(indexed, faction_name)
    topbar = calculate_topbar(
        indexed,
        templates_dir,
        faction_name,
        include_details=False,
        research_templates=research_templates,
        base_daily_cache=base_daily_cache,
    )
    base_daily = faction_base_research_daily(
        indexed,
        templates_dir,
        faction,
        templates=research_templates,
        cache=base_daily_cache,
    )
    research_ui = calculate_research_ui(
        indexed,
        templates_dir,
        faction_name,
        templates=research_templates,
        base_daily_cache=base_daily_cache,
    )
    progress_by_project = project_progress_records_by_template(faction)

    global_candidates: list[dict[str, Any]] = []
    if mode in {"all", "global"}:
        global_fraction = research_plan_reference_weight_fraction(faction, "global")
        global_candidates = [
            research_plan_candidate_row(
                indexed,
                faction,
                name,
                template,
                "global",
                base_daily,
                global_fraction,
                None,
                topbar,
                trait_templates,
                org_templates,
                hab_module_templates,
                utility_module_templates,
                tech_templates,
                project_templates,
            )
            for name, template in available_global_research_templates(indexed, tech_templates)
        ]
        score_research_plan_candidates(global_candidates)

    project_candidates: list[dict[str, Any]] = []
    if mode in {"all", "project"}:
        project_fraction = research_plan_reference_weight_fraction(faction, "project")
        project_candidates = [
            research_plan_candidate_row(
                indexed,
                faction,
                name,
                template,
                "project",
                base_daily,
                project_fraction,
                progress_by_project.get(name),
                topbar,
                trait_templates,
                org_templates,
                hab_module_templates,
                utility_module_templates,
                tech_templates,
                project_templates,
            )
            for name, template in available_project_research_templates(faction, project_templates)
        ]
        score_research_plan_candidates(project_candidates)

    current_projects = research_ui.get("projects") if isinstance(research_ui.get("projects"), dict) else {}
    report = {
        "faction": faction_brief(faction_id, faction),
        "date": (first_value(indexed, "TITimeState") or {}).get("currentDateTime"),
        "questionSupported": "다음 글로벌 연구/프로젝트 연구는 어떤 기술이 좋아?",
        "mode": mode,
        "templateAvailability": {
            "templatesDir": str(templates_dir) if templates_dir else None,
            "globalTechTemplates": len(tech_templates),
            "projectTemplates": len(project_templates),
            "warning": None if tech_templates and project_templates else "Template files are required for candidate collection.",
        },
        "currentState": {
            "researchIncome": research_ui.get("researchIncome"),
            "slotAllocation": research_ui.get("slotAllocation"),
            "activeGlobalResearch": research_ui.get("globalResearch"),
            "activeProjects": current_projects.get("active"),
            "pausedOrStoredProjects": current_projects.get("pausedOrStored"),
            "resourceConstraints": {
                "resourceIncomeDeficiencies": topbar.get("resourceIncomeDeficiencies"),
                "missionControl": (topbar.get("resources") or {}).get("MissionControl"),
                "monthlyResourceDeltas": {
                    resource: row.get("monthly")
                    for resource, row in (topbar.get("resources") or {}).items()
                    if isinstance(row, dict) and resource in {"Money", "Boost", "Water", "Volatiles", "Metals", "NobleMetals", "Fissiles"}
                },
            },
        },
        "globalResearchCandidates": {
            "count": len(global_candidates),
            "source": "TITechTemplate entries whose prereqs are all in TIGlobalResearchState.finishedTechsNames, excluding finished and active techs.",
            "goalViews": research_plan_goal_views(global_candidates, top),
            "shortlist": research_plan_shortlist(global_candidates, top),
        },
        "projectResearchCandidates": {
            "count": len(project_candidates),
            "source": "TIFactionState.availableProjectNames, excluding active project slots; paused/stored progress is included as candidate progress.",
            "goalViews": research_plan_goal_views(project_candidates, top),
            "shortlist": research_plan_shortlist(project_candidates, top),
        },
        "scoreModel": {
            "automatedJudgmentBoundary": "Scores are objective proxy signals for LLM review, not a final utility ranking.",
            "axes": {
                "fastCompletion": "100 for the fastest candidate in the same candidate pool; uses remaining research divided by estimated daily output at the current reference slot weight.",
                "factionSynergy": "Normalized effective multiplier from current category bonuses if this candidate were added to the current research mix.",
                "unlockBreadth": "Normalized count of direct downstream global tech and project templates listing this template as a prereq or alternate prereq.",
                "criticalTemplate": "100 when template metadata marks AI_criticalTech true; otherwise 0.",
                "resourceReliefCoverage": "Normalized count of resource types granted by the project that are currently listed as faction resource-income deficiencies; quantities are kept separately by resource.",
                "currentProgress": "Existing accumulated progress divided by cost, useful for paused/stored projects.",
            },
            "referenceSlotWeights": {
                "global": research_plan_reference_weight_fraction(faction, "global"),
                "project": research_plan_reference_weight_fraction(faction, "project"),
            },
            "limitations": [
                "The tool does not decide strategic priority weights such as whether war, economy, alien-objective progress, or expansion matters most.",
                "Global candidate ETA assumes adding the candidate to the current research mix and current slot weights; actual UI selection may replace a completed slot and change category-penalty math.",
                "Project availability is taken from the save's availableProjectNames; hidden unlock chance mechanics are not re-simulated.",
                "Resource grants are not converted into a single cross-resource utility value.",
            ],
        },
        "llmDecision": {
            "recommendedUse": [
                "Pick the user's strategic goal first.",
                "Use goalViews to find candidates high on the relevant objective signal.",
                "Use shortlist rows for effects, unlocks, costs, ETA, current constraints, and deficiencies.",
                "Make the final recommendation in natural language, explicitly separating automated facts from strategic judgment.",
            ],
            "finalRecommendationAutomated": False,
        },
        "sourceNotes": [
            "This report combines research-ui, topbar, global tech templates, project templates, and faction available-project state.",
            "ObjectiveScores are normalized within global and project candidate pools separately.",
            "Keyword tags are transparent string matches over template names, AI roles, and effect names; they are aids for scanning, not game rules.",
        ],
    }
    if include_all_candidates:
        report["globalResearchCandidates"]["all"] = global_candidates
        report["projectResearchCandidates"]["all"] = project_candidates
    return clean_numbers(report, 6)


def command_research_plan(save_path: Path, templates_dir: Path | None, args: argparse.Namespace) -> None:
    data = load_save(save_path)
    indexed = build_index(data)
    result = calculate_research_plan(
        indexed,
        templates_dir,
        faction_name=args.faction,
        top=args.top,
        mode=args.mode,
        include_all_candidates=args.all_candidates,
    )
    print_json(result, compact=args.compact)


def faction_is_player(indexed: IndexedState, faction: dict[str, Any]) -> bool:
    metadata = first_value(indexed, "TIMetadataState") or {}
    player_name = metadata.get("playerFactionName")
    if player_name and str(player_name) == str(faction.get("displayName")):
        return True
    player = resolve_ref(indexed, faction.get("player"))
    return bool(player and player[2].get("templateName") == "ResistPlayer")


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


def faction_yearly_income_from_ships(
    indexed: IndexedState,
    templates_dir: Path | None,
    faction: dict[str, Any],
    resource: str,
) -> float:
    if resource != "Money":
        return 0.0
    hull_templates = load_named_templates(templates_dir, "TIShipHullTemplate.json")
    designs = faction_ship_designs(faction)
    monthly = 0.0
    for ship in faction_ship_states(indexed, faction):
        design = designs.get(str(ship.get("templateName")), {})
        hull = hull_templates.get(str(design.get("hullName")), {})
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
            total_month += nation_influence_contribution_month(indexed, nation, faction)
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
    hab_module_templates = load_named_templates(templates_dir, "TIHabModuleTemplate.json")
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
) -> dict[str, float]:
    base_incomes = faction.get("baseIncomes_year") if isinstance(faction.get("baseIncomes_year"), dict) else {}
    hq = as_float(base_incomes.get("MissionControl"), 0.0) + scenario_float(indexed, "missionControlBonus", 0.0)
    councilors = faction_yearly_income_from_councilors(indexed, faction, trait_templates, councilor_by_id, "MissionControl")
    nations = faction_yearly_income_from_nations(indexed, faction_id, faction, councilor_by_id, effect_contexts, effect_templates, "MissionControl")
    habs = 0.0
    hab_module_templates = load_named_templates(templates_dir, "TIHabModuleTemplate.json")
    for _, hab in faction_hab_states(indexed, faction):
        for record in hab_module_records(indexed, hab, hab_module_templates):
            template = record.get("template") if isinstance(record.get("template"), dict) else {}
            value = int(as_float(template.get("missionControl"), 0.0))
            if hab_module_active_record(record) and value > 0:
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


def nation_control_point_maintenance_cost(nation: dict[str, Any]) -> float:
    control_points = max(int(as_float(nation.get("numControlPoints"), 0.0)), 1)
    gdp_billions = as_float(nation.get("GDP"), 0.0) / 1_000_000_000.0
    if gdp_billions <= 0.0:
        return 0.0
    return (gdp_billions ** DEFAULT_GLOBAL_CONFIG["controlPointCostScaling"]) / (
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
    baseline = 0.0
    for cp_ref in faction.get("controlPoints") if isinstance(faction.get("controlPoints"), list) else []:
        cp = state_value_by_id(indexed, ref_id(cp_ref))
        if not isinstance(cp, dict) or cp.get("benefitsDisabled"):
            continue
        nation = state_value_by_id(indexed, ref_id(cp.get("nation")))
        if isinstance(nation, dict):
            baseline += nation_control_point_maintenance_cost(nation)

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
    hab_module_templates = load_named_templates(templates_dir, "TIHabModuleTemplate.json")
    for _, hab in faction_hab_states(indexed, faction):
        habs += hab_control_point_capacity(hab, hab_module_records(indexed, hab, hab_module_templates))

    effect_delta = effect_modifier_delta(effect_contexts, effect_templates, "ControlPointMaintenance", global_freebies)
    cap = global_freebies + councilors + habs - effect_delta
    overage = max(baseline - cap, 0.0)
    return {
        "usage": baseline,
        "cap": cap,
        "overage": overage,
        "annualInfluenceCost": overage * overage,
        "missionPenaltyRecent": (faction.get("history_CPCapOverageByDay") or [0.0])[0],
        "missionPenaltyCurrent": overage * DEFAULT_GLOBAL_CONFIG["TIMissionModifier_ControlPointOverage_Multiplier"],
        "components": {
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


def calculate_topbar(
    indexed: IndexedState,
    templates_dir: Path | None,
    faction_name: str | None = None,
    include_details: bool = False,
    *,
    research_templates: ResearchTemplates | None = None,
    base_daily_cache: dict[int, float] | None = None,
) -> dict[str, Any]:
    trait_templates = research_templates.traits if research_templates else load_trait_templates(templates_dir)
    effect_templates = research_templates.effects if research_templates else load_named_templates(templates_dir, "TIEffectTemplate.json")
    faction_id, faction = find_faction_state(indexed, faction_name)
    effect_contexts = faction_effect_contexts(indexed, faction_id)
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
    )
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
            rows[resource] = clean_numbers(
                {
                    "usage": as_float(faction.get("missionControlUsage"), 0.0),
                    "capacity": mc_components["total"],
                    "available": max(mc_components["total"] - as_float(faction.get("missionControlUsage"), 0.0), 0.0),
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
        },
        "showMonthlyIncomes": bool(faction.get("showMonthlyIncomesInTopBarAndIntel")),
        "resources": rows,
        "controlPointMaintenance": clean_numbers(cp_maintenance, 6),
        "resourceIncomeDeficiencies": faction.get("resourceIncomeDeficiencies") or [],
        "sourceNotes": [
            "Top-bar stockpiles are raw TIFactionState.resources.",
            "Top-bar non-research deltas use TIFactionState.GetMonthlyIncome-equivalent yearly components divided by 12 when monthly display is enabled.",
            "Research row includes the distribution-slot bonus, matching GeneralControlsController.ResourceReportString.",
        ],
    }
    return output


def command_topbar(save_path: Path, templates_dir: Path | None, args: argparse.Namespace) -> None:
    data = load_save(save_path)
    indexed = build_index(data)
    result = calculate_topbar(indexed, templates_dir, args.faction, include_details=args.details)
    print_json(result, compact=args.compact)


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
    hab_module_templates = load_named_templates(templates_dir, "TIHabModuleTemplate.json")
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
    effect_templates = load_named_templates(templates_dir, "TIEffectTemplate.json")
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


def command_world_ui(save_path: Path, templates_dir: Path | None, args: argparse.Namespace) -> None:
    data = load_save(save_path)
    indexed = build_index(data)
    result = calculate_world_ui(indexed, templates_dir, args.faction)
    print_json(clean_numbers(result, 6), compact=args.compact)


def command_advise(save_path: Path, templates_dir: Path | None, args: argparse.Namespace) -> None:
    data = load_save(save_path)
    indexed = build_index(data)
    trait_templates = load_trait_templates(templates_dir)
    effect_templates = load_named_templates(templates_dir, "TIEffectTemplate.json")
    faction_id, faction = find_faction_state(indexed, args.faction)
    effect_contexts = faction_effect_contexts(indexed, faction_id)
    summaries, councilor_by_id = councilor_summary_maps(indexed, trait_templates)
    councilor = match_named(summaries, args.councilor)
    if not councilor:
        raise SystemExit(f"Councilor not found: {args.councilor}")
    nation_match = match_raw_state(indexed, "TINationState", args.nation)
    if not nation_match:
        raise SystemExit(f"Nation not found: {args.nation}")
    nation_id, nation = nation_match

    science = as_float((councilor.get("finalAttributes") or {}).get("Science"), 0.0)
    extra_advisor = (int(councilor["id"]), science)
    before_month = nation_research_contribution_month(
        indexed,
        nation,
        faction_id,
        councilor_by_id,
        effect_contexts,
        effect_templates,
    )
    after_month = nation_research_contribution_month(
        indexed,
        nation,
        faction_id,
        councilor_by_id,
        effect_contexts,
        effect_templates,
        extra_advisor=extra_advisor,
    )
    before_daily = before_month * 12.0 / DAYS_PER_YEAR
    after_daily = after_month * 12.0 / DAYS_PER_YEAR
    delta_source_daily = after_daily - before_daily

    current_breakdown = calculate_research_breakdown(indexed, templates_dir, args.faction, include_details=False)
    distribution_percent = as_float(current_breakdown.get("distribution", {}).get("percent"), 0.0)
    delta_after_distribution = delta_source_daily * (1.0 + distribution_percent)
    current_total_daily = as_float(current_breakdown.get("daily", {}).get("total"), 0.0)
    owned_control_points = len(active_owned_control_points(indexed, nation, faction_id))
    notes = []
    if nation_population_millions(indexed, nation) <= 0.0:
        notes.append("Target nation has no population/regions in this save, so its research contribution is zero.")
    if owned_control_points <= 0:
        notes.append("The faction owns no active control points in the target nation, so contribution increase is zero.")

    result = {
        "faction": {
            "id": faction_id,
            "template": faction.get("templateName"),
            "display": faction.get("displayName"),
        },
        "councilor": {
            "id": councilor.get("id"),
            "display": councilor.get("display"),
            "science": science,
        },
        "nation": {
            "id": nation_id,
            "template": nation.get("templateName"),
            "code": campaign_code(nation.get("templateName")),
            "display": nation.get("displayName"),
            "ownedControlPoints": owned_control_points,
            "totalControlPoints": nation.get("numControlPoints"),
            "population_Millions": nation_population_millions(indexed, nation),
        },
        "daily": {
            "nationContributionBefore": before_daily,
            "nationContributionAfter": after_daily,
            "deltaBeforeDistribution": delta_source_daily,
            "deltaAfterDistribution": delta_after_distribution,
            "currentFactionTotal": current_total_daily,
            "projectedFactionTotal": current_total_daily + delta_after_distribution,
        },
        "distribution": {
            "percent": distribution_percent,
        },
        "notes": notes,
    }
    print_json(clean_numbers(result, 6), compact=args.compact)


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


def nation_priority_rows(indexed: IndexedState, nation: dict[str, Any]) -> list[dict[str, Any]]:
    control_points = nation_control_points(indexed, nation)
    representative = control_points[0] if control_points else {}
    priorities = representative.get("controlPointPriorities") if isinstance(representative.get("controlPointPriorities"), dict) else {}
    accumulated = nation.get("_accumulatedInvestmentPoints") if isinstance(nation.get("_accumulatedInvestmentPoints"), dict) else {}
    total_weight = int(as_float(representative.get("totalWeightsForControlPoint"), 0.0))
    rows: list[dict[str, Any]] = []
    for key, label, priority_key, accumulated_key, cost in NATION_PRIORITY_ROWS:
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
                "cost": cost,
            }
        )
    inactive_with_weights = {
        key: int(as_float(priorities.get(key), 0.0))
        for key in NATION_INACTIVE_PRIORITY_KEYS
        if int(as_float(priorities.get(key), 0.0)) > 0
    }
    if inactive_with_weights:
        rows.append(
            {
                "key": "_inactiveRawWeights",
                "label": "UI 비활성 원시 weight",
                "weights": inactive_with_weights,
                "note": "Raw save keeps these requested weights, but UI/controlPoint totalWeights excludes them because the priority is complete, capped, or unavailable.",
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
        raise SystemExit(f"Nation not found: {nation_name}")
    nation_id, nation = found
    faction_id, faction = find_faction_state(indexed, faction_name)
    trait_templates = load_trait_templates(templates_dir)
    effect_templates = load_named_templates(templates_dir, "TIEffectTemplate.json")
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
    can_have_navy = nation_can_have_navy(nation, pc_gdp)
    max_navies = allowed_armies if can_have_navy else 0
    navies_can_build = max(0, armies["count"] - armies["navies"]) if can_have_navy else 0
    control_points = nation_control_points(indexed, nation)
    representative_cp = first_control_point(indexed, nation) or {}
    total_weight = int(as_float(representative_cp.get("totalWeightsForControlPoint"), 0.0))

    output = {
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
            "rows": nation_priority_rows(indexed, nation),
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


def command_nation_ui(save_path: Path, templates_dir: Path | None, args: argparse.Namespace) -> None:
    data = load_save(save_path)
    indexed = build_index(data)
    result = calculate_nation_ui(indexed, templates_dir, args.name, args.faction)
    print_json(result, compact=args.compact)


def command_summary(snapshot: dict[str, Any], args: argparse.Namespace) -> None:
    player_name = snapshot.get("metadata", {}).get("playerFactionName")
    player_faction = None
    if player_name:
        player_faction = match_named(snapshot["factions"], player_name)
    if player_faction is None and snapshot["factions"]:
        player_faction = next((f for f in snapshot["factions"] if f.get("player", {}).get("template") == "ResistPlayer"), None)

    top_nations = []
    if player_faction:
        top_nations = player_faction.get("controlledNations", [])[: args.top_nations]

    factions = []
    for faction in snapshot["factions"]:
        resources = faction.get("resources") or {}
        base_incomes = faction.get("baseIncomes_year") or {}
        factions.append(
            {
                "template": faction.get("template"),
                "display": faction.get("display"),
                "controlPoints": faction.get("controlPoints"),
                "habSectors": faction.get("habSectors"),
                "fleets": faction.get("fleets"),
                "missionControlUsage": faction.get("missionControlUsage"),
                "money": resources.get("Money"),
                "influence": resources.get("Influence"),
                "ops": resources.get("Operations"),
                "exotics": resources.get("Exotics"),
                "researchYear": base_incomes.get("Research"),
                "assessedAlienHateOfMe": faction.get("assessedAlienHateOfMe"),
                "cpOverageRecent": faction.get("cpOverageRecent"),
                "mcShortageRecent": faction.get("mcShortageRecent"),
            }
        )

    output = {
        "source": snapshot.get("source"),
        "currentID": snapshot.get("currentID"),
        "time": snapshot.get("time"),
        "metadata": snapshot.get("metadata"),
        "global": snapshot.get("global"),
        "counts": snapshot.get("typeCounts"),
        "factions": factions,
        "playerControlledNations": top_nations,
    }
    print_json(output, compact=args.compact)


def command_faction(snapshot: dict[str, Any], args: argparse.Namespace) -> None:
    faction = match_named(snapshot["factions"], args.name)
    if not faction:
        raise SystemExit(f"Faction not found: {args.name}")
    result = dict(faction)
    result["controlledNations"] = result.get("controlledNations", [])[: args.limit]
    print_json(result, compact=args.compact)


def command_nation(snapshot: dict[str, Any], args: argparse.Namespace) -> None:
    nation = match_named(snapshot["nations"], args.name)
    if not nation:
        raise SystemExit(f"Nation not found: {args.name}")
    print_json(nation, compact=args.compact)


def command_councilor(snapshot: dict[str, Any], args: argparse.Namespace) -> None:
    councilor = match_named(snapshot["councilors"], args.name)
    if not councilor:
        raise SystemExit(f"Councilor not found: {args.name}")
    result = dict(councilor)
    if args.target_nation and args.current_location_context:
        raise SystemExit("Use only one of --target-nation or --current-location-context.")
    context_nation = None
    context_label = None
    if args.target_nation:
        context_nation = match_named(snapshot["nations"], args.target_nation)
        if not context_nation:
            raise SystemExit(f"Target nation not found: {args.target_nation}")
        context_label = "targetNation"
    elif args.current_location_context:
        context_nation = councilor.get("locationNation") if isinstance(councilor.get("locationNation"), dict) else None
        if not context_nation:
            raise SystemExit(f"Current location nation unavailable for councilor: {args.name}")
        context_label = "currentLocation"

    if context_label:
        result.update(evaluate_councilor_conditionals(councilor, snapshot, context_nation, context_label))
    if not args.details:
        result.pop("traitModDetails", None)
        result.pop("conditionalTraitMods", None)
        result.pop("orgDetails", None)
        result.pop("evaluatedConditionalTraitMods", None)
    print_json(result, compact=args.compact)


def command_types(snapshot: dict[str, Any], args: argparse.Namespace) -> None:
    items = list(snapshot.get("typeCounts", {}).items())
    if args.limit:
        items = items[: args.limit]
    print_json([{"type": key, "count": value} for key, value in items], compact=args.compact)


def command_export(snapshot: dict[str, Any], args: argparse.Namespace) -> None:
    output = Path(args.output).expanduser()
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        json.dump(snapshot, handle, ensure_ascii=False, indent=2)
    print_json({"wrote": str(output), "bytes": output.stat().st_size}, compact=args.compact)


def parse_key_list(value: str | None) -> list[str] | None:
    if not value:
        return None
    return [item.strip() for item in value.split(",") if item.strip()]


def raw_entry_matches(entry: dict[str, Any], args: argparse.Namespace) -> bool:
    value = entry.get("Value") or {}
    if args.id is not None:
        state_id = ref_id(entry.get("Key")) or ref_id(value.get("ID"))
        if state_id != args.id:
            return False
    if args.template and value.get("templateName") != args.template:
        return False
    if args.display:
        display = str(value.get("displayName") or "")
        if args.display.casefold() not in display.casefold():
            return False
    return True


def command_raw(save_path: Path, args: argparse.Namespace) -> None:
    data = load_save(save_path)
    indexed = build_index(data)
    entries = type_entries(indexed, args.type)
    keys = parse_key_list(args.keys)
    output = []
    for entry in entries:
        if not raw_entry_matches(entry, args):
            continue
        value = entry.get("Value") or {}
        state_id = ref_id(entry.get("Key")) or ref_id(value.get("ID"))
        if keys:
            sliced = {key: value.get(key) for key in keys}
            sliced["id"] = state_id
            output.append(sliced)
        else:
            output.append({"id": state_id, "value": value})
        if len(output) >= args.limit:
            break
    print_json(clean_numbers(output), compact=args.compact)


def build_parser() -> argparse.ArgumentParser:
    from ti_parser_cli import build_parser as build_cli_parser

    return build_cli_parser(sys.modules[__name__])


def main(argv: list[str] | None = None) -> int:
    from ti_parser_cli import main as cli_main

    return cli_main(sys.modules[__name__], argv)


if __name__ == "__main__":
    raise SystemExit(main())
