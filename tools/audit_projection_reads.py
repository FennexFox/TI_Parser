"""Developer-only structural audit of save reads in nation projection.

This records operations at wrapped save-container boundaries. It deliberately
does not classify raw reads as visible, own-scope, or safe, and it does not
claim a complete trace when values have been normalized into ordinary Python
containers.
"""

from __future__ import annotations

import argparse
import ast
from collections import Counter
from contextlib import contextmanager
import copy
import hashlib
import importlib.util
import json
import math
import re
import sys
from pathlib import Path
from typing import Any, Iterator


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import ti_parser_core as core
import ti_parser_income as income
import ti_parser_nation_projection as projection
import ti_parser_runtime as runtime_layer
import ti_parser_topbar as topbar_layer
import ti_save_parser as parser
from projection_audit_evidence import review_evidence
from projection_audit_dependencies import reconcile, source_inventory
from projection_audit_dependencies import dependency_append_sites, execution_closure, rule_source_inventory
from projection_audit_dependencies import source_control_flow_context
from ti_parser_mechanics import REGISTRY, Rules
from ti_parser_catalogs import RuntimeCatalogs, canonical_json_bytes, file_sha256, runtime_catalog_scope


SCENARIO = "ModernScenario"
DAYS = 180
CHECKPOINTS = [0, 180]
TRIALS = (
    ("knowledge3_welfare1", 3, 1),
    ("welfare3_knowledge1", 1, 3),
)
BLOCKED_OUTPUT_PARTS = {".ti_cache", ".pytest_cache", ".ruff_cache", "__pycache__", "graphify-out"}
STATIC_CALL_CHECKLIST = (
    ("ti_parser_projection_adapter", "calculate_nation_projection", "adapter preparation"),
    ("ti_parser_org", "councilor_summary_maps", "councilor preparation"),
    ("ti_parser_projection_adapter", "projection_advisor_profiles", "advisor preparation"),
    ("ti_parser_projection_adapter", "extract_nation_projection_state", "save extraction"),
    ("ti_parser_topbar", "calculate_topbar", "observed faction context preparation"),
    ("ti_parser_nation_projection", "projection_output", "execution and output"),
    ("ti_parser_nation_projection", "run_projection", "simulation"),
)
# Runtime calls that can discharge otherwise-missing helper dependencies only
# when the call and its numeric return are source-bound. Their rule metadata
# never becomes a synthetic ruleExecution or coverage claim.
EXECUTION_HELPER_RULE_BINDINGS = {
    "_base_ip": ("nation.ip.base",),
    "_annual_population_growth": ("nation.population.annual-growth",),
    "_live_cohesion_rest": ("nation.periodic.cohesion",),
    "_live_unrest_rest": ("nation.periodic.unrest",),
}
STATIC_MAPPING_CHECKLIST = (
    ("*.Value.controlPointPriorities", "projection control-point pips"),
    ("*.Value.diversityBonus", "projection diversity cache"),
    ("*.Value._accumulatedInvestmentPoints", "projection investment progress"),
    ("*.Value.publicOpinion", "projection public-opinion context"),
    ("*.Value.resourceMarketValues", "projection world market context"),
    ("TICouncilorState and mission references", "advisor profiles and assignment context"),
    ("faction/effect state and faction contexts", "priority bonuses and effect modifiers"),
    ("faction state read by calculate_topbar", "observed faction context"),
    ("packaged catalog JSON and manifest loading", "catalog source preparation"),
    ("IndexedState.gamestates/type_index/id_index containers", "lookup rows and empty collections"),
    ("materialized scalar leaves and helper-normalized values", "all raw scalar-to-output dependencies"),
)
STATIC_CATALOG_KEYS = {"effect", "trait", "org", "research", "ship", "nation_claim", "nation_development"}
SAFE_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,79}$")


class AuditInputError(ValueError):
    """The selected input cannot support the controlled projection run."""


def _load_fixture() -> dict[str, Any]:
    fixture_path = ROOT / "tests" / "fixtures" / "fairplay_projection.py"
    spec = importlib.util.spec_from_file_location("fairplay_projection_fixture", fixture_path)
    if spec is None or spec.loader is None:
        raise AuditInputError("The built-in projection fixture could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.make_save_data()


def _canonical_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _canonical_acceptance_shape() -> dict[str, Any]:
    return {
        "inputKind": "controlled-synthetic-fixture",
        "fixtureDomain": ["A", "B"],
        "days": DAYS,
        "checkpoints": CHECKPOINTS,
        "controlPointCount": 6,
        "fullyOwnedBySelectedFaction": True,
        "everyControlPoint": True,
        "segmentCount": 1,
        "advisorCount": 0,
        "details": False,
        "diagnostics": False,
        "trials": [
            {"fixture": label, "name": trial, "Knowledge": knowledge, "Welfare": welfare}
            for label, (trial, knowledge, welfare) in zip(("A", "B"), TRIALS)
        ],
    }


def _acceptance_binding(
    *,
    catalogs: dict[str, Any],
    scenario: str,
    experiment_shape: dict[str, Any],
    parser_inventory: dict[str, Any],
    required_dependency_ids: tuple[str, ...],
    execution_closure_fingerprint: str | None = None,
    required_domain_predicates: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Bind a review packet to the exact audit baseline it was issued for."""
    components = {
        "catalogBundleFingerprint": catalogs.get("bundleFingerprint"),
        "catalogPackageFileSha256": catalogs.get("files"),
        "scenario": scenario,
        "experimentShape": experiment_shape,
        "parserInventoryFingerprint": _canonical_hash(parser_inventory),
        "parserSourceFileSha256": parser_inventory.get("sourceFileSha256"),
        "requiredDependencyIds": list(required_dependency_ids),
        "executionClosureFingerprint": execution_closure_fingerprint,
        "requiredDomainPredicates": required_domain_predicates,
    }
    return {
        "schemaVersion": 1,
        **components,
        "scopeFingerprint": _canonical_hash(components),
    }


def _source_string_constants() -> set[str]:
    names: set[str] = set()
    modules = (
        "ti_parser_core.py",
        "ti_parser_income.py",
        "ti_parser_projection_adapter.py",
        "ti_parser_nation_projection.py",
        "ti_parser_topbar.py",
        "ti_parser_runtime.py",
    )
    for name in modules:
        tree = ast.parse((TOOLS / name).read_text(encoding="utf-8"), filename=name)
        names.update(
            node.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
        )
    return {value for value in names if SAFE_KEY.fullmatch(value)}


class ReadTracker:
    def __init__(self) -> None:
        self.stage_name = "adapter-preparation"
        self.events: Counter[tuple[str, str, str, str]] = Counter()
        self.escape_events: Counter[tuple[str, str, str]] = Counter()
        self.mutations = 0
        self.safe_keys = _source_string_constants() | STATIC_CATALOG_KEYS
        self.call_counts: Counter[tuple[str, str]] = Counter()
        self.read_consumers: dict[tuple[str, str, str, str], set[str]] = {}
        self.read_call_paths: dict[tuple[str, str, str, str], set[tuple[str, ...]]] = {}
        self.active_trial: ReadTracker | None = None
        self.rule_executions: list[dict[str, Any]] = []
        self.execution_result: dict[str, Any] = {}
        self.runtime_rule_reference_events: dict[str, dict[str, Any]] = {}
        self.runtime_dependency_edge_events: dict[str, dict[str, Any]] = {}
        self.runtime_helper_execution_events: dict[str, dict[str, Any]] = {}
        self.rule_reference_trace_installed = False

    def _record_runtime_event(self, field: str, row: dict[str, Any]) -> None:
        key = json.dumps(row, sort_keys=True, separators=(",", ":"))
        events = getattr(self, field)
        if key not in events:
            events[key] = {**row, "count": 0}
        events[key]["count"] += 1

    def record_rule_reference(self, row: dict[str, Any]) -> None:
        sinks = [self]
        if self.active_trial is not None and self.active_trial is not self:
            sinks.append(self.active_trial)
        for sink in sinks:
            sink._record_runtime_event("runtime_rule_reference_events", row)

    def record_dependency_edge(self, row: dict[str, Any]) -> None:
        sinks = [self]
        if self.active_trial is not None and self.active_trial is not self:
            sinks.append(self.active_trial)
        for sink in sinks:
            sink._record_runtime_event("runtime_dependency_edge_events", row)

    def record_helper_execution(self, row: dict[str, Any]) -> None:
        sinks = [self]
        if self.active_trial is not None and self.active_trial is not self:
            sinks.append(self.active_trial)
        for sink in sinks:
            sink._record_runtime_event("runtime_helper_execution_events", row)

    def safe_path(self, path: str) -> str:
        return path or "$"

    def child_path(self, parent: str, key: Any) -> str:
        if isinstance(key, str) and key in {"gamestates"} and parent in {"", "$"}:
            label = key
        elif isinstance(key, str) and key in self.safe_keys:
            label = key
        else:
            label = "{key}"
        return f"{parent or '$'}.{label}"

    def item_path(self, parent: str, index: Any = None) -> str:
        return f"{parent or '$'}[*]"

    def record(self, path: str, operation: str, container: str) -> None:
        if self.active_trial is not None:
            self.active_trial.stage_name = self.stage_name
            self.active_trial.record(path, operation, container)
        category = "catalog" if path.startswith("$.catalogs") else "save"
        event_key = (self.safe_path(path), self.stage_name, operation, f"{category}-{container}")
        self.events[event_key] += 1
        consumers = self.read_consumers.setdefault(event_key, set())
        frame = sys._getframe(1)
        call_path = []
        # Retain the helper and caller chain: required-field helpers receive keys
        # as parameters, while the literal source evidence lives at the caller.
        for _ in range(12):
            if frame is None:
                break
            module = str(frame.f_globals.get("__name__", ""))
            if module.startswith("ti_parser_"):
                consumer = f"{module}.{frame.f_code.co_name}"
                consumers.add(consumer)
                call_path.append(consumer)
            frame = frame.f_back
        self.read_call_paths.setdefault(event_key, set()).add(tuple(call_path))

    def escape(self, path: str, operation: str, container: str) -> None:
        if self.active_trial is not None:
            self.active_trial.escape(path, operation, container)
        self.escape_events[(self.safe_path(path), operation, container)] += 1

    @contextmanager
    def stage(self, name: str) -> Iterator[None]:
        previous = self.stage_name
        self.stage_name = name
        try:
            yield
        finally:
            self.stage_name = previous

    def report(self) -> dict[str, Any]:
        reads = [
            {
                "path": path,
                "stage": stage,
                "operation": operation,
                "container": container,
                "count": count,
                "classification": "unresolved",
                "consumers": sorted(self.read_consumers.get((path, stage, operation, container), set())),
                "callPathsNearestConsumerFirst": [list(chain) for chain in sorted(self.read_call_paths.get((path, stage, operation, container), set()))],
            }
            for (path, stage, operation, container), count in sorted(self.events.items())
        ]
        escapes = [
            {"path": path, "operation": operation, "container": container, "count": count}
            for (path, operation, container), count in sorted(self.escape_events.items())
        ]
        return {
            "stages": sorted({row["stage"] for row in reads}),
            "classificationDefault": "unresolved",
            "reads": reads,
            "plainContainerEscapes": escapes,
            "rawContainerMutationCount": self.mutations,
            "runtimeRuleReferences": list(self.runtime_rule_reference_events.values()),
            "runtimeDependencyEdges": list(self.runtime_dependency_edge_events.values()),
            "runtimeHelperExecutions": list(self.runtime_helper_execution_events.values()),
        }


class TracedDict(dict):
    """A dict-compatible save wrapper that records structural read operations."""

    def __init__(self, tracker: ReadTracker, path: str) -> None:
        dict.__init__(self)
        self._tracker = tracker
        self._path = path

    def __getitem__(self, key: Any) -> Any:
        self._tracker.record(self._tracker.child_path(self._path, key), "item", "dict")
        return dict.__getitem__(self, key)

    def get(self, key: Any, default: Any = None) -> Any:
        self._tracker.record(self._tracker.child_path(self._path, key), "get", "dict")
        return dict.get(self, key, default)

    def __contains__(self, key: object) -> bool:
        self._tracker.record(self._tracker.child_path(self._path, key), "contains", "dict")
        return dict.__contains__(self, key)

    def __iter__(self) -> Iterator[Any]:
        self._tracker.record(self._path, "iterate-keys", "dict")
        return dict.__iter__(self)

    def __len__(self) -> int:
        self._tracker.record(self._path, "length", "dict")
        return dict.__len__(self)

    def keys(self):
        self._tracker.record(self._path, "keys", "dict")
        for key in dict.__iter__(self):
            self._tracker.record(self._tracker.child_path(self._path, key), "key-yield", "dict")
            yield key

    def values(self):
        self._tracker.record(self._path, "values", "dict")
        for key, value in dict.items(self):
            self._tracker.record(self._tracker.child_path(self._path, key), "value-yield", "dict")
            yield value

    def items(self):
        self._tracker.record(self._path, "items", "dict")
        for key, value in dict.items(self):
            self._tracker.record(self._tracker.child_path(self._path, key), "item-yield", "dict")
            yield key, value

    def copy(self) -> dict:
        self._tracker.record(self._path, "copy", "dict")
        self._tracker.escape(self._path, "dict.copy", "dict")
        return dict.copy(self)

    def __copy__(self) -> dict:
        self._tracker.record(self._path, "copy", "dict")
        self._tracker.escape(self._path, "copy.copy", "dict")
        return dict.copy(self)

    def __deepcopy__(self, memo: dict[int, Any]) -> "TracedDict":
        self._tracker.record(self._path, "deepcopy", "dict")
        existing = memo.get(id(self))
        if existing is not None:
            return existing
        duplicate = TracedDict(self._tracker, self._path)
        memo[id(self)] = duplicate
        for key, value in dict.items(self):
            child_path = self._tracker.child_path(self._path, key)
            self._tracker.record(child_path, "deepcopy-materialize", "dict")
            dict.__setitem__(duplicate, copy.deepcopy(key, memo), copy.deepcopy(value, memo))
        return duplicate

    def __eq__(self, other: object) -> bool:
        self._tracker.record(self._path, "compare", "dict")
        return dict.__eq__(self, other)

    def __setitem__(self, key: Any, value: Any) -> None:
        self._tracker.mutations += 1
        self._tracker.record(self._tracker.child_path(self._path, key), "write-item", "dict")
        dict.__setitem__(self, key, value)

    def setdefault(self, key: Any, default: Any = None) -> Any:
        self._tracker.mutations += 1
        self._tracker.record(self._tracker.child_path(self._path, key), "write-setdefault", "dict")
        return dict.setdefault(self, key, default)

    def update(self, *args: Any, **kwargs: Any) -> None:
        self._tracker.mutations += 1
        self._tracker.record(self._path, "write-update", "dict")
        dict.update(self, *args, **kwargs)


class TracedList(list):
    """A list-compatible save wrapper that records structural read operations."""

    def __init__(self, tracker: ReadTracker, path: str) -> None:
        list.__init__(self)
        self._tracker = tracker
        self._path = path

    def __getitem__(self, index: Any) -> Any:
        operation = "slice" if isinstance(index, slice) else "item"
        self._tracker.record(self._tracker.item_path(self._path), operation, "list")
        return list.__getitem__(self, index)

    def __iter__(self) -> Iterator[Any]:
        self._tracker.record(self._path, "iterate", "list")
        for item in list.__iter__(self):
            self._tracker.record(self._tracker.item_path(self._path), "iterate-yield", "list")
            yield item

    def __len__(self) -> int:
        self._tracker.record(self._path, "length", "list")
        return list.__len__(self)

    def __contains__(self, value: object) -> bool:
        self._tracker.record(self._path, "contains", "list")
        return list.__contains__(self, value)

    def copy(self) -> list:
        self._tracker.record(self._path, "copy", "list")
        self._tracker.escape(self._path, "list.copy", "list")
        return list.copy(self)

    def __copy__(self) -> list:
        self._tracker.record(self._path, "copy", "list")
        self._tracker.escape(self._path, "copy.copy", "list")
        return list.copy(self)

    def __deepcopy__(self, memo: dict[int, Any]) -> "TracedList":
        self._tracker.record(self._path, "deepcopy", "list")
        existing = memo.get(id(self))
        if existing is not None:
            return existing
        duplicate = TracedList(self._tracker, self._path)
        memo[id(self)] = duplicate
        for item in list.__iter__(self):
            self._tracker.record(self._tracker.item_path(self._path), "deepcopy-materialize", "list")
            list.append(duplicate, copy.deepcopy(item, memo))
        return duplicate

    def __setitem__(self, index: Any, value: Any) -> None:
        self._tracker.mutations += 1
        self._tracker.record(self._tracker.item_path(self._path), "write-item", "list")
        list.__setitem__(self, index, value)

    def append(self, value: Any) -> None:
        self._tracker.mutations += 1
        self._tracker.record(self._path, "write-append", "list")
        list.append(self, value)


def traced_copy(value: Any, tracker: ReadTracker, *, root_path: str = "$") -> Any:
    memo: dict[int, Any] = {}

    def wrap(item: Any, path: str = "$") -> Any:
        if not isinstance(item, (dict, list)):
            return item
        existing = memo.get(id(item))
        if existing is not None:
            return existing
        if isinstance(item, dict):
            result: Any = TracedDict(tracker, path)
            memo[id(item)] = result
            for key, child in dict.items(item):
                child_path = tracker.child_path(path, key)
                dict.__setitem__(result, key, wrap(child, child_path))
            return result
        result = TracedList(tracker, path)
        memo[id(item)] = result
        for child in list.__iter__(item):
            list.append(result, wrap(child, tracker.item_path(path)))
        return result

    return wrap(value, root_path)


@contextmanager
def _instrument_catalog_reads(tracker: ReadTracker) -> Iterator[None]:
    """Wrap decoded catalog payloads while retaining their public object APIs."""

    original_loader = runtime_layer.load_runtime_catalogs
    original_module_loader = topbar_layer.load_hab_module_catalog
    runtime_wrappers: dict[int, RuntimeCatalogs] = {}
    module_wrappers: dict[int, dict[str, Any]] = {}

    def traced_loader(*args: Any, **kwargs: Any) -> RuntimeCatalogs:
        loaded = original_loader(*args, **kwargs)
        key = id(loaded)
        if key not in runtime_wrappers:
            wrapped = RuntimeCatalogs(
                scenario=loaded.scenario,
                catalogs={},
                envelopes=loaded.envelopes,
                manifest=loaded.manifest,
                data_dir=loaded.data_dir,
            )
            wrapped.catalogs = traced_copy(loaded.catalogs, tracker, root_path="$.catalogs")
            runtime_wrappers[key] = wrapped
        return runtime_wrappers[key]

    def traced_module_loader(*args: Any, **kwargs: Any) -> dict[str, Any]:
        loaded = original_module_loader(*args, **kwargs)
        key = id(loaded)
        if key not in module_wrappers:
            module_wrappers[key] = traced_copy(
                loaded,
                tracker,
                root_path="$.catalogs.module_catalog",
            )
        return module_wrappers[key]

    runtime_layer.load_runtime_catalogs = traced_loader
    topbar_layer.load_hab_module_catalog = traced_module_loader
    try:
        with runtime_catalog_scope():
            yield
    finally:
        runtime_layer.load_runtime_catalogs = original_loader
        topbar_layer.load_hab_module_catalog = original_module_loader


def _catalog_snapshot() -> dict[str, Any]:
    data_dir = ROOT / "data"
    manifest = json.loads((data_dir / "catalog_manifest.json").read_text(encoding="utf-8"))
    # Loading all standard runtime catalogs validates the package files before
    # the run. Projection itself adds the scenario development catalog.
    RuntimeCatalogs.load(SCENARIO)
    return {
        "bundleFingerprint": manifest.get("bundleFingerprint"),
        "files": {
            path.name: file_sha256(path)
            for path in sorted(data_dir.glob("*.json"))
        },
    }


def _packaged_assembly_hash() -> str | None:
    catalogs = RuntimeCatalogs.load(SCENARIO, catalog_files=("nation_development_catalog.json",))
    sources = catalogs.envelopes["nation_development"].get("sourceFiles", [])
    for source in sources:
        if (
            isinstance(source, dict)
            and isinstance(source.get("name"), str)
            and source["name"].endswith("Assembly-CSharp.dll")
        ):
            value = source.get("sha256")
            return value if isinstance(value, str) else None
    return None


def _assembly_hash_status(provided_hash: str | None, packaged_hash: str | None) -> str:
    if provided_hash is None:
        return "not_provided"
    if packaged_hash is None:
        return "source_hash_missing"
    return "match" if provided_hash == packaged_hash else "mismatch"


def _state_identity(data: dict[str, Any], nation_name: str | None, faction_name: str | None) -> tuple[str, str | None, list[int], bool]:
    indexed = core.build_index(data)
    scenario = core.scenario_template_name(indexed)
    if scenario != SCENARIO:
        raise AuditInputError("The selected save must name ModernScenario")

    player_id, player_faction = core.find_faction_state(indexed, None)
    faction_id, resolved_faction = (
        core.find_faction_state(indexed, faction_name)
        if faction_name is not None
        else (player_id, player_faction)
    )
    if faction_id != player_id:
        raise AuditInputError("The selected faction must be the resolved player faction")

    if nation_name is None:
        candidates: list[tuple[str, bool]] = []
        for entry in core.type_entries(indexed, "TINationState"):
            nation = entry.get("Value") or {}
            name = nation.get("templateName") or nation.get("displayName")
            if not isinstance(name, str):
                continue
            refs = nation.get("controlPoints")
            points = income.nation_control_points(indexed, nation)
            if not isinstance(refs, list) or len(points) != len(refs):
                continue
            if not points or not nation.get("regions"):
                continue
            owned = faction_id is not None and all(
                core.ref_id(point.get("faction")) == faction_id for point in points
            )
            candidates.append((name, owned))
        fully_owned = [name for name, owned in candidates if owned]
        if len(fully_owned) != 1:
            raise AuditInputError(
                "The explicit save needs --nation when it has no unique fully faction-owned nation"
            )
        nation_name = fully_owned[0]
    found = core.match_raw_state(indexed, "TINationState", nation_name)
    if not found or found[0] is None or not isinstance(found[1], dict):
        raise AuditInputError("The selected nation is absent from the save")
    nation_id, nation = found
    if faction_name is None and faction_id is not None:
        faction_name = str(resolved_faction.get("templateName") or resolved_faction.get("displayName") or "")
    refs = nation.get("controlPoints")
    points = income.nation_control_points(indexed, nation)
    if not isinstance(refs, list) or len(points) != len(refs):
        raise AuditInputError("Every selected nation control-point reference must resolve")
    positions = [point.get("positionInNation") for point in points]
    if not positions or any(type(value) is not int for value in positions) or len(set(positions)) != len(positions):
        raise AuditInputError("The selected nation needs distinct saved control-point positions")
    fully_owned = all(core.ref_id(point.get("faction")) == player_id for point in points)
    if not fully_owned:
        raise AuditInputError("Every selected nation control point must be owned by the resolved player faction")
    if len(positions) != 6:
        raise AuditInputError("The bounded projection audit requires exactly six control points")
    return str(nation_name), faction_name, sorted(positions), fully_owned


def _plan(name: str, positions: list[int], knowledge: int, welfare: int) -> dict[str, Any]:
    return {
        "plans": [
            {
                "name": name,
                "segments": [
                    {
                        "controlPoints": [
                            {"position": position, "pips": {"Knowledge": knowledge, "Welfare": welfare}}
                            for position in positions
                        ],
                        "advisors": [],
                    }
                ],
            }
        ]
    }


@contextmanager
def _profile_calls(tracker: ReadTracker):
    old_profile = sys.getprofile()
    active_helpers: dict[int, dict[str, Any]] = {}

    def tool_location(frame: Any, line: int) -> dict[str, Any] | None:
        path = Path(frame.f_code.co_filename).resolve()
        try:
            relative = path.relative_to(ROOT).as_posix()
        except ValueError:
            return None
        if not relative.startswith("tools/"):
            return None
        return {"file": relative, "line": line, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}

    def profile(frame, event, arg):
        if event == "call":
            module = str(frame.f_globals.get("__name__", ""))
            if module.startswith("ti_parser_"):
                tracker.call_counts[(module, frame.f_code.co_name)] += 1
                if tracker.active_trial is not None:
                    tracker.active_trial.call_counts[(module, frame.f_code.co_name)] += 1
                helper_name = frame.f_code.co_name
                rule_ids = EXECUTION_HELPER_RULE_BINDINGS.get(helper_name)
                if module == "ti_parser_nation_projection" and rule_ids:
                    caller = frame.f_back
                    callsite = tool_location(caller, caller.f_lineno) if caller is not None else None
                    caller_module = str(caller.f_globals.get("__name__", "")) if caller is not None else ""
                    caller_consumer = f"{caller_module}.{caller.f_code.co_name}" if caller is not None else None
                    call_context = source_control_flow_context(
                        TOOLS, caller_module,
                        caller.f_code.co_name if caller is not None else "", caller.f_lineno if caller is not None else -1,
                        "call", helper_name,
                    ) if caller is not None and caller_module.startswith("ti_parser_") else {"sourceMapped": False}
                    helper_location = tool_location(frame, frame.f_code.co_firstlineno)
                    active_helpers[id(frame)] = {
                        "helper": helper_name,
                        "helperRuleIds": list(rule_ids),
                        "stage": tracker.stage_name,
                        "caller": caller_consumer,
                        "callSite": callsite,
                        "callSiteContext": call_context,
                        "helperSourceLocation": helper_location,
                        "callPathNearestConsumerFirst": [
                            f"{frame.f_globals.get('__name__', '')}.{frame.f_code.co_name}",
                            *([caller_consumer] if caller_consumer else []),
                        ],
                    }
        elif event == "return":
            helper = active_helpers.pop(id(frame), None)
            if helper is not None:
                module = str(frame.f_globals.get("__name__", ""))
                return_location = tool_location(frame, frame.f_lineno)
                return_context = source_control_flow_context(
                    TOOLS, module, frame.f_code.co_name,
                    frame.f_lineno, "return",
                )
                numeric = isinstance(arg, (int, float)) and not isinstance(arg, bool)
                finite = numeric and math.isfinite(arg)
                helper.update({
                    "returnSite": return_context,
                    "observedReturnLocation": return_location,
                    "returnedNormallyWithFiniteNumber": bool(finite),
                    "returnKind": "finite-number" if finite else "non-finite-number" if numeric else "non-numeric-or-exception",
                    "returnValueRecorded": False,
                    "coverageClaim": "none",
                })
                tracker.record_helper_execution(helper)
        if old_profile is not None:
            old_profile(frame, event, arg)

    sys.setprofile(profile)
    try:
        yield
    finally:
        sys.setprofile(old_profile)


class _TracedRuleNamespace:
    """Transparent temporary proxy that records evaluated ``Rules.X`` accesses."""

    def __init__(self, rules: Any, tracker: ReadTracker, append_sites: set[tuple[str, str, int, str]]) -> None:
        self._rules = rules
        self._tracker = tracker
        self._append_sites = append_sites

    def __getattr__(self, name: str) -> Any:
        value = getattr(self._rules, name)
        identifier = getattr(value, "id", None)
        frame = sys._getframe(1)
        module = str(frame.f_globals.get("__name__", ""))
        if isinstance(identifier, str) and module.startswith("ti_parser_"):
            path = Path(frame.f_code.co_filename).resolve()
            try:
                relative = path.relative_to(ROOT).as_posix()
            except ValueError:
                relative = ""
            if relative.startswith("tools/"):
                location = {"file": relative, "line": frame.f_lineno,
                            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                call_path = []
                caller = frame
                for _ in range(12):
                    if caller is None:
                        break
                    caller_module = str(caller.f_globals.get("__name__", ""))
                    if caller_module.startswith("ti_parser_"):
                        call_path.append(f"{caller_module}.{caller.f_code.co_name}")
                    caller = caller.f_back
                consumer = f"{module}.{frame.f_code.co_name}"
                source_context = source_control_flow_context(
                    TOOLS, module, frame.f_code.co_name, frame.f_lineno,
                    "rule-reference", name,
                )
                self._tracker.record_rule_reference({
                    "ruleId": identifier,
                    "ruleName": name,
                    "consumer": consumer,
                    "sourceLocation": location,
                    "sourceControlFlow": source_context,
                    "stage": self._tracker.stage_name,
                    "callPathNearestConsumerFirst": call_path,
                })

                source_site = (module, frame.f_code.co_name, frame.f_lineno)
                execution = frame.f_locals.get("execution")
                parent_id = execution.get("ruleId") if isinstance(execution, dict) else None
                append_site = (*source_site, name)
                if append_site in self._append_sites and isinstance(parent_id, str):
                    self._tracker.record_dependency_edge({
                        "from": parent_id,
                        "to": identifier,
                        "ruleName": name,
                        "module": module,
                        "function": frame.f_code.co_name,
                        "consumer": consumer,
                        "sourceLocation": location,
                        "sourceControlFlow": source_context,
                        "stage": self._tracker.stage_name,
                        "callPathNearestConsumerFirst": call_path,
                    })
        return value


@contextmanager
def _instrument_rule_references(tracker: ReadTracker):
    """Trace actual rule attribute reads and dynamic dependency appends temporarily."""
    append_sites = {(row["module"], row["function"], row["line"], row["ruleName"])
                    for row in dependency_append_sites(TOOLS)}
    proxy = _TracedRuleNamespace(Rules, tracker, append_sites)
    patched: list[tuple[Any, Any]] = []
    for module in tuple(sys.modules.values()):
        if module is None or not str(getattr(module, "__name__", "")).startswith("ti_parser_"):
            continue
        namespace = vars(module)
        if namespace.get("Rules") is Rules:
            patched.append((module, Rules))
            namespace["Rules"] = proxy
    tracker.rule_reference_trace_installed = True
    if tracker.active_trial is not None:
        tracker.active_trial.rule_reference_trace_installed = True
    try:
        yield
    finally:
        for module, original in patched:
            vars(module)["Rules"] = original


def _run_traced(indexed: core.IndexedState, tracker: ReadTracker, nation: str, faction: str | None, plan: dict[str, Any]) -> dict[str, Any]:
    output = projection.projection_output
    run = projection.run_projection

    def staged_output(*args: Any, **kwargs: Any) -> dict[str, Any]:
        with tracker.stage("projection-output"):
            return output(*args, **kwargs)

    def staged_run(*args: Any, **kwargs: Any) -> dict[str, Any]:
        # Capture the original full return before public output processing. Do
        # not change details, diagnostics, transactions, or calculator inputs.
        with tracker.stage("projection-calculation"):
            result = run(*args, **kwargs)
        sink = tracker.active_trial or tracker
        sink.rule_executions.extend(copy.deepcopy(result.get("ruleExecutions", [])))
        sink.execution_result = {key: copy.deepcopy(result.get(key)) for key in
                                 ("status", "coverage", "metricCoverage", "runtimeStop", "missingMechanicRules", "missingDependencies")}
        return result

    with _instrument_rule_references(tracker), _profile_calls(tracker):
        projection.projection_output = staged_output
        projection.run_projection = staged_run
        try:
            with tracker.stage("adapter-preparation"):
                return parser.calculate_nation_projection(
                    indexed,
                    nation,
                    faction,
                    plan,
                    days=DAYS,
                    checkpoints=CHECKPOINTS,
                    details=False,
                    diagnostics=False,
                )
        finally:
            projection.projection_output = output
            projection.run_projection = run


def _run_plain(indexed: core.IndexedState, nation: str, faction: str | None, plan: dict[str, Any]) -> dict[str, Any]:
    return parser.calculate_nation_projection(
        indexed,
        nation,
        faction,
        plan,
        days=DAYS,
        checkpoints=CHECKPOINTS,
        details=False,
        diagnostics=False,
    )


def _comparison_row(baseline: dict[str, Any], traced: dict[str, Any]) -> dict[str, Any]:
    baseline_plan = (baseline.get("plans") or [{}])[0]
    traced_plan = (traced.get("plans") or [{}])[0]
    return {
        "exactNormalizedResultEqual": canonical_json_bytes(baseline) == canonical_json_bytes(traced),
        "baselineResultSha256": _canonical_hash(baseline),
        "tracedResultSha256": _canonical_hash(traced),
        "topLevelCoverageEqual": baseline.get("coverage") == traced.get("coverage"),
        "planCoverageEqual": baseline_plan.get("coverage") == traced_plan.get("coverage"),
        "statusEqual": baseline_plan.get("status") == traced_plan.get("status"),
        "baselineStatus": baseline_plan.get("status"),
        "tracedStatus": traced_plan.get("status"),
    }


def _static_checklist(tracker: ReadTracker) -> dict[str, Any]:
    call_rows = []
    for module, function, stage in STATIC_CALL_CHECKLIST:
        call_rows.append(
            {
                "module": module,
                "function": function,
                "stage": stage,
                "observed": tracker.call_counts[(module, function)] > 0,
                "callCount": tracker.call_counts[(module, function)],
            }
        )
    inventory = source_inventory(TOOLS, tracker.call_counts)
    reconciliation = reconcile(inventory, tracker.report()["reads"])
    unresolved_mappings = [
        {"sourcePattern": source, "destinationCategory": destination, "status": "unresolved"}
        for source, destination in STATIC_MAPPING_CHECKLIST
    ]
    for row in unresolved_mappings:
        matching = [dependency for dependency in inventory["dependencies"]
                    if dependency["mappingStatus"] == "mapped" and dependency["sourceKey"] in row["sourcePattern"]]
        if matching:
            row.update(status="mapped", sourceEvidence=[dependency["sourceLocation"] for dependency in matching],
                       destinationRoles=sorted({dependency["destinationRole"] for dependency in matching}),
                       visibilityCategory="unresolved")
    missing_calls = sum(not row["observed"] for row in call_rows)
    unresolved_escapes = sum(tracker.escape_events.values())
    complete = (missing_calls == 0 and all(row["status"] == "mapped" for row in unresolved_mappings)
                and unresolved_escapes == 0 and reconciliation["complete"]
                and not inventory["normalizationBoundaries"])
    return {
        "requiredRuntimeCheckpoints": call_rows,
        "normalizationMappings": unresolved_mappings,
        "sourceDerivedDependencies": inventory,
        "dynamicStaticReconciliation": reconciliation,
        "unresolvedPlainContainerEscapes": unresolved_escapes,
        "complete": complete,
        "status": "complete" if complete else "incomplete",
        "reason": "Plain derived containers require source-to-output mapping before a complete read trace can be claimed.",
    }


def _policy_status(
    *, structural_complete: bool, assembly_status: str,
    provided_hash: str | None, packaged_hash: str | None,
    evidence: dict[str, Any] | None = None,
    required_dependency_ids: tuple[str, ...] = (), scope_fingerprint: str | None = None,
) -> dict[str, Any]:
    """Fail closed even when every structural gate passes.

    This is a decision function, not an authority-evidence generator. Accepted
    evidence must explicitly cover source authority, build applicability, and
    every dependency's permitted visibility. Hash equality alone proves none
    of those properties. Live audit runs currently supply no accepted evidence.
    """
    evidence = evidence if isinstance(evidence, dict) else {}
    source = evidence.get("sourceAuthority")
    applicability = evidence.get("buildApplicability")
    visibility = evidence.get("visibility")
    source = source if isinstance(source, dict) else {}
    applicability = applicability if isinstance(applicability, dict) else {}
    visibility = visibility if isinstance(visibility, dict) else {}
    valid_hash = lambda value: isinstance(value, str) and bool(re.fullmatch(r"[0-9a-f]{64}", value))
    valid_references = lambda value: isinstance(value, list) and bool(value) and all(isinstance(item, str) and bool(item.strip()) for item in value)
    source_accepted = (source.get("status") == "accepted"
                       and isinstance(source.get("authorityKind"), str)
                       and source.get("authorityKind") in {"game-dll", "game-source"}
                       and valid_hash(source.get("sha256"))
                       and source.get("sha256") == provided_hash
                       and valid_references(source.get("evidenceReferences")))
    build_accepted = (applicability.get("status") == "accepted"
                      and applicability.get("providedSha256") == provided_hash
                      and applicability.get("packagedSha256") == packaged_hash
                      and valid_references(applicability.get("evidenceReferences")))
    dependencies = visibility.get("dependencies")
    dependency_ids = [row.get("dependencyId") for row in dependencies if isinstance(row, dict)] if isinstance(dependencies, list) else []
    required_ids_valid = (isinstance(required_dependency_ids, tuple) and bool(required_dependency_ids)
                          and all(isinstance(value, str) and bool(value.strip()) for value in required_dependency_ids)
                          and len(set(required_dependency_ids)) == len(required_dependency_ids))
    inventory_bound = (required_ids_valid and valid_hash(scope_fingerprint)
                       and visibility.get("scopeFingerprint") == scope_fingerprint
                       and len(dependency_ids) == len(required_dependency_ids)
                       and all(isinstance(value, str) for value in dependency_ids)
                       and set(dependency_ids) == set(required_dependency_ids))
    allowed_categories = {"player-visible", "player-owned", "globally-public", "intel-gated"}
    visibility_accepted = (visibility.get("status") == "accepted"
                           and visibility.get("allDependenciesClassified") is True
                           and visibility.get("dynamicStaticReconciled") is True
                           and isinstance(dependencies, list) and bool(dependencies)
                           and inventory_bound
                           and all(isinstance(row, dict) and row.get("status") == "accepted"
                                   and isinstance(row.get("category"), str)
                                   and row.get("category") in allowed_categories
                                   and row.get("providedSha256") == provided_hash
                                   and row.get("packagedSha256") == packaged_hash
                                   and valid_references(row.get("evidenceReferences"))
                                   and (row.get("category") != "intel-gated" or row.get("intelGateSatisfied") is True)
                                   for row in dependencies))
    gates = {
        "structuralComplete": structural_complete is True,
        "assemblyProvided": valid_hash(provided_hash),
        "packagedSourceHashPresent": valid_hash(packaged_hash),
        "assemblyHashMatches": assembly_status == "match" and provided_hash == packaged_hash,
        "sourceAuthorityAccepted": source_accepted,
        "buildApplicabilityAccepted": build_accepted,
        "visibilityAccepted": visibility_accepted,
    }
    accepted = all(gates.values())
    return {
        "buildSourceAuthorityStatus": {"status": "accepted" if all(gates[key] for key in ("assemblyProvided", "packagedSourceHashPresent", "assemblyHashMatches", "sourceAuthorityAccepted", "buildApplicabilityAccepted")) else "unresolved", "gates": {key: value for key, value in gates.items() if key not in {"structuralComplete", "visibilityAccepted"}}},
        "visibilityStatus": {"status": "accepted" if visibility_accepted else "unresolved", "classificationDefault": "unresolved"},
        "policyEligibility": {"status": "accepted" if accepted else "not_approved", "eligible": accepted, "gates": gates},
        "exitCode": 0 if accepted else 2,
    }


def audit_projection_reads(
    *,
    data: dict[str, Any],
    input_kind: str,
    nation_name: str | None,
    faction_name: str | None,
    assembly_path: Path | None = None,
) -> tuple[dict[str, Any], int]:
    before_input = _canonical_hash(data)
    baseline_index = core.build_index(data)
    resolved_nation, resolved_faction, positions, fully_owned = _state_identity(
        data, nation_name, faction_name
    )
    catalogs_before = _catalog_snapshot()
    expected_assembly = _packaged_assembly_hash()
    supplied_assembly = file_sha256(assembly_path) if assembly_path is not None else None
    assembly_status = _assembly_hash_status(supplied_assembly, expected_assembly)

    tracker = ReadTracker()
    traced_data = traced_copy(data, tracker)
    preflight_tracker = ReadTracker()
    preflight_data = traced_copy(data, preflight_tracker)
    with preflight_tracker.stage("target-resolution-preflight"), _profile_calls(preflight_tracker):
        traced_identity = _state_identity(preflight_data, nation_name, faction_name)
    if traced_identity != (resolved_nation, resolved_faction, positions, fully_owned):
        raise AuditInputError("Target resolution changed under developer tracing")
    traced_index = core.build_index(traced_data)
    alias_checks = {
        "dataGamestatesPreserved": traced_index.data["gamestates"] is traced_index.gamestates,
        "idIndexValuesAliasSaveRows": all(
            traced_index.id_index[state_id][2] is row["Value"]
            for entries in traced_index.gamestates.values()
            for row in entries
            for state_id in [core.raw_state_id(row)]
            if state_id is not None
        ),
    }

    baseline_results: dict[str, dict[str, Any]] = {}
    traced_results: dict[str, dict[str, Any]] = {}
    trial_trackers: dict[str, ReadTracker] = {}
    for trial_name, knowledge, welfare in TRIALS:
        payload = _plan(trial_name, positions, knowledge, welfare)
        baseline_results[trial_name] = _run_plain(baseline_index, resolved_nation, resolved_faction, payload)
    with _instrument_catalog_reads(tracker):
        for trial_name, knowledge, welfare in TRIALS:
            payload = _plan(trial_name, positions, knowledge, welfare)
            trial_trackers[trial_name] = ReadTracker()
            tracker.active_trial = trial_trackers[trial_name]
            try:
                traced_results[trial_name] = _run_traced(
                    traced_index, tracker, resolved_nation, resolved_faction, payload,
                )
            finally:
                tracker.active_trial = None
    comparisons = {
        trial_name: _comparison_row(baseline_results[trial_name], traced_results[trial_name])
        for trial_name, _knowledge, _welfare in TRIALS
    }

    after_input = _canonical_hash(data)
    catalogs_after = _catalog_snapshot()
    unchanged = before_input == after_input
    catalogs_unchanged = catalogs_before == catalogs_after
    parity = all(
        row["exactNormalizedResultEqual"]
        and row["topLevelCoverageEqual"]
        and row["planCoverageEqual"]
        and row["statusEqual"]
        for row in comparisons.values()
    )
    static = _static_checklist(tracker)
    required_predicates = _canonical_acceptance_shape()
    required_predicates.update(inputKind=input_kind, controlPointCount=len(positions),
                               fullyOwnedBySelectedFaction=fully_owned)
    closures = {}
    for name, trial_tracker in trial_trackers.items():
        source = rule_source_inventory(TOOLS, trial_tracker.call_counts, Rules)
        closures[name] = execution_closure(trial_tracker.rule_executions, source, REGISTRY,
                                          required_predicates=required_predicates,
                                          runtime_rule_references=(
                                              list(trial_tracker.runtime_rule_reference_events.values())
                                              if trial_tracker.rule_reference_trace_installed else None
                                          ),
                                          runtime_dependency_edges=(
                                              list(trial_tracker.runtime_dependency_edge_events.values())
                                              if trial_tracker.rule_reference_trace_installed else None
                                          ),
                                          runtime_helper_executions=(
                                              list(trial_tracker.runtime_helper_execution_events.values())
                                              if trial_tracker.rule_reference_trace_installed else None
                                          ),
                                          helper_rule_bindings=EXECUTION_HELPER_RULE_BINDINGS)
        closures[name]["authoritativeExecutionResult"] = trial_tracker.execution_result
    closure_report = {"trials": closures, "requiredDomainPredicates": required_predicates,
                      "complete": all(row["complete"] for row in closures.values()),
                      "lineageStatus": "unresolved",
                      "reason": "Rule closure is parser execution evidence; scalar lineage, preparation reads and game visibility require separate acceptance."}
    current_review = review_evidence(ROOT, supplied_assembly, expected_assembly,
                                    set().union(*(set(row["closureRuleIds"]) for row in closures.values())))
    closure_report["reviewEvidenceSha256"] = current_review["evidenceSha256"]
    closure_report["currentBuildReviewStatus"] = current_review["status"]
    closure_report["fingerprint"] = _canonical_hash(closure_report)
    gates = {
        "exactResultCoverageAndStatusParity": parity,
        "dataGamestatesAliasPreserved": alias_checks["dataGamestatesPreserved"],
        "idIndexRowAliasesPreserved": alias_checks["idIndexValuesAliasSaveRows"],
        "inputUnchanged": unchanged,
        "catalogsUnchanged": catalogs_unchanged,
        "zeroRawContainerMutations": tracker.mutations == 0,
        "staticCallChecklistComplete": static["complete"],
        "executionClosureComplete": closure_report["complete"],
    }
    structural_status = "complete" if all(gates.values()) else "incomplete"
    required_dependency_ids = tuple(sorted({
        row["dependencyId"]
        for row in static["sourceDerivedDependencies"]["dependencies"]
    }))
    experiment_shape = _canonical_acceptance_shape()
    experiment_shape.update(
        inputKind=input_kind,
        controlPointCount=len(positions),
        fullyOwnedBySelectedFaction=fully_owned,
    )
    acceptance_binding = _acceptance_binding(
        catalogs=catalogs_before,
        scenario=SCENARIO,
        experiment_shape=experiment_shape,
        parser_inventory=static["sourceDerivedDependencies"],
        required_dependency_ids=required_dependency_ids,
        execution_closure_fingerprint=closure_report["fingerprint"],
        required_domain_predicates=required_predicates,
    )
    policy = _policy_status(structural_complete=structural_status == "complete",
                            assembly_status=assembly_status, provided_hash=supplied_assembly,
                            packaged_hash=expected_assembly,
                            required_dependency_ids=required_dependency_ids,
                            scope_fingerprint=acceptance_binding["scopeFingerprint"])
    report = {
        "schemaVersion": 1,
        "tool": "audit_projection_reads",
        "input": {
            "kind": input_kind,
            "scenario": SCENARIO,
            "sha256Before": before_input,
            "sha256After": after_input,
            "unchanged": unchanged,
            "fullyOwnedBySelectedFaction": fully_owned,
            "controlPointCount": len(positions),
        },
        "experiment": {
            "days": DAYS,
            "checkpoints": CHECKPOINTS,
            "everyControlPoint": True,
            "segmentCount": 1,
            "advisorCount": 0,
            "details": False,
            "diagnostics": False,
            "trials": {
                name: {"Knowledge": knowledge, "Welfare": welfare}
                for name, knowledge, welfare in TRIALS
            },
        },
        "comparison": {
            "baselineVersusTraced": comparisons,
            "allTrialsExactAndCoverageEqual": parity,
            "buildIndexAliases": alias_checks,
        },
        "catalogs": {
            "scenario": SCENARIO,
            "bundleFingerprint": catalogs_before["bundleFingerprint"],
            "packageFileSha256": catalogs_before["files"],
            "unchanged": catalogs_unchanged,
            "catalogObjectsWrapped": True,
            "instrumentation": {
                "runtimeCatalogPayloads": "wrapped after package validation and scenario selection",
                "habModuleCatalogPayloads": "wrapped after package load",
                "locationCatalogPayloads": "not read by this call configuration",
                "fileDecodeAndManifestValidation": "unwrapped and explicitly blocking",
            },
        },
        "dynamicReads": tracker.report(),
        "trialReads": {name: trial_tracker.report() for name, trial_tracker in trial_trackers.items()},
        "preflightReads": preflight_tracker.report(),
        "executionClosure": closure_report,
        "currentBuildReview": current_review,
        "staticCallChecklist": static,
        "acceptanceBinding": acceptance_binding,
        "structuralStatus": {
            "status": structural_status,
            "completeTraceClaim": structural_status == "complete",
            "rawReadClassificationDefault": "unresolved",
            "gates": gates,
        },
        "authorityStatus": {
            "status": "unresolved",
            "assemblyHashComparison": assembly_status,
            "packagedSourceSha256": expected_assembly,
            "providedAssemblySha256": supplied_assembly,
            "visibilityClassification": "unresolved",
            "packageBuildIdentityMatches": assembly_status == "match",
        },
        "buildSourceAuthorityStatus": policy["buildSourceAuthorityStatus"],
        "visibilityStatus": policy["visibilityStatus"],
        "policyEligibility": policy["policyEligibility"],
    }
    exit_code = policy["exitCode"]
    return report, exit_code


def _validate_output_path(path: Path) -> Path:
    resolved = path.resolve()
    if any(part.lower() in BLOCKED_OUTPUT_PARTS for part in resolved.parts):
        raise AuditInputError("The explicit report path must be outside incidental cache directories")
    return resolved


def main(argv: list[str] | None = None) -> int:
    argument_parser = argparse.ArgumentParser(description=__doc__)
    argument_parser.add_argument("--save", type=Path, help="explicit .gz save; omit to use the controlled fixture")
    argument_parser.add_argument("--nation", help="nation template/display name for an explicit save")
    argument_parser.add_argument("--faction", help="faction template/display name for an explicit save")
    argument_parser.add_argument("--assembly-path", type=Path, help="explicit Assembly-CSharp.dll for source hash comparison")
    argument_parser.add_argument("--output", type=Path, required=True, help="explicit JSON report path outside incidental caches")
    args = argument_parser.parse_args(argv)
    try:
        output_path = _validate_output_path(args.output)
        if args.save is None:
            data = _load_fixture()
            input_kind = "controlled-synthetic-fixture"
        else:
            data = parser.load_save(args.save)
            input_kind = "explicit-save"
        if args.assembly_path is not None and not args.assembly_path.is_file():
            raise AuditInputError("The explicitly supplied assembly path is not a file")
        report, exit_code = audit_projection_reads(
            data=data,
            input_kind=input_kind,
            nation_name=args.nation,
            faction_name=args.faction,
            assembly_path=args.assembly_path,
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"report": str(output_path), "structuralStatus": report["structuralStatus"]["status"],
                          "assemblyHashComparison": report["authorityStatus"]["assemblyHashComparison"],
                          "authorityStatus": report["authorityStatus"]["status"],
                          "buildSourceAuthorityStatus": report["buildSourceAuthorityStatus"]["status"],
                          "visibilityStatus": report["visibilityStatus"]["status"],
                          "policyEligibility": report["policyEligibility"]["status"],
                          "readPathCount": len(report["dynamicReads"]["reads"])}, ensure_ascii=False))
        return exit_code
    except Exception as exc:
        print(f"projection read audit failed: {type(exc).__name__}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
