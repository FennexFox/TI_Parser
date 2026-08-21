"""Read-only diagnostics for AI fleet goals and ship construction state.

The game save exposes facts about assignments and queues, but it does not expose
the complete decision process that produced them.  This module consequently
keeps save fields under ``observed``, mechanically joined/calculated values under
``derived``, threshold-based warnings under ``suspected``, and unresolved causes
or references under ``unknown``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable

from ti_parser_core import IndexedState, clean_numbers, first_value, ref_id, short_type, type_entries


SUPPORTED_GOAL_TYPES = (
    "FactionGoal_AttackWithFleet",
    "FactionGoal_TransportCouncilorsWithFleet",
)


@dataclass
class _ResolutionStats:
    attempted: int = 0
    resolved: int = 0
    missing: int = 0


def _state_id(value: Any) -> int | None:
    """Accept both serialized TI references and convenient synthetic-test IDs."""
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return ref_id(value)


def _entry_id(entry: dict[str, Any]) -> int | None:
    value = entry.get("Value") if isinstance(entry.get("Value"), dict) else {}
    return _state_id(entry.get("Key")) or _state_id(value.get("ID"))


def _ti_datetime(value: Any) -> datetime | None:
    if not isinstance(value, dict):
        return None
    try:
        return datetime(
            int(value.get("year", 1)),
            int(value.get("month", 1)),
            int(value.get("day", 1)),
            int(value.get("hour", 0)),
            int(value.get("minute", 0)),
            int(value.get("second", 0)),
            int(value.get("millisecond", 0)) * 1000,
        )
    except (TypeError, ValueError):
        return None


def _reference(
    indexed: IndexedState,
    value: Any,
    stats: _ResolutionStats,
    *,
    details: bool = False,
) -> dict[str, Any] | None:
    state_id = _state_id(value)
    if state_id is None:
        return None
    stats.attempted += 1
    found = indexed.id_index.get(state_id)
    if found is None:
        stats.missing += 1
        return {"id": state_id, "resolved": False}

    stats.resolved += 1
    _, type_name, state = found
    result: dict[str, Any] = {
        "id": state_id,
        "resolved": True,
        "type": type_name,
        "template": state.get("templateName"),
        "display": state.get("displayName"),
    }
    if details and type_name == "TISpaceFleetState":
        ship_refs = state.get("ships") if isinstance(state.get("ships"), list) else []
        result.update(
            {
                "faction": _reference(indexed, state.get("faction"), stats),
                "location": _reference(indexed, state.get("location") or state.get("orbit"), stats),
                "dockedLocation": _reference(indexed, state.get("dockedLocation"), stats),
                "homeport": _reference(indexed, state.get("homeport"), stats),
                "ships": [_reference(indexed, item, stats) for item in ship_refs],
                "shipCount": len(ship_refs),
                "inTransfer": state.get("inTransfer"),
                "unavailableForOperations": state.get("unavailableForOperations"),
                "currentOperations": state.get("currentOperations"),
            }
        )
    return result


def _faction_player(indexed: IndexedState, faction_id: int, faction: dict[str, Any], stats: _ResolutionStats) -> tuple[dict[str, Any] | None, bool | None]:
    raw_player = faction.get("player")
    player_summary = _reference(indexed, raw_player, stats)
    if isinstance(raw_player, dict) and isinstance(raw_player.get("isAI"), bool):
        return player_summary, raw_player["isAI"]

    player_id = _state_id(raw_player)
    if player_id is not None:
        found = indexed.id_index.get(player_id)
        if found is not None and isinstance(found[2].get("isAI"), bool):
            return player_summary, found[2]["isAI"]

    # Some minimized saves omit TIFactionState.player but retain the inverse link.
    for entry in type_entries(indexed, "TIPlayerState"):
        player = entry.get("Value") if isinstance(entry.get("Value"), dict) else {}
        if _state_id(player.get("faction")) != faction_id:
            continue
        player_summary = _reference(indexed, entry.get("Key") or player.get("ID"), stats)
        is_ai = player.get("isAI")
        return player_summary, is_ai if isinstance(is_ai, bool) else None
    return player_summary, None


def _faction_summary(faction_id: int, faction: dict[str, Any], is_ai: bool | None) -> dict[str, Any]:
    return {
        "id": faction_id,
        "template": faction.get("templateName"),
        "display": faction.get("displayName"),
        "isAI": is_ai,
    }


def _faction_matches(faction: dict[str, Any], faction_name: str) -> bool:
    needle = faction_name.strip().casefold()
    if not needle:
        return False
    candidates: set[str] = set()
    for value in (faction.get("templateName"), faction.get("displayName")):
        if not value:
            continue
        normalized = str(value).strip().casefold()
        candidates.add(normalized)
        if normalized.endswith("council"):
            candidates.add(normalized[: -len("council")])
    return needle in candidates


def _goal_entries(indexed: IndexedState) -> Iterable[tuple[str, dict[str, Any]]]:
    for full_type, entries in indexed.gamestates.items():
        type_name = short_type(full_type)
        if type_name not in SUPPORTED_GOAL_TYPES or not isinstance(entries, list):
            continue
        for entry in entries:
            if isinstance(entry, dict) and isinstance(entry.get("Value"), dict):
                yield type_name, entry


def _age_days(current: datetime | None, assigned: datetime | None) -> float | None:
    if current is None or assigned is None:
        return None
    return (current - assigned).total_seconds() / 86400.0


def _missing_reference_finding(field: str, reference: dict[str, Any] | None) -> dict[str, Any] | None:
    if reference is None or reference.get("resolved") is not False:
        return None
    return {
        "code": "unresolved-reference",
        "field": field,
        "id": reference.get("id"),
        "message": f"{field} references a state that is absent from the save index.",
    }


def _goal_diagnostic(
    indexed: IndexedState,
    goal_type: str,
    entry: dict[str, Any],
    current: datetime | None,
    stale_days: float | None,
    stats: _ResolutionStats,
) -> dict[str, Any]:
    goal = entry["Value"]
    assigned_ref = _reference(indexed, goal.get("assignedFleet"), stats, details=True)
    raw_pending = goal.get("pendingFleets") if isinstance(goal.get("pendingFleets"), list) else []
    pending_refs = [_reference(indexed, item, stats, details=True) for item in raw_pending]
    assigned_date = goal.get("assignedDate")
    age_days = _age_days(current, _ti_datetime(assigned_date))

    if assigned_ref is not None and pending_refs:
        assignment_state = "assigned-and-pending"
    elif assigned_ref is not None:
        assignment_state = "assigned"
    elif pending_refs:
        assignment_state = "pending"
    else:
        assignment_state = "unassigned"

    observed: dict[str, Any] = {
        "assignedDate": assigned_date,
        "assignedFleet": assigned_ref,
        "pendingFleets": pending_refs,
        "importance": goal.get("importance"),
        "objectiveTemplateName": goal.get("objectiveTemplateName"),
        "exists": goal.get("exists"),
        "archived": goal.get("archived"),
        "resupplyHab": _reference(indexed, goal.get("resupplyHab"), stats),
        "flyByLocation": _reference(indexed, goal.get("flyByLocation"), stats),
    }
    if goal_type == "FactionGoal_AttackWithFleet":
        observed.update(
            {
                "attackTarget": _reference(indexed, goal.get("attackTarget"), stats),
                "dynamicAttackTarget": _reference(indexed, goal.get("dynamicAttackTarget"), stats),
                "enemyFaction": _reference(indexed, goal.get("enemyFaction"), stats),
                "requiresWar": goal.get("requiresWar"),
            }
        )
    else:
        raw_councilors = goal.get("assignedCouncilors") if isinstance(goal.get("assignedCouncilors"), list) else []
        observed.update(
            {
                "assignedCouncilors": [_reference(indexed, item, stats) for item in raw_councilors],
                "councilorDestination": _reference(indexed, goal.get("councilorDestination"), stats),
                "dynamicAttackTarget": _reference(indexed, goal.get("dynamicAttackTarget"), stats),
            }
        )

    unknown: list[dict[str, Any]] = []
    finding = _missing_reference_finding("assignedFleet", assigned_ref)
    if finding:
        unknown.append(finding)
    for position, pending in enumerate(pending_refs):
        finding = _missing_reference_finding(f"pendingFleets[{position}]", pending)
        if finding:
            unknown.append(finding)
    if assigned_date is not None and age_days is None:
        unknown.append(
            {
                "code": "invalid-assigned-date",
                "message": "assignedDate or the current save date could not be parsed; ageDays is unknown.",
            }
        )
    elif age_days is not None and age_days < 0:
        unknown.append(
            {
                "code": "future-assigned-date",
                "message": "assignedDate is later than the current save date.",
            }
        )
    if assignment_state == "unassigned":
        unknown.append(
            {
                "code": "unassigned-goal-cause-unknown",
                "message": "The save contains no assigned or pending fleet; the AI decision cause is not reconstructed.",
            }
        )

    suspected: list[dict[str, Any]] = []
    if stale_days is not None and age_days is not None and age_days >= 0 and age_days >= stale_days:
        suspected.append(
            {
                "code": "stale-assignment",
                "message": "Goal age meets the caller-supplied stale threshold.",
                "ageDays": age_days,
                "thresholdDays": stale_days,
            }
        )

    return {
        "id": _entry_id(entry),
        "type": goal_type,
        "observed": observed,
        "derived": {
            "ageDays": age_days,
            "assignmentState": assignment_state,
            "pendingFleetCount": len(pending_refs),
            "assignedFleetShipCount": assigned_ref.get("shipCount") if assigned_ref and assigned_ref.get("resolved") else None,
        },
        "suspected": suspected,
        "unknown": unknown,
    }


def _queue_pairs(raw: Any) -> list[tuple[Any, list[Any]]]:
    pairs: list[tuple[Any, list[Any]]] = []
    if isinstance(raw, list):
        for row in raw:
            if not isinstance(row, dict):
                continue
            value = row.get("Value")
            pairs.append((row.get("Key"), value if isinstance(value, list) else []))
    elif isinstance(raw, dict):
        for key, value in raw.items():
            try:
                normalized_key: Any = int(key)
            except (TypeError, ValueError):
                normalized_key = key
            pairs.append((normalized_key, value if isinstance(value, list) else []))
    return pairs


def _resource_costs(queue_item: dict[str, Any]) -> dict[str, float]:
    container = queue_item.get("resourcesCost")
    if not isinstance(container, dict):
        return {}
    rows = container.get("resourceCosts")
    if not isinstance(rows, list):
        return {}
    result: dict[str, float] = {}
    for row in rows:
        if not isinstance(row, dict) or not row.get("resource"):
            continue
        try:
            result[str(row["resource"])] = float(row.get("value", 0.0))
        except (TypeError, ValueError):
            continue
    return result


def _explicit_blockers(queue_item: dict[str, Any]) -> dict[str, Any]:
    blocker_fields = (
        "blocked",
        "isBlocked",
        "constructionBlocked",
        "waitingForResources",
        "blockedReason",
        "blockReason",
        "failureReason",
    )
    return {
        field: queue_item.get(field)
        for field in blocker_fields
        if queue_item.get(field) not in (None, False, "", [], {})
    }


def _shipyard_summary(
    indexed: IndexedState,
    yard_ref: Any,
    queue: list[Any],
    faction_resources: dict[str, Any],
    stats: _ResolutionStats,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    yard = _reference(indexed, yard_ref, stats)
    unknown: list[dict[str, Any]] = []
    suspected: list[dict[str, Any]] = []
    sector_summary = None
    hab_summary = None
    yard_state: dict[str, Any] | None = None
    yard_id = _state_id(yard_ref)
    found = indexed.id_index.get(yard_id) if yard_id is not None else None
    if found is None:
        finding = _missing_reference_finding("shipyard", yard)
        if finding:
            unknown.append(finding)
    else:
        yard_state = found[2]
        sector_summary = _reference(indexed, yard_state.get("sector"), stats)
        sector_id = _state_id(yard_state.get("sector"))
        sector_found = indexed.id_index.get(sector_id) if sector_id is not None else None
        if sector_found is not None:
            hab_summary = _reference(indexed, sector_found[2].get("hab"), stats)

    item_summaries: list[dict[str, Any]] = []
    for item in queue:
        if not isinstance(item, dict):
            unknown.append(
                {"code": "invalid-queue-item", "message": "A shipyard queue item is not an object."}
            )
            continue
        costs = _resource_costs(item)
        shortfalls: dict[str, float] = {}
        for resource, cost in costs.items():
            try:
                available = float(faction_resources.get(resource, 0.0))
            except (TypeError, ValueError):
                continue
            if cost > available:
                shortfalls[resource] = cost - available
        blockers = _explicit_blockers(item)
        item_summary = {
            "shipDesignTemplateName": item.get("shipDesignTemplateName"),
            "startDate": item.get("startDate"),
            "daysToCompletion": item.get("daysToCompletion"),
            "costPaid": item.get("costPaid"),
            "resourceCosts": costs,
            "aiFactionGoal": _reference(indexed, item.get("AIFactionGoal"), stats),
            "isRefit": item.get("isRefit"),
            "explicitBlockers": blockers,
            "resourceShortfallsAtCurrentStock": shortfalls,
        }
        item_summaries.append(item_summary)
        if blockers:
            suspected.append(
                {
                    "code": "explicit-construction-blocker",
                    "shipyardId": yard_id,
                    "shipDesignTemplateName": item.get("shipDesignTemplateName"),
                    "evidence": blockers,
                }
            )

    if not queue:
        unknown.append(
            {
                "code": "empty-queue-cause-unknown",
                "shipyardId": yard_id,
                "message": "The shipyard queue is empty; this alone does not establish a resource shortage or other cause.",
            }
        )

    operational = None
    if yard_state is not None:
        operational = not any(
            (
                yard_state.get("exists") is False,
                yard_state.get("archived") is True,
                yard_state.get("destroyed") is True,
                yard_state.get("decommissioning") is True,
                yard_state.get("constructionCompleted") is False,
                yard_state.get("powered") is False,
            )
        )

    return (
        {
            "shipyard": yard,
            "sector": sector_summary,
            "hab": hab_summary,
            "queue": item_summaries,
            "derived": {"queueLength": len(item_summaries), "operational": operational},
        },
        suspected,
        unknown,
    )


def _faction_diagnostic(
    indexed: IndexedState,
    faction_id: int,
    faction: dict[str, Any],
    player: dict[str, Any] | None,
    is_ai: bool,
    current: datetime | None,
    stale_days: float | None,
    stats: _ResolutionStats,
) -> dict[str, Any]:
    goals = [
        _goal_diagnostic(indexed, goal_type, entry, current, stale_days, stats)
        for goal_type, entry in _goal_entries(indexed)
        if _state_id(entry["Value"].get("faction")) == faction_id
        and entry["Value"].get("exists") is not False
        and entry["Value"].get("archived") is not True
    ]

    fleet_refs = faction.get("fleets") if isinstance(faction.get("fleets"), list) else []
    fleets = [_reference(indexed, item, stats, details=True) for item in fleet_refs]
    # Older/minimal saves may not populate faction.fleets; join fleet.faction too.
    known_fleet_ids = {fleet.get("id") for fleet in fleets if fleet}
    for entry in type_entries(indexed, "TISpaceFleetState"):
        fleet = entry.get("Value") if isinstance(entry.get("Value"), dict) else {}
        fleet_id = _entry_id(entry)
        if _state_id(fleet.get("faction")) == faction_id and fleet_id not in known_fleet_ids:
            fleets.append(_reference(indexed, entry.get("Key") or fleet.get("ID"), stats, details=True))
            known_fleet_ids.add(fleet_id)

    resources = faction.get("resources") if isinstance(faction.get("resources"), dict) else {}
    shipyards: list[dict[str, Any]] = []
    suspected: list[dict[str, Any]] = []
    unknown: list[dict[str, Any]] = []
    for yard_ref, queue in _queue_pairs(faction.get("nShipyardQueues")):
        summary, yard_suspected, yard_unknown = _shipyard_summary(indexed, yard_ref, queue, resources, stats)
        shipyards.append(summary)
        suspected.extend(yard_suspected)
        unknown.extend(yard_unknown)

    missing_fleet_ids = [fleet.get("id") for fleet in fleets if fleet and fleet.get("resolved") is False]
    if missing_fleet_ids:
        unknown.append(
            {
                "code": "unresolved-faction-fleets",
                "ids": missing_fleet_ids,
                "message": "One or more faction fleet references are absent from the save index.",
            }
        )

    mc_usage = faction.get("missionControlUsage")
    mc_capacity = next(
        (
            faction.get(field)
            for field in ("missionControlCapacity", "missionControlCap", "maxMissionControl")
            if faction.get(field) is not None
        ),
        None,
    )
    mc_at_capacity = None
    try:
        if mc_usage is not None and mc_capacity is not None:
            mc_at_capacity = float(mc_usage) >= float(mc_capacity)
    except (TypeError, ValueError):
        mc_at_capacity = None
    if mc_at_capacity:
        suspected.append(
            {
                "code": "mission-control-capacity-reached",
                "message": "Observed mission-control usage meets or exceeds an explicit capacity field in the save.",
                "usage": mc_usage,
                "capacity": mc_capacity,
            }
        )
    elif mc_capacity is None:
        unknown.append(
            {
                "code": "mission-control-capacity-unknown",
                "message": "No explicit mission-control capacity field was available; MC blocking is not inferred.",
            }
        )

    suspected.extend(finding for goal in goals for finding in goal["suspected"])
    return {
        "faction": _faction_summary(faction_id, faction, is_ai),
        "goals": goals,
        "observed": {
            "player": player,
            "resources": resources,
            "missionControlUsage": mc_usage,
            "missionControlCapacity": mc_capacity,
            "fleets": fleets,
            "habReferences": [
                _reference(indexed, item, stats)
                for item in (faction.get("habSectors") if isinstance(faction.get("habSectors"), list) else [])
            ],
            "shipyards": shipyards,
        },
        "derived": {
            "goalCount": len(goals),
            "fleetCount": len(fleets),
            "shipCount": sum(int(fleet.get("shipCount") or 0) for fleet in fleets if fleet and fleet.get("resolved")),
            "shipyardCount": len(shipyards),
            "queuedShipCount": sum(int(row["derived"]["queueLength"]) for row in shipyards),
            "missionControlAtExplicitCapacity": mc_at_capacity,
        },
        "suspected": suspected,
        "unknown": unknown,
    }


def calculate_ai_fleet_diagnostics(
    indexed: IndexedState,
    faction_name: str | None = None,
    stale_days: float | None = None,
    diagnostics: bool = False,
) -> dict[str, Any]:
    """Diagnose supported AI fleet goals without reconstructing AI intent.

    When ``faction_name`` is omitted, every faction with an explicitly AI
    ``TIPlayerState`` is included.  The optional name filters that AI set by
    template or display name.  No stale conclusion is produced unless
    ``stale_days`` is supplied by the caller.
    """
    if stale_days is not None:
        if isinstance(stale_days, bool):
            raise ValueError("stale_days must be a non-negative number")
        try:
            stale_days = float(stale_days)
        except (TypeError, ValueError) as exc:
            raise ValueError("stale_days must be a non-negative number") from exc
        if stale_days < 0:
            raise ValueError("stale_days must be a non-negative number")

    time_state = first_value(indexed, "TITimeState") or {}
    raw_current = time_state.get("currentDateTime")
    current = _ti_datetime(raw_current)
    stats = _ResolutionStats()
    candidates: list[tuple[int, dict[str, Any], dict[str, Any] | None, bool]] = []
    named_matches = 0
    for entry in type_entries(indexed, "TIFactionState"):
        faction = entry.get("Value") if isinstance(entry.get("Value"), dict) else {}
        faction_id = _entry_id(entry)
        if faction_id is None:
            continue
        if faction_name is not None and not _faction_matches(faction, faction_name):
            continue
        if faction_name is not None:
            named_matches += 1
        player, is_ai = _faction_player(indexed, faction_id, faction, stats)
        if is_ai is True:
            candidates.append((faction_id, faction, player, is_ai))

    if faction_name is not None and named_matches == 0:
        raise ValueError(f"Faction not found: {faction_name}")
    if faction_name is not None and not candidates:
        raise ValueError(f"Faction is not AI: {faction_name}")

    factions = [
        _faction_diagnostic(indexed, faction_id, faction, player, is_ai, current, stale_days, stats)
        for faction_id, faction, player, is_ai in candidates
    ]
    result: dict[str, Any] = {
        "date": raw_current,
        "filters": {"faction": faction_name, "staleDays": stale_days},
        "factions": factions,
        "derived": {
            "factionCount": len(factions),
            "goalCount": sum(row["derived"]["goalCount"] for row in factions),
        },
    }
    if diagnostics:
        result["calculationDiagnostics"] = {
            "readOnly": True,
            "supportedGoalTypes": list(SUPPORTED_GOAL_TYPES),
            "referenceResolution": {
                "attempted": stats.attempted,
                "resolved": stats.resolved,
                "missing": stats.missing,
            },
            "staleClassificationEnabled": stale_days is not None,
            "limitations": [
                "AI decision weights and intent are not reconstructed.",
                "An empty construction queue is not classified as a resource shortage.",
                "Current-stock shortfalls do not prove construction is blocked unless the save exposes an explicit blocker.",
            ],
        }
    return clean_numbers(result, 6)


__all__ = ["SUPPORTED_GOAL_TYPES", "calculate_ai_fleet_diagnostics"]
