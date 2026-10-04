"""Tests for the visible-input isolated-nation projection adapter."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import json
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from ti_parser_catalogs import CatalogIntegrityError
from ti_parser_nation_projection import ProjectionInputError


def _context() -> dict:
    identity = {
        "schemaVersion": 1,
        "fingerprint": {
            "algorithm": "sha256-canonical-save-json-v1",
            "value": "a" * 64,
        },
        "gameDate": {"year": 2035, "month": 1, "day": 10},
        "scenario": "ModernScenario",
        "latestSaveVersion": "0.4.35",
        "campaignStartVersion": "0.4.35",
        "campaign": {"realWorldCampaignStart": "2026-01-01"},
        "playerFaction": {
            "status": "resolved",
            "id": 7,
            "template": "ResistCouncil",
            "display": "Resistance",
        },
    }
    return {
        "schemaVersion": "conditional-nation-v1",
        "model": "isolated-nation-v1",
        "assumptionsAcknowledged": True,
        "peer": {"saveIdentity": identity, "selectedNationId": 48},
        "observations": {
            "source": "Companion UI report, 2035-01-10",
            "precision": "reported",
            "nation": {
                "id": 48,
                "name": "Example Nation",
                "playerFactionId": 7,
                "asOf": "2035-01-10T00:00:00Z",
                "gdp": 29_000_000_000_000.0,
                "inequality": 3.27,
                "education": 5.44,
                "democracy": 6.25,
                "cohesion": 5.18,
                "unrest": 2.31,
                "sustainability": 5.61,
                "militaryTech": 3.4,
                "fundingYear": 0.0,
                "regions": [
                    {
                        "id": 501,
                        "name": "California",
                        "template": "2026_California",
                        "populationMillions": 40.0,
                        "missionControl": 0,
                    },
                ],
                "controlPoints": [
                    {"id": 801 + position, "position": position, "ownerFactionId": 7}
                    for position in range(6)
                ],
            },
        },
        "assumptions": {
            "daysInCampaign": 3285.0,
            "currentQuarter": 36,
            "nationPopulationGrowthModifier": 0.0,
            "startTimeTemplate": "2026Start",
            "initialProgress": {"Knowledge": 0.0, "Welfare": 0.0},
            "world": {
                "temperatureAnomalyC": 1.2,
                "endOfOil": False,
                "pcgdpToReduceUnrestByOne": 10000.0,
                "cohesionFixedImpact": 20.0,
                "unrestFixedImpact": 10.5,
                "initialCohesionRest": 5.0,
                "initialUnrestRest": 2.0,
            },
            "regions": [
                {
                    "id": 501,
                    "annualPopulationGrowthModifier": 0.2,
                    "xenoformingLevel": 0.0,
                    "nuclearDetonations": 0,
                },
            ],
        },
    }


def _plans() -> list[dict]:
    return [
        {"name": "Knowledge-heavy", "pips": {"Knowledge": 3, "Welfare": 0}},
        {"name": "Welfare-heavy", "pips": {"Knowledge": 0, "Welfare": 3}},
    ]


def _eight_plans() -> list[dict]:
    allocations = (
        {"Knowledge": 1, "Welfare": 0},
        {"Knowledge": 0, "Welfare": 1},
        {"Knowledge": 3, "Welfare": 0},
        {"Knowledge": 0, "Welfare": 3},
        {"Knowledge": 2, "Welfare": 1},
        {"Knowledge": 1, "Welfare": 2},
        {"Knowledge": 3, "Welfare": 3},
        {"Knowledge": 2, "Welfare": 2},
    )
    return [
        {"name": f"Plan {index + 1}", "pips": pips}
        for index, pips in enumerate(allocations)
    ]


def _reconstruct_metric_coverage(result: dict, plan: dict) -> dict:
    table = result["metricCoverageRecords"]
    decoded = {}
    for metric, reference in plan["engineProjection"]["metricCoverage"].items():
        record = table[reference["evidenceIndex"]]
        assert reference["coverage"] == record["coverage"]
        decoded[metric] = record
    return decoded


def _module():
    from ti_parser_conditional_projection import (
        build_conditional_state,
        calculate_conditional_projection,
        get_context_schema,
        get_plans_schema,
    )

    return build_conditional_state, calculate_conditional_projection, get_context_schema, get_plans_schema


def test_build_state_keeps_reported_values_and_catalog_geography_separate():
    build_state, _, _, _ = _module()
    document = _context()

    state, context, provenance = build_state(document)

    assert state.gdp == document["observations"]["nation"]["gdp"]
    assert state.inequality == 3.27
    assert state.at.tzinfo is None  # normalized UTC for the existing engine
    assert sorted(cp.position for cp in state.control_points.values()) == list(range(6))
    assert {cp.owner_faction_id for cp in state.control_points.values()} == {7}
    assert state.regions[501].latitude == pytest.approx(37.21)
    assert len(state.regions) == 1

    observed = provenance["observations"]["fields"]["/observations/nation/inequality"]
    assert observed == {
        "kind": "callerReportedObservation",
        "precision": "reported",
        "source": "Companion UI report, 2035-01-10",
    }
    geography = provenance["observations"]["fields"]["/observations/nation/regions/501/geography"]
    assert geography["kind"] == "packagedPublicCatalog"
    assert provenance["assumptions"]["expanded"]["namedModelConstants"]["rivalWarNeighbors"] == []
    assert provenance["assumptions"]["expanded"]["namedModelConstants"]["advisors"] == []
    assert context.faction_id == 7


def test_180_day_ab_uses_the_engine_and_labels_coverage_as_conditional():
    _, calculate, _, _ = _module()
    original = _context()
    before = deepcopy(original)

    result = calculate(original, _plans())

    assert original == before
    assert result["status"] == "complete"
    assert result["simulationDays"] == 180
    assert result["authoritativeGameOutcome"] is False
    assert result["exactGameOutcome"] is False
    assert [plan["name"] for plan in result["plans"]] == ["Knowledge-heavy", "Welfare-heavy"]
    assert all(plan["status"].startswith("conditional-") for plan in result["plans"])
    assert all("engineCoverageWithinConditionalScenario" in plan for plan in result["plans"])
    assert result["priorityCoverageScope"]
    for plan in result["plans"]:
        projection = plan["engineProjection"]
        assert [checkpoint["day"] for checkpoint in projection["checkpoints"]] == [0, 180]
        assert plan["engineStatus"] == "complete"
        assert plan["engineProjection"]["preflight"]["implicitFallbacks"] == []
        assert plan["engineProjection"]["mechanicRuleIds"]
        assert set(plan["engineCoverageWithinConditionalScenario"]) == {"Knowledge", "Welfare"}
        assert "ruleExecutions" not in projection
        assert "completionEvents" not in projection
    assert result["catalogs"]["scenario"] == "ModernScenario"
    assert result["catalogs"]["catalogBundleFingerprint"]
    knowledge_end = result["plans"][0]["engineProjection"]["checkpoints"][-1]["nation"]
    welfare_end = result["plans"][1]["engineProjection"]["checkpoints"][-1]["nation"]
    assert knowledge_end["education"] > original["observations"]["nation"]["education"]
    assert welfare_end["inequality"] < original["observations"]["nation"]["inequality"]
    assert welfare_end["education"] == original["observations"]["nation"]["education"]
    assert result["mechanicRuleDiagnostics"]
    assert all("id" in item for item in result["mechanicRuleDiagnostics"])
    assert all("ruleId" not in item for item in result["mechanicRuleDiagnostics"])
    assert result["metricCoverageRecords"]
    for plan in result["plans"]:
        assert _reconstruct_metric_coverage(result, plan)
    assert len(json.dumps(result, separators=(",", ":")).encode("utf-8")) < 125_000


def test_compact_summaries_and_coverage_reconstruct_engine_evidence(monkeypatch):
    import ti_parser_nation_projection as engine

    _, calculate, _, _ = _module()
    raw_results = []
    original_run_projection = engine.run_projection

    def capture_raw_result(*args, **kwargs):
        result = original_run_projection(*args, **kwargs)
        raw_results.append(result)
        return result

    monkeypatch.setattr(engine, "run_projection", capture_raw_result)
    result = calculate(_context(), _plans())

    assert len(raw_results) == len(result["plans"]) == 2
    for raw, plan in zip(raw_results, result["plans"], strict=True):
        projection = plan["engineProjection"]
        execution_summary = projection["executionSummary"]
        completion_summary = projection["completionSummary"]
        assert execution_summary["totalCount"] == len(raw["ruleExecutions"])
        assert completion_summary["totalCount"] == len(raw["completionEvents"])
        assert execution_summary["eventDayAvailability"] == "not-reported-by-engine"
        assert "ruleExecutions" not in projection
        assert "completionEvents" not in projection
        assert _reconstruct_metric_coverage(result, plan) == raw["metricCoverage"]

        by_rule = {row["ruleId"]: row for row in execution_summary["byRule"]}
        raw_by_rule = {}
        for row in raw["ruleExecutions"]:
            raw_by_rule.setdefault(row["ruleId"], []).append(row)
        assert set(by_rule) == set(raw_by_rule)
        for rule_id, rows in raw_by_rule.items():
            summary = by_rule[rule_id]
            assert summary["count"] == len(rows)
            assert summary["lastDay"] is None
            assert summary["coverageCounts"] == _counts_for(rows, "effectiveCoverage")
            assert summary["provenanceCounts"] == _counts_for(rows, "provenance")

        by_priority = {row["priority"]: row for row in completion_summary["byPriority"]}
        raw_by_priority = {}
        for row in raw["completionEvents"]:
            raw_by_priority.setdefault(row["priority"], []).append(row)
        assert set(by_priority) == set(raw_by_priority)
        for priority, rows in raw_by_priority.items():
            summary = by_priority[priority]
            assert summary["count"] == len(rows)
            assert summary["firstDay"] == min(row["day"] for row in rows)
            assert summary["lastDay"] == max(row["day"] for row in rows)
            assert summary["statusCounts"] == _counts_for(rows, "effectiveCoverage")


def _counts_for(rows: list[dict], field: str) -> list[dict]:
    counts = {}
    for row in rows:
        value = row.get(field)
        counts[value] = counts.get(value, 0) + 1
    return [
        {"value": value, "count": count}
        for value, count in sorted(counts.items(), key=lambda item: (item[0] is None, str(item[0])))
    ]


def test_eight_plan_conditional_payload_stays_bounded():
    _, calculate, _, _ = _module()

    result = calculate(_context(), _eight_plans())

    assert len(result["plans"]) == 8
    assert all("executionSummary" in row["engineProjection"] for row in result["plans"])
    assert all("completionSummary" in row["engineProjection"] for row in result["plans"])
    assert len(json.dumps(result, separators=(",", ":")).encode("utf-8")) < 280_000


def test_unknown_or_missing_hidden_state_is_rejected_instead_of_zeroed():
    build_state, calculate, _, _ = _module()

    missing_region_assumption = _context()
    missing_region_assumption["assumptions"]["regions"].pop()
    with pytest.raises(ProjectionInputError, match="ids must match"):
        build_state(missing_region_assumption)

    hidden_observation = _context()
    hidden_observation["observations"]["nation"]["regions"][0]["xenoformingLevel"] = 2.0
    with pytest.raises(ProjectionInputError, match="unsupported keys"):
        build_state(hidden_observation)

    missing_world_assumption = _context()
    del missing_world_assumption["assumptions"]["world"]["endOfOil"]
    with pytest.raises(ProjectionInputError, match="missing required keys"):
        build_state(missing_world_assumption)

    with pytest.raises(ProjectionInputError, match="must be 'reported'"):
        wrong_precision = _context()
        wrong_precision["observations"]["precision"] = "exact"
        calculate(wrong_precision, _plans())


def test_assumed_xenoforming_is_never_claimed_as_observed():
    _, calculate, _, _ = _module()
    document = _context()
    document["assumptions"]["regions"][0]["xenoformingLevel"] = 3.5

    result = calculate(document, _plans())

    source = result["inputProvenance"]["assumptions"]["fieldSources"][
        "/assumptions/regions/501/xenoformingLevel"
    ]
    assert source["kind"] == "callerDeclaredAssumption"
    assert "xenoformingLevel" not in str(result["inputProvenance"]["observations"]["fields"])
    assert result["assumptions"]["regions"][0]["xenoformingLevel"] == 3.5


def test_built_state_is_isolated_from_input_and_later_builds():
    build_state, _, _, _ = _module()
    document = _context()

    first_state, first_context, _ = build_state(document)
    document["observations"]["nation"]["gdp"] = 9.0e14
    first_context.priorities.clear()
    second_state, second_context, _ = build_state(_context())

    assert first_state.gdp == 2.9e13
    assert second_state.gdp == 2.9e13
    assert "Knowledge" in second_context.priorities


def test_missing_packaged_catalog_fails_closed(monkeypatch):
    build_state, _, _, _ = _module()

    def missing_catalog(*args, **kwargs):
        raise CatalogIntegrityError("missing packaged catalog")

    monkeypatch.setattr("ti_parser_conditional_projection.RuntimeCatalogs.load", missing_catalog)
    with pytest.raises(CatalogIntegrityError, match="missing packaged catalog"):
        build_state(_context())


def test_isolated_model_rejects_a_non_subject_control_point_owner():
    build_state, _, _, _ = _module()
    document = _context()
    document["observations"]["nation"]["controlPoints"][5]["ownerFactionId"] = 8

    with pytest.raises(ProjectionInputError, match="every observed control point"):
        build_state(document)


def test_runtime_prefix_stop_remains_incomplete_and_is_not_success_masked(monkeypatch):
    import ti_parser_nation_projection as engine

    _, calculate, _, _ = _module()

    def stop_transaction(*args, **kwargs):
        raise engine.ProjectionRuntimeStop(
            "unsupported next monthly action",
            phase="monthlyUpdate",
            trace=({"operation": "beforeUnsupportedAction"},),
        )

    monkeypatch.setattr(engine, "_run_monthly_transaction", stop_transaction)
    result = calculate(_context(), _plans())

    assert result["status"] == "incomplete"
    for plan in result["plans"]:
        assert plan["status"] == "conditional-incomplete"
        assert plan["engineStatus"] == "incomplete"
        stop = plan["engineProjection"]["runtimeStop"]
        assert stop["reason"] == "unsupported next monthly action"
        assert stop["phase"] == "monthlyUpdate"
        assert plan["engineProjection"]["authoritativeFinalState"] is None
        assert plan["engineProjection"]["lastAuthoritativeState"]


def test_low_gdp_monthly_control_point_reduction_stops_before_unobserved_mutation(monkeypatch):
    import ti_parser_nation_projection as engine

    _, calculate, _, _ = _module()
    raw_results = []
    original_run_projection = engine.run_projection

    def capture_raw_result(*args, **kwargs):
        result = original_run_projection(*args, **kwargs)
        raw_results.append(result)
        return result

    monkeypatch.setattr(engine, "run_projection", capture_raw_result)
    document = _context()
    document["observations"]["nation"]["gdp"] = 1_250_000_000_000.0

    result = calculate(document, _plans())

    assert result["status"] == "incomplete"
    for raw, plan in zip(raw_results, result["plans"], strict=True):
        assert plan["status"] == "conditional-incomplete"
        projection = plan["engineProjection"]
        assert _reconstruct_metric_coverage(result, plan) == raw["metricCoverage"]
        stop = projection["runtimeStop"]
        assert stop["phase"] == "beforeControlPointCountMutation"
        assert stop["simulationDay"] == 22
        assert stop["stateContext"]["currentControlPointCount"] == 6
        assert stop["stateContext"]["requiredControlPointCount"] == 3
        assert stop["unsupportedNextStep"]["ruleIds"] == ["nation.periodic.control-points"]
        assert projection["authoritativeFinalState"] is None
        assert len(projection["lastAuthoritativeState"]["controlPoints"]) == 6


def test_education_255_knowledge_plan_has_no_implicit_economy_fallback():
    _, calculate, _, _ = _module()
    document = _context()
    document["observations"]["nation"]["education"] = 255

    result = calculate(document, _plans())

    knowledge_plan = result["plans"][0]["engineProjection"]
    assert knowledge_plan["preflight"]["activePriorities"] == ["Knowledge"]
    assert knowledge_plan["preflight"]["dormantPriorities"] == []
    assert knowledge_plan["preflight"]["implicitFallbacks"] == []


def test_plans_and_schemas_reject_unmodeled_keys_and_invalid_pips():
    _, calculate, context_schema, plans_schema = _module()
    context = _context()
    plans = _plans()

    assert context_schema()["additionalProperties"] is False
    assert context_schema()["properties"]["observations"]["additionalProperties"] is False
    assert plans_schema()["items"]["additionalProperties"] is False
    assert plans_schema()["items"]["properties"]["pips"]["additionalProperties"] is False

    plans[0]["pips"]["Economy"] = 1
    with pytest.raises(ProjectionInputError, match="unsupported keys"):
        calculate(context, plans)

    plans = _plans()
    plans[0]["pips"]["Knowledge"] = 4
    with pytest.raises(ProjectionInputError, match="at most 3"):
        calculate(context, plans)

    plans = _plans()
    plans[0]["pips"] = {"Knowledge": 0, "Welfare": 0}
    with pytest.raises(ProjectionInputError, match="at least one"):
        calculate(context, plans)
