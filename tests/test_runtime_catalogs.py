import json
import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import build_runtime_catalogs as builder
from ti_parser_catalogs import (
    CalculationDependencyError,
    CatalogError,
    RuntimeCatalogs,
    file_sha256,
    validate_catalog_envelope,
    value_fingerprint,
)
from ti_parser_core import CalculationDependencyError as CoreCalculationDependencyError


def write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


class RuntimeCatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.game = self.root / "Terra Invicta"
        self.templates = self.game / "TerraInvicta_Data" / "StreamingAssets" / "Templates"
        self.dlc = self.game / "DLC_Content"
        self.output = self.root / "out"
        self._write_fixture()
        builder.build_all(self.templates, self.output, dlc_content_dir=self.dlc)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _write_fixture(self):
        write_json(
            self.templates / "TIMetaTemplate.json",
            [
                {
                    "dataName": "ModernScenario",
                    "isNewCampaignOption": True,
                    "newCampaignOptionCategory": "Scenario",
                },
                {
                    "dataName": "CompleteSolarSystem",
                    "isNewCampaignOption": True,
                    "newCampaignOptionCategory": "SolarSystem",
                },
            ],
        )
        write_json(
            self.templates / "TIEffectTemplate.json",
            [
                {
                    "dataName": "Effect_Test",
                    "operation": "Additive",
                    "value": 2,
                    "effectTarget": "SourceFaction",
                    "effectDuration": "permanent",
                    "stackable": True,
                    "duration_months": -1,
                    "contexts": ["Research"],
                    "unrelatedAsset": "not packaged",
                }
            ],
        )
        write_json(
            self.templates / "TITraitTemplate.json",
            [
                {
                    "dataName": "Trait_Test",
                    "friendlyName": "Test Trait",
                    "incomeMoney": 1,
                    "statMods": [],
                    "techBonuses": [],
                    "priorityBonuses": [],
                }
            ],
        )
        write_json(
            self.templates / "TIOrgTemplate.json",
            [
                {
                    "dataName": "Org_Test",
                    "friendlyName": "Test Org",
                    "orgType": "Commercial",
                    "tier": 1,
                    "requiresNationality": False,
                    "techBonuses": [],
                }
            ],
        )
        write_json(self.templates / "TIGlobalConfig.json", {"dataName": "globalConfig"})
        write_json(
            self.templates / "TINationTemplate.json",
            [
                {"dataName": "ModernNation"},
                {"dataName": "SharedNation", "popGrowthModifier": 0.1},
            ],
        )
        write_json(
            self.templates / "TIRegionTemplate.json",
            [
                {
                    "dataName": "ModernRegion",
                    "mapRegionName": "map_ModernRegion",
                    "annualPopGrowthModifier": 1.25,
                    "environment": "Vulnerable",
                    "mineCapable": True,
                },
                {"dataName": "DefaultedRegion", "mapRegionName": "map_DefaultedRegion"},
            ],
        )
        write_json(
            self.templates / "TIMapRegionTemplate.json",
            [
                {"dataName": "map_ModernRegion", "latitude": 37.21, "longitude": -119.04},
                {"dataName": "map_DefaultedRegion", "latitude": 0, "longitude": 12.5},
                {"dataName": "map_2003Region", "latitude": 5, "longitude": 10},
                {"dataName": "map_BrokenRegion", "latitude": 27.5, "longitude": -108},
            ],
        )
        write_json(
            self.templates / "TIStartTimeTemplate.json",
            [{"dataName": "ModernStart"}],
        )
        write_json(
            self.templates / "TIBilateralTemplate.json",
            [
                {
                    "dataName": "PhysicalAdjacencyModernDefaulted",
                    "relationType": "PhysicalAdjacency",
                    "region1": "map_ModernRegion",
                    "region2": "map_DefaultedRegion",
                }
            ],
        )
        assembly = self.game / "TerraInvicta_Data" / "Managed" / "Assembly-CSharp.dll"
        assembly.parent.mkdir(parents=True, exist_ok=True)
        assembly.write_bytes(b"fixture assembly with TIGlobalConfig default 1.5f")

        for collection, (filename, _kind, _fields) in builder.SHIP_COLLECTIONS.items():
            row = {
                "dataName": f"{collection}_Test",
                "friendlyName": collection,
                "requiredProjectName": None,
                "weightedBuildMaterials": {"metals": 1},
            }
            if collection == "hulls":
                row.update({"mass_tons": 10, "length_m": 10, "width_m": 4})
            if collection == "drives":
                row.update({"thrust_N": 100, "EV_kps": 10, "efficiency": 0.5})
            if collection == "powerPlants":
                row.update({"maxOutput_GW": 10, "powerPlantClass": "Any_General"})
            if "Weapons" in collection or collection in {"guns", "missiles"}:
                row.update({"mount": "OneHull", "attackMode": True, "cooldown_s": 5})
            write_json(self.templates / filename, [row])

        scenario_specs = {
            "2003Scenario": builder.SCENARIO_DIRECTORIES["2003Scenario"],
            "BrokenEarthScenario": builder.SCENARIO_DIRECTORIES["BrokenEarthScenario"],
        }
        for scenario, relative in scenario_specs.items():
            directory = self.dlc / relative
            write_json(
                directory / "TIMetaTemplate.json",
                [
                    {
                        "dataName": scenario,
                        "isNewCampaignOption": True,
                        "newCampaignOptionCategory": "Scenario",
                    }
                ],
            )
        scenario_2003 = self.dlc / builder.SCENARIO_DIRECTORIES["2003Scenario"]
        write_json(
            scenario_2003 / "TIEffectTemplate.json",
            [{"dataName": "Effect_Test", "operation": "Multiplicative", "value": 3}],
        )
        write_json(
            scenario_2003 / "TITraitTemplate.json",
            [{"dataName": "Trait_2003", "friendlyName": "2003 Trait", "statMods": []}],
        )
        write_json(
            scenario_2003 / "TIOrgTemplate.json",
            [{"dataName": "Org_Test", "tier": 2}],
        )
        write_json(
            scenario_2003 / "TINationTemplate.json",
            [
                {"dataName": "SharedNation", "popGrowthModifier": 0.25},
                {"dataName": "2003Nation", "popGrowthModifier": -0.15},
            ],
        )
        write_json(
            scenario_2003 / "TIRegionTemplate.json",
            [
                {"dataName": "2003Region", "mapRegionName": "map_2003Region", "environment": "Beneficiary"},
            ],
        )
        write_json(
            scenario_2003 / "TIStartTimeTemplate.json",
            [{"dataName": "2003Start", "populationRegressionPeriod_years": 35}],
        )
        broken = self.dlc / builder.SCENARIO_DIRECTORIES["BrokenEarthScenario"]
        write_json(
            broken / "TIEffectTemplate.json",
            [{"dataName": "Effect_Broken", "operation": "Additive", "value": 4, "contexts": ["Research"]}],
        )
        write_json(
            broken / "TIOrgTemplate.json",
            [{"dataName": "Org_Broken", "friendlyName": "Broken Org", "tier": 1}],
        )
        write_json(
            broken / "TIGlobalConfig.json",
            {
                "scenarioTags": ["PostApoc"],
                "controlPointIPFactor": 0.62,
                "nationalInvestmentArmyFactorHome": 0.2,
                "numPrioritiesForLegitimize": 100,
            },
        )
        write_json(
            broken / "TINationTemplate.json",
            [{"dataName": "BrokenNation", "popGrowthModifier": 0.4}],
        )
        write_json(
            broken / "TIRegionTemplate.json",
            [
                {
                    "dataName": "BrokenRegion",
                    "mapRegionName": "map_BrokenRegion",
                    "annualPopGrowthModifier": 1.21,
                    "mineCapable": True,
                }
            ],
        )
        write_json(
            broken / "TIStartTimeTemplate.json",
            [{"dataName": "BrokenStart", "populationRegressionPeriod_years": 60}],
        )

    def test_loader_selects_exact_scenario_overlay_and_exposes_claim_config(self):
        modern = RuntimeCatalogs.load("ModernScenario", self.output)
        millennium = RuntimeCatalogs.load("2003Scenario", self.output)

        self.assertEqual(modern.effects["Effect_Test"]["operation"], "Additive")
        self.assertEqual(millennium.effects["Effect_Test"]["operation"], "Multiplicative")
        self.assertEqual(millennium.effects["Effect_Test"]["contexts"], ["Research"])
        self.assertEqual(millennium.orgs["Org_Test"]["tier"], 2)
        self.assertIn("Trait_2003", millennium.traits)
        self.assertNotIn("unrelatedAsset", modern.effects["Effect_Test"])
        self.assertEqual(
            modern.nation_claims["democracyDecreaseToMakeHostileClaim"],
            1.5,
        )
        self.assertIs(CalculationDependencyError, CoreCalculationDependencyError)

    def test_nation_development_packages_resolved_template_data_for_all_scenarios(self):
        modern = RuntimeCatalogs.load("ModernScenario", self.output).nation_development
        millennium = RuntimeCatalogs.load("2003Scenario", self.output).nation_development
        broken = RuntimeCatalogs.load("BrokenEarthScenario", self.output).nation_development

        self.assertEqual(modern["nationTemplates"]["ModernNation"]["popGrowthModifier"], 0.0)
        self.assertEqual(modern["nationTemplates"]["SharedNation"]["popGrowthModifier"], 0.1)
        self.assertEqual(millennium["nationTemplates"]["SharedNation"]["popGrowthModifier"], 0.25)
        self.assertEqual(millennium["nationTemplates"]["2003Nation"]["popGrowthModifier"], -0.15)
        self.assertNotIn("2003Nation", modern["nationTemplates"])
        self.assertEqual(broken["nationTemplates"]["BrokenNation"]["popGrowthModifier"], 0.4)

        defaulted = modern["regionTemplates"]["DefaultedRegion"]
        self.assertEqual(
            defaulted,
            {
                "dataName": "DefaultedRegion",
                "mapRegionName": "map_DefaultedRegion",
                "annualPopGrowthModifier": 0.0,
                "environment": "Standard",
                "mineCapable": False,
                "oilCapable": False,
            },
        )
        self.assertEqual(millennium["regionTemplates"]["2003Region"]["environment"], "Beneficiary")
        self.assertEqual(broken["regionTemplates"]["BrokenRegion"]["annualPopGrowthModifier"], 1.21)
        self.assertEqual(
            broken["mapRegionTemplates"]["map_BrokenRegion"],
            {"dataName": "map_BrokenRegion", "latitude": 27.5, "longitude": -108},
        )
        self.assertEqual(modern["startTimeTemplates"]["ModernStart"]["populationRegressionPeriod_years"], 20.0)
        self.assertEqual(millennium["startTimeTemplates"]["2003Start"]["populationRegressionPeriod_years"], 35)
        self.assertEqual(broken["startTimeTemplates"]["BrokenStart"]["populationRegressionPeriod_years"], 60)

        self.assertEqual(modern["globalConfig"]["controlPointIPScaling"]["value"], 0.35)
        self.assertEqual(broken["globalConfig"]["controlPointIPFactor"]["value"], 0.62)
        self.assertEqual(broken["globalConfig"]["nationalInvestmentArmyFactorHome"]["value"], 0.2)
        self.assertEqual(broken["globalConfig"]["numPrioritiesForLegitimize"]["value"], 100)

        envelope = json.loads((self.output / "nation_development_catalog.json").read_text(encoding="utf-8"))
        source_names = {source["name"] for source in envelope["sourceFiles"]}
        self.assertTrue(
            {
                "base/TINationTemplate.json",
                "base/TIRegionTemplate.json",
                "base/TIMapRegionTemplate.json",
                "base/TIStartTimeTemplate.json",
                "2003Scenario/TINationTemplate.json",
                "2003Scenario/TIRegionTemplate.json",
                "2003Scenario/TIStartTimeTemplate.json",
                "BrokenEarthScenario/TINationTemplate.json",
                "BrokenEarthScenario/TIRegionTemplate.json",
                "BrokenEarthScenario/TIStartTimeTemplate.json",
                "TerraInvicta_Data/Managed/Assembly-CSharp.dll",
            }.issubset(source_names)
        )

    def test_unsupported_scenario_does_not_fall_back(self):
        with self.assertRaisesRegex(CatalogError, "Unsupported scenario"):
            RuntimeCatalogs.load("UnknownScenario", self.output)

    def test_manifest_detects_catalog_file_corruption(self):
        path = self.output / "effect_catalog.json"
        path.write_text(path.read_text(encoding="utf-8") + " ", encoding="utf-8")

        with self.assertRaisesRegex(CatalogError, "file sha256 mismatch"):
            RuntimeCatalogs.load("ModernScenario", self.output)

    def test_envelope_detects_payload_corruption_even_when_json_is_valid(self):
        path = self.output / "trait_catalog.json"
        envelope = json.loads(path.read_text(encoding="utf-8"))
        envelope["base"]["traits"]["Trait_Test"]["incomeMoney"] = 999

        with self.assertRaisesRegex(CatalogError, "payload fingerprint mismatch"):
            validate_catalog_envelope(envelope, path=path)

    def test_missing_manifest_entry_is_fail_closed(self):
        manifest_path = self.output / "catalog_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        del manifest["catalogs"]["ship_catalog.json"]
        manifest["bundleFingerprint"] = value_fingerprint(manifest["catalogs"])
        write_json(manifest_path, manifest)

        with self.assertRaisesRegex(CatalogError, "missing required entries"):
            RuntimeCatalogs.load("ModernScenario", self.output)

    def test_missing_dependency_uses_shared_structured_error(self):
        catalogs = RuntimeCatalogs.load("ModernScenario", self.output)

        with self.assertRaises(CoreCalculationDependencyError) as caught:
            catalogs.require("effect", "Effect_Missing", context="Research")

        self.assertEqual(
            caught.exception.missing_dependencies,
            [
                {
                    "kind": "effect",
                    "name": "Effect_Missing",
                    "context": "Research",
                    "scenario": "ModernScenario",
                    "reason": "missing catalog row",
                }
            ],
        )

    def test_generator_is_byte_for_byte_deterministic(self):
        second_output = self.root / "out-second"
        builder.build_all(self.templates, second_output, dlc_content_dir=self.dlc)

        first_files = sorted(path.name for path in self.output.iterdir())
        second_files = sorted(path.name for path in second_output.iterdir())
        self.assertEqual(first_files, second_files)
        for filename in first_files:
            self.assertEqual((self.output / filename).read_bytes(), (second_output / filename).read_bytes())

    def test_generator_rejects_duplicate_template_rows(self):
        effect_path = self.templates / "TIEffectTemplate.json"
        row = json.loads(effect_path.read_text(encoding="utf-8"))[0]
        write_json(effect_path, [row, row])

        with self.assertRaisesRegex(CatalogError, "Duplicate dataName"):
            builder.build_all(self.templates, self.root / "bad", dlc_content_dir=self.dlc)

    def test_manifest_and_source_provenance_are_sha256_based(self):
        envelope = json.loads((self.output / "nation_claim_catalog.json").read_text(encoding="utf-8"))
        source_names = {source["name"] for source in envelope["sourceFiles"]}
        self.assertIn("base/TIGlobalConfig.json", source_names)
        self.assertIn("TerraInvicta_Data/Managed/Assembly-CSharp.dll", source_names)
        self.assertTrue(all(len(source["sha256"]) == 64 for source in envelope["sourceFiles"]))
        manifest = json.loads((self.output / "catalog_manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(
            manifest["catalogs"]["effect_catalog.json"]["sha256"],
            file_sha256(self.output / "effect_catalog.json"),
        )


if __name__ == "__main__":
    unittest.main()
