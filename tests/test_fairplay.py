from __future__ import annotations

import json
from pathlib import Path
import sys
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from ti_parser_errors import UserInputError
from ti_parser_fairplay import (
    FAIRPLAY_BOOTSTRAP_POLICY,
    compare_save_context,
    exposed_entries,
    get_profile_output_schema,
    policy_inventory,
    run_profile,
    sanitize_profile_error,
    validate_advice_generation,
    validate_profile,
)
from ti_parser_registry import ANALYSES


_ALGORITHM = "sha256-canonical-save-json-v1"
_HASH = "a" * 64


def _identity(*, fingerprint: dict | None = None, campaign_start=2024, date=None, player_id=10, template="ResistCouncil"):
    return {
        "schemaVersion": 1,
        "fingerprint": fingerprint if fingerprint is not None else {"algorithm": _ALGORITHM, "value": _HASH},
        "gameDate": date if date is not None else {"year": 2035, "month": 1, "day": 10},
        "scenario": "ModernScenario",
        "latestSaveVersion": "0.4.35",
        "campaignStartVersion": "0.4.35",
        "campaign": {"realWorldCampaignStart": campaign_start},
        "playerFaction": {"status": "resolved", "id": player_id, "template": template, "display": "Resistance"},
    }


def _peer_context(identity=None, *, selected_nation_id=48, bound_nation_id=None, status="complete"):
    if bound_nation_id is None:
        bound_nation_id = selected_nation_id
    return {
        "status": status,
        "saveIdentity": _identity() if identity is None else identity,
        "selectedNationId": selected_nation_id,
        "result": {"nation": {"id": bound_nation_id}},
    }


def _parser_observation(analysis, identity, *, status="complete", result=None):
    if result is None:
        result = {"saveIdentity": identity, "selectedNationId": 48} if analysis == "inspect-save" else {
            "selectedNationId": 48,
            "initialState": {"nation": {"populationMillions": 50}},
            "plans": [{"name": "baseline", "status": "complete"}],
            "comparison": {"nationMetrics": {"baseline": {}}},
        }
    return {
        "schemaVersion": 1,
        "analysis": analysis,
        "status": status,
        "saveIdentity": identity,
        "result": result,
    }


def _generation_observations(
    *,
    context=None,
    inspection_identity=None,
    projection_identity=None,
    reinspect_identity=None,
    reobserved_context=None,
    projection_status="complete",
    projection_result=None,
):
    inspection_identity = _identity() if inspection_identity is None else inspection_identity
    projection_identity = _identity() if projection_identity is None else projection_identity
    reinspect_identity = _identity() if reinspect_identity is None else reinspect_identity
    if context is None:
        context = _peer_context()
    if reobserved_context is None:
        reobserved_context = _peer_context()
    return (
        context,
        _parser_observation("inspect-save", inspection_identity),
        _parser_observation(
            "nation-projection", projection_identity, status=projection_status,
            result=projection_result,
        ),
        _parser_observation("inspect-save", reinspect_identity),
        reobserved_context,
    )


def test_registry_has_one_classification_source_without_changing_public_descriptor_shape():
    allowed = {"safe", "own-subject", "visibility-dependent", "diagnostic"}
    assert all(entry.fair_play_classification in allowed for entry in ANALYSES)
    assert all("fair_play_classification" not in entry.as_dict() for entry in ANALYSES)
    assert [entry.command for entry in exposed_entries("fair-play")] == ["inspect-save"]
    projection = next(entry for entry in ANALYSES if entry.command == "nation-projection")
    assert projection.fair_play_classification == "visibility-dependent"
    assert projection.fair_play_guard_policy == "fair-play-projection-v1"
    assert "fair_play_guard_policy" not in projection.as_dict()
    assert {entry.command for entry in exposed_entries("default")} == {
        entry.command for entry in ANALYSES if entry.routing_class in {"bootstrap", "primary"}
    }
    inventory = policy_inventory()
    assert inventory["bootstrapPolicy"] == FAIRPLAY_BOOTSTRAP_POLICY
    assert [row["command"] for row in inventory["analyses"] if row["exposed"]] == ["inspect-save"]
    assert next(row for row in inventory["analyses"] if row["command"] == "capabilities")["classification"] == "safe"
    assert inventory["adviceGenerationPolicy"] == {
        "id": "fair-play-projection-v1",
        "status": "pending",
        "enabled": False,
        "authorityHashStatus": "known-mismatch",
        "runtimeInstalledDiscovery": False,
    }


def test_default_profile_delegates_arguments_and_result_unchanged():
    expected = {"status": "complete", "result": {"kept": True}}
    session = Mock()
    session.run.return_value = expected
    actual = run_profile(session, "nation-projection", profile="default", allow_unverified=True, nation_name="USA")
    assert actual is expected
    session.run.assert_called_once_with("nation-projection", allow_unverified=True, nation_name="USA")


def test_fairplay_inspection_returns_only_allowlisted_identity_and_compatibility():
    identity = _identity()
    session = Mock()
    session.inspect.return_value = {
        "save": {"filename": "private-save.gz"},
        "saveIdentity": {**identity, "unknownRawField": "private marker"},
        "compatibility": {
            "schemaVersion": 1,
            "status": "unverified",
            "reasons": [{"code": "mod-history-present", "field": "recentPatch", "value": True}],
            "modEvidence": {"recentPatch": {"value": True, "observations": ["private marker"]}},
            "catalogFingerprint": "c" * 64,
        },
        "modFlags": {"recentPatch": True},
        "factionCandidates": [{"displayName": "private marker"}],
    }

    result = run_profile(session, "inspect-save", profile="fair-play")

    assert result["status"] == "complete"
    assert set(result["result"]) == {"saveIdentity", "compatibility"}
    assert set(result["saveIdentity"]) == {
        "schemaVersion", "fingerprint", "gameDate", "scenario", "latestSaveVersion",
        "campaignStartVersion", "campaign", "playerFaction",
    }
    assert result["compatibility"] == {
        "schemaVersion": 1,
        "status": "unverified",
        "reasons": [{"code": "mod-history-present"}],
        "unverifiedAllowed": False,
        "catalogFingerprint": "c" * 64,
    }
    encoded = json.dumps(result)
    for private in ("private marker", "private-save.gz", "modFlags", "factionCandidates", "modEvidence"):
        assert private not in encoded

    import jsonschema
    jsonschema.validate(result, get_profile_output_schema("fair-play", "inspect-save"))


def test_fairplay_rejects_unresolved_identity_without_candidate_details():
    session = Mock()
    session.inspect.return_value = {
        "saveIdentity": {
            "schemaVersion": 1,
            "fingerprint": {"algorithm": _ALGORITHM, "value": _HASH},
            "playerFaction": {
                "status": "unresolved",
                "error": {"code": "ambiguous-player", "message": "private marker", "candidates": [{"id": 7}]},
            },
        },
        "compatibility": {"status": "verified", "reasons": []},
    }

    result = run_profile(session, "inspect-save", profile="fair-play")

    assert result["status"] == "error"
    assert result["error"]["code"] == "player-identity-unresolved"
    assert "private marker" not in json.dumps(result)
    import jsonschema
    jsonschema.validate(result, get_profile_output_schema("fair-play", "inspect-save"))


@pytest.mark.parametrize("analysis", [entry.command for entry in ANALYSES
                                      if entry.command != "inspect-save"])
def test_fairplay_denies_calculations_before_session_inspection_or_handler(analysis):
    session = Mock()
    with pytest.raises(UserInputError) as caught:
        run_profile(session, analysis, profile="fair-play", nation_name="USA", days=180,
                    faction_name="Another faction", diagnostics=True)
    assert caught.value.code == "fairplay-analysis-denied"
    session.inspect.assert_not_called()
    session.run.assert_not_called()


def test_profile_errors_are_sanitized_only_for_fairplay():
    payload = {
        "schemaVersion": 1,
        "status": "error",
        "error": {"code": "entity-lookup-failed", "message": "C:\\private\\save.gz", "context": {"path": "C:\\private"}},
        "saveIdentity": _identity(),
    }
    sanitized = sanitize_profile_error(payload, "fair-play")
    assert sanitized == {
        "schemaVersion": 1,
        "status": "error",
        "error": {"code": "entity-lookup-failed", "message": "The request could not be completed under the selected profile."},
    }
    assert sanitize_profile_error(payload, "default") is payload
    success = {"status": "complete", "result": {"safe": True}}
    assert sanitize_profile_error(success, "fair-play") is success
    import jsonschema
    jsonschema.validate(sanitized, get_profile_output_schema("fair-play", "inspect-save"))


def test_only_named_profiles_are_accepted():
    assert validate_profile("default") == "default"
    assert validate_profile("fair-play") == "fair-play"
    with pytest.raises(UserInputError) as caught:
        validate_profile("fairplay")
    assert caught.value.code == "invalid-profile"


def test_compare_save_context_returns_exact_only_for_valid_matching_identity_and_nation():
    parser, companion = _identity(), _identity()
    assert compare_save_context(parser, companion, 48, 48, pinned=False) == {
        "status": "exact", "reason": "exact-fingerprint-and-context-match"
    }
    assert compare_save_context(parser, companion, 48, 49, pinned=True)["status"] == "rejected"
    assert compare_save_context(parser, companion, 48, 49, pinned=True)["reason"] == "selected-nation-id-mismatch"


def test_compare_save_context_allows_only_pinned_provisional_match_when_fingerprint_is_unavailable():
    unsupported = {"algorithm": "unsupported", "value": "opaque"}
    parser, companion = _identity(fingerprint=unsupported), _identity(fingerprint=unsupported)
    assert compare_save_context(parser, companion, "48", "48", pinned=True) == {
        "status": "provisional", "reason": "pinned-context-match-without-exact-fingerprint"
    }
    assert compare_save_context(parser, companion, "48", "48", pinned=False)["reason"] == "pin-required-for-provisional-match"


@pytest.mark.parametrize(
    ("parser_change", "companion_change", "parser_nation", "companion_nation", "expected"),
    [
        ({"campaign_start": 2025}, {}, 48, 48, "campaign-start-mismatch"),
        ({"date": {"year": 2035, "month": 1, "day": 11}}, {}, 48, 48, "game-date-mismatch"),
        ({"player_id": 11}, {}, 48, 48, "player-identity-mismatch"),
        ({}, {}, None, 48, "selected-nation-id-missing"),
    ],
)
def test_compare_save_context_rejects_missing_or_changed_context(
    parser_change, companion_change, parser_nation, companion_nation, expected
):
    assert compare_save_context(
        _identity(**parser_change), _identity(**companion_change), parser_nation, companion_nation, pinned=True
    ) == {"status": "rejected", "reason": expected}


def test_compare_save_context_rejects_fingerprint_mismatch_and_parser_change_even_when_pinned():
    parser = _identity(fingerprint={"algorithm": _ALGORITHM, "value": "b" * 64})
    companion = _identity(fingerprint={"algorithm": _ALGORITHM, "value": _HASH})
    assert compare_save_context(parser, companion, 48, 48, pinned=True)["reason"] == "fingerprint-mismatch"
    assert compare_save_context(
        parser, parser, 48, 48,
        pinned=True, previous_parser_fingerprint={"algorithm": _ALGORITHM, "value": _HASH},
    )["reason"] == "parser-fingerprint-changed"


def test_compare_save_context_rejects_malformed_hash_even_with_matching_context_unless_provisionally_pinned():
    malformed = {"algorithm": _ALGORITHM, "value": "not-a-sha256"}
    parser, companion = _identity(fingerprint=malformed), _identity(fingerprint=malformed)
    assert compare_save_context(parser, companion, 48, 48, pinned=False) == {
        "status": "rejected", "reason": "fingerprint-invalid"
    }
    assert compare_save_context(parser, companion, 48, 48, pinned=True) == {
        "status": "rejected", "reason": "fingerprint-invalid"
    }


def test_compare_save_context_requires_supported_identity_schema_for_exact_status():
    parser, companion = _identity(), _identity()
    parser.pop("schemaVersion")
    assert compare_save_context(parser, companion, 48, 48, pinned=True) == {
        "status": "provisional", "reason": "pinned-context-match-without-exact-fingerprint"
    }
    parser["schemaVersion"] = 2
    assert compare_save_context(parser, companion, 48, 48, pinned=True) == {
        "status": "rejected", "reason": "identity-schema-version-unsupported"
    }


def test_validate_advice_generation_accepts_only_fully_correlated_sequence():
    observations = _generation_observations()

    result = validate_advice_generation(*observations, pinned=False)

    assert result == {
        "status": "exact",
        "reason": "exact-generation-and-context-match",
    }


@pytest.mark.parametrize(
    ("changed_observation", "reason"),
    [
        ("context", "fingerprint-mismatch"),
        ("inspect", "parser-fingerprint-changed"),
        ("projection", "parser-fingerprint-changed"),
        ("reinspect", "parser-fingerprint-changed"),
        ("reobserved", "fingerprint-mismatch"),
    ],
)
def test_validate_advice_generation_rejects_save_changes_at_each_observation(
    changed_observation, reason
):
    changed_identity = _identity(fingerprint={"algorithm": _ALGORITHM, "value": "b" * 64})
    observations = list(_generation_observations())
    index_by_name = {
        "context": 0,
        "inspect": 1,
        "projection": 2,
        "reinspect": 3,
        "reobserved": 4,
    }
    index = index_by_name[changed_observation]
    if index in {0, 4}:
        observations[index] = _peer_context(changed_identity)
    else:
        analysis = "nation-projection" if index == 2 else "inspect-save"
        result = observations[index]["result"]
        if analysis == "inspect-save":
            result = {"saveIdentity": changed_identity, "selectedNationId": 48}
        observations[index] = _parser_observation(analysis, changed_identity, result=result)

    result = validate_advice_generation(*observations, pinned=True)

    assert result["status"] == "rejected"
    assert result["reason"] == reason


@pytest.mark.parametrize(
    ("index", "expected_reason"),
    [
        (0, "context-missing"),
        (1, "inspect-save-envelope-missing"),
        (2, "nation-projection-envelope-missing"),
        (3, "inspect-save-envelope-missing"),
        (4, "companion-reobserved-context-missing"),
    ],
)
def test_validate_advice_generation_rejects_missing_observations(index, expected_reason):
    observations = list(_generation_observations())
    observations[index] = None

    result = validate_advice_generation(*observations, pinned=True)

    assert result == {"status": "rejected", "reason": expected_reason}


@pytest.mark.parametrize(
    ("context", "expected_reason"),
    [
        (_peer_context(selected_nation_id=None), "context-selected-nation-unbound"),
        (_peer_context(selected_nation_id=49, bound_nation_id=48), "context-selected-nation-binding-mismatch"),
    ],
)
def test_validate_advice_generation_requires_peer_selected_nation_binding(context, expected_reason):
    observations = list(_generation_observations(context=context))

    result = validate_advice_generation(*observations, pinned=True)

    assert result == {"status": "rejected", "reason": expected_reason}


def test_validate_advice_generation_does_not_infer_nation_from_inspection_or_raw_projection():
    observations = list(_generation_observations())
    projection = observations[2]
    projection["result"].pop("selectedNationId")
    projection["selectedNationId"] = 48
    projection["result"]["initialState"]["nation"]["id"] = 48

    result = validate_advice_generation(*observations, pinned=True)

    assert result == {
        "status": "rejected",
        "reason": "projection-selected-nation-id-missing",
    }


@pytest.mark.parametrize("index", [1, 3])
def test_validate_advice_generation_requires_inspection_nation_binding(index):
    observations = list(_generation_observations())
    observations[index]["result"].pop("selectedNationId")

    result = validate_advice_generation(*observations, pinned=True)

    assert result == {
        "status": "rejected",
        "reason": "inspect-save-selected-nation-id-missing",
    }


@pytest.mark.parametrize("index", [1, 3])
def test_validate_advice_generation_rejects_inspection_nation_mismatch(index):
    observations = list(_generation_observations())
    observations[index]["result"]["selectedNationId"] = 49

    result = validate_advice_generation(*observations, pinned=True)

    assert result == {
        "status": "rejected",
        "reason": "selected-nation-id-mismatch",
    }


def test_validate_advice_generation_peer_fingerprint_gap_is_pinned_provisional_only():
    unsupported = {"algorithm": "peer-unknown", "value": "same-date-hidden-change"}
    peer_identity = _identity(fingerprint=unsupported)
    observations = _generation_observations(
        context=_peer_context(peer_identity),
        reobserved_context=_peer_context(_identity(fingerprint=unsupported)),
    )

    provisional = validate_advice_generation(*observations, pinned=True)
    unpinned = validate_advice_generation(*observations, pinned=False)

    assert provisional == {
        "status": "provisional",
        "reason": "pinned-context-match-without-peer-fingerprint",
    }
    assert unpinned == {
        "status": "rejected",
        "reason": "pin-required-for-provisional-match",
    }
    assert "same-date-hidden-change" not in json.dumps(provisional)


def test_validate_advice_generation_accepts_incomplete_authoritative_prefix_as_incomplete():
    incomplete_result = {
        "selectedNationId": 48,
        "initialState": {"nation": {"populationMillions": 50}},
        "plans": [{
            "name": "baseline",
            "status": "incomplete",
            "lastAuthoritativeState": {"nation": {"missionControl": 0}},
        }],
        "comparison": {"nationMetrics": {}},
    }
    observations = _generation_observations(
        projection_status="incomplete", projection_result=incomplete_result
    )

    result = validate_advice_generation(*observations, pinned=False)

    assert result == {
        "status": "exact",
        "reason": "exact-generation-and-context-match",
        "outcomeStatus": "incomplete",
    }


@pytest.mark.parametrize(
    ("status", "projection_result", "expected_reason"),
    [
        ("deferred", None, "nation-projection-status-invalid"),
        ("incomplete", None, "nation-projection-result-missing"),
        (
            "incomplete",
            {
                "selectedNationId": 48,
                "initialState": {"nation": {}},
                "plans": [{"name": "baseline", "status": "incomplete"}],
                "comparison": {},
            },
            "projection-result-incomplete-without-authoritative-prefix",
        ),
    ],
)
def test_validate_advice_generation_rejects_unusable_projection_outcomes(
    status, projection_result, expected_reason
):
    observations = list(_generation_observations(
        projection_status=status, projection_result=projection_result
    ))
    if status == "incomplete" and projection_result is None:
        observations[2]["result"] = None

    result = validate_advice_generation(*observations, pinned=True)

    assert result == {"status": "rejected", "reason": expected_reason}


def test_validate_advice_generation_rejects_response_bound_identity_mismatch():
    observations = list(_generation_observations())
    observations[1]["result"]["saveIdentity"] = _identity(
        fingerprint={"algorithm": _ALGORITHM, "value": "b" * 64}
    )

    result = validate_advice_generation(*observations, pinned=True)

    assert result == {
        "status": "rejected",
        "reason": "inspect-save-response-save-identity-mismatch",
    }
