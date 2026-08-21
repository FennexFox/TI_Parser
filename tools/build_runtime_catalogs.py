#!/usr/bin/env python3
"""Generate the package-only effect, trait, org, ship, and claim catalogs."""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
from typing import Any, Callable, Iterable

from catalog_utils import write_utf8_lf
from ti_parser_catalogs import CatalogError, file_sha256, validate_catalog_envelope, value_fingerprint


GENERATOR_NAME = "build_runtime_catalogs"
GENERATOR_VERSION = "1"
SCHEMA_VERSION = 1
MANIFEST_SCHEMA_VERSION = 1
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[1] / "data"
SCENARIO_DIRECTORIES = {
    "2003Scenario": Path("DarkSkies/2003_Scenario/Templates"),
    "BrokenEarthScenario": Path("DarkSkies/Broken_Earth_Scenario/Templates"),
}
COMPILED_DEMOCRACY_DECREASE_TO_HOSTILE_CLAIM = 1.5

EFFECT_FIELDS = (
    "dataName",
    "operation",
    "value",
    "effectTarget",
    "effectDuration",
    "stackable",
    "duration_months",
    "contexts",
)
TRAIT_FIELDS = (
    "dataName",
    "friendlyName",
    "opsCost",
    "boostCost",
    "incomeMoney",
    "incomeInfluence",
    "incomeOps",
    "incomeBoost",
    "incomeResearch",
    "incomeProjects",
    "statMods",
    "techBonuses",
    "priorityBonuses",
    "baseChance",
    "classChance",
)
ORG_FIELDS = (
    "dataName",
    "friendlyName",
    "orgType",
    "tier",
    "homeRegionMapTemplateName",
    "randomized",
    "allowedOnMarket",
    "requiresNationality",
    "requiredOwnerTraits",
    "prohibitedOwnerTraits",
    "affinities",
    "restricted",
    "costMoney",
    "costInfluence",
    "costOps",
    "costBoost",
    "incomeMoney",
    "incomeInfluence",
    "incomeOps",
    "incomeBoost",
    "incomeResearch",
    "incomeProjects",
    "incomeMissionControl",
    "persuasion",
    "investigation",
    "espionage",
    "command",
    "administration",
    "science",
    "security",
    "miningBonus",
    "projectCapacityGranted",
    "techBonuses",
)

COMMON_SHIP_FIELDS = (
    "dataName",
    "friendlyName",
    "displayName",
    "requiredProjectName",
    "weightedBuildMaterials",
    "disable",
)
SHIP_COLLECTIONS: dict[str, tuple[str, str | None, tuple[str, ...]]] = {
    "hulls": (
        "TIShipHullTemplate.json",
        None,
        (
            "noseHardpoints",
            "hullHardpoints",
            "internalModules",
            "consTier",
            "length_m",
            "width_m",
            "structuralIntegrity",
            "mass_tons",
            "crew",
            "alien",
            "noShipyardBuild",
            "monthlyIncome_Money",
            "missionControl",
            "baseConstructionTime_days",
            "shipModuleSlots",
        ),
    ),
    "drives": (
        "TIDriveTemplate.json",
        None,
        (
            "thrusters",
            "driveClassification",
            "thrust_N",
            "EV_kps",
            "specificPower_kgMW",
            "efficiency",
            "flatMass_tons",
            "requiredPowerPlant",
            "thrustCap",
            "cooling",
            "powerGen",
            "propellant",
            "perTankPropellantMaterials",
        ),
    ),
    "powerPlants": (
        "TIPowerPlantTemplate.json",
        None,
        ("maxOutput_GW", "specificPower_tGW", "powerPlantClass", "efficiency", "crew"),
    ),
    "radiators": (
        "TIRadiatorTemplate.json",
        None,
        (
            "specificMass_2s_kgm2",
            "specificPower_2s_KWkg",
            "operatingTemp_K",
            "emissivity",
            "vulnerability",
            "crew",
            "radiatorType",
        ),
    ),
    "armors": (
        "TIShipArmorTemplate.json",
        None,
        (
            "xRayHalfValue_cm",
            "baryonicHalfValue_cm",
            "density_kgm3",
            "heatofVaporization_MJkg",
            "specialties",
        ),
    ),
    "batteries": (
        "TIBatteryTemplate.json",
        "battery",
        ("energyCapacity_GJ", "rechargeRate_GJs", "crew", "mass_tons", "hp"),
    ),
    "heatSinks": (
        "TIHeatSinkTemplate.json",
        "heatSink",
        ("heatCapacity_GJ", "mass_tons", "crew"),
    ),
    "utilities": (
        "TIUtilityModuleTemplate.json",
        "utility",
        (
            "crew",
            "mass_tons",
            "grouping",
            "minConsTier",
            "powerRequirement_MW",
            "specialModuleRules",
            "specialModuleValue",
        ),
    ),
    "guns": (
        "TIGunTemplate.json",
        "gun",
        (
            "mount",
            "crew",
            "attackMode",
            "defenseMode",
            "baseWeaponMass_tons",
            "cooldown_s",
            "salvo_shots",
            "intraSalvoCooldown_s",
            "efficiency",
            "magazine",
            "ammoMass_kg",
            "muzzleVelocity_kps",
            "warheadMass_kg",
            "targetingRange_km",
            "ammoMaterials",
            "damage_MJ",
            "expectedDamage_MJ",
            "flatDamage_MJ",
        ),
    ),
    "magneticWeapons": (
        "TIMagneticGunTemplate.json",
        "magnetic",
        (
            "mount",
            "crew",
            "attackMode",
            "defenseMode",
            "baseWeaponMass_tons",
            "cooldown_s",
            "salvo_shots",
            "intraSalvoCooldown_s",
            "efficiency",
            "magazine",
            "ammoMass_kg",
            "muzzleVelocity_kps",
            "warheadMass_kg",
            "targetingRange_km",
            "ammoMaterials",
            "expectedDamage_MJ",
            "flatDamage_MJ",
        ),
    ),
    "missiles": (
        "TIMissileTemplate.json",
        "missile",
        (
            "mount",
            "crew",
            "attackMode",
            "defenseMode",
            "baseWeaponMass_tons",
            "cooldown_s",
            "salvo_shots",
            "intraSalvoCooldown_s",
            "efficiency",
            "magazine",
            "ammoMass_kg",
            "muzzleVelocity_kps",
            "warheadMass_kg",
            "targetingRange_km",
            "ammoMaterials",
            "acceleration_g",
            "deltaV_kps",
            "flatDamage_MJ",
            "expectedDamage_MJ",
        ),
    ),
    "laserWeapons": (
        "TILaserWeaponTemplate.json",
        "laser",
        (
            "mount",
            "crew",
            "attackMode",
            "defenseMode",
            "baseWeaponMass_tons",
            "cooldown_s",
            "efficiency",
            "shotPower_MJ",
            "targetingRange_km",
        ),
    ),
    "particleWeapons": (
        "TIParticleWeaponTemplate.json",
        "particle",
        (
            "mount",
            "crew",
            "attackMode",
            "defenseMode",
            "baseWeaponMass_tons",
            "cooldown_s",
            "efficiency",
            "shotPower_MJ",
            "targetingRange_km",
        ),
    ),
    "plasmaWeapons": (
        "TIPlasmaWeaponTemplate.json",
        "plasma",
        (
            "mount",
            "crew",
            "attackMode",
            "defenseMode",
            "baseWeaponMass_tons",
            "cooldown_s",
            "efficiency",
            "magazine",
            "ammoMass_kg",
            "muzzleVelocity_kps",
            "warheadMass_kg",
            "chargingEnergy_GJ",
            "targetingRange_km",
            "expectedDamage_MJ",
        ),
    ),
}
WEAPON_COLLECTIONS = {
    "guns",
    "magneticWeapons",
    "missiles",
    "laserWeapons",
    "particleWeapons",
    "plasmaWeapons",
}


def read_json(path: Path) -> Any:
    if not path.is_file():
        raise CatalogError(f"Required catalog source is missing: {path}")
    try:
        content = path.read_text(encoding="utf-8-sig")
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            # Unity's shipped template reader accepts trailing commas.  Remove
            # only commas followed by a closing bracket outside JSON strings.
            return json.loads(_strip_trailing_commas(_strip_json_comments(content)))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CatalogError(f"Unable to read catalog source {path}: {exc}") from exc


def _strip_trailing_commas(content: str) -> str:
    output: list[str] = []
    in_string = False
    escaped = False
    index = 0
    while index < len(content):
        char = content[index]
        if in_string:
            output.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            index += 1
            continue
        if char == '"':
            in_string = True
            output.append(char)
            index += 1
            continue
        if char == ",":
            lookahead = index + 1
            while lookahead < len(content) and content[lookahead].isspace():
                lookahead += 1
            if lookahead < len(content) and content[lookahead] in "]}":
                index += 1
                continue
        output.append(char)
        index += 1
    return "".join(output)


def _strip_json_comments(content: str) -> str:
    output: list[str] = []
    in_string = False
    escaped = False
    index = 0
    while index < len(content):
        char = content[index]
        if in_string:
            output.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            index += 1
            continue
        if char == '"':
            in_string = True
            output.append(char)
            index += 1
            continue
        if char == "/" and index + 1 < len(content) and content[index + 1] == "/":
            index += 2
            while index < len(content) and content[index] not in "\r\n":
                index += 1
            continue
        if char == "/" and index + 1 < len(content) and content[index + 1] == "*":
            index += 2
            while index + 1 < len(content) and content[index : index + 2] != "*/":
                if content[index] in "\r\n":
                    output.append(content[index])
                index += 1
            index = min(index + 2, len(content))
            continue
        output.append(char)
        index += 1
    return "".join(output)


def normalize_fields(row: dict[str, Any], fields: Iterable[str]) -> dict[str, Any]:
    return {field: deepcopy(row[field]) for field in fields if field in row}


def index_raw_rows(path: Path) -> dict[str, dict[str, Any]]:
    raw = read_json(path)
    if not isinstance(raw, list):
        raise CatalogError(f"Template collection must be an array: {path}")
    result: dict[str, dict[str, Any]] = {}
    for row in raw:
        if not isinstance(row, dict):
            raise CatalogError(f"Template collection contains a non-object row: {path}")
        name = row.get("dataName")
        if not isinstance(name, str) or not name:
            raise CatalogError(f"Template row has no dataName: {path}")
        if name in result:
            raise CatalogError(f"Duplicate dataName {name!r}: {path}")
        result[name] = row
    return result


def merge_raw_rows(base: dict[str, dict[str, Any]], overlay_path: Path | None) -> dict[str, dict[str, Any]]:
    result = deepcopy(base)
    if overlay_path is None or not overlay_path.is_file():
        return result
    for name, patch in index_raw_rows(overlay_path).items():
        if name in result:
            result[name].update(deepcopy(patch))
        else:
            result[name] = deepcopy(patch)
    return result


def normalized_collection(
    rows: dict[str, dict[str, Any]],
    fields: Iterable[str],
    *,
    kind: str | None = None,
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for name in sorted(rows):
        row = normalize_fields(rows[name], fields)
        if kind is not None:
            row["_shipPlanKind"] = kind
        result[name] = row
    return result


def resolved_override(
    base_rows: dict[str, dict[str, Any]],
    overlay_path: Path | None,
    fields: Iterable[str],
    *,
    kind: str | None = None,
) -> dict[str, dict[str, Any]]:
    if overlay_path is None or not overlay_path.is_file():
        return {}
    resolved = normalized_collection(merge_raw_rows(base_rows, overlay_path), fields, kind=kind)
    base = normalized_collection(base_rows, fields, kind=kind)
    changed_names = sorted(name for name, row in resolved.items() if base.get(name) != row)
    return {name: resolved[name] for name in changed_names}


def discover_supported_scenarios(
    templates_dir: Path,
    scenario_dirs: dict[str, Path],
) -> list[str]:
    meta_rows = index_raw_rows(templates_dir / "TIMetaTemplate.json")
    base_scenarios = [
        name
        for name, row in meta_rows.items()
        if row.get("isNewCampaignOption") is True and row.get("newCampaignOptionCategory") == "Scenario"
    ]
    discovered = list(base_scenarios)
    for scenario, directory in scenario_dirs.items():
        meta_path = directory / "TIMetaTemplate.json"
        if not meta_path.is_file():
            continue
        rows = index_raw_rows(meta_path)
        row = rows.get(scenario)
        if not row or row.get("newCampaignOptionCategory") != "Scenario":
            raise CatalogError(f"Scenario metadata {scenario!r} is missing from {meta_path}")
        discovered.append(scenario)
    if not discovered:
        raise CatalogError("No supported campaign scenarios were found in TIMetaTemplate.json")
    return sorted(set(discovered))


def source_entry(path: Path, logical_name: str) -> dict[str, str]:
    return {"name": logical_name.replace("\\", "/"), "sha256": file_sha256(path)}


def scenario_metadata_sources(
    templates_dir: Path,
    scenario_dirs: dict[str, Path],
) -> list[dict[str, str]]:
    sources = [source_entry(templates_dir / "TIMetaTemplate.json", "base/TIMetaTemplate.json")]
    for scenario, directory in scenario_dirs.items():
        path = directory / "TIMetaTemplate.json"
        if path.is_file():
            sources.append(source_entry(path, f"{scenario}/TIMetaTemplate.json"))
    return sources


def make_envelope(
    *,
    base: dict[str, Any],
    scenario_overrides: dict[str, dict[str, Any]],
    source_files: list[dict[str, str]],
    supported_scenarios: list[str],
) -> dict[str, Any]:
    payload = {
        "base": base,
        "scenarioOverrides": scenario_overrides,
    }
    return {
        "schemaVersion": SCHEMA_VERSION,
        "generator": {"name": GENERATOR_NAME, "version": GENERATOR_VERSION},
        "sourceFiles": sorted(source_files, key=lambda item: item["name"]),
        "supportedScenarios": list(supported_scenarios),
        **payload,
        "payloadFingerprint": value_fingerprint(payload),
    }


def build_row_catalog(
    *,
    templates_dir: Path,
    scenario_dirs: dict[str, Path],
    supported_scenarios: list[str],
    filename: str,
    collection: str,
    fields: Iterable[str],
) -> dict[str, Any]:
    base_path = templates_dir / filename
    base_rows = index_raw_rows(base_path)
    sources = [
        source_entry(base_path, f"base/{filename}"),
        *scenario_metadata_sources(templates_dir, scenario_dirs),
    ]
    overrides: dict[str, dict[str, Any]] = {}
    for scenario, directory in scenario_dirs.items():
        overlay_path = directory / filename
        if not overlay_path.is_file():
            continue
        sources.append(source_entry(overlay_path, f"{scenario}/{filename}"))
        changed = resolved_override(base_rows, overlay_path, fields)
        if changed:
            overrides[scenario] = {collection: changed}
    return make_envelope(
        base={collection: normalized_collection(base_rows, fields)},
        scenario_overrides=overrides,
        source_files=sources,
        supported_scenarios=supported_scenarios,
    )


def build_ship_catalog(
    templates_dir: Path,
    scenario_dirs: dict[str, Path],
    supported_scenarios: list[str],
) -> dict[str, Any]:
    sources = scenario_metadata_sources(templates_dir, scenario_dirs)
    collections: dict[str, Any] = {}
    weapons: dict[str, dict[str, Any]] = {}
    for collection, (filename, kind, extra_fields) in SHIP_COLLECTIONS.items():
        path = templates_dir / filename
        sources.append(source_entry(path, f"base/{filename}"))
        normalized = normalized_collection(
            index_raw_rows(path),
            (*COMMON_SHIP_FIELDS, *extra_fields),
            kind=kind,
        )
        if collection in WEAPON_COLLECTIONS:
            collisions = sorted(set(weapons) & set(normalized))
            if collisions:
                raise CatalogError(f"Duplicate ship weapon dataName values across template files: {collisions}")
            weapons.update(normalized)
        else:
            collections[collection] = normalized
    collections["weapons"] = {name: weapons[name] for name in sorted(weapons)}
    return make_envelope(
        base=collections,
        scenario_overrides={},
        source_files=sources,
        supported_scenarios=supported_scenarios,
    )


def _global_config(path: Path) -> dict[str, Any]:
    value = read_json(path)
    if isinstance(value, list):
        if len(value) != 1 or not isinstance(value[0], dict):
            raise CatalogError(f"Expected one TIGlobalConfig object: {path}")
        return value[0]
    if not isinstance(value, dict):
        raise CatalogError(f"TIGlobalConfig must be an object: {path}")
    return value


def build_nation_claim_catalog(
    templates_dir: Path,
    scenario_dirs: dict[str, Path],
    supported_scenarios: list[str],
    assembly_path: Path | None,
) -> dict[str, Any]:
    config_path = templates_dir / "TIGlobalConfig.json"
    config = _global_config(config_path)
    configured = config.get("democracyDecreaseToMakeHostileClaim")
    threshold = configured if isinstance(configured, (int, float)) else COMPILED_DEMOCRACY_DECREASE_TO_HOSTILE_CLAIM
    sources = [
        source_entry(config_path, "base/TIGlobalConfig.json"),
        *scenario_metadata_sources(templates_dir, scenario_dirs),
    ]
    value_source = "TIGlobalConfig.json"
    if configured is None:
        if assembly_path is not None and assembly_path.is_file():
            sources.append(source_entry(assembly_path, "TerraInvicta_Data/Managed/Assembly-CSharp.dll"))
        value_source = "TIGlobalConfig.democracyDecreaseToMakeHostileClaim compiled field initializer"
    overrides: dict[str, dict[str, Any]] = {}
    for scenario, directory in scenario_dirs.items():
        overlay_path = directory / "TIGlobalConfig.json"
        if not overlay_path.is_file():
            continue
        sources.append(source_entry(overlay_path, f"{scenario}/TIGlobalConfig.json"))
        overlay_value = _global_config(overlay_path).get("democracyDecreaseToMakeHostileClaim", threshold)
        if overlay_value != threshold:
            overrides[scenario] = {
                "democracyDecreaseToMakeHostileClaim": overlay_value,
            }
    return make_envelope(
        base={
            "democracyDecreaseToMakeHostileClaim": threshold,
            "hostileClaimDueToDemocracyFormula": (
                "targetDemocracy > claimantDemocracy + democracyDecreaseToMakeHostileClaim"
            ),
            "valueSource": value_source,
        },
        scenario_overrides=overrides,
        source_files=sources,
        supported_scenarios=supported_scenarios,
    )


def deterministic_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n"


def write_catalog(path: Path, value: Any) -> None:
    write_utf8_lf(path, deterministic_json(value))


def build_all(
    templates_dir: str | Path,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    *,
    dlc_content_dir: str | Path | None = None,
    assembly_path: str | Path | None = None,
) -> dict[str, Any]:
    templates = Path(templates_dir)
    output = Path(output_dir)
    game_root = templates.parents[2] if len(templates.parents) >= 3 else templates.parent
    dlc_root = Path(dlc_content_dir) if dlc_content_dir is not None else game_root / "DLC_Content"
    resolved_scenario_dirs = {
        scenario: dlc_root / relative
        for scenario, relative in SCENARIO_DIRECTORIES.items()
    }
    resolved_assembly = (
        Path(assembly_path)
        if assembly_path is not None
        else game_root / "TerraInvicta_Data" / "Managed" / "Assembly-CSharp.dll"
    )
    supported_scenarios = discover_supported_scenarios(templates, resolved_scenario_dirs)
    envelopes = {
        "effect_catalog.json": build_row_catalog(
            templates_dir=templates,
            scenario_dirs=resolved_scenario_dirs,
            supported_scenarios=supported_scenarios,
            filename="TIEffectTemplate.json",
            collection="effects",
            fields=EFFECT_FIELDS,
        ),
        "trait_catalog.json": build_row_catalog(
            templates_dir=templates,
            scenario_dirs=resolved_scenario_dirs,
            supported_scenarios=supported_scenarios,
            filename="TITraitTemplate.json",
            collection="traits",
            fields=TRAIT_FIELDS,
        ),
        "org_catalog.json": build_row_catalog(
            templates_dir=templates,
            scenario_dirs=resolved_scenario_dirs,
            supported_scenarios=supported_scenarios,
            filename="TIOrgTemplate.json",
            collection="orgs",
            fields=ORG_FIELDS,
        ),
        "ship_catalog.json": build_ship_catalog(templates, resolved_scenario_dirs, supported_scenarios),
        "nation_claim_catalog.json": build_nation_claim_catalog(
            templates,
            resolved_scenario_dirs,
            supported_scenarios,
            resolved_assembly,
        ),
    }
    for filename, envelope in envelopes.items():
        write_catalog(output / filename, envelope)
    entries = {
        filename: {
            "sha256": file_sha256(output / filename),
            "schemaVersion": envelope["schemaVersion"],
            "payloadFingerprint": envelope["payloadFingerprint"],
        }
        for filename, envelope in sorted(envelopes.items())
    }
    research_path = output / "research_catalog.json"
    if research_path.is_file():
        research_envelope = validate_catalog_envelope(read_json(research_path), path=research_path)
        entries[research_path.name] = {
            "sha256": file_sha256(research_path),
            "schemaVersion": research_envelope["schemaVersion"],
            "payloadFingerprint": research_envelope["payloadFingerprint"],
        }
        entries = dict(sorted(entries.items()))
    manifest = {
        "schemaVersion": MANIFEST_SCHEMA_VERSION,
        "generator": {"name": GENERATOR_NAME, "version": GENERATOR_VERSION},
        "catalogs": entries,
        "bundleFingerprint": value_fingerprint(entries),
    }
    write_catalog(output / "catalog_manifest.json", manifest)
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--templates-dir", required=True, help="Base StreamingAssets/Templates directory")
    parser.add_argument("--dlc-content-dir", help="DLC_Content directory; inferred from the base path by default")
    parser.add_argument("--assembly-path", help="Assembly-CSharp.dll path for compiled-config provenance")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = build_all(
        args.templates_dir,
        args.output_dir,
        dlc_content_dir=args.dlc_content_dir,
        assembly_path=args.assembly_path,
    )
    print(deterministic_json(manifest), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
