"""Bounded LLM bootstrap; no history, dashboard or parallel mechanics."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from ti_parser_core import CalculationDependencyError, find_faction_state, first_value
from ti_parser_errors import UserInputError
from ti_parser_catalogs import CatalogError, runtime_catalog_scope
from ti_parser_core import ModuleCatalogError, LocationCatalogError, SolarPowerDataError
from ti_parser_capabilities import capabilities


def shareable(value):
    """Remove infrastructure paths from diagnostics while preserving evidence."""
    if isinstance(value, dict):
        return {k: shareable(v) for k,v in value.items() if k not in {"path", "dataDir", "cache", "cacheFingerprint", "templateSource"}}
    if isinstance(value, (list, tuple)):
        return [shareable(v) for v in value]
    if isinstance(value, Path):
        return value.name
    if isinstance(value, str):
        # Errors may embed paths; redact path tokens rather than exposing user directories.
        import re
        value = re.sub(r"[A-Za-z]:[\\/][^\n,;\"']*", "<local-path>", value)
        value = re.sub(r"(?<![\w:])/(?:[^\s/]+/)+[^\s,;]*", "<local-path>", value)
    return value


def bootstrap_context(session, *, allow_unverified=False):
    inspection = session.inspect()
    report = {"schemaVersion": 1, "kind": "llm-bootstrap-context",
              "save": inspection["save"], "saveIdentity": inspection["saveIdentity"],
              "compatibility": inspection["compatibility"],
              "savedFacts": inspection, "sections": {},
              "availableAnalyses": [row for row in capabilities()["analyses"] if row["kind"] not in {"maintenance", "inventory"}]}
    try:
        sid, faction = find_faction_state(session.indexed)
        report["savedFacts"] = {**inspection, "playerFaction": {"id":sid,"template":faction.get("templateName"),"display":faction.get("displayName")},
            "resources": faction.get("resources"), "missionControlUsage": faction.get("missionControlUsage"),
            "currentProjectProgress": faction.get("currentProjectProgress"), "researchWeights": faction.get("researchWeights")}
    except UserInputError as exc:
        report["playerResolutionError"] = exc.to_dict()
    sections = report["sections"]
    if inspection["compatibility"]["status"] != "verified" and not allow_unverified:
        report["status"] = "deferred"
        for name in ("topbar", "research-ui"):
            sections[name] = {"status":"deferred", "reason":"unverified-compatibility"}
        return shareable(report)
    report["compatibility"] = session.require_calculation(allow_unverified)
    with session.calculation_scope(allow_unverified=allow_unverified):
        for name in ("topbar", "research-ui"):
            try:
                result = session.calculate(name, allow_unverified=allow_unverified)
                incomplete = result.get("status") in {"incomplete", "partial", "unsupported"} or result.get("complete") is False
                sections[name] = {"status": "incomplete" if incomplete else "complete", "result": result,
                    "evidence": {"source":"existing-domain-calculator", "catalogFingerprint": session.compatibility["catalogFingerprint"]}}
            except CalculationDependencyError as exc:
                sections[name] = {"status":"incomplete", "missingDependencies":exc.missing_dependencies}
            except (UserInputError, CatalogError, ModuleCatalogError, LocationCatalogError, SolarPowerDataError) as exc:
                sections[name] = {"status":"incomplete", "error": exc.to_dict() if isinstance(exc,UserInputError) else {"code":"calculation-input-error","message":str(exc)}}
    report["status"] = "complete" if all(row["status"] == "complete" for row in sections.values()) else "incomplete"
    return shareable(report)


def write_analysis(report, output, save_path):
    destination, source = Path(output).expanduser(), Path(save_path)
    if destination.resolve() == source.resolve() or (destination.exists() and os.path.samefile(destination, source)):
        raise UserInputError("Analysis output must not overwrite the source save", code="unsafe-output")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=destination.parent, delete=False) as handle:
            temporary = Path(handle.name)
            json.dump(report, handle, ensure_ascii=False, indent=2, allow_nan=False)
            handle.write("\n")
        os.replace(temporary, destination)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
