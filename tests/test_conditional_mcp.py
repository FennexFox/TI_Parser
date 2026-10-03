"""Conditional-profile MCP inventory and visible-context adapter tests."""

from __future__ import annotations

import json
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("mcp")
anyio = pytest.importorskip("anyio")
jsonschema = pytest.importorskip("jsonschema")

from mcp import Client  # noqa: E402

import ti_parser_mcp as adapter  # noqa: E402
from ti_parser_fairplay import exposed_entries  # noqa: E402


def _identity() -> dict:
    return {
        "schemaVersion": 1,
        "fingerprint": {
            "algorithm": "sha256-canonical-save-json-v1",
            "value": "a" * 64,
        },
        "gameDate": {"year": 2035, "month": 1, "day": 10},
        "scenario": "ModernScenario",
        "latestSaveVersion": "test-version",
        "campaignStartVersion": None,
        "campaign": {"realWorldCampaignStart": None},
        "playerFaction": {
            "status": "resolved",
            "id": 42,
            "template": "ResistCouncil",
            "display": "Resistance",
        },
    }


def _compatibility() -> dict:
    return {
        "schemaVersion": 1,
        "status": "verified",
        "reasons": [],
        "unverifiedAllowed": False,
        "version": {"latestSaveVersion": "test-version", "observations": []},
        "scenario": {"name": "ModernScenario", "observations": []},
        "modEvidence": {},
        "catalogFingerprint": "b" * 64,
        "runtimeAssets": [],
        "registry": {
            "filename": "compatibility_registry.json",
            "schemaVersion": 1,
            "sha256": "c" * 64,
            "entryCount": 1,
            "matchedEvidence": {},
        },
    }


class _ConditionalSession:
    instances: list["_ConditionalSession"] = []

    def __init__(self, path: Path):
        self.path = Path(path)
        nation_id = 77
        point_ids = [101, 102, 103, 104, 105, 106]
        id_index = {
            nation_id: (
                nation_id,
                "TINationState",
                {"controlPoints": [{"value": point_id} for point_id in point_ids]},
            )
        }
        for position, point_id in enumerate(point_ids):
            id_index[point_id] = (
                point_id,
                "TIControlPointState",
                {
                    "positionInNation": position,
                    "faction": {"value": 42},
                    "nation": {"value": nation_id},
                },
            )
        self.indexed = SimpleNamespace(id_index=id_index)
        type(self).instances.append(self)

    def inspect(self) -> dict:
        return {"saveIdentity": _identity(), "compatibility": _compatibility()}


class _FakeConditionalApplication:
    last_instance: "_FakeConditionalApplication | None" = None

    def __init__(self, *, inspect_save):
        self.inspect_save = inspect_save
        self.last_inspection = None
        type(self).last_instance = self

    def tool_contracts(self) -> dict:
        envelope = {
            "type": "object",
            "required": ["schemaVersion", "status"],
            "properties": {
                "schemaVersion": {"const": 1},
                "status": {"type": "string"},
            },
            "additionalProperties": True,
        }
        return {
            "register-visible-context": {
                "description": "Register an explicit visible context.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "document": {"type": "object"},
                        "save_path": {"type": "string"},
                        "pinned": {"type": "boolean", "default": False},
                    },
                    "required": ["document", "save_path"],
                    "additionalProperties": False,
                },
                "outputSchema": envelope,
            },
            "conditional-nation-projection": {
                "description": "Project declared plans as conditional scenarios.",
                "inputSchema": {"type": "object", "additionalProperties": False},
                "outputSchema": envelope,
            },
            "verify-visible-generation": {
                "description": "Verify the generation for registered visible context.",
                "inputSchema": {"type": "object", "additionalProperties": False},
                "outputSchema": envelope,
            },
        }

    def capabilities(self) -> dict:
        return {
            "schemaVersion": 1,
            "profile": "conditional",
            "policy": {"outcomes": "scenario-only"},
            "tools": [
                "register-visible-context",
                "conditional-nation-projection",
                "verify-visible-generation",
            ],
        }

    def capabilities_output_schema(self) -> dict:
        return {"type": "object", "properties": {"schemaVersion": {"const": 1},
                "profile": {"const": "conditional"}, "policy": {"type": "object"},
                "tools": {"type": "array", "items": {"type": "string"}}},
                "required": ["schemaVersion", "profile", "policy", "tools"], "additionalProperties": False}

    async def call(self, name: str, arguments: dict) -> dict:
        if name == "register-visible-context":
            self.last_inspection = await self.inspect_save(
                arguments["save_path"], nation_id=arguments["document"]["nationId"]
            )
            return {"schemaVersion": 1, "status": "complete", "receipt": "opaque"}
        if name == "conditional-nation-projection":
            return {"schemaVersion": 1, "status": "complete", "scenarios": []}
        if name == "verify-visible-generation":
            return {"schemaVersion": 1, "status": "complete", "verified": True}
        return {"schemaVersion": 1, "status": "error", "error": {"code": "request-rejected"}}


@pytest.fixture
def conditional_server(monkeypatch):
    _ConditionalSession.instances = []
    _FakeConditionalApplication.last_instance = None
    monkeypatch.setattr(adapter, "AnalysisSession", _ConditionalSession)
    stub_module = types.ModuleType("ti_parser_conditional_application")
    stub_module.ConditionalApplication = _FakeConditionalApplication
    monkeypatch.setitem(sys.modules, "ti_parser_conditional_application", stub_module)
    return adapter.create_server(profile="conditional")


async def _call(server, name: str, arguments: dict | None = None):
    async with Client(server, mode="legacy") as client:
        return await client.call_tool(name, arguments or {})


async def _list_tools(server):
    async with Client(server, mode="legacy") as client:
        return await client.list_tools()


def test_conditional_inventory_is_isolated_and_schemas_are_valid(conditional_server):
    listed = anyio.run(_list_tools, conditional_server)
    by_name = {tool.name: tool for tool in listed.tools}
    expected = {
        "capabilities",
        "inspect-save",
        "register-visible-context",
        "conditional-nation-projection",
        "verify-visible-generation",
    }
    assert set(by_name) == expected
    for tool in by_name.values():
        jsonschema.Draft202012Validator.check_schema(tool.input_schema)
        assert tool.output_schema is not None
        jsonschema.Draft202012Validator.check_schema(tool.output_schema)
    assert "Companion" in conditional_server.instructions
    assert "never be presented as observed save truth" in conditional_server.instructions

    capabilities = anyio.run(_call, conditional_server, "capabilities")
    assert capabilities.is_error is False
    jsonschema.validate(capabilities.structured_content, by_name["capabilities"].output_schema)
    assert capabilities.structured_content["profile"] == "conditional"
    assert capabilities.structured_content["tools"] == [
        "inspect-save",
        "register-visible-context",
        "conditional-nation-projection",
        "verify-visible-generation",
    ]
    assert not _ConditionalSession.instances


def test_conditional_excluded_routes_are_denied_without_path_normalization(
    conditional_server, monkeypatch, tmp_path
):
    normalized: list[str] = []
    original_normalize = adapter._normalize_save_path

    def track_normalize(value):
        normalized.append(value)
        return original_normalize(value)

    monkeypatch.setattr(adapter, "_normalize_save_path", track_normalize)
    secret_path = str(tmp_path / "hidden-campaign.gz")
    for name in (
        "raw",
        "types",
        "nation-projection",
        "analyze",
        "ai-fleet-diagnostics",
        "catalog-verify",
    ):
        result = anyio.run(
            _call,
            conditional_server,
            name,
            {"save_path": secret_path, "nation_name": "Hidden nation", "days": 180},
        )
        assert result.is_error
        rendered = json.dumps(result.structured_content)
        assert "hidden-campaign" not in rendered
        assert "Hidden nation" not in rendered
    assert not normalized
    assert not _ConditionalSession.instances


def test_conditional_inspection_is_sanitized_and_registration_binds_visible_subject(
    conditional_server, monkeypatch, tmp_path
):
    import ti_parser_fairplay

    monkeypatch.setattr(
        ti_parser_fairplay,
        "_resolve_owned_subject",
        lambda _session, nation_id: (nation_id, _identity()),
    )
    save_path = tmp_path / "pinned-save.gz"
    save_path.write_bytes(b"fixture save bytes")

    inspected = anyio.run(
        _call, conditional_server, "inspect-save", {"save_path": str(save_path)}
    )
    inspect_schema = next(
        tool.output_schema
        for tool in anyio.run(_list_tools, conditional_server).tools
        if tool.name == "inspect-save"
    )
    jsonschema.validate(inspected.structured_content, inspect_schema)
    assert inspected.is_error is False
    assert "modEvidence" not in inspected.structured_content["compatibility"]
    assert len(_ConditionalSession.instances) == 1

    registered = anyio.run(
        _call,
        conditional_server,
        "register-visible-context",
        {
            "document": {"nationId": 77},
            "save_path": str(save_path),
            "pinned": True,
        },
    )
    assert registered.is_error is False
    bound = _FakeConditionalApplication.last_instance.last_inspection
    assert bound["status"] == "complete"
    assert bound["saveIdentity"] == _identity()
    assert bound["subject"] == {
        "nationId": 77,
        "playerFactionId": 42,
        "controlPointIds": [101, 102, 103, 104, 105, 106],
    }
    assert len(_ConditionalSession.instances) == 1


def test_default_and_fair_play_inventories_remain_unchanged():
    default_names = {entry.command for entry in exposed_entries("default")}
    fair_play_names = {entry.command for entry in exposed_entries("fair-play")}
    assert default_names == {entry.command for entry in adapter._exposed_entries()}
    assert fair_play_names == {"inspect-save"}
    assert "conditional-nation-projection" not in default_names
    assert "conditional-nation-projection" not in fair_play_names

    default_server = adapter.create_server()
    fair_play_server = adapter.create_server(profile="fair-play")
    assert {tool.name for tool in anyio.run(_list_tools, default_server).tools} == (
        default_names | {"capabilities"}
    )
    assert {tool.name for tool in anyio.run(_list_tools, fair_play_server).tools} == {
        "inspect-save",
        "capabilities",
    }
