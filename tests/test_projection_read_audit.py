from __future__ import annotations

import copy
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import audit_projection_reads as audit
from projection_audit_dependencies import reconcile, source_inventory
from collections import Counter
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

    data = audit._load_fixture()
    data["gamestates"]["TINationState"][0]["Value"]["controlPoints"].pop()
    with pytest.raises(audit.AuditInputError, match="exactly six control points"):
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
    assert any(read["callPathsNearestConsumerFirst"] and read["consumers"] for read in report["dynamicReads"]["reads"])
    assert report["policyEligibility"]["status"] == "not_approved"
    assert report["buildSourceAuthorityStatus"]["status"] == "unresolved"
    assert report["visibilityStatus"]["status"] == "unresolved"
    inventory = report["staticCallChecklist"]["sourceDerivedDependencies"]
    assert {row["sourceKey"] for row in inventory["dependencies"] if row["mappingStatus"] == "mapped"} >= {
        "controlPointPriorities", "diversityBonus", "_accumulatedInvestmentPoints", "publicOpinion", "resourceMarketValues",
    }
    assert all(row["visibilityCategory"] == "unresolved" for row in inventory["dependencies"])
    assert inventory["sourceFileSha256"]
    assert inventory["normalizationBoundaries"]
    reconciliation = report["staticCallChecklist"]["dynamicStaticReconciliation"]
    assert reconciliation["mappedDynamicReadCount"] > 0
    assert reconciliation["unresolvedDynamicReadCount"] > 0
    assert reconciliation["complete"] is False


def _accepted_policy_evidence(digest):
    # Decision-function fixture only: no claim of live game-source acceptance.
    return {
        "sourceAuthority": {"status": "accepted", "authorityKind": "game-dll", "sha256": digest,
                            "evidenceReferences": ["unit-test accepted source review"]},
        "buildApplicability": {"status": "accepted", "providedSha256": digest, "packagedSha256": digest,
                               "evidenceReferences": ["unit-test accepted build review"]},
        "visibility": {"status": "accepted", "allDependenciesClassified": True, "dynamicStaticReconciled": True,
                       "scopeFingerprint": "c" * 64,
                       "dependencies": [{"dependencyId": "unit-test-dependency", "providedSha256": digest, "packagedSha256": digest,
                                         "status": "accepted", "category": "player-visible",
                                         "evidenceReferences": ["unit-test accepted visibility review"]}]},
    }


def _policy_decision(**kwargs):
    kwargs.setdefault("required_dependency_ids", ("unit-test-dependency",))
    kwargs.setdefault("scope_fingerprint", "c" * 64)
    return audit._policy_status(**kwargs)


@pytest.mark.parametrize("assembly_status,provided,packaged", [
    ("not_provided", None, "a" * 64),
    ("source_hash_missing", "a" * 64, None),
    ("mismatch", "b" * 64, "a" * 64),
    ("match", "a" * 64, "a" * 64),
    ("match", None, None),
])
def test_structural_complete_never_approves_absent_or_unreviewed_authority(assembly_status, provided, packaged):
    result = _policy_decision(structural_complete=True, assembly_status=assembly_status,
                                 provided_hash=provided, packaged_hash=packaged)
    assert result["exitCode"] == 2
    assert result["policyEligibility"]["eligible"] is False


@pytest.mark.parametrize("section", ["sourceAuthority", "buildApplicability", "visibility"])
@pytest.mark.parametrize("status", ["absent", "unresolved", "mismatch", "rejected"])
def test_each_authority_gate_blocks_even_with_structural_parity(section, status):
    digest = "a" * 64
    evidence = _accepted_policy_evidence(digest)
    evidence[section]["status"] = status
    result = _policy_decision(structural_complete=True, assembly_status="match",
                                 provided_hash=digest, packaged_hash=digest, evidence=evidence)
    assert result["exitCode"] == 2
    assert result["policyEligibility"]["status"] == "not_approved"


def test_explicit_accepted_evidence_is_required_for_all_gate_decision_success():
    digest = "a" * 64
    evidence = _accepted_policy_evidence(digest)
    result = _policy_decision(structural_complete=True, assembly_status="match",
                                 provided_hash=digest, packaged_hash=digest, evidence=evidence)
    assert result["exitCode"] == 0
    assert all(result["policyEligibility"]["gates"].values())
    assert result["visibilityStatus"]["status"] == "accepted"
    assert _policy_decision(structural_complete=False, assembly_status="match", provided_hash=digest,
                                packaged_hash=digest, evidence=evidence)["exitCode"] == 2


@pytest.mark.parametrize("category", ["hidden", "unresolved", "invented", "intel-gated"])
def test_hidden_unknown_or_unproven_intel_visibility_blocks(category):
    digest = "a" * 64
    evidence = _accepted_policy_evidence(digest)
    evidence["visibility"]["dependencies"][0]["category"] = category
    assert _policy_decision(structural_complete=True, assembly_status="match", provided_hash=digest,
                                packaged_hash=digest, evidence=evidence)["exitCode"] == 2


@pytest.mark.parametrize("case", ["missing", "extra", "duplicate", "foreign-source", "foreign-package", "foreign-scope", "empty-reference", "string-reference", "truthy-structural", "malformed-status", "malformed-category", "missing-required-scope"])
def test_accepted_review_must_bind_exact_inventory_and_source(case):
    digest = "a" * 64
    evidence = _accepted_policy_evidence(digest)
    kwargs = dict(structural_complete=True, assembly_status="match", provided_hash=digest, packaged_hash=digest, evidence=evidence)
    visibility = evidence["visibility"]
    row = visibility["dependencies"][0]
    if case == "missing":
        visibility["dependencies"] = []
    elif case == "extra":
        visibility["dependencies"].append(dict(row, dependencyId="extra"))
    elif case == "duplicate":
        visibility["dependencies"].append(dict(row))
    elif case == "foreign-source":
        row["providedSha256"] = "b" * 64
    elif case == "foreign-package":
        row["packagedSha256"] = "b" * 64
    elif case == "foreign-scope":
        visibility["scopeFingerprint"] = "b" * 64
    elif case == "empty-reference":
        evidence["sourceAuthority"]["evidenceReferences"] = [""]
    elif case == "string-reference":
        evidence["buildApplicability"]["evidenceReferences"] = "review"
    elif case == "truthy-structural":
        kwargs["structural_complete"] = "complete"
    elif case == "malformed-status":
        row["status"] = {"status": "accepted"}
    elif case == "malformed-category":
        row["category"] = ["player-visible"]
    elif case == "missing-required-scope":
        kwargs["required_dependency_ids"] = ()
    assert _policy_decision(**kwargs)["exitCode"] == 2


def test_source_dependency_mapping_hashes_locations_and_unknown_reads_fail_closed():
    inventory = source_inventory(ROOT / "tools", Counter({("ti_parser_projection_adapter", "extract_nation_projection_state"): 1}))
    dependency = next(row for row in inventory["dependencies"] if row["sourceKey"] == "publicOpinion")
    assert dependency["destinationRole"] == "NationProjectionState.public_opinion"
    assert dependency["destinationLocations"]
    assert dependency["sourceLocation"]["sha256"] == audit.file_sha256(ROOT / dependency["sourceLocation"]["file"])
    consumer = dependency["consumer"]
    reconciled = reconcile(inventory, [
        {"path": "$.gamestates.TINationState[*].Value.publicOpinion", "consumers": [consumer], "stage": "adapter-preparation", "operation": "get"},
        {"path": "$.gamestates.TINationState[*].Value.newUnclassifiedField", "consumers": [consumer], "stage": "adapter-preparation", "operation": "get"},
    ])
    assert reconciled["mappedDynamicReadCount"] == 1
    assert reconciled["unresolvedDynamicReadCount"] == 1
    assert reconciled["complete"] is False


def test_scalar_helper_wiring_is_mapped_separately_from_visibility():
    inventory = source_inventory(ROOT / "tools", Counter({("ti_parser_projection_adapter", "extract_nation_projection_state"): 1}))
    dependency = next(row for row in inventory["dependencies"] if row["sourceKey"] == "inequality")
    assert dependency["destinationRole"] == "NationProjectionState.inequality"
    assert dependency["mappingStatus"] == "mapped"
    assert dependency["visibilityCategory"] == "unresolved"
    assert dependency["blocking"] is True


def test_plain_constructor_comprehension_slice_and_normalization_boundaries_remain_explicit():
    tracker = audit.ReadTracker()
    traced = audit.traced_copy({"rows": [{"value": 1}, {"value": 2}], "numbers": {"one": 2.5}}, tracker)
    plain_dict = dict(traced)
    plain_list = list(traced["rows"])
    sliced = traced["rows"][:1]
    comprehension = [row["value"] for row in traced["rows"]]
    normalized = _normalise_mapping(traced["numbers"])
    assert plain_dict["rows"] is traced["rows"]
    assert plain_list[0] is sliced[0] is traced["rows"][0]
    assert comprehension == [1, 2]
    assert normalized == {"one": 2.5}
    assert not isinstance(plain_dict, audit.TracedDict)
    assert not isinstance(plain_list, audit.TracedList)
    inventory = source_inventory(ROOT / "tools", Counter({("ti_parser_projection_adapter", "extract_nation_projection_state"): 1}))
    operations = {row["operation"] for row in inventory["normalizationBoundaries"]}
    assert {"DictComp", "ListComp", "dict", "float", "int", "as_float"} <= operations
    # Observed operations preserve nested wrappers, but materialized scalars and
    # ordinary outer containers do not become a complete trace by that fact.
    assert reconcile(inventory, tracker.report()["reads"])["complete"] is False


def test_index_row_alias_and_shallow_copy_preserve_nested_identity_but_block_unmapped_escape():
    tracker = audit.ReadTracker()
    data = audit.traced_copy(audit._load_fixture(), tracker)
    indexed = audit.core.build_index(data)
    nation_row = indexed.gamestates["TINationState"][0]
    nation_id = audit.core.raw_state_id(nation_row)
    assert indexed.id_index[nation_id][2] is nation_row["Value"]
    shallow = copy.copy(nation_row)
    assert shallow["Value"] is nation_row["Value"]
    assert audit._static_checklist(tracker)["unresolvedPlainContainerEscapes"] == 1
    assert audit._static_checklist(tracker)["complete"] is False
