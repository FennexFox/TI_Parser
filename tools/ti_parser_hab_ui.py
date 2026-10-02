"""Hab state, location, solar power, slots and UI calculations."""

from __future__ import annotations

from ti_parser_errors import UserInputError

import math
from datetime import datetime
from pathlib import Path
from typing import Any

import ti_parser_hab as hab_layer
from ti_parser_config import (
    ASTRONOMICAL_UNIT_KM,
    DAYS_PER_YEAR,
    GRAVITATIONAL_CONSTANT,
    HAB_CONFIG,
    HAB_MONTHLY_RESOURCES,
    MAX_SOLAR_POWER_MULTIPLIER,
    STANDARD_GRAVITY_MPS2,
)
from ti_parser_core import (
    IndexedState,
    LocationCatalogError,
    SolarPowerDataError,
    as_float,
    clean_numbers,
    faction_effect_contexts,
    find_faction_state,
    load_hab_module_catalog,
    load_location_catalog,
    match_raw_state,
    ref_id,
    ref_summary,
    resolve_ref,
    state_value_by_id,
)
from ti_parser_runtime import (
    active_modules_in_sectors,
    calculation_catalogs,
    councilor_summary_maps,
    faction_hab_states,
    faction_is_active_human,
    faction_mining_rate,
    faction_sector_states,
    get_effective_module_state,
    hab_administration_modifier,
    hab_crew,
    hab_farm_crew_discount,
    hab_module_active_record,
    hab_module_counts,
    hab_module_current_mission_control,
    hab_module_okay,
    hab_module_records,
    hab_monthly_resource_income,
    hab_slot_summary,
    hab_template_special_rules,
    nation_adviser_science_bonus,
    required_catalog_row,
    state_adviser_attribute_bonus,
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
        raise UserInputError(f"Hab not found: {hab_name}")
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


def hab_barycenter_state(indexed: IndexedState, hab: dict[str, Any]) -> dict[str, Any]:
    return state_value_by_id(indexed, ref_id(hab.get("barycenter"))) or {}


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
        active_templates: dict[str, dict[str, Any]] = {}
        for module in active_modules:
            template_name = str(module.get("templateName") or "")
            active_templates[template_name] = required_catalog_row(
                indexed,
                hab_module_templates,
                "hab-module",
                template_name,
                "research-breakdown.hab",
            )
        records = hab_module_records(indexed, hab, hab_module_templates)
        raw_research_month = 0.0
        admin_modifier = 1.0
        module_counts: dict[str, int] = {}
        for module in active_modules:
            template_name = str(module.get("templateName") or "")
            template = active_templates[template_name]
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
