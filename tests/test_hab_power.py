import math
import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import ti_save_parser as ti


def ref(state_id):
    return {"value": state_id}


def add_state(gamestates, type_name, state_id, value):
    value = dict(value)
    value.setdefault("ID", ref(state_id))
    gamestates.setdefault(type_name, []).append({"Key": ref(state_id), "Value": value})
    return value


class HabPowerTests(unittest.TestCase):
    def test_variable_solar_power_fails_without_body_templates(self):
        gamestates = {}
        add_state(gamestates, "TISpaceBodyState", 10, {"templateName": "Sol"})
        add_state(gamestates, "TISpaceBodyState", 11, {"templateName": "Mercury", "barycenter": ref(10)})
        add_state(gamestates, "TIHabSiteState", 20, {"parentBody": ref(11), "latitude": 0.0})
        indexed = ti.build_index({"gamestates": gamestates})
        hab = {"displayName": "Mercury Base", "habType": "Base", "barycenter": ref(11), "habSite": ref(20)}
        solar = {"dataName": "SolarArray", "power": 80, "specialRules": ["Solar_Power_Variable_Output"]}

        with self.assertRaisesRegex(ti.SolarPowerDataError, "space-body template catalog"):
            ti.hab_module_power(solar, indexed=indexed, hab=hab, body_templates={})

    def test_variable_solar_power_fails_when_location_body_template_is_missing(self):
        gamestates = {}
        add_state(gamestates, "TISpaceBodyState", 10, {"templateName": "Sol"})
        add_state(gamestates, "TISpaceBodyState", 11, {"templateName": "Mercury", "barycenter": ref(10)})
        add_state(gamestates, "TIHabSiteState", 20, {"parentBody": ref(11), "latitude": 0.0})
        indexed = ti.build_index({"gamestates": gamestates})
        hab = {"displayName": "Mercury Base", "habType": "Base", "barycenter": ref(11), "habSite": ref(20)}
        solar = {"dataName": "SolarArray", "power": 80, "specialRules": ["Solar_Power_Variable_Output"]}

        with self.assertRaisesRegex(ti.SolarPowerDataError, "body template 'Mercury'"):
            ti.hab_module_power(
                solar,
                indexed=indexed,
                hab=hab,
                body_templates={"Sol": {"dataName": "Sol", "objectType": "Star"}},
            )

    def test_orbital_variable_solar_power_fails_when_orbit_template_is_missing(self):
        gamestates = {}
        add_state(gamestates, "TISpaceBodyState", 10, {"templateName": "Sol"})
        add_state(gamestates, "TISpaceBodyState", 11, {"templateName": "Mercury", "barycenter": ref(10)})
        add_state(gamestates, "TIOrbitState", 20, {"templateName": "MercuryLowOrbit", "barycenter": ref(11)})
        indexed = ti.build_index({"gamestates": gamestates})
        hab = {"displayName": "Mercury Station", "habType": "Station", "barycenter": ref(11), "orbitState": ref(20)}
        solar = {"dataName": "SolarArray", "power": 80, "specialRules": ["Solar_Power_Variable_Output"]}
        bodies = {
            "Sol": {"dataName": "Sol", "objectType": "Star"},
            "Mercury": {"dataName": "Mercury", "objectType": "Planet", "semiMajorAxis_AU": 0.4},
        }

        with self.assertRaisesRegex(ti.SolarPowerDataError, "orbit template catalog"):
            ti.hab_module_power(solar, indexed=indexed, hab=hab, body_templates=bodies, orbit_templates={})

        with self.assertRaisesRegex(ti.SolarPowerDataError, "orbit template 'MercuryLowOrbit'"):
            ti.hab_module_power(
                solar,
                indexed=indexed,
                hab=hab,
                body_templates=bodies,
                orbit_templates={"DifferentOrbit": {"dataName": "DifferentOrbit", "altitude_km": 100.0}},
            )

    def test_variable_solar_power_fails_when_solar_distance_is_unresolved(self):
        gamestates = {}
        add_state(gamestates, "TISpaceBodyState", 11, {"templateName": "UnknownOrbitBody"})
        add_state(gamestates, "TIHabSiteState", 20, {"parentBody": ref(11), "latitude": 0.0})
        indexed = ti.build_index({"gamestates": gamestates})
        hab = {"displayName": "Unlocated Base", "habType": "Base", "barycenter": ref(11), "habSite": ref(20)}
        solar = {"dataName": "SolarArray", "power": 80, "specialRules": ["Solar_Power_Variable_Output"]}

        with self.assertRaisesRegex(ti.SolarPowerDataError, "solar distance could not be derived"):
            ti.hab_module_power(
                solar,
                indexed=indexed,
                hab=hab,
                body_templates={"UnknownOrbitBody": {"dataName": "UnknownOrbitBody", "objectType": "Planet"}},
            )

    def test_variable_solar_error_propagates_through_power_summary(self):
        solar = {"dataName": "SolarArray", "power": 80, "specialRules": ["Solar_Power_Variable_Output"]}
        record = {
            "templateName": "SolarArray",
            "template": solar,
            "completed": True,
            "powered": True,
            "destroyed": False,
            "decommissioning": False,
        }

        with self.assertRaisesRegex(ti.SolarPowerDataError, "nominal module power is not a valid fallback"):
            ti.hab_power_summary([record])

    def test_fixed_output_power_does_not_require_location_templates(self):
        self.assertEqual(ti.hab_module_power({"dataName": "FissionPile", "power": 20}), 20)

    def test_radial_orbit_radius_respects_small_body_hill_radius_and_minimum_altitude(self):
        orbit_template = {"radialOrbit": True}
        body_template = {
            "dimensionX_km": 26.8,
            "dimensionY_km": 22.4,
            "dimensionZ_km": 18.4,
            "Hill Radius in km": 16.31,
        }

        self.assertAlmostEqual(ti.orbit_template_semi_major_axis_km(orbit_template, body_template), 23.4)

    def test_surface_solar_power_applies_distance_polar_and_mirror_bonuses(self):
        gamestates = {}
        add_state(gamestates, "TISpaceBodyState", 10, {"templateName": "Sol"})
        add_state(
            gamestates,
            "TISpaceBodyState",
            11,
            {
                "templateName": "Mercury",
                "barycenter": ref(10),
                "solarMirrorBonus": [{"Key": ref(1), "Value": 6}],
            },
        )
        add_state(gamestates, "TIHabSiteState", 20, {"parentBody": ref(11), "latitude": 90.0})
        indexed = ti.build_index({"gamestates": gamestates})
        hab = {"habType": "Base", "barycenter": ref(11), "habSite": ref(20), "faction": ref(1)}
        body_templates = {
            "Sol": {"dataName": "Sol", "objectType": "Star"},
            "Mercury": {
                "dataName": "Mercury",
                "objectType": "Planet",
                "atmosphere": "Trace",
                "tilt_Deg": 2.0,
                "semiMajorAxis_AU": 0.5,
            },
        }
        solar_array = {
            "dataName": "SolarArray",
            "tier": 2,
            "power": 80,
            "specialRules": ["Solar_Power_Variable_Output"],
        }

        self.assertEqual(
            ti.hab_module_power(solar_array, indexed=indexed, hab=hab, body_templates=body_templates),
            252,
        )

    def test_orbital_solar_power_applies_distance_and_body_occlusion_without_mirror_bonus(self):
        gamestates = {}
        add_state(gamestates, "TISpaceBodyState", 10, {"templateName": "Sol"})
        add_state(
            gamestates,
            "TISpaceBodyState",
            11,
            {
                "templateName": "Mars",
                "barycenter": ref(10),
                "solarMirrorBonus": [{"Key": ref(1), "Value": 100}],
            },
        )
        add_state(gamestates, "TIOrbitState", 20, {"templateName": "TestMarsOrbit", "barycenter": ref(11)})
        indexed = ti.build_index({"gamestates": gamestates})
        hab = {"habType": "Station", "barycenter": ref(11), "orbitState": ref(20), "faction": ref(1)}
        body_templates = {
            "Sol": {"dataName": "Sol", "objectType": "Star"},
            "Mars": {
                "dataName": "Mars",
                "objectType": "Planet",
                "semiMajorAxis_AU": 2.0,
                "equatorialRadius_km": 100.0,
            },
        }
        orbit_templates = {"TestMarsOrbit": {"dataName": "TestMarsOrbit", "altitude_km": 100.0}}
        solar_array = {
            "dataName": "SolarArray",
            "tier": 2,
            "power": 80,
            "specialRules": ["Solar_Power_Variable_Output"],
        }
        expected_multiplier = (1.0 - math.atan(0.5) / math.pi) / 4.0

        self.assertAlmostEqual(
            ti.hab_natural_solar_multiplier(indexed, hab, body_templates, orbit_templates),
            expected_multiplier,
        )
        self.assertEqual(
            ti.hab_module_power(
                solar_array,
                indexed=indexed,
                hab=hab,
                body_templates=body_templates,
                orbit_templates=orbit_templates,
            ),
            17,
        )

    def test_power_summaries_use_effective_solar_output_and_enforce_maximum(self):
        gamestates = {}
        add_state(gamestates, "TISpaceBodyState", 10, {"templateName": "Sol"})
        add_state(
            gamestates,
            "TISpaceBodyState",
            11,
            {
                "templateName": "Mercury",
                "barycenter": ref(10),
                "solarMirrorBonus": [{"Key": ref(1), "Value": 500}],
            },
        )
        add_state(gamestates, "TIHabSiteState", 20, {"parentBody": ref(11), "latitude": 0.0})
        indexed = ti.build_index({"gamestates": gamestates})
        hab = {"habType": "Base", "barycenter": ref(11), "habSite": ref(20), "faction": ref(1)}
        body_templates = {
            "Sol": {"dataName": "Sol", "objectType": "Star"},
            "Mercury": {
                "dataName": "Mercury",
                "objectType": "Planet",
                "atmosphere": "Trace",
                "semiMajorAxis_AU": 0.1,
            },
        }
        solar_array = {
            "dataName": "SolarArray",
            "tier": 2,
            "power": 80,
            "specialRules": ["Solar_Power_Variable_Output"],
        }
        records = [
            {
                "templateName": "SolarArray",
                "template": solar_array,
                "completed": True,
                "powered": True,
                "destroyed": False,
                "decommissioning": False,
            },
            {
                "templateName": "Consumer",
                "template": {"dataName": "Consumer", "power": -30},
                "completed": True,
                "powered": True,
                "destroyed": False,
                "decommissioning": False,
            },
        ]

        self.assertEqual(
            ti.hab_power_summary(records, indexed=indexed, hab=hab, body_templates=body_templates),
            {"consumed": 30, "generated": 640, "net": 610},
        )
        self.assertEqual(
            ti.hab_projected_power_summary(records, indexed=indexed, hab=hab, body_templates=body_templates),
            {"consumed": 30, "generated": 640, "net": 610},
        )


if __name__ == "__main__":
    unittest.main()
