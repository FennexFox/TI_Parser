"""Developer-only, source-derived projection dependency evidence.

Parser AST evidence establishes wiring, never game visibility or mechanics.
This intentionally incomplete inventory keeps unknown consumers blocking.
"""

from __future__ import annotations

import ast
from functools import lru_cache
import hashlib
import json
from pathlib import Path
from typing import Any


KNOWN_NORMALIZATIONS = {
    "controlPointPriorities": ("ControlPointProjectionState.pips", "plan allocation and priority weights"),
    "diversityBonus": ("ControlPointProjectionState.diversity_bonus_cache", "priority investment multiplier"),
    "_accumulatedInvestmentPoints": ("NationProjectionState.progress", "priority completion transactions"),
    "publicOpinion": ("NationProjectionState.public_opinion", "public opinion and research context"),
    "resourceMarketValues": ("NationProjectionState.world_context.resourceMarketValues", "world market economy context"),
}


def _branch_context(function: ast.AST, target: ast.AST) -> list[dict[str, Any]]:
    """Retain enclosing predicates as source evidence, never as branch outcomes."""
    result = []
    for node in ast.walk(function):
        if isinstance(node, ast.If):
            arms = (("body", node.body), ("else", node.orelse))
        elif isinstance(node, ast.IfExp):
            arms = (("body", [node.body]), ("else", [node.orelse]))
        else:
            continue
        for arm, children in arms:
            if any(target is child for statement in children for child in ast.walk(statement)):
                result.append({"line": node.lineno, "predicate": ast.unparse(node.test), "arm": arm,
                               "outcome": "unproven"})
    return sorted(result, key=lambda row: row["line"])


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
                        "branchContext": _branch_context(function, node),
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
    static_only = [dict(row, reconciliation="static-candidate-not-observed",
                        nonObservationExplanation="Enclosing source predicates are contextual evidence only; absence from a container trace does not establish an untaken or safe branch. Scalar and materialized lineage remain unproven.") for row in inventory["dependencies"]
                   if (row["consumer"], row["sourceLocation"]["line"]) not in observed]
    return {"dynamicToStatic": rows, "staticCandidatesNotObserved": static_only,
            "mappedDynamicReadCount": sum(row["status"] == "mapped" for row in rows),
            "unresolvedDynamicReadCount": sum(row["status"] != "mapped" for row in rows),
            "complete": bool(rows) and all(row["status"] == "mapped" for row in rows) and not static_only}


def rule_source_inventory(tools: Path, call_counts: Any, rules: Any) -> dict[str, Any]:
    """Map observed consumers to static rule candidates and literal dependency edges.

    A rule reference inside an observed function is not an execution record.
    Dynamic dispatch and branches remain explicit until reconciled separately.
    """
    references, edges, hashes = [], [], {}

    def rule_attribute(node: ast.AST) -> ast.Attribute | None:
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "Rules":
            return node
        if (isinstance(node, ast.Attribute) and node.attr == "id"
                and isinstance(node.value, ast.Attribute)
                and isinstance(node.value.value, ast.Name) and node.value.value.id == "Rules"):
            return node.value
        return None

    def rule_id(node: ast.AST) -> str | None:
        attribute = rule_attribute(node)
        if attribute is not None:
            rule = getattr(rules, attribute.attr, None)
            return getattr(rule, "id", f"unregistered:Rules.{attribute.attr}")
        return None

    for module in sorted({module for module, _name in call_counts}):
        path = tools / f"{module}.py"
        if not path.is_file():
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        hashes[f"tools/{path.name}"] = digest
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for function in ast.walk(tree):
            if not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)) or not call_counts[(module, function.name)]:
                continue
            for node in ast.walk(function):
                attribute = rule_attribute(node)
                if attribute is not None and attribute is node:
                    identifier = rule_id(attribute)
                    references.append({"ruleId": identifier, "consumer": f"{module}.{function.name}",
                                       "sourceLocation": {"file": f"tools/{path.name}", "line": attribute.lineno, "sha256": digest},
                                       "branchContext": _branch_context(function, attribute), "executionStatus": "candidate-only"})
                if isinstance(node, ast.Dict):
                    entries = {key.value: value for key, value in zip(node.keys, node.values)
                               if isinstance(key, ast.Constant) and isinstance(key.value, str)}
                    parent = rule_id(entries["ruleId"]) if "ruleId" in entries else None
                    if parent and "dependencies" in entries:
                        for child in ast.walk(entries["dependencies"]):
                            attribute = rule_attribute(child)
                            if attribute is child:
                                dependency = rule_id(attribute)
                                edges.append({"from": parent, "to": dependency, "sourceLocation":
                                              {"file": f"tools/{path.name}", "line": attribute.lineno, "sha256": digest},
                                              "consumer": f"{module}.{function.name}",
                                              "branchContext": _branch_context(function, attribute)})
    return {"ruleReferences": references, "registeredLiteralEdges": edges,
            "dynamicDependencyAppendSites": dependency_append_sites(tools),
            "sourceFileSha256": hashes}


def dependency_append_sites(tools: Path) -> list[dict[str, Any]]:
    """Find source-bound dynamic ``execution['dependencies'].append(Rules.X.id)`` sites.

    The parent rule is selected at runtime, so the AST can establish the append
    operation and child source location but cannot invent the parent. A runtime
    trace must supply the actual ``execution['ruleId']`` for that invocation.
    """
    sites = []
    for path in sorted(tools.glob("ti_parser_*.py")):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.name)
        parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
        functions = [node for node in ast.walk(tree)
                     if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
        for function in functions:
            for node in ast.walk(function):
                if not (isinstance(node, ast.Attribute) and node.attr == "id"
                        and isinstance(node.value, ast.Attribute)
                        and isinstance(node.value.value, ast.Name) and node.value.value.id == "Rules"):
                    continue
                parent = parents.get(node)
                while parent is not None and parent is not function:
                    if (isinstance(parent, ast.Call) and isinstance(parent.func, ast.Attribute)
                            and parent.func.attr == "append" and isinstance(parent.func.value, ast.Subscript)
                            and isinstance(parent.func.value.value, ast.Name)
                            and parent.func.value.value.id == "execution"
                            and isinstance(parent.func.value.slice, ast.Constant)
                            and parent.func.value.slice.value == "dependencies"):
                        sites.append({
                            "module": path.stem,
                            "function": function.name,
                            "ruleName": node.value.attr,
                            "line": node.lineno,
                            "sourceLocation": {"file": f"tools/{path.name}", "line": node.lineno, "sha256": digest},
                            "branchContext": _branch_context(function, node),
                        })
                        break
                    parent = parents.get(parent)
    return sorted(sites, key=lambda row: (row["module"], row["function"], row["line"]))


@lru_cache(maxsize=4096)
def source_control_flow_context(tools: Path, module: str, function_name: str, line: int,
                                site_kind: str, callee_name: str = "") -> dict[str, Any]:
    """Bind an observed call/return line to its enclosing source predicates."""
    path = tools / f"{module}.py"
    if not path.is_file():
        return {"sourceMapped": False, "reason": "source file missing"}
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.name)
    function = next((node for node in ast.walk(tree)
                     if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                     and node.name == function_name), None)
    if function is None:
        return {"sourceMapped": False, "reason": "containing function missing"}
    if site_kind == "return":
        targets = [node for node in ast.walk(function) if isinstance(node, ast.Return) and node.lineno == line]
    elif site_kind == "call":
        def called_name(node: ast.Call) -> str | None:
            if isinstance(node.func, ast.Name):
                return node.func.id
            if isinstance(node.func, ast.Attribute):
                return node.func.attr
            return None
        targets = [node for node in ast.walk(function)
                   if isinstance(node, ast.Call) and node.lineno == line and called_name(node) == callee_name]
    elif site_kind == "rule-reference":
        targets = [node for node in ast.walk(function)
                   if isinstance(node, ast.Attribute) and node.attr == callee_name and node.lineno == line
                   and isinstance(node.value, ast.Name) and node.value.id == "Rules"]
    else:
        targets = []
    if len(targets) != 1:
        return {"sourceMapped": False, "reason": "observed line did not map to one source site",
                "sourceLocation": {"file": f"tools/{path.name}", "line": line, "sha256": digest}}
    target = targets[0]
    contexts = []
    for node in ast.walk(function):
        if isinstance(node, ast.If):
            arms = (("body", node.body), ("else", node.orelse))
        elif isinstance(node, ast.IfExp):
            arms = (("body", [node.body]), ("else", [node.orelse]))
        else:
            continue
        for arm, statements in arms:
            if any(target is child for statement in statements for child in ast.walk(statement)):
                outcome = {"call": "observed-call-site", "return": "observed-return-site",
                           "rule-reference": "observed-rule-reference"}.get(site_kind, "observed-source-site")
                contexts.append({"line": node.lineno, "predicate": ast.unparse(node.test), "arm": arm,
                                 "outcome": outcome})
    expression = ast.unparse(target.value) if isinstance(target, ast.Return) and target.value is not None else None
    return {"sourceMapped": True,
            "sourceLocation": {"file": f"tools/{path.name}", "line": line, "sha256": digest},
            "siteKind": site_kind, "function": function_name,
            "calleeName": callee_name if site_kind in {"call", "rule-reference"} else None,
            "branchContext": sorted(contexts, key=lambda row: row["line"]),
            "returnExpression": expression}


def execution_closure(executions: list[dict[str, Any]], source: dict[str, Any], registry: Any,
                      *, required_predicates: dict[str, Any],
                      runtime_rule_references: list[dict[str, Any]] | None = None,
                      runtime_dependency_edges: list[dict[str, Any]] | None = None,
                      runtime_helper_executions: list[dict[str, Any]] | None = None,
                      helper_rule_bindings: dict[str, tuple[str, ...]] | None = None) -> dict[str, Any]:
    """Compute a bounded rule graph and reconcile it with optional runtime source tracing.

    Runtime reference rows are evidence only when they bind to an exact AST
    ``Rules.X.id`` site and current source hash. Missing trace input preserves
    the earlier candidate-only, fail-closed behavior.
    """
    executed = {str(row.get("ruleId")) for row in executions}
    edges = {(str(row.get("ruleId")), str(dependency)) for row in executions
             for dependency in row.get("directDependencies", row.get("dependencies", []))}
    registered_edges = {(row["from"], row["to"]) for row in source["registeredLiteralEdges"]}
    dynamic_edge_rows = list(runtime_dependency_edges or [])
    dynamic_append_sites = {
        (row["module"], row["function"], row["ruleName"], row["line"], row["sourceLocation"]["file"],
         row["sourceLocation"]["sha256"])
        for row in source.get("dynamicDependencyAppendSites", [])
    }
    matched_dynamic_edges = []
    unmapped_runtime_edges = []
    for event in dynamic_edge_rows:
        location = event.get("sourceLocation", {})
        context = event.get("sourceControlFlow") or {}
        context_location = context.get("sourceLocation") or {}
        context_bound = (
            context.get("sourceMapped") is True
            and context.get("siteKind") == "rule-reference"
            and context.get("function") == event.get("function")
            and context.get("calleeName") == event.get("ruleName")
            and {key: context_location.get(key) for key in ("file", "line", "sha256")}
            == {key: location.get(key) for key in ("file", "line", "sha256")}
        )
        key = (event.get("module"), event.get("function"), event.get("ruleName"), location.get("line"),
               location.get("file"), location.get("sha256"))
        (matched_dynamic_edges if context_bound and key in dynamic_append_sites else unmapped_runtime_edges).append(event)
    calculation_edges = {(str(row.get("from")), str(row.get("to"))) for row in matched_dynamic_edges
                         if row.get("stage") == "projection-calculation"}
    registered_edges.update(calculation_edges)

    candidates_by_site = {}
    for row in source["ruleReferences"]:
        location = row["sourceLocation"]
        key = (row["ruleId"], row["consumer"], location.get("file"), location.get("line"), location.get("sha256"))
        candidates_by_site.setdefault(key, []).append(row)
    observed_by_site: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    unmapped_runtime_references = []
    for event in runtime_rule_references or []:
        location = event.get("sourceLocation", {})
        key = (str(event.get("ruleId")), event.get("consumer"), location.get("file"),
               location.get("line"), location.get("sha256"))
        if key in candidates_by_site:
            observed_by_site.setdefault(key, []).append(event)
        else:
            unmapped_runtime_references.append(event)

    annotated_static_references = []
    unrecorded_static = []
    static_not_evaluated = []
    calculation_reference_ids = set()
    for row in source["ruleReferences"]:
        location = row["sourceLocation"]
        key = (row["ruleId"], row["consumer"], location.get("file"), location.get("line"), location.get("sha256"))
        events = observed_by_site.get(key, [])
        stages = sorted({str(event.get("stage", "unknown")) for event in events})
        if "projection-calculation" in stages:
            status = "calculation-stage-rule-metadata-reference-observed"
            calculation_reference_ids.add(row["ruleId"])
        elif events:
            status = "preparation-or-output-rule-metadata-reference-observed"
        elif runtime_rule_references is not None:
            status = "not-evaluated-at-source-site"
            static_not_evaluated.append(dict(row, executionStatus=status,
                                             stageObservations=[],
                                             nonObservationExplanation="The source-bound runtime Rules proxy observed no access to this exact AST reference site during the bounded trial; this excludes it from this trial's executed-rule closure but does not establish visibility or harmlessness."))
        else:
            status = "candidate-only"
            unrecorded_static.append(row)
        annotated_static_references.append(dict(row, executionStatus=status, stageObservations=stages))

    runtime_edge_evidence = []
    for parent, child in sorted(edges):
        static_sites = [row for row in source["registeredLiteralEdges"]
                        if (row["from"], row["to"]) == (parent, child)]
        observed_sites = [site for site in static_sites if any(
            event.get("stage") == "projection-calculation"
            and event.get("ruleId") == child and event.get("consumer") == site.get("consumer")
            and event.get("sourceLocation") == site.get("sourceLocation")
            for event in runtime_rule_references or [])]
        dynamic_sites = [event for event in matched_dynamic_edges
                         if (str(event.get("from")), str(event.get("to"))) == (parent, child)
                         and event.get("stage") == "projection-calculation"]
        runtime_edge_evidence.append({
            "from": parent, "to": child,
            "status": "execution-recorded" if child in executed else
                     "dynamic-source-edge-observed" if dynamic_sites else
                     "rule-reference-observed" if observed_sites else "source-edge-not-observed",
            "staticSourceLocations": [row.get("sourceLocation") for row in static_sites],
            "observedSourceLocations": [row["sourceLocation"] for row in observed_sites] +
                                       [row["sourceLocation"] for row in dynamic_sites],
        })

    helper_rule_bindings = helper_rule_bindings or {}
    helper_execution_evidence = []
    unmatched_helper_events = []
    source_hashes = source.get("sourceFileSha256", {})
    for event in runtime_helper_executions or []:
        helper = event.get("helper")
        expected_rule_ids = list(helper_rule_bindings.get(str(helper), ()))
        helper_location = event.get("helperSourceLocation") or {}
        callsite_context = event.get("callSiteContext") or {}
        return_site = event.get("returnSite") or {}
        callsite_location = callsite_context.get("sourceLocation") or {}
        return_location = return_site.get("sourceLocation") or {}
        observed_call_location = event.get("callSite") or {}
        observed_return_location = event.get("observedReturnLocation") or {}
        helper_name = str(helper or "")
        caller_name = str(event.get("caller") or "").rsplit(".", 1)[-1]
        source_bound = (
            bool(expected_rule_ids)
            and event.get("helperRuleIds") == expected_rule_ids
            and helper_location.get("file") in source_hashes
            and helper_location.get("sha256") == source_hashes.get(helper_location.get("file"))
            and callsite_context.get("siteKind") == "call"
            and callsite_context.get("function") == caller_name
            and callsite_context.get("calleeName") == helper_name
            and bool(callsite_context.get("sourceMapped"))
            and callsite_location.get("file") in source_hashes
            and callsite_location.get("sha256") == source_hashes.get(callsite_location.get("file"))
            and {key: callsite_location.get(key) for key in ("file", "line", "sha256")}
            == {key: observed_call_location.get(key) for key in ("file", "line", "sha256")}
            and return_site.get("siteKind") == "return"
            and return_site.get("function") == helper_name
            and bool(return_site.get("sourceMapped"))
            and return_location.get("file") in source_hashes
            and return_location.get("sha256") == source_hashes.get(return_location.get("file"))
            and {key: return_location.get(key) for key in ("file", "line", "sha256")}
            == {key: observed_return_location.get(key) for key in ("file", "line", "sha256")}
            and event.get("returnedNormallyWithFiniteNumber") is True
        )
        helper_row = {**event, "sourceBound": source_bound,
                      "bindingStatus": "source-bound-helper-contract" if source_bound else "unresolved"}
        helper_execution_evidence.append(helper_row)
        if not source_bound:
            unmatched_helper_events.append(helper_row)

    def helper_proves_edge(parent: str, child: str, static_sites: list[dict[str, Any]]) -> list[dict[str, Any]]:
        evidence = []
        for helper in helper_execution_evidence:
            if (helper.get("sourceBound") is not True
                    or helper.get("stage") != "projection-calculation"
                    or child not in helper.get("helperRuleIds", [])):
                continue
            for site in static_sites:
                site_location = site.get("sourceLocation", {})
                call_location = (helper.get("callSiteContext") or {}).get("sourceLocation", {})
                site_branches = [(row.get("predicate"), row.get("arm")) for row in site.get("branchContext", [])]
                call_branches = [(row.get("predicate"), row.get("arm"))
                                 for row in (helper.get("callSiteContext") or {}).get("branchContext", [])]
                if (helper.get("caller") == site.get("consumer")
                        and call_location.get("file") == site_location.get("file")
                        and call_location.get("sha256") == site_location.get("sha256")
                        and site_branches == call_branches):
                    evidence.append({"helper": helper.get("helper"), "helperRuleIds": helper.get("helperRuleIds"),
                                     "returnKind": helper.get("returnKind"),
                                     "returnSite": helper.get("returnSite"),
                                     "callSiteContext": helper.get("callSiteContext"),
                                     "coverageClaim": "none"})
        return evidence

    closure = executed | {child for _parent, child in edges}
    blockers = []
    for identifier in sorted(closure):
        if identifier not in registry:
            blockers.append({"kind": "unknown-rule", "ruleId": identifier})
    for parent, child in sorted(edges):
        if (parent, child) not in registered_edges:
            blockers.append({"kind": "unreconciled-dynamic-edge", "from": parent, "to": child,
                             "reason": "No literal ruleId/dependencies source declaration in observed consumers; dynamic edge needs explicit source reconciliation."})
        evidence = next((row for row in runtime_edge_evidence if (row["from"], row["to"]) == (parent, child)), None)
        static_sites = [row for row in source["registeredLiteralEdges"]
                        if (row["from"], row["to"]) == (parent, child)]
        helpers = helper_proves_edge(parent, child, static_sites)
        if evidence is not None:
            evidence["returnedHelperEvidence"] = helpers
            if helpers and child not in executed:
                evidence["status"] = "helper-invocation-returned"
        if child not in executed and not helpers:
            blockers.append({"kind": "dependency-not-recorded", "from": parent, "to": child,
                             "edgeEvidence": evidence.get("status") if evidence else "none",
                             "reason": "The edge is recorded, but no standalone ruleExecution or source-bound helper call with a mapped finite return was observed."})
    graph = {identifier: {child for parent, child in edges if parent == identifier} for identifier in closure}
    transitive = {}
    for identifier in sorted(closure):
        reached, pending = set(), list(graph.get(identifier, ()))
        while pending:
            child = pending.pop()
            if child in reached:
                continue
            reached.add(child)
            pending.extend(graph.get(child, ()))
        transitive[identifier] = sorted(reached)
        if identifier in reached:
            blockers.append({"kind": "dependency-cycle", "ruleId": identifier})
    for row in unrecorded_static:
        blockers.append({"kind": "unexplained-static-path", "ruleId": row["ruleId"],
                         "consumer": row["consumer"], "sourceLocation": row["sourceLocation"],
                         "branchContext": row["branchContext"],
                         "reason": "Observed function contains an unrecorded rule reference; source predicate alone cannot prove exclusion or scalar lineage."})
    for row in unmapped_runtime_references:
        blockers.append({"kind": "unmapped-runtime-rule-reference", "ruleId": row.get("ruleId"),
                         "consumer": row.get("consumer"), "sourceLocation": row.get("sourceLocation"),
                         "reason": "Runtime Rules access did not bind to an AST candidate with the same source hash, consumer and line."})
    for row in unmapped_runtime_edges:
        blockers.append({"kind": "unmapped-runtime-dependency-edge", "from": row.get("from"), "to": row.get("to"),
                         "sourceLocation": row.get("sourceLocation"),
                         "reason": "Runtime dependency append did not bind to a source-hashed AST append site."})
    for row in unmatched_helper_events:
        blockers.append({"kind": "unmapped-or-incomplete-helper-execution", "helper": row.get("helper"),
                         "sourceLocation": row.get("helperSourceLocation"),
                         "reason": "The helper call, callsite, return site, or finite numeric return did not bind to current source and an audit rule mapping."})
    if not executions:
        blockers.append({"kind": "missing-execution-records"})
    coverage_records = sorted({(str(row.get("ruleId")), str(row.get("effectiveCoverage")),
                               str(row.get("coverageResolverId")), str(row.get("provenance")))
                              for row in executions})
    static_candidates = {row["ruleId"] for row in source["ruleReferences"]}
    runtime_reference_rows = [event for event in (runtime_rule_references or [])
                              if event.get("stage") == "projection-calculation"
                              and (str(event.get("ruleId")), event.get("consumer"),
                                   event.get("sourceLocation", {}).get("file"),
                                   event.get("sourceLocation", {}).get("line"),
                                   event.get("sourceLocation", {}).get("sha256")) in observed_by_site]
    report = {"executedRuleIds": sorted(executed), "directEdges": [{"from": p, "to": c} for p, c in sorted(edges)],
              "closureRuleIds": sorted(closure), "transitiveDependencies": transitive,
              "staticCandidateRuleIds": sorted(static_candidates),
              "requiredRuleIds": sorted(closure | (static_candidates if runtime_rule_references is None else set())),
              "calculationRuleReferenceIds": sorted(calculation_reference_ids),
              "helperRuleReferenceCount": sum(int(event.get("count", 1)) for event in runtime_reference_rows),
              "sourceBoundRuntimeRuleReferences": [event for event in runtime_reference_rows],
              "runtimeRuleReferencesMapped": runtime_rule_references is not None and not unmapped_runtime_references,
              "unmappedRuntimeRuleReferences": unmapped_runtime_references,
              "staticRuleReferenceReconciliation": annotated_static_references,
              "staticCandidatesNotEvaluated": static_not_evaluated,
              "runtimeDependencyEdgeEvidence": runtime_edge_evidence,
              "runtimeDependencyEdges": matched_dynamic_edges,
              "unmappedRuntimeDependencyEdges": unmapped_runtime_edges,
              "sourceBoundHelperExecutions": helper_execution_evidence,
              "executionCoverageRecords": [{"ruleId": identifier, "effectiveCoverage": coverage,
                                             "coverageResolverId": resolver, "provenance": provenance}
                                            for identifier, coverage, resolver, provenance in coverage_records],
              "registryEvidence": {identifier: registry[identifier].diagnostics()
                                   for identifier in sorted(closure) if identifier in registry
                                   and hasattr(registry[identifier], "diagnostics")},
              "executionRecordCount": len(executions), "unrecordedStaticRuleReferences": unrecorded_static,
              "requiredDomainPredicates": required_predicates, "blockers": blockers,
              "complete": not blockers, "sourceFileSha256": source["sourceFileSha256"]}
    report["fingerprint"] = hashlib.sha256(json.dumps(report, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return report
