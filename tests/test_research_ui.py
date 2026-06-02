import sys
import unittest
from pathlib import Path
from unittest.mock import patch


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
    def test_topbar_records_before_distribution_research_in_shared_cache(self):
        indexed = ti.build_index({"gamestates": {}})
        faction = {"ID": ref(7), "templateName": "ResistCouncil", "resources": {"Research": 4.0}}
        templates = ti.ResearchTemplates({}, {}, {}, {}, {}, {}, {})
        cache = {}
        research = {
            "daily": {"total": 15.0, "beforeDistribution": 12.5, "distributionBonus": 2.5, "bySource": {}},
            "monthly": {"total": 456.0},
            "annual": {"total": 5475.0},
        }

        with (
            patch.object(ti, "TOPBAR_RESOURCES", ("Research",)),
            patch.object(ti, "find_faction_state", return_value=(7, faction)),
            patch.object(ti, "faction_effect_contexts", return_value={}),
            patch.object(ti, "councilor_summary_maps", return_value=([], {})),
            patch.object(ti, "faction_max_mission_control_components", return_value={"total": 0.0}),
            patch.object(ti, "faction_control_point_maintenance", return_value={}),
            patch.object(ti, "calculate_research_breakdown", return_value=research),
        ):
            result = ti.calculate_topbar(indexed, None, research_templates=templates, base_daily_cache=cache)

        self.assertEqual(cache, {7: 12.5})
        self.assertEqual(result["resources"]["Research"]["daily"], 15.0)

    def test_base_daily_cache_reuses_breakdown_for_same_faction(self):
        indexed, faction = build_research_fixture()
        cache = {}

        with patch.object(ti, "calculate_research_breakdown", return_value={"daily": {"beforeDistribution": 12.5}}) as breakdown:
            first = ti.faction_base_research_daily(indexed, None, faction, cache=cache)
            second = ti.faction_base_research_daily(indexed, None, faction, cache=cache)

        self.assertEqual(first, 12.5)
        self.assertEqual(second, 12.5)
        breakdown.assert_called_once()

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
