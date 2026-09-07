#!/usr/bin/env python3
"""Build the packaged Terra Invicta body/orbit calculation catalog."""

from __future__ import annotations

import argparse
import hashlib
from collections.abc import Callable
from pathlib import Path
from typing import Any

import ti_save_parser as ti
from catalog_utils import source_fingerprint, write_json_output


SCHEMA_VERSION = 2
DEFAULT_JSON_OUTPUT = Path("data/location_catalog.json")
BODY_FIELDS = (
    "dataName",
    "friendlyName",
    "barycenterName",
    "objectType",
    "atmosphere",
    "semiMajorAxis_AU",
    "semiMajorAxis_km",
    "eccentricity",
    "inclination_Deg",
    "tilt_Deg",
    "meanRadius_km",
    "equatorialRadius_km",
    "oblateness",
    "dimensionX_km",
    "dimensionY_km",
    "dimensionZ_km",
    "mass_kg",
    "Hill Radius in km",
    "rotationPeriod_strHours",
    "irradiatedMultiplier",
    "maxHabSize",
)
ORBIT_FIELDS = (
    "dataName",
    "friendlyName",
    "barycenterName",
    "altitude_km",
    "semiMajorAxis_km",
    "semiMajorAxis_AU",
    "eccentricity",
    "inclination_Deg",
    "radialOrbit",
    "synch",
    "irradiatedMultiplier",
    "interfaceOrbit",
    "earthLEO",
    "stationCapacity",
)
NAVIGABLE_FIELDS = (
    "dataName",
    "lagrangeValue",
    "relatedObject",
    "orbits",
    "maxHabSize",
)


def normalize_template(template: dict[str, Any], fields: tuple[str, ...]) -> dict[str, Any]:
    row: dict[str, Any] = {}
    for field in fields:
        value = template.get(field)
        if value is None:
            continue
        row[field] = value
    return row


def body_mean_radius_km(template: dict[str, Any]) -> float:
    mean_radius = ti.as_float(template.get("meanRadius_km"), 0.0)
    if mean_radius > 0.0:
        return mean_radius
    equatorial_radius = ti.as_float(template.get("equatorialRadius_km"), 0.0)
    if equatorial_radius > 0.0:
        polar_radius = equatorial_radius * (1.0 - ti.as_float(template.get("oblateness"), 0.0))
        return (equatorial_radius * 2.0 + polar_radius) / 3.0
    dimensions = [
        value
        for field in ("dimensionX_km", "dimensionY_km", "dimensionZ_km")
        if (value := ti.as_float(template.get(field), 0.0)) > 0.0
    ]
    return sum(dimensions) / len(dimensions) / 2.0 if dimensions else 0.0


def body_max_radius_km(template: dict[str, Any]) -> float:
    dimensions = [
        value
        for field in ("dimensionX_km", "dimensionY_km", "dimensionZ_km")
        if (value := ti.as_float(template.get(field), 0.0)) > 0.0
    ]
    if dimensions:
        return max(dimensions) / 2.0
    equatorial_radius = ti.as_float(template.get("equatorialRadius_km"), 0.0)
    return equatorial_radius if equatorial_radius > 0.0 else body_mean_radius_km(template)


def normalize_body(template: dict[str, Any]) -> dict[str, Any]:
    row = normalize_template(template, BODY_FIELDS)
    mean_radius = body_mean_radius_km(template)
    max_radius = body_max_radius_km(template)
    hill_radius = ti.as_float(template.get("Hill Radius in km"), 0.0)
    if mean_radius > 0.0:
        row["meanRadius_km"] = mean_radius
    if max_radius > 0.0:
        row["maxRadius_km"] = max_radius
    if hill_radius > 0.0:
        row["hillRadius_km"] = hill_radius
    return row


def normalize_navigable(template: dict[str, Any]) -> dict[str, Any]:
    row = normalize_template(template, NAVIGABLE_FIELDS)
    row["locationKind"] = "LagrangePoint"
    return row


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_with_hash(path: Path) -> dict[str, Any]:
    result = source_fingerprint(path)
    result["sha256"] = file_sha256(path)
    return result


def normalize_collection(
    templates: dict[str, dict[str, Any]],
    fields: tuple[str, ...],
    source_name: str,
    normalizer: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    if not templates:
        raise ValueError(f"Required source template collection is missing or empty: {source_name}")
    normalize = normalizer or (lambda template: normalize_template(template, fields))
    rows = [normalize(template) for template in templates.values()]
    invalid = [row for row in rows if not row.get("dataName")]
    if invalid:
        raise ValueError(f"Source template collection contains rows without dataName: {source_name}")
    rows.sort(key=lambda row: str(row["dataName"]))
    return rows


def validate_location_relations(
    bodies: list[dict[str, Any]],
    navigables: list[dict[str, Any]],
    orbits: list[dict[str, Any]],
) -> None:
    body_names = {str(row["dataName"]) for row in bodies}
    navigable_names = {str(row["dataName"]) for row in navigables}
    collisions = sorted(body_names & navigable_names)
    if collisions:
        raise ValueError(f"Body/navigable dataName collisions: {collisions}")
    orbits_by_name = {str(row["dataName"]): row for row in orbits}
    for navigable in navigables:
        name = str(navigable["dataName"])
        related_object = str(navigable.get("relatedObject") or "")
        if related_object not in body_names:
            raise ValueError(f"Navigable {name!r} references missing related body {related_object!r}")
        orbit_names = navigable.get("orbits") if isinstance(navigable.get("orbits"), list) else []
        if not orbit_names or len(set(orbit_names)) != len(orbit_names):
            raise ValueError(f"Navigable {name!r} has invalid orbit references")
        for orbit_name in orbit_names:
            orbit = orbits_by_name.get(str(orbit_name))
            if orbit is None:
                raise ValueError(f"Navigable {name!r} references missing orbit {orbit_name!r}")
            if orbit.get("barycenterName") != name:
                raise ValueError(f"Navigable {name!r} orbit {orbit_name!r} has a mismatched barycenter")


def build_catalog(templates_dir: Path) -> dict[str, Any]:
    body_path = templates_dir / "TISpaceBodyTemplate.json"
    navigable_path = templates_dir / "TINavigableTemplate.json"
    orbit_path = templates_dir / "TIOrbitTemplate.json"
    bodies = normalize_collection(
        ti.load_named_templates(templates_dir, body_path.name),
        BODY_FIELDS,
        body_path.name,
        normalize_body,
    )
    navigables = normalize_collection(
        ti.load_named_templates(templates_dir, navigable_path.name),
        NAVIGABLE_FIELDS,
        navigable_path.name,
        normalize_navigable,
    )
    orbits = normalize_collection(
        ti.load_named_templates(templates_dir, orbit_path.name),
        ORBIT_FIELDS,
        orbit_path.name,
    )
    validate_location_relations(bodies, navigables, orbits)
    return {
        "schemaVersion": SCHEMA_VERSION,
        "source": {
            "templateRoot": "TerraInvicta_Data/StreamingAssets/Templates",
            "spaceBodyTemplate": source_with_hash(body_path),
            "navigableTemplate": source_with_hash(navigable_path),
            "orbitTemplate": source_with_hash(orbit_path),
        },
        "counts": {"spaceBodies": len(bodies), "navigables": len(navigables), "orbits": len(orbits)},
        "notes": [
            "Runtime calculations use this packaged catalog and never fall back to installed body/navigable/orbit templates.",
            "Absent optional fields remain absent rather than being normalized to zero.",
            "Lagrange navigables remain distinct from physical bodies and have no synthesized physical properties.",
            "Installed 2003 and Broken Earth scenario sources contain no body/navigable/orbit overrides.",
        ],
        "spaceBodies": bodies,
        "navigables": navigables,
        "orbits": orbits,
        "byDataName": {
            "spaceBodies": {row["dataName"]: index for index, row in enumerate(bodies)},
            "navigables": {row["dataName"]: index for index, row in enumerate(navigables)},
            "orbits": {row["dataName"]: index for index, row in enumerate(orbits)},
        },
        "scenarioOverrides": {},
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate the normalized Terra Invicta body/orbit catalog.")
    parser.add_argument("--templates-dir", help="Path to TerraInvicta_Data\\StreamingAssets\\Templates.")
    parser.add_argument("--json-output", default=str(DEFAULT_JSON_OUTPUT), help="Generated JSON output path.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    templates_dir = ti.resolve_templates_dir(args.templates_dir)
    if templates_dir is None:
        raise SystemExit("Templates directory not found. Pass --templates-dir.")
    catalog = build_catalog(templates_dir)
    json_output = Path(args.json_output)
    write_json_output(json_output, catalog)
    ti.print_json(
        {
            "spaceBodies": len(catalog["spaceBodies"]),
            "navigables": len(catalog["navigables"]),
            "orbits": len(catalog["orbits"]),
            "json": str(json_output),
            "templatesDir": str(templates_dir),
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
