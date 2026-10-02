"""Research project consequences, module unlocks and resource tradeoffs."""

from __future__ import annotations

from ti_parser_errors import UserInputError

from pathlib import Path
from typing import Any

from ti_parser_config import (
    DAYS_PER_YEAR,
    DEFAULT_GLOBAL_CONFIG,
    HAB_MONTHLY_RESOURCES,
    PROJECT_ANALYSIS_MODULE_SAMPLE_COUNTS,
    PROJECT_ANALYSIS_SORT_CHOICES,
)
from ti_parser_core import (
    CalculationDependency,
    CalculationDependencyError,
    IndexedState,
    as_float,
    clean_numbers,
    faction_effect_contexts,
    find_faction_state,
    first_value,
    load_location_catalog,
    ref_id,
)
from ti_parser_hab_construction import (
    hab_planned_empty_slots,
    hab_projected_power_summary,
    hab_upgrade_info,
    module_build_cost_map,
    module_unmet_requirements,
    resource_scarcity_weights,
)
from ti_parser_hab_plan import (
    candidate_affordable,
    module_balanced_score,
    module_candidate_row,
    module_category_bonus_score,
    module_project_score,
    module_research_score,
    module_resource_score,
    monthly_delta_times,
    tech_bonus_map_for_template,
)
from ti_parser_hab_ui import hab_location_summary
from ti_parser_research import (
    calculate_research_ui,
    eta_from_daily,
    faction_base_research_daily,
    faction_category_modifier_components,
    faction_project_allowed,
    faction_project_slots,
    faction_research_weights,
    faction_total_research_weights,
    load_research_templates,
    multiple_facilities_multiplier,
    project_facility_counts,
    project_progress_by_slot,
    project_template_cost,
    template_display,
)
from ti_parser_runtime import (
    calculation_catalogs,
    councilor_summary_maps,
    faction_brief,
    faction_hab_states,
    faction_mining_rate,
    hab_module_counts,
    hab_module_records,
    hab_slot_summary,
    hab_template_income,
    hab_template_special_rules,
    hab_template_support,
    required_catalog_row,
)
from ti_parser_topbar import (
    calculate_topbar,
    mission_control_available_for_planning,
)


def project_progress_entries_by_name(faction: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for progress in faction.get("currentProjectProgress") if isinstance(faction.get("currentProjectProgress"), list) else []:
        if not isinstance(progress, dict):
            continue
        template_name = progress.get("projectTemplateName")
        if template_name:
            result.setdefault(str(template_name), []).append(progress)
    return result


def active_project_names(faction: dict[str, Any]) -> set[str]:
    active_slots = set(faction_project_slots(faction))
    names: set[str] = set()
    for slot, progress in project_progress_by_slot(faction).items():
        if slot in active_slots and progress.get("projectTemplateName"):
            names.add(str(progress.get("projectTemplateName")))
    return names


def project_analysis_candidate_names(
    faction: dict[str, Any],
    project_templates: dict[str, dict[str, Any]],
    include_active: bool = False,
) -> list[str]:
    available = faction.get("availableProjectNames") if isinstance(faction.get("availableProjectNames"), list) else []
    names = {str(name) for name in available if name}
    active_names = active_project_names(faction)
    for name, entries in project_progress_entries_by_name(faction).items():
        if include_active or name not in active_names:
            names.add(name)
    if include_active:
        names.update(active_names)

    finished = set(faction.get("finishedProjectNames") if isinstance(faction.get("finishedProjectNames"), list) else [])
    filtered = []
    for name in names:
        template = project_templates.get(name)
        if not isinstance(template, dict):
            raise CalculationDependencyError(
                CalculationDependency(
                    kind="research-project",
                    name=name,
                    context="project-analysis.candidates",
                    scenario=None,
                    reason="save candidate is absent from the packaged research catalog",
                )
            )
        if template.get("disable"):
            continue
        if name in finished and not template.get("repeatable"):
            continue
        if name in active_names and not include_active:
            continue
        filtered.append(name)
    return sorted(filtered, key=lambda item: str(template_display(item, project_templates.get(item, {})) or item))


def project_candidate_status(faction: dict[str, Any], project_name: str) -> dict[str, Any]:
    active_slots = set(faction_project_slots(faction))
    entries = project_progress_entries_by_name(faction).get(project_name, [])
    slots = [int(as_float(entry.get("slot"), -1.0)) for entry in entries]
    active = [slot for slot in slots if slot in active_slots]
    stored = [slot for slot in slots if slot not in active_slots]
    accumulated = max((as_float(entry.get("accumulatedResearch"), 0.0) for entry in entries), default=0.0)
    if active:
        status = "active"
    elif stored:
        status = "stored"
    else:
        status = "available"
    return {
        "status": status,
        "slots": slots,
        "activeSlots": active,
        "storedSlots": stored,
        "accumulatedResearch": accumulated,
    }


def default_project_analysis_slot(faction: dict[str, Any]) -> int | None:
    slots = faction_project_slots(faction)
    return slots[-1] if slots else None


def active_slots_with_hypothetical_project_category(
    indexed: IndexedState,
    faction: dict[str, Any],
    tech_templates: dict[str, dict[str, Any]],
    project_templates: dict[str, dict[str, Any]],
    category: str | None,
    project_slot: int,
) -> int:
    if not category:
        return 0
    weights = faction_research_weights(faction)
    count = 0
    global_research = first_value(indexed, "TIGlobalResearchState") or {}
    tech_progress = global_research.get("techProgress") if isinstance(global_research.get("techProgress"), list) else []
    for slot in range(3):
        if weights[slot] <= 0.0 or slot >= len(tech_progress):
            continue
        progress = tech_progress[slot] if isinstance(tech_progress[slot], dict) else {}
        template_name = progress.get("techTemplateName")
        if not template_name:
            continue
        template = required_catalog_row(
            indexed,
            tech_templates,
            "research-tech",
            template_name,
            "project-analysis.hypothetical.active-tech",
        )
        if template.get("techCategory") == category:
            count += 1

    projects = project_progress_by_slot(faction)
    for slot in range(3, 6):
        if weights[slot] <= 0.0 or not faction_project_allowed(faction, slot):
            continue
        if slot == project_slot:
            slot_category = category
        else:
            progress = projects.get(slot)
            template_name = progress.get("projectTemplateName") if isinstance(progress, dict) else None
            if not template_name:
                continue
            template = required_catalog_row(
                indexed,
                project_templates,
                "research-project",
                template_name,
                "project-analysis.hypothetical.active-project",
            )
            slot_category = template.get("techCategory")
        if slot_category == category:
            count += 1
    return count


def hypothetical_project_category_modifier(
    indexed: IndexedState,
    faction: dict[str, Any],
    trait_templates: dict[str, dict[str, Any]],
    org_templates: dict[str, dict[str, Any]],
    hab_module_templates: dict[str, dict[str, Any]],
    utility_module_templates: dict[str, dict[str, Any]],
    tech_templates: dict[str, dict[str, Any]],
    project_templates: dict[str, dict[str, Any]],
    category: str | None,
    project_slot: int,
) -> dict[str, Any]:
    components = faction_category_modifier_components(
        indexed,
        faction,
        trait_templates,
        org_templates,
        hab_module_templates,
        utility_module_templates,
        category,
    )
    active_same_category = active_slots_with_hypothetical_project_category(
        indexed,
        faction,
        tech_templates,
        project_templates,
        category,
        project_slot,
    )
    penalty_power = max(active_same_category - 1, 0)
    distributed = components["sum"] * (DEFAULT_GLOBAL_CONFIG["categoryBonusPenaltyPerExtraSlot"] ** penalty_power)
    return {
        "category": category,
        "components": components,
        "activeSlotsWithCategory": active_same_category,
        "extraSlotPenaltyPower": penalty_power,
        "distributed": distributed,
    }


def hypothetical_project_points_to_slot(
    indexed: IndexedState,
    faction: dict[str, Any],
    project_template: dict[str, Any],
    slot: int,
    base_daily: float,
    tech_templates: dict[str, dict[str, Any]],
    project_templates: dict[str, dict[str, Any]],
    trait_templates: dict[str, dict[str, Any]],
    org_templates: dict[str, dict[str, Any]],
    hab_module_templates: dict[str, dict[str, Any]],
    utility_module_templates: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    weights = faction_research_weights(faction)
    total_weights = faction_total_research_weights(faction)
    if (
        slot < 0
        or slot >= len(weights)
        or total_weights <= 0.0
        or weights[slot] <= 0.0
        or not faction_project_allowed(faction, slot)
    ):
        return {"daily": 0.0, "weight": 0.0, "weightFraction": 0.0, "category": project_template.get("techCategory"), "modifiers": None}

    category = project_template.get("techCategory")
    category_modifier = hypothetical_project_category_modifier(
        indexed,
        faction,
        trait_templates,
        org_templates,
        hab_module_templates,
        utility_module_templates,
        tech_templates,
        project_templates,
        category,
        slot,
    )
    project_facilities = project_facility_counts(
        indexed,
        faction,
        trait_templates,
        hab_module_templates,
        org_templates=org_templates,
    )
    project_bonus = multiple_facilities_multiplier(project_facilities)
    effective_daily = base_daily * (1.0 + as_float(category_modifier["distributed"], 0.0) + project_bonus)
    weight_fraction = weights[slot] / total_weights
    return {
        "daily": effective_daily * weight_fraction,
        "weight": weights[slot],
        "weightFraction": weight_fraction,
        "category": category,
        "modifiers": {
            "category": category_modifier,
            "projectFacilities": project_facilities,
            "projectFacilityBonus": project_bonus,
            "effectiveMultiplier": 1.0 + as_float(category_modifier["distributed"], 0.0) + project_bonus,
        },
    }


def module_template_static_monthly_delta(template: dict[str, Any]) -> dict[str, dict[str, float]]:
    delta: dict[str, dict[str, float]] = {}
    for resource in HAB_MONTHLY_RESOURCES:
        income = hab_template_income(resource, template)
        support = hab_template_support(resource, template, include_crew_support=True)
        net = income - support
        if income or support or net:
            delta[resource] = {"income": income, "support": support, "net": net}
    return delta


def project_resource_grant_map(template: dict[str, Any]) -> dict[str, float]:
    grants: dict[str, float] = {}
    for grant in template.get("resourcesGranted") if isinstance(template.get("resourcesGranted"), list) else []:
        if not isinstance(grant, dict):
            continue
        resource = grant.get("resource")
        if not resource:
            continue
        grants[str(resource)] = grants.get(str(resource), 0.0) + as_float(grant.get("value"), 0.0)
    return grants


def resource_grant_score(grants: dict[str, float], scarcity_weights: dict[str, float]) -> float:
    return sum(amount * scarcity_weights.get(resource, 1.0) for resource, amount in grants.items())


def project_finished_faction_view(faction: dict[str, Any], project_name: str) -> dict[str, Any]:
    result = dict(faction)
    finished = list(faction.get("finishedProjectNames") if isinstance(faction.get("finishedProjectNames"), list) else [])
    if project_name not in finished:
        finished.append(project_name)
    result["finishedProjectNames"] = finished
    return result


def project_unlocked_module_templates(
    project_name: str,
    hab_module_templates: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    modules = [
        template
        for template in hab_module_templates.values()
        if template.get("requiredProjectName") == project_name and not template.get("disable")
    ]
    modules.sort(key=lambda template: str(template_display(str(template.get("dataName")), template) or template.get("dataName")))
    return modules


def module_static_analysis(template: dict[str, Any], scarcity_weights: dict[str, float]) -> dict[str, Any]:
    monthly_delta = module_template_static_monthly_delta(template)
    research_score = module_research_score(monthly_delta)
    project_score = module_project_score(monthly_delta)
    category_bonus_score = module_category_bonus_score(template)
    resource_score = module_resource_score(monthly_delta, scarcity_weights)
    return clean_numbers(
        {
            "template": template.get("dataName"),
            "display": template_display(str(template.get("dataName")), template),
            "tier": int(as_float(template.get("tier"), 0.0)),
            "habType": template.get("habType") or "Any",
            "power": int(as_float(template.get("power"), 0.0)),
            "crew": int(as_float(template.get("crew"), 0.0)),
            "missionControl": int(as_float(template.get("missionControl"), 0.0)),
            "buildTime_Days": as_float(template.get("buildTime_Days"), 0.0),
            "buildCostTemplateWeights": module_build_cost_map(template),
            "monthlyDeltaBeforeHabModifiers": monthly_delta,
            "techBonuses": tech_bonus_map_for_template(template),
            "specialRules": hab_template_special_rules(template),
            "scores": {
                "research": research_score,
                "projects": project_score,
                "category-bonus": category_bonus_score,
                "resources": resource_score,
                "balanced": module_balanced_score(research_score, resource_score),
            },
        },
        6,
    )


def module_count_sample(candidate: dict[str, Any] | None, count: int, planned_slots: int) -> dict[str, Any]:
    if not candidate:
        return {"count": count, "possibleWithPlannedSlots": False}
    scores = candidate.get("scores") if isinstance(candidate.get("scores"), dict) else {}
    return clean_numbers(
        {
            "count": count,
            "possibleWithPlannedSlots": count <= planned_slots,
            "assumption": "repeats the best current hab option and does not reserve extra power-support modules",
            "powerTotal": int(as_float(candidate.get("power"), 0.0)) * count,
            "missionControlTotal": int(as_float(candidate.get("missionControl"), 0.0)) * count,
            "buildTime_Days": candidate.get("buildTime_Days"),
            "monthlyDeltaTotal": monthly_delta_times(candidate.get("monthlyDelta") or {}, count),
            "scoresTotal": {name: as_float(value, 0.0) * count for name, value in scores.items()},
        },
        6,
    )


def prospective_module_unlocks_for_project(
    indexed: IndexedState,
    templates_dir: Path | None,
    faction_id: int,
    faction: dict[str, Any],
    project_name: str,
    hab_module_templates: dict[str, dict[str, Any]],
    topbar: dict[str, Any],
    top: int,
) -> list[dict[str, Any]]:
    unlocked_modules = project_unlocked_module_templates(project_name, hab_module_templates)
    if not unlocked_modules:
        return []

    location_catalog = load_location_catalog()
    body_templates = location_catalog.body_templates
    orbit_templates = location_catalog.orbit_templates
    runtime_catalogs = calculation_catalogs(indexed, "project-analysis")
    effect_templates = runtime_catalogs.effects
    trait_templates = runtime_catalogs.traits
    _, councilor_by_id = councilor_summary_maps(indexed, trait_templates)
    effect_contexts = faction_effect_contexts(indexed, faction_id)
    mining_rate = faction_mining_rate(indexed, faction)
    scarcity_weights = resource_scarcity_weights(topbar)
    mc_available = mission_control_available_for_planning(topbar)
    faction_with_project = project_finished_faction_view(faction, project_name)
    habs = [(hab_id, hab) for hab_id, hab in faction_hab_states(indexed, faction) if ref_id(hab.get("faction")) == faction_id]

    analyses: list[dict[str, Any]] = []
    for template in unlocked_modules:
        rows: list[dict[str, Any]] = []
        blocked_reasons: dict[str, int] = {}
        eligible_habs = 0
        planned_slots = 0
        current_slots = 0
        power_fit_slots = 0
        for hab_id, hab in habs:
            records = hab_module_records(indexed, hab, hab_module_templates)
            slots = hab_slot_summary(records)
            upgrade = hab_upgrade_info(records)
            current_tier = int(as_float(hab.get("tier"), 0.0)) or None
            target_tier = int(as_float(upgrade.get("targetTier"), 0.0)) or current_tier or 1
            planning = hab_planned_empty_slots(slots, upgrade, current_tier)
            reasons = module_unmet_requirements(
                indexed,
                template,
                hab,
                faction_with_project,
                target_tier,
                hab_module_counts(records),
                body_templates,
                hab_module_templates,
            )
            if reasons:
                for reason in reasons:
                    blocked_reasons[reason] = blocked_reasons.get(reason, 0) + 1
                continue
            eligible_habs += 1
            hab_planned_slots = int(planning.get("plannedEmpty", 0))
            hab_current_slots = int(planning.get("currentUsableEmpty", 0))
            planned_slots += hab_planned_slots
            current_slots += hab_current_slots
            if hab_planned_slots <= 0:
                continue
            projected_power = hab_projected_power_summary(
                records,
                indexed=indexed,
                hab=hab,
                body_templates=body_templates,
                orbit_templates=orbit_templates,
            )
            row = module_candidate_row(
                indexed,
                hab,
                records,
                faction_with_project,
                template,
                projected_power,
                mc_available,
                effect_contexts,
                effect_templates,
                mining_rate,
                scarcity_weights,
                councilor_by_id,
                body_templates,
                orbit_templates,
            )
            row["hab"] = {"id": hab_id, "display": hab.get("displayName"), "plannedEmptySlots": hab_planned_slots}
            row["location"] = hab_location_summary(indexed, templates_dir, hab)
            rows.append(clean_numbers(row, 6))
            if row.get("fitsCurrentProjectedPower"):
                power_fit_slots += hab_planned_slots

        rows.sort(
            key=lambda row: (
                not candidate_affordable(row),
                not bool(row.get("fitsCurrentProjectedPower")),
                -as_float((row.get("scores") or {}).get("balanced"), 0.0),
                -as_float((row.get("scores") or {}).get("research"), 0.0),
                str((row.get("hab") or {}).get("display") or ""),
            )
        )
        best = rows[0] if rows else None
        analyses.append(
            clean_numbers(
                {
                    "template": template.get("dataName"),
                    "display": template_display(str(template.get("dataName")), template),
                    "static": module_static_analysis(template, scarcity_weights),
                    "currentBuildOptions": {
                        "eligibleHabs": eligible_habs,
                        "currentUsableEmptySlotsOnEligibleHabs": current_slots,
                        "plannedEmptySlotsOnEligibleHabs": planned_slots,
                        "powerFitPlannedSlots": power_fit_slots,
                        "blockedReasonCounts": blocked_reasons,
                        "bestOptions": rows[:top],
                    },
                    "countSamples": [
                        module_count_sample(best, count, planned_slots)
                        for count in PROJECT_ANALYSIS_MODULE_SAMPLE_COUNTS
                    ],
                },
                6,
            )
        )
    return analyses


def resource_bottlenecks(topbar: dict[str, Any]) -> list[dict[str, Any]]:
    bottlenecks: list[dict[str, Any]] = []
    resources = topbar.get("resources") if isinstance(topbar.get("resources"), dict) else {}
    for resource, row in resources.items():
        if resource == "MissionControl" or not isinstance(row, dict):
            continue
        monthly = as_float(row.get("monthly"), 0.0)
        current = as_float(row.get("current"), 0.0)
        if monthly >= 0.0:
            continue
        months_left = current / abs(monthly) if current > 0.0 else 0.0
        if months_left < 3.0:
            severity = "critical"
        elif months_left < 12.0:
            severity = "tight"
        else:
            severity = "deficit"
        bottlenecks.append(
            {
                "resource": resource,
                "current": current,
                "monthly": monthly,
                "monthsToZero": months_left,
                "severity": severity,
            }
        )
    bottlenecks.sort(key=lambda item: (as_float(item.get("monthsToZero"), 999.0), str(item.get("resource"))))

    mc = resources.get("MissionControl") if isinstance(resources.get("MissionControl"), dict) else {}
    mc_available = as_float(mc.get("available"), 0.0)
    if mc and mc_available <= 5.0:
        bottlenecks.insert(
            0,
            {
                "resource": "MissionControl",
                "available": mc_available,
                "usage": as_float(mc.get("usage"), 0.0),
                "capacity": as_float(mc.get("capacity"), 0.0),
                "severity": "critical" if mc_available <= 0.0 else "tight",
            },
        )
    return clean_numbers(bottlenecks, 6)


def project_module_aggregate(module_unlocks: list[dict[str, Any]]) -> dict[str, Any]:
    aggregate = {
        "unlockedModuleCount": len(module_unlocks),
        "bestSampleResearch": 0.0,
        "bestSampleResources": 0.0,
        "bestSampleCategoryBonus": 0.0,
        "bestSampleBalanced": None,
        "bestSampleMonthlyDelta": {},
        "bestPowerFitPlannedSlots": 0,
        "plannedEmptySlots": 0,
    }
    for unlock in module_unlocks:
        options = unlock.get("currentBuildOptions") if isinstance(unlock.get("currentBuildOptions"), dict) else {}
        aggregate["plannedEmptySlots"] += int(as_float(options.get("plannedEmptySlotsOnEligibleHabs"), 0.0))
        aggregate["bestPowerFitPlannedSlots"] = max(
            int(aggregate["bestPowerFitPlannedSlots"]),
            int(as_float(options.get("powerFitPlannedSlots"), 0.0)),
        )
        samples = unlock.get("countSamples") if isinstance(unlock.get("countSamples"), list) else []
        candidate_samples = [sample for sample in samples if isinstance(sample, dict) and sample.get("possibleWithPlannedSlots")]
        if not candidate_samples:
            candidate_samples = [sample for sample in samples if isinstance(sample, dict) and sample.get("scoresTotal")]
        if not candidate_samples:
            continue
        sample = max(candidate_samples, key=lambda item: as_float((item.get("scoresTotal") or {}).get("balanced"), 0.0))
        scores = sample.get("scoresTotal") if isinstance(sample.get("scoresTotal"), dict) else {}
        balanced = as_float(scores.get("balanced"), 0.0)
        current_balanced = aggregate.get("bestSampleBalanced")
        if current_balanced is None or balanced > as_float(current_balanced, 0.0):
            aggregate["bestSampleBalanced"] = balanced
            aggregate["bestSampleResearch"] = as_float(scores.get("research"), 0.0)
            aggregate["bestSampleResources"] = as_float(scores.get("resources"), 0.0)
            aggregate["bestSampleCategoryBonus"] = as_float(scores.get("category-bonus"), 0.0)
            aggregate["bestSampleMonthlyDelta"] = sample.get("monthlyDeltaTotal") or {}
    if aggregate["bestSampleBalanced"] is None:
        aggregate["bestSampleBalanced"] = 0.0
    return clean_numbers(aggregate, 6)


def bottleneck_penalty_from_delta(
    monthly_delta: dict[str, dict[str, float]],
    bottlenecks: list[dict[str, Any]],
    scarcity_weights: dict[str, float],
) -> float:
    bottleneck_resources = {
        str(row.get("resource"))
        for row in bottlenecks
        if row.get("resource") and row.get("severity") in {"critical", "tight"}
    }
    penalty = 0.0
    for resource, row in monthly_delta.items():
        if resource not in bottleneck_resources or not isinstance(row, dict):
            continue
        net = as_float(row.get("net"), 0.0)
        if net < 0.0:
            penalty += abs(net) * scarcity_weights.get(resource, 1.0)
    return penalty


def project_analysis_flags(
    candidate: dict[str, Any],
    bottlenecks: list[dict[str, Any]],
) -> list[str]:
    flags: list[str] = []
    eta_days = as_float((candidate.get("research") or {}).get("eta", {}).get("days"), 0.0)
    if eta_days > 180.0:
        flags.append("long project ETA")
    elif eta_days > 90.0:
        flags.append("medium project ETA")
    if not candidate.get("moduleUnlocks") and not (candidate.get("direct") or {}).get("effects") and not (candidate.get("direct") or {}).get("resourcesGranted"):
        flags.append("no quantified direct payoff in this analysis")
    module = candidate.get("moduleAggregate") if isinstance(candidate.get("moduleAggregate"), dict) else {}
    if as_float(module.get("unlockedModuleCount"), 0.0) and as_float(module.get("plannedEmptySlots"), 0.0) <= 0.0:
        flags.append("unlocked modules have no currently planned empty slots")
    if as_float(module.get("unlockedModuleCount"), 0.0) and as_float(module.get("bestPowerFitPlannedSlots"), 0.0) <= 0.0:
        flags.append("best unlocked module options likely need power support")

    bottleneck_resources = {
        str(row.get("resource"))
        for row in bottlenecks
        if row.get("resource") and row.get("severity") in {"critical", "tight"}
    }
    monthly_delta = module.get("bestSampleMonthlyDelta") if isinstance(module.get("bestSampleMonthlyDelta"), dict) else {}
    for resource, row in monthly_delta.items():
        if resource in bottleneck_resources and isinstance(row, dict) and as_float(row.get("net"), 0.0) < 0.0:
            flags.append(f"best unlocked module sample worsens {resource}")
    if candidate.get("repeatable") and (candidate.get("direct") or {}).get("resourcesGranted"):
        flags.append("repeatable one-time resource project")
    return flags


def project_candidate_analysis(
    indexed: IndexedState,
    templates_dir: Path | None,
    faction_id: int,
    faction: dict[str, Any],
    project_name: str,
    project_template: dict[str, Any],
    analysis_slot: int,
    base_daily: float,
    topbar: dict[str, Any],
    bottlenecks: list[dict[str, Any]],
    tech_templates: dict[str, dict[str, Any]],
    project_templates: dict[str, dict[str, Any]],
    trait_templates: dict[str, dict[str, Any]],
    org_templates: dict[str, dict[str, Any]],
    hab_module_templates: dict[str, dict[str, Any]],
    utility_module_templates: dict[str, dict[str, Any]],
    top: int,
) -> dict[str, Any]:
    status = project_candidate_status(faction, project_name)
    cost = project_template_cost(indexed, project_template, faction)
    remaining = max(cost - as_float(status.get("accumulatedResearch"), 0.0), 0.0)
    slot_points = hypothetical_project_points_to_slot(
        indexed,
        faction,
        project_template,
        analysis_slot,
        base_daily,
        tech_templates,
        project_templates,
        trait_templates,
        org_templates,
        hab_module_templates,
        utility_module_templates,
    )
    eta = eta_from_daily(indexed, remaining, as_float(slot_points.get("daily"), 0.0))
    scarcity_weights = resource_scarcity_weights(topbar)
    module_unlocks = prospective_module_unlocks_for_project(
        indexed,
        templates_dir,
        faction_id,
        faction,
        project_name,
        hab_module_templates,
        topbar,
        top=min(top, 5),
    )
    module_aggregate = project_module_aggregate(module_unlocks)
    grants = project_resource_grant_map(project_template)
    raw_effects = project_template.get("effects")
    effects = [str(effect) for effect in raw_effects] if isinstance(raw_effects, list) else []
    direct_grant_score = resource_grant_score(grants, scarcity_weights)
    direct_effect_score = len(effects) * 20.0
    module_research = as_float(module_aggregate.get("bestSampleResearch"), 0.0)
    module_resources = as_float(module_aggregate.get("bestSampleResources"), 0.0)
    module_category = as_float(module_aggregate.get("bestSampleCategoryBonus"), 0.0)
    module_balanced = as_float(module_aggregate.get("bestSampleBalanced"), 0.0)
    bottleneck_penalty = bottleneck_penalty_from_delta(
        module_aggregate.get("bestSampleMonthlyDelta") if isinstance(module_aggregate.get("bestSampleMonthlyDelta"), dict) else {},
        bottlenecks,
        scarcity_weights,
    )
    eta_days = as_float(eta.get("days"), 0.0)
    eta_months = eta_days / (DAYS_PER_YEAR / 12.0) if eta_days > 0.0 else 0.0
    research_raw = module_research + module_category * 100.0 + direct_effect_score
    research_sustainable = research_raw + module_resources - bottleneck_penalty
    resource_recovery = direct_grant_score + max(module_resources, 0.0)
    module_unlock_value = module_balanced + module_category * 100.0
    short_horizon = (resource_recovery + direct_effect_score + max(module_research, 0.0)) / max(eta_months + 1.0, 1.0)
    long_horizon = research_sustainable + module_unlock_value - eta_days * 0.05
    low_cost = 10000.0 / max(remaining, 100.0)
    candidate: dict[str, Any] = {
        "template": project_name,
        "display": template_display(project_name, project_template),
        "category": project_template.get("techCategory"),
        "repeatable": bool(project_template.get("repeatable")),
        "aiRole": {
            "project": project_template.get("AI_projectRole"),
            "tech": project_template.get("AI_techRole"),
        },
        "status": status,
        "research": {
            "slot": analysis_slot,
            "cost": cost,
            "remaining": remaining,
            "slotDailyEstimate": slot_points.get("daily"),
            "slotModel": slot_points,
            "eta": eta,
        },
        "direct": {
            "effects": effects,
            "resourcesGranted": grants,
            "resourceGrantScarcityScore": direct_grant_score,
        },
        "moduleUnlocks": module_unlocks,
        "moduleAggregate": module_aggregate,
        "scoreComponents": {
            "directEffectScore": direct_effect_score,
            "directResourceGrantScarcityScore": direct_grant_score,
            "moduleBestSampleResearch": module_research,
            "moduleBestSampleResources": module_resources,
            "moduleBestSampleCategoryBonus": module_category,
            "moduleBestSampleBalanced": module_balanced,
            "bottleneckPenalty": bottleneck_penalty,
            "etaDays": eta_days,
        },
        "heuristicScores": {
            "research-raw": research_raw,
            "research-sustainable": research_sustainable,
            "resource-recovery": resource_recovery,
            "module-unlock": module_unlock_value,
            "short-horizon": short_horizon,
            "long-horizon": long_horizon,
            "low-cost": low_cost,
        },
    }
    candidate["flags"] = project_analysis_flags(candidate, bottlenecks)
    return clean_numbers(candidate, 6)


def project_ranking_brief(candidate: dict[str, Any], axis: str) -> dict[str, Any]:
    return {
        "template": candidate.get("template"),
        "display": candidate.get("display"),
        "category": candidate.get("category"),
        "score": (candidate.get("heuristicScores") or {}).get(axis),
        "etaDays": ((candidate.get("research") or {}).get("eta") or {}).get("days"),
        "moduleUnlocks": [
            unlock.get("template")
            for unlock in (candidate.get("moduleUnlocks") or [])
            if isinstance(unlock, dict)
        ],
        "flags": candidate.get("flags"),
    }


def calculate_project_analysis(
    indexed: IndexedState,
    templates_dir: Path | None,
    faction_name: str | None = None,
    top: int = 10,
    sort_axis: str = "research-sustainable",
    slot: int | None = None,
    include_active: bool = False,
    include_all: bool = False,
) -> dict[str, Any]:
    faction_id, faction = find_faction_state(indexed, faction_name)
    research_templates = load_research_templates(indexed, templates_dir)
    base_daily_cache: dict[int, float] = {}
    project_templates = research_templates.projects
    tech_templates = research_templates.techs
    trait_templates = research_templates.traits
    org_templates = research_templates.orgs
    hab_module_templates = research_templates.hab_modules
    utility_module_templates = research_templates.utility_modules
    analysis_slot = slot if slot is not None else default_project_analysis_slot(faction)
    if analysis_slot is None:
        raise UserInputError("Faction has no unlocked project research slot.")
    if analysis_slot not in faction_project_slots(faction):
        raise UserInputError(f"Project slot {analysis_slot} is not currently unlocked for this faction.")
    if sort_axis not in PROJECT_ANALYSIS_SORT_CHOICES:
        raise UserInputError(f"Unknown project-analysis sort axis: {sort_axis}")

    topbar = calculate_topbar(
        indexed,
        templates_dir,
        faction.get("templateName"),
        include_details=False,
        research_templates=research_templates,
        base_daily_cache=base_daily_cache,
    )
    bottlenecks = resource_bottlenecks(topbar)
    base_daily = faction_base_research_daily(
        indexed,
        templates_dir,
        faction,
        templates=research_templates,
        cache=base_daily_cache,
    )
    names = project_analysis_candidate_names(faction, project_templates, include_active=include_active)
    candidates = [
        project_candidate_analysis(
            indexed,
            templates_dir,
            faction_id,
            faction,
            name,
            project_templates[name],
            analysis_slot,
            base_daily,
            topbar,
            bottlenecks,
            tech_templates,
            project_templates,
            trait_templates,
            org_templates,
            hab_module_templates,
            utility_module_templates,
            top,
        )
        for name in names
    ]
    candidates.sort(
        key=lambda candidate: (
            -as_float((candidate.get("heuristicScores") or {}).get(sort_axis), 0.0),
            as_float(((candidate.get("research") or {}).get("eta") or {}).get("days"), 999999.0),
            str(candidate.get("display") or candidate.get("template")),
        )
    )
    ranking_axes = ("research-sustainable", "research-raw", "resource-recovery", "module-unlock", "short-horizon", "long-horizon")
    rankings = {
        axis: [
            project_ranking_brief(candidate, axis)
            for candidate in sorted(
                candidates,
                key=lambda item: (
                    -as_float((item.get("heuristicScores") or {}).get(axis), 0.0),
                    as_float(((item.get("research") or {}).get("eta") or {}).get("days"), 999999.0),
                    str(item.get("display") or item.get("template")),
                ),
            )[:top]
        ]
        for axis in ranking_axes
    }
    research_ui = calculate_research_ui(
        indexed,
        templates_dir,
        faction.get("templateName"),
        templates=research_templates,
        base_daily_cache=base_daily_cache,
    )
    return clean_numbers(
        {
            "faction": faction_brief(faction_id, faction),
            "date": (first_value(indexed, "TITimeState") or {}).get("currentDateTime"),
            "filters": {
                "top": top,
                "sort": sort_axis,
                "analysisSlot": analysis_slot,
                "includeActive": include_active,
                "includeAll": include_all,
                "candidateCount": len(candidates),
            },
            "constraints": {
                "missionControl": (topbar.get("resources") or {}).get("MissionControl"),
                "bottlenecks": bottlenecks,
                "resourceScarcityWeights": resource_scarcity_weights(topbar),
            },
            "activeProjects": research_ui.get("projects", {}).get("active"),
            "scoreModel": {
                "purpose": "explainable shortlist generation for LLM/human synthesis, not an automatic final recommendation",
                "research-raw": "best unlocked-module sample Research/month + 100 * category-bonus sample + 20 per direct project effect",
                "research-sustainable": "research-raw + scarcity-weighted module resource score - critical/tight bottleneck worsening penalty",
                "resource-recovery": "one-time resources granted weighted by current scarcity + positive unlocked-module resource score",
                "module-unlock": "best unlocked-module balanced score + 100 * best category-bonus sample",
                "short-horizon": "(resource-recovery + direct-effect score + positive module research) divided by ETA months + 1",
                "long-horizon": "research-sustainable + module-unlock - 0.05 * ETA days",
                "low-cost": "10000 / remaining research cost, floored at 100 cost",
            },
            "rankings": rankings,
            "candidates": candidates if include_all else candidates[:top],
            "sourceNotes": [
                "This command ranks candidates on multiple transparent heuristic axes; it intentionally does not choose a final project.",
                "Hypothetical project ETA uses the chosen project slot's current research weight and current category/project-facility modifiers.",
                "Module unlock samples pretend the project is finished, scan current/planned empty slots, and repeat the best current hab option for 1/2/4-module samples.",
                "Negative support in module deltas means the hypothetical module reduces existing upkeep.",
                "Module samples do not solve a global construction queue, global MC allocation, or extra power-support placement.",
            ],
        },
        6,
    )
