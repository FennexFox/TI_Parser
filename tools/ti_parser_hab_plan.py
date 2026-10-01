"""Hab candidate scoring, upgrade selection and fill plans."""

from __future__ import annotations

from ti_parser_errors import UserInputError

from pathlib import Path
from typing import Any

from ti_parser_config import (
    HAB_PLAN_FOCUS_CHOICES,
    HAB_PLAN_TECH_BONUS_CATEGORIES,
)
from ti_parser_core import (
    IndexedState,
    as_float,
    clean_numbers,
    faction_effect_contexts,
    find_faction_state,
    load_hab_module_catalog,
    load_location_catalog,
    match_raw_state,
    ref_id,
)
from ti_parser_hab_construction import (
    candidate_module_monthly_delta,
    hab_module_construction_analysis,
    hab_planned_empty_slots,
    hab_projected_power_summary,
    hab_upgrade_info,
    module_affordable_with_template_weights,
    module_break_even_analysis,
    module_build_cost_map,
    module_unmet_requirements,
    resource_market_purchase_values,
    resource_scarcity_weights,
)
from ti_parser_hab_ui import (
    hab_location_summary,
    hab_module_power,
    hab_power_summary,
)
from ti_parser_research import (
    tech_bonus_sum,
    template_display,
)
from ti_parser_runtime import (
    calculation_catalogs,
    councilor_summary_maps,
    faction_brief,
    faction_hab_states,
    faction_mining_rate,
    hab_module_active_record,
    hab_module_counts,
    hab_module_okay,
    hab_module_records,
    hab_slot_summary,
    hab_template_special_rules,
)
from ti_parser_topbar import (
    calculate_topbar,
    mission_control_available_for_planning,
)


def module_research_score(monthly_delta: dict[str, dict[str, float]]) -> float:
    return as_float(monthly_delta.get("Research", {}).get("net"), 0.0)


def module_project_score(monthly_delta: dict[str, dict[str, float]]) -> float:
    return as_float(monthly_delta.get("Projects", {}).get("net"), 0.0)


def module_category_bonus_score(template: dict[str, Any]) -> float:
    return sum(tech_bonus_sum(template.get("techBonuses"), category) for category in HAB_PLAN_TECH_BONUS_CATEGORIES)


def module_balanced_score(research_score: float, resource_score: float) -> float:
    return research_score + resource_score


def module_resource_score(monthly_delta: dict[str, dict[str, float]], scarcity_weights: dict[str, float]) -> float:
    return sum(
        as_float(row.get("net"), 0.0) * scarcity_weights.get(resource, 1.0)
        for resource, row in monthly_delta.items()
        if resource in scarcity_weights
    )


def module_candidate_row(
    indexed: IndexedState,
    hab: dict[str, Any],
    records: list[dict[str, Any]],
    faction: dict[str, Any],
    template: dict[str, Any],
    projected_power: dict[str, int],
    mission_control_available: float,
    effect_contexts: dict[str, list[str]],
    effect_templates: dict[str, dict[str, Any]],
    mining_rate: float,
    scarcity_weights: dict[str, float],
    councilor_by_id: dict[int, dict[str, Any]],
    body_templates: dict[str, dict[str, Any]],
    orbit_templates: dict[str, dict[str, Any]],
    prior_record: dict[str, Any] | None = None,
) -> dict[str, Any]:
    monthly_delta = candidate_module_monthly_delta(
        indexed,
        hab,
        records,
        faction,
        template,
        effect_contexts,
        effect_templates,
        mining_rate,
        councilor_by_id,
        prior_record,
    )
    template_power = int(as_float(template.get("power"), 0.0))
    power = hab_module_power(
        template,
        indexed=indexed,
        hab=hab,
        body_templates=body_templates,
        orbit_templates=orbit_templates,
    )
    prior_template = prior_record.get("template", {}) if isinstance(prior_record, dict) else {}
    prior_power = hab_module_power(
        prior_template,
        indexed=indexed,
        hab=hab,
        body_templates=body_templates,
        orbit_templates=orbit_templates,
    ) if prior_template else 0
    power_change = power - prior_power
    construction = hab_module_construction_analysis(
        indexed,
        hab,
        records,
        faction,
        template,
        body_templates,
        orbit_templates,
        is_upgrade=prior_record is not None,
    )
    break_even = module_break_even_analysis(construction, monthly_delta, resource_market_purchase_values(indexed))
    mission_control = int(as_float(template.get("missionControl"), 0.0))
    prior_mission_control = int(as_float(prior_template.get("missionControl"), 0.0))
    mission_control_change = mission_control - prior_mission_control
    research_score = module_research_score(monthly_delta)
    project_score = module_project_score(monthly_delta)
    category_bonus_score = module_category_bonus_score(template)
    resource_score = module_resource_score(monthly_delta, scarcity_weights)
    return {
        "template": template.get("dataName"),
        "display": template_display(str(template.get("dataName")), template),
        "tier": int(as_float(template.get("tier"), 0.0)),
        "habType": template.get("habType") or "Any",
        "isUpgrade": prior_record is not None,
        "priorTemplate": prior_record.get("templateName") if isinstance(prior_record, dict) else None,
        "power": power,
        "templatePower": template_power,
        "powerChange": power_change,
        "projectedPowerAfterOne": projected_power.get("net", 0) + power_change,
        "missionControl": mission_control_change,
        "resultingMissionControl": mission_control,
        "onePerHab": bool(template.get("onePerHab")),
        "fitsCurrentProjectedPower": projected_power.get("net", 0) + power_change >= 0,
        "fitsCurrentMissionControl": mission_control_change >= 0 or mission_control_available + mission_control_change >= 0,
        "crew": int(as_float(template.get("crew"), 0.0)),
        "buildTime_Days": construction.get("constructionTime_Days"),
        "buildCostTemplateWeights": module_build_cost_map(template),
        "affordableByTemplateWeights": module_affordable_with_template_weights(template, faction),
        "construction": construction,
        "breakEven": break_even,
        "monthlyDelta": monthly_delta,
        "techBonuses": tech_bonus_map_for_template(template),
        "specialRules": hab_template_special_rules(template),
        "scores": {
            "research": research_score,
            "projects": project_score,
            "category-bonus": category_bonus_score,
            "resources": resource_score,
            "balanced": module_balanced_score(research_score, resource_score),
        },
        "scoreComponents": {
            "researchMonthlyNet": research_score,
            "projectsMonthlyNet": project_score,
            "categoryBonusSum": category_bonus_score,
            "resourceScarcityWeightedNet": resource_score,
        },
    }


def tech_bonus_map_for_template(template: dict[str, Any]) -> dict[str, float]:
    bonuses: dict[str, float] = {}
    for item in template.get("techBonuses") if isinstance(template.get("techBonuses"), list) else []:
        if not isinstance(item, dict):
            continue
        category = str(item.get("category"))
        bonuses[category] = bonuses.get(category, 0.0) + as_float(item.get("bonus"), 0.0)
    return bonuses


def hab_module_candidate_rows(
    indexed: IndexedState,
    templates_dir: Path | None,
    hab: dict[str, Any],
    records: list[dict[str, Any]],
    faction_id: int,
    faction: dict[str, Any],
    target_tier: int,
    projected_power: dict[str, int],
    mission_control_available: float,
    topbar: dict[str, Any],
) -> list[dict[str, Any]]:
    hab_module_templates = load_hab_module_catalog()
    location_catalog = load_location_catalog()
    body_templates = location_catalog.body_templates
    orbit_templates = location_catalog.orbit_templates
    runtime_catalogs = calculation_catalogs(indexed, "hab-plan")
    effect_templates = runtime_catalogs.effects
    trait_templates = runtime_catalogs.traits
    _, councilor_by_id = councilor_summary_maps(indexed, trait_templates)
    effect_contexts = faction_effect_contexts(indexed, faction_id)
    mining_rate = faction_mining_rate(indexed, faction)
    scarcity_weights = resource_scarcity_weights(topbar)
    module_counts = hab_module_counts(records)
    rows: list[dict[str, Any]] = []
    for template in hab_module_templates.values():
        reasons = module_unmet_requirements(
            indexed,
            template,
            hab,
            faction,
            target_tier,
            module_counts,
            body_templates,
            hab_module_templates,
        )
        if reasons:
            continue
        row = module_candidate_row(
            indexed,
            hab,
            records,
            faction,
            template,
            projected_power,
            mission_control_available,
            effect_contexts,
            effect_templates,
            mining_rate,
            scarcity_weights,
            councilor_by_id,
            body_templates,
            orbit_templates,
        )
        has_score = any(abs(as_float(value, 0.0)) > 0.0 for value in row.get("scores", {}).values())
        if not has_score and row["power"] <= 0 and row["missionControl"] <= 0:
            continue
        rows.append(clean_numbers(row, 6))
    return rows


def hab_module_upgrade_rows(
    indexed: IndexedState,
    templates_dir: Path | None,
    hab: dict[str, Any],
    records: list[dict[str, Any]],
    faction_id: int,
    faction: dict[str, Any],
    projected_power: dict[str, int],
    mission_control_available: float,
    topbar: dict[str, Any],
) -> list[dict[str, Any]]:
    hab_module_templates = load_hab_module_catalog()
    location_catalog = load_location_catalog()
    body_templates = location_catalog.body_templates
    orbit_templates = location_catalog.orbit_templates
    runtime_catalogs = calculation_catalogs(indexed, "hab-plan")
    effect_templates = runtime_catalogs.effects
    trait_templates = runtime_catalogs.traits
    _, councilor_by_id = councilor_summary_maps(indexed, trait_templates)
    effect_contexts = faction_effect_contexts(indexed, faction_id)
    mining_rate = faction_mining_rate(indexed, faction)
    scarcity_weights = resource_scarcity_weights(topbar)
    templates_by_prior: dict[str, list[dict[str, Any]]] = {}
    for template in hab_module_templates.values():
        prior_name = template.get("upgradesFromName")
        if prior_name:
            templates_by_prior.setdefault(str(prior_name), []).append(template)

    rows: list[dict[str, Any]] = []
    current_tier = int(as_float(hab.get("tier"), 0.0))
    target_tier = min(max(current_tier + 1, 1), 3)
    for record in records:
        if not hab_module_active_record(record):
            continue
        for template in templates_by_prior.get(str(record.get("templateName") or ""), []):
            module_counts = hab_module_counts(records)
            prior_name = str(record.get("templateName") or "")
            module_counts[prior_name] = max(module_counts.get(prior_name, 0) - 1, 0)
            reasons = module_unmet_requirements(
                indexed,
                template,
                hab,
                faction,
                target_tier,
                module_counts,
                body_templates,
                hab_module_templates,
            )
            reasons = [reason for reason in reasons if reason != "core module"]
            if reasons:
                continue
            row = module_candidate_row(
                indexed,
                hab,
                records,
                faction,
                template,
                projected_power,
                mission_control_available,
                effect_contexts,
                effect_templates,
                mining_rate,
                scarcity_weights,
                councilor_by_id,
                body_templates,
                orbit_templates,
                prior_record=record,
            )
            row["sectorNum"] = record.get("sectorNum")
            row["slot"] = record.get("slot")
            row["isCoreUpgrade"] = bool(template.get("coreModule"))
            rows.append(clean_numbers(row, 6))
    return rows


def sorted_candidates(candidates: list[dict[str, Any]], focus: str, top: int) -> list[dict[str, Any]]:
    return sorted(
        candidates,
        key=lambda row: (
            not candidate_affordable(row),
            -as_float((row.get("scores") or {}).get(focus), 0.0),
            not bool(row.get("fitsCurrentProjectedPower")),
            -int(as_float(row.get("tier"), 0.0)),
            -as_float((row.get("scores") or {}).get("balanced"), 0.0),
            str(row.get("display") or row.get("template")),
        ),
    )[:top]


def candidate_focus_score(candidate: dict[str, Any] | None, focus: str) -> float:
    if not candidate:
        return 0.0
    return as_float((candidate.get("scores") or {}).get(focus), 0.0)


def opportunity_cost_baseline(candidates: list[dict[str, Any]], focus: str) -> dict[str, Any]:
    affordable = [candidate for candidate in candidates if candidate_affordable(candidate)]
    if not affordable:
        return {"template": None, "display": None, "score": 0.0}
    best = max(
        affordable,
        key=lambda candidate: (
            candidate_focus_score(candidate, focus),
            candidate_focus_score(candidate, "balanced"),
            int(as_float(candidate.get("tier"), 0.0)),
            str(candidate.get("display") or candidate.get("template")),
        ),
    )
    score = max(candidate_focus_score(best, focus), 0.0)
    if score <= 0.0:
        return {"template": None, "display": None, "score": 0.0}
    return {
        "template": best.get("template"),
        "display": best.get("display"),
        "score": score,
    }


def opportunity_cost_for_score(score: float, baseline_score: float) -> float:
    return max(baseline_score - score, 0.0)


def opportunity_costs_for_candidate(candidate: dict[str, Any], baselines: dict[str, dict[str, Any]]) -> dict[str, Any]:
    costs: dict[str, Any] = {}
    for focus, baseline in baselines.items():
        baseline_score = as_float(baseline.get("score"), 0.0)
        score = candidate_focus_score(candidate, focus)
        cost = opportunity_cost_for_score(score, baseline_score)
        costs[focus] = {
            "bestAlternative": baseline,
            "score": score,
            "cost": cost,
            "scoreAfterOpportunityCost": score - cost,
        }
    return costs


def annotate_candidate_opportunity_costs(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    baselines = {focus: opportunity_cost_baseline(candidates, focus) for focus in HAB_PLAN_FOCUS_CHOICES}
    for candidate in candidates:
        candidate["opportunityCosts"] = clean_numbers(opportunity_costs_for_candidate(candidate, baselines), 6)
    return candidates


def power_candidates(candidates: list[dict[str, Any]], top: int) -> list[dict[str, Any]]:
    return sorted(
        [
            candidate
            for candidate in candidates
            if as_float(candidate.get("powerChange") if candidate.get("isUpgrade") else candidate.get("power"), 0.0) > 0.0
        ],
        key=lambda row: (
            not candidate_affordable(row),
            -as_float(row.get("powerChange") if row.get("isUpgrade") else row.get("power"), 0.0),
            -int(as_float(row.get("tier"), 0.0)),
            str(row.get("display") or row.get("template")),
        ),
    )[:top]


def candidate_affordable(row: dict[str, Any]) -> bool:
    construction = row.get("construction") if isinstance(row.get("construction"), dict) else {}
    if "affordableByCurrentStockpile" in construction:
        return bool(construction.get("affordableByCurrentStockpile"))
    return bool(row.get("affordableByTemplateWeights", True))


def payback_candidates(candidates: list[dict[str, Any]], top: int) -> list[dict[str, Any]]:
    return sorted(
        [
            candidate
            for candidate in candidates
            if (candidate.get("breakEven") or {}).get("breakEvenFromStart_months") is not None
        ],
        key=lambda row: (
            not candidate_affordable(row),
            as_float((row.get("breakEven") or {}).get("breakEvenFromStart_months"), float("inf")),
            -as_float((row.get("breakEven") or {}).get("monthlyNetMarketEquivalentMoney"), 0.0),
            str(row.get("display") or row.get("template")),
        ),
    )[:top]


def monthly_delta_times(delta: dict[str, dict[str, float]], count: int) -> dict[str, dict[str, float]]:
    result: dict[str, dict[str, float]] = {}
    for resource, row in delta.items():
        if not isinstance(row, dict):
            continue
        result[resource] = {
            key: as_float(value, 0.0) * count
            for key, value in row.items()
            if key in {"income", "support", "net"}
        }
    return result


def add_monthly_delta(target: dict[str, dict[str, float]], delta: dict[str, dict[str, float]], count: int = 1) -> None:
    for resource, row in monthly_delta_times(delta, count).items():
        target_row = target.setdefault(resource, {"income": 0.0, "support": 0.0, "net": 0.0})
        for key, value in row.items():
            target_row[key] = as_float(target_row.get(key), 0.0) + value


def suggested_fill_entry(
    candidate: dict[str, Any],
    count: int,
    reason: str,
    focus: str,
    baseline_score: float,
) -> dict[str, Any]:
    score_each = candidate_focus_score(candidate, focus)
    opportunity_cost_each = opportunity_cost_for_score(score_each, baseline_score)
    return {
        "count": count,
        "template": candidate.get("template"),
        "display": candidate.get("display"),
        "reason": reason,
        "tier": candidate.get("tier"),
        "powerEach": candidate.get("power"),
        "powerTotal": int(as_float(candidate.get("power"), 0.0)) * count,
        "missionControlEach": candidate.get("missionControl"),
            "missionControlTotal": int(as_float(candidate.get("missionControl"), 0.0)) * count,
            "constructionEach": candidate.get("construction"),
            "breakEvenEach": candidate.get("breakEven"),
            "monthlyDeltaTotal": monthly_delta_times(candidate.get("monthlyDelta") or {}, count),
        "scoresEach": candidate.get("scores"),
        "opportunityCost": {
            "focus": focus,
            "scoreEach": score_each,
            "bestAlternativeScoreEach": baseline_score,
            "costEach": opportunity_cost_each,
            "costTotal": opportunity_cost_each * count,
            "scoreAfterOpportunityCostTotal": (score_each - opportunity_cost_each) * count,
        },
    }


def suggested_hab_fill(
    candidates: list[dict[str, Any]],
    slots: int,
    focus: str,
    projected_power: int,
    mc_available: float,
) -> dict[str, Any]:
    if slots <= 0:
        return {
            "slotsRequested": slots,
            "slotsFilled": 0,
            "unfilledSlots": 0,
            "projectedPowerNetAfter": projected_power,
            "missionControlAvailableAfter": mc_available,
            "monthlyDeltaTotal": {},
            "moduleCounts": [],
            "method": "no planned empty slots",
        }

    affordable_candidates = [candidate for candidate in candidates if candidate_affordable(candidate)]
    focus_pool = sorted_candidates(affordable_candidates, focus, len(affordable_candidates))
    support_pool = power_candidates(affordable_candidates, len(affordable_candidates))
    opportunity_baseline = opportunity_cost_baseline(affordable_candidates, focus)
    baseline_score = as_float(opportunity_baseline.get("score"), 0.0)
    best_plan: dict[str, Any] | None = None

    for focus_candidate in focus_pool[:20]:
        focus_limit = 1 if focus_candidate.get("onePerHab") else slots
        focus_power = int(as_float(focus_candidate.get("power"), 0.0))
        focus_mc = int(as_float(focus_candidate.get("missionControl"), 0.0))
        focus_score = as_float((focus_candidate.get("scores") or {}).get(focus), 0.0)
        for focus_count in range(1, focus_limit + 1):
            remaining_slots = slots - focus_count
            support_options: list[tuple[dict[str, Any] | None, int]] = [(None, 0)]
            for support_candidate in support_pool[:20]:
                if support_candidate.get("template") == focus_candidate.get("template"):
                    continue
                support_limit = 1 if support_candidate.get("onePerHab") else remaining_slots
                support_options.extend((support_candidate, count) for count in range(1, support_limit + 1))

            for support_candidate, support_count in support_options:
                if support_count > remaining_slots:
                    continue
                support_power = int(as_float((support_candidate or {}).get("power"), 0.0))
                support_mc = int(as_float((support_candidate or {}).get("missionControl"), 0.0))
                power_after = projected_power + focus_power * focus_count + support_power * support_count
                mc_after = mc_available + focus_mc * focus_count + support_mc * support_count
                if power_after < 0 or mc_after < 0:
                    continue
                slots_filled = focus_count + support_count
                support_score = as_float(((support_candidate or {}).get("scores") or {}).get(focus), 0.0)
                plan_score = (
                    focus_score * focus_count
                    + support_score * support_count
                )
                opportunity_cost = max(baseline_score * slots_filled - plan_score, 0.0)
                unfilled_opportunity_cost = baseline_score * max(slots - slots_filled, 0)
                score_after_opportunity_cost = plan_score - opportunity_cost
                plan = {
                    "score": plan_score,
                    "opportunityCost": opportunity_cost,
                    "unfilledOpportunityCost": unfilled_opportunity_cost,
                    "scoreAfterOpportunityCost": score_after_opportunity_cost,
                    "slotsFilled": slots_filled,
                    "powerAfter": power_after,
                    "mcAfter": mc_after,
                    "focusCandidate": focus_candidate,
                    "focusCount": focus_count,
                    "supportCandidate": support_candidate,
                    "supportCount": support_count,
                }
                if best_plan is None or (
                    plan["scoreAfterOpportunityCost"],
                    plan["score"],
                    plan["focusCount"],
                    -plan["supportCount"],
                    plan["powerAfter"],
                ) > (
                    best_plan["scoreAfterOpportunityCost"],
                    best_plan["score"],
                    best_plan["focusCount"],
                    -best_plan["supportCount"],
                    best_plan["powerAfter"],
                ):
                    best_plan = plan

    if best_plan is None:
        return {
            "slotsRequested": slots,
            "slotsFilled": 0,
            "unfilledSlots": slots,
            "projectedPowerNetAfter": projected_power,
            "missionControlAvailableAfter": mc_available,
            "monthlyDeltaTotal": {},
            "moduleCounts": [],
            "method": "no feasible candidate set under projected power and MC",
        }

    monthly_total: dict[str, dict[str, float]] = {}
    entries = [
        suggested_fill_entry(
            best_plan["focusCandidate"],
            best_plan["focusCount"],
            f"top {focus} score",
            focus,
            baseline_score,
        ),
    ]
    add_monthly_delta(monthly_total, best_plan["focusCandidate"].get("monthlyDelta") or {}, best_plan["focusCount"])
    if best_plan["supportCandidate"] and best_plan["supportCount"]:
        entries.append(
            suggested_fill_entry(
                best_plan["supportCandidate"],
                best_plan["supportCount"],
                "power support for selected fill",
                focus,
                baseline_score,
            )
        )
        add_monthly_delta(monthly_total, best_plan["supportCandidate"].get("monthlyDelta") or {}, best_plan["supportCount"])

    return clean_numbers(
        {
            "slotsRequested": slots,
            "slotsFilled": best_plan["slotsFilled"],
            "unfilledSlots": slots - best_plan["slotsFilled"],
            "projectedPowerNetAfter": best_plan["powerAfter"],
            "missionControlAvailableAfter": best_plan["mcAfter"],
            "monthlyDeltaTotal": monthly_total,
            "moduleCounts": entries,
            "score": {
                "focus": focus,
                "gross": best_plan["score"],
                "opportunityCost": best_plan["opportunityCost"],
                "unfilledSlotOpportunityCost": best_plan["unfilledOpportunityCost"],
                "totalOpportunityCostIncludingUnfilledSlots": (
                    best_plan["opportunityCost"] + best_plan["unfilledOpportunityCost"]
                ),
                "afterOpportunityCost": best_plan["scoreAfterOpportunityCost"],
                "afterOpportunityCostIncludingUnfilledSlots": (
                    best_plan["scoreAfterOpportunityCost"] - best_plan["unfilledOpportunityCost"]
                ),
                "bestAlternativePerSlot": opportunity_baseline,
            },
            "method": "single focus module type plus optional single power-support type, ranked by focus score after slot opportunity cost",
        },
        6,
    )


def hab_plan_row(
    indexed: IndexedState,
    templates_dir: Path | None,
    hab_id: int,
    hab: dict[str, Any],
    faction_id: int,
    faction: dict[str, Any],
    focus: str,
    top: int,
    topbar: dict[str, Any],
) -> dict[str, Any]:
    hab_module_templates = load_hab_module_catalog()
    location_catalog = load_location_catalog()
    body_templates = location_catalog.body_templates
    orbit_templates = location_catalog.orbit_templates
    records = hab_module_records(indexed, hab, hab_module_templates)
    slots = hab_slot_summary(records)
    upgrade = hab_upgrade_info(records)
    current_tier = int(as_float(hab.get("tier"), 0.0)) or None
    target_tier = int(as_float(upgrade.get("targetTier"), 0.0)) or current_tier or 1
    planned_slots = hab_planned_empty_slots(slots, upgrade, current_tier)
    projected_power = hab_projected_power_summary(
        records,
        indexed=indexed,
        hab=hab,
        body_templates=body_templates,
        orbit_templates=orbit_templates,
    )
    mc_available = mission_control_available_for_planning(topbar)
    candidates = hab_module_candidate_rows(
        indexed,
        templates_dir,
        hab,
        records,
        faction_id,
        faction,
        target_tier,
        projected_power,
        mc_available,
        topbar,
    )
    upgrade_candidates = hab_module_upgrade_rows(
        indexed,
        templates_dir,
        hab,
        records,
        faction_id,
        faction,
        projected_power,
        mc_available,
        topbar,
    )
    annotate_candidate_opportunity_costs(candidates)
    annotate_candidate_opportunity_costs(upgrade_candidates)
    return {
        "id": hab_id,
        "display": hab.get("displayName"),
        "habType": hab.get("habType"),
        "tier": current_tier,
        "targetTier": target_tier,
        "location": hab_location_summary(indexed, templates_dir, hab),
        "upgrade": upgrade,
        "slots": {
            "current": slots,
            "planning": planned_slots,
        },
        "power": {
            "active": hab_power_summary(
                records,
                indexed=indexed,
                hab=hab,
                body_templates=body_templates,
                orbit_templates=orbit_templates,
            ),
            "projectedAfterCurrentQueue": projected_power,
        },
        "moduleCounts": hab_module_counts(records),
        "underConstruction": [
            {
                "sectorNum": record.get("sectorNum"),
                "slot": record.get("slot"),
                "template": record.get("templateName"),
                "display": record.get("display"),
                "priorTemplate": record.get("priorTemplateName"),
                "completionDate": (record.get("state") or {}).get("completionDate"),
                "buildCost": (record.get("state") or {}).get("buildCost"),
                "baseBuildDuration_days": (record.get("state") or {}).get("baseBuildDuration_days"),
                "appliedBuildConstructionBonus": (record.get("state") or {}).get("appliedBuildConstructionBonus"),
            }
            for record in records
            if hab_module_okay(record) and not record.get("completed")
        ],
        "candidateSummary": {
            "count": len(candidates),
            "topBalanced": sorted_candidates(candidates, "balanced", top),
            "topResearch": sorted_candidates(candidates, "research", top),
            "topProjects": sorted_candidates(candidates, "projects", top),
            "topCategoryBonus": sorted_candidates(candidates, "category-bonus", top),
            "topResources": sorted_candidates(candidates, "resources", top),
            "topPower": power_candidates(candidates, top),
            "topPayback": payback_candidates(candidates, top),
        },
        "upgradeSummary": {
            "count": len(upgrade_candidates),
            "tierUpgradeCandidate": next((row for row in upgrade_candidates if row.get("isCoreUpgrade")), None),
            "topPayback": payback_candidates(upgrade_candidates, top),
            "topResources": sorted_candidates(upgrade_candidates, "resources", top),
            "topPower": power_candidates(upgrade_candidates, top),
        },
        "suggestedFill": suggested_hab_fill(
            candidates,
            int(planned_slots.get("plannedEmpty", 0)),
            focus,
            int(projected_power.get("net", 0)),
            mc_available,
        ),
    }


def calculate_hab_plan(
    indexed: IndexedState,
    templates_dir: Path | None,
    faction_name: str | None = None,
    hab_name: str | None = None,
    upgrading_to_tier: int | None = None,
    include_all: bool = False,
    focus: str = "balanced",
    top: int = 8,
) -> dict[str, Any]:
    faction_id, faction = find_faction_state(indexed, faction_name)
    topbar = calculate_topbar(indexed, templates_dir, faction.get("templateName"), include_details=False)
    if hab_name:
        found = match_raw_state(indexed, "TIHabState", hab_name)
        if not found or found[0] is None:
            raise UserInputError(f"Hab not found: {hab_name}")
        habs = [(found[0], found[1])]
    else:
        habs = faction_hab_states(indexed, faction)

    rows = [
        hab_plan_row(indexed, templates_dir, hab_id, hab, faction_id, faction, focus, top, topbar)
        for hab_id, hab in habs
        if ref_id(hab.get("faction")) == faction_id
    ]
    if upgrading_to_tier is not None:
        rows = [row for row in rows if int(as_float(row.get("targetTier"), 0.0)) == upgrading_to_tier and row["upgrade"].get("isUpgrading")]
    if not include_all:
        rows = [row for row in rows if int(row["slots"]["planning"].get("plannedEmpty", 0)) > 0]
    rows.sort(
        key=lambda row: (
            -int(row["slots"]["planning"].get("plannedEmpty", 0)),
            str(row.get("display") or ""),
        )
    )

    return clean_numbers(
        {
            "faction": faction_brief(faction_id, faction),
            "focus": focus,
            "filters": {
                "hab": hab_name,
                "upgradingToTier": upgrading_to_tier,
                "includeAll": include_all,
                "top": top,
                "returnedHabs": len(rows),
            },
            "scoreModel": {
                "research": "monthly Research net only; Projects and tech category bonuses are not folded into this score",
                "projects": "monthly Projects net only",
                "category-bonus": "raw sum of techBonuses across research categories",
                "resources": "monthly resource net weighted by current scarcity heuristic",
                "balanced": {
                    "formula": "research + resources",
                    "weights": {"research": 1.0, "resources": 1.0, "projects": 0.0, "category-bonus": 0.0},
                },
                "opportunityCost": {
                    "formula": "max(max(best affordable candidate score for focus, 0) - candidate score for focus, 0) per occupied slot",
                    "suggestedFill": "plans are ranked by gross focus score minus slot opportunity cost",
                    "unfilledSlots": "reported separately as foregone best-alternative score, but not charged when ranking occupied-module choices",
                },
            },
            "factionConstraints": {
                "missionControl": topbar.get("resources", {}).get("MissionControl") if isinstance(topbar.get("resources"), dict) else None,
                "monthlyResourceDeltas": {
                    resource: row.get("monthly")
                    for resource, row in (topbar.get("resources") or {}).items()
                    if isinstance(row, dict) and resource in {"Money", "Boost", "Water", "Volatiles", "Metals", "NobleMetals", "Fissiles"}
                },
            },
            "habs": rows,
            "sourceNotes": [
                "This is a planning model, not an exact in-game optimizer.",
                "plannedEmpty includes currently usable empty slots plus locked empty placeholders only when the core is upgrading to a higher tier.",
                "Candidates are filtered by known project unlocks, target tier, hab type, one-per-hab rules, and simple location-only special rules.",
                "candidateSummary.topPower and upgradeSummary.topPower are comparison shortlists, not recommendations to add generation; only suggestedFill entries labeled power support indicate a habitat-local power need.",
                "Scores are separated by output type: research is Research/month, projects is Projects/month, category-bonus is raw tech bonus sum, resources is scarcity-weighted net resource flow.",
                "construction.materials applies module mass, gravity scaling, solar-mirror distance scaling, irradiated-location extra metals, helium-3 fissiles substitution, and the two-thirds upgrade discount.",
                "construction.constructionTime_Days includes active hab construction-speed modifiers and the in-progress core completion minimum when applicable.",
                "breakEven values use current market purchase prices for Money and purchasable space resources; MC, research, projects, influence, operations, strategic unlocks, boost substitution, and Earth transfer time are excluded.",
            ],
        },
        6,
    )
