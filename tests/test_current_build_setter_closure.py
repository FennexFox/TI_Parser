"""Regression checks for current-build nation setter callbacks."""

from dataclasses import replace

import pytest

from tests.test_nation_projection import context, mechanic_rule_test, state, unity_context
import ti_parser_nation_projection as projection
from ti_parser_mechanics import Rules


def _source_state(*, in_federation=False):
    value = state()
    value.in_federation = in_federation
    value.public_opinion = {"Resist": 1.0, "Undecided": 0.0}
    value.public_opinion_context = {"activeHumanIdeologyNames": ["resist", "cooperate"]}
    value.faction_effect_contexts = {7: {}, 8: {}}
    value.rest_state_context = {
        "sourceBacked": True, "provenance": "heldFixedWorldContext", "alienNation": False,
        "wars": [], "rivals": [], "neighbors": [], "alliedArmies": [],
        "spaceBodyRadiusKm": 6371.0, "ownBaseInvestmentPointsMonth": 30.0,
        "pcgdpToReduceUnrestBy1": 3000.0, "alienHabSurveillanceStrength": 0.0,
    }
    value.world_context["endOfOil"] = False
    return value


def _rest_context():
    value = unity_context()
    return replace(value, global_config={**value.global_config,
                                         "maxDistanceImpactOnCohesion": {"value": -5.0},
                                         "cohesionImpactPerKMtoPopCenter": {"value": 0.001}})


@mechanic_rule_test(Rules.NATION_PRIORITY_VALIDATION_TRIGGER.id, Rules.NATION_IP_ECONOMY_SCORE.id, evidence="stateTransition")
def test_modify_gdp_callback_revalidates_against_post_setter_gdp():
    value = _source_state()
    region = value.regions[1]
    region.mission_control = 4
    value.mission_control = 4
    value.control_points[1].pips = {"MissionControl": 1}
    used = set()
    trace = []

    result = projection._modify_gdp(value, 10_000_000_000.0, context(), used, trace=trace)

    assert result["callbackTriggered"] is True
    assert projection._region_mc_cap(value, region, context()) == 5
    assert value.control_points[1].pips == {"MissionControl": 1}
    assert Rules.NATION_PRIORITY_VALIDATION_TRIGGER.id in used
    assert [row["operation"] for row in trace] == ["modifyGDP", "priorityValidationTrigger"]


@mechanic_rule_test(Rules.NATION_PRIORITY_VALIDATION_TRIGGER.id, Rules.NATION_PRIORITY_KNOWLEDGE_COMPLETE.id, evidence="stateTransition")
def test_education_callback_revalidates_against_post_setter_education():
    value = _source_state()
    region = value.regions[1]
    region.mission_control = 4
    value.mission_control = 4
    value.control_points[1].pips = {"MissionControl": 1}
    used = set()
    trace = []

    result = projection._add_to_education(value, 0.5, context(), used, trace=trace)

    assert result["callbackTriggered"] is True
    assert projection._region_mc_cap(value, region, context()) == 5
    assert value.control_points[1].pips == {"MissionControl": 1}
    assert Rules.NATION_PRIORITY_VALIDATION_TRIGGER.id in used
    assert [row["operation"] for row in trace] == ["addToEducation", "priorityValidationTrigger"]


@mechanic_rule_test(Rules.NATION_PRIORITY_VALIDATION_TRIGGER.id, evidence="stateTransition")
@pytest.mark.parametrize("membership", [None, True])
def test_modify_gdp_unknown_or_federated_funding_gate_stops_before_gdp_mutation(membership):
    value = _source_state(in_federation=membership)
    value.regions[1].mission_control = 0
    value.mission_control = 0
    before = value.gdp

    with pytest.raises(projection.ProjectionRuntimeStop) as caught:
        projection._modify_gdp(value, 1_000_000.0, context(), set())

    assert value.gdp == before
    assert caught.value.phase == "beforeModifyGDP"
    assert caught.value.dependencies[0]["field"] == "federation.MemberPooledResource_Year(Money)"


@mechanic_rule_test(Rules.NATION_PRIORITY_VALIDATION_TRIGGER.id, evidence="stateTransition")
def test_legacy_direct_gdp_gate_exposes_its_nonfederated_assumption():
    value = state()
    value.regions[1].mission_control = 0
    value.mission_control = 0
    value.funding_year = 10_000.0
    trace = []

    result = projection._modify_gdp(value, 1_000_000.0, context(), set(), trace=trace)

    assert result["callbackTriggered"] is True
    assert result["assumptions"]
    assert trace[1]["operation"] == "scenarioAssumption"


@mechanic_rule_test(Rules.NATION_PERIODIC_REGION_CACHE.id, evidence="stateTransition")
def test_nonfederated_daily_cache_refresh_clears_federation_economy_bonus():
    value = _source_state(in_federation=False)
    value.federation_economy_bonus = 12.5

    cache = projection._refresh_region_cache(value, context())

    assert value.federation_economy_bonus == 0.0
    assert cache["federationEconomyBonus"] == 0.0
    assert cache["canAccumulateDecolonize"] is False


@mechanic_rule_test(
    Rules.NATION_PRIORITY_WELFARE_COMPLETE.id,
    Rules.NATION_PRIORITY_WELFARE_INEQUALITY.id,
    evidence="stateTransition",
)
def test_welfare_source_inequality_overflow_applies_cohesion_and_unrest_setters():
    value = state()
    value.inequality = 8.5
    value.cohesion = 4.0
    value.unrest = 0.0
    current = context()
    current = replace(current, global_config={
        **current.global_config,
        "welfarePriorityInequalityChange": {"value": 2.0},
    })

    execution = projection._apply_completion(value, "Welfare", current, set())

    assert value.inequality == 9.0
    assert value.cohesion == pytest.approx(2.5)
    assert value.unrest == pytest.approx(1.5)
    welfare = next(row for row in execution["childExecutions"] if row["ruleId"] == Rules.NATION_PRIORITY_WELFARE_INEQUALITY.id)
    assert welfare["outputs"] == ["nation.inequality", "nation.cohesion", "nation.unrest"]


@mechanic_rule_test(
    Rules.NATION_PRIORITY_WELFARE_COMPLETE.id,
    Rules.NATION_PRIORITY_WELFARE_COLONY_TRIGGER.id,
    evidence="stateTransition",
)
def test_welfare_uses_daily_decolonization_cache_instead_of_live_colony_guess():
    value = state()
    region = value.regions[1]
    region.colony = True
    region.welfare_colony_counter = 999
    value.cached_can_accumulate_decolonize = False

    projection._apply_completion(value, "Welfare", context(), set())

    assert region.welfare_colony_counter == 999
    assert region.colony is True


@mechanic_rule_test(
    Rules.NATION_PERIODIC_POPULATION.id,
    Rules.NATION_POPULATION_MONTHLY_GROWTH.id,
    Rules.NATION_PRIORITY_VALIDATION_TRIGGER.id,
    evidence="ordering",
)
def test_monthly_unknown_federation_gate_preserves_population_prefix_and_expected_evidence():
    value = _source_state()
    value.in_federation = None
    region = value.regions[1]
    region.annual_population_growth = 0.12
    region.mission_control = 0
    value.mission_control = 0
    old_population = value.population_millions
    old_gdp = value.gdp

    with pytest.raises(projection.ProjectionRuntimeStop) as caught:
        projection._run_monthly_transaction(value, _rest_context(), 1)

    stopped = caught.value.authoritative_state
    assert stopped.population_millions > old_population
    assert stopped.population_mean_path is True
    assert stopped.gdp == old_gdp
    assert stopped.metric_tracker.evidence["nation.population"].coverage == "expected"
    assert caught.value.attempted_transaction["populationUpdates"][0]["gdpDelta"] is None
    prefix = next(
        row for row in caught.value.attempted_transaction["ruleExecutions"]
        if row["ruleId"] == Rules.NATION_POPULATION_MONTHLY_GROWTH.id
    )
    assert prefix["effectiveCoverage"] == "expected"
    assert prefix["authoritativePrefix"] is True
