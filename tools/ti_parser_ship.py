"""Pure ship component, ranking, power, resource, and armor helpers."""

from __future__ import annotations

import math
from typing import Any, Iterable

from ti_parser_core import as_float, clean_numbers


SPACE_RESOURCE_TO_TONS = 0.1


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
    scale = SPACE_RESOURCE_TO_TONS
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
        shot_power_gj = as_float(template.get("shotPower_MJ"), 0.0) / 1000.0
        return (shot_power_gj + bonus_power_gj) / efficiency
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
