import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import ti_parser_ai as ai
import ti_parser_core as core


def ref(state_id):
    return {"value": state_id}


def add_state(gamestates, type_name, state_id, value):
    value = dict(value)
    value.setdefault("ID", ref(state_id))
    gamestates.setdefault(type_name, []).append({"Key": ref(state_id), "Value": value})
    return value


def synthetic_index(*, assigned_fleet=ref(20), assigned_date=None, queue=None):
    gamestates = {}
    add_state(
        gamestates,
        "TITimeState",
        1,
        {"currentDateTime": {"year": 2035, "month": 1, "day": 11}},
    )
    faction = add_state(
        gamestates,
        "TIFactionState",
        10,
        {
            "templateName": "AlienCouncil",
            "displayName": "Aliens",
            "player": ref(11),
            "fleets": [ref(20)],
            "habSectors": [ref(30)],
            "resources": {"Water": 5.0},
            "missionControlUsage": 4,
            "nShipyardQueues": [{"Key": ref(32), "Value": [] if queue is None else queue}],
        },
    )
    add_state(gamestates, "TIPlayerState", 11, {"faction": ref(10), "isAI": True})
    add_state(
        gamestates,
        "TISpaceFleetState",
        20,
        {
            "templateName": "FleetA",
            "displayName": "Fleet A",
            "faction": ref(10),
            "ships": [ref(21)],
            "homeport": ref(30),
        },
    )
    add_state(gamestates, "TISpaceShipState", 21, {"templateName": "ShipA", "displayName": "Ship A"})
    add_state(gamestates, "TIHabState", 30, {"templateName": "HabA", "displayName": "Hab A", "faction": ref(10)})
    add_state(gamestates, "TISectorState", 31, {"hab": ref(30), "faction": ref(10)})
    add_state(
        gamestates,
        "TIHabModuleState",
        32,
        {"templateName": "ShipyardA", "sector": ref(31), "constructionCompleted": True, "powered": True},
    )
    add_state(
        gamestates,
        "FactionGoal_AttackWithFleet",
        40,
        {
            "faction": ref(10),
            "assignedFleet": assigned_fleet,
            "pendingFleets": [],
            "assignedDate": assigned_date or {"year": 2035, "month": 1, "day": 1},
            "attackTarget": ref(30),
            "exists": True,
            "archived": False,
        },
    )
    # Human factions are deliberately excluded when no filter is supplied.
    add_state(gamestates, "TIFactionState", 50, {"templateName": "ResistCouncil", "player": ref(51)})
    add_state(gamestates, "TIPlayerState", 51, {"faction": ref(50), "isAI": False})
    return core.build_index({"gamestates": gamestates}), faction


class AIFleetDiagnosticsTests(unittest.TestCase):
    def test_resolves_assignment_fleet_ship_hab_and_shipyard(self):
        indexed, _ = synthetic_index()

        result = ai.calculate_ai_fleet_diagnostics(indexed, diagnostics=True)

        self.assertEqual(result["derived"]["factionCount"], 1)
        faction = result["factions"][0]
        goal = faction["goals"][0]
        self.assertEqual(goal["derived"]["assignmentState"], "assigned")
        self.assertEqual(goal["observed"]["assignedFleet"]["ships"][0]["id"], 21)
        self.assertEqual(faction["observed"]["shipyards"][0]["hab"]["id"], 30)
        self.assertEqual(result["calculationDiagnostics"]["referenceResolution"]["missing"], 0)

    def test_broken_assigned_and_pending_references_are_unknown(self):
        indexed, faction = synthetic_index(assigned_fleet=ref(999))
        faction["fleets"] = []
        goal = indexed.id_index[40][2]
        goal["pendingFleets"] = [ref(998)]

        result = ai.calculate_ai_fleet_diagnostics(indexed, faction_name="Alien")

        diagnostic = result["factions"][0]["goals"][0]
        self.assertFalse(diagnostic["observed"]["assignedFleet"]["resolved"])
        self.assertEqual(
            [finding["field"] for finding in diagnostic["unknown"] if finding["code"] == "unresolved-reference"],
            ["assignedFleet", "pendingFleets[0]"],
        )

    def test_empty_queue_does_not_infer_resource_shortage(self):
        indexed, _ = synthetic_index(queue=[])

        result = ai.calculate_ai_fleet_diagnostics(indexed)

        faction = result["factions"][0]
        self.assertIn("empty-queue-cause-unknown", [finding["code"] for finding in faction["unknown"]])
        self.assertNotIn("resource-shortage", [finding["code"] for finding in faction["suspected"]])

    def test_stale_is_only_classified_with_caller_threshold_including_boundary(self):
        indexed, _ = synthetic_index()

        without_threshold = ai.calculate_ai_fleet_diagnostics(indexed)
        at_boundary = ai.calculate_ai_fleet_diagnostics(indexed, stale_days=10)
        above_age = ai.calculate_ai_fleet_diagnostics(indexed, stale_days=11)

        self.assertEqual(without_threshold["factions"][0]["goals"][0]["derived"]["ageDays"], 10.0)
        self.assertEqual(without_threshold["factions"][0]["goals"][0]["suspected"], [])
        self.assertEqual(at_boundary["factions"][0]["goals"][0]["suspected"][0]["code"], "stale-assignment")
        self.assertEqual(above_age["factions"][0]["goals"][0]["suspected"], [])

    def test_transport_goal_connects_councilor_and_destination(self):
        indexed, _ = synthetic_index()
        add_state(
            indexed.gamestates,
            "FactionGoal_TransportCouncilorsWithFleet",
            41,
            {
                "faction": ref(10),
                "assignedFleet": None,
                "pendingFleets": [ref(20)],
                "assignedCouncilors": [ref(60)],
                "councilorDestination": ref(30),
                "assignedDate": {"year": 2035, "month": 1, "day": 10},
                "exists": True,
            },
        )
        add_state(indexed.gamestates, "TICouncilorState", 60, {"displayName": "Observer"})
        # build_index is needed because the synthetic fixture was extended after indexing.
        indexed = core.build_index(indexed.data)

        result = ai.calculate_ai_fleet_diagnostics(indexed)

        transport = next(goal for goal in result["factions"][0]["goals"] if "Transport" in goal["type"])
        self.assertEqual(transport["derived"]["assignmentState"], "pending")
        self.assertEqual(transport["observed"]["assignedCouncilors"][0]["id"], 60)
        self.assertEqual(transport["observed"]["councilorDestination"]["id"], 30)


if __name__ == "__main__":
    unittest.main()
