import copy
import sys
import unittest
from datetime import datetime
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import ti_parser_nation_projection as projection
from ti_parser_mechanics import Rules, mechanic_rule_test


def context(*, priorities=None, diversity=None):
    priorities = priorities or {
        "Economy": {"enumValue": 0, "investmentCost": 1},
        "Welfare": {"enumValue": 1, "investmentCost": 1},
        "Knowledge": {"enumValue": 3, "investmentCost": 1},
        "Government": {"enumValue": 4, "investmentCost": 1},
        "Unity": {"enumValue": 5, "investmentCost": 2},
        "Funding": {"enumValue": 7, "investmentCost": 1},
        "MissionControl": {"enumValue": 11, "investmentCost": 1},
        "Military_BuildArmy": {"enumValue": 14, "investmentCost": 1},
    }
    values = {
        "nationalInvestmentArmyFactorHome": {"value": 0.5},
        "nationalInvestmentArmyFactorAway": {"value": 1.0},
        "nationalInvestmentNavyFactor": {"value": 0.5},
        "populationBasedIPEffectScaling": {"value": -0.35},
        "controlPointIPScaling": {"value": 0.35},
        "controlPointIPFactor": {"value": 1.0},
        "controlPointCountScaling": {"value": 0.0},
        "controlPointScalingDivisor": {"value": 1.0},
        "coreEcoRegionGDPModifier": {"value": 1.25},
        "coreResourceRegionGDPModifier": {"value": 1.25},
        "colonyRegionGDPModifier": {"value": 0.5},
        "coreMineralBuildMilitaryModifier": {"value": 0.05},
        "federationGDPEconomyBonus": {"value": 0.01},
        "minPopulationForFirstArmy_millions": {"value": 5.0},
        "minPopulationForAdditionalArmiesPer_millions": {"value": 25.0},
        "welfarePriorityInequalityChange": {"value": -0.005},
        "numPrioritiesForLegitimize": {"value": 1},
        "maxCombinedImpactFromHostileClaims": {"value": 16.0},
        "inequalityCohesionMultiplier": {"value": 2.25},
        "severeInequality": {"value": 4.75},
        "populationCohesionImpactPower": {"value": 0.2},
        "knowledgePriorityEducationIncrease": {"value": 0.005},
        "governmentPriorityDemocracyIncrease": {"value": 0.01},
        "unityPriorityEducationChange": {"value": -0.001},
        "unityBaseCohesionChange": {"value": 0.1},
        "unityMinCohesionChange": {"value": 0.025},
        "fundingPriorityBaseIncomeIncrease": {"value": 10.0},
        "maxMonthlyCohesionIncrease_normal": {"value": 0.1},
        "maxMonthlyCohesionDecrease_normal": {"value": 0.1},
        "maxMonthlyCohesionDecrease_cap": {"value": 0.25},
        "maxMonthlyUnrestMovement_normal": {"value": 0.25},
        "maxMonthlyUnrestMovement_rapidIncrease": {"value": 1.0},
    }
    return projection.ProjectionContext(
        faction_id=7,
        priorities=priorities,
        global_config=values,
        diversity_bonuses=diversity or {"Knowledge": 0.2, "Unity": 0.2},
        initial_funding_pool_year=120,
        initial_own_funding_year=100,
        financial_sector_bonus=1.25,
        financial_sector_owned=True,
        nation_template={"popGrowthModifier": 0.0},
        start_template={"populationRegressionPeriod_years": 20.0},
    )


def state(*, pips=None, cp_count=1, progress=None, advisors=(), at=None, annual_growth=0.0):
    pips = pips or {"Knowledge": 3}
    control_points = {}
    for position in range(cp_count):
        control_points[position + 1] = projection.ControlPointProjectionState(
            position + 1, position, 7, False, None, dict(pips), {}
        )
    priorities = context().priorities
    initial_progress = {name: 0.0 for name in priorities}
    initial_progress.update(progress or {})
    return projection.NationProjectionState(
        nation_id=10,
        at=at or datetime(2030, 1, 2),
        gdp=1_000_000_000_000.0,
        inequality=4.0,
        education=8.0,
        democracy=5.0,
        cohesion=4.0,
        cohesion_rest=5.0,
        unrest=3.0,
        unrest_rest=2.0,
        sustainability=1.0,
        military_tech=4.0,
        funding_year=100.0,
        economy_score=30.0,
        occupation_factor=1.0,
        army_maintenance=0.0,
        progress=initial_progress,
        regions={1: projection.RegionProjectionState(
            id=1, population_millions=50.0, boost_per_year=12.0, mission_control=4,
            annual_population_growth=annual_growth, per_capita_gdp=20_000, gdp=1_000_000_000_000.0,
            region_order=0, template_name="Region_1", latitude=10.0, longitude=20.0,
            annual_population_growth_modifier=0.0, environment="Standard", xenoforming_level=0.0,
            nuclear_detonations=0, colony=False, permanent_colony=False, resource_region=False,
            oil_region=False, core_economic_region=False, mine_capable=False, oil_capable=False,
            capital=True, occupation_fraction=0.0, fully_occupied=False, welfare_colony_counter=0,
        )},
        control_points=control_points,
        advisors=tuple(advisors),
        mission_control=4,
        days_in_campaign=365.0,
        current_quarter=4,
        pcgdp_tracker={4: 20_000.0},
        military=True,
        space_flight_program=True,
        num_control_points_unclamped=cp_count,
        rest_state_context={"cohesionFixedImpact": 12.0, "unrestFixedImpact": 10.5, "pcgdpToReduceUnrestBy1": 3_000.0},
        world_context={"temperatureAnomaly_C": 1.0},
    )


class NationProjectionPlanTests(unittest.TestCase):
    @mechanic_rule_test(Rules.NATION_ADVISOR_ATTRIBUTE_SOURCE.id)
    def test_saved_and_virtual_advisor_validation(self):
        initial = state()
        saved = {3: projection.AdvisorProfile("saved", "Hanna", 12, 24, 3)}
        payload = {"plans": [{"name": "p", "segments": [{"advisors": [
            {"councilor": {"name": "Hanna"}},
            {"virtual": {"name": "virtual", "administration": 25, "science": 8}},
        ]}]}]}
        plans, _ = projection.parse_projection_document(payload, state=initial, councilors=saved, priorities=context().priorities)
        self.assertEqual([item.name for item in plans[0].segments[0].advisors], ["Hanna", "virtual"])
        bad = {"plans": [{"name": "p", "segments": [{"advisors": [{"virtual": {"name": "x", "administration": 26, "science": 0}}]}]}]}
        with self.assertRaises(projection.ProjectionInputError):
            projection.parse_projection_document(bad, state=initial, councilors=saved, priorities=context().priorities)

    def test_omitted_and_empty_advisors_and_full_cp_replacement(self):
        initial = state(pips={"Knowledge": 2, "Unity": 1})
        payload = {"plans": [{"name": "p", "segments": [
            {"until": {"day": 1}},
            {"controlPoints": [{"position": 0, "pips": {"Knowledge": 3}}], "advisors": []},
        ]}]}
        plans, _ = projection.parse_projection_document(payload, state=initial, councilors={}, priorities=context().priorities)
        self.assertIsNone(plans[0].segments[0].advisors)
        self.assertEqual(plans[0].segments[1].advisors, ())
        self.assertEqual(plans[0].segments[1].control_points[0].pips, {"Knowledge": 3})


class NationProjectionTransactionTests(unittest.TestCase):
    @mechanic_rule_test(Rules.NATION_IP_CONTROL_POINT_ALLOCATION.id)
    def test_one_tick_control_point_allocation(self):
        initial = state()
        initial.unrest = 0
        tx = projection._run_investment_transaction(initial, context(), 1, 0)
        self.assertAlmostEqual(tx["allocation"]["Knowledge"], (1000.0 ** 0.35) * 12.0 / 365.2422)

    @mechanic_rule_test(Rules.NATION_IP_PRIORITY_BONUS.id)
    def test_diversity_and_owner_priority_bonus(self):
        initial = state(pips={"Knowledge": 1, "Unity": 1})
        initial.unrest = 0
        initial.control_points[1].priority_bonuses = {"Knowledge": 0.2}
        tx = projection._run_investment_transaction(initial, context(), 1, 0)
        base_share = (1000.0 ** 0.35) * 0.5 * 12.0 / 365.2422
        self.assertAlmostEqual(tx["allocation"]["Knowledge"], base_share * 1.3)

    @mechanic_rule_test(Rules.NATION_IP_BASE.id, Rules.NATION_ADVISOR_STACKING.id)
    def test_advisor_base_ip_and_rank_decay(self):
        advisors = (
            projection.AdvisorProfile("virtual", "a", 20, 10),
            projection.AdvisorProfile("virtual", "b", 10, 20),
        )
        initial = state(advisors=advisors)
        initial.gdp = 1_000_000_000.0
        initial.economy_score = 1.0
        initial.unrest = 0
        self.assertAlmostEqual(projection._base_ip(initial, context()), 1.25)

    @mechanic_rule_test(Rules.NATION_PRIORITY_KNOWLEDGE_COMPLETE.id)
    def test_knowledge_completion(self):
        initial = state(progress={"Knowledge": 0.99})
        before = initial.education
        tx = projection._run_investment_transaction(initial, context(), 1, 0)
        self.assertEqual(tx["completions"][0]["priority"], "Knowledge")
        self.assertGreater(initial.education, before)

    def test_unity_fails_closed_until_public_opinion_downstream_is_implemented(self):
        initial = state(pips={"Unity": 3}, progress={"Unity": 1.99})
        result = projection.run_projection(initial, projection.PriorityPlan("p", (projection.PlanSegment(None, None, None, None),)), context(), days=1)
        self.assertEqual(result["status"], "incomplete")
        self.assertIn("nation.priority.unity.complete", result["missingMechanicRules"])

    @mechanic_rule_test(Rules.NATION_PRIORITY_GOVERNMENT_COMPLETE.id)
    def test_government_completion_below_cap(self):
        initial = state(pips={"Government": 3}, progress={"Government": 0.99})
        projection._run_investment_transaction(initial, context(), 1, 0)
        expected = 5.0 + (50_000_000.0 / 50_000_000.0) ** -0.35 * 0.01 * 8.0 / 10.0
        self.assertAlmostEqual(initial.democracy, expected)

    @mechanic_rule_test(Rules.NATION_PRIORITY_FUNDING_COMPLETE.id, Rules.NATION_FACTION_CONTRIBUTION.id)
    def test_funding_completion_and_contribution(self):
        initial = state(pips={"Funding": 3}, progress={"Funding": 0.99})
        before = projection._contribution(initial, context())["funding"]
        projection._run_investment_transaction(initial, context(), 1, 0)
        self.assertEqual(initial.funding_year, 111)
        self.assertGreater(projection._contribution(initial, context())["funding"], before)

    @mechanic_rule_test(Rules.NATION_PRIORITY_COMPLETION_ORDER.id)
    def test_condition_waits_for_multi_completion_transaction(self):
        initial = state(pips={"Knowledge": 3, "Funding": 3}, progress={"Knowledge": 0.99, "Funding": 0.99})
        condition = projection.MetricCondition("nation.funding", ">=", 111.0)
        plan = projection.PriorityPlan("p", (
            projection.PlanSegment(None, condition, None, None),
            projection.PlanSegment(None, None, None, ()),
        ))
        result = projection.run_projection(initial, plan, context(), days=1, details=True)
        investment = result["transactions"][0]
        self.assertEqual([event["priority"] for event in investment["completions"]], ["Knowledge", "Funding"])
        self.assertEqual(result["segmentTransitions"][-1]["effectiveDay"], 2)

    def test_conditional_pips_and_advisor_apply_together_next_tick(self):
        initial = state(pips={"Knowledge": 3})
        advisor = projection.AdvisorProfile("virtual", "admin", 20, 0)
        plan = projection.PriorityPlan("p", (
            projection.PlanSegment(1, None, None, None),
            projection.PlanSegment(None, None, (projection.ControlPointPolicy(1, {"Funding": 3}),), (advisor,)),
        ))
        result = projection.run_projection(initial, plan, context(), days=2, details=True)
        investments = [row for row in result["transactions"] if row["kind"] == "investment"]
        self.assertIn("Knowledge", investments[0]["allocation"])
        self.assertIn("Funding", investments[1]["allocation"])
        self.assertGreater(investments[1]["baseInvestmentPointsMonth"], investments[0]["baseInvestmentPointsMonth"])
        self.assertEqual(result["advisorTransitions"][-1]["day"], 2)

    def test_start_satisfied_segment_skips_before_first_tick(self):
        initial = state(pips={"Knowledge": 3})
        plan = projection.PriorityPlan("p", (
            projection.PlanSegment(None, projection.MetricCondition("nation.cohesion", ">=", 4.0), None, None),
            projection.PlanSegment(None, None, (projection.ControlPointPolicy(1, {"Government": 3}),), None),
        ))
        result = projection.run_projection(initial, plan, context(), days=1, details=True)
        investment = next(row for row in result["transactions"] if row["kind"] == "investment")
        self.assertEqual(investment["segmentIndex"], 1)
        self.assertIn("Government", investment["allocation"])

    @mechanic_rule_test(Rules.NATION_PERIODIC_COHESION.id, Rules.NATION_PERIODIC_UNREST.id)
    def test_monthly_cohesion_and_unrest(self):
        initial = state(at=datetime(2030, 1, 31, 12), annual_growth=0.0)
        result = projection.run_projection(initial, projection.PriorityPlan("p", (projection.PlanSegment(None, None, None, None),)), context(), days=1, details=True)
        self.assertEqual(result["status"], "complete")
        self.assertAlmostEqual(result["nationProjection"]["cohesion"], 4.1)
        self.assertAlmostEqual(result["nationProjection"]["unrest"], 2.75)

    @mechanic_rule_test(Rules.NATION_PERIODIC_POPULATION.id)
    def test_monthly_population_expected(self):
        initial = state(at=datetime(2030, 1, 31, 12), annual_growth=0.12)
        before = initial.population_millions
        result = projection.run_projection(initial, projection.PriorityPlan("p", (projection.PlanSegment(None, None, None, None),)), context(), days=1)
        self.assertGreater(result["nationProjection"]["populationMillions"], before)
        self.assertEqual(result["metricCoverage"]["nation.population"]["coverage"], "expected")
        self.assertIn("meanPath", result["metricCoverage"]["nation.population"]["provenance"])
        self.assertFalse(result["metricCoverage"]["nation.population"]["expectationGuarantee"])

    def test_mean_path_propagates_through_executed_dependencies_only(self):
        initial = state(
            pips={"Knowledge": 1, "Government": 1, "Welfare": 1},
            at=datetime(2030, 1, 2),
            annual_growth=0.12,
        )
        result = projection.run_projection(
            initial,
            projection.PriorityPlan("p", (projection.PlanSegment(None, None, None, None),)),
            context(),
            days=40,
        )
        expected_metrics = {
            "nation.population", "nation.gdp", "nation.perCapitaGdp", "nation.education",
            "nation.democracy", "nation.inequality", "nation.cohesion", "nation.cohesionRest",
            "nation.unrestRest", "nation.baseInvestmentPointsMonth", "nation.research",
            "nation.priorityProgress.Knowledge", "factionContribution.research",
        }
        for metric in expected_metrics:
            with self.subTest(metric=metric):
                evidence = result["metricCoverage"][metric]
                self.assertEqual(evidence["coverage"], "expected")
                self.assertIn("meanPath", evidence["provenance"])
                self.assertFalse(evidence["expectationGuarantee"])
        self.assertEqual(result["metricCoverage"]["nation.funding"]["coverage"], "exact")
        self.assertEqual(result["metricCoverage"]["nation.sustainability"]["coverage"], "exact")

    def test_rule_executions_expose_actual_inputs_outputs_and_welfare_children(self):
        initial = state(pips={"Welfare": 3}, progress={"Welfare": 0.99})
        result = projection.run_projection(
            initial,
            projection.PriorityPlan("p", (projection.PlanSegment(None, None, None, None),)),
            context(),
            days=1,
        )
        welfare = [row for row in result["ruleExecutions"] if row["ruleId"].startswith("nation.priority.welfare")]
        self.assertEqual(
            [row["ruleId"] for row in welfare],
            [Rules.NATION_PRIORITY_WELFARE_COMPLETE.id, Rules.NATION_PRIORITY_WELFARE_INEQUALITY.id],
        )
        self.assertIn("nation.priorityProgress.Welfare", welfare[0]["inputs"])
        self.assertEqual(welfare[0]["outputs"], ["nation.inequality"])
        self.assertNotIn(Rules.NATION_PRIORITY_WELFARE_DECOLONIZATION.id, result["mechanicRuleIds"])

    def test_mc_rule_can_be_aggregate_only_while_nation_total_is_exact(self):
        initial = state(pips={"MissionControl": 3}, progress={"MissionControl": 0.99})
        second = copy.deepcopy(initial.regions[1])
        second.id = 2
        second.region_order = 1
        initial.regions[1].mission_control = 0
        second.mission_control = 0
        initial.regions[2] = second
        initial.mission_control = 0
        result = projection.run_projection(
            initial,
            projection.PriorityPlan("p", (projection.PlanSegment(None, None, None, None),)),
            context(),
            days=1,
        )
        execution = next(
            row for row in result["ruleExecutions"]
            if row["ruleId"] == Rules.NATION_PRIORITY_MISSION_CONTROL_PLACEMENT.id
        )
        self.assertEqual(execution["effectiveCoverage"], "aggregateOnly")
        self.assertEqual(result["metricCoverage"]["nation.missionControl"]["coverage"], "exact")

    @mechanic_rule_test(Rules.NATION_IP_CONTROL_POINT_DEFAULT_ECONOMY.id)
    def test_invalid_only_control_point_persistently_falls_back_to_raw_economy(self):
        initial = state(pips={"Government": 3})
        initial.democracy = 10.0
        trace = []
        effective = projection._record_and_fix_control_point(initial, initial.control_points[1], context(), trace=trace)
        self.assertEqual(effective, {"Economy": 1})
        self.assertEqual(initial.control_points[1].pips["Economy"], 1)
        self.assertEqual(initial.control_points[1].total_weight, 1)
        self.assertEqual(trace[0]["operation"], "defaultEconomy")

    @mechanic_rule_test(
        Rules.NATION_PRIORITY_GOVERNMENT_COMPLETE.id,
        Rules.NATION_PRIORITY_GOVERNMENT_LEGITIMIZE.id,
        Rules.NATION_PRIORITY_KNOWLEDGE_COMPLETE.id,
    )
    def test_government_at_cap_applies_knowledge_and_legitimizes_claim(self):
        initial = state()
        initial.democracy = 10.0
        initial.hostile_region_ids = {1}
        before = initial.education
        used = set()
        event = projection._apply_completion(initial, "Government", context(), used)
        self.assertGreater(initial.education, before)
        self.assertEqual(initial.hostile_region_ids, set())
        self.assertEqual(event["removedHostileClaimRegionId"], 1)

    @mechanic_rule_test(
        Rules.NATION_PRIORITY_WELFARE_INEQUALITY.id,
        Rules.NATION_PRIORITY_WELFARE_COLONY_TRIGGER.id,
        Rules.NATION_PRIORITY_WELFARE_DECOLONIZATION.id,
        Rules.NATION_PRIORITY_WELFARE_DECOLONIZATION_DOWNSTREAM.id,
    )
    def test_welfare_children_activate_only_on_the_executed_path(self):
        ordinary = state()
        used = set()
        event = projection._apply_completion(ordinary, "Welfare", context(), used)
        self.assertAlmostEqual(ordinary.inequality, 3.995)
        self.assertEqual(event["dependencies"], [Rules.NATION_PRIORITY_WELFARE_INEQUALITY.id])

        colony = state()
        colony.regions[1].colony = True
        colony.regions[1].welfare_colony_counter = 999
        used = set()
        event = projection._apply_completion(colony, "Welfare", context(), used)
        self.assertFalse(colony.regions[1].colony)
        self.assertTrue(colony.regions[1].permanent_colony)
        self.assertEqual(colony.regions[1].welfare_colony_counter, 0)
        self.assertEqual(event["decolonizedRegionId"], 1)

    @mechanic_rule_test(Rules.NATION_PRIORITY_MISSION_CONTROL_PLACEMENT.id)
    def test_mission_control_no_candidate_preserves_dll_mutation_order(self):
        initial = state(pips={"MissionControl": 3}, progress={"MissionControl": 0.99})
        initial.regions[1].mission_control = 0
        initial.regions[1].fully_occupied = True
        initial.mission_control = 0
        tx = projection._run_investment_transaction(initial, context(), 1, 0)
        operations = [row["operation"] for row in tx["mutationTrace"]]
        self.assertLess(operations.index("completionGuard"), operations.index("setPriority"))
        self.assertLess(operations.index("setPriority"), operations.index("defaultEconomy"))
        self.assertLess(operations.index("defaultEconomy"), operations.index("consumeProgress"))
        self.assertEqual(initial.regions[1].mission_control, 0)
        self.assertEqual(initial.control_points[1].pips["MissionControl"], 0)
        self.assertEqual(initial.control_points[1].pips["Economy"], 1)

    @mechanic_rule_test(Rules.NATION_PRIORITY_MISSION_CONTROL_PLACEMENT.id)
    def test_mission_control_single_candidate_is_exact(self):
        initial = state(pips={"MissionControl": 3}, progress={"MissionControl": 0.99})
        initial.regions[1].mission_control = 0
        initial.mission_control = 0
        tx = projection._run_investment_transaction(initial, context(), 1, 0)
        event = tx["completions"][0]
        self.assertEqual(event["effectiveCoverage"], "exact")
        self.assertEqual(event["regionId"], 1)
        self.assertEqual(initial.mission_control, 1)

    @mechanic_rule_test(Rules.NATION_PRIORITY_MISSION_CONTROL_PLACEMENT.id)
    def test_mission_control_non_equivalent_candidates_stop_before_mutation(self):
        initial = state(pips={"MissionControl": 3}, progress={"MissionControl": 0.99})
        second = copy.deepcopy(initial.regions[1])
        second.id = 2
        second.region_order = 1
        second.colony = True
        initial.regions[1].mission_control = 0
        second.mission_control = 0
        initial.regions[2] = second
        initial.mission_control = sum(region.mission_control for region in initial.regions.values())
        result = projection.run_projection(
            initial,
            projection.PriorityPlan("p", (projection.PlanSegment(None, None, None, None),)),
            context(),
            days=1,
        )
        self.assertEqual(result["status"], "incomplete")
        self.assertIn(Rules.NATION_PRIORITY_MISSION_CONTROL_PLACEMENT.id, result["missingMechanicRules"])
        self.assertEqual(result["lastAuthoritativeState"]["nation"]["missionControl"], 0)
        self.assertEqual(initial.progress["MissionControl"], 0.99)

    def test_interrupted_transaction_keeps_completed_authoritative_prefix(self):
        initial = state(
            pips={"Knowledge": 1, "MissionControl": 1},
            progress={"Knowledge": 0.99, "MissionControl": 0.99},
        )
        second = copy.deepcopy(initial.regions[1])
        second.id = 2
        second.region_order = 1
        second.colony = True
        initial.regions[1].mission_control = 0
        second.mission_control = 0
        initial.regions[2] = second
        initial.mission_control = 0
        result = projection.run_projection(
            initial,
            projection.PriorityPlan("p", (projection.PlanSegment(None, None, None, None),)),
            context(),
            days=1,
            details=True,
        )
        self.assertEqual(result["status"], "incomplete")
        self.assertGreater(result["lastAuthoritativeState"]["nation"]["education"], 8.0)
        event = result["completionEvents"][0]
        self.assertEqual(event["priority"], "Knowledge")
        self.assertEqual(event["transactionStatus"], "authoritativePrefix")
        self.assertEqual(result["transactions"], [])
        attempted = result["runtimeStop"]["attemptedTransaction"]
        self.assertEqual(attempted["phase"], "priorityCompletion")
        self.assertEqual(attempted["completions"][0]["priority"], "Knowledge")
        self.assertEqual(result["runtimeStop"]["lastAuthoritativeTransaction"]["transactionStatus"], "authoritativePrefix")
        self.assertEqual(result["runtimeStop"]["trigger"]["priority"], "MissionControl")

    @mechanic_rule_test(
        Rules.NATION_PRIORITY_WELFARE_INEQUALITY.id,
        Rules.NATION_PRIORITY_WELFARE_COLONY_TRIGGER.id,
        Rules.NATION_PRIORITY_WELFARE_DECOLONIZATION.id,
        Rules.NATION_PRIORITY_WELFARE_DECOLONIZATION_DOWNSTREAM.id,
    )
    def test_welfare_missing_decolonization_dependency_rolls_back_completion(self):
        initial = state(pips={"Welfare": 3}, progress={"Welfare": 0.99})
        initial.regions[1].colony = True
        initial.regions[1].permanent_colony = None
        initial.regions[1].welfare_colony_counter = 999
        result = projection.run_projection(
            initial,
            projection.PriorityPlan("p", (projection.PlanSegment(None, None, None, None),)),
            context(),
            days=1,
        )
        self.assertEqual(result["status"], "incomplete")
        self.assertIn(Rules.NATION_PRIORITY_WELFARE_DECOLONIZATION_DOWNSTREAM.id, result["missingMechanicRules"])
        self.assertEqual(result["lastAuthoritativeState"]["nation"]["inequality"], 4.0)
        self.assertEqual(initial.regions[1].welfare_colony_counter, 999)

    @mechanic_rule_test(Rules.NATION_PERIODIC_CONTROL_POINTS.id)
    def test_monthly_control_point_count_change_rolls_back_before_population(self):
        initial = state(at=datetime(2030, 1, 31, 12), annual_growth=0.12)
        ctx = context()
        ctx.global_config["controlPointCountScaling"]["value"] = 0.35
        result = projection.run_projection(
            initial,
            projection.PriorityPlan("p", (projection.PlanSegment(None, None, None, None),)),
            ctx,
            days=1,
        )
        self.assertEqual(result["status"], "incomplete")
        self.assertIn(Rules.NATION_PERIODIC_CONTROL_POINTS.id, result["missingMechanicRules"])
        self.assertEqual(result["lastAuthoritativeState"]["nation"]["populationMillions"], 50.0)
        self.assertEqual(result["runtimeStop"]["at"], "2030-02-01T00:00:00")
        self.assertEqual(result["runtimeStop"]["phase"], "beforeControlPointCountMutation")
        self.assertEqual(result["runtimeStop"]["stateContext"]["currentControlPointCount"], 1)
        self.assertGreater(result["runtimeStop"]["stateContext"]["requiredControlPointCount"], 1)
        self.assertEqual(result["runtimeStop"]["transactionKind"], "monthly")

    def test_government_cap_effect_cost_and_economy_fallback_are_authoritative(self):
        initial = state(pips={"Government": 3}, progress={"Government": 0.99})
        initial.democracy = 9.999
        result = projection.run_projection(
            initial,
            projection.PriorityPlan("p", (projection.PlanSegment(None, None, None, None),)),
            context(),
            days=2,
            details=True,
        )
        self.assertEqual(result["status"], "incomplete")
        self.assertEqual(result["lastAuthoritativeState"]["nation"]["democracy"], 10.0)
        self.assertLess(result["lastAuthoritativeState"]["nation"]["priorityProgress"]["Government"], 1.0)
        control_point = result["lastAuthoritativeState"]["controlPoints"][0]
        self.assertEqual(control_point["rawPips"]["Government"], 3)
        self.assertEqual(control_point["rawPips"]["Economy"], 1)
        self.assertEqual(control_point["effectivePips"], {"Economy": 1})
        government_event = next(event for event in result["completionEvents"] if event["priority"] == "Government")
        self.assertEqual(government_event["remainingProgress"], result["lastAuthoritativeState"]["nation"]["priorityProgress"]["Government"])
        self.assertEqual(result["runtimeStop"]["phase"], "beforeAllocation")
        self.assertTrue(any(
            row["operation"] == "defaultEconomy"
            for row in result["runtimeStop"]["authoritativeMutations"]
        ))
        self.assertFalse(any(
            row["ruleId"] == Rules.NATION_PRIORITY_ECONOMY_COMPLETE.id
            for row in result["ruleExecutions"]
        ))

    def test_runtime_unsupported_economy_fallback_preserves_authoritative_prefix(self):
        initial = state(pips={"MissionControl": 3}, progress={"MissionControl": 0.99})
        initial.regions[1].mission_control = 0
        initial.regions[1].fully_occupied = True
        initial.mission_control = 0
        plan = projection.PriorityPlan("p", (projection.PlanSegment(None, None, None, None),))
        result = projection.run_projection(initial, plan, context(), days=2, details=True)
        self.assertEqual(result["status"], "incomplete")
        self.assertIn("nation.priority.economy.complete", result["missingMechanicRules"])
        self.assertEqual(result["lastAuthoritativeState"]["nation"]["missionControl"], 0)
        control_point = result["lastAuthoritativeState"]["controlPoints"][0]
        self.assertEqual(control_point["rawPips"]["MissionControl"], 0)
        self.assertEqual(control_point["rawPips"]["Economy"], 1)
        self.assertEqual(control_point["effectivePips"], {"Economy": 1})
        self.assertEqual(result["runtimeStop"]["phase"], "beforeAllocation")
        self.assertEqual(result["runtimeStop"]["trigger"]["priority"], "Economy")
        self.assertEqual(result["runtimeStop"]["unsupportedNextStep"]["mechanic"], "priorityAllocation")
        self.assertTrue(any(event["priority"] == "MissionControl" for event in result["completionEvents"]))
        self.assertFalse(any(
            row["ruleId"] == Rules.NATION_PRIORITY_ECONOMY_COMPLETE.id
            for row in result["ruleExecutions"]
        ))
        self.assertEqual(initial.control_points[1].pips["MissionControl"], 3)

    def test_scheduler_runs_monthly_before_daily_investment_and_noon_cache(self):
        initial = state(at=datetime(2030, 1, 31, 12), annual_growth=0.0)
        plan = projection.PriorityPlan("p", (projection.PlanSegment(None, None, None, None),))
        result = projection.run_projection(initial, plan, context(), days=1, details=True)
        self.assertEqual([row["kind"] for row in result["transactions"]], ["monthly", "investment", "derivedCache"])
        self.assertEqual([row["at"][-8:] for row in result["transactions"]], ["00:00:00", "10:30:00", "12:00:00"])

    @mechanic_rule_test(Rules.NATION_PRIORITY_BUILD_ARMY_PLACEMENT.id, Rules.NATION_ASSET_ARMY_MAINTENANCE.id)
    def test_build_army_deterministic_selection_and_next_tick_maintenance(self):
        initial = state(pips={"Military_BuildArmy": 3}, cp_count=2, progress={"Military_BuildArmy": 0.99})
        initial.regions[2] = projection.RegionProjectionState(
            id=2, population_millions=40.0, mission_control=0, region_order=1,
            latitude=5.0, longitude=5.0, annual_population_growth=0.0,
            annual_population_growth_modifier=0.0, environment="Standard", xenoforming_level=0.0,
            nuclear_detonations=0, colony=False, permanent_colony=False, resource_region=False,
            oil_region=False, core_economic_region=True, capital=False, occupation_fraction=0.0,
            fully_occupied=False, welfare_colony_counter=0,
        )
        projection._refresh_economy_score(initial, context())
        before = projection._base_ip(initial, context())
        tx = projection._run_investment_transaction(initial, context(), 1, 0)
        event = next(row for row in tx["completions"] if row["priority"] == "Military_BuildArmy")
        self.assertEqual(event["homeRegionId"], 2)
        self.assertEqual(event["controlPointPosition"], 1)
        self.assertAlmostEqual(projection._base_ip(initial, context()), before - 0.5)

    @mechanic_rule_test(Rules.NATION_POPULATION_ANNUAL_GROWTH.id, Rules.NATION_POPULATION_MONTHLY_GROWTH.id)
    def test_population_formula_uses_deterministic_mean_input_not_trajectory_expectation(self):
        initial = state(annual_growth=None)
        region = initial.regions[1]
        expected_percent = (
            4.49788037409348
            + max(-4.49788037409348, -0.418190741 * 8.0)
            - 0.0624798523403752 * 4.0
            + 9.80843732089162e-06 * 20_000.0
            - 0.115739931206548 * (10.0 ** 0.5)
        )
        self.assertAlmostEqual(projection._annual_population_growth(initial, region, context()), expected_percent * 0.01)

    def test_unsupported_priority_fails_closed(self):
        initial = state(pips={"Economy": 3})
        result = projection.run_projection(initial, projection.PriorityPlan("p", (projection.PlanSegment(None, None, None, None),)), context(), days=1)
        self.assertEqual(result["status"], "incomplete")
        self.assertIsNone(result["authoritativeFinalState"])
        self.assertIn("nation.priority.economy.complete", result["missingMechanicRules"])


if __name__ == "__main__":
    unittest.main()
