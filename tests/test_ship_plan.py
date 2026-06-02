import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import ti_save_parser as ti


class ShipPlanTests(unittest.TestCase):
    def test_unlock_filter_checks_projects_disable_and_obsolete_parts(self):
        faction = {
            "finishedProjectNames": ["Project_Ready"],
            "obsoletedShipParts": ["LegacyBattery"],
        }

        self.assertTrue(ti.ship_plan_part_unlocked({"dataName": "Baseline"}, faction))
        self.assertTrue(
            ti.ship_plan_part_unlocked(
                {"dataName": "Ready", "requiredProjectName": "Project_Ready"},
                faction,
            )
        )
        self.assertFalse(
            ti.ship_plan_part_unlocked(
                {"dataName": "Locked", "requiredProjectName": "Project_Missing"},
                faction,
            )
        )
        self.assertFalse(ti.ship_plan_part_unlocked({"dataName": "Disabled", "disable": True}, faction))
        self.assertFalse(ti.ship_plan_part_unlocked({"dataName": "LegacyBattery"}, faction))
        self.assertTrue(ti.ship_plan_part_unlocked({"dataName": "LegacyBattery"}, faction, include_obsolete=True))

    def test_compatible_power_plants_match_class_capacity_and_low_mass(self):
        drive = {
            "requiredPowerPlantClass": "Gas_Core_Fission",
            "powerRequirementGW": 10,
        }
        plants = [
            {"template": "TooSmall", "powerPlantClass": "Gas_Core_Fission", "maxOutputGW": 9, "specificMassTonsPerGW": 1},
            {"template": "WrongClass", "powerPlantClass": "Solid_Core_Fission", "maxOutputGW": 20, "specificMassTonsPerGW": 1},
            {"template": "Heavy", "powerPlantClass": "Gas_Core_Fission", "maxOutputGW": 20, "specificMassTonsPerGW": 5},
            {"template": "Light", "powerPlantClass": "Gas_Core_Fission", "maxOutputGW": 10, "specificMassTonsPerGW": 2},
        ]

        matches = ti.ship_plan_compatible_power_plants(drive, plants)

        self.assertEqual([row["template"] for row in matches], ["Light", "Heavy"])

    def test_drive_goal_views_keep_thrust_and_exhaust_velocity_separate(self):
        drives = [
            ti.ship_plan_drive_row({"dataName": "Fast", "thrust_N": 100, "EV_kps": 5}),
            ti.ship_plan_drive_row({"dataName": "Efficient", "thrust_N": 10, "EV_kps": 50}),
        ]

        views = ti.ship_plan_drive_goal_views(drives, [], top=1)

        self.assertEqual(views["thrust"][0]["template"], "Fast")
        self.assertEqual(views["exhaustVelocity"][0]["template"], "Efficient")

    def test_self_powered_drive_classes_do_not_require_reactor_output(self):
        self.assertEqual(
            ti.ship_plan_drive_power_requirement_gw(
                {
                    "driveClassification": "NuclearSaltWater",
                    "thrust_N": 1_000_000,
                    "EV_kps": 10,
                    "efficiency": 0.5,
                }
            ),
            0,
        )
        self.assertEqual(
            ti.ship_plan_drive_power_requirement_gw(
                {
                    "driveClassification": "Fission_Thermal",
                    "thrust_N": 1_000_000,
                    "EV_kps": 10,
                    "efficiency": 0.5,
                }
            ),
            10,
        )

    def test_weapon_row_reports_ship_mount_and_damage_proxy(self):
        row = ti.ship_plan_weapon_row(
            {
                "dataName": "TestMissile",
                "mount": "HalfHull",
                "attackMode": True,
                "flatDamage_MJ": 12,
                "salvo_shots": 3,
                "cooldown_s": 2,
            },
            "missile",
        )

        self.assertEqual(row["mountLocation"], "hull")
        self.assertEqual(row["mountSlots"], 0.5)
        self.assertEqual(row["damagePerCooldownMJPerSecondProxy"], 18)
        self.assertEqual(ti.ship_plan_weapon_row({"dataName": "FighterGun", "mount": "HalfNose"}, "gun")["mountSlots"], 0.5)
        self.assertIsNone(ti.ship_plan_weapon_row({"dataName": "BaseDefense", "mount": "T1BaseDefense"}, "laser"))

    def test_utility_role_tags_expose_colony_assault_and_science_modules(self):
        colony = ti.ship_plan_utility_role_tags({"dataName": "SolarOutpostKit", "specialModuleRules": ["FoundSolarOutpost"]})
        assault = ti.ship_plan_utility_role_tags({"dataName": "MarineAssaultUnit", "specialModuleRules": ["Assault"]})
        science = ti.ship_plan_utility_role_tags({"dataName": "MobileLab", "specialModuleRules": ["GenerateSpaceScienceBonus", "Prospector"]})

        self.assertIn("colony", colony)
        self.assertIn("assault", assault)
        self.assertIn("science", science)

    def test_parser_exposes_ship_plan_options(self):
        args = ti.build_parser().parse_args(
            ["ship-plan", "--role", "transfer", "--top", "3", "--include-obsolete", "--design", "Defiant"]
        )

        self.assertEqual(args.command, "ship-plan")
        self.assertEqual(args.role, "transfer")
        self.assertEqual(args.top, 3)
        self.assertTrue(args.include_obsolete)
        self.assertEqual(args.design, "Defiant")

    def test_select_design_prefers_exact_name_and_rejects_ambiguous_fragments(self):
        designs = [
            {"template": "playerShipTemplate1", "display": "PKG Defiant"},
            {"template": "playerShipTemplate2", "display": "PKL Defiant Escort"},
        ]

        self.assertEqual(ti.ship_plan_select_design(designs, "PKG Defiant")["template"], "playerShipTemplate1")
        with self.assertRaises(SystemExit):
            ti.ship_plan_select_design(designs, "Defiant")

    def test_simulate_ship_design_reconstructs_non_combat_builder_values(self):
        indexed = ti.IndexedState(data={}, gamestates={}, id_index={})
        catalogs = {
            "hulls": {
                "TestHull": {
                    "dataName": "TestHull",
                    "mass_tons": 100,
                    "crew": 2,
                    "consTier": 2,
                    "length_m": 10,
                    "width_m": 2,
                    "baseConstructionTime_days": 100,
                    "missionControl": 1,
                    "monthlyIncome_Money": -1,
                    "weightedBuildMaterials": {"metals": 1},
                }
            },
            "drives": {
                "TestDrive": {
                    "dataName": "TestDrive",
                    "thrust_N": 100_000,
                    "EV_kps": 10,
                    "efficiency": 0.5,
                    "req power": 1,
                    "flatMass_tons": 5,
                    "specificPower_kgMW": 0,
                    "thrustCap": 2,
                    "cooling": "Closed",
                    "requiredPowerPlant": "Any_General",
                    "weightedBuildMaterials": {"metals": 1},
                    "perTankPropellantMaterials": {"water": 1},
                }
            },
            "powerPlants": {
                "TestPlant": {
                    "dataName": "TestPlant",
                    "powerPlantClass": "Fuel_Cell",
                    "maxOutput_GW": 10,
                    "specificPower_tGW": 2,
                    "efficiency": 0.8,
                    "crew": 1,
                    "weightedBuildMaterials": {"fissiles": 1},
                }
            },
            "radiators": {
                "TestRadiator": {
                    "dataName": "TestRadiator",
                    "specificPower_2s_KWkg": 10,
                    "weightedBuildMaterials": {"nobleMetals": 1},
                }
            },
            "armors": {},
            "utilities": {
                "Magazine": {
                    "dataName": "Magazine",
                    "_shipPlanKind": "utility",
                    "crew": 1,
                    "mass_tons": 10,
                    "specialModuleRules": ["Magazine"],
                    "specialModuleValue": 0.5,
                    "weightedBuildMaterials": {"metals": 1},
                }
            },
            "weapons": {
                "TestMissile": {
                    "dataName": "TestMissile",
                    "_shipPlanKind": "missile",
                    "crew": 1,
                    "baseWeaponMass_tons": 2,
                    "magazine": 4,
                    "ammoMass_kg": 100,
                    "weightedBuildMaterials": {"metals": 1},
                    "ammoMaterials": {"volatiles": 1},
                }
            },
            "effects": {},
            "shipyards": {},
        }
        design = {
            "hullName": "TestHull",
            "driveName": "TestDrive",
            "powerPlantName": "TestPlant",
            "radiatorName": "TestRadiator",
            "propellantTanks": 1,
            "moduleTemplateEntries": [{"moduleName": "Magazine"}],
            "hullWeaponTemplateEntries": [{"moduleName": "TestMissile"}],
            "noseWeaponTemplateEntries": [],
            "noseArmor": {},
            "lateralArmor": {},
            "tailArmor": {},
        }

        simulation = ti.simulate_ship_design(indexed, 1, {}, design, catalogs)

        self.assertTrue(simulation["complete"])
        self.assertEqual(simulation["crew"], 5)
        self.assertAlmostEqual(simulation["massTons"]["weapons"], 2.6)
        self.assertAlmostEqual(simulation["massTons"]["wet"], 259.848119, places=5)
        self.assertAlmostEqual(simulation["storage"]["magazineMultiplier"], 0.5)
        self.assertAlmostEqual(simulation["construction"]["resources"]["water"], 11)
        self.assertAlmostEqual(simulation["construction"]["resources"]["volatiles"], 1.06)
        self.assertAlmostEqual(simulation["construction"]["time"]["byShipyardTier"]["1"]["days"], 150)
        self.assertAlmostEqual(simulation["construction"]["time"]["byShipyardTier"]["3"]["days"], 60)
        self.assertFalse(simulation["combatPerformanceRatingIncluded"])


if __name__ == "__main__":
    unittest.main()
