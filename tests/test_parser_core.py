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
