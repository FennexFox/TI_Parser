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

    def test_saved_mission_phase_schedule_rejects_non_object_repeat_change(self):
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
                    "repeatChanges": [None],
                },
            },
        }
        event = {
            "eventName": "CouncilorMissionUpdate",
            "triggerTime": {"year": 2045, "month": 1, "day": 16, "hour": 12},
            "repeatType": "Semimonthly",
            "repeatChangeTriggered": [False],
        }
        with (
            patch.object(ti_save_parser, "type_entries", return_value=[{"Value": event}]),
            patch.object(ti_save_parser, "first_value", return_value={"phaseActive": True}),
            patch.object(ti_save_parser, "scenario_template_name", return_value="ModernScenario"),
            self.assertRaises(ti_save_parser.CalculationDependencyError) as caught,
        ):
            ti_save_parser.projection_advisor_mission_schedule(object(), development)

        dependency = caught.exception.missing_dependencies[0]
        self.assertEqual(dependency["kind"], "catalog-field")
        self.assertEqual(dependency["name"], "advisorMission.missionPhaseEvent.repeatChanges")

    def test_invalid_faction_effect_expiration_is_structured(self):
        effects = [{
            "Value": {
                "factionEffectExpirations": [{
                    "Key": {"value": 7},
                    "Value": {"TemporaryKnowledge": "not-a-timestamp"},
                }],
            },
        }]
        with (
            patch.object(ti_save_parser, "type_entries", return_value=effects),
            patch.object(ti_save_parser, "scenario_template_name", return_value="ModernScenario"),
            self.assertRaises(ti_save_parser.CalculationDependencyError) as caught,
        ):
            ti_save_parser.faction_effect_expirations_for_projection(object())

        dependency = caught.exception.missing_dependencies[0]
        self.assertEqual(dependency["kind"], "save-field")
        self.assertEqual(dependency["name"], "TIEffectsState.factionEffectExpirations")

    def test_unresolved_projection_region_is_structured(self):
        indexed = ti_save_parser.build_index({"gamestates": {}})
        nation = {"GDP": 1_000_000.0, "regions": [{"value": 41}]}
        with (
            patch.object(ti_save_parser, "first_value", return_value={
                "currentDateTime": {"year": 2045, "month": 1, "day": 1, "hour": 0},
            }),
            patch.object(ti_save_parser, "nation_control_points", return_value=[]),
            patch.object(ti_save_parser, "nation_population_millions", return_value=1.0),
            patch.object(ti_save_parser, "state_value_by_id", return_value=None),
            self.assertRaises(ti_save_parser.CalculationDependencyError) as caught,
        ):
            ti_save_parser.extract_nation_projection_state(
                indexed,
                1,
                nation,
                {},
                {},
                {},
            )

        dependency = caught.exception.missing_dependencies[0]
        self.assertEqual(dependency["kind"], "save-reference")
        self.assertEqual(dependency["name"], "nation.regions")


if __name__ == "__main__":
    unittest.main()
