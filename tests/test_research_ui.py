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


def build_research_fixture(*, docked=False):
    gamestates = {}
    faction = add_state(
        gamestates,
        "TIFactionState",
        1,
        {
            "templateName": "ResistCouncil",
            "displayName": "Resistance",
            "researchWeights": [3, 3, 3, 2, 2, 2],
            "orgProjectSlotUnlocked": True,
            "habProjectSlotUnlocked": True,
            "currentProjectProgress": [
                {"projectTemplateName": "ProjectXeno", "slot": 3, "accumulatedResearch": 10.0},
                {"projectTemplateName": "ProjectMilitary", "slot": 4, "accumulatedResearch": 20.0},
                {"projectTemplateName": "ProjectSpace", "slot": 5, "accumulatedResearch": 30.0},
                {"projectTemplateName": "ProjectPausedSpace", "slot": 6, "accumulatedResearch": 40.0},
            ],
            "fleets": [ref(200)],
            "shipDesigns": [
                {
                    "dataName": "ScienceShip",
                    "moduleTemplateEntries": [{"moduleName": "MobileSpaceScienceLab", "slot": 2}],
                }
            ],
        },
    )
    add_state(
        gamestates,
        "TIGlobalResearchState",
        100,
        {
            "techProgress": [
                {"techTemplateName": "GlobalSpace", "accumulatedResearch": 0.0},
                {"techTemplateName": "GlobalLife", "accumulatedResearch": 0.0},
                {"techTemplateName": "GlobalInfo", "accumulatedResearch": 0.0},
            ]
        },
    )
    fleet = {
        "faction": ref(1),
        "ships": [ref(201)],
        "barycenter": ref(300),
    }
    if docked:
        fleet["dockedLocation"] = ref(400)
    add_state(gamestates, "TISpaceFleetState", 200, fleet)
    add_state(gamestates, "TISpaceShipState", 201, {"templateName": "ScienceShip", "fleet": ref(200)})
    add_state(gamestates, "TISpaceBodyState", 300, {"templateName": "Mars"})
    indexed = ti.build_index({"gamestates": gamestates})
    return indexed, faction


class ResearchUiTests(unittest.TestCase):
    def test_active_project_slots_exclude_paused_stored_slots(self):
        indexed, faction = build_research_fixture()

        self.assertEqual(ti.faction_project_slots(faction), [3, 4, 5])
        self.assertIn(6, ti.project_progress_by_slot(faction))
        self.assertEqual(ti.faction_total_research_weights(faction), 15.0)
        slots, bonus = ti.research_distribution(faction)
        self.assertEqual(slots, 6)
        self.assertAlmostEqual(bonus, 0.3)
        self.assertEqual(
            ti.active_slots_with_category(
                indexed,
                faction,
                {"GlobalSpace": {"techCategory": "SpaceScience"}},
                {
                    "ProjectSpace": {"techCategory": "SpaceScience"},
                    "ProjectPausedSpace": {"techCategory": "SpaceScience"},
                },
                "SpaceScience",
            ),
            2,
        )

    def test_distribution_ignores_locked_project_slot_weights(self):
        _, faction = build_research_fixture()
        faction["orgProjectSlotUnlocked"] = False
        faction["habProjectSlotUnlocked"] = False

        self.assertEqual(ti.faction_project_slots(faction), [3])
        self.assertEqual(ti.faction_total_research_weights(faction), 11.0)
        slots, bonus = ti.research_distribution(faction)
        self.assertEqual(slots, 4)
        self.assertAlmostEqual(bonus, 0.2)

    def test_space_science_fleet_modifier_counts_undocked_mobile_lab(self):
        indexed, faction = build_research_fixture(docked=False)
        utility_templates = {
            "MobileSpaceScienceLab": {
                "specialModuleRules": ["GenerateSpaceScienceBonus"],
                "specialModuleValue": 0.05,
            }
        }

        points = ti.research_points_to_slot(
            indexed,
            faction,
            0,
            100.0,
            {"GlobalSpace": {"techCategory": "SpaceScience"}},
            {"ProjectSpace": {"techCategory": "SpaceScience"}},
            {},
            {},
            {},
            utility_templates,
        )

        self.assertAlmostEqual(points["modifiers"]["category"]["components"]["fleets"], 0.05)
        self.assertAlmostEqual(points["daily"], 20.9)

    def test_space_science_fleet_modifier_ignores_docked_mobile_lab(self):
        indexed, faction = build_research_fixture(docked=True)
        utility_templates = {
            "MobileSpaceScienceLab": {
                "specialModuleRules": ["GenerateSpaceScienceBonus"],
                "specialModuleValue": 0.05,
            }
        }

        points = ti.research_points_to_slot(
            indexed,
            faction,
            0,
            100.0,
            {"GlobalSpace": {"techCategory": "SpaceScience"}},
            {"ProjectSpace": {"techCategory": "SpaceScience"}},
            {},
            {},
            {},
            utility_templates,
        )

        self.assertAlmostEqual(points["modifiers"]["category"]["components"]["fleets"], 0.0)
        self.assertAlmostEqual(points["daily"], 20.0)


if __name__ == "__main__":
    unittest.main()
