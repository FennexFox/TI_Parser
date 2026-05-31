import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import ti_save_parser as ti


def ref(state_id):
    return {"value": state_id}


def add_state(gamestates, type_name, state_id, value):
    value = dict(value)
    value.setdefault("ID", ref(state_id))
    gamestates.setdefault(type_name, []).append({"Key": ref(state_id), "Value": value})
    return value


class ProjectAnalysisTests(unittest.TestCase):
    def test_candidate_names_include_available_and_stored_but_skip_active_by_default(self):
        faction = {
            "availableProjectNames": ["Project_Available"],
            "researchWeights": [1, 1, 1, 1, 1, 1],
            "orgProjectSlotUnlocked": True,
            "habProjectSlotUnlocked": True,
            "currentProjectProgress": [
                {"projectTemplateName": "Project_Active", "slot": 3, "accumulatedResearch": 10},
                {"projectTemplateName": "Project_Stored", "slot": 6, "accumulatedResearch": 20},
            ],
        }
        templates = {
            name: {"dataName": name, "friendlyName": name}
            for name in ("Project_Available", "Project_Active", "Project_Stored")
        }

        self.assertEqual(
            ti.project_analysis_candidate_names(faction, templates),
            ["Project_Available", "Project_Stored"],
        )
        self.assertEqual(
            ti.project_analysis_candidate_names(faction, templates, include_active=True),
            ["Project_Active", "Project_Available", "Project_Stored"],
        )

    def test_hypothetical_project_slot_counts_candidate_category(self):
        gamestates = {}
        faction = add_state(
            gamestates,
            "TIFactionState",
            1,
            {
                "templateName": "ResistCouncil",
                "displayName": "Resistance",
                "researchWeights": [0, 0, 0, 1, 1, 0],
                "orgProjectSlotUnlocked": True,
                "habProjectSlotUnlocked": False,
                "currentProjectProgress": [
                    {"projectTemplateName": "Project_CurrentSpace", "slot": 3, "accumulatedResearch": 0},
                ],
            },
        )
        indexed = ti.build_index({"gamestates": gamestates})

        points = ti.hypothetical_project_points_to_slot(
            indexed,
            faction,
            {"dataName": "Project_CandidateSpace", "techCategory": "SpaceScience"},
            4,
            100.0,
            {},
            {"Project_CurrentSpace": {"techCategory": "SpaceScience"}},
            {},
            {},
            {},
            {},
        )

        self.assertAlmostEqual(points["daily"], 50.0)
        self.assertEqual(points["modifiers"]["category"]["activeSlotsWithCategory"], 2)
        self.assertEqual(points["modifiers"]["category"]["extraSlotPenaltyPower"], 1)

    def test_bottleneck_penalty_charges_critical_resource_worsening(self):
        penalty = ti.bottleneck_penalty_from_delta(
            {"Water": {"net": -3.0}, "Metals": {"net": -5.0}},
            [{"resource": "Water", "severity": "critical"}],
            {"Water": 5.0, "Metals": 1.0},
        )

        self.assertEqual(penalty, 15.0)

    def test_candidate_farm_delta_credits_existing_uncovered_crew(self):
        indexed = ti.build_index({"gamestates": {}})
        hab = {"anyCoreCompleted": True}
        records = [
            {
                "templateName": "Core",
                "completed": True,
                "powered": True,
                "template": {"dataName": "Core", "coreModule": True, "crew": 1000},
            }
        ]
        template = {
            "dataName": "AgricultureComplex",
            "crew": 25,
            "specialRules": ["Farm"],
            "specialRulesValue": 3000,
        }

        delta = ti.candidate_module_monthly_delta(indexed, hab, records, {}, template, {}, {}, 1.0, {})
        expected_saved_support = (
            1000
            * ti.DEFAULT_GLOBAL_CONFIG["crewWaterConsumptionTons_year"]
            * ti.DEFAULT_GLOBAL_CONFIG["spaceResourceToTons"]
            / 12.0
        )

        self.assertAlmostEqual(delta["Water"]["support"], -expected_saved_support)
        self.assertAlmostEqual(delta["Water"]["net"], expected_saved_support)
        self.assertAlmostEqual(delta["Volatiles"]["support"], -expected_saved_support)
        self.assertAlmostEqual(delta["Volatiles"]["net"], expected_saved_support)


if __name__ == "__main__":
    unittest.main()
