"""Org-plan helpers for the Terra Invicta save parser."""

from __future__ import annotations

from itertools import combinations
from pathlib import Path
from types import MappingProxyType
from typing import Any, Iterable

import ti_parser_snapshot as snapshot_layer
from ti_parser_core import (
    IndexedState,
    as_float,
    clean_numbers,
    find_faction_state,
    load_named_templates,
    load_trait_templates,
    ref_id,
    resolve_ref,
    state_value_by_id,
    type_entries,
)
from ti_parser_snapshot import SnapshotConfig


FACTION_IDEOLOGY_BY_TEMPLATE = MappingProxyType(
    {
        "ResistCouncil": "Resist",
        "DestroyCouncil": "Destroy",
        "ExploitCouncil": "Exploit",
        "SubmitCouncil": "Submit",
        "AppeaseCouncil": "Appease",
        "CooperateCouncil": "Cooperate",
        "EscapeCouncil": "Escape",
        "AlienCouncil": "Alien",
    }
)

DEFAULT_MAX_COUNCILOR_ATTRIBUTE = 25
COUNCILOR_ATTRIBUTES = (
    "Persuasion",
    "Investigation",
    "Espionage",
    "Command",
    "Administration",
    "Science",
    "Security",
    "Loyalty",
    "ApparentLoyalty",
)
ORG_ATTRIBUTE_FIELDS = {
    "Persuasion": "persuasion",
    "Investigation": "investigation",
    "Espionage": "espionage",
    "Command": "command",
    "Administration": "administration",
    "Science": "science",
    "Security": "security",
}
ORG_PLAN_SCORE_ATTRIBUTES = tuple(ORG_ATTRIBUTE_FIELDS)
ORG_PLAN_FOCUS_CHOICES = ("balanced", *(attribute.casefold() for attribute in ORG_PLAN_SCORE_ATTRIBUTES))
ORG_PLAN_COST_FIELDS = {
    "Money": "costMoney",
    "Influence": "costInfluence",
    "Operations": "costOps",
    "Boost": "costBoost",
}
NATION_CONDITION_FIELDS = {
    "TINationCondition_fCohesion": "cohesion",
    "TINationCondition_fDemocracy": "democracy",
    "TINationCondition_fEducation": "education",
    "TINationCondition_fInequality": "inequality",
    "TINationCondition_fUnrest": "unrest",
}

FACTION_RESOURCES = (
    "Money",
    "Influence",
    "Operations",
    "Research",
    "Projects",
    "Boost",
    "MissionControl",
    "Water",
    "Volatiles",
    "Metals",
    "NobleMetals",
    "Fissiles",
    "Antimatter",
    "Exotics",
)
ORG_SNAPSHOT_CONFIG = SnapshotConfig(
    schema_version=4,
    default_max_councilor_attribute=DEFAULT_MAX_COUNCILOR_ATTRIBUTE,
    councilor_attributes=COUNCILOR_ATTRIBUTES,
    faction_resources=FACTION_RESOURCES,
    org_attribute_fields=tuple(ORG_ATTRIBUTE_FIELDS.items()),
)

parse_modifier_number = snapshot_layer.parse_modifier_number


def sum_attr_mods(mods: list[dict[str, Any]]) -> dict[str, int]:
    return snapshot_layer.sum_attr_mods(mods, ORG_SNAPSHOT_CONFIG)


def clamp_attribute(value: int, max_value: int = DEFAULT_MAX_COUNCILOR_ATTRIBUTE) -> int:
    return snapshot_layer.clamp_attribute(value, max_value)


def councilor_attribute_breakdown(
    indexed: IndexedState,
    councilor: dict[str, Any],
    trait_templates: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    return snapshot_layer.councilor_attribute_breakdown(indexed, councilor, trait_templates, ORG_SNAPSHOT_CONFIG)


def match_named(items: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    needle = name.casefold()
    exact_fields = ("template", "code", "display")
    for item in items:
        for field in exact_fields:
            value = item.get(field)
            if isinstance(value, str) and value.casefold() == needle:
                return item
    for item in items:
        for field in exact_fields:
            value = item.get(field)
            if isinstance(value, str) and needle in value.casefold():
                return item
    return None


def parse_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().casefold()
        if normalized in {"true", "1", "yes"}:
            return True
        if normalized in {"false", "0", "no"}:
            return False
    return None


def compare_condition(sign: str | None, actual: Any, expected: Any) -> bool | None:
    if actual is None or expected is None:
        return None
    sign = sign or "EqualTo"
    if sign == "EqualTo":
        return actual == expected
    if sign == "NotEqualTo":
        return actual != expected
    if isinstance(actual, bool) or isinstance(expected, bool):
        return None
    if sign == "GreaterThan":
        return actual > expected
    if sign == "GreaterThanOrEqualTo":
        return actual >= expected
    if sign == "LessThan":
        return actual < expected
    if sign == "LessThanOrEqualTo":
        return actual <= expected
    return None


def faction_ideology_key(faction: dict[str, Any]) -> str | None:
    template = faction.get("templateName")
    if isinstance(template, str):
        if template in FACTION_IDEOLOGY_BY_TEMPLATE:
            return FACTION_IDEOLOGY_BY_TEMPLATE[template]
        if template.endswith("Council"):
            return template.removesuffix("Council")
    return None


def faction_brief(faction_id: int | None, faction: dict[str, Any] | None) -> dict[str, Any] | None:
    if not faction:
        return None
    return {
        "id": faction_id,
        "template": faction.get("templateName"),
        "display": faction.get("displayName"),
        "ideology": faction_ideology_key(faction),
    }


def faction_councilor_ids(faction: dict[str, Any]) -> list[int]:
    refs = faction.get("councilors") if isinstance(faction.get("councilors"), list) else []
    return [state_id for state_id in (ref_id(item) for item in refs) if state_id is not None]


def find_faction_for_councilor(snapshot: dict[str, Any], councilor: dict[str, Any]) -> dict[str, Any] | None:
    faction_name = councilor.get("faction") or councilor.get("factionDisplay")
    if not isinstance(faction_name, str):
        return None
    return match_named(snapshot.get("factions", []), faction_name)


def condition_eval_unknown(reason: str) -> dict[str, Any]:
    return {
        "conditionResult": None,
        "conditionActual": None,
        "conditionExpected": None,
        "conditionField": None,
        "conditionEvalNote": reason,
    }


def condition_nation_summary(nation: dict[str, Any] | None) -> dict[str, Any] | None:
    if nation is None:
        return None
    keys = ("id", "template", "code", "display", "unrest", "cohesion", "democracy", "education", "inequality")
    return {key: nation.get(key) for key in keys if key in nation}


def evaluate_condition(
    mod: dict[str, Any],
    councilor: dict[str, Any],
    snapshot: dict[str, Any],
    context_nation: dict[str, Any] | None,
) -> dict[str, Any]:
    condition = mod.get("condition") if isinstance(mod.get("condition"), dict) else {}
    condition_type = mod.get("conditionType") or condition.get("$type")
    sign = condition.get("sign")

    if condition_type in NATION_CONDITION_FIELDS:
        if context_nation is None:
            return condition_eval_unknown("nation-scoped condition needs --target-nation or --current-location-context")
        field = NATION_CONDITION_FIELDS[condition_type]
        actual = context_nation.get(field)
        expected = parse_modifier_number(condition.get("strValue"))
        return {
            "conditionResult": compare_condition(sign, actual, expected),
            "conditionActual": actual,
            "conditionExpected": expected,
            "conditionField": field,
            "conditionEvalNote": None,
        }

    if condition_type == "TICouncilorCondition_bInHomeNation":
        if context_nation is None:
            return condition_eval_unknown("home-nation condition needs --target-nation or --current-location-context")
        home_nation = councilor.get("homeNation") if isinstance(councilor.get("homeNation"), dict) else None
        actual = None
        if home_nation and home_nation.get("id") is not None and context_nation.get("id") is not None:
            actual = home_nation.get("id") == context_nation.get("id")
        expected = parse_bool(condition.get("strValue"))
        return {
            "conditionResult": compare_condition(sign, actual, expected),
            "conditionActual": actual,
            "conditionExpected": expected,
            "conditionField": "inHomeNation",
            "conditionEvalNote": None if actual is not None else "home nation or context nation is unavailable",
        }

    if condition_type == "TIFactionCondition_efResourceValue":
        faction = find_faction_for_councilor(snapshot, councilor)
        resource = condition.get("strIdx")
        actual = None
        if faction and isinstance(faction.get("resources"), dict) and isinstance(resource, str):
            actual = faction["resources"].get(resource)
        expected = parse_modifier_number(condition.get("strValue"))
        return {
            "conditionResult": compare_condition(sign, actual, expected),
            "conditionActual": actual,
            "conditionExpected": expected,
            "conditionField": f"resources.{resource}",
            "conditionEvalNote": None if actual is not None else "faction resource is unavailable",
        }

    if condition_type == "TIGlobalCondition_bNuclearWeaponsUsed":
        actual = (snapshot.get("global", {}).get("nuclearStrikes") or 0) > 0
        expected = parse_bool(condition.get("strValue"))
        return {
            "conditionResult": compare_condition(sign, actual, expected),
            "conditionActual": actual,
            "conditionExpected": expected,
            "conditionField": "global.nuclearStrikes>0",
            "conditionEvalNote": None,
        }

    return condition_eval_unknown(f"unsupported condition type: {condition_type}")


def apply_conditional_attribute_mods(
    final_attributes: dict[str, int],
    clamped_max_attributes: dict[str, int],
    active_mods: list[dict[str, Any]],
) -> tuple[dict[str, int], dict[str, int], dict[str, int]]:
    totals = sum_attr_mods(active_mods)
    contextual_attributes: dict[str, int] = {}
    contextual_max_attributes: dict[str, int] = {}
    for attribute in COUNCILOR_ATTRIBUTES:
        negative_mods = sum(
            mod["contribution"]
            for mod in active_mods
            if mod.get("attribute") == attribute and isinstance(mod.get("contribution"), int) and mod["contribution"] < 0
        )
        max_value = clamped_max_attributes.get(attribute, DEFAULT_MAX_COUNCILOR_ATTRIBUTE) + negative_mods
        contextual_max_attributes[attribute] = max_value
        contextual_attributes[attribute] = clamp_attribute(final_attributes.get(attribute, 0) + totals[attribute], max_value)
    return contextual_attributes, totals, contextual_max_attributes


def evaluate_councilor_conditionals(
    councilor: dict[str, Any],
    snapshot: dict[str, Any],
    context_nation: dict[str, Any] | None,
    context_label: str,
) -> dict[str, Any]:
    evaluated_mods = []
    warnings = []
    active_mods = []
    for mod in councilor.get("conditionalTraitMods") or []:
        if not isinstance(mod, dict):
            continue
        evaluated = dict(mod)
        evaluated.update(evaluate_condition(evaluated, councilor, snapshot, context_nation))
        evaluated_mods.append(evaluated)
        if evaluated.get("conditionResult") is True and evaluated.get("supported") and isinstance(evaluated.get("contribution"), int):
            active_mods.append(evaluated)
        elif evaluated.get("conditionResult") is None:
            warnings.append(
                f"{evaluated.get('trait')} {evaluated.get('attribute')}: {evaluated.get('conditionEvalNote')}"
            )

    contextual_attributes, totals, contextual_max_attributes = apply_conditional_attribute_mods(
        councilor.get("finalAttributes") or {},
        councilor.get("clampedMaxAttributes") or {},
        active_mods,
    )
    return {
        "conditionContext": {
            "mode": context_label,
            "nation": condition_nation_summary(context_nation),
        },
        "contextualAttributeMods": totals,
        "contextualMaxAttributes": contextual_max_attributes,
        "contextualAttributes": contextual_attributes,
        "evaluatedConditionalTraitMods": evaluated_mods,
        "conditionEvaluationWarnings": warnings,
    }


def councilor_summary_maps(
    indexed: IndexedState,
    trait_templates: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[int, dict[str, Any]]]:
    summaries = snapshot_layer.summarize_councilors(indexed, trait_templates, ORG_SNAPSHOT_CONFIG)
    by_id = {
        summary["id"]: summary
        for summary in summaries
        if isinstance(summary.get("id"), int)
    }
    return summaries, by_id


def org_attribute_values(org: dict[str, Any]) -> dict[str, int]:
    return {
        attribute: int(as_float(org.get(field), 0.0))
        for attribute, field in ORG_ATTRIBUTE_FIELDS.items()
    }


def org_acquisition_cost(org: dict[str, Any]) -> dict[str, float]:
    return {
        resource: as_float(org.get(field), 0.0)
        for resource, field in ORG_PLAN_COST_FIELDS.items()
        if as_float(org.get(field), 0.0) != 0.0
    }


def org_plan_cost_affordable(resources: dict[str, Any], cost: dict[str, Any]) -> bool:
    return all(as_float(resources.get(resource), 0.0) >= as_float(amount, 0.0) for resource, amount in cost.items())


def org_plan_normalize_focus(focus: str) -> str | None:
    if focus == "balanced":
        return None
    for attribute in ORG_PLAN_SCORE_ATTRIBUTES:
        if attribute.casefold() == focus.casefold():
            return attribute
    raise ValueError(f"Unsupported org-plan focus: {focus}")


def org_plan_objective_score(attributes: dict[str, Any], focus: str = "balanced") -> float:
    attribute = org_plan_normalize_focus(focus)
    if attribute:
        return as_float(attributes.get(attribute), 0.0)
    return sum(as_float(attributes.get(key), 0.0) for key in ORG_PLAN_SCORE_ATTRIBUTES)


def org_plan_final_attributes(profile: dict[str, Any], orgs: Iterable[dict[str, Any]]) -> dict[str, int]:
    base_attributes = profile.get("baseAttributes") if isinstance(profile.get("baseAttributes"), dict) else {}
    trait_totals = profile.get("traitAttributeMods") if isinstance(profile.get("traitAttributeMods"), dict) else {}
    org_totals = {attribute: 0 for attribute in COUNCILOR_ATTRIBUTES}
    for org in orgs:
        for attribute, value in org_attribute_values(org).items():
            org_totals[attribute] += value

    final_attributes: dict[str, int] = {}
    for attribute in COUNCILOR_ATTRIBUTES:
        trait_value = int(as_float(trait_totals.get(attribute), 0.0))
        org_value = int(as_float(org_totals.get(attribute), 0.0))
        unclamped = int(as_float(base_attributes.get(attribute), 0.0)) + trait_value + org_value
        clamped_max = DEFAULT_MAX_COUNCILOR_ATTRIBUTE + min(0, trait_value) + min(0, org_value)
        final_attributes[attribute] = clamp_attribute(unclamped, clamped_max)
    return final_attributes


def org_plan_roster_summary(
    profile: dict[str, Any],
    org_by_id: dict[int, dict[str, Any]],
    org_ids: Iterable[int],
) -> dict[str, Any]:
    ids = tuple(org_ids)
    orgs = [org_by_id[org_id] for org_id in ids if org_id in org_by_id]
    attributes = org_plan_final_attributes(profile, orgs)
    tier_total = sum(int(as_float(org.get("tier"), 0.0)) for org in orgs)
    administration = int(as_float(attributes.get("Administration"), 0.0))
    return {
        "orgIds": list(ids),
        "attributes": attributes,
        "tierTotal": tier_total,
        "administration": administration,
        "freeCapacity": administration - tier_total,
        "validCapacity": tier_total <= administration,
    }


def org_plan_attribute_delta(before: dict[str, Any], after: dict[str, Any]) -> dict[str, int]:
    return {
        attribute: int(as_float(after.get(attribute), 0.0) - as_float(before.get(attribute), 0.0))
        for attribute in ORG_PLAN_SCORE_ATTRIBUTES
        if int(as_float(after.get(attribute), 0.0) - as_float(before.get(attribute), 0.0)) != 0
    }


def org_plan_org_row(org: dict[str, Any], source: str | None = None) -> dict[str, Any]:
    row = {
        "id": ref_id(org.get("ID")),
        "template": org.get("templateName"),
        "display": org.get("displayName"),
        "tier": int(as_float(org.get("tier"), 0.0)),
        "attributes": {key: value for key, value in org_attribute_values(org).items() if value != 0},
        "cost": org_acquisition_cost(org),
    }
    if source:
        row["source"] = source
    return row


def org_plan_region_nation_id(indexed: IndexedState | None, region_ref: Any) -> int | None:
    if indexed is None:
        return None
    found = resolve_ref(indexed, region_ref)
    if not found:
        return None
    return ref_id(found[2].get("nation"))


def org_plan_owner_eligibility(
    indexed: IndexedState | None,
    councilor: dict[str, Any],
    org: dict[str, Any],
    org_templates: dict[str, dict[str, Any]] | None,
) -> tuple[bool, list[str]]:
    template = (org_templates or {}).get(str(org.get("templateName")), {})
    traits = set(councilor.get("traitTemplateNames") if isinstance(councilor.get("traitTemplateNames"), list) else [])
    reasons: list[str] = []

    required_traits = template.get("requiredOwnerTraits") if isinstance(template.get("requiredOwnerTraits"), list) else []
    prohibited_traits = template.get("prohibitedOwnerTraits") if isinstance(template.get("prohibitedOwnerTraits"), list) else []
    missing_traits = [trait for trait in required_traits if trait not in traits]
    blocked_traits = [trait for trait in prohibited_traits if trait in traits]
    if missing_traits:
        reasons.append(f"missing required owner traits: {', '.join(str(value) for value in missing_traits)}")
    if blocked_traits:
        reasons.append(f"prohibited owner traits: {', '.join(str(value) for value in blocked_traits)}")

    if template.get("requiresNationality"):
        councilor_nation_id = org_plan_region_nation_id(indexed, councilor.get("homeRegion"))
        org_nation_id = org_plan_region_nation_id(indexed, org.get("homeRegion"))
        if councilor_nation_id is None or org_nation_id is None:
            reasons.append("nationality requirement could not be resolved")
        elif councilor_nation_id != org_nation_id:
            reasons.append("nationality requirement does not match")
    return not reasons, reasons


def org_plan_major_attributes(attributes: dict[str, Any], limit: int = 2) -> list[str]:
    mission_attributes = [attribute for attribute in ORG_PLAN_SCORE_ATTRIBUTES if attribute != "Administration"]
    return sorted(
        mission_attributes,
        key=lambda attribute: (-as_float(attributes.get(attribute), 0.0), attribute),
    )[:limit]


def councilor_org_plan_profile(
    indexed: IndexedState,
    councilor_id: int,
    councilor: dict[str, Any],
    trait_templates: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    breakdown = councilor_attribute_breakdown(indexed, councilor, trait_templates)
    org_refs = councilor.get("orgs") if isinstance(councilor.get("orgs"), list) else []
    org_ids = [
        org_id
        for org_id in (ref_id(value) for value in org_refs)
        if org_id is not None
    ]
    return {
        "id": councilor_id,
        "display": councilor.get("displayName"),
        "template": councilor.get("templateName"),
        "councilor": councilor,
        "baseAttributes": breakdown.get("baseAttributes") or {},
        "traitAttributeMods": breakdown.get("traitAttributeMods") or {},
        "currentAttributes": breakdown.get("finalAttributes") or {},
        "assignedOrgIds": org_ids,
    }


def org_plan_best_assignment(
    profile: dict[str, Any],
    org_by_id: dict[int, dict[str, Any]],
    assigned_org_ids: Iterable[int],
    candidate_id: int,
    source: str,
    resources: dict[str, Any],
    focus: str,
    indexed: IndexedState | None = None,
    org_templates: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    candidate = org_by_id.get(candidate_id)
    if not candidate:
        return None
    eligible, eligibility_reasons = org_plan_owner_eligibility(
        indexed,
        profile.get("councilor") if isinstance(profile.get("councilor"), dict) else {},
        candidate,
        org_templates,
    )
    if not eligible:
        return None

    current_ids = tuple(org_id for org_id in assigned_org_ids if org_id != candidate_id)
    before = org_plan_roster_summary(profile, org_by_id, current_ids)
    cost = org_acquisition_cost(candidate) if source == "market" else {}
    affordable = org_plan_cost_affordable(resources, cost)
    candidate_tier = max(0, int(as_float(candidate.get("tier"), 0.0)))
    # A valid current roster only needs to free at most the incoming org's tier.
    # Enumerating larger removal sets adds exponential work and cannot improve a
    # non-negative capped stat objective.
    max_removed = min(len(current_ids), max(candidate_tier, 1))
    best: tuple[tuple[float, float, int, int], dict[str, Any]] | None = None

    for remove_count in range(max_removed + 1):
        for removed_ids in combinations(current_ids, remove_count):
            removed = set(removed_ids)
            after_ids = tuple(org_id for org_id in current_ids if org_id not in removed) + (candidate_id,)
            after = org_plan_roster_summary(profile, org_by_id, after_ids)
            if not after["validCapacity"]:
                continue
            gain = org_plan_objective_score(after["attributes"], focus) - org_plan_objective_score(before["attributes"], focus)
            balanced_gain = org_plan_objective_score(after["attributes"]) - org_plan_objective_score(before["attributes"])
            rank = (gain, balanced_gain, -remove_count, after["freeCapacity"])
            action = {
                "councilorId": profile.get("id"),
                "councilor": profile.get("display"),
                "source": source,
                "candidate": org_plan_org_row(candidate, source),
                "cost": cost,
                "affordableNow": affordable,
                "eligible": True,
                "eligibilityNotes": eligibility_reasons,
                "removedOrgs": [
                    org_plan_org_row(org_by_id[org_id], "returnedToInventory")
                    for org_id in removed_ids
                    if org_id in org_by_id
                ],
                "attributesBefore": before["attributes"],
                "attributesAfter": after["attributes"],
                "attributeDelta": org_plan_attribute_delta(before["attributes"], after["attributes"]),
                "tierTotalBefore": before["tierTotal"],
                "tierTotalAfter": after["tierTotal"],
                "freeCapacityBefore": before["freeCapacity"],
                "freeCapacityAfter": after["freeCapacity"],
                "objective": focus,
                "objectiveScoreBefore": org_plan_objective_score(before["attributes"], focus),
                "objectiveScoreAfter": org_plan_objective_score(after["attributes"], focus),
                "objectiveGain": gain,
                "balancedScoreBefore": org_plan_objective_score(before["attributes"]),
                "balancedScoreAfter": org_plan_objective_score(after["attributes"]),
                "balancedGain": balanced_gain,
            }
            if best is None or rank > best[0]:
                best = (rank, action)
    return clean_numbers(best[1], 6) if best else None


def org_plan_committee_totals(
    profiles: dict[int, dict[str, Any]],
    org_by_id: dict[int, dict[str, Any]],
    roster: dict[int, tuple[int, ...]],
) -> dict[str, int]:
    totals = {attribute: 0 for attribute in ORG_PLAN_SCORE_ATTRIBUTES}
    for councilor_id, profile in profiles.items():
        attributes = org_plan_roster_summary(profile, org_by_id, roster.get(councilor_id, ()))["attributes"]
        for attribute in totals:
            totals[attribute] += int(as_float(attributes.get(attribute), 0.0))
    return totals


def org_plan_committee_score(
    profiles: dict[int, dict[str, Any]],
    org_by_id: dict[int, dict[str, Any]],
    roster: dict[int, tuple[int, ...]],
    focus: str,
) -> float:
    return org_plan_objective_score(org_plan_committee_totals(profiles, org_by_id, roster), focus)


def org_plan_state_key(state: dict[str, Any]) -> tuple[Any, ...]:
    return (
        tuple((councilor_id, tuple(sorted(org_ids))) for councilor_id, org_ids in sorted(state["roster"].items())),
        tuple(sorted(state["market"])),
        tuple(sorted(state["inventory"])),
    )


def search_org_committee_plan(
    profiles: dict[int, dict[str, Any]] | Iterable[dict[str, Any]],
    org_by_id: dict[int, dict[str, Any]],
    market_ids: Iterable[int],
    inventory_ids: Iterable[int],
    resources: dict[str, Any],
    focus: str = "balanced",
    max_actions: int = 4,
    beam_width: int = 8,
    indexed: IndexedState | None = None,
    org_templates: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if not isinstance(profiles, dict):
        profiles = {
            int(profile["id"]): profile
            for profile in profiles
            if isinstance(profile.get("id"), int)
        }
    roster = {
        councilor_id: tuple(profile.get("assignedOrgIds") if isinstance(profile.get("assignedOrgIds"), list) else [])
        for councilor_id, profile in profiles.items()
    }
    initial = {
        "roster": roster,
        "market": frozenset(market_ids),
        "inventory": frozenset(inventory_ids),
        "resources": {resource: as_float(value, 0.0) for resource, value in resources.items()},
        "actions": [],
    }
    initial["score"] = org_plan_committee_score(profiles, org_by_id, roster, focus)
    initial["balancedScore"] = org_plan_committee_score(profiles, org_by_id, roster, "balanced")
    initial_totals = org_plan_committee_totals(profiles, org_by_id, roster)
    beam = [initial]
    best = initial
    explored_states = 1

    for _ in range(max(0, max_actions)):
        next_by_key: dict[tuple[Any, ...], dict[str, Any]] = {}
        for state in beam:
            pool_ids = sorted(set(state["market"]) | set(state["inventory"]))
            for candidate_id in pool_ids:
                source = "market" if candidate_id in state["market"] else "ownedInventory"
                for councilor_id, profile in profiles.items():
                    action = org_plan_best_assignment(
                        profile,
                        org_by_id,
                        state["roster"].get(councilor_id, ()),
                        candidate_id,
                        source,
                        state["resources"],
                        focus,
                        indexed=indexed,
                        org_templates=org_templates,
                    )
                    capacity_gain = as_float(action.get("freeCapacityAfter"), 0.0) - as_float(action.get("freeCapacityBefore"), 0.0) if action else 0.0
                    if (
                        not action
                        or not action["affordableNow"]
                        or (
                            as_float(action.get("objectiveGain"), 0.0) <= 0.0
                            and capacity_gain <= 0.0
                        )
                    ):
                        continue

                    removed_ids = {
                        row["id"]
                        for row in action["removedOrgs"]
                        if isinstance(row.get("id"), int)
                    }
                    current_ids = state["roster"].get(councilor_id, ())
                    next_roster = dict(state["roster"])
                    next_roster[councilor_id] = tuple(org_id for org_id in current_ids if org_id not in removed_ids) + (candidate_id,)
                    next_market = set(state["market"])
                    next_inventory = set(state["inventory"])
                    if source == "market":
                        next_market.discard(candidate_id)
                    else:
                        next_inventory.discard(candidate_id)
                    next_inventory.update(removed_ids)
                    next_resources = dict(state["resources"])
                    for resource, amount in action["cost"].items():
                        next_resources[resource] = as_float(next_resources.get(resource), 0.0) - as_float(amount, 0.0)
                    score = org_plan_committee_score(profiles, org_by_id, next_roster, focus)
                    balanced_score = org_plan_committee_score(profiles, org_by_id, next_roster, "balanced")
                    next_action = dict(action)
                    next_action["step"] = len(state["actions"]) + 1
                    next_action["committeeObjectiveScoreAfter"] = score
                    next_action["committeeBalancedScoreAfter"] = balanced_score
                    next_state = {
                        "roster": next_roster,
                        "market": frozenset(next_market),
                        "inventory": frozenset(next_inventory),
                        "resources": next_resources,
                        "actions": [*state["actions"], next_action],
                        "score": score,
                        "balancedScore": balanced_score,
                    }
                    key = org_plan_state_key(next_state)
                    existing = next_by_key.get(key)
                    if existing is None or (score, balanced_score) > (existing["score"], existing["balancedScore"]):
                        next_by_key[key] = next_state
        if not next_by_key:
            break
        explored_states += len(next_by_key)
        beam = sorted(
            next_by_key.values(),
            key=lambda state: (-state["score"], -state["balancedScore"], len(state["actions"])),
        )[: max(1, beam_width)]
        if (beam[0]["score"], beam[0]["balancedScore"]) > (best["score"], best["balancedScore"]):
            best = beam[0]

    final_totals = org_plan_committee_totals(profiles, org_by_id, best["roster"])
    final_roster = []
    for councilor_id, profile in profiles.items():
        summary = org_plan_roster_summary(profile, org_by_id, best["roster"].get(councilor_id, ()))
        final_roster.append(
            {
                "id": councilor_id,
                "display": profile.get("display"),
                "majorAttributes": org_plan_major_attributes(summary["attributes"]),
                **summary,
            }
        )
    return clean_numbers(
        {
            "objective": focus,
            "objectiveScoreBefore": initial["score"],
            "objectiveScoreAfter": best["score"],
            "objectiveGain": best["score"] - initial["score"],
            "balancedScoreBefore": initial["balancedScore"],
            "balancedScoreAfter": best["balancedScore"],
            "balancedGain": best["balancedScore"] - initial["balancedScore"],
            "committeeAttributesBefore": initial_totals,
            "committeeAttributesAfter": final_totals,
            "committeeAttributeDelta": org_plan_attribute_delta(initial_totals, final_totals),
            "actions": best["actions"],
            "marketAcquisitions": sum(1 for action in best["actions"] if action.get("source") == "market"),
            "remainingResources": best["resources"],
            "remainingMarketOrgIds": sorted(best["market"]),
            "remainingOwnedInventoryOrgIds": sorted(best["inventory"]),
            "finalRoster": final_roster,
            "search": {
                "maxActions": max_actions,
                "beamWidth": beam_width,
                "exploredStates": explored_states,
                "boundedHeuristic": True,
            },
        },
        6,
    )


def calculate_org_plan(
    indexed: IndexedState,
    templates_dir: Path | None,
    faction_name: str | None = None,
    focus: str = "balanced",
    top: int = 5,
    include_unassigned: bool = True,
    max_actions: int = 4,
    beam_width: int = 8,
    include_all_candidates: bool = False,
) -> dict[str, Any]:
    trait_templates = load_trait_templates(templates_dir)
    org_templates = load_named_templates(templates_dir, "TIOrgTemplate.json")
    faction_id, faction = find_faction_state(indexed, faction_name)
    profiles = {
        councilor_id: councilor_org_plan_profile(indexed, councilor_id, councilor, trait_templates)
        for councilor_id in faction_councilor_ids(faction)
        for councilor in [state_value_by_id(indexed, councilor_id)]
        if councilor
    }
    org_by_id = {
        org_id: org
        for entry in type_entries(indexed, "TIOrgState")
        for org in [entry.get("Value") or {}]
        for org_id in [ref_id(entry.get("Key")) or ref_id(org.get("ID"))]
        if org_id is not None
    }
    market_refs = faction.get("availableOrgs") if isinstance(faction.get("availableOrgs"), list) else []
    inventory_refs = faction.get("unassignedOrgs") if include_unassigned and isinstance(faction.get("unassignedOrgs"), list) else []
    market_ids = [
        org_id
        for org_id in (ref_id(value) for value in market_refs)
        if org_id is not None and org_id in org_by_id
    ]
    inventory_ids = [
        org_id
        for org_id in (ref_id(value) for value in inventory_refs)
        if org_id is not None and org_id in org_by_id
    ]
    resources = faction.get("resources") if isinstance(faction.get("resources"), dict) else {}
    source_by_id = {org_id: "market" for org_id in market_ids}
    source_by_id.update({org_id: "ownedInventory" for org_id in inventory_ids})
    candidate_ids = sorted(source_by_id)

    councilor_rows = []
    for councilor_id, profile in profiles.items():
        current = org_plan_roster_summary(profile, org_by_id, profile["assignedOrgIds"])
        goal_views: dict[str, list[dict[str, Any]]] = {}
        all_actions: dict[str, list[dict[str, Any]]] = {}
        for view_focus in ORG_PLAN_FOCUS_CHOICES:
            actions = [
                action
                for candidate_id in candidate_ids
                for action in [
                    org_plan_best_assignment(
                        profile,
                        org_by_id,
                        profile["assignedOrgIds"],
                        candidate_id,
                        source_by_id[candidate_id],
                        resources,
                        view_focus,
                        indexed=indexed,
                        org_templates=org_templates,
                    )
                ]
                if action and as_float(action.get("objectiveGain"), 0.0) > 0.0
            ]
            actions.sort(
                key=lambda action: (
                    -as_float(action.get("objectiveGain"), 0.0),
                    0 if action.get("affordableNow") else 1,
                    str((action.get("candidate") or {}).get("display")),
                )
            )
            goal_views[view_focus] = actions[: max(0, top)]
            if include_all_candidates:
                all_actions[view_focus] = actions
        councilor_rows.append(
            {
                "id": councilor_id,
                "display": profile.get("display"),
                "majorAttributes": org_plan_major_attributes(current["attributes"]),
                "current": current,
                "goalViews": goal_views,
                **({"allCandidateActions": all_actions} if include_all_candidates else {}),
            }
        )

    committee_plan = search_org_committee_plan(
        profiles,
        org_by_id,
        market_ids,
        inventory_ids,
        resources,
        focus=focus,
        max_actions=max_actions,
        beam_width=beam_width,
        indexed=indexed,
        org_templates=org_templates,
    )
    return clean_numbers(
        {
            "faction": faction_brief(faction_id, faction),
            "focus": focus,
            "candidateSources": {
                "market": {
                    "count": len(market_ids),
                    "orgs": [
                        {
                            **org_plan_org_row(org_by_id[org_id], "market"),
                            "affordableNow": org_plan_cost_affordable(resources, org_acquisition_cost(org_by_id[org_id])),
                        }
                        for org_id in market_ids
                    ],
                },
                "ownedInventory": {
                    "included": include_unassigned,
                    "count": len(inventory_ids),
                    "orgs": [org_plan_org_row(org_by_id[org_id], "ownedInventory") for org_id in inventory_ids],
                },
            },
            "councilors": councilor_rows,
            "committeePlan": committee_plan,
            "scoreModel": {
                "balanced": f"Sum of capped councilor stats: {', '.join(ORG_PLAN_SCORE_ATTRIBUTES)}.",
                "attributeFocus": "A named focus maximizes the committee total for that capped attribute.",
                "majorAttributes": "Each councilor's two highest current non-Administration mission stats; use the matching goalViews for specialization.",
            },
            "limitations": [
                "The market candidate set comes from TIFactionState.availableOrgs, which is the save's faction-visible acquisition list.",
                "Owned unassigned orgs are included by default so the plan does not recommend spending resources before using existing inventory; pass --market-only to exclude them.",
                "The committee plan is a bounded beam-search heuristic, not a proof of the mathematical global optimum.",
                "The planner optimizes capped councilor stats and Administration capacity. Income, mining, tech-category bonuses, granted missions, and takeover defense remain visible on org states but are not folded into the score.",
            ],
        },
        6,
    )
