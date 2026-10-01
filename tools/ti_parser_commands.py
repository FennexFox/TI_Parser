"""CLI command handlers: load input, call domain services and render output."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import ti_parser_application as application_layer
import ti_parser_nation_projection as nation_projection_layer
from ti_parser_core import (
    build_index,
    clean_numbers,
    load_save,
    print_json,
    ref_id,
    resolve_save_path,
    type_entries,
)
from ti_parser_verify import verify_catalogs


def command_index(save_path, args):
    indexed = getattr(args, "_indexed", None)
    return indexed if indexed is not None else build_index(load_save(save_path))


def command_org_plan(save_path: Path, templates_dir: Path | None, args: argparse.Namespace) -> None:
    indexed = command_index(save_path, args)
    result = application_layer.dispatch(
        "org-plan", indexed, templates_dir=templates_dir,
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
    indexed = command_index(save_path, args)
    result = application_layer.dispatch(
        "hab-ui", indexed, templates_dir=templates_dir, hab_name=args.name,
    )
    print_json(result, compact=args.compact)


def command_hab_slots(save_path: Path, templates_dir: Path | None, args: argparse.Namespace) -> None:
    indexed = command_index(save_path, args)
    result = application_layer.dispatch(
        "hab-slots", indexed, templates_dir=templates_dir,
        faction_name=args.faction,
        include_all=args.all,
        include_module_counts=args.module_counts,
    )
    print_json(result, compact=args.compact)


def command_hab_plan(save_path: Path, templates_dir: Path | None, args: argparse.Namespace) -> None:
    indexed = command_index(save_path, args)
    result = application_layer.dispatch(
        "hab-plan", indexed, templates_dir=templates_dir,
        faction_name=args.faction,
        hab_name=args.name,
        upgrading_to_tier=args.upgrading_to_tier,
        include_all=args.all,
        focus=args.focus,
        top=args.top,
    )
    print_json(result, compact=args.compact)


def command_project_analysis(save_path: Path, templates_dir: Path | None, args: argparse.Namespace) -> None:
    indexed = command_index(save_path, args)
    result = application_layer.dispatch(
        "project-analysis", indexed, templates_dir=templates_dir,
        faction_name=args.faction,
        top=args.top,
        sort_axis=args.sort,
        slot=args.slot,
        include_active=args.include_active,
        include_all=args.all,
    )
    print_json(result, compact=args.compact)


def command_research(save_path: Path, templates_dir: Path | None, args: argparse.Namespace) -> None:
    indexed = command_index(save_path, args)
    result = application_layer.dispatch(
        "research", indexed, templates_dir=templates_dir,
        faction_name=args.faction, include_details=args.details,
    )
    print_json(result, compact=args.compact)


def command_research_ui(save_path: Path, templates_dir: Path | None, args: argparse.Namespace) -> None:
    indexed = command_index(save_path, args)
    result = application_layer.dispatch(
        "research-ui", indexed, templates_dir=templates_dir, faction_name=args.faction,
    )
    print_json(result, compact=args.compact)


def command_research_plan(save_path: Path, templates_dir: Path | None, args: argparse.Namespace) -> None:
    indexed = command_index(save_path, args)
    result = application_layer.dispatch(
        "research-plan", indexed, templates_dir=templates_dir,
        faction_name=args.faction,
        top=args.top,
        mode=args.mode,
        include_all_candidates=args.all_candidates,
    )
    print_json(result, compact=args.compact)


def command_ship_plan(save_path: Path, templates_dir: Path | None, args: argparse.Namespace) -> None:
    indexed = command_index(save_path, args)
    result = application_layer.dispatch(
        "ship-plan", indexed, templates_dir=templates_dir,
        faction_name=args.faction,
        role=args.role,
        top=args.top,
        include_obsolete=args.include_obsolete,
        include_all_components=args.all_components,
        design_name=args.design,
    )
    print_json(result, compact=args.compact)


def command_nation_claims(save_path: Path, templates_dir: Path | None, args: argparse.Namespace) -> None:
    indexed = command_index(save_path, args)
    result = application_layer.dispatch(
        "nation-claims", indexed, templates_dir=templates_dir,
        claimant_name=args.claimant,
        target_name=args.target,
        diagnostics=args.diagnostics,
    )
    print_json(result, compact=args.compact)


def command_ai_fleet_diagnostics(save_path: Path, templates_dir: Path | None, args: argparse.Namespace) -> None:
    indexed = command_index(save_path, args)
    result = application_layer.dispatch(
        "ai-fleet-diagnostics", indexed, templates_dir=templates_dir,
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
    indexed = command_index(save_path, args)
    result = application_layer.dispatch(
        "topbar", indexed, templates_dir=templates_dir,
        faction_name=args.faction,
        include_details=args.details,
        include_diagnostics=args.diagnostics,
        forecast_resource=args.forecast_resource,
    )
    print_json(result, compact=args.compact)


def command_world_ui(save_path: Path, templates_dir: Path | None, args: argparse.Namespace) -> None:
    indexed = command_index(save_path, args)
    result = application_layer.dispatch(
        "world-ui", indexed, templates_dir=templates_dir, faction_name=args.faction,
    )
    print_json(result, compact=args.compact)


def command_advise(save_path: Path, templates_dir: Path | None, args: argparse.Namespace) -> None:
    indexed = command_index(save_path, args)
    result = application_layer.dispatch(
        "advise", indexed, templates_dir=templates_dir,
        faction_name=args.faction,
        councilor_name=args.councilor,
        nation_name=args.nation,
    )
    print_json(result, compact=args.compact)


def command_nation_ui(save_path: Path, templates_dir: Path | None, args: argparse.Namespace) -> None:
    indexed = command_index(save_path, args)
    result = application_layer.dispatch(
        "nation-ui", indexed, templates_dir=templates_dir,
        nation_name=args.name, faction_name=args.faction,
    )
    print_json(result, compact=args.compact)


def command_nation_projection(save_path: Path, templates_dir: Path | None, args: argparse.Namespace) -> None:
    indexed = command_index(save_path, args)
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
    result = application_layer.dispatch(
        "nation-projection", indexed, templates_dir=templates_dir,
        nation_name=args.name,
        faction_name=args.faction,
        plan_payload=plan_payload,
        days=args.days,
        checkpoints=checkpoints,
        details=args.details,
        diagnostics=args.diagnostics,
    )
    print_json(result, compact=args.compact)


def command_summary(snapshot: dict[str, Any], args: argparse.Namespace) -> None:
    output = application_layer.dispatch("summary", snapshot, top_nations=args.top_nations)
    print_json(output, compact=args.compact)


def command_faction(snapshot: dict[str, Any], args: argparse.Namespace) -> None:
    result = application_layer.dispatch("faction", snapshot, name=args.name, limit=args.limit)
    print_json(result, compact=args.compact)


def command_nation(snapshot: dict[str, Any], args: argparse.Namespace) -> None:
    nation = application_layer.dispatch("nation", snapshot, name=args.name)
    print_json(nation, compact=args.compact)


def command_councilor(snapshot: dict[str, Any], args: argparse.Namespace) -> None:
    result = application_layer.dispatch(
        "councilor", snapshot, name=args.name,
        details=args.details,
        target_nation=args.target_nation,
        current_location_context=args.current_location_context,
    )
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
    indexed = command_index(save_path, args)
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
