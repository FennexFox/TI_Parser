import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import ti_parser_core as core
import ti_save_parser as ti


def ref(state_id):
    return {"value": state_id}


def add_state(gamestates, type_name, state_id, value):
    value = dict(value)
    value.setdefault("ID", ref(state_id))
    gamestates.setdefault(type_name, []).append({"Key": ref(state_id), "Value": value})
    return value


class ParserReliabilityTests(unittest.TestCase):
    def test_non_resistance_human_player_is_selected_from_player_state(self):
        gamestates = {}
        add_state(gamestates, "TIFactionState", 10, {"templateName": "ResistCouncil", "displayName": "Resistance"})
        academy = add_state(
            gamestates,
            "TIFactionState",
            11,
            {"templateName": "CooperateCouncil", "displayName": "Academy", "player": ref(21)},
        )
        add_state(gamestates, "TIPlayerState", 20, {"isAI": True, "faction": ref(10)})
        add_state(gamestates, "TIPlayerState", 21, {"isAI": False, "faction": ref(11)})
        add_state(gamestates, "TIMetadataState", 1, {"playerFactionName": "Academy"})
        indexed = ti.build_index({"gamestates": gamestates})

        faction_id, faction = ti.find_faction_state(indexed)

        self.assertEqual(faction_id, 11)
        self.assertIs(faction, academy)
        self.assertTrue(ti.faction_is_player(indexed, faction))
        self.assertEqual(ti.find_faction_state(indexed, "ResistCouncil")[0], 10)

    def test_unresolved_player_faction_fails_closed(self):
        indexed = ti.build_index(
            {
                "gamestates": {
                    "TIFactionState": [
                        {"Key": ref(10), "Value": {"ID": ref(10), "templateName": "ResistCouncil"}},
                        {"Key": ref(11), "Value": {"ID": ref(11), "templateName": "CooperateCouncil"}},
                    ]
                }
            }
        )
        with self.assertRaises(SystemExit):
            ti.find_faction_state(indexed)

    def test_packaged_catalog_supplies_operations_center_and_missing_catalog_fails(self):
        templates = core.load_hab_module_catalog()
        self.assertEqual(templates["OperationsCenter"]["missionControl"], 4)
        self.assertEqual(templates["OperationsCenter"]["power"], -100)
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(core.ModuleCatalogError):
                core.load_hab_module_catalog(Path(tmp) / "missing.json")

    def test_missing_module_template_fails_instead_of_becoming_zero(self):
        gamestates = {}
        add_state(gamestates, "TIHabModuleState", 20, {"templateName": "UnknownModule"})
        add_state(gamestates, "TISectorState", 11, {"faction": ref(1), "hab": ref(10), "habModules": [ref(20)]})
        hab = add_state(gamestates, "TIHabState", 10, {"faction": ref(1), "sectors": [ref(11)]})
        indexed = ti.build_index({"gamestates": gamestates})
        with self.assertRaises(core.ModuleCatalogError):
            ti.hab_module_records(indexed, hab, {})

    def test_missing_active_cp_effect_template_fails_instead_of_becoming_zero(self):
        indexed = ti.build_index({"gamestates": {}})
        with self.assertRaises(RuntimeError):
            ti.faction_control_point_maintenance(
                indexed,
                None,
                1,
                {},
                {},
                {"ControlPointMaintenance": ["UnknownCPModifier"]},
                {},
            )

    def test_upgrade_uses_game_specific_prior_template_semantics(self):
        record = {
            "templateName": "Target",
            "template": {
                "dataName": "Target",
                "crew": 12,
                "incomeVolatiles_month": 100,
                "supportMaterials_month": {"volatiles": 20},
                "power": -20,
                "missionControl": 10,
            },
            "priorTemplateName": "Prior",
            "priorTemplate": {
                "dataName": "Prior",
                "incomeVolatiles_month": 10,
                "supportMaterials_month": {"volatiles": 1},
                "power": 5,
                "missionControl": 4,
            },
            "state": {"priorModuleCompleted": True, "completionDate": "2035-02-01T00:00:00"},
            "completed": False,
            "powered": False,
            "destroyed": False,
            "decommissioning": False,
        }
        monthly = ti.hab_monthly_resource_income(
            {"anyCoreCompleted": True},
            [record],
            "Volatiles",
            1.0,
        )

        self.assertAlmostEqual(monthly["income"], 0.0)
        self.assertAlmostEqual(monthly["support"], 0.35)
        self.assertAlmostEqual(monthly["net"], -0.35)
        self.assertEqual(ti.hab_power_summary([record]), {"consumed": 0, "generated": 0, "net": 0})
        self.assertEqual(ti.hab_module_current_mission_control(record), 4)

    def test_new_construction_is_crew_only_until_completion(self):
        record = {
            "templateName": "Producer",
            "template": {
                "dataName": "Producer",
                "crew": 12,
                "incomeVolatiles_month": 10,
                "supportMaterials_month": {"volatiles": 2},
            },
            "state": {"completionDate": "2035-02-01T00:00:00"},
            "completed": False,
            "powered": False,
            "destroyed": False,
            "decommissioning": False,
        }
        before = ti.hab_monthly_resource_income(
            {"anyCoreCompleted": True}, [record], "Volatiles", 1.0, at_date=datetime(2035, 1, 1)
        )
        after = ti.hab_monthly_resource_income(
            {"anyCoreCompleted": True}, [record], "Volatiles", 1.0, at_date=datetime(2035, 2, 1)
        )

        self.assertAlmostEqual(before["support"], 0.35)
        self.assertEqual(before["income"], 0.0)
        self.assertAlmostEqual(after["support"], 2.35)
        self.assertEqual(after["income"], 10.0)

    def test_unpowered_special_rule_still_consumes_mission_control(self):
        record = {
            "templateName": "Core",
            "template": {"missionControl": -2, "specialRules": ["ConsumesMCWhenUnpowered"]},
            "completed": True,
            "powered": False,
            "destroyed": False,
            "decommissioning": False,
        }
        self.assertEqual(ti.hab_module_current_mission_control(record), -2)

    def test_mining_combines_site_module_org_effects_and_month_conversion(self):
        gamestates = {}
        faction = add_state(gamestates, "TIFactionState", 1, {"councilors": [ref(2)]})
        add_state(gamestates, "TICouncilorState", 2, {"orgs": [ref(3)]})
        add_state(gamestates, "TIOrgState", 3, {"applyingBonuses": True, "miningBonus": 0.25})
        indexed = ti.build_index({"gamestates": gamestates})
        template = {"mine": True, "miningModifier": 1.5}
        effects = {
            "Space": {"operation": "Additive", "value": 0.2},
            "Vol": {"operation": "Additive", "value": 0.1},
        }

        monthly = ti.hab_template_income(
            "Volatiles",
            template,
            indexed=indexed,
            faction=faction,
            hab_site={"volatiles_day": 2.0},
            effect_contexts={"SpaceMiningBonus": ["Space"], "MiningVolatilesBonus": ["Vol"]},
            effect_templates=effects,
        )

        self.assertAlmostEqual(monthly, 2.0 * 1.5 * 1.55 * ti.DAYS_PER_YEAR / 12.0)

    def test_mining_fails_when_authoritative_site_yield_is_missing(self):
        indexed = ti.build_index({"gamestates": {}})
        with self.assertRaises(RuntimeError):
            ti.hab_template_income(
                "Volatiles",
                {"mine": True, "miningModifier": 1.0},
                indexed=indexed,
                faction={},
                hab_site={"water_day": 1.0},
            )

    def test_completion_forecast_recalculates_before_and_after_event(self):
        gamestates = {}
        faction = add_state(
            gamestates,
            "TIFactionState",
            1,
            {"templateName": "CooperateCouncil", "displayName": "Academy", "player": ref(2), "habSectors": [ref(11)]},
        )
        add_state(gamestates, "TIPlayerState", 2, {"isAI": False, "faction": ref(1)})
        add_state(gamestates, "TIMetadataState", 3, {"playerFactionName": "Academy"})
        add_state(
            gamestates,
            "TITimeState",
            4,
            {"currentDateTime": {"year": 2035, "month": 1, "day": 1, "hour": 0, "minute": 0, "second": 0}},
        )
        add_state(
            gamestates,
            "TIHabModuleState",
            20,
            {
                "templateName": "Producer",
                "constructionCompleted": False,
                "powered": False,
                "completionDate": "2035-02-01T00:00:00",
            },
        )
        add_state(gamestates, "TISectorState", 11, {"faction": ref(1), "hab": ref(10), "habModules": [ref(20)]})
        add_state(
            gamestates,
            "TIHabState",
            10,
            {"displayName": "Test Hab", "faction": ref(1), "sectors": [ref(11)], "anyCoreCompleted": True},
        )
        indexed = ti.build_index({"gamestates": gamestates})
        forecast = ti.forecast_faction_hab_resource(
            indexed,
            faction,
            {"Producer": {"dataName": "Producer", "incomeVolatiles_month": 10, "supportMaterials_month": {"volatiles": 1}}},
            {},
            {},
            {},
            "Volatiles",
        )

        self.assertEqual(len(forecast["events"]), 2)
        self.assertEqual(forecast["events"][0]["net"], 0.0)
        self.assertEqual(forecast["events"][1]["net"], 9.0)
        self.assertEqual(forecast["firstSustainedSurplusDate"], "2035-02-01T00:00:00")

    def test_exit_save_three_regression_when_local_fixture_is_available(self):
        save_path = next(
            (
                directory / "ExitSave(3).gz"
                for directory in ti.candidate_save_dirs()
                if (directory / "ExitSave(3).gz").is_file()
            ),
            None,
        )
        if save_path is None:
            self.skipTest("local ExitSave(3).gz fixture is not installed")
        indexed = ti.build_index(ti.load_save(save_path))
        templates_dir = ti.resolve_scenario_templates(save_path, ti.resolve_templates_dir(None))
        result = ti.calculate_topbar(indexed, templates_dir, include_details=True)

        self.assertEqual(result["faction"]["template"], "CooperateCouncil")
        self.assertTrue(result["faction"]["player"])
        self.assertEqual(result["resources"]["MissionControl"]["usage"], 164.0)
        self.assertGreater(result["resources"]["MissionControl"]["capacity"], 119.0)
        cp = result["controlPointMaintenance"]
        self.assertGreater(cp["cap"], 500.0)
        self.assertAlmostEqual(sum(cp["breakdown"].values()), cp["cap"])


if __name__ == "__main__":
    unittest.main()
