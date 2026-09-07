import sys
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import ti_parser_cli
import ti_save_parser


class NationProjectionCliTests(unittest.TestCase):
    def test_cli_parser_accepts_projection_contract(self):
        args = ti_parser_cli.build_parser(ti_save_parser).parse_args([
            "nation-projection", "KOR", "--days", "365", "--plan-file", "plans.json",
            "--checkpoints", "30,90", "--faction", "ResistCouncil", "--details", "--diagnostics",
        ])
        self.assertEqual(args.command, "nation-projection")
        self.assertEqual(args.days, 365)
        self.assertEqual(args.checkpoints, "30,90")
        self.assertTrue(args.details)
        self.assertTrue(args.diagnostics)

    def test_cli_dispatch_maps_projection_to_raw_save_command(self):
        self.assertEqual(ti_parser_cli.RAW_COMMANDS["nation-projection"], "command_nation_projection")

    def test_saved_mission_phase_schedule_is_extracted_fail_closed(self):
        development = {
            "advisorMission": {
                "automaticSuccess": True,
                "movementRule": "MoveToTarget",
                "persistentEffect": True,
                "resolutionOrder": 0,
                "resolutionSegmentsPerPhase": 5,
                "cost": {"type": "TIMissionCost_Flat", "resource": "Influence", "value": 10.0},
                "missionPhaseEvent": {
                    "templateName": "CouncilorMissionUpdate",
                    "repeatChanges": [{"campaignYearsGreaterThan": 15.0, "repeatType": "EveryThreeWeeksToMonth"}],
                },
            },
        }
        event = {
            "eventName": "CouncilorMissionUpdate",
            "triggerTime": {"year": 2045, "month": 1, "day": 16, "hour": 12},
            "repeatType": "Semimonthly",
            "timeStep": 1,
            "startMonth": 3,
            "repeatChangeTriggered": [False],
        }
        with (
            patch.object(ti_save_parser, "type_entries", return_value=[{"Value": event}]),
            patch.object(ti_save_parser, "first_value", return_value={"phaseActive": True}),
        ):
            schedule = ti_save_parser.projection_advisor_mission_schedule(object(), development)

        self.assertEqual(schedule.next_phase_at, datetime(2045, 1, 16, 12))
        self.assertTrue(schedule.phase_active)
        self.assertEqual(schedule.repeat_changes, ((15.0, "EveryThreeWeeksToMonth", False),))


if __name__ == "__main__":
    unittest.main()
