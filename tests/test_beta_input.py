import gzip
import json
import sys
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import ti_parser_core as core


def ref(state_id: int) -> dict[str, int]:
    return {"value": state_id}


def row(state_id: int | None, **value):
    if state_id is None:
        return {"Value": value}
    return {"Key": ref(state_id), "Value": {"ID": ref(state_id), **value}}


def indexed_factions():
    return core.build_index(
        {
            "gamestates": {
                "TIFactionState": [
                    row(10, templateName="ResistCouncil", displayName="Resistance"),
                    row(11, templateName="CooperateCouncil", displayName="Academy"),
                ],
                "TINationState": [
                    row(20, templateName="USA", displayName="United States"),
                    row(21, templateName="USNA", displayName="United States of North America"),
                ],
            }
        }
    )


def test_errors_have_stable_structured_payloads():
    error = core.EntityLookupError(
        "ambiguous",
        code="entity-ambiguous",
        candidates=[{"id": 1, "name": "One"}],
        context={"selector": "o"},
    )

    assert isinstance(error, core.UserInputError)
    assert error.to_dict() == {
        "code": "entity-ambiguous",
        "message": "ambiguous",
        "candidates": [{"id": 1, "name": "One"}],
        "context": {"selector": "o"},
    }


@pytest.mark.parametrize("contents", [b"not gzip", gzip.compress(b"not json")])
def test_load_save_converts_decode_failures_to_save_integrity_error(tmp_path, contents):
    save_path = tmp_path / "broken.gz"
    save_path.write_bytes(contents)

    with pytest.raises(core.SaveIntegrityError) as caught:
        core.load_save(save_path)

    assert caught.value.to_dict()["code"] == "save-decode-failed"
    assert caught.value.to_dict()["context"]["path"] == str(save_path)


def test_load_save_rejects_missing_gamestates(tmp_path):
    save_path = tmp_path / "wrong-shape.gz"
    with gzip.open(save_path, "wt", encoding="utf-8") as handle:
        json.dump({"notGamestates": {}}, handle)

    with pytest.raises(core.SaveIntegrityError, match="Not a recognized"):
        core.load_save(save_path)


@pytest.mark.parametrize(
    "payload, code",
    [
        ({}, "save-structure-invalid"),
        ({"gamestates": []}, "save-structure-invalid"),
        ({"gamestates": {"TINationState": {"unexpected": 1}}}, "save-collection-invalid"),
        ({"gamestates": {"TINationState": [None]}}, "save-row-invalid"),
        ({"gamestates": {"TINationState": [{}]}}, "save-row-invalid"),
    ],
)
def test_build_index_rejects_malformed_required_collections_and_rows(payload, code):
    with pytest.raises(core.SaveIntegrityError) as caught:
        core.build_index(payload)
    assert caught.value.code == code


def test_build_index_allows_rows_without_optional_ids():
    state = {"scenarioMetaTemplateName": "2003Scenario"}
    indexed = core.build_index({"gamestates": {"TITimeState": [{"Value": state}]}})

    assert indexed.id_index == {}
    assert core.first_value(indexed, "TITimeState") is state


def test_build_index_rejects_duplicate_ids_and_key_value_id_mismatch():
    with pytest.raises(core.SaveIntegrityError) as duplicate:
        core.build_index(
            {"gamestates": {"TINationState": [row(1, templateName="A"), row(1, templateName="B")]}}
        )
    assert duplicate.value.code == "save-state-id-duplicate"
    assert [candidate["name"] for candidate in duplicate.value.candidates] == ["A", "B"]

    with pytest.raises(core.SaveIntegrityError) as mismatch:
        core.build_index(
            {
                "gamestates": {
                    "TINationState": [
                        {"Key": ref(1), "Value": {"ID": ref(2), "templateName": "A"}}
                    ]
                }
            }
        )
    assert mismatch.value.code == "save-row-id-mismatch"


def test_match_raw_state_prefers_unique_exact_over_partial_and_accepts_integer_id():
    indexed = indexed_factions()

    assert core.match_raw_state(indexed, "TINationState", "USA")[0] == 20
    assert core.match_raw_state(indexed, "TINationState", 21)[0] == 21


def test_match_raw_state_rejects_ambiguous_partial_with_candidates():
    indexed = indexed_factions()

    with pytest.raises(core.EntityLookupError) as caught:
        core.match_raw_state(indexed, "TINationState", "United")

    payload = caught.value.to_dict()
    assert payload["code"] == "entity-ambiguous"
    assert {candidate["id"] for candidate in payload["candidates"]} == {20, 21}


def test_integer_lookup_validates_entity_type():
    indexed = indexed_factions()

    with pytest.raises(core.EntityLookupError) as caught:
        core.match_raw_state(indexed, "TIFactionState", 20)

    assert caught.value.code == "entity-type-mismatch"
    assert caught.value.candidates == [{"id": 20, "name": "United States", "type": "TINationState"}]


def test_find_faction_state_accepts_integer_and_uses_typed_errors():
    indexed = indexed_factions()

    assert core.find_faction_state(indexed, 11)[0] == 11
    with pytest.raises(core.EntityLookupError) as missing:
        core.find_faction_state(indexed, "Servants")
    assert missing.value.code == "entity-not-found"

    with pytest.raises(core.EntityLookupError) as unresolved:
        core.find_faction_state(indexed)
    assert unresolved.value.code == "player-faction-unresolved"
