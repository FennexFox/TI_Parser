"""Smoke-test the MCP adapter from the bytes that the beta ZIP packages."""

from __future__ import annotations

import asyncio
import gzip
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from build_beta_distribution import build_beta_distribution  # noqa: E402
from verify_beta_distribution import extract_verified  # noqa: E402


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MCP_AVAILABLE = importlib.util.find_spec("mcp") is not None


def _tracked_in_head(path: str) -> bool:
    result = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", "HEAD", "--", path],
        cwd=REPOSITORY_ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        stdin=subprocess.DEVNULL,
    )
    return result.returncode == 0 and path in result.stdout.splitlines()


def _synthetic_save(path: Path) -> None:
    def row(save_id: int, **values: object) -> dict[str, object]:
        return {"Key": {"value": save_id}, "Value": {"ID": {"value": save_id}, **values}}

    data = {
        "gamestates": {
            "TITimeState": [
                row(
                    1,
                    scenarioMetaTemplateName="ModernScenario",
                    currentDateTime={"year": 2035, "month": 1, "day": 10},
                )
            ],
            "TIFactionState": [
                row(
                    2,
                    templateName="ResistCouncil",
                    displayName="Resistance",
                    player={"value": 3},
                    resources={},
                    baseIncomes_year={"Research": 365},
                    councilors=[],
                    controlPoints=[],
                    habitats=[],
                    fleets=[],
                    researchWeights=[0] * 6,
                    currentProjectProgress=[],
                    availableProjectNames=[],
                    finishedProjectNames=[],
                    missionControlUsage=0,
                )
            ],
            "TIPlayerState": [row(3, faction={"value": 2}, isAI=False)],
            "TIEffectsState": [row(4, effects=[])],
            "TIGlobalResearchState": [row(5, techProgress=[], finishedTechsNames=[])],
            "TIGlobalValuesState": [
                row(6, latestSaveVersion="synthetic-not-verified", moddingActive=False, moddingUsedAnytime=False)
            ],
        }
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        json.dump(data, handle)


def _envelope(result: object) -> dict[str, object]:
    structured = getattr(result, "structured_content", None)
    if isinstance(structured, dict) and structured:
        return structured
    for item in getattr(result, "content", []):
        if getattr(item, "type", None) == "text":
            value = json.loads(item.text)
            if isinstance(value, dict):
                return value
    raise AssertionError(f"MCP result did not contain a JSON envelope: {result!r}")


@pytest.mark.skipif(not MCP_AVAILABLE, reason="optional MCP dependency is not installed")
def test_extracted_zip_serves_application_over_stdio(tmp_path: Path) -> None:
    # The distribution is deliberately built from HEAD. A dirty checkout is
    # not a valid release artifact until the adapter changes are committed.
    if not _tracked_in_head("tools/ti_parser_mcp.py"):
        pytest.skip("MCP adapter is not present in the committed HEAD")
    if not _tracked_in_head("tools/ti_parser_schema.py"):
        pytest.skip("Output-schema helper is not present in the committed HEAD")

    archive = tmp_path / "ti-parser-mcp.zip"
    build_beta_distribution(REPOSITORY_ROOT, archive, ref="HEAD")
    extracted = tmp_path / "extracted"
    extract_verified(archive, extracted)
    assert (extracted / "tools" / "ti_parser_schema.py").is_file()
    assert not (extracted / "tests").exists()
    assert not (extracted / "tools" / "audit_projection_reads.py").exists()
    assert not (extracted / "tools" / "projection_audit_dependencies.py").exists()
    assert not (extracted / "tools" / "projection_audit_evidence.py").exists()
    assert not (extracted / "dev-docs" / "projection_execution_evidence.json").exists()
    assert not (extracted / "tools" / "run_fairplay_routing.py").exists()
    if _tracked_in_head("tools/ti_parser_fairplay.py"):
        assert (extracted / "tools" / "ti_parser_fairplay.py").is_file()
        assert not (extracted / "dev-docs").exists()

    save = tmp_path / "외부 세이브 경로" / "campaign copy.gz"
    _synthetic_save(save)
    original_save_bytes = save.read_bytes()

    async def exercise_client() -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        from jsonschema import Draft202012Validator, validate

        server = StdioServerParameters(
            command=sys.executable,
            args=[str(extracted / "tools" / "ti_parser_mcp.py")],
            cwd=str(tmp_path),
        )
        with (tmp_path / "mcp-stderr.log").open("w", encoding="utf-8") as errlog:
            async with stdio_client(server, errlog=errlog) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream, read_timeout_seconds=120) as session:
                    initialized = await session.initialize()
                    assert initialized.server_info.name
                    listed = await session.list_tools()
                    tools_by_name = {tool.name: tool for tool in listed.tools}
                    tool_names = set(tools_by_name)
                    assert "capabilities" in tool_names
                    for tool in listed.tools:
                        assert tool.output_schema is not None
                        Draft202012Validator.check_schema(tool.input_schema)
                        Draft202012Validator.check_schema(tool.output_schema)

                    inspected_result = await session.call_tool("inspect-save", {"save_path": str(save)})
                    assert not inspected_result.is_error
                    inspected = _envelope(inspected_result)
                    validate(inspected, tools_by_name["inspect-save"].output_schema)

                    deferred_result = await session.call_tool("topbar", {"save_path": str(save)})
                    assert not deferred_result.is_error
                    deferred = _envelope(deferred_result)
                    validate(deferred, tools_by_name["topbar"].output_schema)

                    allowed_result = await session.call_tool(
                        "topbar", {"save_path": str(save), "allow_unverified": True}
                    )
                    assert not allowed_result.is_error
                    allowed = _envelope(allowed_result)
                    validate(allowed, tools_by_name["topbar"].output_schema)

                    capabilities_result = await session.call_tool("capabilities", {})
                    assert not capabilities_result.is_error
                    validate(_envelope(capabilities_result), tools_by_name["capabilities"].output_schema)

                    missing_result = await session.call_tool(
                        "topbar", {"save_path": str(tmp_path / "missing-save.gz")}
                    )
                    assert missing_result.is_error
                    missing_payload = _envelope(missing_result)
                    assert "saveIdentity" not in missing_payload
                    validate(missing_payload, tools_by_name["topbar"].output_schema)
                    return inspected, deferred, allowed

    inspected, deferred, allowed = asyncio.run(exercise_client())
    assert inspected["status"] == "complete"
    assert deferred["status"] == "deferred"
    assert allowed["status"] == "complete"
    assert inspected["saveIdentity"] == deferred["saveIdentity"] == allowed["saveIdentity"]
    assert save.read_bytes() == original_save_bytes

    if _tracked_in_head("tools/ti_parser_fairplay.py"):
        async def exercise_fairplay():
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client
            from jsonschema import validate

            params = StdioServerParameters(command=sys.executable, args=[
                str(extracted / "tools" / "ti_parser_mcp.py"), "--profile", "fair-play",
            ], cwd=str(tmp_path))
            async with stdio_client(params) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    listed = await session.list_tools()
                    by_name = {tool.name: tool for tool in listed.tools}
                    assert set(by_name) == {"inspect-save", "capabilities"}
                    inventory = await session.call_tool("capabilities", {})
                    inventory_payload = _envelope(inventory)
                    validate(inventory_payload, by_name["capabilities"].output_schema)
                    assert inventory_payload["fairPlayPolicy"]["id"] == "fair-play-projection-v1"
                    assert inventory_payload["fairPlayPolicy"]["enabled"] is False
                    result = await session.call_tool("inspect-save", {"save_path": str(save)})
                    assert not result.is_error
                    payload = _envelope(result)
                    validate(payload, by_name["inspect-save"].output_schema)
                    assert payload["saveIdentity"] == inspected["saveIdentity"]
                    assert "modEvidence" not in payload["compatibility"]

        asyncio.run(exercise_fairplay())
        assert save.read_bytes() == original_save_bytes


def test_missing_optional_dependency_is_stderr_only(tmp_path: Path) -> None:
    isolated_entrypoint = (
        "import runpy, sys; "
        "sys.path.insert(0, sys.argv[1]); "
        "entrypoint = sys.argv[2]; sys.argv = [entrypoint]; "
        "runpy.run_path(entrypoint, run_name='__main__')"
    )
    process = subprocess.Popen(
        [
            sys.executable,
            "-I",
            "-S",
            "-B",
            "-c",
            isolated_entrypoint,
            str(REPOSITORY_ROOT / "tools"),
            str(REPOSITORY_ROOT / "tools" / "ti_parser_mcp.py"),
        ],
        cwd=tmp_path,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    stdout, stderr = process.communicate(timeout=120)

    assert process.returncode == 2
    assert stdout == ""
    assert "pip install -r requirements-mcp.txt" in stderr


@pytest.mark.skipif(not MCP_AVAILABLE, reason="optional MCP dependency is not installed")
def test_stdio_startup_stdout_is_protocol_only(tmp_path: Path) -> None:
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "ti-parser-stdio-test", "version": "1.0"},
        },
    }
    process = subprocess.Popen(
        [sys.executable, str(REPOSITORY_ROOT / "tools" / "ti_parser_mcp.py")],
        cwd=tmp_path,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    stdout, stderr = process.communicate(json.dumps(request) + "\n", timeout=120)

    assert process.returncode == 0, stderr
    lines = [line for line in stdout.splitlines() if line.strip()]
    assert lines, "the adapter did not return an initialize response"
    first = json.loads(lines[0])
    assert first["id"] == 1
    assert first["result"]["serverInfo"]["name"] == "ti-parser"
