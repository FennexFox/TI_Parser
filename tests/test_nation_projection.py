import sys
import unittest
from datetime import datetime
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import ti_parser_nation_projection as projection


def context(*, priorities=None, diversity=None):
    priorities = priorities or {
        "Economy": {"enumValue": 0, "investmentCost": 1},
        "Knowledge": {"enumValue": 3, "investmentCost": 1},
        "Government": {"enumValue": 4, "investmentCost": 1},
        "Unity": {"enumValue": 5, "investmentCost": 2},
        "Funding": {"enumValue": 7, "investmentCost": 1},
    }
    values = {
        "nationalInvestmentArmyFactorHome": {"value": 0.5},
        "nationalInvestmentArmyFactorAway": {"value": 1.0},
        "nationalInvestmentNavyFactor": {"value": 0.5},
        "populationBasedIPEffectScaling": {"value": -0.35},
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
        regions={1: projection.RegionProjectionState(1, 50.0, 12.0, 4, annual_growth, 20_000)},
        control_points=control_points,
        advisors=tuple(advisors),
        mission_control=4,
    )


class NationProjectionPlanTests(unittest.TestCase):
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
    def test_one_tick_control_point_allocation(self):
        initial = state()
        initial.unrest = 0
        tx = projection._run_investment_transaction(initial, context(), 1, 0)
        self.assertAlmostEqual(tx["allocation"]["Knowledge"], 30 * 12 / projection.DAYS_PER_YEAR)

    def test_diversity_and_owner_priority_bonus(self):
        initial = state(pips={"Knowledge": 1, "Unity": 1})
        initial.unrest = 0
        initial.control_points[1].priority_bonuses = {"Knowledge": 0.2}
        tx = projection._run_investment_transaction(initial, context(), 1, 0)
        base_share = 30 * 0.5 * 12 / projection.DAYS_PER_YEAR
        self.assertAlmostEqual(tx["allocation"]["Knowledge"], base_share * 1.3)

    def test_advisor_base_ip_and_rank_decay(self):
        advisors = (
            projection.AdvisorProfile("virtual", "a", 20, 10),
            projection.AdvisorProfile("virtual", "b", 10, 20),
        )
        initial = state(advisors=advisors)
        initial.economy_score = 10
        initial.unrest = 0
        self.assertAlmostEqual(projection._base_ip(initial), 12.5)

    def test_knowledge_completion(self):
        initial = state(progress={"Knowledge": 0.99})
        before = initial.education
        tx = projection._run_investment_transaction(initial, context(), 1, 0)
        self.assertEqual(tx["completions"][0]["priority"], "Knowledge")
        self.assertGreater(initial.education, before)

    def test_unity_completion(self):
        initial = state(pips={"Unity": 3}, progress={"Unity": 1.99})
        before = initial.cohesion
        projection._run_investment_transaction(initial, context(), 1, 0)
        self.assertGreater(initial.cohesion, before)

    def test_government_completion_below_cap(self):
        initial = state(pips={"Government": 3}, progress={"Government": 0.99})
        projection._run_investment_transaction(initial, context(), 1, 0)
        self.assertGreater(initial.democracy, 5.0)

    def test_funding_completion_and_contribution(self):
        initial = state(pips={"Funding": 3}, progress={"Funding": 0.99})
        before = projection._contribution(initial, context())["funding"]
        projection._run_investment_transaction(initial, context(), 1, 0)
        self.assertEqual(initial.funding_year, 111)
        self.assertGreater(projection._contribution(initial, context())["funding"], before)

    def test_condition_waits_for_multi_completion_transaction(self):
        initial = state(pips={"Knowledge": 3, "Unity": 3}, progress={"Knowledge": 0.99, "Unity": 1.99})
        condition = projection.MetricCondition("nation.cohesion", ">=", 4.01)
        plan = projection.PriorityPlan("p", (
            projection.PlanSegment(None, condition, None, None),
            projection.PlanSegment(None, None, None, ()),
        ))
        result = projection.run_projection(initial, plan, context(), days=1, details=True)
        investment = result["transactions"][0]
        self.assertEqual([event["priority"] for event in investment["completions"]], ["Knowledge", "Unity"])
        self.assertEqual(result["segmentTransitions"][-1]["effectiveDay"], 2)

    def test_conditional_pips_and_advisor_apply_together_next_tick(self):
        initial = state(pips={"Knowledge": 3})
        advisor = projection.AdvisorProfile("virtual", "admin", 20, 0)
        plan = projection.PriorityPlan("p", (
            projection.PlanSegment(1, None, None, None),
            projection.PlanSegment(None, None, (projection.ControlPointPolicy(1, {"Unity": 3}),), (advisor,)),
        ))
        result = projection.run_projection(initial, plan, context(), days=2, details=True)
        investments = [row for row in result["transactions"] if row["kind"] == "investment"]
        self.assertIn("Knowledge", investments[0]["allocation"])
        self.assertIn("Unity", investments[1]["allocation"])
        self.assertGreater(investments[1]["baseInvestmentPointsMonth"], investments[0]["baseInvestmentPointsMonth"])
        self.assertEqual(result["advisorTransitions"][-1]["day"], 2)

    def test_start_satisfied_segment_skips_before_first_tick(self):
        initial = state(pips={"Knowledge": 3})
        plan = projection.PriorityPlan("p", (
            projection.PlanSegment(None, projection.MetricCondition("nation.cohesion", ">=", 4.0), None, None),
            projection.PlanSegment(None, None, (projection.ControlPointPolicy(1, {"Unity": 3}),), None),
        ))
        result = projection.run_projection(initial, plan, context(), days=1, details=True)
        investment = next(row for row in result["transactions"] if row["kind"] == "investment")
        self.assertEqual(investment["segmentIndex"], 1)
        self.assertIn("Unity", investment["allocation"])

    def test_monthly_cohesion_and_unrest(self):
        initial = state(at=datetime(2030, 1, 31), annual_growth=0.0)
        result = projection.run_projection(initial, projection.PriorityPlan("p", (projection.PlanSegment(None, None, None, None),)), context(), days=1, details=True)
        self.assertEqual(result["status"], "complete")
        self.assertAlmostEqual(result["nationProjection"]["cohesion"], 4.1)
        self.assertAlmostEqual(result["nationProjection"]["unrest"], 2.75)

    def test_monthly_population_expected(self):
        initial = state(at=datetime(2030, 1, 31), annual_growth=0.12)
        before = initial.population_millions
        result = projection.run_projection(initial, projection.PriorityPlan("p", (projection.PlanSegment(None, None, None, None),)), context(), days=1)
        self.assertGreater(result["nationProjection"]["populationMillions"], before)

    def test_unsupported_priority_fails_closed(self):
        initial = state(pips={"Economy": 3})
        result = projection.run_projection(initial, projection.PriorityPlan("p", (projection.PlanSegment(None, None, None, None),)), context(), days=1)
        self.assertEqual(result["status"], "incomplete")
        self.assertIsNone(result["authoritativeFinalState"])
        self.assertIn("nation.priority.economy.complete", result["missingMechanicRules"])


if __name__ == "__main__":
    unittest.main()
