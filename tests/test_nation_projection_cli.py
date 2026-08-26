import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import ti_parser_cli
import ti_save_parser


class NationProjectionCliTests(unittest.TestCase):
    def test_cli_parser_accepts_projection_contract(self):
        args = ti_parser_cli.build_parser(ti_save_parser).parse_args([
            "nation-projection", "KOR", "--days", "365", "--plan-file", "plans.json",
            "--checkpoints", "30,90", "--faction", "ResistCouncil", "--details", "--diagnostics",
        ])
        self.assertEqual(args.command, "nation-projection")
        self.assertEqual(args.days, 365)
        self.assertEqual(args.checkpoints, "30,90")
        self.assertTrue(args.details)
        self.assertTrue(args.diagnostics)

    def test_cli_dispatch_maps_projection_to_raw_save_command(self):
        self.assertEqual(ti_parser_cli.RAW_COMMANDS["nation-projection"], "command_nation_projection")


if __name__ == "__main__":
    unittest.main()
