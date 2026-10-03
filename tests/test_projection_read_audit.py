from __future__ import annotations

import copy
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import audit_projection_reads as audit
from projection_audit_dependencies import execution_closure, reconcile, source_inventory
from projection_audit_dependencies import dependency_append_sites, source_control_flow_context
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


def test_runtime_catalog_source_hash_is_the_current_packaged_build_fingerprint():
    assert audit._packaged_assembly_hash() == "4a4b9aae4154e444e9727204205d2d42ae8ed9e1c5f92cdc1280074a259d8350"
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
    assert report["experiment"]["checkpoints"] == [0, 180]
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
        "projection-calculation",
        "projection-output",
    }
    assert all(read["classification"] == "unresolved" for read in report["dynamicReads"]["reads"])
    assert any(read["container"].startswith("catalog-") for read in report["dynamicReads"]["reads"])
    assert any(read["callPathsNearestConsumerFirst"] and read["consumers"] for read in report["dynamicReads"]["reads"])
    assert report["policyEligibility"]["status"] == "not_approved"
    assert report["buildSourceAuthorityStatus"]["status"] == "unresolved"
    assert report["visibilityStatus"]["status"] == "unresolved"
    inventory = report["staticCallChecklist"]["sourceDerivedDependencies"]
    binding = report["acceptanceBinding"]
    assert binding["catalogBundleFingerprint"] == report["catalogs"]["bundleFingerprint"]
    assert binding["catalogPackageFileSha256"] == report["catalogs"]["packageFileSha256"]
    assert binding["scenario"] == "ModernScenario"
    assert binding["experimentShape"] == audit._canonical_acceptance_shape()
    assert binding["parserInventoryFingerprint"] == audit._canonical_hash(inventory)
    assert binding["parserSourceFileSha256"] == inventory["sourceFileSha256"]
    assert binding["requiredDependencyIds"] == sorted({row["dependencyId"] for row in inventory["dependencies"]})
    binding_components = {
        key: value for key, value in binding.items()
        if key not in {"schemaVersion", "scopeFingerprint"}
    }
    assert binding["scopeFingerprint"] == audit._canonical_hash(binding_components)
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
    assert {row["stage"] for row in report["preflightReads"]["reads"]} == {"target-resolution-preflight"}
    closure = report["executionClosure"]
    assert closure["complete"] is False
    assert report["structuralStatus"]["gates"]["executionClosureComplete"] is False
    assert binding["executionClosureFingerprint"] == closure["fingerprint"]
    assert binding["requiredDomainPredicates"] == closure["requiredDomainPredicates"]
    assert set(report["trialReads"]) == {name for name, _k, _w in audit.TRIALS}
    assert all(report["trialReads"][name]["reads"] for name in report["trialReads"])
    for name, trial in closure["trials"].items():
        assert trial["authoritativeExecutionResult"]["status"] == report["comparison"]["baselineVersusTraced"][name]["baselineStatus"]
        assert trial["authoritativeExecutionResult"]["runtimeStop"] is None
        assert "nation.priority.knowledge.complete" in trial["executedRuleIds"]
        assert "nation.priority.welfare.complete" in trial["executedRuleIds"]
        assert trial["executionRecordCount"] > len(trial["executedRuleIds"])
        assert trial["blockers"]
        welfare_edges = [row for row in trial["runtimeDependencyEdges"]
                         if row["from"] == "nation.priority.welfare.complete"
                         and row["to"] == "nation.priority.welfare.inequality"]
        assert welfare_edges
        assert all(row["sourceControlFlow"]["sourceMapped"] for row in welfare_edges)
        assert all(row["sourceControlFlow"]["siteKind"] == "rule-reference" for row in welfare_edges)
        expected_helpers = {
            "_base_ip": "nation.ip.base",
            "_annual_population_growth": "nation.population.annual-growth",
            "_live_cohesion_rest": "nation.periodic.cohesion",
            "_live_unrest_rest": "nation.periodic.unrest",
        }
        calculation_helpers = [row for row in trial["sourceBoundHelperExecutions"]
                               if row["stage"] == "projection-calculation"]
        for helper_name, rule_id in expected_helpers.items():
            events = [row for row in calculation_helpers if row["helper"] == helper_name]
            assert events
            assert all(row["sourceBound"] is True for row in events)
            assert all(row["coverageClaim"] == "none" and row["returnValueRecorded"] is False for row in events)
            assert all(row["callSiteContext"]["sourceMapped"] and row["returnSite"]["sourceMapped"]
                       for row in events)
            edge = next(row for row in trial["runtimeDependencyEdgeEvidence"]
                        if row["to"] == rule_id)
            assert edge["status"] == "helper-invocation-returned"
            assert any(row["helper"] == helper_name for row in edge["returnedHelperEvidence"])
            assert rule_id not in trial["executedRuleIds"]


def _closure_source(*edges, references=()):
    return {"registeredLiteralEdges": [{"from": p, "to": c} for p, c in edges],
            "ruleReferences": list(references), "sourceFileSha256": {}}


def test_execution_closure_preserves_transitive_edges_and_blocks_unknown_rules_and_missing_records():
    result = execution_closure(
        [{"ruleId": "a", "dependencies": ["b"]}, {"ruleId": "b", "dependencies": ["unknown"]}],
        _closure_source(("a", "b")), {"a": object(), "b": object()}, required_predicates={"days": 180},
    )
    assert result["executedRuleIds"] == ["a", "b"]
    assert result["closureRuleIds"] == ["a", "b", "unknown"]
    assert result["transitiveDependencies"]["a"] == ["b", "unknown"]
    assert {row["kind"] for row in result["blockers"]} == {
        "unknown-rule", "unreconciled-dynamic-edge", "dependency-not-recorded",
    }
    assert result["complete"] is False


def test_execution_closure_blocks_cycles_and_unrecorded_conditional_rules():
    branch = {"ruleId": "branch", "consumer": "test.consumer", "sourceLocation": {"line": 3},
              "branchContext": [{"line": 2, "predicate": "state.colony", "arm": "body", "outcome": "unproven"}]}
    result = execution_closure(
        [{"ruleId": "a", "dependencies": ["b"]}, {"ruleId": "b", "dependencies": ["a"]}],
        _closure_source(("a", "b"), ("b", "a"), references=[branch]),
        {name: object() for name in ("a", "b", "branch")}, required_predicates={"colony": False},
    )
    assert result["complete"] is False
    assert {row["kind"] for row in result["blockers"]} == {"dependency-cycle", "unexplained-static-path"}
    assert result["unrecordedStaticRuleReferences"] == [branch]


def test_execution_closure_fingerprint_binds_edges_and_required_predicates():
    source = _closure_source(("a", "b"))
    executions = [{"ruleId": "a", "dependencies": ["b"]}, {"ruleId": "b", "dependencies": []}]
    first = execution_closure(executions, source, {"a": 1, "b": 1}, required_predicates={"days": 180})
    changed = execution_closure(executions, source, {"a": 1, "b": 1}, required_predicates={"days": 181})
    assert first["complete"] is True
    assert first["fingerprint"] != changed["fingerprint"]


def test_rule_reference_only_does_not_resolve_missing_dependency_execution():
    location = {"file": "tools/ti_parser_example.py", "line": 5, "sha256": "a" * 64}
    source = {
        "registeredLiteralEdges": [{"from": "parent", "to": "child", "consumer": "ti_parser_example.calculate",
                                     "sourceLocation": location, "branchContext": []}],
        "ruleReferences": [{"ruleId": "child", "consumer": "ti_parser_example.calculate",
                            "sourceLocation": location, "branchContext": []}],
        "dynamicDependencyAppendSites": [],
        "sourceFileSha256": {"tools/ti_parser_example.py": "a" * 64},
    }
    reference = {"ruleId": "child", "consumer": "ti_parser_example.calculate", "sourceLocation": location,
                 "stage": "projection-calculation", "callPathNearestConsumerFirst": ["ti_parser_example.calculate"]}

    result = execution_closure(
        [{"ruleId": "parent", "dependencies": ["child"]}], source, {"parent": 1, "child": 1},
        required_predicates={"days": 180}, runtime_rule_references=[reference], runtime_dependency_edges=[],
        runtime_helper_executions=[], helper_rule_bindings={},
    )

    assert result["executedRuleIds"] == ["parent"]
    assert "dependency-not-recorded" in {row["kind"] for row in result["blockers"]}
    assert result["runtimeDependencyEdgeEvidence"][0]["status"] == "rule-reference-observed"


def test_source_bound_returned_helper_call_resolves_only_its_static_dependency_edge():
    edge_location = {"file": "tools/ti_parser_example.py", "line": 5, "sha256": "a" * 64}
    helper_location = {"file": "tools/ti_parser_helper.py", "line": 10, "sha256": "b" * 64}
    source = {
        "registeredLiteralEdges": [{"from": "parent", "to": "child", "consumer": "ti_parser_example.calculate",
                                     "sourceLocation": edge_location, "branchContext": []}],
        "ruleReferences": [{"ruleId": "child", "consumer": "ti_parser_example.calculate",
                            "sourceLocation": edge_location, "branchContext": []}],
        "dynamicDependencyAppendSites": [],
        "sourceFileSha256": {"tools/ti_parser_example.py": "a" * 64,
                              "tools/ti_parser_helper.py": "b" * 64},
    }
    reference = {"ruleId": "child", "consumer": "ti_parser_example.calculate", "sourceLocation": edge_location,
                 "stage": "projection-calculation"}
    helper = {
        "helper": "calculate_child", "helperRuleIds": ["child"], "stage": "projection-calculation",
        "caller": "ti_parser_example.calculate", "helperSourceLocation": helper_location,
        "callSite": edge_location,
        "returnSite": {"sourceMapped": True, "sourceLocation": helper_location,
                       "siteKind": "return", "function": "calculate_child",
                       "branchContext": [{"predicate": "state.enabled", "arm": "body",
                                          "outcome": "observed-return-site"}],
                       "returnExpression": "state.value"},
        "observedReturnLocation": helper_location,
        "callSiteContext": {"sourceMapped": True, "siteKind": "call", "function": "calculate",
                            "calleeName": "calculate_child", "sourceLocation": edge_location,
                            "branchContext": []},
        "returnedNormallyWithFiniteNumber": True, "returnKind": "finite-number", "coverageClaim": "none",
    }

    result = execution_closure(
        [{"ruleId": "parent", "dependencies": ["child"]}], source, {"parent": 1, "child": 1},
        required_predicates={"days": 180}, runtime_rule_references=[reference], runtime_dependency_edges=[],
        runtime_helper_executions=[helper], helper_rule_bindings={"calculate_child": ("child",)},
    )

    assert result["complete"] is True
    assert result["executedRuleIds"] == ["parent"]
    assert result["runtimeDependencyEdgeEvidence"][0]["status"] == "helper-invocation-returned"
    assert result["runtimeDependencyEdgeEvidence"][0]["returnedHelperEvidence"][0]["coverageClaim"] == "none"


def test_helper_return_does_not_close_an_edge_from_another_callsite():
    edge_location = {"file": "tools/ti_parser_example.py", "line": 5, "sha256": "a" * 64}
    helper_location = {"file": "tools/ti_parser_helper.py", "line": 10, "sha256": "b" * 64}
    other_call_location = {"file": "tools/ti_parser_other.py", "line": 12, "sha256": "c" * 64}
    source = {
        "registeredLiteralEdges": [{"from": "parent", "to": "child", "consumer": "ti_parser_example.calculate",
                                     "sourceLocation": edge_location, "branchContext": []}],
        "ruleReferences": [], "dynamicDependencyAppendSites": [],
        "sourceFileSha256": {"tools/ti_parser_example.py": "a" * 64,
                              "tools/ti_parser_helper.py": "b" * 64,
                              "tools/ti_parser_other.py": "c" * 64},
    }
    helper = {
        "helper": "calculate_child", "helperRuleIds": ["child"], "stage": "projection-calculation",
        "caller": "ti_parser_example.calculate", "helperSourceLocation": helper_location,
        "callSite": other_call_location,
        "callSiteContext": {"sourceMapped": True, "siteKind": "call", "function": "calculate",
                            "calleeName": "calculate_child", "sourceLocation": other_call_location,
                            "branchContext": []},
        "returnSite": {"sourceMapped": True, "siteKind": "return", "function": "calculate_child",
                       "sourceLocation": helper_location, "branchContext": [],
                       "returnExpression": "state.value"},
        "observedReturnLocation": helper_location,
        "returnedNormallyWithFiniteNumber": True, "returnKind": "finite-number", "coverageClaim": "none",
    }

    result = execution_closure(
        [{"ruleId": "parent", "dependencies": ["child"]}], source, {"parent": 1, "child": 1},
        required_predicates={"days": 180}, runtime_rule_references=[], runtime_dependency_edges=[],
        runtime_helper_executions=[helper], helper_rule_bindings={"calculate_child": ("child",)},
    )

    assert "dependency-not-recorded" in {row["kind"] for row in result["blockers"]}
    assert result["runtimeDependencyEdgeEvidence"][0]["returnedHelperEvidence"] == []


def test_dynamic_dependency_append_is_edge_evidence_without_helper_execution_proof():
    location = {"file": "tools/ti_parser_example.py", "line": 9, "sha256": "c" * 64}
    source = {
        "registeredLiteralEdges": [],
        "ruleReferences": [{"ruleId": "child", "consumer": "ti_parser_example.calculate",
                            "sourceLocation": location, "branchContext": []}],
        "dynamicDependencyAppendSites": [{"module": "ti_parser_example", "function": "calculate", "ruleName": "CHILD", "line": 9,
                                           "sourceLocation": location}],
        "sourceFileSha256": {"tools/ti_parser_example.py": "c" * 64},
    }
    reference = {"ruleId": "child", "consumer": "ti_parser_example.calculate", "sourceLocation": location,
                 "stage": "projection-calculation"}
    edge = {"from": "parent", "to": "child", "ruleName": "CHILD", "module": "ti_parser_example", "function": "calculate",
            "consumer": "ti_parser_example.calculate", "sourceLocation": location,
            "sourceControlFlow": {"sourceMapped": True, "siteKind": "rule-reference", "function": "calculate",
                                  "calleeName": "CHILD", "sourceLocation": location, "branchContext": []},
            "stage": "projection-calculation"}

    result = execution_closure(
        [{"ruleId": "parent", "dependencies": ["child"]}], source, {"parent": 1, "child": 1},
        required_predicates={"days": 180}, runtime_rule_references=[reference], runtime_dependency_edges=[edge],
        runtime_helper_executions=[], helper_rule_bindings={},
    )

    kinds = {row["kind"] for row in result["blockers"]}
    assert "unreconciled-dynamic-edge" not in kinds
    assert "dependency-not-recorded" in kinds
    assert result["runtimeDependencyEdgeEvidence"][0]["status"] == "dynamic-source-edge-observed"


def test_dynamic_dependency_append_inventory_and_call_return_context_are_source_hashed(tmp_path):
    (tmp_path / "ti_parser_example.py").write_text(
        "def calculate(execution, state):\n"
        "    if state.enabled:\n"
        "        execution['dependencies'].append(Rules.CHILD.id)\n"
        "        return state.value\n",
        encoding="utf-8",
    )
    sites = dependency_append_sites(tmp_path)
    assert len(sites) == 1
    assert sites[0]["line"] == 3
    assert sites[0]["branchContext"] == [{"line": 2, "predicate": "state.enabled", "arm": "body",
                                           "outcome": "unproven"}]
    context = source_control_flow_context(tmp_path, "ti_parser_example", "calculate", 4, "return")
    assert context["sourceMapped"] is True
    assert context["siteKind"] == "return"
    assert context["function"] == "calculate"
    assert context["returnExpression"] == "state.value"
    assert context["branchContext"] == [{"line": 2, "predicate": "state.enabled", "arm": "body",
                                          "outcome": "observed-return-site"}]


def test_rule_reference_context_records_observed_branch_without_claiming_execution(tmp_path):
    (tmp_path / "ti_parser_example.py").write_text(
        "def calculate(state):\n"
        "    if state.enabled:\n"
        "        return Rules.CHILD.id\n",
        encoding="utf-8",
    )
    context = source_control_flow_context(tmp_path, "ti_parser_example", "calculate", 3,
                                          "rule-reference", "CHILD")
    assert context["sourceMapped"] is True
    assert context["siteKind"] == "rule-reference"
    assert context["function"] == "calculate"
    assert context["calleeName"] == "CHILD"
    assert context["branchContext"] == [{"line": 2, "predicate": "state.enabled", "arm": "body",
                                          "outcome": "observed-rule-reference"}]


def test_static_non_observation_keeps_branch_predicates_unproven(tmp_path):
    (tmp_path / "ti_parser_example.py").write_text(
        "def consumer(state):\n    if state.get('colony'):\n        return state.get('hiddenCounter')\n", encoding="utf-8",
    )
    inventory = source_inventory(tmp_path, Counter({("ti_parser_example", "consumer"): 1}))
    result = reconcile(inventory, [])
    hidden = next(row for row in result["staticCandidatesNotObserved"] if row["sourceKey"] == "hiddenCounter")
    assert hidden["branchContext"][0]["predicate"] == "state.get('colony')"
    assert hidden["branchContext"][0]["outcome"] == "unproven"
    assert hidden["blocking"] is True
    assert result["complete"] is False


def test_trial_trackers_do_not_merge_reads_from_the_other_trial():
    combined, first, second = audit.ReadTracker(), audit.ReadTracker(), audit.ReadTracker()
    combined.active_trial = first
    combined.record("$.firstField", "get", "dict")
    combined.active_trial = second
    combined.record("$.secondField", "get", "dict")
    combined.active_trial = None
    assert {row["path"] for row in first.report()["reads"]} == {"$.firstField"}
    assert {row["path"] for row in second.report()["reads"]} == {"$.secondField"}
    assert {row["path"] for row in combined.report()["reads"]} == {"$.firstField", "$.secondField"}


def test_developer_capture_preserves_incomplete_authoritative_prefix_and_details_false(monkeypatch):
    result = {"status": "incomplete", "ruleExecutions": [{"ruleId": "verified-prefix", "dependencies": []}],
              "runtimeStop": {"unsupportedNextStep": {"ruleId": "unexecuted-next-step"}},
              "coverage": {"complete": False}, "metricCoverage": {"prefix": "exact"}}
    calls = []

    def original_run(*args, **kwargs):
        calls.append(kwargs)
        return result

    def original_output(*args, **kwargs):
        return audit.projection.run_projection(details=kwargs["details"])

    def calculator(*args, **kwargs):
        return audit.projection.projection_output(details=kwargs["details"])

    monkeypatch.setattr(audit.projection, "run_projection", original_run)
    monkeypatch.setattr(audit.projection, "projection_output", original_output)
    monkeypatch.setattr(audit.parser, "calculate_nation_projection", calculator)
    tracker = audit.ReadTracker()
    captured = audit._run_traced(None, tracker, "A", "B", {})
    assert captured is result
    assert calls == [{"details": False}]
    assert tracker.rule_executions == result["ruleExecutions"]
    assert tracker.execution_result["runtimeStop"] == result["runtimeStop"]
    assert "unexecuted-next-step" not in {row["ruleId"] for row in tracker.rule_executions}
    assert audit.projection.run_projection is original_run
    assert audit.projection.projection_output is original_output


def test_live_audit_with_matching_assembly_still_requires_accepted_visibility_evidence(tmp_path, monkeypatch):
    assembly_path = tmp_path / "matching-assembly.dll"
    assembly_path.write_bytes(b"synthetic matching assembly bytes")
    digest = audit.file_sha256(assembly_path)
    monkeypatch.setattr(audit, "_packaged_assembly_hash", lambda: digest)

    report, exit_code = audit.audit_projection_reads(
        data=audit._load_fixture(),
        input_kind="controlled-synthetic-fixture",
        nation_name=None,
        faction_name=None,
        assembly_path=assembly_path,
    )

    assert report["authorityStatus"]["assemblyHashComparison"] == "match"
    assert report["authorityStatus"]["packageBuildIdentityMatches"] is True
    assert report["visibilityStatus"]["status"] == "unresolved"
    assert report["policyEligibility"]["status"] == "not_approved"
    assert exit_code == 2


def _accepted_policy_evidence(digest, *, scope_fingerprint="c" * 64, dependency_ids=("unit-test-dependency",)):
    # Decision-function fixture only: no claim of live game-source acceptance.
    return {
        "sourceAuthority": {"status": "accepted", "authorityKind": "game-dll", "sha256": digest,
                            "evidenceReferences": ["unit-test accepted source review"]},
        "buildApplicability": {"status": "accepted", "providedSha256": digest, "packagedSha256": digest,
                               "evidenceReferences": ["unit-test accepted build review"]},
        "visibility": {"status": "accepted", "allDependenciesClassified": True, "dynamicStaticReconciled": True,
                       "scopeFingerprint": scope_fingerprint,
                       "dependencies": [
                           {"dependencyId": dependency_id, "providedSha256": digest, "packagedSha256": digest,
                            "status": "accepted", "category": "player-visible",
                            "evidenceReferences": ["unit-test accepted visibility review"]}
                           for dependency_id in dependency_ids
                       ]},
    }


def _policy_decision(**kwargs):
    kwargs.setdefault("required_dependency_ids", ("unit-test-dependency",))
    kwargs.setdefault("scope_fingerprint", "c" * 64)
    return audit._policy_status(**kwargs)


def _acceptance_test_inputs():
    return {
        "catalogs": {
            "bundleFingerprint": "a" * 64,
            "files": {"runtime_catalog.json": "b" * 64},
        },
        "scenario": "ModernScenario",
        "experiment_shape": audit._canonical_acceptance_shape(),
        "parser_inventory": {
            "scope": {"scenario": "ModernScenario"},
            "sourceFileSha256": {"tools/ti_parser_core.py": "c" * 64},
            "dependencies": [{"dependencyId": "unit-test-dependency", "sourceLocation": {"sha256": "c" * 64}}],
            "normalizationBoundaries": [],
        },
        "required_dependency_ids": ("unit-test-dependency",),
    }


@pytest.mark.parametrize("change", [
    "catalog-bundle", "catalog-file", "scenario", "input-kind", "days", "checkpoints",
    "control-point-count", "ownership", "segment-count", "advisor-count", "details",
    "diagnostics", "fixture-domain", "trial-domain", "parser-inventory", "parser-source-hash",
    "required-dependency-set",
])
def test_accepted_packet_expires_when_any_baseline_component_changes(change):
    baseline = _acceptance_test_inputs()
    original_binding = audit._acceptance_binding(**baseline)
    digest = "d" * 64
    accepted_packet = _accepted_policy_evidence(
        digest,
        scope_fingerprint=original_binding["scopeFingerprint"],
        dependency_ids=baseline["required_dependency_ids"],
    )
    original_decision = _policy_decision(
        structural_complete=True,
        assembly_status="match",
        provided_hash=digest,
        packaged_hash=digest,
        evidence=accepted_packet,
        required_dependency_ids=baseline["required_dependency_ids"],
        scope_fingerprint=original_binding["scopeFingerprint"],
    )
    assert original_decision["exitCode"] == 0

    changed = copy.deepcopy(baseline)
    if change == "catalog-bundle":
        changed["catalogs"]["bundleFingerprint"] = "e" * 64
    elif change == "catalog-file":
        changed["catalogs"]["files"]["runtime_catalog.json"] = "e" * 64
    elif change == "scenario":
        changed["scenario"] = "ChangedScenario"
    elif change == "input-kind":
        changed["experiment_shape"]["inputKind"] = "explicit-save"
    elif change == "days":
        changed["experiment_shape"]["days"] = 181
    elif change == "checkpoints":
        changed["experiment_shape"]["checkpoints"] = [0, 181]
    elif change == "control-point-count":
        changed["experiment_shape"]["controlPointCount"] = 5
    elif change == "ownership":
        changed["experiment_shape"]["fullyOwnedBySelectedFaction"] = False
    elif change == "segment-count":
        changed["experiment_shape"]["segmentCount"] = 2
    elif change == "advisor-count":
        changed["experiment_shape"]["advisorCount"] = 1
    elif change == "details":
        changed["experiment_shape"]["details"] = True
    elif change == "diagnostics":
        changed["experiment_shape"]["diagnostics"] = True
    elif change == "fixture-domain":
        changed["experiment_shape"]["fixtureDomain"] = ["A"]
    elif change == "trial-domain":
        changed["experiment_shape"]["trials"][0]["Knowledge"] = 4
    elif change == "parser-inventory":
        changed["parser_inventory"]["normalizationBoundaries"].append({"operation": "new-boundary"})
    elif change == "parser-source-hash":
        changed["parser_inventory"]["sourceFileSha256"]["tools/ti_parser_core.py"] = "e" * 64
    elif change == "required-dependency-set":
        changed["required_dependency_ids"] = ("unit-test-dependency", "new-dependency")
        changed["parser_inventory"]["dependencies"].append({
            "dependencyId": "new-dependency", "sourceLocation": {"sha256": "e" * 64},
        })

    changed_binding = audit._acceptance_binding(**changed)
    assert changed_binding["scopeFingerprint"] != original_binding["scopeFingerprint"]
    changed_decision = _policy_decision(
        structural_complete=True,
        assembly_status="match",
        provided_hash=digest,
        packaged_hash=digest,
        evidence=accepted_packet,
        required_dependency_ids=changed["required_dependency_ids"],
        scope_fingerprint=changed_binding["scopeFingerprint"],
    )
    assert changed_decision["exitCode"] == 2


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
