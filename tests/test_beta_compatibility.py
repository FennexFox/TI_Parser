import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import json
from pathlib import Path

import pytest

from ti_parser_compatibility import (
    CompatibilityRegistryError,
    RUNTIME_ASSET_FILENAMES,
    assess_compatibility,
    inspect_save,
    runtime_bundle_fingerprint,
)
from ti_parser_core import build_index


def ref(value):
    return {"value": value}


def state(state_id, value):
    return {"Key": ref(state_id), "Value": {"ID": ref(state_id), **value}}


def indexed_save(*, version="1.2.3", scenario="ModernScenario", flags=None):
    flags = flags or {
        "playedWithMods": False,
        "moddingActive": False,
        "moddingUsedAnytime": False,
    }
    metadata = {"playerFactionName": "Resistance"}
    global_values = {"latestSaveVersion": version}
    for key, value in flags.items():
        (metadata if key == "playedWithMods" else global_values)[key] = value
    return build_index(
        {
            "gamestates": {
                "TITimeState": [
                    state(
                        1,
                        {
                            "scenarioMetaTemplateName": scenario,
                            "currentDateTime": {"year": 2035, "month": 2, "day": 3},
                        },
                    )
                ],
                "TIMetadataState": [state(2, metadata)],
                "TIGlobalValuesState": [state(3, global_values)],
                "TIFactionState": [
                    state(10, {"templateName": "2030_Resistance", "displayName": "Resistance"})
                ],
                "TIPlayerState": [state(11, {"isAI": False, "faction": ref(10)})],
            }
        }
    )


def write_data_dir(path: Path, entries=None):
    path.mkdir(parents=True, exist_ok=True)
    for filename in RUNTIME_ASSET_FILENAMES:
        (path / filename).write_bytes((filename + "\n").encode())
    registry = {"schemaVersion": 1, "description": "test evidence", "entries": entries or []}
    (path / "compatibility_registry.json").write_text(json.dumps(registry), encoding="utf-8")


def test_inspection_reports_raw_facts_without_loading_catalogs(monkeypatch, tmp_path):
    import ti_parser_compatibility as compatibility

    write_data_dir(tmp_path)
    monkeypatch.setattr(compatibility, "DEFAULT_RUNTIME_CATALOG_DIR", tmp_path)
    inspected = inspect_save(indexed_save(), tmp_path / "synthetic.gz")

    assert inspected["date"] == {"year": 2035, "month": 2, "day": 3}
    assert inspected["scenario"] == "ModernScenario"
    assert inspected["latestSaveVersion"] == "1.2.3"
    assert inspected["modFlags"] == {
        "playedWithMods": False,
        "moddingActive": False,
        "moddingUsedAnytime": False,
    }
    assert inspected["factionCandidates"][0]["factionId"] == 10
    assert inspected["saveIdentity"]["playerFaction"]["id"] == 10


def test_empty_registry_is_conservatively_unverified(tmp_path):
    write_data_dir(tmp_path)
    result = assess_compatibility(indexed_save(), tmp_path)
    assert result["status"] == "unverified"
    assert result["reasons"] == [{"code": "unsupported-exact-runtime-tuple"}]


def test_exact_tuple_with_evidence_and_all_false_mod_flags_is_verified(tmp_path):
    write_data_dir(tmp_path)
    fingerprint = runtime_bundle_fingerprint(tmp_path)
    entries = [
        {
            "latestSaveVersion": "1.2.3",
            "scenario": "ModernScenario",
            "catalogFingerprint": fingerprint,
            "evidence": {"source": "synthetic regression evidence"},
        }
    ]
    (tmp_path / "compatibility_registry.json").write_text(
        json.dumps({"schemaVersion": 1, "entries": entries}), encoding="utf-8"
    )
    result = assess_compatibility(indexed_save(), tmp_path)
    assert result["status"] == "verified"
    assert result["reasons"] == []
    assert result["registry"]["matchedEvidence"] == entries[0]["evidence"]


@pytest.mark.parametrize(
    ("flags", "reason_code"),
    [
        (
            {"playedWithMods": True, "moddingActive": False, "moddingUsedAnytime": False},
            "mod-history-present",
        ),
        ({"playedWithMods": False, "moddingActive": False}, "mod-flag-missing"),
        (
            {"playedWithMods": False, "moddingActive": "false", "moddingUsedAnytime": False},
            "mod-flag-invalid",
        ),
    ],
)
def test_mod_history_missing_or_invalid_flags_are_unverified(tmp_path, flags, reason_code):
    write_data_dir(tmp_path)
    result = assess_compatibility(indexed_save(flags=flags), tmp_path)
    assert result["status"] == "unverified"
    assert reason_code in {reason["code"] for reason in result["reasons"]}


def test_conflicting_mod_observations_are_unverified(tmp_path):
    write_data_dir(tmp_path)
    indexed = indexed_save()
    indexed.gamestates["TIGlobalValuesState"][0]["Value"]["playedWithMods"] = True
    result = assess_compatibility(indexed, tmp_path)
    assert result["status"] == "unverified"
    assert {reason["code"] for reason in result["reasons"]} >= {"mod-flag-conflicting"}


def test_fingerprint_covers_standalone_module_and_location_bytes(tmp_path):
    write_data_dir(tmp_path)
    initial = runtime_bundle_fingerprint(tmp_path)
    (tmp_path / "module_catalog.json").write_bytes(b"changed module")
    module_changed = runtime_bundle_fingerprint(tmp_path)
    (tmp_path / "location_catalog.json").write_bytes(b"changed location")
    assert initial != module_changed
    assert module_changed != runtime_bundle_fingerprint(tmp_path)


def test_registry_is_excluded_from_runtime_fingerprint(tmp_path):
    write_data_dir(tmp_path)
    initial = runtime_bundle_fingerprint(tmp_path)
    (tmp_path / "compatibility_registry.json").write_text(
        json.dumps({"schemaVersion": 1, "entries": [], "description": "changed"}), encoding="utf-8"
    )
    assert runtime_bundle_fingerprint(tmp_path) == initial


def test_invalid_registry_raises_structured_error(tmp_path):
    write_data_dir(tmp_path)
    (tmp_path / "compatibility_registry.json").write_text(
        json.dumps({"schemaVersion": 1, "entries": [{"scenario": "ModernScenario"}]}),
        encoding="utf-8",
    )
    with pytest.raises(CompatibilityRegistryError) as caught:
        assess_compatibility(indexed_save(), tmp_path)
    assert caught.value.to_dict()["code"] == "compatibility-registry-entry"


def test_missing_scenario_is_inspectable_but_unverified(tmp_path):
    write_data_dir(tmp_path)
    indexed = indexed_save()
    del indexed.gamestates["TITimeState"][0]["Value"]["scenarioMetaTemplateName"]
    result = assess_compatibility(indexed, tmp_path)
    assert result["status"] == "unverified"
    assert {reason["code"] for reason in result["reasons"]} >= {"scenario-missing"}
