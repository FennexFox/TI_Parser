import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import build_runtime_catalogs as builder
from ti_parser_catalogs import (
    CalculationDependencyError,
    CatalogError,
    CatalogIntegrityError,
    RuntimeCatalogs,
    UnsupportedCatalogScenarioError,
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
            broken / "TIDriveTemplate.json",
            [
                {
                    "dataName": "drives_Test",
                    "thrust_N": 250,
                    "weightedBuildMaterials": {"metals": 1, "nobleMetals": 2},
                }
            ],
        )
        write_json(broken / "TIGlobalConfig.json", {"scenarioTags": ["PostApoc"]})

    def test_loader_selects_exact_scenario_overlay_and_exposes_claim_config(self):
        modern = RuntimeCatalogs.load("ModernScenario", self.output)
        millennium = RuntimeCatalogs.load("2003Scenario", self.output)
        broken = RuntimeCatalogs.load("BrokenEarthScenario", self.output)

        self.assertEqual(modern.effects["Effect_Test"]["operation"], "Additive")
        self.assertEqual(millennium.effects["Effect_Test"]["operation"], "Multiplicative")
        self.assertEqual(millennium.effects["Effect_Test"]["contexts"], ["Research"])
        self.assertEqual(millennium.orgs["Org_Test"]["tier"], 2)
        self.assertIn("Trait_2003", millennium.traits)
        self.assertNotIn("unrelatedAsset", modern.effects["Effect_Test"])
        self.assertEqual(modern.ships["drives"]["drives_Test"]["thrust_N"], 100)
        self.assertEqual(broken.ships["drives"]["drives_Test"]["thrust_N"], 250)
        self.assertEqual(
            broken.ships["drives"]["drives_Test"]["weightedBuildMaterials"],
            {"metals": 1, "nobleMetals": 2},
        )
        self.assertTrue(broken.calculation_diagnostics()["catalogs"]["ship"]["overrideApplied"])
        self.assertFalse(modern.calculation_diagnostics()["catalogs"]["ship"]["overrideApplied"])
        self.assertEqual(
            modern.nation_claims["democracyDecreaseToMakeHostileClaim"],
            1.5,
        )
        self.assertIs(CalculationDependencyError, CoreCalculationDependencyError)

    def test_unsupported_scenario_does_not_fall_back(self):
        with self.assertRaisesRegex(UnsupportedCatalogScenarioError, "Unsupported scenario"):
            RuntimeCatalogs.load("UnknownScenario", self.output)

    def test_manifest_detects_catalog_file_corruption(self):
        path = self.output / "effect_catalog.json"
        path.write_text(path.read_text(encoding="utf-8") + " ", encoding="utf-8")

        with self.assertRaisesRegex(CatalogIntegrityError, "file sha256 mismatch"):
            RuntimeCatalogs.load("ModernScenario", self.output)

    def test_envelope_detects_payload_corruption_even_when_json_is_valid(self):
        path = self.output / "trait_catalog.json"
        envelope = json.loads(path.read_text(encoding="utf-8"))
        envelope["base"]["traits"]["Trait_Test"]["incomeMoney"] = 999

        with self.assertRaisesRegex(CatalogIntegrityError, "payload fingerprint mismatch"):
            validate_catalog_envelope(envelope, path=path)

    def test_missing_manifest_entry_is_fail_closed(self):
        manifest_path = self.output / "catalog_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        del manifest["catalogs"]["ship_catalog.json"]
        manifest["bundleFingerprint"] = value_fingerprint(manifest["catalogs"])
        write_json(manifest_path, manifest)

        with self.assertRaisesRegex(CatalogIntegrityError, "missing required entries"):
            RuntimeCatalogs.load("ModernScenario", self.output)

    def test_lf_normalized_copy_loads_every_supported_scenario(self):
        normalized = self.root / "normalized"
        shutil.copytree(self.output, normalized)
        for path in normalized.glob("*.json"):
            content = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
            path.write_bytes(content)
            self.assertNotIn(b"\r", content)
            self.assertTrue(content.endswith(b"\n"))

        envelope = json.loads((normalized / "effect_catalog.json").read_text(encoding="utf-8"))
        for scenario in envelope["supportedScenarios"]:
            loaded = RuntimeCatalogs.load(scenario, normalized)
            self.assertEqual(loaded.scenario, scenario)

    def test_generated_manifest_hashes_the_actual_lf_bytes(self):
        manifest = json.loads((self.output / "catalog_manifest.json").read_text(encoding="utf-8"))
        for filename, entry in manifest["catalogs"].items():
            content = (self.output / filename).read_bytes()
            self.assertNotIn(b"\r", content)
            self.assertTrue(content.endswith(b"\n"))
            self.assertEqual(entry["sha256"], file_sha256(self.output / filename))

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

    def test_ship_override_is_recursive_minimal_and_tracks_overlay_source(self):
        envelope = json.loads((self.output / "ship_catalog.json").read_text(encoding="utf-8"))

        self.assertEqual(
            envelope["scenarioOverrides"]["BrokenEarthScenario"],
            {
                "drives": {
                    "drives_Test": {
                        "thrust_N": 250,
                        "weightedBuildMaterials": {"nobleMetals": 2},
                    }
                }
            },
        )
        self.assertIn(
            "BrokenEarthScenario/TIDriveTemplate.json",
            {source["name"] for source in envelope["sourceFiles"]},
        )

    def test_generator_rejects_duplicate_ship_rows_in_scenario_overlay(self):
        overlay_path = (
            self.dlc / builder.SCENARIO_DIRECTORIES["BrokenEarthScenario"] / "TIDriveTemplate.json"
        )
        row = json.loads(overlay_path.read_text(encoding="utf-8"))[0]
        write_json(overlay_path, [row, row])

        with self.assertRaisesRegex(CatalogError, "Duplicate dataName"):
            builder.build_all(self.templates, self.root / "duplicate-ship", dlc_content_dir=self.dlc)

    def test_generator_rejects_cross_family_weapon_collision_in_scenario_overlay(self):
        overlay_path = (
            self.dlc / builder.SCENARIO_DIRECTORIES["2003Scenario"] / "TIMissileTemplate.json"
        )
        write_json(
            overlay_path,
            [{"dataName": "guns_Test", "friendlyName": "Collision", "mount": "OneHull"}],
        )

        with self.assertRaisesRegex(CatalogError, "2003Scenario"):
            builder.build_all(self.templates, self.root / "weapon-collision", dlc_content_dir=self.dlc)

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
