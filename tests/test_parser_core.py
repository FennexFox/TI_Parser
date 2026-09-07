import gzip
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import ti_parser_core as core
import ti_save_parser as ti


class ParserCoreTests(unittest.TestCase):
    def test_campaign_code_strips_2003_and_broken_earth_prefixes(self):
        self.assertEqual(core.campaign_code("2003_USA"), "USA")
        self.assertEqual(core.campaign_code("1962_WES"), "WES")

    def test_template_loader_caches_until_file_fingerprint_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            templates_dir = Path(tmp)
            template_path = templates_dir / "TITestTemplate.json"
            template_path.write_text('[{"dataName": "Alpha", "value": 1}]', encoding="utf-8")
            core._load_named_templates_cached.cache_clear()

            first = core.load_named_templates(templates_dir, template_path.name)
            second = core.load_named_templates(templates_dir, template_path.name)
            self.assertIs(first, second)

            old_stat = template_path.stat()
            template_path.write_text('[{"dataName": "Beta", "value": 22}]', encoding="utf-8")
            os.utime(template_path, ns=(old_stat.st_atime_ns, old_stat.st_mtime_ns + 1_000_000))

            third = core.load_named_templates(templates_dir, template_path.name)

        self.assertEqual(list(third), ["Beta"])
        self.assertIsNot(first, third)

    def test_scenario_template_sources_overlay_only_the_selected_scenario(self):
        with tempfile.TemporaryDirectory() as tmp:
            game_root = Path(tmp) / "Terra Invicta"
            base_dir = game_root / "TerraInvicta_Data" / "StreamingAssets" / "Templates"
            scenario_2003 = game_root / core.SCENARIO_DLC_TEMPLATE_HINTS["2003Scenario"]
            broken_earth = game_root / core.SCENARIO_DLC_TEMPLATE_HINTS["BrokenEarthScenario"]
            for directory in (base_dir, scenario_2003, broken_earth):
                directory.mkdir(parents=True)
            (base_dir / "TITechTemplate.json").write_text(
                '[{"dataName":"MissionToSpace","researchCost":250}]', encoding="utf-8"
            )
            (scenario_2003 / "TITechTemplate.json").write_text(
                '[{"dataName":"MissionToSpace","researchCost":1000},'
                '{"dataName":"MillenniumOnly","researchCost":10}]',
                encoding="utf-8",
            )
            (broken_earth / "TITechTemplate.json").write_text(
                '[{"dataName":"MissionToSpace","researchCost":2000},'
                '{"dataName":"PostApocOnly","researchCost":20}]',
                encoding="utf-8",
            )
            indexed = core.build_index(
                {
                    "gamestates": {
                        "TITimeState": [
                            {"Value": {"scenarioMetaTemplateName": "2003Scenario"}}
                        ]
                    }
                }
            )

            sources = core.scenario_template_sources(indexed, base_dir)
            templates = core.load_named_templates(sources, "TITechTemplate.json")

        self.assertEqual(sources, (base_dir, scenario_2003))
        self.assertEqual(templates["MissionToSpace"]["researchCost"], 1000)
        self.assertIn("MillenniumOnly", templates)
        self.assertNotIn("PostApocOnly", templates)

    def test_unknown_scenario_can_be_discovered_from_dlc_meta_template(self):
        with tempfile.TemporaryDirectory() as tmp:
            game_root = Path(tmp) / "Terra Invicta"
            base_dir = game_root / "TerraInvicta_Data" / "StreamingAssets" / "Templates"
            future_dir = game_root / "DLC_Content" / "FutureDLC" / "FutureScenario" / "Templates"
            base_dir.mkdir(parents=True)
            future_dir.mkdir(parents=True)
            (future_dir / "TIMetaTemplate.json").write_text(
                '[{"dataName":"FutureScenario"}]', encoding="utf-8"
            )
            indexed = core.build_index(
                {"gamestates": {"TITimeState": [{"Value": {"scenarioMetaTemplateName": "FutureScenario"}}]}}
            )

            sources = core.scenario_template_sources(indexed, base_dir)

        self.assertEqual(sources, (base_dir, future_dir))

    def test_save_parser_reexports_core_api(self):
        self.assertIs(ti.IndexedState, core.IndexedState)
        self.assertIs(ti.build_index, core.build_index)
        self.assertIs(ti.load_named_templates, core.load_named_templates)
        self.assertIs(ti.resolve_save_path, core.resolve_save_path)

    def test_raw_cli_reads_minimal_compressed_save(self):
        with tempfile.TemporaryDirectory() as tmp:
            save_path = Path(tmp) / "minimal.gz"
            payload = {
                "gamestates": {
                    "TIFactionState": [
                        {
                            "Key": {"value": 1},
                            "Value": {
                                "ID": {"value": 1},
                                "templateName": "ResistCouncil",
                                "displayName": "Resistance",
                            },
                        }
                    ]
                }
            }
            with gzip.open(save_path, "wt", encoding="utf-8") as handle:
                json.dump(payload, handle)

            stdout = StringIO()
            with redirect_stdout(stdout):
                exit_code = ti.main(
                    [
                        "--save",
                        str(save_path),
                        "raw",
                        "--type",
                        "TIFactionState",
                        "--compact",
                    ]
                )

        self.assertEqual(exit_code, 0)
        self.assertEqual(
            json.loads(stdout.getvalue()),
            [{"id": 1, "value": payload["gamestates"]["TIFactionState"][0]["Value"]}],
        )

    def test_raw_cli_script_entrypoint_reads_minimal_compressed_save(self):
        with tempfile.TemporaryDirectory() as tmp:
            save_path = Path(tmp) / "minimal.gz"
            payload = {
                "gamestates": {
                    "TIFactionState": [
                        {
                            "Key": {"value": 1},
                            "Value": {"ID": {"value": 1}, "templateName": "ResistCouncil"},
                        }
                    ]
                }
            }
            with gzip.open(save_path, "wt", encoding="utf-8") as handle:
                json.dump(payload, handle)

            completed = subprocess.run(
                [
                    sys.executable,
                    str(Path(__file__).resolve().parents[1] / "tools" / "ti_save_parser.py"),
                    "--save",
                    str(save_path),
                    "raw",
                    "--type",
                    "TIFactionState",
                    "--compact",
                ],
                check=True,
                capture_output=True,
                stdin=subprocess.DEVNULL,
                text=True,
            )

        self.assertEqual(json.loads(completed.stdout), [{"id": 1, "value": payload["gamestates"]["TIFactionState"][0]["Value"]}])


if __name__ == "__main__":
    unittest.main()
