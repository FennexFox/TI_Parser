"""Shared save loading, indexing, and serialization helpers."""

from __future__ import annotations

import gzip
import hashlib
import json
import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable


DEFAULT_CACHE_DIR = ".ti_cache"
SAVE_GLOB = "*.gz"
DEFAULT_MODULE_CATALOG = Path(__file__).resolve().parents[1] / "data" / "module_catalog.json"
DEFAULT_LOCATION_CATALOG = Path(__file__).resolve().parents[1] / "data" / "location_catalog.json"
TemplateSource = Path | tuple[Path, ...] | list[Path] | None
SCENARIO_DLC_TEMPLATE_HINTS = {
    "2003Scenario": Path("DLC_Content/DarkSkies/2003_Scenario/Templates"),
    "BrokenEarthScenario": Path("DLC_Content/DarkSkies/Broken_Earth_Scenario/Templates"),
}


@dataclass(frozen=True)
class IndexedState:
    data: dict[str, Any]
    gamestates: dict[str, list[dict[str, Any]]]
    id_index: dict[int, tuple[str, str, dict[str, Any]]]


class ModuleCatalogError(RuntimeError):
    """Raised when authoritative hab-module data cannot be loaded safely."""


class LocationCatalogError(RuntimeError):
    """Raised when authoritative body/orbit data cannot be loaded safely."""


class SolarPowerDataError(RuntimeError):
    """Raised when location-aware solar output lacks authoritative location data."""


@dataclass(frozen=True)
class CalculationDependency:
    """One required calculation input that could not be resolved safely."""

    kind: str
    name: str
    context: str | None
    scenario: str | None
    reason: str

    def to_dict(self) -> dict[str, str | None]:
        return {
            "kind": self.kind,
            "name": self.name,
            "context": self.context,
            "scenario": self.scenario,
            "reason": self.reason,
        }


class CalculationDependencyError(RuntimeError):
    """Raised instead of returning a value with required inputs omitted."""

    def __init__(self, dependency: CalculationDependency):
        self.dependencies = (dependency,)
        self.missing_dependencies = [dependency.to_dict()]
        context = f" in context {dependency.context!r}" if dependency.context else ""
        super().__init__(
            f"Missing or invalid {dependency.kind} dependency {dependency.name!r}{context}: "
            f"{dependency.reason}"
        )


@dataclass(frozen=True)
class LocationCatalog:
    """One version-locked body/navigable/orbit location dataset."""

    body_templates: dict[str, dict[str, Any]]
    navigable_templates: dict[str, dict[str, Any]]
    location_templates: dict[str, dict[str, Any]]
    orbit_templates: dict[str, dict[str, Any]]
    metadata: dict[str, Any]


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


def scenario_template_name(indexed: IndexedState) -> str | None:
    time_state = first_value(indexed, "TITimeState") or {}
    value = time_state.get("scenarioMetaTemplateName")
    return str(value) if value else None


def template_directories(templates: TemplateSource) -> tuple[Path, ...]:
    if templates is None:
        return ()
    if isinstance(templates, Path):
        return (templates,)
    return tuple(Path(path) for path in templates)


def template_source_paths(templates: TemplateSource) -> list[str]:
    return [str(directory.resolve()) for directory in template_directories(templates)]


def template_source_value(templates: TemplateSource) -> str | list[str] | None:
    sources = template_source_paths(templates)
    if not sources:
        return None
    return sources[0] if len(sources) == 1 else sources


def game_root_from_templates_dir(templates_dir: Path) -> Path | None:
    resolved = templates_dir.resolve()
    if (
        resolved.name == "Templates"
        and resolved.parent.name == "StreamingAssets"
        and resolved.parent.parent.name == "TerraInvicta_Data"
    ):
        return resolved.parent.parent.parent
    return None


def scenario_template_sources(indexed: IndexedState, base_templates_dir: Path | None) -> tuple[Path, ...] | None:
    if base_templates_dir is None:
        return None
    sources = [base_templates_dir]
    scenario_name = scenario_template_name(indexed)
    game_root = game_root_from_templates_dir(base_templates_dir)
    if not scenario_name or game_root is None:
        return tuple(sources)

    hinted = SCENARIO_DLC_TEMPLATE_HINTS.get(scenario_name)
    if hinted is not None:
        candidate = game_root / hinted
        if candidate.is_dir():
            sources.append(candidate)
            return tuple(sources)

    dlc_dir = game_root / "DLC_Content"
    if not dlc_dir.is_dir():
        return tuple(sources)
    for meta_path in sorted(dlc_dir.rglob("TIMetaTemplate.json")):
        candidate = meta_path.parent
        try:
            meta_templates = load_named_templates(candidate, meta_path.name)
        except (OSError, json.JSONDecodeError):
            continue
        if scenario_name in meta_templates and candidate not in sources:
            sources.append(candidate)
    return tuple(sources)


def resolve_scenario_templates(save_path: Path, base_templates_dir: Path | None) -> tuple[Path, ...] | None:
    return scenario_template_sources(build_index(load_save(save_path)), base_templates_dir)


def file_fingerprint(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.is_file():
        return None
    stat = path.stat()
    return {"path": str(path), "size": stat.st_size, "mtime_ns": stat.st_mtime_ns}


def template_file_fingerprints(templates: TemplateSource, filename: str) -> list[dict[str, Any]]:
    return [
        fingerprint
        for directory in template_directories(templates)
        if (fingerprint := file_fingerprint(directory / filename)) is not None
    ]


def snapshot_fingerprint(save_path: Path, templates_dir: TemplateSource) -> dict[str, Any]:
    return {
        "save": save_fingerprint(save_path),
        "templateSources": template_source_paths(templates_dir),
        "traitTemplates": template_file_fingerprints(templates_dir, "TITraitTemplate.json"),
    }


def load_trait_templates(templates_dir: TemplateSource) -> dict[str, dict[str, Any]]:
    return load_named_templates(templates_dir, "TITraitTemplate.json")


def module_catalog_diagnostics(catalog_path: Path = DEFAULT_MODULE_CATALOG) -> dict[str, Any]:
    resolved = catalog_path.resolve()
    if not resolved.is_file():
        raise ModuleCatalogError(f"Required module catalog not found: {resolved}")
    stat = resolved.stat()
    with resolved.open("r", encoding="utf-8-sig") as handle:
        raw = json.load(handle)
    if not isinstance(raw, dict) or not isinstance(raw.get("modules"), list):
        raise ModuleCatalogError(f"Invalid module catalog structure: {resolved}")
    return {
        "path": str(resolved),
        "schemaVersion": raw.get("schemaVersion"),
        "moduleCount": len(raw["modules"]),
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
        "source": raw.get("source"),
    }


def location_catalog_diagnostics(catalog_path: Path = DEFAULT_LOCATION_CATALOG) -> dict[str, Any]:
    resolved = catalog_path.resolve()
    catalog = load_location_catalog(resolved)
    stat = resolved.stat()
    return {
        "path": str(resolved),
        "schemaVersion": catalog.metadata["schemaVersion"],
        "bodyCount": len(catalog.body_templates),
        "navigableCount": len(catalog.navigable_templates),
        "locationCount": len(catalog.location_templates),
        "orbitCount": len(catalog.orbit_templates),
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
        "source": catalog.metadata.get("source"),
        "scenarioOverrides": sorted(catalog.metadata.get("scenarioOverrides") or {}),
    }


def load_location_catalog(catalog_path: Path = DEFAULT_LOCATION_CATALOG) -> LocationCatalog:
    """Load packaged body/orbit data; raw game templates are never a runtime fallback."""

    resolved = catalog_path.resolve()
    if not resolved.is_file():
        raise LocationCatalogError(f"Required location catalog not found: {resolved}")
    stat = resolved.stat()
    return _load_location_catalog_cached(str(resolved), stat.st_size, stat.st_mtime_ns)


@lru_cache(maxsize=None)
def _load_location_catalog_cached(path_value: str, size: int, mtime_ns: int) -> LocationCatalog:
    del size, mtime_ns
    path = Path(path_value)
    try:
        with path.open("r", encoding="utf-8-sig") as handle:
            raw = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise LocationCatalogError(f"Unable to read location catalog {path}: {exc}") from exc
    if not isinstance(raw, dict) or raw.get("schemaVersion") != 2:
        raise LocationCatalogError(f"Unsupported or missing location catalog schemaVersion in: {path}")
    if not isinstance(raw.get("scenarioOverrides"), dict):
        raise LocationCatalogError(f"Invalid scenarioOverrides collection in location catalog: {path}")
    if raw["scenarioOverrides"]:
        raise LocationCatalogError(
            f"Scenario-specific location catalog overrides are present but runtime selection is not implemented: {path}"
        )

    def index_rows(collection_name: str, required_fields: set[str]) -> dict[str, dict[str, Any]]:
        rows = raw.get(collection_name)
        if not isinstance(rows, list) or not rows:
            raise LocationCatalogError(f"Invalid or empty {collection_name} collection in location catalog: {path}")
        templates: dict[str, dict[str, Any]] = {}
        for row in rows:
            if not isinstance(row, dict):
                raise LocationCatalogError(f"Invalid row in {collection_name} collection: {path}")
            data_name = row.get("dataName")
            missing = required_fields - set(row)
            if not isinstance(data_name, str) or not data_name or missing:
                raise LocationCatalogError(
                    f"Invalid {collection_name} row {data_name!r}; missing {sorted(missing)} in: {path}"
                )
            if data_name in templates:
                raise LocationCatalogError(f"Duplicate {collection_name} dataName {data_name!r} in: {path}")
            templates[data_name] = dict(row)
        return templates

    space_body_templates = index_rows("spaceBodies", {"dataName", "objectType"})
    navigable_templates = index_rows(
        "navigables",
        {"dataName", "locationKind", "lagrangeValue", "relatedObject", "orbits", "maxHabSize"},
    )
    orbit_templates = index_rows("orbits", {"dataName", "irradiatedMultiplier"})
    collisions = sorted(set(space_body_templates) & set(navigable_templates))
    if collisions:
        raise LocationCatalogError(f"Location catalog body/navigable dataName collisions {collisions}: {path}")
    location_templates = {**space_body_templates, **navigable_templates}
    counts = raw.get("counts")
    expected_counts = {
        "spaceBodies": len(space_body_templates),
        "navigables": len(navigable_templates),
        "orbits": len(orbit_templates),
    }
    if counts != expected_counts:
        raise LocationCatalogError(f"Location catalog counts do not match row collections: {path}")
    for name, body in space_body_templates.items():
        if not isinstance(body.get("objectType"), str) or not isinstance(body.get("atmosphere"), str):
            raise LocationCatalogError(f"Invalid body classification fields for {name!r} in: {path}")
        if not isinstance(body.get("irradiatedMultiplier"), (int, float)) or not isinstance(
            body.get("maxHabSize"), (int, float)
        ):
            raise LocationCatalogError(f"Invalid body calculation fields for {name!r} in: {path}")
    for name, orbit in orbit_templates.items():
        if not isinstance(orbit.get("irradiatedMultiplier"), (int, float)):
            raise LocationCatalogError(f"Invalid orbit calculation fields for {name!r} in: {path}")
    for name, navigable in navigable_templates.items():
        if navigable.get("locationKind") != "LagrangePoint" or navigable.get("lagrangeValue") not in {
            "L1",
            "L2",
            "L3",
            "L4",
            "L5",
        }:
            raise LocationCatalogError(f"Invalid navigable classification fields for {name!r} in: {path}")
        if not isinstance(navigable.get("relatedObject"), str) or not isinstance(navigable.get("orbits"), list):
            raise LocationCatalogError(f"Invalid navigable relation fields for {name!r} in: {path}")
        if not isinstance(navigable.get("maxHabSize"), (int, float)):
            raise LocationCatalogError(f"Invalid navigable maxHabSize for {name!r} in: {path}")
        related_object = str(navigable["relatedObject"])
        if related_object not in space_body_templates:
            raise LocationCatalogError(
                f"Navigable {name!r} references missing related body {related_object!r} in: {path}"
            )
        orbit_names = navigable["orbits"]
        if (
            not orbit_names
            or any(not isinstance(orbit_name, str) or not orbit_name for orbit_name in orbit_names)
            or len(set(orbit_names)) != len(orbit_names)
        ):
            raise LocationCatalogError(f"Navigable {name!r} has invalid orbit references in: {path}")
        missing_orbits = [orbit_name for orbit_name in orbit_names if orbit_name not in orbit_templates]
        if missing_orbits:
            raise LocationCatalogError(f"Navigable {name!r} references missing orbits {missing_orbits} in: {path}")
        mismatched_orbits = [
            orbit_name for orbit_name in orbit_names if orbit_templates[orbit_name].get("barycenterName") != name
        ]
        if mismatched_orbits:
            raise LocationCatalogError(
                f"Navigable {name!r} has orbits with mismatched barycenters {mismatched_orbits} in: {path}"
            )
    expected_indexes = {
        "spaceBodies": {name: index for index, name in enumerate(row["dataName"] for row in raw["spaceBodies"])},
        "navigables": {name: index for index, name in enumerate(row["dataName"] for row in raw["navigables"])},
        "orbits": {name: index for index, name in enumerate(row["dataName"] for row in raw["orbits"])},
    }
    if raw.get("byDataName") != expected_indexes:
        raise LocationCatalogError(f"Location catalog byDataName indexes do not match row order: {path}")
    return LocationCatalog(
        body_templates=space_body_templates,
        navigable_templates=navigable_templates,
        location_templates=location_templates,
        orbit_templates=orbit_templates,
        metadata={
            "schemaVersion": raw["schemaVersion"],
            "source": raw.get("source"),
            "scenarioOverrides": raw["scenarioOverrides"],
        },
    )


def _catalog_module_to_template(module: dict[str, Any]) -> dict[str, Any]:
    """Rehydrate the normalized catalog row into the parser's template shape."""

    result: dict[str, Any] = {
        "dataName": module.get("dataName"),
        "friendlyName": module.get("friendlyName"),
        "tier": module.get("tier", 0),
        "habType": module.get("habType") or "Any",
    }
    for group in ("flags", "requirements", "construction", "operation"):
        values = module.get(group)
        if isinstance(values, dict):
            result.update(values)

    income_fields = {
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
    for resource, value in (module.get("monthlyIncome") or {}).items():
        field = income_fields.get(str(resource))
        if field:
            result[field] = value

    support_fields = {
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
    without_crew = ((module.get("monthlySupport") or {}).get("withoutCrew") or {})
    result["supportMaterials_month"] = {
        field: without_crew[resource]
        for resource, field in support_fields.items()
        if resource in without_crew
    }

    bonuses = module.get("bonuses") if isinstance(module.get("bonuses"), dict) else {}
    result["specialRules"] = list(bonuses.get("specialRules") or [])
    result["specialRulesValue"] = bonuses.get("specialRulesValue", 0)
    tech = bonuses.get("tech") if isinstance(bonuses.get("tech"), dict) else {}
    result["techBonuses"] = [
        {"category": category, "bonus": value}
        for category, value in tech.items()
    ]
    return result


def load_hab_module_catalog(catalog_path: Path = DEFAULT_MODULE_CATALOG) -> dict[str, dict[str, Any]]:
    """Load packaged normalized hab modules; absence or corruption is fatal."""

    resolved = catalog_path.resolve()
    if not resolved.is_file():
        raise ModuleCatalogError(f"Required module catalog not found: {resolved}")
    stat = resolved.stat()
    return _load_hab_module_catalog_cached(str(resolved), stat.st_size, stat.st_mtime_ns)


@lru_cache(maxsize=None)
def _load_hab_module_catalog_cached(path_value: str, size: int, mtime_ns: int) -> dict[str, dict[str, Any]]:
    del size, mtime_ns
    path = Path(path_value)
    with path.open("r", encoding="utf-8-sig") as handle:
        raw = json.load(handle)
    modules = raw.get("modules") if isinstance(raw, dict) else None
    if not isinstance(modules, list) or not modules:
        raise ModuleCatalogError(f"Invalid or empty module catalog: {path}")
    templates: dict[str, dict[str, Any]] = {}
    required_operation_fields = {
        "crew",
        "power",
        "missionControl",
        "controlPointCapacity",
        "constructionTimeModifier",
        "miningModifier",
    }
    for module in modules:
        if not isinstance(module, dict) or not module.get("dataName"):
            raise ModuleCatalogError(f"Invalid module row in catalog: {path}")
        operation = module.get("operation")
        missing_operation_fields = required_operation_fields - set(operation if isinstance(operation, dict) else {})
        if missing_operation_fields:
            raise ModuleCatalogError(
                f"Module {module.get('dataName')} is missing required operation fields "
                f"{sorted(missing_operation_fields)} in catalog: {path}"
            )
        template = _catalog_module_to_template(module)
        templates[str(template["dataName"])] = template
    return templates


def load_named_templates(templates_dir: TemplateSource, filename: str) -> dict[str, dict[str, Any]]:
    paths = [directory / filename for directory in template_directories(templates_dir)]
    paths = [path for path in paths if path.is_file()]
    if not paths:
        return {}
    if len(paths) == 1:
        path = paths[0]
        stat = path.stat()
        return _load_named_templates_cached(str(path.resolve()), stat.st_size, stat.st_mtime_ns)

    merged: dict[str, dict[str, Any]] = {}
    for path in paths:
        stat = path.stat()
        merged.update(_load_named_templates_cached(str(path.resolve()), stat.st_size, stat.st_mtime_ns))
    return merged


@lru_cache(maxsize=None)
def _load_named_templates_cached(path_value: str, size: int, mtime_ns: int) -> dict[str, dict[str, Any]]:
    path = Path(path_value)
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
        needle = name.casefold()
        exact: list[tuple[int, dict[str, Any]]] = []
        partial: list[tuple[int, dict[str, Any]]] = []
        for entry in type_entries(indexed, "TIFactionState"):
            faction = entry.get("Value") or {}
            state_id = raw_state_id(entry)
            if state_id is None or not isinstance(faction, dict):
                continue
            names = raw_name_values(faction)
            if any(value.casefold() == needle for value in names):
                exact.append((state_id, faction))
            elif any(needle in value.casefold() for value in names):
                partial.append((state_id, faction))
        matches = exact or partial
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            labels = ", ".join(str(faction.get("templateName")) for _, faction in matches)
            raise SystemExit(f"Faction override is ambiguous ({name}): {labels}")
        raise SystemExit(f"Faction not found: {name}")

    player_candidates: dict[int, dict[str, Any]] = {}
    for entry in type_entries(indexed, "TIPlayerState"):
        player = entry.get("Value") or {}
        if not isinstance(player, dict) or player.get("isAI") is not False:
            continue
        faction_id = ref_id(player.get("faction"))
        faction = state_value_by_id(indexed, faction_id)
        if faction_id is not None and isinstance(faction, dict):
            player_candidates[faction_id] = faction

    metadata = first_value(indexed, "TIMetadataState") or {}
    player_faction_name = metadata.get("playerFactionName")
    metadata_candidates: dict[int, dict[str, Any]] = {}
    if player_faction_name:
        needle = str(player_faction_name).casefold()
        for entry in type_entries(indexed, "TIFactionState"):
            faction = entry.get("Value") or {}
            state_id = raw_state_id(entry)
            if state_id is None or not isinstance(faction, dict):
                continue
            if any(value.casefold() == needle for value in raw_name_values(faction)):
                metadata_candidates[state_id] = faction

    if len(player_candidates) > 1:
        labels = ", ".join(str(value.get("templateName")) for value in player_candidates.values())
        raise SystemExit(f"Multiple human player factions found in TIPlayerState: {labels}")
    if len(metadata_candidates) > 1:
        labels = ", ".join(str(value.get("templateName")) for value in metadata_candidates.values())
        raise SystemExit(f"Metadata playerFactionName is ambiguous: {labels}")
    if player_candidates and metadata_candidates and player_candidates.keys() != metadata_candidates.keys():
        raise SystemExit("Human player faction metadata conflicts with TIPlayerState.")
    candidates = player_candidates or metadata_candidates
    if len(candidates) == 1:
        return next(iter(candidates.items()))
    if player_faction_name and not metadata_candidates:
        raise SystemExit(f"Metadata player faction could not be resolved: {player_faction_name}")
    raise SystemExit("Human player faction could not be resolved from save metadata/player state.")


def faction_is_human_player(indexed: IndexedState, faction: dict[str, Any]) -> bool:
    """Return whether faction is the uniquely resolved human player faction."""

    player_id, _ = find_faction_state(indexed)
    return player_id == ref_id(faction.get("ID"))


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
    active_effects = effect_contexts.get(context, [])
    if not isinstance(active_effects, list):
        raise CalculationDependencyError(
            CalculationDependency(
                kind="effectContext",
                name=context,
                context=context,
                scenario=None,
                reason="active effect names must be a list",
            )
        )

    result = float(base_value)
    valid_operations = {
        "Additive",
        "Multiplicative",
        "SetToFixedValue",
        "IncreaseToValue",
        "DecreaseToValue",
    }
    for effect_name in active_effects:
        if not isinstance(effect_name, str) or not effect_name:
            raise CalculationDependencyError(
                CalculationDependency(
                    kind="effect",
                    name=str(effect_name),
                    context=context,
                    scenario=None,
                    reason="active effect name must be a non-empty string",
                )
            )
        if effect_name not in effect_templates:
            raise CalculationDependencyError(
                CalculationDependency(
                    kind="effect",
                    name=effect_name,
                    context=context,
                    scenario=None,
                    reason="referenced effect is missing from the effect catalog",
                )
            )
        effect = effect_templates[effect_name]
        if not isinstance(effect, dict):
            raise CalculationDependencyError(
                CalculationDependency(
                    kind="effect",
                    name=effect_name,
                    context=context,
                    scenario=None,
                    reason="effect catalog row must be an object",
                )
            )
        operation = effect.get("operation")
        if operation not in valid_operations:
            reason = "operation is missing" if operation is None else f"unsupported operation {operation!r}"
            raise CalculationDependencyError(
                CalculationDependency(
                    kind="effect",
                    name=effect_name,
                    context=context,
                    scenario=None,
                    reason=reason,
                )
            )
        if "value" not in effect:
            raise CalculationDependencyError(
                CalculationDependency(
                    kind="effect",
                    name=effect_name,
                    context=context,
                    scenario=None,
                    reason="value is missing",
                )
            )
        raw_value = effect["value"]
        value = as_float(raw_value, math.nan)
        if isinstance(raw_value, bool) or not math.isfinite(value):
            raise CalculationDependencyError(
                CalculationDependency(
                    kind="effect",
                    name=effect_name,
                    context=context,
                    scenario=None,
                    reason="value must be a finite number",
                )
            )
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
    summary = {
        "id": state_id,
        "type": type_name,
        "template": state.get("templateName"),
        "code": campaign_code(state.get("templateName")),
        "display": state.get("displayName"),
    }
    if "isAI" in state:
        summary["isAI"] = state.get("isAI")
    return summary


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
