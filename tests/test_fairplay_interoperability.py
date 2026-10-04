"""Two-server fair-play interoperability acceptance probes.

These deterministic MCP client calls verify server contracts and policy. They
are not evidence of model tool-routing behavior; that requires a separate
Codex-side prompt run using the case file.
"""

from __future__ import annotations

import gzip
import hashlib
import importlib.util
import json
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
TOOLS_PATH = REPOSITORY_ROOT / "tools"
if str(TOOLS_PATH) not in sys.path:
    sys.path.insert(0, str(TOOLS_PATH))

from ti_parser_fairplay import compare_save_context  # noqa: E402


SAVE_IDENTITY_ALGORITHM = "sha256-canonical-save-json-v1"


def _ref(state_id: int) -> dict[str, int]:
    return {"value": state_id}


def _state(state_id: int, value: dict[str, Any]) -> dict[str, Any]:
    return {"Key": _ref(state_id), "Value": {"ID": _ref(state_id), **value}}


def _canonical_fingerprint(save_data: dict[str, Any]) -> dict[str, str]:
    canonical = json.dumps(
        save_data,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=True,
    ).encode("utf-8")
    return {"algorithm": SAVE_IDENTITY_ALGORITHM, "value": hashlib.sha256(canonical).hexdigest()}


def _synthetic_save_data(generation: int) -> dict[str, Any]:
    faction_id, player_id, nation_id, control_point_id = 2, 3, 48, 49
    gamestates = {
        "TITimeState": [
            _state(
                1,
                {
                    "scenarioMetaTemplateName": "ModernScenario",
                    "currentDateTime": {"year": 2035, "month": 1, "day": 10},
                },
            )
        ],
        "TIFactionState": [
            _state(
                faction_id,
                {
                    "templateName": "ResistCouncil",
                    "displayName": "Resistance",
                    "isHumanPlayer": True,
                    "player": _ref(player_id),
                    "controlPoints": [_ref(control_point_id)],
                    "resources": {},
                },
            )
        ],
        "TIPlayerState": [_state(player_id, {"faction": _ref(faction_id), "isAI": False})],
        "TINationState": [
            _state(
                nation_id,
                {
                    "templateName": "UnitedStates",
                    "displayName": "United States",
                    "controlPoints": [_ref(control_point_id)],
                    "priorityTemplateNames": ["Economy", "Knowledge"],
                },
            )
        ],
        "TIControlPointState": [
            _state(
                control_point_id,
                {
                    "nation": _ref(nation_id),
                    "faction": _ref(faction_id),
                    "controlPointNum": 0,
                },
            )
        ],
        "TIGlobalValuesState": [
            _state(
                6,
                {
                    "latestSaveVersion": "0.4.35",
                    "campaignStartVersion": "0.4.35",
                    "realWorldCampaignStart": 2024,
                },
            )
        ],
    }
    return {
        "currentID": {"value": 1000},
        "gamestates": gamestates,
        # Test-only generation marker changes parsed content without changing
        # the visible campaign, date, player, or selected nation.
        "testFixtureGeneration": generation,
    }


def _companion_identity(save_data: dict[str, Any], *, include_fingerprint: bool) -> dict[str, Any]:
    identity: dict[str, Any] = {
        "schemaVersion": 1,
        "gameDate": {"year": 2035, "month": 1, "day": 10},
        "scenario": "ModernScenario",
        "latestSaveVersion": "0.4.35",
        "campaignStartVersion": "0.4.35",
        "campaign": {"realWorldCampaignStart": 2024},
        "playerFaction": {
            "status": "resolved",
            "id": 2,
            "template": "ResistCouncil",
            "display": "Resistance",
        },
    }
    if include_fingerprint:
        identity["fingerprint"] = _canonical_fingerprint(save_data)
    return identity


def create_mock_fixture(
    root: Path,
    *,
    generation: int = 0,
    include_fingerprint: bool = True,
) -> tuple[Path, Path]:
    """Write a synthetic TI save and matching mock Companion JSON fixture.

    This public test helper is also used by the root-level Codex routing run.
    The Companion fixture contains only visible synthetic nation facts and an
    identity bound to the exact parsed-save generation.
    """

    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    save_data = _synthetic_save_data(generation)
    save_path = root / "synthetic-campaign.gz"
    raw_save = json.dumps(save_data, ensure_ascii=False, separators=(",", ":"), allow_nan=True).encode("utf-8")
    save_path.write_bytes(gzip.compress(raw_save, mtime=0))

    fixture = {
        "schemaVersion": 1,
        "snapshotIdentity": _companion_identity(save_data, include_fingerprint=include_fingerprint),
        "selectedNationId": 48,
        "nation": {
            "id": 48,
            "name": "United States",
            "owner": {"status": "player-controlled", "controlPoints": 1, "of": 1},
            "currentState": {
                "populationMillions": 340,
                "priorities": {"Economy": 2, "Knowledge": 3},
                "visibleResources": {"Money": 1250, "Influence": 84},
            },
            "evidence": "Fixed synthetic player-visible fixture values; no projection was calculated.",
        },
        "recentChanges": [
            {
                "kind": "priority-changed",
                "priority": "Economy",
                "from": 1,
                "to": 2,
                "recordedAt": {"year": 2035, "month": 1, "day": 10},
            }
        ],
    }
    companion_path = root / "companion-fixture.json"
    companion_path.write_text(json.dumps(fixture, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return save_path, companion_path


def _mcp_dependencies_available() -> bool:
    return all(importlib.util.find_spec(name) is not None for name in ("mcp", "anyio"))


def _read_fixture(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_companion_observation(response: Any) -> dict[str, Any]:
    """Normalize a Companion current-state result to the generation-guard shape.

    The helper carries through only fields explicitly present in the mock
    response. It rejects a missing identity, selected nation, or matching
    ``result.nation.id`` rather than inferring any of them.
    """

    payload = getattr(response, "structured_content", response)
    if not isinstance(payload, Mapping):
        raise ValueError("Companion observation must be a mapping.")
    if payload.get("schemaVersion") != 1 or payload.get("status") != "complete":
        raise ValueError("Companion observation must be complete schema version 1.")
    identity = payload.get("saveIdentity")
    selected_nation_id = payload.get("selectedNationId")
    result = payload.get("result")
    nation = result.get("nation") if isinstance(result, Mapping) else None
    nation_id = nation.get("id") if isinstance(nation, Mapping) else None
    if not isinstance(identity, Mapping):
        raise ValueError("Companion save identity is missing.")
    if type(selected_nation_id) not in (int, str) or not selected_nation_id:
        raise ValueError("Companion selected nation ID is missing or invalid.")
    if type(nation_id) not in (int, str) or not nation_id or nation_id != selected_nation_id:
        raise ValueError("Companion selected nation is not bound to result.nation.id.")
    if not isinstance(payload.get("source"), str) or not payload["source"]:
        raise ValueError("Companion source label is missing.")
    return {
        "schemaVersion": payload["schemaVersion"],
        "status": payload["status"],
        "source": payload["source"],
        "saveIdentity": identity,
        "selectedNationId": selected_nation_id,
        "result": {"nation": nation},
    }


def _identity_from_companion_fixture(path: Path) -> dict[str, Any]:
    return _read_fixture(path)["snapshotIdentity"]


@pytest.mark.skipif(not _mcp_dependencies_available(), reason="optional MCP SDK and anyio are required")
def test_two_real_stdio_servers_enforce_fairplay_and_keep_sources_separate(tmp_path: Path) -> None:
    import anyio
    from mcp import Client
    from mcp.client.stdio import StdioServerParameters

    save_path, companion_fixture = create_mock_fixture(tmp_path / "exact")
    companion_server = REPOSITORY_ROOT / "tests" / "support" / "mock_companion_mcp.py"
    parser_server = REPOSITORY_ROOT / "tools" / "ti_parser_mcp.py"

    async def exercise_servers() -> dict[str, Any]:
        companion_params = StdioServerParameters(
            command=sys.executable,
            args=[str(companion_server), "--fixture", str(companion_fixture)],
        )
        parser_params = StdioServerParameters(
            command=sys.executable,
            args=[str(parser_server), "--profile", "fair-play"],
        )
        # Both subprocess servers remain connected concurrently for the whole probe.
        async with Client(companion_params, mode="legacy") as companion, Client(
            parser_params, mode="legacy"
        ) as parser:
            companion_tools = await companion.list_tools()
            parser_tools = await parser.list_tools()
            current = await companion.call_tool("companion_current_nation", {})
            history = await companion.call_tool("companion_recent_changes", {})

            # A nonexistent path makes the ordering observable: fair-play must
            # reject this hidden route before it tries to read or open a save.
            projection = await parser.call_tool(
                "nation-projection",
                {
                    "save_path": str(tmp_path / "must-not-be-opened.gz"),
                    "nation_name": "United States",
                    "days": 180,
                    "plan_payload": {"plans": []},
                },
            )
            hidden_goal_marker = "PRIVATE-HIDDEN-GOAL-9f02"
            hidden = await parser.call_tool(
                "raw",
                {
                    "save_path": str(tmp_path / "must-not-be-opened.gz"),
                    "goal": hidden_goal_marker,
                    "include_hidden_faction": True,
                },
            )
            # Only after both denials do we make the one permitted save lookup.
            inspection = await parser.call_tool("inspect-save", {"save_path": str(save_path)})
            return {
                "companionToolNames": [tool.name for tool in companion_tools.tools],
                "parserToolNames": [tool.name for tool in parser_tools.tools],
                "current": current,
                "history": history,
                "projection": projection,
                "hidden": hidden,
                "hiddenGoalMarker": hidden_goal_marker,
                "inspection": inspection,
            }

    results = anyio.run(exercise_servers)
    assert set(results["companionToolNames"]) == {
        "companion_current_nation",
        "companion_recent_changes",
    }
    assert set(results["parserToolNames"]) == {"capabilities", "inspect-save"}

    current = results["current"]
    history = results["history"]
    assert current.is_error is False
    assert history.is_error is False
    assert current.structured_content["source"] == "synthetic-companion-fixture"
    assert history.structured_content["source"] == "synthetic-companion-fixture"
    companion_context = normalize_companion_observation(current)
    assert companion_context["result"]["nation"]["id"] == 48
    assert companion_context["saveIdentity"] == history.structured_content["saveIdentity"]
    assert companion_context["result"]["nation"]["evidence"].endswith("no projection was calculated.")
    assert "projection" not in json.dumps(
        companion_context["result"]["nation"]["currentState"]
    ).lower()

    projection = results["projection"]
    assert projection.is_error
    assert projection.structured_content["error"]["code"] == "unsupported-analysis"
    assert "must-not-be-opened" not in json.dumps(projection.structured_content)
    assert "United States" not in projection.structured_content["error"]["message"]

    hidden = results["hidden"]
    hidden_json = json.dumps(hidden.structured_content)
    assert hidden.is_error
    assert hidden.structured_content["error"]["message"] == (
        "The request could not be completed under the selected profile."
    )
    assert results["hiddenGoalMarker"] not in hidden_json
    assert "must-not-be-opened" not in hidden_json
    assert "include_hidden_faction" not in hidden_json

    inspection = results["inspection"]
    assert inspection.is_error is False
    parser_identity = inspection.structured_content["saveIdentity"]
    companion_identity = companion_context["saveIdentity"]
    assert parser_identity["fingerprint"] == companion_identity["fingerprint"]
    assert parser_identity["gameDate"] == companion_identity["gameDate"]
    assert parser_identity["campaign"] == companion_identity["campaign"]
    assert parser_identity["playerFaction"]["id"] == companion_identity["playerFaction"]["id"]
    assert parser_identity["playerFaction"]["template"] == companion_identity["playerFaction"]["template"]
    assert "selectedNationId" not in parser_identity

    # Test-oracle comparison: this fixture's selected nation is known because
    # the harness created both sides. It is not obtained through a TI tool.
    fixture_nation_id = _read_fixture(companion_fixture)["selectedNationId"]
    assert compare_save_context(
        parser_identity,
        companion_identity,
        fixture_nation_id,
        fixture_nation_id,
        pinned=False,
    ) == {"status": "exact", "reason": "exact-fingerprint-and-context-match"}

    # A real MCP-only comparison cannot claim exactness because TI fair-play
    # intentionally does not expose selectedNationId.
    public_comparison = compare_save_context(
        parser_identity,
        companion_identity,
        None,
        fixture_nation_id,
        pinned=True,
    )
    assert public_comparison == {"status": "rejected", "reason": "selected-nation-id-missing"}


def test_fixture_correlation_supports_pinned_provisional_and_rejects_new_generation(tmp_path: Path) -> None:
    save0, companion0 = create_mock_fixture(tmp_path / "generation-0")
    from ti_parser_session import AnalysisSession

    parser_identity = AnalysisSession(save0).facts["saveIdentity"]
    exact_identity = _identity_from_companion_fixture(companion0)
    nation_id = _read_fixture(companion0)["selectedNationId"]
    assert compare_save_context(
        parser_identity,
        exact_identity,
        nation_id,
        nation_id,
        pinned=False,
    ) == {"status": "exact", "reason": "exact-fingerprint-and-context-match"}

    save_no_hash, companion_no_hash = create_mock_fixture(
        tmp_path / "provisional", include_fingerprint=False
    )
    del save_no_hash
    no_hash_identity = _identity_from_companion_fixture(companion_no_hash)
    provisional = compare_save_context(
        parser_identity,
        no_hash_identity,
        nation_id,
        nation_id,
        pinned=True,
    )
    assert provisional == {
        "status": "provisional",
        "reason": "pinned-context-match-without-exact-fingerprint",
    }
    assert compare_save_context(
        parser_identity,
        no_hash_identity,
        nation_id,
        nation_id,
        pinned=False,
    ) == {"status": "rejected", "reason": "pin-required-for-provisional-match"}

    save1, companion1 = create_mock_fixture(tmp_path / "generation-1", generation=1)
    assert save1.read_bytes() != (tmp_path / "generation-0" / "synthetic-campaign.gz").read_bytes()
    changed_generation_identity = _identity_from_companion_fixture(companion1)
    mismatch = compare_save_context(
        parser_identity,
        changed_generation_identity,
        nation_id,
        nation_id,
        pinned=True,
    )
    assert mismatch == {"status": "rejected", "reason": "fingerprint-mismatch"}


def test_companion_normalizer_rejects_missing_or_unbound_selected_nation(tmp_path: Path) -> None:
    _save_path, fixture_path = create_mock_fixture(tmp_path)
    fixture = _read_fixture(fixture_path)
    payload = {
        "schemaVersion": 1,
        "status": "complete",
        "source": "synthetic-companion-fixture",
        "saveIdentity": fixture["snapshotIdentity"],
        "selectedNationId": fixture["selectedNationId"],
        "result": {"nation": fixture["nation"]},
    }

    normalized = normalize_companion_observation(payload)
    assert normalized["saveIdentity"] == fixture["snapshotIdentity"]
    assert normalized["selectedNationId"] == 48
    assert normalized["result"]["nation"]["id"] == 48

    without_selected_id = dict(payload)
    without_selected_id.pop("selectedNationId")
    with pytest.raises(ValueError, match="selected nation ID is missing"):
        normalize_companion_observation(without_selected_id)

    mismatched = dict(payload)
    mismatched["selectedNationId"] = 49
    with pytest.raises(ValueError, match="not bound"):
        normalize_companion_observation(mismatched)


def test_acceptance_case_file_records_routing_evidence_separately() -> None:
    cases_path = REPOSITORY_ROOT / "tests" / "support" / "fairplay_acceptance_cases.json"
    data = json.loads(cases_path.read_text(encoding="utf-8"))
    assert data["schemaVersion"] == 1
    assert data["automationEvidence"]["kind"] == "deterministic MCP client calls"
    assert data["automationEvidence"]["llmRoutingStatus"] == "pending"
    assert {case["failure_category"] for case in data["cases"]} >= {
        "routing",
        "correlation",
        "policy",
        "mechanics",
    }
    assert len(data["cases"]) == 6


def test_mock_server_and_fixture_stay_outside_the_runtime_distribution() -> None:
    from build_beta_distribution import _is_distribution_path

    assert not _is_distribution_path("tests/support/mock_companion_mcp.py")
    assert not _is_distribution_path("tests/support/fairplay_acceptance_cases.json")
