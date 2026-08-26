import os
import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import ti_save_parser as parser
import ti_parser_nation_projection as projection


REAL_SAVE = os.environ.get("TI_PARSER_REAL_SAVE")


@unittest.skipUnless(REAL_SAVE, "TI_PARSER_REAL_SAVE is not set")
class NationProjectionRealSaveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.save_path = Path(str(REAL_SAVE))
        if not cls.save_path.is_file():
            raise unittest.SkipTest("TI_PARSER_REAL_SAVE does not point to a file")
        cls.indexed = parser.build_index(parser.load_save(cls.save_path))
        cls.nation_id, cls.nation = parser.match_raw_state(cls.indexed, "TINationState", "CAL")
        if cls.nation_id is None or cls.nation is None:
            raise unittest.SkipTest("CAL is not present in the selected real save")

    def _all_cp_plan(self, name, pips, *, days=365, goals=None, segments=None, details=False):
        positions = sorted(cp["positionInNation"] for cp in parser.nation_control_points(self.indexed, self.nation))
        if segments is None:
            segments = [{"controlPoints": [{"position": position, "pips": dict(pips)} for position in positions]}]
        payload = {"plans": [{"name": name, "segments": segments}]}
        if goals:
            payload["goals"] = goals
        return parser.calculate_nation_projection(
            self.indexed,
            "CAL",
            None,
            payload,
            days=days,
            checkpoints=[value for value in (30, 90, 180, 365) if value <= days],
            details=details,
            diagnostics=True,
        )["plans"][0]

    def test_default_plan_reports_active_dormant_and_fail_closed_blockers(self):
        result = parser.calculate_nation_projection(
            self.indexed,
            "CAL",
            None,
            None,
            days=1,
            checkpoints=[],
            details=False,
            diagnostics=True,
        )["plans"][0]
        self.assertEqual(result["status"], "incomplete")
        self.assertIsNone(result["authoritativeFinalState"])
        self.assertIn("activePriorities", result["preflight"])
        self.assertIn("dormantPriorities", result["preflight"])
        self.assertTrue(result["missingMechanicRules"])

    def test_knowledge_only_year_runs_population_monthly_and_quarterly_boundaries(self):
        result = self._all_cp_plan("knowledge", {"Knowledge": 3})
        self.assertEqual(result["status"], "complete")
        self.assertEqual(len(result["checkpoints"]), 4)
        self.assertEqual(result["metricCoverage"]["nation.population"]["coverage"], "expected")
        self.assertIn("meanPath", result["metricCoverage"]["nation.population"]["provenance"])
        self.assertIn("heldFixedWorldContext", result["metricCoverage"]["nation.population"]["provenance"])
        self.assertFalse(result["metricCoverage"]["nation.population"]["expectationGuarantee"])

    def test_government_condition_switches_to_knowledge_on_next_investment_tick(self):
        initial_democracy = float(self.nation["democracy"])
        positions = sorted(cp["positionInNation"] for cp in parser.nation_control_points(self.indexed, self.nation))
        segments = [
            {
                "until": {"metric": "nation.democracy", "op": ">=", "value": initial_democracy + 0.001},
                "controlPoints": [{"position": position, "pips": {"Government": 3}} for position in positions],
            },
            {"controlPoints": [{"position": position, "pips": {"Knowledge": 3}} for position in positions]},
        ]
        result = self._all_cp_plan("government-knowledge", {}, days=90, segments=segments, details=True)
        self.assertEqual(result["status"], "complete")
        self.assertGreaterEqual(len(result["segmentTransitions"]), 2)
        transition = result["segmentTransitions"][-1]
        self.assertGreater(transition["effectiveDay"], transition["day"])

    def test_welfare_and_knowledge_run_without_activating_distant_decolonization(self):
        result = self._all_cp_plan("welfare-knowledge", {"Welfare": 2, "Knowledge": 1}, days=90, details=True)
        self.assertEqual(result["status"], "complete")
        executions = [row for row in result["ruleExecutions"] if row["ruleId"] == "nation.priority.welfare.complete"]
        self.assertTrue(executions)
        self.assertTrue(all("nation.priority.welfare.decolonization" not in row["dependencies"] for row in executions))

    def test_current_mc_and_army_paths_resolve_from_save_state_without_hardcoded_ids(self):
        output = parser.calculate_nation_projection(
            self.indexed,
            "CAL",
            None,
            {"plans": [{"name": "extract", "segments": [{"controlPoints": [
                {"position": cp["positionInNation"], "pips": {"Knowledge": 3}}
                for cp in parser.nation_control_points(self.indexed, self.nation)
            ]}]}]},
            days=0,
            checkpoints=[],
            details=False,
            diagnostics=False,
        )
        self.assertEqual(output["plans"][0]["status"], "complete")

        catalogs = parser.calculation_catalogs(self.indexed, "nation-projection-real-save")
        development = catalogs.nation_development
        faction_id, faction = parser.find_faction_state(self.indexed, None)
        _, summaries = parser.councilor_summary_maps(self.indexed, catalogs.traits)
        all_advisors, _ = parser.projection_advisor_profiles(self.indexed, faction_id, faction, summaries)
        owner_bonuses = {}
        for cp in parser.nation_control_points(self.indexed, self.nation):
            owner_id = parser.ref_id(cp.get("faction"))
            owner = parser.state_value_by_id(self.indexed, owner_id)
            if owner_id is not None and isinstance(owner, dict) and owner_id not in owner_bonuses:
                owner_bonuses[owner_id] = parser.faction_priority_bonuses_for_projection(
                    self.indexed, owner_id, owner, development["priorities"], catalogs.traits, catalogs.effects
                )
        state = parser.extract_nation_projection_state(
            self.indexed, self.nation_id, self.nation, all_advisors, owner_bonuses, development
        )
        context = projection.ProjectionContext(
            faction_id=faction_id,
            priorities=development["priorities"],
            global_config=development["globalConfig"],
            diversity_bonuses=development["diversityBonuses"],
            nation_template=development["nationTemplates"][self.nation["templateName"]],
            start_template=development["startTimeTemplates"][parser.first_value(self.indexed, "TITimeState")["templateName"]],
        )

        mc_candidates = projection._mission_control_candidates(state, context)
        if len(mc_candidates) == 1:
            state.progress["MissionControl"] = float(development["priorities"]["MissionControl"]["investmentCost"]) - 0.001
            for cp in state.control_points.values():
                cp.pips = {"MissionControl": 3}
            transaction = projection._run_investment_transaction(state, context, 1, 0)
            event = next(row for row in transaction["completions"] if row["priority"] == "MissionControl")
            self.assertEqual(event["regionId"], mc_candidates[0].id)
            self.assertEqual(event["effectiveCoverage"], "exact")

        army_target = projection._next_army_region(state)
        if army_target is not None and projection._priority_valid(state, "Military_BuildArmy", context):
            state.progress["Military_BuildArmy"] = float(development["priorities"]["Military_BuildArmy"]["investmentCost"]) - 0.001
            for cp in state.control_points.values():
                cp.pips = {"Military_BuildArmy": 3}
            before = projection._base_ip(state, context)
            transaction = projection._run_investment_transaction(state, context, 2, 0)
            event = next(row for row in transaction["completions"] if row["priority"] == "Military_BuildArmy")
            self.assertEqual(event["homeRegionId"], army_target.id)
            self.assertEqual(event["effectiveCoverage"], "exact")
            self.assertLess(projection._base_ip(state, context), before)


if __name__ == "__main__":
    unittest.main()
