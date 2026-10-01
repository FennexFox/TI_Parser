"""CLI command handlers: load input, call domain services and render output."""

from __future__ import annotations

from ti_parser_errors import UserInputError

import argparse
import json
from pathlib import Path
from typing import Any

import ti_parser_nation_projection as nation_projection_layer
from ti_parser_ai import calculate_ai_fleet_diagnostics
from ti_parser_claims import calculate_nation_claims
from ti_parser_config import DAYS_PER_YEAR
from ti_parser_core import (
    as_float,
    build_index,
    campaign_code,
    clean_numbers,
    faction_effect_contexts,
    find_faction_state,
    load_save,
    match_raw_state,
    print_json,
    ref_id,
    resolve_save_path,
    state_value_by_id,
    type_entries,
)
from ti_parser_hab_plan import calculate_hab_plan
from ti_parser_hab_ui import (
    calculate_hab_slots,
    calculate_hab_ui,
)
from ti_parser_nation_ui import calculate_nation_ui
from ti_parser_project_analysis import calculate_project_analysis
from ti_parser_projection_adapter import calculate_nation_projection
from ti_parser_research import (
    calculate_research_breakdown,
    calculate_research_ui,
)
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
from ti_parser_verify import verify_catalogs
from ti_parser_world import calculate_world_ui


def command_org_plan(save_path: Path, templates_dir: Path | None, args: argparse.Namespace) -> None:
    data = load_save(save_path)
    indexed = build_index(data)
    result = calculate_org_plan(
        indexed,
        templates_dir,
        faction_name=args.faction,
        focus=args.focus,
        top=args.top,
        include_unassigned=not args.market_only,
        max_actions=args.max_actions,
        beam_width=args.beam_width,
        include_all_candidates=args.all_candidates,
    )
    print_json(result, compact=args.compact)


def command_hab_ui(save_path: Path, templates_dir: Path | None, args: argparse.Namespace) -> None:
    data = load_save(save_path)
    indexed = build_index(data)
    result = calculate_hab_ui(indexed, templates_dir, args.name)
    print_json(result, compact=args.compact)


def command_hab_slots(save_path: Path, templates_dir: Path | None, args: argparse.Namespace) -> None:
    data = load_save(save_path)
    indexed = build_index(data)
    result = calculate_hab_slots(
        indexed,
        templates_dir,
        faction_name=args.faction,
        include_all=args.all,
        include_module_counts=args.module_counts,
    )
    print_json(clean_numbers(result, 6), compact=args.compact)


def command_hab_plan(save_path: Path, templates_dir: Path | None, args: argparse.Namespace) -> None:
    data = load_save(save_path)
    indexed = build_index(data)
    result = calculate_hab_plan(
        indexed,
        templates_dir,
        faction_name=args.faction,
        hab_name=args.name,
        upgrading_to_tier=args.upgrading_to_tier,
        include_all=args.all,
        focus=args.focus,
        top=args.top,
    )
    print_json(result, compact=args.compact)


def command_project_analysis(save_path: Path, templates_dir: Path | None, args: argparse.Namespace) -> None:
    data = load_save(save_path)
    indexed = build_index(data)
    result = calculate_project_analysis(
        indexed,
        templates_dir,
        faction_name=args.faction,
        top=args.top,
        sort_axis=args.sort,
        slot=args.slot,
        include_active=args.include_active,
        include_all=args.all,
    )
    print_json(result, compact=args.compact)


def command_research(save_path: Path, templates_dir: Path | None, args: argparse.Namespace) -> None:
    data = load_save(save_path)
    indexed = build_index(data)
    result = calculate_research_breakdown(indexed, templates_dir, args.faction, include_details=args.details)
    print_json(result, compact=args.compact)


def command_research_ui(save_path: Path, templates_dir: Path | None, args: argparse.Namespace) -> None:
    data = load_save(save_path)
    indexed = build_index(data)
    result = calculate_research_ui(indexed, templates_dir, args.faction)
    print_json(result, compact=args.compact)


def command_research_plan(save_path: Path, templates_dir: Path | None, args: argparse.Namespace) -> None:
    data = load_save(save_path)
    indexed = build_index(data)
    result = calculate_research_plan(
        indexed,
        templates_dir,
        faction_name=args.faction,
        top=args.top,
        mode=args.mode,
        include_all_candidates=args.all_candidates,
    )
    print_json(result, compact=args.compact)


def command_ship_plan(save_path: Path, templates_dir: Path | None, args: argparse.Namespace) -> None:
    data = load_save(save_path)
    indexed = build_index(data)
    result = calculate_ship_plan(
        indexed,
        templates_dir,
        faction_name=args.faction,
        role=args.role,
        top=args.top,
        include_obsolete=args.include_obsolete,
        include_all_components=args.all_components,
        design_name=args.design,
    )
    if args.design:
        result = {
            "faction": result["faction"],
            "date": result["date"],
            "selectedDesign": result["selectedDesign"],
            "limitations": result["limitations"],
        }
    print_json(result, compact=args.compact)


def command_nation_claims(save_path: Path, templates_dir: Path | None, args: argparse.Namespace) -> None:
    data = load_save(save_path)
    indexed = build_index(data)
    runtime_catalogs = calculation_catalogs(indexed, "nation-claims")
    result = calculate_nation_claims(
        indexed,
        claimant_name=args.claimant,
        target_name=args.target,
        claim_catalog=runtime_catalogs.nation_claims,
        diagnostics=args.diagnostics,
    )
    if args.diagnostics:
        claim_diagnostics = result.pop("calculationDiagnostics", {})
        result["calculationDiagnostics"] = {
            "runtime": runtime_catalogs.calculation_diagnostics(),
            "claims": claim_diagnostics,
        }
    print_json(result, compact=args.compact)


def command_ai_fleet_diagnostics(save_path: Path, templates_dir: Path | None, args: argparse.Namespace) -> None:
    data = load_save(save_path)
    indexed = build_index(data)
    result = calculate_ai_fleet_diagnostics(
        indexed,
        faction_name=args.faction,
        stale_days=args.stale_days,
        diagnostics=args.diagnostics,
    )
    print_json(result, compact=args.compact)


def command_catalog_verify(args: argparse.Namespace) -> int:
    try:
        save_path = resolve_save_path(args.save)
    except FileNotFoundError:
        if args.save:
            raise
        save_path = None
    result = verify_catalogs(
        Path(args.templates_dir),
        args.scenario,
        save_path=save_path,
    )
    print_json(result, compact=args.compact)
    return 0 if result["status"] == "passed" else 2


def command_topbar(save_path: Path, templates_dir: Path | None, args: argparse.Namespace) -> None:
    data = load_save(save_path)
    indexed = build_index(data)
    result = calculate_topbar(
        indexed,
        templates_dir,
        args.faction,
        include_details=args.details,
        include_diagnostics=args.diagnostics,
        forecast_resource=args.forecast_resource,
    )
    print_json(result, compact=args.compact)


def command_world_ui(save_path: Path, templates_dir: Path | None, args: argparse.Namespace) -> None:
    data = load_save(save_path)
    indexed = build_index(data)
    result = calculate_world_ui(indexed, templates_dir, args.faction)
    print_json(clean_numbers(result, 6), compact=args.compact)


def command_advise(save_path: Path, templates_dir: Path | None, args: argparse.Namespace) -> None:
    data = load_save(save_path)
    indexed = build_index(data)
    runtime_catalogs = calculation_catalogs(indexed, "advise")
    trait_templates = runtime_catalogs.traits
    effect_templates = runtime_catalogs.effects
    faction_id, faction = find_faction_state(indexed, args.faction)
    effect_contexts = faction_effect_contexts(indexed, faction_id)
    summaries, councilor_by_id = councilor_summary_maps(indexed, trait_templates)
    councilor = match_named(summaries, args.councilor)
    if not councilor:
        raise UserInputError(f"Councilor not found: {args.councilor}")

    councilor_id = councilor.get("id")
    councilor_state = state_value_by_id(indexed, councilor_id if isinstance(councilor_id, int) else None)
    councilor_faction_id = ref_id(councilor_state.get("faction")) if isinstance(councilor_state, dict) else None
    if councilor_faction_id != faction_id:
        raise UserInputError(f"Councilor not available for faction: {args.councilor}")
    if councilor.get("active") is not True or councilor.get("detained") is True:
        raise UserInputError(f"Councilor unavailable: {args.councilor}")

    nation_match = match_raw_state(indexed, "TINationState", args.nation)
    if not nation_match:
        raise UserInputError(f"Nation not found: {args.nation}")
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

    current_breakdown = calculate_research_breakdown(indexed, templates_dir, args.faction, include_details=False)
    distribution_percent = as_float(current_breakdown.get("distribution", {}).get("percent"), 0.0)
    delta_after_distribution = delta_source_daily * (1.0 + distribution_percent)
    current_total_daily = as_float(current_breakdown.get("daily", {}).get("total"), 0.0)
    owned_control_points = len(active_owned_control_points(indexed, nation, faction_id))
    notes = []
    if nation_population_millions(indexed, nation) <= 0.0:
        notes.append("Target nation has no population/regions in this save, so its research contribution is zero.")
    if owned_control_points <= 0:
        notes.append("The faction owns no active control points in the target nation, so contribution increase is zero.")

    result = {
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
        "distribution": {
            "percent": distribution_percent,
        },
        "notes": notes,
    }
    print_json(clean_numbers(result, 6), compact=args.compact)


def command_nation_ui(save_path: Path, templates_dir: Path | None, args: argparse.Namespace) -> None:
    data = load_save(save_path)
    indexed = build_index(data)
    result = calculate_nation_ui(indexed, templates_dir, args.name, args.faction)
    print_json(result, compact=args.compact)


def command_nation_projection(save_path: Path, templates_dir: Path | None, args: argparse.Namespace) -> None:
    data = load_save(save_path)
    indexed = build_index(data)
    plan_payload = None
    if args.plan_file:
        try:
            plan_payload = json.loads(Path(args.plan_file).read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise nation_projection_layer.ProjectionInputError(f"Unable to read plan file: {exc}") from exc
    checkpoints = []
    if args.checkpoints:
        try:
            checkpoints = sorted({int(value) for value in args.checkpoints.split(",") if value.strip()})
        except ValueError as exc:
            raise nation_projection_layer.ProjectionInputError("--checkpoints must be comma-separated integer days") from exc
        if any(value < 0 or value > args.days for value in checkpoints):
            raise nation_projection_layer.ProjectionInputError("Checkpoint days must be inside the projection horizon")
    result = calculate_nation_projection(
        indexed, args.name, args.faction, plan_payload, days=args.days, checkpoints=checkpoints,
        details=args.details, diagnostics=args.diagnostics,
    )
    print_json(clean_numbers(result, 6), compact=args.compact)


def command_summary(snapshot: dict[str, Any], args: argparse.Namespace) -> None:
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
    if metadata_candidates and player_state_candidates and metadata_candidates[0].get("id") != player_state_candidates[0].get("id"):
        raise UserInputError("Snapshot player faction metadata conflicts with TIPlayerState.")
    player_faction = (player_state_candidates or metadata_candidates or [None])[0]
    if player_faction is None:
        raise UserInputError("Human player faction could not be resolved in snapshot.")

    top_nations = []
    if player_faction:
        top_nations = player_faction.get("controlledNations", [])[: args.top_nations]

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

    output = {
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
        "playerControlledNations": top_nations,
    }
    print_json(output, compact=args.compact)


def command_faction(snapshot: dict[str, Any], args: argparse.Namespace) -> None:
    faction = match_named(snapshot["factions"], args.name)
    if not faction:
        raise UserInputError(f"Faction not found: {args.name}")
    result = dict(faction)
    result["controlledNations"] = result.get("controlledNations", [])[: args.limit]
    print_json(result, compact=args.compact)


def command_nation(snapshot: dict[str, Any], args: argparse.Namespace) -> None:
    nation = match_named(snapshot["nations"], args.name)
    if not nation:
        raise UserInputError(f"Nation not found: {args.name}")
    print_json(nation, compact=args.compact)


def command_councilor(snapshot: dict[str, Any], args: argparse.Namespace) -> None:
    councilor = match_named(snapshot["councilors"], args.name)
    if not councilor:
        raise UserInputError(f"Councilor not found: {args.name}")
    result = dict(councilor)
    if args.target_nation and args.current_location_context:
        raise UserInputError("Use only one of --target-nation or --current-location-context.")
    context_nation = None
    context_label = None
    if args.target_nation:
        context_nation = match_named(snapshot["nations"], args.target_nation)
        if not context_nation:
            raise UserInputError(f"Target nation not found: {args.target_nation}")
        context_label = "targetNation"
    elif args.current_location_context:
        context_nation = councilor.get("locationNation") if isinstance(councilor.get("locationNation"), dict) else None
        if not context_nation:
            raise UserInputError(f"Current location nation unavailable for councilor: {args.name}")
        context_label = "currentLocation"

    if context_label:
        result.update(evaluate_councilor_conditionals(councilor, snapshot, context_nation, context_label))
    if not args.details:
        result.pop("traitModDetails", None)
        result.pop("conditionalTraitMods", None)
        result.pop("orgDetails", None)
        result.pop("evaluatedConditionalTraitMods", None)
    print_json(result, compact=args.compact)


def command_types(snapshot: dict[str, Any], args: argparse.Namespace) -> None:
    items = list(snapshot.get("typeCounts", {}).items())
    if args.limit:
        items = items[: args.limit]
    print_json([{"type": key, "count": value} for key, value in items], compact=args.compact)


def command_export(snapshot: dict[str, Any], args: argparse.Namespace) -> None:
    output = Path(args.output).expanduser()
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        json.dump(snapshot, handle, ensure_ascii=False, indent=2)
    print_json({"wrote": str(output), "bytes": output.stat().st_size}, compact=args.compact)


def parse_key_list(value: str | None) -> list[str] | None:
    if not value:
        return None
    return [item.strip() for item in value.split(",") if item.strip()]


def raw_entry_matches(entry: dict[str, Any], args: argparse.Namespace) -> bool:
    value = entry.get("Value") or {}
    if args.id is not None:
        state_id = ref_id(entry.get("Key")) or ref_id(value.get("ID"))
        if state_id != args.id:
            return False
    if args.template and value.get("templateName") != args.template:
        return False
    if args.display:
        display = str(value.get("displayName") or "")
        if args.display.casefold() not in display.casefold():
            return False
    return True


def command_raw(save_path: Path, args: argparse.Namespace) -> None:
    data = load_save(save_path)
    indexed = build_index(data)
    entries = type_entries(indexed, args.type)
    keys = parse_key_list(args.keys)
    output = []
    for entry in entries:
        if not raw_entry_matches(entry, args):
            continue
        value = entry.get("Value") or {}
        state_id = ref_id(entry.get("Key")) or ref_id(value.get("ID"))
        if keys:
            sliced = {key: value.get(key) for key in keys}
            sliced["id"] = state_id
            output.append(sliced)
        else:
            output.append({"id": state_id, "value": value})
        if len(output) >= args.limit:
            break
    print_json(clean_numbers(output), compact=args.compact)
