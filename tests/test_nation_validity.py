import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from ti_parser_nation_validity import evaluate_priority_validity
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

    def test_capability_priorities(self):
        self.assertTrue(evaluate_priority_validity("Military_FoundMilitary", {"military": False}).valid)
        self.assertTrue(evaluate_priority_validity("Military_InitiateNuclearProgram", {"military": True, "nuclearProgram": False}).valid)
        self.assertTrue(evaluate_priority_validity("Military_BuildSTOSquadron", {"military": True, "canBuildSTO": True, "hasBoostRegion": True}).valid)


if __name__ == "__main__":
    unittest.main()
