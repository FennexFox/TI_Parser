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
from ti_parser_catalogs import RuntimeCatalogs, canonical_json_bytes, file_sha256, runtime_catalog_scope


SCENARIO = "ModernScenario"
DAYS = 180
CHECKPOINTS = [30, 90, 180]
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
        category = "catalog" if path.startswith("$.catalogs") else "save"
        self.events[(self.safe_path(path), self.stage_name, operation, f"{category}-{container}")] += 1

    def escape(self, path: str, operation: str, container: str) -> None:
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
            }
            for (path, stage, operation, container), count in sorted(self.events.items())
        ]
        escapes = [
            {"path": path, "operation": operation, "container": container, "count": count}
            for (path, operation, container), count in sorted(self.escape_events.items())
        ]
        return {
            "stages": ["adapter-preparation", "projection-execution-output"],
            "classificationDefault": "unresolved",
            "reads": reads,
            "plainContainerEscapes": escapes,
            "rawContainerMutationCount": self.mutations,
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

    def profile(frame, event, _arg):
        if event == "call":
            module = str(frame.f_globals.get("__name__", ""))
            if module.startswith("ti_parser_"):
                tracker.call_counts[(module, frame.f_code.co_name)] += 1
        if old_profile is not None:
            old_profile(frame, event, _arg)

    sys.setprofile(profile)
    try:
        yield
    finally:
        sys.setprofile(old_profile)


def _run_traced(indexed: core.IndexedState, tracker: ReadTracker, nation: str, faction: str | None, plan: dict[str, Any]) -> dict[str, Any]:
    output = projection.projection_output

    def staged_output(*args: Any, **kwargs: Any) -> dict[str, Any]:
        with tracker.stage("projection-execution-output"):
            return output(*args, **kwargs)

    with _profile_calls(tracker):
        projection.projection_output = staged_output
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
    unresolved_mappings = [
        {"sourcePattern": source, "destinationCategory": destination, "status": "unresolved"}
        for source, destination in STATIC_MAPPING_CHECKLIST
    ]
    missing_calls = sum(not row["observed"] for row in call_rows)
    unresolved_escapes = sum(row["count"] for row in tracker.escape_events.values())
    complete = missing_calls == 0 and not unresolved_mappings and unresolved_escapes == 0
    return {
        "requiredRuntimeCheckpoints": call_rows,
        "normalizationMappings": unresolved_mappings,
        "unresolvedPlainContainerEscapes": unresolved_escapes,
        "complete": complete,
        "status": "complete" if complete else "incomplete",
        "reason": "Plain derived containers require source-to-output mapping before a complete read trace can be claimed.",
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

    trials = (
        ("knowledge3_welfare1", 3, 1),
        ("welfare3_knowledge1", 1, 3),
    )
    tracker = ReadTracker()
    traced_data = traced_copy(data, tracker)
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
    for trial_name, knowledge, welfare in trials:
        payload = _plan(trial_name, positions, knowledge, welfare)
        baseline_results[trial_name] = _run_plain(baseline_index, resolved_nation, resolved_faction, payload)
    with _instrument_catalog_reads(tracker):
        for trial_name, knowledge, welfare in trials:
            payload = _plan(trial_name, positions, knowledge, welfare)
            traced_results[trial_name] = _run_traced(
                traced_index,
                tracker,
                resolved_nation,
                resolved_faction,
                payload,
            )
    comparisons = {
        trial_name: _comparison_row(baseline_results[trial_name], traced_results[trial_name])
        for trial_name, _knowledge, _welfare in trials
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
    gates = {
        "exactResultCoverageAndStatusParity": parity,
        "dataGamestatesAliasPreserved": alias_checks["dataGamestatesPreserved"],
        "idIndexRowAliasesPreserved": alias_checks["idIndexValuesAliasSaveRows"],
        "inputUnchanged": unchanged,
        "catalogsUnchanged": catalogs_unchanged,
        "zeroRawContainerMutations": tracker.mutations == 0,
        "staticCallChecklistComplete": static["complete"],
    }
    structural_status = "complete" if all(gates.values()) else "incomplete"
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
            "advisorCount": 0,
            "details": False,
            "diagnostics": False,
            "trials": {
                name: {"Knowledge": knowledge, "Welfare": welfare}
                for name, knowledge, welfare in trials
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
        "staticCallChecklist": static,
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
    }
    exit_code = 0 if structural_status == "complete" and assembly_status != "mismatch" else 2
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
        print(json.dumps({"report": str(output_path), "structuralStatus": report["structuralStatus"]["status"], "authorityStatus": report["authorityStatus"]["assemblyHashComparison"], "readPathCount": len(report["dynamicReads"]["reads"])}, ensure_ascii=False))
        return exit_code
    except Exception as exc:
        print(f"projection read audit failed: {type(exc).__name__}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
