"""Strict loader and dependency errors for packaged runtime catalogs.

Runtime calculations should import this module instead of discovering a local
Terra Invicta installation.  Raw templates are an input to the generator only.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from ti_parser_core import CalculationDependency, CalculationDependencyError


CATALOG_MANIFEST = "catalog_manifest.json"
DEFAULT_CATALOG_FILES = (
    "effect_catalog.json",
    "trait_catalog.json",
    "org_catalog.json",
    "ship_catalog.json",
    "nation_claim_catalog.json",
)
ENVELOPE_FIELDS = {
    "schemaVersion",
    "generator",
    "sourceFiles",
    "supportedScenarios",
    "base",
    "scenarioOverrides",
    "payloadFingerprint",
}


class CatalogError(RuntimeError):
    """Base class for packaged catalog loading failures."""


class CatalogIntegrityError(CatalogError):
    """A packaged catalog is absent, corrupt, or incompatible."""


class UnsupportedCatalogScenarioError(CatalogError):
    """The save names a canonical scenario unsupported by the catalog."""

    def __init__(self, scenario: str, supported_scenarios: Iterable[str]) -> None:
        self.scenario = scenario
        self.supported_scenarios = tuple(supported_scenarios)
        super().__init__(
            f"Unsupported scenario {scenario!r}; supported scenarios: {list(self.supported_scenarios)}"
        )


def canonical_json_bytes(value: Any) -> bytes:
    """Return the stable JSON representation used by all catalog hashes."""

    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def value_fingerprint(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def envelope_payload(envelope: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "base": envelope.get("base"),
        "scenarioOverrides": envelope.get("scenarioOverrides"),
    }


def validate_catalog_envelope(
    envelope: Any,
    *,
    path: Path | None = None,
) -> dict[str, Any]:
    location = f" in {path}" if path else ""
    if not isinstance(envelope, dict):
        raise CatalogIntegrityError(f"Catalog envelope must be an object{location}")
    missing = ENVELOPE_FIELDS - set(envelope)
    if missing:
        raise CatalogIntegrityError(f"Catalog envelope is missing {sorted(missing)}{location}")
    if not isinstance(envelope["schemaVersion"], int) or envelope["schemaVersion"] < 1:
        raise CatalogIntegrityError(f"Invalid schemaVersion{location}")
    generator = envelope["generator"]
    if (
        not isinstance(generator, dict)
        or not isinstance(generator.get("name"), str)
        or not generator.get("name")
        or not isinstance(generator.get("version"), str)
        or not generator.get("version")
    ):
        raise CatalogIntegrityError(f"Invalid generator metadata{location}")
    source_files = envelope["sourceFiles"]
    if not isinstance(source_files, list):
        raise CatalogIntegrityError(f"sourceFiles must be an array{location}")
    source_names: set[str] = set()
    for source in source_files:
        if not isinstance(source, dict) or set(source) != {"name", "sha256"}:
            raise CatalogIntegrityError(f"Invalid sourceFiles entry{location}")
        name = source.get("name")
        sha256 = source.get("sha256")
        if not isinstance(name, str) or not name or name in source_names:
            raise CatalogIntegrityError(f"Invalid or duplicate source file name {name!r}{location}")
        if not _is_sha256(sha256):
            raise CatalogIntegrityError(f"Invalid source file sha256 for {name!r}{location}")
        source_names.add(name)
    scenarios = envelope["supportedScenarios"]
    if (
        not isinstance(scenarios, list)
        or not scenarios
        or any(not isinstance(item, str) or not item for item in scenarios)
        or len(set(scenarios)) != len(scenarios)
    ):
        raise CatalogIntegrityError(f"supportedScenarios must contain unique scenario names{location}")
    if not isinstance(envelope["base"], dict):
        raise CatalogIntegrityError(f"base must be an object{location}")
    overrides = envelope["scenarioOverrides"]
    if not isinstance(overrides, dict):
        raise CatalogIntegrityError(f"scenarioOverrides must be an object{location}")
    unsupported_overrides = sorted(set(overrides) - set(scenarios))
    if unsupported_overrides:
        raise CatalogIntegrityError(
            f"Scenario overrides are not declared as supported: {unsupported_overrides}{location}"
        )
    if any(not isinstance(value, dict) for value in overrides.values()):
        raise CatalogIntegrityError(f"Every scenario override must be an object{location}")
    expected = value_fingerprint(envelope_payload(envelope))
    if envelope["payloadFingerprint"] != expected:
        raise CatalogIntegrityError(f"Catalog payload fingerprint mismatch{location}")
    return envelope


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(char in "0123456789abcdef" for char in value)


def _merge_overlay(base: Any, overlay: Any) -> Any:
    if not isinstance(base, dict) or not isinstance(overlay, dict):
        return deepcopy(overlay)
    result = deepcopy(base)
    for key, value in overlay.items():
        result[key] = _merge_overlay(result[key], value) if key in result else deepcopy(value)
    return result


def select_catalog_scenario(envelope: Mapping[str, Any], scenario: str) -> dict[str, Any]:
    scenarios = envelope.get("supportedScenarios")
    if not isinstance(scenario, str) or not scenario:
        raise CatalogIntegrityError("A canonical scenario name is required")
    if not isinstance(scenarios, list) or scenario not in scenarios:
        raise UnsupportedCatalogScenarioError(scenario, scenarios or [])
    base = envelope.get("base")
    override = (envelope.get("scenarioOverrides") or {}).get(scenario, {})
    return _merge_overlay(base, override)


class RuntimeCatalogs:
    """Validated, scenario-selected packaged calculation data."""

    def __init__(
        self,
        *,
        scenario: str,
        catalogs: Mapping[str, dict[str, Any]],
        envelopes: Mapping[str, dict[str, Any]],
        manifest: Mapping[str, Any],
        data_dir: Path,
    ) -> None:
        self.scenario = scenario
        self.catalogs = dict(catalogs)
        self.envelopes = dict(envelopes)
        self.manifest = dict(manifest)
        self.data_dir = data_dir

    @classmethod
    def load(
        cls,
        scenario: str,
        data_dir: str | Path | None = None,
        *,
        catalog_files: Iterable[str] | None = None,
    ) -> "RuntimeCatalogs":
        root = Path(data_dir) if data_dir is not None else Path(__file__).resolve().parents[1] / "data"
        manifest_path = root / CATALOG_MANIFEST
        manifest = _load_json(manifest_path, "catalog manifest")
        entries = _validate_manifest(manifest, manifest_path)
        requested = tuple(catalog_files or DEFAULT_CATALOG_FILES)
        missing_entries = sorted(set(requested) - set(entries))
        if missing_entries:
            raise CatalogIntegrityError(
                f"Catalog manifest is missing required entries {missing_entries}: {manifest_path}"
            )

        selected: dict[str, dict[str, Any]] = {}
        envelopes: dict[str, dict[str, Any]] = {}
        for filename in requested:
            path = root / filename
            if not path.is_file():
                raise CatalogIntegrityError(f"Packaged catalog is missing: {path}")
            entry = entries[filename]
            actual_sha = file_sha256(path)
            if actual_sha != entry["sha256"]:
                raise CatalogIntegrityError(f"Catalog file sha256 mismatch: {path}")
            envelope = validate_catalog_envelope(_load_json(path, "catalog"), path=path)
            if envelope["schemaVersion"] != entry["schemaVersion"]:
                raise CatalogIntegrityError(f"Catalog schemaVersion disagrees with manifest: {path}")
            if envelope["payloadFingerprint"] != entry["payloadFingerprint"]:
                raise CatalogIntegrityError(f"Catalog payload fingerprint disagrees with manifest: {path}")
            key = filename.removesuffix("_catalog.json")
            selected[key] = select_catalog_scenario(envelope, scenario)
            envelopes[key] = envelope
        return cls(
            scenario=scenario,
            catalogs=selected,
            envelopes=envelopes,
            manifest=manifest,
            data_dir=root,
        )

    @classmethod
    def from_directory(
        cls,
        data_dir: str | Path,
        scenario: str,
        *,
        catalog_files: Iterable[str] | None = None,
    ) -> "RuntimeCatalogs":
        return cls.load(scenario, data_dir, catalog_files=catalog_files)

    @property
    def effects(self) -> dict[str, dict[str, Any]]:
        return self._rows("effect", "effects")

    @property
    def effect_templates(self) -> dict[str, dict[str, Any]]:
        return self.effects

    @property
    def traits(self) -> dict[str, dict[str, Any]]:
        return self._rows("trait", "traits")

    @property
    def trait_templates(self) -> dict[str, dict[str, Any]]:
        return self.traits

    @property
    def orgs(self) -> dict[str, dict[str, Any]]:
        return self._rows("org", "orgs")

    @property
    def org_templates(self) -> dict[str, dict[str, Any]]:
        return self.orgs

    @property
    def research(self) -> dict[str, dict[str, Any]]:
        value = self.catalogs.get("research")
        if not isinstance(value, dict):
            raise CatalogIntegrityError("Loaded catalog bundle has no research payload")
        return value

    @property
    def ships(self) -> dict[str, dict[str, Any]]:
        value = self.catalogs.get("ship")
        if not isinstance(value, dict):
            raise CatalogIntegrityError("Loaded catalog bundle has no ship payload")
        return value

    @property
    def ship_templates(self) -> dict[str, dict[str, Any]]:
        return self.ships

    @property
    def ship_simulation_catalogs(self) -> dict[str, dict[str, dict[str, Any]]]:
        ships = self.ships
        utilities = {
            **self._ship_rows("utilities"),
            **self._ship_rows("batteries"),
            **self._ship_rows("heatSinks"),
        }
        return {
            "hulls": self._ship_rows("hulls"),
            "drives": self._ship_rows("drives"),
            "powerPlants": self._ship_rows("powerPlants"),
            "radiators": self._ship_rows("radiators"),
            "armors": self._ship_rows("armors"),
            "utilities": utilities,
            "weapons": self._ship_rows("weapons"),
            "effects": self.effects,
        }

    @property
    def nation_claims(self) -> dict[str, Any]:
        value = self.catalogs.get("nation_claim")
        if not isinstance(value, dict):
            raise CatalogIntegrityError("Loaded catalog bundle has no nation-claim payload")
        return value

    @property
    def nation_claim_catalog(self) -> dict[str, Any]:
        return self.nation_claims

    def _ship_rows(self, collection: str) -> dict[str, dict[str, Any]]:
        rows = self.ships.get(collection)
        if not isinstance(rows, dict):
            raise CatalogIntegrityError(f"Loaded ship catalog has no {collection} collection")
        return rows

    def _rows(self, catalog: str, collection: str) -> dict[str, dict[str, Any]]:
        payload = self.catalogs.get(catalog)
        rows = payload.get(collection) if isinstance(payload, dict) else None
        if not isinstance(rows, dict):
            raise CatalogIntegrityError(f"Loaded {catalog} catalog has no {collection} collection")
        return rows

    def require(
        self,
        kind: str,
        name: str,
        *,
        context: str | None = None,
        reason: str = "missing catalog row",
    ) -> dict[str, Any]:
        aliases = {
            "effect": self.effects,
            "trait": self.traits,
            "org": self.orgs,
        }
        rows = aliases.get(kind)
        if rows is None:
            collection = self.ships.get(kind)
            rows = collection if isinstance(collection, dict) else None
        row = rows.get(name) if isinstance(rows, dict) else None
        if not isinstance(row, dict):
            raise CalculationDependencyError(
                CalculationDependency(
                    kind=kind,
                    name=name,
                    context=context,
                    scenario=self.scenario,
                    reason=reason,
                )
            )
        return row

    def calculation_diagnostics(self) -> dict[str, Any]:
        return {
            "scenario": self.scenario,
            "catalogBundleFingerprint": self.manifest.get("bundleFingerprint"),
            "catalogs": {
                name: {
                    "schemaVersion": envelope["schemaVersion"],
                    "payloadFingerprint": envelope["payloadFingerprint"],
                    "overrideApplied": self.scenario in envelope["scenarioOverrides"],
                }
                for name, envelope in sorted(self.envelopes.items())
            },
        }


def load_runtime_catalogs(
    scenario: str,
    data_dir: str | Path | None = None,
    *,
    catalog_files: Iterable[str] | None = None,
) -> RuntimeCatalogs:
    return RuntimeCatalogs.load(scenario, data_dir, catalog_files=catalog_files)


def _load_json(path: Path, label: str) -> Any:
    if not path.is_file():
        raise CatalogIntegrityError(f"Packaged {label} is missing: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CatalogIntegrityError(f"Unable to read {label}: {path}: {exc}") from exc


def _validate_manifest(manifest: Any, path: Path) -> dict[str, dict[str, Any]]:
    if not isinstance(manifest, dict) or manifest.get("schemaVersion") != 1:
        raise CatalogIntegrityError(f"Unsupported catalog manifest schema: {path}")
    generator = manifest.get("generator")
    if not isinstance(generator, dict) or not generator.get("name") or not generator.get("version"):
        raise CatalogIntegrityError(f"Invalid catalog manifest generator metadata: {path}")
    entries = manifest.get("catalogs")
    if not isinstance(entries, dict) or not entries:
        raise CatalogIntegrityError(f"Catalog manifest has no catalog entries: {path}")
    for filename, entry in entries.items():
        if (
            not isinstance(filename, str)
            or Path(filename).name != filename
            or not filename.endswith("_catalog.json")
            or not isinstance(entry, dict)
            or not _is_sha256(entry.get("sha256"))
            or not isinstance(entry.get("schemaVersion"), int)
            or not _is_sha256(entry.get("payloadFingerprint"))
        ):
            raise CatalogIntegrityError(f"Invalid catalog manifest entry {filename!r}: {path}")
    expected_bundle = value_fingerprint(entries)
    if manifest.get("bundleFingerprint") != expected_bundle:
        raise CatalogIntegrityError(f"Catalog manifest bundle fingerprint mismatch: {path}")
    return entries
