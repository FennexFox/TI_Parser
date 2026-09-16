import gzip
import json
import shutil
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path


import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import ti_parser_core as core
import ti_parser_snapshot as snapshot
import ti_save_parser as ti
from ti_parser_catalogs import (
    CATALOG_MANIFEST,
    DEFAULT_CATALOG_FILES,
    RuntimeCatalogs,
    envelope_payload,
    file_sha256,
    value_fingerprint,
)


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

    def _write_minimal_save(self, directory: Path, *, with_academic_councilor: bool = False) -> Path:
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
        if with_academic_councilor:
            payload["gamestates"]["TICouncilorState"] = [
                {
                    "Key": {"value": 5},
                    "Value": {
                        "ID": {"value": 5},
                        "templateName": "TestCouncilor",
                        "traitTemplateNames": ["Academic"],
                        "attributes": {"Command": 5},
                        "orgs": [],
                    },
                }
            ]
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

    def _copy_runtime_catalog_bundle(self, directory: Path) -> Path:
        bundle = directory / "catalogs"
        bundle.mkdir()
        for filename in (CATALOG_MANIFEST, *DEFAULT_CATALOG_FILES):
            shutil.copy2(Path(__file__).resolve().parents[1] / "data" / filename, bundle / filename)
        return bundle

    def _update_manifest_for_trait_catalog(self, bundle: Path) -> None:
        trait_path = bundle / "trait_catalog.json"
        trait = json.loads(trait_path.read_text(encoding="utf-8"))
        trait["payloadFingerprint"] = value_fingerprint(envelope_payload(trait))
        trait_path.write_text(json.dumps(trait, ensure_ascii=False), encoding="utf-8")

        manifest_path = bundle / CATALOG_MANIFEST
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        entry = manifest["catalogs"]["trait_catalog.json"]
        entry["sha256"] = file_sha256(trait_path)
        entry["payloadFingerprint"] = trait["payloadFingerprint"]
        manifest["bundleFingerprint"] = value_fingerprint(manifest["catalogs"])
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")

    def test_validated_catalog_change_rebuilds_snapshot_with_fresh_attributes(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            save_path = self._write_minimal_save(tmp_dir, with_academic_councilor=True)
            cache_dir = tmp_dir / ".ti_cache"
            bundle = self._copy_runtime_catalog_bundle(tmp_dir)

            def load_temporary_bundle(scenario: str) -> RuntimeCatalogs:
                return RuntimeCatalogs.from_directory(bundle, scenario)

            with (
                patch.object(core, "DEFAULT_RUNTIME_CATALOG_DIR", bundle),
                patch.object(snapshot, "load_runtime_catalogs", side_effect=load_temporary_bundle),
            ):
                first, first_path, first_hit = ti.load_or_build_snapshot(save_path, cache_dir, None)
                self.assertFalse(first_hit)
                self.assertEqual(first["councilors"][0]["finalAttributes"]["Command"], 4)

                trait_path = bundle / "trait_catalog.json"
                trait = json.loads(trait_path.read_text(encoding="utf-8"))
                trait["base"]["traits"]["Academic"]["statMods"][0]["strValue"] = "3"
                trait_path.write_text(json.dumps(trait, ensure_ascii=False), encoding="utf-8")
                self._update_manifest_for_trait_catalog(bundle)

                second, second_path, second_hit = ti.load_or_build_snapshot(save_path, cache_dir, None)

            self.assertFalse(second_hit)
            self.assertNotEqual(first_path, second_path)
            self.assertEqual(second["councilors"][0]["finalAttributes"]["Command"], 8)

    def test_cache_hit_validates_its_catalog_without_loading_the_save(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            save_path = self._write_minimal_save(tmp_dir)
            cache_dir = tmp_dir / ".ti_cache"
            ti.load_or_build_snapshot(save_path, cache_dir, None)

            with (
                patch.object(snapshot, "load_runtime_catalogs", wraps=snapshot.load_runtime_catalogs) as loader,
                patch.object(snapshot, "load_save", side_effect=AssertionError("cache hit loaded save")),
            ):
                cached, _, cache_hit = ti.load_or_build_snapshot(save_path, cache_dir, None)

            self.assertTrue(cache_hit)
            self.assertEqual(cached["currentID"], 42)
            loader.assert_called_once_with("BrokenEarthScenario")

    def test_invalid_catalog_cannot_be_hidden_by_a_cache_hit(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            save_path = self._write_minimal_save(tmp_dir)
            cache_dir = tmp_dir / ".ti_cache"
            ti.load_or_build_snapshot(save_path, cache_dir, None)

            with patch.object(
                snapshot,
                "load_runtime_catalogs",
                side_effect=snapshot.CatalogIntegrityError("catalog is corrupt"),
            ):
                with self.assertRaisesRegex(core.CalculationDependencyError, "catalog is corrupt"):
                    ti.load_or_build_snapshot(save_path, cache_dir, None)

    def test_corrupt_catalog_fails_after_a_real_snapshot_is_cached(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            save_path = self._write_minimal_save(tmp_dir)
            cache_dir = tmp_dir / ".ti_cache"
            bundle = self._copy_runtime_catalog_bundle(tmp_dir)

            def load_temporary_bundle(scenario: str) -> RuntimeCatalogs:
                return RuntimeCatalogs.from_directory(bundle, scenario)

            with (
                patch.object(core, "DEFAULT_RUNTIME_CATALOG_DIR", bundle),
                patch.object(snapshot, "load_runtime_catalogs", side_effect=load_temporary_bundle),
            ):
                _, _, first_hit = ti.load_or_build_snapshot(save_path, cache_dir, None)
                self.assertFalse(first_hit)
                (bundle / "trait_catalog.json").write_bytes(b"{corrupt catalog")

                with self.assertRaisesRegex(core.CalculationDependencyError, "Catalog file sha256 mismatch"):
                    ti.load_or_build_snapshot(save_path, cache_dir, None)

    def test_malformed_or_invalid_utf8_or_non_object_cache_rebuilds(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            save_path = self._write_minimal_save(tmp_dir)
            cache_dir = tmp_dir / ".ti_cache"
            _, cache_path, _ = ti.load_or_build_snapshot(save_path, cache_dir, None)

            for invalid_json in (b"{not json", b"\xff", b"[]"):
                cache_path.write_bytes(invalid_json)
                rebuilt, rebuilt_path, cache_hit = ti.load_or_build_snapshot(save_path, cache_dir, None)
                self.assertFalse(cache_hit)
                self.assertEqual(rebuilt_path, cache_path)
                self.assertEqual(rebuilt["currentID"], 42)

    def test_failed_atomic_write_preserves_existing_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache_path = Path(tmp) / "snapshot.json"
            previous = '{"existing":true}'
            cache_path.write_text(previous, encoding="utf-8")

            with patch.object(snapshot.json, "dump", side_effect=OSError("disk full")):
                with self.assertRaisesRegex(OSError, "disk full"):
                    snapshot.write_snapshot_atomically(cache_path, {"replacement": True})

            self.assertEqual(cache_path.read_text(encoding="utf-8"), previous)
            self.assertEqual(list(cache_path.parent.glob(f".{cache_path.name}.*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
