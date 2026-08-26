"""Explicit raw-reference verification for packaged TI parser catalogs.

This module is development tooling, not a normal parser runtime dependency.  It
requires a caller-supplied StreamingAssets/Templates directory, rebuilds the
normalized reference payloads in a temporary directory, and compares them with
the packaged catalogs selected for the requested scenario.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
import tempfile
from typing import Any, Mapping

from ti_parser_catalogs import (
    CATALOG_MANIFEST,
    DEFAULT_CATALOG_FILES,
    CatalogError,
    RuntimeCatalogs,
    validate_catalog_envelope,
)


REL_TOL = 1e-9
ABS_TOL = 1e-6
MAX_MISMATCHES = 50
CORE_CATALOGS = {
    "effect": "effect_catalog.json",
    "trait": "trait_catalog.json",
    "org": "org_catalog.json",
    "ship": "ship_catalog.json",
    "nation_development": "nation_development_catalog.json",
}


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CatalogError(f"Unable to read verification input {path}: {exc}") from exc


def _requested_manifest_files(data_dir: Path, *, require_runtime_defaults: bool = True) -> tuple[str, ...]:
    manifest = _load_json(data_dir / CATALOG_MANIFEST)
    entries = manifest.get("catalogs") if isinstance(manifest, dict) else None
    discovered = set(entries) if isinstance(entries, dict) else set()
    if require_runtime_defaults:
        discovered.update(DEFAULT_CATALOG_FILES)
    return tuple(sorted(discovered))


def _display(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, Mapping):
        return {"type": "object", "keys": len(value)}
    if isinstance(value, list):
        return {"type": "array", "length": len(value)}
    return repr(value)


def _compare_values(
    packaged: Any,
    raw: Any,
    *,
    path: str = "$",
    mismatches: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Recursively compare normalized values using the verification tolerance."""

    result = mismatches if mismatches is not None else []
    if len(result) >= MAX_MISMATCHES:
        return result

    packaged_number = isinstance(packaged, (int, float)) and not isinstance(packaged, bool)
    raw_number = isinstance(raw, (int, float)) and not isinstance(raw, bool)
    if packaged_number and raw_number:
        if not math.isclose(float(packaged), float(raw), rel_tol=REL_TOL, abs_tol=ABS_TOL):
            result.append({"path": path, "packaged": packaged, "raw": raw, "reason": "numeric mismatch"})
        return result

    if isinstance(packaged, Mapping) and isinstance(raw, Mapping):
        packaged_keys = set(packaged)
        raw_keys = set(raw)
        for key in sorted(packaged_keys - raw_keys, key=str):
            if len(result) >= MAX_MISMATCHES:
                return result
            result.append(
                {
                    "path": f"{path}.{key}",
                    "packaged": _display(packaged[key]),
                    "raw": None,
                    "reason": "missing from raw reference",
                }
            )
        for key in sorted(raw_keys - packaged_keys, key=str):
            if len(result) >= MAX_MISMATCHES:
                return result
            result.append(
                {
                    "path": f"{path}.{key}",
                    "packaged": None,
                    "raw": _display(raw[key]),
                    "reason": "missing from packaged payload",
                }
            )
        for key in sorted(packaged_keys & raw_keys, key=str):
            _compare_values(packaged[key], raw[key], path=f"{path}.{key}", mismatches=result)
            if len(result) >= MAX_MISMATCHES:
                return result
        return result

    if isinstance(packaged, list) and isinstance(raw, list):
        if len(packaged) != len(raw):
            result.append(
                {
                    "path": path,
                    "packaged": {"length": len(packaged)},
                    "raw": {"length": len(raw)},
                    "reason": "array length mismatch",
                }
            )
        for index, (packaged_item, raw_item) in enumerate(zip(packaged, raw)):
            _compare_values(packaged_item, raw_item, path=f"{path}[{index}]", mismatches=result)
            if len(result) >= MAX_MISMATCHES:
                return result
        return result

    if packaged != raw:
        result.append(
            {
                "path": path,
                "packaged": _display(packaged),
                "raw": _display(raw),
                "reason": "value mismatch",
            }
        )
    return result


def _source_hash_report(
    packaged_envelope: Mapping[str, Any],
    raw_envelope: Mapping[str, Any],
) -> dict[str, Any]:
    def source_map(envelope: Mapping[str, Any]) -> dict[str, str]:
        sources = envelope.get("sourceFiles")
        if not isinstance(sources, list):
            return {}
        return {
            str(row["name"]): str(row["sha256"])
            for row in sources
            if isinstance(row, Mapping) and row.get("name") is not None and row.get("sha256") is not None
        }

    packaged = source_map(packaged_envelope)
    raw = source_map(raw_envelope)
    common = set(packaged) & set(raw)
    mismatched = [
        {"name": name, "packaged": packaged[name], "raw": raw[name]}
        for name in sorted(common)
        if packaged[name] != raw[name]
    ]
    return {
        "match": packaged == raw,
        "packaged": dict(sorted(packaged.items())),
        "raw": dict(sorted(raw.items())),
        "missingInPackaged": sorted(set(raw) - set(packaged)),
        "unexpectedInPackaged": sorted(set(packaged) - set(raw)),
        "mismatched": mismatched,
    }


def _row_count(domain: str, payload: Mapping[str, Any]) -> int:
    if domain == "effect":
        rows = payload.get("effects")
        return len(rows) if isinstance(rows, Mapping) else 0
    if domain == "trait":
        rows = payload.get("traits")
        return len(rows) if isinstance(rows, Mapping) else 0
    if domain == "org":
        rows = payload.get("orgs")
        return len(rows) if isinstance(rows, Mapping) else 0
    if domain == "ship":
        return sum(
            len(rows)
            for name, rows in payload.items()
            if name != "weapons" and isinstance(rows, Mapping)
        )
    if domain == "research":
        return sum(len(payload.get(name) or {}) for name in ("techs", "projects"))
    return 0


def _comparison_check(
    domain: str,
    scenario: str,
    packaged_payload: Mapping[str, Any],
    raw_payload: Mapping[str, Any],
    packaged_envelope: Mapping[str, Any],
    raw_envelope: Mapping[str, Any],
) -> dict[str, Any]:
    mismatches = _compare_values(packaged_payload, raw_payload)
    hashes = _source_hash_report(packaged_envelope, raw_envelope)
    packaged_overrides = packaged_envelope.get("scenarioOverrides")
    raw_overrides = raw_envelope.get("scenarioOverrides")
    packaged_override = isinstance(packaged_overrides, Mapping) and scenario in packaged_overrides
    raw_override = isinstance(raw_overrides, Mapping) and scenario in raw_overrides
    override_match = packaged_override == raw_override
    passed = not mismatches and hashes["match"] and override_match
    return {
        "name": f"{domain}-catalog-parity",
        "domain": domain,
        "status": "passed" if passed else "failed",
        "rowsCompared": _row_count(domain, raw_payload),
        "selectedScenario": scenario,
        "scenarioOverrideApplied": packaged_override,
        "rawScenarioOverrideApplied": raw_override,
        "scenarioOverrideMatch": override_match,
        "payloadMatch": not mismatches,
        "mismatches": mismatches,
        "mismatchesTruncated": len(mismatches) >= MAX_MISMATCHES,
        "sourceHashes": hashes,
    }


def _unavailable_calculation_checks() -> list[dict[str, Any]]:
    reasons = {
        "mercury-solar": "requires a save/indexed Mercury location and the location/module calculation path",
        "control-point-cap": "requires a save/indexed faction, nations, control points, and active effects",
        "mission-control": "requires a save/indexed faction, habs, nations, and active effects",
        "research-calculation": "requires a save/indexed research state and active-effect state",
        "org-eligibility": "requires a save/indexed faction and councilor eligibility context",
        "saved-design-simulation": "requires a save/indexed ship design and component assignments",
    }
    return [
        {
            "name": name,
            "domain": "calculation",
            "status": "unavailable",
            "reason": reason,
            "requiredInput": "save/indexed state is not part of verify_catalogs(templates_dir, scenario, data_dir)",
        }
        for name, reason in reasons.items()
    ]


def _parity_check(name: str, packaged: Any, raw: Any, **details: Any) -> dict[str, Any]:
    mismatches = _compare_values(packaged, raw)
    return {
        "name": name,
        "domain": "calculation",
        "status": "passed" if not mismatches else "failed",
        "mismatches": mismatches,
        **details,
    }


def _save_calculation_checks(
    templates_dir: Path,
    save_path: Path,
    scenario: str,
    packaged_runtime: RuntimeCatalogs,
    raw_runtime: RuntimeCatalogs,
) -> list[dict[str, Any]]:
    """Run save-backed raw/package parity checks without using raw data at runtime."""

    import build_location_catalog as location_builder
    import ti_parser_org as org_layer
    import ti_save_parser as parser

    data = parser.load_save(save_path)
    indexed = parser.build_index(data)
    save_scenario = parser.scenario_template_name(indexed)
    if save_scenario != scenario:
        return [
            {
                "name": name,
                "domain": "calculation",
                "status": "unavailable",
                "reason": f"save scenario {save_scenario!r} does not match requested scenario {scenario!r}",
            }
            for name in (
                "mercury-solar",
                "control-point-cap",
                "mission-control",
                "research-calculation",
                "org-eligibility",
                "saved-design-simulation",
            )
        ]

    research = packaged_runtime.research

    def research_templates(runtime: RuntimeCatalogs) -> Any:
        return parser.ResearchTemplates(
            traits=runtime.traits,
            effects=runtime.effects,
            orgs=runtime.orgs,
            hab_modules=parser.load_hab_module_catalog(),
            utility_modules=runtime.ships["utilities"],
            techs=research["techs"],
            projects=research["projects"],
        )

    checks: list[dict[str, Any]] = []
    packaged_topbar = parser.calculate_topbar(
        indexed,
        None,
        research_templates=research_templates(packaged_runtime),
    )
    raw_topbar = parser.calculate_topbar(
        indexed,
        None,
        research_templates=research_templates(raw_runtime),
    )
    checks.append(
        _parity_check(
            "control-point-cap",
            packaged_topbar.get("controlPointMaintenance"),
            raw_topbar.get("controlPointMaintenance"),
        )
    )
    checks.append(
        _parity_check(
            "mission-control",
            (packaged_topbar.get("resources") or {}).get("MissionControl"),
            (raw_topbar.get("resources") or {}).get("MissionControl"),
        )
    )
    checks.append(
        _parity_check(
            "research-calculation",
            (packaged_topbar.get("resources") or {}).get("Research"),
            (raw_topbar.get("resources") or {}).get("Research"),
        )
    )

    packaged_org = org_layer.calculate_org_plan(
        indexed,
        None,
        max_actions=0,
        beam_width=1,
        include_all_candidates=False,
        runtime_catalogs=packaged_runtime,
    )
    raw_org = org_layer.calculate_org_plan(
        indexed,
        None,
        max_actions=0,
        beam_width=1,
        include_all_candidates=False,
        runtime_catalogs=raw_runtime,
    )
    checks.append(
        _parity_check(
            "org-eligibility",
            packaged_org.get("candidateSources"),
            raw_org.get("candidateSources"),
        )
    )

    raw_location = location_builder.build_catalog(templates_dir)
    raw_bodies = {
        str(row["dataName"]): row
        for row in raw_location.get("spaceBodies", [])
        if isinstance(row, Mapping) and row.get("dataName")
    }
    raw_orbits = {
        str(row["dataName"]): row
        for row in raw_location.get("orbits", [])
        if isinstance(row, Mapping) and row.get("dataName")
    }
    packaged_location = parser.load_location_catalog()
    mercury_hab = None
    for entry in parser.type_entries(indexed, "TIHabState"):
        hab = entry.get("Value") or {}
        barycenter = parser.hab_barycenter_state(indexed, hab)
        if "Mercury" in str(barycenter.get("templateName") or ""):
            mercury_hab = hab
            break
    if mercury_hab is None:
        mercury_body_id = next(
            (
                parser.raw_state_id(entry)
                for entry in parser.type_entries(indexed, "TISpaceBodyState")
                if (entry.get("Value") or {}).get("templateName") == "Mercury"
            ),
            None,
        )
        mercury_orbit_id = next(
            (
                parser.raw_state_id(entry)
                for entry in parser.type_entries(indexed, "TIOrbitState")
                if parser.ref_id((entry.get("Value") or {}).get("barycenter")) == mercury_body_id
            ),
            None,
        )
        if mercury_body_id is not None and mercury_orbit_id is not None:
            mercury_hab = {
                "displayName": "catalog-verify Mercury orbital sample",
                "habType": "Platform",
                "barycenter": {"value": mercury_body_id},
                "orbitState": {"value": mercury_orbit_id},
            }
    if mercury_hab is None:
        checks.append(
            {
                "name": "mercury-solar",
                "domain": "calculation",
                "status": "unavailable",
                "reason": "matching save contains no Mercury hab",
            }
        )
    else:
        packaged_solar = parser.hab_natural_solar_multiplier(
            indexed,
            mercury_hab,
            packaged_location.body_templates,
            packaged_location.orbit_templates,
        )
        raw_solar = parser.hab_natural_solar_multiplier(indexed, mercury_hab, raw_bodies, raw_orbits)
        checks.append(
            _parity_check(
                "mercury-solar",
                packaged_solar,
                raw_solar,
                packagedValue=packaged_solar,
                rawValue=raw_solar,
            )
        )

    design_context = None
    for entry in parser.type_entries(indexed, "TIFactionState"):
        faction = entry.get("Value") or {}
        designs = faction.get("shipDesigns") if isinstance(faction.get("shipDesigns"), list) else []
        if designs:
            design_context = (parser.raw_state_id(entry), faction, designs[0])
            break
    if design_context is None:
        checks.append(
            {
                "name": "saved-design-simulation",
                "domain": "calculation",
                "status": "unavailable",
                "reason": "matching save contains no saved ship design",
            }
        )
    else:
        faction_id, faction, design = design_context
        shipyards = parser.load_hab_module_catalog()
        packaged_ship = parser.simulate_ship_design(
            indexed,
            faction_id,
            faction,
            design,
            {**packaged_runtime.ship_simulation_catalogs, "shipyards": shipyards},
        )
        raw_ship = parser.simulate_ship_design(
            indexed,
            faction_id,
            faction,
            design,
            {**raw_runtime.ship_simulation_catalogs, "shipyards": shipyards},
        )
        checks.append(_parity_check("saved-design-simulation", packaged_ship, raw_ship))
    return checks


def _verify_research(
    templates_dir: Path,
    scenario: str,
    data_dir: Path,
) -> dict[str, Any]:
    research_path = data_dir / "research_catalog.json"
    if not research_path.is_file():
        return {
            "name": "research-catalog-parity",
            "domain": "research",
            "status": "failed",
            "reason": f"packaged research catalog is missing: {research_path}",
        }

    try:
        import build_research_catalog as research_builder

        packaged_envelope = validate_catalog_envelope(_load_json(research_path), path=research_path)
        source = packaged_envelope.get("source")
        languages = source.get("localizationLanguages") if isinstance(source, Mapping) else []
        if not isinstance(languages, list) or any(not isinstance(value, str) for value in languages):
            raise CatalogError("Research catalog localizationLanguages provenance is invalid")
        raw_envelope = research_builder.build_catalog(templates_dir, list(languages))
        raw_envelope = validate_catalog_envelope(raw_envelope)
        packaged_payload = research_builder.select_runtime_payload(packaged_envelope, scenario)
        raw_payload = research_builder.select_runtime_payload(raw_envelope, scenario)
        return _comparison_check(
            "research",
            scenario,
            packaged_payload,
            raw_payload,
            packaged_envelope,
            raw_envelope,
        )
    except Exception as exc:  # verification must report the failed evidence boundary
        return {
            "name": "research-catalog-parity",
            "domain": "research",
            "status": "failed",
            "reason": f"{type(exc).__name__}: {exc}",
        }


def verify_catalogs(
    templates_dir: str | Path,
    scenario: str,
    data_dir: str | Path | None = None,
    save_path: str | Path | None = None,
) -> dict[str, Any]:
    """Compare packaged catalogs with normalized rows rebuilt from raw sources.

    The result never labels calculations as passed when the API lacks their save
    inputs.  Such future extension points are emitted as explicit
    ``unavailable`` checks.
    """

    templates = Path(templates_dir).expanduser().resolve()
    if not templates.is_dir():
        raise FileNotFoundError(f"Templates directory not found: {templates}")
    if not isinstance(scenario, str) or not scenario:
        raise ValueError("A canonical non-empty scenario name is required")
    package_root = (
        Path(data_dir).expanduser().resolve()
        if data_dir is not None
        else Path(__file__).resolve().parents[1] / "data"
    )

    checks: list[dict[str, Any]] = []
    packaged_runtime: RuntimeCatalogs | None = None
    raw_runtime: RuntimeCatalogs | None = None
    try:
        requested = _requested_manifest_files(package_root)
        packaged_runtime = RuntimeCatalogs.load(scenario, package_root, catalog_files=requested)
        checks.append(
            {
                "name": "runtime-manifest",
                "domain": "catalogs",
                "status": "passed",
                "requestedCatalogs": list(requested),
                "diagnostics": packaged_runtime.calculation_diagnostics(),
            }
        )
    except Exception as exc:
        checks.append(
            {
                "name": "runtime-manifest",
                "domain": "catalogs",
                "status": "failed",
                "reason": f"{type(exc).__name__}: {exc}",
            }
        )

    if packaged_runtime is not None:
        try:
            import build_runtime_catalogs as runtime_builder

            with tempfile.TemporaryDirectory(prefix="ti-parser-verify-") as temp_value:
                raw_output = Path(temp_value)
                runtime_builder.build_all(templates, raw_output)
                raw_requested = _requested_manifest_files(raw_output, require_runtime_defaults=False)
                raw_runtime = RuntimeCatalogs.load(scenario, raw_output, catalog_files=raw_requested)
                for domain, filename in CORE_CATALOGS.items():
                    raw_envelope = raw_runtime.envelopes.get(domain)
                    packaged_envelope = packaged_runtime.envelopes.get(domain)
                    raw_payload = raw_runtime.catalogs.get(domain)
                    packaged_payload = packaged_runtime.catalogs.get(domain)
                    if not all(
                        isinstance(value, Mapping)
                        for value in (raw_envelope, packaged_envelope, raw_payload, packaged_payload)
                    ):
                        checks.append(
                            {
                                "name": f"{domain}-catalog-parity",
                                "domain": domain,
                                "status": "failed",
                                "reason": f"required selected payload or envelope is missing for {filename}",
                            }
                        )
                        continue
                    checks.append(
                        _comparison_check(
                            domain,
                            scenario,
                            packaged_payload,
                            raw_payload,
                            packaged_envelope,
                            raw_envelope,
                        )
                    )
        except Exception as exc:
            checks.append(
                {
                    "name": "raw-runtime-generation",
                    "domain": "catalogs",
                    "status": "failed",
                    "reason": f"{type(exc).__name__}: {exc}",
                }
            )
            completed_domains = {check.get("domain") for check in checks}
            for domain in CORE_CATALOGS:
                if domain not in completed_domains:
                    checks.append(
                        {
                            "name": f"{domain}-catalog-parity",
                            "domain": domain,
                            "status": "unavailable",
                            "reason": "raw normalized catalogs could not be generated",
                        }
                    )
    else:
        for domain in CORE_CATALOGS:
            checks.append(
                {
                    "name": f"{domain}-catalog-parity",
                    "domain": domain,
                    "status": "unavailable",
                    "reason": "packaged RuntimeCatalogs/manifest validation failed",
                }
            )

    checks.append(_verify_research(templates, scenario, package_root))
    if save_path is not None and packaged_runtime is not None and raw_runtime is not None:
        try:
            checks.extend(
                _save_calculation_checks(
                    templates,
                    Path(save_path).expanduser().resolve(),
                    scenario,
                    packaged_runtime,
                    raw_runtime,
                )
            )
        except Exception as exc:
            checks.extend(
                {
                    **check,
                    "reason": f"{type(exc).__name__}: {exc}",
                }
                for check in _unavailable_calculation_checks()
            )
    else:
        checks.extend(_unavailable_calculation_checks())
    summary = {
        status: sum(check.get("status") == status for check in checks)
        for status in ("passed", "failed", "unavailable")
    }
    summary["total"] = len(checks)
    overall_status = "failed" if summary["failed"] else "partial" if summary["unavailable"] else "passed"
    return {
        "status": overall_status,
        "scenario": scenario,
        "templatesDir": str(templates),
        "dataDir": str(package_root),
        "savePath": str(Path(save_path).expanduser().resolve()) if save_path is not None else None,
        "tolerance": {"relTol": REL_TOL, "absTol": ABS_TOL},
        "summary": summary,
        "checks": checks,
    }


__all__ = ["verify_catalogs"]
