from __future__ import annotations

import json
import gzip
from copy import deepcopy
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
    _run_subject_bound_projection,
    _run_guarded_projection,
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


@pytest.fixture(autouse=True)
def generation_session(tmp_path):
    """Real index, inspection and packaged-catalog projection for binding tests."""
    from tests.fixtures.fairplay_projection import make_save_data
    from ti_parser_session import AnalysisSession
    global _GENERATION_SESSION
    data = make_save_data()
    data["gamestates"]["TIGlobalValuesState"][0]["Value"].update(
        realWorldCampaignStart=2024, latestSaveVersion="0.4.35",
        campaignStartVersion="0.4.35",
    )
    path = tmp_path / "subject.gz"
    with gzip.open(path, "wt", encoding="utf-8") as output:
        json.dump(data, output)
    _GENERATION_SESSION = AnalysisSession(path)
    return _GENERATION_SESSION


def _generation_observations(
    *, context=None, inspection_identity=None, projection_identity=None,
    reinspect_identity=None, reobserved_context=None,
    projection_status="complete", projection_result=None,
):
    # Issuance is private trusted application work, not fair-play admission.
    # The happy path uses the actual adapter and packaged catalogs. Explicit
    # incomplete/error shapes below model the domain boundary independently.
    session = _GENERATION_SESSION
    inspection = run_profile(session, "inspect-save", profile="fair-play")
    reinspect = run_profile(session, "inspect-save", profile="fair-play")
    kwargs = dict(nation_name="USA", days=1, allow_unverified=True)
    if projection_status != "complete" or projection_result is not None:
        from unittest.mock import patch
        modeled = deepcopy(projection_result) if projection_result is not None else {
            "initialState": {"nation": {}}, "plans": [{"status": projection_status}], "comparison": {},
        }
        with patch("ti_parser_application.calculate_nation_projection", return_value=modeled):
            projection, binding = _run_subject_bound_projection(session, **kwargs)
        if projection_status == "deferred":
            projection["status"] = "deferred"
    else:
        projection, binding = _run_subject_bound_projection(session, **kwargs)
        assert projection["status"] == "complete"
    identity = inspection["saveIdentity"]
    for envelope, override in ((inspection, inspection_identity), (projection, projection_identity), (reinspect, reinspect_identity)):
        if override is not None:
            envelope["saveIdentity"] = override
            if "saveIdentity" in envelope["result"]:
                envelope["result"]["saveIdentity"] = override
    return (
        _peer_context(identity, selected_nation_id=20) if context is None else context,
        inspection, projection, reinspect,
        _peer_context(identity, selected_nation_id=20) if reobserved_context is None else reobserved_context,
        binding,
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
        "authorityHashStatus": "not_evaluated",
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

    result = validate_advice_generation(*observations[:5], pinned=False, subject_binding=observations[5])

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
    observations = list(_generation_observations())
    changed_identity = deepcopy(observations[1]["saveIdentity"])
    changed_identity["fingerprint"]["value"] = "b" * 64
    index_by_name = {
        "context": 0,
        "inspect": 1,
        "projection": 2,
        "reinspect": 3,
        "reobserved": 4,
    }
    index = index_by_name[changed_observation]
    if index in {0, 4}:
        observations[index] = _peer_context(changed_identity, selected_nation_id=20)
    else:
        analysis = "nation-projection" if index == 2 else "inspect-save"
        result = observations[index]["result"]
        if analysis == "inspect-save":
            result = {"saveIdentity": changed_identity}
        observations[index] = _parser_observation(analysis, changed_identity, result=result)

    result = validate_advice_generation(*observations[:5], pinned=True, subject_binding=observations[5])

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

    result = validate_advice_generation(*observations[:5], pinned=True, subject_binding=observations[5])

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

    result = validate_advice_generation(*observations[:5], pinned=True, subject_binding=observations[5])

    assert result == {"status": "rejected", "reason": expected_reason}


def test_validate_advice_generation_requires_application_receipt():
    observations = _generation_observations()
    for guessed in (None, {"selectedNationId": 20}, {"nation": {"id": 20}}):
        assert validate_advice_generation(*observations[:5], pinned=True, subject_binding=guessed) == {
            "status": "rejected", "reason": "projection-subject-binding-missing-or-invalid",
        }


def test_validate_advice_generation_inspections_are_save_only():
    observations = _generation_observations()
    assert all("selectedNationId" not in observations[index]["result"] for index in (1, 3))
    assert validate_advice_generation(*observations[:5], pinned=False, subject_binding=observations[5])["status"] == "exact"


@pytest.mark.parametrize("mutation", ["contents", "copy", "foreign"])
def test_validate_advice_generation_rejects_changed_or_foreign_result(mutation):
    observations = list(_generation_observations())
    if mutation == "contents":
        observations[2]["result"]["selectedNationId"] = 9999
        reason = "projection-subject-binding-result-changed"
    elif mutation == "copy":
        observations[2] = deepcopy(observations[2])
        reason = "projection-subject-binding-result-mismatch"
    else:
        observations[5] = _generation_observations()[5]
        reason = "projection-subject-binding-result-mismatch"
    assert validate_advice_generation(*observations[:5], pinned=True, subject_binding=observations[5]) == {
        "status": "rejected", "reason": reason,
    }


def test_validate_advice_generation_peer_fingerprint_gap_is_pinned_provisional_only():
    unsupported = {"algorithm": "peer-unknown", "value": "same-date-hidden-change"}
    peer_identity = deepcopy(_GENERATION_SESSION.facts["saveIdentity"])
    peer_identity["fingerprint"] = unsupported
    observations = _generation_observations(
        context=_peer_context(peer_identity, selected_nation_id=20),
        reobserved_context=_peer_context(deepcopy(peer_identity), selected_nation_id=20),
    )

    provisional = validate_advice_generation(*observations[:5], pinned=True, subject_binding=observations[5])
    unpinned = validate_advice_generation(*observations[:5], pinned=False, subject_binding=observations[5])

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
        "selectedNationId": 20,
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

    result = validate_advice_generation(*observations[:5], pinned=False, subject_binding=observations[5])

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

    result = validate_advice_generation(*observations[:5], pinned=True, subject_binding=observations[5])

    assert result == {"status": "rejected", "reason": expected_reason}


def test_validate_advice_generation_rejects_response_bound_identity_mismatch():
    observations = list(_generation_observations())
    observations[1]["result"]["saveIdentity"] = _identity(
        fingerprint={"algorithm": _ALGORITHM, "value": "b" * 64}
    )

    result = validate_advice_generation(*observations[:5], pinned=True, subject_binding=observations[5])

    assert result == {
        "status": "rejected",
        "reason": "inspect-save-response-save-identity-mismatch",
    }


@pytest.mark.parametrize("allow_unverified", [False, True])
def test_pending_guard_denies_before_any_session_work(allow_unverified):
    session = Mock()
    with pytest.raises(UserInputError) as exc:
        _run_guarded_projection(session, nation_name="USA", days=1, allow_unverified=allow_unverified)
    assert exc.value.code == "fairplay-analysis-denied"
    assert session.mock_calls == []


@pytest.mark.parametrize("mutation", ["missing-cp", "wrong-type", "unowned", "missing-owner", "wrong-owner-type", "empty-cps", "count-mismatch", "duplicate-cp", "foreign-cp", "ambiguous-player", "arbitrary-id"])
def test_subject_operation_rejects_unresolved_or_unowned_save_subject(generation_session, mutation, monkeypatch):
    from ti_parser_core import build_index
    data = deepcopy(generation_session.indexed.data)
    states = data["gamestates"]
    nation = states["TINationState"][0]["Value"]
    cp = states["TIControlPointState"][0]["Value"]
    selector = "USA"
    if mutation == "missing-cp":
        states["TIControlPointState"].pop(0)
    elif mutation == "wrong-type":
        states["TIRegionState"].append(states["TIControlPointState"].pop(0))
    elif mutation == "unowned":
        states["TIFactionState"].append({"Key": {"value": 99}, "Value": {"ID": {"value": 99}, "templateName": "Other"}})
        cp["faction"] = {"value": 99}
    elif mutation == "missing-owner":
        cp["faction"] = {"value": 999}
    elif mutation == "wrong-owner-type":
        cp["faction"] = {"value": 100}
    elif mutation == "empty-cps":
        nation["controlPoints"] = []
    elif mutation == "count-mismatch":
        nation["numControlPoints"] = 7
    elif mutation == "duplicate-cp":
        nation["controlPoints"][1] = nation["controlPoints"][0]
    elif mutation == "foreign-cp":
        cp["nation"] = {"value": 999}
    elif mutation == "ambiguous-player":
        states["TIPlayerState"].append({"Key": {"value": 888}, "Value": {"isAI": False, "faction": {"value": 999}}})
    else:
        selector = 999999
    generation_session.indexed = build_index(data)
    run = Mock(side_effect=AssertionError("must not calculate unresolved subject"))
    monkeypatch.setattr(generation_session, "run", run)
    with pytest.raises(UserInputError):
        _run_subject_bound_projection(generation_session, nation_name=selector, days=1, allow_unverified=True)
    assert run.mock_calls == []


@pytest.mark.parametrize("index", [0, 4])
def test_subject_context_nation_must_match_resolved_projection(index):
    observations = list(_generation_observations())
    observations[index] = _peer_context(observations[1]["saveIdentity"], selected_nation_id=999)
    assert validate_advice_generation(*observations[:5], pinned=True, subject_binding=observations[5]) == {
        "status": "rejected", "reason": "selected-nation-id-mismatch",
    }


def test_subject_binding_cannot_be_reused_for_another_session(generation_session):
    from ti_parser_session import AnalysisSession
    observations = list(_generation_observations())
    other = AnalysisSession(generation_session.save_path)
    observations[2], _ = _run_subject_bound_projection(other, nation_name="USA", days=1, allow_unverified=True)
    assert validate_advice_generation(*observations[:5], pinned=False, subject_binding=observations[5]) == {
        "status": "rejected", "reason": "projection-subject-binding-result-mismatch",
    }


def test_policy_metadata_alone_cannot_activate_guard(monkeypatch):
    from ti_parser_fairplay import FAIRPLAY_ADVICE_GENERATION_POLICY
    monkeypatch.setitem(FAIRPLAY_ADVICE_GENERATION_POLICY, "enabled", True)
    monkeypatch.setitem(FAIRPLAY_ADVICE_GENERATION_POLICY, "status", "accepted")
    monkeypatch.setitem(FAIRPLAY_ADVICE_GENERATION_POLICY, "authorityHashStatus", "match")
    session = Mock()
    with pytest.raises(UserInputError) as exc:
        _run_guarded_projection(session, nation_name="USA", days=1, allow_unverified=True)
    assert exc.value.code == "fairplay-analysis-denied"
    assert session.mock_calls == []


@pytest.mark.parametrize("index", [2, 3])
def test_real_save_change_before_or_after_projection_is_rejected(generation_session, index):
    from ti_parser_session import AnalysisSession
    observations = list(_generation_observations())
    data = deepcopy(generation_session.indexed.data)
    data["gamestates"]["TINationState"][0]["Value"]["GDP"] += 1
    with gzip.open(generation_session.save_path, "wt", encoding="utf-8") as output:
        json.dump(data, output)
    changed = AnalysisSession(generation_session.save_path)
    if index == 2:
        observations[2], observations[5] = _run_subject_bound_projection(
            changed, nation_name="USA", days=1, allow_unverified=True,
        )
    else:
        observations[3] = run_profile(changed, "inspect-save", profile="fair-play")
    assert observations[index]["saveIdentity"]["gameDate"] == observations[1]["saveIdentity"]["gameDate"]
    assert validate_advice_generation(*observations[:5], pinned=True, subject_binding=observations[5]) == {
        "status": "rejected", "reason": "parser-fingerprint-changed",
    }
