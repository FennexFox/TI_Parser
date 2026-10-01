"""Bounded LLM bootstrap; no history, dashboard or parallel mechanics."""
from __future__ import annotations

import math
import json
import os
import re
import tempfile
from pathlib import Path
from ti_parser_core import find_faction_state
from ti_parser_errors import UserInputError
from ti_parser_version import __version__
from ti_parser_capabilities import capabilities


def shareable(value):
    """Remove infrastructure paths from diagnostics while preserving evidence."""
    if isinstance(value, dict):
        return {k: shareable(v) for k,v in value.items() if k not in {"path", "dataDir", "cache", "cacheFingerprint", "templateSource"}}
    if isinstance(value, (list, tuple)):
        return [shareable(v) for v in value]
    if isinstance(value, float) and not math.isfinite(value):
        return {"status": "non-finite", "representation": "NaN" if math.isnan(value) else ("Infinity" if value > 0 else "-Infinity")}
    if isinstance(value, Path):
        return value.name
    if isinstance(value, str):
        # Errors may embed paths; redact path tokens rather than exposing user directories.
        value = re.sub(r"[A-Za-z]:[\\/][^\n,;\"']*", "<local-path>", value)
        value = re.sub(r"(?<![\w:])/(?:[^\s/]+/)+[^\s,;]*", "<local-path>", value)
    return value


def bootstrap_context(session, *, allow_unverified=False):
    inspection = session.inspect()
    report = {"schemaVersion": 1, "parserVersion": __version__, "kind": "llm-bootstrap-context",
              "save": inspection["save"], "saveIdentity": inspection["saveIdentity"],
              "compatibility": inspection["compatibility"],
              "savedFacts": {"modFlags": inspection["modFlags"]}, "sections": {},
              "availableAnalyses": [row for row in capabilities()["analyses"] if row["routingClass"] == "primary"]}
    try:
        sid, faction = find_faction_state(session.indexed)
        report["savedFacts"] = {"modFlags": inspection["modFlags"], "playerFaction": {"id":sid,"template":faction.get("templateName"),"display":faction.get("displayName")},
            "resources": faction.get("resources"), "missionControlUsage": faction.get("missionControlUsage"),
            "currentProjectProgress": [row for row in (faction.get("currentProjectProgress") or []) if isinstance(row,dict) and row.get("slot") in (3,4,5)], "researchWeights": faction.get("researchWeights")}
    except UserInputError as exc:
        report["playerResolutionError"] = exc.to_dict()
    sections = report["sections"]
    if inspection["compatibility"]["status"] != "verified" and not allow_unverified:
        report["status"] = "deferred"
        for name in ("topbar", "research-ui"):
            sections[name] = {"status":"deferred", "reason":"unverified-compatibility"}
        return shareable(report)
    try:
        report["compatibility"] = session.require_calculation(allow_unverified)
    except UserInputError as exc:
        report["status"] = "incomplete"
        for name in ("topbar", "research-ui"):
            sections[name] = {"status": "incomplete", "error": exc.to_dict()}
        return shareable(report)
    with session.calculation_scope(allow_unverified=allow_unverified):
        for name in ("topbar", "research-ui"):
            outcome = session.run(name, allow_unverified=allow_unverified)
            section = {"status": "complete" if outcome["status"] == "complete" else "incomplete"}
            if "result" in outcome:
                result = outcome["result"]
                if name == "research-ui" and "projects" in result:
                    result = {**result, "projects": {"active": result["projects"].get("active", []),
                        "pausedOrStoredCount": len(result["projects"].get("pausedOrStored", []))}}
                section.update({"result": result,
                    "evidence": {"source":"existing-domain-calculator", "catalogFingerprint": session.compatibility["catalogFingerprint"]}})
            for field in ("missingDependencies", "error"):
                if field in outcome:
                    section[field] = outcome[field]
            sections[name] = section
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
