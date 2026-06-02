import json
import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import build_module_catalog as mc
import build_research_catalog as rc
import catalog_utils as cu


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class CatalogGeneratorTests(unittest.TestCase):
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
                    }
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

            self.assertEqual(catalog["schemaVersion"], 1)
            self.assertEqual(catalog["source"]["techTemplate"]["file"], "TITechTemplate.json")
            self.assertEqual(catalog["source"]["projectTemplate"]["file"], "TIProjectTemplate.json")
            self.assertEqual(catalog["counts"]["total"], 3)
            self.assertEqual(catalog["counts"]["byKind"], {"tech": 2, "project": 1})
            self.assertEqual(catalog["counts"]["edges"], 3)
            self.assertEqual(catalog["unknownPrerequisites"], [])

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


if __name__ == "__main__":
    unittest.main()
