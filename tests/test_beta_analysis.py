import gzip
import io
import json
import sys
from pathlib import Path
from contextlib import redirect_stdout
from unittest.mock import patch
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import ti_save_parser as ti
import ti_parser_session as sessions
from ti_parser_errors import UserInputError
from ti_parser_core import CalculationDependencyError, CalculationDependency
from ti_parser_analysis import write_analysis
from ti_parser_capabilities import capabilities, CALCULATION_COMMANDS
from tests import test_package_only_runtime as fixtures


def test_bootstrap_loads_once_and_preserves_identity(tmp_path):
    save = fixtures.PackageOnlyRuntimeTests()._research_save(tmp_path)
    with patch.object(sessions, "load_save", wraps=sessions.load_save) as load, patch.object(sessions, "build_index", wraps=sessions.build_index) as index:
        session = sessions.AnalysisSession(save)
        inspected = session.inspect()
        deferred = session.analyze()
        result = session.analyze(allow_unverified=True)
    assert load.call_count == index.call_count == 1
    assert deferred["status"] == "deferred"
    assert result["status"] == "complete", result
    assert inspected["saveIdentity"] == result["saveIdentity"]
    assert set(result["sections"]) == {"topbar", "research-ui"}
    assert "controlPointMaintenance" in result["sections"]["topbar"]["result"]
    assert result["availableAnalyses"]
    assert not {"analyze", "inspect-save"} & {row["command"] for row in result["availableAnalyses"]}
    assert str(tmp_path) not in json.dumps(result)
    assert not any(k in result for k in ("nations", "habs", "fleets", "history"))


def test_partial_dependency_failure_preserves_other_section(tmp_path):
    session = sessions.AnalysisSession(fixtures.PackageOnlyRuntimeTests()._research_save(tmp_path))
    error = CalculationDependencyError(CalculationDependency("test", "required", "research", None, "missing"))
    with patch.object(sessions, "calculate_research_ui", side_effect=error):
        result = session.analyze(allow_unverified=True)
    assert result["status"] == "incomplete"
    assert result["sections"]["topbar"]["status"] == "complete"
    assert result["sections"]["research-ui"]["missingDependencies"]
    with patch.object(sessions, "calculate_topbar", side_effect=RuntimeError("programming bug")):
        with pytest.raises(RuntimeError):
            session.analyze(allow_unverified=True)


def test_calculator_incomplete_not_promoted(tmp_path):
    session = sessions.AnalysisSession(fixtures.PackageOnlyRuntimeTests()._research_save(tmp_path))
    with patch.object(sessions, "calculate_topbar", return_value={"status":"incomplete"}):
        result = session.analyze(allow_unverified=True)
    assert result["status"] == "incomplete"


def test_identity_changes_with_content_but_not_serialization(tmp_path):
    save = fixtures.PackageOnlyRuntimeTests()._save(tmp_path)
    first = sessions.AnalysisSession(save).facts["saveIdentity"]
    with gzip.open(save, "rt", encoding="utf-8") as handle:
        data = json.load(handle)
    other = tmp_path / "other.gz"
    with gzip.open(other, "wt", encoding="utf-8") as handle:
        json.dump(data, handle, sort_keys=True, indent=4)
    assert sessions.AnalysisSession(other).facts["saveIdentity"] == first
    data["extraSavedFact"] = 1
    with gzip.open(other, "wt", encoding="utf-8") as handle:
        json.dump(data, handle)
    assert sessions.AnalysisSession(other).facts["saveIdentity"]["fingerprint"] != first["fingerprint"]


def test_output_cannot_overwrite_source(tmp_path):
    save = fixtures.PackageOnlyRuntimeTests()._save(tmp_path)
    before = save.read_bytes()
    with pytest.raises(UserInputError):
        write_analysis({}, save, save)
    assert save.read_bytes() == before
    destination = tmp_path / "nested" / "report.json"
    write_analysis({"status":"deferred"}, destination, save)
    assert json.loads(destination.read_text())["status"] == "deferred"


def test_capabilities_matches_all_cli_commands_and_policies():
    import argparse
    from ti_parser_cli import build_parser
    parser = build_parser(ti)
    commands = next(a.choices for a in parser._actions if isinstance(a,argparse._SubParsersAction))
    inventory = {row["command"]: row for row in capabilities()["analyses"]}
    assert set(inventory) == set(commands)
    assert inventory["analyze"]["allowsExplicitUnverifiedConsent"] is True
    assert inventory["inspect-save"]["allowsExplicitUnverifiedConsent"] is False
    assert {name for name,row in inventory.items() if row["requiresVerifiedCompatibility"]} == CALCULATION_COMMANDS
    with patch.object(ti,"resolve_save_path",side_effect=AssertionError("must not read save")), redirect_stdout(io.StringIO()):
        assert ti.main(["capabilities"]) == 0


def test_analyze_cli_writes_same_report_and_explicit_status(tmp_path):
    save = fixtures.PackageOnlyRuntimeTests()._save(tmp_path)
    output = tmp_path / "report.json"
    stdout = io.StringIO()
    with redirect_stdout(stdout):
        code = ti.main(["--save",str(save),"analyze","--output",str(output)])
    assert code == 2
    assert json.loads(stdout.getvalue()) == json.loads(output.read_text(encoding="utf-8"))


def test_bootstrap_reuses_catalog_bundle_across_sections(tmp_path):
    from ti_parser_catalogs import RuntimeCatalogs
    session = sessions.AnalysisSession(fixtures.PackageOnlyRuntimeTests()._research_save(tmp_path))
    with patch.object(RuntimeCatalogs, "load", wraps=RuntimeCatalogs.load) as load:
        assert session.analyze(allow_unverified=True)["status"] == "complete"
    assert load.call_count == 1


def test_identity_supports_game_infinity_without_collapsing_strings(tmp_path):
    save = fixtures.PackageOnlyRuntimeTests()._save(tmp_path)
    with gzip.open(save, "rt", encoding="utf-8") as handle:
        data = json.load(handle)
    data["gameLimit"] = float("inf")
    with gzip.open(save, "wt", encoding="utf-8") as handle:
        json.dump(data, handle)
    first = sessions.AnalysisSession(save).facts["saveIdentity"]
    data["gameLimit"] = "Infinity"
    with gzip.open(save, "wt", encoding="utf-8") as handle:
        json.dump(data, handle)
    assert sessions.AnalysisSession(save).facts["saveIdentity"]["fingerprint"] != first["fingerprint"]


def test_allow_does_not_bypass_broken_registry_and_keeps_report_shareable(tmp_path):
    from ti_parser_compatibility import CompatibilityRegistryError
    session = sessions.AnalysisSession(fixtures.PackageOnlyRuntimeTests()._save(tmp_path))
    error = CompatibilityRegistryError("registry-invalid", f"Invalid registry: {tmp_path / 'registry.json'}", details={"path":str(tmp_path / 'registry.json')})
    with patch.object(sessions, "assess_compatibility", side_effect=error), patch.object(sessions, "calculate_topbar") as calculate:
        result = session.analyze(allow_unverified=True)
    calculate.assert_not_called()
    assert result["status"] == "incomplete"
    assert "saveIdentity" in result
    assert str(tmp_path) not in json.dumps(result)
    assert result["sections"]["topbar"]["error"]["code"] == "registry-invalid"
