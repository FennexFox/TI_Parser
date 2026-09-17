"""Saved ship simulation, shipyard timing and ship plans."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from ti_parser_config import (
    DEFAULT_GLOBAL_CONFIG,
    SHIP_PLAN_SHIPYARD_TIERS,
    STANDARD_GRAVITY_MPS2,
)
from ti_parser_core import (
    IndexedState,
    apply_effect_modifiers,
    as_float,
    clean_numbers,
    faction_effect_contexts,
    find_faction_state,
    first_value,
    load_hab_module_catalog,
)
from ti_parser_runtime import (
    calculation_catalogs,
    faction_brief,
    faction_ship_states,
    required_catalog_row,
    scenario_customizations,
    scenario_float,
)
from ti_parser_ship import (
    ship_plan_add_scaled_materials,
    ship_plan_armor_mass_tons,
    ship_plan_clean_resources,
    ship_plan_drive_goal_views,
    ship_plan_drive_open_cycle,
    ship_plan_drive_power_requirement_gw,
    ship_plan_drive_row,
    ship_plan_drive_thrust_power_gw,
    ship_plan_generic_row,
    ship_plan_hull_row,
    ship_plan_part_unlocked,
    ship_plan_power_plant_class_compatible,
    ship_plan_power_plant_row,
    ship_plan_utility_row,
    ship_plan_utility_rule_value,
    ship_plan_weapon_cost,
    ship_plan_weapon_energy_gj,
    ship_plan_weapon_goal_views,
    ship_plan_weapon_mass_tons,
    ship_plan_weapon_row,
)


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
    for tier, shipyard_name in SHIP_PLAN_SHIPYARD_TIERS.items():
        shipyard = required_catalog_row(
            indexed,
            shipyard_templates,
            "hab-module",
            shipyard_name,
            "ship-design.construction-time.shipyard",
            "required packaged shipyard definition is absent",
        )
        tier_delta = tier - hull_tier
        if tier_delta > 0:
            yard_modifier = as_float(shipyard.get("constructionTimeModifier"), 1.0) ** tier_delta
        elif tier_delta < 0:
            yard_modifier = DEFAULT_GLOBAL_CONFIG["smallShipyardPenaltyPowerPerTier"] ** (-tier_delta)
        else:
            yard_modifier = 1.0
        by_tier[str(tier)] = {
            "shipyard": shipyard_name,
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
    hull = required_catalog_row(
        indexed,
        catalogs["hulls"],
        "ship-hull",
        design.get("hullName"),
        "ship-design.simulation.hull",
    )
    drive = required_catalog_row(
        indexed,
        catalogs["drives"],
        "ship-drive",
        design.get("driveName"),
        "ship-design.simulation.drive",
    )
    power_plant = required_catalog_row(
        indexed,
        catalogs["powerPlants"],
        "ship-power-plant",
        design.get("powerPlantName"),
        "ship-design.simulation.power-plant",
    )
    radiator = required_catalog_row(
        indexed,
        catalogs["radiators"],
        "ship-radiator",
        design.get("radiatorName"),
        "ship-design.simulation.radiator",
    )
    utility_entries = design.get("moduleTemplateEntries") if isinstance(design.get("moduleTemplateEntries"), list) else []
    weapon_entries = [
        *(design.get("hullWeaponTemplateEntries") if isinstance(design.get("hullWeaponTemplateEntries"), list) else []),
        *(design.get("noseWeaponTemplateEntries") if isinstance(design.get("noseWeaponTemplateEntries"), list) else []),
    ]
    utilities = []
    for entry in utility_entries:
        if not isinstance(entry, dict):
            continue
        module_name = str(entry.get("moduleName") or "")
        if not module_name or module_name == "Empty":
            continue
        utilities.append(
            required_catalog_row(
                indexed,
                catalogs["utilities"],
                "ship-utility",
                module_name,
                "ship-design.simulation.utility",
            )
        )
    weapons = []
    for entry in weapon_entries:
        if not isinstance(entry, dict):
            continue
        module_name = str(entry.get("moduleName") or "")
        if not module_name or module_name == "Empty":
            continue
        weapons.append(
            required_catalog_row(
                indexed,
                catalogs["weapons"],
                "ship-weapon",
                module_name,
                "ship-design.simulation.weapon",
            )
        )
    armor_facings = {
        facing: design.get(f"{facing}Armor") if isinstance(design.get(f"{facing}Armor"), dict) else {}
        for facing in ("nose", "lateral", "tail")
    }
    armor_templates: dict[str, dict[str, Any] | None] = {}
    for facing, entry in armor_facings.items():
        if as_float(entry.get("armorValue"), 0.0) <= 0.0:
            armor_templates[facing] = None
            continue
        armor_templates[facing] = required_catalog_row(
            indexed,
            catalogs["armors"],
            "ship-armor",
            entry.get("materialName"),
            f"ship-design.simulation.{facing}-armor",
        )
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
            "source": "packaged-runtime-catalog",
            "templatesDir": None,
            "warning": None if hull_templates and drive_templates else "The packaged ship catalog is missing required component rows.",
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
