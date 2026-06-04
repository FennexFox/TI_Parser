"""Build a standalone all-drive comparison dashboard from local TI data."""

from __future__ import annotations

import argparse
import copy
import json
import math
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from ti_parser_core import as_float, load_named_templates, resolve_templates_dir  # noqa: E402
from ti_save_parser import (  # noqa: E402
    ship_plan_drive_open_cycle,
    ship_plan_drive_power_requirement_gw,
    ship_plan_drive_thrust_power_gw,
    ship_plan_power_plant_class_compatible,
)


STANDARD_GRAVITY_MPS2 = 9.80665
TARGET_DV_KPS = 1000.0
DEFAULT_DRY_MASS_TONS = 1000.0

CATEGORY_ORDER = ("Chemical", "Electric", "Fission", "Fusion", "Antimatter", "Alien")
DEFAULT_CATEGORY_KEY = "Fusion"
SELF_POWERED_POWER_KEY = "Self_Contained"

CATEGORY_META: dict[str, dict[str, Any]] = {
    "Chemical": {"label": {"ko": "화학", "en": "Chemical"}, "color": "#d38b28", "colorOklch": "oklch(70% 0.145 65)"},
    "Electric": {"label": {"ko": "전기", "en": "Electric"}, "color": "#0891b2", "colorOklch": "oklch(66% 0.135 220)"},
    "Fission": {"label": {"ko": "핵분열", "en": "Fission"}, "color": "#65a30d", "colorOklch": "oklch(66% 0.150 135)"},
    "Fusion": {"label": {"ko": "핵융합", "en": "Fusion"}, "color": "#7c3aed", "colorOklch": "oklch(66% 0.165 300)"},
    "Antimatter": {"label": {"ko": "반물질", "en": "Antimatter"}, "color": "#db2777", "colorOklch": "oklch(66% 0.180 350)"},
    "Alien": {"label": {"ko": "외계", "en": "Alien"}, "color": "#71717a", "colorOklch": "oklch(62% 0.035 285)"},
}

SUBFAMILY_META: dict[tuple[str, str], dict[str, Any]] = {
    ("Chemical", "Chemical"): {
        "label": {"ko": "Chemical", "en": "Chemical"},
        "color": "#d28d2d",
        "colorOklch": "oklch(70% 0.145 65)",
        "bandColor": "#e0a24a",
        "bandColorOklch": "oklch(75% 0.140 70)",
    },
    ("Electric", "Electromagnetic"): {
        "label": {"ko": "Electromagnetic", "en": "Electromagnetic"},
        "color": "#2563eb",
        "colorOklch": "oklch(62% 0.175 260)",
        "bandColor": "#4e8ffb",
        "bandColorOklch": "oklch(68% 0.165 260)",
    },
    ("Electric", "Electrostatic"): {
        "label": {"ko": "Electrostatic", "en": "Electrostatic"},
        "color": "#0891b2",
        "colorOklch": "oklch(65% 0.135 220)",
        "bandColor": "#00abbd",
        "bandColorOklch": "oklch(70% 0.130 215)",
    },
    ("Electric", "Electrothermal"): {
        "label": {"ko": "Electrothermal", "en": "Electrothermal"},
        "color": "#0d9488",
        "colorOklch": "oklch(65% 0.135 185)",
        "bandColor": "#14b8a6",
        "bandColorOklch": "oklch(71% 0.130 185)",
    },
    ("Fission", "Solid_Core_Fission"): {
        "label": {"ko": "Solid Core", "en": "Solid Core"},
        "color": "#4d7c0f",
        "colorOklch": "oklch(58% 0.135 135)",
        "bandColor": "#65a30d",
        "bandColorOklch": "oklch(66% 0.145 135)",
    },
    ("Fission", "Liquid_Core_Fission"): {
        "label": {"ko": "Liquid Core", "en": "Liquid Core"},
        "color": "#15803d",
        "colorOklch": "oklch(58% 0.130 150)",
        "bandColor": "#22a35a",
        "bandColorOklch": "oklch(66% 0.135 150)",
    },
    ("Fission", "Gas_Core_Fission"): {
        "label": {"ko": "Gas Core", "en": "Gas Core"},
        "color": "#0f766e",
        "colorOklch": "oklch(58% 0.120 175)",
        "bandColor": "#14a092",
        "bandColorOklch": "oklch(66% 0.125 175)",
    },
    ("Fission", "Fission_Pulse"): {
        "label": {"ko": "Fission Pulse", "en": "Fission Pulse"},
        "color": "#a16207",
        "colorOklch": "oklch(58% 0.130 80)",
        "bandColor": "#ca8a04",
        "bandColorOklch": "oklch(68% 0.135 80)",
    },
    ("Fission", "NuclearSaltWater"): {
        "label": {"ko": "Nuclear Salt Water", "en": "Nuclear Salt Water"},
        "color": "#047857",
        "colorOklch": "oklch(58% 0.125 165)",
        "bandColor": "#10a27a",
        "bandColorOklch": "oklch(66% 0.130 165)",
    },
    ("Fusion", "Electrostatic_Confinement_Fusion"): {
        "label": {"ko": "Fusor / Electrostatic", "en": "Fusor / Electrostatic"},
        "color": "#2563eb",
        "colorOklch": "oklch(62% 0.175 260)",
        "bandColor": "#4e8ffb",
        "bandColorOklch": "oklch(66% 0.175 260)",
    },
    ("Fusion", "Mirrored_Magnetic_Confinement_Fusion"): {
        "label": {"ko": "Reflex / Mirror Cell", "en": "Reflex / Mirror Cell"},
        "color": "#0891b2",
        "colorOklch": "oklch(62% 0.145 205)",
        "bandColor": "#00abbd",
        "bandColorOklch": "oklch(66% 0.150 205)",
    },
    ("Fusion", "Toroid_Magnetic_Confinement_Fusion"): {
        "label": {"ko": "Torus / Tokamak", "en": "Torus / Tokamak"},
        "color": "#7c3aed",
        "colorOklch": "oklch(62% 0.170 310)",
        "bandColor": "#b270df",
        "bandColorOklch": "oklch(66% 0.170 310)",
    },
    ("Fusion", "Hybrid_Confinement_Fusion"): {
        "label": {"ko": "Polywell-Plasmajet / Hybrid", "en": "Polywell-Plasmajet / Hybrid"},
        "color": "#059669",
        "colorOklch": "oklch(62% 0.155 150)",
        "bandColor": "#38ac5c",
        "bandColorOklch": "oklch(66% 0.155 150)",
    },
    ("Fusion", "Z_Pinch_Fusion"): {
        "label": {"ko": "Zeta / Z-Pinch", "en": "Zeta / Z-Pinch"},
        "color": "#dc2626",
        "colorOklch": "oklch(62% 0.170 25)",
        "bandColor": "#e8605b",
        "bandColorOklch": "oklch(66% 0.170 25)",
    },
    ("Fusion", "Inertial_Confinement_Fusion"): {
        "label": {"ko": "Nova / Inertial", "en": "Nova / Inertial"},
        "color": "#ca8a04",
        "colorOklch": "oklch(64% 0.150 75)",
        "bandColor": "#d58e00",
        "bandColorOklch": "oklch(70% 0.155 75)",
    },
    ("Fusion", "Fusion_Pulse"): {
        "label": {"ko": "Fusion Pulse", "en": "Fusion Pulse"},
        "color": "#9333ea",
        "colorOklch": "oklch(62% 0.165 300)",
        "bandColor": "#b36cf2",
        "bandColorOklch": "oklch(68% 0.160 300)",
    },
    ("Antimatter", "Antimatter_Plasma_Core"): {
        "label": {"ko": "Antimatter Plasma Core", "en": "Antimatter Plasma Core"},
        "color": "#db2777",
        "colorOklch": "oklch(62% 0.175 350)",
        "bandColor": "#ef5b9c",
        "bandColorOklch": "oklch(68% 0.170 350)",
    },
    ("Antimatter", "Antimatter_Beam_Core"): {
        "label": {"ko": "Antimatter Beam Core", "en": "Antimatter Beam Core"},
        "color": "#be185d",
        "colorOklch": "oklch(58% 0.170 5)",
        "bandColor": "#e05282",
        "bandColorOklch": "oklch(66% 0.165 5)",
    },
    ("Alien", "Alien"): {
        "label": {"ko": "Alien", "en": "Alien"},
        "color": "#71717a",
        "colorOklch": "oklch(62% 0.035 285)",
        "bandColor": "#83839e",
        "bandColorOklch": "oklch(62% 0.040 285)",
    },
}


class ResearchCostIndex:
    def __init__(self, catalog_path: Path) -> None:
        with catalog_path.open("r", encoding="utf-8-sig") as handle:
            catalog = json.load(handle)
        self.catalog = catalog
        self.nodes: dict[str, dict[str, Any]] = {
            str(node.get("dataName")): node
            for node in catalog.get("nodes", [])
            if isinstance(node, dict) and node.get("dataName")
        }
        self._closure_cache: dict[str, frozenset[str]] = {}

    def node(self, name: str | None) -> dict[str, Any] | None:
        if not name:
            return None
        return self.nodes.get(str(name))

    def display(self, name: str | None) -> dict[str, str | None]:
        node = self.node(name)
        if not node:
            return {"ko": None, "en": str(name) if name else None}
        display = node.get("displayName") if isinstance(node.get("displayName"), dict) else {}
        return {
            "ko": display.get("kor") or node.get("friendlyName") or name,
            "en": display.get("en") or node.get("friendlyName") or name,
        }

    def own_cost(self, name: str | None) -> float:
        node = self.node(name)
        return max(0.0, as_float(node.get("researchCost"), 0.0)) if node else 0.0

    def closure(self, name: str | None) -> frozenset[str]:
        if not name or name not in self.nodes:
            return frozenset()
        return self._closure(name, frozenset())

    def cumulative_cost(self, name: str | None) -> float:
        return sum(self.own_cost(node_name) for node_name in self.closure(name))

    def _closure(self, name: str, stack: frozenset[str]) -> frozenset[str]:
        if name in self._closure_cache:
            return self._closure_cache[name]
        if name in stack:
            return frozenset({name})
        node = self.nodes.get(name)
        if not node:
            return frozenset()
        result = {name}
        result.update(self._requirements_closure(node.get("requirements"), stack | {name}))
        frozen = frozenset(result)
        self._closure_cache[name] = frozen
        return frozen

    def _requirements_closure(self, requirement: Any, stack: frozenset[str]) -> set[str]:
        if isinstance(requirement, list):
            result: set[str] = set()
            for item in requirement:
                result.update(self._requirements_closure(item, stack))
            return result
        if not isinstance(requirement, dict):
            return set()
        if requirement.get("node"):
            return set(self._closure(str(requirement["node"]), stack))
        if isinstance(requirement.get("all"), list):
            result: set[str] = set()
            for item in requirement["all"]:
                result.update(self._requirements_closure(item, stack))
            return result
        if isinstance(requirement.get("any"), list):
            choices = [
                self._requirements_closure(item, stack)
                for item in requirement["any"]
            ]
            if not choices:
                return set()
            return min(choices, key=lambda choice: sum(self.own_cost(node_name) for node_name in choice))
        return set()


def remove_thruster_suffix(data_name: str, display: str) -> tuple[str, str, int | None]:
    match = re.match(r"^(.*)x([1-6])$", data_name)
    if not match:
        return data_name, display, None
    base_key = match.group(1)
    count = int(match.group(2))
    base_display = re.sub(r"\s+x[1-6]$", "", display).strip()
    return base_key, base_display or base_key, count


def is_alien_component(template: dict[str, Any]) -> bool:
    values = " ".join(
        str(template.get(key) or "")
        for key in ("dataName", "friendlyName", "requiredProjectName", "powerPlantClass")
    )
    return "alien" in values.casefold()


def label_text(value: dict[str, str] | str, lang: str = "ko") -> str:
    if isinstance(value, dict):
        return value.get(lang) or value.get("en") or value.get("ko") or ""
    return str(value)


def drive_category_key(classification: str, alien: bool) -> str:
    if alien:
        return "Alien"
    if classification == "Chemical":
        return "Chemical"
    if classification in {"Electromagnetic", "Electrostatic", "Electrothermal"}:
        return "Electric"
    if classification in {"Fission_Thermal", "Fission_Pulse", "NuclearSaltWater"}:
        return "Fission"
    if classification in {"Fusion_Thermal", "Fusion_Pulse"}:
        return "Fusion"
    if classification == "Antimatter":
        return "Antimatter"
    return "Electric"


def drive_subfamily_key(classification: str, required_power_plant: str, category_key: str, alien: bool) -> str:
    if alien:
        return "Alien"
    if category_key in {"Chemical", "Electric"}:
        return classification or category_key
    if classification == "Fission_Thermal":
        return required_power_plant or "Fission_Thermal"
    if classification in {"Fission_Pulse", "NuclearSaltWater", "Fusion_Pulse"}:
        return classification
    if category_key in {"Fusion", "Antimatter"}:
        return required_power_plant or classification or category_key
    return required_power_plant or classification or category_key


def subfamily_meta(category_key: str, subfamily_key: str) -> dict[str, Any]:
    meta = SUBFAMILY_META.get((category_key, subfamily_key))
    if meta:
        return meta
    category = CATEGORY_META.get(category_key, CATEGORY_META["Electric"])
    fallback_label = subfamily_key.replace("_", " ") if subfamily_key else category_key
    return {
        "label": {"ko": fallback_label, "en": fallback_label},
        "color": category["color"],
        "colorOklch": category["colorOklch"],
        "bandColor": category["color"],
        "bandColorOklch": category["colorOklch"],
    }


def category_sort_key(category_key: str) -> int:
    try:
        return CATEGORY_ORDER.index(category_key)
    except ValueError:
        return len(CATEGORY_ORDER)


def self_contained_power_option(drive_cumulative: float) -> dict[str, Any]:
    return {
        "id": SELF_POWERED_POWER_KEY,
        "displayName": "Self-contained drive",
        "powerPlantClass": SELF_POWERED_POWER_KEY,
        "maxOutputGW": 0.0,
        "specificMassTonsPerGW": 0.0,
        "efficiency": 1.0,
        "crew": 0.0,
        "requiredProject": None,
        "requiredProjectDisplay": {"ko": "자체동력 추진기", "en": "Self-contained drive"},
        "ownResearchCost": 0.0,
        "cumulativeResearch": drive_cumulative,
        "alien": False,
        "sequenceIndex": 0,
        "sequenceLabel": "self-contained drive",
        "selfContained": True,
    }


def power_option_hardware_key(drive: dict[str, Any], option: dict[str, Any]) -> tuple[float, float]:
    power_requirement = as_float(drive.get("powerRequirementGW"), 0.0)
    reactor_mass = 0.0 if option.get("selfContained") else max(
        1.0,
        as_float(option.get("specificMassTonsPerGW"), 0.0) * power_requirement,
    )
    waste_heat = 0.0 if drive.get("openCycleCooling") or option.get("selfContained") else power_requirement * (
        1.0 - as_float(option.get("efficiency"), 0.0)
    )
    return reactor_mass, max(0.0, waste_heat)


def prune_efficiency_frontier(drive: dict[str, Any], sequence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if str(drive.get("requiredPowerPlantClass") or "") != "Any_General":
        return sequence
    if as_float(drive.get("powerRequirementGW"), 0.0) <= 0.0:
        return sequence
    frontier: list[dict[str, Any]] = []
    for option in sequence:
        option_mass, option_heat = power_option_hardware_key(drive, option)
        dominated = False
        for kept in frontier:
            kept_mass, kept_heat = power_option_hardware_key(drive, kept)
            if kept_mass <= option_mass and kept_heat <= option_heat and (kept_mass < option_mass or kept_heat < option_heat):
                dominated = True
                break
        if not dominated:
            frontier.append(option)
    return frontier


def reactor_row(template: dict[str, Any], research: ResearchCostIndex) -> dict[str, Any]:
    project = template.get("requiredProjectName")
    cumulative = research.cumulative_cost(str(project) if project else None)
    return {
        "id": template.get("dataName"),
        "displayName": template.get("friendlyName") or template.get("dataName"),
        "powerPlantClass": template.get("powerPlantClass"),
        "maxOutputGW": as_float(template.get("maxOutput_GW"), 0.0),
        "specificMassTonsPerGW": as_float(template.get("specificPower_tGW"), 0.0),
        "efficiency": as_float(template.get("efficiency"), 0.0),
        "crew": as_float(template.get("crew"), 0.0),
        "requiredProject": project,
        "requiredProjectDisplay": research.display(str(project) if project else None),
        "ownResearchCost": research.own_cost(str(project) if project else None),
        "cumulativeResearch": cumulative,
        "alien": is_alien_component(template),
    }


def radiator_row(template: dict[str, Any], research: ResearchCostIndex) -> dict[str, Any]:
    project = template.get("requiredProjectName")
    return {
        "id": template.get("dataName"),
        "displayName": template.get("friendlyName") or template.get("dataName"),
        "radiatorType": template.get("radiatorType"),
        "specificPowerKWPerKg": as_float(template.get("specificPower_2s_KWkg"), 0.0),
        "requiredProject": project,
        "requiredProjectDisplay": research.display(str(project) if project else None),
        "ownResearchCost": research.own_cost(str(project) if project else None),
        "cumulativeResearch": research.cumulative_cost(str(project) if project else None),
        "alien": is_alien_component(template),
    }


def compatible_power_sequence(
    drive: dict[str, Any],
    power_plants: list[dict[str, Any]],
    unlock_closure: frozenset[str],
    drive_cumulative: float,
) -> list[dict[str, Any]]:
    if as_float(drive.get("powerRequirementGW"), 0.0) <= 0.0:
        return [self_contained_power_option(drive_cumulative)]
    drive_alien = bool(drive["alien"])
    compatible = [
        plant
        for plant in power_plants
        if bool(plant["alien"]) == drive_alien
        and ship_plan_power_plant_class_compatible(
            str(drive["requiredPowerPlantClass"] or ""),
            str(plant["powerPlantClass"] or ""),
        )
        and as_float(plant["maxOutputGW"], 0.0) >= as_float(drive["powerRequirementGW"], 0.0)
    ]
    if not compatible and drive_alien:
        compatible = [
            plant
            for plant in power_plants
            if ship_plan_power_plant_class_compatible(
                str(drive["requiredPowerPlantClass"] or ""),
                str(plant["powerPlantClass"] or ""),
            )
            and as_float(plant["maxOutputGW"], 0.0) >= as_float(drive["powerRequirementGW"], 0.0)
        ]
    compatible = sorted(
        compatible,
        key=lambda plant: (
            as_float(plant["cumulativeResearch"], math.inf),
            as_float(plant["specificMassTonsPerGW"], math.inf),
            str(plant["displayName"]),
        ),
    )
    if not compatible:
        return []

    closure_matches = [
        plant
        for plant in compatible
        if plant.get("requiredProject") in unlock_closure
    ]
    if closure_matches:
        lower = max(closure_matches, key=lambda plant: as_float(plant["cumulativeResearch"], 0.0))
    else:
        already_available = [
            plant
            for plant in compatible
            if as_float(plant["cumulativeResearch"], math.inf) <= drive_cumulative
        ]
        lower = max(already_available, key=lambda plant: as_float(plant["cumulativeResearch"], 0.0)) if already_available else compatible[0]

    lower_cost = as_float(lower["cumulativeResearch"], 0.0)
    sequence = [
        {**plant}
        for plant in compatible
        if as_float(plant["cumulativeResearch"], 0.0) >= lower_cost
    ]
    sequence = prune_efficiency_frontier(drive, sequence)
    for index, plant in enumerate(sequence):
        plant["sequenceIndex"] = index
        plant["sequenceLabel"] = "unlock power plant" if index == 0 else f"+{index} power step"
    return sequence


def build_data(templates_dir: Path, research_catalog_path: Path) -> dict[str, Any]:
    research = ResearchCostIndex(research_catalog_path)
    drive_templates = load_named_templates(templates_dir, "TIDriveTemplate.json")
    power_plant_templates = load_named_templates(templates_dir, "TIPowerPlantTemplate.json")
    radiator_templates = load_named_templates(templates_dir, "TIRadiatorTemplate.json")

    power_plants = [
        reactor_row(template, research)
        for template in power_plant_templates.values()
        if not template.get("disable")
    ]
    radiators = sorted(
        [
            radiator_row(template, research)
            for template in radiator_templates.values()
            if (
                not template.get("disable")
                and not is_alien_component(template)
                and as_float(template.get("specificPower_2s_KWkg"), 0.0) > 0.0
            )
        ],
        key=lambda row: (-as_float(row["specificPowerKWPerKg"], 0.0), str(row["displayName"])),
    )
    default_radiator = next(
        (row for row in radiators if row.get("id") == "DustyPlasma"),
        max(radiators, key=lambda row: as_float(row["specificPowerKWPerKg"], 0.0), default=None),
    )

    drive_rows: list[dict[str, Any]] = []
    for template in drive_templates.values():
        if template.get("disable"):
            continue
        data_name = str(template.get("dataName") or "")
        display = str(template.get("friendlyName") or data_name)
        base_key, base_display, thruster_count = remove_thruster_suffix(data_name, display)
        if thruster_count is None:
            continue

        classification = str(template.get("driveClassification") or "")
        project = str(template.get("requiredProjectName") or "")
        cumulative = research.cumulative_cost(project)
        closure = research.closure(project)
        thrust_power_gw = ship_plan_drive_thrust_power_gw(template)
        power_requirement_gw = ship_plan_drive_power_requirement_gw(template)
        required_power_class = str(template.get("requiredPowerPlant") or "")
        alien = is_alien_component(template)
        category_key = drive_category_key(classification, alien)
        subfamily_key = drive_subfamily_key(classification, required_power_class, category_key, alien)
        family_key = f"{category_key}:{subfamily_key}"
        meta = subfamily_meta(category_key, subfamily_key)
        category_meta = CATEGORY_META.get(category_key, CATEGORY_META["Electric"])
        power_band_key = SELF_POWERED_POWER_KEY if power_requirement_gw <= 0.0 else required_power_class
        drive_mass_tons = as_float(template.get("flatMass_tons"), 0.0) + thrust_power_gw * as_float(
            template.get("specificPower_kgMW"), 0.0
        )
        row = {
            "id": data_name,
            "baseKey": base_key,
            "displayName": display,
            "baseDisplayName": base_display,
            "thrusterCount": thruster_count,
            "classification": classification,
            "requiredPowerPlantClass": required_power_class,
            "powerBandKey": power_band_key,
            "categoryKey": category_key,
            "categoryLabel": label_text(category_meta["label"], "ko"),
            "categoryLabelEn": label_text(category_meta["label"], "en"),
            "categoryColor": category_meta["color"],
            "categoryColorOklch": category_meta["colorOklch"],
            "subfamilyKey": family_key,
            "familyKey": family_key,
            "familyLabel": label_text(meta["label"], "ko"),
            "familyLabelEn": label_text(meta["label"], "en"),
            "familyColor": meta.get("color", "#334155"),
            "familyColorOklch": meta.get("colorOklch", meta.get("color", "#334155")),
            "familyBandColor": meta.get("bandColor", meta.get("color", "#64748b")),
            "familyBandColorOklch": meta.get("bandColorOklch", meta.get("bandColor", meta.get("color", "#64748b"))),
            "alien": alien,
            "requiredProject": project,
            "requiredProjectDisplay": research.display(project),
            "ownResearchCost": research.own_cost(project),
            "cumulativeResearch": cumulative,
            "thrustN": as_float(template.get("thrust_N"), 0.0),
            "exhaustVelocityKps": as_float(template.get("EV_kps"), 0.0),
            "specificImpulseSeconds": as_float(template.get("EV_kps"), 0.0) * 1000.0 / STANDARD_GRAVITY_MPS2,
            "efficiency": as_float(template.get("efficiency"), 0.0),
            "thrustPowerGW": thrust_power_gw,
            "powerRequirementGW": power_requirement_gw,
            "flatMassTons": as_float(template.get("flatMass_tons"), 0.0),
            "specificPowerKgMW": as_float(template.get("specificPower_kgMW"), 0.0),
            "driveMassTons": drive_mass_tons,
            "openCycleCooling": ship_plan_drive_open_cycle(template, drive_templates),
            "propellant": template.get("propellant"),
            "perTankPropellantMaterials": template.get("perTankPropellantMaterials") or {},
            "powerOptions": [],
        }
        row["powerOptions"] = compatible_power_sequence(row, power_plants, closure, cumulative)
        drive_rows.append(row)

    present_categories = {row["categoryKey"] for row in drive_rows}
    categories = []
    for category_key in CATEGORY_ORDER:
        if category_key not in CATEGORY_META:
            continue
        if category_key not in present_categories and category_key != "Alien":
            continue
        category_meta = CATEGORY_META[category_key]
        categories.append(
            {
                "key": category_key,
                "label": label_text(category_meta["label"], "ko"),
                "labelEn": label_text(category_meta["label"], "en"),
                "color": category_meta["color"],
                "colorOklch": category_meta["colorOklch"],
                "alien": category_key == "Alien",
                "defaultVisible": category_key == DEFAULT_CATEGORY_KEY,
            }
        )

    subfamilies = []
    family_seen: set[str] = set()
    for row in sorted(
        drive_rows,
        key=lambda item: (
            category_sort_key(item["categoryKey"]),
            item["familyLabel"],
            item["familyKey"],
        ),
    ):
        if row["familyKey"] in family_seen:
            continue
        family_seen.add(row["familyKey"])
        subfamilies.append(
            {
                "key": row["familyKey"],
                "categoryKey": row["categoryKey"],
                "label": row["familyLabel"],
                "labelEn": row["familyLabelEn"],
                "color": row["familyColor"],
                "colorOklch": row["familyColorOklch"],
                "bandColor": row["familyBandColor"],
                "bandColorOklch": row["familyBandColorOklch"],
                "alien": row["alien"],
            }
        )

    source_files = {
        "templatesDir": str(templates_dir),
        "driveTemplate": str(templates_dir / "TIDriveTemplate.json"),
        "powerPlantTemplate": str(templates_dir / "TIPowerPlantTemplate.json"),
        "radiatorTemplate": str(templates_dir / "TIRadiatorTemplate.json"),
        "researchCatalog": str(research_catalog_path),
    }
    return {
        "schemaVersion": 2,
        "source": source_files,
        "defaults": {
            "targetDvKps": TARGET_DV_KPS,
            "dryMassTons": DEFAULT_DRY_MASS_TONS,
            "thrusterCount": 1,
            "radiatorId": default_radiator.get("id") if default_radiator else None,
            "defaultCategoryKey": DEFAULT_CATEGORY_KEY,
        },
        "method": {
            "cumulativeResearch": "Minimal research closure from data/research_catalog.json. all branches are unioned, any branches choose the lowest total research closure, and shared prerequisites are counted once.",
            "drivePowerRequirementGW": "thrust_N * EV_kps * 0.5 / 1,000,000 / efficiency, matching tools/ti_save_parser.py.",
            "driveMassTons": "flatMass_tons + thrustPowerGW * specificPower_kgMW, matching the local ship-plan simulation.",
            "powerPlantMassTons": "zero for self-contained drives, otherwise max(1, powerPlant specificPower_tGW * drivePowerRequirementGW), matching the local ship-plan simulation's power-plant mass term.",
            "radiatorMassTons": "zero for self-contained or open-cycle cooling drives, otherwise wasteHeatGW * 1,000,000 / radiator specificPower_2s_KWkg / 1000, with wasteHeatGW = drivePowerRequirementGW * (1 - powerPlantEfficiency).",
            "totalMass": "baseDryMass + drive mass + power plant mass + radiator mass + propellant mass, where propellantMass = dryMassWithHardware * (exp(targetDvKps / exhaustVelocityKps) - 1). The dashboard slider is the base dry mass before adding the selected drive, power plant, and radiator.",
        },
        "categories": categories,
        "subfamilies": subfamilies,
        "families": subfamilies,
        "radiators": radiators,
        "drives": sorted(
            drive_rows,
            key=lambda item: (
                item["cumulativeResearch"],
                category_sort_key(item["categoryKey"]),
                item["familyLabel"],
                item["baseDisplayName"],
                item["thrusterCount"],
            ),
        ),
    }


HTML_TEMPLATE = r"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Terra Invicta Drive Comparison</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #11100f;
      --panel: #191b1a;
      --panel-2: #242725;
      --input: #101211;
      --ink: #eef4ef;
      --muted: #a4afa8;
      --line: #343a36;
      --strong-line: #59635d;
      --accent: #14b8a6;
      --danger: #f87171;
      --shadow: 0 14px 34px rgba(0, 0, 0, 0.36);
      --dry: #8b9a91;
      --hardware: #f59e0b;
      --propellant: #22c55e;
      font-family: Inter, "Segoe UI", system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--ink);
    }
    header {
      padding: 22px 28px 14px;
      border-bottom: 1px solid var(--line);
      background: #151614;
    }
    h1 {
      margin: 0 0 6px;
      font-size: 24px;
      line-height: 1.2;
      letter-spacing: 0;
    }
    .subtle {
      color: var(--muted);
      font-size: 13px;
      line-height: 1.45;
      max-width: 1100px;
    }
    main {
      padding: 18px 28px 28px;
      display: grid;
      grid-template-columns: minmax(240px, 320px) minmax(0, 1fr);
      gap: 18px;
    }
    .controls, .chart-shell, .table-shell, .notes {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
    }
    .controls {
      padding: 16px;
      align-self: start;
      position: sticky;
      top: 14px;
      max-height: calc(100vh - 28px);
      overflow: auto;
    }
    .chart-shell {
      min-width: 0;
      padding: 14px 16px 12px;
    }
    .chart-body {
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(240px, 300px);
      gap: 14px;
      align-items: stretch;
    }
    .table-shell {
      grid-column: 2;
      overflow: hidden;
    }
    .notes {
      grid-column: 2;
      min-width: 0;
      padding: 14px 16px;
      color: var(--muted);
      font-size: 12px;
      line-height: 1.55;
      overflow-wrap: anywhere;
      word-break: keep-all;
    }
    .notes p {
      margin: 0;
      max-width: 100%;
    }
    .notes .source-note {
      display: block;
      margin-top: 4px;
      overflow-wrap: anywhere;
      word-break: break-word;
    }
    .control-block {
      padding: 0 0 16px;
      margin: 0 0 16px;
      border-bottom: 1px solid var(--line);
    }
    .control-block:last-child {
      border-bottom: 0;
      margin-bottom: 0;
      padding-bottom: 0;
    }
    .label {
      display: block;
      color: #d8e1db;
      font-weight: 650;
      font-size: 12px;
      margin-bottom: 8px;
    }
    select, input[type="number"] {
      width: 100%;
      min-height: 36px;
      border: 1px solid var(--strong-line);
      border-radius: 6px;
      padding: 7px 9px;
      background: var(--input);
      color: var(--ink);
      font: inherit;
    }
    input[type="range"] {
      width: 100%;
      accent-color: var(--accent);
    }
    .split {
      display: grid;
      grid-template-columns: minmax(0, 1fr) 112px;
      gap: 8px;
      align-items: center;
    }
    .segmented {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 6px;
    }
    .segmented label {
      min-height: 34px;
      display: flex;
      align-items: center;
      justify-content: center;
      border: 1px solid var(--strong-line);
      border-radius: 6px;
      background: var(--input);
      color: var(--muted);
      cursor: pointer;
      font-size: 13px;
      font-weight: 650;
    }
    .segmented input {
      position: absolute;
      opacity: 0;
      pointer-events: none;
    }
    .segmented label:has(input:checked) {
      border-color: var(--accent);
      background: rgba(20, 184, 166, 0.16);
      color: var(--ink);
    }
    .segmented.compact {
      width: 132px;
      flex: 0 0 auto;
    }
    .segmented.compact label {
      min-height: 28px;
      font-size: 12px;
    }
    .chart-toggle {
      display: flex;
      align-items: center;
      gap: 6px;
      min-height: 28px;
      color: var(--muted);
      font-size: 12px;
      white-space: nowrap;
      cursor: pointer;
    }
    .chart-toggle input {
      width: 16px;
      height: 16px;
      accent-color: var(--accent);
      flex: 0 0 auto;
    }
    .check-row, .category-row, .family-row {
      display: flex;
      align-items: center;
      gap: 8px;
      min-height: 28px;
      color: #d5ddd8;
      font-size: 13px;
    }
    .check-row input, .category-row input, .family-row input {
      width: 16px;
      height: 16px;
      accent-color: var(--accent);
      flex: 0 0 auto;
    }
    .family-swatch {
      width: 10px;
      height: 10px;
      border-radius: 50%;
      flex: 0 0 auto;
    }
    .button-row {
      display: flex;
      gap: 8px;
      margin-bottom: 8px;
    }
    button {
      border: 1px solid var(--strong-line);
      background: #202421;
      color: var(--ink);
      border-radius: 6px;
      min-height: 30px;
      padding: 5px 9px;
      font: inherit;
      font-size: 12px;
      cursor: pointer;
    }
    button:hover { border-color: #8a968d; }
    .compact-command {
      min-height: 28px;
      padding: 4px 8px;
      white-space: nowrap;
      flex: 0 0 auto;
    }
    .compact-command:disabled {
      opacity: 0.45;
      cursor: default;
    }
    .compact-command:disabled:hover {
      border-color: var(--strong-line);
    }
    #chart {
      width: 100%;
      height: min(70vh, 680px);
      min-height: 520px;
      display: block;
      min-width: 0;
      cursor: grab;
      touch-action: none;
      user-select: none;
    }
    #chart.is-panning {
      cursor: grabbing;
    }
    .axis text {
      fill: #a9b5ad;
      font-size: 11px;
    }
    .axis path, .axis line {
      stroke: var(--strong-line);
      shape-rendering: crispEdges;
    }
    .grid line {
      stroke: #2a302c;
      shape-rendering: crispEdges;
    }
    .axis-title {
      fill: #d8e1db;
      font-size: 12px;
      font-weight: 650;
    }
    .legend {
      display: flex;
      gap: 12px;
      flex-wrap: wrap;
      margin: 8px 2px 0;
      color: var(--muted);
      font-size: 12px;
    }
    .legend-group {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
      padding-right: 4px;
    }
    .legend-heading {
      color: #d8e1db;
      font-weight: 700;
    }
    .legend-item {
      display: inline-flex;
      align-items: center;
      gap: 6px;
    }
    .legend-swatch {
      width: 11px;
      height: 11px;
      border-radius: 50%;
    }
    .summary-strip {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: center;
      margin-bottom: 8px;
      color: var(--muted);
      font-size: 12px;
    }
    .summary-controls {
      display: flex;
      align-items: center;
      justify-content: flex-end;
      gap: 12px;
      min-width: 0;
    }
    .summary-strip strong {
      color: var(--ink);
      font-weight: 700;
    }
    .tooltip {
      position: relative;
      pointer-events: auto;
      max-width: none;
      width: 100%;
      height: min(70vh, 680px);
      min-height: 520px;
      background: #101211;
      color: var(--ink);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 34px 12px 12px;
      font-size: 12px;
      line-height: 1.45;
      opacity: 1;
      overflow: hidden;
      display: flex;
      flex-direction: column;
    }
    .tooltip.tooltip-empty {
      display: flex;
      align-items: center;
      justify-content: center;
      color: var(--muted);
      padding: 12px;
    }
    .tooltip-placeholder {
      color: var(--muted);
    }
    .tooltip-close {
      position: absolute;
      top: 8px;
      right: 8px;
      width: 24px;
      height: 24px;
      min-height: 0;
      padding: 0;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      border-radius: 6px;
      border-color: var(--line);
      background: #1a1d1b;
      color: var(--muted);
      font-size: 18px;
      line-height: 1;
    }
    .tooltip-close:hover {
      color: var(--ink);
      border-color: var(--strong-line);
    }
    .tooltip-count {
      color: var(--muted);
      font-size: 11px;
      margin: -16px 34px 8px 0;
      min-height: 16px;
    }
    .tooltip-items {
      min-height: 0;
      overflow: auto;
      display: flex;
      flex-direction: column;
      gap: 9px;
      padding-right: 2px;
    }
    .tooltip-item {
      position: relative;
      padding: 9px 30px 9px 10px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #151816;
    }
    .tooltip-item-close {
      position: absolute;
      top: 7px;
      right: 7px;
      width: 22px;
      height: 22px;
      min-height: 0;
      padding: 0;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      border-radius: 6px;
      border-color: var(--line);
      background: #202421;
      color: var(--muted);
      font-size: 15px;
      line-height: 1;
    }
    .tooltip-item-close:hover {
      color: var(--ink);
      border-color: var(--strong-line);
    }
    .tooltip h2 {
      margin: 0 0 5px;
      font-size: 13px;
      line-height: 1.3;
      color: var(--ink);
      letter-spacing: 0;
    }
    .tooltip .muted { color: #a9b5ad; }
    .tooltip-breakdown {
      margin-top: 6px;
      padding-top: 6px;
      border-top: 1px solid var(--line);
    }
    .tooltip-breakdown-grid {
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 2px 12px;
      margin-bottom: 6px;
    }
    .tooltip-breakdown-grid span {
      color: #a9b5ad;
    }
    .tooltip-breakdown-grid strong {
      font-weight: 700;
      font-variant-numeric: tabular-nums;
    }
    .tooltip-stack {
      display: flex;
      height: 7px;
      overflow: hidden;
      border-radius: 999px;
      background: #0e100f;
      border: 1px solid #2d342f;
      margin-bottom: 5px;
    }
    .tooltip-stack span {
      box-shadow: inset -1px 0 rgb(0 0 0 / 0.28), inset 1px 0 rgb(255 255 255 / 0.05);
    }
    .stack-hull {
      background: #793e00;
      background: oklch(43% 0.105 58);
    }
    .stack-drive {
      background: #9b5a14;
      background: oklch(53% 0.115 61);
    }
    .stack-reactor {
      background: #bd7729;
      background: oklch(63% 0.125 64);
    }
    .stack-radiator {
      background: #e0953d;
      background: oklch(73% 0.135 67);
    }
    .stack-propellant { background: var(--propellant); }
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 12px;
    }
    thead {
      background: var(--panel-2);
      color: #d8e1db;
    }
    th, td {
      text-align: left;
      padding: 9px 10px;
      border-bottom: 1px solid var(--line);
      vertical-align: top;
    }
    th.numeric, td.numeric { text-align: right; font-variant-numeric: tabular-nums; }
    .sort-button {
      all: unset;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 5px;
      width: 100%;
      color: inherit;
      font: inherit;
      font-weight: 700;
    }
    th.numeric .sort-button {
      justify-content: flex-end;
    }
    .sort-button:hover {
      color: var(--ink);
    }
    .sort-button[data-active="true"]::after {
      content: attr(data-arrow);
      color: var(--accent);
      font-size: 10px;
      line-height: 1;
    }
    tbody tr:hover { background: #202421; }
    .drive-name { font-weight: 650; color: #f3f7f4; }
    .project-name { color: var(--muted); font-size: 11px; margin-top: 2px; }
    .cell-viz {
      min-width: 150px;
    }
    .numeric .cell-viz {
      margin-left: auto;
    }
    .cell-value {
      display: block;
      margin-bottom: 5px;
      white-space: nowrap;
    }
    .sparkbar,
    .sparkrange {
      position: relative;
      height: 6px;
      border-radius: 999px;
      background: #0e100f;
      border: 1px solid #2d342f;
      overflow: hidden;
    }
    .spark-fill {
      position: absolute;
      inset: 0 auto 0 0;
      min-width: 2px;
      border-radius: 999px;
      background: linear-gradient(90deg, rgba(20, 184, 166, 0.45), rgba(20, 184, 166, 0.95));
    }
    .sparkrange-fill {
      position: absolute;
      top: 0;
      bottom: 0;
      min-width: 2px;
      border-radius: 999px;
      background: linear-gradient(90deg, rgba(34, 197, 94, 0.45), rgba(245, 158, 11, 0.9));
    }
    .pill {
      display: inline-flex;
      align-items: center;
      gap: 5px;
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 2px 7px;
      white-space: nowrap;
      background: #202421;
    }
    .warning {
      color: var(--danger);
      font-weight: 650;
    }
    @media (max-width: 980px) {
      main { grid-template-columns: 1fr; padding: 14px; }
      header { padding: 18px 14px 12px; }
      .controls { position: static; max-height: none; }
      .chart-body { grid-template-columns: 1fr; }
      .table-shell { grid-column: 1; }
      .notes { grid-column: 1; }
      #chart { height: 560px; }
      .tooltip { height: min(52vh, 520px); min-height: 220px; }
    }
  </style>
</head>
<body>
  <header>
    <h1>Terra Invicta 드라이브 비교</h1>
    <div class="subtle">
      X축은 로컬 연구 카탈로그에서 계산한 최소 누적 연구력입니다. 총질량 그래프는 각 드라이브 개방 시점의 호환 전원부터 이후 전원 후보까지 적용했을 때의 목표 dV 달성 질량을 보여주며, breakdown은 차트 오른쪽 상세 패널에서 확인할 수 있습니다.
    </div>
  </header>
  <main>
    <aside class="controls">
      <section class="control-block">
        <label class="label" for="metric">세로축</label>
        <select id="metric">
          <option value="thrustMN">추력 (MN)</option>
          <option value="fuelEfficiency">연료효율 (km/s or s)</option>
          <option value="powerRequirementGW">출력 요구량 (GW)</option>
          <option value="totalMassTons">목표 dV 총질량 (t)</option>
          <option value="twr">TWR</option>
        </select>
      </section>
      <section class="control-block">
        <label class="label" for="nameSearch">이름 검색</label>
        <input id="nameSearch" type="search" placeholder="드라이브 또는 프로젝트">
      </section>
      <section class="control-block">
        <label class="label" for="thrusters">엔진 수</label>
        <div class="split">
          <input id="thrusters" type="range" min="1" max="6" value="1" step="1">
          <input id="thrustersNumber" type="number" min="1" max="6" value="1" step="1">
        </div>
      </section>
      <section class="control-block">
        <label class="label" for="dryMass">기준 선체 건조 질량 (t)</label>
        <div class="split">
          <input id="dryMass" type="range" min="100" max="10000" value="1000" step="100">
          <input id="dryMassNumber" type="number" min="1" max="1000000" value="1000" step="10">
        </div>
      </section>
      <section class="control-block">
        <label class="label" for="targetDv">목표 dV (km/s)</label>
        <div class="split">
          <input id="targetDv" type="range" min="10" max="5000" value="1000" step="10">
          <input id="targetDvNumber" type="number" min="1" max="100000" value="1000" step="10">
        </div>
      </section>
      <section class="control-block">
        <label class="label" for="radiator">라디에이터</label>
        <select id="radiator"></select>
      </section>
      <section class="control-block">
        <span class="label">축 스케일</span>
        <label class="check-row"><input id="logX" type="checkbox"> X축 로그</label>
        <label class="check-row"><input id="logY" type="checkbox" checked> Y축 로그</label>
      </section>
      <section class="control-block">
        <span class="label">대분류</span>
        <div id="categories"></div>
      </section>
      <section class="control-block">
        <span class="label">세부 계열</span>
        <div class="button-row">
          <button id="allFamilies" type="button">전체 선택</button>
          <button id="clearFamilies" type="button">전체 해제</button>
        </div>
        <div id="families"></div>
      </section>
    </aside>
    <section class="chart-shell">
      <div class="summary-strip">
        <div><strong id="visibleCount">0</strong>개 드라이브 표시</div>
        <div class="summary-controls">
          <div id="chartFuelUnit" class="segmented compact" style="display: none;">
            <label><input type="radio" name="fuelUnit" value="kps" checked>km/s</label>
            <label><input type="radio" name="fuelUnit" value="seconds">s</label>
          </div>
          <button id="resetZoom" class="compact-command" type="button" disabled>보기 초기화</button>
          <div id="metricHint"></div>
        </div>
      </div>
      <div class="chart-body">
        <svg id="chart" role="img" aria-label="Drive comparison chart"></svg>
        <div id="tooltip" class="tooltip tooltip-empty"><div class="tooltip-placeholder">선택 없음</div></div>
      </div>
      <div id="legend" class="legend"></div>
    </section>
    <section class="table-shell">
      <table>
        <thead>
          <tr>
            <th><button class="sort-button" type="button" data-sort="drive">추진기</button></th>
            <th><button class="sort-button" type="button" data-sort="family">대분류 / 세부 계열</button></th>
            <th class="numeric"><button class="sort-button" type="button" data-sort="research">누적 연구력</button></th>
            <th class="numeric"><button class="sort-button" id="metricColumn" type="button" data-sort="metric">값</button></th>
            <th><button class="sort-button" type="button" data-sort="reactor">전원 단계</button></th>
          </tr>
        </thead>
        <tbody id="tableBody"></tbody>
      </table>
    </section>
    <section class="notes">
      <p><strong>계산 메모.</strong> 총질량은 기준 선체 건조 질량, 드라이브 질량, 전원 질량, 선택 라디에이터 질량, 목표 dV에 필요한 추진체 질량을 합산합니다. 드라이브 출력 요구량, 드라이브 질량, 전원 질량, 라디에이터 질량은 이 저장소의 기존 ship-plan 계산식과 같은 항을 사용하며, 무장/유틸리티 전력은 제외해 드라이브-전원-라디에이터 비교만 분리했습니다.</p>
      <span id="sourceNote" class="source-note"></span>
    </section>
  </main>
  <script id="ti-data" type="application/json">__DATA_JSON__</script>
  <script>
    const DATA = JSON.parse(document.getElementById("ti-data").textContent);
    const STANDARD_GRAVITY_MPS2 = 9.80665;
    const UI_LANG = document.documentElement.lang === "en" ? "en" : "ko";
    const state = {
      metric: "thrustMN",
      thrusters: DATA.defaults.thrusterCount,
      fuelEfficiencyUnit: "kps",
      dryMassTons: DATA.defaults.dryMassTons,
      targetDvKps: DATA.defaults.targetDvKps,
      radiatorId: DATA.defaults.radiatorId,
      logX: false,
      logY: true,
      searchTerm: "",
      sortKey: "research",
      sortDirection: "asc",
      lastTooltipItems: [],
      hoverPoints: [],
      dismissedTooltipKeys: new Set(),
      hoverHitSignature: "",
      zoom: null,
      zoomContext: "",
      pan: null,
      categories: Object.fromEntries(DATA.categories.map(category => [category.key, !!category.defaultVisible])),
      families: Object.fromEntries(DATA.subfamilies.map(family => [family.key, true])),
    };

    const metricDefs = {
      thrustMN: {
        label: "추력 (MN)",
        hint: "템플릿 thrust_N을 MN으로 환산",
        value: row => row.thrustN / 1e6,
        format: value => formatNumber(value, " MN"),
      },
      fuelEfficiency: {
        get label() {
          return state.fuelEfficiencyUnit === "seconds" ? "연료효율 (s)" : "연료효율 (km/s)";
        },
        get hint() {
          return state.fuelEfficiencyUnit === "seconds"
            ? "EV_kps * 1000 / 9.80665"
            : "템플릿 EV_kps";
        },
        value: row => state.fuelEfficiencyUnit === "seconds" ? row.specificImpulseSeconds : row.exhaustVelocityKps,
        format: value => formatNumber(value, state.fuelEfficiencyUnit === "seconds" ? " s" : " km/s"),
      },
      powerRequirementGW: {
        label: "출력 요구량 (GW)",
        hint: "thrust_N * EV_kps * 0.5 / 1,000,000 / efficiency",
        value: row => row.powerRequirementGW,
        format: value => formatNumber(value, " GW"),
      },
      totalMassTons: {
        label: "목표 dV 총질량 (t)",
        hint: "총질량 = 기준 건조질량 + 드라이브 + 전원 + 라디에이터 + 추진체",
        value: row => {
          const values = massOptions(row);
          return values.length ? values[0].totalMassTons : NaN;
        },
        format: value => formatNumber(value, " t"),
      },
      twr: {
        label: "TWR",
        hint: "추력 / (목표 dV 총질량 * g)",
        value: row => {
          const values = massOptions(row);
          return values.length ? values[0].twr : NaN;
        },
        format: value => formatNumber(value, ""),
      },
    };

    const chart = document.getElementById("chart");
    const tooltip = document.getElementById("tooltip");
    const categoryRoot = document.getElementById("categories");
    const familyRoot = document.getElementById("families");
    const CHART_HIT_RADIUS_PX = 16;
    let chartViewport = null;
    let chartHitTargets = [];
    let currentChartRows = [];

    function setupControls() {
      const metric = document.getElementById("metric");
      const thrusters = document.getElementById("thrusters");
      const thrustersNumber = document.getElementById("thrustersNumber");
      const fuelUnitBlock = document.getElementById("chartFuelUnit");
      const dryMass = document.getElementById("dryMass");
      const dryMassNumber = document.getElementById("dryMassNumber");
      const targetDv = document.getElementById("targetDv");
      const targetDvNumber = document.getElementById("targetDvNumber");
      const radiator = document.getElementById("radiator");
      const logX = document.getElementById("logX");
      const logY = document.getElementById("logY");
      const nameSearch = document.getElementById("nameSearch");

      tooltip.addEventListener("click", event => {
        const itemClose = event.target.closest(".tooltip-item-close");
        if (itemClose) {
          removeTooltipItem(itemClose.getAttribute("data-tooltip-key"));
          return;
        }
        if (event.target.closest(".tooltip-close")) {
          clearTooltip();
        }
      });

      DATA.radiators.forEach(item => {
        const option = document.createElement("option");
        option.value = item.id;
        option.textContent = `${item.displayName} (${formatNumber(item.specificPowerKWPerKg, " kW/kg")})`;
        option.selected = item.id === state.radiatorId;
        radiator.appendChild(option);
      });
      if (!state.radiatorId && DATA.radiators[0]) {
        state.radiatorId = DATA.radiators[0].id;
        radiator.value = state.radiatorId;
      }

      DATA.categories.forEach(category => {
        const label = document.createElement("label");
        label.className = "category-row";
        label.dataset.categoryKey = category.key;
        const input = document.createElement("input");
        input.type = "checkbox";
        input.checked = !!state.categories[category.key];
        input.addEventListener("change", () => {
          state.categories[category.key] = input.checked;
          syncFilterInputs();
          render();
        });
        const swatch = document.createElement("span");
        swatch.className = "family-swatch";
        swatch.setAttribute("style", backgroundStyle(category.color, category.colorOklch || category.color));
        const text = document.createElement("span");
        text.textContent = localLabel(category);
        label.append(input, swatch, text);
        categoryRoot.appendChild(label);
      });

      DATA.subfamilies.forEach(family => {
        const label = document.createElement("label");
        label.className = "family-row";
        label.dataset.familyKey = family.key;
        label.dataset.categoryKey = family.categoryKey;
        const input = document.createElement("input");
        input.type = "checkbox";
        input.checked = !!state.families[family.key];
        input.addEventListener("change", () => {
          state.families[family.key] = input.checked;
          render();
        });
        const swatch = document.createElement("span");
        swatch.className = "family-swatch";
        swatch.setAttribute("style", backgroundStyle(family.color, family.colorOklch || family.color));
        const text = document.createElement("span");
        text.textContent = localLabel(family);
        label.append(input, swatch, text);
        familyRoot.appendChild(label);
      });

      metric.addEventListener("change", () => {
        state.metric = metric.value;
        fuelUnitBlock.style.display = state.metric === "fuelEfficiency" ? "" : "none";
        render();
      });
      thrusters.addEventListener("change", () => {
        state.thrusters = Number(thrusters.value);
        thrustersNumber.value = String(state.thrusters);
        render();
      });
      thrusters.addEventListener("input", () => {
        state.thrusters = Number(thrusters.value);
        thrustersNumber.value = String(state.thrusters);
        render();
      });
      thrustersNumber.addEventListener("input", () => {
        const value = Math.round(clamp(Number(thrustersNumber.value) || 1, 1, 6));
        state.thrusters = value;
        thrusters.value = String(value);
        render();
      });
      document.querySelectorAll('input[name="fuelUnit"]').forEach(input => {
        input.addEventListener("change", () => {
          state.fuelEfficiencyUnit = input.value;
          render();
        });
      });
      document.querySelectorAll("[data-sort]").forEach(button => {
        button.addEventListener("click", () => {
          const key = button.dataset.sort;
          if (state.sortKey === key) {
            state.sortDirection = state.sortDirection === "asc" ? "desc" : "asc";
          } else {
            state.sortKey = key;
            state.sortDirection = ["drive", "family", "reactor"].includes(key) ? "asc" : "desc";
          }
          renderTable(filteredRows());
          updateSortHeaders();
        });
      });
      dryMass.addEventListener("input", () => {
        state.dryMassTons = Number(dryMass.value);
        dryMassNumber.value = String(Math.round(state.dryMassTons));
        render();
      });
      dryMassNumber.addEventListener("input", () => {
        const value = clamp(Number(dryMassNumber.value) || 1, 1, 1000000);
        state.dryMassTons = value;
        dryMass.value = String(clamp(value, Number(dryMass.min), Number(dryMass.max)));
        render();
      });
      targetDv.addEventListener("input", () => {
        state.targetDvKps = Number(targetDv.value);
        targetDvNumber.value = String(Math.round(state.targetDvKps));
        render();
      });
      targetDvNumber.addEventListener("input", () => {
        const value = clamp(Number(targetDvNumber.value) || 1, 1, 100000);
        state.targetDvKps = value;
        targetDv.value = String(clamp(value, Number(targetDv.min), Number(targetDv.max)));
        render();
      });
      radiator.addEventListener("change", () => {
        state.radiatorId = radiator.value;
        render();
      });
      logX.addEventListener("change", () => {
        state.logX = logX.checked;
        render();
      });
      logY.addEventListener("change", () => {
        state.logY = logY.checked;
        render();
      });
      nameSearch.addEventListener("input", () => {
        state.searchTerm = nameSearch.value.trim().toLocaleLowerCase();
        render();
      });
      document.getElementById("allFamilies").addEventListener("click", () => {
        DATA.subfamilies.forEach(f => {
          if (state.categories[f.categoryKey]) state.families[f.key] = true;
        });
        syncFilterInputs();
        render();
      });
      document.getElementById("clearFamilies").addEventListener("click", () => {
        DATA.subfamilies.forEach(f => {
          if (state.categories[f.categoryKey]) state.families[f.key] = false;
        });
        syncFilterInputs();
        render();
      });
      document.getElementById("sourceNote").textContent = ` Source: ${DATA.source.driveTemplate}; ${DATA.source.radiatorTemplate}`;
      syncFilterInputs();
      setupChartInteraction();
      updateChartControls();
      updateSortHeaders();
    }

    function setupChartInteraction() {
      const resetZoom = document.getElementById("resetZoom");
      resetZoom.addEventListener("click", () => {
        state.zoom = null;
        redrawChartOnly();
      });
      chart.addEventListener("wheel", handleChartWheel, { passive: false });
      chart.addEventListener("pointerdown", handleChartPointerDown);
      chart.addEventListener("pointermove", handleChartPointerMove);
      chart.addEventListener("pointerup", endChartPan);
      chart.addEventListener("pointercancel", endChartPan);
      chart.addEventListener("pointerleave", handleChartPointerLeave);
      chart.addEventListener("dblclick", event => {
        event.preventDefault();
        state.zoom = null;
        redrawChartOnly();
      });
    }

    function updateChartControls() {
      const fuelUnitBlock = document.getElementById("chartFuelUnit");
      fuelUnitBlock.style.display = state.metric === "fuelEfficiency" ? "" : "none";
    }

    function localLabel(item) {
      if (UI_LANG === "en") return item.labelEn || item.label || item.key;
      return item.label || item.labelEn || item.key;
    }

    function rowCategoryLabel(row) {
      return UI_LANG === "en" ? (row.categoryLabelEn || row.categoryLabel) : (row.categoryLabel || row.categoryLabelEn);
    }

    function rowFamilyLabel(row) {
      return UI_LANG === "en" ? (row.familyLabelEn || row.familyLabel) : (row.familyLabel || row.familyLabelEn);
    }

    function rowProjectLabel(row) {
      return UI_LANG === "en"
        ? (row.requiredProjectDisplay.en || row.requiredProjectDisplay.ko || row.requiredProject)
        : (row.requiredProjectDisplay.ko || row.requiredProjectDisplay.en || row.requiredProject);
    }

    function syncFilterInputs() {
      document.querySelectorAll(".category-row").forEach(row => {
        const input = row.querySelector("input");
        input.checked = !!state.categories[row.dataset.categoryKey];
      });
      document.querySelectorAll(".family-row").forEach(row => {
        const activeCategory = !!state.categories[row.dataset.categoryKey];
        const input = row.querySelector("input");
        row.style.display = activeCategory ? "" : "none";
        input.disabled = !activeCategory;
        input.checked = !!state.families[row.dataset.familyKey];
      });
    }

    function clamp(value, min, max) {
      return Math.max(min, Math.min(max, value));
    }

    function filteredRows() {
      return DATA.drives.filter(row => {
        if (row.thrusterCount !== state.thrusters) return false;
        if (!state.categories[row.categoryKey]) return false;
        if (!state.families[row.familyKey]) return false;
        if (state.searchTerm) {
          const haystack = [
            row.displayName,
            row.baseDisplayName,
            row.requiredProject,
            rowProjectLabel(row),
            rowCategoryLabel(row),
            rowFamilyLabel(row),
          ].join(" ").toLocaleLowerCase();
          if (!haystack.includes(state.searchTerm)) return false;
        }
        return Number.isFinite(row.cumulativeResearch) && row.cumulativeResearch > 0;
      });
    }

    function selectedRadiator() {
      return DATA.radiators.find(item => item.id === state.radiatorId) || DATA.radiators[0] || null;
    }

    function massOptions(row) {
      const baseDryTons = state.dryMassTons;
      const targetDv = state.targetDvKps;
      const radiator = selectedRadiator();
      const radiatorSpecificPower = radiator ? Number(radiator.specificPowerKWPerKg) : NaN;
      const massRatioMinusOne = Math.exp(targetDv / row.exhaustVelocityKps) - 1;
      if (!Number.isFinite(massRatioMinusOne) || massRatioMinusOne < 0) return [];
      const options = row.powerOptions || row.reactorOptions || [];
      const computed = options.map(option => {
        const selfContained = !!option.selfContained || row.powerRequirementGW <= 0;
        const powerPlantMassTons = selfContained ? 0 : Math.max(1, option.specificMassTonsPerGW * row.powerRequirementGW);
        const wasteHeatGW = selfContained || row.openCycleCooling ? 0 : row.powerRequirementGW * (1 - option.efficiency);
        const radiatorMassTons = !selfContained && radiatorSpecificPower > 0
          ? Math.max(0, wasteHeatGW * 1_000_000 / radiatorSpecificPower / 1000)
          : 0;
        const hardwareMassTons = row.driveMassTons + powerPlantMassTons + radiatorMassTons;
        const dryWithHardwareTons = baseDryTons + hardwareMassTons;
        const propellantTons = dryWithHardwareTons * massRatioMinusOne;
        const totalMassTons = dryWithHardwareTons + propellantTons;
        const twr = row.thrustN / (totalMassTons * 1000 * STANDARD_GRAVITY_MPS2);
        return {
          ...option,
          reactorMassTons: powerPlantMassTons,
          powerPlantMassTons,
          radiatorMassTons,
          wasteHeatGW,
          hardwareMassTons,
          baseDryTons,
          dryWithHardwareTons,
          propellantTons,
          totalMassTons,
          twr,
        };
      });
      return actualPowerFrontier(row, computed);
    }

    function actualPowerFrontier(row, options) {
      if (row.requiredPowerPlantClass !== "Any_General" || row.powerRequirementGW <= 0 || options.length <= 1) {
        return options;
      }
      const frontier = [];
      let bestTotalMass = Infinity;
      options.forEach((option, index) => {
        if (index === 0 || option.totalMassTons < bestTotalMass * (1 - 1e-9)) {
          frontier.push(option);
          bestTotalMass = Math.min(bestTotalMass, option.totalMassTons);
        }
      });
      return frontier;
    }

    function makeScale(domain, range, logScale) {
      let [d0, d1] = domain;
      if (!Number.isFinite(d0) || !Number.isFinite(d1) || d0 === d1) {
        d0 = 1;
        d1 = 10;
      }
      if (logScale) {
        d0 = Math.max(d0, 1e-9);
        d1 = Math.max(d1, d0 * 1.01);
        const l0 = Math.log10(d0);
        const l1 = Math.log10(d1);
        return value => {
          const v = Math.log10(Math.max(value, 1e-9));
          return range[0] + (v - l0) / (l1 - l0) * (range[1] - range[0]);
        };
      }
      return value => range[0] + (value - d0) / (d1 - d0) * (range[1] - range[0]);
    }

    function linearTicks(min, max, count = 6) {
      if (!Number.isFinite(min) || !Number.isFinite(max) || min === max) return [min || 0];
      const span = max - min;
      const raw = span / count;
      const pow = Math.pow(10, Math.floor(Math.log10(raw)));
      const step = [1, 2, 5, 10].find(v => raw <= v * pow) * pow;
      const start = Math.ceil(min / step) * step;
      const ticks = [];
      for (let value = start; value <= max + step * 0.25; value += step) ticks.push(value);
      return ticks;
    }

    function logTicks(min, max, maxTicks = 9) {
      min = Math.max(min, 1e-9);
      const start = Math.floor(Math.log10(min));
      const end = Math.ceil(Math.log10(max));
      const exponentSpan = Math.max(0, end - start);
      const denseTicks = denseLogTicks(min, max, start, end);
      if (denseTicks.length <= maxTicks + 2) return denseTicks;
      const exponentStep = niceTickStep(Math.max(1, exponentSpan / Math.max(maxTicks - 1, 1)));
      const ticks = [];
      const firstExp = Math.ceil(start / exponentStep) * exponentStep;
      for (let exp = firstExp; exp <= end; exp += exponentStep) {
        const value = Math.pow(10, exp);
        if (value >= min * 0.999 && value <= max * 1.001) ticks.push(value);
      }
      if (!ticks.length) ticks.push(Math.sqrt(min * max));
      return ticks.slice(0, maxTicks + 1);
    }

    function denseLogTicks(min, max, start, end) {
      const ticks = [];
      for (let exp = start; exp <= end; exp++) {
        [1, 2, 5].forEach(multiplier => {
          const value = multiplier * Math.pow(10, exp);
          if (value >= min * 0.999 && value <= max * 1.001) ticks.push(value);
        });
      }
      return ticks;
    }

    function niceTickStep(rawStep) {
      const pow = Math.pow(10, Math.floor(Math.log10(rawStep)));
      const normalized = rawStep / pow;
      const nice = normalized <= 1 ? 1 : normalized <= 2 ? 2 : normalized <= 5 ? 5 : 10;
      return nice * pow;
    }

    function maxAxisTicks(pixelSpan, minPixelGap = 54) {
      return Math.max(3, Math.floor(pixelSpan / minPixelGap) + 1);
    }

    function render() {
      const rows = filteredRows();
      const metric = metricDefs[state.metric];
      document.getElementById("visibleCount").textContent = rows.length;
      document.getElementById("metricHint").textContent = metric.hint;
      document.getElementById("metricColumn").textContent = metric.label;
      updateChartControls();
      renderLegend(rows);
      renderChart(rows);
      renderTable(rows);
      updateSortHeaders();
      refreshTooltip(rows);
    }

    function redrawChartOnly() {
      const rows = filteredRows();
      renderChart(rows);
      updateZoomButton();
      refreshTooltip(rows);
    }

    function currentZoomContext() {
      const categoryState = DATA.categories.map(category => `${category.key}:${state.categories[category.key] ? 1 : 0}`).join("|");
      const familyState = DATA.subfamilies.map(family => `${family.key}:${state.families[family.key] ? 1 : 0}`).join("|");
      return [
        state.metric,
        state.fuelEfficiencyUnit,
        state.thrusters,
        state.dryMassTons,
        state.targetDvKps,
        state.radiatorId,
        state.logX ? 1 : 0,
        state.logY ? 1 : 0,
        state.searchTerm,
        categoryState,
        familyState,
      ].join(";");
    }

    function updateZoomButton() {
      const resetZoom = document.getElementById("resetZoom");
      if (resetZoom) resetZoom.disabled = !state.zoom;
    }

    function updateSortHeaders() {
      document.querySelectorAll("[data-sort]").forEach(button => {
        const active = button.dataset.sort === state.sortKey;
        button.dataset.active = active ? "true" : "false";
        button.dataset.arrow = active ? (state.sortDirection === "asc" ? "▲" : "▼") : "";
        button.setAttribute("aria-sort", active ? (state.sortDirection === "asc" ? "ascending" : "descending") : "none");
      });
    }

    function renderLegend(rows) {
      const used = new Set(rows.map(row => row.familyKey));
      const legend = document.getElementById("legend");
      legend.innerHTML = "";
      DATA.categories.forEach(category => {
        const subfamilies = DATA.subfamilies.filter(f => f.categoryKey === category.key && used.has(f.key));
        if (!subfamilies.length) return;
        const group = document.createElement("span");
        group.className = "legend-group";
        const heading = document.createElement("span");
        heading.className = "legend-heading";
        heading.textContent = localLabel(category);
        group.appendChild(heading);
        subfamilies.forEach(f => {
          const item = document.createElement("span");
          item.className = "legend-item";
          const swatch = document.createElement("span");
          swatch.className = "legend-swatch";
          if (isBandMetric()) {
            swatch.setAttribute("style", backgroundStyle(f.bandColor || f.color, f.bandColorOklch || f.bandColor || f.color));
          } else {
            swatch.setAttribute("style", backgroundStyle(f.color, f.colorOklch || f.color));
          }
          item.append(swatch, document.createTextNode(localLabel(f)));
          group.appendChild(item);
        });
        legend.appendChild(group);
      });
      if (isBandMetric()) {
        const item = document.createElement("span");
        item.className = "legend-item";
        item.textContent = `${metricDefs[state.metric].label} 밴드: 개방 전원부터 이후 전원 후보`;
        legend.appendChild(item);
      }
    }

    function valueDomain(rows) {
      if (isBandMetric()) {
        const values = rows.flatMap(row => massOptions(row).map(option => optionMetricValue(option)));
        return paddedDomain(values, state.logY);
      }
      const values = rows.map(metricDefs[state.metric].value).filter(v => Number.isFinite(v) && v > 0);
      return paddedDomain(values, state.logY);
    }

    function paddedDomain(values, logScale) {
      if (!values.length) return [1, 10];
      let min = Math.min(...values);
      let max = Math.max(...values);
      if (logScale) {
        min = Math.max(min / 1.35, 1e-9);
        max *= 1.35;
      } else {
        const pad = (max - min || max || 1) * 0.08;
        min = Math.max(0, min - pad);
        max += pad;
      }
      return [min, max];
    }

    function renderChart(rows) {
      const width = 1120;
      const height = 660;
      const margin = { top: 34, right: 32, bottom: 72, left: 86 };
      const innerW = width - margin.left - margin.right;
      const innerH = height - margin.top - margin.bottom;
      currentChartRows = rows;
      chartHitTargets = [];
      state.hoverPoints = [];
      chart.setAttribute("viewBox", `0 0 ${width} ${height}`);
      chart.innerHTML = "";

      const xValues = rows.map(row => row.cumulativeResearch).filter(v => Number.isFinite(v) && v > 0);
      const baseXDomain = paddedDomain(xValues, state.logX);
      const baseYDomain = valueDomain(rows);
      const xDomain = state.zoom ? constrainDomain(state.zoom.xDomain, baseXDomain, state.logX) : baseXDomain;
      const yDomain = state.zoom ? constrainDomain(state.zoom.yDomain, baseYDomain, state.logY) : baseYDomain;
      if (state.zoom) {
        state.zoom = { xDomain, yDomain };
      }
      const x = makeScale(xDomain, [margin.left, margin.left + innerW], state.logX);
      const y = makeScale(yDomain, [margin.top + innerH, margin.top], state.logY);
      chartViewport = { width, height, margin, innerW, innerH, xDomain, yDomain, baseXDomain, baseYDomain };

      drawGridAndAxes({ width, height, margin, innerW, innerH, x, y, xDomain, yDomain });
      const clipId = "plotClip";
      const defs = svgEl("defs", {});
      const clipPath = svgEl("clipPath", { id: clipId });
      clipPath.appendChild(svgEl("rect", { x: margin.left, y: margin.top, width: innerW, height: innerH }));
      defs.appendChild(clipPath);
      chart.appendChild(defs);
      const plot = svgEl("g", { "clip-path": `url(#${clipId})` });
      chart.appendChild(plot);

      if (isBandMetric()) {
        drawTotalMassBands(rows, x, y, plot);
      } else {
        drawMetricLines(rows, x, y, plot);
      }
      updateZoomButton();
    }

    function handleChartWheel(event) {
      if (!chartViewport) return;
      const point = svgPointFromEvent(event);
      if (!pointInPlot(point)) return;
      event.preventDefault();
      const focal = clampPointToPlot(point);
      const zoomFactor = Math.exp(Math.sign(event.deltaY) * 0.22);
      const xValue = invertScale(focal.x, chartViewport.xDomain, [chartViewport.margin.left, chartViewport.margin.left + chartViewport.innerW], state.logX);
      const yValue = invertScale(focal.y, chartViewport.yDomain, [chartViewport.margin.top + chartViewport.innerH, chartViewport.margin.top], state.logY);
      setZoomDomains(
        zoomDomainAround(chartViewport.xDomain, xValue, zoomFactor, state.logX),
        zoomDomainAround(chartViewport.yDomain, yValue, zoomFactor, state.logY),
      );
    }

    function handleChartPointerDown(event) {
      if (!chartViewport || event.button !== 0) return;
      const point = svgPointFromEvent(event);
      if (!pointInPlot(point)) return;
      state.pan = {
        pointerId: event.pointerId,
        startPoint: point,
        xDomain: chartViewport.xDomain.slice(),
        yDomain: chartViewport.yDomain.slice(),
      };
      chart.classList.add("is-panning");
      try {
        chart.setPointerCapture(event.pointerId);
      } catch {
        // Synthetic pointer events used by tests do not always have an active pointer capture target.
      }
      event.preventDefault();
    }

    function handleChartPointerMove(event) {
      if (!state.pan) {
        updateHoverFromPointer(event);
        return;
      }
      if (!chartViewport || event.pointerId !== state.pan.pointerId) return;
      const point = svgPointFromEvent(event);
      const dx = point.x - state.pan.startPoint.x;
      const dy = point.y - state.pan.startPoint.y;
      setZoomDomains(
        panDomainByPixels(state.pan.xDomain, dx, [chartViewport.margin.left, chartViewport.margin.left + chartViewport.innerW], state.logX),
        panDomainByPixels(state.pan.yDomain, dy, [chartViewport.margin.top + chartViewport.innerH, chartViewport.margin.top], state.logY),
      );
      event.preventDefault();
    }

    function handleChartPointerLeave() {
      state.hoverHitSignature = "";
      state.dismissedTooltipKeys.clear();
      setHoverPoints([]);
    }

    function endChartPan(event) {
      if (!state.pan || event.pointerId !== state.pan.pointerId) return;
      if (chart.hasPointerCapture(event.pointerId)) chart.releasePointerCapture(event.pointerId);
      state.pan = null;
      chart.classList.remove("is-panning");
    }

    function setZoomDomains(xDomain, yDomain) {
      if (!chartViewport) return;
      const nextX = constrainDomain(xDomain, chartViewport.baseXDomain, state.logX);
      const nextY = constrainDomain(yDomain, chartViewport.baseYDomain, state.logY);
      state.zoom = sameDomain(nextX, chartViewport.baseXDomain, state.logX) && sameDomain(nextY, chartViewport.baseYDomain, state.logY)
        ? null
        : { xDomain: nextX, yDomain: nextY };
      const rows = filteredRows();
      renderChart(rows);
      refreshTooltip(rows);
    }

    function svgPointFromEvent(event) {
      const rect = chart.getBoundingClientRect();
      const scaleX = chartViewport.width / Math.max(rect.width, 1);
      const scaleY = chartViewport.height / Math.max(rect.height, 1);
      return {
        x: (event.clientX - rect.left) * scaleX,
        y: (event.clientY - rect.top) * scaleY,
      };
    }

    function pointInPlot(point) {
      const { margin, innerW, innerH } = chartViewport;
      return point.x >= margin.left
        && point.x <= margin.left + innerW
        && point.y >= margin.top
        && point.y <= margin.top + innerH;
    }

    function clampPointToPlot(point) {
      const { margin, innerW, innerH } = chartViewport;
      return {
        x: clamp(point.x, margin.left, margin.left + innerW),
        y: clamp(point.y, margin.top, margin.top + innerH),
      };
    }

    function updateHoverFromPointer(event) {
      if (!chartViewport || !chartHitTargets.length) return;
      const point = svgPointFromEvent(event);
      if (!pointInPlot(point)) {
        state.hoverHitSignature = "";
        state.dismissedTooltipKeys.clear();
        setHoverPoints([]);
        return;
      }
      const hits = hitTargetsAt(point);
      if (!hits.length) {
        state.hoverHitSignature = "";
        state.dismissedTooltipKeys.clear();
        setHoverPoints([]);
        return;
      }
      const signature = hits.map(hit => hit.key).join("|");
      if (signature !== state.hoverHitSignature) {
        state.hoverHitSignature = signature;
        state.dismissedTooltipKeys.clear();
      }
      const visibleHits = hits.filter(hit => !state.dismissedTooltipKeys.has(hit.key));
      const nextRefs = dedupeTooltipRefs(visibleHits);
      setHoverPoints(nextRefs);
      if (nextRefs.length && !sameTooltipRefs(nextRefs, state.lastTooltipItems)) {
        state.lastTooltipItems = nextRefs;
        refreshTooltip(currentChartRows);
      }
    }

    function hitTargetsAt(point) {
      const rect = chart.getBoundingClientRect();
      const scaleX = Math.max(rect.width, 1) / chartViewport.width;
      const scaleY = Math.max(rect.height, 1) / chartViewport.height;
      return chartHitTargets
        .map(target => ({
          ...target,
          distance: Math.hypot((target.x - point.x) * scaleX, (target.y - point.y) * scaleY),
        }))
        .filter(target => target.distance <= CHART_HIT_RADIUS_PX)
        .sort((a, b) => a.distance - b.distance || a.order - b.order);
    }

    function invertScale(pixel, domain, range, logScale) {
      const ratio = (pixel - range[0]) / (range[1] - range[0]);
      if (logScale) {
        const d0 = Math.log10(Math.max(domain[0], 1e-9));
        const d1 = Math.log10(Math.max(domain[1], 1e-9));
        return Math.pow(10, d0 + ratio * (d1 - d0));
      }
      return domain[0] + ratio * (domain[1] - domain[0]);
    }

    function zoomDomainAround(domain, focalValue, factor, logScale) {
      if (!Number.isFinite(focalValue) || factor <= 0) return domain;
      if (logScale) {
        const d0 = Math.log10(Math.max(domain[0], 1e-9));
        const d1 = Math.log10(Math.max(domain[1], 1e-9));
        const focal = Math.log10(Math.max(focalValue, 1e-9));
        return [
          Math.pow(10, focal - (focal - d0) * factor),
          Math.pow(10, focal + (d1 - focal) * factor),
        ];
      }
      return [
        focalValue - (focalValue - domain[0]) * factor,
        focalValue + (domain[1] - focalValue) * factor,
      ];
    }

    function panDomainByPixels(domain, pixelDelta, range, logScale) {
      const first = invertScale(range[0] - pixelDelta, domain, range, logScale);
      const second = invertScale(range[1] - pixelDelta, domain, range, logScale);
      return [Math.min(first, second), Math.max(first, second)];
    }

    function constrainDomain(domain, baseDomain, logScale) {
      if (!domain || !baseDomain) return baseDomain;
      const toSpace = value => logScale ? Math.log10(Math.max(value, 1e-9)) : value;
      const fromSpace = value => logScale ? Math.pow(10, value) : value;
      let start = Math.min(toSpace(domain[0]), toSpace(domain[1]));
      let end = Math.max(toSpace(domain[0]), toSpace(domain[1]));
      const baseStart = Math.min(toSpace(baseDomain[0]), toSpace(baseDomain[1]));
      const baseEnd = Math.max(toSpace(baseDomain[0]), toSpace(baseDomain[1]));
      const baseSpan = Math.max(baseEnd - baseStart, 1e-9);
      let span = Math.max(end - start, baseSpan / 1000);
      if (span >= baseSpan) return baseDomain.slice();
      const midpoint = (start + end) / 2;
      start = midpoint - span / 2;
      end = midpoint + span / 2;
      if (start < baseStart) {
        end += baseStart - start;
        start = baseStart;
      }
      if (end > baseEnd) {
        start -= end - baseEnd;
        end = baseEnd;
      }
      return [fromSpace(start), fromSpace(end)];
    }

    function sameDomain(a, b, logScale) {
      if (!a || !b) return false;
      const toSpace = value => logScale ? Math.log10(Math.max(value, 1e-9)) : value;
      const b0 = toSpace(b[0]);
      const b1 = toSpace(b[1]);
      const tolerance = Math.max(Math.abs(b1 - b0), 1) * 1e-8;
      return Math.abs(toSpace(a[0]) - b0) <= tolerance && Math.abs(toSpace(a[1]) - b1) <= tolerance;
    }

    function drawGridAndAxes(ctx) {
      const { width, height, margin, innerW, innerH, x, y, xDomain, yDomain } = ctx;
      const xTicks = state.logX ? logTicks(...xDomain) : linearTicks(...xDomain, 7);
      const yMaxTicks = maxAxisTicks(innerH);
      const yTicks = state.logY ? logTicks(...yDomain, yMaxTicks) : linearTicks(...yDomain, yMaxTicks);
      const grid = svgEl("g", { class: "grid" });
      yTicks.forEach(tick => {
        grid.appendChild(svgEl("line", { x1: margin.left, x2: margin.left + innerW, y1: y(tick), y2: y(tick) }));
      });
      xTicks.forEach(tick => {
        grid.appendChild(svgEl("line", { x1: x(tick), x2: x(tick), y1: margin.top, y2: margin.top + innerH }));
      });
      chart.appendChild(grid);

      const axis = svgEl("g", { class: "axis" });
      axis.appendChild(svgEl("line", { x1: margin.left, x2: margin.left + innerW, y1: margin.top + innerH, y2: margin.top + innerH }));
      axis.appendChild(svgEl("line", { x1: margin.left, x2: margin.left, y1: margin.top, y2: margin.top + innerH }));
      xTicks.forEach(tick => {
        const gx = x(tick);
        axis.appendChild(svgEl("line", { x1: gx, x2: gx, y1: margin.top + innerH, y2: margin.top + innerH + 5 }));
        const text = svgEl("text", { x: gx, y: margin.top + innerH + 22, "text-anchor": "middle" });
        text.textContent = formatResearch(tick);
        axis.appendChild(text);
      });
      yTicks.forEach(tick => {
        const gy = y(tick);
        axis.appendChild(svgEl("line", { x1: margin.left - 5, x2: margin.left, y1: gy, y2: gy }));
        const text = svgEl("text", { x: margin.left - 10, y: gy + 4, "text-anchor": "end" });
        text.textContent = formatTick(tick);
        axis.appendChild(text);
      });
      const xTitle = svgEl("text", { class: "axis-title", x: margin.left + innerW / 2, y: height - 22, "text-anchor": "middle" });
      xTitle.textContent = `누적 연구력${state.logX ? " (log)" : ""}`;
      axis.appendChild(xTitle);
      const yTitle = svgEl("text", {
        class: "axis-title",
        x: 18,
        y: margin.top + innerH / 2,
        transform: `rotate(-90 18 ${margin.top + innerH / 2})`,
        "text-anchor": "middle",
      });
      yTitle.textContent = `${metricDefs[state.metric].label}${state.logY ? " (log)" : ""}`;
      axis.appendChild(yTitle);
      chart.appendChild(axis);
    }

    function groupedRows(rows) {
      const groups = new Map();
      rows.forEach(row => {
        if (!groups.has(row.familyKey)) groups.set(row.familyKey, []);
        groups.get(row.familyKey).push(row);
      });
      groups.forEach(group => group.sort((a, b) => a.cumulativeResearch - b.cumulativeResearch || a.baseDisplayName.localeCompare(b.baseDisplayName)));
      return groups;
    }

    function pointAttrs(row, powerOptionId, fill, stroke = "none", strokeWidth = 0) {
      const hovered = isHoveredPoint(row, powerOptionId);
      return {
        class: "data-point",
        "data-row-id": row.id,
        "data-power-option-id": powerOptionId || "",
        "data-default-stroke": stroke,
        "data-default-stroke-width": strokeWidth,
        fill,
        stroke: hovered ? "#fff" : stroke,
        "stroke-width": hovered ? 2.2 : strokeWidth,
      };
    }

    function pointKey(rowId, powerOptionId = null) {
      return `${rowId}::${powerOptionId || ""}`;
    }

    function tooltipRef(rowOrId, powerOptionId = null) {
      const rowId = typeof rowOrId === "object" ? (rowOrId.rowId || rowOrId.id) : rowOrId;
      const optionId = typeof rowOrId === "object" && rowOrId.powerOptionId !== undefined && powerOptionId === null
        ? rowOrId.powerOptionId
        : powerOptionId;
      const normalizedOptionId = optionId || "";
      return { rowId, powerOptionId: normalizedOptionId, key: pointKey(rowId, normalizedOptionId) };
    }

    function dedupeTooltipRefs(items) {
      const refs = [];
      const seen = new Set();
      (items || []).forEach(item => {
        const ref = tooltipRef(item);
        if (!ref.rowId || seen.has(ref.key)) return;
        seen.add(ref.key);
        refs.push(ref);
      });
      return refs;
    }

    function sameTooltipRefs(left, right) {
      const a = dedupeTooltipRefs(left);
      const b = dedupeTooltipRefs(right);
      return a.length === b.length && a.every((item, index) => item.key === b[index].key);
    }

    function isHoveredPoint(row, powerOptionId = null) {
      const key = pointKey(row.id, powerOptionId);
      return state.hoverPoints.some(item => item.key === key);
    }

    function setHoverPoints(items) {
      state.hoverPoints = dedupeTooltipRefs(items);
      updateHoverStyles();
    }

    function registerHitTarget(row, powerOptionId, xCoord, yCoord, radius = 5) {
      if (!Number.isFinite(xCoord) || !Number.isFinite(yCoord) || !pointVisibleInPlot(xCoord, yCoord)) return;
      chartHitTargets.push({
        ...tooltipRef(row, powerOptionId),
        x: xCoord,
        y: yCoord,
        radius,
        order: chartHitTargets.length,
      });
    }

    function pointVisibleInPlot(xCoord, yCoord) {
      if (!chartViewport) return false;
      const { margin, innerW, innerH } = chartViewport;
      return xCoord >= margin.left
        && xCoord <= margin.left + innerW
        && yCoord >= margin.top
        && yCoord <= margin.top + innerH;
    }

    function updateHoverStyles() {
      const hoveredKeys = new Set(state.hoverPoints.map(item => item.key));
      chart.querySelectorAll(".data-point").forEach(point => {
        const hovered = hoveredKeys.has(pointKey(point.getAttribute("data-row-id"), point.getAttribute("data-power-option-id")));
        point.setAttribute("stroke", hovered ? "#fff" : (point.getAttribute("data-default-stroke") || "none"));
        point.setAttribute("stroke-width", hovered ? "2.2" : (point.getAttribute("data-default-stroke-width") || "0"));
      });
    }

    function drawMetricLines(rows, x, y, plot) {
      const groups = groupedRows(rows);
      groups.forEach(group => {
        const color = group[0].familyColor;
        const path = linePath(group.map(row => [x(row.cumulativeResearch), y(metricDefs[state.metric].value(row))]));
        plot.appendChild(svgEl("path", { d: path, fill: "none", stroke: color, "stroke-width": 2.2, "stroke-linejoin": "round", "stroke-linecap": "round", opacity: 0.82 }));
        group.forEach(row => {
          const value = metricDefs[state.metric].value(row);
          if (!Number.isFinite(value) || value <= 0) return;
          const cx = x(row.cumulativeResearch);
          const cy = y(value);
          registerHitTarget(row, null, cx, cy, 5.5);
          const circle = svgEl("circle", { ...pointAttrs(row, null, color), cx, cy, r: 5.5 });
          plot.appendChild(circle);
        });
      });
    }

    function drawTotalMassBands(rows, x, y, plot) {
      const groups = groupedRows(rows);
      groups.forEach(group => {
        const color = group[0].familyBandColor || group[0].familyColor;
        const colorOklch = group[0].familyBandColorOklch || color;
        const fillStyle = paintStyle("fill", color, colorOklch);
        const strokeStyle = paintStyle("stroke", color, colorOklch);
        const maxOptions = Math.max(...group.map(row => massOptions(row).length), 0);
        for (let index = maxOptions - 2; index >= 0; index--) {
          const pairs = group
            .map(row => ({ row, options: massOptions(row) }))
            .filter(item => item.options[index] && item.options[index + 1]);
          if (pairs.length < 2) continue;
          const upper = pairs.map(item => [x(item.row.cumulativeResearch), y(optionMetricValue(item.options[index]))]);
          const lower = pairs.slice().reverse().map(item => [x(item.row.cumulativeResearch), y(optionMetricValue(item.options[index + 1]))]);
          const polygon = [...upper, ...lower];
          plot.appendChild(svgEl("path", {
            d: linePath(polygon) + "Z",
            fill: color,
            style: fillStyle,
            opacity: Math.max(0.06, 0.22 - index * 0.025),
            stroke: "none",
          }));
        }
        for (let index = 0; index < maxOptions; index++) {
          const points = group
            .map(row => ({ row, option: massOptions(row)[index] }))
            .filter(item => item.option);
          if (points.length >= 2) {
            plot.appendChild(svgEl("path", {
              d: linePath(points.map(item => [x(item.row.cumulativeResearch), y(optionMetricValue(item.option))])),
              fill: "none",
              stroke: color,
              style: strokeStyle,
              "stroke-width": index === 0 ? 2.1 : 1.2,
              "stroke-dasharray": index === 0 ? "" : "5 5",
              opacity: index === 0 ? 0.9 : 0.45,
            }));
          }
        }
        group.forEach(row => {
          const options = massOptions(row);
          if (!options.length) return;
          const gx = x(row.cumulativeResearch);
          const ys = options.map(option => y(optionMetricValue(option)));
          plot.appendChild(svgEl("line", { x1: gx, x2: gx, y1: Math.min(...ys), y2: Math.max(...ys), stroke: color, style: strokeStyle, "stroke-width": 1.2, opacity: 0.32 }));
          options.forEach((option, index) => {
            const cy = y(optionMetricValue(option));
            registerHitTarget(row, option.id, gx, cy, index === 0 ? 5 : 3.4);
            const circle = svgEl("circle", {
              ...pointAttrs(row, option.id, index === 0 ? color : "var(--panel)", color, 1.5),
              cx: gx,
              cy,
              r: index === 0 ? 5 : 3.4,
              style: index === 0 ? fillStyle : "",
              opacity: index === 0 ? 0.96 : 0.78,
            });
            plot.appendChild(circle);
          });
        });
      });
    }

    function isBandMetric(metric = state.metric) {
      return metric === "totalMassTons" || metric === "twr";
    }

    function optionMetricValue(option, metric = state.metric) {
      return metric === "twr" ? option.twr : option.totalMassTons;
    }

    function linePath(points) {
      return points.map((point, index) => `${index === 0 ? "M" : "L"}${point[0].toFixed(2)},${point[1].toFixed(2)}`).join(" ");
    }

    function svgEl(name, attrs) {
      const el = document.createElementNS("http://www.w3.org/2000/svg", name);
      Object.entries(attrs || {}).forEach(([key, value]) => {
        if (value !== undefined && value !== null) el.setAttribute(key, String(value));
      });
      return el;
    }

    function paintStyle(property, fallback, preferred) {
      const base = fallback || "#64748b";
      const paint = preferred || base;
      return `${property}:${base};${property}:${paint};`;
    }

    function backgroundStyle(fallback, preferred) {
      return paintStyle("background", fallback, preferred);
    }

    function tooltipPanelHtml(items) {
      const countText = UI_LANG === "en" ? `${items.length} selected` : `선택 항목 ${items.length}개`;
      const count = items.length > 1 ? `<div class="tooltip-count">${countText}</div>` : "";
      return `
        <button class="tooltip-close" type="button" aria-label="선택 해제">&times;</button>
        ${count}
        <div class="tooltip-items">
          ${items.map(item => tooltipHtml(item.row, item.option, item.key)).join("")}
        </div>
      `;
    }

    function tooltipHtml(row, option = null, key = "") {
      const metric = metricDefs[state.metric];
      const value = metric.value(row);
      const radiator = selectedRadiator();
      const breakdown = option ? tooltipBreakdownHtml(row, option) : "";
      const selected = option ? `
        <div><strong>${escapeHtml(option.displayName)}</strong>: ${formatNumber(option.totalMassTons, " t")} total · TWR ${formatNumber(option.twr, "")}</div>
        ${breakdown}
      ` : "";
      return `
        <section class="tooltip-item" data-tooltip-key="${escapeHtml(key)}">
          <button class="tooltip-item-close" type="button" data-tooltip-key="${escapeHtml(key)}" aria-label="항목 삭제">&times;</button>
          <h2>${escapeHtml(row.displayName)}</h2>
          <div class="muted">${escapeHtml(rowCategoryLabel(row))} / ${escapeHtml(rowFamilyLabel(row))} · ${escapeHtml(rowProjectLabel(row))}</div>
          <div>누적 연구력: <strong>${formatResearch(row.cumulativeResearch)}</strong> · 자체 프로젝트: ${formatResearch(row.ownResearchCost)}</div>
          <div>추력: ${formatNumber(row.thrustN / 1e6, " MN")} · EV: ${formatNumber(row.exhaustVelocityKps, " km/s")} · Isp: ${formatNumber(row.specificImpulseSeconds, " s")}</div>
          <div>효율: ${formatPercent(row.efficiency)} · 출력 요구량: ${formatNumber(row.powerRequirementGW, " GW")}</div>
          <div>드라이브 질량: ${formatNumber(row.driveMassTons, " t")}</div>
          <div>라디에이터: ${escapeHtml(radiator ? radiator.displayName : "-")}</div>
          ${!isBandMetric() ? `<div>${escapeHtml(metric.label)}: <strong>${metric.format(value)}</strong></div>` : ""}
          ${selected}
        </section>
      `;
    }

    function tooltipBreakdownHtml(row, option) {
      const components = [
        ["선체", option.baseDryTons, "stack-hull"],
        ["드라이브", row.driveMassTons, "stack-drive"],
        ["전원", option.powerPlantMassTons, "stack-reactor"],
        ["라디에이터", option.radiatorMassTons, "stack-radiator"],
        ["추진체", option.propellantTons, "stack-propellant"],
      ];
      const total = Math.max(option.totalMassTons, 1e-9);
      const componentRows = components.map(([label, value]) => `
            <span>${label}</span><strong>${formatNumber(value, " t")}</strong>
      `).join("");
      const componentSegments = components.map(([label, value, className]) => {
        const share = clamp(value / total * 100, 0, 100);
        return `<span class="${className}" style="width:${share.toFixed(2)}%" title="${label}: ${formatNumber(value, " t")}"></span>`;
      }).join("");
      return `
        <div class="tooltip-breakdown">
          <div class="tooltip-breakdown-grid">
            ${componentRows}
          </div>
          <div class="tooltip-stack" aria-hidden="true">
            ${componentSegments}
          </div>
          <div class="muted">폐열: ${formatNumber(option.wasteHeatGW, " GW")}</div>
        </div>
      `;
    }

    function resolveTooltipItems(rows) {
      const rowById = new Map(rows.map(row => [row.id, row]));
      const resolved = [];
      const seen = new Set();
      state.lastTooltipItems.forEach(item => {
        const ref = tooltipRef(item);
        const row = rowById.get(ref.rowId);
        if (!row) return;
        let option = null;
        let powerOptionId = "";
        if (isBandMetric()) {
          const options = massOptions(row);
          option = options.find(candidate => candidate.id === ref.powerOptionId) || options[0] || null;
          if (!option) return;
          powerOptionId = option.id || "";
        }
        const key = pointKey(row.id, powerOptionId);
        if (seen.has(key)) return;
        seen.add(key);
        resolved.push({ row, option, rowId: row.id, powerOptionId, key });
      });
      return resolved;
    }

    function refreshTooltip(rows = currentChartRows) {
      if (!state.lastTooltipItems.length) {
        renderEmptyTooltip();
        return;
      }
      const resolved = resolveTooltipItems(rows);
      if (!resolved.length) {
        clearTooltip();
        return;
      }
      const resolvedKeys = new Set(resolved.map(item => item.key));
      state.lastTooltipItems = resolved.map(item => tooltipRef(item.rowId, item.powerOptionId));
      state.hoverPoints = state.hoverPoints.filter(item => resolvedKeys.has(item.key));
      tooltip.innerHTML = tooltipPanelHtml(resolved);
      tooltip.classList.remove("tooltip-empty");
      updateHoverStyles();
    }

    function removeTooltipItem(key) {
      if (!key) return;
      state.dismissedTooltipKeys.add(key);
      state.lastTooltipItems = state.lastTooltipItems.filter(item => tooltipRef(item).key !== key);
      state.hoverPoints = state.hoverPoints.filter(item => item.key !== key);
      if (state.lastTooltipItems.length) {
        refreshTooltip(currentChartRows);
      } else {
        renderEmptyTooltip();
      }
      updateHoverStyles();
    }

    function renderEmptyTooltip() {
      tooltip.innerHTML = `<div class="tooltip-placeholder">선택 없음</div>`;
      tooltip.classList.add("tooltip-empty");
    }

    function clearTooltip() {
      state.lastTooltipItems = [];
      state.hoverPoints = [];
      state.dismissedTooltipKeys.clear();
      state.hoverHitSignature = "";
      renderEmptyTooltip();
      updateHoverStyles();
    }

    function renderTable(rows) {
      const tbody = document.getElementById("tableBody");
      tbody.innerHTML = "";
      const maxResearch = Math.max(...rows.map(row => row.cumulativeResearch).filter(Number.isFinite), 1);
      const metricDomain = tableMetricDomain(rows);
      const sorted = sortRows(rows);
      sorted.forEach(row => {
        const tr = document.createElement("tr");
        const powerOptions = massOptions(row);
        const powerCell = powerOptions.length
          ? reactorBandLabel(powerOptions)
          : `<span class="warning">없음</span>`;
        tr.innerHTML = `
          <td><div class="drive-name">${escapeHtml(row.displayName)}</div><div class="project-name">${escapeHtml(rowProjectLabel(row))}</div></td>
          <td><span class="pill"><span class="family-swatch" style="${backgroundStyle(row.familyColor, row.familyColorOklch || row.familyColor)}"></span>${escapeHtml(rowCategoryLabel(row))} / ${escapeHtml(rowFamilyLabel(row))}</span></td>
          <td class="numeric">${researchCell(row, maxResearch)}</td>
          <td class="numeric">${metricCell(row, metricDomain)}</td>
          <td>${powerCell}</td>
        `;
        tbody.appendChild(tr);
      });
    }

    function sortRows(rows) {
      const direction = state.sortDirection === "asc" ? 1 : -1;
      return rows.slice().sort((a, b) => {
        const aValue = sortValue(a, state.sortKey);
        const bValue = sortValue(b, state.sortKey);
        let result;
        if (typeof aValue === "number" && typeof bValue === "number") {
          result = aValue - bValue;
        } else {
          result = String(aValue ?? "").localeCompare(String(bValue ?? ""), undefined, { numeric: true, sensitivity: "base" });
        }
        if (result === 0) {
          result = a.cumulativeResearch - b.cumulativeResearch || a.displayName.localeCompare(b.displayName);
        }
        return result * direction;
      });
    }

    function sortValue(row, key) {
      if (key === "drive") return row.displayName;
      if (key === "family") return `${rowCategoryLabel(row)} / ${rowFamilyLabel(row)}`;
      if (key === "research") return row.cumulativeResearch;
      if (key === "metric") return metricDefs[state.metric].value(row);
      if (key === "reactor") {
        const options = massOptions(row);
        return options.length ? reactorBandText(options) : "";
      }
      return row.cumulativeResearch;
    }

    function researchCell(row, maxResearch) {
      const width = clamp(row.cumulativeResearch / maxResearch * 100, 0, 100);
      return `
        <div class="cell-viz" title="${formatNumber(row.cumulativeResearch, " research")}">
          <span class="cell-value">${formatResearch(row.cumulativeResearch)}</span>
          <div class="sparkbar" aria-hidden="true"><span class="spark-fill" style="width:${width.toFixed(2)}%"></span></div>
        </div>
      `;
    }

    function tableMetricDomain(rows) {
      const values = rows.flatMap(row => {
        if (isBandMetric()) {
          return optionRange(row).values;
        }
        const value = metricDefs[state.metric].value(row);
        return Number.isFinite(value) && value > 0 ? [value] : [];
      });
      if (!values.length) return { min: 0, max: 1, log: false };
      const min = Math.min(...values);
      const max = Math.max(...values);
      const log = shouldUseSparkLog(values);
      return { min, max, log };
    }

    function shouldUseSparkLog(values) {
      const positive = values.filter(value => Number.isFinite(value) && value > 0);
      if (!positive.length) return false;
      const min = Math.min(...positive);
      const max = Math.max(...positive);
      if (state.metric === "totalMassTons") return true;
      return min > 0 && max / min >= 50;
    }

    function metricCell(row, domain) {
      if (isBandMetric()) {
        return rangeMetricCell(row, domain);
      }
      const value = metricDefs[state.metric].value(row);
      if (!Number.isFinite(value)) return "-";
      const position = sparkPosition(value, domain);
      return `
        <div class="cell-viz" title="${metricDefs[state.metric].format(value)}${domain.log ? " · log sparkline" : ""}">
          <span class="cell-value">${metricDefs[state.metric].format(value)}</span>
          <div class="sparkbar" aria-hidden="true"><span class="spark-fill" style="width:${position.toFixed(2)}%"></span></div>
        </div>
      `;
    }

    function optionRange(row) {
      const options = massOptions(row);
      const values = options.map(option => optionMetricValue(option)).filter(Number.isFinite);
      if (!values.length) return { values: [], min: NaN, max: NaN };
      return { values, min: Math.min(...values), max: Math.max(...values) };
    }

    function rangeMetricCell(row, domain) {
      const range = optionRange(row);
      if (!range.values.length) return "-";
      const left = sparkPosition(range.min, domain);
      const right = sparkPosition(range.max, domain);
      const width = Math.max(right - left, 0.5);
      const formatter = metricDefs[state.metric].format;
      return `
        <div class="cell-viz" title="${formatter(range.min)} - ${formatter(range.max)}${domain.log ? " · log sparkline" : ""}">
          <span class="cell-value">${formatter(range.min)} - ${formatter(range.max)}</span>
          <div class="sparkrange" aria-hidden="true"><span class="sparkrange-fill" style="left:${left.toFixed(2)}%;width:${width.toFixed(2)}%"></span></div>
        </div>
      `;
    }

    function sparkPosition(value, domain) {
      if (!Number.isFinite(value)) return 0;
      if (domain.log) {
        const min = Math.max(domain.min, 1e-9);
        const max = Math.max(domain.max, min * 1.01);
        const span = Math.max(Math.log10(max) - Math.log10(min), 1e-9);
        return clamp((Math.log10(Math.max(value, 1e-9)) - Math.log10(min)) / span * 100, 0, 100);
      }
      const span = Math.max(domain.max - domain.min, 1e-9);
      return clamp((value - domain.min) / span * 100, 0, 100);
    }

    function reactorBandLabel(options) {
      return escapeHtml(reactorBandText(options));
    }

    function reactorBandText(options) {
      if (!options.length) return "";
      const first = String(options[0].displayName || "");
      if (options.length === 1) return first;
      const last = String(options[options.length - 1].displayName || "");
      const firstRoman = splitRomanSuffix(first);
      const lastRoman = splitRomanSuffix(last);
      if (firstRoman && lastRoman && firstRoman.base === lastRoman.base) {
        return `${first} → ${lastRoman.roman}`;
      }
      return `${first} → ${last}`;
    }

    function splitRomanSuffix(value) {
      const match = String(value).match(/^(.*\S)\s+([IVXLCDM]+)$/);
      if (!match) return null;
      return { base: match[1], roman: match[2] };
    }

    function escapeHtml(value) {
      return String(value ?? "").replace(/[&<>"']/g, char => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;",
      }[char]));
    }

    function formatResearch(value) {
      if (!Number.isFinite(value)) return "-";
      return formatCompact(value, 1_000);
    }

    function formatTick(value) {
      if (!Number.isFinite(value)) return "-";
      if (Math.abs(value) < 1 && value !== 0) return value.toPrecision(2);
      return formatCompact(value, 1_000);
    }

    function formatNumber(value, suffix = "") {
      if (!Number.isFinite(value)) return "-";
      return `${formatCompact(value, 1_000_000)}${suffix}`;
    }

    function formatCompact(value, threshold = 1_000) {
      if (!Number.isFinite(value)) return "-";
      const abs = Math.abs(value);
      if (abs < threshold) return trim(value);
      const suffixes = ["", "k", "M", "B", "T", "Qa", "Qi", "Sx", "Sp", "Oc", "No", "Dc"];
      let tier = Math.floor(Math.log10(abs) / 3);
      if (tier >= suffixes.length) return Number(value).toExponential(0).replace("e+", "e");
      let scaled = value / Math.pow(1000, tier);
      if (Math.abs(scaled) >= 999.5 && tier < suffixes.length - 1) {
        tier += 1;
        scaled = value / Math.pow(1000, tier);
      }
      return `${trim(scaled)}${suffixes[tier]}`;
    }

    function trim(value) {
      if (!Number.isFinite(value)) return "-";
      const abs = Math.abs(value);
      const digits = abs >= 100 ? 0 : abs >= 10 ? 1 : abs >= 1 ? 2 : 3;
      return Number(value).toLocaleString("en-US", { maximumFractionDigits: digits });
    }

    function formatPercent(value) {
      return Number.isFinite(value) ? `${trim(value * 100)}%` : "-";
    }

    setupControls();
    render();
    window.addEventListener("resize", render);
  </script>
</body>
</html>
"""


ENGLISH_BLOCK_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    (
        "<strong>계산 메모.</strong> 총질량은 기준 선체 건조 질량, 드라이브 질량, 전원 질량, 선택 라디에이터 질량, 목표 dV에 필요한 추진체 질량을 합산합니다. 드라이브 출력 요구량, 드라이브 질량, 전원 질량, 라디에이터 질량은 이 저장소의 기존 ship-plan 계산식과 같은 항을 사용하며, 무장/유틸리티 전력은 제외해 드라이브-전원-라디에이터 비교만 분리했습니다.",
        "<strong>Calculation note.</strong> Total mass adds the base hull dry mass, drive mass, power plant mass, selected radiator mass, and propellant mass required for the target dV. Drive power requirement, drive mass, power plant mass, and radiator mass use the same terms as this repository's ship-plan calculation, with weapon and utility power excluded to isolate the drive-power-radiator comparison.",
    ),
    (
        "총질량 = 기준 건조질량 + 드라이브 + 전원 + 라디에이터 + 추진체",
        "Total mass = base dry mass + drive + power plant + radiator + propellant",
    ),
    (" 밴드: 개방 전원부터 이후 전원 후보", " band: unlocked power plant through later candidates"),
)


ENGLISH_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    ('<html lang="ko">', '<html lang="en">'),
    ("Terra Invicta 드라이브 비교", "Terra Invicta Drive Comparison"),
    (
        "X축은 로컬 연구 카탈로그에서 계산한 최소 누적 연구력입니다. 총질량 그래프는 각 드라이브 개방 시점의 호환 전원부터 이후 전원 후보까지 적용했을 때의 목표 dV 달성 질량을 보여주며, breakdown은 차트 오른쪽 상세 패널에서 확인할 수 있습니다.",
        "The X axis is the minimum cumulative research computed from the local research catalog. Total-mass charts show the target dV mass from the compatible power plant available when each drive unlocks through later power candidates; the breakdown appears in the detail panel on the right side of the chart.",
    ),
    ("세로축", "Vertical axis"),
    ("이름 검색", "Name search"),
    ("드라이브 또는 프로젝트", "Drive or project"),
    ("추력 (MN)", "Thrust (MN)"),
    ("연료효율 (km/s or s)", "Fuel efficiency (km/s or s)"),
    ("연료효율 (km/s)", "Fuel efficiency (km/s)"),
    ("연료효율 (s)", "Fuel efficiency (s)"),
    ("출력 요구량 (GW)", "Power requirement (GW)"),
    ("목표 dV 총질량 (t)", "Target dV total mass (t)"),
    ("엔진 수", "Engine count"),
    ("기준 선체 건조 질량 (t)", "Base hull dry mass (t)"),
    ("목표 dV (km/s)", "Target dV (km/s)"),
    ("라디에이터", "Radiator"),
    ("축 스케일", "Axis scale"),
    ("X축 로그", "Log X axis"),
    ("Y축 로그", "Log Y axis"),
    ("대분류 / 세부 계열", "Category / Subfamily"),
    ("대분류", "Category"),
    ("세부 계열", "Subfamily"),
    ("전체 선택", "Select all"),
    ("전체 해제", "Clear all"),
    ("보기 초기화", "Reset view"),
    ("개 추진기 표시", " drives shown"),
    ("개 드라이브 표시", " drives shown"),
    ("선택 없음", "No selection"),
    ("추진기", "Drive"),
    ("누적 연구력", "Cumulative research"),
    ("값", "Value"),
    ("전원 단계", "Power plant tier"),
    ("템플릿 thrust_N을 MN으로 환산", "Template thrust_N converted to MN"),
    ("템플릿 EV_kps", "Template EV_kps"),
    ("추력 / (목표 dV 총질량 * g)", "Thrust / (target dV total mass * g)"),
    ("추력:", "Thrust:"),
    ("출력 요구량:", "Power requirement:"),
    ("선택 해제", "Clear selection"),
    ("항목 삭제", "Remove item"),
    ("자체 프로젝트", "Own project"),
    ("효율", "Efficiency"),
    ("드라이브 질량", "Drive mass"),
    ("선체", "Hull"),
    ("드라이브", "Drive"),
    ("전원", "Power plant"),
    ("추진체", "Propellant"),
    ("폐열", "Waste heat"),
    ("없음", "None"),
)


def portable_source_label(key: str, value: Any) -> str:
    if key == "templatesDir":
        return "TerraInvicta_Data/StreamingAssets/Templates"
    name = Path(str(value)).name
    return name or str(value)


def portable_data(data: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(data)
    source = result.get("source")
    if isinstance(source, dict):
        result["source"] = {
            key: portable_source_label(str(key), value)
            for key, value in source.items()
        }
    return result


def build_html(data: dict[str, Any], lang: str = "ko", portable: bool = False) -> str:
    if portable:
        data = portable_data(data)
    html = HTML_TEMPLATE
    if lang == "en":
        for korean, english in ENGLISH_BLOCK_REPLACEMENTS:
            html = html.replace(korean, english)
        for korean, english in ENGLISH_REPLACEMENTS:
            html = html.replace(korean, english)
        html = html.replace(
            "row.requiredProjectDisplay.ko || row.requiredProjectDisplay.en || row.requiredProject",
            "row.requiredProjectDisplay.en || row.requiredProjectDisplay.ko || row.requiredProject",
        )
    data_json = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    html = html.replace("__DATA_JSON__", data_json.replace("</script", "<\\/script"))
    return html


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--templates-dir", help="Path to TerraInvicta_Data/StreamingAssets/Templates.")
    parser.add_argument(
        "--research-catalog",
        default=str(ROOT / "data" / "research_catalog.json"),
        help="Path to generated research_catalog.json.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Standalone HTML output path.",
    )
    parser.add_argument(
        "--lang",
        choices=("ko", "en"),
        default="ko",
        help="Dashboard UI language.",
    )
    parser.add_argument(
        "--portable",
        action="store_true",
        help="Scrub local absolute source paths so the generated single HTML file is suitable for sharing.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    templates_dir = resolve_templates_dir(args.templates_dir)
    if templates_dir is None:
        raise SystemExit("Templates directory not found. Pass --templates-dir.")
    research_catalog = Path(args.research_catalog).expanduser().resolve()
    if not research_catalog.is_file():
        raise SystemExit(f"Research catalog not found: {research_catalog}")
    if args.output:
        default_output = Path(args.output)
    elif args.portable:
        default_output = ROOT / ("drive_comparison_en_portable.html" if args.lang == "en" else "drive_comparison_portable.html")
    else:
        default_output = ROOT / ("drive_comparison_en.html" if args.lang == "en" else "drive_comparison.html")
    output = default_output.expanduser().resolve()
    data = build_data(templates_dir, research_catalog)
    html = build_html(data, args.lang, args.portable)
    output.write_text(html, encoding="utf-8")
    print(f"Wrote {output}")
    print(f"Drive variants: {len(data['drives'])}")
    print(f"Categories: {len(data['categories'])}")
    print(f"Subfamilies: {len(data['subfamilies'])}")


if __name__ == "__main__":
    main()
