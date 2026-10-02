"""Pure machine-facing application handlers for parser analyses.

The functions in this module accept an already loaded indexed save or compact
snapshot and return the calculated value.  They deliberately do not know about
the command line, output formatting, save loading, or snapshot cache files.
The domain ``calculate_*`` functions remain authoritative for mechanics; these
handlers only assemble the arguments and the small command-level selections
that historically lived in :mod:`ti_parser_commands`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ti_parser_ai import calculate_ai_fleet_diagnostics
from ti_parser_claims import calculate_nation_claims
from ti_parser_config import DAYS_PER_YEAR
from ti_parser_core import (
    as_float,
    campaign_code,
    clean_numbers,
    faction_effect_contexts,
    find_faction_state,
    match_raw_state,
    ref_id,
    state_value_by_id,
)
from ti_parser_errors import UserInputError
from ti_parser_hab_plan import calculate_hab_plan
from ti_parser_hab_ui import calculate_hab_slots, calculate_hab_ui
from ti_parser_nation_ui import calculate_nation_ui
from ti_parser_nation_projection import ProjectionInputError
from ti_parser_project_analysis import calculate_project_analysis
from ti_parser_projection_adapter import calculate_nation_projection
from ti_parser_research import calculate_research_breakdown, calculate_research_ui
from ti_parser_research_plan import calculate_research_plan
from ti_parser_runtime import (
    active_owned_control_points,
    calculate_org_plan,
    calculation_catalogs,
    councilor_summary_maps,
    evaluate_councilor_conditionals,
    match_named,
    nation_population_millions,
    nation_research_contribution_month,
)
from ti_parser_ship_plan import calculate_ship_plan
from ti_parser_topbar import calculate_topbar
from ti_parser_world import calculate_world_ui


_RUNTIME_OVERRIDES = frozenset({"research_templates", "base_daily_cache"})


def dispatch(analysis_id: str, source: Any, *, templates_dir: Path | None = None, **kwargs: Any) -> Any:
    """Run one registered analysis against an existing indexed source.

    The registry owns argument validation and application-callability policy.
    ``templates_dir`` remains in the CLI wrapper signature for compatibility,
    but normal application execution is package-only and rejects a supplied
    template tree.  The remaining internal overrides are retained solely for
    the legacy session calculation path and are validated by the registry with
    its explicit runtime-override opt-in.
    """

    if templates_dir is not None:
        raise UserInputError(
            "templates_dir is verification-only; application calculations use packaged catalogs.",
            code="templates-dir-not-allowed",
        )

    from ti_parser_registry import get_analysis, validate_arguments

    entry = get_analysis(analysis_id)
    internal = {name for name in kwargs if name in _RUNTIME_OVERRIDES}
    if internal and analysis_id not in {"topbar", "research-ui"}:
        raise UserInputError(
            "Runtime overrides are supported only for topbar and research-ui compatibility calls.",
            code="invalid-arguments",
            context={"analysis": analysis_id, "arguments": sorted(internal)},
        )
    validate_arguments(entry, kwargs, allow_runtime_overrides=bool(internal))
    handler = entry.handler
    if handler is None:
        raise UserInputError(
            f"Analysis is not callable through the application API: {analysis_id}",
            code="unsupported-analysis",
            context={"analysis": analysis_id},
        )
    if entry.input_kind == "snapshot":
        if internal:
            raise UserInputError(
                "Runtime overrides are not supported for snapshot analyses.",
                code="invalid-arguments",
                context={"analysis": analysis_id},
            )
        return handler(source, **kwargs)
    return handler(source, None, **kwargs)


# Indexed-save analyses -----------------------------------------------------


def handle_org_plan(
    indexed: Any,
    templates_dir: Path | None = None,
    faction_name: str | int | None = None,
    focus: str = "balanced",
    top: int = 5,
    include_unassigned: bool = True,
    max_actions: int = 4,
    beam_width: int = 8,
    include_all_candidates: bool = False,
) -> dict[str, Any]:
    return calculate_org_plan(
        indexed,
        templates_dir,
        faction_name=faction_name,
        focus=focus,
        top=top,
        include_unassigned=include_unassigned,
        max_actions=max_actions,
        beam_width=beam_width,
        include_all_candidates=include_all_candidates,
    )


def handle_hab_ui(
    indexed: Any,
    templates_dir: Path | None = None,
    *,
    hab_name: str | int,
) -> dict[str, Any]:
    return calculate_hab_ui(indexed, templates_dir, hab_name)


def handle_hab_slots(
    indexed: Any,
    templates_dir: Path | None = None,
    faction_name: str | int | None = None,
    include_all: bool = False,
    include_module_counts: bool = False,
) -> dict[str, Any]:
    return clean_numbers(calculate_hab_slots(
        indexed,
        templates_dir,
        faction_name=faction_name,
        include_all=include_all,
        include_module_counts=include_module_counts,
    ), 6)


def handle_hab_plan(
    indexed: Any,
    templates_dir: Path | None = None,
    faction_name: str | int | None = None,
    hab_name: str | int | None = None,
    upgrading_to_tier: int | None = None,
    include_all: bool = False,
    focus: str = "balanced",
    top: int = 8,
) -> dict[str, Any]:
    return calculate_hab_plan(
        indexed,
        templates_dir,
        faction_name=faction_name,
        hab_name=hab_name,
        upgrading_to_tier=upgrading_to_tier,
        include_all=include_all,
        focus=focus,
        top=top,
    )


def handle_project_analysis(
    indexed: Any,
    templates_dir: Path | None = None,
    faction_name: str | int | None = None,
    top: int = 10,
    sort_axis: str = "research-sustainable",
    slot: int | None = None,
    include_active: bool = False,
    include_all: bool = False,
) -> dict[str, Any]:
    return calculate_project_analysis(
        indexed,
        templates_dir,
        faction_name=faction_name,
        top=top,
        sort_axis=sort_axis,
        slot=slot,
        include_active=include_active,
        include_all=include_all,
    )


def handle_research(
    indexed: Any,
    templates_dir: Path | None = None,
    faction_name: str | int | None = None,
    include_details: bool = False,
) -> dict[str, Any]:
    return calculate_research_breakdown(
        indexed,
        templates_dir,
        faction_name,
        include_details=include_details,
    )


def handle_research_ui(
    indexed: Any,
    templates_dir: Path | None = None,
    faction_name: str | int | None = None,
    *,
    templates: Any | None = None,
    base_daily_cache: dict[int, float] | None = None,
) -> dict[str, Any]:
    return calculate_research_ui(
        indexed,
        templates_dir,
        faction_name,
        templates=templates,
        base_daily_cache=base_daily_cache,
    )


def handle_research_plan(
    indexed: Any,
    templates_dir: Path | None = None,
    faction_name: str | int | None = None,
    top: int = 8,
    mode: str = "all",
    include_all_candidates: bool = False,
) -> dict[str, Any]:
    return calculate_research_plan(
        indexed,
        templates_dir,
        faction_name=faction_name,
        top=top,
        mode=mode,
        include_all_candidates=include_all_candidates,
    )


def handle_ship_plan(
    indexed: Any,
    templates_dir: Path | None = None,
    faction_name: str | int | None = None,
    role: str = "balanced",
    top: int = 8,
    include_obsolete: bool = False,
    include_all_components: bool = False,
    design_name: str | None = None,
) -> dict[str, Any]:
    result = calculate_ship_plan(
        indexed,
        templates_dir,
        faction_name=faction_name,
        role=role,
        top=top,
        include_obsolete=include_obsolete,
        include_all_components=include_all_components,
        design_name=design_name,
    )
    if design_name:
        return {
            "faction": result["faction"],
            "date": result["date"],
            "selectedDesign": result["selectedDesign"],
            "limitations": result["limitations"],
        }
    return result


def handle_nation_claims(
    indexed: Any,
    templates_dir: Path | None = None,
    claimant_name: str | int | None = None,
    target_name: str | int | None = None,
    diagnostics: bool = False,
) -> dict[str, Any]:
    # ``templates_dir`` is retained as part of the common application contract.
    # Nation claims use the package-only runtime catalog and never read it.
    del templates_dir
    runtime_catalogs = calculation_catalogs(indexed, "nation-claims")
    result = calculate_nation_claims(
        indexed,
        claimant_name=claimant_name,
        target_name=target_name,
        claim_catalog=runtime_catalogs.nation_claims,
        diagnostics=diagnostics,
    )
    if diagnostics:
        claim_diagnostics = result.pop("calculationDiagnostics", {})
        result["calculationDiagnostics"] = {
            "runtime": runtime_catalogs.calculation_diagnostics(),
            "claims": claim_diagnostics,
        }
    return result


def handle_ai_fleet_diagnostics(
    indexed: Any,
    templates_dir: Path | None = None,
    faction_name: str | int | None = None,
    stale_days: float | None = None,
    diagnostics: bool = False,
) -> dict[str, Any]:
    del templates_dir
    return calculate_ai_fleet_diagnostics(
        indexed,
        faction_name=faction_name,
        stale_days=stale_days,
        diagnostics=diagnostics,
    )


def handle_topbar(
    indexed: Any,
    templates_dir: Path | None = None,
    faction_name: str | int | None = None,
    include_details: bool = False,
    *,
    research_templates: Any | None = None,
    base_daily_cache: dict[int, float] | None = None,
    include_diagnostics: bool = False,
    forecast_resource: str | None = None,
) -> dict[str, Any]:
    return calculate_topbar(
        indexed,
        templates_dir,
        faction_name,
        include_details=include_details,
        research_templates=research_templates,
        base_daily_cache=base_daily_cache,
        include_diagnostics=include_diagnostics,
        forecast_resource=forecast_resource,
    )


def handle_world_ui(
    indexed: Any,
    templates_dir: Path | None = None,
    faction_name: str | int | None = None,
) -> dict[str, Any]:
    return clean_numbers(calculate_world_ui(indexed, templates_dir, faction_name), 6)


def handle_advise(
    indexed: Any,
    templates_dir: Path | None = None,
    faction_name: str | int | None = None,
    *,
    councilor_name: str | int,
    nation_name: str | int,
) -> dict[str, Any]:
    runtime_catalogs = calculation_catalogs(indexed, "advise")
    trait_templates = runtime_catalogs.traits
    effect_templates = runtime_catalogs.effects
    faction_id, faction = find_faction_state(indexed, faction_name)
    effect_contexts = faction_effect_contexts(indexed, faction_id)
    summaries, councilor_by_id = councilor_summary_maps(indexed, trait_templates)
    councilor = match_named(summaries, councilor_name)
    if not councilor:
        raise UserInputError(f"Councilor not found: {councilor_name}")

    councilor_id = councilor.get("id")
    councilor_state = state_value_by_id(indexed, councilor_id if isinstance(councilor_id, int) else None)
    councilor_faction_id = ref_id(councilor_state.get("faction")) if isinstance(councilor_state, dict) else None
    if councilor_faction_id != faction_id:
        raise UserInputError(f"Councilor not available for faction: {councilor_name}")
    if councilor.get("active") is not True or councilor.get("detained") is True:
        raise UserInputError(f"Councilor unavailable: {councilor_name}")

    nation_match = match_raw_state(indexed, "TINationState", nation_name)
    if not nation_match:
        raise UserInputError(f"Nation not found: {nation_name}")
    nation_id, nation = nation_match

    science = as_float((councilor.get("finalAttributes") or {}).get("Science"), 0.0)
    extra_advisor = (int(councilor["id"]), science)
    before_month = nation_research_contribution_month(
        indexed,
        nation,
        faction_id,
        councilor_by_id,
        effect_contexts,
        effect_templates,
    )
    after_month = nation_research_contribution_month(
        indexed,
        nation,
        faction_id,
        councilor_by_id,
        effect_contexts,
        effect_templates,
        extra_advisor=extra_advisor,
    )
    before_daily = before_month * 12.0 / DAYS_PER_YEAR
    after_daily = after_month * 12.0 / DAYS_PER_YEAR
    delta_source_daily = after_daily - before_daily

    current_breakdown = handle_research(
        indexed,
        templates_dir,
        faction_name,
        include_details=False,
    )
    distribution_percent = as_float(current_breakdown.get("distribution", {}).get("percent"), 0.0)
    delta_after_distribution = delta_source_daily * (1.0 + distribution_percent)
    current_total_daily = as_float(current_breakdown.get("daily", {}).get("total"), 0.0)
    owned_control_points = len(active_owned_control_points(indexed, nation, faction_id))
    notes = []
    if nation_population_millions(indexed, nation) <= 0.0:
        notes.append("Target nation has no population/regions in this save, so its research contribution is zero.")
    if owned_control_points <= 0:
        notes.append("The faction owns no active control points in the target nation, so contribution increase is zero.")

    return clean_numbers({
        "faction": {
            "id": faction_id,
            "template": faction.get("templateName"),
            "display": faction.get("displayName"),
        },
        "councilor": {
            "id": councilor.get("id"),
            "display": councilor.get("display"),
            "science": science,
        },
        "nation": {
            "id": nation_id,
            "template": nation.get("templateName"),
            "code": campaign_code(nation.get("templateName")),
            "display": nation.get("displayName"),
            "ownedControlPoints": owned_control_points,
            "totalControlPoints": nation.get("numControlPoints"),
            "population_Millions": nation_population_millions(indexed, nation),
        },
        "daily": {
            "nationContributionBefore": before_daily,
            "nationContributionAfter": after_daily,
            "deltaBeforeDistribution": delta_source_daily,
            "deltaAfterDistribution": delta_after_distribution,
            "currentFactionTotal": current_total_daily,
            "projectedFactionTotal": current_total_daily + delta_after_distribution,
        },
        "distribution": {"percent": distribution_percent},
        "notes": notes,
    }, 6)


def handle_nation_ui(
    indexed: Any,
    templates_dir: Path | None = None,
    *,
    nation_name: str | int,
    faction_name: str | int | None = None,
) -> dict[str, Any]:
    return calculate_nation_ui(indexed, templates_dir, nation_name, faction_name)


def handle_nation_projection(
    indexed: Any,
    templates_dir: Path | None = None,
    *,
    nation_name: str | int,
    faction_name: str | int | None = None,
    plan_payload: Any = None,
    days: int,
    checkpoints: list[int] | None = None,
    details: bool = False,
    diagnostics: bool = False,
) -> dict[str, Any]:
    del templates_dir
    if days <= 0:
        raise ProjectionInputError("Projection days must be positive")
    if checkpoints is not None and any(day < 0 or day > days for day in checkpoints):
        raise ProjectionInputError("Checkpoint days must be inside the projection horizon")
    return clean_numbers(calculate_nation_projection(
        indexed,
        nation_name,
        faction_name,
        plan_payload,
        days=days,
        checkpoints=[] if checkpoints is None else checkpoints,
        details=details,
        diagnostics=diagnostics,
    ), 6)


# Compact snapshot selections ------------------------------------------------


def handle_summary(snapshot: dict[str, Any], top_nations: int = 20) -> dict[str, Any]:
    player_name = snapshot.get("metadata", {}).get("playerFactionName")
    metadata_candidates = []
    if player_name:
        needle = str(player_name).casefold()
        metadata_candidates = [
            faction
            for faction in snapshot["factions"]
            if needle
            in {
                str(faction.get("template") or "").casefold(),
                str(
                    campaign_code(
                        faction.get("template") if isinstance(faction.get("template"), str) else None
                    )
                    or ""
                ).casefold(),
                str(faction.get("display") or "").casefold(),
                str(faction.get("code") or "").casefold(),
            }
        ]
    player_state_candidates = [
        faction
        for faction in snapshot["factions"]
        if isinstance(faction.get("player"), dict) and faction["player"].get("isAI") is False
    ]
    if len(metadata_candidates) > 1 or len(player_state_candidates) > 1:
        raise UserInputError("Multiple human player faction candidates found in snapshot.")
    if player_name and not metadata_candidates:
        raise UserInputError(
            f"Metadata player faction could not be resolved: {player_name}",
            code="player-faction-unresolved",
        )
    if metadata_candidates and player_state_candidates and metadata_candidates[0].get("id") != player_state_candidates[0].get("id"):
        raise UserInputError("Snapshot player faction metadata conflicts with TIPlayerState.")
    player_faction = (player_state_candidates or metadata_candidates or [None])[0]
    if player_faction is None:
        raise UserInputError("Human player faction could not be resolved in snapshot.")

    top_nations_value = player_faction.get("controlledNations", [])[:top_nations]
    factions = []
    for faction in snapshot["factions"]:
        resources = faction.get("resources") or {}
        base_incomes = faction.get("baseIncomes_year") or {}
        factions.append(
            {
                "template": faction.get("template"),
                "display": faction.get("display"),
                "controlPoints": faction.get("controlPoints"),
                "habSectors": faction.get("habSectors"),
                "fleets": faction.get("fleets"),
                "missionControlUsage": faction.get("missionControlUsage"),
                "money": resources.get("Money"),
                "influence": resources.get("Influence"),
                "ops": resources.get("Operations"),
                "exotics": resources.get("Exotics"),
                "researchYear": base_incomes.get("Research"),
                "assessedAlienHateOfMe": faction.get("assessedAlienHateOfMe"),
                "cpOverageRecent": faction.get("cpOverageRecent"),
                "mcShortageRecent": faction.get("mcShortageRecent"),
            }
        )

    return {
        "faction": {
            "display": player_faction.get("display"),
            "template": player_faction.get("template"),
            "player": True,
        },
        "source": snapshot.get("source"),
        "currentID": snapshot.get("currentID"),
        "time": snapshot.get("time"),
        "metadata": snapshot.get("metadata"),
        "global": snapshot.get("global"),
        "counts": snapshot.get("typeCounts"),
        "factions": factions,
        "playerControlledNations": top_nations_value,
    }


def handle_faction(snapshot: dict[str, Any], name: str | int, limit: int = 50) -> dict[str, Any]:
    faction = match_named(snapshot["factions"], name)
    if not faction:
        raise UserInputError(f"Faction not found: {name}")
    result = dict(faction)
    result["controlledNations"] = result.get("controlledNations", [])[:limit]
    return result


def handle_nation(snapshot: dict[str, Any], name: str | int) -> dict[str, Any]:
    nation = match_named(snapshot["nations"], name)
    if not nation:
        raise UserInputError(f"Nation not found: {name}")
    return nation


def handle_councilor(
    snapshot: dict[str, Any],
    name: str | int,
    details: bool = False,
    target_nation: str | int | None = None,
    current_location_context: bool = False,
) -> dict[str, Any]:
    councilor = match_named(snapshot["councilors"], name)
    if not councilor:
        raise UserInputError(f"Councilor not found: {name}")
    result = dict(councilor)
    if target_nation and current_location_context:
        raise UserInputError("Use only one of --target-nation or --current-location-context.")
    context_nation = None
    context_label = None
    if target_nation:
        context_nation = match_named(snapshot["nations"], target_nation)
        if not context_nation:
            raise UserInputError(f"Target nation not found: {target_nation}")
        context_label = "targetNation"
    elif current_location_context:
        context_nation = councilor.get("locationNation") if isinstance(councilor.get("locationNation"), dict) else None
        if not context_nation:
            raise UserInputError(f"Current location nation unavailable for councilor: {name}")
        context_label = "currentLocation"

    if context_label:
        result.update(evaluate_councilor_conditionals(councilor, snapshot, context_nation, context_label))
    if not details:
        result.pop("traitModDetails", None)
        result.pop("conditionalTraitMods", None)
        result.pop("orgDetails", None)
        result.pop("evaluatedConditionalTraitMods", None)
    return result


# The registry intentionally contains the 19 primary analyses plus the AI
# diagnostic route.  Maintenance/inspection commands remain CLI-only.
HANDLERS = {
    "summary": handle_summary,
    "faction": handle_faction,
    "nation": handle_nation,
    "councilor": handle_councilor,
    "topbar": handle_topbar,
    "research": handle_research,
    "research-ui": handle_research_ui,
    "research-plan": handle_research_plan,
    "org-plan": handle_org_plan,
    "hab-ui": handle_hab_ui,
    "hab-slots": handle_hab_slots,
    "hab-plan": handle_hab_plan,
    "ship-plan": handle_ship_plan,
    "project-analysis": handle_project_analysis,
    "nation-ui": handle_nation_ui,
    "nation-claims": handle_nation_claims,
    "nation-projection": handle_nation_projection,
    "advise": handle_advise,
    "world-ui": handle_world_ui,
    "ai-fleet-diagnostics": handle_ai_fleet_diagnostics,
}
