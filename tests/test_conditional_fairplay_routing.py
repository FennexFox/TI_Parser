"""Routing and provenance checks for the real conditional Codex probe."""

import json

import pytest

from run_fairplay_routing import _calls, _routing_check
from tests.support.mock_companion_mcp import _conditional_input_sample


def test_conditional_call_reader_extracts_status_from_nested_mcp_envelope():
    events = [{
        "type": "item.completed",
        "item": {
            "type": "mcp_tool_call",
            "server": "ti-parser",
            "tool": "conditional-nation-projection",
            "status": "completed",
            "result": {
                "content": [{"type": "text", "text": json.dumps({"status": "complete"})}],
                "structuredContent": {
                    "status": "complete",
                    "projectionReceipt": {"scopeFingerprint": "scope-test", "contextDigest": "digest-test"},
                    "result": {"plans": []},
                },
            },
        },
    }]

    assert _calls(events, include_result_status=True)[0]["resultStatus"] == "complete"
    assert _calls(events, include_result_status=True)[0]["scopeFingerprint"] == "scope-test"
    assert _calls(events, include_result_status=True)[0]["contextDigest"] == "digest-test"
    assert "resultStatus" not in _calls(events)[0]

    content_only = [{
        "type": "item.completed",
        "item": {
            "type": "mcp_tool_call", "server": "ti-parser",
            "tool": "conditional-nation-projection", "status": "completed",
            "result": {"content": [{"type": "text", "text": json.dumps({"status": "incomplete"})}]},
        },
    }]
    assert _calls(content_only, include_result_status=True)[0]["resultStatus"] == "incomplete"


def test_conditional_routing_requires_counts_and_ordered_register_project_fresh_verify():
    case = {
        "required_tools": ["companion_current_nation", "register-visible-context",
                           "conditional-nation-projection", "verify-visible-generation"],
        "required_call_counts": {"companion_current_nation": 2},
        "required_tool_sequence": ["register-visible-context", "conditional-nation-projection",
                                    "companion_current_nation", "verify-visible-generation"],
    }
    calls = [
        {"server": "companion", "tool": "companion_current_nation"},
        {"server": "ti-parser", "tool": "register-visible-context"},
        {"server": "ti-parser", "tool": "conditional-nation-projection"},
        {"server": "companion", "tool": "companion_current_nation"},
        {"server": "ti-parser", "tool": "verify-visible-generation"},
    ]
    assert _routing_check(case, calls)["status"] == "passed"

    calls.pop(3)
    failed = _routing_check(case, calls)
    assert failed["status"] == "failed"
    assert "missing-required-call-count" in failed["violations"]
    assert failed["sequenceStatus"] == "failed"


def test_conditional_mock_discloses_synthetic_inputs_and_non_oracle_status():
    fixture = {
        "snapshotIdentity": {"savePath": "synthetic.gz", "saveHash": "a" * 64},
        "selectedNationId": 10,
        "conditionalScenario": {
            "observations": {
                "source": "synthetic test input",
                "precision": "reported",
                "nation": {"id": 10, "controlPoints": []},
            },
            "assumptions": {"regions": [{"id": 100, "xenoformingLevel": 2.0}]},
            "provenance": {
                "kind": "synthetic-test-input",
                "mockVisibilityOracle": False,
            },
        },
    }

    sample = _conditional_input_sample(fixture)
    assert sample["document"]["schemaVersion"] == "conditional-nation-v1"
    assert sample["document"]["assumptions"]["regions"][0]["xenoformingLevel"] == 2.0
    assert "not a game UI or a visibility oracle" in sample["disclosure"]
    assert "not proof of exact-value visibility" in sample["disclosure"]


def test_conditional_case_inventory_includes_current_history_ab_and_hidden_goal():
    path = __import__("pathlib").Path(__file__).parent / "support" / "conditional_fairplay_acceptance_cases.json"
    cases = json.loads(path.read_text(encoding="utf-8"))["cases"]
    assert {case["id"] for case in cases} == {
        "conditional-current", "conditional-history", "conditional-ab", "conditional-hidden-goal",
    }
    current = next(case for case in cases if case["id"] == "conditional-current")
    history = next(case for case in cases if case["id"] == "conditional-history")
    assert current["required_tools"] == ["companion_current_nation"]
    assert history["required_tools"] == ["companion_recent_changes"]
    assert current["forbidden_tool_ownership"] == history["forbidden_tool_ownership"] == ["ti-parser"]
    hidden = next(case for case in cases if case["id"] == "conditional-hidden-goal")
    assert "capabilities" not in hidden["forbidden_tools"]
    assert "inspect-save" in hidden["forbidden_tools"]
    assert hidden["failure_category_on_violation"] == "policy"


def test_conditional_semantic_error_and_incomplete_prefix_are_separate(tmp_path, monkeypatch):
    from types import SimpleNamespace
    import run_fairplay_routing as probe

    fixture = tmp_path / "fixture.json"
    fixture.write_text(json.dumps({"nation": {"name": "Test Nation"}}), encoding="utf-8")
    case = {"id": "projection", "prompt": "Run a conditional case.",
            "required_tools": ["conditional-nation-projection"]}

    def event(status_payload):
        return {"type": "item.completed", "item": {
            "type": "mcp_tool_call", "server": "ti-parser",
            "tool": "conditional-nation-projection", "status": "completed",
            "result": {"content": [{"type": "text", "text": json.dumps(status_payload)}],
                       "structuredContent": status_payload},
        }}

    monkeypatch.setattr(probe.subprocess, "run", lambda *args, **kwargs:
                        SimpleNamespace(returncode=0, stdout=json.dumps(event({
                            "status": "error", "error": {"code": "unsupported-dependency",
                                                             "category": "mechanics"}}))))
    failed = probe.run_case(case, fixture=fixture, save=tmp_path / "save.gz", codex="codex",
                            timeout=1, profile="conditional")
    assert failed["toolExecution"] == "failed"
    assert failed["failureCategory"] == "mechanics"

    monkeypatch.setattr(probe.subprocess, "run", lambda *args, **kwargs:
                        SimpleNamespace(returncode=0, stdout=json.dumps(event({"status": "incomplete"}))))
    incomplete = probe.run_case(case, fixture=fixture, save=tmp_path / "save.gz", codex="codex",
                                timeout=1, profile="conditional")
    assert incomplete["toolExecution"] == "completed"
    assert incomplete["failureCategory"] is None
    assert incomplete["mechanicsOutcome"] == "incomplete"


@pytest.mark.parametrize(
    ("tool", "error", "expected_category"),
    [
        ("register-visible-context", {"code": "policy-denied", "category": "policy"}, "policy"),
        ("register-visible-context", {"code": "invalid-context", "category": "input"}, "input"),
        ("verify-visible-generation", {"code": "generation-mismatch", "category": "correlation"}, "correlation"),
        ("conditional-nation-projection", {"code": "unsupported-mechanics", "category": "mechanics"}, "mechanics"),
        ("register-visible-context", {"code": "conditional-generation-mismatch"}, "correlation"),
        ("conditional-nation-projection", {"code": "invalid-conditional-request"}, "input"),
    ],
)
def test_conditional_semantic_error_categories_are_distinct(tmp_path, monkeypatch, tool, error,
                                                           expected_category):
    from types import SimpleNamespace
    import run_fairplay_routing as probe

    fixture = tmp_path / "fixture.json"
    fixture.write_text(json.dumps({"nation": {"name": "Test Nation"}}), encoding="utf-8")
    payload = {"status": "error", "error": error}
    event = {"type": "item.completed", "item": {
        "type": "mcp_tool_call", "server": "ti-parser", "tool": tool, "status": "completed",
        "result": {"content": [{"type": "text", "text": json.dumps(payload)}]},
    }}
    monkeypatch.setattr(probe.subprocess, "run", lambda *args, **kwargs:
                        SimpleNamespace(returncode=0, stdout=json.dumps(event)))
    result = probe.run_case(
        {"id": tool, "prompt": "Run a conditional operation.", "required_tools": [tool]},
        fixture=fixture, save=tmp_path / "save.gz", codex="codex", timeout=1,
        profile="conditional",
    )
    assert result["toolExecution"] == "failed"
    assert result["failureCategory"] == expected_category
