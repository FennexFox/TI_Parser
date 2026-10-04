"""Real conditional MCP integration against the isolated engine and save adapter."""

from __future__ import annotations

from copy import deepcopy
import gzip
import json
from pathlib import Path

import pytest

mcp = pytest.importorskip("mcp")
anyio = pytest.importorskip("anyio")
jsonschema = pytest.importorskip("jsonschema")

from mcp import Client  # noqa: E402

import ti_parser_mcp as adapter  # noqa: E402
from tests.fixtures.fairplay_projection import make_save_data  # noqa: E402


NATION_ID = 20
FACTION_ID = 2


def _write_save(tmp_path: Path, name: str = "visible.gz", *, data: dict | None = None) -> Path:
    save_data = deepcopy(data) if data is not None else make_save_data()
    global_values = save_data["gamestates"]["TIGlobalValuesState"][0]["Value"]
    global_values.update(
        realWorldCampaignStart=2024,
        latestSaveVersion="0.4.35",
        campaignStartVersion="0.4.35",
    )
    path = tmp_path / name
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        json.dump(save_data, handle)
    return path


async def _call(server, name: str, arguments: dict | None = None):
    async with Client(server, mode="legacy") as client:
        return await client.call_tool(name, arguments or {})


async def _list_tools(server):
    async with Client(server, mode="legacy") as client:
        return await client.list_tools()


def _schemas(server) -> dict[str, dict]:
    listed = anyio.run(_list_tools, server)
    schemas = {tool.name: tool.output_schema for tool in listed.tools}
    for tool in listed.tools:
        jsonschema.Draft202012Validator.check_schema(tool.input_schema)
        assert tool.output_schema is not None
        jsonschema.Draft202012Validator.check_schema(tool.output_schema)
    return schemas


def _context(identity: dict) -> dict:
    """Caller report and explicit assumptions; deliberately independent of hidden save fields."""
    return {
        "schemaVersion": "conditional-nation-v1",
        "model": "isolated-nation-v1",
        "assumptionsAcknowledged": True,
        "peer": {"saveIdentity": deepcopy(identity), "selectedNationId": NATION_ID},
        "observations": {
            "source": "synthetic visible-input integration fixture",
            "precision": "reported",
            "nation": {
                "id": NATION_ID,
                "name": "United States",
                "playerFactionId": FACTION_ID,
                "asOf": "2035-01-10T00:00:00Z",
                "gdp": 29_000_000_000_000.0,
                "inequality": 3.0,
                "education": 12.0,
                "democracy": 8.0,
                "cohesion": 5.0,
                "unrest": 0.0,
                "sustainability": 4.0,
                "militaryTech": 5.0,
                "fundingYear": 120.0,
                "regions": [{
                    "id": 100,
                    "name": "California",
                    "template": "California",
                    "populationMillions": 40.0,
                    "missionControl": 4,
                }],
                "controlPoints": [
                    {"id": point_id, "position": position, "ownerFactionId": FACTION_ID}
                    for position, point_id in enumerate(range(31, 37))
                ],
            },
        },
        "assumptions": {
            "daysInCampaign": 3300.0,
            "currentQuarter": 36,
            "nationPopulationGrowthModifier": 0.0,
            "startTimeTemplate": "ModernDayStart",
            "initialProgress": {"Knowledge": 0.0, "Welfare": 0.0},
            "world": {
                "temperatureAnomalyC": 1.0,
                "endOfOil": False,
                "pcgdpToReduceUnrestByOne": 10_000.0,
                "cohesionFixedImpact": 5.0,
                "unrestFixedImpact": 10.5,
                "initialCohesionRest": 5.0,
                "initialUnrestRest": 0.0,
            },
            "regions": [{
                "id": 100,
                "annualPopulationGrowthModifier": 0.0,
                "xenoformingLevel": 0.0,
                "nuclearDetonations": 0,
            }],
        },
    }


def _registered(server, save_path: Path, schemas: dict[str, dict]):
    inspected = anyio.run(_call, server, "inspect-save", {"save_path": str(save_path)})
    assert inspected.is_error is False
    jsonschema.validate(inspected.structured_content, schemas["inspect-save"])
    document = _context(inspected.structured_content["saveIdentity"])
    registration_args = {"document": document, "save_path": str(save_path), "pinned": False}
    jsonschema.validate(registration_args, next(
        tool.input_schema for tool in anyio.run(_list_tools, server).tools
        if tool.name == "register-visible-context"
    ))
    registered = anyio.run(_call, server, "register-visible-context", registration_args)
    assert registered.is_error is False
    jsonschema.validate(registered.structured_content, schemas["register-visible-context"])
    return document, registered.structured_content


def test_real_conditional_server_register_project_verify_and_schemas(tmp_path):
    save_path = _write_save(tmp_path)
    server = adapter.create_server(profile="conditional")
    schemas = _schemas(server)
    names = {tool.name for tool in anyio.run(_list_tools, server).tools}
    assert names == {
        "inspect-save", "capabilities", "register-visible-context",
        "conditional-nation-projection", "verify-visible-generation",
    }

    capabilities = anyio.run(_call, server, "capabilities")
    assert capabilities.is_error is False
    assert capabilities.structured_content["policy"]["rawSaveProjectionEnabled"] is False
    jsonschema.validate(capabilities.structured_content, schemas["capabilities"])

    document, registered = _registered(server, save_path, schemas)
    plans = [
        {"name": "knowledge-led", "pips": {"Knowledge": 3, "Welfare": 1}},
        {"name": "welfare-led", "pips": {"Knowledge": 1, "Welfare": 3}},
    ]
    project_args = {"receipt": registered["receipt"], "plans": plans}
    jsonschema.validate(project_args, next(
        tool.input_schema for tool in anyio.run(_list_tools, server).tools
        if tool.name == "conditional-nation-projection"
    ))
    projected = anyio.run(_call, server, "conditional-nation-projection", project_args)
    assert projected.is_error is False
    jsonschema.validate(projected.structured_content, schemas["conditional-nation-projection"])
    result = projected.structured_content
    assert result["status"] == "complete"
    assert result["result"]["authoritativeGameOutcome"] is False
    assert result["result"]["exactGameOutcome"] is False
    assert all(row["status"] == "conditional-complete" for row in result["result"]["plans"])

    verify_args = {
        "receipt": registered["receipt"],
        "projection_receipt": result["projectionReceipt"],
        "document": document,
    }
    jsonschema.validate(verify_args, next(
        tool.input_schema for tool in anyio.run(_list_tools, server).tools
        if tool.name == "verify-visible-generation"
    ))
    verified = anyio.run(_call, server, "verify-visible-generation", verify_args)
    assert verified.is_error is False
    jsonschema.validate(verified.structured_content, schemas["verify-visible-generation"])
    assert verified.structured_content["adviceStatus"] == "conditional-only"


def test_hidden_save_physics_do_not_override_explicit_context(tmp_path):
    baseline = make_save_data()
    altered = deepcopy(baseline)
    nation = altered["gamestates"]["TINationState"][0]["Value"]
    nation["GDP"] = 4_000_000_000_000.0
    nation["_accumulatedInvestmentPoints"] = {"Knowledge": 99_999.0, "Welfare": 0.0}
    nation["cohesionRestState_dailyCache"] = 9.0
    region = altered["gamestates"]["TIRegionState"][0]["Value"]
    region["populationInMillions"] = 2.0
    region["xenoforming"] = {"value": 101}
    altered["gamestates"]["TIXenoformingState"][0]["Value"]["xenoformingLevel"] = 20.0
    cp = altered["gamestates"]["TIControlPointState"][0]["Value"]
    cp["controlPointPriorities"] = {"Welfare": 3, "Knowledge": 0}

    paths = (_write_save(tmp_path, "baseline.gz", data=baseline),
             _write_save(tmp_path, "altered-hidden-state.gz", data=altered))
    server = adapter.create_server(profile="conditional")
    schemas = _schemas(server)
    outputs = []
    for index, path in enumerate(paths):
        _document, registered = _registered(server, path, schemas)
        plans = [{"name": "same-reported-plan", "pips": {"Knowledge": 3, "Welfare": 1}},
                 {"name": "comparison-plan", "pips": {"Knowledge": 1, "Welfare": 3}}]
        response = anyio.run(_call, server, "conditional-nation-projection", {
            "receipt": registered["receipt"], "plans": plans,
        })
        assert response.is_error is False, index
        outputs.append(response.structured_content["result"])

    first, second = outputs
    assert first["status"] == second["status"] == "complete"
    assert first["assumptions"] == second["assumptions"]
    for left, right in zip(first["plans"], second["plans"], strict=True):
        assert left["engineProjection"] == right["engineProjection"]


@pytest.mark.parametrize("defect", ["five-points", "duplicate-position", "foreign-owner"])
def test_visible_context_requires_exact_six_owned_control_points(tmp_path, defect):
    server = adapter.create_server(profile="conditional")
    schemas = _schemas(server)
    path = _write_save(tmp_path)
    document, _registered_context = _registered(server, path, schemas)
    changed = deepcopy(document)
    cps = changed["observations"]["nation"]["controlPoints"]
    if defect == "five-points":
        cps.pop()
    elif defect == "duplicate-position":
        cps[-1]["position"] = cps[-2]["position"]
    else:
        cps[-1]["ownerFactionId"] = 8
    response = anyio.run(_call, server, "register-visible-context", {
        "document": changed, "save_path": str(path), "pinned": False,
    })
    assert response.is_error is True
    jsonschema.validate(response.structured_content, schemas["register-visible-context"])
    assert response.structured_content["status"] == "error"


@pytest.mark.parametrize("defect", ["missing-reference", "foreign-owner", "five-save-points"])
def test_real_save_subject_rejects_bad_six_point_references(tmp_path, defect):
    data = make_save_data()
    nation = data["gamestates"]["TINationState"][0]["Value"]
    if defect == "missing-reference":
        nation["controlPoints"][0] = {"value": 9999}
    elif defect == "foreign-owner":
        data["gamestates"]["TIControlPointState"][0]["Value"]["faction"] = {"value": 8}
    else:
        nation["controlPoints"].pop()
        nation["numControlPoints"] = 5
    path = _write_save(tmp_path, data=data)
    server = adapter.create_server(profile="conditional")
    schemas = _schemas(server)
    inspected = anyio.run(_call, server, "inspect-save", {"save_path": str(path)})
    assert inspected.is_error is False
    context = _context(inspected.structured_content["saveIdentity"])
    response = anyio.run(_call, server, "register-visible-context", {
        "document": context, "save_path": str(path), "pinned": False,
    })
    assert response.is_error is True
    jsonschema.validate(response.structured_content, schemas["register-visible-context"])
    assert response.structured_content["status"] == "error"


def test_save_generation_change_after_projection_denies_verification(tmp_path):
    path = _write_save(tmp_path)
    server = adapter.create_server(profile="conditional")
    schemas = _schemas(server)
    document, registered = _registered(server, path, schemas)
    plans = [{"name": "knowledge-led", "pips": {"Knowledge": 3, "Welfare": 1}},
             {"name": "welfare-led", "pips": {"Knowledge": 1, "Welfare": 3}}]
    projected = anyio.run(_call, server, "conditional-nation-projection", {
        "receipt": registered["receipt"], "plans": plans,
    })
    assert projected.is_error is False

    replacement = make_save_data()
    replacement["gamestates"]["TINationState"][0]["Value"]["GDP"] += 1_000_000.0
    _write_save(tmp_path, path.name, data=replacement)
    verified = anyio.run(_call, server, "verify-visible-generation", {
        "receipt": registered["receipt"],
        "projection_receipt": projected.structured_content["projectionReceipt"],
        "document": document,
    })
    assert verified.is_error is True
    jsonschema.validate(verified.structured_content, schemas["verify-visible-generation"])
    assert verified.structured_content["status"] == "error"


def test_conditional_server_does_not_enable_raw_save_fair_play_projection(tmp_path):
    path = _write_save(tmp_path)
    server = adapter.create_server(profile="conditional")
    listed = anyio.run(_list_tools, server)
    assert "nation-projection" not in {tool.name for tool in listed.tools}
    denied = anyio.run(_call, server, "nation-projection", {
        "save_path": str(path), "nation_name": "United States", "days": 180,
    })
    assert denied.is_error is True
    assert "nation-projection" not in server._ti_parser_conditional_application.capabilities()["tools"]
