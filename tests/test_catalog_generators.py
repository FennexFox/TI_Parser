import json
import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import build_module_catalog as mc
import build_location_catalog as lc
import build_research_catalog as rc
import catalog_utils as cu
import ti_parser_catalogs as runtime_catalogs


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class CatalogGeneratorTests(unittest.TestCase):
    def test_catalog_writers_emit_utf8_lf_with_one_trailing_newline(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            json_path = root / "catalog.json"
            text_path = root / "catalog.md"

            cu.write_json_output(json_path, {"label": "한글", "value": 1})
            cu.write_text_output(text_path, "first\r\nsecond\r\n\r\n")

            json_bytes = json_path.read_bytes()
            text_bytes = text_path.read_bytes()
            self.assertEqual(json_bytes.decode("utf-8"), '{\n  "label": "한글",\n  "value": 1\n}\n')
            self.assertEqual(text_bytes, b"first\nsecond\n")
            self.assertNotIn(b"\r", json_bytes + text_bytes)

    def test_location_catalog_normalizes_body_navigable_and_orbit_without_zero_filling(self):
        with tempfile.TemporaryDirectory() as tmp:
            templates_dir = Path(tmp) / "Templates"
            write_json(
                templates_dir / "TISpaceBodyTemplate.json",
                [
                    {
                        "dataName": "Mars",
                        "friendlyName": "Mars",
                        "barycenterName": "Sol",
                        "objectType": "Planet",
                        "atmosphere": "Thin",
                        "semiMajorAxis_AU": 1.523679,
                        "equatorialRadius_km": 3396.2,
                        "mass_kg": 6.4171e23,
                        "oblateness": 0.00648,
                        "rotationPeriod_strHours": "24.6230",
                        "irradiatedMultiplier": 1,
                        "maxHabSize": 4,
                    },
                    {
                        "dataName": "Mercury",
                        "friendlyName": "Mercury",
                        "barycenterName": "Sol",
                        "objectType": "Planet",
                        "atmosphere": "Trace",
                        "semiMajorAxis_AU": 0.387099,
                        "equatorialRadius_km": 2493.7,
                        "mass_kg": 3.3011e23,
                        "oblateness": 0.0,
                        "rotationPeriod_strHours": "1407.6",
                        "irradiatedMultiplier": 2,
                        "maxHabSize": 4,
                    }
                ],
            )
            write_json(
                templates_dir / "TINavigableTemplate.json",
                [
                    {
                        "dataName": "SunMarsL1",
                        "lagrangeValue": "L1",
                        "relatedObject": "Mars",
                        "orbits": ["SunMarsL1Orbit"],
                        "maxHabSize": 3,
                    }
                ],
            )
            write_json(
                templates_dir / "TIOrbitTemplate.json",
                [
                    {
                        "dataName": "LowMercuryOrbit",
                        "barycenterName": "Mercury",
                        "radialOrbit": True,
                        "synch": False,
                        "irradiatedMultiplier": 2.0,
                    },
                    {
                        "dataName": "SunMarsL1Orbit",
                        "barycenterName": "SunMarsL1",
                        "semiMajorAxis_km": 3500,
                        "irradiatedMultiplier": 1,
                    },
                ],
            )

            catalog = lc.build_catalog(templates_dir)

            self.assertEqual(catalog["schemaVersion"], 2)
            self.assertEqual(catalog["source"]["spaceBodyTemplate"]["file"], "TISpaceBodyTemplate.json")
            self.assertEqual(catalog["source"]["navigableTemplate"]["file"], "TINavigableTemplate.json")
            self.assertEqual(catalog["source"]["orbitTemplate"]["file"], "TIOrbitTemplate.json")
            self.assertEqual(len(catalog["source"]["spaceBodyTemplate"]["sha256"]), 64)
            self.assertEqual(catalog["counts"], {"spaceBodies": 2, "navigables": 1, "orbits": 2})
            self.assertEqual(catalog["byDataName"]["spaceBodies"], {"Mars": 0, "Mercury": 1})
            self.assertEqual(catalog["byDataName"]["navigables"], {"SunMarsL1": 0})
            self.assertEqual(
                catalog["byDataName"]["orbits"],
                {"LowMercuryOrbit": 0, "SunMarsL1Orbit": 1},
            )
            body = catalog["spaceBodies"][catalog["byDataName"]["spaceBodies"]["Mercury"]]
            navigable = catalog["navigables"][0]
            orbit = catalog["orbits"][0]
            self.assertEqual(body["mass_kg"], 3.3011e23)
            self.assertEqual(body["oblateness"], 0)
            self.assertEqual(body["meanRadius_km"], 2493.7)
            self.assertEqual(body["maxRadius_km"], 2493.7)
            self.assertEqual(
                navigable,
                {
                    "dataName": "SunMarsL1",
                    "lagrangeValue": "L1",
                    "relatedObject": "Mars",
                    "orbits": ["SunMarsL1Orbit"],
                    "maxHabSize": 3,
                    "locationKind": "LagrangePoint",
                },
            )
            self.assertTrue(orbit["radialOrbit"])
            self.assertFalse(orbit["synch"])
            self.assertEqual(orbit["irradiatedMultiplier"], 2)

    def test_module_catalog_build_and_markdown_use_localized_fixture(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            templates_dir = root / "Templates"
            localization_dir = root / "Localization"

            write_json(
                templates_dir / "TIHabModuleTemplate.json",
                [
                    {
                        "dataName": "Module_Alpha",
                        "friendlyName": "Alpha Module",
                        "tier": 2,
                        "habType": "Any",
                        "buildTime_Days": 12.5,
                        "baseMass_tons": 3.25,
                        "weightedBuildMaterials": {
                            "money": 0,
                            "influence": 0,
                            "ops": 0,
                            "boost": 0,
                            "water": 0.2,
                            "volatiles": 0.4,
                            "metals": 0.6,
                            "nobleMetals": 0.1,
                            "fissiles": 0,
                            "antimatter": 0,
                            "exotics": 0,
                        },
                        "crew": 10,
                        "power": 5,
                        "missionControl": 1,
                        "controlPointCapacity": 0,
                        "constructionTimeModifier": 0.75,
                        "miningModifier": 0.0,
                        "incomeMoney_month": 1.5,
                        "incomeResearch_month": 2.5,
                        "incomeBoost_month": 0.5,
                        "supportMaterials_month": {
                            "money": 0.25,
                            "water": 0.1,
                            "volatiles": 0.2,
                        },
                        "specialRules": ["Farm", "MoneyIfNotBuilding"],
                        "specialRulesValue": 1.25,
                        "techBonuses": [
                            {"category": "Energy", "bonus": 1.5},
                            {"category": "Energy", "bonus": 0.5},
                        ],
                    },
                    {
                        "dataName": "Module_Disabled",
                        "friendlyName": "Disabled Module",
                        "tier": 9,
                        "habType": "Any",
                        "disable": True,
                    },
                ],
            )
            write_text(
                localization_dir / "kor" / "TIHabModuleTemplate.kor",
                "\n".join(
                    [
                        "# comments and blank lines are ignored",
                        "TIHabModuleTemplate.displayName.Module_Alpha=알파 모듈",
                        "TIHabModuleTemplate.description.Module_Alpha=테스트 설명",
                    ]
                ),
            )
            write_text(
                localization_dir / "en" / "TIHabModuleTemplate.en",
                "\n".join(
                    [
                        "TIHabModuleTemplate.displayName.Module_Alpha=Alpha Module",
                        "TIHabModuleTemplate.description.Module_Alpha=Test description",
                    ]
                ),
            )

            catalog = mc.build_catalog(templates_dir, cu.parse_languages("kor,en"))
            markdown = mc.build_markdown(catalog, "kor")

            self.assertEqual(catalog["schemaVersion"], 1)
            self.assertEqual(catalog["source"]["moduleTemplate"]["file"], "TIHabModuleTemplate.json")
            self.assertEqual(len(catalog["modules"]), 1)
            self.assertEqual(catalog["modules"][0]["dataName"], "Module_Alpha")
            self.assertEqual(catalog["modules"][0]["displayName"]["kor"], "알파 모듈")
            self.assertEqual(catalog["modules"][0]["displayName"]["en"], "Alpha Module")
            self.assertEqual(catalog["modules"][0]["bonuses"]["tech"], {"Energy": 2})
            self.assertEqual(catalog["byDataName"], {"Module_Alpha": 0})
            self.assertIn("알파 모듈", markdown)
            self.assertIn("Module count: `1` total, `1` normally buildable human modules.", markdown)
            self.assertIn("High-Value Recommendation Inputs", markdown)

    def test_research_catalog_build_and_markdown_use_localized_fixture(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            templates_dir = root / "Templates"
            localization_dir = root / "Localization"

            write_json(
                templates_dir / "TITechTemplate.json",
                [
                    {
                        "dataName": "Tech_Alpha",
                        "friendlyName": "Alpha Tech",
                        "techCategory": "Energy",
                        "researchCost": 100.5,
                        "prereqs": [],
                        "effects": ["Effect_Alpha"],
                    },
                    {
                        "dataName": "Tech_Beta",
                        "friendlyName": "Beta Tech",
                        "techCategory": "Energy",
                        "researchCost": 120,
                        "prereqs": ["Tech_Alpha"],
                        "effects": [],
                    },
                ],
            )
            write_json(
                templates_dir / "TIProjectTemplate.json",
                [
                    {
                        "dataName": "Project_Gamma",
                        "friendlyName": "Gamma Project",
                        "techCategory": "SpaceScience",
                        "researchCost": 250,
                        "prereqs": ["Tech_Alpha"],
                        "altPrereq0": "Tech_Beta",
                        "requiredObjectiveName": "InvestigateSignal",
                        "altRequiredObjectiveName": "ContactTheAliens",
                        "requiredMilestone": "AccessAlienTech",
                        "factionPrereq": ["ResistCouncil", "DestroyCouncil"],
                        "requiresNation": "KOR",
                        "oneTimeGlobally": True,
                        "repeatable": False,
                        "disable": False,
                        "factionAvailableChance": 0.25,
                        "initialUnlockChance": 0.5,
                        "deltaUnlockChance": 0.1,
                        "maxUnlockChance": 0.9,
                        "factionAlways": ["ResistCouncil"],
                        "orgGranted": "Org_Gamma",
                        "resourcesGranted": [{"resource": "Money", "amount": 5}],
                    },
                    {
                        "dataName": "Project_Disabled",
                        "friendlyName": "Disabled Project",
                        "techCategory": "Energy",
                        "researchCost": 1,
                        "disable": True,
                    },
                ],
            )
            write_text(
                localization_dir / "kor" / "TITechTemplate.kor",
                "\n".join(
                    [
                        "TITechTemplate.displayName.Tech_Alpha=알파 기술",
                        "TITechTemplate.displayName.Tech_Beta=베타 기술",
                    ]
                ),
            )
            write_text(
                localization_dir / "en" / "TITechTemplate.en",
                "\n".join(
                    [
                        "TITechTemplate.displayName.Tech_Alpha=Alpha Tech",
                        "TITechTemplate.displayName.Tech_Beta=Beta Tech",
                    ]
                ),
            )
            write_text(
                localization_dir / "kor" / "TIProjectTemplate.kor",
                "TIProjectTemplate.displayName.Project_Gamma=감마 프로젝트\n",
            )
            write_text(
                localization_dir / "en" / "TIProjectTemplate.en",
                "TIProjectTemplate.displayName.Project_Gamma=Gamma Project\n",
            )

            catalog = rc.build_catalog(templates_dir, cu.parse_languages("kor,en"))
            markdown = rc.build_markdown(catalog, "kor")

            self.assertEqual(catalog["schemaVersion"], 2)
            runtime_catalogs.validate_catalog_envelope(catalog)
            self.assertEqual(catalog["generator"], {"name": "build_research_catalog", "version": "2"})
            self.assertIn("2026Scenario", catalog["supportedScenarios"])
            self.assertIn("2003Scenario", catalog["supportedScenarios"])
            self.assertEqual(len(catalog["payloadFingerprint"]), 64)
            self.assertEqual(
                [item["name"] for item in catalog["sourceFiles"]],
                sorted(item["name"] for item in catalog["sourceFiles"]),
            )
            self.assertTrue(all(len(item["sha256"]) == 64 for item in catalog["sourceFiles"]))
            self.assertEqual(catalog["source"]["techTemplate"]["file"], "TITechTemplate.json")
            self.assertEqual(catalog["source"]["projectTemplate"]["file"], "TIProjectTemplate.json")
            self.assertEqual(len(catalog["source"]["techTemplate"]["sha256"]), 64)
            self.assertEqual(catalog["counts"]["total"], 3)
            self.assertEqual(catalog["counts"]["byKind"], {"tech": 2, "project": 1})
            self.assertEqual(catalog["counts"]["edges"], 3)
            self.assertEqual(catalog["unknownPrerequisites"], [])

            runtime_project = catalog["base"]["projects"]["Project_Gamma"]
            self.assertEqual(runtime_project["dataName"], "Project_Gamma")
            self.assertEqual(runtime_project["techCategory"], "SpaceScience")
            self.assertEqual(runtime_project["researchCost"], 250)
            self.assertEqual(runtime_project["resourcesGranted"], [{"resource": "Money", "value": 5}])
            self.assertEqual(runtime_project["AI_criticalTech"], False)
            self.assertIn("Project_Disabled", catalog["base"]["projects"])
            self.assertNotIn("Project_Disabled", catalog["byDataName"])
            self.assertTrue(catalog["base"]["projects"]["Project_Disabled"]["disable"])

            project = catalog["nodes"][catalog["byDataName"]["Project_Gamma"]]
            self.assertEqual(project["displayName"]["kor"], "감마 프로젝트")
            self.assertEqual(project["prerequisiteNodes"], ["Tech_Alpha", "Tech_Beta"])
            self.assertEqual(
                project["requirements"]["all"][0]["any"],
                [
                    {"node": "Tech_Alpha", "kind": "tech"},
                    {"node": "Tech_Beta", "kind": "tech"},
                ],
            )
            self.assertEqual(
                catalog["childrenByPrereq"],
                {"Tech_Alpha": ["Project_Gamma", "Tech_Beta"], "Tech_Beta": ["Project_Gamma"]},
            )
            self.assertIn("알파 기술", markdown)
            self.assertIn("감마 프로젝트", markdown)
            self.assertIn("Node count: `3` total, `2` global techs, `1` projects.", markdown)
            self.assertIn("Schema version `2`", markdown)

            first = json.dumps(catalog, ensure_ascii=False, sort_keys=True)
            (templates_dir / "TITechTemplate.json").touch()
            second = json.dumps(
                rc.build_catalog(templates_dir, cu.parse_languages("kor,en")),
                ensure_ascii=False,
                sort_keys=True,
            )
            self.assertEqual(first, second)

    def test_research_catalog_scenario_overlay_is_exact_and_base_is_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            templates_dir = root / "Templates"
            overlay_dir = root / "Overlay"
            write_json(
                templates_dir / "TITechTemplate.json",
                [
                    {
                        "dataName": "Tech_Alpha",
                        "friendlyName": "Alpha",
                        "techCategory": "Energy",
                        "researchCost": 100,
                    }
                ],
            )
            write_json(
                templates_dir / "TIProjectTemplate.json",
                [
                    {
                        "dataName": "Project_Alpha",
                        "friendlyName": "Project Alpha",
                        "techCategory": "Energy",
                        "researchCost": 200,
                    }
                ],
            )
            write_json(
                overlay_dir / "TITechTemplate.json",
                [
                    {
                        "dataName": "Tech_Alpha",
                        "researchCost": 125,
                    },
                    {
                        "dataName": "Tech_2003",
                        "friendlyName": "Millennium Tech",
                        "techCategory": "SocialScience",
                        "researchCost": 300,
                    },
                ],
            )

            catalog = rc.build_catalog(
                templates_dir,
                [],
                scenario_template_dirs={"2003Scenario": overlay_dir},
                supported_scenarios=["ModernScenario", "2003Scenario"],
            )

            standard = rc.select_runtime_payload(catalog, "ModernScenario")
            millennium = rc.select_runtime_payload(catalog, "2003Scenario")
            self.assertEqual(standard["techs"]["Tech_Alpha"]["researchCost"], 100)
            self.assertNotIn("Tech_2003", standard["techs"])
            self.assertEqual(millennium["techs"]["Tech_Alpha"]["researchCost"], 125)
            self.assertEqual(millennium["techs"]["Tech_2003"]["techCategory"], "SocialScience")
            with self.assertRaisesRegex(rc.ResearchCatalogError, "Unsupported research scenario"):
                rc.select_runtime_payload(catalog, "UnknownScenario")

    def test_research_catalog_rejects_duplicate_runtime_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            templates_dir = Path(tmp) / "Templates"
            write_json(
                templates_dir / "TITechTemplate.json",
                [
                    {"dataName": "Duplicate", "techCategory": "Energy", "researchCost": 1},
                    {"dataName": "Duplicate", "techCategory": "Energy", "researchCost": 2},
                ],
            )
            write_json(
                templates_dir / "TIProjectTemplate.json",
                [{"dataName": "Project_One", "techCategory": "Energy", "researchCost": 1}],
            )

            with self.assertRaisesRegex(rc.ResearchCatalogError, "Duplicate research dataName"):
                rc.build_catalog(templates_dir, [])


if __name__ == "__main__":
    unittest.main()
