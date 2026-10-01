"""Pure save inspection and conservative beta compatibility assessment.

This module deliberately inspects raw indexed save state and packaged file bytes
only.  It must stay usable before any runtime catalog or calculator is loaded.
"""

from __future__ import annotations

from ti_parser_errors import UserInputError
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

from ti_parser_core import (
    DEFAULT_RUNTIME_CATALOG_DIR,
    IndexedState,
    campaign_code,
    first_value,
    ref_id,
    scenario_template_name,
    state_value_by_id,
    type_entries,
)


REGISTRY_FILENAME = "compatibility_registry.json"
REGISTRY_SCHEMA_VERSION = 1
RUNTIME_ASSET_FILENAMES = (
    "catalog_manifest.json",
    "effect_catalog.json",
    "trait_catalog.json",
    "org_catalog.json",
    "ship_catalog.json",
    "nation_claim_catalog.json",
    "nation_development_catalog.json",
    "research_catalog.json",
    "module_catalog.json",
    "location_catalog.json",
)
MOD_FLAG_FIELDS = ("playedWithMods", "moddingActive", "moddingUsedAnytime")


class CompatibilityRegistryError(UserInputError):
    """A compatibility registry cannot be trusted safely."""

    def __init__(self, code: str, message: str, *, details: dict[str, Any] | None = None) -> None:
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(message, code=code)

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "details": self.details}


def _is_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _registry_path(data_dir: Path) -> Path:
    return data_dir / REGISTRY_FILENAME


def _read_registry(data_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    path = _registry_path(data_dir)
    try:
        content = path.read_bytes()
    except OSError as exc:
        raise CompatibilityRegistryError(
            "compatibility-registry-unreadable",
            f"Unable to read compatibility registry: {path}",
            details={"path": str(path), "error": type(exc).__name__},
        ) from exc
    try:
        registry = json.loads(content.decode("utf-8-sig"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise CompatibilityRegistryError(
            "compatibility-registry-invalid-json",
            f"Compatibility registry is not valid JSON: {path}",
            details={"path": str(path), "error": str(exc)},
        ) from exc
    if not isinstance(registry, dict) or registry.get("schemaVersion") != REGISTRY_SCHEMA_VERSION:
        raise CompatibilityRegistryError(
            "compatibility-registry-schema",
            f"Unsupported compatibility registry schema: {path}",
            details={"path": str(path), "expectedSchemaVersion": REGISTRY_SCHEMA_VERSION},
        )
    entries = registry.get("entries")
    if not isinstance(entries, list):
        raise CompatibilityRegistryError(
            "compatibility-registry-entries",
            f"Compatibility registry entries must be an array: {path}",
            details={"path": str(path)},
        )
    seen: set[tuple[str, str, str]] = set()
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict) or set(entry) != {
            "latestSaveVersion",
            "scenario",
            "catalogFingerprint",
            "evidence",
        }:
            raise CompatibilityRegistryError(
                "compatibility-registry-entry",
                f"Invalid compatibility registry entry at index {index}: {path}",
                details={"path": str(path), "entryIndex": index},
            )
        version = entry["latestSaveVersion"]
        scenario = entry["scenario"]
        fingerprint = entry["catalogFingerprint"]
        evidence = entry["evidence"]
        if (
            not isinstance(version, str)
            or not version
            or not isinstance(scenario, str)
            or not scenario
            or not _is_sha256(fingerprint)
            or not isinstance(evidence, dict)
            or not evidence
        ):
            raise CompatibilityRegistryError(
                "compatibility-registry-entry",
                f"Invalid compatibility registry entry at index {index}: {path}",
                details={"path": str(path), "entryIndex": index},
            )
        key = (version, scenario, fingerprint)
        if key in seen:
            raise CompatibilityRegistryError(
                "compatibility-registry-duplicate",
                f"Duplicate compatibility registry entry at index {index}: {path}",
                details={"path": str(path), "entryIndex": index},
            )
        seen.add(key)
    return registry, {
        "filename": path.name,
        "schemaVersion": registry["schemaVersion"],
        "sha256": _sha256_bytes(content),
        "entryCount": len(entries),
    }


def _hash_assets(data_dir: Path) -> tuple[str | None, list[dict[str, Any]], list[str]]:
    """Fingerprint all packaged runtime assets without parsing or trusting a manifest."""

    digest = hashlib.sha256()
    assets: list[dict[str, Any]] = []
    missing: list[str] = []
    for filename in RUNTIME_ASSET_FILENAMES:
        path = data_dir / filename
        try:
            content = path.read_bytes()
        except OSError:
            missing.append(filename)
            continue
        sha256 = _sha256_bytes(content)
        assets.append({"name": filename, "sha256": sha256, "size": len(content)})
        digest.update(filename.encode("utf-8"))
        digest.update(b"\0")
        digest.update(content)
        digest.update(b"\0")
    return (digest.hexdigest() if not missing else None), assets, missing


def runtime_bundle_fingerprint(data_dir: str | Path | None = None) -> str:
    """Return the deterministic raw-byte fingerprint of every runtime data asset."""

    root = Path(data_dir) if data_dir is not None else DEFAULT_RUNTIME_CATALOG_DIR
    fingerprint, _assets, missing = _hash_assets(root)
    if missing:
        raise CompatibilityRegistryError(
            "runtime-assets-missing",
            "One or more packaged runtime assets are missing.",
            details={"dataDir": str(root.resolve()), "missing": missing},
        )
    assert fingerprint is not None
    return fingerprint


def _state_field_evidence(
    indexed: IndexedState, state_types: Iterable[str], field: str
) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    for state_type in state_types:
        for entry in type_entries(indexed, state_type):
            state = entry.get("Value")
            if isinstance(state, dict) and field in state:
                evidence.append(
                    {"stateType": state_type, "stateId": ref_id(entry.get("Key")), "value": state[field]}
                )
    return evidence


def _single_value(evidence: list[dict[str, Any]], expected_type: type) -> tuple[Any, str | None]:
    if not evidence:
        return None, "missing"
    values = [item["value"] for item in evidence]
    if any(type(value) is not expected_type for value in values):
        return None, "invalid"
    first = values[0]
    if any(value != first for value in values[1:]):
        return None, "conflicting"
    return first, None


def _faction_candidates(indexed: IndexedState) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for entry in type_entries(indexed, "TIPlayerState"):
        player = entry.get("Value")
        if not isinstance(player, dict) or player.get("isAI") is not False:
            continue
        faction_id = ref_id(player.get("faction"))
        faction = state_value_by_id(indexed, faction_id)
        candidates.append(
            {
                "source": "TIPlayerState.isAI=false",
                "playerStateId": ref_id(entry.get("Key")),
                "factionId": faction_id,
                "templateName": faction.get("templateName") if faction else None,
                "code": campaign_code(faction.get("templateName")) if faction else None,
                "displayName": faction.get("displayName") if faction else None,
            }
        )
    for entry in type_entries(indexed, "TIMetadataState"):
        metadata = entry.get("Value")
        if isinstance(metadata, dict) and "playerFactionName" in metadata:
            candidates.append(
                {
                    "source": "TIMetadataState.playerFactionName",
                    "metadataStateId": ref_id(entry.get("Key")),
                    "name": metadata.get("playerFactionName"),
                }
            )
    return candidates


def _raw_facts(indexed: IndexedState) -> dict[str, Any]:
    time_state = first_value(indexed, "TITimeState") or {}
    scenario_evidence = _state_field_evidence(indexed, ("TITimeState",), "scenarioMetaTemplateName")
    scenario, _scenario_problem = _single_value(scenario_evidence, str)
    version_evidence = _state_field_evidence(indexed, ("TIGlobalValuesState",), "latestSaveVersion")
    version, _version_problem = _single_value(version_evidence, str)
    flags: dict[str, Any] = {}
    for field in MOD_FLAG_FIELDS:
        evidence = _state_field_evidence(indexed, ("TIMetadataState", "TIGlobalValuesState"), field)
        value, _problem = _single_value(evidence, bool)
        flags[field] = value
    return {
        "date": time_state.get("currentDateTime"),
        "factionCandidates": _faction_candidates(indexed),
        "scenario": scenario,
        "latestSaveVersion": version,
        "modFlags": flags,
    }


def save_identity(indexed: IndexedState) -> dict[str, Any]:
    """Versioned canonical JSON content identity; independent of gzip/path/mtime."""
    from ti_parser_core import find_faction_state
    from ti_parser_errors import EntityLookupError
    facts = _raw_facts(indexed)
    global_state = first_value(indexed, "TIGlobalValuesState") or {}
    encoded = json.dumps(indexed.data, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    try:
        sid, faction = find_faction_state(indexed)
        player = {"status": "resolved", "id": sid, "template": faction.get("templateName"), "display": faction.get("displayName")}
    except EntityLookupError as exc:
        player = {"status": "unresolved", "error": exc.to_dict()}
    return {
        "schemaVersion": 1,
        "fingerprint": {"algorithm": "sha256-canonical-save-json-v1", "value": hashlib.sha256(encoded).hexdigest()},
        "gameDate": facts["date"], "scenario": facts["scenario"],
        "latestSaveVersion": facts["latestSaveVersion"],
        "campaignStartVersion": global_state.get("campaignStartVersion"),
        "campaign": {"realWorldCampaignStart": global_state.get("realWorldCampaignStart")},
        "playerFaction": player,
    }


def inspect_save(indexed: IndexedState, save_path: str | Path) -> dict[str, Any]:
    """Saved facts only: works even when catalogs/registry are unavailable."""
    return {"schemaVersion": 1, "save": {"filename": Path(save_path).name},
            "saveIdentity": save_identity(indexed), **_raw_facts(indexed)}


def assess_compatibility(
    indexed: IndexedState, data_dir: str | Path | None = None
) -> dict[str, Any]:
    """Assess an exact save/runtime tuple, failing closed on every uncertainty."""

    root = Path(data_dir) if data_dir is not None else DEFAULT_RUNTIME_CATALOG_DIR
    registry, registry_metadata = _read_registry(root)
    catalog_fingerprint, assets, missing_assets = _hash_assets(root)
    reasons: list[dict[str, Any]] = []

    version_evidence = _state_field_evidence(indexed, ("TIGlobalValuesState",), "latestSaveVersion")
    version, version_problem = _single_value(version_evidence, str)
    if version_problem:
        reasons.append({"code": f"latest-save-version-{version_problem}", "field": "latestSaveVersion"})

    scenario_evidence = _state_field_evidence(indexed, ("TITimeState",), "scenarioMetaTemplateName")
    scenario, scenario_problem = _single_value(scenario_evidence, str)
    if scenario_problem:
        reasons.append({"code": f"scenario-{scenario_problem}", "field": "scenarioMetaTemplateName"})

    mod_evidence: dict[str, Any] = {}
    for field in MOD_FLAG_FIELDS:
        evidence = _state_field_evidence(indexed, ("TIMetadataState", "TIGlobalValuesState"), field)
        value, problem = _single_value(evidence, bool)
        mod_evidence[field] = {"value": value, "observations": evidence}
        if problem:
            reasons.append({"code": f"mod-flag-{problem}", "field": field})
        elif value is True:
            reasons.append({"code": "mod-history-present", "field": field})

    if missing_assets:
        reasons.append({"code": "runtime-assets-missing", "assets": missing_assets})

    match = None
    if version is not None and scenario is not None and catalog_fingerprint is not None:
        match = next(
            (
                entry
                for entry in registry["entries"]
                if entry["latestSaveVersion"] == version
                and entry["scenario"] == scenario
                and entry["catalogFingerprint"] == catalog_fingerprint
            ),
            None,
        )
        if match is None:
            reasons.append({"code": "unsupported-exact-runtime-tuple"})

    status = "verified" if not reasons and match is not None else "unverified"
    return {
        "schemaVersion": 1,
        "status": status,
        "reasons": reasons,
        "version": {"latestSaveVersion": version, "observations": version_evidence},
        "scenario": {"name": scenario, "observations": scenario_evidence},
        "modEvidence": mod_evidence,
        "catalogFingerprint": catalog_fingerprint,
        "runtimeAssets": assets,
        "registry": {**registry_metadata, "matchedEvidence": match["evidence"] if match else None},
    }

