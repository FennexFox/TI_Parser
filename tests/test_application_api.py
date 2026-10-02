"""Contract tests for the reusable machine-facing application API."""

from __future__ import annotations

import io
import json
import sys
from copy import deepcopy
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import ti_parser_application as application
import ti_parser_capabilities as capability_layer
import ti_parser_registry as registry
import ti_parser_session as session_layer
import ti_save_parser as cli_api
from ti_parser_core import CalculationDependency, CalculationDependencyError
from tests import test_package_only_runtime as fixtures


def _save(tmp_path: Path, *, research: bool = False, scenario: str = "ModernScenario") -> Path:
    factory = fixtures.PackageOnlyRuntimeTests()
    if research:
        return factory._research_save(tmp_path)
    return factory._save(tmp_path, scenario)


def _descriptor_name(descriptor):
    """Read the stable registry name across mapping and descriptor forms."""

    if isinstance(descriptor, dict):
        return descriptor.get("analysis", descriptor.get("command", descriptor.get("name")))
    for field in ("analysis", "analysis_id", "command", "name", "id"):
        value = getattr(descriptor, field, None)
        if value is not None:
            return value
    return None


def _registry_names() -> set[str]:
    descriptors = registry.ANALYSES
    if isinstance(descriptors, dict):
        return set(descriptors)
    return {_descriptor_name(descriptor) for descriptor in descriptors}


def _cli_result(save: Path, command: str, *arguments: str) -> dict:
    output = io.StringIO()
    with redirect_stdout(output):
        code = cli_api.main(
            ["--allow-unverified", "--save", str(save), command, *arguments, "--compact"]
        )
    assert code == 0, output.getvalue()
    return json.loads(output.getvalue())


def test_registry_descriptors_and_application_handlers_cover_machine_routes():
    names = _registry_names()
    assert {"topbar", "research-ui", "world-ui"} <= names
    assert len(registry.PRIMARY_ANALYSIS_IDS) == 19
    assert registry.PRIMARY_ANALYSIS_IDS <= set(application.HANDLERS)
    for name in registry.PRIMARY_ANALYSIS_IDS:
        descriptor = registry.get_analysis(name)
        assert descriptor is not None
        handler = getattr(descriptor, "handler", None)
        if handler is None and isinstance(descriptor, dict):
            handler = descriptor.get("handler")
        assert callable(handler)

    assert {"topbar", "research-ui", "world-ui"} <= set(application.HANDLERS)


def test_capabilities_primary_routes_exclude_raw_types_and_ai_diagnostics():
    inventory = capability_layer.capabilities()["analyses"]
    primary = {
        row["command"]
        for row in inventory
        if row.get("routingClass") == "primary"
    }
    assert {"topbar", "research-ui", "world-ui"} <= primary
    assert not {"raw", "types", "ai-fleet-diagnostics"} & primary


def test_run_success_envelope_contains_context_and_result(tmp_path):
    save = _save(tmp_path)
    payload = {"resources": {"Money": {"current": 42.0}}}
    session = session_layer.AnalysisSession(save)

    with patch.object(application, "calculate_topbar", return_value=payload):
        envelope = session.run("topbar", allow_unverified=True)

    assert envelope["schemaVersion"] == 1
    assert envelope["parserVersion"]
    assert envelope["analysis"] == "topbar"
    assert envelope["saveIdentity"] == session.facts["saveIdentity"]
    assert envelope["compatibility"]["unverifiedAllowed"] is True
    assert envelope["status"] == "complete"
    assert envelope["result"] == payload
    assert "error" not in envelope
    assert "missingDependencies" not in envelope


def test_run_unknown_analysis_returns_error_envelope(tmp_path):
    session = session_layer.AnalysisSession(_save(tmp_path))

    envelope = session.run("does-not-exist")

    assert envelope["analysis"] == "does-not-exist"
    assert envelope["status"] == "error"
    assert envelope["error"]
    assert "result" not in envelope


def test_run_rejects_missing_required_arguments_with_context(tmp_path):
    session = session_layer.AnalysisSession(_save(tmp_path))

    envelope = session.run("nation-projection", allow_unverified=True, nation_name="KOR")

    assert envelope["status"] == "error"
    assert envelope["error"]["code"] == "invalid-arguments"
    assert "days" in envelope["error"]["context"]["missingArguments"]


@pytest.mark.parametrize(
    ("kwargs", "expected_code"),
    (
        ({"include_details": "yes"}, "invalid-arguments"),
        ({"forecast_resource": 17}, "invalid-arguments"),
        ({"research_templates": object()}, "invalid-input"),
    ),
)
def test_run_rejects_invalid_or_private_runtime_arguments(tmp_path, kwargs, expected_code):
    session = session_layer.AnalysisSession(_save(tmp_path))

    with patch.object(application, "calculate_topbar") as calculate:
        envelope = session.run("topbar", allow_unverified=True, **kwargs)

    assert envelope["status"] == "error"
    assert envelope["error"]["code"] == expected_code
    calculate.assert_not_called()


def test_run_unverified_calculation_is_deferred_before_handler(tmp_path):
    session = session_layer.AnalysisSession(_save(tmp_path))

    with patch.object(application, "calculate_topbar") as calculate:
        envelope = session.run("topbar")

    assert envelope["status"] == "deferred"
    assert envelope["compatibility"]["unverifiedAllowed"] is False
    assert envelope["error"]
    calculate.assert_not_called()


def test_run_rejects_non_boolean_unverified_consent(tmp_path):
    session = session_layer.AnalysisSession(_save(tmp_path))

    with patch.object(application, "calculate_topbar") as calculate:
        envelope = session.run("topbar", allow_unverified="false")

    assert envelope["status"] == "error"
    assert envelope["error"]["code"] == "invalid-arguments"
    assert envelope["compatibility"]["unverifiedAllowed"] is False
    calculate.assert_not_called()


def test_run_dependency_failure_is_incomplete_and_structured(tmp_path):
    session = session_layer.AnalysisSession(_save(tmp_path))
    dependency = CalculationDependency(
        "catalog", "required-row", "application.test", "ModernScenario", "fixture dependency"
    )
    failure = CalculationDependencyError(dependency)

    with patch.object(application, "calculate_topbar", side_effect=failure):
        envelope = session.run("topbar", allow_unverified=True)

    assert envelope["status"] == "incomplete"
    assert envelope["missingDependencies"] == failure.missing_dependencies
    assert "result" not in envelope


def test_success_and_dependency_failure_share_save_context(tmp_path):
    session = session_layer.AnalysisSession(_save(tmp_path))
    dependency = CalculationDependency(
        "catalog", "required-row", "application.test", "ModernScenario", "fixture dependency"
    )

    with patch.object(application, "calculate_topbar", return_value={"ok": True}):
        success = session.run("topbar", allow_unverified=True)
    with patch.object(application, "calculate_topbar", side_effect=CalculationDependencyError(dependency)):
        failure = session.run("topbar", allow_unverified=True)

    assert success["status"] == "complete"
    assert failure["status"] == "incomplete"
    for field in ("schemaVersion", "parserVersion", "analysis", "saveIdentity", "compatibility"):
        assert failure[field] == success[field]


def test_run_preserves_partial_projection_result_and_marks_envelope_incomplete(tmp_path):
    session = session_layer.AnalysisSession(_save(tmp_path))
    partial = {
        "plans": [
            {
                "name": "complete-plan",
                "status": "complete",
                "scopeStatus": {"worldMarket": {"status": "complete"}},
            },
            {
                "name": "partial-plan",
                "status": "incomplete",
                "scopeStatus": {"worldMarket": {"status": "incomplete"}},
                "authoritativeFinalState": {"controlPoints": {"raw": [1, 0, 0]}},
                "missingDependencies": [{"kind": "market", "name": "price", "reason": "fixture"}],
            },
        ],
        "comparison": {"excludedIncompletePlans": ["partial-plan"]},
    }

    with patch.object(application, "calculate_nation_projection", return_value=partial):
        envelope = session.run(
            "nation-projection",
            allow_unverified=True,
            nation_name="KOR",
            faction_name=None,
            plan_payload=None,
            days=1,
            checkpoints=[],
            details=False,
            diagnostics=False,
        )

    assert envelope["status"] == "incomplete"
    assert envelope["result"] == partial
    assert envelope["result"]["plans"][1]["authoritativeFinalState"] == partial["plans"][1]["authoritativeFinalState"]
    assert envelope["result"]["plans"][1]["scopeStatus"] == partial["plans"][1]["scopeStatus"]


@pytest.mark.parametrize(
    "projection_updates",
    (
        {"days": 0},
        {"days": -1},
        {"days": 1, "checkpoints": [2]},
        {"days": 1, "checkpoints": "1,2"},
        {"days": 1, "checkpoints": [True]},
    ),
)
def test_projection_handler_rejects_invalid_horizon_and_checkpoints(tmp_path, projection_updates):
    session = session_layer.AnalysisSession(_save(tmp_path))
    kwargs = {
        "nation_name": "KOR",
        "faction_name": None,
        "plan_payload": None,
        "days": 1,
        "checkpoints": [],
        "details": False,
        "diagnostics": False,
    }
    kwargs.update(projection_updates)

    with patch.object(application, "calculate_nation_projection") as calculate:
        envelope = session.run("nation-projection", allow_unverified=True, **kwargs)

    assert envelope["status"] == "error"
    assert envelope["error"]
    calculate.assert_not_called()


def test_run_unexpected_programming_exception_propagates(tmp_path):
    session = session_layer.AnalysisSession(_save(tmp_path))

    with patch.object(application, "calculate_topbar", side_effect=RuntimeError("programming bug")):
        with pytest.raises(RuntimeError, match="programming bug"):
            session.run("topbar", allow_unverified=True)


def test_broken_compatibility_registry_preserves_context_and_stops_calculation(tmp_path):
    from ti_parser_compatibility import CompatibilityRegistryError
    session = session_layer.AnalysisSession(_save(tmp_path))
    failure = CompatibilityRegistryError("registry-invalid", "Invalid fixture registry")
    with patch.object(session_layer, "assess_compatibility", side_effect=failure), patch.object(application, "calculate_topbar") as calculate:
        envelope = session.run("topbar", allow_unverified=True)
        inspection = session.run("inspect-save")
    assert envelope["status"] == "incomplete"
    assert envelope["error"]["code"] == "registry-invalid"
    assert envelope["saveIdentity"] == inspection["saveIdentity"]
    assert envelope["compatibility"] == inspection["compatibility"] | {"unverifiedAllowed": True}
    calculate.assert_not_called()


def test_catalog_integrity_failure_remains_a_blocking_dependency_with_context(tmp_path):
    from ti_parser_catalogs import CatalogIntegrityError, RuntimeCatalogs
    session = session_layer.AnalysisSession(_save(tmp_path))
    with patch.object(RuntimeCatalogs, "load", side_effect=CatalogIntegrityError("Corrupt fixture bundle")):
        envelope = session.run("topbar", allow_unverified=True)
    assert envelope["status"] == "incomplete"
    assert envelope["missingDependencies"][0]["kind"] == "catalog-integrity"
    assert envelope["saveIdentity"] == session.facts["saveIdentity"]
    assert envelope["compatibility"] == session.compatibility | {"unverifiedAllowed": True}
    assert "result" not in envelope


def test_legacy_calculate_keeps_direct_payload_and_runtime_override_options(tmp_path):
    session = session_layer.AnalysisSession(_save(tmp_path))
    templates, cache = object(), {2: 3.0}
    payload = {"resources": {}}
    with patch.object(application, "calculate_topbar", return_value=payload) as calculate:
        result = session.calculate("topbar", allow_unverified=True, research_templates=templates, base_daily_cache=cache)
    assert result is payload
    assert calculate.call_args.kwargs["research_templates"] is templates
    assert calculate.call_args.kwargs["base_daily_cache"] is cache


def test_sequential_calls_reuse_save_index_and_matching_catalog_bundle(tmp_path):
    save = _save(tmp_path, research=True)
    original_load = session_layer.load_save
    original_index = session_layer.build_index
    from ti_parser_catalogs import RuntimeCatalogs

    with (
        patch.object(session_layer, "load_save", wraps=original_load) as load,
        patch.object(session_layer, "build_index", wraps=original_index) as index,
        patch.object(RuntimeCatalogs, "load", wraps=RuntimeCatalogs.load) as catalogs,
    ):
        session = session_layer.AnalysisSession(save)
        assert session.run("topbar", allow_unverified=True)["status"] == "complete"
        assert session.run("topbar", allow_unverified=True)["status"] == "complete"

    assert load.call_count == 1
    assert index.call_count == 1
    assert catalogs.call_count == 1


def test_catalog_failure_is_not_cached_and_session_scope_is_restored(tmp_path):
    from ti_parser_catalogs import CatalogIntegrityError, RuntimeCatalogs, load_runtime_catalogs

    session = session_layer.AnalysisSession(_save(tmp_path))
    loaded = object()
    failure = CatalogIntegrityError("fixture catalog failure")

    with patch.object(RuntimeCatalogs, "load", side_effect=[failure, loaded]) as load:
        with pytest.raises(CatalogIntegrityError):
            with session.calculation_scope(allow_unverified=True):
                load_runtime_catalogs("ModernScenario")

        with session.calculation_scope(allow_unverified=True):
            assert load_runtime_catalogs("ModernScenario") is loaded
        with session.calculation_scope(allow_unverified=True):
            assert load_runtime_catalogs("ModernScenario") is loaded

    assert load.call_count == 2


def test_nested_sessions_keep_their_catalog_caches_isolated(tmp_path):
    from ti_parser_catalogs import RuntimeCatalogs, load_runtime_catalogs

    save = _save(tmp_path)
    first = session_layer.AnalysisSession(save)
    second = session_layer.AnalysisSession(save)

    with patch.object(RuntimeCatalogs, "load", wraps=RuntimeCatalogs.load) as load:
        with first.calculation_scope(allow_unverified=True):
            first_catalogs = load_runtime_catalogs("ModernScenario")
            with second.calculation_scope(allow_unverified=True):
                second_catalogs = load_runtime_catalogs("ModernScenario")
                with first.calculation_scope(allow_unverified=True):
                    assert load_runtime_catalogs("ModernScenario") is first_catalogs
            assert load_runtime_catalogs("ModernScenario") is first_catalogs

    assert first_catalogs is not second_catalogs
    assert load.call_count == 2


def test_sessions_are_isolated_for_catalog_cache_and_save_index(tmp_path):
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"
    first_root.mkdir()
    second_root.mkdir()
    first_save = _save(first_root)
    second_save = _save(second_root, research=True)
    from ti_parser_catalogs import RuntimeCatalogs

    with patch.object(RuntimeCatalogs, "load", wraps=RuntimeCatalogs.load) as load:
        first = session_layer.AnalysisSession(first_save)
        second = session_layer.AnalysisSession(second_save)
        first.run("topbar", allow_unverified=True)
        second.run("topbar", allow_unverified=True)

    assert first._catalog_cache is not second._catalog_cache
    assert first.facts["saveIdentity"] != second.facts["saveIdentity"]
    assert load.call_count == 2


def test_snapshot_uses_existing_session_index(tmp_path):
    save = _save(tmp_path)
    session = session_layer.AnalysisSession(save)

    with patch("ti_parser_snapshot.build_index", side_effect=AssertionError("snapshot rebuilt index")):
        envelope = session.run("summary", allow_unverified=True)

    assert envelope["status"] == "complete"
    assert envelope["result"]


@pytest.mark.parametrize(
    ("command", "research"),
    (("topbar", False), ("research-ui", True), ("world-ui", False)),
)
def test_application_result_matches_real_cli_for_primary_ui_routes(tmp_path, command, research):
    save = _save(tmp_path, research=research)
    session = session_layer.AnalysisSession(save)

    envelope = session.run(command, allow_unverified=True)
    cli_result = _cli_result(save, command)
    cli_compatibility = cli_result.pop("compatibility")

    assert envelope["status"] == "complete", envelope
    assert cli_compatibility == envelope["compatibility"]
    assert envelope["result"] == cli_result


def test_handler_specific_research_ui_shape_is_preserved(tmp_path):
    save = _save(tmp_path, research=True)
    session = session_layer.AnalysisSession(save)

    envelope = session.run("research-ui", allow_unverified=True)

    assert envelope["status"] == "complete"
    assert "projects" in envelope["result"]
    assert "active" in envelope["result"]["projects"]
    assert "pausedOrStored" in envelope["result"]["projects"]


@pytest.mark.parametrize("command", ["topbar", "research-ui"])
def test_integer_faction_selector_matches_default_player_in_api_and_cli(tmp_path, command):
    from ti_parser_core import find_faction_state
    save = _save(tmp_path, research=True)
    session = session_layer.AnalysisSession(save)
    faction_id, _ = find_faction_state(session.indexed)
    default = session.run(command, allow_unverified=True)
    selected = session.run(command, allow_unverified=True, faction_name=faction_id)
    actual = _cli_result(save, command, "--entity-id", str(faction_id))
    actual.pop("compatibility")
    assert default["status"] == selected["status"] == "complete"
    assert default["result"] == selected["result"] == actual


def test_all_faction_arguments_accept_integer_ids_at_application_boundary():
    for entry in registry.ANALYSES:
        if not any(argument.name == "faction_name" for argument in entry.arguments):
            continue
        kwargs = {argument.name: (1 if argument.name == "days" else "Target")
                  for argument in entry.arguments if argument.required}
        kwargs["faction_name"] = 2
        registry.validate_arguments(entry, kwargs)


def test_application_run_rejects_invalid_research_plan_mode_before_calculation(tmp_path, monkeypatch):
    session = session_layer.AnalysisSession(_save(tmp_path, research=True))

    def forbid_calculation(*_args, **_kwargs):
        raise AssertionError("invalid analysis arguments must be rejected before calculation")

    monkeypatch.setattr(session, "calculate", forbid_calculation)
    envelope = session.run("research-plan", allow_unverified=True, mode="unsupported-mode")

    assert envelope["status"] == "error"
    assert envelope["error"]["code"] == "invalid-arguments"
    assert "result" not in envelope


def test_ship_plan_design_api_matches_cli_and_keeps_only_selected_design(tmp_path):
    save = fixtures.PackageOnlyRuntimeTests()._ship_save(tmp_path)
    session = session_layer.AnalysisSession(save)

    envelope = session.run(
        "ship-plan",
        allow_unverified=True,
        faction_name="ResistCouncil",
        top=1,
        design_name="Package Test Ship",
    )
    cli_result = _cli_result(
        save,
        "ship-plan",
        "ResistCouncil",
        "--top",
        "1",
        "--design",
        "Package Test Ship",
    )
    cli_result.pop("compatibility")

    assert envelope["status"] == "complete", envelope
    assert envelope["result"] == cli_result
    assert set(envelope["result"]) == {"faction", "date", "selectedDesign", "limitations"}
    assert envelope["result"]["selectedDesign"]["display"] == "Package Test Ship"


def test_nation_claims_diagnostics_api_matches_cli_reshaping(tmp_path):
    save = fixtures.PackageOnlyRuntimeTests()._claims_save(tmp_path)
    session = session_layer.AnalysisSession(save)

    envelope = session.run(
        "nation-claims",
        allow_unverified=True,
        claimant_name="CLA",
        diagnostics=True,
    )
    cli_result = _cli_result(save, "nation-claims", "CLA", "--diagnostics")
    cli_result.pop("compatibility")

    assert envelope["status"] == "complete", envelope
    assert envelope["result"] == cli_result
    assert set(envelope["result"]["calculationDiagnostics"]) == {"runtime", "claims"}


def test_councilor_context_selection_does_not_mutate_cached_snapshot(tmp_path):
    session = session_layer.AnalysisSession(_save(tmp_path))
    snapshot = {
        "councilors": [
            {
                "id": 20,
                "template": "PackageCouncilor",
                "display": "Package Councilor",
                "locationNation": {"id": 1, "template": "HOME", "display": "Home"},
                "conditionalTraitMods": [{"trait": "Diplomat"}],
                "evaluatedConditionalTraitMods": [{"old": True}],
            }
        ],
        "nations": [
            {"id": 1, "template": "HOME", "display": "Home"},
            {"id": 2, "template": "TARGET", "display": "Target"},
        ],
    }
    session.__dict__["_snapshot"] = snapshot
    before = deepcopy(snapshot)

    with patch.object(
        application,
        "evaluate_councilor_conditionals",
        return_value={"evaluatedConditionalTraitMods": [{"context": "selected"}]},
    ) as evaluate:
        target = session.run(
            "councilor",
            allow_unverified=True,
            name="Package Councilor",
            target_nation="Target",
        )
        current = session.run(
            "councilor",
            allow_unverified=True,
            name="Package Councilor",
            current_location_context=True,
        )

    assert target["status"] == current["status"] == "complete"
    assert evaluate.call_count == 2
    first_call = evaluate.call_args_list[0].args
    second_call = evaluate.call_args_list[1].args
    assert first_call[1] is snapshot
    assert first_call[2] is snapshot["nations"][1]
    assert first_call[3] == "targetNation"
    assert second_call[1] is snapshot
    assert second_call[2] is snapshot["councilors"][0]["locationNation"]
    assert second_call[3] == "currentLocation"
    assert snapshot == before


def test_summary_rejects_unresolved_player_metadata_despite_human_player_candidate(tmp_path):
    factory = fixtures.PackageOnlyRuntimeTests()
    gamestates = factory._base_gamestates()
    gamestates["TIMetadataState"] = [
        fixtures.state(7, {"playerFactionName": "Missing Faction"})
    ]
    save = factory._write_save(tmp_path, "unresolved-player-metadata", gamestates)
    session = session_layer.AnalysisSession(save)

    envelope = session.run("summary", allow_unverified=True)

    assert envelope["saveIdentity"]["playerFaction"]["status"] == "unresolved"
    assert envelope["status"] == "error"
    assert envelope["error"]["code"] == "player-faction-unresolved"


def test_summary_resolves_player_metadata_through_campaign_code(tmp_path):
    factory = fixtures.PackageOnlyRuntimeTests()
    gamestates = factory._base_gamestates()
    faction = factory._value(gamestates, "TIFactionState", 2)
    faction["templateName"] = "2030_Resistance"
    faction["displayName"] = None
    gamestates["TIMetadataState"] = [
        fixtures.state(7, {"playerFactionName": "Resistance"})
    ]
    save = factory._write_save(tmp_path, "campaign-code-player-metadata", gamestates)
    session = session_layer.AnalysisSession(save)

    envelope = session.run("summary", allow_unverified=True)

    assert envelope["saveIdentity"]["playerFaction"]["status"] == "resolved"
    assert envelope["status"] == "complete"
    assert envelope["result"]["faction"]["template"] == "2030_Resistance"
