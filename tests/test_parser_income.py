import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import ti_parser_core as core
import ti_parser_income as income
import ti_save_parser as ti


class ParserIncomeTests(unittest.TestCase):
    def _build_indexed(self):
        payload = {
            "gamestates": {
                "TIFactionState": [
                    {
                        "Key": {"value": 1},
                        "Value": {
                            "ID": {"value": 1},
                            "templateName": "ResistCouncil",
                            "displayName": "Resistance",
                            "councilors": [{"value": 2}],
                        },
                    }
                ],
                "TICouncilorState": [
                    {
                        "Key": {"value": 2},
                        "Value": {
                            "ID": {"value": 2},
                            "displayName": "Ada",
                            "detained": False,
                            "isAlien": False,
                            "traitTemplateNames": ["Scholar"],
                            "orgs": [],
                        },
                    }
                ],
                "TIRegionState": [
                    {
                        "Key": {"value": 11},
                        "Value": {
                            "ID": {"value": 11},
                            "missionControl": 3,
                            "boostPerYear_dekatons": 0.5,
                        },
                    },
                    {
                        "Key": {"value": 12},
                        "Value": {
                            "ID": {"value": 12},
                            "missionControl": 2,
                            "boostPerYear_dekatons": 1.0,
                        },
                    },
                ],
                "TIControlPointState": [
                    {
                        "Key": {"value": 31},
                        "Value": {
                            "ID": {"value": 31},
                            "positionInNation": 0,
                            "controlPointType": "FinancialSector",
                            "faction": {"value": 1},
                            "benefitsDisabled": False,
                        },
                    },
                    {
                        "Key": {"value": 32},
                        "Value": {
                            "ID": {"value": 32},
                            "positionInNation": 1,
                            "controlPointType": "KnowledgeSector",
                            "faction": {"value": 1},
                            "benefitsDisabled": False,
                        },
                    },
                ],
                "TINationState": [
                    {
                        "Key": {"value": 21},
                        "Value": {
                            "ID": {"value": 21},
                            "displayName": "Testland",
                            "GDP": 1_000_000.0,
                            "education": 10.0,
                            "democracy": 6.0,
                            "cohesion": 5.0,
                            "unrest": 0.0,
                            "numControlPoints": 2,
                            "military": True,
                            "spaceFunding_year": 120.0,
                            "controlPoints": [{"value": 31}, {"value": 32}],
                            "regions": [{"value": 11}, {"value": 12}],
                        },
                    }
                ],
                "TITraitTemplate": [
                    {
                        "Key": {"value": 100},
                        "Value": {
                            "ID": {"value": 100},
                            "dataName": "Scholar",
                            "incomeResearch": 2.5,
                            "incomeMissionControl": 1.0,
                            "incomeMoney": 3.0,
                        },
                    }
                ],
            }
        }
        return core.build_index(payload)

    def test_income_wrappers_match_direct_module_calls(self):
        indexed = self._build_indexed()
        faction = core.state_value_by_id(indexed, 1)
        nation = core.state_value_by_id(indexed, 21)
        councilor = core.state_value_by_id(indexed, 2)
        self.assertIsNotNone(faction)
        self.assertIsNotNone(nation)
        self.assertIsNotNone(councilor)

        trait_templates = {
            "Scholar": {
                "incomeResearch": 2.5,
                "incomeMissionControl": 1.0,
                "incomeMoney": 3.0,
            }
        }
        councilor_by_id = {2: {"finalAttributes": {"Science": 10.0}}}

        self.assertEqual(
            ti.councilor_research_and_mc(indexed, faction, trait_templates, councilor_by_id),
            income.councilor_research_and_mc(
                indexed,
                faction,
                trait_templates,
                councilor_by_id,
                ti.faction_councilor_ids,
                ti.INCOME_CONFIG,
            ),
        )
        self.assertEqual(
            ti.nation_money_contribution_month(indexed, nation, 1),
            income.nation_money_contribution_month(indexed, nation, 1, ti.INCOME_CONFIG),
        )
        self.assertEqual(
            ti.nation_research_contribution_month(indexed, nation, 1, councilor_by_id, {}, {}),
            income.nation_research_contribution_month(
                indexed,
                nation,
                1,
                councilor_by_id,
                {},
                {},
                ti.INCOME_CONFIG,
            ),
        )
        self.assertEqual(
            ti.nation_mission_control_contribution(indexed, nation, 1),
            income.nation_mission_control_contribution(indexed, nation, 1),
        )

    def test_mission_control_remainder_uses_nation_position_for_owned_subset(self):
        indexed = self._build_indexed()
        nation = core.state_value_by_id(indexed, 21)
        second_cp = core.state_value_by_id(indexed, 32)
        self.assertIsNotNone(nation)
        self.assertIsNotNone(second_cp)
        # Five MC over two points gives the final, position-1 point the extra MC.
        core.state_value_by_id(indexed, 31)["faction"] = {"value": 2}
        self.assertEqual(income.nation_mission_control_contribution(indexed, nation, 1), 3)

    def test_mission_control_missing_position_fails_closed_when_remainder_matters(self):
        indexed = self._build_indexed()
        nation = core.state_value_by_id(indexed, 21)
        second_cp = core.state_value_by_id(indexed, 32)
        self.assertIsNotNone(nation)
        self.assertIsNotNone(second_cp)
        core.state_value_by_id(indexed, 31)["faction"] = {"value": 2}
        second_cp.pop("positionInNation")

        with self.assertRaises(core.CalculationDependencyError) as raised:
            income.nation_mission_control_contribution(indexed, nation, 1)

        dependency = raised.exception.missing_dependencies[0]
        self.assertEqual(dependency["kind"], "control-point-position")
        self.assertEqual(dependency["context"], "nation-mission-control-contribution")

    def test_mission_control_invalid_position_fails_closed_when_remainder_matters(self):
        indexed = self._build_indexed()
        nation = core.state_value_by_id(indexed, 21)
        second_cp = core.state_value_by_id(indexed, 32)
        self.assertIsNotNone(nation)
        self.assertIsNotNone(second_cp)
        core.state_value_by_id(indexed, 31)["faction"] = {"value": 2}
        second_cp["positionInNation"] = 2

        with self.assertRaises(core.CalculationDependencyError):
            income.nation_mission_control_contribution(indexed, nation, 1)

    def test_mission_control_missing_position_is_not_needed_for_even_split(self):
        indexed = self._build_indexed()
        nation = core.state_value_by_id(indexed, 21)
        second_cp = core.state_value_by_id(indexed, 32)
        first_region = core.state_value_by_id(indexed, 11)
        self.assertIsNotNone(nation)
        self.assertIsNotNone(second_cp)
        self.assertIsNotNone(first_region)
        core.state_value_by_id(indexed, 31)["faction"] = {"value": 2}
        second_cp.pop("positionInNation")
        first_region["missionControl"] = 2

        self.assertEqual(income.nation_mission_control_contribution(indexed, nation, 1), 2)

    def test_adviser_bonus_excludes_inactive_and_detained_councilors_before_ranking(self):
        state = {"advisingCouncilors": [{"value": 1}, {"value": 2}, {"value": 3}]}
        councilors = {
            1: {"active": True, "detained": False, "finalAttributes": {"Science": 50.0}},
            2: {"active": False, "detained": False, "finalAttributes": {"Science": 100.0}},
            3: {"active": True, "detained": True, "finalAttributes": {"Science": 90.0}},
        }

        self.assertAlmostEqual(income.nation_adviser_science_bonus(state, councilors), 0.5)

    def test_monthly_research_excludes_inactive_advisers(self):
        indexed = self._build_indexed()
        nation = core.state_value_by_id(indexed, 21)
        nation.update({"GDP": 1e12, "education": 8, "democracy": 5, "cohesion": 5, "unrest": 0})
        for region_id in (11, 12):
            core.state_value_by_id(indexed, region_id)["populationInMillions"] = 25
        nation["advisingCouncilors"] = []
        baseline = income.nation_monthly_research(indexed, nation, {})
        nation["advisingCouncilors"] = [{"value": 1}, {"value": 2}]
        councilors = {
            1: {"active": True, "finalAttributes": {"Science": 20}},
            2: {"active": False, "finalAttributes": {"Science": 100}},
        }
        self.assertGreater(baseline, 0)
        self.assertAlmostEqual(income.nation_monthly_research(indexed, nation, councilors), baseline * 1.2)

    def test_unknown_adviser_activity_and_unresolved_reference_fail_closed(self):
        state = {"advisingCouncilors": [{"value": 7}]}
        for summaries in ({}, {7: {"active": None, "finalAttributes": {"Science": 20}}}):
            with self.subTest(summaries=summaries):
                with self.assertRaises(core.CalculationDependencyError):
                    income.nation_adviser_science_bonus(state, summaries)
                with self.assertRaises(core.CalculationDependencyError):
                    income.state_adviser_attribute_bonus(state, summaries, "Science")

    def test_projection_adviser_roster_excludes_serialized_detention(self):
        rows = [
            {"Key": {"value": identity}, "Value": {
                "ID": {"value": identity}, "status": "Active", "faction": {"value": 7},
                "detainingFaction": None if identity == 1 else {"value": 8},
            }}
            for identity in (1, 2)
        ]
        indexed = core.build_index({"gamestates": {"TICouncilorState": rows}})
        faction = {"councilors": [{"value": 1}, {"value": 2}]}
        summaries = {identity: {"finalAttributes": {"Science": 20}} for identity in (1, 2)}
        all_advisers, available = ti.projection_advisor_profiles(indexed, 7, faction, summaries)
        self.assertEqual(set(all_advisers), {1})
        self.assertEqual(set(available), {1})

    def test_nation_and_hab_adviser_science_bonuses_use_the_same_active_values(self):
        state = {"advisingCouncilors": [{"value": 1}, {"value": 2}, {"value": 3}]}
        councilors = {
            1: {"active": True, "detained": False, "finalAttributes": {"Science": 30.0}},
            2: {"active": True, "detained": False, "finalAttributes": {"Science": 20.0}},
            3: {"active": False, "detained": False, "finalAttributes": {"Science": 100.0}},
        }
        expected = 0.3 + 0.1

        self.assertAlmostEqual(income.nation_adviser_science_bonus(state, councilors), expected)
        self.assertAlmostEqual(income.state_adviser_attribute_bonus(state, councilors, "Science"), expected)

    def test_extra_advisor_does_not_duplicate_an_existing_adviser_reference(self):
        state = {"advisingCouncilors": [{"value": 1}]}
        councilors = {
            1: {"active": True, "detained": False, "finalAttributes": {"Science": 40.0}},
        }
        indexed = self._build_indexed()
        nation = core.state_value_by_id(indexed, 21)
        self.assertIsNotNone(nation)
        nation["advisingCouncilors"] = state["advisingCouncilors"]

        self.assertAlmostEqual(income.nation_adviser_science_bonus(state, councilors, (1, 100.0)), 0.4)
        self.assertAlmostEqual(
            income.nation_monthly_research(indexed, nation, councilors, (1, 100.0)),
            income.nation_monthly_research(indexed, nation, councilors),
        )


if __name__ == "__main__":
    unittest.main()
