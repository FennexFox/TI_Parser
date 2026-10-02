from __future__ import annotations

import copy
import argparse
import sys
from pathlib import Path
from typing import Literal, Mapping

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import ti_parser_config as config
import ti_parser_cli
import ti_parser_registry as registry
import ti_save_parser as public_api
from ti_parser_errors import UserInputError


def test_input_schema_covers_callable_analyses_and_returns_fresh_objects():
    for analysis in registry.ANALYSES:
        if not analysis.application_callable:
            continue
        schema = registry.get_input_schema(analysis.command)
        assert schema["type"] == "object"
        assert schema["additionalProperties"] is False
        assert set(schema["required"]) <= set(schema["properties"])

    inspect_schema = registry.get_input_schema("inspect-save")
    analyze_schema = registry.get_input_schema("analyze")
    assert inspect_schema["properties"] == {}
    assert analyze_schema["properties"] == {}

    schema = registry.get_input_schema("nation-projection")
    original = copy.deepcopy(schema)
    schema["properties"]["plan_payload"]["anyOf"][0]["type"] = "array"
    assert registry.get_input_schema("nation-projection") == original


def test_input_schema_preserves_required_defaults_unions_arrays_and_hides_internal_args():
    faction = registry.get_input_schema("faction")
    assert faction["required"] == ["name"]
    assert faction["properties"]["name"] == {
        "anyOf": [{"type": "string"}, {"type": "integer"}]
    }
    assert faction["properties"]["limit"]["default"] == 50

    projection = registry.get_input_schema("nation-projection")
    assert set(projection["required"]) == {"nation_name", "days"}
    assert projection["properties"]["checkpoints"] == {
        "anyOf": [
            {"type": "array", "items": {"type": "integer"}},
            {"type": "null"},
        ],
        "default": None,
    }
    assert "templates_dir" not in projection["properties"]
    assert "runtime_catalogs" not in projection["properties"]


def test_analysis_choice_metadata_and_schema_share_config_constants():
    cases = (
        ("org-plan", "focus", config.ORG_PLAN_FOCUS_CHOICES),
        ("hab-plan", "focus", config.HAB_PLAN_FOCUS_CHOICES),
        ("ship-plan", "role", config.SHIP_PLAN_ROLE_CHOICES),
        ("project-analysis", "sort_axis", config.PROJECT_ANALYSIS_SORT_CHOICES),
        ("topbar", "forecast_resource", config.HAB_MONTHLY_RESOURCES),
        ("research-plan", "mode", config.RESEARCH_PLAN_MODE_CHOICES),
    )
    for analysis_id, name, choices in cases:
        argument = next(item for item in registry.get_analysis(analysis_id).arguments if item.name == name)
        assert argument.as_dict()["choices"] == list(choices)
        schema = registry.get_input_schema(analysis_id)["properties"][name]
        if "anyOf" in schema:
            value_schema = next(branch for branch in schema["anyOf"] if branch.get("type") != "null")
            assert value_schema["enum"] == list(choices)
        else:
            assert schema["enum"] == list(choices)

    slot = registry.get_input_schema("project-analysis")["properties"]["slot"]
    assert slot["anyOf"] == [
        {"type": "integer", "enum": [3, 4, 5]},
        {"type": "null"},
    ]


def test_research_plan_cli_uses_the_shared_mode_choices():
    assert public_api.RESEARCH_PLAN_MODE_CHOICES is config.RESEARCH_PLAN_MODE_CHOICES
    parser = ti_parser_cli.build_parser(public_api)
    subparsers = next(action for action in parser._actions if isinstance(action, argparse._SubParsersAction))
    research_plan = subparsers.choices["research-plan"]
    mode = next(action for action in research_plan._actions if action.dest == "mode")
    assert tuple(mode.choices) == config.RESEARCH_PLAN_MODE_CHOICES


def test_plan_payload_object_or_null_is_a_shared_application_shape_rule():
    schema = registry.get_input_schema("nation-projection")["properties"]["plan_payload"]
    assert schema == {
        "anyOf": [{"type": "object"}, {"type": "null"}],
        "default": None,
    }
    registry.validate_argument_shape("nation-projection", "plan_payload", None)
    registry.validate_argument_shape("nation-projection", "plan_payload", {"plans": []})

    with pytest.raises(UserInputError) as caught:
        registry.validate_argument_shape("nation-projection", "plan_payload", "not-json-object")
    assert caught.value.code == "invalid-arguments"
    assert caught.value.context["argument"] == "plan_payload"

    kwargs = {"nation_name": "KOR", "days": 1, "plan_payload": []}
    with pytest.raises(UserInputError) as caught:
        registry.validate_arguments("nation-projection", kwargs)
    assert caught.value.code == "invalid-arguments"


def test_schema_rejects_unknown_analysis_and_non_callable_registry_entries():
    with pytest.raises(UserInputError) as unknown:
        registry.get_input_schema("missing-analysis")
    assert unknown.value.code == "unknown-analysis"

    with pytest.raises(UserInputError) as unsupported:
        registry.get_input_schema("capabilities")
    assert unsupported.value.code == "unsupported-analysis"


def test_schema_type_translator_preserves_richer_python_annotations():
    assert registry._schema_for_annotation(tuple[str, int]) == {
        "type": "array",
        "prefixItems": [{"type": "string"}, {"type": "integer"}],
        "items": False,
        "minItems": 2,
        "maxItems": 2,
    }
    assert registry._schema_for_annotation(Mapping[str, int]) == {
        "type": "object",
        "additionalProperties": {"type": "integer"},
    }
    assert registry._schema_for_annotation(Path) == {"type": "string"}
    assert registry._schema_for_annotation(Literal["first", "second"]) == {
        "enum": ["first", "second"],
        "type": "string",
    }
