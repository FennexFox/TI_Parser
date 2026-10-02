"""Optional local stdio MCP adapter for the application analysis boundary.

The MCP SDK is deliberately imported only when :func:`create_server` or
``main`` is called.  Importing this module therefore does not add an optional
runtime dependency to the normal CLI or application API.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import sys
from collections import OrderedDict
from pathlib import Path
from typing import Any, Mapping

from ti_parser_capabilities import capabilities as application_capabilities
from ti_parser_errors import UserInputError
from ti_parser_registry import ANALYSES, get_analysis, get_input_schema, validate_argument_shape
from ti_parser_session import AnalysisSession
from ti_parser_version import __version__


_MISSING = object()
_MAX_SESSIONS = 2


class MissingSDKError(RuntimeError):
    """Raised when the optional MCP dependency is not installed."""


def _tool_schema(entry: Any) -> dict[str, Any]:
    """Add transport fields to the registry-owned public analysis contract."""

    schema = get_input_schema(entry.command)
    schema["properties"]["save_path"] = {"type": "string"}
    schema["required"] = ["save_path", *schema.get("required", [])]
    if entry.allows_explicit_unverified_consent:
        schema["properties"]["allow_unverified"] = {"type": "boolean", "default": False}
    return schema


def _capability_schema() -> dict[str, Any]:
    return {"type": "object", "properties": {}, "additionalProperties": False}


def _mcp_capabilities(entries: tuple[Any, ...], schemas: Mapping[str, dict[str, Any]]) -> dict[str, Any]:
    """Project the application inventory onto the tools exposed over MCP."""

    payload = application_capabilities()
    payload["analyses"] = []
    for entry in entries:
        row = entry.as_dict()
        row["inputSchema"] = schemas[entry.command]
        payload["analyses"].append(row)
    return payload


def _tool_description(entry: Any) -> str:
    description = entry.purpose
    if entry.kind == "planning-evidence":
        description += " Provides evidence for strategy decisions."
    if entry.routing_class == "bootstrap":
        description += " This is a bootstrap analysis route."
    description = f"{entry.kind}: {description}"
    return description


def _json_text(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _result(types_module: Any, payload: Any, *, is_error: bool = False) -> Any:
    """Return one envelope as both MCP structured and JSON text content."""

    text = _json_text(payload)
    return types_module.CallToolResult(
        content=[types_module.TextContent(type="text", text=text)],
        structured_content=payload,
        is_error=is_error,
    )


def _error_payload(code: str, message: str, *, context: Mapping[str, Any] | None = None) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message}
    if context:
        error["context"] = dict(context)
    return {"schemaVersion": 1, "status": "error", "error": error}


def _normalize_save_path(value: Any) -> Path:
    if not isinstance(value, str) or not value:
        raise UserInputError("save_path must be a non-empty string", code="invalid-arguments")
    try:
        return Path(value).expanduser().resolve(strict=False)
    except (OSError, ValueError) as exc:
        raise UserInputError("save_path is not a valid path", code="invalid-arguments") from exc


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class SessionCache:
    """A two-entry, content-aware LRU cache of application sessions."""

    def __init__(self, *, max_sessions: int = _MAX_SESSIONS) -> None:
        self.max_sessions = max_sessions
        self._entries: OrderedDict[str, tuple[str, AnalysisSession]] = OrderedDict()
        self._lock = asyncio.Lock()

    @property
    def entries(self) -> Mapping[str, tuple[str, AnalysisSession]]:
        return self._entries

    def _pre_session_error(self, path: Path, exc: BaseException) -> dict[str, Any]:
        if isinstance(exc, UserInputError):
            error = exc.to_dict()
        elif isinstance(exc, OSError):
            error = {"code": "save-unavailable", "message": str(exc) or exc.__class__.__name__}
        else:
            error = {"code": "save-unavailable", "message": str(exc) or exc.__class__.__name__}
        error.setdefault("context", {})
        error["context"].setdefault("path", str(path))
        return {"schemaVersion": 1, "status": "error", "error": error}

    def _load(self, path: Path) -> tuple[AnalysisSession | None, dict[str, Any] | None]:
        try:
            before = _sha256(path)
        except (OSError, ValueError) as exc:
            return None, self._pre_session_error(path, exc)

        key = str(path)
        cached = self._entries.get(key)
        if cached is not None and cached[0] == before:
            self._entries.move_to_end(key)
            return cached[1], None
        if cached is not None:
            # A changed file invalidates the generation before reconstruction;
            # failed or unstable replacement must never retain stale state.
            self._entries.pop(key, None)

        try:
            session = AnalysisSession(path)
        except (UserInputError, OSError) as exc:
            return None, self._pre_session_error(path, exc)

        try:
            after = _sha256(path)
        except (OSError, ValueError) as exc:
            return None, self._pre_session_error(path, exc)
        if before != after:
            return None, _error_payload(
                "save-changed-during-read",
                "The save changed while its analysis session was being created; retry the call.",
                context={"path": str(path)},
            )

        self._entries[key] = (after, session)
        self._entries.move_to_end(key)
        while len(self._entries) > self.max_sessions:
            self._entries.popitem(last=False)
        return session, None

    async def run(
        self,
        path: Path,
        analysis: str,
        *,
        allow_unverified: bool,
        kwargs: Mapping[str, Any],
    ) -> dict[str, Any]:
        async with self._lock:
            session, error = self._load(path)
            if error is not None:
                return error
            assert session is not None
            return session.run(analysis, allow_unverified=allow_unverified, **dict(kwargs))


def _exposed_entries() -> tuple[Any, ...]:
    return tuple(
        entry
        for entry in ANALYSES
        if entry.routing_class in {"bootstrap", "primary"}
    )


def create_server() -> Any:
    """Create a low-level MCP server; importing this function needs ``mcp``."""

    try:
        import mcp.types as mcp_types
        from mcp.server.lowlevel import Server
    except ModuleNotFoundError as exc:  # pragma: no cover - exercised in package smoke tests
        raise MissingSDKError(
            "The optional MCP adapter requires mcp==2.2.0; install it with "
            "python -m pip install -r requirements-mcp.txt."
        ) from exc

    cache = SessionCache()
    entries = _exposed_entries()
    schemas = {entry.command: _tool_schema(entry) for entry in entries}
    tools = [
        mcp_types.Tool(
            name=entry.command,
            description=_tool_description(entry),
            input_schema=schemas[entry.command],
        )
        for entry in entries
    ]
    tools.append(
        mcp_types.Tool(
            name="capabilities",
            description="Return MCP-visible analysis metadata without opening a save.",
            input_schema=_capability_schema(),
        )
    )

    async def on_list_tools(_ctx: Any, _params: Any) -> Any:
        return mcp_types.ListToolsResult(tools=tools)

    async def on_call_tool(_ctx: Any, params: Any) -> Any:
        name = params.name
        arguments = dict(params.arguments or {})
        if name == "capabilities":
            if arguments:
                return _result(
                    mcp_types,
                    _error_payload("invalid-arguments", "capabilities does not accept arguments"),
                    is_error=True,
                )
            return _result(mcp_types, _mcp_capabilities(entries, schemas))

        try:
            entry = get_analysis(name)
        except UserInputError as exc:
            return _result(mcp_types, _error_payload(exc.code, exc.message, context=exc.context), is_error=True)
        if entry not in entries:
            return _result(
                mcp_types,
                _error_payload("unsupported-analysis", f"Analysis is not exposed by the MCP adapter: {name}"),
                is_error=True,
            )

        save_path = arguments.pop("save_path", _MISSING)
        try:
            path = _normalize_save_path(save_path)
        except UserInputError as exc:
            return _result(mcp_types, _error_payload(exc.code, exc.message, context=exc.context), is_error=True)

        allow_present = "allow_unverified" in arguments
        allow_unverified = arguments.pop("allow_unverified", False)
        if not entry.allows_explicit_unverified_consent and allow_present:
            return _result(
                mcp_types,
                _error_payload("invalid-arguments", f"allow_unverified is not supported for {name}"),
                is_error=True,
            )
        if "plan_payload" in arguments:
            try:
                validate_argument_shape(name, "plan_payload", arguments["plan_payload"])
            except UserInputError as exc:
                return _result(
                    mcp_types,
                    _error_payload(exc.code, exc.message, context=exc.context),
                    is_error=True,
                )
        payload = await cache.run(
            path,
            name,
            allow_unverified=allow_unverified,
            kwargs=arguments,
        )
        return _result(mcp_types, payload, is_error=isinstance(payload, dict) and payload.get("status") == "error")

    server = Server(
        "ti-parser",
        version=__version__,
        description="Terra Invicta save analysis through the local MCP stdio transport.",
        on_list_tools=on_list_tools,
        on_call_tool=on_call_tool,
    )
    # Kept private on the server for in-process tests and diagnostics; it does
    # not alter the SDK contract or expose save contents outside tool results.
    server._ti_parser_session_cache = cache  # type: ignore[attr-defined]
    return server


async def _run_stdio(server: Any) -> None:
    from mcp.server.stdio import stdio_server

    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def main() -> None:
    """Run the adapter over stdio, keeping stdout exclusively for MCP frames."""

    try:
        server = create_server()
    except MissingSDKError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2) from exc
    asyncio.run(_run_stdio(server))


if __name__ == "__main__":  # pragma: no cover
    main()
