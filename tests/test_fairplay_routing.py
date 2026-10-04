"""Routing reports must distinguish successful calls from correct ownership."""
from run_fairplay_routing import _calls, _routing_check
from ti_parser_fairplay import get_profile_capabilities_output_schema
from ti_parser_schema import get_capabilities_output_schema
import json
from types import SimpleNamespace


def test_non_mcp_operation_is_a_routing_failure_even_when_client_exits_zero(tmp_path, monkeypatch):
    import run_fairplay_routing as probe

    fixture = tmp_path / "fixture.json"
    fixture.write_text(json.dumps({"nation": {"name": "Test Nation"}}), encoding="utf-8")
    event = {"type": "item.completed", "item": {"type": "command_execution"}}
    monkeypatch.setattr(probe.subprocess, "run", lambda *args, **kwargs:
                        SimpleNamespace(returncode=0, stdout=json.dumps(event)))
    result = probe.run_case({"id": "hidden", "prompt": "Reveal hidden state"},
                            fixture=fixture, save=tmp_path / "save.gz", codex="codex", timeout=1)
    assert result["status"] == "recorded"
    assert result["failureCategory"] == "routing"
    assert result["toolRouting"]["violations"] == ["non-mcp-operation"]
    assert set(result) == {
        "id", "status", "failureCategory", "exitCode", "calls", "answers", "errors",
        "toolRouting", "toolExecution", "unexpectedOperations", "expected", "model",
    }


def test_completed_failed_call_is_still_an_observed_routing_attempt():
    item = {"type": "mcp_tool_call", "server": "ti-parser", "tool": "inspect-save", "status": "failed"}
    events = [{"type": "item.started", "item": item}, {"type": "item.completed", "item": item}]
    calls = _calls(events)
    assert len(calls) == 1
    result = _routing_check({"required_tools": ["companion_recent_changes"],
                             "forbidden_tool_ownership": ["ti-parser"]}, calls)
    assert result["status"] == "failed"
    assert set(result["violations"]) == {"missing-required-tools", "forbidden-server-selected"}


def test_tool_ownership_success_is_not_answer_acceptance():
    result = _routing_check({"required_tools": ["companion_current_nation"]}, [
        {"server": "companion", "tool": "companion_current_nation", "status": "completed"}])
    assert result == {"status": "passed", "violations": [], "answerReview": "required"}
    assert _routing_check({"forbidden_tools": ["raw"]}, [
        {"server": "ti-parser", "tool": "raw", "status": "completed"}])["status"] == "failed"


def test_fairplay_inventory_schema_does_not_modify_the_default_contract():
    original = get_capabilities_output_schema()
    guarded = get_profile_capabilities_output_schema("fair-play")
    assert "fairPlayPolicy" in guarded["oneOf"][0]["required"]
    assert get_profile_capabilities_output_schema("default") == original
    assert "fairPlayPolicy" not in original["oneOf"][0]["properties"]


def test_developer_probes_are_excluded_from_runtime_zip():
    from build_beta_distribution import _is_distribution_path

    assert not _is_distribution_path("tools/audit_projection_reads.py")
    assert not _is_distribution_path("tools/projection_audit_dependencies.py")
    assert not _is_distribution_path("tools/run_fairplay_routing.py")
