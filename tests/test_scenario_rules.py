import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import ti_parser_core as core
import ti_save_parser as ti


class ScenarioRuleTests(unittest.TestCase):
    def _build_indexed(
        self,
        scenario: str | None,
        *,
        using_customizations: bool = False,
        national_ip_multiplier: float = 1.0,
    ) -> core.IndexedState:
        return core.build_index(
            {
                "gamestates": {
                    "TITimeState": [
                        {
                            "Key": {"value": 1},
                            "Value": {
                                "ID": {"value": 1},
                                "scenarioMetaTemplateName": scenario,
                            },
                        }
                    ],
                    "TIGlobalValuesState": [
                        {
                            "Key": {"value": 2},
                            "Value": {
                                "ID": {"value": 2},
                                "controlPointMaintenanceFreebies": 0,
                                "scenarioCustomizations": {
                                    "usingCustomizations": using_customizations,
                                    "nationalIPMultiplier": national_ip_multiplier,
                                },
                            },
                        }
                    ],
                    "TIFactionState": [
                        {
                            "Key": {"value": 10},
                            "Value": {
                                "ID": {"value": 10},
                                "templateName": "ResistCouncil",
                                "controlPoints": [{"value": 31}],
                                "councilors": [],
                                "habSectors": [],
                                "history_CPCapOverageByDay": [0.0],
                            },
                        }
                    ],
                    "TINationState": [
                        {
                            "Key": {"value": 21},
                            "Value": {
                                "ID": {"value": 21},
                                "templateName": "1962_WES" if scenario == "BrokenEarthScenario" else "USA",
                                "GDP": 100_000_000_000.0,
                                "numControlPoints": 2,
                                "controlPoints": [{"value": 31}],
                                "regions": [{"value": 41}],
                                "publicOpinion": {"Resist": 0.6},
                                "_accumulatedInvestmentPoints": {"Military_BuildArmy": 5.0},
                            },
                        }
                    ],
                    "TIControlPointState": [
                        {
                            "Key": {"value": 31},
                            "Value": {
                                "ID": {"value": 31},
                                "nation": {"value": 21},
                                "faction": {"value": 10},
                                "benefitsDisabled": False,
                                "totalWeightsForControlPoint": 3,
                                "controlPointPriorities": {"Military_BuildArmy": 3},
                            },
                        }
                    ],
                    "TIRegionState": [
                        {
                            "Key": {"value": 41},
                            "Value": {"ID": {"value": 41}, "populationInMillions": 100.0},
                        }
                    ],
                }
            }
        )

    @staticmethod
    def _army_cost(indexed: core.IndexedState) -> float:
        nation = core.state_value_by_id(indexed, 21)
        assert nation is not None
        rows = ti.nation_priority_rows(indexed, nation)
        return next(row["cost"] for row in rows if row["key"] == "BuildArmy")

    def test_army_cost_uses_canonical_scenario_rules(self):
        self.assertEqual(self._army_cost(self._build_indexed(None)), 60)
        self.assertEqual(self._army_cost(self._build_indexed("2003Scenario")), 60)
        self.assertEqual(self._army_cost(self._build_indexed("BrokenEarthScenario")), 40)

    def test_active_national_ip_multiplier_scales_priority_costs(self):
        indexed = self._build_indexed(
            "BrokenEarthScenario",
            using_customizations=True,
            national_ip_multiplier=2.0,
        )
        self.assertEqual(self._army_cost(indexed), 20)

    def test_inactive_or_invalid_national_ip_multiplier_is_ignored(self):
        inactive = self._build_indexed(
            "BrokenEarthScenario",
            using_customizations=False,
            national_ip_multiplier=2.0,
        )
        invalid = self._build_indexed(
            "BrokenEarthScenario",
            using_customizations=True,
            national_ip_multiplier=0.0,
        )
        self.assertEqual(self._army_cost(inactive), 40)
        self.assertEqual(self._army_cost(invalid), 40)

    def test_broken_earth_control_point_usage_is_seventy_percent_of_standard(self):
        standard = self._build_indexed("2003Scenario")
        broken_earth = self._build_indexed("BrokenEarthScenario")
        standard_faction = core.state_value_by_id(standard, 10)
        broken_earth_faction = core.state_value_by_id(broken_earth, 10)
        assert standard_faction is not None and broken_earth_faction is not None

        standard_result = ti.faction_control_point_maintenance(
            standard, None, 10, standard_faction, {}, {}, {}
        )
        broken_earth_result = ti.faction_control_point_maintenance(
            broken_earth, None, 10, broken_earth_faction, {}, {}, {}
        )

        self.assertAlmostEqual(broken_earth_result["usage"], standard_result["usage"] * 0.7)
        self.assertEqual(broken_earth_result["components"]["scenarioMultiplier"], 0.7)

    def test_public_opinion_influence_effect_scales_nation_income(self):
        indexed = self._build_indexed("2003Scenario")
        nation = core.state_value_by_id(indexed, 21)
        faction = core.state_value_by_id(indexed, 10)
        assert nation is not None and faction is not None
        effects = {
            "Effect_BS_InfluencePenalty": {
                "operation": "Additive",
                "value": -0.25,
            }
        }

        base = ti.nation_influence_contribution_month(indexed, nation, faction)
        modified = ti.nation_influence_contribution_month(
            indexed,
            nation,
            faction,
            {"PublicOpinionInfluence": ["Effect_BS_InfluencePenalty"]},
            effects,
        )

        self.assertAlmostEqual(base, 2.5)
        self.assertAlmostEqual(modified, 1.875)


if __name__ == "__main__":
    unittest.main()
