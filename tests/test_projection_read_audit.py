from __future__ import annotations

import copy
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import audit_projection_reads as audit
from ti_parser_catalogs import RuntimeCatalogs


def _normalise_mapping(raw):
    return {str(key): float(value) for key, value in raw.items()}


def test_traced_containers_record_common_reads_and_normalization_without_values():
    shared = {"value": 2.5}
    raw = {
        "first": shared,
        "second": shared,
        "rows": [{"value": 1}, {"value": 2}, {"value": 3}],
        "numbers": {"one": 1, "two": 2},
        "private-map-key": {"value": "private-marker"},
    }
    tracker = audit.ReadTracker()
    traced = audit.traced_copy(raw, tracker)

    assert traced.get("first") is traced["second"]
    assert traced["rows"][0]["value"] == 1
    assert [row["value"] for row in traced["rows"][:2]] == [1, 2]
    assert _normalise_mapping(traced["numbers"]) == {"one": 1.0, "two": 2.0}
    assert dict(traced)["first"] is traced["first"]
    assert list(traced["rows"])[1]["value"] == 2
    assert {str(key): float(value) for key, value in traced["numbers"].items()} == {
        "one": 1.0,
        "two": 2.0,
    }
    shallow = copy.copy(traced["first"])
    deep = copy.deepcopy(traced)
    assert type(shallow) is dict
    assert isinstance(deep, audit.TracedDict)
    assert deep["first"] is deep["second"]
    assert deep["rows"][2]["value"] == 3

    operations = {operation for _path, _stage, operation, _kind in tracker.events}
    assert {"get", "item", "iterate", "slice", "items", "item-yield", "deepcopy"} <= operations
    assert {operation for _path, operation, _kind in tracker.escape_events} == {"copy.copy"}
    encoded = json.dumps(tracker.report())
    assert "private-marker" not in encoded
    assert "private-map-key" not in encoded
    assert all(row["classification"] == "unresolved" for row in tracker.report()["reads"])


def test_runtime_catalog_source_hash_is_a_packaged_old_build_fingerprint():
    assert audit._packaged_assembly_hash() == "ff7916c2085ddbafa5acf1e8ea185d37e629096752be388ba6fa1f627f027bb5"
    catalogs = RuntimeCatalogs.load("ModernScenario", catalog_files=("nation_development_catalog.json",))
    assert catalogs.nation_development["nationTemplates"]["USA"]["dataName"] == "USA"


def test_explicit_assembly_hash_mismatch_does_not_certify_visibility(tmp_path):
    assembly_path = tmp_path / "explicit-assembly.dll"
    assembly_path.write_bytes(b"explicit test assembly bytes")

    status = audit._assembly_hash_status(
        audit.file_sha256(assembly_path),
        audit._packaged_assembly_hash(),
    )

    assert status == "mismatch"
    assert audit._assembly_hash_status(None, audit._packaged_assembly_hash()) == "not_provided"


def test_audit_target_must_be_unique_fully_player_owned_and_resolved():
    data = audit._load_fixture()
    faction_row = {
        "Key": {"value": 99},
        "Value": {"ID": {"value": 99}, "templateName": "AcademyCouncil", "displayName": "Academy"},
    }
    data["gamestates"]["TIFactionState"].append(faction_row)
    with pytest.raises(audit.AuditInputError, match="resolved player faction"):
        audit._state_identity(data, "USA", "AcademyCouncil")

    data = audit._load_fixture()
    data["gamestates"]["TINationState"][0]["Value"]["controlPoints"].append({"value": 999})
    with pytest.raises(audit.AuditInputError, match="reference must resolve"):
        audit._state_identity(data, "USA", None)

    data = audit._load_fixture()
    data["gamestates"]["TIControlPointState"][-1]["Value"]["faction"] = {"value": 999}
    with pytest.raises(audit.AuditInputError, match="must be owned by the resolved player faction"):
        audit._state_identity(data, "USA", None)


def test_audit_runs_both_180_day_trials_with_real_catalogs_and_exact_trace_parity(tmp_path):
    assembly_path = tmp_path / "explicit-assembly.dll"
    assembly_path.write_bytes(b"explicit test assembly bytes")
    report, exit_code = audit.audit_projection_reads(
        data=audit._load_fixture(),
        input_kind="controlled-synthetic-fixture",
        nation_name=None,
        faction_name=None,
        assembly_path=assembly_path,
    )

    assert exit_code == 2
    assert report["experiment"]["days"] == 180
    assert report["experiment"]["advisorCount"] == 0
    assert report["experiment"]["details"] is False
    assert report["experiment"]["diagnostics"] is False
    assert report["input"]["fullyOwnedBySelectedFaction"] is True
    assert report["comparison"]["allTrialsExactAndCoverageEqual"] is True
    assert report["comparison"]["buildIndexAliases"] == {
        "dataGamestatesPreserved": True,
        "idIndexValuesAliasSaveRows": True,
    }
    assert {row["baselineStatus"] for row in report["comparison"]["baselineVersusTraced"].values()} == {"complete"}
    assert report["catalogs"]["unchanged"] is True
    assert report["catalogs"]["catalogObjectsWrapped"] is True
    assert report["catalogs"]["instrumentation"]["fileDecodeAndManifestValidation"] == "unwrapped and explicitly blocking"
    assert report["staticCallChecklist"]["status"] == "incomplete"
    assert all(
        checkpoint["observed"]
        for checkpoint in report["staticCallChecklist"]["requiredRuntimeCheckpoints"]
    )
    assert {row["function"] for row in report["staticCallChecklist"]["requiredRuntimeCheckpoints"]} >= {
        "councilor_summary_maps",
        "projection_advisor_profiles",
        "calculate_topbar",
    }
    assert any("type_index/id_index" in row["sourcePattern"] for row in report["staticCallChecklist"]["normalizationMappings"])
    assert report["structuralStatus"]["status"] == "incomplete"
    assert report["authorityStatus"]["assemblyHashComparison"] == "mismatch"
    assert report["authorityStatus"]["status"] == "unresolved"
    assert report["authorityStatus"]["packageBuildIdentityMatches"] is False
    assert report["authorityStatus"]["visibilityClassification"] == "unresolved"
    assert report["structuralStatus"]["gates"]["idIndexRowAliasesPreserved"] is True
    assert report["structuralStatus"]["gates"]["zeroRawContainerMutations"] is True
    assert {read["stage"] for read in report["dynamicReads"]["reads"]} == {
        "adapter-preparation",
        "projection-execution-output",
    }
    assert all(read["classification"] == "unresolved" for read in report["dynamicReads"]["reads"])
    assert any(read["container"].startswith("catalog-") for read in report["dynamicReads"]["reads"])
