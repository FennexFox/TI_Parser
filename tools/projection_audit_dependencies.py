"""Developer-only, source-derived projection dependency evidence.

Parser AST evidence establishes wiring, never game visibility or mechanics.
This intentionally incomplete inventory keeps unknown consumers blocking.
"""

from __future__ import annotations

import ast
import hashlib
from pathlib import Path
from typing import Any


KNOWN_NORMALIZATIONS = {
    "controlPointPriorities": ("ControlPointProjectionState.pips", "plan allocation and priority weights"),
    "diversityBonus": ("ControlPointProjectionState.diversity_bonus_cache", "priority investment multiplier"),
    "_accumulatedInvestmentPoints": ("NationProjectionState.progress", "priority completion transactions"),
    "publicOpinion": ("NationProjectionState.public_opinion", "public opinion and research context"),
    "resourceMarketValues": ("NationProjectionState.world_context.resourceMarketValues", "world market economy context"),
}


def _destination_evidence(function: ast.AST, source_key: str, destination: str) -> list[int]:
    """Verify a bounded assignment/name chain to the stated constructor field."""
    linked_names: set[str] = set()
    assignments = [node for node in ast.walk(function) if isinstance(node, (ast.Assign, ast.AnnAssign))]
    for _ in range(len(assignments) + 1):
        previous = set(linked_names)
        for assignment in assignments:
            value = assignment.value
            if value is None:
                continue
            nodes = list(ast.walk(value))
            linked = (any(isinstance(node, ast.Constant) and node.value == source_key for node in nodes)
                      or any(isinstance(node, ast.Name) and node.id in linked_names for node in nodes))
            if linked:
                targets = assignment.targets if isinstance(assignment, ast.Assign) else [assignment.target]
                linked_names.update(target.id for target in targets if isinstance(target, ast.Name))
        if previous == linked_names:
            break
    constructor, field, *_rest = destination.split(".")
    lines = []
    for node in ast.walk(function):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute) or node.func.attr != constructor:
            continue
        for keyword in node.keywords:
            if keyword.arg == field and any(isinstance(child, ast.Name) and child.id in linked_names for child in ast.walk(keyword.value)):
                lines.append(keyword.value.lineno)
    return lines


def _direct_scalar_destinations(function: ast.AST) -> dict[str, tuple[str, list[int]]]:
    """Read exact required-field-to-constructor wiring, without inferring visibility."""
    result = {}
    for node in ast.walk(function):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr not in {"NationProjectionState", "RegionProjectionState", "ArmyProjectionState"}:
            continue
        for keyword in node.keywords:
            for child in ast.walk(keyword.value):
                if (isinstance(child, ast.Call) and isinstance(child.func, ast.Name)
                        and child.func.id in {"_required_projection_number", "_required_projection_bool", "_required_projection_string"}
                        and len(child.args) >= 3 and isinstance(child.args[2], ast.Constant)
                        and isinstance(child.args[2].value, str)):
                    result[child.args[2].value] = (f"{node.func.attr}.{keyword.arg}", [keyword.value.lineno])
    return result


def source_inventory(tools: Path, call_counts: Any) -> dict[str, Any]:
    """Inventory literal reads and potential normalization boundaries in run consumers.

    Literal reads may belong to derived objects rather than raw save state. They
    are candidates, so no unmatched candidate is silently certified as a read.
    """
    dependencies = []
    boundaries = []
    hashes = {}
    for module in sorted({module for module, _function in call_counts}):
        path = tools / f"{module}.py"
        if not path.is_file():
            continue
        source = path.read_text(encoding="utf-8")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        hashes[f"tools/{path.name}"] = digest
        tree = ast.parse(source)
        for function in ast.walk(tree):
            if not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not call_counts[(module, function.name)]:
                continue
            consumer = f"{module}.{function.name}"
            direct_destinations = _direct_scalar_destinations(function) if module == "ti_parser_projection_adapter" else {}
            for node in ast.walk(function):
                if not hasattr(node, "lineno"):
                    continue
                key = None
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Attribute) and node.func.attr in {"get", "setdefault"} and node.args:
                        key = node.args[0]
                    elif isinstance(node.func, ast.Name) and node.func.id.startswith("_required_projection_") and len(node.args) >= 3:
                        key = node.args[2]
                elif isinstance(node, ast.Subscript):
                    key = node.slice
                location = {"file": f"tools/{path.name}", "line": node.lineno, "sha256": digest}
                if isinstance(key, ast.Constant) and isinstance(key.value, str):
                    known = KNOWN_NORMALIZATIONS.get(key.value) if module == "ti_parser_projection_adapter" and function.name == "extract_nation_projection_state" else None
                    destination_lines = _destination_evidence(function, key.value, known[0]) if known else []
                    if not destination_lines:
                        known = None
                    if key.value in direct_destinations:
                        destination, destination_lines = direct_destinations[key.value]
                        known = (destination, "required scalar constructor input")
                    dependencies.append({
                        "dependencyId": f"{consumer}:{node.lineno}:{key.value}",
                        "sourcePattern": f"*.{key.value}",
                        "sourceKey": key.value,
                        "sourceLocation": location,
                        "consumer": consumer,
                        "destinationRole": known[0] if known else "unresolved",
                        "destinationUse": known[1] if known else "unresolved",
                        "destinationLocations": [dict(location, line=line) for line in destination_lines],
                        "mappingStatus": "mapped" if known else "unresolved",
                        "evidenceLayers": {"parserImplementation": "AST literal read and source hash", "save": "dynamic reconciliation required", "gameAuthority": "absent", "scenarioAssumptions": "ModernScenario, six fully player-owned control points, 180 days, Knowledge/Welfare, one segment, advisors empty, details/diagnostics false"},
                        "visibilityCategory": "unresolved",
                        "visibilityEvidence": [],
                        "buildApplicability": "parser source hash only; game build unresolved",
                        "blocking": True,
                    })
                boundary = None
                if isinstance(node, (ast.DictComp, ast.ListComp, ast.SetComp, ast.GeneratorExp)):
                    boundary = type(node).__name__
                elif isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name) and node.func.id in {"dict", "list", "float", "int", "str", "bool", "as_float"}:
                        boundary = node.func.id
                    elif isinstance(node.func, ast.Attribute) and node.func.attr in {"copy", "deepcopy", "items", "values"}:
                        boundary = node.func.attr
                elif isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Slice):
                    boundary = "slice"
                if boundary:
                    boundaries.append({"consumer": consumer, "sourceLocation": location, "operation": boundary, "status": "unresolved", "reason": "AST candidate requires scalar/container lineage to destination reconciliation"})
    return {"scope": {"scenario": "ModernScenario", "controlPointCount": 6, "days": 180,
                      "segmentCount": 1, "advisors": [], "details": False, "diagnostics": False,
                      "trials": [{"Knowledge": 3, "Welfare": 1}, {"Knowledge": 1, "Welfare": 3}]},
            "sourceFileSha256": hashes, "dependencies": dependencies, "normalizationBoundaries": boundaries}


def reconcile(inventory: dict[str, Any], reads: list[dict[str, Any]]) -> dict[str, Any]:
    """Reconcile observed paths with AST consumer evidence; ambiguity blocks."""
    rows = []
    observed = set()
    for read in reads:
        candidates = [row for row in inventory["dependencies"]
                      if row["sourceKey"] in read["path"].split(".")
                      and row["consumer"] in read.get("consumers", [])]
        for row in candidates:
            observed.add((row["consumer"], row["sourceLocation"]["line"]))
        mapped = [row for row in candidates if row["mappingStatus"] == "mapped"]
        # An enclosing mapped path does not certify descendants or other consumers.
        exact_leaf = bool(mapped) and all(read["path"].endswith("." + row["sourceKey"]) for row in mapped)
        status = "mapped" if exact_leaf and len({row["destinationRole"] for row in mapped}) == 1 else "unresolved"
        rows.append({"path": read["path"], "stage": read["stage"], "operation": read["operation"], "status": status,
                     "candidateSourceLocations": [row["sourceLocation"] for row in candidates],
                     "destinationRoles": sorted({row["destinationRole"] for row in mapped}),
                     "reason": "source-derived normalization mapping" if status == "mapped" else "unclassified, ambiguous, container, or parameterized read requires lineage evidence"})
    static_only = [dict(row, reconciliation="static-candidate-not-observed") for row in inventory["dependencies"]
                   if (row["consumer"], row["sourceLocation"]["line"]) not in observed]
    return {"dynamicToStatic": rows, "staticCandidatesNotObserved": static_only,
            "mappedDynamicReadCount": sum(row["status"] == "mapped" for row in rows),
            "unresolvedDynamicReadCount": sum(row["status"] != "mapped" for row in rows),
            "complete": bool(rows) and all(row["status"] == "mapped" for row in rows) and not static_only}
