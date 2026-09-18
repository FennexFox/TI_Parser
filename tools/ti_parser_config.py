"""Shared parser constants and immutable configuration objects."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType

import ti_parser_hab as hab_layer
import ti_parser_income as income_layer
import ti_parser_ship as ship_layer
from ti_parser_nation_validity import (
    MIN_CONTROL_POINTS_FOR_NAVY,
    MIN_CONTROL_POINTS_FOR_NAVY_EXCEPTION,
    PCGDP_FOR_NAVY_EXCEPTION,
)
from ti_parser_snapshot import SnapshotConfig


SCHEMA_VERSION = 7


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
    "spaceResourceToTons": ship_layer.SPACE_RESOURCE_TO_TONS,
    "crewBaselineWater_tons": 2.0,
    "crewBaselineVolatiles_tons": 2.0,
    "crewWaterConsumptionTons_year": 3.5,
    "crewVolatilesConsumptionTons_year": 3.5,
    "crewSalary_year": 0.1,
    "baselineMaxHumanCruiseAcceleration_g": 2.0,
    "baselineMaxHumanCombatAcceleration_g": 3.0,
    "smallShipyardPenaltyPowerPerTier": 1.5,
}


DEFAULT_CP_MAINTENANCE_GDP_SCALE = 1_000_000_000.0


CP_MAINTENANCE_CAMPAIGN_START_GDP_FACTOR = 6.26e-06


MIN_POPULATION_FOR_FIRST_ARMY_MILLIONS = 5.0


MIN_POPULATION_FOR_ADDITIONAL_ARMIES_PER_MILLIONS = 25.0


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
    1: "SpaceDock",
    2: "Shipyard",
    3: "Spaceworks",
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


RESEARCH_PLAN_SCORE_AXES = (
    "fastCompletion",
    "factionSynergy",
    "unlockBreadth",
    "criticalTemplate",
    "resourceReliefCoverage",
    "currentProgress",
)


PRIORITY_BONUS_ORG_FIELDS = {
    "Economy": "economyBonus", "Welfare": "welfareBonus", "Environment": "environmentBonus",
    "Knowledge": "knowledgeBonus", "Government": "governmentBonus", "Unity": "unityBonus",
    "Oppression": "oppressionBonus", "Funding": "spaceDevBonus", "Spoils": "spoilsBonus",
    "Civilian_InitiateSpaceflightProgram": "spaceflightBonus", "LaunchFacilities": "spaceflightBonus",
    "MissionControl": "MCBonus", "Military_FoundMilitary": "militaryBonus", "Military": "militaryBonus",
    "Military_BuildArmy": "militaryBonus", "Military_BuildNavy": "militaryBonus",
    "Military_BuildSpaceDefenses": "militaryBonus", "Military_BuildSTOSquadron": "spaceflightBonus",
}


PRIORITY_BONUS_EFFECT_CONTEXTS = {
    "Economy": "EconomyPriority", "Welfare": "WelfarePriority", "Environment": "EnvironmentPriority",
    "Knowledge": "KnowledgePriority", "Government": "GovernmentPriority", "Unity": "UnityPriority",
    "Oppression": "OppressionPriority", "Funding": "SpaceDevPriority", "Spoils": "SpoilsPriority",
    "Civilian_InitiateSpaceflightProgram": "SpaceflightPriority", "LaunchFacilities": "LaunchFacilitiesPriority",
    "MissionControl": "MissionControlPriority", "Military": "MilitaryPriority",
    "Military_BuildArmy": "BuildArmyPriority", "Military_BuildNavy": "UpgradeArmyPriority",
    "Military_InitiateNuclearProgram": "BuildNuclearWeaponsPriority",
    "Military_BuildNuclearWeapons": "BuildNuclearWeaponsPriority",
    "Military_BuildSpaceDefenses": "BuildSpaceDefensesPriority", "Military_BuildSTOSquadron": "BuildSTOSquadronPriority",
}
