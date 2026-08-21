from __future__ import annotations

from contextlib import redirect_stdout
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


def ref(state_id: int) -> dict[str, int]:
    return {"value": state_id}


def state(state_id: int, value: dict) -> dict:
    return {"Key": ref(state_id), "Value": {"ID": ref(state_id), **value}}


class PackageOnlyRuntimeTests(unittest.TestCase):
    def _save(self, root: Path, scenario: str = "ModernScenario") -> Path:
        path = root / "synthetic.gz"
        data = {
            "currentID": {"value": 20},
            "gamestates": {
                "TITimeState": [state(1, {"scenarioMetaTemplateName": scenario})],
                "TIFactionState": [
                    state(
                        2,
                        {
                            "templateName": "ResistCouncil",
                            "displayName": "Resistance",
                            "isHumanPlayer": True,
                            "player": ref(3),
                            "resources": {},
                            "baseIncomes_year": {},
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
            },
        }
        with gzip.open(path, "wt", encoding="utf-8") as handle:
            json.dump(data, handle)
        return path

    def test_summary_and_topbar_never_touch_raw_template_loaders(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            save = self._save(root)
            trap = RuntimeError("raw template access is forbidden")
            with (
                patch.object(ti, "resolve_templates_dir", side_effect=trap),
                patch.object(ti, "resolve_scenario_templates", side_effect=trap),
                patch.object(ti, "load_named_templates", side_effect=trap),
                patch.object(ti, "load_trait_templates", side_effect=trap),
            ):
                for arguments in (
                    ["--save", str(save), "--cache-dir", str(root / "cache"), "summary", "--compact"],
                    ["--save", str(save), "topbar", "ResistCouncil", "--compact"],
                ):
                    output = StringIO()
                    with redirect_stdout(output):
                        code = ti.main(arguments)
                    self.assertEqual(code, 0, output.getvalue())
                    self.assertNotEqual(json.loads(output.getvalue()).get("status"), "incomplete")

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
