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


if __name__ == "__main__":
    unittest.main()
