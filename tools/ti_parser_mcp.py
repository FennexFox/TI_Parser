"""Optional local stdio MCP adapter for the application analysis boundary.

The MCP SDK is deliberately imported only when :func:`create_server` or
``main`` is called.  Importing this module therefore does not add an optional
runtime dependency to the normal CLI or application API.
"""

from __future__ import annotations

import asyncio
import argparse
import hashlib
import json
import sys
from collections import OrderedDict
from pathlib import Path
from typing import Any, Mapping

from ti_parser_capabilities import capabilities as application_capabilities
from ti_parser_errors import UserInputError
from ti_parser_registry import get_analysis, get_input_schema, validate_argument_shape
from ti_parser_session import AnalysisSession
from ti_parser_fairplay import (
    FAIRPLAY_BOOTSTRAP_POLICY, FAIRPLAY_ROUTING_INSTRUCTIONS, exposed_entries, get_profile_output_schema,
    get_profile_capabilities_output_schema, policy_inventory,
    run_profile, sanitize_profile_error, validate_profile,
)
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


def _tool_description(entry: Any, profile: str = "default") -> str:
    description = entry.purpose
    if profile == "fair-play" and entry.command == "inspect-save":
        return ("Save identity and compatibility inspection for an explicit correlation or "
                "compatibility request. Current nation facts and previous-save changes "
                "belong to Companion; this tool supplies neither. "
                "It is not a prerequisite for Companion-only answers. "
                "It supplies no selected nation ID or forecast.")
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
        profile: str = "default",
    ) -> dict[str, Any]:
        async with self._lock:
            session, error = self._load(path)
            if error is not None:
                return error
            assert session is not None
            return run_profile(session, analysis, profile=profile,
                               allow_unverified=allow_unverified, **dict(kwargs))


def _exposed_entries(profile: str = "default") -> tuple[Any, ...]:
    return exposed_entries(profile)


_CONDITIONAL_TOOL_NAMES = (
    "register-visible-context",
    "conditional-nation-projection",
    "verify-visible-generation",
)
_CONDITIONAL_INSPECT_SCHEMA = {
    "type": "object",
    "properties": {"save_path": {"type": "string"}},
    "required": ["save_path"],
    "additionalProperties": False,
}
_CONDITIONAL_CAPABILITIES_ERROR_SCHEMA = {
    "type": "object",
    "properties": {
        "schemaVersion": {"const": 1},
        "status": {"const": "error"},
        "error": {
            "type": "object",
            "properties": {
                "code": {"type": "string"},
                "message": {"type": "string"},
                "context": {"type": "object"},
            },
            "required": ["code", "message"],
            "additionalProperties": False,
        },
    },
    "required": ["schemaVersion", "status", "error"],
    "additionalProperties": False,
}
_CONDITIONAL_ROUTING_INSTRUCTIONS = (
    "Use Companion for current state and historical changes. Conditional "
    "projection results describe scenario outcomes and must never be presented "
    "as observed save truth. Use only explicitly declared visible context. Do "
    "not inspect hidden state or fall back to another TI Parser profile. Verify "
    "the visible generation before relying on a projection."
)


def _conditional_inspection_error(payload: Any) -> Any:
    """Apply the existing fair-play error sanitizer to private inspections."""

    return sanitize_profile_error(payload, "fair-play")


def _create_conditional_server(mcp_types: Any, server_class: Any) -> Any:
    """Create the isolated visible-context conditional MCP surface."""

    from ti_parser_conditional_application import ConditionalApplication

    cache = SessionCache()

    async def inspect_save(save_path: str, nation_id: int | None = None) -> dict[str, Any]:
        try:
            path = _normalize_save_path(save_path)
        except UserInputError as exc:
            return _conditional_inspection_error(
                _error_payload(exc.code, exc.message, context=exc.context)
            )

        if nation_id is None:
            try:
                payload = await cache.run(
                    path,
                    "inspect-save",
                    allow_unverified=False,
                    kwargs={},
                    profile="fair-play",
                )
            except Exception:
                return _conditional_inspection_error(
                    _error_payload("save-unavailable", "The save could not be inspected.")
                )
            return _conditional_inspection_error(payload)

        try:
            if type(nation_id) is not int:
                raise UserInputError(
                    "Subject nation is unresolved", code="fairplay-subject-unresolved"
                )
            async with cache._lock:
                session, error = cache._load(path)
                if error is not None:
                    return _conditional_inspection_error(error)
                assert session is not None

                from ti_parser_fairplay import _normalize_id, _resolve_owned_subject

                resolved_nation_id, identity = _resolve_owned_subject(session, nation_id)
                player = identity.get("playerFaction") if isinstance(identity, Mapping) else None
                player_id = player.get("id") if isinstance(player, Mapping) else None
                if type(player_id) is not int:
                    raise UserInputError(
                        "Subject player is unresolved", code="fairplay-subject-unresolved"
                    )

                nation_state = session.indexed.id_index.get(resolved_nation_id)
                if nation_state is None or nation_state[1] != "TINationState":
                    raise UserInputError(
                        "Subject nation is unresolved", code="fairplay-subject-unresolved"
                    )
                references = nation_state[2].get("controlPoints")
                if not isinstance(references, list) or len(references) != 6:
                    raise UserInputError(
                        "Subject ownership is unresolved", code="fairplay-subject-unresolved"
                    )

                positions: set[int] = set()
                rows: list[tuple[int, int]] = []
                seen_ids: set[int] = set()
                for reference in references:
                    cp_id = _normalize_id(reference)
                    cp_state = session.indexed.id_index.get(cp_id) if type(cp_id) is int else None
                    if (
                        type(cp_id) is not int
                        or cp_id in seen_ids
                        or cp_state is None
                        or cp_state[1] != "TIControlPointState"
                    ):
                        raise UserInputError(
                            "Subject control point is unresolved",
                            code="fairplay-subject-unresolved",
                        )
                    control_point = cp_state[2]
                    position = control_point.get("positionInNation")
                    owner_id = _normalize_id(control_point.get("faction"))
                    cp_nation_id = _normalize_id(control_point.get("nation"))
                    if (
                        type(position) is not int
                        or position < 0
                        or position >= 6
                        or position in positions
                        or owner_id != player_id
                        or cp_nation_id != resolved_nation_id
                    ):
                        raise UserInputError(
                            "Subject ownership is unresolved",
                            code="fairplay-subject-unresolved",
                        )
                    seen_ids.add(cp_id)
                    positions.add(position)
                    rows.append((position, cp_id))

                if positions != set(range(6)):
                    raise UserInputError(
                        "Subject control-point positions are unresolved",
                        code="fairplay-subject-unresolved",
                    )
                rows.sort()
                if _sha256(path) != cache._entries[str(path)][0]:
                    cache._entries.pop(str(path), None)
                    raise UserInputError("Save changed during subject inspection", code="save-changed-during-read")
                return {
                    "schemaVersion": 1,
                    "status": "complete",
                    "saveIdentity": identity,
                    "subject": {
                        "nationId": resolved_nation_id,
                        "playerFactionId": player_id,
                        "controlPointIds": [cp_id for _, cp_id in rows],
                    },
                }
        except UserInputError as exc:
            return _conditional_inspection_error(
                _error_payload(exc.code, exc.message, context=exc.context)
            )
        except Exception:
            return _conditional_inspection_error(
                _error_payload(
                    "request-rejected", "The visible subject could not be verified."
                )
            )

    application = ConditionalApplication(inspect_save=inspect_save)
    contracts = application.tool_contracts()
    if not isinstance(contracts, Mapping) or set(_CONDITIONAL_TOOL_NAMES) - set(contracts):
        raise RuntimeError("Conditional application tool contracts are incomplete")
    capabilities_schema = application.capabilities_output_schema()
    if not isinstance(capabilities_schema, dict):
        raise RuntimeError("Conditional application capabilities schema is invalid")
    conditional_capabilities_schema = {
        "type": "object",
        "anyOf": [capabilities_schema, _CONDITIONAL_CAPABILITIES_ERROR_SCHEMA],
    }

    tools = [
        mcp_types.Tool(
            name="inspect-save",
            description=(
                "Return sanitized save identity and compatibility. This supplies neither "
                "current Companion state nor historical changes."
            ),
            input_schema=_CONDITIONAL_INSPECT_SCHEMA,
            output_schema=get_profile_output_schema("fair-play", "inspect-save"),
        )
    ]
    for name in _CONDITIONAL_TOOL_NAMES:
        contract = contracts[name]
        tools.append(
            mcp_types.Tool(
                name=name,
                description=contract["description"],
                input_schema=contract["inputSchema"],
                output_schema=contract["outputSchema"],
            )
        )
    tools.append(
        mcp_types.Tool(
            name="capabilities",
            description="Return the conditional profile policy and visible-context tools without opening a save.",
            input_schema=_capability_schema(),
            output_schema=conditional_capabilities_schema,
        )
    )
    allowed_names = {tool.name for tool in tools}

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
            try:
                payload = application.capabilities()
                if not isinstance(payload, dict):
                    raise TypeError("Invalid conditional capabilities")
                listed_names = payload.get("tools")
                if not isinstance(listed_names, list):
                    raise TypeError("Invalid conditional capabilities")
                payload = dict(payload)
                payload["tools"] = [
                    "inspect-save",
                    *[tool_name for tool_name in listed_names if tool_name != "inspect-save"],
                ]
            except Exception:
                payload = _error_payload(
                    "request-rejected", "Conditional capabilities are unavailable."
                )
                return _result(mcp_types, payload, is_error=True)
            return _result(mcp_types, payload)

        if name not in allowed_names:
            return _result(
                mcp_types,
                _error_payload("unsupported-analysis", "The requested tool is unavailable in this profile."),
                is_error=True,
            )

        try:
            if name == "inspect-save":
                if set(arguments) != {"save_path"}:
                    raise UserInputError("Invalid inspection arguments", code="invalid-arguments")
                payload = await inspect_save(arguments.get("save_path"))
            else:
                payload = await application.call(name, arguments)
        except Exception:
            if name == "inspect-save":
                payload = _conditional_inspection_error(_error_payload("request-rejected", "Request rejected"))
            else:
                from ti_parser_conditional_application import _error
                payload = _error("request-rejected")
        is_error = isinstance(payload, dict) and payload.get("status") == "error"
        return _result(mcp_types, payload, is_error=is_error)

    server = server_class(
        "ti-parser",
        version=__version__,
        description="Terra Invicta conditional visible-context analysis through local MCP stdio transport.",
        instructions=_CONDITIONAL_ROUTING_INSTRUCTIONS,
        on_list_tools=on_list_tools,
        on_call_tool=on_call_tool,
    )
    server._ti_parser_session_cache = cache  # type: ignore[attr-defined]
    server._ti_parser_conditional_application = application  # type: ignore[attr-defined]
    return server


def create_server(*, profile: str = "default") -> Any:
    """Create a low-level MCP server; importing this function needs ``mcp``."""

    if profile != "conditional":
        validate_profile(profile)
    try:
        import mcp.types as mcp_types
        from mcp.server.lowlevel import Server
    except ModuleNotFoundError as exc:  # pragma: no cover - exercised in package smoke tests
        raise MissingSDKError(
            "The optional MCP adapter requires mcp==2.2.0; install it with "
            "python -m pip install -r requirements-mcp.txt."
        ) from exc

    if profile == "conditional":
        return _create_conditional_server(mcp_types, Server)

    cache = SessionCache()
    entries = _exposed_entries(profile)
    schemas = {entry.command: _tool_schema(entry) for entry in entries}
    tools = [
        mcp_types.Tool(
            name=entry.command,
            description=_tool_description(entry, profile),
            input_schema=schemas[entry.command],
            output_schema=get_profile_output_schema(profile, entry.command),
        )
        for entry in entries
    ]
    tools.append(
        mcp_types.Tool(
            name="capabilities",
            description=("Return MCP-visible analysis metadata without opening a save. "
                         "Fair-play-projection-v1 is pending and disabled; only identity inspection "
                         "is allowed." if profile == "fair-play" else
                         "Return MCP-visible analysis metadata without opening a save."),
            input_schema=_capability_schema(),
            output_schema=get_profile_capabilities_output_schema(profile),
        )
    )

    def profile_result(types_module: Any, payload: Any, *, is_error: bool = False) -> Any:
        return _result(types_module, sanitize_profile_error(payload, profile), is_error=is_error)

    async def on_list_tools(_ctx: Any, _params: Any) -> Any:
        return mcp_types.ListToolsResult(tools=tools)

    async def on_call_tool(_ctx: Any, params: Any) -> Any:
        name = params.name
        arguments = dict(params.arguments or {})
        if name == "capabilities":
            if arguments:
                return profile_result(
                    mcp_types,
                    _error_payload("invalid-arguments", "capabilities does not accept arguments"),
                    is_error=True,
                )
            inventory = _mcp_capabilities(entries, schemas)
            if profile == "fair-play":
                inventory["bootstrapPolicy"] = FAIRPLAY_BOOTSTRAP_POLICY
                inventory["fairPlayPolicy"] = policy_inventory()["adviceGenerationPolicy"]
            return profile_result(mcp_types, inventory)

        try:
            entry = get_analysis(name)
        except UserInputError as exc:
            return profile_result(mcp_types, _error_payload(exc.code, exc.message, context=exc.context), is_error=True)
        if entry not in entries:
            return profile_result(
                mcp_types,
                _error_payload("unsupported-analysis", f"Analysis is not exposed by the MCP adapter: {name}"),
                is_error=True,
            )

        save_path = arguments.pop("save_path", _MISSING)
        try:
            path = _normalize_save_path(save_path)
        except UserInputError as exc:
            return profile_result(mcp_types, _error_payload(exc.code, exc.message, context=exc.context), is_error=True)

        allow_present = "allow_unverified" in arguments
        allow_unverified = arguments.pop("allow_unverified", False)
        if not entry.allows_explicit_unverified_consent and allow_present:
            return profile_result(
                mcp_types,
                _error_payload("invalid-arguments", f"allow_unverified is not supported for {name}"),
                is_error=True,
            )
        if "plan_payload" in arguments:
            try:
                validate_argument_shape(name, "plan_payload", arguments["plan_payload"])
            except UserInputError as exc:
                return profile_result(
                    mcp_types,
                    _error_payload(exc.code, exc.message, context=exc.context),
                    is_error=True,
                )
        payload = await cache.run(
            path,
            name,
            allow_unverified=allow_unverified,
            kwargs=arguments,
            profile=profile,
        )
        return profile_result(mcp_types, payload, is_error=isinstance(payload, dict) and payload.get("status") == "error")

    server = Server(
        "ti-parser",
        version=__version__,
        description="Terra Invicta save analysis through the local MCP stdio transport.",
        instructions=FAIRPLAY_ROUTING_INSTRUCTIONS if profile == "fair-play" else None,
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

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=("default", "fair-play", "conditional"), default="default")
    args = parser.parse_args()
    try:
        server = create_server(profile=args.profile)
    except MissingSDKError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2) from exc
    asyncio.run(_run_stdio(server))


if __name__ == "__main__":  # pragma: no cover
    main()
