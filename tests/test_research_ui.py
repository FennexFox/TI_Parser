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


def add_human_player(gamestates, faction, faction_id=1, player_id=2):
    faction["player"] = ref(player_id)
    add_state(
        gamestates,
        "TIPlayerState",
        player_id,
        {"templateName": "TestPlayer", "isAI": False, "faction": ref(faction_id)},
    )
    add_state(gamestates, "TIMetadataState", player_id + 1000, {"playerFactionName": faction["displayName"]})


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
    add_human_player(gamestates, faction)
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


def build_mission_control_fixture():
    gamestates = {}
    faction = add_state(
        gamestates,
        "TIFactionState",
        1,
        {
            "templateName": "ResistCouncil",
            "displayName": "Resistance",
            "baseIncomes_year": {"MissionControl": 2.0},
            "missionControlUsage": 5.0,
            "habSectors": [ref(11)],
        },
    )
    add_human_player(gamestates, faction)
    add_state(
        gamestates,
        "TIHabState",
        10,
        {
            "displayName": "Mission Control Test Hab",
            "faction": ref(1),
            "sectors": [ref(11)],
            "anyCoreCompleted": True,
        },
    )
    add_state(
        gamestates,
        "TISectorState",
        11,
        {
            "faction": ref(1),
            "hab": ref(10),
            "habModules": [ref(20), ref(21), ref(22), ref(23), ref(24)],
        },
    )
    add_state(
        gamestates,
        "TIHabModuleState",
        20,
        {
            "templateName": "CommandCenter",
            "priorModuleTemplateName": "OperationsCenter",
            "priorModuleCompleted": True,
            "constructionCompleted": False,
            "powered": False,
        },
    )
    add_state(
        gamestates,
        "TIHabModuleState",
        21,
        {
            "templateName": "OperationsCenter",
            "constructionCompleted": False,
            "powered": False,
        },
    )
    add_state(
        gamestates,
        "TIHabModuleState",
        22,
        {
            "templateName": "ResearchCampus",
            "constructionCompleted": False,
            "powered": False,
        },
    )
    add_state(
        gamestates,
        "TIHabModuleState",
        23,
        {
            "templateName": "OperationsCenter",
            "constructionCompleted": False,
            "powered": False,
            "destroyed": True,
        },
    )
    add_state(
        gamestates,
        "TIHabModuleState",
        24,
        {
            "templateName": "OperationsCenter",
            "constructionCompleted": True,
            "powered": True,
        },
    )
    templates = {
        "OperationsCenter": {"dataName": "OperationsCenter", "missionControl": 4},
        "CommandCenter": {"dataName": "CommandCenter", "missionControl": 10},
        "ResearchCampus": {"dataName": "ResearchCampus", "missionControl": -1},
    }
    return ti.build_index({"gamestates": gamestates}), faction, templates


class ResearchUiTests(unittest.TestCase):
    def test_topbar_counts_upgrading_operations_center_and_projects_queue(self):
        indexed, _, hab_templates = build_mission_control_fixture()
        templates = ti.ResearchTemplates({}, {}, {}, hab_templates, {}, {}, {})

        with (
            patch.object(ti, "TOPBAR_RESOURCES", ("MissionControl",)),
            patch.object(ti, "faction_control_point_maintenance", return_value={}),
        ):
            result = ti.calculate_topbar(indexed, None, include_details=True, research_templates=templates)

        mission_control = result["resources"]["MissionControl"]
        self.assertEqual(mission_control["capacity"], 10.0)
        self.assertEqual(mission_control["usage"], 5.0)
        self.assertEqual(mission_control["available"], 5.0)
        self.assertEqual(mission_control["components"]["habs"], 8.0)
        self.assertEqual(
            mission_control["projectedAfterCurrentQueue"],
            {
                "capacity": 20.0,
                "usage": 6.0,
                "available": 14.0,
                "capacityChange": 10.0,
                "habCapacityChange": 10.0,
                "effectsChange": 0.0,
                "usageChange": 1,
                "headroomChange": 9.0,
                "moduleChanges": [
                    {
                        "template": "CommandCenter",
                        "priorTemplate": "OperationsCenter",
                        "count": 1,
                        "capacityChange": 6,
                        "usageChange": 0,
                        "headroomChange": 6,
                    },
                    {
                        "template": "OperationsCenter",
                        "priorTemplate": None,
                        "count": 1,
                        "capacityChange": 4,
                        "usageChange": 0,
                        "headroomChange": 4,
                    },
                    {
                        "template": "ResearchCampus",
                        "priorTemplate": None,
                        "count": 1,
                        "capacityChange": 0,
                        "usageChange": 1,
                        "headroomChange": -1,
                    },
                ],
            },
        )

    def test_queue_projection_applies_mission_control_disruption(self):
        indexed, _, hab_templates = build_mission_control_fixture()
        templates = ti.ResearchTemplates(
            {},
            {"DisruptMC": {"operation": "Multiplicative", "value": 0.5}},
            {},
            hab_templates,
            {},
            {},
            {},
        )

        with (
            patch.object(ti, "TOPBAR_RESOURCES", ("MissionControl",)),
            patch.object(
                ti,
                "faction_effect_contexts",
                return_value={"MissionControlDisruption_PCT": ["DisruptMC"]},
            ),
            patch.object(ti, "faction_control_point_maintenance", return_value={}),
        ):
            result = ti.calculate_topbar(indexed, None, include_details=True, research_templates=templates)

        mission_control = result["resources"]["MissionControl"]
        projected = mission_control["projectedAfterCurrentQueue"]
        self.assertEqual(mission_control["capacity"], 5.0)
        self.assertEqual(projected["capacity"], 10.0)
        self.assertEqual(projected["capacityChange"], 5.0)
        self.assertEqual(projected["habCapacityChange"], 10.0)
        self.assertEqual(projected["effectsChange"], -5.0)
        self.assertEqual(projected["usage"], 6.0)
        self.assertEqual(projected["available"], 4.0)
        self.assertEqual(projected["headroomChange"], 4.0)

    def test_queue_projection_reapplies_fixed_mission_control_effect(self):
        indexed, _, hab_templates = build_mission_control_fixture()
        templates = ti.ResearchTemplates(
            {},
            {"FixedMC": {"operation": "SetToFixedValue", "value": 7.0}},
            {},
            hab_templates,
            {},
            {},
            {},
        )

        with (
            patch.object(ti, "TOPBAR_RESOURCES", ("MissionControl",)),
            patch.object(
                ti,
                "faction_effect_contexts",
                return_value={"MissionControlDisruption_PCT": ["FixedMC"]},
            ),
            patch.object(ti, "faction_control_point_maintenance", return_value={}),
        ):
            result = ti.calculate_topbar(indexed, None, include_details=True, research_templates=templates)

        mission_control = result["resources"]["MissionControl"]
        projected = mission_control["projectedAfterCurrentQueue"]
        self.assertEqual(mission_control["capacity"], 7.0)
        self.assertEqual(projected["capacity"], 7.0)
        self.assertEqual(projected["capacityChange"], 0.0)
        self.assertEqual(projected["habCapacityChange"], 10.0)
        self.assertEqual(projected["effectsChange"], -10.0)
        self.assertEqual(projected["available"], 1.0)
        self.assertEqual(projected["headroomChange"], -1.0)

    def test_research_breakdown_applies_mc_effect_to_upgrading_operations_center(self):
        indexed, _, hab_templates = build_mission_control_fixture()
        templates = ti.ResearchTemplates(
            {},
            {"DisruptMC": {"operation": "Multiplicative", "value": 0.5}},
            {},
            hab_templates,
            {},
            {},
            {},
        )

        with patch.object(
            ti,
            "faction_effect_contexts",
            return_value={"MissionControlDisruption_PCT": ["DisruptMC"]},
        ):
            result = ti.calculate_research_breakdown(
                indexed,
                None,
                include_details=True,
                templates=templates,
            )

        mission_control = result["missionControl"]
        self.assertEqual(mission_control["max"], 5.0)
        self.assertEqual(mission_control["available"], 0.0)
        self.assertEqual(mission_control["excessUsedForResearch"], 0.0)
        self.assertEqual(mission_control["components"]["habs"], 8)
        self.assertEqual(mission_control["components"]["effects"], -5.0)

    def test_foreign_sector_module_does_not_contribute_mission_control(self):
        record = {
            "templateName": "OperationsCenter",
            "template": {"missionControl": 4},
            "completed": True,
            "powered": True,
            "destroyed": False,
            "decommissioning": False,
            "sectorOwnedByHabFaction": False,
        }

        self.assertEqual(ti.hab_module_current_mission_control(record), 0)
        self.assertEqual(ti.hab_module_projected_mission_control(record), 0)

    def test_research_breakdown_mc_keeps_prior_operations_center_visible(self):
        indexed, faction, hab_templates = build_mission_control_fixture()

        research_month, mission_control, details = ti.hab_research_and_mc(
            indexed,
            faction,
            hab_templates,
            {},
        )

        self.assertEqual(research_month, 0.0)
        self.assertEqual(mission_control, 8)
        self.assertEqual(len(details), 1)
        self.assertEqual(details[0]["missionControl"], 8)

    def test_planning_prefers_current_queue_mission_control_projection(self):
        self.assertEqual(
            ti.mission_control_available_for_planning(
                {
                    "resources": {
                        "MissionControl": {
                            "available": 5,
                            "projectedAfterCurrentQueue": {"available": 14},
                        }
                    }
                }
            ),
            14.0,
        )
        self.assertEqual(
            ti.mission_control_available_for_planning(
                {"resources": {"MissionControl": {"available": 5}}}
            ),
            5.0,
        )

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
            patch.object(ti, "faction_is_player", return_value=True),
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
