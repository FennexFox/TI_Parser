"""SDK-free structural checks for application-owned MCP output schemas."""

from __future__ import annotations


def test_analysis_output_covers_application_and_pre_session_envelopes():
    from ti_parser_schema import get_analysis_output_schema

    schema = get_analysis_output_schema()
    assert schema["type"] == "object"
    application, pre_session = schema["oneOf"]

    assert application["required"] == [
        "schemaVersion",
        "parserVersion",
        "analysis",
        "saveIdentity",
        "compatibility",
        "status",
    ]
    assert application["properties"]["status"]["enum"] == [
        "complete",
        "deferred",
        "incomplete",
        "error",
    ]
    assert application["properties"]["result"] == {}
    assert application["properties"]["missingDependencies"]["items"]["type"] == "object"

    identity = application["properties"]["saveIdentity"]["properties"]
    assert identity["fingerprint"]["properties"]["value"]["pattern"] == "^[0-9a-f]{64}$"
    player = identity["playerFaction"]["oneOf"]
    assert {branch["properties"]["status"]["const"] for branch in player} == {
        "resolved",
        "unresolved",
    }

    compatibility = application["properties"]["compatibility"]
    assert set(compatibility["required"]) == {"status", "reasons", "unverifiedAllowed"}
    assert compatibility["additionalProperties"] is True

    assert pre_session["required"] == ["schemaVersion", "status", "error"]
    assert "saveIdentity" not in pre_session["properties"]
    assert pre_session["additionalProperties"] is False
    error = pre_session["properties"]["error"]
    assert set(error["required"]) == {"code", "message"}
    assert {"context", "candidates", "details"} <= set(error["properties"])


def test_capabilities_schema_describes_registry_inventory_and_load_error():
    from ti_parser_schema import get_capabilities_output_schema

    output = get_capabilities_output_schema()
    assert output["type"] == "object"
    inventory, pre_session = output["oneOf"]
    assert set(inventory["required"]) == {
        "schemaVersion",
        "parserVersion",
        "analyses",
        "bootstrapPolicy",
    }
    descriptor = inventory["properties"]["analyses"]["items"]
    assert "inputSchema" in descriptor["properties"]
    assert "inputSchema" not in descriptor["required"]
    assert "arguments" in descriptor["required"]
    assert pre_session["properties"]["status"] == {"const": "error"}


def test_schema_helpers_return_independent_mutable_objects():
    from ti_parser_schema import (
        get_analysis_output_schema,
        get_capabilities_output_schema,
        get_tool_error_schema,
    )

    first = get_analysis_output_schema()
    second = get_analysis_output_schema()
    first["oneOf"][0]["properties"]["status"]["enum"].clear()
    assert second["oneOf"][0]["properties"]["status"]["enum"]

    error = get_tool_error_schema()
    error["properties"]["error"]["properties"].pop("context")
    assert "context" in get_tool_error_schema()["properties"]["error"]["properties"]
    assert "context" in get_capabilities_output_schema()["oneOf"][1]["properties"]["error"]["properties"]
