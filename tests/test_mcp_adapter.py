"""Optional MCP adapter contract, cache, and stdio transport tests."""

from __future__ import annotations

import gzip
import json
import os
import subprocess
import sys
import threading
import time
from copy import deepcopy
from pathlib import Path

import pytest

pytest.importorskip("mcp")
anyio = pytest.importorskip("anyio")
jsonschema = pytest.importorskip("jsonschema")

from mcp import Client  # noqa: E402
from mcp.client.stdio import StdioServerParameters  # noqa: E402

import ti_parser_mcp as adapter  # noqa: E402
from ti_parser_errors import SaveIntegrityError  # noqa: E402
from ti_parser_config import (  # noqa: E402
    HAB_MONTHLY_RESOURCES,
    HAB_PLAN_FOCUS_CHOICES,
    ORG_PLAN_FOCUS_CHOICES,
    PROJECT_ANALYSIS_SORT_CHOICES,
    RESEARCH_PLAN_MODE_CHOICES,
    SHIP_PLAN_ROLE_CHOICES,
)
from ti_parser_registry import ANALYSES, get_input_schema  # noqa: E402
from ti_parser_schema import (  # noqa: E402
    get_analysis_output_schema,
    get_capabilities_output_schema,
    get_tool_error_schema,
)


def _save_identity(path: Path, *, unresolved_player: bool = False) -> dict:
    player = (
        {"status": "unresolved", "error": {"code": "player-faction-unresolved", "message": "fixture"}}
        if unresolved_player
        else {"status": "resolved", "id": 42, "template": "ResistCouncil", "display": "Resistance"}
    )
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
        "playerFaction": player,
    }


def _fake_envelope(
    analysis: str,
    path: Path,
    *,
    status: str = "complete",
    allow_unverified: bool = False,
    unresolved_player: bool = False,
) -> dict:
    compatibility_status = "unverified" if unresolved_player or status == "deferred" else "verified"
    compatibility = {
        "schemaVersion": 1,
        "status": compatibility_status,
        "reasons": [] if compatibility_status == "verified" else [{"code": "fixture-unverified"}],
        "unverifiedAllowed": allow_unverified,
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
    payload = {
        "schemaVersion": 1,
        "parserVersion": "0.0.0-test",
        "analysis": analysis,
        "saveIdentity": _save_identity(path, unresolved_player=unresolved_player),
        "compatibility": compatibility,
        "status": status,
        "result": {"arguments": {}},
    }
    if status == "incomplete":
        payload.pop("result")
        payload["missingDependencies"] = [{"kind": "catalog", "name": "fixture"}]
    elif status == "deferred":
        payload.pop("result")
        payload["error"] = {"code": "unverified-compatibility", "message": "fixture"}
    elif status == "error":
        payload.pop("result")
        payload["error"] = {"code": "invalid-arguments", "message": "fixture"}
    return payload


class _FakeSession:
    instances: list["_FakeSession"] = []
    responses: list[dict] = []
    raised: BaseException | None = None
    active = 0
    maximum_active = 0
    active_lock = threading.Lock()

    def __init__(self, path: Path):
        self.path = Path(path)
        type(self).instances.append(self)

    def run(self, analysis: str, *, allow_unverified: object = False, **kwargs):
        if type(self).raised is not None:
            raise type(self).raised
        with type(self).active_lock:
            type(self).active += 1
            type(self).maximum_active = max(type(self).maximum_active, type(self).active)
        try:
            time.sleep(0.01)
            if type(self).responses:
                return type(self).responses.pop(0)
            payload = _fake_envelope(
                analysis,
                self.path,
                allow_unverified=allow_unverified is True,
            )
            payload["result"]["arguments"] = kwargs
            return payload
        finally:
            with type(self).active_lock:
                type(self).active -= 1


@pytest.fixture
def fake_adapter(monkeypatch):
    _FakeSession.instances = []
    _FakeSession.responses = []
    _FakeSession.raised = None
    _FakeSession.active = 0
    _FakeSession.maximum_active = 0
    monkeypatch.setattr(adapter, "AnalysisSession", _FakeSession)
    return adapter


def _save(tmp_path: Path, name: str = "save.gz", contents: bytes = b"save") -> Path:
    path = tmp_path / name
    path.write_bytes(contents)
    return path


def _make_player_faction_unresolved(save: Path) -> None:
    with gzip.open(save, "rt", encoding="utf-8") as handle:
        data = json.load(handle)
    players = data["gamestates"]["TIPlayerState"]
    player = next(row["Value"] for row in players if row["Value"].get("isAI") is False)
    player["faction"] = {"value": 987654321}
    with gzip.open(save, "wt", encoding="utf-8") as handle:
        json.dump(data, handle)


def _validate_result(result, schema: dict) -> None:
    assert json.loads(result.content[0].text) == result.structured_content
    jsonschema.validate(result.structured_content, schema)


async def _call(server, name: str, arguments: dict | None = None):
    async with Client(server, mode="legacy") as client:
        return await client.call_tool(name, arguments or {})


async def _list_tools(server):
    async with Client(server, mode="legacy") as client:
        return await client.list_tools()


def test_import_and_inprocess_protocol_expose_registry_routes(fake_adapter, tmp_path):
    server = fake_adapter.create_server()
    listed = anyio.run(_list_tools, server)
    by_name = {tool.name: tool for tool in listed.tools}

    expected = {entry.command for entry in fake_adapter._exposed_entries()} | {"capabilities"}
    assert set(by_name) == expected
    assert "ai-fleet-diagnostics" not in by_name
    assert "raw" not in by_name
    assert "catalog-verify" not in by_name

    for name, tool in by_name.items():
        jsonschema.Draft202012Validator.check_schema(tool.input_schema)
        assert tool.output_schema is not None
        jsonschema.Draft202012Validator.check_schema(tool.output_schema)
        expected_output_schema = (
            get_capabilities_output_schema() if name == "capabilities" else get_analysis_output_schema()
        )
        assert tool.output_schema == expected_output_schema

    projection = by_name["nation-projection"].input_schema
    assert projection["properties"]["save_path"] == {"type": "string"}
    assert projection["properties"]["plan_payload"]["anyOf"] == [{"type": "object"}, {"type": "null"}]
    assert projection["properties"]["checkpoints"]["anyOf"][0]["items"] == {"type": "integer"}
    assert projection["additionalProperties"] is False
    assert set(projection["required"]) == {"save_path", "nation_name", "days"}
    assert "simulation:" in by_name["nation-projection"].description
    assert by_name["org-plan"].input_schema["properties"]["focus"]["enum"] == list(ORG_PLAN_FOCUS_CHOICES)
    assert by_name["hab-plan"].input_schema["properties"]["focus"]["enum"] == list(HAB_PLAN_FOCUS_CHOICES)
    assert by_name["ship-plan"].input_schema["properties"]["role"]["enum"] == list(SHIP_PLAN_ROLE_CHOICES)
    assert by_name["project-analysis"].input_schema["properties"]["sort_axis"]["enum"] == list(
        PROJECT_ANALYSIS_SORT_CHOICES
    )
    assert by_name["project-analysis"].input_schema["properties"]["slot"]["anyOf"] == [
        {"type": "integer", "enum": [3, 4, 5]},
        {"type": "null"},
    ]
    assert by_name["research-plan"].input_schema["properties"]["mode"]["enum"] == list(
        RESEARCH_PLAN_MODE_CHOICES
    )
    assert by_name["topbar"].input_schema["properties"]["forecast_resource"]["anyOf"][0]["enum"] == list(
        HAB_MONTHLY_RESOURCES
    )

    # Each application tool exposes the same public analysis schema held by
    # the registry after only the two MCP-owned transport fields are added.
    for entry in fake_adapter._exposed_entries():
        public_schema = get_input_schema(entry.command)
        listed_schema = deepcopy(by_name[entry.command].input_schema)
        listed_schema["properties"].pop("save_path")
        if entry.allows_explicit_unverified_consent:
            listed_schema["properties"].pop("allow_unverified")
        listed_schema["required"].remove("save_path")
        assert listed_schema == public_schema
        fresh_schema = get_input_schema(entry.command)
        assert fresh_schema == public_schema
        assert fresh_schema is not public_schema
        assert fresh_schema["properties"] is not public_schema["properties"]
        if public_schema["properties"]:
            public_schema["properties"].clear()
            assert fresh_schema["properties"] == listed_schema["properties"]

    path = _save(tmp_path)
    result = anyio.run(_call, server, "topbar", {"save_path": str(path), "allow_unverified": True})
    assert result.is_error is False
    assert json.loads(result.content[0].text) == result.structured_content
    assert result.structured_content["saveIdentity"]["fingerprint"]["value"] == "a" * 64
    jsonschema.validate(result.structured_content, by_name["topbar"].output_schema)


def test_capabilities_is_save_free_and_contains_only_mcp_metadata(fake_adapter, tmp_path):
    server = fake_adapter.create_server()
    result = anyio.run(_call, server, "capabilities", {})
    payload = result.structured_content
    listed = {tool.name: tool for tool in anyio.run(_list_tools, server).tools}
    names = {row["command"] for row in payload["analyses"]}
    assert result.is_error is False
    assert names == {entry.command for entry in fake_adapter._exposed_entries()}
    assert "raw" not in names
    assert all("inputSchema" in row for row in payload["analyses"])
    assert not _FakeSession.instances
    jsonschema.validate(payload, listed["capabilities"].output_schema)
    assert all(row["inputSchema"] == listed[row["command"]].input_schema for row in payload["analyses"])
    invalid = anyio.run(_call, server, "capabilities", {"unexpected": True})
    assert invalid.is_error is True
    _validate_result(invalid, listed["capabilities"].output_schema)


def test_output_schemas_reject_malformed_application_and_inventory_envelopes():
    analysis_schema = get_analysis_output_schema()
    capabilities_schema = get_capabilities_output_schema()
    error_schema = get_tool_error_schema()
    good = _fake_envelope("topbar", Path("fixture.gz"))
    jsonschema.validate(good, analysis_schema)
    jsonschema.validate(
        {"schemaVersion": 1, "status": "error", "error": {"code": "save-unavailable", "message": "missing"}},
        error_schema,
    )

    malformed_identity = deepcopy(good)
    malformed_identity["saveIdentity"]["fingerprint"]["value"] = "too-short"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(malformed_identity, analysis_schema)

    malformed_status = deepcopy(good)
    malformed_status["status"] = "partial-but-unknown"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(malformed_status, analysis_schema)

    pre_session_with_identity = {
        "schemaVersion": 1,
        "status": "error",
        "saveIdentity": good["saveIdentity"],
        "error": {"code": "save-unavailable", "message": "missing"},
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(pre_session_with_identity, error_schema)

    malformed_inventory = {
        "schemaVersion": 1,
        "parserVersion": "0.0.0-test",
        "analyses": [],
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(malformed_inventory, capabilities_schema)


def test_cache_reuses_content_generation_and_evicts_lru(fake_adapter, tmp_path):
    server = fake_adapter.create_server()
    first = _save(tmp_path, "a.gz", b"a")
    second = _save(tmp_path, "b.gz", b"b")
    third = _save(tmp_path, "c.gz", b"c")

    for path in (first, second, first, third, first, second):
        result = anyio.run(_call, server, "topbar", {"save_path": str(path), "allow_unverified": True})
        assert result.structured_content["status"] == "complete"
    assert len(_FakeSession.instances) == 4  # a, b, c, then b after LRU eviction

    stamp = first.stat().st_mtime_ns
    first.write_bytes(b"z")
    os.utime(first, ns=(stamp, stamp))
    anyio.run(_call, server, "topbar", {"save_path": str(first), "allow_unverified": True})
    assert len(_FakeSession.instances) == 5


def test_registry_policy_and_live_handler_annotations_drive_tool_schema(fake_adapter, monkeypatch):
    server = fake_adapter.create_server()
    listed = anyio.run(_list_tools, server)
    expected = {
        entry.command
        for entry in ANALYSES
        if entry.routing_class in {"bootstrap", "primary"}
    }
    assert {tool.name for tool in listed.tools if tool.name != "capabilities"} == expected

    import ti_parser_application as application

    def changed_handler(indexed, templates_dir=None, injected: str | None = None):
        del indexed, templates_dir, injected
        return {}

    monkeypatch.setitem(application.HANDLERS, "topbar", changed_handler)
    changed = fake_adapter.create_server()
    changed_tools = {tool.name: tool for tool in anyio.run(_list_tools, changed).tools}
    assert changed_tools["topbar"].input_schema["properties"]["injected"] == {
        "anyOf": [{"type": "string"}, {"type": "null"}],
        "default": None,
    }


def test_changed_during_session_construction_is_structured_and_uncached(fake_adapter, monkeypatch, tmp_path):
    server = fake_adapter.create_server()
    path = _save(tmp_path)
    values = iter(("before", "after"))
    monkeypatch.setattr(fake_adapter, "_sha256", lambda _path: next(values))

    result = anyio.run(_call, server, "topbar", {"save_path": str(path), "allow_unverified": True})
    assert result.is_error is True
    assert result.structured_content["error"]["code"] == "save-changed-during-read"
    assert "saveIdentity" not in result.structured_content
    assert not server._ti_parser_session_cache.entries


def test_error_statuses_and_pre_session_failures_keep_their_distinction(fake_adapter, tmp_path):
    path = _save(tmp_path)
    fake_adapter_session = _FakeSession
    fake_adapter_session.responses = [
        _fake_envelope("topbar", path, status="deferred"),
        _fake_envelope("topbar", path, status="incomplete"),
        _fake_envelope("topbar", path, status="error"),
    ]
    server = fake_adapter.create_server()

    deferred = anyio.run(_call, server, "topbar", {"save_path": str(path)})
    incomplete = anyio.run(_call, server, "topbar", {"save_path": str(path)})
    error = anyio.run(_call, server, "topbar", {"save_path": str(path)})
    missing = anyio.run(_call, server, "topbar", {"save_path": str(tmp_path / "missing.gz")})

    assert deferred.is_error is False and deferred.structured_content["status"] == "deferred"
    assert incomplete.is_error is False and incomplete.structured_content["status"] == "incomplete"
    assert error.is_error is True and error.structured_content["status"] == "error"
    assert missing.is_error is True
    assert "saveIdentity" not in missing.structured_content
    for result in (deferred, incomplete, error):
        jsonschema.validate(result.structured_content, get_analysis_output_schema())
    jsonschema.validate(missing.structured_content, get_tool_error_schema())
    jsonschema.validate(missing.structured_content, get_analysis_output_schema())
    assert json.loads(missing.content[0].text) == missing.structured_content


def test_partial_projection_envelope_is_forwarded_without_reshaping(fake_adapter, tmp_path):
    path = _save(tmp_path)
    payload = _fake_envelope(
        "nation-projection", path, status="incomplete", allow_unverified=True
    )
    payload["missingDependencies"] = [{"kind": "market", "name": "price"}]
    payload["result"] = {
        "plans": [{
            "status": "incomplete",
            "scopeStatus": {"worldMarket": {"status": "incomplete"}},
            "authoritativeFinalState": {"controlPoints": {"raw": [1, 0, 0]}},
        }],
        "comparison": {"excludedIncompletePlans": ["fixture"]},
    }
    _FakeSession.responses = [payload]
    result = anyio.run(
        _call,
        fake_adapter.create_server(),
        "nation-projection",
        {"save_path": str(path), "allow_unverified": True, "nation_name": "KOR", "days": 1},
    )
    assert result.is_error is False
    assert result.structured_content == payload
    assert json.loads(result.content[0].text) == payload
    jsonschema.validate(result.structured_content, get_analysis_output_schema())


def test_constructor_expected_errors_are_structured_but_unexpected_errors_propagate(fake_adapter, monkeypatch, tmp_path):
    path = _save(tmp_path)

    class InvalidSave:
        def __init__(self, _path):
            raise SaveIntegrityError("bad fixture", code="save-structure-invalid")

    monkeypatch.setattr(fake_adapter, "AnalysisSession", InvalidSave)
    server = fake_adapter.create_server()
    invalid = anyio.run(_call, server, "topbar", {"save_path": str(path), "allow_unverified": True})
    assert invalid.is_error is True
    assert invalid.structured_content["error"]["code"] == "save-structure-invalid"
    assert not server._ti_parser_session_cache.entries

    class BrokenConstruction:
        def __init__(self, _path):
            raise ValueError("programming bug")

    monkeypatch.setattr(fake_adapter, "AnalysisSession", BrokenConstruction)

    async def broken_cache_call():
        return await fake_adapter.SessionCache().run(
            path,
            "topbar",
            allow_unverified=True,
            kwargs={},
        )

    with pytest.raises(ValueError, match="programming bug"):
        anyio.run(broken_cache_call)

    class BrokenRun:
        def __init__(self, _path):
            pass

        def run(self, *_args, **_kwargs):
            raise RuntimeError("programming bug")

    monkeypatch.setattr(fake_adapter, "AnalysisSession", BrokenRun)

    async def raising_call():
        return await fake_adapter.SessionCache().run(
            path,
            "topbar",
            allow_unverified=True,
            kwargs={},
        )

    with pytest.raises(RuntimeError, match="programming bug"):
        anyio.run(raising_call)


def test_transport_rejects_consent_and_projection_payload_shape(fake_adapter, tmp_path):
    server = fake_adapter.create_server()
    path = _save(tmp_path)
    inspect_consent = anyio.run(_call, server, "inspect-save", {"save_path": str(path), "allow_unverified": False})
    scalar_plan = anyio.run(
        _call,
        server,
        "nation-projection",
        {"save_path": str(path), "allow_unverified": True, "nation_name": "KOR", "days": 1, "plan_payload": "bad"},
    )
    list_plan = anyio.run(
        _call,
        server,
        "nation-projection",
        {"save_path": str(path), "allow_unverified": True, "nation_name": "KOR", "days": 1, "plan_payload": []},
    )
    assert inspect_consent.is_error is True
    assert scalar_plan.is_error is True and scalar_plan.structured_content["error"]["code"] == "invalid-arguments"
    assert list_plan.is_error is True and list_plan.structured_content["error"]["code"] == "invalid-arguments"


def test_server_lock_serializes_concurrent_session_calls(fake_adapter, tmp_path):
    server = fake_adapter.create_server()
    path = _save(tmp_path)

    async def group():
        # A task group expresses two in-flight protocol calls portably across
        # the AnyIO versions supported by the optional SDK environment.
        async with anyio.create_task_group() as tg:
            tg.start_soon(_call, server, "topbar", {"save_path": str(path), "allow_unverified": True})
            tg.start_soon(_call, server, "topbar", {"save_path": str(path), "allow_unverified": True})

    anyio.run(group)
    assert _FakeSession.maximum_active == 1


def test_real_application_validation_keeps_save_context(tmp_path, monkeypatch):
    from tests.test_application_api import _save as real_save

    save = real_save(tmp_path)
    def forbid_process(*_args, **_kwargs):
        raise AssertionError("MCP analysis must call the application API directly")

    monkeypatch.setattr(subprocess, "run", forbid_process)
    monkeypatch.setattr(subprocess, "Popen", forbid_process)
    server = adapter.create_server()
    tool_schemas = {tool.name: tool.output_schema for tool in anyio.run(_list_tools, server).tools}
    inspected = anyio.run(_call, server, "inspect-save", {"save_path": str(save)})
    deferred = anyio.run(_call, server, "topbar", {"save_path": str(save)})
    calculated = anyio.run(
        _call, server, "topbar", {"save_path": str(save), "allow_unverified": True}
    )
    assert deferred.structured_content["status"] == "deferred"
    assert calculated.structured_content["status"] == "complete"
    assert inspected.structured_content["saveIdentity"] == calculated.structured_content["saveIdentity"]
    _validate_result(inspected, tool_schemas["inspect-save"])
    _validate_result(deferred, tool_schemas["topbar"])
    _validate_result(calculated, tool_schemas["topbar"])
    invalid_argument = anyio.run(
        _call,
        server,
        "topbar",
        {"save_path": str(save), "allow_unverified": True, "include_details": "yes"},
    )
    invalid_consent = anyio.run(
        _call,
        server,
        "topbar",
        {"save_path": str(save), "allow_unverified": "yes"},
    )
    assert invalid_argument.is_error is True
    assert invalid_argument.structured_content["error"]["code"] == "invalid-arguments"
    assert "saveIdentity" in invalid_argument.structured_content
    _validate_result(invalid_argument, tool_schemas["topbar"])
    assert invalid_consent.is_error is True
    assert invalid_consent.structured_content["error"]["code"] == "invalid-arguments"
    assert "saveIdentity" in invalid_consent.structured_content
    _validate_result(invalid_consent, tool_schemas["topbar"])


def test_real_unresolved_player_and_compatibility_failure_match_output_schema(tmp_path, monkeypatch):
    from tests.test_application_api import _save as real_save
    from ti_parser_compatibility import CompatibilityRegistryError
    import ti_parser_session

    unresolved_root = tmp_path / "unresolved"
    unresolved_root.mkdir()
    unresolved_save = real_save(unresolved_root)
    _make_player_faction_unresolved(unresolved_save)
    server = adapter.create_server()
    tool_schemas = {tool.name: tool.output_schema for tool in anyio.run(_list_tools, server).tools}
    unresolved = anyio.run(_call, server, "inspect-save", {"save_path": str(unresolved_save)})
    assert unresolved.structured_content["saveIdentity"]["playerFaction"]["status"] == "unresolved"
    _validate_result(unresolved, tool_schemas["inspect-save"])

    def broken_registry(_indexed):
        raise CompatibilityRegistryError("compatibility-registry-invalid", "broken registry fixture")

    monkeypatch.setattr(ti_parser_session, "assess_compatibility", broken_registry)
    failure_root = tmp_path / "compatibility-error"
    failure_root.mkdir()
    failed_save = real_save(failure_root)
    failed = anyio.run(
        _call,
        server,
        "topbar",
        {"save_path": str(failed_save), "allow_unverified": True},
    )
    assert failed.is_error is False
    assert failed.structured_content["status"] == "incomplete"
    assert failed.structured_content["error"]["code"] == "compatibility-registry-invalid"
    _validate_result(failed, tool_schemas["topbar"])


def test_real_stdio_server_lists_capabilities(tmp_path):
    del tmp_path
    script = Path(__file__).resolve().parents[1] / "tools" / "ti_parser_mcp.py"

    async def run_stdio():
        params = StdioServerParameters(command=sys.executable, args=[str(script)])
        async with Client(params, mode="legacy") as client:
            listed = await client.list_tools()
            result = await client.call_tool("capabilities", {})
            return listed, result

    listed, result = anyio.run(run_stdio)
    assert "capabilities" in {tool.name for tool in listed.tools}
    assert result.is_error is False
    assert result.structured_content["analyses"]
