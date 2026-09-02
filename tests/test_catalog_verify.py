from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import build_research_catalog as research_builder
import build_runtime_catalogs as runtime_builder
import ti_parser_verify as verifier
from ti_parser_catalogs import file_sha256, value_fingerprint


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


class CatalogVerifyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.game = self.root / "Terra Invicta"
        self.templates = self.game / "TerraInvicta_Data" / "StreamingAssets" / "Templates"
        self.data = self.root / "data"
        self._write_raw_fixture()
        self._generate_packaged()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _write_raw_fixture(self) -> None:
        write_json(
            self.templates / "TIMetaTemplate.json",
            [
                {
                    "dataName": "ModernScenario",
                    "isNewCampaignOption": True,
                    "newCampaignOptionCategory": "Scenario",
                }
            ],
        )
        write_json(
            self.templates / "TIEffectTemplate.json",
            [
                {
                    "dataName": "Effect_Test",
                    "operation": "Additive",
                    "value": 2.0,
                    "contexts": ["Research"],
                }
            ],
        )
        write_json(
            self.templates / "TITraitTemplate.json",
            [{"dataName": "Trait_Test", "friendlyName": "Trait", "incomeResearch": 1.0}],
        )
        write_json(
            self.templates / "TIOrgTemplate.json",
            [{"dataName": "Org_Test", "friendlyName": "Org", "orgType": "Commercial", "tier": 1}],
        )
        write_json(
            self.templates / "TIGlobalConfig.json",
            {"dataName": "globalConfig", "democracyDecreaseToMakeHostileClaim": 1.5},
        )
        write_json(
            self.templates / "TIMissionTemplate.json",
            [{
                "dataName": "Advise",
                "persistentEffect": True,
                "resolutionOrder": 0,
                "resolutionMethod": {"$type": "TIMissionResolution_Automatic"},
                "movementRule": "MoveToTarget",
                "cost": {"$type": "TIMissionCost_Flat", "resourceType": "Influence", "value": 10},
            }],
        )
        write_json(
            self.templates / "TITimeEventTemplate.json",
            [{"dataName": "CouncilorMissionUpdate", "eventType": "Semimonthly", "repeatChanges": []}],
        )
        write_json(
            self.templates / "TINationTemplate.json",
            [{"dataName": "Nation_Test", "popGrowthModifier": 0.0}],
        )
        write_json(
            self.templates / "TIRegionTemplate.json",
            [
                {
                    "dataName": "Region_Test",
                    "mapRegionName": "map_Region_Test",
                    "annualPopGrowthModifier": 0.5,
                    "environment": "Standard",
                    "mineCapable": False,
                    "oilCapable": False,
                }
            ],
        )
        write_json(
            self.templates / "TIMapRegionTemplate.json",
            [{"dataName": "map_Region_Test", "latitude": 1.0, "longitude": 2.0}],
        )
        write_json(
            self.templates / "TIStartTimeTemplate.json",
            [{"dataName": "Start_Test", "populationRegressionPeriod_years": 20.0}],
        )
        write_json(
            self.templates / "TIBilateralTemplate.json",
            [{"dataName": "Adj_Test", "relationType": "PhysicalAdjacency", "region1": "map_Region_Test", "region2": "map_Region_Test"}],
        )
        for collection, (filename, _kind, _fields) in runtime_builder.SHIP_COLLECTIONS.items():
            row = {
                "dataName": f"{collection}_Test",
                "friendlyName": collection,
                "requiredProjectName": None,
                "weightedBuildMaterials": {"metals": 1.0},
            }
            if collection == "hulls":
                row.update({"mass_tons": 10.0, "length_m": 10.0, "width_m": 4.0})
            elif collection == "drives":
                row.update({"thrust_N": 100.0, "EV_kps": 10.0, "efficiency": 0.5})
            elif collection == "powerPlants":
                row.update({"maxOutput_GW": 10.0, "powerPlantClass": "Any_General"})
            write_json(self.templates / filename, [row])

        write_json(
            self.templates / "TITechTemplate.json",
            [
                {
                    "dataName": "Tech_Test",
                    "friendlyName": "Tech Test",
                    "techCategory": "Energy",
                    "researchCost": 100.0,
                    "prereqs": [],
                    "effects": [],
                }
            ],
        )
        write_json(
            self.templates / "TIProjectTemplate.json",
            [
                {
                    "dataName": "Project_Test",
                    "friendlyName": "Project Test",
                    "techCategory": "Energy",
                    "researchCost": 50.0,
                    "prereqs": ["Tech_Test"],
                    "effects": [],
                }
            ],
        )

    def _generate_packaged(self) -> None:
        runtime_builder.build_all(self.templates, self.data)
        research = research_builder.build_catalog(self.templates, [])
        research_path = self.data / "research_catalog.json"
        write_json(research_path, research)
        manifest_path = self.data / "catalog_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["catalogs"]["research_catalog.json"] = {
            "sha256": file_sha256(research_path),
            "schemaVersion": research["schemaVersion"],
            "payloadFingerprint": research["payloadFingerprint"],
        }
        manifest["bundleFingerprint"] = value_fingerprint(manifest["catalogs"])
        write_json(manifest_path, manifest)

    @staticmethod
    def _check(result: dict, name: str) -> dict:
        return next(check for check in result["checks"] if check["name"] == name)

    def test_verifies_manifest_core_rows_research_hashes_and_reports_calculation_gaps(self) -> None:
        result = verifier.verify_catalogs(self.templates, "ModernScenario", self.data)

        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["tolerance"], {"relTol": 1e-9, "absTol": 1e-6})
        self.assertEqual(self._check(result, "runtime-manifest")["status"], "passed")
        for domain in ("effect", "trait", "org", "ship", "research"):
            check = self._check(result, f"{domain}-catalog-parity")
            self.assertEqual(check["status"], "passed", check)
            self.assertTrue(check["payloadMatch"])
            self.assertTrue(check["sourceHashes"]["match"])
            self.assertGreater(check["rowsCompared"], 0)
        self.assertEqual(self._check(result, "mercury-solar")["status"], "unavailable")
        self.assertEqual(self._check(result, "saved-design-simulation")["status"], "unavailable")
        self.assertEqual(result["summary"]["failed"], 0)
        self.assertEqual(result["summary"]["unavailable"], 6)

    def test_scenario_override_is_selected_and_reported(self) -> None:
        scenario_dir = (
            self.game / "DLC_Content" / runtime_builder.SCENARIO_DIRECTORIES["2003Scenario"]
        )
        write_json(
            scenario_dir / "TIMetaTemplate.json",
            [
                {
                    "dataName": "2003Scenario",
                    "isNewCampaignOption": True,
                    "newCampaignOptionCategory": "Scenario",
                }
            ],
        )
        write_json(
            scenario_dir / "TIEffectTemplate.json",
            [{"dataName": "Effect_Test", "operation": "Multiplicative", "value": 3.0}],
        )
        self._generate_packaged()

        result = verifier.verify_catalogs(self.templates, "2003Scenario", self.data)

        check = self._check(result, "effect-catalog-parity")
        self.assertEqual(check["status"], "passed", check)
        self.assertTrue(check["scenarioOverrideApplied"])
        self.assertTrue(check["rawScenarioOverrideApplied"])

    def test_changed_raw_source_fails_payload_and_source_hash_parity(self) -> None:
        effect_path = self.templates / "TIEffectTemplate.json"
        raw = json.loads(effect_path.read_text(encoding="utf-8"))
        raw[0]["value"] = 9.0
        write_json(effect_path, raw)

        result = verifier.verify_catalogs(self.templates, "ModernScenario", self.data)

        self.assertEqual(result["status"], "failed")
        check = self._check(result, "effect-catalog-parity")
        self.assertEqual(check["status"], "failed")
        self.assertFalse(check["payloadMatch"])
        self.assertFalse(check["sourceHashes"]["match"])
        self.assertTrue(any(row["name"] == "base/TIEffectTemplate.json" for row in check["sourceHashes"]["mismatched"]))

    def test_manifest_corruption_is_structured_failure(self) -> None:
        effect_path = self.data / "effect_catalog.json"
        effect_path.write_text(effect_path.read_text(encoding="utf-8") + " ", encoding="utf-8")

        result = verifier.verify_catalogs(self.templates, "ModernScenario", self.data)

        self.assertEqual(result["status"], "failed")
        self.assertEqual(self._check(result, "runtime-manifest")["status"], "failed")
        self.assertEqual(self._check(result, "effect-catalog-parity")["status"], "unavailable")

    def test_numeric_comparison_uses_required_tolerance(self) -> None:
        self.assertEqual(verifier._compare_values({"value": 1.0}, {"value": 1.0 + 5e-7}), [])
        mismatches = verifier._compare_values({"value": 1.0}, {"value": 1.0 + 5e-5})
        self.assertEqual(mismatches[0]["reason"], "numeric mismatch")


if __name__ == "__main__":
    unittest.main()
