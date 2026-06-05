"""Build a standalone all-drive comparison dashboard from local TI data."""

from __future__ import annotations

import argparse
import copy
import json
import math
import re
import sys
from pathlib import Path
from typing import Any, Iterable


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
TARGET_DV_KPS = 500.0
DEFAULT_DRY_MASS_TONS = 10000.0

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

CATEGORY_HELP: dict[str, dict[str, str]] = {
    "Chemical": {
        "ko": "고추력·저효율 계통입니다. 연구 부담은 낮지만 장거리 dV에서는 추진체가 급증하므로 초반 단거리 요격, 저궤도 방어, 낮은 dV 프리셋을 점검할 때 유용합니다.",
        "en": "High-thrust, low-efficiency drives. They are cheap to unlock, but propellant mass grows quickly at high dV, so use them for early short-range interceptors, orbital defense, and low-dV presets.",
    },
    "Electric": {
        "ko": "고효율·저추력 계통입니다. 느린 장거리 이동과 저가 운용에는 좋지만 전투 가속은 낮은 편이어서 TWR 필터와 전원/라디에이터 조합을 함께 확인하는 것이 좋습니다.",
        "en": "High-efficiency, low-thrust drives. They suit slow long-range transfers and cheap operation, but combat acceleration is usually low, so inspect TWR together with power and radiator choices.",
    },
    "Fission": {
        "ko": "초중반의 실전형 전환 계통입니다. 화학보다 효율이 좋고 핵융합보다 빨리 열리므로 내행성권 전투함, 순찰함, 중간 dV 임무를 비교할 때 적합합니다.",
        "en": "Practical early-to-midgame transition drives. They beat chemical efficiency and unlock before most fusion paths, making them useful for inner-system warships, patrol craft, and medium-dV missions.",
    },
    "Fusion": {
        "ko": "중후반 핵심 투자 후보입니다. 계열별 성격 차이가 크지만 대체로 높은 dV와 실전 TWR을 함께 노릴 수 있어 어떤 핵융합 라인에 연구력을 넣을지 비교하기 좋습니다.",
        "en": "Core mid-to-lategame investment candidates. Families differ sharply, but many can combine high dV with usable combat TWR, making this category the main place to compare fusion research paths.",
    },
    "Antimatter": {
        "ko": "최후반 고성능·고비용 계통입니다. 연구와 자원 부담이 크지만 빠른 전략 기동과 고성능 전투함을 노릴 때 총질량/TWR의 상한선을 확인하기 좋습니다.",
        "en": "Very-lategame, high-performance, high-cost drives. They are expensive in research and resources, but useful for checking the ceiling of fast strategic movement and elite combat ship designs.",
    },
    "Alien": {
        "ko": "외계 부품 참고용 계통입니다. 일반적인 인류 연구 투자 대상은 아니며, 성능 기준선이나 데이터 확인을 위해 필요할 때만 켜는 편이 좋습니다.",
        "en": "Reference category for alien components. These are not normal human research investments; enable them mainly for benchmarks or data inspection.",
    },
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

    def closure_cost(self, closure: Iterable[str]) -> float:
        return sum(self.own_cost(node_name) for node_name in set(closure))

    def combined_cumulative_cost(self, *names: str | None) -> float:
        closure: set[str] = set()
        for name in names:
            closure.update(self.closure(name))
        return self.closure_cost(closure)

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
        for option in row["powerOptions"]:
            option["combinedCumulativeResearch"] = research.combined_cumulative_cost(
                project,
                str(option.get("requiredProject") or "") or None,
            )
        first_power_research = (
            as_float(row["powerOptions"][0].get("combinedCumulativeResearch"), 0.0)
            if row["powerOptions"]
            else 0.0
        )
        row["unlockCumulativeResearch"] = max(cumulative, first_power_research)
        drive_rows.append(row)

    present_categories = {row["categoryKey"] for row in drive_rows}
    categories = []
    for category_key in CATEGORY_ORDER:
        if category_key not in CATEGORY_META:
            continue
        if category_key not in present_categories and category_key != "Alien":
            continue
        category_meta = CATEGORY_META[category_key]
        category_help = CATEGORY_HELP.get(category_key, {})
        categories.append(
            {
                "key": category_key,
                "label": label_text(category_meta["label"], "ko"),
                "labelEn": label_text(category_meta["label"], "en"),
                "help": label_text(category_help, "ko"),
                "helpEn": label_text(category_help, "en"),
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
      position: relative;
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
    .control-hint {
      margin-top: 6px;
      color: var(--muted);
      font-size: 11px;
      line-height: 1.35;
    }
    [data-help] {
      cursor: help;
    }
    .family-name {
      min-width: 0;
      flex: 1 1 auto;
    }
    .family-count {
      margin-left: auto;
      color: var(--muted);
      font-size: 11px;
      font-variant-numeric: tabular-nums;
      white-space: nowrap;
    }
    .family-warnings {
      display: grid;
      gap: 5px;
      margin-top: 8px;
    }
    .family-warning {
      border: 1px solid rgba(245, 158, 11, 0.35);
      border-radius: 6px;
      padding: 6px 8px;
      background: rgba(245, 158, 11, 0.08);
      color: #f1c17e;
      font-size: 11px;
      line-height: 1.35;
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
    .toggle-button {
      display: inline-flex;
      align-items: center;
      width: auto;
      justify-content: center;
      margin-top: 0;
      white-space: nowrap;
    }
    .toggle-button[aria-pressed="true"] {
      border-color: #0f766e;
      background: rgba(20, 184, 166, 0.16);
      color: #b9fff4;
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
      font-size: 12px;
    }
    .axis path, .axis line {
      stroke: var(--strong-line);
      shape-rendering: crispEdges;
    }
    .grid line {
      stroke: #2a302c;
      shape-rendering: crispEdges;
    }
    .axis .axis-title {
      fill: #d8e1db;
      font-size: 16px;
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
    .diagnostic-banner {
      margin: 0 0 10px;
      padding: 7px 9px;
      border: 1px solid rgba(245, 158, 11, 0.32);
      border-radius: 6px;
      background: rgba(245, 158, 11, 0.07);
      color: #f1c17e;
      font-size: 12px;
      line-height: 1.35;
    }
    .diagnostic-banner[hidden] {
      display: none;
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
      z-index: 5;
    }
    .tooltip.tooltip-empty {
      display: flex;
      align-items: center;
      justify-content: center;
      color: var(--muted);
      padding: 12px;
    }
    .tooltip.tooltip-empty.has-diagnostic,
    .tooltip.tooltip-empty.has-panel {
      align-items: stretch;
      justify-content: flex-start;
      color: var(--ink);
      padding: 12px;
    }
    .tooltip-placeholder {
      color: var(--muted);
    }
    .scenario-panel,
    .usage-panel {
      display: grid;
      gap: 9px;
      width: 100%;
      color: #d8e1db;
    }
    .scenario-panel h2,
    .usage-panel h2 {
      margin: 0;
      color: var(--ink);
      font-size: 14px;
      line-height: 1.3;
    }
    .scenario-panel p,
    .usage-panel p {
      margin: 0;
      color: #a9b5ad;
      line-height: 1.45;
    }
    .scenario-panel ul,
    .usage-panel ul {
      margin: 0;
      padding-left: 18px;
      color: #cdd7d0;
    }
    .scenario-panel li,
    .usage-panel li {
      margin: 3px 0;
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
    .tooltip-pin {
      display: inline-flex;
      align-items: center;
      min-height: 18px;
      padding: 1px 6px;
      margin-right: 7px;
      border: 1px solid #936f33;
      border-radius: 999px;
      background: rgba(224, 149, 61, 0.13);
      color: #f1c17e;
      font-size: 11px;
      font-weight: 700;
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
      padding: 9px 36px 9px 40px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #151816;
    }
    .tooltip-item.is-pinned {
      border-color: rgba(224, 149, 61, 0.75);
      box-shadow: inset 0 0 0 1px rgba(224, 149, 61, 0.12);
    }
    .tooltip-item-order {
      position: absolute;
      top: 7px;
      left: 7px;
      display: grid;
      grid-template-columns: 1fr;
      gap: 3px;
    }
    .tooltip-item-move {
      width: 26px;
      height: 18px;
      min-height: 0;
      padding: 0;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      border-radius: 6px;
      border-color: var(--line);
      background: #202421;
      color: var(--muted);
      font-size: 11px;
      line-height: 1;
      user-select: none;
    }
    .tooltip-item-move:hover:not(:disabled) {
      color: var(--ink);
      border-color: var(--strong-line);
    }
    .tooltip-item-move:disabled {
      opacity: 0.35;
      cursor: default;
    }
    .tooltip-item-actions {
      position: absolute;
      top: 7px;
      right: 7px;
      display: grid;
      grid-template-columns: 1fr;
      gap: 5px;
      align-items: start;
    }
    .tooltip-item-pin,
    .tooltip-item-close {
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
    .tooltip-item-pin {
      width: 22px;
      min-width: 0;
      padding: 0;
      font-size: 13px;
      font-weight: 700;
    }
    .tooltip-item-pin[aria-pressed="true"] {
      border-color: #936f33;
      background: rgba(224, 149, 61, 0.16);
      color: #f1c17e;
    }
    .tooltip-item-pin:hover,
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
    .tooltip-title-power {
      display: block;
      margin-top: 2px;
      color: #f1c17e;
      font-size: 12px;
      font-weight: 600;
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
      X축은 최초 호환 전원을 포함한 누적 연구력입니다. 같은 연구력 대비 총질량, TWR, 추력, 효율을 비교해 어느 추진기 계통에 투자할지 판단하는 데 초점을 둡니다.
    </div>
  </header>
  <main>
    <aside class="controls">
      <section class="control-block">
        <label class="label" for="metric">세로축</label>
        <select id="metric">
          <optgroup label="시뮬레이션(총 질량, TWR)">
            <option value="totalMassTons">목표 dV 총질량 (t)</option>
            <option value="twr">TWR</option>
          </optgroup>
          <optgroup label="기본 정보(추력, 효율, 출력)">
            <option value="thrustMN">추력 (MN)</option>
            <option value="fuelEfficiency">연료효율 (km/s or s)</option>
            <option value="powerRequirementGW">출력 요구량 (GW)</option>
          </optgroup>
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
          <input id="dryMass" type="range" min="100" max="100000" value="10000" step="100">
          <input id="dryMassNumber" type="number" min="0" max="1000000" value="10000" step="10">
        </div>
      </section>
      <section class="control-block">
        <label class="label" for="targetDv">목표 dV (km/s)</label>
        <div class="split">
          <input id="targetDv" type="range" min="0" max="2000" value="500" step="5">
          <input id="targetDvNumber" type="number" min="0" max="100000" value="500" step="1">
        </div>
      </section>
      <section class="control-block">
        <label class="label" for="radiator">라디에이터</label>
        <select id="radiator"></select>
      </section>
      <section id="bandAnalysisControls" class="control-block">
        <span class="label">총질량/TWR 보조 표시</span>
        <label id="showTwrInfoRow" class="check-row"><input id="showTwrInfo" type="checkbox" checked> TWR 정보 표시</label>
        <label id="showMassInfoRow" class="check-row" style="display: none;"><input id="showMassInfo" type="checkbox" checked> 총질량 정보 표시</label>
        <label class="check-row"><input id="paretoHighlight" type="checkbox" checked> 파레토 후보 강조</label>
        <label class="check-row"><input id="showImpracticalCandidates" type="checkbox"> 비현실적 후보 표시</label>
        <div id="minTwrControl" style="margin-top: 10px;">
          <label class="label" for="minTwrExp">최소 TWR</label>
          <div class="split">
            <input id="minTwrExp" type="range" min="-4" max="1" value="-4" step="0.1">
            <input id="minTwrNumber" type="number" min="0.0001" max="10" value="0.0001" step="0.0001">
          </div>
          <div id="minTwrReadout" class="control-hint">표시: TWR >= 0.0001 g</div>
        </div>
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
        <div id="familyWarnings" class="family-warnings"></div>
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
          <button id="powerResearchToggle" class="compact-command toggle-button" type="button" aria-pressed="false" style="display: none;">추가 전원 연구력 반영</button>
          <button id="resetZoom" class="compact-command" type="button" disabled>보기 초기화</button>
          <div id="metricHint"></div>
        </div>
      </div>
      <div id="chartDiagnostic" class="diagnostic-banner" hidden></div>
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
      metric: "totalMassTons",
      thrusters: DATA.defaults.thrusterCount,
      fuelEfficiencyUnit: "kps",
      dryMassTons: DATA.defaults.dryMassTons,
      targetDvKps: DATA.defaults.targetDvKps,
      radiatorId: DATA.defaults.radiatorId,
      logX: false,
      logY: true,
      showTwrInfo: true,
      showMassInfo: true,
      paretoHighlight: true,
      showImpracticalCandidates: false,
      usePowerResearch: false,
      minTwr: 0.0001,
      searchTerm: "",
      sortKey: "research",
      sortDirection: "asc",
      lastTooltipItems: [],
      hoverPoints: [],
      tooltipPinned: false,
      pinnedTooltipItems: [],
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
          const values = chartMassOptions(row);
          return values.length ? values[0].totalMassTons : NaN;
        },
        format: value => formatNumber(value, " t"),
      },
      twr: {
        label: "TWR",
        hint: "추력 / (목표 dV 총질량 * g)",
        value: row => {
          const values = chartMassOptions(row);
          return values.length ? values[0].twr : NaN;
        },
        format: value => formatTwr(value, ""),
      },
    };

    const chart = document.getElementById("chart");
    const tooltip = document.getElementById("tooltip");
    const categoryRoot = document.getElementById("categories");
    const familyRoot = document.getElementById("families");
    const CHART_HIT_RADIUS_PX = 16;
    const CHART_CLICK_TOLERANCE_PX = 5;
    const EXTREME_MASS_RATIO = 1_000_000;
    const MASS_RATIO_OVERFLOW_EXPONENT = 709;
    const HIDDEN_REASON_PRIORITY = [
      "minTwr",
      "targetDvOrMassRatio",
      "researchFilter",
      "invalidPowerPlant",
      "invalidComputation",
      "axisRange",
      "other",
      "familyFilter",
    ];
    const HELP_TEXT = {
      showTwrInfo: {
        ko: "목표 dV 총질량 그래프에서 각 점의 밝기를 TWR로 인코딩합니다. 같은 총질량이라도 실제로 가속이 가능한 후보인지 빠르게 구분할 때 유용합니다.",
        en: "On the target-dV total-mass chart, point brightness encodes TWR. This helps separate low-mass candidates that can actually accelerate from low-mass but sluggish designs.",
      },
      showMassInfo: {
        ko: "TWR 그래프에서 각 점의 밝기를 총질량의 역수로 인코딩합니다. 높은 TWR 후보 중에서도 같은 목표 dV를 더 가벼운 총질량으로 달성하는 조합을 찾는 데 도움을 줍니다.",
        en: "On the TWR chart, point brightness encodes the inverse of total mass. This helps find high-TWR candidates that also reach the target dV with a lighter ship.",
      },
      paretoHighlight: {
        ko: "누적 연구력은 더 낮고, 총질량은 더 가볍고, TWR은 더 높은 후보가 존재하면 해당 후보를 흐리게 표시합니다. 명백히 밀리는 조합을 줄여 투자 후보를 좁히는 기능입니다.",
        en: "Dims candidates that are dominated by another option with no more research, no more total mass, and at least as much TWR. It narrows attention to stronger investment candidates.",
      },
      showImpracticalCandidates: {
        ko: "최소 TWR 또는 극단적 질량비 때문에 보통 숨겨지는 후보도 차트에 남깁니다. 왜 특정 계열이 사라지는지 조사하거나 낮은 dV 프리셋을 찾을 때 사용하세요.",
        en: "Keeps candidates that would normally be hidden by minimum TWR or extreme mass ratio. Use it to inspect why a family disappears or to design lower-dV presets.",
      },
      minTwr: {
        ko: "총질량 그래프에서 습질량 기준 TWR이 이 값보다 낮은 후보를 숨깁니다. 값을 낮추면 장거리 dV에는 가능하지만 가속이 매우 느린 조합까지 확인할 수 있습니다.",
        en: "On total-mass charts, hides candidates whose wet-mass TWR is below this threshold. Lower it to inspect designs that can reach the dV but accelerate very slowly.",
      },
    };
    let chartViewport = null;
    let chartHitTargets = [];
    let currentChartRows = [];
    let currentDiagnostics = null;
    const allDriveRowsById = new Map(DATA.drives.map(row => [row.id, row]));

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
      const showTwrInfo = document.getElementById("showTwrInfo");
      const showMassInfo = document.getElementById("showMassInfo");
      const paretoHighlight = document.getElementById("paretoHighlight");
      const showImpracticalCandidates = document.getElementById("showImpracticalCandidates");
      const powerResearchToggle = document.getElementById("powerResearchToggle");
      const minTwrExp = document.getElementById("minTwrExp");
      const minTwrNumber = document.getElementById("minTwrNumber");
      const nameSearch = document.getElementById("nameSearch");

      applyHelp(showTwrInfo.closest(".check-row"), helpText("showTwrInfo"));
      applyHelp(showMassInfo.closest(".check-row"), helpText("showMassInfo"));
      applyHelp(paretoHighlight.closest(".check-row"), helpText("paretoHighlight"));
      applyHelp(showImpracticalCandidates.closest(".check-row"), helpText("showImpracticalCandidates"));
      applyHelp(document.querySelector("#minTwrControl .label"), helpText("minTwr"));

      metric.value = state.metric;
      dryMass.value = String(clamp(state.dryMassTons, Number(dryMass.min), Number(dryMass.max)));
      dryMassNumber.value = String(Math.round(state.dryMassTons));
      targetDv.value = String(clamp(state.targetDvKps, Number(targetDv.min), Number(targetDv.max)));
      targetDvNumber.value = String(Math.round(state.targetDvKps));

      tooltip.addEventListener("click", event => {
        const moveButton = event.target.closest(".tooltip-item-move");
        if (moveButton) {
          moveTooltipItemByOffset(
            moveButton.getAttribute("data-tooltip-key"),
            moveButton.getAttribute("data-direction") === "up" ? -1 : 1,
          );
          return;
        }
        const itemClose = event.target.closest(".tooltip-item-close");
        if (itemClose) {
          removeTooltipItem(itemClose.getAttribute("data-tooltip-key"));
          return;
        }
        const itemPin = event.target.closest(".tooltip-item-pin");
        if (itemPin) {
          toggleTooltipItemPin(itemPin.getAttribute("data-tooltip-key"));
          return;
        }
        if (event.target.closest(".tooltip-close")) {
          clearTooltip({ keepPinned: true });
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
        applyHelp(label, localCategoryHelp(category));
        label.tabIndex = 0;
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
        text.className = "family-name";
        text.textContent = localLabel(family);
        const count = document.createElement("span");
        count.className = "family-count";
        count.dataset.familyCount = family.key;
        count.textContent = "0 / 0";
        label.append(input, swatch, text, count);
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
        const raw = Number(dryMassNumber.value);
        const value = clamp(Number.isFinite(raw) ? raw : 0, 0, 1000000);
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
        const raw = Number(targetDvNumber.value);
        const value = clamp(Number.isFinite(raw) ? raw : 0, 0, 100000);
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
      showTwrInfo.addEventListener("change", () => {
        state.showTwrInfo = showTwrInfo.checked;
        render();
      });
      showMassInfo.addEventListener("change", () => {
        state.showMassInfo = showMassInfo.checked;
        render();
      });
      paretoHighlight.addEventListener("change", () => {
        state.paretoHighlight = paretoHighlight.checked;
        render();
      });
      showImpracticalCandidates.addEventListener("change", () => {
        state.showImpracticalCandidates = showImpracticalCandidates.checked;
        render();
      });
      powerResearchToggle.addEventListener("click", () => {
        state.usePowerResearch = !state.usePowerResearch;
        render();
      });
      minTwrExp.addEventListener("input", () => {
        const exponent = Number(minTwrExp.value);
        state.minTwr = Math.pow(10, exponent);
        syncMinTwrInputs();
        render();
      });
      minTwrNumber.addEventListener("input", () => {
        state.minTwr = clamp(Number(minTwrNumber.value) || 0.0001, 0.0001, 10);
        syncMinTwrInputs();
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
      document.addEventListener("keydown", handleChartKeyDown);
    }

    function updateChartControls() {
      const fuelUnitBlock = document.getElementById("chartFuelUnit");
      const bandAnalysisControls = document.getElementById("bandAnalysisControls");
      const showTwrInfoRow = document.getElementById("showTwrInfoRow");
      const showMassInfoRow = document.getElementById("showMassInfoRow");
      const minTwrControl = document.getElementById("minTwrControl");
      const powerResearchToggle = document.getElementById("powerResearchToggle");
      fuelUnitBlock.style.display = state.metric === "fuelEfficiency" ? "" : "none";
      bandAnalysisControls.style.display = isBandMetric() ? "" : "none";
      showTwrInfoRow.style.display = state.metric === "totalMassTons" ? "" : "none";
      showMassInfoRow.style.display = state.metric === "twr" ? "" : "none";
      minTwrControl.style.display = state.metric === "totalMassTons" ? "" : "none";
      powerResearchToggle.style.display = isBandMetric() ? "" : "none";
      powerResearchToggle.setAttribute("aria-pressed", state.usePowerResearch ? "true" : "false");
      const showImpracticalCandidates = document.getElementById("showImpracticalCandidates");
      if (showImpracticalCandidates) showImpracticalCandidates.checked = !!state.showImpracticalCandidates;
      syncMinTwrInputs();
    }

    function syncMinTwrInputs() {
      const slider = document.getElementById("minTwrExp");
      const number = document.getElementById("minTwrNumber");
      const readout = document.getElementById("minTwrReadout");
      if (!slider || !number || !readout) return;
      state.minTwr = clamp(state.minTwr || 0.0001, 0.0001, 10);
      const exponent = clamp(Math.log10(state.minTwr), Number(slider.min), Number(slider.max));
      slider.value = String(exponent);
      number.value = String(Number(state.minTwr.toPrecision(4)));
      readout.textContent = `${UI_LANG === "en" ? "Showing" : "표시"}: TWR >= ${formatTwr(state.minTwr, " g")}`;
    }

    function localLabel(item) {
      if (UI_LANG === "en") return item.labelEn || item.label || item.key;
      return item.label || item.labelEn || item.key;
    }

    function localCategoryHelp(category) {
      if (UI_LANG === "en") return category.helpEn || category.help || "";
      return category.help || category.helpEn || "";
    }

    function helpText(key) {
      const item = HELP_TEXT[key] || {};
      return UI_LANG === "en" ? (item.en || item.ko || "") : (item.ko || item.en || "");
    }

    function applyHelp(element, text) {
      if (!element || !text) return;
      element.dataset.help = text;
      element.title = text;
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
      return computeDriveDiagnostics().visibleRows;
    }

    function computeDriveDiagnostics() {
      const familyStats = new Map(DATA.subfamilies.map(family => [family.key, {
        ...family,
        total: 0,
        visible: 0,
        hidden: 0,
        selected: !!state.categories[family.categoryKey] && !!state.families[family.key],
        hiddenReasons: {},
      }]));
      const visibleRows = [];
      DATA.drives.forEach(row => {
        const evaluation = evaluateDriveVisibility(row);
        if (evaluation.visible) visibleRows.push(row);
        if (!rowInFamilyDiagnosticScope(row)) return;
        const stats = familyStats.get(row.familyKey);
        if (!stats) return;
        stats.total += 1;
        if (evaluation.visible) {
          stats.visible += 1;
        } else if (stats.selected) {
          stats.hidden += 1;
          const reasons = evaluation.reasons.filter(reason => reason !== "familyFilter");
          (reasons.length ? reasons : ["other"]).forEach(reason => {
            stats.hiddenReasons[reason] = (stats.hiddenReasons[reason] || 0) + 1;
          });
        }
      });
      const families = DATA.subfamilies.map(family => {
        const stats = familyStats.get(family.key);
        return {
          ...stats,
          dominantReason: dominantHiddenReason(stats.hiddenReasons),
        };
      });
      return {
        visibleRows,
        families,
        zeroFamilies: families.filter(family => family.selected && family.total > 0 && family.visible === 0),
      };
    }

    function evaluateDriveVisibility(row) {
      const reasons = [];
      if (row.thrusterCount !== state.thrusters || !rowMatchesSearch(row) || !rowFamilySelected(row)) {
        reasons.push("familyFilter");
      }
      if (!Number.isFinite(rowUnlockResearchValue(row)) || rowUnlockResearchValue(row) <= 0) {
        reasons.push("researchFilter");
      }
      if (isBandMetric()) {
        reasons.push(...bandMetricHiddenReasons(row));
      } else {
        const value = metricDefs[state.metric].value(row);
        if (!Number.isFinite(value) || value <= 0) reasons.push("axisRange");
      }
      return {
        visible: reasons.length === 0,
        reasons: [...new Set(reasons)],
      };
    }

    function rowFamilySelected(row) {
      return !!state.categories[row.categoryKey] && !!state.families[row.familyKey];
    }

    function rowInFamilyDiagnosticScope(row) {
      return row.thrusterCount === state.thrusters && rowMatchesSearch(row);
    }

    function rowMatchesSearch(row) {
      if (!state.searchTerm) return true;
      const haystack = [
        row.displayName,
        row.baseDisplayName,
        row.requiredProject,
        rowProjectLabel(row),
        rowCategoryLabel(row),
        rowFamilyLabel(row),
      ].join(" ").toLocaleLowerCase();
      return haystack.includes(state.searchTerm);
    }

    function bandMetricHiddenReasons(row) {
      const configuredOptions = row.powerOptions || row.reactorOptions || [];
      if (!configuredOptions.length) return ["invalidPowerPlant"];
      const massInfo = massRatioDiagnostics(row);
      const options = massOptions(row);
      if (!options.length) {
        if (massInfo.overflow || massInfo.extreme) return ["targetDvOrMassRatio"];
        return [massInfo.invalid ? "invalidComputation" : "invalidPowerPlant"];
      }
      const finiteMetricOptions = options.filter(option => Number.isFinite(optionMetricValue(option)) && optionMetricValue(option) > 0);
      if (!finiteMetricOptions.length) return ["invalidComputation"];
      const reasons = [];
      if (state.metric === "totalMassTons" && state.minTwr > 0 && !state.showImpracticalCandidates) {
        const twrPassing = finiteMetricOptions.some(option => Number.isFinite(option.twr) && option.twr >= state.minTwr);
        if (!twrPassing) {
          reasons.push("minTwr");
          if (massInfo.extreme || massInfo.overflow || finiteMetricOptions.some(isExtremeMassRatioOption)) {
            reasons.push("targetDvOrMassRatio");
          }
        }
      }
      return reasons;
    }

    function massRatioDiagnostics(row) {
      const targetDv = Number(state.targetDvKps);
      const exhaustVelocity = Number(row.exhaustVelocityKps);
      if (!Number.isFinite(targetDv) || !Number.isFinite(exhaustVelocity) || exhaustVelocity <= 0) {
        return { invalid: true, overflow: false, extreme: false, massRatio: NaN };
      }
      const exponent = targetDv / exhaustVelocity;
      if (!Number.isFinite(exponent)) {
        return { invalid: true, overflow: false, extreme: false, massRatio: NaN };
      }
      if (exponent > MASS_RATIO_OVERFLOW_EXPONENT) {
        return { invalid: false, overflow: true, extreme: true, massRatio: Infinity };
      }
      const massRatio = Math.exp(exponent);
      return {
        invalid: !Number.isFinite(massRatio),
        overflow: !Number.isFinite(massRatio),
        extreme: Number.isFinite(massRatio) && massRatio >= EXTREME_MASS_RATIO,
        massRatio,
      };
    }

    function isExtremeMassRatioOption(option) {
      return Number.isFinite(option.massRatio) && option.massRatio >= EXTREME_MASS_RATIO;
    }

    function isImpracticalOption(option) {
      if (!state.showImpracticalCandidates) return false;
      return (state.metric === "totalMassTons" && state.minTwr > 0 && Number.isFinite(option.twr) && option.twr < state.minTwr)
        || isExtremeMassRatioOption(option);
    }

    function dominantHiddenReason(hiddenReasons) {
      return HIDDEN_REASON_PRIORITY.find(reason => (hiddenReasons && hiddenReasons[reason] > 0)) || "other";
    }

    function rowUnlockResearchValue(row) {
      const value = Number(row.unlockCumulativeResearch);
      if (Number.isFinite(value) && value > 0) return value;
      return Number(row.cumulativeResearch);
    }

    function rowUnlockResearchValue(row) {
      const value = Number(row.unlockCumulativeResearch);
      if (Number.isFinite(value) && value > 0) return value;
      return Number(row.cumulativeResearch);
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
      const massRatio = massRatioMinusOne + 1;
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
          massRatio,
          massRatioMinusOne,
        };
      });
      return actualPowerFrontier(row, computed);
    }

    function chartMassOptions(row, metric = state.metric) {
      const options = massOptions(row);
      if (metric === "totalMassTons" && state.minTwr > 0 && !state.showImpracticalCandidates) {
        return options.filter(option => Number.isFinite(option.twr) && option.twr >= state.minTwr);
      }
      return options;
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
      const diagnostics = computeDriveDiagnostics();
      currentDiagnostics = diagnostics;
      const rows = diagnostics.visibleRows;
      const metric = metricDefs[state.metric];
      document.getElementById("visibleCount").textContent = rows.length;
      document.getElementById("metricHint").textContent = metric.hint;
      document.getElementById("metricColumn").textContent = metric.label;
      updateChartControls();
      renderFamilyDiagnostics(diagnostics);
      renderChartDiagnostic(diagnostics);
      renderLegend(rows);
      renderChart(rows);
      renderTable(rows);
      updateSortHeaders();
      refreshTooltip(rows);
    }

    function redrawChartOnly() {
      const diagnostics = computeDriveDiagnostics();
      currentDiagnostics = diagnostics;
      const rows = diagnostics.visibleRows;
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
        state.showImpracticalCandidates ? 1 : 0,
        state.usePowerResearch ? 1 : 0,
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

    function renderFamilyDiagnostics(diagnostics) {
      const byKey = new Map(diagnostics.families.map(family => [family.key, family]));
      document.querySelectorAll(".family-row").forEach(row => {
        const stats = byKey.get(row.dataset.familyKey);
        const count = row.querySelector(".family-count");
        if (!count || !stats) return;
        count.textContent = UI_LANG === "en"
          ? `${stats.visible} / ${stats.total} shown`
          : `${stats.visible} / ${stats.total} 표시`;
      });
      const warningsRoot = document.getElementById("familyWarnings");
      if (!warningsRoot) return;
      warningsRoot.innerHTML = "";
      diagnostics.zeroFamilies.forEach(family => {
        const item = document.createElement("div");
        item.className = "family-warning";
        item.textContent = familyWarningText(family);
        warningsRoot.appendChild(item);
      });
    }

    function renderChartDiagnostic(diagnostics) {
      const banner = document.getElementById("chartDiagnostic");
      if (!banner) return;
      if (!diagnostics.zeroFamilies.length) {
        banner.hidden = true;
        banner.textContent = "";
        return;
      }
      const count = diagnostics.zeroFamilies.length;
      banner.hidden = false;
      banner.textContent = UI_LANG === "en"
        ? `${count} selected drive ${count === 1 ? "family has" : "families have"} no visible candidates under the current scenario.`
        : `선택된 드라이브 계열 ${count}개는 현재 시나리오에서 표시 후보가 없습니다.`;
    }

    function familyWarningText(family) {
      const label = localLabel(family);
      const phrase = hiddenReasonPhrase(family.dominantReason, family.hiddenReasons);
      return UI_LANG === "en"
        ? `${label}: ${family.hidden} drives hidden by ${phrase}.`
        : `${label}: ${family.hidden}개 드라이브가 ${phrase} 때문에 숨겨졌습니다.`;
    }

    function hiddenReasonPhrase(reason, hiddenReasons = {}) {
      const reasonKey = reason || "other";
      if (reasonKey === "minTwr" && hiddenReasons.targetDvOrMassRatio) {
        return UI_LANG === "en" ? "current dV / minimum TWR settings" : "현재 dV / 최소 TWR 설정";
      }
      const phrases = {
        minTwr: UI_LANG === "en" ? "the current minimum TWR filter" : "현재 최소 TWR 필터",
        targetDvOrMassRatio: UI_LANG === "en" ? "the current target dV / mass-ratio scenario" : "현재 목표 dV / 질량비 시나리오",
        researchFilter: UI_LANG === "en" ? "research unlock constraints" : "연구 개방 조건",
        invalidPowerPlant: UI_LANG === "en" ? "missing compatible power candidates" : "호환 전원 후보 부족",
        invalidComputation: UI_LANG === "en" ? "non-finite mass or TWR calculations" : "계산 불능 질량 또는 TWR",
        axisRange: UI_LANG === "en" ? "the current axis range or metric" : "현재 축 범위 또는 지표",
        other: UI_LANG === "en" ? "other current filters" : "기타 현재 필터",
        familyFilter: UI_LANG === "en" ? "family/category filters" : "대분류/계열 필터",
      };
      return phrases[reasonKey] || phrases.other;
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
        item.textContent = state.usePowerResearch
          ? `${metricDefs[state.metric].label} 밴드: 추가 전원 연구력 포함`
          : `${metricDefs[state.metric].label} 밴드: 최초 전원 연구력 기준`;
        legend.appendChild(item);
        const powerResearch = document.createElement("span");
        powerResearch.className = "legend-item";
        powerResearch.textContent = state.usePowerResearch
          ? "X축: 최초+추가 전원 포함 연구력"
          : "X축: 최초 전원 포함 연구력";
        legend.appendChild(powerResearch);
        if (secondaryEncodingEnabled()) {
          const secondary = document.createElement("span");
          secondary.className = "legend-item";
          secondary.textContent = state.metric === "totalMassTons"
            ? "점 밝기: TWR 높을수록 밝음"
            : "점 밝기: 총질량 낮을수록 밝음";
          legend.appendChild(secondary);
        }
        if (state.paretoHighlight) {
          const pareto = document.createElement("span");
          pareto.className = "legend-item";
          pareto.textContent = "흐린 점: Pareto 지배 후보";
          legend.appendChild(pareto);
        }
      }
    }

    function valueDomain(rows) {
      if (isBandMetric()) {
        const values = rows.flatMap(row => chartMassOptions(row).map(option => optionMetricValue(option)));
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
      state.hoverPoints = state.tooltipPinned ? dedupeTooltipRefs(state.lastTooltipItems) : pinnedTooltipRefs();
      chart.setAttribute("viewBox", `0 0 ${width} ${height}`);
      chart.setAttribute("preserveAspectRatio", "xMidYMid meet");
      chart.innerHTML = "";

      const xValues = chartResearchValues(rows);
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
        startClientX: event.clientX,
        startClientY: event.clientY,
        hasMoved: false,
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
      const movementPx = Math.hypot(event.clientX - state.pan.startClientX, event.clientY - state.pan.startClientY);
      if (movementPx > CHART_CLICK_TOLERANCE_PX) {
        state.pan.hasMoved = true;
      }
      if (!state.pan.hasMoved) return;
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
      if (state.tooltipPinned) return;
      state.hoverHitSignature = "";
      state.dismissedTooltipKeys.clear();
      const pinned = pinnedTooltipRefs();
      setHoverPoints(pinned);
      if (pinned.length && !sameTooltipRefs(pinned, state.lastTooltipItems)) {
        state.lastTooltipItems = pinned;
        refreshTooltip(currentChartRows);
      }
    }

    function endChartPan(event) {
      if (!state.pan || event.pointerId !== state.pan.pointerId) return;
      const movementPx = Math.hypot(event.clientX - state.pan.startClientX, event.clientY - state.pan.startClientY);
      const shouldPinClick = !state.pan.hasMoved && movementPx <= CHART_CLICK_TOLERANCE_PX;
      const clickPoint = shouldPinClick ? svgPointFromEvent(event) : null;
      if (chart.hasPointerCapture(event.pointerId)) chart.releasePointerCapture(event.pointerId);
      state.pan = null;
      chart.classList.remove("is-panning");
      if (shouldPinClick) {
        handleChartClick(clickPoint);
        event.preventDefault();
      }
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
      const transform = svgViewportTransform();
      return {
        x: (event.clientX - transform.rect.left - transform.offsetX) / transform.scale,
        y: (event.clientY - transform.rect.top - transform.offsetY) / transform.scale,
      };
    }

    function svgViewportTransform() {
      const rect = chart.getBoundingClientRect();
      const viewWidth = Math.max(chartViewport.width, 1);
      const viewHeight = Math.max(chartViewport.height, 1);
      const scale = Math.min(Math.max(rect.width, 1) / viewWidth, Math.max(rect.height, 1) / viewHeight);
      const safeScale = Number.isFinite(scale) && scale > 0 ? scale : 1;
      const drawnWidth = viewWidth * safeScale;
      const drawnHeight = viewHeight * safeScale;
      return {
        rect,
        scale: safeScale,
        offsetX: (rect.width - drawnWidth) / 2,
        offsetY: (rect.height - drawnHeight) / 2,
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
      if (state.tooltipPinned) return;
      if (!chartViewport || !chartHitTargets.length) return;
      const point = svgPointFromEvent(event);
      if (!pointInPlot(point)) {
        state.hoverHitSignature = "";
        state.dismissedTooltipKeys.clear();
        const pinned = pinnedTooltipRefs();
        setHoverPoints(pinned);
        if (pinned.length && !sameTooltipRefs(pinned, state.lastTooltipItems)) {
          state.lastTooltipItems = pinned;
          refreshTooltip(currentChartRows);
        }
        return;
      }
      const hits = hitTargetsAt(point);
      if (!hits.length) {
        state.hoverHitSignature = "";
        state.dismissedTooltipKeys.clear();
        const pinned = pinnedTooltipRefs();
        setHoverPoints(pinned);
        if (pinned.length && !sameTooltipRefs(pinned, state.lastTooltipItems)) {
          state.lastTooltipItems = pinned;
          refreshTooltip(currentChartRows);
        }
        return;
      }
      const signature = hits.map(hit => hit.key).join("|");
      if (signature !== state.hoverHitSignature) {
        state.hoverHitSignature = signature;
        state.dismissedTooltipKeys.clear();
      }
      const visibleHits = hits.filter(hit => !state.dismissedTooltipKeys.has(hit.key));
      const nextRefs = mergePinnedTooltipRefs(visibleHits);
      setHoverPoints(nextRefs);
      if (nextRefs.length && !sameTooltipRefs(nextRefs, state.lastTooltipItems)) {
        state.lastTooltipItems = nextRefs;
        refreshTooltip(currentChartRows);
      }
    }

    function handleChartClick(point) {
      if (!chartViewport || !pointInPlot(point)) {
        clearTooltip({ keepPinned: true });
        return;
      }
      const hits = hitTargetsAt(point);
      const visibleHits = state.tooltipPinned
        ? hits
        : hits.filter(hit => !state.dismissedTooltipKeys.has(hit.key));
      if (!visibleHits.length) {
        clearTooltip({ keepPinned: true });
        return;
      }
      pinTooltipItems(visibleHits);
    }

    function handleChartKeyDown(event) {
      if (isEditableTarget(event.target)) return;
      if (event.key === "Escape" && (state.tooltipPinned || state.lastTooltipItems.length)) {
        clearTooltip({ keepPinned: true });
        event.preventDefault();
        return;
      }
      const key = event.key.length === 1 ? event.key.toLowerCase() : event.key;
      if ((key === "p" || event.code === "Space") && state.lastTooltipItems.length) {
        if (state.tooltipPinned) {
          unpinTooltip();
        } else {
          pinTooltipItems(state.hoverPoints.length ? state.hoverPoints : state.lastTooltipItems);
        }
        event.preventDefault();
      }
    }

    function isEditableTarget(target) {
      if (!target) return false;
      const tagName = target.tagName ? target.tagName.toLowerCase() : "";
      return target.isContentEditable || ["input", "select", "textarea", "button"].includes(tagName);
    }

    function hitTargetsAt(point) {
      const transform = svgViewportTransform();
      return chartHitTargets
        .map(target => ({
          ...target,
          distance: Math.hypot(target.x - point.x, target.y - point.y) * transform.scale,
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
      xTitle.textContent = `${state.usePowerResearch && isBandMetric() ? "누적 연구력 (최초+추가 전원 포함)" : "누적 연구력 (최초 전원 포함)"}${state.logX ? " (log)" : ""}`;
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
      groups.forEach(group => group.sort((a, b) => rowUnlockResearchValue(a) - rowUnlockResearchValue(b) || a.baseDisplayName.localeCompare(b.baseDisplayName)));
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

    function resolveTooltipRow(ref, rowById, rows) {
      const direct = rowById.get(ref.rowId);
      if (direct) return direct;
      const original = allDriveRowsById.get(ref.rowId);
      if (!original) return null;
      return rows.find(row => row.baseKey === original.baseKey
        && row.thrusterCount === state.thrusters
        && row.familyKey === original.familyKey)
        || rows.find(row => row.baseKey === original.baseKey && row.thrusterCount === state.thrusters)
        || null;
    }

    function isPinnedTooltipKey(key) {
      return state.pinnedTooltipItems.some(item => item.key === key);
    }

    function pinnedTooltipRefs() {
      const lastPinned = dedupeTooltipRefs(state.lastTooltipItems).filter(item => isPinnedTooltipKey(item.key));
      const included = new Set(lastPinned.map(item => item.key));
      const missingPinned = dedupeTooltipRefs(state.pinnedTooltipItems).filter(item => !included.has(item.key));
      return [...lastPinned, ...missingPinned];
    }

    function mergePinnedTooltipRefs(items) {
      const pinned = pinnedTooltipRefs();
      const pinnedKeys = new Set(pinned.map(item => item.key));
      const transient = dedupeTooltipRefs(items).filter(item => !pinnedKeys.has(item.key));
      return [...pinned, ...transient];
    }

    function syncPinnedTooltipOrder() {
      const pinnedKeys = new Set(state.pinnedTooltipItems.map(item => item.key));
      state.pinnedTooltipItems = dedupeTooltipRefs(state.lastTooltipItems).filter(item => pinnedKeys.has(item.key));
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
        const path = linePath(group.map(row => [x(rowUnlockResearchValue(row)), y(metricDefs[state.metric].value(row))]));
        plot.appendChild(svgEl("path", { d: path, fill: "none", stroke: color, "stroke-width": 2.2, "stroke-linejoin": "round", "stroke-linecap": "round", opacity: 0.82 }));
        group.forEach(row => {
          const value = metricDefs[state.metric].value(row);
          if (!Number.isFinite(value) || value <= 0) return;
          const cx = x(rowUnlockResearchValue(row));
          const cy = y(value);
          const option = defaultTooltipOption(row);
          const powerOptionId = option ? option.id : null;
          registerHitTarget(row, powerOptionId, cx, cy, 5.5);
          const circle = svgEl("circle", { ...pointAttrs(row, powerOptionId, color), cx, cy, r: 5.5 });
          plot.appendChild(circle);
        });
      });
    }

    function chartResearchValues(rows) {
      const values = isBandMetric()
        ? rows.flatMap(row => [
          rowUnlockResearchValue(row),
          ...chartMassOptions(row).map(option => optionAdditionalResearchValue(row, option)),
        ])
        : rows.map(row => rowUnlockResearchValue(row));
      return values.filter(value => Number.isFinite(value) && value > 0);
    }

    function optionAdditionalResearchValue(row, option = null) {
      if (!option) return rowUnlockResearchValue(row);
      const combined = Number(option.combinedCumulativeResearch);
      if (Number.isFinite(combined) && combined > 0) return combined;
      const plantResearch = Number(option.cumulativeResearch);
      return Math.max(rowUnlockResearchValue(row), Number.isFinite(plantResearch) ? plantResearch : 0);
    }

    function optionResearchValue(row, option = null) {
      if (isBandMetric() && state.usePowerResearch && option) {
        return optionAdditionalResearchValue(row, option);
      }
      return rowUnlockResearchValue(row);
    }

    function optionX(row, option, x) {
      return x(optionResearchValue(row, option));
    }

    function drawTotalMassBands(rows, x, y, plot) {
      const pointData = bandPointData(rows);
      const secondaryDomain = secondaryEncodingDomain(pointData);
      const paretoKeys = state.paretoHighlight ? paretoPointKeys(pointData) : new Set();
      const groups = groupedRows(rows);
      groups.forEach(group => {
        const color = group[0].familyBandColor || group[0].familyColor;
        const colorOklch = group[0].familyBandColorOklch || color;
        const fillStyle = paintStyle("fill", color, colorOklch);
        const strokeStyle = paintStyle("stroke", color, colorOklch);
        const maxOptions = Math.max(...group.map(row => chartMassOptions(row).length), 0);
        if (state.usePowerResearch) {
          drawPowerResearchBandSurfaces(group, x, y, plot, color, fillStyle, strokeStyle);
        } else {
          for (let index = maxOptions - 2; index >= 0; index--) {
            const pairs = group
              .map(row => ({ row, options: chartMassOptions(row) }))
              .filter(item => item.options[index] && item.options[index + 1]);
            if (pairs.length < 2) continue;
            const upper = pairs.map(item => [optionX(item.row, item.options[index], x), y(optionMetricValue(item.options[index]))]);
            const lower = pairs.slice().reverse().map(item => [optionX(item.row, item.options[index + 1], x), y(optionMetricValue(item.options[index + 1]))]);
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
              .map(row => ({ row, option: chartMassOptions(row)[index] }))
              .filter(item => item.option);
            if (points.length >= 2) {
              plot.appendChild(svgEl("path", {
                d: linePath(points.map(item => [optionX(item.row, item.option, x), y(optionMetricValue(item.option))])),
                fill: "none",
                stroke: color,
                style: strokeStyle,
                "stroke-width": index === 0 ? 2.1 : 1.2,
                "stroke-dasharray": index === 0 ? "" : "5 5",
                opacity: index === 0 ? 0.9 : 0.45,
              }));
            }
          }
        }
        group.forEach(row => {
          const options = chartMassOptions(row);
          if (!options.length) return;
          const optionPoints = options.map(option => ({
            option,
            xCoord: optionX(row, option, x),
            yCoord: y(optionMetricValue(option)),
          })).sort((a, b) => a.xCoord - b.xCoord || a.yCoord - b.yCoord);
          if (optionPoints.length > 1) {
            if (state.usePowerResearch) {
              plot.appendChild(svgEl("path", {
                d: linePath(optionPoints.map(point => [point.xCoord, point.yCoord])),
                fill: "none",
                stroke: color,
                style: strokeStyle,
                "stroke-width": 1.1,
                opacity: 0.28,
              }));
            } else {
              const gx = optionPoints[0].xCoord;
              const ys = optionPoints.map(point => point.yCoord);
              plot.appendChild(svgEl("line", { x1: gx, x2: gx, y1: Math.min(...ys), y2: Math.max(...ys), stroke: color, style: strokeStyle, "stroke-width": 1.2, opacity: 0.32 }));
            }
          }
          options.forEach((option, index) => {
            const gx = optionX(row, option, x);
            const cy = y(optionMetricValue(option));
            const key = pointKey(row.id, option.id);
            const visual = bandPointVisual(option, secondaryDomain, paretoKeys.has(key));
            const impractical = isImpracticalOption(option);
            registerHitTarget(row, option.id, gx, cy, index === 0 ? 5 : 3.4);
            const circle = svgEl("circle", {
              ...pointAttrs(row, option.id, index === 0 ? color : "var(--panel)", impractical ? "var(--danger)" : color, impractical ? 2 : 1.5),
              cx: gx,
              cy,
              r: index === 0 ? 5 : 3.4,
              style: `${index === 0 ? fillStyle : ""}${visual.style}`,
              opacity: impractical ? Math.max(visual.opacity * 0.78, 0.38) : visual.opacity,
              "data-impractical": impractical ? "true" : "false",
            });
            plot.appendChild(circle);
          });
        });
      });
    }

    function drawPowerResearchBandSurfaces(group, x, y, plot, color, fillStyle, strokeStyle) {
      const stepGroups = new Map();
      const pairGroups = new Map();
      const familyKey = group[0] ? group[0].familyKey : "";
      group.forEach(row => {
        const options = chartMassOptions(row);
        options.forEach((option, index) => {
          const step = powerStepIndex(option, index);
          if (!stepGroups.has(step)) stepGroups.set(step, []);
          stepGroups.get(step).push({ row, option, index: step });
          const next = options[index + 1];
          if (next) {
            const nextStep = powerStepIndex(next, index + 1);
            const pairKey = `${step}::${nextStep}`;
            if (!pairGroups.has(pairKey)) pairGroups.set(pairKey, []);
            pairGroups.get(pairKey).push({ row, upper: option, lower: next, index: step, lowerIndex: nextStep });
          }
        });
      });

      pairGroups.forEach((pairs, pairKey) => {
        if (pairs.length < 2) return;
        const ordered = pairs.slice().sort((a, b) => pairSortValue(a) - pairSortValue(b)
          || rowUnlockResearchValue(a.row) - rowUnlockResearchValue(b.row)
          || a.row.baseDisplayName.localeCompare(b.row.baseDisplayName));
        const upper = ordered.map(item => [optionX(item.row, item.upper, x), y(optionMetricValue(item.upper))]);
        const lower = ordered.slice().reverse().map(item => [optionX(item.row, item.lower, x), y(optionMetricValue(item.lower))]);
        const avgIndex = ordered.reduce((sum, item) => sum + item.index, 0) / ordered.length;
        plot.appendChild(svgEl("path", {
          d: linePath([...upper, ...lower]) + "Z",
          fill: color,
          style: fillStyle,
          opacity: Math.max(0.05, 0.18 - avgIndex * 0.02),
          stroke: "none",
          "data-band-family": familyKey,
          "data-band-pair-step": pairKey,
        }));
      });

      stepGroups.forEach((points, step) => {
        if (points.length < 2) return;
        const ordered = points.slice().sort((a, b) => optionResearchValue(a.row, a.option) - optionResearchValue(b.row, b.option)
          || rowUnlockResearchValue(a.row) - rowUnlockResearchValue(b.row)
          || a.row.baseDisplayName.localeCompare(b.row.baseDisplayName));
        const avgIndex = ordered.reduce((sum, item) => sum + item.index, 0) / ordered.length;
        plot.appendChild(svgEl("path", {
          d: linePath(ordered.map(item => [optionX(item.row, item.option, x), y(optionMetricValue(item.option))])),
          fill: "none",
          stroke: color,
          style: strokeStyle,
          "stroke-width": avgIndex < 0.5 ? 2.1 : 1.2,
          "stroke-dasharray": avgIndex < 0.5 ? "" : "5 5",
          opacity: avgIndex < 0.5 ? 0.9 : 0.45,
          "data-band-family": familyKey,
          "data-band-step": step,
        }));
      });
    }

    function powerStepIndex(option, fallbackIndex = 0) {
      const value = Number(option && option.sequenceIndex);
      return Number.isFinite(value) ? value : fallbackIndex;
    }

    function pairSortValue(item) {
      return (optionResearchValue(item.row, item.upper) + optionResearchValue(item.row, item.lower)) / 2;
    }

    function bandPointData(rows) {
      return rows.flatMap(row => chartMassOptions(row).map(option => ({
        row,
        option,
        key: pointKey(row.id, option.id),
        research: optionResearchValue(row, option),
        totalMassTons: option.totalMassTons,
        twr: option.twr,
      }))).filter(item => Number.isFinite(item.research)
        && Number.isFinite(item.totalMassTons)
        && Number.isFinite(item.twr)
        && item.totalMassTons > 0
        && item.twr > 0);
    }

    function secondaryEncodingEnabled() {
      return (state.metric === "totalMassTons" && state.showTwrInfo)
        || (state.metric === "twr" && state.showMassInfo);
    }

    function secondaryEncodingDomain(points) {
      if (!secondaryEncodingEnabled()) return null;
      const scores = points.map(item => secondaryScore(item.option)).filter(Number.isFinite);
      if (!scores.length) return null;
      return { min: Math.min(...scores), max: Math.max(...scores) };
    }

    function secondaryScore(option) {
      if (state.metric === "totalMassTons") {
        return Math.log10(Math.max(option.twr, 1e-12));
      }
      if (state.metric === "twr") {
        return -Math.log10(Math.max(option.totalMassTons, 1e-9));
      }
      return NaN;
    }

    function bandPointVisual(option, secondaryDomain, pareto) {
      let normalized = 0.72;
      if (secondaryDomain) {
        const span = Math.max(secondaryDomain.max - secondaryDomain.min, 1e-9);
        normalized = clamp((secondaryScore(option) - secondaryDomain.min) / span, 0, 1);
      }
      const encodedOpacity = secondaryDomain ? 0.42 + normalized * 0.58 : 0.88;
      const paretoOpacity = state.paretoHighlight && !pareto ? 0.28 : 1;
      const brightness = secondaryDomain ? 0.68 + normalized * 0.72 : 1;
      return {
        opacity: clamp(encodedOpacity * paretoOpacity, 0.12, 1),
        style: `filter:brightness(${brightness.toFixed(2)});`,
      };
    }

    function paretoPointKeys(points) {
      const result = new Set();
      points.forEach(candidate => {
        const dominated = points.some(other => other.key !== candidate.key
          && other.research <= candidate.research
          && other.totalMassTons <= candidate.totalMassTons
          && other.twr >= candidate.twr
          && (other.research < candidate.research
            || other.totalMassTons < candidate.totalMassTons
            || other.twr > candidate.twr));
        if (!dominated) result.add(candidate.key);
      });
      return result;
    }

    function isBandMetric(metric = state.metric) {
      return metric === "totalMassTons" || metric === "twr";
    }

    function optionMetricValue(option, metric = state.metric) {
      return metric === "twr" ? option.twr : option.totalMassTons;
    }

    function defaultTooltipOption(row) {
      const options = chartMassOptions(row, state.metric);
      return options[0] || massOptions(row)[0] || null;
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
      const pinnedText = UI_LANG === "en" ? "Pinned" : "고정됨";
      const pinnedCardText = UI_LANG === "en" ? "pinned cards" : "고정 카드";
      const countText = UI_LANG === "en" ? `${items.length} selected` : `선택 항목 ${items.length}개`;
      const statusParts = [];
      if (state.tooltipPinned) statusParts.push(`<span class="tooltip-pin">${pinnedText}</span>`);
      const pinnedCount = items.filter(item => isPinnedTooltipKey(item.key)).length;
      if (pinnedCount) statusParts.push(`<span class="tooltip-pin">${pinnedCount} ${pinnedCardText}</span>`);
      if (items.length > 1) statusParts.push(countText);
      const count = statusParts.length ? `<div class="tooltip-count">${statusParts.join("")}</div>` : "";
      return `
        <button class="tooltip-close" type="button" aria-label="선택 해제">&times;</button>
        ${count}
        <div class="tooltip-items">
          ${items.map((item, index) => tooltipHtml(item.row, item.option, item.key, index, items.length)).join("")}
        </div>
      `;
    }

    function pinTooltipItems(items) {
      const refs = dedupeTooltipRefs(items);
      if (!refs.length) {
        clearTooltip();
        return;
      }
      state.tooltipPinned = true;
      state.dismissedTooltipKeys.clear();
      const nextRefs = dedupeTooltipRefs([...state.lastTooltipItems, ...refs]);
      state.hoverHitSignature = nextRefs.map(item => item.key).join("|");
      state.lastTooltipItems = nextRefs;
      setHoverPoints(nextRefs);
      refreshTooltip(currentChartRows);
    }

    function unpinTooltip() {
      state.tooltipPinned = false;
      state.hoverHitSignature = "";
      state.dismissedTooltipKeys.clear();
      refreshTooltip(currentChartRows);
    }

    function tooltipHtml(row, option = null, key = "", index = 0, itemCount = 1) {
      const radiator = selectedRadiator();
      const selected = option ? tooltipBreakdownHtml(row, option) : "";
      const powerName = option ? option.displayName : (UI_LANG === "en" ? "No power plant candidate" : "전원 후보 없음");
      const pinned = isPinnedTooltipKey(key);
      const pinLabel = UI_LANG === "en" ? (pinned ? "Unpin this card" : "Pin this card") : (pinned ? "이 카드 고정 해제" : "이 카드 고정");
      const unlockResearch = rowUnlockResearchValue(row);
      const powerResearch = option && state.usePowerResearch
        ? `<div>추가 전원 포함 연구력: <strong>${formatResearch(optionResearchValue(row, option))}</strong></div>`
        : "";
      return `
        <section class="tooltip-item${pinned ? " is-pinned" : ""}" data-tooltip-key="${escapeHtml(key)}">
          <div class="tooltip-item-order" aria-label="순서 변경">
            <button class="tooltip-item-move" type="button" data-tooltip-key="${escapeHtml(key)}" data-direction="up" aria-label="위로 이동"${index === 0 ? " disabled" : ""}>▲</button>
            <button class="tooltip-item-move" type="button" data-tooltip-key="${escapeHtml(key)}" data-direction="down" aria-label="아래로 이동"${index >= itemCount - 1 ? " disabled" : ""}>▼</button>
          </div>
          <div class="tooltip-item-actions">
            <button class="tooltip-item-close" type="button" data-tooltip-key="${escapeHtml(key)}" aria-label="항목 삭제">&times;</button>
            <button class="tooltip-item-pin" type="button" data-tooltip-key="${escapeHtml(key)}" aria-label="${escapeHtml(pinLabel)}" aria-pressed="${pinned ? "true" : "false"}">📌</button>
          </div>
          <h2>${escapeHtml(row.displayName)}<span class="tooltip-title-power">${escapeHtml(powerName)}</span></h2>
          <div class="muted">${escapeHtml(rowCategoryLabel(row))} / ${escapeHtml(rowFamilyLabel(row))} · ${escapeHtml(rowProjectLabel(row))}</div>
          <div>개방 연구력: <strong>${formatResearch(unlockResearch)}</strong> · 추진기 연구: ${formatResearch(row.cumulativeResearch)} · 자체 프로젝트: ${formatResearch(row.ownResearchCost)}</div>
          ${powerResearch}
          <div>추력: ${formatNumber(row.thrustN / 1e6, " MN")} · EV: ${formatNumber(row.exhaustVelocityKps, " km/s")} · Isp: ${formatNumber(row.specificImpulseSeconds, " s")}</div>
          <div>효율: ${formatPercent(row.efficiency)} · 출력 요구량: ${formatNumber(row.powerRequirementGW, " GW")}</div>
          <div>라디에이터: ${escapeHtml(radiator ? radiator.displayName : "-")}</div>
          ${selected}
        </section>
      `;
    }

    function tooltipBreakdownHtml(row, option) {
      const totalLabel = UI_LANG === "en" ? "Total mass" : "총질량";
      const twrLabel = UI_LANG === "en" ? "TWR" : "TWR";
      const components = [
        [UI_LANG === "en" ? "Hull" : "선체", option.baseDryTons, "stack-hull"],
        [UI_LANG === "en" ? "Drive" : "드라이브", row.driveMassTons, "stack-drive"],
        [UI_LANG === "en" ? "Power plant" : "전원", option.powerPlantMassTons, "stack-reactor"],
        [UI_LANG === "en" ? "Radiator" : "라디에이터", option.radiatorMassTons, "stack-radiator"],
        [UI_LANG === "en" ? "Propellant" : "추진체", option.propellantTons, "stack-propellant"],
      ];
      const total = Math.max(option.totalMassTons, 1e-9);
      const impracticalNote = isImpracticalOption(option)
        ? `<div class="warning">${UI_LANG === "en" ? "Shown as an impractical candidate under the current scenario." : "현재 시나리오에서 비현실적 후보로 표시 중입니다."}</div>`
        : "";
      const componentRows = components.map(([label, value]) => `
            <span>${label}</span><strong>${formatNumber(value, " t")}</strong>
      `).join("");
      const componentSegments = components.map(([label, value, className]) => {
        const share = clamp(value / total * 100, 0, 100);
        return `<span class="${className}" style="width:${share.toFixed(2)}%" title="${label}: ${formatNumber(value, " t")}"></span>`;
      }).join("");
      return `
        <div class="tooltip-breakdown">
          <div><strong>${totalLabel}</strong>: ${formatNumber(option.totalMassTons, " t")} · ${twrLabel}: ${formatTwr(option.twr, " g")}</div>
          ${impracticalNote}
          <div class="tooltip-breakdown-grid">
            ${componentRows}
          </div>
          <div class="tooltip-stack" aria-hidden="true">
            ${componentSegments}
          </div>
          <div class="muted">${UI_LANG === "en" ? "Waste heat" : "폐열"}: ${formatNumber(option.wasteHeatGW, " GW")}</div>
        </div>
      `;
    }

    function resolveTooltipItems(rows) {
      const rowById = new Map(rows.map(row => [row.id, row]));
      const resolved = [];
      const seen = new Set();
      state.lastTooltipItems.forEach(item => {
        const ref = tooltipRef(item);
        const row = resolveTooltipRow(ref, rowById, rows);
        if (!row) return;
        const options = chartMassOptions(row, state.metric);
        const option = options.find(candidate => candidate.id === ref.powerOptionId) || defaultTooltipOption(row);
        if (!option) return;
        const powerOptionId = option.id || "";
        const key = pointKey(row.id, powerOptionId);
        if (seen.has(key)) return;
        seen.add(key);
        resolved.push({ row, option, rowId: row.id, powerOptionId, key, sourceKey: ref.key });
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
      const pinnedKeys = new Set(state.pinnedTooltipItems.map(item => item.key));
      const hoverKeys = new Set(state.hoverPoints.map(item => item.key));
      state.lastTooltipItems = resolved.map(item => tooltipRef(item.rowId, item.powerOptionId));
      state.pinnedTooltipItems = resolved
        .filter(item => pinnedKeys.has(item.sourceKey) || pinnedKeys.has(item.key))
        .map(item => tooltipRef(item.rowId, item.powerOptionId));
      const nextPinnedKeys = new Set(state.pinnedTooltipItems.map(item => item.key));
      state.hoverPoints = resolved
        .filter(item => hoverKeys.has(item.sourceKey) || hoverKeys.has(item.key) || nextPinnedKeys.has(item.key))
        .map(item => tooltipRef(item.rowId, item.powerOptionId));
      tooltip.innerHTML = tooltipPanelHtml(resolved);
      tooltip.classList.remove("tooltip-empty");
      tooltip.classList.remove("has-diagnostic");
      tooltip.classList.remove("has-panel");
      updateHoverStyles();
    }

    function moveTooltipItemByOffset(key, offset) {
      if (!key || !offset) return;
      const refs = dedupeTooltipRefs(state.lastTooltipItems);
      const index = refs.findIndex(item => item.key === key);
      if (index < 0) return;
      const nextIndex = clamp(index + offset, 0, refs.length - 1);
      if (nextIndex === index) return;
      const [moving] = refs.splice(index, 1);
      refs.splice(nextIndex, 0, moving);
      state.lastTooltipItems = refs;
      syncPinnedTooltipOrder();
      const hoveredKeys = new Set(state.hoverPoints.map(item => item.key));
      if (hoveredKeys.size) {
        state.hoverPoints = refs.filter(item => hoveredKeys.has(item.key));
      }
      refreshTooltip(currentChartRows);
    }

    function toggleTooltipItemPin(key) {
      if (!key) return;
      const refs = dedupeTooltipRefs(state.lastTooltipItems);
      const ref = refs.find(item => item.key === key);
      if (!ref) return;
      if (isPinnedTooltipKey(key)) {
        state.pinnedTooltipItems = state.pinnedTooltipItems.filter(item => item.key !== key);
      } else {
        state.pinnedTooltipItems = dedupeTooltipRefs([...state.pinnedTooltipItems, ref]);
      }
      state.lastTooltipItems = mergePinnedTooltipRefs(refs);
      setHoverPoints(mergePinnedTooltipRefs(state.hoverPoints));
      refreshTooltip(currentChartRows);
    }

    function removeTooltipItem(key) {
      if (!key) return;
      state.dismissedTooltipKeys.add(key);
      state.lastTooltipItems = state.lastTooltipItems.filter(item => tooltipRef(item).key !== key);
      state.hoverPoints = state.hoverPoints.filter(item => item.key !== key);
      state.pinnedTooltipItems = state.pinnedTooltipItems.filter(item => item.key !== key);
      if (state.lastTooltipItems.length) {
        refreshTooltip(currentChartRows);
      } else {
        clearTooltip();
      }
      updateHoverStyles();
    }

    function renderEmptyTooltip() {
      const family = currentDiagnostics && currentDiagnostics.zeroFamilies.length
        ? currentDiagnostics.zeroFamilies[0]
        : null;
      if (family) {
        tooltip.innerHTML = scenarioPanelHtml(family, currentDiagnostics.zeroFamilies.length);
        tooltip.classList.add("has-diagnostic");
        tooltip.classList.remove("has-panel");
      } else {
        tooltip.innerHTML = usagePanelHtml();
        tooltip.classList.remove("has-diagnostic");
        tooltip.classList.add("has-panel");
      }
      tooltip.classList.add("tooltip-empty");
    }

    function clearTooltip(options = {}) {
      const keepPinned = !!options.keepPinned;
      const pinnedRefs = keepPinned ? pinnedTooltipRefs() : [];
      state.lastTooltipItems = pinnedRefs;
      state.hoverPoints = pinnedRefs;
      state.tooltipPinned = false;
      if (!keepPinned) state.pinnedTooltipItems = [];
      state.dismissedTooltipKeys.clear();
      state.hoverHitSignature = pinnedRefs.map(item => item.key).join("|");
      if (pinnedRefs.length) {
        refreshTooltip(currentChartRows);
      } else {
        renderEmptyTooltip();
      }
      updateHoverStyles();
    }

    function usagePanelHtml() {
      if (UI_LANG === "en") {
        return `
          <div class="usage-panel">
            <h2>How to use detail cards</h2>
            <p>Hover over a chart point to show its total-mass/TWR card here. Click a point to keep the current card set while you inspect other parts of the chart.</p>
            <ul>
              <li>Use Pin on an individual card to keep that drive visible while hovering over distant candidates.</li>
              <li>Use the arrow buttons to reorder cards, and the x button to remove cards that are no longer useful.</li>
              <li>For total-mass and TWR charts, compare the mass breakdown, wet-mass TWR, and power plant line together before choosing a research path.</li>
            </ul>
          </div>
        `;
      }
      return `
        <div class="usage-panel">
          <h2>상세 카드 사용법</h2>
          <p>차트의 데이터포인트에 마우스를 올리면 해당 추진기와 전원 조합의 총질량/TWR 카드가 이 영역에 표시됩니다. 데이터포인트를 클릭하면 현재 카드 묶음을 유지한 채 다른 지점을 살펴볼 수 있습니다.</p>
          <ul>
            <li>개별 카드의 핀 버튼을 누르면 서로 멀리 떨어진 후보를 계속 남겨 두고 비교할 수 있습니다.</li>
            <li>화살표 버튼으로 카드 순서를 바꾸고, x 버튼으로 더 이상 필요 없는 카드를 삭제할 수 있습니다.</li>
            <li>총질량/TWR 그래프에서는 질량 breakdown, 습질량 TWR, 전원 계열을 함께 보면서 어떤 연구 계통에 투자할지 판단하세요.</li>
          </ul>
        </div>
      `;
    }

    function scenarioPanelHtml(family, zeroFamilyCount) {
      const title = UI_LANG === "en" ? "Why are some drives hidden?" : "왜 일부 드라이브가 숨겨졌나요?";
      const body = scenarioExplanationText(family);
      const suggestions = scenarioSuggestions();
      const more = zeroFamilyCount > 1
        ? (UI_LANG === "en"
          ? `<p>${zeroFamilyCount - 1} additional selected ${zeroFamilyCount - 1 === 1 ? "family is" : "families are"} also hidden under this scenario.</p>`
          : `<p>이 외에도 선택된 계열 ${zeroFamilyCount - 1}개가 현재 시나리오에서 숨겨져 있습니다.</p>`)
        : "";
      return `
        <div class="scenario-panel">
          <h2>${escapeHtml(title)}</h2>
          <p>${escapeHtml(body)}</p>
          ${more}
          <div>
            <div class="muted">${escapeHtml(UI_LANG === "en" ? "Suggestions" : "제안")}</div>
            <ul>
              ${suggestions.map(item => `<li>${escapeHtml(item)}</li>`).join("")}
            </ul>
          </div>
        </div>
      `;
    }

    function scenarioExplanationText(family) {
      const familyName = localLabel(family);
      const dryMass = formatNumber(state.dryMassTons, " t");
      const targetDv = formatNumber(state.targetDvKps, UI_LANG === "en" ? " km/s" : " km/s");
      const reason = family.dominantReason;
      if (reason === "minTwr") {
        return UI_LANG === "en"
          ? `At ${dryMass} dry mass and ${targetDv} target dV, ${familyName} drives exist, but none meet the current minimum TWR filter. In this scenario their propellant mass can become very large, lowering wet-mass TWR.`
          : `건조질량 ${dryMass}, 목표 dV ${targetDv} 조건에서 ${familyName} 드라이브는 존재하지만 현재 최소 TWR 필터를 만족하지 못합니다. 이 시나리오에서는 추진체 질량이 매우 커져 습질량 TWR이 낮아질 수 있습니다.`;
      }
      if (reason === "targetDvOrMassRatio") {
        return UI_LANG === "en"
          ? `At ${dryMass} dry mass and ${targetDv} target dV, ${familyName} drives exist, but the required mass ratio is extreme for the current scenario.`
          : `건조질량 ${dryMass}, 목표 dV ${targetDv} 조건에서 ${familyName} 드라이브는 존재하지만 현재 시나리오의 요구 질량비가 극단적으로 큽니다.`;
      }
      if (reason === "invalidPowerPlant") {
        return UI_LANG === "en"
          ? `${familyName} drives exist, but no compatible power candidate can be evaluated under the current scenario.`
          : `${familyName} 드라이브는 존재하지만 현재 시나리오에서 평가 가능한 호환 전원 후보가 없습니다.`;
      }
      if (reason === "researchFilter") {
        return UI_LANG === "en"
          ? `${familyName} drives exist, but their research unlock values are not usable under the current data filters.`
          : `${familyName} 드라이브는 존재하지만 현재 데이터 필터에서 연구 개방값을 사용할 수 없습니다.`;
      }
      if (reason === "invalidComputation") {
        return UI_LANG === "en"
          ? `${familyName} drives exist, but the current scenario does not produce finite mass or TWR values for them.`
          : `${familyName} 드라이브는 존재하지만 현재 시나리오에서 유한한 질량 또는 TWR 값을 계산할 수 없습니다.`;
      }
      return UI_LANG === "en"
        ? `${familyName} drives exist, but none are visible under the current axis, scenario, and filter settings.`
        : `${familyName} 드라이브는 존재하지만 현재 축, 시나리오, 필터 설정에서는 표시되는 후보가 없습니다.`;
    }

    function scenarioSuggestions() {
      const suggestions = UI_LANG === "en"
        ? ["Lower target dV", "Lower or disable the minimum TWR filter", "Use a lower-dV scenario for this drive family"]
        : ["목표 dV 낮추기", "최소 TWR 필터 낮추기 또는 해제하기", "이 드라이브 계열에 맞는 낮은 dV 시나리오 사용하기"];
      suggestions.push(UI_LANG === "en" ? "Enable Show impractical candidates" : "비현실적 후보 표시 켜기");
      return suggestions;
    }

    function renderTable(rows) {
      const tbody = document.getElementById("tableBody");
      tbody.innerHTML = "";
      const maxResearch = Math.max(...rows.map(rowUnlockResearchValue).filter(Number.isFinite), 1);
      const metricDomain = tableMetricDomain(rows);
      const sorted = sortRows(rows);
      sorted.forEach(row => {
        const tr = document.createElement("tr");
        const powerOptions = isBandMetric() ? chartMassOptions(row) : massOptions(row);
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
          result = rowUnlockResearchValue(a) - rowUnlockResearchValue(b) || a.displayName.localeCompare(b.displayName);
        }
        return result * direction;
      });
    }

    function sortValue(row, key) {
      if (key === "drive") return row.displayName;
      if (key === "family") return `${rowCategoryLabel(row)} / ${rowFamilyLabel(row)}`;
      if (key === "research") return rowUnlockResearchValue(row);
      if (key === "metric") return metricDefs[state.metric].value(row);
      if (key === "reactor") {
        const options = massOptions(row);
        return options.length ? reactorBandText(options) : "";
      }
      return rowUnlockResearchValue(row);
    }

    function researchCell(row, maxResearch) {
      const research = rowUnlockResearchValue(row);
      const width = clamp(research / maxResearch * 100, 0, 100);
      return `
        <div class="cell-viz" title="${formatNumber(research, " research")}">
          <span class="cell-value">${formatResearch(research)}</span>
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
      const options = isBandMetric() ? chartMassOptions(row) : massOptions(row);
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

    function formatTwr(value, suffix = "") {
      if (!Number.isFinite(value)) return "-";
      const abs = Math.abs(value);
      const text = abs > 0 && abs < 0.001
        ? Number(value.toPrecision(2)).toString()
        : formatCompact(value, 1_000_000);
      return `${text}${suffix}`;
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
    (" 밴드: 최초 전원 연구력 기준", " band: first power research basis"),
    (" 밴드: 추가 전원 연구력 포함", " band: including additional power research"),
)


ENGLISH_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    ('<html lang="ko">', '<html lang="en">'),
    ("Terra Invicta 드라이브 비교", "Terra Invicta Drive Comparison"),
    (
        "X축은 최초 호환 전원을 포함한 누적 연구력입니다. 같은 연구력 대비 총질량, TWR, 추력, 효율을 비교해 어느 추진기 계통에 투자할지 판단하는 데 초점을 둡니다.",
        "The X axis is cumulative research including the first compatible power plant. Use it to compare total mass, TWR, thrust, and efficiency at similar research costs and decide which drive path to invest in.",
    ),
    ("세로축", "Vertical axis"),
    ("시뮬레이션(총 질량, TWR)", "Simulation (total mass, TWR)"),
    ("기본 정보(추력, 효율, 출력)", "Basic information (thrust, efficiency, power)"),
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
    ("총질량/TWR 보조 표시", "Total mass/TWR overlay"),
    ("TWR 정보 표시", "Show TWR information"),
    ("총질량 정보 표시", "Show total mass information"),
    ("파레토 후보 강조", "Highlight Pareto candidates"),
    ("비현실적 후보 표시", "Show impractical candidates"),
    ("추가 전원 연구력 반영", "Include additional power research"),
    ("X축: 최초+추가 전원 포함 연구력", "X axis: first + additional power research"),
    ("X축: 최초 전원 포함 연구력", "X axis: first power-inclusive research"),
    ("추가 전원 포함 연구력:", "Additional power-inclusive research:"),
    ("누적 연구력 (최초+추가 전원 포함)", "Cumulative research (first + additional power included)"),
    ("누적 연구력 (최초 전원 포함)", "Cumulative research (first power included)"),
    ("개방 연구력:", "Unlock research:"),
    ("추진기 연구:", "Drive research:"),
    ("최소 TWR", "Minimum TWR"),
    ("표시: TWR >= 0.0001 g", "Showing: TWR >= 0.0001 g"),
    ("기준 없음", "No minimum threshold"),
    ("점 밝기: TWR 높을수록 밝음", "Point brightness: brighter means higher TWR"),
    ("점 밝기: 총질량 낮을수록 밝음", "Point brightness: brighter means lower total mass"),
    ("흐린 점: Pareto 지배 후보", "Dim points: Pareto-dominated candidates"),
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
    ("순서 변경", "Reorder card"),
    ("위로 이동", "Move up"),
    ("아래로 이동", "Move down"),
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
