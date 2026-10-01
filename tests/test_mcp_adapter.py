"""Optional MCP adapter contract, cache, and stdio transport tests."""

from __future__ import annotations

import json
import os
import sys
import threading
import time
from pathlib import Path

import pytest

pytest.importorskip("mcp")
anyio = pytest.importorskip("anyio")

from mcp import Client  # noqa: E402
from mcp.client.stdio import StdioServerParameters  # noqa: E402

import ti_parser_mcp as adapter  # noqa: E402
from ti_parser_errors import SaveIntegrityError  # noqa: E402
from ti_parser_registry import ANALYSES  # noqa: E402


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
            return {
                "schemaVersion": 1,
                "parserVersion": "test",
                "analysis": analysis,
                "saveIdentity": {"path": str(self.path)},
                "compatibility": {"status": "verified", "unverifiedAllowed": allow_unverified is True},
                "status": "complete",
                "result": {"arguments": kwargs},
            }
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

    projection = by_name["nation-projection"].input_schema
    assert projection["properties"]["save_path"] == {"type": "string"}
    assert projection["properties"]["plan_payload"]["anyOf"] == [{"type": "object"}, {"type": "null"}]
    assert projection["properties"]["checkpoints"]["anyOf"][0]["items"] == {"type": "integer"}
    assert projection["additionalProperties"] is False
    assert set(projection["required"]) == {"save_path", "nation_name", "days"}
    assert "simulation:" in by_name["nation-projection"].description

    path = _save(tmp_path)
    result = anyio.run(_call, server, "topbar", {"save_path": str(path), "allow_unverified": True})
    assert result.is_error is False
    assert json.loads(result.content[0].text) == result.structured_content
    assert result.structured_content["saveIdentity"]["path"] == str(path.resolve())


def test_capabilities_is_save_free_and_contains_only_mcp_metadata(fake_adapter, tmp_path):
    server = fake_adapter.create_server()
    result = anyio.run(_call, server, "capabilities", {})
    payload = result.structured_content
    names = {row["command"] for row in payload["analyses"]}
    assert result.is_error is False
    assert names == {entry.command for entry in fake_adapter._exposed_entries()}
    assert "raw" not in names
    assert all("inputSchema" in row for row in payload["analyses"])
    assert not _FakeSession.instances


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
        {"schemaVersion": 1, "analysis": "topbar", "status": "deferred", "error": {"code": "unverified"}},
        {"schemaVersion": 1, "analysis": "topbar", "status": "incomplete", "missingDependencies": [{"kind": "catalog"}]},
        {"schemaVersion": 1, "analysis": "topbar", "status": "error", "error": {"code": "invalid-arguments"}},
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


def test_partial_projection_envelope_is_forwarded_without_reshaping(fake_adapter, tmp_path):
    path = _save(tmp_path)
    payload = {
        "schemaVersion": 1,
        "parserVersion": "test",
        "analysis": "nation-projection",
        "saveIdentity": {"path": str(path.resolve()), "fingerprint": "fixture"},
        "compatibility": {"status": "verified", "unverifiedAllowed": True},
        "status": "incomplete",
        "missingDependencies": [{"kind": "market", "name": "price"}],
        "result": {
            "plans": [{
                "status": "incomplete",
                "scopeStatus": {"worldMarket": {"status": "incomplete"}},
                "authoritativeFinalState": {"controlPoints": {"raw": [1, 0, 0]}},
            }],
            "comparison": {"excludedIncompletePlans": ["fixture"]},
        },
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


def test_real_application_validation_keeps_save_context(tmp_path):
    from tests.test_application_api import _save as real_save

    save = real_save(tmp_path)
    server = adapter.create_server()
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
    assert invalid_consent.is_error is True
    assert invalid_consent.structured_content["error"]["code"] == "invalid-arguments"
    assert "saveIdentity" in invalid_consent.structured_content


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
