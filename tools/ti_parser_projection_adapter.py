"""Save-state extraction and input assembly for nation projection."""

from __future__ import annotations

from ti_parser_errors import UserInputError

import math
from datetime import datetime
from typing import Any

import ti_parser_income as income_layer
import ti_parser_nation_projection as nation_projection_layer
import ti_parser_snapshot as snapshot_layer
from ti_parser_config import (
    INCOME_CONFIG,
    PRIORITY_BONUS_EFFECT_CONTEXTS,
    PRIORITY_BONUS_ORG_FIELDS,
)
from ti_parser_core import (
    CalculationDependency,
    CalculationDependencyError,
    IndexedState,
    apply_effect_modifiers,
    as_float,
    faction_effect_contexts,
    find_faction_state,
    first_value,
    load_hab_module_catalog,
    load_location_catalog,
    match_raw_state,
    raw_state_id,
    ref_id,
    resolve_ref,
    scenario_template_name,
    state_value_by_id,
    type_entries,
)
from ti_parser_hab_ui import hab_leo_priority_bonuses
from ti_parser_mechanics import Rules
from ti_parser_nation_ui import federation_space_program
from ti_parser_runtime import (
    calculation_catalogs,
    councilor_summary_maps,
    faction_councilor_ids,
    faction_hab_states,
    hab_module_records,
    nation_control_points,
    nation_current_mission_control,
    nation_federation_pooled_year,
    nation_population_millions,
    national_ip_multiplier,
    ti_datetime,
)
from ti_parser_topbar import calculate_topbar
from ti_parser_world import temperature_anomaly_components


def faction_priority_bonuses_for_projection(
    indexed: IndexedState,
    faction_id: int,
    faction: dict[str, Any],
    priorities: dict[str, Any],
    trait_templates: dict[str, dict[str, Any]],
    effect_templates: dict[str, dict[str, Any]],
    *,
    apply_effects: bool = True,
) -> tuple[dict[str, float], dict[str, float]]:
    bonuses = {name: 0.0 for name in priorities}
    for councilor_id in faction_councilor_ids(faction):
        councilor = state_value_by_id(indexed, councilor_id) or {}
        for org_ref in councilor.get("orgs") if isinstance(councilor.get("orgs"), list) else []:
            org = state_value_by_id(indexed, ref_id(org_ref)) or {}
            if not org.get("applyingBonuses"):
                continue
            for priority, field in PRIORITY_BONUS_ORG_FIELDS.items():
                if priority in bonuses:
                    bonuses[priority] += as_float(org.get(field), 0.0)
        for trait_name in councilor.get("traitTemplateNames") if isinstance(councilor.get("traitTemplateNames"), list) else []:
            trait = trait_templates.get(str(trait_name), {})
            for row in trait.get("priorityBonuses") if isinstance(trait.get("priorityBonuses"), list) else []:
                if not isinstance(row, dict):
                    continue
                priority = str(row.get("priority") or "")
                if priority in bonuses:
                    bonuses[priority] += as_float(row.get("bonus"), 0.0)
    hab_module_templates = load_hab_module_catalog()
    for _, hab in faction_hab_states(indexed, faction):
        for priority, value in hab_leo_priority_bonuses(hab, hab_module_records(indexed, hab, hab_module_templates)).items():
            if priority in bonuses:
                bonuses[priority] += as_float(value, 0.0)
    base_bonuses = dict(bonuses)
    if apply_effects:
        contexts = faction_effect_contexts(indexed, faction_id)
        for priority, context_name in PRIORITY_BONUS_EFFECT_CONTEXTS.items():
            if priority in bonuses:
                bonuses[priority] = apply_effect_modifiers(contexts, effect_templates, context_name, bonuses[priority])
    return bonuses, base_bonuses


def faction_effect_expirations_for_projection(indexed: IndexedState) -> dict[int, dict[str, datetime]]:
    result: dict[int, dict[str, datetime]] = {}
    for entry in type_entries(indexed, "TIEffectsState"):
        value = entry.get("Value") or {}
        pairs = value.get("factionEffectExpirations")
        if not isinstance(pairs, list):
            continue
        for pair in pairs:
            if not isinstance(pair, dict):
                continue
            faction_id = ref_id(pair.get("Key"))
            raw_expirations = pair.get("Value")
            if faction_id is None or not isinstance(raw_expirations, dict):
                continue
            parsed: dict[str, datetime] = {}
            for effect_name, raw_expiration in raw_expirations.items():
                expiration = ti_datetime(raw_expiration)
                if expiration is None:
                    raise _projection_dependency_error(
                        indexed,
                        source="save-field",
                        field="TIEffectsState.factionEffectExpirations",
                        rule_id=Rules.NATION_EFFECT_CONTEXT_EXPIRATION.id,
                        reason=f"faction effect {effect_name!r} has an invalid expiration timestamp",
                    )
                parsed[str(effect_name)] = expiration
            result[faction_id] = parsed
    return result


def projection_advisor_profiles(
    indexed: IndexedState,
    faction_id: int,
    faction: dict[str, Any],
    councilor_by_id: dict[int, dict[str, Any]],
) -> tuple[dict[int, nation_projection_layer.AdvisorProfile], dict[int, nation_projection_layer.AdvisorProfile]]:
    all_profiles: dict[int, nation_projection_layer.AdvisorProfile] = {}
    available: dict[int, nation_projection_layer.AdvisorProfile] = {}
    roster = set(faction_councilor_ids(faction))
    for entry in type_entries(indexed, "TICouncilorState"):
        councilor = entry.get("Value") or {}
        councilor_id = raw_state_id(entry)
        if councilor_id is None:
            continue
        summary = councilor_by_id.get(councilor_id, {})
        attributes = summary.get("finalAttributes") if isinstance(summary.get("finalAttributes"), dict) else {}
        profile = nation_projection_layer.AdvisorProfile(
            "saved",
            str(councilor.get("displayName") or councilor.get("templateName") or councilor_id),
            as_float(attributes.get("Administration"), 0.0),
            as_float(attributes.get("Science"), 0.0),
            councilor_id,
        )
        active = (
            snapshot_layer.councilor_activity(councilor)[0] is True
            and councilor.get("exists", True)
            and not councilor.get("archived")
        )
        if active:
            all_profiles[councilor_id] = profile
        if councilor_id in roster and ref_id(councilor.get("faction")) == faction_id and active:
            available[councilor_id] = profile
    return all_profiles, available


def projection_advisor_mission_schedule(
    indexed: IndexedState,
    development: dict[str, Any],
) -> nation_projection_layer.AdvisorMissionSchedule:
    config = development.get("advisorMission")
    if not isinstance(config, dict):
        raise _projection_dependency_error(
            indexed,
            source="catalog-field",
            field="advisorMission",
            rule_id=Rules.NATION_ADVISOR_MISSION_LIFECYCLE.id,
            reason="packaged Advise mission mechanics are absent",
        )
    cost = config.get("cost")
    phase_config = config.get("missionPhaseEvent")
    if (
        config.get("automaticSuccess") is not True
        or config.get("movementRule") != "MoveToTarget"
        or config.get("persistentEffect") is not True
        or not isinstance(cost, dict)
        or cost.get("type") != "TIMissionCost_Flat"
        or cost.get("resource") != "Influence"
        or not isinstance(phase_config, dict)
    ):
        raise _projection_dependency_error(
            indexed,
            source="catalog-field",
            field="advisorMission",
            rule_id=Rules.NATION_ADVISOR_MISSION_LIFECYCLE.id,
            reason="packaged Advise mission mechanics do not match the audited automatic MoveToTarget contract",
        )
    event = next((
        entry.get("Value") or {}
        for entry in type_entries(indexed, "TITimeEvent")
        if (entry.get("Value") or {}).get("eventName") == "CouncilorMissionUpdate"
        and not (entry.get("Value") or {}).get("archived")
    ), None)
    if not isinstance(event, dict):
        raise _projection_dependency_error(
            indexed,
            source="save-state",
            field="TITimeEvent.CouncilorMissionUpdate",
            rule_id=Rules.NATION_ADVISOR_MISSION_LIFECYCLE.id,
            reason="active mission-phase event is absent",
        )
    next_phase = ti_datetime(event.get("triggerTime"))
    repeat_type = event.get("repeatType")
    if next_phase is None or not isinstance(repeat_type, str):
        raise _projection_dependency_error(
            indexed,
            source="save-field",
            field="CouncilorMissionUpdate.triggerTime/repeatType",
            rule_id=Rules.NATION_ADVISOR_MISSION_LIFECYCLE.id,
            reason="mission-phase timing is invalid",
        )
    raw_changes = phase_config.get("repeatChanges")
    triggered = event.get("repeatChangeTriggered")
    if (
        phase_config.get("templateName") != "CouncilorMissionUpdate"
        or not isinstance(raw_changes, list)
        or triggered is not None and not isinstance(triggered, list)
    ):
        raise _projection_dependency_error(
            indexed,
            source="catalog-or-save-field",
            field="advisorMission.missionPhaseEvent/CouncilorMissionUpdate.repeatChangeTriggered",
            rule_id=Rules.NATION_ADVISOR_MISSION_LIFECYCLE.id,
            reason="mission-phase repeat-change inputs are invalid",
        )
    triggered = triggered or []
    repeat_changes: list[tuple[float, str, bool]] = []
    for index, row in enumerate(raw_changes):
        if not isinstance(row, dict):
            raise _projection_dependency_error(
                indexed,
                source="catalog-field",
                field="advisorMission.missionPhaseEvent.repeatChanges",
                rule_id=Rules.NATION_ADVISOR_MISSION_LIFECYCLE.id,
                reason="mission-phase repeat change row is not an object",
            )
        threshold = row.get("campaignYearsGreaterThan")
        updated_type = row.get("repeatType")
        saved_trigger = triggered[index] if index < len(triggered) else False
        if (
            not isinstance(threshold, (int, float)) or isinstance(threshold, bool)
            or not math.isfinite(float(threshold)) or float(threshold) < 0
            or not isinstance(updated_type, str) or not updated_type
            or not isinstance(saved_trigger, bool)
        ):
            raise _projection_dependency_error(
                indexed,
                source="catalog-field",
                field="advisorMission.missionPhaseEvent.repeatChanges",
                rule_id=Rules.NATION_ADVISOR_MISSION_LIFECYCLE.id,
                reason="mission-phase repeat change is invalid",
            )
        repeat_changes.append((float(threshold), updated_type, saved_trigger))
    cost_value = cost.get("value")
    segments = config.get("resolutionSegmentsPerPhase")
    resolution_order = config.get("resolutionOrder")
    time_step = event.get("timeStep", 1)
    start_month = event.get("startMonth", next_phase.month)
    if (
        not isinstance(cost_value, (int, float)) or isinstance(cost_value, bool)
        or not math.isfinite(float(cost_value)) or cost_value < 0
        or not isinstance(segments, (int, float)) or isinstance(segments, bool)
        or not float(segments).is_integer() or int(segments) <= 0
        or not isinstance(resolution_order, (int, float)) or isinstance(resolution_order, bool)
        or not float(resolution_order).is_integer() or not 0 <= float(resolution_order) < int(segments)
        or not isinstance(time_step, (int, float)) or isinstance(time_step, bool)
        or not float(time_step).is_integer() or int(time_step) <= 0
        or not isinstance(start_month, (int, float)) or isinstance(start_month, bool)
        or not float(start_month).is_integer() or not 1 <= int(start_month) <= 12
    ):
        raise _projection_dependency_error(
            indexed,
            source="catalog-or-save-field",
            field="advisorMission.cost/resolution and CouncilorMissionUpdate.timeStep/startMonth",
            rule_id=Rules.NATION_ADVISOR_MISSION_LIFECYCLE.id,
            reason="mission lifecycle numeric inputs are invalid",
        )
    mission_phase = first_value(indexed, "TIMissionPhaseState") or {}
    return nation_projection_layer.AdvisorMissionSchedule(
        next_phase_at=next_phase,
        repeat_type=repeat_type,
        time_step=int(time_step),
        start_month=int(start_month),
        resolution_segments_per_phase=int(segments),
        resolution_order=int(resolution_order),
        automatic_success=True,
        movement_rule="MoveToTarget",
        influence_cost=float(cost_value),
        repeat_changes=tuple(repeat_changes),
        phase_active=mission_phase.get("phaseActive") is True,
    )


def _projection_dependency_error(
    indexed: IndexedState,
    *,
    source: str,
    field: str,
    rule_id: str,
    reason: str,
) -> CalculationDependencyError:
    """Build the structured fail-closed error used by projection extraction.

    ``CalculationDependency`` predates the mechanics registry and intentionally
    has no dedicated rule-id member.  The stable rule ID is therefore carried
    in ``context`` while ``name`` preserves the exact source field/catalog row.
    That keeps the existing public error contract intact and still lets callers
    associate the missing input with the same registry entry used by the engine.
    """

    return CalculationDependencyError(
        CalculationDependency(
            kind=source,
            name=field,
            context=rule_id,
            scenario=scenario_template_name(indexed),
            reason=reason,
        )
    )


def _required_projection_number(
    indexed: IndexedState,
    source_value: dict[str, Any],
    field: str,
    *,
    source: str,
    rule_id: str,
) -> float:
    value = source_value.get(field)
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(float(value)):
        raise _projection_dependency_error(
            indexed,
            source=source,
            field=field,
            rule_id=rule_id,
            reason="required finite numeric value is absent or invalid; no projection default is permitted",
        )
    return float(value)


def _required_projection_bool(
    indexed: IndexedState,
    source_value: dict[str, Any],
    field: str,
    *,
    source: str,
    rule_id: str,
) -> bool:
    value = source_value.get(field)
    if not isinstance(value, bool):
        raise _projection_dependency_error(
            indexed,
            source=source,
            field=field,
            rule_id=rule_id,
            reason="required boolean value is absent or invalid; no projection default is permitted",
        )
    return value


def _required_projection_string(
    indexed: IndexedState,
    source_value: dict[str, Any],
    field: str,
    *,
    source: str,
    rule_id: str,
) -> str:
    value = source_value.get(field)
    if not isinstance(value, str) or not value:
        raise _projection_dependency_error(
            indexed,
            source=source,
            field=field,
            rule_id=rule_id,
            reason="required non-empty string value is absent or invalid; no projection default is permitted",
        )
    return value


def _required_projection_army_type(
    indexed: IndexedState,
    source_value: dict[str, Any],
    field: str,
    *,
    source: str,
    rule_id: str,
) -> str:
    """Require one of the audited ``ArmyType`` enum names for Navy selection."""
    value = _required_projection_string(
        indexed, source_value, field, source=source, rule_id=rule_id,
    )
    if value not in {"Human", "AlienMegafauna", "AlienInvader"}:
        raise _projection_dependency_error(
            indexed,
            source=source,
            field=field,
            rule_id=rule_id,
            reason="army type is not a supported ArmyType enum value; no projection default is permitted",
        )
    return value


def _required_projection_deployment_type(
    indexed: IndexedState,
    source_value: dict[str, Any],
    field: str,
    *,
    source: str,
    rule_id: str,
) -> str:
    """Require one of the audited ``DeploymentType`` enum names."""
    value = _required_projection_string(
        indexed, source_value, field, source=source, rule_id=rule_id,
    )
    if value not in {"None", "Standard", "Naval"}:
        raise _projection_dependency_error(
            indexed,
            source=source,
            field=field,
            rule_id=rule_id,
            reason="deployment type is not a supported DeploymentType enum value; no projection default is permitted",
        )
    return value


def _required_projection_ocean_type(
    indexed: IndexedState,
    source_value: dict[str, Any],
    field: str,
    *,
    source: str,
    rule_id: str,
) -> str:
    value = _required_projection_string(
        indexed, source_value, field, source=source, rule_id=rule_id,
    )
    if value not in {"No", "None", "Yes", "Seasonal"}:
        raise _projection_dependency_error(
            indexed,
            source=source,
            field=field,
            rule_id=rule_id,
            reason="required ocean type is unsupported; no projection default is permitted",
        )
    return value


def _required_projection_mapping(
    indexed: IndexedState,
    source_value: dict[str, Any],
    field: str,
    *,
    source: str,
    rule_id: str,
) -> dict[str, Any]:
    value = source_value.get(field)
    if not isinstance(value, dict):
        raise _projection_dependency_error(
            indexed,
            source=source,
            field=field,
            rule_id=rule_id,
            reason="required object is absent or invalid; no projection default is permitted",
        )
    return value


def _required_projection_list(
    indexed: IndexedState,
    source_value: dict[str, Any],
    field: str,
    *,
    source: str,
    rule_id: str,
) -> list[Any]:
    value = source_value.get(field)
    if not isinstance(value, list):
        raise _projection_dependency_error(
            indexed,
            source=source,
            field=field,
            rule_id=rule_id,
            reason="required array is absent or invalid; no projection default is permitted",
        )
    return value


def _required_projection_catalog_row(
    indexed: IndexedState,
    rows: Any,
    name: Any,
    *,
    collection: str,
    rule_id: str,
) -> dict[str, Any]:
    normalized = str(name or "")
    row = rows.get(normalized) if isinstance(rows, dict) else None
    if normalized and isinstance(row, dict):
        return row
    raise _projection_dependency_error(
        indexed,
        source="catalog-field",
        field=f"{collection}.{normalized or '<missing reference>'}",
        rule_id=rule_id,
        reason="save-referenced template row is absent from the packaged scenario catalog",
    )


def _serialized_numeric_tracker(
    indexed: IndexedState,
    value: Any,
    *,
    field: str,
    rule_id: str,
) -> dict[int, float]:
    if not isinstance(value, list):
        raise _projection_dependency_error(
            indexed,
            source="save-field",
            field=field,
            rule_id=rule_id,
            reason="required serialized numeric tracker is absent or invalid",
        )
    result: dict[int, float] = {}
    for row in value:
        if (
            not isinstance(row, dict)
            or not isinstance(row.get("Key"), int)
            or not isinstance(row.get("Value"), (int, float))
            or isinstance(row.get("Value"), bool)
        ):
            raise _projection_dependency_error(
                indexed,
                source="save-field",
                field=field,
                rule_id=rule_id,
                reason="serialized numeric tracker contains an invalid Key/Value row",
            )
        result[int(row["Key"])] = float(row["Value"])
    return result


def _region_occupation_fraction(region: dict[str, Any], indexed: IndexedState,
                                nation: dict[str, Any], nation_id: int) -> float:
    """Current DLL max of summed enemy-alliance occupation for each war.

    Invalid/unresolved source returns NaN so the adapter's dependency gate
    rejects it. No individual-occupier maximum substitutes for an alliance.
    """
    occupations = region.get("occupations")
    if occupations == {} or occupations == []:
        return 0.0
    if not isinstance(occupations, list):
        return math.nan
    values: dict[int, float] = {}
    for row in occupations:
        if not isinstance(row, dict):
            return math.nan
        key, value = ref_id(row.get("Key")), row.get("Value")
        if key is None or key in values or not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value) or value < 0:
            return math.nan
        values[key] = float(value)
    wars = nation.get("currentWarStates")
    if not isinstance(wars, list):
        return math.nan
    maximum = 0.0
    for war_ref in wars:
        resolved = resolve_ref(indexed, war_ref)
        if resolved is None or resolved[1] != "TIWarState":
            return math.nan
        war = resolved[2]
        alliances = []
        for name in ("_attackingAlliance", "_defendingAlliance"):
            members = war.get(name)
            if not isinstance(members, list):
                return math.nan
            ids = []
            for member in members:
                found = resolve_ref(indexed, member)
                if found is None or found[1] != "TINationState":
                    return math.nan
                ids.append(ref_id(member))
            if len(ids) != len(set(ids)):
                return math.nan
            alliances.append(ids)
        attack, defend = alliances
        if set(attack) & set(defend):
            return math.nan
        enemy = defend if nation_id in attack else attack if nation_id in defend else []
        maximum = max(maximum, sum(values.get(member, 0.0) for member in enemy))
    return min(1.0, maximum)


def _extract_projection_rest_inputs(
    indexed: IndexedState,
    nation: dict[str, Any],
    state: nation_projection_layer.NationProjectionState,
    development: dict[str, Any],
) -> dict[str, Any]:
    """Extract getter inputs directly; clamped UI caches cannot identify them."""
    rule_id = Rules.NATION_PERIODIC_DERIVED_CACHE.id

    def missing(field: str, reason: str, *, source: str = "save-reference") -> CalculationDependencyError:
        return _projection_dependency_error(indexed, source=source, field=field, rule_id=rule_id, reason=reason)

    def resolve(reference: Any, field: str) -> dict[str, Any]:
        value = state_value_by_id(indexed, ref_id(reference))
        if not isinstance(value, dict):
            raise missing(field, "required resting-state reference cannot be resolved")
        return value

    def number(value: dict[str, Any], field: str) -> float:
        return _required_projection_number(indexed, value, field, source="save-field", rule_id=rule_id)

    def refs(value: dict[str, Any], field: str) -> list[Any]:
        return _required_projection_list(indexed, value, field, source="save-field", rule_id=rule_id)

    def relation_rows(field: str) -> list[dict[str, Any]]:
        rows = []
        seen = set()
        for reference in refs(nation, field):
            other_id = ref_id(reference)
            other = resolve(reference, f"nation.{field}")
            if field == "wars" and other_id in seen:
                continue
            seen.add(other_id)
            rows.append({"id": other_id, "democracy": number(other, "democracy"),
                         "extant": bool(refs(other, "regions")),
                         "numControlPoints": len(refs(other, "controlPoints"))})
        return rows

    alien_nation = _required_projection_bool(indexed, nation, "alienNation", source="save-field", rule_id=rule_id)
    public_opinion = _required_projection_mapping(indexed, nation, "publicOpinion", source="save-field", rule_id=Rules.NATION_COHESION_PUBLIC_OPINION.id)
    if not public_opinion or len(state.public_opinion) != len(public_opinion) or not all(math.isfinite(value) and value >= 0 for value in state.public_opinion.values()):
        raise missing("nation.publicOpinion", "live cohesion requires a complete numeric public-opinion mapping", source="save-field")
    if not state.pcgdp_tracker:
        raise missing("tracker_PCGDP_ByQuarter", "the live PCGDP cohesion getter requires a nonempty serialized tracker", source="save-field")
    capital = next((region for region in state.regions.values() if region.capital), None)
    if capital is None:
        raise missing("nation.capital", "live cohesion requires a capital belonging to the target nation")
    region_template = development["regionTemplates"][capital.template_name]
    map_template = development["mapRegionTemplates"][region_template["mapRegionName"]]
    if "solarBody" not in map_template:
        raise missing("mapRegionTemplates.solarBody", "catalog omits the solar-body input required by the distance getter", source="catalog-field")
    body_name = map_template["solarBody"]
    if body_name is None:
        body_name = "Earth"  # TIRegionState.solarBodyName's explicit source default.
    if not isinstance(body_name, str) or not body_name:
        raise missing("mapRegionTemplates.solarBody", "solar body must be a nonempty name or source null", source="catalog-field")
    body_template = load_location_catalog().body_templates.get(body_name)
    radius = _required_projection_number(indexed, {"meanRadius_km": (body_template or {}).get("meanRadius_km")}, "meanRadius_km", source="location-catalog-field", rule_id=rule_id)
    allied_armies = []
    for ally_ref in refs(nation, "allies"):
        ally = resolve(ally_ref, "nation.allies")
        ally_is_alien = _required_projection_bool(indexed, ally, "alienNation", source="save-field", rule_id=rule_id)
        for army_ref in refs(ally, "armies"):
            army = resolve(army_ref, "ally.armies")
            army_type = _required_projection_army_type(indexed, army, "armyType", source="save-field", rule_id=rule_id)
            if ally_is_alien and army_type == "AlienMegafauna":
                continue
            current_region_id = ref_id(army.get("currentRegion"))
            resolve(army.get("currentRegion"), "ally.army.currentRegion")
            if current_region_id not in state.regions:
                continue
            home_nation = resolve(army.get("homeNation"), "ally.army.homeNation")
            allied_armies.append({"strength": number(army, "strength"), "armyType": army_type,
                                  "factionId": ref_id(army.get("faction")), "currentRegionId": current_region_id,
                                  "homeBaseInvestmentPointsMonth": number(home_nation, "baseInvestmentPoints_month")})
    neighbors = None
    raw_adjacency = nation.get("adjacentNations")
    if raw_adjacency == {}:
        raw_adjacency = []
    if isinstance(raw_adjacency, list):
        neighbors = []
        for pair in raw_adjacency:
            if not isinstance(pair, dict) or pair.get("Value") not in {"None", "FriendlyCrossingOnly", "FullAdjacency"}:
                raise missing("nation.adjacentNations", "adjacency mapping contains an unsupported enum or malformed row", source="save-field")
            other = resolve(pair.get("Key"), "nation.adjacentNations")
            other_is_alien = _required_projection_bool(indexed, other, "alienNation", source="save-field", rule_id=rule_id)
            if pair["Value"] == "FullAdjacency" and not other_is_alien and refs(other, "regions"):
                neighbors.append({"democracy": number(other, "democracy"), "atWar": bool(refs(other, "wars"))})
    own_base = nation.get("baseInvestmentPoints_month")
    return {"sourceBacked": True, "provenance": "heldFixedWorldContext", "alienNation": alien_nation,
            "rivals": relation_rows("rivals"), "wars": relation_rows("wars"), "neighbors": neighbors,
            "spaceBodyRadiusKm": radius, "alliedArmies": allied_armies,
            "ownBaseInvestmentPointsMonth": float(own_base) if isinstance(own_base, (int, float)) and not isinstance(own_base, bool) and math.isfinite(own_base) else None,
            "pcgdpToReduceUnrestBy1": state.world_context["pcgdpToReduceUnrestBy1"],
            "alienHabSurveillanceStrength": _projection_alien_hab_surveillance(indexed, development)}


def _projection_alien_hab_surveillance(indexed: IndexedState, development: dict[str, Any]) -> float | None:
    """Reconstruct AlienHabSurveillanceStrength; unresolved source stays unknown."""
    templates = development.get("factionTemplates") or {}
    aliens = [entry.get("Value") or {} for entry in type_entries(indexed, "TIFactionState")
              if templates.get((entry.get("Value") or {}).get("templateName"), {}).get("isAlien") is True]
    if len(aliens) != 1 or not isinstance(aliens[0].get("habSectors"), list):
        return None
    habs: dict[int, dict[str, Any]] = {}
    for reference in aliens[0]["habSectors"]:
        sector = state_value_by_id(indexed, ref_id(reference))
        if not isinstance(sector, dict):
            return None
        hab_id = ref_id(sector.get("hab"))
        hab = state_value_by_id(indexed, hab_id)
        if hab_id is None or not isinstance(hab, dict):
            return None
        habs[hab_id] = hab
    module_templates = load_hab_module_catalog() if habs else {}
    total = 0.0
    for hab in habs.values():
        if hab.get("habType") == "Base":
            continue
        if hab.get("habType") != "Station":
            return None
        orbit = state_value_by_id(indexed, ref_id(hab.get("orbitState")))
        body = state_value_by_id(indexed, ref_id((orbit or {}).get("barycenter")))
        if not isinstance(body, dict) or not isinstance(body.get("templateName"), str):
            return None
        # GameStateManager.Earth resolves the unique Earth template state.
        parent = state_value_by_id(indexed, ref_id(body.get("barycenter")))
        if body["templateName"] != "Earth" and (parent or {}).get("templateName") != "Earth":
            if body.get("barycenter") is not None and not isinstance(parent, dict):
                return None
            continue
        if not isinstance(hab.get("sectors"), list):
            return None
        for sector_ref in hab["sectors"]:
            sector = state_value_by_id(indexed, ref_id(sector_ref))
            if not isinstance(sector, dict):
                return None
            if ref_id(sector.get("faction")) is None:
                continue
            if not isinstance(sector.get("habModules"), list):
                return None
            for module_ref in sector["habModules"]:
                module = state_value_by_id(indexed, ref_id(module_ref))
                if not isinstance(module, dict):
                    return None
                if not module.get("templateName"):
                    continue
                fields = ("constructionCompleted", "destroyed", "decommissioning", "powered")
                if not all(isinstance(module.get(field), bool) for field in fields):
                    return None
                if not module["constructionCompleted"] or module["destroyed"] or module["decommissioning"] or not module["powered"]:
                    continue
                template = module_templates.get(module["templateName"])
                if not isinstance(template, dict) or not isinstance(template.get("specialRules"), list):
                    return None
                if "AlienSurveillance" in template["specialRules"]:
                    value = template.get("specialRulesValue")
                    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
                        return None
                    total += value
    return total


def extract_nation_projection_state(
    indexed: IndexedState,
    nation_id: int,
    nation: dict[str, Any],
    all_advisors: dict[int, nation_projection_layer.AdvisorProfile],
    owner_bonuses: dict[int, dict[str, float]],
    development: dict[str, Any],
    advisor_schedule: nation_projection_layer.AdvisorMissionSchedule | None = None,
) -> nation_projection_layer.NationProjectionState:
    global_config = development.get("globalConfig") if isinstance(development.get("globalConfig"), dict) else {}
    nation_templates = development.get("nationTemplates") if isinstance(development.get("nationTemplates"), dict) else {}
    region_templates = development.get("regionTemplates") if isinstance(development.get("regionTemplates"), dict) else {}
    map_templates = development.get("mapRegionTemplates") if isinstance(development.get("mapRegionTemplates"), dict) else {}
    bilateral_templates = development.get("bilateralTemplates") if isinstance(development.get("bilateralTemplates"), dict) else {}
    time_state = first_value(indexed, "TITimeState") or {}
    start = ti_datetime(time_state.get("currentDateTime"))
    if start is None:
        raise nation_projection_layer.ProjectionInputError("Save has no valid TITimeState.currentDateTime")
    points = nation_control_points(indexed, nation)
    control_points: dict[int, nation_projection_layer.ControlPointProjectionState] = {}
    positions: set[int] = set()
    for index, cp in enumerate(points):
        cp_id = int(as_float((cp.get("ID") or {}).get("value"), -1))
        position = cp.get("positionInNation")
        if cp_id < 0 or not isinstance(position, int) or position in positions:
            raise nation_projection_layer.ProjectionInputError("Target nation has invalid or duplicate control-point identity/position")
        if ref_id(cp.get("nation")) not in {None, nation_id}:
            raise nation_projection_layer.ProjectionInputError("Control point nation reference does not match target nation")
        positions.add(position)
        owner_id = ref_id(cp.get("faction"))
        raw_pips = cp.get("controlPointPriorities") if isinstance(cp.get("controlPointPriorities"), dict) else {}
        raw_diversity = cp.get("diversityBonus") if isinstance(cp.get("diversityBonus"), dict) else {}
        control_points[cp_id] = nation_projection_layer.ControlPointProjectionState(
            id=cp_id,
            position=position,
            owner_faction_id=owner_id,
            benefits_disabled=bool(cp.get("benefitsDisabled")),
            control_point_type=cp.get("controlPointType"),
            pips={str(key): int(as_float(value, 0.0)) for key, value in raw_pips.items()},
            priority_bonuses=dict(owner_bonuses.get(owner_id or -1, {})),
            total_weight=int(as_float(cp.get("totalWeightsForControlPoint"), 0.0)),
            num_priorities_with_weight=int(as_float(cp.get("numPrioritiesWithWeight"), 0.0)),
            diversity_bonus_cache={str(key): as_float(value, 0.0) for key, value in raw_diversity.items()},
        )
    regions: dict[int, nation_projection_layer.RegionProjectionState] = {}
    region_map_names: dict[int, str] = {}
    total_population = _required_projection_number(
        indexed,
        {"population": nation_population_millions(indexed, nation)},
        "population",
        source="derived-save-field",
        rule_id=Rules.NATION_POPULATION_ANNUAL_GROWTH.id,
    )
    nation_gdp = _required_projection_number(indexed, nation, "GDP", source="save-field", rule_id=Rules.NATION_IP_ECONOMY_SCORE.id)
    pcgdp = nation_gdp / (total_population * 1_000_000.0) if total_population else 0.0
    space_defenses = 0
    sto_fighters = 0
    raw_region_refs = _required_projection_list(indexed, nation, "regions", source="save-field", rule_id=Rules.NATION_POPULATION_MONTHLY_GROWTH.id)
    capital_id = ref_id(nation.get("capital"))
    for region_order, region_ref in enumerate(raw_region_refs):
        region_id = ref_id(region_ref)
        region = state_value_by_id(indexed, region_id)
        if region_id is None or not isinstance(region, dict):
            raise _projection_dependency_error(
                indexed,
                source="save-reference",
                field="nation.regions",
                rule_id=Rules.NATION_POPULATION_MONTHLY_GROWTH.id,
                reason="target nation contains an unresolved region reference",
            )
        template_name = str(region.get("templateName") or "")
        template = _required_projection_catalog_row(
            indexed, region_templates, template_name,
            collection="regionTemplates", rule_id=Rules.NATION_POPULATION_ANNUAL_GROWTH.id,
        )
        map_name = str(template.get("mapRegionName") or "")
        map_template = _required_projection_catalog_row(
            indexed, map_templates, map_name,
            collection="mapRegionTemplates", rule_id=Rules.NATION_POPULATION_ANNUAL_GROWTH.id,
        )
        xeno = state_value_by_id(indexed, ref_id(region.get("xenoforming")))
        if not isinstance(xeno, dict):
            raise _projection_dependency_error(
                indexed,
                source="save-reference",
                field=f"region.{region_id}.xenoforming",
                rule_id=Rules.NATION_POPULATION_ANNUAL_GROWTH.id,
                reason="required xenoforming state reference cannot be resolved",
            )
        occupation_fraction = _region_occupation_fraction(region, indexed, nation, nation_id)
        if not math.isfinite(occupation_fraction):
            raise _projection_dependency_error(
                indexed,
                source="save-field",
                field=f"region.{region_id}.occupations/currentWarStates/enemyAlliance",
                rule_id=Rules.NATION_IP_BASE.id,
                reason="occupation input or required war-alliance references are unavailable or invalid",
            )
        colony = _required_projection_bool(indexed, region, "colonyRegion", source="save-field", rule_id=Rules.NATION_PRIORITY_WELFARE_COLONY_TRIGGER.id)
        permanent_colony = _required_projection_bool(indexed, region, "permanentlyDecolonized", source="save-field", rule_id=Rules.NATION_PRIORITY_WELFARE_DECOLONIZATION.id)
        resource_region = _required_projection_bool(indexed, region, "resourceRegion", source="save-field", rule_id=Rules.NATION_PRIORITY_WELFARE_DECOLONIZATION_DOWNSTREAM.id)
        oil_region = _required_projection_bool(indexed, region, "oilRegion", source="save-field", rule_id=Rules.NATION_PRIORITY_WELFARE_DECOLONIZATION_DOWNSTREAM.id)
        core_region = _required_projection_bool(indexed, region, "coreEconomicRegion", source="save-field", rule_id=Rules.NATION_PRIORITY_BUILD_ARMY_PLACEMENT.id)
        latitude_field = f"mapRegionTemplates.{map_name}.latitude"
        longitude_field = f"mapRegionTemplates.{map_name}.longitude"
        environment_field = f"regionTemplates.{template_name}.environment"
        latitude = _required_projection_number(
            indexed,
            {latitude_field: map_template.get("latitude")},
            latitude_field,
            source="catalog-field",
            rule_id=Rules.NATION_POPULATION_ANNUAL_GROWTH.id,
        )
        longitude = _required_projection_number(
            indexed,
            {longitude_field: map_template.get("longitude")},
            longitude_field,
            source="catalog-field",
            rule_id=Rules.NATION_POPULATION_ANNUAL_GROWTH.id,
        )
        environment = _required_projection_string(
            indexed,
            {environment_field: template.get("environment")},
            environment_field,
            source="catalog-field",
            rule_id=Rules.NATION_POPULATION_ANNUAL_GROWTH.id,
        )
        region_map_names[region_id] = map_name
        regions[region_id] = nation_projection_layer.RegionProjectionState(
            id=region_id,
            population_millions=_required_projection_number(indexed, region, "populationInMillions", source="save-field", rule_id=Rules.NATION_POPULATION_MONTHLY_GROWTH.id),
            boost_per_year=_required_projection_number(indexed, region, "boostPerYear_dekatons", source="save-field", rule_id=Rules.NATION_FACTION_CONTRIBUTION.id),
            mission_control=int(_required_projection_number(indexed, region, "missionControl", source="save-field", rule_id=Rules.NATION_PRIORITY_MISSION_CONTROL_PLACEMENT.id)),
            ocean_type=_required_projection_ocean_type(indexed, region, "oceanType", source="save-field", rule_id=Rules.NATION_PRIORITY_VALIDITY.id),
            annual_population_growth=None,
            per_capita_gdp=pcgdp,
            gdp=None,
            region_order=region_order,
            template_name=template_name,
            latitude=latitude,
            longitude=longitude,
            annual_population_growth_modifier=_required_projection_number(indexed, region, "annualPopGrowthModifier", source="save-field", rule_id=Rules.NATION_POPULATION_ANNUAL_GROWTH.id),
            environment=environment,
            xenoforming_level=_required_projection_number(indexed, xeno, "xenoformingLevel", source="save-field", rule_id=Rules.NATION_POPULATION_ANNUAL_GROWTH.id),
            nuclear_detonations=int(_required_projection_number(indexed, region, "nuclearDetonations", source="save-field", rule_id=Rules.NATION_POPULATION_ANNUAL_GROWTH.id)),
            colony=colony,
            permanent_colony=permanent_colony,
            resource_region=resource_region,
            oil_region=oil_region,
            core_economic_region=core_region,
            mine_capable=bool(template.get("mineCapable")),
            oil_capable=bool(template.get("oilCapable")),
            capital=region_id == capital_id,
            occupation_fraction=occupation_fraction,
            fully_occupied=ref_id(region.get("leadOccupier")) is not None,
            mission_control_cap=None,
            welfare_colony_counter=int(_required_projection_number(indexed, region, "accumulatedDecolonizeTriggers", source="save-field", rule_id=Rules.NATION_PRIORITY_WELFARE_COLONY_TRIGGER.id)),
            anti_space_defenses=region.get("antiSpaceDefenses") if isinstance(region.get("antiSpaceDefenses"), bool) else None,
            num_sto_fighters=int(region["numSTOFighters"]) if isinstance(region.get("numSTOFighters"), int) and not isinstance(region.get("numSTOFighters"), bool) else None,
            economy_region_counters={
                key: int(_required_projection_number(
                    indexed,
                    region,
                    field,
                    source="save-field",
                    rule_id=Rules.NATION_PRIORITY_ECONOMY_MARKET.id,
                ))
                for key, field in (
                    ("coreEconomic", "accumulatedCoreEconomyRegionTriggers"),
                    ("mining", "accumulatedCoreMiningRegionTriggers"),
                    ("oil", "accumulatedCoreOilRegionTriggers"),
                )
            },
        )
        defense = state_value_by_id(indexed, ref_id(region.get("spaceDefenseFacility"))) or {}
        space_defenses += 1 if defense.get("weaponTemplateName") else 0
        sto_fighters += int(as_float(region.get("numSTOFighters"), 0.0))
    map_to_region = {map_name: region_id for region_id, map_name in region_map_names.items()}
    adjacency: dict[int, set[int]] = {region_id: set() for region_id in regions}
    for row in bilateral_templates.values():
        if not isinstance(row, dict) or row.get("relationType") != "PhysicalAdjacency":
            continue
        left = map_to_region.get(str(row.get("region1") or ""))
        right = map_to_region.get(str(row.get("region2") or ""))
        if left is not None and right is not None:
            adjacency[left].add(right)
            adjacency[right].add(left)
    for region_id, adjacent_ids in adjacency.items():
        regions[region_id].adjacent_region_ids = tuple(sorted(adjacent_ids, key=lambda value: regions[value].region_order))

    armies: list[nation_projection_layer.ArmyProjectionState] = []
    navy_count = 0
    for army_ref in _required_projection_list(indexed, nation, "armies", source="save-field", rule_id=Rules.NATION_ASSET_ARMY_MAINTENANCE.id):
        army_id = ref_id(army_ref)
        army = state_value_by_id(indexed, army_id)
        if army_id is None or not isinstance(army, dict):
            raise _projection_dependency_error(indexed, source="save-reference", field="nation.armies", rule_id=Rules.NATION_ASSET_ARMY_MAINTENANCE.id, reason="army reference cannot be resolved")
        deployment = _required_projection_deployment_type(
            indexed, army, "deploymentType", source="save-field",
            rule_id=Rules.NATION_PRIORITY_BUILD_NAVY_COMPLETE.id,
        )
        if deployment == "Naval" and not army.get("destroyed"):
            navy_count += 1
        armies.append(nation_projection_layer.ArmyProjectionState(
            id=army_id,
            strength=_required_projection_number(indexed, army, "strength", source="save-field", rule_id=Rules.NATION_ASSET_ARMY_MAINTENANCE.id),
            deployment_type=deployment,
            home_region_id=int(ref_id(army.get("homeRegion")) or -1),
            current_region_id=int(ref_id(army.get("currentRegion")) or -1),
            control_point_position=int(_required_projection_number(indexed, army, "controlPointIdx", source="save-field", rule_id=Rules.NATION_PRIORITY_BUILD_ARMY_PLACEMENT.id)),
            faction_id=ref_id(army.get("faction")),
            army_type=_required_projection_army_type(indexed, army, "armyType", source="save-field", rule_id=Rules.NATION_PRIORITY_BUILD_NAVY_COMPLETE.id),
            operations=float(len(army.get("currentOperations") or [])),
            destroyed=bool(army.get("destroyed")),
        ))
    advising_councilor_refs = _required_projection_list(
        indexed,
        nation,
        "advisingCouncilors",
        source="save-field",
        rule_id=Rules.NATION_ADVISOR_MISSION_LIFECYCLE.id,
    )
    current_advisors = tuple(
        all_advisors[councilor_id]
        for councilor_id in (ref_id(value) for value in advising_councilor_refs)
        if councilor_id in all_advisors
    )
    current_phase_assignments: list[nation_projection_layer.AdvisorProfile] = []
    repeating_advisors: list[nation_projection_layer.AdvisorProfile] = []
    prepaid_ids: set[int] = set()
    current_ids = {profile.councilor_id for profile in current_advisors if profile.councilor_id is not None}
    for entry in type_entries(indexed, "TICouncilorState"):
        councilor = entry.get("Value") or {}
        councilor_id = raw_state_id(entry)
        if councilor_id is None or councilor_id not in all_advisors:
            continue
        mission = state_value_by_id(indexed, ref_id(councilor.get("activeMission")))
        assigned_here = (
            isinstance(mission, dict)
            and mission.get("templateName") == "Advise"
            and ref_id(mission.get("target")) == nation_id
        )
        if assigned_here:
            current_phase_assignments.append(all_advisors[councilor_id])
            prepaid_ids.add(councilor_id)
        if (assigned_here or councilor_id in current_ids) and (
            councilor.get("repeatOrder") is True or councilor.get("permanentAssignment") is True
        ):
            repeating_advisors.append(all_advisors[councilor_id])
    advisor_policy = tuple(dict.fromkeys(repeating_advisors))
    phase_assignments = tuple(dict.fromkeys(current_phase_assignments))
    economy_score = _required_projection_number(indexed, nation, "economyScore", source="save-field", rule_id=Rules.NATION_IP_ECONOMY_SCORE.id)
    gdp_modifiers = {
        name: _required_projection_number(
            indexed,
            {
                f"globalConfig.{name}.value": (
                    global_config.get(name, {}).get("value")
                    if isinstance(global_config.get(name), dict)
                    else None
                )
            },
            f"globalConfig.{name}.value",
            source="catalog-field",
            rule_id=Rules.NATION_IP_BASE.id,
        )
        for name in (
            "coreEcoRegionGDPModifier",
            "coreResourceRegionGDPModifier",
            "colonyRegionGDPModifier",
        )
    }
    weights: dict[int, float] = {}
    for region in regions.values():
        weight = region.population_millions
        if region.core_economic_region:
            weight *= gdp_modifiers["coreEcoRegionGDPModifier"]
        if region.resource_region or region.oil_region:
            weight *= gdp_modifiers["coreResourceRegionGDPModifier"]
        if region.colony:
            weight *= gdp_modifiers["colonyRegionGDPModifier"]
        weights[region.id] = weight
    total_weight = sum(weights.values())
    occupation_penalty = sum((weights[region.id] / total_weight) * float(region.occupation_fraction or 0.0) for region in regions.values()) if total_weight else 0.0
    occupation_factor = min(max(1.0 - occupation_penalty, 0.0), 1.0)
    progress = _required_projection_mapping(
        indexed,
        nation,
        "_accumulatedInvestmentPoints",
        source="save-field",
        rule_id=Rules.NATION_PRIORITY_COMPLETION_ORDER.id,
    )
    global_state = first_value(indexed, "TIGlobalValuesState") or {}
    temperature = temperature_anomaly_components(global_state)
    hostile_claim_refs = _required_projection_list(
        indexed,
        nation,
        "hostileClaims",
        source="save-field",
        rule_id=Rules.NATION_PRIORITY_GOVERNMENT_LEGITIMIZE.id,
    )
    hostile_ids = set()
    for reference in hostile_claim_refs:
        region_id = ref_id(reference)
        resolved_claim = resolve_ref(indexed, reference)
        if region_id is None or resolved_claim is None or resolved_claim[1] != "TIRegionState":
            raise _projection_dependency_error(indexed, source="save-reference", field="nation.hostileClaims",
                                               rule_id=Rules.NATION_PRIORITY_GOVERNMENT_LEGITIMIZE.id,
                                               reason="hostile claim must resolve to a region state")
        if region_id in regions:
            hostile_ids.add(region_id)
    if not control_points:
        raise _projection_dependency_error(
            indexed,
            source="save-reference",
            field="nation.controlPoints",
            rule_id=Rules.NATION_PERIODIC_CONTROL_POINTS.id,
            reason="target nation has no resolvable control point; the executive faction cannot be determined",
        )
    executive_cp = max(control_points.values(), key=lambda value: value.position)
    raw_public_opinion = nation.get("publicOpinion")
    public_opinion = {
        str(key): float(value)
        for key, value in raw_public_opinion.items()
        if isinstance(raw_public_opinion, dict)
        and isinstance(value, (int, float))
        and not isinstance(value, bool)
    } if isinstance(raw_public_opinion, dict) else {}
    raw_market = global_state.get("resourceMarketValues")
    market_values = {
        name: float(raw_market[name])
        for name in ("Metals", "NobleMetals")
        if isinstance(raw_market, dict)
        and isinstance(raw_market.get(name), (int, float))
        and not isinstance(raw_market.get(name), bool)
    }
    market_blockers = set()
    if set(market_values) != {"Metals", "NobleMetals"}:
        market_blockers.add(Rules.NATION_PRIORITY_ECONOMY_MARKET.id)
    state = nation_projection_layer.NationProjectionState(
        nation_id=nation_id, at=start, gdp=nation_gdp,
        inequality=_required_projection_number(indexed, nation, "inequality", source="save-field", rule_id=Rules.NATION_PRIORITY_WELFARE_INEQUALITY.id),
        education=_required_projection_number(indexed, nation, "education", source="save-field", rule_id=Rules.NATION_PRIORITY_KNOWLEDGE_COMPLETE.id),
        democracy=_required_projection_number(indexed, nation, "democracy", source="save-field", rule_id=Rules.NATION_PRIORITY_GOVERNMENT_COMPLETE.id),
        cohesion=_required_projection_number(indexed, nation, "cohesion", source="save-field", rule_id=Rules.NATION_PERIODIC_COHESION.id),
        cohesion_rest=_required_projection_number(indexed, nation, "cohesionRestState_dailyCache", source="save-field", rule_id=Rules.NATION_PERIODIC_DERIVED_CACHE.id),
        unrest=_required_projection_number(indexed, nation, "unrest", source="save-field", rule_id=Rules.NATION_PERIODIC_UNREST.id),
        unrest_rest=_required_projection_number(indexed, nation, "unrestRestState_dailyCache", source="save-field", rule_id=Rules.NATION_PERIODIC_DERIVED_CACHE.id),
        sustainability=_required_projection_number(indexed, nation, "sustainability", source="save-field", rule_id=Rules.NATION_PRIORITY_VALIDITY.id),
        military_tech=_required_projection_number(indexed, nation, "militaryTechLevel", source="save-field", rule_id=Rules.NATION_PRIORITY_VALIDITY.id),
        funding_year=_required_projection_number(indexed, nation, "spaceFunding_year", source="save-field", rule_id=Rules.NATION_PRIORITY_FUNDING_COMPLETE.id), economy_score=economy_score,
        occupation_factor=occupation_factor, army_maintenance=0.0,
        progress={str(key): as_float(value, 0.0) for key, value in progress.items()}, regions=regions,
        control_points=control_points, advisors=current_advisors, mission_control=nation_current_mission_control(indexed, nation),
        army_count=len([army for army in armies if not army.destroyed and army.deployment_type != "Naval"]), navy_count=navy_count, nuclear_weapons=int(as_float(nation.get("numNuclearWeapons"), 0.0)),
        space_defenses=space_defenses, sto_fighters=sto_fighters,
        days_in_campaign=_required_projection_number(indexed, time_state, "daysInCampaign", source="save-field", rule_id=Rules.NATION_POPULATION_ANNUAL_GROWTH.id),
        current_quarter=int(_required_projection_number(indexed, time_state, "currentQuarterSinceStart", source="save-field", rule_id=Rules.NATION_PERIODIC_DERIVED_CACHE.id)),
        pcgdp_tracker=_serialized_numeric_tracker(indexed, nation.get("tracker_PCGDP_ByQuarter"), field="tracker_PCGDP_ByQuarter", rule_id=Rules.NATION_PERIODIC_DERIVED_CACHE.id),
        military=_required_projection_bool(indexed, nation, "military", source="save-field", rule_id=Rules.NATION_PRIORITY_VALIDITY.id),
        space_flight_program=_required_projection_bool(indexed, nation, "spaceFlightProgram", source="save-field", rule_id=Rules.NATION_PRIORITY_VALIDITY.id),
        federation_space_program=federation_space_program(indexed, nation),
        nuclear_program=_required_projection_bool(indexed, nation, "nuclearProgram", source="save-field", rule_id=Rules.NATION_PRIORITY_VALIDITY.id),
        can_build_space_defenses=_required_projection_bool(indexed, nation, "canBuildSpaceDefenses", source="save-field", rule_id=Rules.NATION_PRIORITY_VALIDITY.id),
        can_build_sto=_required_projection_bool(indexed, nation, "canBuildSTOSquadrons", source="save-field", rule_id=Rules.NATION_PRIORITY_VALIDITY.id),
        num_control_points_unclamped=int(_required_projection_number(indexed, nation, "numControlPoints_unclamped", source="save-field", rule_id=Rules.NATION_PERIODIC_CONTROL_POINTS.id)),
        legitimize_counter=as_float(nation.get("accumulatedLegitimizeClaimTriggers"), 0.0),
        hostile_region_ids=hostile_ids,
        hostile_region_ids_complete=True,
        executive_faction_id=executive_cp.owner_faction_id,
        public_opinion=public_opinion,
        armies=armies,
        world_context={
            "earthAtmosphericCO2_ppm": _required_projection_number(indexed, global_state, "earthAtmosphericCO2_ppm", source="save-field", rule_id=Rules.NATION_POPULATION_ANNUAL_GROWTH.id),
            "earthAtmosphericCH4_ppm": _required_projection_number(indexed, global_state, "earthAtmosphericCH4_ppm", source="save-field", rule_id=Rules.NATION_POPULATION_ANNUAL_GROWTH.id),
            "earthAtmosphericN2O_ppm": _required_projection_number(indexed, global_state, "earthAtmosphericN2O_ppm", source="save-field", rule_id=Rules.NATION_POPULATION_ANNUAL_GROWTH.id),
            "stratosphericAerosols_ppm": _required_projection_number(indexed, global_state, "stratosphericAerosols_ppm", source="save-field", rule_id=Rules.NATION_POPULATION_ANNUAL_GROWTH.id),
            "temperatureAnomaly_C": temperature["total"],
            "pcgdpToReduceUnrestBy1": _required_projection_number(indexed, global_state, "fixedPCGDPToReduceUnrestBy1", source="save-field", rule_id=Rules.NATION_PERIODIC_DERIVED_CACHE.id),
            "resourceMarketValues": market_values,
            "endOfOil": global_state.get("endOfOil") if isinstance(global_state.get("endOfOil"), bool) else None,
        },
        federation_economy_bonus=as_float(nation.get("restofFederationECOBonus_dailyCache"), 0.0),
        cached_num_mining_regions=int(as_float(nation.get("numMiningRegions_dailyCache"), 0.0)),
        cached_num_oil_regions=int(as_float(nation.get("numOilRegions_dailyCache"), 0.0)),
        cached_num_core_economic_regions=int(as_float(nation.get("numCoreEconomicRegions_dailyCache"), 0.0)),
        cached_can_accumulate_core_economy=bool(nation.get("canAccumulateCoreEconomyTriggers")),
        cached_can_accumulate_core_mining=bool(nation.get("canAccumulateCoreMiningTriggers")),
        cached_can_accumulate_core_oil=bool(nation.get("canAccumulateCoreOilTriggers")),
        policy_no_oil_development=bool(nation.get("policy_noOilDevelopment")),
        policy_no_mineral_development=bool(nation.get("policy_noMineralDevelopment")),
        world_market_blockers=market_blockers,
        advisor_policy=advisor_policy,
        advisor_mission_schedule=advisor_schedule,
        advisor_current_phase_assignments=phase_assignments,
        advisor_assignment_prepaid_ids=frozenset(prepaid_ids),
    )
    state.rest_state_context = _extract_projection_rest_inputs(indexed, nation, state, development)
    state.cached_can_accumulate_legitimize = nation.get("canAccumulateLegitimizeClaimTriggers") if isinstance(nation.get("canAccumulateLegitimizeClaimTriggers"), bool) else None
    state.cached_can_accumulate_decontaminate = nation.get("canAccumulateDecontaminateTriggers") if isinstance(nation.get("canAccumulateDecontaminateTriggers"), bool) else None
    state.max_military_tech_level = float(nation["maxMilitaryTechLevel"]) if isinstance(nation.get("maxMilitaryTechLevel"), (int, float)) and not isinstance(nation.get("maxMilitaryTechLevel"), bool) and math.isfinite(nation["maxMilitaryTechLevel"]) else None
    state.policy_no_nukes = nation.get("policy_noNukes") if isinstance(nation.get("policy_noNukes"), bool) else None
    return state


def calculate_nation_projection(
    indexed: IndexedState,
    nation_name: str,
    faction_name: str | None,
    plan_payload: Any,
    *,
    days: int,
    checkpoints: list[int],
    details: bool,
    diagnostics: bool,
) -> dict[str, Any]:
    found = match_raw_state(indexed, "TINationState", nation_name)
    if not found or found[0] is None:
        raise UserInputError(f"Nation not found: {nation_name}")
    nation_id, nation = found
    faction_id, faction = find_faction_state(indexed, faction_name)
    catalogs = calculation_catalogs(indexed, "nation-projection")
    development = catalogs.nation_development
    priorities = development.get("priorities") if isinstance(development.get("priorities"), dict) else {}
    global_config = development.get("globalConfig") if isinstance(development.get("globalConfig"), dict) else {}
    _, councilor_by_id = councilor_summary_maps(indexed, catalogs.traits)
    all_advisors, available_advisors = projection_advisor_profiles(indexed, faction_id, faction, councilor_by_id)
    owner_bonuses: dict[int, dict[str, float]] = {}
    owner_bonus_bases: dict[int, dict[str, float]] = {}
    for cp in nation_control_points(indexed, nation):
        owner_id = ref_id(cp.get("faction"))
        owner = state_value_by_id(indexed, owner_id)
        if owner_id is not None and isinstance(owner, dict) and owner_id not in owner_bonuses:
            owner_bonuses[owner_id], owner_bonus_bases[owner_id] = faction_priority_bonuses_for_projection(
                indexed,
                owner_id,
                owner,
                priorities,
                catalogs.traits,
                catalogs.effects,
            )
    advisor_schedule = projection_advisor_mission_schedule(indexed, development)
    state = extract_nation_projection_state(
        indexed,
        nation_id,
        nation,
        all_advisors,
        owner_bonuses,
        development,
        advisor_schedule,
    )
    plans, goals = nation_projection_layer.parse_projection_document(plan_payload, state=state, councilors=available_advisors, priorities=priorities)
    contexts = faction_effect_contexts(indexed, faction_id)
    research_factor = apply_effect_modifiers(contexts, catalogs.effects, "ControlPointResearch", 1.0)
    faction_priority_modifiers: dict[int, dict[str, float]] = {}
    welfare_config = global_config.get("welfarePriorityInequalityChange")
    welfare_base = _required_projection_number(
        indexed,
        {
            "globalConfig.welfarePriorityInequalityChange.value": (
                welfare_config.get("value")
                if isinstance(welfare_config, dict)
                else None
            ),
        },
        "globalConfig.welfarePriorityInequalityChange.value",
        source="catalog-field",
        rule_id=Rules.NATION_PRIORITY_WELFARE_INEQUALITY.id,
    )
    for owner_id in owner_bonuses:
        owner_contexts = faction_effect_contexts(indexed, owner_id)
        faction_priority_modifiers[owner_id] = {
            "WelfareInequalityReductionBonus": apply_effect_modifiers(
                owner_contexts,
                catalogs.effects,
                "WelfareInequalityReductionBonus",
                welfare_base,
            ) - welfare_base,
        }
    faction_templates = development.get("factionTemplates") if isinstance(development.get("factionTemplates"), dict) else {}
    ideology_templates = development.get("ideologyTemplates") if isinstance(development.get("ideologyTemplates"), dict) else {}
    faction_ideologies: dict[int, str] = {}
    active_human: list[tuple[int, int, str]] = []
    alien_faction_id: int | None = None
    proxy_candidates: list[tuple[int, int]] = []
    all_faction_contexts: dict[int, dict[str, tuple[str, ...]]] = {}
    for entry in type_entries(indexed, "TIFactionState"):
        value = entry.get("Value") or {}
        owner_id = raw_state_id(entry)
        template_name = str(value.get("templateName") or "")
        faction_template = faction_templates.get(template_name)
        if owner_id is None or not isinstance(faction_template, dict):
            continue
        ideology_name = str(faction_template.get("ideologyName") or "")
        ideology_template = ideology_templates.get(ideology_name)
        if not isinstance(ideology_template, dict):
            continue
        ideology = str(ideology_template.get("ideology") or "")
        if not ideology:
            continue
        faction_ideologies[owner_id] = ideology
        all_faction_contexts[owner_id] = {
            str(name): tuple(str(effect) for effect in effects)
            for name, effects in faction_effect_contexts(indexed, owner_id).items()
        }
        if faction_template.get("isAlien") is True or ideology_template.get("alien") is True:
            alien_faction_id = owner_id
        else:
            active_human.append((int(ideology_template.get("sortOrder") or 0), owner_id, ideology_name))
            will_proxy = ideology_template.get("willProxy")
            if isinstance(will_proxy, int) and will_proxy > 0:
                proxy_candidates.append((will_proxy, owner_id))
    permanent_allies = {owner_id: (owner_id,) for owner_id in faction_ideologies}
    if alien_faction_id is not None and proxy_candidates:
        proxy_id = min(proxy_candidates)[1]
        permanent_allies[alien_faction_id] = tuple(dict.fromkeys((*permanent_allies[alien_faction_id], proxy_id)))
        permanent_allies[proxy_id] = tuple(dict.fromkeys((*permanent_allies[proxy_id], alien_faction_id)))
    state.public_opinion_context = {
        "activeHumanIdeologyNames": [name for _sort, _owner, name in sorted(active_human)],
        "alienFactionId": alien_faction_id,
        "alienProxyFactionId": min(proxy_candidates)[1] if proxy_candidates else None,
    }
    state.faction_effect_contexts = {
        owner_id: {name: list(effects) for name, effects in contexts.items()}
        for owner_id, contexts in all_faction_contexts.items()
    }
    state.faction_effect_expirations = faction_effect_expirations_for_projection(indexed)
    state.faction_priority_bonus_cache = {
        owner_id: dict(bonuses) for owner_id, bonuses in owner_bonuses.items()
    }
    nation_template_name = str(nation.get("templateName") or "")
    start_template_name = str((first_value(indexed, "TITimeState") or {}).get("templateName") or "")
    nation_template = _required_projection_catalog_row(
        indexed,
        development.get("nationTemplates"),
        nation_template_name,
        collection="nationTemplates",
        rule_id=Rules.NATION_POPULATION_ANNUAL_GROWTH.id,
    )
    start_template = _required_projection_catalog_row(
        indexed,
        development.get("startTimeTemplates"),
        start_template_name,
        collection="startTimeTemplates",
        rule_id=Rules.NATION_POPULATION_ANNUAL_GROWTH.id,
    )
    context = nation_projection_layer.ProjectionContext(
        faction_id=faction_id, priorities=priorities, global_config=global_config,
        diversity_bonuses=development.get("diversityBonuses") or {}, national_ip_multiplier=national_ip_multiplier(indexed),
        initial_funding_pool_year=nation_federation_pooled_year(indexed, nation, "Money"),
        initial_own_funding_year=as_float(nation.get("spaceFunding_year"), 0.0),
        initial_boost_pool_year=nation_federation_pooled_year(indexed, nation, "Boost"),
        knowledge_sector_owned=income_layer.nation_has_owned_knowledge_sector(indexed, nation, faction_id),
        financial_sector_owned=income_layer.nation_financial_sector_owned(indexed, nation, faction_id),
        knowledge_sector_bonus=INCOME_CONFIG.knowledge_sector_research_bonus,
        financial_sector_bonus=INCOME_CONFIG.financial_sector_funding_bonus,
        research_effect_factor=research_factor,
        nation_template=nation_template,
        region_templates=development.get("regionTemplates") or {},
        start_template=start_template,
        faction_priority_modifiers=faction_priority_modifiers,
        faction_ideologies=faction_ideologies,
        ideology_templates=ideology_templates,
        permanent_allies=permanent_allies,
        faction_effect_contexts=all_faction_contexts,
        effect_templates=catalogs.effects,
        faction_priority_bonus_bases=owner_bonus_bases,
    )
    nation_projection_layer.calibrate_rest_state_context(
        state,
        context,
        pcgdp_to_reduce_unrest_by_one=state.world_context["pcgdpToReduceUnrestBy1"],
    )
    topbar = calculate_topbar(indexed, None, faction_name, include_details=False)
    observed = {
        "researchMonthly": ((topbar.get("resources") or {}).get("Research") or {}).get("monthly"),
        "fundingMonthly": ((topbar.get("resources") or {}).get("Money") or {}).get("monthly"),
        "boostMonthly": ((topbar.get("resources") or {}).get("Boost") or {}).get("monthly"),
        "missionControlCapacity": ((topbar.get("resources") or {}).get("MissionControl") or {}).get("capacity"),
    }
    faction_context = {
        "id": faction_id, "template": faction.get("templateName"), "display": faction.get("displayName"),
        "observedTotalAtStart": observed,
        "scope": "observed whole-faction context only; excluded from conditions, comparison and future projection",
    }
    source_notes = [
        "Runtime mechanics use packaged, hash-verified catalog data; raw templates and DLL are generator/audit inputs only.",
        "factionContribution.* is only the selected faction's contribution from the target nation.",
        "Advise uses the saved mission-phase cadence, automatic success, assignment movement, and expected order-0 resolution timing; renewal Influence is reported separately.",
        "Existing save-to-save comparisons are observational unless produced by a controlled no-action validation run.",
        "Climate and external resting-state inputs are held fixed at the save snapshot; population jitter uses deterministic mean input.",
    ]
    return nation_projection_layer.projection_output(
        state, plans, context, days=days, checkpoints=checkpoints, goals=goals, details=details,
        diagnostics=diagnostics, faction_context=faction_context, source_notes=source_notes,
    )
