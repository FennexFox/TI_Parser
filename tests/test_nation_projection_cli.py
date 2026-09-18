import sys
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import ti_parser_cli
import ti_parser_projection_adapter as projection_adapter
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
            patch.object(projection_adapter, "type_entries", return_value=[{"Value": event}]),
            patch.object(projection_adapter, "first_value", return_value={"phaseActive": True}),
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
            patch.object(projection_adapter, "type_entries", return_value=[{"Value": event}]),
            patch.object(projection_adapter, "first_value", return_value={"phaseActive": True}),
            patch.object(projection_adapter, "scenario_template_name", return_value="ModernScenario"),
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
            patch.object(projection_adapter, "type_entries", return_value=effects),
            patch.object(projection_adapter, "scenario_template_name", return_value="ModernScenario"),
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
            patch.object(projection_adapter, "first_value", return_value={
                "currentDateTime": {"year": 2045, "month": 1, "day": 1, "hour": 0},
            }),
            patch.object(projection_adapter, "nation_control_points", return_value=[]),
            patch.object(projection_adapter, "nation_population_millions", return_value=1.0),
            patch.object(projection_adapter, "state_value_by_id", return_value=None),
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

    def test_projection_ocean_type_rejects_unknown_enum(self):
        indexed = ti_save_parser.build_index({"gamestates": {}})
        with (
            patch.object(projection_adapter, "scenario_template_name", return_value="ModernScenario"),
            self.assertRaises(ti_save_parser.CalculationDependencyError) as caught,
        ):
            ti_save_parser._required_projection_ocean_type(
                indexed, {"oceanType": "Lake"}, "oceanType",
                source="save-field", rule_id="nation.priority.validity",
            )
        dependency = caught.exception.missing_dependencies[0]
        self.assertEqual(dependency["kind"], "save-field")
        self.assertEqual(dependency["name"], "oceanType")

    def test_projection_army_type_is_required_for_build_navy(self):
        indexed = ti_save_parser.build_index({"gamestates": {}})
        with (
            patch.object(projection_adapter, "scenario_template_name", return_value="ModernScenario"),
            self.assertRaises(ti_save_parser.CalculationDependencyError) as caught,
        ):
            ti_save_parser._required_projection_army_type(
                indexed, {}, "armyType", source="save-field",
                rule_id=ti_save_parser.Rules.NATION_PRIORITY_BUILD_NAVY_COMPLETE.id,
            )

        dependency = caught.exception.missing_dependencies[0]
        self.assertEqual(dependency["kind"], "save-field")
        self.assertEqual(dependency["name"], "armyType")
        self.assertEqual(dependency["context"], ti_save_parser.Rules.NATION_PRIORITY_BUILD_NAVY_COMPLETE.id)

        with self.assertRaises(ti_save_parser.CalculationDependencyError):
            ti_save_parser._required_projection_army_type(
                indexed, {"armyType": "UnknownArmy"}, "armyType", source="save-field",
                rule_id=ti_save_parser.Rules.NATION_PRIORITY_BUILD_NAVY_COMPLETE.id,
            )

    def test_projection_deployment_type_is_required_for_build_navy(self):
        indexed = ti_save_parser.build_index({"gamestates": {}})
        with self.assertRaises(ti_save_parser.CalculationDependencyError):
            ti_save_parser._required_projection_deployment_type(
                indexed, {}, "deploymentType", source="save-field",
                rule_id=ti_save_parser.Rules.NATION_PRIORITY_BUILD_NAVY_COMPLETE.id,
            )
        self.assertEqual(
            ti_save_parser._required_projection_deployment_type(
                indexed, {"deploymentType": "Naval"}, "deploymentType", source="save-field",
                rule_id=ti_save_parser.Rules.NATION_PRIORITY_BUILD_NAVY_COMPLETE.id,
            ),
            "Naval",
        )
        with self.assertRaises(ti_save_parser.CalculationDependencyError):
            ti_save_parser._required_projection_deployment_type(
                indexed, {"deploymentType": "UnknownDeployment"}, "deploymentType", source="save-field",
                rule_id=ti_save_parser.Rules.NATION_PRIORITY_BUILD_NAVY_COMPLETE.id,
            )

    @staticmethod
    def _projection_extraction_fixture():
        region = {
            "templateName": "Region1",
            "xenoforming": {"value": 102},
            "occupations": [],
            "colonyRegion": False,
            "permanentlyDecolonized": False,
            "resourceRegion": False,
            "oilRegion": False,
            "coreEconomicRegion": False,
            "populationInMillions": 1.0,
            "boostPerYear_dekatons": 0.0,
            "missionControl": 0,
            "oceanType": "No",
            "annualPopGrowthModifier": 0.0,
            "nuclearDetonations": 0,
            "accumulatedDecolonizeTriggers": 0,
            "accumulatedCoreEconomyRegionTriggers": 0,
            "accumulatedCoreMiningRegionTriggers": 0,
            "accumulatedCoreOilRegionTriggers": 0,
            "leadOccupier": None,
            "spaceDefenseFacility": None,
            "numSTOFighters": 0,
        }
        nation = {
            "GDP": 1_000_000_000.0,
            "regions": [{"value": 101}],
            "capital": {"value": 101},
            "armies": [],
            "advisingCouncilors": [],
            "hostileClaims": [],
            "economyScore": 10.0,
            "_accumulatedInvestmentPoints": {},
            "inequality": 4.0,
            "education": 5.0,
            "democracy": 5.0,
            "cohesion": 5.0,
            "cohesionRestState_dailyCache": 5.0,
            "unrest": 0.0,
            "unrestRestState_dailyCache": 0.0,
            "sustainability": 1.0,
            "militaryTechLevel": 1.0,
            "spaceFunding_year": 0.0,
            "tracker_PCGDP_ByQuarter": [],
            "military": True,
            "spaceFlightProgram": False,
            "nuclearProgram": False,
            "canBuildSpaceDefenses": False,
            "canBuildSTOSquadrons": False,
            "numControlPoints_unclamped": 1,
        }
        control_point = {
            "ID": {"value": 201},
            "positionInNation": 0,
            "nation": {"value": 1},
            "faction": {"value": 7},
            "benefitsDisabled": False,
            "controlPointPriorities": {},
            "diversityBonus": {},
            "totalWeightsForControlPoint": 0,
            "numPrioritiesWithWeight": 0,
        }
        time_state = {
            "currentDateTime": {"year": 2045, "month": 1, "day": 1, "hour": 0},
            "daysInCampaign": 1.0,
            "currentQuarterSinceStart": 1,
        }
        global_state = {
            "earthAtmosphericCO2_ppm": 400.0,
            "earthAtmosphericCH4_ppm": 2.0,
            "earthAtmosphericN2O_ppm": 0.3,
            "stratosphericAerosols_ppm": 0.0,
            "fixedPCGDPToReduceUnrestBy1": 3_000.0,
            "resourceMarketValues": {"Metals": 10.0, "NobleMetals": 20.0},
            "endOfOil": False,
        }
        development = {
            "globalConfig": {
                "coreEcoRegionGDPModifier": {"value": 1.0},
                "coreResourceRegionGDPModifier": {"value": 1.0},
                "colonyRegionGDPModifier": {"value": 1.0},
            },
            "regionTemplates": {
                "Region1": {
                    "mapRegionName": "Map1",
                    "environment": "Standard",
                    "mineCapable": False,
                    "oilCapable": False,
                },
            },
            "mapRegionTemplates": {"Map1": {"latitude": 0.0, "longitude": 0.0}},
        }
        return object(), nation, region, control_point, time_state, global_state, development

    def test_projection_state_lists_reject_null_save_fields(self):
        cases = (
            ("advisingCouncilors", ti_save_parser.Rules.NATION_ADVISOR_MISSION_LIFECYCLE.id),
            ("hostileClaims", ti_save_parser.Rules.NATION_PRIORITY_GOVERNMENT_LEGITIMIZE.id),
        )
        for field, rule_id in cases:
            with self.subTest(field=field):
                indexed, nation, region, control_point, time_state, global_state, development = self._projection_extraction_fixture()
                nation[field] = None
                with (
                    patch.object(projection_adapter, "first_value", side_effect=lambda _indexed, wanted_type: time_state if wanted_type == "TITimeState" else global_state),
                    patch.object(projection_adapter, "ti_datetime", return_value=datetime(2045, 1, 1)),
                    patch.object(projection_adapter, "nation_control_points", return_value=[control_point]),
                    patch.object(projection_adapter, "nation_population_millions", return_value=1.0),
                    patch.object(projection_adapter, "state_value_by_id", side_effect=lambda _indexed, state_id: {101: region, 102: {"xenoformingLevel": 0.0}}.get(state_id)),
                    patch.object(projection_adapter, "type_entries", return_value=[]),
                    patch.object(projection_adapter, "temperature_anomaly_components", return_value={"total": 0.0}),
                    patch.object(projection_adapter, "nation_current_mission_control", return_value=0),
                    patch.object(projection_adapter, "federation_space_program", return_value=False),
                    patch.object(projection_adapter, "scenario_template_name", return_value="ModernScenario"),
                    self.assertRaises(ti_save_parser.CalculationDependencyError) as caught,
                ):
                    ti_save_parser.extract_nation_projection_state(
                        indexed,
                        1,
                        nation,
                        {},
                        {7: {}},
                        development,
                    )

                dependency = caught.exception.missing_dependencies[0]
                self.assertEqual(dependency["kind"], "save-field")
                self.assertEqual(dependency["name"], field)
                self.assertEqual(dependency["context"], rule_id)

    def test_projection_welfare_catalog_number_rejects_missing_or_malformed_value(self):
        development_base = {"priorities": {}, "globalConfig": {}}
        cases = (
            {},
            {"welfarePriorityInequalityChange": None},
            {"welfarePriorityInequalityChange": {"value": "invalid"}},
        )
        for global_config in cases:
            with self.subTest(global_config=global_config):
                development = {**development_base, "globalConfig": global_config}
                catalogs = SimpleNamespace(
                    nation_development=development,
                    traits={},
                    effects={},
                )
                with (
                    patch.object(projection_adapter, "match_raw_state", return_value=(1, {})),
                    patch.object(projection_adapter, "find_faction_state", return_value=(2, {})),
                    patch.object(projection_adapter, "calculation_catalogs", return_value=catalogs),
                    patch.object(projection_adapter, "councilor_summary_maps", return_value=({}, {})),
                    patch.object(projection_adapter, "projection_advisor_profiles", return_value=({}, {})),
                    patch.object(projection_adapter, "nation_control_points", return_value=[]),
                    patch.object(projection_adapter, "projection_advisor_mission_schedule", return_value=None),
                    patch.object(projection_adapter, "extract_nation_projection_state", return_value=object()),
                    patch.object(projection_adapter.nation_projection_layer, "parse_projection_document", return_value=((), ())),
                    patch.object(projection_adapter, "faction_effect_contexts", return_value={}),
                    patch.object(projection_adapter, "apply_effect_modifiers", return_value=1.0),
                    patch.object(projection_adapter, "scenario_template_name", return_value="ModernScenario"),
                    self.assertRaises(ti_save_parser.CalculationDependencyError) as caught,
                ):
                    projection_adapter.calculate_nation_projection(
                        object(), "KOR", None, None,
                        days=1, checkpoints=[], details=False, diagnostics=False,
                    )

                dependency = caught.exception.missing_dependencies[0]
                self.assertEqual(dependency["kind"], "catalog-field")
                self.assertEqual(
                    dependency["name"],
                    "globalConfig.welfarePriorityInequalityChange.value",
                )
                self.assertEqual(
                    dependency["context"],
                    ti_save_parser.Rules.NATION_PRIORITY_WELFARE_INEQUALITY.id,
                )


if __name__ == "__main__":
    unittest.main()
