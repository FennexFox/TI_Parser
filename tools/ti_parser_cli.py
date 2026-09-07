"""Command-line parser and dispatch for the Terra Invicta save parser."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from types import ModuleType
from typing import Any


RAW_COMMANDS = {
    "org-plan": "command_org_plan",
    "research": "command_research",
    "research-ui": "command_research_ui",
    "research-plan": "command_research_plan",
    "topbar": "command_topbar",
    "advise": "command_advise",
    "nation-ui": "command_nation_ui",
    "nation-projection": "command_nation_projection",
    "world-ui": "command_world_ui",
    "hab-ui": "command_hab_ui",
    "hab-slots": "command_hab_slots",
    "hab-plan": "command_hab_plan",
    "ship-plan": "command_ship_plan",
    "project-analysis": "command_project_analysis",
    "nation-claims": "command_nation_claims",
    "ai-fleet-diagnostics": "command_ai_fleet_diagnostics",
}

SNAPSHOT_COMMANDS = {
    "summary": "command_summary",
    "faction": "command_faction",
    "nation": "command_nation",
    "councilor": "command_councilor",
    "types": "command_types",
    "export": "command_export",
}


def build_parser(api: ModuleType) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Parse Terra Invicta saves into compact summaries.")
    parser.add_argument("--save", help="Path to a .gz Terra Invicta save. Defaults to newest local save.")
    parser.add_argument("--templates-dir", help="Path to TerraInvicta_Data\\StreamingAssets\\Templates.")
    parser.add_argument("--cache-dir", default=api.DEFAULT_CACHE_DIR, help="Directory for compact parser cache.")
    parser.add_argument("--refresh-cache", action="store_true", help="Ignore and rebuild the compact cache.")
    parser.add_argument("--compact", action="store_true", help="Print compact JSON.")

    subparsers = parser.add_subparsers(dest="command", required=False)

    def add_compact_flag(subparser: argparse.ArgumentParser) -> None:
        subparser.add_argument("--compact", action="store_true", default=argparse.SUPPRESS, help="Print compact JSON.")

    summary = subparsers.add_parser("summary", help="Print compact campaign summary.")
    summary.add_argument("--top-nations", type=int, default=20)
    add_compact_flag(summary)

    faction = subparsers.add_parser("faction", help="Print one faction summary.")
    faction.add_argument("name")
    faction.add_argument("--limit", type=int, default=50, help="Maximum controlled nations to include.")
    add_compact_flag(faction)

    nation = subparsers.add_parser("nation", help="Print one nation summary.")
    nation.add_argument("name")
    add_compact_flag(nation)

    councilor = subparsers.add_parser("councilor", help="Print one councilor summary with calculated attributes.")
    councilor.add_argument("name")
    councilor.add_argument("--details", action="store_true", help="Include trait/org calculation detail lists.")
    councilor.add_argument("--target-nation", help="Evaluate conditional trait modifiers against this target nation.")
    councilor.add_argument(
        "--current-location-context",
        action="store_true",
        help="Evaluate conditional trait modifiers against the councilor's current location nation.",
    )
    add_compact_flag(councilor)

    org_plan = subparsers.add_parser(
        "org-plan",
        help="Recommend acquirable org assignments for councilor specialization and committee-wide stats.",
    )
    org_plan.add_argument("faction", nargs="?", help="Faction template/display/code. Defaults to the player faction.")
    org_plan.add_argument("--focus", choices=api.ORG_PLAN_FOCUS_CHOICES, default="balanced")
    org_plan.add_argument("--top", type=int, default=5, help="Candidate rows per councilor objective view.")
    org_plan.add_argument("--market-only", action="store_true", help="Exclude already-owned unassigned orgs from planning.")
    org_plan.add_argument("--max-actions", type=int, default=4, help="Maximum assignment and replacement steps in committee search.")
    org_plan.add_argument("--beam-width", type=int, default=8, help="Number of committee states retained at each search step.")
    org_plan.add_argument("--all-candidates", action="store_true", help="Include full positive candidate action lists.")
    add_compact_flag(org_plan)

    research = subparsers.add_parser("research", help="Calculate faction research income from raw save values.")
    research.add_argument("faction", nargs="?", help="Faction template/display/code. Defaults to the player faction.")
    research.add_argument("--details", action="store_true", help="Include nation/councilor/hab source details.")
    add_compact_flag(research)

    research_ui = subparsers.add_parser("research-ui", help="Reconstruct the Research screen's active global techs and projects.")
    research_ui.add_argument("faction", nargs="?", help="Faction template/display/code. Defaults to the player faction.")
    add_compact_flag(research_ui)

    research_plan = subparsers.add_parser(
        "research-plan",
        help="Build an LLM-ready report for choosing next global tech or project research.",
    )
    research_plan.add_argument("faction", nargs="?", help="Faction template/display/code. Defaults to the player faction.")
    research_plan.add_argument("--top", type=int, default=8, help="Rows per objective signal view.")
    research_plan.add_argument("--mode", choices=("all", "global", "project"), default="all")
    research_plan.add_argument("--all-candidates", action="store_true", help="Include full candidate lists, not just shortlists.")
    add_compact_flag(research_plan)

    topbar = subparsers.add_parser("topbar", help="Reconstruct the top resource bar values for a faction.")
    topbar.add_argument("faction", nargs="?", help="Faction template/display/code. Defaults to the player faction.")
    topbar.add_argument("--details", action="store_true", help="Include yearly source components for each resource.")
    topbar.add_argument("--diagnostics", action="store_true", help="Include calculation provenance and assumptions.")
    topbar.add_argument(
        "--forecast-resource",
        choices=api.HAB_MONTHLY_RESOURCES,
        help="Simulate faction hab income after each queued module completion.",
    )
    add_compact_flag(topbar)

    advise = subparsers.add_parser("advise", help="Estimate research change from assigning a councilor to Advise a nation.")
    advise.add_argument("councilor")
    advise.add_argument("nation")
    advise.add_argument("--faction", help="Faction template/display/code. Defaults to the player faction.")
    add_compact_flag(advise)

    nation_ui = subparsers.add_parser("nation-ui", help="Calculate nation UI panel values from raw save values.")
    nation_ui.add_argument("name")
    nation_ui.add_argument("--faction", help="Faction template/display/code for faction-share fields. Defaults to player.")
    add_compact_flag(nation_ui)

    nation_projection = subparsers.add_parser(
        "nation-projection",
        help="Project audited nation priority effects under conditional CP and Advisor policies.",
    )
    nation_projection.add_argument("name", help="Nation template/display/code.")
    nation_projection.add_argument("--days", type=int, required=True, help="Positive projection horizon in days.")
    nation_projection.add_argument("--plan-file", help="JSON plan document; current CP pips/advisors are retained when omitted.")
    nation_projection.add_argument("--checkpoints", help="Comma-separated projection day checkpoints.")
    nation_projection.add_argument("--faction", help="Faction used for Advisor resolution and target-nation contribution view.")
    nation_projection.add_argument("--details", action="store_true", help="Include investment and periodic transaction diagnostics.")
    nation_projection.add_argument("--diagnostics", action="store_true", help="Expand mechanic rule IDs with audit provenance.")
    add_compact_flag(nation_projection)

    world_ui = subparsers.add_parser("world-ui", help="Calculate the Intel world data panel from raw save values.")
    world_ui.add_argument("--faction", help="Faction template/display/code for sell-value modifiers. Defaults to player.")
    add_compact_flag(world_ui)

    hab_ui = subparsers.add_parser("hab-ui", help="Calculate hab UI panel values from raw save values.")
    hab_ui.add_argument("name")
    add_compact_flag(hab_ui)

    hab_slots = subparsers.add_parser("hab-slots", help="List habs with currently usable empty slots.")
    hab_slots.add_argument("--faction", help="Faction template/display/code. Defaults to the player faction.")
    hab_slots.add_argument("--all", action="store_true", help="Include habs with zero usable empty slots.")
    hab_slots.add_argument("--module-counts", action="store_true", help="Include per-hab module template counts.")
    add_compact_flag(hab_slots)

    hab_plan = subparsers.add_parser("hab-plan", help="Recommend module candidates for current or future hab slots.")
    hab_plan.add_argument("name", nargs="?", help="Specific hab name/id fragment. Omit to scan faction habs.")
    hab_plan.add_argument("--faction", help="Faction template/display/code. Defaults to the player faction.")
    hab_plan.add_argument("--upgrading-to-tier", type=int, help="Only include habs whose core is upgrading to this tier.")
    hab_plan.add_argument("--focus", choices=api.HAB_PLAN_FOCUS_CHOICES, default="balanced")
    hab_plan.add_argument("--top", type=int, default=8, help="Candidate rows per category.")
    hab_plan.add_argument("--all", action="store_true", help="Include habs with no planned empty slots.")
    add_compact_flag(hab_plan)

    ship_plan = subparsers.add_parser(
        "ship-plan",
        help="Build an LLM-ready report for designing ships from currently unlocked parts.",
    )
    ship_plan.add_argument("faction", nargs="?", help="Faction template/display/code. Defaults to the player faction.")
    ship_plan.add_argument("--role", choices=api.SHIP_PLAN_ROLE_CHOICES, default="balanced")
    ship_plan.add_argument("--top", type=int, default=8, help="Rows per drive, weapon, and role-utility shortlist.")
    ship_plan.add_argument("--include-obsolete", action="store_true", help="Include ship parts marked obsolete by the faction.")
    ship_plan.add_argument("--all-components", action="store_true", help="Include full unlocked drive, utility, and weapon lists.")
    ship_plan.add_argument("--design", help="Select one saved ship design by display-name or template fragment.")
    add_compact_flag(ship_plan)

    project_analysis = subparsers.add_parser("project-analysis", help="Rank available project candidates on transparent heuristic axes.")
    project_analysis.add_argument("faction", nargs="?", help="Faction template/display/code. Defaults to the player faction.")
    project_analysis.add_argument("--top", type=int, default=10, help="Candidate rows per ranking axis and in the main candidate list.")
    project_analysis.add_argument("--sort", choices=api.PROJECT_ANALYSIS_SORT_CHOICES, default="research-sustainable")
    project_analysis.add_argument("--slot", type=int, choices=range(3, 6), help="Project slot to use for hypothetical ETA estimates.")
    project_analysis.add_argument("--include-active", action="store_true", help="Include currently active projects in the candidate set.")
    project_analysis.add_argument("--all", action="store_true", help="Return every candidate instead of only the top rows for --sort.")
    add_compact_flag(project_analysis)

    nation_claims = subparsers.add_parser("nation-claims", help="Explain saved nation claims and reconstructed hostility rules.")
    nation_claims.add_argument("claimant", nargs="?", help="Optional claimant nation template/display/code filter.")
    nation_claims.add_argument("--target", help="Optional current target nation template/display/code filter.")
    nation_claims.add_argument("--diagnostics", action="store_true")
    add_compact_flag(nation_claims)

    ai_fleet = subparsers.add_parser("ai-fleet-diagnostics", help="Inspect AI fleet goals, assignments, queues, and unresolved causes.")
    ai_fleet.add_argument("faction", nargs="?", help="Optional AI faction template/display/code filter.")
    ai_fleet.add_argument("--stale-days", type=float, help="Add suspected stale diagnostics at this caller-selected threshold.")
    ai_fleet.add_argument("--diagnostics", action="store_true")
    add_compact_flag(ai_fleet)

    catalog_verify = subparsers.add_parser("catalog-verify", help="Compare packaged catalogs with an explicitly supplied game template tree.")
    catalog_verify.add_argument("--scenario", required=True, help="Exact canonical scenario template name.")
    add_compact_flag(catalog_verify)

    types = subparsers.add_parser("types", help="Print gamestate type counts.")
    types.add_argument("--limit", type=int, default=0)
    add_compact_flag(types)

    export = subparsers.add_parser("export", help="Export the compact snapshot.")
    export.add_argument("--output", required=True)
    add_compact_flag(export)

    raw = subparsers.add_parser("raw", help="Read selected raw gamestate entries from the save.")
    raw.add_argument("--type", required=True, help="Short or full gamestate type name.")
    raw.add_argument("--id", type=int)
    raw.add_argument("--template")
    raw.add_argument("--display")
    raw.add_argument("--keys", help="Comma-separated keys to include.")
    raw.add_argument("--limit", type=int, default=5)
    add_compact_flag(raw)

    cache = subparsers.add_parser("cache", help="Build or validate the compact cache.")
    cache.set_defaults(cache_command=True)
    add_compact_flag(cache)

    return parser


def main(api: ModuleType, argv: list[str] | None = None) -> int:
    parser = build_parser(api)
    args = parser.parse_args(argv)
    command = args.command or "summary"
    if command == "nation-projection" and args.days <= 0:
        parser.error("nation-projection --days must be positive")

    try:
        if command == "catalog-verify":
            if not args.templates_dir:
                parser.error("catalog-verify requires --templates-dir")
            api.command_catalog_verify(args)
            return 0
        if args.templates_dir:
            parser.error("--templates-dir is verification-only; use it with catalog-verify")
        save_path = api.resolve_save_path(args.save)
        if command == "raw":
            api.command_raw(save_path, args)
            return 0
        templates_dir = None
        if command in RAW_COMMANDS:
            getattr(api, RAW_COMMANDS[command])(save_path, templates_dir, args)
            return 0

        snapshot, cache_path_value, cache_hit = api.load_or_build_snapshot(
            save_path,
            Path(args.cache_dir),
            templates_dir,
            refresh=args.refresh_cache,
        )
        if command in SNAPSHOT_COMMANDS:
            getattr(api, SNAPSHOT_COMMANDS[command])(snapshot, args)
        elif command == "cache":
            api.print_json(
                {
                    "cache": str(cache_path_value),
                    "cacheHit": cache_hit,
                    "source": snapshot.get("source"),
                    "templateSource": snapshot.get("templateSource"),
                    "schemaVersion": snapshot.get("schemaVersion"),
                },
                compact=args.compact,
            )
        else:
            parser.error(f"Unknown command: {command}")
    except BrokenPipeError:
        return 1
    except api.CalculationDependencyError as exc:
        api.print_json(
            {
                "status": "incomplete",
                "missingDependencies": exc.missing_dependencies,
            },
            compact=getattr(args, "compact", False),
        )
        return 2
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0
