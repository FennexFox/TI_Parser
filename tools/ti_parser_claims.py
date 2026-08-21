"""Read-only nation and region claim diagnostics.

The save is authoritative for which regions a nation claims and which of those
claims are statically hostile.  The only dynamic hostility rule reconstructed
here is the game-code comparison documented in the packaged claim catalog::

    target.democracy > claimant.democracy
        + democracyDecreaseToMakeHostileClaim

No default is supplied for that threshold: omitting it makes affected rows and
the overall calculation incomplete instead of producing a plausible result.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from ti_parser_core import (
    IndexedState,
    campaign_code,
    match_raw_state,
    raw_state_id,
    ref_id,
    resolve_ref,
    scenario_template_name,
    type_entries,
)


DEMOCRACY_RULE = "democracyDecreaseToMakeHostileClaim"
DEMOCRACY_FORMULA = (
    "target.democracy > claimant.democracy + "
    "democracyDecreaseToMakeHostileClaim"
)


def _deep_merge(base: Mapping[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    merged = deepcopy(dict(base))
    for key, value in override.items():
        current = merged.get(key)
        if isinstance(current, Mapping) and isinstance(value, Mapping):
            merged[key] = _deep_merge(current, value)
        else:
            merged[key] = deepcopy(value)
    return merged


def _catalog_for_scenario(
    claim_catalog: Mapping[str, Any] | None,
    scenario: str | None,
) -> tuple[dict[str, Any], list[str], dict[str, Any]]:
    """Return selected catalog payload, applied override names, and metadata."""

    if not isinstance(claim_catalog, Mapping):
        return {}, [], {}

    top_level = dict(claim_catalog)
    base = top_level.get("base")
    selected = deepcopy(dict(base)) if isinstance(base, Mapping) else deepcopy(top_level)
    overrides = top_level.get("scenarioOverrides")
    applied: list[str] = []
    if scenario and isinstance(overrides, Mapping) and isinstance(overrides.get(scenario), Mapping):
        selected = _deep_merge(selected, overrides[scenario])
        applied.append(scenario)

    metadata = {
        key: deepcopy(top_level[key])
        for key in (
            "schemaVersion",
            "generator",
            "sourceFiles",
            "payloadFingerprint",
            "supportedScenarios",
        )
        if key in top_level
    }
    return selected, applied, metadata


def _numeric_rule(payload: Mapping[str, Any], name: str) -> float | None:
    """Find one unambiguous numeric rule value without guessing a default."""

    found: list[float] = []

    def visit(value: Any) -> None:
        if isinstance(value, Mapping):
            for key, child in value.items():
                if key == name and isinstance(child, (int, float)) and not isinstance(child, bool):
                    found.append(float(child))
                elif isinstance(child, Mapping):
                    visit(child)

    visit(payload)
    if not found:
        return None
    first = found[0]
    return first if all(value == first for value in found) else None


def _nation_summary(state_id: int | None, nation: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if nation is None:
        return None
    template = nation.get("templateName")
    return {
        "id": state_id,
        "template": template,
        "code": campaign_code(str(template)) if template else None,
        "display": nation.get("displayName"),
        "democracy": _number_or_none(nation.get("democracy")),
    }


def _number_or_none(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def _state_name(state: Mapping[str, Any]) -> str | None:
    value = state.get("templateName") or state.get("displayName")
    return str(value) if value else None


def _catalog_claim_metadata(
    payload: Mapping[str, Any],
    claimant: Mapping[str, Any],
    region: Mapping[str, Any] | None,
    region_id: int,
) -> dict[str, Any]:
    """Read optional evidence metadata from common normalized catalog shapes.

    Catalog metadata is advisory evidence only.  Save references remain the
    source of current claim and static-hostility state.
    """

    claimant_names = {
        str(value)
        for value in (claimant.get("templateName"), campaign_code(claimant.get("templateName")))
        if value
    }
    region_names = {
        str(value)
        for value in (
            region_id,
            (region or {}).get("templateName"),
            campaign_code((region or {}).get("templateName")),
        )
        if value is not None
    }

    candidates: list[Mapping[str, Any]] = []
    rows = payload.get("claims")
    if isinstance(rows, list):
        candidates.extend(row for row in rows if isinstance(row, Mapping))

    nations = payload.get("nations")
    if isinstance(nations, Mapping):
        for claimant_name in claimant_names:
            nation_row = nations.get(claimant_name)
            if isinstance(nation_row, Mapping):
                nation_claims = nation_row.get("claims")
                if isinstance(nation_claims, list):
                    candidates.extend(row for row in nation_claims if isinstance(row, Mapping))
                elif isinstance(nation_claims, Mapping):
                    for region_name in region_names:
                        row = nation_claims.get(region_name)
                        if isinstance(row, Mapping):
                            candidates.append(row)
    elif isinstance(nations, list):
        for nation_row in nations:
            if not isinstance(nation_row, Mapping):
                continue
            name = nation_row.get("dataName") or nation_row.get("templateName")
            if name not in claimant_names:
                continue
            nation_claims = nation_row.get("claims")
            if isinstance(nation_claims, list):
                candidates.extend(row for row in nation_claims if isinstance(row, Mapping))

    def matches(row: Mapping[str, Any]) -> bool:
        claimant_name = row.get("claimant") or row.get("claimantName")
        region_name = row.get("region") or row.get("regionName") or row.get("regionId")
        return (claimant_name is None or str(claimant_name) in claimant_names) and (
            region_name is not None and str(region_name) in region_names
        )

    matching = [dict(row) for row in candidates if matches(row)]
    return _deep_merge({}, matching[-1]) if matching else {}


def _requested_nation_id(indexed: IndexedState, name: str | None, label: str) -> int | None:
    if name is None:
        return None
    found = match_raw_state(indexed, "TINationState", name)
    if found is None:
        raise ValueError(f"{label} nation not found: {name}")
    if found[0] is None:
        raise ValueError(f"{label} nation has no state ID: {name}")
    return found[0]


def calculate_nation_claims(
    indexed: IndexedState,
    claimant_name: str | None = None,
    target_name: str | None = None,
    claim_catalog: Mapping[str, Any] | None = None,
    diagnostics: bool = False,
) -> dict[str, Any]:
    """Explain saved nation claims and their currently evidenced hostility.

    ``claimant_name`` and ``target_name`` accept the same template/code/display
    matching used by other parser APIs.  ``target_name`` selects the current
    owner of each claimed region, not the region itself.
    """

    scenario = scenario_template_name(indexed)
    catalog, applied_overrides, catalog_metadata = _catalog_for_scenario(claim_catalog, scenario)
    threshold = _numeric_rule(catalog, DEMOCRACY_RULE)
    claimant_filter_id = _requested_nation_id(indexed, claimant_name, "Claimant")
    target_filter_id = _requested_nation_id(indexed, target_name, "Target")

    nation_entries: list[tuple[int | None, dict[str, Any]]] = []
    for entry in type_entries(indexed, "TINationState"):
        nation = entry.get("Value") or {}
        if isinstance(nation, dict):
            nation_entries.append((raw_state_id(entry), nation))
    nations_by_id = {state_id: nation for state_id, nation in nation_entries if state_id is not None}

    rows: list[dict[str, Any]] = []
    missing_dependencies: list[dict[str, Any]] = []
    seen_missing: set[tuple[str, str, str]] = set()

    def missing(kind: str, name: str, context: str, reason: str) -> None:
        key = (kind, name, context)
        if key in seen_missing:
            return
        seen_missing.add(key)
        missing_dependencies.append(
            {
                "kind": kind,
                "name": name,
                "context": context,
                "scenario": scenario,
                "reason": reason,
            }
        )

    for claimant_id, claimant in nation_entries:
        if claimant_filter_id is not None and claimant_id != claimant_filter_id:
            continue

        claims = claimant.get("claims") if isinstance(claimant.get("claims"), list) else []
        hostile_claims = claimant.get("hostileClaims") if isinstance(claimant.get("hostileClaims"), list) else []
        claim_ids = [value for item in claims if (value := ref_id(item)) is not None]
        hostile_ids = {value for item in hostile_claims if (value := ref_id(item)) is not None}
        ordered_ids = list(dict.fromkeys(claim_ids + sorted(hostile_ids - set(claim_ids))))

        for region_id in ordered_ids:
            found_region = resolve_ref(indexed, {"value": region_id})
            region = found_region[2] if found_region and found_region[1] == "TIRegionState" else None
            owner_id = ref_id(region.get("nation")) if region else None
            owner_state = nations_by_id.get(owner_id)
            if target_filter_id is not None and owner_id != target_filter_id:
                continue

            context = f"{_state_name(claimant) or claimant_id}:{region_id}"
            raw_claim = region_id in claim_ids
            static_hostile = region_id in hostile_ids
            metadata = _catalog_claim_metadata(catalog, claimant, region, region_id)
            permanent_value = metadata.get("permanent")
            if not isinstance(permanent_value, bool):
                permanent_value = metadata.get("permanentHostile")
            permanent = permanent_value if isinstance(permanent_value, bool) else None

            claimant_democracy = _number_or_none(claimant.get("democracy"))
            target_democracy = _number_or_none(owner_state.get("democracy")) if owner_state else None
            right_hand_side = (
                claimant_democracy + threshold
                if claimant_democracy is not None and threshold is not None
                else None
            )
            comparison = (
                target_democracy > right_hand_side
                if target_democracy is not None and right_hand_side is not None
                else None
            )

            if region is None:
                hostility_kind = "unknown"
                status = "unknown"
                reason = "Claimed region state is missing; ownership and dynamic hostility cannot be evaluated."
                missing("region", str(region_id), context, "claimed TIRegionState reference is unresolved")
            elif static_hostile:
                hostility_kind = "static"
                status = "hostile"
                reason = "The region is listed in TINationState.hostileClaims."
            elif owner_state is None:
                hostility_kind = "unknown"
                status = "unknown"
                reason = "The claimed region has no resolvable current nation owner."
                missing("nation", str(owner_id), context, "claimed region owner is unresolved")
            elif claimant_democracy is None or target_democracy is None:
                hostility_kind = "unknown"
                status = "unknown"
                reason = "A democracy value required by the evidenced hostility rule is missing."
                missing("save-field", "democracy", context, "claimant or target democracy is missing")
            elif threshold is None:
                hostility_kind = "unknown"
                status = "unknown"
                reason = "The packaged claim rule threshold is unavailable or ambiguous."
                missing("claim-rule", DEMOCRACY_RULE, context, "required threshold is missing or ambiguous")
            elif comparison:
                hostility_kind = "conditional"
                status = "hostile"
                reason = "The target democracy is strictly greater than the dynamic hostility boundary."
            else:
                hostility_kind = "peaceful"
                status = "peaceful"
                reason = "The static hostile flag is absent and the strict democracy comparison is false."

            changeable_by_government = hostility_kind in {"conditional", "peaceful"}
            formula = {
                "expression": DEMOCRACY_FORMULA,
                "claimantDemocracy": claimant_democracy,
                "targetDemocracy": target_democracy,
                "democracyDecreaseToMakeHostileClaim": threshold,
                "hostileBoundary": right_hand_side,
                "comparisonResult": comparison,
                "comparisonIsStrict": True,
            }
            evidence = {
                "observed": [
                    "TINationState.claims" if raw_claim else "TINationState.hostileClaims",
                    "TINationState.hostileClaims",
                    "TIRegionState.nation",
                    "TINationState.democracy",
                ],
                "derived": [
                    "region owner resolved from TIRegionState.nation",
                    f"effective status derived using {DEMOCRACY_FORMULA}",
                ],
                "unknown": [] if permanent is not None else ["permanence is not evidenced for this claim"],
            }
            row = {
                "claimant": _nation_summary(claimant_id, claimant),
                "target": {
                    "nation": _nation_summary(owner_id, owner_state),
                    "region": {
                        "id": region_id,
                        "template": region.get("templateName") if region else None,
                        "code": campaign_code(region.get("templateName")) if region else None,
                        "display": region.get("displayName") if region else None,
                    },
                },
                "claimSource": "TINationState.claims" if raw_claim else "TINationState.hostileClaims",
                "rawClaim": raw_claim,
                "staticHostile": static_hostile,
                "currentEffectiveStatus": status,
                "hostilityKind": hostility_kind,
                "hostile": True if status == "hostile" else False if status == "peaceful" else None,
                "permanent": permanent,
                "reason": reason,
                "governmentRule": formula,
                "changeability": {
                    "changeableByGovernmentValues": changeable_by_government,
                    "canBecomePeacefulByFormula": hostility_kind == "conditional",
                    "canBecomeHostileByFormula": hostility_kind == "peaceful",
                    "conditionForHostile": DEMOCRACY_FORMULA,
                    "conditionForPeaceful": (
                        "target.democracy <= claimant.democracy + "
                        "democracyDecreaseToMakeHostileClaim"
                    ),
                },
                "provenance": evidence,
                "succession": {
                    "annexation": "unknown / not reconstructed",
                    "unification": "unknown / not reconstructed",
                    "independence": "unknown / not reconstructed",
                    "federation": "unknown / not reconstructed",
                },
            }
            if metadata:
                row["catalogMetadata"] = metadata
            rows.append(row)

    counts = {
        "total": len(rows),
        "staticHostile": sum(row["hostilityKind"] == "static" for row in rows),
        "conditionalHostile": sum(row["hostilityKind"] == "conditional" for row in rows),
        "peaceful": sum(row["hostilityKind"] == "peaceful" for row in rows),
        "unknown": sum(row["hostilityKind"] == "unknown" for row in rows),
    }
    result: dict[str, Any] = {
        "status": "incomplete" if missing_dependencies else "complete",
        "scenario": scenario,
        "filters": {"claimant": claimant_name, "target": target_name},
        "counts": counts,
        "claims": rows,
        "missingDependencies": missing_dependencies,
        "knownLimitations": [
            "Annexation, unification, independence, and federation claim succession are not reconstructed.",
            "Claim permanence is unknown unless explicitly evidenced by catalog metadata.",
        ],
    }
    if diagnostics:
        result["calculationDiagnostics"] = {
            "status": result["status"],
            "selectedScenario": scenario,
            "catalog": catalog_metadata or None,
            "appliedScenarioOverrides": applied_overrides,
            "rule": {
                "name": DEMOCRACY_RULE,
                "value": threshold,
                "formula": DEMOCRACY_FORMULA,
                "source": "decompiled game-code rule supplied by the claim catalog",
            },
            "missingDependencies": missing_dependencies,
            "assumptions": [],
            "knownLimitations": result["knownLimitations"],
        }
    return result


__all__ = ["calculate_nation_claims"]
