#!/usr/bin/env python3
"""Compact Terra Invicta save parser.

The goal is to avoid repeatedly sending the full decompressed save through an
LLM context. The CLI parses the local save, builds a small indexed snapshot, and
prints only the requested slice.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterable


SCHEMA_VERSION = 4
DEFAULT_CACHE_DIR = ".ti_cache"
SAVE_GLOB = "*.gz"
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
NATION_CONDITION_FIELDS = {
    "TINationCondition_fCohesion": "cohesion",
    "TINationCondition_fDemocracy": "democracy",
    "TINationCondition_fEducation": "education",
    "TINationCondition_fInequality": "inequality",
    "TINationCondition_fUnrest": "unrest",
}


@dataclass(frozen=True)
class IndexedState:
    data: dict[str, Any]
    gamestates: dict[str, list[dict[str, Any]]]
    id_index: dict[int, tuple[str, str, dict[str, Any]]]


def json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def print_json(value: Any, *, compact: bool = False) -> None:
    if compact:
        print(json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=json_default))
    else:
        print(json.dumps(value, ensure_ascii=False, indent=2, default=json_default))


def ref_id(value: Any) -> int | None:
    if isinstance(value, dict):
        raw = value.get("value")
        if isinstance(raw, int):
            return raw
    return None


def short_type(full_type: str) -> str:
    return full_type.rsplit(".", 1)[-1]


def campaign_code(template_name: str | None) -> str | None:
    if not template_name:
        return None
    if "_" in template_name and template_name[:4].isdigit():
        return template_name.split("_", 1)[1]
    return template_name


def clean_number(value: Any, digits: int = 3) -> Any:
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return round(value, digits)
    return value


def clean_numbers(value: Any, digits: int = 3) -> Any:
    if isinstance(value, dict):
        return {str(k): clean_numbers(v, digits) for k, v in value.items()}
    if isinstance(value, list):
        return [clean_numbers(v, digits) for v in value]
    return clean_number(value, digits)


def save_fingerprint(save_path: Path) -> dict[str, Any]:
    stat = save_path.stat()
    return {
        "path": str(save_path),
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    }


def cache_key(fingerprint: dict[str, Any]) -> str:
    raw = json.dumps(fingerprint, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def candidate_save_dirs() -> Iterable[Path]:
    home = Path.home()
    yield home / "Documents" / "My Games" / "TerraInvicta" / "Saves"
    yield home / "OneDrive" / "Documents" / "My Games" / "TerraInvicta" / "Saves"
    yield home / "OneDrive" / "문서" / "My Games" / "TerraInvicta" / "Saves"


def candidate_templates_dirs() -> Iterable[Path]:
    steam_roots = (
        Path("C:/Program Files (x86)/Steam/steamapps/common"),
        Path("C:/Program Files/Steam/steamapps/common"),
        Path("D:/SteamLibrary/steamapps/common"),
        Path("E:/SteamLibrary/steamapps/common"),
    )
    for root in steam_roots:
        yield root / "Terra Invicta" / "TerraInvicta_Data" / "StreamingAssets" / "Templates"


def find_latest_save() -> Path:
    candidates: list[Path] = []
    for directory in candidate_save_dirs():
        if directory.is_dir():
            candidates.extend(path for path in directory.glob(SAVE_GLOB) if path.is_file())
    if not candidates:
        raise FileNotFoundError("No Terra Invicta .gz saves found. Pass --save <path>.")
    return max(candidates, key=lambda path: path.stat().st_mtime_ns)


def resolve_save_path(save_arg: str | None) -> Path:
    if save_arg:
        path = Path(save_arg).expanduser()
        if not path.is_file():
            raise FileNotFoundError(f"Save file not found: {path}")
        return path
    return find_latest_save()


def resolve_templates_dir(templates_arg: str | None) -> Path | None:
    if templates_arg:
        path = Path(templates_arg).expanduser()
        if not path.is_dir():
            raise FileNotFoundError(f"Templates directory not found: {path}")
        return path
    for path in candidate_templates_dirs():
        if (path / "TITraitTemplate.json").is_file():
            return path
    return None


def load_save(save_path: Path) -> dict[str, Any]:
    with gzip.open(save_path, "rt", encoding="utf-8-sig") as handle:
        data = json.load(handle)
    if not isinstance(data, dict) or "gamestates" not in data:
        raise ValueError(f"Not a recognized Terra Invicta save: {save_path}")
    return data


def file_fingerprint(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.is_file():
        return None
    stat = path.stat()
    return {"path": str(path), "size": stat.st_size, "mtime_ns": stat.st_mtime_ns}


def snapshot_fingerprint(save_path: Path, templates_dir: Path | None) -> dict[str, Any]:
    return {
        "save": save_fingerprint(save_path),
        "traitTemplate": file_fingerprint(templates_dir / "TITraitTemplate.json" if templates_dir else None),
    }


def load_trait_templates(templates_dir: Path | None) -> dict[str, dict[str, Any]]:
    if templates_dir is None:
        return {}
    trait_path = templates_dir / "TITraitTemplate.json"
    if not trait_path.is_file():
        return {}
    with trait_path.open("r", encoding="utf-8-sig") as handle:
        raw = json.load(handle)
    if not isinstance(raw, list):
        return {}
    return {item["dataName"]: item for item in raw if isinstance(item, dict) and item.get("dataName")}


def load_named_templates(templates_dir: Path | None, filename: str) -> dict[str, dict[str, Any]]:
    if templates_dir is None:
        return {}
    path = templates_dir / filename
    if not path.is_file():
        return {}
    with path.open("r", encoding="utf-8-sig") as handle:
        raw = json.load(handle)
    if not isinstance(raw, list):
        return {}
    return {item["dataName"]: item for item in raw if isinstance(item, dict) and item.get("dataName")}


def as_float(value: Any, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return default
    return default


def raw_state_id(entry: dict[str, Any]) -> int | None:
    value = entry.get("Value") or {}
    return ref_id(entry.get("Key")) or ref_id(value.get("ID"))


def raw_name_values(state: dict[str, Any]) -> list[str]:
    values = []
    for value in (state.get("templateName"), campaign_code(state.get("templateName")), state.get("displayName")):
        if value:
            values.append(str(value))
    return values


def match_raw_state(indexed: IndexedState, wanted_type: str, name: str) -> tuple[int | None, dict[str, Any]] | None:
    needle = name.casefold()
    partial: list[tuple[int | None, dict[str, Any]]] = []
    for entry in type_entries(indexed, wanted_type):
        state = entry.get("Value") or {}
        if not isinstance(state, dict):
            continue
        names = raw_name_values(state)
        state_id = raw_state_id(entry)
        if any(value.casefold() == needle for value in names):
            return state_id, state
        if any(needle in value.casefold() for value in names):
            partial.append((state_id, state))
    return partial[0] if partial else None


def state_value_by_id(indexed: IndexedState, state_id: int | None) -> dict[str, Any] | None:
    if state_id is None:
        return None
    found = indexed.id_index.get(state_id)
    return found[2] if found else None


def find_faction_state(indexed: IndexedState, name: str | None = None) -> tuple[int, dict[str, Any]]:
    if name:
        found = match_raw_state(indexed, "TIFactionState", name)
        if found and found[0] is not None:
            return found[0], found[1]
        raise SystemExit(f"Faction not found: {name}")

    metadata = first_value(indexed, "TIMetadataState") or {}
    player_faction_name = metadata.get("playerFactionName")
    if player_faction_name:
        found = match_raw_state(indexed, "TIFactionState", str(player_faction_name))
        if found and found[0] is not None:
            return found[0], found[1]

    resist_candidate: tuple[int, dict[str, Any]] | None = None
    for entry in type_entries(indexed, "TIFactionState"):
        faction = entry.get("Value") or {}
        state_id = raw_state_id(entry)
        if state_id is None:
            continue
        player = resolve_ref(indexed, faction.get("player"))
        if player and player[2].get("templateName") == "ResistPlayer":
            return state_id, faction
        if faction.get("templateName") == "ResistCouncil":
            resist_candidate = (state_id, faction)
    if resist_candidate:
        return resist_candidate

    for entry in type_entries(indexed, "TIFactionState"):
        faction = entry.get("Value") or {}
        state_id = raw_state_id(entry)
        if state_id is not None:
            return state_id, faction
    raise SystemExit("No faction states found.")


def faction_effect_contexts(indexed: IndexedState, faction_id: int) -> dict[str, list[str]]:
    for entry in type_entries(indexed, "TIEffectsState"):
        effects_state = entry.get("Value") or {}
        pairs = effects_state.get("factionEffectsNames") if isinstance(effects_state.get("factionEffectsNames"), list) else []
        for pair in pairs:
            if not isinstance(pair, dict) or ref_id(pair.get("Key")) != faction_id:
                continue
            value = pair.get("Value")
            if isinstance(value, dict):
                return {
                    str(context): [str(item) for item in names if item]
                    for context, names in value.items()
                    if isinstance(names, list)
                }
    return {}


def apply_effect_modifiers(
    effect_contexts: dict[str, list[str]],
    effect_templates: dict[str, dict[str, Any]],
    context: str,
    base_value: float,
) -> float:
    result = float(base_value)
    for effect_name in effect_contexts.get(context, []):
        effect = effect_templates.get(effect_name)
        if not effect:
            continue
        operation = effect.get("operation")
        value = as_float(effect.get("value"), 0.0)
        if operation == "Additive":
            result += value
        elif operation == "Multiplicative":
            result *= value
        elif operation == "SetToFixedValue":
            result = value
        elif operation == "IncreaseToValue":
            result = max(result, value)
        elif operation == "DecreaseToValue":
            result = min(result, value)
    return result


def effect_modifier_delta(
    effect_contexts: dict[str, list[str]],
    effect_templates: dict[str, dict[str, Any]],
    context: str,
    base_value: float,
) -> float:
    return apply_effect_modifiers(effect_contexts, effect_templates, context, base_value) - base_value


def build_index(data: dict[str, Any]) -> IndexedState:
    gamestates = data.get("gamestates", {})
    if not isinstance(gamestates, dict):
        raise ValueError("Save gamestates field is not an object")

    id_index: dict[int, tuple[str, str, dict[str, Any]]] = {}
    for full_type, entries in gamestates.items():
        if not isinstance(entries, list):
            continue
        type_name = short_type(full_type)
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            value = entry.get("Value")
            if not isinstance(value, dict):
                continue
            state_id = ref_id(entry.get("Key")) or ref_id(value.get("ID"))
            if state_id is not None:
                id_index[state_id] = (full_type, type_name, value)
    return IndexedState(data=data, gamestates=gamestates, id_index=id_index)


def resolve_ref(indexed: IndexedState, value: Any) -> tuple[str, str, dict[str, Any]] | None:
    state_id = ref_id(value)
    if state_id is None:
        return None
    return indexed.id_index.get(state_id)


def ref_summary(indexed: IndexedState, value: Any) -> dict[str, Any] | None:
    state_id = ref_id(value)
    if state_id is None:
        return None
    found = indexed.id_index.get(state_id)
    if not found:
        return {"id": state_id}
    _, type_name, state = found
    return {
        "id": state_id,
        "type": type_name,
        "template": state.get("templateName"),
        "code": campaign_code(state.get("templateName")),
        "display": state.get("displayName"),
    }


def region_nation_summary(indexed: IndexedState, value: Any) -> dict[str, Any] | None:
    found = resolve_ref(indexed, value)
    if not found:
        return None
    region = found[2]
    return ref_summary(indexed, region.get("nation"))


def type_entries(indexed: IndexedState, wanted_type: str) -> list[dict[str, Any]]:
    for full_type, entries in indexed.gamestates.items():
        if full_type == wanted_type or short_type(full_type) == wanted_type:
            return entries
    return []


def first_value(indexed: IndexedState, wanted_type: str) -> dict[str, Any] | None:
    entries = type_entries(indexed, wanted_type)
    if entries:
        value = entries[0].get("Value")
        if isinstance(value, dict):
            return value
    return None


def time_summary(indexed: IndexedState) -> dict[str, Any]:
    time_state = first_value(indexed, "TITimeState") or {}
    current = time_state.get("currentDateTime") or {}
    return {
        "daysInCampaign": time_state.get("daysInCampaign"),
        "currentQuarterSinceStart": time_state.get("currentQuarterSinceStart"),
        "currentDateTime": current,
        "template": time_state.get("templateName"),
    }


def metadata_summary(indexed: IndexedState) -> dict[str, Any]:
    metadata = first_value(indexed, "TIMetadataState") or {}
    keys = (
        "playerFactionName",
        "gameTimeString",
        "difficulty",
        "playedWithMods",
        "customDifficulty",
        "researchSpeedMultiplier",
        "controlPointMaintenanceFreebieBonus",
        "missionControlBonus",
        "alienProgressionSpeed",
        "miningProductivityMultiplier",
        "nationalIPMultiplier",
        "averageMonthlyEvents",
    )
    return {key: metadata.get(key) for key in keys if key in metadata}


def global_summary(indexed: IndexedState) -> dict[str, Any]:
    global_state = first_value(indexed, "TIGlobalValuesState") or {}
    keys = (
        "difficulty",
        "campaignStartVersion",
        "latestSaveVersion",
        "realWorldCampaignStart",
        "controlPointMaintenanceFreebies",
        "moddingActive",
        "moddingUsedAnytime",
        "earthAtmosphericCO2_ppm",
        "earthAtmosphericCH4_ppm",
        "earthAtmosphericN2O_ppm",
        "globalSeaLevelAnomaly_cm",
        "looseNukes",
        "nuclearStrikes",
        "bestGlobalHumanMiltech",
        "maxGlobalExpectedHabSiteProduction_day",
    )
    return clean_numbers({key: global_state.get(key) for key in keys if key in global_state})


def faction_key_from_ref(indexed: IndexedState, value: Any) -> str | None:
    found = resolve_ref(indexed, value)
    if not found:
        return None
    state = found[2]
    return state.get("templateName") or state.get("displayName")


def faction_display_from_ref(indexed: IndexedState, value: Any) -> str | None:
    found = resolve_ref(indexed, value)
    if not found:
        return None
    state = found[2]
    return state.get("displayName") or state.get("templateName")


def control_point_summary(indexed: IndexedState, cp_value: dict[str, Any]) -> dict[str, Any]:
    faction = ref_summary(indexed, cp_value.get("faction"))
    return {
        "id": ref_id(cp_value.get("ID")),
        "position": cp_value.get("positionInNation"),
        "type": cp_value.get("controlPointType"),
        "faction": faction.get("template") if faction else None,
        "factionDisplay": faction.get("display") if faction else None,
        "defended": cp_value.get("defended"),
        "benefitsDisabled": cp_value.get("benefitsDisabled"),
        "priorities": clean_numbers(cp_value.get("controlPointPriorities") or {}),
    }


def summarize_regions(indexed: IndexedState, region_refs: list[Any]) -> dict[str, Any]:
    population = 0.0
    boost = 0.0
    mission_control = 0
    region_count = 0
    named_regions: list[str] = []
    for region_ref in region_refs:
        found = resolve_ref(indexed, region_ref)
        if not found:
            continue
        region = found[2]
        region_count += 1
        named_regions.append(region.get("displayName") or region.get("templateName") or str(ref_id(region_ref)))
        population += float(region.get("populationInMillions") or region.get("population_Millions") or 0.0)
        boost += float(region.get("boostPerYear_dekatons") or region.get("boostPerYear_tons") or 0.0)
        mission_control += int(region.get("missionControl") or 0)
    return {
        "count": region_count,
        "population_Millions": round(population, 3),
        "boostPerYear_dekatons": round(boost, 3),
        "missionControl": mission_control,
        "names": named_regions,
    }


def summarize_nation(indexed: IndexedState, entry: dict[str, Any]) -> dict[str, Any]:
    nation = entry.get("Value") or {}
    state_id = ref_id(entry.get("Key")) or ref_id(nation.get("ID"))
    region_refs = nation.get("regions") if isinstance(nation.get("regions"), list) else []
    region_summary = summarize_regions(indexed, region_refs)
    population = region_summary["population_Millions"]
    gdp = nation.get("GDP")
    per_capita = None
    if isinstance(gdp, (int, float)) and population:
        per_capita = gdp / (population * 1_000_000.0)

    cp_summaries: list[dict[str, Any]] = []
    cp_refs = nation.get("controlPoints") if isinstance(nation.get("controlPoints"), list) else []
    for cp_ref in cp_refs:
        found = resolve_ref(indexed, cp_ref)
        if found:
            cp_summaries.append(control_point_summary(indexed, found[2]))

    owner_counts: dict[str, int] = {}
    owner_display: dict[str, str] = {}
    executive_owner = None
    max_position = max((cp.get("position") for cp in cp_summaries if isinstance(cp.get("position"), int)), default=None)
    for cp in cp_summaries:
        owner = cp.get("faction")
        if not owner:
            continue
        owner_counts[owner] = owner_counts.get(owner, 0) + 1
        owner_display[owner] = cp.get("factionDisplay") or owner
        if cp.get("position") == max_position:
            executive_owner = owner

    return clean_numbers(
        {
            "id": state_id,
            "template": nation.get("templateName"),
            "code": campaign_code(nation.get("templateName")),
            "display": nation.get("displayName"),
            "GDP": gdp,
            "perCapitaGDP": per_capita,
            "population_Millions": population,
            "regions": region_summary["count"],
            "regionNames": region_summary["names"],
            "unrest": nation.get("unrest"),
            "cohesion": nation.get("cohesion"),
            "democracy": nation.get("democracy"),
            "education": nation.get("education"),
            "inequality": nation.get("inequality"),
            "militaryTechLevel": nation.get("militaryTechLevel"),
            "numNuclearWeapons": nation.get("numNuclearWeapons"),
            "baseInvestmentPoints_month": nation.get("baseInvestmentPoints_month"),
            "boostPerYear_dekatons": region_summary["boostPerYear_dekatons"],
            "missionControl": region_summary["missionControl"],
            "numControlPoints": nation.get("numControlPoints"),
            "numControlPoints_unclamped": nation.get("numControlPoints_unclamped"),
            "executiveOwner": executive_owner,
            "ownerCounts": owner_counts,
            "ownerDisplay": owner_display,
            "controlPoints": cp_summaries,
            "allies": [ref_summary(indexed, item) for item in nation.get("allies", [])],
            "rivals": [ref_summary(indexed, item) for item in nation.get("rivals", [])],
            "wars": [ref_summary(indexed, item) for item in nation.get("wars", [])],
        }
    )


def average(values: Any) -> float | None:
    if not isinstance(values, list) or not values:
        return None
    numeric = [float(value) for value in values if isinstance(value, (int, float))]
    if not numeric:
        return None
    return sum(numeric) / len(numeric)


def parse_modifier_number(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def int_like(value: float) -> int:
    return int(value)


def trait_mod_has_condition(mod: dict[str, Any]) -> bool:
    condition = mod.get("condition")
    return isinstance(condition, dict) and bool(condition)


def stat_mod_entry(trait_name: str, trait: dict[str, Any], mod: dict[str, Any], base_attributes: dict[str, int]) -> dict[str, Any] | None:
    attribute = mod.get("stat")
    if attribute not in COUNCILOR_ATTRIBUTES:
        return None
    operation = mod.get("operation")
    raw_value = mod.get("strValue")
    value = parse_modifier_number(raw_value)
    base_value = base_attributes.get(attribute, 0)
    contribution = None
    supported = True
    note = None

    if operation == "Additive" and value is not None:
        contribution = int_like(value)
    elif operation == "SetToFixedValue" and value is not None:
        contribution = int_like(value) - base_value
    elif operation == "Multiplicative" and value is not None:
        contribution = int_like(base_value * value - base_value)
    elif operation == "SetToAnotherAttribute" and isinstance(raw_value, str):
        contribution = base_attributes.get(raw_value, 0) - base_value
    elif operation in {"IncreaseToValue", "DecreaseToValue"}:
        contribution = 0
        note = "operation is displayed by traits but is not applied by TICouncilorState.ApplyTraitStatValue"
    else:
        supported = False
        note = "operation requires contextual game state and is not evaluated in base finalAttributes"

    return {
        "trait": trait_name,
        "traitDisplay": trait.get("friendlyName") or trait_name,
        "attribute": attribute,
        "operation": operation,
        "value": raw_value,
        "contribution": contribution,
        "conditional": trait_mod_has_condition(mod),
        "conditionType": (mod.get("condition") or {}).get("$type") if isinstance(mod.get("condition"), dict) else None,
        "condition": mod.get("condition"),
        "supported": supported,
        "note": note,
    }


def sum_attr_mods(mods: list[dict[str, Any]]) -> dict[str, int]:
    totals = {attribute: 0 for attribute in COUNCILOR_ATTRIBUTES}
    for mod in mods:
        contribution = mod.get("contribution")
        attribute = mod.get("attribute")
        if attribute in totals and isinstance(contribution, int):
            totals[attribute] += contribution
    return totals


def org_attribute_mods(indexed: IndexedState, councilor: dict[str, Any]) -> tuple[dict[str, int], list[dict[str, Any]]]:
    totals = {attribute: 0 for attribute in COUNCILOR_ATTRIBUTES}
    details: list[dict[str, Any]] = []
    org_refs = councilor.get("orgs") if isinstance(councilor.get("orgs"), list) else []
    for org_ref in org_refs:
        found = resolve_ref(indexed, org_ref)
        if not found:
            continue
        org = found[2]
        applying = bool(org.get("applyingBonuses"))
        mods = {}
        if applying:
            for attribute, field in ORG_ATTRIBUTE_FIELDS.items():
                value = org.get(field)
                if isinstance(value, int) and value != 0:
                    totals[attribute] += value
                    mods[attribute] = value
        details.append(
            {
                "id": ref_id(org.get("ID")),
                "template": org.get("templateName"),
                "display": org.get("displayName"),
                "tier": org.get("tier"),
                "applyingBonuses": applying,
                "attributeMods": mods,
            }
        )
    return totals, details


def trait_attribute_mods(
    councilor: dict[str, Any],
    trait_templates: dict[str, dict[str, Any]],
    base_attributes: dict[str, int],
) -> tuple[dict[str, int], list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    unconditional: list[dict[str, Any]] = []
    conditional: list[dict[str, Any]] = []
    warnings: list[str] = []
    trait_names = councilor.get("traitTemplateNames") if isinstance(councilor.get("traitTemplateNames"), list) else []
    for trait_name in trait_names:
        trait = trait_templates.get(trait_name)
        if not trait:
            warnings.append(f"missing trait template: {trait_name}")
            continue
        stat_mods = trait.get("statMods") if isinstance(trait.get("statMods"), list) else []
        for mod in stat_mods:
            if not isinstance(mod, dict) or not mod.get("stat"):
                continue
            entry = stat_mod_entry(trait_name, trait, mod, base_attributes)
            if entry is None:
                continue
            if entry["conditional"]:
                conditional.append(entry)
            else:
                unconditional.append(entry)
                if not entry["supported"]:
                    warnings.append(
                        f"unsupported unconditional trait mod: {trait_name} {entry['attribute']} {entry['operation']}"
                    )
    return sum_attr_mods(unconditional), unconditional, conditional, warnings


def clamp_attribute(value: int, max_value: int = DEFAULT_MAX_COUNCILOR_ATTRIBUTE) -> int:
    return max(0, min(value, max_value))


def councilor_attribute_breakdown(
    indexed: IndexedState,
    councilor: dict[str, Any],
    trait_templates: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    raw_attributes = councilor.get("attributes") if isinstance(councilor.get("attributes"), dict) else {}
    base_attributes = {
        attribute: int(raw_attributes.get(attribute, 0))
        for attribute in COUNCILOR_ATTRIBUTES
    }
    trait_totals, trait_details, conditional_details, warnings = trait_attribute_mods(
        councilor,
        trait_templates,
        base_attributes,
    )
    org_totals, org_details = org_attribute_mods(indexed, councilor)

    final_attributes: dict[str, int] = {}
    unclamped_attributes: dict[str, int] = {}
    clamped_max_attributes: dict[str, int] = {}
    for attribute in COUNCILOR_ATTRIBUTES:
        unclamped = base_attributes[attribute] + trait_totals.get(attribute, 0) + org_totals.get(attribute, 0)
        negative_mods = min(0, trait_totals.get(attribute, 0)) + min(0, org_totals.get(attribute, 0))
        clamped_max = DEFAULT_MAX_COUNCILOR_ATTRIBUTE + negative_mods
        unclamped_attributes[attribute] = unclamped
        clamped_max_attributes[attribute] = clamped_max
        final_attributes[attribute] = clamp_attribute(unclamped, clamped_max)

    conditional_potential = {attribute: final_attributes[attribute] for attribute in COUNCILOR_ATTRIBUTES}
    for mod in conditional_details:
        attribute = mod.get("attribute")
        contribution = mod.get("contribution")
        if attribute in conditional_potential and isinstance(contribution, int):
            conditional_potential[attribute] = clamp_attribute(
                conditional_potential[attribute] + contribution,
                clamped_max_attributes[attribute],
            )

    return {
        "baseAttributes": base_attributes,
        "traitAttributeMods": trait_totals,
        "orgAttributeMods": org_totals,
        "finalAttributes": final_attributes,
        "unclampedAttributes": unclamped_attributes,
        "clampedMaxAttributes": clamped_max_attributes,
        "conditionalPotentialAttributes": conditional_potential,
        "traitModDetails": trait_details,
        "conditionalTraitMods": conditional_details,
        "orgDetails": org_details,
        "calculationWarnings": warnings,
    }


def summarize_faction(indexed: IndexedState, entry: dict[str, Any], nation_by_id: dict[int, dict[str, Any]]) -> dict[str, Any]:
    faction = entry.get("Value") or {}
    state_id = ref_id(entry.get("Key")) or ref_id(faction.get("ID"))
    cp_refs = faction.get("controlPoints") if isinstance(faction.get("controlPoints"), list) else []
    nation_counts: dict[int, int] = {}
    for cp_ref in cp_refs:
        found = resolve_ref(indexed, cp_ref)
        if not found:
            continue
        cp_state = found[2]
        nation_ref = cp_state.get("nation")
        nation_id = ref_id(nation_ref)
        if nation_id is not None:
            nation_counts[nation_id] = nation_counts.get(nation_id, 0) + 1

    controlled_nations = []
    for nation_id, cp_count in nation_counts.items():
        nation = nation_by_id.get(nation_id)
        if not nation:
            continue
        controlled_nations.append(
            {
                "id": nation_id,
                "template": nation.get("template"),
                "code": nation.get("code"),
                "display": nation.get("display"),
                "ownedControlPoints": cp_count,
                "totalControlPoints": nation.get("numControlPoints"),
                "executiveOwner": nation.get("executiveOwner"),
                "GDP": nation.get("GDP"),
                "population_Millions": nation.get("population_Millions"),
                "unrest": nation.get("unrest"),
                "cohesion": nation.get("cohesion"),
            }
        )
    controlled_nations.sort(key=lambda item: (-item["ownedControlPoints"], str(item.get("display"))))

    resources = faction.get("resources") if isinstance(faction.get("resources"), dict) else {}
    base_incomes = faction.get("baseIncomes_year") if isinstance(faction.get("baseIncomes_year"), dict) else {}
    return clean_numbers(
        {
            "id": state_id,
            "template": faction.get("templateName"),
            "display": faction.get("displayName"),
            "player": ref_summary(indexed, faction.get("player")),
            "resources": {key: resources.get(key) for key in FACTION_RESOURCES if key in resources},
            "baseIncomes_year": {key: base_incomes.get(key) for key in FACTION_RESOURCES if key in base_incomes},
            "missionControlUsage": faction.get("missionControlUsage"),
            "resourceIncomeDeficiencies": faction.get("resourceIncomeDeficiencies"),
            "councilors": len(faction.get("councilors") or []),
            "controlPoints": len(cp_refs),
            "controlledNations": controlled_nations,
            "habSectors": len(faction.get("habSectors") or []),
            "fleets": len(faction.get("fleets") or []),
            "shipDesigns": len(faction.get("shipDesigns") or []),
            "finishedProjects": len(faction.get("finishedProjectNames") or []),
            "availableProjects": len(faction.get("availableProjectNames") or []),
            "assessedAlienHateOfMe": faction.get("assessedAlienHateOfMe"),
            "lastDateOfFixedAlienHate": faction.get("lastDateOfFixedAlienHate"),
            "cpOverageRecent": (faction.get("history_CPCapOverageByDay") or [None])[0],
            "cpOverageAverage32d": average(faction.get("history_CPCapOverageByDay")),
            "mcShortageRecent": (faction.get("history_MCCapOverageByDay") or [None])[0],
            "mcShortageAverage32d": average(faction.get("history_MCCapOverageByDay")),
        }
    )


def summarize_councilors(indexed: IndexedState, trait_templates: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for entry in type_entries(indexed, "TICouncilorState"):
        councilor = entry.get("Value") or {}
        faction = ref_summary(indexed, councilor.get("faction"))
        home_region = ref_summary(indexed, councilor.get("homeRegion"))
        location = ref_summary(indexed, councilor.get("location"))
        attributes = councilor_attribute_breakdown(indexed, councilor, trait_templates)
        result.append(
            clean_numbers(
                {
                    "id": ref_id(entry.get("Key")) or ref_id(councilor.get("ID")),
                    "template": councilor.get("templateName"),
                    "display": councilor.get("displayName"),
                    "faction": faction.get("template") if faction else None,
                    "factionDisplay": faction.get("display") if faction else None,
                    "location": location,
                    "locationNation": region_nation_summary(indexed, councilor.get("location")),
                    "homeRegion": home_region,
                    "homeNation": region_nation_summary(indexed, councilor.get("homeRegion")),
                    "active": councilor.get("active"),
                    "detained": councilor.get("detained"),
                    "turned": councilor.get("turned"),
                    "personalName": councilor.get("personalName"),
                    "familyName": councilor.get("familyName"),
                    "typeTemplateName": councilor.get("typeTemplateName"),
                    "traits": councilor.get("traitTemplateNames") or [],
                    "orgCount": len(councilor.get("orgs") or []),
                    "baseAttributes": attributes["baseAttributes"],
                    "traitAttributeMods": attributes["traitAttributeMods"],
                    "orgAttributeMods": attributes["orgAttributeMods"],
                    "finalAttributes": attributes["finalAttributes"],
                    "unclampedAttributes": attributes["unclampedAttributes"],
                    "clampedMaxAttributes": attributes["clampedMaxAttributes"],
                    "conditionalPotentialAttributes": attributes["conditionalPotentialAttributes"],
                    "traitModDetails": attributes["traitModDetails"],
                    "conditionalTraitMods": attributes["conditionalTraitMods"],
                    "orgDetails": attributes["orgDetails"],
                    "calculationWarnings": attributes["calculationWarnings"],
                }
            )
        )
    return result


def summarize_fleets(indexed: IndexedState) -> list[dict[str, Any]]:
    result = []
    for entry in type_entries(indexed, "TISpaceFleetState"):
        fleet = entry.get("Value") or {}
        faction = ref_summary(indexed, fleet.get("faction"))
        ships = fleet.get("ships") if isinstance(fleet.get("ships"), list) else []
        result.append(
            clean_numbers(
                {
                    "id": ref_id(entry.get("Key")) or ref_id(fleet.get("ID")),
                    "template": fleet.get("templateName"),
                    "display": fleet.get("displayName"),
                    "faction": faction.get("template") if faction else None,
                    "factionDisplay": faction.get("display") if faction else None,
                    "location": ref_summary(indexed, fleet.get("location") or fleet.get("orbit")),
                    "ships": len(ships),
                    "spaceCombatValue": fleet.get("spaceCombatValue") or fleet.get("_spaceCombatValue"),
                    "inTransfer": fleet.get("inTransfer"),
                    "arrivalDate": fleet.get("arrivalDate"),
                }
            )
        )
    return result


def build_snapshot(save_path: Path, data: dict[str, Any], templates_dir: Path | None) -> dict[str, Any]:
    indexed = build_index(data)
    trait_templates = load_trait_templates(templates_dir)
    type_counts = {
        short_type(full_type): len(entries) if isinstance(entries, list) else 1
        for full_type, entries in indexed.gamestates.items()
    }

    nations = [summarize_nation(indexed, entry) for entry in type_entries(indexed, "TINationState")]
    nation_by_id = {nation["id"]: nation for nation in nations if nation.get("id") is not None}
    factions = [summarize_faction(indexed, entry, nation_by_id) for entry in type_entries(indexed, "TIFactionState")]
    councilors = summarize_councilors(indexed, trait_templates)
    fleets = summarize_fleets(indexed)

    return {
        "schemaVersion": SCHEMA_VERSION,
        "cacheFingerprint": snapshot_fingerprint(save_path, templates_dir),
        "source": save_fingerprint(save_path),
        "templateSource": file_fingerprint(templates_dir / "TITraitTemplate.json" if templates_dir else None),
        "currentID": (data.get("currentID") or {}).get("value"),
        "time": time_summary(indexed),
        "metadata": metadata_summary(indexed),
        "global": global_summary(indexed),
        "typeCounts": dict(sorted(type_counts.items(), key=lambda item: (-item[1], item[0]))),
        "factions": factions,
        "nations": nations,
        "councilors": councilors,
        "fleets": fleets,
    }


def load_or_build_snapshot(
    save_path: Path,
    cache_dir: Path,
    templates_dir: Path | None,
    refresh: bool = False,
) -> tuple[dict[str, Any], Path, bool]:
    fingerprint = snapshot_fingerprint(save_path, templates_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / f"{cache_key(fingerprint)}.snapshot.json"
    if not refresh and path.is_file():
        with path.open("r", encoding="utf-8") as handle:
            cached = json.load(handle)
        if cached.get("schemaVersion") == SCHEMA_VERSION and cached.get("cacheFingerprint") == fingerprint:
            return cached, path, True

    data = load_save(save_path)
    snapshot = build_snapshot(save_path, data, templates_dir)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(snapshot, handle, ensure_ascii=False, separators=(",", ":"))
    return snapshot, path, False


def match_named(items: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    needle = name.casefold()
    exact_fields = ("template", "code", "display")
    for item in items:
        for field in exact_fields:
            value = item.get(field)
            if isinstance(value, str) and value.casefold() == needle:
                return item
    for item in items:
        for field in exact_fields:
            value = item.get(field)
            if isinstance(value, str) and needle in value.casefold():
                return item
    return None


def parse_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().casefold()
        if normalized in {"true", "1", "yes"}:
            return True
        if normalized in {"false", "0", "no"}:
            return False
    return None


def compare_condition(sign: str | None, actual: Any, expected: Any) -> bool | None:
    if actual is None or expected is None:
        return None
    sign = sign or "EqualTo"
    if sign == "EqualTo":
        return actual == expected
    if sign == "NotEqualTo":
        return actual != expected
    if isinstance(actual, bool) or isinstance(expected, bool):
        return None
    if sign == "GreaterThan":
        return actual > expected
    if sign == "GreaterThanOrEqualTo":
        return actual >= expected
    if sign == "LessThan":
        return actual < expected
    if sign == "LessThanOrEqualTo":
        return actual <= expected
    return None


def find_faction_for_councilor(snapshot: dict[str, Any], councilor: dict[str, Any]) -> dict[str, Any] | None:
    faction_name = councilor.get("faction") or councilor.get("factionDisplay")
    if not isinstance(faction_name, str):
        return None
    return match_named(snapshot.get("factions", []), faction_name)


def condition_eval_unknown(reason: str) -> dict[str, Any]:
    return {
        "conditionResult": None,
        "conditionActual": None,
        "conditionExpected": None,
        "conditionField": None,
        "conditionEvalNote": reason,
    }


def condition_nation_summary(nation: dict[str, Any] | None) -> dict[str, Any] | None:
    if nation is None:
        return None
    keys = ("id", "template", "code", "display", "unrest", "cohesion", "democracy", "education", "inequality")
    return {key: nation.get(key) for key in keys if key in nation}


def evaluate_condition(
    mod: dict[str, Any],
    councilor: dict[str, Any],
    snapshot: dict[str, Any],
    context_nation: dict[str, Any] | None,
) -> dict[str, Any]:
    condition = mod.get("condition") if isinstance(mod.get("condition"), dict) else {}
    condition_type = mod.get("conditionType") or condition.get("$type")
    sign = condition.get("sign")

    if condition_type in NATION_CONDITION_FIELDS:
        if context_nation is None:
            return condition_eval_unknown("nation-scoped condition needs --target-nation or --current-location-context")
        field = NATION_CONDITION_FIELDS[condition_type]
        actual = context_nation.get(field)
        expected = parse_modifier_number(condition.get("strValue"))
        return {
            "conditionResult": compare_condition(sign, actual, expected),
            "conditionActual": actual,
            "conditionExpected": expected,
            "conditionField": field,
            "conditionEvalNote": None,
        }

    if condition_type == "TICouncilorCondition_bInHomeNation":
        if context_nation is None:
            return condition_eval_unknown("home-nation condition needs --target-nation or --current-location-context")
        home_nation = councilor.get("homeNation") if isinstance(councilor.get("homeNation"), dict) else None
        actual = None
        if home_nation and home_nation.get("id") is not None and context_nation.get("id") is not None:
            actual = home_nation.get("id") == context_nation.get("id")
        expected = parse_bool(condition.get("strValue"))
        return {
            "conditionResult": compare_condition(sign, actual, expected),
            "conditionActual": actual,
            "conditionExpected": expected,
            "conditionField": "inHomeNation",
            "conditionEvalNote": None if actual is not None else "home nation or context nation is unavailable",
        }

    if condition_type == "TIFactionCondition_efResourceValue":
        faction = find_faction_for_councilor(snapshot, councilor)
        resource = condition.get("strIdx")
        actual = None
        if faction and isinstance(faction.get("resources"), dict) and isinstance(resource, str):
            actual = faction["resources"].get(resource)
        expected = parse_modifier_number(condition.get("strValue"))
        return {
            "conditionResult": compare_condition(sign, actual, expected),
            "conditionActual": actual,
            "conditionExpected": expected,
            "conditionField": f"resources.{resource}",
            "conditionEvalNote": None if actual is not None else "faction resource is unavailable",
        }

    if condition_type == "TIGlobalCondition_bNuclearWeaponsUsed":
        actual = (snapshot.get("global", {}).get("nuclearStrikes") or 0) > 0
        expected = parse_bool(condition.get("strValue"))
        return {
            "conditionResult": compare_condition(sign, actual, expected),
            "conditionActual": actual,
            "conditionExpected": expected,
            "conditionField": "global.nuclearStrikes>0",
            "conditionEvalNote": None,
        }

    return condition_eval_unknown(f"unsupported condition type: {condition_type}")


def apply_conditional_attribute_mods(
    final_attributes: dict[str, int],
    clamped_max_attributes: dict[str, int],
    active_mods: list[dict[str, Any]],
) -> tuple[dict[str, int], dict[str, int], dict[str, int]]:
    totals = sum_attr_mods(active_mods)
    contextual_attributes: dict[str, int] = {}
    contextual_max_attributes: dict[str, int] = {}
    for attribute in COUNCILOR_ATTRIBUTES:
        negative_mods = sum(
            mod["contribution"]
            for mod in active_mods
            if mod.get("attribute") == attribute and isinstance(mod.get("contribution"), int) and mod["contribution"] < 0
        )
        max_value = clamped_max_attributes.get(attribute, DEFAULT_MAX_COUNCILOR_ATTRIBUTE) + negative_mods
        contextual_max_attributes[attribute] = max_value
        contextual_attributes[attribute] = clamp_attribute(final_attributes.get(attribute, 0) + totals[attribute], max_value)
    return contextual_attributes, totals, contextual_max_attributes


def evaluate_councilor_conditionals(
    councilor: dict[str, Any],
    snapshot: dict[str, Any],
    context_nation: dict[str, Any] | None,
    context_label: str,
) -> dict[str, Any]:
    evaluated_mods = []
    warnings = []
    active_mods = []
    for mod in councilor.get("conditionalTraitMods") or []:
        if not isinstance(mod, dict):
            continue
        evaluated = dict(mod)
        evaluated.update(evaluate_condition(evaluated, councilor, snapshot, context_nation))
        evaluated_mods.append(evaluated)
        if evaluated.get("conditionResult") is True and evaluated.get("supported") and isinstance(evaluated.get("contribution"), int):
            active_mods.append(evaluated)
        elif evaluated.get("conditionResult") is None:
            warnings.append(
                f"{evaluated.get('trait')} {evaluated.get('attribute')}: {evaluated.get('conditionEvalNote')}"
            )

    contextual_attributes, totals, contextual_max_attributes = apply_conditional_attribute_mods(
        councilor.get("finalAttributes") or {},
        councilor.get("clampedMaxAttributes") or {},
        active_mods,
    )
    return {
        "conditionContext": {
            "mode": context_label,
            "nation": condition_nation_summary(context_nation),
        },
        "contextualAttributeMods": totals,
        "contextualMaxAttributes": contextual_max_attributes,
        "contextualAttributes": contextual_attributes,
        "evaluatedConditionalTraitMods": evaluated_mods,
        "conditionEvaluationWarnings": warnings,
    }


def councilor_summary_maps(
    indexed: IndexedState,
    trait_templates: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[int, dict[str, Any]]]:
    summaries = summarize_councilors(indexed, trait_templates)
    by_id = {
        summary["id"]: summary
        for summary in summaries
        if isinstance(summary.get("id"), int)
    }
    return summaries, by_id


def faction_councilor_ids(faction: dict[str, Any]) -> list[int]:
    refs = faction.get("councilors") if isinstance(faction.get("councilors"), list) else []
    return [state_id for state_id in (ref_id(item) for item in refs) if state_id is not None]


def councilor_is_income_active(councilor: dict[str, Any]) -> bool:
    return not councilor.get("detained") and not councilor.get("isAlien")


def councilor_monthly_income(
    indexed: IndexedState,
    councilor: dict[str, Any],
    trait_templates: dict[str, dict[str, Any]],
    final_attributes: dict[str, Any],
    resource: str,
) -> float:
    if not councilor_is_income_active(councilor):
        return 0.0
    fields = COUNCILOR_INCOME_FIELDS.get(resource)
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
) -> float:
    monthly = councilor_monthly_income(indexed, councilor, trait_templates, final_attributes, resource)
    if resource in {"Projects", "MissionControl"}:
        return monthly
    return monthly * 12.0


def councilor_resource_income(
    indexed: IndexedState,
    councilor: dict[str, Any],
    trait_templates: dict[str, dict[str, Any]],
    final_attributes: dict[str, Any],
    resource: str,
) -> float:
    return councilor_monthly_income(indexed, councilor, trait_templates, final_attributes, resource)


def councilor_research_and_mc(
    indexed: IndexedState,
    faction: dict[str, Any],
    trait_templates: dict[str, dict[str, Any]],
    councilor_by_id: dict[int, dict[str, Any]],
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
        research_month = councilor_resource_income(indexed, councilor, trait_templates, final_attributes, "Research")
        mc_capacity = int(councilor_resource_income(indexed, councilor, trait_templates, final_attributes, "MissionControl"))
        research_day = research_month * 12.0 / DAYS_PER_YEAR
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


def nation_allowed_armies(indexed: IndexedState, nation: dict[str, Any], population_millions: float) -> int:
    if not nation.get("military") or population_millions < MIN_POPULATION_FOR_FIRST_ARMY_MILLIONS:
        return 0
    population_limit = 1 + int(population_millions / MIN_POPULATION_FOR_ADDITIONAL_ARMIES_PER_MILLIONS)
    return min(nation_non_colony_unoccupied_region_count(indexed, nation), population_limit)


def nation_can_have_navy(nation: dict[str, Any], per_capita_gdp: float) -> bool:
    control_points = int(as_float(nation.get("numControlPoints"), 0.0))
    if control_points >= MIN_CONTROL_POINTS_FOR_NAVY:
        return True
    return control_points >= MIN_CONTROL_POINTS_FOR_NAVY_EXCEPTION and per_capita_gdp >= PCGDP_FOR_NAVY_EXCEPTION


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
    return pooled * (own_points ** 3) / denominator


def faction_ideology_key(faction: dict[str, Any]) -> str | None:
    template = faction.get("templateName")
    if isinstance(template, str):
        if template in FACTION_IDEOLOGY_BY_TEMPLATE:
            return FACTION_IDEOLOGY_BY_TEMPLATE[template]
        if template.endswith("Council"):
            return template.removesuffix("Council")
    return None


def faction_public_opinion(nation: dict[str, Any], faction: dict[str, Any]) -> float:
    public_opinion = nation.get("publicOpinion") if isinstance(nation.get("publicOpinion"), dict) else {}
    ideology = faction_ideology_key(faction)
    return as_float(public_opinion.get(ideology), 0.0) if ideology else 0.0


def nation_financial_sector_owned(indexed: IndexedState, nation: dict[str, Any], faction_id: int) -> bool:
    return any(
        cp.get("controlPointType") == "FinancialSector"
        and ref_id(cp.get("faction")) == faction_id
        and not cp.get("benefitsDisabled")
        for cp in nation_control_points(indexed, nation)
    )


def nation_money_contribution_month(indexed: IndexedState, nation: dict[str, Any], faction_id: int) -> float:
    owned_points = active_owned_control_points(indexed, nation, faction_id)
    num_control_points = int(as_float(nation.get("numControlPoints"), len(nation_control_points(indexed, nation))))
    if not owned_points or num_control_points <= 0:
        return 0.0
    monthly = nation_federation_pooled_year(indexed, nation, "Money") / 12.0
    if nation_financial_sector_owned(indexed, nation, faction_id):
        monthly *= DEFAULT_GLOBAL_CONFIG["financialSectorFundingBonus"]
    return monthly / num_control_points * len(owned_points)


def nation_boost_contribution_month(indexed: IndexedState, nation: dict[str, Any], faction_id: int) -> float:
    owned_points = active_owned_control_points(indexed, nation, faction_id)
    num_control_points = int(as_float(nation.get("numControlPoints"), len(nation_control_points(indexed, nation))))
    if not owned_points or num_control_points <= 0:
        return 0.0
    monthly = nation_federation_pooled_year(indexed, nation, "Boost") / 12.0
    return monthly / num_control_points * len(owned_points)


def nation_influence_contribution_month(indexed: IndexedState, nation: dict[str, Any], faction: dict[str, Any]) -> float:
    population = nation_population_millions(indexed, nation)
    return population * faction_public_opinion(nation, faction) * 0.5 / 12.0


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
    extra_advisor: tuple[int, float] | None = None,
) -> float:
    owned_points = active_owned_control_points(indexed, nation, faction_id)
    num_control_points = int(as_float(nation.get("numControlPoints"), len(nation_control_points(indexed, nation))))
    if not owned_points or num_control_points <= 0:
        return 0.0
    monthly_research = nation_monthly_research(indexed, nation, councilor_by_id, extra_advisor)
    if nation_has_owned_knowledge_sector(indexed, nation, faction_id):
        monthly_research *= DEFAULT_GLOBAL_CONFIG["knowledgeSectorResearchBonus"]
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


def hab_site_daily_production(hab_site: dict[str, Any] | None, resource: str) -> float:
    if not hab_site:
        return 0.0
    field = HAB_SITE_PRODUCTION_FIELDS.get(resource)
    return as_float(hab_site.get(field), 0.0) if field else 0.0


def faction_active_org_mining_bonus(indexed: IndexedState, faction: dict[str, Any]) -> float:
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
) -> float:
    if not faction:
        return 1.0
    value = 1.0 + faction_active_org_mining_bonus(indexed, faction)
    value = apply_effect_modifiers(effect_contexts, effect_templates, "SpaceMiningBonus", value)
    resource_context = MINING_BONUS_CONTEXTS.get(resource)
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
) -> float:
    if "MoneyIfNotBuilding" in hab_template_special_rules(template) and hab_has_construction:
        return 0.0
    field = HAB_INCOME_FIELDS.get(resource)
    income = as_float(template.get(field), 0.0) if field else 0.0
    if (
        resource in BASIC_SPACE_RESOURCES
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
        )
        income += (
            hab_site_daily_production(hab_site, resource)
            * as_float(template.get("miningModifier"), 1.0)
            * mining_multiplier
            * mining_rate
            * DAYS_PER_YEAR
            / 12.0
        )
    return income


def hab_template_direct_support(resource: str, template: dict[str, Any]) -> float:
    support = template.get("supportMaterials_month")
    if not isinstance(support, dict):
        return 0.0
    field = HAB_SUPPORT_FIELDS.get(resource)
    return as_float(support.get(field), 0.0) if field else 0.0


def hab_template_crew_support(resource: str, template: dict[str, Any]) -> float:
    crew = as_float(template.get("crew"), 0.0)
    rules = hab_template_special_rules(template)
    if resource == "Money":
        if "Stability" in rules:
            return 0.0
        return crew * DEFAULT_GLOBAL_CONFIG["crewSalary_year"] / 12.0
    if resource == "Water":
        return (
            crew
            * DEFAULT_GLOBAL_CONFIG["crewWaterConsumptionTons_year"]
            * DEFAULT_GLOBAL_CONFIG["spaceResourceToTons"]
            / 12.0
        )
    if resource == "Volatiles":
        return (
            crew
            * DEFAULT_GLOBAL_CONFIG["crewVolatilesConsumptionTons_year"]
            * DEFAULT_GLOBAL_CONFIG["spaceResourceToTons"]
            / 12.0
        )
    return 0.0


def hab_template_support(resource: str, template: dict[str, Any], include_crew_support: bool = True) -> float:
    total = hab_template_direct_support(resource, template)
    if include_crew_support:
        total += hab_template_crew_support(resource, template)
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
            )
            support += hab_template_support(resource, template, include_crew_support=True)
            if "Farm" in hab_template_special_rules(template):
                farm_discount += int(as_float(template.get("specialRulesValue"), 0.0))
        else:
            support += hab_template_crew_support(resource, template)

    if resource == "Water":
        covered_crew = min(farm_discount, crew)
        support -= (
            covered_crew
            * DEFAULT_GLOBAL_CONFIG["crewWaterConsumptionTons_year"]
            * DEFAULT_GLOBAL_CONFIG["spaceResourceToTons"]
            / 12.0
        )
    elif resource == "Volatiles":
        covered_crew = min(farm_discount, crew)
        support -= (
            covered_crew
            * DEFAULT_GLOBAL_CONFIG["crewVolatilesConsumptionTons_year"]
            * DEFAULT_GLOBAL_CONFIG["spaceResourceToTons"]
            / 12.0
        )

    if resource in HAB_ADMIN_ADVISER_RESOURCES:
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


def hab_leo_priority_bonuses(hab: dict[str, Any], records: list[dict[str, Any]]) -> dict[str, float]:
    if not hab.get("inEarthLEO"):
        return {}
    bonuses: dict[str, float] = {}
    for record in records:
        if not hab_module_active_record(record):
            continue
        template = record.get("template") if isinstance(record.get("template"), dict) else {}
        rules = hab_template_special_rules(template)
        for rule, priority in HAB_LEO_PRIORITY_RULES.items():
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
    administration_modifier = hab_administration_modifier(records)
    science_adviser_multiplier = 1.0 + state_adviser_attribute_bonus(hab, councilor_by_id, "Science")
    administration_adviser_multiplier = 1.0 + state_adviser_attribute_bonus(hab, councilor_by_id, "Administration")
    hab_site = state_value_by_id(indexed, ref_id(hab.get("habSite")))
    projected_crew = hab_crew(records)
    existing_farm_discount = hab_farm_crew_discount(records, any_core_completed=True)
    candidate_crew = int(as_float(template.get("crew"), 0.0))
    candidate_farm_discount = (
        int(as_float(template.get("specialRulesValue"), 0.0))
        if "Farm" in hab_template_special_rules(template)
        else 0
    )
    extra_farm_coverage = max(
        min(existing_farm_discount + candidate_farm_discount, projected_crew + candidate_crew)
        - min(existing_farm_discount, projected_crew),
        0,
    )

    deltas: dict[str, dict[str, float]] = {}
    for resource in HAB_MONTHLY_RESOURCES:
        income = hab_template_income(
            resource,
            template,
            False,
            indexed=indexed,
            faction=faction,
            hab_site=hab_site,
            effect_contexts=effect_contexts,
            effect_templates=effect_templates,
            mining_rate=mining_rate,
        )
        support = hab_template_support(resource, template, include_crew_support=True)
        if resource == "Water":
            support -= (
                extra_farm_coverage
                * DEFAULT_GLOBAL_CONFIG["crewWaterConsumptionTons_year"]
                * DEFAULT_GLOBAL_CONFIG["spaceResourceToTons"]
                / 12.0
            )
        elif resource == "Volatiles":
            support -= (
                extra_farm_coverage
                * DEFAULT_GLOBAL_CONFIG["crewVolatilesConsumptionTons_year"]
                * DEFAULT_GLOBAL_CONFIG["spaceResourceToTons"]
                / 12.0
            )

        if resource in HAB_ADMIN_ADVISER_RESOURCES:
            income *= administration_adviser_multiplier
            income *= administration_modifier
        elif resource == "Research":
            income *= science_adviser_multiplier
            income *= administration_modifier
        elif resource in {"Influence", "Operations", "Exotics"}:
            income *= administration_modifier
        support = max(support, 0.0)
        net = income - support
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


def suggested_fill_entry(candidate: dict[str, Any], count: int, reason: str) -> dict[str, Any]:
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
                plan = {
                    "score": plan_score,
                    "slotsFilled": slots_filled,
                    "powerAfter": power_after,
                    "mcAfter": mc_after,
                    "focusCandidate": focus_candidate,
                    "focusCount": focus_count,
                    "supportCandidate": support_candidate,
                    "supportCount": support_count,
                }
                if best_plan is None or (
                    plan["score"],
                    plan["focusCount"],
                    -plan["supportCount"],
                    plan["powerAfter"],
                ) > (
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
        suggested_fill_entry(best_plan["focusCandidate"], best_plan["focusCount"], f"top {focus} score"),
    ]
    add_monthly_delta(monthly_total, best_plan["focusCandidate"].get("monthlyDelta") or {}, best_plan["focusCount"])
    if best_plan["supportCandidate"] and best_plan["supportCount"]:
        entries.append(
            suggested_fill_entry(
                best_plan["supportCandidate"],
                best_plan["supportCount"],
                "power support for selected fill",
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
            "method": "single focus module type plus optional single power-support type",
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


def calculate_research_breakdown(
    indexed: IndexedState,
    templates_dir: Path | None,
    faction_name: str | None = None,
    include_details: bool = False,
) -> dict[str, Any]:
    trait_templates = load_trait_templates(templates_dir)
    effect_templates = load_named_templates(templates_dir, "TIEffectTemplate.json")
    hab_module_templates = load_named_templates(templates_dir, "TIHabModuleTemplate.json")
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
) -> float:
    name = faction.get("templateName") or faction.get("displayName")
    if not name or faction.get("templateName") == "AlienCouncil":
        return 0.0
    return as_float(calculate_research_breakdown(indexed, templates_dir, str(name), include_details=False)["daily"]["beforeDistribution"], 0.0)


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
) -> dict[str, Any]:
    trait_templates = load_trait_templates(templates_dir)
    org_templates = load_named_templates(templates_dir, "TIOrgTemplate.json")
    hab_module_templates = load_named_templates(templates_dir, "TIHabModuleTemplate.json")
    utility_module_templates = load_named_templates(templates_dir, "TIUtilityModuleTemplate.json")
    tech_templates = load_named_templates(templates_dir, "TITechTemplate.json")
    project_templates = load_named_templates(templates_dir, "TIProjectTemplate.json")

    faction_id, faction = find_faction_state(indexed, faction_name)
    selected_base_daily = faction_base_research_daily(indexed, templates_dir, faction)
    all_human_factions = [
        (other_id, other, faction_base_research_daily(indexed, templates_dir, other))
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
) -> dict[str, Any]:
    trait_templates = load_trait_templates(templates_dir)
    effect_templates = load_named_templates(templates_dir, "TIEffectTemplate.json")
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
            research = calculate_research_breakdown(indexed, templates_dir, faction_name, include_details=include_details)
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
    parser = argparse.ArgumentParser(description="Parse Terra Invicta saves into compact summaries.")
    parser.add_argument("--save", help="Path to a .gz Terra Invicta save. Defaults to newest local save.")
    parser.add_argument("--templates-dir", help="Path to TerraInvicta_Data\\StreamingAssets\\Templates.")
    parser.add_argument("--cache-dir", default=DEFAULT_CACHE_DIR, help="Directory for compact parser cache.")
    parser.add_argument("--refresh-cache", action="store_true", help="Ignore and rebuild the compact cache.")
    parser.add_argument("--compact", action="store_true", help="Print compact JSON.")

    subparsers = parser.add_subparsers(dest="command", required=False)

    def add_compact_flag(subparser: argparse.ArgumentParser) -> None:
        subparser.add_argument("--compact", action="store_true", default=argparse.SUPPRESS, help="Print compact JSON.")

    summary = subparsers.add_parser("summary", help="Print compact campaign summary.")
    summary.add_argument("--top-nations", type=int, default=20)
    add_compact_flag(summary)

    faction = subparsers.add_parser("faction", help="Print one faction summary.")
    faction.add_argument("name")
    faction.add_argument("--limit", type=int, default=50, help="Maximum controlled nations to include.")
    add_compact_flag(faction)

    nation = subparsers.add_parser("nation", help="Print one nation summary.")
    nation.add_argument("name")
    add_compact_flag(nation)

    councilor = subparsers.add_parser("councilor", help="Print one councilor summary with calculated attributes.")
    councilor.add_argument("name")
    councilor.add_argument("--details", action="store_true", help="Include trait/org calculation detail lists.")
    councilor.add_argument("--target-nation", help="Evaluate conditional trait modifiers against this target nation.")
    councilor.add_argument(
        "--current-location-context",
        action="store_true",
        help="Evaluate conditional trait modifiers against the councilor's current location nation.",
    )
    add_compact_flag(councilor)

    research = subparsers.add_parser("research", help="Calculate faction research income from raw save values.")
    research.add_argument("faction", nargs="?", help="Faction template/display/code. Defaults to the player faction.")
    research.add_argument("--details", action="store_true", help="Include nation/councilor/hab source details.")
    add_compact_flag(research)

    research_ui = subparsers.add_parser("research-ui", help="Reconstruct the Research screen's active global techs and projects.")
    research_ui.add_argument("faction", nargs="?", help="Faction template/display/code. Defaults to the player faction.")
    add_compact_flag(research_ui)

    topbar = subparsers.add_parser("topbar", help="Reconstruct the top resource bar values for a faction.")
    topbar.add_argument("faction", nargs="?", help="Faction template/display/code. Defaults to the player faction.")
    topbar.add_argument("--details", action="store_true", help="Include yearly source components for each resource.")
    add_compact_flag(topbar)

    advise = subparsers.add_parser("advise", help="Estimate research change from assigning a councilor to Advise a nation.")
    advise.add_argument("councilor")
    advise.add_argument("nation")
    advise.add_argument("--faction", help="Faction template/display/code. Defaults to the player faction.")
    add_compact_flag(advise)

    nation_ui = subparsers.add_parser("nation-ui", help="Calculate nation UI panel values from raw save values.")
    nation_ui.add_argument("name")
    nation_ui.add_argument("--faction", help="Faction template/display/code for faction-share fields. Defaults to player.")
    add_compact_flag(nation_ui)

    world_ui = subparsers.add_parser("world-ui", help="Calculate the Intel world data panel from raw save values.")
    world_ui.add_argument("--faction", help="Faction template/display/code for sell-value modifiers. Defaults to player.")
    add_compact_flag(world_ui)

    hab_ui = subparsers.add_parser("hab-ui", help="Calculate hab UI panel values from raw save values.")
    hab_ui.add_argument("name")
    add_compact_flag(hab_ui)

    hab_slots = subparsers.add_parser("hab-slots", help="List habs with currently usable empty slots.")
    hab_slots.add_argument("--faction", help="Faction template/display/code. Defaults to the player faction.")
    hab_slots.add_argument("--all", action="store_true", help="Include habs with zero usable empty slots.")
    hab_slots.add_argument("--module-counts", action="store_true", help="Include per-hab module template counts.")
    add_compact_flag(hab_slots)

    hab_plan = subparsers.add_parser("hab-plan", help="Recommend module candidates for current or future hab slots.")
    hab_plan.add_argument("name", nargs="?", help="Specific hab name/id fragment. Omit to scan faction habs.")
    hab_plan.add_argument("--faction", help="Faction template/display/code. Defaults to the player faction.")
    hab_plan.add_argument("--upgrading-to-tier", type=int, help="Only include habs whose core is upgrading to this tier.")
    hab_plan.add_argument("--focus", choices=HAB_PLAN_FOCUS_CHOICES, default="balanced")
    hab_plan.add_argument("--top", type=int, default=8, help="Candidate rows per category.")
    hab_plan.add_argument("--all", action="store_true", help="Include habs with no planned empty slots.")
    add_compact_flag(hab_plan)

    types = subparsers.add_parser("types", help="Print gamestate type counts.")
    types.add_argument("--limit", type=int, default=0)
    add_compact_flag(types)

    export = subparsers.add_parser("export", help="Export the compact snapshot.")
    export.add_argument("--output", required=True)
    add_compact_flag(export)

    raw = subparsers.add_parser("raw", help="Read selected raw gamestate entries from the save.")
    raw.add_argument("--type", required=True, help="Short or full gamestate type name.")
    raw.add_argument("--id", type=int)
    raw.add_argument("--template")
    raw.add_argument("--display")
    raw.add_argument("--keys", help="Comma-separated keys to include.")
    raw.add_argument("--limit", type=int, default=5)
    add_compact_flag(raw)

    cache = subparsers.add_parser("cache", help="Build or validate the compact cache.")
    cache.set_defaults(cache_command=True)
    add_compact_flag(cache)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    command = args.command or "summary"

    try:
        save_path = resolve_save_path(args.save)
        templates_dir = resolve_templates_dir(args.templates_dir)
        if command == "raw":
            command_raw(save_path, args)
            return 0
        if command == "research":
            command_research(save_path, templates_dir, args)
            return 0
        if command == "research-ui":
            command_research_ui(save_path, templates_dir, args)
            return 0
        if command == "topbar":
            command_topbar(save_path, templates_dir, args)
            return 0
        if command == "advise":
            command_advise(save_path, templates_dir, args)
            return 0
        if command == "nation-ui":
            command_nation_ui(save_path, templates_dir, args)
            return 0
        if command == "world-ui":
            command_world_ui(save_path, templates_dir, args)
            return 0
        if command == "hab-ui":
            command_hab_ui(save_path, templates_dir, args)
            return 0
        if command == "hab-slots":
            command_hab_slots(save_path, templates_dir, args)
            return 0
        if command == "hab-plan":
            command_hab_plan(save_path, templates_dir, args)
            return 0

        snapshot, cache_path_value, cache_hit = load_or_build_snapshot(
            save_path,
            Path(args.cache_dir),
            templates_dir,
            refresh=args.refresh_cache,
        )
        if command == "summary":
            command_summary(snapshot, args)
        elif command == "faction":
            command_faction(snapshot, args)
        elif command == "nation":
            command_nation(snapshot, args)
        elif command == "councilor":
            command_councilor(snapshot, args)
        elif command == "types":
            command_types(snapshot, args)
        elif command == "export":
            command_export(snapshot, args)
        elif command == "cache":
            print_json(
                {
                    "cache": str(cache_path_value),
                    "cacheHit": cache_hit,
                    "source": snapshot.get("source"),
                    "templateSource": snapshot.get("templateSource"),
                    "schemaVersion": snapshot.get("schemaVersion"),
                },
                compact=args.compact,
            )
        else:
            parser.error(f"Unknown command: {command}")
    except BrokenPipeError:
        return 1
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
