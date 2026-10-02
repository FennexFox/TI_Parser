"""Synthetic Companion MCP server for fair-play interoperability tests.

This server reads one explicit JSON fixture and exposes only its player-visible
current nation and saved change log. It has no dependency on Companion code or
state outside that fixture.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any


def _json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _result(types_module: Any, payload: dict[str, Any], *, is_error: bool = False) -> Any:
    return types_module.CallToolResult(
        content=[types_module.TextContent(type="text", text=_json_text(payload))],
        structured_content=payload,
        is_error=is_error,
    )


def _load_fixture(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if (
        not isinstance(value, dict)
        or value.get("schemaVersion") != 1
        or not isinstance(value.get("snapshotIdentity"), dict)
        or not isinstance(value.get("nation"), dict)
        or not isinstance(value.get("recentChanges"), list)
    ):
        raise ValueError("Fixture must contain schemaVersion 1, snapshotIdentity, nation, and recentChanges.")
    return value


def create_server(fixture_path: Path) -> Any:
    """Create a low-level MCP server backed only by ``fixture_path``."""

    try:
        import mcp.types as mcp_types
        from mcp.server.lowlevel import Server
    except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency path
        raise RuntimeError("The mock Companion server requires the optional MCP SDK.") from exc

    fixture = _load_fixture(fixture_path)
    empty_input = {"type": "object", "properties": {}, "additionalProperties": False}
    output = {"type": "object", "additionalProperties": True}
    tools = [
        mcp_types.Tool(
            name="companion_current_nation",
            description=(
                "Read the synthetic player's current nation state and snapshot identity "
                "from the explicitly configured test fixture. Returns fixture evidence "
                "only; it does not calculate projections or read TI Parser data."
            ),
            input_schema=empty_input,
            output_schema=output,
        ),
        mcp_types.Tool(
            name="companion_recent_changes",
            description=(
                "Read the saved recent-change log and its current snapshot identity "
                "from the explicitly configured test fixture. It does not infer history "
                "from TI Parser data."
            ),
            input_schema=empty_input,
            output_schema=output,
        ),
    ]

    async def on_list_tools(_ctx: Any, _params: Any) -> Any:
        return mcp_types.ListToolsResult(tools=tools)

    async def on_call_tool(_ctx: Any, params: Any) -> Any:
        if params.arguments:
            return _result(
                mcp_types,
                {"schemaVersion": 1, "status": "error", "error": {"code": "invalid-arguments"}},
                is_error=True,
            )
        if params.name == "companion_current_nation":
            payload = {
                "schemaVersion": 1,
                "status": "complete",
                "source": "synthetic-companion-fixture",
                "saveIdentity": fixture["snapshotIdentity"],
                "selectedNationId": fixture["selectedNationId"],
                "result": {"nation": fixture["nation"]},
            }
            return _result(mcp_types, payload)
        if params.name == "companion_recent_changes":
            payload = {
                "schemaVersion": 1,
                "status": "complete",
                "source": "synthetic-companion-fixture",
                "saveIdentity": fixture["snapshotIdentity"],
                "selectedNationId": fixture["selectedNationId"],
                "recentChanges": fixture["recentChanges"],
            }
            return _result(mcp_types, payload)
        return _result(
            mcp_types,
            {"schemaVersion": 1, "status": "error", "error": {"code": "tool-unavailable"}},
            is_error=True,
        )

    return Server(
        "mock-companion",
        version="1.0.0-test",
        description="Synthetic player-visible Companion evidence for local interoperability tests.",
        on_list_tools=on_list_tools,
        on_call_tool=on_call_tool,
    )


async def _run_stdio(server: Any) -> None:
    from mcp.server.stdio import stdio_server

    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", required=True, type=Path)
    args = parser.parse_args()
    try:
        server = create_server(args.fixture)
    except (OSError, ValueError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2) from exc
    asyncio.run(_run_stdio(server))


if __name__ == "__main__":  # pragma: no cover - exercised as a stdio subprocess
    main()
