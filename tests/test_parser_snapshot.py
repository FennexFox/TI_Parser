import gzip
import json
import tempfile
import unittest
from pathlib import Path


import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import ti_parser_core as core
import ti_parser_snapshot as snapshot
import ti_save_parser as ti


class ParserSnapshotTests(unittest.TestCase):
    def test_faction_reference_helpers_keep_name_fallbacks(self):
        indexed = core.build_index(
            {
                "gamestates": {
                    "TIFactionState": [
                        {"Key": {"value": 1}, "Value": {"ID": {"value": 1}, "displayName": "Display Only"}},
                        {"Key": {"value": 2}, "Value": {"ID": {"value": 2}, "templateName": "TemplateOnly"}},
                    ]
                }
            }
        )

        self.assertEqual(ti.faction_key_from_ref(indexed, {"value": 1}), "Display Only")
        self.assertEqual(ti.faction_display_from_ref(indexed, {"value": 2}), "TemplateOnly")

    def _write_minimal_save(self, directory: Path) -> Path:
        payload = {
            "currentID": {"value": 42},
            "gamestates": {
                "TITimeState": [
                    {
                        "Key": {"value": 1},
                        "Value": {
                            "ID": {"value": 1},
                            "templateName": "TITimeState",
                            "masterMetaTemplateName": "TerraInvictaScenario",
                            "scenarioMetaTemplateName": "BrokenEarthScenario",
                            "daysInCampaign": 12,
                            "currentQuarterSinceStart": 3,
                            "currentDateTime": {"year": 2035, "month": 6, "day": 2},
                        },
                    }
                ],
                "TIMetadataState": [
                    {
                        "Key": {"value": 2},
                        "Value": {
                            "ID": {"value": 2},
                            "templateName": "TIMetadataState",
                            "playerFactionName": "Resistance",
                            "gameTimeString": "2035-06-02",
                        },
                    }
                ],
                "TIGlobalValuesState": [
                    {
                        "Key": {"value": 3},
                        "Value": {
                            "ID": {"value": 3},
                            "templateName": "TIGlobalValuesState",
                            "nuclearStrikes": 1,
                        },
                    }
                ],
                "TIFactionState": [
                    {
                        "Key": {"value": 4},
                        "Value": {
                            "ID": {"value": 4},
                            "templateName": "ResistCouncil",
                            "displayName": "Resistance",
                            "resources": {"Money": 10.0, "Research": 5.0},
                            "baseIncomes_year": {"Research": 12.0},
                            "controlPoints": [],
                            "councilors": [],
                            "habSectors": [],
                            "fleets": [],
                            "shipDesigns": [],
                            "finishedProjectNames": [],
                            "availableProjectNames": [],
                            "history_CPCapOverageByDay": [1, 2],
                            "history_MCCapOverageByDay": [3, 4],
                        },
                    }
                ],
            },
        }
        save_path = directory / "minimal.gz"
        with gzip.open(save_path, "wt", encoding="utf-8") as handle:
            json.dump(payload, handle)
        return save_path

    def test_snapshot_module_and_wrapper_share_cache_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            save_path = self._write_minimal_save(tmp_dir)
            data = core.load_save(save_path)

            direct = snapshot.build_snapshot(save_path, data, None, ti.SNAPSHOT_CONFIG)
            wrapped = ti.build_snapshot(save_path, data, None)

            self.assertEqual(wrapped, direct)
            self.assertEqual(wrapped["schemaVersion"], ti.SCHEMA_VERSION)
            self.assertEqual(wrapped["currentID"], 42)
            self.assertEqual(wrapped["time"]["daysInCampaign"], 12)
            self.assertEqual(wrapped["time"]["masterMetaTemplateName"], "TerraInvictaScenario")
            self.assertEqual(wrapped["time"]["scenarioMetaTemplateName"], "BrokenEarthScenario")
            self.assertEqual(wrapped["metadata"]["playerFactionName"], "Resistance")
            self.assertEqual(wrapped["global"]["nuclearStrikes"], 1)
            self.assertEqual(wrapped["factions"][0]["template"], "ResistCouncil")
            self.assertEqual(wrapped["factions"][0]["resources"]["Money"], 10.0)

            cache_dir = tmp_dir / ".ti_cache"
            first_snapshot, cache_path, cache_hit = ti.load_or_build_snapshot(save_path, cache_dir, None)
            second_snapshot, second_cache_path, second_hit = ti.load_or_build_snapshot(save_path, cache_dir, None)

            self.assertFalse(cache_hit)
            self.assertTrue(second_hit)
            self.assertEqual(first_snapshot, wrapped)
            self.assertEqual(second_snapshot, wrapped)
            self.assertEqual(cache_path, second_cache_path)
            self.assertEqual(cache_path.suffixes[-2:], [".snapshot", ".json"])
            self.assertEqual(first_snapshot["schemaVersion"], ti.SCHEMA_VERSION)


if __name__ == "__main__":
    unittest.main()
