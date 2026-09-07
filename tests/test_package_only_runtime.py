from __future__ import annotations

from contextlib import ExitStack, redirect_stdout
from io import StringIO
import gzip
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import ti_save_parser as ti
import ti_parser_core as core


def ref(state_id: int) -> dict[str, int]:
    return {"value": state_id}


def state(state_id: int, value: dict) -> dict:
    return {"Key": ref(state_id), "Value": {"ID": ref(state_id), **value}}


class PackageOnlyRuntimeTests(unittest.TestCase):
    def _base_gamestates(self, scenario: str = "ModernScenario") -> dict[str, list[dict]]:
        return {
                "TITimeState": [
                    state(
                        1,
                        {
                            "scenarioMetaTemplateName": scenario,
                            "currentDateTime": {"year": 2035, "month": 1, "day": 10},
                        },
                    )
                ],
                "TIFactionState": [
                    state(
                        2,
                        {
                            "templateName": "ResistCouncil",
                            "displayName": "Resistance",
                            "isHumanPlayer": True,
                            "player": ref(3),
                            "resources": {},
                            "baseIncomes_year": {"Research": 365},
                            "councilors": [],
                            "controlPoints": [],
                            "habitats": [],
                            "fleets": [],
                            "researchWeights": [0, 0, 0, 0, 0, 0],
                            "currentProjectProgress": [],
                            "availableProjectNames": [],
                            "finishedProjectNames": [],
                            "missionControlUsage": 0,
                        },
                    )
                ],
                "TIPlayerState": [state(3, {"faction": ref(2), "isAI": False})],
                "TIEffectsState": [state(4, {"effects": []})],
                "TIGlobalResearchState": [state(5, {"techProgress": [], "finishedTechsNames": []})],
                "TIGlobalValuesState": [state(6, {})],
        }

    def _write_save(self, root: Path, name: str, gamestates: dict[str, list[dict]]) -> Path:
        path = root / f"{name}.gz"
        data = {"currentID": {"value": 1000}, "gamestates": gamestates}
        with gzip.open(path, "wt", encoding="utf-8") as handle:
            json.dump(data, handle)
        return path

    def _save(self, root: Path, scenario: str = "ModernScenario") -> Path:
        return self._write_save(root, "base", self._base_gamestates(scenario))

    @staticmethod
    def _value(gamestates: dict[str, list[dict]], type_name: str, state_id: int) -> dict:
        return next(row["Value"] for row in gamestates[type_name] if row["Key"] == ref(state_id))

    def _research_save(self, root: Path) -> Path:
        gamestates = self._base_gamestates()
        faction = self._value(gamestates, "TIFactionState", 2)
        faction.update(
            {
                "researchWeights": [3, 3, 3, 1, 0, 0],
                "currentProjectProgress": [
                    {
                        "projectTemplateName": "Project_40mmAutocannon",
                        "slot": 3,
                        "accumulatedResearch": 25,
                    }
                ],
                "availableProjectNames": ["Project_40mmAutocannon"],
                "orgProjectSlotUnlocked": True,
            }
        )
        gamestates["TIGlobalResearchState"] = [
            state(
                5,
                {
                    "techProgress": [
                        {
                            "techTemplateName": "AdvancedChemicalRocketry",
                            "accumulatedResearch": 100,
                        }
                    ],
                    "finishedTechsNames": [],
                },
            )
        ]
        return self._write_save(root, "research", gamestates)

    def _org_save(self, root: Path) -> Path:
        gamestates = self._base_gamestates()
        faction = self._value(gamestates, "TIFactionState", 2)
        faction.update(
            {
                "councilors": [ref(20)],
                "availableOrgs": [ref(21)],
                "resources": {"Influence": 1000, "Money": 1000},
            }
        )
        gamestates["TICouncilorState"] = [
            state(
                20,
                {
                    "displayName": "Package Councilor",
                    "faction": ref(2),
                    "active": True,
                    "detained": False,
                    "attributes": {"Administration": 10, "Science": 5},
                    "traitTemplateNames": [],
                    "orgs": [],
                },
            )
        ]
        gamestates["TIOrgState"] = [
            state(
                21,
                {
                    "templateName": "AirForceResearchLaboratory",
                    "displayName": "Air Force Research Laboratory",
                    "tier": 2,
                    "science": 1,
                    "costInfluence": 100,
                },
            )
        ]
        return self._write_save(root, "org", gamestates)

    def _hab_save(self, root: Path) -> Path:
        gamestates = self._base_gamestates()
        faction = self._value(gamestates, "TIFactionState", 2)
        faction.update(
            {
                "habSectors": [ref(31)],
                "resources": {
                    "Money": 1000,
                    "Water": 1000,
                    "Volatiles": 1000,
                    "Metals": 1000,
                    "NobleMetals": 1000,
                    "Fissiles": 1000,
                },
                "finishedProjectNames": [
                    "Project_OutpostCore",
                    "Project_FissionPile",
                    "Project_SpaceDock",
                ],
            }
        )
        gamestates["TIHabState"] = [
            state(
                30,
                {
                    "templateName": "PackageHab",
                    "displayName": "Package Hab",
                    "faction": ref(2),
                    "habType": "Base",
                    "tier": 1,
                    "sectors": [ref(31)],
                    "anyCoreCompleted": True,
                },
            )
        ]
        gamestates["TISectorState"] = [
            state(
                31,
                {
                    "faction": ref(2),
                    "hab": ref(30),
                    "sectorNum": 0,
                    "habModules": [ref(32), ref(33), ref(34)],
                },
            )
        ]
        gamestates["TIHabModuleState"] = [
            state(
                32,
                {
                    "templateName": "OutpostCore",
                    "sector": ref(31),
                    "constructionCompleted": True,
                    "powered": True,
                },
            ),
            state(
                33,
                {
                    "templateName": "FissionPile",
                    "sector": ref(31),
                    "constructionCompleted": False,
                    "powered": False,
                    "completionDate": "2035-01-20T00:00:00",
                },
            ),
            state(34, {"sector": ref(31), "constructionCompleted": False, "powered": False}),
        ]
        return self._write_save(root, "hab", gamestates)

    def _ship_save(self, root: Path) -> Path:
        gamestates = self._base_gamestates()
        faction = self._value(gamestates, "TIFactionState", 2)
        faction.update(
            {
                "finishedProjectNames": [
                    "Project_Warships",
                    "Project_Solid-FuelSpaceRockets",
                ],
                "shipDesigns": [
                    {
                        "dataName": "PackageTestShip",
                        "friendlyName": "Package Test Ship",
                        "hullName": "Gunship",
                        "driveName": "ApexSolidRocketx1",
                        "powerPlantName": "FuelCellI",
                        "radiatorName": "AluminumFin",
                        "propellantTanks": 1,
                        "moduleTemplateEntries": [{"moduleName": "Empty"}],
                        "hullWeaponTemplateEntries": [],
                        "noseWeaponTemplateEntries": [{"moduleName": "Empty"}],
                        "noseArmor": {},
                        "lateralArmor": {},
                        "tailArmor": {},
                    }
                ],
            }
        )
        return self._write_save(root, "ship", gamestates)

    def _claims_save(self, root: Path) -> Path:
        gamestates = self._base_gamestates()
        gamestates["TINationState"] = [
            state(
                40,
                {
                    "templateName": "CLA",
                    "displayName": "Claimant",
                    "democracy": 5,
                    "claims": [ref(42)],
                    "hostileClaims": [],
                },
            ),
            state(41, {"templateName": "TGT", "displayName": "Target", "democracy": 8}),
        ]
        gamestates["TIRegionState"] = [
            state(42, {"templateName": "ClaimRegion", "displayName": "Claim Region", "nation": ref(41)})
        ]
        return self._write_save(root, "claims", gamestates)

    def _ai_save(self, root: Path) -> Path:
        gamestates = self._base_gamestates()
        gamestates["TIFactionState"].append(
            state(
                50,
                {
                    "templateName": "AlienCouncil",
                    "displayName": "Aliens",
                    "player": ref(51),
                    "fleets": [ref(52)],
                    "habSectors": [],
                    "resources": {},
                    "nShipyardQueues": {},
                },
            )
        )
        gamestates["TIPlayerState"].append(state(51, {"faction": ref(50), "isAI": True}))
        gamestates["TISpaceFleetState"] = [
            state(52, {"templateName": "PackageFleet", "faction": ref(50), "ships": [ref(53)]})
        ]
        gamestates["TISpaceShipState"] = [state(53, {"templateName": "PackageShip", "fleet": ref(52)})]
        gamestates["FactionGoal_AttackWithFleet"] = [
            state(
                54,
                {
                    "faction": ref(50),
                    "assignedFleet": ref(52),
                    "pendingFleets": [],
                    "assignedDate": {"year": 2035, "month": 1, "day": 1},
                    "exists": True,
                    "archived": False,
                },
            )
        ]
        return self._write_save(root, "ai", gamestates)

    def _raw_loader_traps(self, message: str = "raw template access is forbidden") -> ExitStack:
        stack = ExitStack()
        error = RuntimeError(message)
        for module in (core, ti):
            for name in (
                "candidate_templates_dirs",
                "resolve_templates_dir",
                "resolve_scenario_templates",
                "load_named_templates",
                "load_trait_templates",
            ):
                if hasattr(module, name):
                    stack.enter_context(patch.object(module, name, side_effect=error))
        return stack

    def _run(self, save: Path, arguments: list[str]) -> dict:
        output = StringIO()
        with redirect_stdout(output):
            code = ti.main(["--save", str(save), *arguments, "--compact"])
        self.assertEqual(code, 0, output.getvalue())
        result = json.loads(output.getvalue())
        self.assertNotEqual(result.get("status"), "incomplete", output.getvalue())
        return result

    def test_summary_and_topbar_never_touch_raw_template_loaders(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            save = self._save(root)
            with self._raw_loader_traps():
                for arguments in (
                    ["--save", str(save), "--cache-dir", str(root / "cache"), "summary", "--compact"],
                    ["--save", str(save), "topbar", "ResistCouncil", "--compact"],
                ):
                    output = StringIO()
                    with redirect_stdout(output):
                        code = ti.main(arguments)
                    self.assertEqual(code, 0, output.getvalue())
                    self.assertNotEqual(json.loads(output.getvalue()).get("status"), "incomplete")

    def test_major_normal_cli_matrix_is_package_only_and_populated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base = self._save(root)
            research = self._research_save(root)
            org = self._org_save(root)
            hab = self._hab_save(root)
            ship = self._ship_save(root)
            claims = self._claims_save(root)
            ai_save = self._ai_save(root)

            with self._raw_loader_traps():
                summary = self._run(base, ["--cache-dir", str(root / "cache"), "summary"])
                self.assertEqual(summary["faction"]["template"], "ResistCouncil")

                topbar = self._run(base, ["topbar", "ResistCouncil"])
                self.assertIn("Research", topbar["resources"])

                research_result = self._run(research, ["research", "ResistCouncil"])
                self.assertGreater(research_result["daily"]["total"], 0)

                research_ui = self._run(research, ["research-ui", "ResistCouncil"])
                self.assertEqual(research_ui["globalResearch"][0]["template"], "AdvancedChemicalRocketry")

                research_plan = self._run(research, ["research-plan", "ResistCouncil", "--top", "1"])
                self.assertGreater(research_plan["globalResearchCandidates"]["count"], 0)
                self.assertEqual(research_plan["templateAvailability"]["source"], "packaged-runtime-catalog")

                org_plan = self._run(
                    org,
                    [
                        "org-plan",
                        "ResistCouncil",
                        "--top",
                        "1",
                        "--max-actions",
                        "1",
                        "--beam-width",
                        "1",
                    ],
                )
                self.assertEqual(org_plan["candidateSources"]["market"]["count"], 1)
                self.assertEqual(len(org_plan["councilors"]), 1)

                hab_ui = self._run(hab, ["hab-ui", "Package Hab"])
                self.assertEqual(hab_ui["modules"]["slots"]["empty"], 1)

                hab_plan = self._run(hab, ["hab-plan", "Package Hab", "--top", "1"])
                self.assertEqual(len(hab_plan["habs"]), 1)
                self.assertGreater(hab_plan["habs"][0]["candidateSummary"]["count"], 0)

                forecast = self._run(hab, ["topbar", "ResistCouncil", "--forecast-resource", "Money"])
                self.assertGreater(len(forecast["forecast"]["events"]), 0)

                ship_plan = self._run(
                    ship,
                    ["ship-plan", "ResistCouncil", "--top", "1", "--design", "Package Test Ship"],
                )
                self.assertTrue(ship_plan["selectedDesign"]["simulation"]["complete"])

                claim_result = self._run(claims, ["nation-claims", "CLA", "--diagnostics"])
                self.assertEqual(len(claim_result["claims"]), 1)
                self.assertIn("runtime", claim_result["calculationDiagnostics"])

                ai_result = self._run(ai_save, ["ai-fleet-diagnostics", "AlienCouncil", "--diagnostics"])
                self.assertEqual(ai_result["derived"]["factionCount"], 1)
                self.assertEqual(ai_result["derived"]["goalCount"], 1)

    def test_unsupported_scenario_is_structured_incomplete(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            save = self._save(Path(tmp), "UnsupportedScenario")
            output = StringIO()
            with redirect_stdout(output):
                code = ti.main(["--save", str(save), "topbar", "ResistCouncil", "--compact"])
            result = json.loads(output.getvalue())
            self.assertEqual(code, 2)
            self.assertEqual(result["status"], "incomplete")
            self.assertEqual(result["missingDependencies"][0]["kind"], "scenario")
            self.assertEqual(result["missingDependencies"][0]["scenario"], "UnsupportedScenario")

    def test_catalog_error_types_map_to_distinct_calculation_dependencies(self) -> None:
        indexed = ti.build_index(
            {
                "gamestates": {
                    "TITimeState": [state(1, {"scenarioMetaTemplateName": "ModernScenario"})],
                }
            }
        )
        cases = (
            (
                ti.UnsupportedCatalogScenarioError("ModernScenario", ["2003Scenario"]),
                "scenario",
                "ModernScenario",
            ),
            (ti.CatalogIntegrityError("manifest hash mismatch"), "catalog-integrity", "runtime bundle"),
        )
        for error, expected_kind, expected_name in cases:
            with self.subTest(error=type(error).__name__):
                with patch.object(ti, "load_runtime_catalogs", side_effect=error):
                    with self.assertRaises(ti.CalculationDependencyError) as caught:
                        ti.calculation_catalogs(indexed, "topbar")
                dependency = caught.exception.missing_dependencies[0]
                self.assertEqual(dependency["kind"], expected_kind)
                self.assertEqual(dependency["name"], expected_name)


if __name__ == "__main__":
    unittest.main()
