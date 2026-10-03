import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from ti_parser_nation_validity import evaluate_priority_validity
import ti_parser_nation_projection as projection
from test_nation_projection import context, state, unity_context, unity_state


class CurrentBuildPriorityValidityTests(unittest.TestCase):
    def test_environment_uses_sustainability_and_cached_decontaminate_inputs(self):
        evaluate = evaluate_priority_validity
        self.assertTrue(evaluate("Environment", {"sustainability": 0.0}).valid)
        self.assertTrue(evaluate("Environment", {
            "sustainability": 2.0,
            "bestCurrentSustainabilityValue": 1.0,
        }).valid)
        self.assertTrue(evaluate("Environment", {
            "sustainability": 1.0,
            "bestCurrentSustainabilityValue": 1.0,
            "canAccumulateDecontaminateTriggers": True,
        }).valid)
        self.assertFalse(evaluate("Environment", {
            "sustainability": 1.0,
            "bestCurrentSustainabilityValue": 1.0,
            "canAccumulateDecontaminateTriggers": False,
        }).valid)

        unresolved_floor = evaluate("Environment", {
            "sustainability": 1.0,
            "canAccumulateDecontaminateTriggers": False,
        })
        self.assertIsNone(unresolved_floor.valid)
        self.assertEqual(unresolved_floor.dependencies[0]["field"], "bestCurrentSustainabilityValue")

        unresolved_cache = evaluate("Environment", {
            "sustainability": 1.0,
            "bestCurrentSustainabilityValue": 1.0,
        })
        self.assertIsNone(unresolved_cache.valid)
        self.assertEqual(unresolved_cache.dependencies[0]["field"], "canAccumulateDecontaminateTriggers")

    def test_government_uses_the_cached_legitimize_gate(self):
        evaluate = evaluate_priority_validity
        self.assertTrue(evaluate("Government", {"democracy": 9.0}).valid)
        self.assertFalse(evaluate("Government", {
            "democracy": 10.0,
            "canAccumulateLegitimizeClaimTriggers": False,
        }).valid)
        self.assertTrue(evaluate("Government", {
            "democracy": 10.0,
            "canAccumulateLegitimizeClaimTriggers": True,
        }).valid)
        unresolved = evaluate("Government", {"democracy": 10.0})
        self.assertIsNone(unresolved.valid)
        self.assertEqual(unresolved.dependencies[0]["field"], "canAccumulateLegitimizeClaimTriggers")

    def test_oppression_military_and_launch_facilities_use_current_gates(self):
        evaluate = evaluate_priority_validity
        self.assertFalse(evaluate("Oppression", {"military": False}).valid)
        self.assertTrue(evaluate("Oppression", {"military": True}).valid)
        self.assertIsNone(evaluate("Oppression", {}).valid)

        self.assertFalse(evaluate("Military", {"military": False}).valid)
        self.assertTrue(evaluate("Military", {
            "military": True,
            "militaryTechLevel": 4.0,
            "maxMilitaryTechLevel": 5.0,
        }).valid)
        self.assertFalse(evaluate("Military", {
            "military": True,
            "militaryTechLevel": 5.0,
            "maxMilitaryTechLevel": 5.0,
        }).valid)
        self.assertIsNone(evaluate("Military", {"military": True, "militaryTechLevel": 4.0}).valid)

        self.assertTrue(evaluate("LaunchFacilities", {"spaceFlightProgram": True}).valid)
        self.assertTrue(evaluate("LaunchFacilities", {
            "spaceFlightProgram": False,
            "federationSpaceProgram": True,
        }).valid)
        self.assertFalse(evaluate("LaunchFacilities", {
            "spaceFlightProgram": False,
            "federationSpaceProgram": False,
        }).valid)
        self.assertIsNone(evaluate("LaunchFacilities", {"spaceFlightProgram": False}).valid)

    def test_military_subpriorities_apply_policy_and_capacity_gates(self):
        evaluate = evaluate_priority_validity
        self.assertFalse(evaluate("Military_BuildArmy", {"military": False}).valid)
        self.assertFalse(evaluate("Military_InitiateNuclearProgram", {"military": False}).valid)
        self.assertFalse(evaluate("Military_InitiateNuclearProgram", {
            "military": True,
            "nuclearProgram": False,
            "policy_noNukes": True,
        }).valid)
        self.assertTrue(evaluate("Military_InitiateNuclearProgram", {
            "military": True,
            "nuclearProgram": False,
            "policy_noNukes": False,
        }).valid)
        self.assertIsNone(evaluate("Military_InitiateNuclearProgram", {
            "military": True,
            "nuclearProgram": False,
        }).valid)

        self.assertFalse(evaluate("Military_BuildNuclearWeapons", {
            "nuclearProgram": True,
            "policy_noNukes": True,
        }).valid)
        self.assertTrue(evaluate("Military_BuildNuclearWeapons", {
            "nuclearProgram": True,
            "policy_noNukes": False,
        }).valid)
        self.assertFalse(evaluate("Military_BuildSpaceDefenses", {"military": False}).valid)
        self.assertFalse(evaluate("Military_BuildSpaceDefenses", {
            "military": True,
            "canBuildSpaceDefenses": False,
        }).valid)
        self.assertFalse(evaluate("Military_BuildSpaceDefenses", {
            "military": True,
            "canBuildSpaceDefenses": True,
            "completeAntiSpaceDefenses": True,
        }).valid)
        self.assertTrue(evaluate("Military_BuildSpaceDefenses", {
            "military": True,
            "canBuildSpaceDefenses": True,
            "completeAntiSpaceDefenses": False,
        }).valid)
        self.assertIsNone(evaluate("Military_BuildSpaceDefenses", {
            "military": True,
            "canBuildSpaceDefenses": True,
        }).valid)

        self.assertFalse(evaluate("Military_BuildSTOSquadron", {"military": False}).valid)
        self.assertFalse(evaluate("Military_BuildSTOSquadron", {
            "military": True,
            "canBuildSTO": True,
            "rawBoostPerYear_dekatons": 0.0,
        }).valid)
        self.assertFalse(evaluate("Military_BuildSTOSquadron", {
            "military": True,
            "canBuildSTO": True,
            "rawBoostPerYear_dekatons": 1.0,
            "hasSTOFighterCapacity": False,
        }).valid)
        self.assertTrue(evaluate("Military_BuildSTOSquadron", {
            "military": True,
            "canBuildSTO": True,
            "rawBoostPerYear_dekatons": 1.0,
            "hasSTOFighterCapacity": True,
        }).valid)
        self.assertIsNone(evaluate("Military_BuildSTOSquadron", {
            "military": True,
            "canBuildSTO": True,
            "rawBoostPerYear_dekatons": 1.0,
        }).valid)

    def test_mission_control_short_circuits_when_spaceflight_or_capacity_is_absent(self):
        evaluate = evaluate_priority_validity
        self.assertFalse(evaluate("MissionControl", {
            "spaceFlightProgram": False,
            "federationSpaceProgram": False,
        }).valid)
        self.assertFalse(evaluate("MissionControl", {
            "spaceFlightProgram": True,
            "missionControlHasCapacity": False,
        }).valid)
        self.assertTrue(evaluate("MissionControl", {
            "spaceFlightProgram": False,
            "federationSpaceProgram": True,
            "missionControlHasCapacity": True,
        }).valid)
        self.assertIsNone(evaluate("MissionControl", {
            "spaceFlightProgram": True,
        }).valid)

    @staticmethod
    def _completion_snapshot(value):
        return (
            value.democracy,
            value.education,
            value.cohesion,
            value.legitimize_counter,
            dict(value.public_opinion),
            set(value.hostile_region_ids),
            value.cached_can_accumulate_legitimize,
        )

    def test_missing_cached_gate_stops_government_and_unity_before_mutation(self):
        government = state()
        government.cached_can_accumulate_legitimize = None
        before = self._completion_snapshot(government)
        used = set()
        with self.assertRaises(projection.ProjectionRuntimeStop) as error:
            projection._apply_completion(government, "Government", context(), used)
        self.assertEqual(error.exception.dependencies[0]["field"], "canAccumulateLegitimizeClaimTriggers")
        self.assertEqual(self._completion_snapshot(government), before)
        self.assertEqual(used, set())

        unity = unity_state()
        unity.cached_can_accumulate_legitimize = None
        before = self._completion_snapshot(unity)
        used = set()
        with self.assertRaises(projection.ProjectionRuntimeStop) as error:
            projection._apply_completion(
                unity,
                "Unity",
                unity_context(),
                used,
                unity_public_opinion_policy="meanPath",
            )
        self.assertEqual(error.exception.dependencies[0]["field"], "canAccumulateLegitimizeClaimTriggers")
        self.assertEqual(self._completion_snapshot(unity), before)
        self.assertEqual(used, set())

    def test_cached_false_skips_hostile_id_fallback_and_true_requires_target_completeness(self):
        known_empty = state()
        known_empty.cached_can_accumulate_legitimize = False
        known_empty.hostile_region_ids = {1}
        known_empty.hostile_region_ids_complete = False
        projection._apply_completion(known_empty, "Government", context(), set())
        self.assertEqual(known_empty.legitimize_counter, 0.0)
        self.assertEqual(known_empty.hostile_region_ids, {1})
        self.assertFalse(known_empty.cached_can_accumulate_legitimize)

        unresolved_target = state()
        unresolved_target.cached_can_accumulate_legitimize = True
        unresolved_target.hostile_region_ids = {1}
        unresolved_target.hostile_region_ids_complete = False
        before = self._completion_snapshot(unresolved_target)
        used = set()
        with self.assertRaises(projection.ProjectionRuntimeStop) as error:
            projection._apply_completion(unresolved_target, "Government", context(), used)
        self.assertEqual(error.exception.dependencies[0]["field"], "hostileClaims/regions")
        self.assertEqual(self._completion_snapshot(unresolved_target), before)
        self.assertEqual(used, set())

    def test_daily_cache_and_remove_setter_update_legitimize_cache_only_with_complete_ids(self):
        incomplete = state()
        incomplete.hostile_region_ids = {1}
        incomplete.hostile_region_ids_complete = False
        incomplete.cached_can_accumulate_legitimize = True
        projection._refresh_region_cache(incomplete, context())
        self.assertIsNone(incomplete.cached_can_accumulate_legitimize)

        government = state()
        government.democracy = 10.0
        government.cached_can_accumulate_legitimize = True
        government.hostile_region_ids = {1}
        government.hostile_region_ids_complete = True
        event = projection._apply_completion(government, "Government", context(), set())
        self.assertEqual(event["removedHostileClaimRegionId"], 1)
        self.assertEqual(government.hostile_region_ids, set())
        self.assertFalse(government.cached_can_accumulate_legitimize)

        unity = unity_state()
        unity.cached_can_accumulate_legitimize = True
        unity.hostile_region_ids = {1}
        unity.hostile_region_ids_complete = True
        event = projection._apply_completion(
            unity,
            "Unity",
            unity_context(),
            set(),
            unity_public_opinion_policy="meanPath",
        )
        self.assertEqual(event["removedHostileClaimRegionId"], 1)
        self.assertEqual(unity.hostile_region_ids, set())
        self.assertFalse(unity.cached_can_accumulate_legitimize)


if __name__ == "__main__":
    unittest.main()


def test_projection_rejects_hostile_claim_resolving_to_control_point():
    import pytest
    import ti_save_parser as parser
    from tests.fixtures.fairplay_projection import make_save_data

    data = make_save_data()
    data["gamestates"]["TINationState"][0]["Value"]["hostileClaims"] = [{"value": 31}]
    with pytest.raises(parser.CalculationDependencyError) as caught:
        parser.calculate_nation_projection(
            parser.build_index(data), "USA", None,
            {"plans": [{"name": "p", "segments": [{}]}]}, days=1,
            checkpoints=[], details=False, diagnostics=False,
        )
    assert any(item["name"] == "nation.hostileClaims" for item in caught.value.missing_dependencies)
