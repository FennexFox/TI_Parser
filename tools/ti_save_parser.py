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
    CalculationDependency,
    CalculationDependencyError,
    DEFAULT_CACHE_DIR,
    SAVE_GLOB,
    IndexedState,
    LocationCatalogError,
    SolarPowerDataError,
    TemplateSource,
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
    faction_is_human_player,
    find_faction_state,
    find_latest_save,
    first_value,
    json_default,
    load_named_templates,
    load_hab_module_catalog,
    load_location_catalog,
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
    resolve_scenario_templates,
    resolve_templates_dir,
    save_fingerprint,
    scenario_template_name,
    short_type,
    snapshot_fingerprint,
    state_value_by_id,
    template_source_value,
    type_entries,
    module_catalog_diagnostics,
    location_catalog_diagnostics,
)
from ti_parser_catalogs import (
    CatalogIntegrityError,
    RuntimeCatalogs,
    UnsupportedCatalogScenarioError,
    load_runtime_catalogs,
)
from ti_parser_ai import calculate_ai_fleet_diagnostics
from ti_parser_claims import calculate_nation_claims
from ti_parser_verify import verify_catalogs
import ti_parser_snapshot as snapshot_layer
import ti_parser_income as income_layer
import ti_parser_hab as hab_layer
import ti_parser_org as org_layer
from ti_parser_snapshot import SnapshotConfig


SCHEMA_VERSION = 6
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
    "crewBaselineWater_tons": 2.0,
    "crewBaselineVolatiles_tons": 2.0,
    "crewWaterConsumptionTons_year": 3.5,
    "crewVolatilesConsumptionTons_year": 3.5,
    "crewSalary_year": 0.1,
    "baselineMaxHumanCruiseAcceleration_g": 2.0,
    "baselineMaxHumanCombatAcceleration_g": 3.0,
    "smallShipyardPenaltyPowerPerTier": 1.5,
}


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
    try:
        return load_runtime_catalogs(
            scenario,
            catalog_files=(
                "effect_catalog.json",
                "trait_catalog.json",
                "org_catalog.json",
                "research_catalog.json",
                "ship_catalog.json",
                "nation_claim_catalog.json",
            ),
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
) -> dict[str, Any]:
    """Resolve a referenced catalog row or stop the calculation as incomplete."""

    normalized = str(name or "")
    row = rows.get(normalized)
    if normalized and isinstance(row, dict):
        return row
    raise CalculationDependencyError(
        CalculationDependency(
            kind=kind,
            name=normalized or "<missing reference>",
            context=context,
            scenario=scenario_template_name(indexed),
            reason="save references a row absent from the packaged catalog",
        )
    )


DEFAULT_CP_MAINTENANCE_GDP_SCALE = 1_000_000_000.0
CP_MAINTENANCE_CAMPAIGN_START_GDP_FACTOR = 6.26e-06
MIN_POPULATION_FOR_FIRST_ARMY_MILLIONS = 5.0
MIN_POPULATION_FOR_ADDITIONAL_ARMIES_PER_MILLIONS = 25.0
MIN_CONTROL_POINTS_FOR_NAVY = 4
MIN_CONTROL_POINTS_FOR_NAVY_EXCEPTION = 3
PCGDP_FOR_NAVY_EXCEPTION = 40000.0
STANDARD_GRAVITY_MPS2 = 9.806650161743164
GRAVITATIONAL_CONSTANT = 6.67384e-11
ASTRONOMICAL_UNIT_KM = 149_597_870.7
MAX_SOLAR_POWER_MULTIPLIER = 8.0
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


@dataclass(frozen=True)
class ScenarioRules:
    build_army_priority_cost: float = 60.0
    control_point_maintenance_multiplier: float = 1.0


DEFAULT_SCENARIO_RULES = ScenarioRules()
SCENARIO_RULE_OVERRIDES = MappingProxyType(
    {
        "BrokenEarthScenario": ScenarioRules(
            build_army_priority_cost=40.0,
            control_point_maintenance_multiplier=0.7,
        ),
    }
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
TOPBAR_EFFECT_CONTEXTS = frozenset(
    {
        "ControlPointMaintenance",
        "MissionControlDisruption_PCT",
        "SpaceMiningBonus",
        "MiningWaterBonus",
        "MiningVolatilesBonus",
        "MiningMetalsBonus",
        "MiningNoblesBonus",
        "MiningFissilesBonus",
        "PublicOpinionInfluence",
        "ControlPointResearch",
        "HabResearchProduction",
    }
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
SHIP_PLAN_ROLE_CHOICES = ("balanced", "combat", "intercept", "transfer", "colony", "assault", "science")
SHIP_PLAN_WEAPON_TEMPLATE_FILES = (
    ("gun", "TIGunTemplate.json"),
    ("magnetic", "TIMagneticGunTemplate.json"),
    ("missile", "TIMissileTemplate.json"),
    ("laser", "TILaserWeaponTemplate.json"),
    ("particle", "TIParticleWeaponTemplate.json"),
    ("plasma", "TIPlasmaWeaponTemplate.json"),
)
SHIP_PLAN_UTILITY_TEMPLATE_FILES = (
    ("utility", "TIUtilityModuleTemplate.json"),
    ("battery", "TIBatteryTemplate.json"),
    ("heatSink", "TIHeatSinkTemplate.json"),
)
SHIP_PLAN_SHIPYARD_TIERS = {
    1: {"template": "SpaceDock", "constructionTimeModifier": 1.0},
    2: {"template": "Shipyard", "constructionTimeModifier": 0.8},
    3: {"template": "Spaceworks", "constructionTimeModifier": 0.6},
}
SHIP_PLAN_SELF_POWERED_DRIVE_CLASSES = {
    "Chemical",
    "Fission_Pulse",
    "NuclearSaltWater",
    "Fusion_Pulse",
}
SHIP_PLAN_MOUNT_SLOTS = {
    "HalfHull": ("hull", 0.5),
    "HalfNose": ("nose", 0.5),
    "OneHull": ("hull", 1.0),
    "TwoHullHoriz": ("hull", 2.0),
    "FourHull": ("hull", 4.0),
    "OneNose": ("nose", 1.0),
    "TwoNoseVert": ("nose", 2.0),
    "ThreeNoseAngle": ("nose", 3.0),
    "FourNose": ("nose", 4.0),
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


def space_body_template(
    body: dict[str, Any] | None,
    body_templates: dict[str, dict[str, Any]] | None,
) -> dict[str, Any]:
    if not body:
        return {}
    template_name = str(body.get("templateName") or "")
    template = (body_templates or {}).get(template_name)
    if template is None and template_name:
        raise LocationCatalogError(f"Space-body template {template_name!r} is missing from the packaged location catalog")
    return template or {}


def space_body_mean_radius_km(template: dict[str, Any]) -> float:
    mean_radius = as_float(template.get("meanRadius_km"), 0.0)
    if mean_radius > 0.0:
        return mean_radius
    equatorial_radius = as_float(template.get("equatorialRadius_km"), 0.0)
    if equatorial_radius > 0.0:
        polar_radius = equatorial_radius * (1.0 - as_float(template.get("oblateness"), 0.0))
        return (equatorial_radius * 2.0 + polar_radius) / 3.0
    dimensions = [
        dimension
        for field in ("dimensionX_km", "dimensionY_km", "dimensionZ_km")
        if (dimension := as_float(template.get(field), 0.0)) > 0.0
    ]
    return sum(dimensions) / len(dimensions) / 2.0 if dimensions else 0.0


def space_body_max_radius_km(template: dict[str, Any]) -> float:
    normalized_radius = as_float(template.get("maxRadius_km"), 0.0)
    if normalized_radius > 0.0:
        return normalized_radius
    dimensions = [
        dimension
        for field in ("dimensionX_km", "dimensionY_km", "dimensionZ_km")
        if (dimension := as_float(template.get(field), 0.0)) > 0.0
    ]
    if dimensions:
        return max(dimensions) / 2.0
    equatorial_radius = as_float(template.get("equatorialRadius_km"), 0.0)
    return equatorial_radius if equatorial_radius > 0.0 else space_body_mean_radius_km(template)


def natural_space_object_sun_distance_au(
    indexed: IndexedState,
    location: dict[str, Any] | None,
    body_templates: dict[str, dict[str, Any]],
) -> float | None:
    current = location
    visited: set[int] = set()
    while current:
        current_id = ref_id(current.get("ID"))
        if current_id is not None:
            if current_id in visited:
                return None
            visited.add(current_id)
        secondary = state_value_by_id(indexed, ref_id(current.get("secondaryObject")))
        if secondary:
            current = secondary
            continue
        template = space_body_template(current, body_templates)
        distance_au = as_float(template.get("semiMajorAxis_AU"), 0.0)
        if distance_au > 0.0:
            return distance_au
        current = state_value_by_id(indexed, ref_id(current.get("barycenter")))
    return None


def space_body_atmosphere_solar_modifier(template: dict[str, Any]) -> float:
    return {
        "Massive": 0.0,
        "Thick": 0.25,
        "Standard": 0.5,
        "Thin": 0.75,
    }.get(str(template.get("atmosphere") or ""), 1.0)


def space_body_surface_solar_visibility(
    indexed: IndexedState,
    body: dict[str, Any],
    hab_site: dict[str, Any] | None,
    body_templates: dict[str, dict[str, Any]],
) -> float:
    template = space_body_template(body, body_templates)
    object_type = str(template.get("objectType") or "")
    if object_type == "Star":
        return 1.0
    if object_type in {"Asteroid", "AsteroidalMoon"}:
        return 0.6
    if object_type == "Comet":
        return 0.3

    daylight_fraction = 0.5
    parent = state_value_by_id(indexed, ref_id(body.get("barycenter")))
    parent_template = space_body_template(parent, body_templates)
    latitude = abs(as_float((hab_site or {}).get("latitude"), 0.0))
    if (
        hab_site
        and str(parent_template.get("objectType") or "") == "Star"
        and as_float(template.get("tilt_Deg"), 0.0) < 5.0
        and latitude > 85.0
    ):
        daylight_fraction += latitude / 360.0
    return space_body_atmosphere_solar_modifier(template) * daylight_fraction


def orbit_template_semi_major_axis_km(
    orbit_template: dict[str, Any],
    barycenter_template: dict[str, Any],
) -> float:
    semi_major_axis_km = as_float(orbit_template.get("semiMajorAxis_km"), 0.0)
    altitude_km = as_float(orbit_template.get("altitude_km"), 0.0)
    semi_major_axis_au = as_float(orbit_template.get("semiMajorAxis_AU"), 0.0)
    if semi_major_axis_km <= 0.0 and altitude_km > 0.0:
        semi_major_axis_km = space_body_mean_radius_km(barycenter_template) + altitude_km
    elif semi_major_axis_km <= 0.0 and semi_major_axis_au > 0.0:
        semi_major_axis_km = semi_major_axis_au * ASTRONOMICAL_UNIT_KM
    elif semi_major_axis_km <= 0.0 and orbit_template.get("synch"):
        mass_kg = as_float(barycenter_template.get("mass_kg"), 0.0)
        rotation_hours = as_float(barycenter_template.get("rotationPeriod_strHours"), 0.0)
        if mass_kg > 0.0 and rotation_hours > 0.0:
            rotation_seconds = rotation_hours * 3600.0
            semi_major_axis_km = (
                GRAVITATIONAL_CONSTANT * mass_kg * rotation_seconds * rotation_seconds / (4.0 * math.pi * math.pi)
            ) ** (1.0 / 3.0) / 1000.0
    elif semi_major_axis_km <= 0.0 and orbit_template.get("radialOrbit"):
        semi_major_axis_km = space_body_max_radius_km(barycenter_template) * 3.25

    max_radius_km = space_body_max_radius_km(barycenter_template)
    hill_radius_km = as_float(
        barycenter_template.get("hillRadius_km", barycenter_template.get("Hill Radius in km")),
        0.0,
    )
    if semi_major_axis_km > 0.0 and max_radius_km > 0.0:
        if hill_radius_km > 0.0:
            semi_major_axis_km = min(semi_major_axis_km, hill_radius_km)
        semi_major_axis_km = max(semi_major_axis_km, max_radius_km + 10.0)
    return semi_major_axis_km


def space_body_orbit_solar_visibility(
    indexed: IndexedState,
    body: dict[str, Any],
    orbit_template: dict[str, Any],
    body_templates: dict[str, dict[str, Any]],
) -> float:
    template = space_body_template(body, body_templates)
    semi_major_axis_km = orbit_template_semi_major_axis_km(orbit_template, template)
    mean_radius_km = space_body_mean_radius_km(template)
    if semi_major_axis_km <= 0.0 or mean_radius_km <= 0.0:
        raise SolarPowerDataError(
            f"Cannot derive orbital solar visibility for {orbit_template.get('dataName') or '<unknown orbit>'}: "
            "the packaged location catalog lacks resolvable orbit radius or body radius data."
        )
    visibility = 1.0 - math.atan(mean_radius_km / semi_major_axis_km) / math.pi

    parent = state_value_by_id(indexed, ref_id(body.get("barycenter")))
    parent_template = space_body_template(parent, body_templates)
    grandparent = state_value_by_id(indexed, ref_id((parent or {}).get("barycenter")))
    grandparent_template = space_body_template(grandparent, body_templates)
    body_orbit_km = as_float(template.get("semiMajorAxis_km"), 0.0)
    parent_orbit_km = as_float(parent_template.get("semiMajorAxis_AU"), 0.0) * ASTRONOMICAL_UNIT_KM
    parent_mean_radius_km = space_body_mean_radius_km(parent_template)
    grandparent_mean_radius_km = space_body_mean_radius_km(grandparent_template)
    if (
        str(template.get("objectType") or "") in {"PlanetaryMoon", "AsteroidalMoon"}
        and as_float(template.get("inclination_Deg"), 0.0) + as_float(parent_template.get("tilt_Deg"), 0.0) < 5.0
        and body_orbit_km > 0.0
        and parent_orbit_km > 0.0
        and grandparent_mean_radius_km > 0.0
        and parent_orbit_km * parent_mean_radius_km / grandparent_mean_radius_km > body_orbit_km
    ):
        visibility *= 1.0 - math.atan(parent_mean_radius_km / body_orbit_km) / math.pi
    return visibility


def lagrange_solar_visibility(
    indexed: IndexedState,
    lagrange: dict[str, Any],
    orbit_template: dict[str, Any],
    body_templates: dict[str, dict[str, Any]],
) -> float:
    if not str(lagrange.get("templateName") or "").endswith("L2"):
        return 1.0
    secondary = state_value_by_id(indexed, ref_id(lagrange.get("secondaryObject")))
    secondary_template = space_body_template(secondary, body_templates)
    primary = state_value_by_id(indexed, ref_id((secondary or {}).get("barycenter")))
    primary_template = space_body_template(primary, body_templates)
    if str(primary_template.get("objectType") or "") != "Star":
        return 1.0

    secondary_orbit_km = as_float(secondary_template.get("semiMajorAxis_AU"), 0.0) * ASTRONOMICAL_UNIT_KM
    secondary_radius_km = space_body_mean_radius_km(secondary_template)
    primary_radius_km = space_body_mean_radius_km(primary_template)
    secondary_mass_kg = as_float(secondary_template.get("mass_kg"), 0.0)
    primary_mass_kg = as_float(primary_template.get("mass_kg"), 0.0)
    if min(secondary_orbit_km, secondary_radius_km, primary_radius_km, secondary_mass_kg, primary_mass_kg) <= 0.0:
        raise SolarPowerDataError(
            f"Cannot derive L2 solar visibility for {lagrange.get('templateName') or '<unknown Lagrange point>'}: "
            "the packaged location catalog lacks required radius, mass, or orbit data."
        )

    shadow_length_km = secondary_orbit_km * secondary_radius_km / primary_radius_km
    hill_ratio = (secondary_mass_kg / (3.0 * primary_mass_kg)) ** (1.0 / 3.0)
    eccentricity = as_float(secondary_template.get("eccentricity"), 0.0)
    minimum_l2_km = secondary_orbit_km * (1.0 - eccentricity) * hill_ratio
    if minimum_l2_km > shadow_length_km:
        return 1.0
    maximum_l2_km = secondary_orbit_km * (1.0 + eccentricity) * hill_ratio
    orbit_km = orbit_template_semi_major_axis_km(orbit_template, {})
    full_shadow_radius_km = minimum_l2_km * secondary_radius_km / shadow_length_km
    if orbit_km > full_shadow_radius_km:
        return 1.0
    return minimum_l2_km / maximum_l2_km if maximum_l2_km >= shadow_length_km else 0.05


def hab_natural_solar_multiplier(
    indexed: IndexedState,
    hab: dict[str, Any],
    body_templates: dict[str, dict[str, Any]],
    orbit_templates: dict[str, dict[str, Any]],
) -> float:
    validate_hab_solar_context(indexed, hab, body_templates, orbit_templates)
    barycenter = hab_barycenter_state(indexed, hab)
    distance_au = natural_space_object_sun_distance_au(indexed, barycenter, body_templates)
    if hab.get("habType") == "Base" or hab.get("habSite"):
        body = state_value_by_id(indexed, ref_id(hab.get("barycenter")))
        template = space_body_template(body, body_templates)
        if str(template.get("objectType") or "") == "Star":
            return 1.0
        if distance_au is None or distance_au <= 0.0 or not body:
            raise_solar_power_data_error(hab, "solar distance could not be derived from the body template chain")
        site = state_value_by_id(indexed, ref_id(hab.get("habSite")))
        return space_body_surface_solar_visibility(indexed, body, site, body_templates) / (distance_au * distance_au)

    if distance_au is None or distance_au <= 0.0:
        raise_solar_power_data_error(hab, "solar distance could not be derived from the body template chain")
    orbit_state = state_value_by_id(indexed, ref_id(hab.get("orbitState"))) or {}
    orbit_template = orbit_templates.get(str(orbit_state.get("templateName") or ""), {})
    if barycenter.get("secondaryObject"):
        visibility = lagrange_solar_visibility(indexed, barycenter, orbit_template, body_templates)
    else:
        visibility = space_body_orbit_solar_visibility(indexed, barycenter, orbit_template, body_templates)
    return visibility / (distance_au * distance_au)


def solar_hab_label(hab: dict[str, Any]) -> str:
    return str(hab.get("displayName") or hab.get("templateName") or ref_id(hab.get("ID")) or "<unknown hab>")


def raise_solar_power_data_error(hab: dict[str, Any], detail: str) -> None:
    raise SolarPowerDataError(
        f"Cannot calculate Solar_Power_Variable_Output at {solar_hab_label(hab)}: {detail}. "
        "Nominal module power is not a valid fallback."
    )


def require_solar_body_template(
    hab: dict[str, Any],
    body: dict[str, Any] | None,
    body_templates: dict[str, dict[str, Any]],
    role: str,
) -> dict[str, Any]:
    if not body:
        raise_solar_power_data_error(hab, f"{role} body state is unresolved")
    template_name = str(body.get("templateName") or "")
    if not template_name:
        raise_solar_power_data_error(hab, f"{role} body state has no templateName")
    template = body_templates.get(template_name)
    if not isinstance(template, dict) or not template:
        raise_solar_power_data_error(hab, f"required body template {template_name!r} ({role}) is missing")
    return template


def validate_hab_solar_context(
    indexed: IndexedState,
    hab: dict[str, Any],
    body_templates: dict[str, dict[str, Any]],
    orbit_templates: dict[str, dict[str, Any]],
) -> None:
    """Fail closed when a variable-output solar calculation lacks location templates."""

    if not body_templates:
        raise_solar_power_data_error(hab, "the space-body template catalog is missing or empty")
    barycenter = hab_barycenter_state(indexed, hab)
    if not barycenter:
        raise_solar_power_data_error(hab, "the hab barycenter state is unresolved")

    surface = hab.get("habType") == "Base" or bool(hab.get("habSite"))
    if surface:
        body = state_value_by_id(indexed, ref_id(hab.get("barycenter")))
        require_solar_body_template(hab, body, body_templates, "surface")
        if hab.get("habSite") and not state_value_by_id(indexed, ref_id(hab.get("habSite"))):
            raise_solar_power_data_error(hab, "the hab-site state is unresolved")
        parent = state_value_by_id(indexed, ref_id((body or {}).get("barycenter")))
        if parent:
            require_solar_body_template(hab, parent, body_templates, "surface parent")
    else:
        orbit_state = state_value_by_id(indexed, ref_id(hab.get("orbitState")))
        if not orbit_state:
            raise_solar_power_data_error(hab, "the orbit state is unresolved")
        orbit_template_name = str(orbit_state.get("templateName") or "")
        if not orbit_template_name:
            raise_solar_power_data_error(hab, "the orbit state has no templateName")
        if not orbit_templates:
            raise_solar_power_data_error(hab, "the orbit template catalog is missing or empty")
        orbit_template = orbit_templates.get(orbit_template_name)
        if not isinstance(orbit_template, dict) or not orbit_template:
            raise_solar_power_data_error(hab, f"required orbit template {orbit_template_name!r} is missing")

        if barycenter.get("secondaryObject"):
            secondary = state_value_by_id(indexed, ref_id(barycenter.get("secondaryObject")))
            require_solar_body_template(hab, secondary, body_templates, "Lagrange secondary")
            primary = state_value_by_id(indexed, ref_id((secondary or {}).get("barycenter")))
            if primary:
                require_solar_body_template(hab, primary, body_templates, "Lagrange primary")
        else:
            require_solar_body_template(hab, barycenter, body_templates, "orbital barycenter")
            parent = state_value_by_id(indexed, ref_id(barycenter.get("barycenter")))
            if parent:
                require_solar_body_template(hab, parent, body_templates, "orbital parent")
                grandparent = state_value_by_id(indexed, ref_id(parent.get("barycenter")))
                if grandparent:
                    require_solar_body_template(hab, grandparent, body_templates, "orbital grandparent")


def hab_solar_mirror_bonus(
    indexed: IndexedState,
    hab: dict[str, Any],
    faction_id: int | None,
    tier: int,
) -> int:
    if faction_id is None or not (hab.get("habType") == "Base" or hab.get("habSite")):
        return 0
    body = state_value_by_id(indexed, ref_id(hab.get("barycenter"))) or {}
    rows = body.get("solarMirrorBonus") if isinstance(body.get("solarMirrorBonus"), list) else []
    for row in rows:
        if isinstance(row, dict) and ref_id(row.get("Key")) == faction_id:
            return int(as_float(row.get("Value"), 0.0)) * tier
    return 0


def hab_module_power(
    template: dict[str, Any],
    *,
    indexed: IndexedState | None = None,
    hab: dict[str, Any] | None = None,
    body_templates: dict[str, dict[str, Any]] | None = None,
    orbit_templates: dict[str, dict[str, Any]] | None = None,
) -> int:
    template_power = int(as_float(template.get("power"), 0.0))
    rules = hab_template_special_rules(template)
    if "Solar_Power_Variable_Output" in rules:
        if indexed is None or hab is None:
            raise SolarPowerDataError(
                "Solar_Power_Variable_Output requires indexed hab and location-template context; "
                "nominal module power is not a valid fallback."
            )
        multiplier = hab_natural_solar_multiplier(indexed, hab, body_templates or {}, orbit_templates or {})
        output = int(round(multiplier * as_float(template.get("power"), 0.0)))
        output += hab_solar_mirror_bonus(
            indexed,
            hab,
            ref_id(hab.get("faction")),
            int(as_float(template.get("tier"), 0.0)),
        )
        return min(output, int(MAX_SOLAR_POWER_MULTIPLIER * as_float(template.get("power"), 0.0)))
    if indexed is not None and hab is not None and body_templates:
        if "Cost_Scales_With_Gravity" in rules:
            faction = state_value_by_id(indexed, ref_id(hab.get("faction"))) or {}
            relative_energy = space_body_relative_energy_for_mining(
                indexed,
                hab_construction_surface_body(indexed, hab),
                faction,
                body_templates,
            )
            return int(template_power / 2.0 + round(template_power / 2.0 * relative_energy))
    return template_power


def hab_power_summary(
    records: list[dict[str, Any]],
    *,
    indexed: IndexedState | None = None,
    hab: dict[str, Any] | None = None,
    body_templates: dict[str, dict[str, Any]] | None = None,
    orbit_templates: dict[str, dict[str, Any]] | None = None,
    at_date: datetime | None = None,
) -> dict[str, int]:
    generated = 0
    consumed = 0
    for record in records:
        effective = get_effective_module_state(record, at_date)
        if not effective.get("operational"):
            continue
        template = effective.get("operationalTemplate") if isinstance(effective.get("operationalTemplate"), dict) else {}
        power = hab_module_power(
            template,
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
    if not orbit or not barycenter:
        return summary

    location_catalog = load_location_catalog()
    orbit_templates = location_catalog.orbit_templates
    location_templates = location_catalog.location_templates
    orbit_name = str(orbit.get("template") or "")
    body_name = str(barycenter.get("template") or "")
    orbit_template = orbit_templates.get(orbit_name)
    body_template = location_templates.get(body_name)
    if orbit_template is None:
        raise LocationCatalogError(f"Orbit template {orbit_name!r} is missing from the packaged location catalog")
    if body_template is None:
        raise LocationCatalogError(f"Natural-location template {body_name!r} is missing from the packaged location catalog")
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
    hab_module_templates = load_hab_module_catalog()
    location_catalog = load_location_catalog()
    body_templates = location_catalog.body_templates
    orbit_templates = location_catalog.orbit_templates
    runtime_catalogs = calculation_catalogs(indexed, "hab-ui")
    trait_templates = runtime_catalogs.traits
    effect_templates = runtime_catalogs.effects
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
            "power": hab_power_summary(
                records,
                indexed=indexed,
                hab=hab,
                body_templates=body_templates,
                orbit_templates=orbit_templates,
            ),
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
                    "power": hab_module_power(
                        record.get("template", {}),
                        indexed=indexed,
                        hab=hab,
                        body_templates=body_templates,
                        orbit_templates=orbit_templates,
                    ),
                    "templatePower": record.get("template", {}).get("power"),
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
    hab_module_templates = load_hab_module_catalog()
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


def resource_market_purchase_values(indexed: IndexedState) -> dict[str, float]:
    global_state = first_value(indexed, "TIGlobalValuesState") or {}
    values = global_state.get("resourceMarketValues") if isinstance(global_state.get("resourceMarketValues"), dict) else {}
    return {resource: as_float(values.get(resource), 0.0) for resource in WORLD_MARKET_RESOURCES}


def faction_is_active_human(indexed: IndexedState, faction: dict[str, Any]) -> bool:
    if faction.get("isAlien") or str(faction.get("templateName") or "") == "AlienCouncil":
        return False
    if faction.get("player"):
        return True
    metadata = first_value(indexed, "TIMetadataState") or {}
    player_faction_name = str(metadata.get("playerFactionName") or "")
    return player_faction_name in raw_name_values(faction)


def space_body_semi_major_axis_km(template: dict[str, Any]) -> float:
    semi_major_axis_km = as_float(template.get("semiMajorAxis_km"), 0.0)
    if semi_major_axis_km > 0.0:
        return semi_major_axis_km
    return as_float(template.get("semiMajorAxis_AU"), 0.0) * ASTRONOMICAL_UNIT_KM


def space_body_local_escape_velocity_mps(template: dict[str, Any], radius_km: float) -> float:
    mass_kg = as_float(template.get("mass_kg"), 0.0)
    if mass_kg <= 0.0 or radius_km <= 0.0:
        return 0.0
    return math.sqrt(2.0 * GRAVITATIONAL_CONSTANT * mass_kg / (radius_km * 1000.0))


def space_body_drag_velocity_penalty_kps(template: dict[str, Any]) -> float:
    return {
        "Massive": 30.0,
        "Thick": 15.0,
        "Standard": 0.5,
        "Thin": 0.05,
    }.get(str(template.get("atmosphere") or ""), 0.0)


def space_body_relative_energy_for_mining(
    indexed: IndexedState,
    body: dict[str, Any] | None,
    faction: dict[str, Any],
    body_templates: dict[str, dict[str, Any]],
) -> float:
    if not body:
        return 0.0
    template = space_body_template(body, body_templates)
    mean_radius_km = space_body_mean_radius_km(template)
    escape_mps = space_body_local_escape_velocity_mps(template, mean_radius_km)
    escape_mps += space_body_drag_velocity_penalty_kps(template) * 1000.0

    parent = state_value_by_id(indexed, ref_id(body.get("barycenter")))
    parent_template = space_body_template(parent, body_templates)
    body_orbit_km = space_body_semi_major_axis_km(template)
    if str(template.get("objectType") or "") in {"PlanetaryMoon", "AsteroidalMoon"}:
        if str(parent_template.get("dataName") or "") == "Earth" and faction_is_active_human(indexed, faction):
            parent_escape_mps = space_body_local_escape_velocity_mps(parent_template, body_orbit_km) / 2.0
            escape_velocity_kps = math.sqrt(escape_mps * escape_mps + parent_escape_mps * parent_escape_mps) / 1000.0
        else:
            parent_escape_mps = space_body_local_escape_velocity_mps(parent_template, body_orbit_km)
            grandparent = state_value_by_id(indexed, ref_id((parent or {}).get("barycenter")))
            grandparent_template = space_body_template(grandparent, body_templates)
            parent_orbit_km = space_body_semi_major_axis_km(parent_template)
            grandparent_escape_mps = space_body_local_escape_velocity_mps(grandparent_template, parent_orbit_km) / 2.0
            escape_velocity_kps = math.sqrt(
                escape_mps * escape_mps
                + parent_escape_mps * parent_escape_mps
                + grandparent_escape_mps * grandparent_escape_mps
            ) / 1000.0
    else:
        parent_escape_mps = space_body_local_escape_velocity_mps(parent_template, body_orbit_km) / 2.0
        escape_velocity_kps = math.sqrt(escape_mps * escape_mps + parent_escape_mps * parent_escape_mps) / 1000.0

    transfer_energy = 0.0
    if faction_is_active_human(indexed, faction) and str(parent_template.get("dataName") or "") != "Earth":
        transfer_energy = (natural_space_object_sun_distance_au(indexed, body, body_templates) or 0.0) * 10.0
    return (escape_velocity_kps * escape_velocity_kps / 2.0 + transfer_energy) * 0.005


def hab_construction_surface_body(indexed: IndexedState, hab: dict[str, Any]) -> dict[str, Any]:
    barycenter = hab_barycenter_state(indexed, hab)
    if barycenter.get("secondaryObject"):
        return state_value_by_id(indexed, ref_id(barycenter.get("secondaryObject"))) or {}
    return barycenter


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
    body_templates: dict[str, dict[str, Any]],
    orbit_templates: dict[str, dict[str, Any]],
    prior_record: dict[str, Any] | None = None,
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
        prior_record,
    )
    template_power = int(as_float(template.get("power"), 0.0))
    power = hab_module_power(
        template,
        indexed=indexed,
        hab=hab,
        body_templates=body_templates,
        orbit_templates=orbit_templates,
    )
    prior_template = prior_record.get("template", {}) if isinstance(prior_record, dict) else {}
    prior_power = hab_module_power(
        prior_template,
        indexed=indexed,
        hab=hab,
        body_templates=body_templates,
        orbit_templates=orbit_templates,
    ) if prior_template else 0
    power_change = power - prior_power
    construction = hab_module_construction_analysis(
        indexed,
        hab,
        records,
        faction,
        template,
        body_templates,
        orbit_templates,
        is_upgrade=prior_record is not None,
    )
    break_even = module_break_even_analysis(construction, monthly_delta, resource_market_purchase_values(indexed))
    mission_control = int(as_float(template.get("missionControl"), 0.0))
    prior_mission_control = int(as_float(prior_template.get("missionControl"), 0.0))
    mission_control_change = mission_control - prior_mission_control
    research_score = module_research_score(monthly_delta)
    project_score = module_project_score(monthly_delta)
    category_bonus_score = module_category_bonus_score(template)
    resource_score = module_resource_score(monthly_delta, scarcity_weights)
    return {
        "template": template.get("dataName"),
        "display": template_display(str(template.get("dataName")), template),
        "tier": int(as_float(template.get("tier"), 0.0)),
        "habType": template.get("habType") or "Any",
        "isUpgrade": prior_record is not None,
        "priorTemplate": prior_record.get("templateName") if isinstance(prior_record, dict) else None,
        "power": power,
        "templatePower": template_power,
        "powerChange": power_change,
        "projectedPowerAfterOne": projected_power.get("net", 0) + power_change,
        "missionControl": mission_control_change,
        "resultingMissionControl": mission_control,
        "onePerHab": bool(template.get("onePerHab")),
        "fitsCurrentProjectedPower": projected_power.get("net", 0) + power_change >= 0,
        "fitsCurrentMissionControl": mission_control_change >= 0 or mission_control_available + mission_control_change >= 0,
        "crew": int(as_float(template.get("crew"), 0.0)),
        "buildTime_Days": construction.get("constructionTime_Days"),
        "buildCostTemplateWeights": module_build_cost_map(template),
        "affordableByTemplateWeights": module_affordable_with_template_weights(template, faction),
        "construction": construction,
        "breakEven": break_even,
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
    hab_module_templates = load_hab_module_catalog()
    location_catalog = load_location_catalog()
    body_templates = location_catalog.body_templates
    orbit_templates = location_catalog.orbit_templates
    runtime_catalogs = calculation_catalogs(indexed, "hab-plan")
    effect_templates = runtime_catalogs.effects
    trait_templates = runtime_catalogs.traits
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
            body_templates,
            orbit_templates,
        )
        has_score = any(abs(as_float(value, 0.0)) > 0.0 for value in row.get("scores", {}).values())
        if not has_score and row["power"] <= 0 and row["missionControl"] <= 0:
            continue
        rows.append(clean_numbers(row, 6))
    return rows


def hab_module_upgrade_rows(
    indexed: IndexedState,
    templates_dir: Path | None,
    hab: dict[str, Any],
    records: list[dict[str, Any]],
    faction_id: int,
    faction: dict[str, Any],
    projected_power: dict[str, int],
    mission_control_available: float,
    topbar: dict[str, Any],
) -> list[dict[str, Any]]:
    hab_module_templates = load_hab_module_catalog()
    location_catalog = load_location_catalog()
    body_templates = location_catalog.body_templates
    orbit_templates = location_catalog.orbit_templates
    runtime_catalogs = calculation_catalogs(indexed, "hab-plan")
    effect_templates = runtime_catalogs.effects
    trait_templates = runtime_catalogs.traits
    _, councilor_by_id = councilor_summary_maps(indexed, trait_templates)
    effect_contexts = faction_effect_contexts(indexed, faction_id)
    mining_rate = faction_mining_rate(indexed, faction)
    scarcity_weights = resource_scarcity_weights(topbar)
    templates_by_prior: dict[str, list[dict[str, Any]]] = {}
    for template in hab_module_templates.values():
        prior_name = template.get("upgradesFromName")
        if prior_name:
            templates_by_prior.setdefault(str(prior_name), []).append(template)

    rows: list[dict[str, Any]] = []
    current_tier = int(as_float(hab.get("tier"), 0.0))
    target_tier = min(max(current_tier + 1, 1), 3)
    for record in records:
        if not hab_module_active_record(record):
            continue
        for template in templates_by_prior.get(str(record.get("templateName") or ""), []):
            module_counts = hab_module_counts(records)
            prior_name = str(record.get("templateName") or "")
            module_counts[prior_name] = max(module_counts.get(prior_name, 0) - 1, 0)
            reasons = module_unmet_requirements(
                indexed,
                template,
                hab,
                faction,
                target_tier,
                module_counts,
                body_templates,
            )
            reasons = [reason for reason in reasons if reason != "core module"]
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
                body_templates,
                orbit_templates,
                prior_record=record,
            )
            row["sectorNum"] = record.get("sectorNum")
            row["slot"] = record.get("slot")
            row["isCoreUpgrade"] = bool(template.get("coreModule"))
            rows.append(clean_numbers(row, 6))
    return rows


def sorted_candidates(candidates: list[dict[str, Any]], focus: str, top: int) -> list[dict[str, Any]]:
    return sorted(
        candidates,
        key=lambda row: (
            not candidate_affordable(row),
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
        [
            candidate
            for candidate in candidates
            if as_float(candidate.get("powerChange") if candidate.get("isUpgrade") else candidate.get("power"), 0.0) > 0.0
        ],
        key=lambda row: (
            not candidate_affordable(row),
            -as_float(row.get("powerChange") if row.get("isUpgrade") else row.get("power"), 0.0),
            -int(as_float(row.get("tier"), 0.0)),
            str(row.get("display") or row.get("template")),
        ),
    )[:top]


def candidate_affordable(row: dict[str, Any]) -> bool:
    construction = row.get("construction") if isinstance(row.get("construction"), dict) else {}
    if "affordableByCurrentStockpile" in construction:
        return bool(construction.get("affordableByCurrentStockpile"))
    return bool(row.get("affordableByTemplateWeights", True))


def payback_candidates(candidates: list[dict[str, Any]], top: int) -> list[dict[str, Any]]:
    return sorted(
        [
            candidate
            for candidate in candidates
            if (candidate.get("breakEven") or {}).get("breakEvenFromStart_months") is not None
        ],
        key=lambda row: (
            not candidate_affordable(row),
            as_float((row.get("breakEven") or {}).get("breakEvenFromStart_months"), float("inf")),
            -as_float((row.get("breakEven") or {}).get("monthlyNetMarketEquivalentMoney"), 0.0),
            str(row.get("display") or row.get("template")),
        ),
    )[:top]


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
            "constructionEach": candidate.get("construction"),
            "breakEvenEach": candidate.get("breakEven"),
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
    hab_module_templates = load_hab_module_catalog()
    location_catalog = load_location_catalog()
    body_templates = location_catalog.body_templates
    orbit_templates = location_catalog.orbit_templates
    records = hab_module_records(indexed, hab, hab_module_templates)
    slots = hab_slot_summary(records)
    upgrade = hab_upgrade_info(records)
    current_tier = int(as_float(hab.get("tier"), 0.0)) or None
    target_tier = int(as_float(upgrade.get("targetTier"), 0.0)) or current_tier or 1
    planned_slots = hab_planned_empty_slots(slots, upgrade, current_tier)
    projected_power = hab_projected_power_summary(
        records,
        indexed=indexed,
        hab=hab,
        body_templates=body_templates,
        orbit_templates=orbit_templates,
    )
    mc_available = mission_control_available_for_planning(topbar)
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
    upgrade_candidates = hab_module_upgrade_rows(
        indexed,
        templates_dir,
        hab,
        records,
        faction_id,
        faction,
        projected_power,
        mc_available,
        topbar,
    )
    annotate_candidate_opportunity_costs(candidates)
    annotate_candidate_opportunity_costs(upgrade_candidates)
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
            "active": hab_power_summary(
                records,
                indexed=indexed,
                hab=hab,
                body_templates=body_templates,
                orbit_templates=orbit_templates,
            ),
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
                "buildCost": (record.get("state") or {}).get("buildCost"),
                "baseBuildDuration_days": (record.get("state") or {}).get("baseBuildDuration_days"),
                "appliedBuildConstructionBonus": (record.get("state") or {}).get("appliedBuildConstructionBonus"),
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
            "topPayback": payback_candidates(candidates, top),
        },
        "upgradeSummary": {
            "count": len(upgrade_candidates),
            "tierUpgradeCandidate": next((row for row in upgrade_candidates if row.get("isCoreUpgrade")), None),
            "topPayback": payback_candidates(upgrade_candidates, top),
            "topResources": sorted_candidates(upgrade_candidates, "resources", top),
            "topPower": power_candidates(upgrade_candidates, top),
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
                "construction.materials applies module mass, gravity scaling, solar-mirror distance scaling, irradiated-location extra metals, helium-3 fissiles substitution, and the two-thirds upgrade discount.",
                "construction.constructionTime_Days includes active hab construction-speed modifiers and the in-progress core completion minimum when applicable.",
                "breakEven values use current market purchase prices for Money and purchasable space resources; MC, research, projects, influence, operations, strategic unlocks, boost substitution, and Earth transfer time are excluded.",
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
        template = project_templates.get(name)
        if not isinstance(template, dict):
            raise CalculationDependencyError(
                CalculationDependency(
                    kind="research-project",
                    name=name,
                    context="project-analysis.candidates",
                    scenario=None,
                    reason="save candidate is absent from the packaged research catalog",
                )
            )
        if template.get("disable"):
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

    location_catalog = load_location_catalog()
    body_templates = location_catalog.body_templates
    orbit_templates = location_catalog.orbit_templates
    runtime_catalogs = calculation_catalogs(indexed, "project-analysis")
    effect_templates = runtime_catalogs.effects
    trait_templates = runtime_catalogs.traits
    _, councilor_by_id = councilor_summary_maps(indexed, trait_templates)
    effect_contexts = faction_effect_contexts(indexed, faction_id)
    mining_rate = faction_mining_rate(indexed, faction)
    scarcity_weights = resource_scarcity_weights(topbar)
    mc_available = mission_control_available_for_planning(topbar)
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
            projected_power = hab_projected_power_summary(
                records,
                indexed=indexed,
                hab=hab,
                body_templates=body_templates,
                orbit_templates=orbit_templates,
            )
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
                body_templates,
                orbit_templates,
            )
            row["hab"] = {"id": hab_id, "display": hab.get("displayName"), "plannedEmptySlots": hab_planned_slots}
            row["location"] = hab_location_summary(indexed, templates_dir, hab)
            rows.append(clean_numbers(row, 6))
            if row.get("fitsCurrentProjectedPower"):
                power_fit_slots += hab_planned_slots

        rows.sort(
            key=lambda row: (
                not candidate_affordable(row),
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
    research_templates = load_research_templates(indexed, templates_dir)
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
        records = hab_module_records(indexed, hab, hab_module_templates)
        raw_research_month = 0.0
        admin_modifier = 1.0
        module_counts: dict[str, int] = {}
        for module in active_modules:
            template_name = module.get("templateName")
            template = hab_module_templates.get(template_name, {})
            module_counts[str(template_name)] = module_counts.get(str(template_name), 0) + 1
            raw_research_month += as_float(template.get("incomeResearch_month"), 0.0)
            special_rules = template.get("specialRules") if isinstance(template.get("specialRules"), list) else []
            if "Efficiency" in special_rules:
                admin_modifier *= 1.0 + as_float(template.get("specialRulesValue"), 0.0)

        hab_mission_control = sum(max(hab_module_current_mission_control(record), 0) for record in records)
        total_mission_control += hab_mission_control
        adviser_bonus = nation_adviser_science_bonus(hab, councilor_by_id)
        research_month = raw_research_month * (1.0 + adviser_bonus) * admin_modifier
        total_research_month += research_month
        if research_month or hab_mission_control:
            details.append(
                {
                    "id": hab_id,
                    "display": hab.get("displayName"),
                    "rawResearchMonth": raw_research_month,
                    "adminModifier": admin_modifier,
                    "adviserBonus": adviser_bonus,
                    "researchMonth": research_month,
                    "researchDay": research_month * 12.0 / DAYS_PER_YEAR,
                    "missionControl": hab_mission_control,
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


def command_research(save_path: Path, templates_dir: Path | None, args: argparse.Namespace) -> None:
    data = load_save(save_path)
    indexed = build_index(data)
    result = calculate_research_breakdown(indexed, templates_dir, args.faction, include_details=args.details)
    print_json(result, compact=args.compact)


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
        if not isinstance(template, dict):
            raise CalculationDependencyError(
                CalculationDependency(
                    kind="research-project",
                    name=name,
                    context="research-plan.available-projects",
                    scenario=None,
                    reason="save candidate is absent from the packaged research catalog",
                )
            )
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
    research_templates = load_research_templates(indexed, templates_dir)
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
            "templatesDir": template_source_value(templates_dir),
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


def ship_plan_part_unlocked(
    template: dict[str, Any],
    faction: dict[str, Any],
    include_obsolete: bool = False,
) -> bool:
    name = str(template.get("dataName") or "")
    if not name or template.get("disable"):
        return False
    obsolete = faction.get("obsoletedShipParts") if isinstance(faction.get("obsoletedShipParts"), list) else []
    if not include_obsolete and name in obsolete:
        return False
    required_project = template.get("requiredProjectName")
    if not required_project:
        return True
    finished = faction.get("finishedProjectNames") if isinstance(faction.get("finishedProjectNames"), list) else []
    return str(required_project) in finished


def ship_plan_materials(template: dict[str, Any], key: str = "weightedBuildMaterials") -> dict[str, float]:
    values = template.get(key)
    if not isinstance(values, dict):
        return {}
    return {
        str(resource): as_float(amount, 0.0)
        for resource, amount in values.items()
        if as_float(amount, 0.0) != 0.0
    }


def ship_plan_hull_row(template: dict[str, Any]) -> dict[str, Any]:
    return clean_numbers(
        {
            "template": template.get("dataName"),
            "display": template.get("friendlyName") or template.get("displayName") or template.get("dataName"),
            "constructionTier": template.get("consTier"),
            "massTons": template.get("mass_tons"),
            "structuralIntegrity": template.get("structuralIntegrity"),
            "crew": template.get("crew"),
            "missionControl": template.get("missionControl"),
            "monthlyMoney": template.get("monthlyIncome_Money"),
            "baseConstructionDays": template.get("baseConstructionTime_days"),
            "slots": {
                "noseHardpoints": template.get("noseHardpoints"),
                "hullHardpoints": template.get("hullHardpoints"),
                "utility": template.get("internalModules"),
            },
            "requiredProject": template.get("requiredProjectName"),
            "buildMaterials": ship_plan_materials(template),
        }
    )


def ship_plan_drive_row(template: dict[str, Any]) -> dict[str, Any]:
    thrust = as_float(template.get("thrust_N"), 0.0)
    exhaust_velocity = as_float(template.get("EV_kps"), 0.0)
    return clean_numbers(
        {
            "template": template.get("dataName"),
            "display": template.get("friendlyName") or template.get("dataName"),
            "classification": template.get("driveClassification"),
            "thrusters": template.get("thrusters"),
            "thrustN": thrust,
            "exhaustVelocityKps": exhaust_velocity,
            "powerRequirementGW": ship_plan_drive_power_requirement_gw(template),
            "requiredPowerPlantClass": template.get("requiredPowerPlant"),
            "cooling": template.get("cooling"),
            "powerGeneration": template.get("powerGen"),
            "flatMassTons": template.get("flatMass_tons"),
            "propellant": template.get("propellant"),
            "perTankPropellantMaterials": ship_plan_materials(template, "perTankPropellantMaterials"),
            "requiredProject": template.get("requiredProjectName"),
            "proxyScores": {
                "thrust": thrust,
                "exhaustVelocity": exhaust_velocity,
                "balanced": math.sqrt(max(thrust, 0.0)) * exhaust_velocity,
            },
        }
    )


def ship_plan_drive_thrust_power_gw(template: dict[str, Any]) -> float:
    return as_float(template.get("thrust_N"), 0.0) * as_float(template.get("EV_kps"), 0.0) * 0.5 / 1_000_000.0


def ship_plan_drive_power_requirement_gw(template: dict[str, Any]) -> float:
    if str(template.get("driveClassification") or "") in SHIP_PLAN_SELF_POWERED_DRIVE_CLASSES:
        return 0.0
    efficiency = as_float(template.get("efficiency"), 0.0)
    return ship_plan_drive_thrust_power_gw(template) / efficiency if efficiency > 0.0 else 0.0


def ship_plan_power_plant_row(template: dict[str, Any]) -> dict[str, Any]:
    return clean_numbers(
        {
            "template": template.get("dataName"),
            "display": template.get("friendlyName") or template.get("dataName"),
            "powerPlantClass": template.get("powerPlantClass"),
            "maxOutputGW": template.get("maxOutput_GW"),
            "specificMassTonsPerGW": template.get("specificPower_tGW"),
            "efficiency": template.get("efficiency"),
            "crew": template.get("crew"),
            "requiredProject": template.get("requiredProjectName"),
            "buildMaterials": ship_plan_materials(template),
        }
    )


def ship_plan_power_plant_class_compatible(required_class: str, plant_class: str) -> bool:
    if required_class in {"", "Any_General"} or required_class == plant_class:
        return True
    if required_class == "Any_Magnetic_Confinement_Fusion":
        return plant_class in {
            "Any_Magnetic_Confinement_Fusion",
            "Toroid_Magnetic_Confinement_Fusion",
            "Mirrored_Magnetic_Confinement_Fusion",
            "Hybrid_Confinement_Fusion",
        }
    return plant_class == "Molten_Salt_Core_Fission" and required_class in {
        "Solid_Core_Fission",
        "Liquid_Core_Fission",
    }


def ship_plan_compatible_power_plants(
    drive: dict[str, Any],
    power_plants: Iterable[dict[str, Any]],
    top: int = 3,
) -> list[dict[str, Any]]:
    required_class = str(drive.get("requiredPowerPlantClass") or "")
    required_output = as_float(drive.get("powerRequirementGW"), 0.0)
    compatible = [
        plant
        for plant in power_plants
        if (
            ship_plan_power_plant_class_compatible(
                required_class,
                str(plant.get("powerPlantClass") or ""),
            )
        )
        and as_float(plant.get("maxOutputGW"), 0.0) >= required_output
    ]
    return sorted(
        compatible,
        key=lambda plant: (
            as_float(plant.get("specificMassTonsPerGW"), 1_000_000_000.0),
            -as_float(plant.get("maxOutputGW"), 0.0),
            str(plant.get("display") or plant.get("template")),
        ),
    )[: max(0, top)]


def ship_plan_drive_goal_views(
    drives: Iterable[dict[str, Any]],
    power_plants: Iterable[dict[str, Any]],
    top: int,
) -> dict[str, list[dict[str, Any]]]:
    drive_rows = list(drives)
    plant_rows = list(power_plants)
    result: dict[str, list[dict[str, Any]]] = {}
    for axis in ("thrust", "exhaustVelocity", "balanced"):
        rows = sorted(
            drive_rows,
            key=lambda row: (
                -as_float((row.get("proxyScores") or {}).get(axis), 0.0),
                str(row.get("display") or row.get("template")),
            ),
        )[: max(0, top)]
        result[axis] = [
            {
                **row,
                "compatiblePowerPlants": ship_plan_compatible_power_plants(row, plant_rows),
            }
            for row in rows
            if as_float((row.get("proxyScores") or {}).get(axis), 0.0) > 0.0
        ]
    return result


def ship_plan_weapon_row(template: dict[str, Any], kind: str) -> dict[str, Any] | None:
    mount = str(template.get("mount") or "")
    mount_summary = SHIP_PLAN_MOUNT_SLOTS.get(mount)
    if mount_summary is None:
        return None
    salvo_shots = max(1.0, as_float(template.get("salvo_shots"), 1.0))
    damage = max(
        as_float(template.get("flatDamage_MJ"), 0.0),
        as_float(template.get("expectedDamage_MJ"), 0.0),
        as_float(template.get("shotPower_MJ"), 0.0),
    )
    cooldown = as_float(template.get("cooldown_s"), 0.0)
    return clean_numbers(
        {
            "template": template.get("dataName"),
            "display": template.get("friendlyName") or template.get("displayName") or template.get("dataName"),
            "kind": kind,
            "mount": mount,
            "mountLocation": mount_summary[0],
            "mountSlots": mount_summary[1],
            "attackMode": bool(template.get("attackMode")),
            "defenseMode": bool(template.get("defenseMode")),
            "dedicatedPointDefense": bool(template.get("defenseMode")) and not bool(template.get("attackMode")),
            "massTons": template.get("baseWeaponMass_tons"),
            "crew": template.get("crew"),
            "targetingRangeKm": template.get("targetingRange_km"),
            "cooldownSeconds": cooldown,
            "salvoShots": salvo_shots,
            "damagePerShotMJProxy": damage,
            "damagePerCooldownMJPerSecondProxy": damage * salvo_shots / cooldown if cooldown > 0.0 else 0.0,
            "magazine": template.get("magazine"),
            "projectileAccelerationG": template.get("acceleration_g"),
            "projectileDeltaVKps": template.get("deltaV_kps"),
            "muzzleVelocityKps": template.get("muzzleVelocity_kps"),
            "requiredProject": template.get("requiredProjectName"),
            "buildMaterials": ship_plan_materials(template),
        }
    )


def ship_plan_weapon_goal_views(weapons: Iterable[dict[str, Any]], top: int) -> dict[str, list[dict[str, Any]]]:
    weapon_rows = list(weapons)
    views = {
        "dedicatedPointDefense": [
            row
            for row in sorted(
                weapon_rows,
                key=lambda row: (
                    not bool(row.get("dedicatedPointDefense")),
                    -as_float(row.get("targetingRangeKm"), 0.0),
                    as_float(row.get("massTons"), 0.0),
                    str(row.get("display") or row.get("template")),
                ),
            )
            if row.get("dedicatedPointDefense")
        ][: max(0, top)],
        "damageRateProxy": sorted(
            [row for row in weapon_rows if row.get("attackMode")],
            key=lambda row: (
                -as_float(row.get("damagePerCooldownMJPerSecondProxy"), 0.0),
                str(row.get("display") or row.get("template")),
            ),
        )[: max(0, top)],
        "range": sorted(
            weapon_rows,
            key=lambda row: (
                -as_float(row.get("targetingRangeKm"), 0.0),
                str(row.get("display") or row.get("template")),
            ),
        )[: max(0, top)],
        "missileManeuver": sorted(
            [row for row in weapon_rows if row.get("kind") == "missile"],
            key=lambda row: (
                -as_float(row.get("projectileAccelerationG"), 0.0),
                -as_float(row.get("projectileDeltaVKps"), 0.0),
                str(row.get("display") or row.get("template")),
            ),
        )[: max(0, top)],
    }
    return views


def ship_plan_utility_role_tags(template: dict[str, Any]) -> list[str]:
    rules = [str(rule) for rule in template.get("specialModuleRules") if rule] if isinstance(template.get("specialModuleRules"), list) else []
    text = " ".join([str(template.get("dataName") or ""), *rules]).casefold()
    tags = {"balanced"}
    if any(token in text for token in ("magazine", "targeting", "ecm", "repair", "spiker", "laserengine")):
        tags.update({"combat", "intercept"})
    if any(token in text for token in ("thrust", "hydron", "refuel", "aerobraking", "scoop", "isru")):
        tags.update({"intercept", "transfer"})
    if "found" in text:
        tags.add("colony")
    if "assault" in text:
        tags.add("assault")
    if any(token in text for token in ("science", "prospector")):
        tags.add("science")
    return sorted(tags)


def ship_plan_utility_row(template: dict[str, Any]) -> dict[str, Any]:
    return clean_numbers(
        {
            "template": template.get("dataName"),
            "display": template.get("friendlyName") or template.get("dataName"),
            "massTons": template.get("mass_tons"),
            "crew": template.get("crew"),
            "powerRequirementMW": template.get("powerRequirement_MW"),
            "minimumConstructionTier": template.get("minConsTier"),
            "rules": template.get("specialModuleRules") or [],
            "specialValue": template.get("specialModuleValue"),
            "roleTags": ship_plan_utility_role_tags(template),
            "requiredProject": template.get("requiredProjectName"),
            "buildMaterials": ship_plan_materials(template),
        }
    )


def ship_plan_generic_row(template: dict[str, Any], fields: Iterable[tuple[str, str]]) -> dict[str, Any]:
    row = {
        "template": template.get("dataName"),
        "display": template.get("friendlyName") or template.get("displayName") or template.get("dataName"),
        "requiredProject": template.get("requiredProjectName"),
        "buildMaterials": ship_plan_materials(template),
    }
    for output_name, template_name in fields:
        row[output_name] = template.get(template_name)
    return clean_numbers(row)


def ship_plan_add_scaled_materials(
    destination: dict[str, float],
    materials: dict[str, Any] | None,
    multiplier: float,
) -> None:
    if not isinstance(materials, dict):
        return
    for resource, amount in materials.items():
        value = as_float(amount, 0.0) * multiplier
        if value:
            destination[str(resource)] = destination.get(str(resource), 0.0) + value


def ship_plan_clean_resources(resources: dict[str, float]) -> dict[str, float]:
    return {
        resource: value
        for resource, value in sorted(resources.items())
        if abs(value) > 1e-9
    }


def ship_plan_utility_rule_value(
    template: dict[str, Any],
    rule: str,
    default: float,
) -> float:
    rules = template.get("specialModuleRules")
    if not isinstance(rules, list) or not rules or rules[0] != rule:
        return default
    return as_float(template.get("specialModuleValue"), default)


def ship_plan_weapon_mass_tons(template: dict[str, Any], magazine_multiplier: float) -> float:
    mass = as_float(template.get("baseWeaponMass_tons"), 0.0)
    if template.get("_shipPlanKind") in {"gun", "magnetic", "missile", "plasma"}:
        mass += (
            (1.0 + magazine_multiplier)
            * as_float(template.get("magazine"), 0.0)
            * as_float(template.get("ammoMass_kg"), 0.0)
            / 1000.0
        )
    return mass


def ship_plan_weapon_cost(
    template: dict[str, Any],
    magazine_multiplier: float,
) -> dict[str, float]:
    result: dict[str, float] = {}
    scale = DEFAULT_GLOBAL_CONFIG["spaceResourceToTons"]
    kind = template.get("_shipPlanKind")
    base_mass = as_float(template.get("baseWeaponMass_tons"), 0.0)
    magazine_mass = (
        (1.0 + magazine_multiplier)
        * as_float(template.get("magazine"), 0.0)
        * as_float(template.get("ammoMass_kg"), 0.0)
        / 1000.0
    )
    if kind == "plasma":
        ship_plan_add_scaled_materials(result, template.get("weightedBuildMaterials"), (base_mass + magazine_mass) * scale)
    else:
        ship_plan_add_scaled_materials(result, template.get("weightedBuildMaterials"), base_mass * scale)
        if kind in {"gun", "magnetic", "missile"}:
            ship_plan_add_scaled_materials(result, template.get("ammoMaterials"), magazine_mass * scale)
    return result


def ship_plan_weapon_energy_gj(template: dict[str, Any], bonus_power_gj: float = 0.0) -> float:
    kind = template.get("_shipPlanKind")
    efficiency = as_float(template.get("efficiency"), 1.0)
    if efficiency <= 0.0:
        return 0.0
    if kind == "magnetic":
        return (
            0.5
            * as_float(template.get("ammoMass_kg"), 0.0)
            * (as_float(template.get("muzzleVelocity_kps"), 0.0) * 1000.0) ** 2
            / efficiency
            * 1e-9
        )
    if kind == "plasma":
        return (
            as_float(template.get("chargingEnergy_GJ"), 0.0)
            + 0.5
            * as_float(template.get("warheadMass_kg"), 0.0)
            * (as_float(template.get("muzzleVelocity_kps"), 0.0) * 1000.0) ** 2
            * 1e-9
        ) / efficiency
    if kind in {"laser", "particle"}:
        return (as_float(template.get("shotPower_MJ"), 0.0) + bonus_power_gj) / efficiency / 1000.0
    return 0.0


def ship_plan_armor_mass_tons(
    template: dict[str, Any],
    armor_points: float,
    hull_length_m: float,
    hull_width_m: float,
    lateral_armor_depth_m: float,
    *,
    lateral: bool,
    cinematic_scale: bool,
) -> float:
    density = as_float(template.get("density_kgm3"), 0.0)
    heat_of_vaporization = as_float(template.get("heatofVaporization_MJkg"), 0.0)
    if density <= 0.0 or heat_of_vaporization <= 0.0 or armor_points <= 0.0:
        return 0.0
    plate_thickness_m = (20.0 / heat_of_vaporization) / density / 0.005
    outer_radius_m = (hull_width_m + 2.0 * lateral_armor_depth_m) / 2.0
    outer_area_m2 = math.pi * outer_radius_m**2
    if lateral:
        original_volume_m3 = math.pi * (hull_width_m / 2.0) ** 2 * hull_length_m
        armor_volume_m3 = outer_area_m2 * hull_length_m - original_volume_m3
        armor_volume_m3 *= 0.75 if cinematic_scale else 0.5
    else:
        armor_volume_m3 = plate_thickness_m * armor_points * outer_area_m2
        if not cinematic_scale:
            armor_volume_m3 *= 3.0
    return max(0.0, armor_volume_m3 * density / 1000.0)


def ship_plan_drive_open_cycle(
    drive: dict[str, Any],
    drive_templates: dict[str, dict[str, Any]],
) -> bool:
    cooling = str(drive.get("cooling") or "")
    if cooling == "Open":
        return True
    if cooling != "Calc":
        return False
    classification = str(drive.get("driveClassification") or "")
    if classification in {"Fission_Pulse", "Fusion_Pulse"}:
        return True
    name = str(drive.get("dataName") or "")
    single_name = f"{name[:-1]}1" if name and name[-1:].isdigit() else name
    single = drive_templates.get(single_name, drive)
    exhaust_velocity = as_float(single.get("EV_kps"), 0.0) * 1000.0
    return exhaust_velocity > 0.0 and as_float(single.get("thrust_N"), 0.0) / exhaust_velocity >= 3.0


def ship_plan_shipyard_times(
    indexed: IndexedState,
    faction_id: int,
    hull: dict[str, Any],
    effect_templates: dict[str, dict[str, Any]],
    shipyard_templates: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    effect_contexts = faction_effect_contexts(indexed, faction_id)
    speed = scenario_float(indexed, "shipConstructionSpeedPlayer", 1.0)
    settings_modifier = 1.0 / speed if speed > 0.0 else 1.0
    base_days = as_float(hull.get("baseConstructionTime_days"), 0.0)
    hull_tier = int(as_float(hull.get("consTier"), 0.0))

    def with_effects(days: float) -> float:
        return apply_effect_modifiers(effect_contexts, effect_templates, "ShipConstructionTime", days)

    by_tier: dict[str, Any] = {}
    for tier, fallback in SHIP_PLAN_SHIPYARD_TIERS.items():
        shipyard = shipyard_templates.get(str(fallback["template"]), fallback)
        tier_delta = tier - hull_tier
        if tier_delta > 0:
            yard_modifier = as_float(shipyard.get("constructionTimeModifier"), 1.0) ** tier_delta
        elif tier_delta < 0:
            yard_modifier = DEFAULT_GLOBAL_CONFIG["smallShipyardPenaltyPowerPerTier"] ** (-tier_delta)
        else:
            yard_modifier = 1.0
        by_tier[str(tier)] = {
            "shipyard": fallback["template"],
            "days": with_effects(base_days * yard_modifier * settings_modifier),
        }
    return {
        "withoutShipyardDays": with_effects(base_days * settings_modifier),
        "byShipyardTier": by_tier,
        "settingsModifier": settings_modifier,
        "effectNames": effect_contexts.get("ShipConstructionTime", []),
    }


def ship_plan_simulation_catalogs(indexed: IndexedState) -> dict[str, dict[str, dict[str, Any]]]:
    catalogs = calculation_catalogs(indexed, "ship-plan").ship_simulation_catalogs
    return {**catalogs, "shipyards": load_hab_module_catalog()}


def simulate_ship_design(
    indexed: IndexedState,
    faction_id: int,
    faction: dict[str, Any],
    design: dict[str, Any],
    catalogs: dict[str, dict[str, dict[str, Any]]],
) -> dict[str, Any]:
    hull = catalogs["hulls"].get(str(design.get("hullName") or ""))
    drive = catalogs["drives"].get(str(design.get("driveName") or ""))
    power_plant = catalogs["powerPlants"].get(str(design.get("powerPlantName") or ""))
    radiator = catalogs["radiators"].get(str(design.get("radiatorName") or ""))
    utility_entries = design.get("moduleTemplateEntries") if isinstance(design.get("moduleTemplateEntries"), list) else []
    weapon_entries = [
        *(design.get("hullWeaponTemplateEntries") if isinstance(design.get("hullWeaponTemplateEntries"), list) else []),
        *(design.get("noseWeaponTemplateEntries") if isinstance(design.get("noseWeaponTemplateEntries"), list) else []),
    ]
    utilities = [
        catalogs["utilities"].get(str(entry.get("moduleName") or ""))
        for entry in utility_entries
        if isinstance(entry, dict)
    ]
    weapons = [
        catalogs["weapons"].get(str(entry.get("moduleName") or ""))
        for entry in weapon_entries
        if isinstance(entry, dict)
    ]
    armor_facings = {
        facing: design.get(f"{facing}Armor") if isinstance(design.get(f"{facing}Armor"), dict) else {}
        for facing in ("nose", "lateral", "tail")
    }
    armor_templates = {
        facing: catalogs["armors"].get(str(entry.get("materialName") or ""))
        for facing, entry in armor_facings.items()
    }
    missing_templates = [
        name
        for name, template in (
            (design.get("hullName"), hull),
            (design.get("driveName"), drive),
            (design.get("powerPlantName"), power_plant),
            (design.get("radiatorName"), radiator),
            *(
                (entry.get("moduleName"), template)
                for entry, template in zip(utility_entries, utilities)
                if isinstance(entry, dict)
            ),
            *(
                (entry.get("moduleName"), template)
                for entry, template in zip(weapon_entries, weapons)
                if isinstance(entry, dict)
            ),
            *(
                (entry.get("materialName"), armor_templates[facing])
                for facing, entry in armor_facings.items()
                if as_float(entry.get("armorValue"), 0.0) > 0.0
            ),
        )
        if name and str(name) != "Empty" and template is None
    ]
    if not all((hull, drive, power_plant, radiator)) or missing_templates:
        return {
            "complete": False,
            "missingTemplates": sorted({str(name) for name in missing_templates}),
        }

    utilities = [template for template in utilities if template]
    weapons = [template for template in weapons if template]
    crew = int(
        as_float(hull.get("crew"), 0.0)
        + as_float(drive.get("crew"), 0.0)
        + as_float(power_plant.get("crew"), 0.0)
        + as_float(radiator.get("crew"), 0.0)
        + sum(as_float(template.get("crew"), 0.0) for template in utilities)
        + sum(as_float(template.get("crew"), 0.0) for template in weapons)
    )
    magazine_multiplier = sum(
        as_float(template.get("specialModuleValue"), 0.0)
        for template in utilities
        if "Magazine" in (template.get("specialModuleRules") or [])
    )
    thrust_multiplier = math.prod(
        value
        for template in utilities
        for value in [ship_plan_utility_rule_value(template, "ThrustMultiplier", 1.0)]
        if value != 0.0
    )
    exhaust_velocity_multiplier = math.prod(
        value
        for template in utilities
        for value in [ship_plan_utility_rule_value(template, "EVMultiplier", 1.0)]
        if value != 0.0
    )
    laser_bonus_power_mj = sum(ship_plan_utility_rule_value(template, "LaserPowerBonus", 0.0) for template in utilities)
    particle_bonus_power_mj = sum(
        ship_plan_utility_rule_value(template, "ParticleBeamPowerBonus", 0.0)
        for template in utilities
    )
    weapon_energy_gj = []
    for template in weapons:
        bonus_power_mj = 0.0
        if template.get("_shipPlanKind") == "laser":
            bonus_power_mj = laser_bonus_power_mj * (1.0 if template.get("attackMode") else 0.5)
        elif template.get("_shipPlanKind") == "particle":
            bonus_power_mj = particle_bonus_power_mj * (1.0 if template.get("attackMode") else 0.5)
        weapon_energy_gj.append(ship_plan_weapon_energy_gj(template, bonus_power_mj / 1000.0))

    required_systems_power_gw = (
        crew * 5e-6
        + as_float(hull.get("consTier"), 0.0) * 0.005
        + sum(as_float(template.get("powerRequirement_MW"), 0.0) / 1000.0 for template in utilities)
    ) * 1.1
    required_weapons_power_generation_gw = sum(
        energy
        / (
            as_float(template.get("intraSalvoCooldown_s"), 0.0)
            if as_float(template.get("salvo_shots"), 1.0) != 1.0
            else as_float(template.get("cooldown_s"), 0.0)
        )
        for template, energy in zip(weapons, weapon_energy_gj)
        if energy > 0.0
        and (
            (
                as_float(template.get("intraSalvoCooldown_s"), 0.0)
                if as_float(template.get("salvo_shots"), 1.0) != 1.0
                else as_float(template.get("cooldown_s"), 0.0)
            )
            > 0.0
        )
    )
    thrust_power_gw = ship_plan_drive_thrust_power_gw(drive)
    drive_power_requirement_gw = ship_plan_drive_power_requirement_gw(drive)
    power_plant_efficiency = as_float(power_plant.get("efficiency"), 1.0)
    ship_power_requirement_gw = drive_power_requirement_gw + (
        required_systems_power_gw + required_weapons_power_generation_gw
    ) / power_plant_efficiency
    open_cycle_cooling = ship_plan_drive_open_cycle(drive, catalogs["drives"])
    waste_heat_gw = (
        required_systems_power_gw
        + required_weapons_power_generation_gw
        + (0.0 if open_cycle_cooling else drive_power_requirement_gw)
    ) * (1.0 - power_plant_efficiency)

    drive_mass_tons = as_float(drive.get("flatMass_tons"), 0.0) + thrust_power_gw * as_float(
        drive.get("specificPower_kgMW"), 0.0
    )
    power_plant_mass_tons = max(1.0, as_float(power_plant.get("specificPower_tGW"), 0.0) * ship_power_requirement_gw)
    radiator_mass_tons = (
        waste_heat_gw * 1_000_000.0 / as_float(radiator.get("specificPower_2s_KWkg"), 1.0) / 1000.0
    )
    hull_length_m = as_float(hull.get("length_m"), 0.0)
    hull_width_m = as_float(hull.get("width_m"), 0.0)
    lateral_armor = armor_templates["lateral"]
    lateral_armor_value = as_float(armor_facings["lateral"].get("armorValue"), 0.0)
    lateral_depth_m = 0.0
    if lateral_armor and lateral_armor_value > 0.0:
        lateral_depth_m = (
            (20.0 / as_float(lateral_armor.get("heatofVaporization_MJkg"), 1.0))
            / as_float(lateral_armor.get("density_kgm3"), 1.0)
            / 0.005
            * lateral_armor_value
        )
    cinematic_scale = bool(scenario_customizations(indexed).get("cinematicCombatRealismScale"))
    armor_masses = {
        facing: ship_plan_armor_mass_tons(
            armor_templates[facing] or {},
            as_float(armor_facings[facing].get("armorValue"), 0.0),
            hull_length_m,
            hull_width_m,
            lateral_depth_m,
            lateral=facing == "lateral",
            cinematic_scale=cinematic_scale,
        )
        for facing in ("nose", "lateral", "tail")
    }
    utility_mass_tons = sum(as_float(template.get("mass_tons"), 0.0) for template in utilities)
    weapon_mass_tons = sum(ship_plan_weapon_mass_tons(template, magazine_multiplier) for template in weapons)
    crew_mass_tons = crew * 4.0
    dry_mass_tons = (
        as_float(hull.get("mass_tons"), 0.0)
        + drive_mass_tons
        + power_plant_mass_tons
        + radiator_mass_tons
        + utility_mass_tons
        + weapon_mass_tons
        + sum(armor_masses.values())
        + crew_mass_tons
    )
    propellant_mass_tons = as_float(design.get("propellantTanks"), 0.0) * 100.0
    wet_mass_tons = dry_mass_tons + propellant_mass_tons
    modified_thrust_n = as_float(drive.get("thrust_N"), 0.0) * thrust_multiplier
    modified_exhaust_velocity_kps = as_float(drive.get("EV_kps"), 0.0) * exhaust_velocity_multiplier
    effect_contexts = faction_effect_contexts(indexed, faction_id)
    max_cruise_acceleration_g = apply_effect_modifiers(
        effect_contexts,
        catalogs["effects"],
        "Ship_MaxSurvivableCruiseAcceleration_Bonus",
        DEFAULT_GLOBAL_CONFIG["baselineMaxHumanCruiseAcceleration_g"],
    )
    max_combat_acceleration_g = apply_effect_modifiers(
        effect_contexts,
        catalogs["effects"],
        "Ship_MaxSurvivableCombatAcceleration_Bonus",
        DEFAULT_GLOBAL_CONFIG["baselineMaxHumanCombatAcceleration_g"],
    )
    cruise_acceleration_mps2 = min(modified_thrust_n / (wet_mass_tons * 1000.0), max_cruise_acceleration_g * STANDARD_GRAVITY_MPS2)
    combat_acceleration_mps2 = min(
        modified_thrust_n * as_float(drive.get("thrustCap"), 0.0) / (wet_mass_tons * 1000.0),
        max_combat_acceleration_g * STANDARD_GRAVITY_MPS2,
    )
    delta_v_kps = modified_exhaust_velocity_kps * math.log(wet_mass_tons / dry_mass_tons) if dry_mass_tons > 0.0 else 0.0
    maneuver_thrust_n = 2_500_000.0 + sum(
        ship_plan_utility_rule_value(template, "RotationalThrust", 0.0)
        for template in utilities
    )
    moment_of_inertia = (1.0 / 12.0) * wet_mass_tons * 1000.0 * hull_length_m**2
    angular_acceleration_degps2 = (
        maneuver_thrust_n * 2.0 * hull_length_m / 2.0 / moment_of_inertia * 180.0 / math.pi
        if moment_of_inertia > 0.0
        else 0.0
    )

    scale = DEFAULT_GLOBAL_CONFIG["spaceResourceToTons"]
    resource_breakdown: dict[str, dict[str, float]] = {}

    def add_cost(name: str, materials: dict[str, Any] | None, mass_tons: float) -> None:
        values = resource_breakdown.setdefault(name, {})
        ship_plan_add_scaled_materials(values, materials, mass_tons * scale)

    add_cost("hull", hull.get("weightedBuildMaterials"), as_float(hull.get("mass_tons"), 0.0))
    add_cost("drive", drive.get("weightedBuildMaterials"), drive_mass_tons)
    add_cost("powerPlant", power_plant.get("weightedBuildMaterials"), power_plant_mass_tons)
    add_cost("radiator", radiator.get("weightedBuildMaterials"), radiator_mass_tons)
    for template in weapons:
        for resource, value in ship_plan_weapon_cost(template, magazine_multiplier).items():
            resource_breakdown.setdefault("weapons", {})[resource] = resource_breakdown.setdefault("weapons", {}).get(resource, 0.0) + value
    for template in utilities:
        add_cost("utilities", template.get("weightedBuildMaterials"), as_float(template.get("mass_tons"), 0.0))
    for facing, mass_tons in armor_masses.items():
        add_cost("armor", (armor_templates[facing] or {}).get("weightedBuildMaterials"), mass_tons)
    add_cost(
        "crew",
        {
            "water": DEFAULT_GLOBAL_CONFIG["crewBaselineWater_tons"],
            "volatiles": DEFAULT_GLOBAL_CONFIG["crewBaselineVolatiles_tons"],
        },
        crew,
    )
    add_cost("propellant", drive.get("perTankPropellantMaterials"), propellant_mass_tons)
    resources: dict[str, float] = {}
    for values in resource_breakdown.values():
        for resource, value in values.items():
            resources[resource] = resources.get(resource, 0.0) + value

    warnings = []
    required_class = str(drive.get("requiredPowerPlant") or "")
    plant_class = str(power_plant.get("powerPlantClass") or "")
    if not ship_plan_power_plant_class_compatible(required_class, plant_class):
        warnings.append(f"Drive requires {required_class}; selected power plant is {plant_class}.")
    if as_float(power_plant.get("maxOutput_GW"), 0.0) < ship_power_requirement_gw:
        warnings.append("Selected power plant maximum output is below the simulated ship power requirement.")
    if hull.get("alien"):
        warnings.append("Alien acceleration caps are not reconstructed; human survivability caps were used.")

    return clean_numbers(
        {
            "complete": True,
            "crew": crew,
            "massTons": {
                "wet": wet_mass_tons,
                "dry": dry_mass_tons,
                "propellant": propellant_mass_tons,
                "hull": as_float(hull.get("mass_tons"), 0.0),
                "drive": drive_mass_tons,
                "powerPlant": power_plant_mass_tons,
                "radiator": radiator_mass_tons,
                "weapons": weapon_mass_tons,
                "utilities": utility_mass_tons,
                "armor": {"total": sum(armor_masses.values()), **armor_masses},
                "crew": crew_mass_tons,
            },
            "propulsion": {
                "cruiseAccelerationMilliG": cruise_acceleration_mps2 / STANDARD_GRAVITY_MPS2 * 1000.0,
                "combatAccelerationMilliG": combat_acceleration_mps2 / STANDARD_GRAVITY_MPS2 * 1000.0,
                "cruiseDeltaVKps": delta_v_kps,
                "angularAccelerationDegreesPerSecondSquared": angular_acceleration_degps2,
                "modifiedThrustN": modified_thrust_n,
                "modifiedExhaustVelocityKps": modified_exhaust_velocity_kps,
                "openCycleCooling": open_cycle_cooling,
            },
            "power": {
                "driveRequirementGW": drive_power_requirement_gw,
                "systemsRequirementGW": required_systems_power_gw,
                "weaponsGenerationRequirementGW": required_weapons_power_generation_gw,
                "weaponsStorageRequirementGJ": sum(weapon_energy_gj),
                "shipProductionRequirementGW": ship_power_requirement_gw,
                "wasteHeatGW": waste_heat_gw,
            },
            "storage": {
                "heatSinkCapacityGJ": sum(as_float(template.get("heatCapacity_GJ"), 0.0) for template in utilities),
                "batteryCapacityGJ": sum(as_float(template.get("energyCapacity_GJ"), 0.0) for template in utilities),
                "magazineMultiplier": magazine_multiplier,
            },
            "construction": {
                "resources": ship_plan_clean_resources(resources),
                "resourceBreakdown": {
                    category: ship_plan_clean_resources(values)
                    for category, values in resource_breakdown.items()
                    if ship_plan_clean_resources(values)
                },
                "time": ship_plan_shipyard_times(indexed, faction_id, hull, catalogs["effects"], catalogs["shipyards"]),
            },
            "upkeep": {
                "missionControl": hull.get("missionControl"),
                "monthlyMoney": hull.get("monthlyIncome_Money"),
            },
            "warnings": warnings,
            "combatPerformanceRatingIncluded": False,
        },
        6,
    )


def ship_plan_existing_designs(
    indexed: IndexedState,
    faction_id: int,
    faction: dict[str, Any],
    catalogs: dict[str, dict[str, dict[str, Any]]],
) -> list[dict[str, Any]]:
    active_counts: dict[str, int] = {}
    for ship in faction_ship_states(indexed, faction):
        name = str(ship.get("templateName") or "")
        active_counts[name] = active_counts.get(name, 0) + 1
    built_counts = faction.get("shipsBuiltInClass") if isinstance(faction.get("shipsBuiltInClass"), dict) else {}
    result = []
    for design in faction.get("shipDesigns") if isinstance(faction.get("shipDesigns"), list) else []:
        if not isinstance(design, dict):
            continue
        name = str(design.get("dataName") or "")
        simulation = simulate_ship_design(indexed, faction_id, faction, design, catalogs)
        if not simulation.get("complete"):
            missing = simulation.get("missingTemplates") or ["<missing required component reference>"]
            raise CalculationDependencyError(
                CalculationDependency(
                    kind="ship-component",
                    name=", ".join(str(item) for item in missing),
                    context=f"ship-plan.saved-design.{name or '<unnamed>'}",
                    scenario=scenario_template_name(indexed),
                    reason="saved design references a component absent from the packaged catalog",
                )
            )
        result.append(
            clean_numbers(
                {
                    "template": name,
                    "display": design.get("_displayName") or design.get("friendlyName") or name,
                    "role": design.get("role"),
                    "hull": design.get("hullName"),
                    "drive": design.get("driveName"),
                    "powerPlant": design.get("powerPlantName"),
                    "radiator": design.get("radiatorName"),
                    "propellantTanks": design.get("propellantTanks"),
                    "armor": {
                        "nose": design.get("noseArmor"),
                        "lateral": design.get("lateralArmor"),
                        "tail": design.get("tailArmor"),
                    },
                    "utilities": design.get("moduleTemplateEntries") or [],
                    "hullWeapons": design.get("hullWeaponTemplateEntries") or [],
                    "noseWeapons": design.get("noseWeaponTemplateEntries") or [],
                    "simulation": simulation,
                    "activeShips": active_counts.get(name, 0),
                    "shipsBuilt": int(as_float(built_counts.get(name), 0.0)),
                }
            )
        )
    return sorted(result, key=lambda row: str(row.get("display") or row.get("template")))


def ship_plan_select_design(existing_designs: list[dict[str, Any]], fragment: str) -> dict[str, Any]:
    needle = fragment.casefold()
    exact = [
        row
        for row in existing_designs
        if needle in {str(row.get("template") or "").casefold(), str(row.get("display") or "").casefold()}
    ]
    if len(exact) == 1:
        return exact[0]
    matches = [
        row
        for row in existing_designs
        if needle in str(row.get("template") or "").casefold() or needle in str(row.get("display") or "").casefold()
    ]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise SystemExit(f"No ship design matched: {fragment}")
    raise SystemExit(f"Multiple ship designs matched {fragment!r}: {', '.join(str(row.get('display')) for row in matches)}")


def calculate_ship_plan(
    indexed: IndexedState,
    templates_dir: Path | None,
    faction_name: str | None = None,
    role: str = "balanced",
    top: int = 8,
    include_obsolete: bool = False,
    include_all_components: bool = False,
    design_name: str | None = None,
) -> dict[str, Any]:
    faction_id, faction = find_faction_state(indexed, faction_name)
    runtime_catalogs = calculation_catalogs(indexed, "ship-plan")
    simulation_catalogs = {**runtime_catalogs.ship_simulation_catalogs, "shipyards": load_hab_module_catalog()}
    ship_templates = runtime_catalogs.ships
    hull_templates = simulation_catalogs["hulls"]
    drive_templates = simulation_catalogs["drives"]
    plant_templates = simulation_catalogs["powerPlants"]
    radiator_templates = simulation_catalogs["radiators"]
    battery_templates = ship_templates["batteries"]
    heat_sink_templates = ship_templates["heatSinks"]
    armor_templates = simulation_catalogs["armors"]
    utility_templates = ship_templates["utilities"]
    weapon_templates = [
        (str(template.get("_shipPlanKind") or "weapon"), template)
        for template in ship_templates["weapons"].values()
    ]

    available = lambda template: ship_plan_part_unlocked(template, faction, include_obsolete=include_obsolete)
    hulls = [
        ship_plan_hull_row(template)
        for template in hull_templates.values()
        if available(template) and not template.get("alien") and not template.get("noShipyardBuild")
    ]
    drives = [ship_plan_drive_row(template) for template in drive_templates.values() if available(template)]
    power_plants = [ship_plan_power_plant_row(template) for template in plant_templates.values() if available(template)]
    radiators = [
        ship_plan_generic_row(
            template,
            (
                ("specificPowerKWPerKg", "specificPower_2s_KWkg"),
                ("specificMassKgPerM2", "specificMass_2s_kgm2"),
                ("vulnerability", "vulnerability"),
                ("radiatorType", "radiatorType"),
            ),
        )
        for template in radiator_templates.values()
        if available(template)
    ]
    batteries = [
        ship_plan_generic_row(
            template,
            (("capacityGJ", "energyCapacity_GJ"), ("rechargeGJPerSecond", "rechargeRate_GJs"), ("massTons", "mass_tons")),
        )
        for template in battery_templates.values()
        if available(template)
    ]
    heat_sinks = [
        ship_plan_generic_row(template, (("capacityGJ", "heatCapacity_GJ"), ("massTons", "mass_tons")))
        for template in heat_sink_templates.values()
        if available(template)
    ]
    armors = [
        ship_plan_generic_row(
            template,
            (
                ("densityKgPerM3", "density_kgm3"),
                ("xRayHalfValueCm", "xRayHalfValue_cm"),
                ("baryonicHalfValueCm", "baryonicHalfValue_cm"),
                ("heatOfVaporizationMJPerKg", "heatofVaporization_MJkg"),
                ("specialties", "specialties"),
            ),
        )
        for template in armor_templates.values()
        if available(template)
    ]
    utilities = [
        ship_plan_utility_row(template)
        for template in utility_templates.values()
        if available(template) and template.get("dataName") != "Empty"
    ]
    weapons = [
        row
        for kind, template in weapon_templates
        if available(template)
        for row in [ship_plan_weapon_row(template, kind)]
        if row is not None
    ]

    drive_views = ship_plan_drive_goal_views(drives, power_plants, top)
    weapon_views = ship_plan_weapon_goal_views(weapons, top)
    selected_drives = {
        str(row.get("template")): row
        for rows in drive_views.values()
        for row in rows
    }
    selected_weapons = {
        str(row.get("template")): row
        for rows in weapon_views.values()
        for row in rows
    }
    role_utilities = [
        row
        for row in sorted(utilities, key=lambda row: str(row.get("display") or row.get("template")))
        if role == "balanced" or role in (row.get("roleTags") or [])
    ][: max(0, top)]
    required_category_warnings = [
        f"No non-obsolete unlocked {name} found; rerun with --include-obsolete if a hidden legacy part is still needed."
        for name, rows in (
            ("power plants", power_plants),
            ("radiators", radiators),
            ("batteries", batteries),
            ("armors", armors),
        )
        if not rows and not include_obsolete
    ]
    existing_designs = ship_plan_existing_designs(indexed, faction_id, faction, simulation_catalogs)

    report = {
        "faction": faction_brief(faction_id, faction),
        "date": (first_value(indexed, "TITimeState") or {}).get("currentDateTime"),
        "questionSupported": "What ship design should I build, and what non-combat physical and construction values do my saved designs have?",
        "requestedRole": role,
        "templateAvailability": {
            "templatesDir": template_source_value(templates_dir),
            "warning": None if hull_templates and drive_templates else "Local Terra Invicta ship templates are required.",
        },
        "currentState": {
            "resources": faction.get("resources") or {},
            "resourceIncomeDeficiencies": faction.get("resourceIncomeDeficiencies") or [],
            "obsoleteShipPartCount": len(faction.get("obsoletedShipParts") or []),
            "includeObsoleteParts": include_obsolete,
            "requiredCategoryWarnings": required_category_warnings,
            "existingDesigns": existing_designs,
        },
        "unlockedCounts": {
            "hulls": len(hulls),
            "drives": len(drives),
            "powerPlants": len(power_plants),
            "radiators": len(radiators),
            "batteries": len(batteries),
            "heatSinks": len(heat_sinks),
            "armors": len(armors),
            "utilities": len(utilities),
            "weapons": len(weapons),
        },
        "componentCatalog": {
            "hulls": sorted(hulls, key=lambda row: (as_float(row.get("constructionTier"), 0.0), str(row.get("display")))),
            "powerPlants": sorted(power_plants, key=lambda row: (as_float(row.get("specificMassTonsPerGW"), 0.0), str(row.get("display")))),
            "radiators": sorted(radiators, key=lambda row: (-as_float(row.get("specificPowerKWPerKg"), 0.0), str(row.get("display")))),
            "batteries": sorted(batteries, key=lambda row: (-as_float(row.get("capacityGJ"), 0.0), str(row.get("display")))),
            "heatSinks": sorted(heat_sinks, key=lambda row: (-as_float(row.get("capacityGJ"), 0.0), str(row.get("display")))),
            "armors": sorted(armors, key=lambda row: (as_float(row.get("densityKgPerM3"), 0.0), str(row.get("display")))),
            "driveGoalViews": drive_views,
            "driveShortlist": sorted(selected_drives.values(), key=lambda row: str(row.get("display") or row.get("template"))),
            "weaponGoalViews": weapon_views,
            "weaponShortlist": sorted(selected_weapons.values(), key=lambda row: str(row.get("display") or row.get("template"))),
            "roleUtilityShortlist": role_utilities,
        },
        "llmDecision": {
            "recommendedUse": [
                "Choose a hull that fits the role and required weapon or utility slots.",
                "Choose a drive from the relevant proxy view, then use compatiblePowerPlants to keep the pairing legal.",
                "Choose radiator, armor, battery, heat sink, utilities, weapons, propellant tanks, and armor values while checking resource constraints.",
                "Treat proxy rankings as shortlist evidence and make the final design recommendation explicitly.",
            ],
            "recommendedDriveView": {
                "balanced": "balanced",
                "combat": "balanced",
                "intercept": "thrust",
                "transfer": "exhaustVelocity",
                "colony": "exhaustVelocity",
                "assault": "exhaustVelocity",
                "science": "exhaustVelocity",
            }.get(role),
            "roleHints": {
                "balanced": "Review all proxy views and state the intended operating area.",
                "combat": "Prioritize weapon coverage, point defense, combat utilities, armor, and heat handling.",
                "intercept": "Prioritize thrust and projectile-defense coverage for local-response ships.",
                "transfer": "Prioritize exhaust velocity and refueling or thrust utility options.",
                "colony": "Prioritize exhaust velocity, propellant, and Found* utility modules.",
                "assault": "Prioritize Marine Assault utility modules and enough transfer performance to reach the target.",
                "science": "Prioritize Mobile Space Science Lab or Prospector utility modules and economical transfer performance.",
            }.get(role),
            "finalRecommendationAutomated": False,
        },
        "limitations": [
            "Drive rankings are transparent thrust, exhaust-velocity, and sqrt(thrust) * exhaust-velocity proxies; they are not mission transfer simulations.",
            "Saved-design simulations reconstruct non-combat builder values from local templates: mass, propulsion, power, heat, storage, armor, construction resources and time, MC, and monthly money upkeep.",
            "Combat performance ratings are intentionally excluded. Weapon damage-rate fields remain shortlist comparison proxies only.",
            "Weapon damage-rate fields are comparison proxies over template damage, salvo size, and cooldown; they are not hit-probability or armor-penetration simulations.",
            "Unlock filtering uses finishedProjectNames, disable flags, and obsoletedShipParts from the save. Hidden game rules are not re-simulated.",
            "Construction resources do not apply AI difficulty scaling or helium-3 access substitution. Human saved designs are the validated target.",
        ],
    }
    if design_name:
        report["selectedDesign"] = ship_plan_select_design(existing_designs, design_name)
    if include_all_components:
        report["allUnlockedComponents"] = {
            "drives": sorted(drives, key=lambda row: str(row.get("display") or row.get("template"))),
            "utilities": sorted(utilities, key=lambda row: str(row.get("display") or row.get("template"))),
            "weapons": sorted(weapons, key=lambda row: str(row.get("display") or row.get("template"))),
        }
    return clean_numbers(report, 6)


def command_ship_plan(save_path: Path, templates_dir: Path | None, args: argparse.Namespace) -> None:
    data = load_save(save_path)
    indexed = build_index(data)
    result = calculate_ship_plan(
        indexed,
        templates_dir,
        faction_name=args.faction,
        role=args.role,
        top=args.top,
        include_obsolete=args.include_obsolete,
        include_all_components=args.all_components,
        design_name=args.design,
    )
    if args.design:
        result = {
            "faction": result["faction"],
            "date": result["date"],
            "selectedDesign": result["selectedDesign"],
            "limitations": result["limitations"],
        }
    print_json(result, compact=args.compact)


def command_nation_claims(save_path: Path, templates_dir: Path | None, args: argparse.Namespace) -> None:
    data = load_save(save_path)
    indexed = build_index(data)
    runtime_catalogs = calculation_catalogs(indexed, "nation-claims")
    result = calculate_nation_claims(
        indexed,
        claimant_name=args.claimant,
        target_name=args.target,
        claim_catalog=runtime_catalogs.nation_claims,
        diagnostics=args.diagnostics,
    )
    if args.diagnostics:
        result["calculationDiagnostics"] = runtime_catalogs.calculation_diagnostics()
    print_json(result, compact=args.compact)


def command_ai_fleet_diagnostics(save_path: Path, templates_dir: Path | None, args: argparse.Namespace) -> None:
    data = load_save(save_path)
    indexed = build_index(data)
    result = calculate_ai_fleet_diagnostics(
        indexed,
        faction_name=args.faction,
        stale_days=args.stale_days,
        diagnostics=args.diagnostics,
    )
    print_json(result, compact=args.compact)


def command_catalog_verify(args: argparse.Namespace) -> None:
    result = verify_catalogs(
        Path(args.templates_dir),
        args.scenario,
        save_path=resolve_save_path(args.save),
    )
    print_json(result, compact=args.compact)


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
    missing_effects = sorted(
        {
            name
            for context in TOPBAR_EFFECT_CONTEXTS
            for name in effect_contexts.get(context, [])
            if name not in effect_templates
        }
    )
    if missing_effects:
        raise RuntimeError(
            "Effects required by topbar calculations are missing template data: " + ", ".join(missing_effects)
        )
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


def command_topbar(save_path: Path, templates_dir: Path | None, args: argparse.Namespace) -> None:
    data = load_save(save_path)
    indexed = build_index(data)
    result = calculate_topbar(
        indexed,
        templates_dir,
        args.faction,
        include_details=args.details,
        include_diagnostics=args.diagnostics,
        forecast_resource=args.forecast_resource,
    )
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


def command_world_ui(save_path: Path, templates_dir: Path | None, args: argparse.Namespace) -> None:
    data = load_save(save_path)
    indexed = build_index(data)
    result = calculate_world_ui(indexed, templates_dir, args.faction)
    print_json(clean_numbers(result, 6), compact=args.compact)


def command_advise(save_path: Path, templates_dir: Path | None, args: argparse.Namespace) -> None:
    data = load_save(save_path)
    indexed = build_index(data)
    runtime_catalogs = calculation_catalogs(indexed, "advise")
    trait_templates = runtime_catalogs.traits
    effect_templates = runtime_catalogs.effects
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
    runtime_catalogs = calculation_catalogs(indexed, "nation-ui")
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
    can_have_navy = nation_can_have_navy(nation, pc_gdp)
    max_navies = allowed_armies if can_have_navy else 0
    navies_can_build = max(0, armies["count"] - armies["navies"]) if can_have_navy else 0
    control_points = nation_control_points(indexed, nation)
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
    metadata_candidates = []
    if player_name:
        needle = str(player_name).casefold()
        metadata_candidates = [
            faction
            for faction in snapshot["factions"]
            if needle
            in {
                str(faction.get("template") or "").casefold(),
                str(faction.get("display") or "").casefold(),
                str(faction.get("code") or "").casefold(),
            }
        ]
    player_state_candidates = [
        faction
        for faction in snapshot["factions"]
        if isinstance(faction.get("player"), dict) and faction["player"].get("isAI") is False
    ]
    if len(metadata_candidates) > 1 or len(player_state_candidates) > 1:
        raise SystemExit("Multiple human player faction candidates found in snapshot.")
    if metadata_candidates and player_state_candidates and metadata_candidates[0].get("id") != player_state_candidates[0].get("id"):
        raise SystemExit("Snapshot player faction metadata conflicts with TIPlayerState.")
    player_faction = (player_state_candidates or metadata_candidates or [None])[0]
    if player_faction is None:
        raise SystemExit("Human player faction could not be resolved in snapshot.")

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
        "faction": {
            "display": player_faction.get("display"),
            "template": player_faction.get("template"),
            "player": True,
        },
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
