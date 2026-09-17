import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import ti_save_parser as ti
from ti_parser_catalogs import RuntimeCatalogs
from tests import test_package_only_runtime as fixtures


class ParserCliTests(unittest.TestCase):
    def test_topbar_reuses_catalogs_within_each_command_only(self):
        with tempfile.TemporaryDirectory() as directory:
            save = fixtures.PackageOnlyRuntimeTests()._save(Path(directory))
            with patch.object(RuntimeCatalogs, "load", wraps=RuntimeCatalogs.load) as loader:
                for invocation in (1, 2):
                    code, output, errors = self.run_cli(["--save", str(save), "topbar"])
                    self.assertEqual(code, 0, errors)
                    self.assertIn("resources", json.loads(output))
                    self.assertEqual(loader.call_count, invocation)

    def run_cli(self, args):
        output, errors = io.StringIO(), io.StringIO()
        with redirect_stdout(output), redirect_stderr(errors):
            code = ti.main(args)
        return code, output.getvalue(), errors.getvalue()

    def test_default_summary_matches_explicit_summary_and_honors_limit(self):
        snapshot = {
            "metadata": {},
            "factions": [{"id": 1, "template": "ResistCouncil", "player": {"isAI": False},
                          "controlledNations": list(range(25))}],
        }
        with (
            patch.object(ti, "resolve_save_path", return_value=Path("fixture.gz")),
            patch.object(ti, "load_or_build_snapshot", return_value=(snapshot, Path("cache.json"), True)),
        ):
            default = self.run_cli([])
            explicit = self.run_cli(["summary"])
            limited = self.run_cli(["summary", "--top-nations", "3"])
        self.assertEqual(default, explicit)
        self.assertEqual(default[0], 0, default)
        self.assertEqual(len(json.loads(default[1])["playerControlledNations"]), 20)
        self.assertEqual(json.loads(limited[1])["playerControlledNations"], [0, 1, 2])

    def test_verification_exit_status_reflects_complete_result(self):
        for status, expected in (("passed", 0), ("failed", 2), ("partial", 2)):
            with (
                self.subTest(status=status),
                patch.object(ti, "resolve_save_path", return_value=Path("fixture.gz")),
                patch.object(ti, "verify_catalogs", return_value={"status": status}),
            ):
                code, output, errors = self.run_cli([
                    "--templates-dir", "templates", "catalog-verify", "--scenario", "ModernScenario",
                ])
                self.assertEqual(code, expected)
                self.assertEqual(json.loads(output)["status"], status)
                self.assertEqual(errors, "")

    def test_verification_without_local_save_reports_partial_checks(self):
        with (
            patch.object(ti, "resolve_save_path", side_effect=FileNotFoundError("No saves")),
            patch.object(ti, "verify_catalogs", return_value={"status": "partial"}) as verify,
        ):
            code, output, _ = self.run_cli([
                "--templates-dir", "templates", "catalog-verify", "--scenario", "ModernScenario",
            ])
            self.assertEqual(code, 2)
            self.assertEqual(json.loads(output)["status"], "partial")
            self.assertIsNone(verify.call_args.kwargs["save_path"])
            verify.reset_mock()
            code, _, errors = self.run_cli([
                "--save", "missing.gz", "--templates-dir", "templates",
                "catalog-verify", "--scenario", "ModernScenario",
            ])
            self.assertEqual(code, 2)
            self.assertIn("No saves", errors)
            verify.assert_not_called()

    def test_missing_topbar_effect_is_structured_dependency(self):
        context = sorted(ti.TOPBAR_EFFECT_CONTEXTS)[0]
        with (
            patch.object(ti, "resolve_save_path", return_value=Path("fixture.gz")),
            patch.object(ti, "load_save", return_value={"gamestates": {}}),
            patch.object(ti, "calculation_catalogs", return_value=SimpleNamespace(traits={}, effects={})),
            patch.object(ti, "load_hab_module_catalog", return_value={}),
            patch.object(ti, "find_faction_state", return_value=(1, {})),
            patch.object(ti, "faction_effect_contexts", return_value={context: ["MissingEffect"]}),
        ):
            code, output, errors = self.run_cli(["topbar"])
        self.assertEqual(code, 2)
        self.assertEqual(errors, "")
        result = json.loads(output)
        self.assertEqual(result["status"], "incomplete")
        dependency = result["missingDependencies"][0]
        self.assertEqual(dependency["kind"], "effect")
        self.assertEqual(dependency["name"], "MissingEffect")
        self.assertEqual(dependency["context"], f"topbar.{context}")


if __name__ == "__main__":
    unittest.main()
