import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from ti_parser_nation_validity import (
    MIN_CONTROL_POINTS_FOR_NAVY,
    MIN_CONTROL_POINTS_FOR_NAVY_EXCEPTION,
    PCGDP_FOR_NAVY_EXCEPTION,
    can_build_navy,
    evaluate_priority_validity,
)
from ti_parser_mechanics import Rules, mechanic_rule_test


class NationPriorityValidityTests(unittest.TestCase):
    @mechanic_rule_test(Rules.NATION_PRIORITY_VALIDITY.id, evidence="expectedValue")
    def test_government_cap_requires_hostile_region(self):
        self.assertFalse(evaluate_priority_validity("Government", {"democracy": 10.0, "hasHostileRegion": False}).valid)
        self.assertTrue(evaluate_priority_validity("Government", {"democracy": 10.0, "hasHostileRegion": True}).valid)

    def test_mission_control_and_army_use_precomputed_live_capacity(self):
        self.assertTrue(evaluate_priority_validity("MissionControl", {"spaceFlightProgram": True, "missionControlHasCapacity": True}).valid)
        self.assertFalse(evaluate_priority_validity("MissionControl", {"spaceFlightProgram": True, "missionControlHasCapacity": False}).valid)
        self.assertTrue(evaluate_priority_validity("Military_BuildArmy", {"allowedArmies": 3, "currentArmies": 2}).valid)

    def test_missing_input_is_unknown_not_false(self):
        result = evaluate_priority_validity("MissionControl", {"spaceFlightProgram": True})
        self.assertIsNone(result.valid)
        self.assertEqual(result.dependencies[0]["field"], "missionControlHasCapacity")

    def test_mission_control_can_use_federation_space_program(self):
        view = {"spaceFlightProgram": False, "missionControlHasCapacity": True}
        self.assertTrue(evaluate_priority_validity("MissionControl", {**view, "federationSpaceProgram": True}).valid)
        self.assertFalse(evaluate_priority_validity("MissionControl", {**view, "federationSpaceProgram": False}).valid)
        self.assertIsNone(evaluate_priority_validity("MissionControl", view).valid)

    def test_capability_priorities(self):
        self.assertTrue(evaluate_priority_validity("Military_FoundMilitary", {"military": False}).valid)
        self.assertTrue(evaluate_priority_validity("Military_InitiateNuclearProgram", {"military": True, "nuclearProgram": False}).valid)
        self.assertTrue(evaluate_priority_validity("Military_BuildSTOSquadron", {"military": True, "canBuildSTO": True, "hasBoostRegion": True}).valid)

    @mechanic_rule_test(Rules.NATION_PRIORITY_VALIDITY.id, evidence="expectedValue")
    def test_build_navy_uses_the_full_coastal_predicate(self):
        view = {
            "military": True,
            "armyCount": 1,
            "navyCount": 0,
            "coastalRegions": 1,
            "controlPointCount": MIN_CONTROL_POINTS_FOR_NAVY,
            "perCapitaGDP": 1.0,
            "minControlPointsForNavy": MIN_CONTROL_POINTS_FOR_NAVY,
            "minControlPointsForNavyException": MIN_CONTROL_POINTS_FOR_NAVY_EXCEPTION,
            "pcgdpForNavyException": PCGDP_FOR_NAVY_EXCEPTION,
        }
        self.assertTrue(can_build_navy(view))
        self.assertTrue(evaluate_priority_validity("Military_BuildNavy", {"canBuildNavy": can_build_navy(view)}).valid)

        self.assertFalse(can_build_navy({**view, "coastalRegions": 0}))
        self.assertFalse(can_build_navy({**view, "armyCount": 0}))
        self.assertTrue(can_build_navy({
            **view,
            "controlPointCount": MIN_CONTROL_POINTS_FOR_NAVY_EXCEPTION,
            "perCapitaGDP": PCGDP_FOR_NAVY_EXCEPTION,
        }))
        self.assertFalse(can_build_navy({
            **view,
            "armyCount": 2,
            "navyCount": 1,
            "controlPointCount": MIN_CONTROL_POINTS_FOR_NAVY_EXCEPTION,
            "perCapitaGDP": PCGDP_FOR_NAVY_EXCEPTION,
        }))
        self.assertTrue(can_build_navy({**view, "armyCount": 2, "navyCount": 1}))

    def test_build_navy_missing_precomputed_input_is_unknown(self):
        result = evaluate_priority_validity("Military_BuildNavy", {})
        self.assertIsNone(result.valid)
        self.assertEqual(result.dependencies[0]["field"], "canBuildNavy")


if __name__ == "__main__":
    unittest.main()
