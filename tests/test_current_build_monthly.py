"""Current DLL live rest getters, monthly order, and explicit source boundaries."""

import copy
import math
from dataclasses import replace
from datetime import datetime
from unittest.mock import patch

import pytest

from tests.test_nation_projection import context, state, unity_context
from tools.audit_projection_reads import _load_fixture
import ti_parser_nation_projection as projection
import ti_parser_projection_adapter as adapter
import ti_save_parser as parser


def source_state():
    value = state()
    # This fixture explicitly describes a non-federated nation.
    value.in_federation = False
    value.public_opinion = {"Resist": 1.0, "Undecided": 0.0}
    value.public_opinion_context = {"activeHumanIdeologyNames": ["resist", "cooperate"]}
    value.faction_effect_contexts = {7: {}, 8: {}}
    value.rest_state_context = {
        "sourceBacked": True, "provenance": "heldFixedWorldContext", "alienNation": False,
        "wars": [], "rivals": [], "neighbors": [], "alliedArmies": [],
        "spaceBodyRadiusKm": 6371.0, "ownBaseInvestmentPointsMonth": 30.0,
        "pcgdpToReduceUnrestBy1": 3000.0, "alienHabSurveillanceStrength": 0.0,
    }
    return value


def rest_context():
    value = unity_context()
    return replace(value, global_config={**value.global_config,
                                       "maxDistanceImpactOnCohesion": {"value": -5.0},
                                       "cohesionImpactPerKMtoPopCenter": {"value": 0.001}})


def test_monthly_uses_live_cohesion_then_live_unrest_without_mutating_daily_caches():
    value = state()
    value.gdp = 300_000_000_000.0
    value.rest_state_context["cohesionFixedImpact"] = 26.0
    value.cohesion_rest = 0.0
    value.unrest_rest = 0.0
    value.unrest = 4.55
    projection._run_monthly_transaction(value, context(), 1)
    assert value.cohesion == pytest.approx(4.1)
    assert value.unrest == pytest.approx(10.5 - 4.1 - 6000.0 / 3000.0)
    assert (value.cohesion_rest, value.unrest_rest) == (0.0, 0.0)


@pytest.mark.parametrize("cache", [0.0, 5.0, 10.0])
def test_lossy_rest_caches_are_never_inverted_into_exact_residuals(cache):
    value = state()
    value.cohesion_rest = value.unrest_rest = cache
    value.rest_state_context = {}
    projection.calibrate_rest_state_context(value, context(), pcgdp_to_reduce_unrest_by_one=3000.0)
    assert "cohesionFixedImpact" not in value.rest_state_context
    assert "unrestFixedImpact" not in value.rest_state_context
    with pytest.raises(projection.ProjectionRuntimeStop, match="source inputs are incomplete"):
        projection._refresh_rest_caches(value, context(), 1)


def test_live_rest_source_terms_ignore_even_clamped_or_democracy_centered_caches():
    value = source_state()
    value.democracy = 8.0
    expected = projection._live_cohesion_rest(value, rest_context())
    for cache in (0.0, 5.0, 10.0):
        value.cohesion_rest = cache
        projection.calibrate_rest_state_context(value, rest_context(), pcgdp_to_reduce_unrest_by_one=3000.0)
        assert projection._live_cohesion_rest(value, rest_context()) == expected


def test_source_regions_rivals_and_wars_recompute_across_democracy_threshold():
    value = source_state()
    value.rest_state_context["wars"] = [{"id": 2, "extant": True, "democracy": 7.0, "numControlPoints": 2}]
    value.rest_state_context["rivals"] = [{"id": 3, "extant": True, "democracy": 7.0, "numControlPoints": 2}]
    value.democracy = 5.99
    assert projection._rest_fixed_impacts(value, rest_context())[0] == 17.5
    value.democracy = 6.0
    assert projection._rest_fixed_impacts(value, rest_context())[0] == 16.0
    second = copy.deepcopy(value.regions[1])
    second.id, second.capital, second.latitude, second.longitude = 2, False, 10.0, 110.0
    value.regions[2] = second
    a = math.sin(math.radians(90.0) / 2.0) ** 2 * math.cos(math.radians(10.0)) ** 2
    distance = 6371.0 * 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a)) / 2.0
    expected = 16.0 + max(-5.0, math.trunc(-distance * 0.001 * 100.0) / 100.0)
    assert projection._rest_fixed_impacts(value, rest_context())[0] == pytest.approx(expected)


def test_monthly_war_democracy_precedes_live_movement_and_low_cohesion_stop():
    value = state(at=datetime(2030, 1, 31, 12))
    value.rest_state_context["wars"] = [{"id": 2}]
    value.cohesion = 3.0
    result = projection.run_projection(value, projection.PriorityPlan("p", (projection.PlanSegment(None, None, None, None),)), context(), days=1)
    assert result["status"] == "incomplete"
    assert result["runtimeStop"]["phase"] == "beforeLowCohesionDemocracy"
    nation = result["lastAuthoritativeState"]["nation"]
    assert nation["democracy"] == pytest.approx(4.99)
    assert nation["cohesion"] == 3.0
    assert nation["populationMillions"] == 50.0


def test_monthly_neighbor_democracy_precedes_live_getter():
    value = state()
    value.democracy = 6.49
    value.rest_state_context["neighbors"] = [{"democracy": 8.0, "atWar": False}]
    current_context = replace(context(), global_config={**context().global_config,
                                                       "basePassiveDemocracyIncreaseFromNeighbor": {"value": 0.04}})
    expected = copy.deepcopy(value)
    expected.democracy = 6.53
    live_target = projection._live_cohesion_rest(expected, current_context)
    projection._run_monthly_transaction(value, current_context, 1)
    assert value.democracy == pytest.approx(6.53)
    assert value.cohesion == pytest.approx(4.0 + min(0.1, live_target - 4.0))


def test_allied_armies_apply_effects_to_cumulative_sum_in_list_order_and_filter_strings():
    value = source_state()
    value.armies = [projection.ArmyProjectionState(1, 1.0, "Standard", 1, 1, 0, 7, "Human")]
    value.rest_state_context["alliedArmies"] = [{"strength": 0.5, "currentRegionId": 1, "factionId": 8,
                                                "armyType": "Human", "homeBaseInvestmentPointsMonth": 1.0}]
    value.faction_effect_contexts = {7: {"ArmyUnrestReductionImpact": ["double", "filtered"]},
                                   8: {"ArmyUnrestReductionImpact": ["triple"]}}
    current_context = replace(rest_context(), effect_templates={
        "double": {"operation": "Multiplicative", "value": 2.0, "strValue": ""},
        "triple": {"operation": "Multiplicative", "value": 3.0, "strValue": None},
        "filtered": {"operation": "Additive", "value": 1000.0, "strValue": "specificTarget"},
    })
    assert projection._own_army_unrest_impact(value, current_context) == pytest.approx(-18.75)
    value.rest_state_context["ownBaseInvestmentPointsMonth"] = 0.0
    assert projection._own_army_unrest_impact(value, current_context) == pytest.approx(-3.75)
    value.rest_state_context["alliedArmies"][0]["homeBaseInvestmentPointsMonth"] = 0.0
    assert projection._own_army_unrest_impact(value, current_context) == 0.0
    value.rest_state_context["alliedArmies"][0]["armyType"] = "AlienInvader"
    assert projection._own_army_unrest_impact(value, current_context) == pytest.approx(-3.75)


def test_army_effect_filter_missing_input_stops_before_claiming_exact_unrest():
    value = source_state()
    value.armies = [projection.ArmyProjectionState(1, 1.0, "Standard", 1, 1, 0, 7, "Human")]
    value.faction_effect_contexts[7] = {"ArmyUnrestReductionImpact": ["unknownFilter"]}
    current_context = replace(rest_context(), effect_templates={"unknownFilter": {"operation": "Multiplicative", "value": 2.0}})
    with pytest.raises(projection.ProjectionRuntimeStop, match="filter input is unavailable"):
        projection._own_army_unrest_impact(value, current_context)


def test_source_alien_xenoforming_and_army_gate_are_explicit():
    value = source_state()
    value.rest_state_context["alienNation"] = True
    value.regions[1].xenoforming_level = 40.0
    assert projection._rest_fixed_impacts(value, rest_context())[1] == 8.5


def test_explicit_scenario_rest_terms_report_assumption_provenance():
    value = state()
    transaction = projection._refresh_rest_caches(value, context(), 1)
    assert transaction["ruleExecutions"][0]["provenance"] == "scenarioAssumption"
    assert "heldFixedWorldContext" in value.metric_tracker.evidence["nation.cohesionRest"].provenance


def test_public_adapter_rejects_missing_rival_input_instead_of_reconstructing_from_cache():
    data = _load_fixture()
    del data["gamestates"]["TINationState"][0]["Value"]["rivals"]
    with pytest.raises(parser.CalculationDependencyError) as caught:
        parser.calculate_nation_projection(parser.build_index(data), "USA", None,
                                           {"plans": [{"name": "p", "segments": [{}]}]}, days=1,
                                           checkpoints=[], details=False, diagnostics=False)
    assert caught.value.missing_dependencies[0]["name"] == "rivals"


def test_zero_surveillance_strength_requires_an_explicit_alien_sector_list():
    data = _load_fixture()
    development = {"factionTemplates": {"AlienCouncil": {"isAlien": True}}}
    assert adapter._projection_alien_hab_surveillance(parser.build_index(data), development) == 0.0
    del data["gamestates"]["TIFactionState"][1]["Value"]["habSectors"]
    assert adapter._projection_alien_hab_surveillance(parser.build_index(data), development) is None


def test_positive_surveillance_stops_before_abductions_and_movement():
    value = state()
    value.rest_state_context["alienHabSurveillanceStrength"] = 1.0
    with pytest.raises(projection.ProjectionRuntimeStop) as caught:
        projection._run_monthly_transaction(value, context(), 1)
    assert caught.value.phase == "beforeMonthlyAbductions"
    assert caught.value.authoritative_state.cohesion == 4.0
    assert caught.value.authoritative_state.population_millions == 50.0


def test_monthly_population_uses_the_live_region_gdp_share_in_region_order():
    value = state()
    first = value.regions[1]
    first.population_millions = 10.0
    first.annual_population_growth = 0.12
    first.core_economic_region = True
    second = copy.deepcopy(first)
    second.id = 2
    second.population_millions = 40.0
    second.annual_population_growth = -0.12
    second.core_economic_region = False
    second.region_order = 1
    value.regions[2] = second

    initial_gdp = value.gdp
    growth_exponent = 0.0833333358168602
    first_rate = math.pow(1.12, growth_exponent) - 1.0
    second_rate = math.pow(0.88, growth_exponent) - 1.0
    first_new = 10.0 * (1.0 + first_rate)
    second_new = 40.0 * (1.0 + second_rate)
    first_delta = first_new - 10.0
    second_delta = second_new - 40.0

    first_weight = first_new * 1.25
    first_region_gdp = initial_gdp * first_weight / (first_weight + 40.0)
    first_live_pcgdp = first_region_gdp / (first_new * 1_000_000.0)
    first_gdp_delta = first_live_pcgdp * first_delta * 1_000_000.0
    gdp_after_first = initial_gdp + first_gdp_delta

    second_weight = second_new
    second_region_gdp = gdp_after_first * second_weight / (first_weight + second_weight)
    second_live_pcgdp = second_region_gdp / (second_new * 1_000_000.0)
    second_gdp_delta = second_live_pcgdp * second_delta * 1_000_000.0
    expected_gdp = gdp_after_first + second_gdp_delta

    transaction, _ = projection._run_monthly_transaction(value, context(), 1)

    updates = transaction["populationUpdates"]
    assert [row["regionId"] for row in updates] == [1, 2]
    assert updates[0]["gdpDelta"] == pytest.approx(first_gdp_delta)
    assert updates[1]["gdpDelta"] == pytest.approx(second_gdp_delta)
    assert value.gdp == pytest.approx(expected_gdp)
    final_weight_total = first_new * 1.25 + second_new
    assert first.gdp == pytest.approx(expected_gdp * first_new * 1.25 / final_weight_total)
    assert second.gdp == pytest.approx(expected_gdp * second_new / final_weight_total)
    assert first.gdp + second.gdp == pytest.approx(value.gdp)


def test_monthly_population_loss_clamps_education_and_live_gdp_floor():
    value = state(annual_growth=-0.99)
    value.education = 1.0
    value.gdp = value.population_millions * 1_000_000.0 * 100.0
    initial_gdp = value.gdp
    old_population = value.regions[1].population_millions
    rate = math.pow(0.01, 0.0833333358168602) - 1.0
    new_population = max(old_population * (1.0 + rate), 0.001)
    delta = new_population - old_population
    unclamped_gdp = initial_gdp + (initial_gdp / (new_population * 1_000_000.0)) * delta * 1_000_000.0
    expected_gdp_floor = new_population * 1_000_000.0 * 100.0
    assert unclamped_gdp < expected_gdp_floor

    transaction, _ = projection._run_monthly_transaction(value, context(), 1)

    assert value.education == 1.0
    assert value.gdp == pytest.approx(expected_gdp_floor)
    assert value.regions[1].gdp == pytest.approx(value.gdp)
    assert transaction["populationUpdates"][0]["gdpDelta"] == pytest.approx(expected_gdp_floor - initial_gdp)
