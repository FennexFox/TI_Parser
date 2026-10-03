"""Developer-only, fail-closed applicability of reviewed closure findings.

These findings explain blockers. They are never an approval packet, a game
visibility oracle, or a runtime dependency of the parser.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable


EVIDENCE_PATH = "dev-docs/projection_execution_evidence.json"


def review_evidence(root: Path, provided_hash: str | None, packaged_hash: str | None,
                    rule_ids: Iterable[str]) -> dict[str, Any]:
    path = root / EVIDENCE_PATH
    try:
        raw = path.read_bytes()
        document = json.loads(raw)
        if not isinstance(document, dict) or document.get("schemaVersion") != 1:
            raise ValueError("unsupported evidence document")
    except (OSError, ValueError) as exc:
        return {"status": "unavailable", "eligible": False,
                "reason": type(exc).__name__, "mechanics": [], "visibility": [],
                "unreviewedRuleIds": sorted(set(rule_ids)), "evidenceSha256": None}

    findings: dict[str, list[dict[str, Any]]] = {}
    for section_name, destination in (("mechanics", "mechanics"), ("visibilityFindings", "visibility")):
        section = document.get(section_name)
        section = section if isinstance(section, dict) else {}
        rows = section.get("findings")
        rows = rows if isinstance(rows, list) else []
        applicable_build = (isinstance(provided_hash, str) and bool(re.fullmatch(r"[0-9a-f]{64}", provided_hash))
                            and provided_hash == packaged_hash == section.get("currentDllSha256"))
        findings[destination] = []
        for row in rows:
            if not isinstance(row, dict):
                findings[destination].append({"applicability": "stale", "reason": "malformed-finding"})
                continue
            sources = ([dict(row["parser"], path=row["parser"].get("file"))]
                       if destination == "mechanics" and isinstance(row.get("parser"), dict)
                       else row.get("parserSources", []))
            current_sources = isinstance(sources, list) and bool(sources)
            for source in sources if isinstance(sources, list) else []:
                try:
                    relative = Path(source["path"])
                    target = (root / relative).resolve()
                    if relative.is_absolute() or not target.is_relative_to((root / "tools").resolve()):
                        raise ValueError("source outside parser tools")
                    payload = target.read_bytes()
                    algorithm = document.get("parserSourceHashAlgorithm", "sha256-bytes")
                    if algorithm == "sha256-utf8-lf":
                        payload = payload.replace(b"\r\n", b"\n")
                    elif algorithm != "sha256-bytes":
                        raise ValueError("unsupported source hash algorithm")
                    current_sources = current_sources and hashlib.sha256(payload).hexdigest() == source.get("sourceSha256")
                except (KeyError, TypeError, OSError, ValueError):
                    current_sources = False
            findings[destination].append({**row,
                "applicability": "current" if applicable_build and current_sources else "stale",
                "permissionEstablished": False})

    required = set(rule_ids)
    reviewed = {row.get("ruleId") for row in findings["mechanics"] if row.get("applicability") == "current"}
    return {"status": "incomplete", "eligible": False,
            "reason": "Scoped review findings explain blockers; they do not establish complete mechanics or visibility acceptance.",
            "evidenceSha256": hashlib.sha256(raw).hexdigest(),
            "mechanics": findings["mechanics"], "visibility": findings["visibility"],
            "runtimeClosureRuleIds": sorted(required),
            "unreviewedRuleIds": sorted(required - reviewed)}
