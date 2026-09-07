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
        found = parser.match_raw_state(cls.indexed, "TINationState", "CAL")
        preferred_id, preferred = found if found else (None, None)

        def viable(nation):
            if not isinstance(nation, dict) or not nation.get("controlPoints") or not nation.get("regions"):
                return False
            refs = (*nation.get("controlPoints", []), *nation.get("regions", []))
            return all(
                isinstance(parser.state_value_by_id(cls.indexed, parser.ref_id(ref)), dict)
                for ref in refs
            )

        if viable(preferred):
            cls.nation_id, cls.nation = preferred_id, preferred
        else:
            candidates = []
            for entry in parser.type_entries(cls.indexed, "TINationState"):
                nation = entry.get("Value") or {}
                nation_id = parser.raw_state_id(entry)
                if nation_id is not None and nation.get("templateName") != "ALN" and viable(nation):
                    candidates.append((nation_id, nation))
            if not candidates:
                raise unittest.SkipTest("The selected real save has no projection-capable nation")
            cls.nation_id, cls.nation = min(candidates, key=lambda item: item[0])
        cls.nation_token = str(cls.nation.get("templateName") or cls.nation_id)
        cls.positions = sorted(cp["positionInNation"] for cp in parser.nation_control_points(cls.indexed, cls.nation))

    def _all_cp_plan(
        self,
        name,
        pips,
        *,
        days=365,
        goals=None,
        segments=None,
        details=False,
        unity_policy=None,
    ):
        if segments is None:
            segments = [{"controlPoints": [{"position": position, "pips": dict(pips)} for position in self.positions]}]
        plan = {"name": name, "segments": segments}
        if unity_policy is not None:
            plan["stochasticPolicy"] = {"unityPublicOpinion": unity_policy}
        payload = {"plans": [plan]}
        if goals:
            payload["goals"] = goals
        return parser.calculate_nation_projection(
            self.indexed,
            self.nation_token,
            None,
            payload,
            days=days,
            checkpoints=[value for value in (30, 90, 180, 365) if value <= days],
            details=details,
            diagnostics=True,
        )["plans"][0]

    def _projection_state_context(self):
        catalogs = parser.calculation_catalogs(self.indexed, "nation-projection")
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
        return state, context, development

    @staticmethod
    def _expected_mc_candidates(state, context):
        def global_value(name):
            return float(context.global_config[name]["value"])

        ordered = sorted(state.regions.values(), key=lambda region: region.region_order)
        weights = []
        for region in ordered:
            weight = region.population_millions
            if region.core_economic_region:
                weight *= global_value("coreEcoRegionGDPModifier")
            if region.resource_region or region.oil_region:
                weight *= global_value("coreResourceRegionGDPModifier")
            if region.colony:
                weight *= global_value("colonyRegionGDPModifier")
            weights.append(weight)
        total = sum(weights)
        divisor = max(200.0, 300.0 - 6.0 * state.education)
        result = []
        for region, weight in zip(ordered, weights):
            regional_gdp = state.gdp * weight / total
            cap = max(region.mission_control, 1 + int((regional_gdp / 1_000_000_000.0) / divisor))
            if not region.fully_occupied and region.mission_control < cap:
                result.append(region)
        return result

    @staticmethod
    def _expected_army_target(state):
        homes = {army.home_region_id for army in state.standard_armies}
        candidates = [
            region for region in sorted(state.regions.values(), key=lambda region: region.region_order)
            if not region.fully_occupied and not region.colony and region.id not in homes
        ]
        if any(region.core_economic_region for region in candidates):
            candidates = [region for region in candidates if region.core_economic_region]
        return max(candidates, key=lambda region: region.population_millions, default=None)

    @staticmethod
    def _expected_army_cp_position(state):
        positions = sorted(cp.position for cp in state.control_points.values())
        counts = {position: 0 for position in positions}
        for army in state.standard_armies:
            if army.control_point_position in counts:
                counts[army.control_point_position] += 1
        maximum = max(counts.values(), default=0)
        selected = positions[-1]
        selected_count = counts[selected]
        for position in reversed(positions):
            count = counts[position]
            if count < maximum and count < selected_count:
                selected = position
                selected_count = count
        return selected

    def test_default_plan_reports_active_dormant_and_fail_closed_blockers(self):
        result = parser.calculate_nation_projection(
            self.indexed,
            self.nation_token,
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
        for metric in (
            "nation.education", "nation.cohesion", "nation.cohesionRest", "nation.unrestRest",
            "nation.baseInvestmentPointsMonth", "nation.research", "factionContribution.research",
        ):
            with self.subTest(metric=metric):
                self.assertEqual(result["metricCoverage"][metric]["coverage"], "expected")
                self.assertIn("meanPath", result["metricCoverage"][metric]["provenance"])

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

    def test_one_year_policy_matrix_runs_independently(self):
        initial_democracy = float(self.nation["democracy"])
        conditional_segments = [
            {
                "until": {"metric": "nation.democracy", "op": ">=", "value": initial_democracy + 0.001},
                "controlPoints": [{"position": position, "pips": {"Government": 3}} for position in self.positions],
            },
            {
                "controlPoints": [
                    {"position": position, "pips": {"Knowledge": 2, "Welfare": 1}}
                    for position in self.positions
                ],
            },
        ]
        cases = (
            ("government", {"Government": 3}, None),
            ("government-knowledge", {"Government": 1, "Knowledge": 2}, None),
            ("knowledge-welfare", {"Knowledge": 2, "Welfare": 1}, None),
            ("government-condition-knowledge-welfare", {}, conditional_segments),
        )
        for name, pips, segments in cases:
            with self.subTest(plan=name):
                result = self._all_cp_plan(name, pips, days=365, segments=segments, details=True)
                self.assertEqual(result["status"], "complete")
                self.assertEqual(len(result["checkpoints"]), 4)
                self.assertTrue(result["completionEvents"])
                if segments is not None:
                    self.assertGreaterEqual(len(result["segmentTransitions"]), 2)

    def test_nation_ui_live_validity_matches_serialized_control_point_totals(self):
        result = parser.calculate_nation_ui(self.indexed, None, self.nation_token)
        priorities = result["priorities"]
        mission_control = priorities["validityByPriority"].get("MissionControl")
        self.assertIsNotNone(mission_control)
        inactive = next((row["weights"] for row in priorities["rows"] if row["key"] == "_inactiveRawWeights"), {})
        if mission_control["valid"]:
            self.assertNotIn("MissionControl", inactive)
        for row in priorities["controlPoints"]:
            if not row["unknownPriorities"]:
                self.assertTrue(row["consistent"])

    def test_build_navy_validity_matches_extracted_coastal_state(self):
        ui_validity = parser.calculate_nation_ui(self.indexed, None, self.nation_token)["priorities"]["validityByPriority"]
        state, context, _ = self._projection_state_context()
        self.assertTrue(all(region.ocean_type in {"No", "None", "Yes", "Seasonal"} for region in state.regions.values()))
        self.assertEqual(
            ui_validity["Military_BuildNavy"]["valid"],
            projection._priority_valid(state, "Military_BuildNavy", context),
        )

    def test_current_mc_and_army_paths_resolve_from_save_state_without_hardcoded_ids(self):
        output = parser.calculate_nation_projection(
            self.indexed,
            self.nation_token,
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

        state, context, development = self._projection_state_context()

        mc_candidates = self._expected_mc_candidates(state, context)
        if len(mc_candidates) == 1:
            mc_plan = self._all_cp_plan(
                "mc-knowledge", {"MissionControl": 2, "Knowledge": 1}, days=365, details=True
            )
            self.assertEqual(mc_plan["status"], "complete")
            mc_plan_event = next(event for event in mc_plan["completionEvents"] if event["priority"] == "MissionControl")
            self.assertEqual(mc_plan_event["regionId"], mc_candidates[0].id)
            self.assertEqual(mc_plan_event["effectiveCoverage"], "exact")
            state.progress["MissionControl"] = float(development["priorities"]["MissionControl"]["investmentCost"]) - 0.001
            for cp in state.control_points.values():
                cp.pips = {"MissionControl": 3}
            transaction = projection._run_investment_transaction(state, context, 1, 0)
            event = next(row for row in transaction["completions"] if row["priority"] == "MissionControl")
            self.assertEqual(event["regionId"], mc_candidates[0].id)
            self.assertEqual(event["effectiveCoverage"], "exact")

        army_target = self._expected_army_target(state)
        if army_target is not None and projection._priority_valid(state, "Military_BuildArmy", context):
            army_plan = self._all_cp_plan(
                "army-knowledge", {"Military_BuildArmy": 2, "Knowledge": 1}, days=365, details=True
            )
            self.assertEqual(army_plan["status"], "complete")
            army_plan_event = next(event for event in army_plan["completionEvents"] if event["priority"] == "Military_BuildArmy")
            self.assertEqual(army_plan_event["homeRegionId"], army_target.id)
            self.assertEqual(army_plan_event["effectiveCoverage"], "exact")
            expected_position = self._expected_army_cp_position(state)
            self.assertEqual(army_plan_event["controlPointPosition"], expected_position)
            state.progress["Military_BuildArmy"] = float(development["priorities"]["Military_BuildArmy"]["investmentCost"]) - 0.001
            for cp in state.control_points.values():
                cp.pips = {"Military_BuildArmy": 3}
            transaction = projection._run_investment_transaction(state, context, 2, 0)
            event = next(row for row in transaction["completions"] if row["priority"] == "Military_BuildArmy")
            self.assertEqual(event["homeRegionId"], army_target.id)
            self.assertEqual(event["controlPointPosition"], expected_position)
            self.assertEqual(event["effectiveCoverage"], "exact")
            for cp in state.control_points.values():
                cp.pips = {"Knowledge": 3}
            next_transaction = projection._run_investment_transaction(state, context, 3, 0)
            expected_maintenance = float(context.global_config["nationalInvestmentArmyFactorHome"]["value"])
            self.assertAlmostEqual(
                transaction["baseInvestmentPointsMonth"] - next_transaction["baseInvestmentPointsMonth"],
                expected_maintenance,
            )

    def test_long_government_fallback_can_reach_later_economy_completion(self):
        result = self._all_cp_plan("government-long", {"Government": 3}, days=2500, details=True)
        self.assertTrue(any(event["priority"] == "Government" for event in result["completionEvents"]))
        self.assertTrue(any(
            row["ruleId"] == "nation.priority.economy.complete"
            for row in result["ruleExecutions"]
        ))
        if result["status"] == "incomplete":
            self.assertEqual(result["runtimeStop"]["trigger"]["ruleId"], "nation.periodic.control-points")

    def test_economy_and_unity_observational_matrix(self):
        cases = (
            ("economy", {"Economy": 3}, None),
            ("economy-knowledge", {"Economy": 2, "Knowledge": 1}, None),
            ("unity", {"Unity": 3}, "meanPath"),
            ("unity-knowledge-welfare", {"Unity": 1, "Knowledge": 1, "Welfare": 1}, "meanPath"),
            ("economy-unity", {"Economy": 2, "Unity": 1}, "meanPath"),
        )
        for name, pips, unity_policy in cases:
            with self.subTest(plan=name):
                result = self._all_cp_plan(
                    name,
                    pips,
                    days=365,
                    details=True,
                    unity_policy=unity_policy,
                )
                self.assertTrue(result["completionEvents"])
                if result["status"] == "incomplete":
                    self.assertEqual(
                        result["runtimeStop"]["trigger"]["ruleId"],
                        "nation.periodic.control-points",
                    )
                if "Unity" in pips:
                    opinion_rows = [
                        value for key, value in result["metricCoverage"].items()
                        if key.startswith("nation.publicOpinion.")
                    ]
                    self.assertTrue(opinion_rows)
                    self.assertTrue(all(row["coverage"] == "expected" for row in opinion_rows))
                    self.assertTrue(all(
                        "deterministicExpectedTransition" in row.get("stochasticTreatments", [])
                        for row in opinion_rows
                    ))

    def test_unity_without_opt_in_fails_preflight(self):
        result = self._all_cp_plan("unity-no-opt-in", {"Unity": 3}, days=1)
        self.assertEqual(result["status"], "incomplete")
        self.assertEqual(
            result["preflight"]["stochasticPolicyBlockers"][0]["policy"],
            "unityPublicOpinion",
        )


if __name__ == "__main__":
    unittest.main()
