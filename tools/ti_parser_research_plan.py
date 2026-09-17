"""Available research candidates, scoring and research plans."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ti_parser_config import (
    DEFAULT_GLOBAL_CONFIG,
    RESEARCH_PLAN_SCORE_AXES,
)
from ti_parser_core import (
    CalculationDependency,
    CalculationDependencyError,
    IndexedState,
    as_float,
    clean_numbers,
    find_faction_state,
    first_value,
)
from ti_parser_research import (
    active_slots_with_category,
    calculate_research_ui,
    eta_from_daily,
    faction_base_research_daily,
    faction_category_modifier_components,
    faction_project_slots,
    faction_research_weights,
    faction_total_research_weights,
    load_research_templates,
    multiple_facilities_multiplier,
    project_facility_counts,
    project_progress_by_slot,
    project_template_cost,
    tech_template_cost,
    template_display,
)
from ti_parser_runtime import faction_brief
from ti_parser_topbar import calculate_topbar


def string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if item]
    if isinstance(value, str) and value:
        return [value]
    return []


def research_template_prereqs(template: dict[str, Any]) -> list[str]:
    prereqs = string_list(template.get("prereqs"))
    for key in ("altPrereq0",):
        for name in string_list(template.get(key)):
            if name not in prereqs:
                prereqs.append(name)
    return prereqs


def research_template_effects(template: dict[str, Any]) -> list[str]:
    return string_list(template.get("effects"))


def research_template_resources_granted(template: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for item in template.get("resourcesGranted") if isinstance(template.get("resourcesGranted"), list) else []:
        if not isinstance(item, dict):
            continue
        resource = item.get("resource")
        if not resource:
            continue
        rows.append({"resource": str(resource), "value": as_float(item.get("value"), 0.0)})
    return rows


def active_global_research_names(indexed: IndexedState) -> set[str]:
    global_research = first_value(indexed, "TIGlobalResearchState") or {}
    progress = global_research.get("techProgress") if isinstance(global_research.get("techProgress"), list) else []
    return {
        str(row.get("techTemplateName"))
        for row in progress
        if isinstance(row, dict) and row.get("techTemplateName")
    }


def finished_global_research_names(indexed: IndexedState) -> set[str]:
    global_research = first_value(indexed, "TIGlobalResearchState") or {}
    return set(string_list(global_research.get("finishedTechsNames")))


def available_global_research_templates(
    indexed: IndexedState,
    tech_templates: dict[str, dict[str, Any]],
) -> list[tuple[str, dict[str, Any]]]:
    finished = finished_global_research_names(indexed)
    active = active_global_research_names(indexed)
    rows = []
    for name, template in tech_templates.items():
        if name in finished or name in active:
            continue
        if as_float(template.get("researchCost"), 0.0) <= 0.0:
            continue
        prereqs = research_template_prereqs(template)
        if all(prereq in finished for prereq in prereqs):
            rows.append((name, template))
    rows.sort(key=lambda item: (as_float(item[1].get("researchCost"), 0.0), item[1].get("friendlyName") or item[0]))
    return rows


def project_progress_records_by_template(faction: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    progress = faction.get("currentProjectProgress") if isinstance(faction.get("currentProjectProgress"), list) else []
    for item in progress:
        if not isinstance(item, dict) or not item.get("projectTemplateName"):
            continue
        name = str(item.get("projectTemplateName"))
        existing = rows.get(name)
        if existing is None or as_float(item.get("accumulatedResearch"), 0.0) > as_float(existing.get("accumulatedResearch"), 0.0):
            rows[name] = item
    return rows


def active_project_research_names(faction: dict[str, Any]) -> set[str]:
    progress_by_slot = project_progress_by_slot(faction)
    names = set()
    for slot in faction_project_slots(faction):
        progress = progress_by_slot.get(slot)
        if progress and progress.get("projectTemplateName"):
            names.add(str(progress.get("projectTemplateName")))
    return names


def available_project_research_templates(
    faction: dict[str, Any],
    project_templates: dict[str, dict[str, Any]],
) -> list[tuple[str, dict[str, Any]]]:
    available = string_list(faction.get("availableProjectNames"))
    active = active_project_research_names(faction)
    rows = []
    for name in available:
        if name in active:
            continue
        template = project_templates.get(name)
        if not isinstance(template, dict):
            raise CalculationDependencyError(
                CalculationDependency(
                    kind="research-project",
                    name=name,
                    context="research-plan.available-projects",
                    scenario=None,
                    reason="save candidate is absent from the packaged research catalog",
                )
            )
        if as_float(template.get("researchCost"), 0.0) <= 0.0:
            continue
        rows.append((name, template))
    rows.sort(key=lambda item: (as_float(item[1].get("researchCost"), 0.0), item[1].get("friendlyName") or item[0]))
    return rows


def research_plan_reference_weight_fraction(faction: dict[str, Any], kind: str) -> float:
    weights = faction_research_weights(faction)
    total = faction_total_research_weights(faction)
    if total <= 0.0:
        return 0.0
    slots = range(0, 3) if kind == "global" else faction_project_slots(faction)
    fractions = [weights[slot] / total for slot in slots if slot < len(weights) and weights[slot] > 0.0]
    return max(fractions) if fractions else 0.0


def direct_unlocks_for_template(
    template_name: str,
    tech_templates: dict[str, dict[str, Any]],
    project_templates: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    techs = [
        {"template": name, "display": template_display(name, template), "category": template.get("techCategory")}
        for name, template in tech_templates.items()
        if template_name in research_template_prereqs(template)
    ]
    projects = [
        {"template": name, "display": template_display(name, template), "category": template.get("techCategory")}
        for name, template in project_templates.items()
        if template_name in research_template_prereqs(template)
    ]
    techs.sort(key=lambda row: str(row.get("display") or row.get("template")))
    projects.sort(key=lambda row: str(row.get("display") or row.get("template")))
    return {"globalTechs": techs, "projects": projects, "count": len(techs) + len(projects)}


def research_plan_keyword_tags(template: dict[str, Any]) -> list[str]:
    text = " ".join(
        [
            str(template.get("dataName") or ""),
            str(template.get("friendlyName") or ""),
            str(template.get("AI_techRole") or ""),
            str(template.get("AI_projectRole") or ""),
            " ".join(research_template_effects(template)),
        ]
    ).casefold()
    rules = {
        "alien-xeno": ("alien", "xeno", "hydra", "pherocyte", "salamander"),
        "ship-combat": ("ship", "weapon", "laser", "missile", "torpedo", "armor", "navy", "fleet", "combat"),
        "space-economy": ("hab", "mining", "colony", "outpost", "space", "missioncontrol", "shipbuilding"),
        "earth-economy": ("economy", "funding", "welfare", "climate", "gdp", "development"),
        "council-ops": ("council", "ops", "investigation", "espionage", "security", "administration"),
        "research-infrastructure": ("research", "lab", "science", "university", "institute"),
        "resources": ("resource", "water", "volatile", "metals", "fissile", "antimatter", "exotic"),
    }
    return [tag for tag, needles in rules.items() if any(needle in text for needle in needles)]


def research_plan_category_context(
    indexed: IndexedState,
    faction: dict[str, Any],
    category: str | None,
    kind: str,
    trait_templates: dict[str, dict[str, Any]],
    org_templates: dict[str, dict[str, Any]],
    hab_module_templates: dict[str, dict[str, Any]],
    utility_module_templates: dict[str, dict[str, Any]],
    tech_templates: dict[str, dict[str, Any]],
    project_templates: dict[str, dict[str, Any]],
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
    current_active = active_slots_with_category(indexed, faction, tech_templates, project_templates, category)
    added_penalty_power = current_active
    category_bonus_if_added = as_float(components.get("sum"), 0.0) * (
        DEFAULT_GLOBAL_CONFIG["categoryBonusPenaltyPerExtraSlot"] ** added_penalty_power
    )
    project_facilities = (
        project_facility_counts(
            indexed,
            faction,
            trait_templates,
            hab_module_templates,
            org_templates=org_templates,
        )
        if kind == "project"
        else None
    )
    project_bonus = multiple_facilities_multiplier(project_facilities or {}) if kind == "project" else 0.0
    return clean_numbers(
        {
            "category": category,
            "components": components,
            "currentActiveSlotsWithCategory": current_active,
            "addedSlotPenaltyPower": added_penalty_power,
            "categoryBonusIfAddedToCurrentMix": category_bonus_if_added,
            "projectFacilities": project_facilities,
            "projectFacilityBonus": project_bonus if kind == "project" else None,
            "effectiveMultiplierIfAddedToCurrentMix": 1.0 + category_bonus_if_added + project_bonus,
        },
        6,
    )


def research_plan_resource_grant_maps(
    resources_granted: list[dict[str, Any]],
    cost_remaining: float,
    deficient_resources: set[str],
) -> dict[str, Any]:
    by_resource = {row["resource"]: row["value"] for row in resources_granted}
    per_research = {
        resource: value / cost_remaining
        for resource, value in by_resource.items()
        if cost_remaining > 0.0
    }
    deficient = {resource: value for resource, value in by_resource.items() if resource in deficient_resources}
    return clean_numbers(
        {
            "byResource": by_resource,
            "perRemainingResearch": per_research,
            "currentlyDeficientResourcesGranted": deficient,
            "deficientResourceTypesCovered": len(deficient),
        },
        6,
    )


def research_plan_candidate_row(
    indexed: IndexedState,
    faction: dict[str, Any],
    template_name: str,
    template: dict[str, Any],
    kind: str,
    base_daily: float,
    reference_weight_fraction: float,
    progress: dict[str, Any] | None,
    topbar: dict[str, Any],
    trait_templates: dict[str, dict[str, Any]],
    org_templates: dict[str, dict[str, Any]],
    hab_module_templates: dict[str, dict[str, Any]],
    utility_module_templates: dict[str, dict[str, Any]],
    tech_templates: dict[str, dict[str, Any]],
    project_templates: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    category = template.get("techCategory")
    cost = tech_template_cost(indexed, template) if kind == "global" else project_template_cost(indexed, template, faction)
    accumulated = as_float((progress or {}).get("accumulatedResearch"), 0.0)
    remaining = max(cost - accumulated, 0.0)
    category_context = research_plan_category_context(
        indexed,
        faction,
        category,
        kind,
        trait_templates,
        org_templates,
        hab_module_templates,
        utility_module_templates,
        tech_templates,
        project_templates,
    )
    estimated_daily = base_daily * reference_weight_fraction * as_float(category_context.get("effectiveMultiplierIfAddedToCurrentMix"), 0.0)
    effects = research_template_effects(template)
    resources_granted = research_template_resources_granted(template)
    deficient_resources = set(string_list(topbar.get("resourceIncomeDeficiencies")))
    grants = research_plan_resource_grant_maps(resources_granted, remaining, deficient_resources)
    unlocks = direct_unlocks_for_template(template_name, tech_templates, project_templates)
    eta = eta_from_daily(indexed, remaining, estimated_daily)
    progress_fraction = accumulated / cost if cost > 0.0 else None
    return clean_numbers(
        {
            "kind": kind,
            "template": template_name,
            "display": template_display(template_name, template),
            "category": category,
            "classification": {
                "aiTechRole": template.get("AI_techRole"),
                "aiProjectRole": template.get("AI_projectRole"),
                "aiCriticalTech": bool(template.get("AI_criticalTech")),
                "keywordTags": research_plan_keyword_tags(template),
            },
            "research": {
                "cost": cost,
                "accumulated": accumulated,
                "remaining": remaining,
                "progressFraction": progress_fraction,
                "referenceWeightFraction": reference_weight_fraction,
                "estimatedDailyAtReferenceWeight": estimated_daily,
                "etaAtReferenceWeight": eta,
                "progressSlot": (progress or {}).get("slot"),
                "repeatable": bool(template.get("repeatable")) if kind == "project" else None,
                "oneTimeGlobally": bool(template.get("oneTimeGlobally")) if kind == "project" else None,
            },
            "requirements": {
                "prereqs": research_template_prereqs(template),
                "factionPrereq": string_list(template.get("factionPrereq")),
                "requiredMilestone": template.get("requiredMilestone"),
                "requiredObjectiveName": template.get("requiredObjectiveName"),
                "altRequiredObjectiveName": template.get("altRequiredObjectiveName"),
                "requiresNation": template.get("requiresNation"),
            },
            "effects": effects,
            "resourcesGranted": grants,
            "orgGranted": template.get("orgGranted"),
            "unlocks": unlocks,
            "categoryContext": category_context,
            "scoreEvidence": {
                "estimatedDaysAtReferenceWeight": eta.get("days"),
                "categoryEffectiveMultiplier": category_context.get("effectiveMultiplierIfAddedToCurrentMix"),
                "directUnlockCount": unlocks.get("count"),
                "aiCriticalTech": bool(template.get("AI_criticalTech")),
                "deficientResourceTypesCovered": grants.get("deficientResourceTypesCovered"),
                "progressFraction": progress_fraction or 0.0,
            },
        },
        6,
    )


def score_research_plan_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    positive_days = [
        as_float((candidate.get("scoreEvidence") or {}).get("estimatedDaysAtReferenceWeight"), 0.0)
        for candidate in candidates
        if as_float((candidate.get("scoreEvidence") or {}).get("estimatedDaysAtReferenceWeight"), 0.0) > 0.0
    ]
    min_days = min(positive_days) if positive_days else 0.0
    max_category = max(
        [as_float((candidate.get("scoreEvidence") or {}).get("categoryEffectiveMultiplier"), 0.0) for candidate in candidates]
        or [0.0]
    )
    max_unlocks = max(
        [as_float((candidate.get("scoreEvidence") or {}).get("directUnlockCount"), 0.0) for candidate in candidates]
        or [0.0]
    )
    max_deficient = max(
        [as_float((candidate.get("scoreEvidence") or {}).get("deficientResourceTypesCovered"), 0.0) for candidate in candidates]
        or [0.0]
    )
    for candidate in candidates:
        evidence = candidate.get("scoreEvidence") if isinstance(candidate.get("scoreEvidence"), dict) else {}
        days = as_float(evidence.get("estimatedDaysAtReferenceWeight"), 0.0)
        category = as_float(evidence.get("categoryEffectiveMultiplier"), 0.0)
        unlocks = as_float(evidence.get("directUnlockCount"), 0.0)
        deficient = as_float(evidence.get("deficientResourceTypesCovered"), 0.0)
        progress = as_float(evidence.get("progressFraction"), 0.0)
        scores = {
            "fastCompletion": 100.0 * min_days / days if min_days > 0.0 and days > 0.0 else 0.0,
            "factionSynergy": 100.0 * category / max_category if max_category > 0.0 else 0.0,
            "unlockBreadth": 100.0 * unlocks / max_unlocks if max_unlocks > 0.0 else 0.0,
            "criticalTemplate": 100.0 if evidence.get("aiCriticalTech") else 0.0,
            "resourceReliefCoverage": 100.0 * deficient / max_deficient if max_deficient > 0.0 else 0.0,
            "currentProgress": min(max(progress * 100.0, 0.0), 100.0),
        }
        candidate["objectiveScores"] = clean_numbers(scores, 6)
    return candidates


def research_plan_goal_views(candidates: list[dict[str, Any]], top: int) -> dict[str, list[dict[str, Any]]]:
    views: dict[str, list[dict[str, Any]]] = {}
    for axis in RESEARCH_PLAN_SCORE_AXES:
        rows = sorted(
            candidates,
            key=lambda candidate: (
                -as_float((candidate.get("objectiveScores") or {}).get(axis), 0.0),
                as_float((candidate.get("scoreEvidence") or {}).get("estimatedDaysAtReferenceWeight"), 1_000_000_000.0),
                str(candidate.get("display") or candidate.get("template")),
            ),
        )
        views[axis] = [
            {
                "template": row.get("template"),
                "display": row.get("display"),
                "kind": row.get("kind"),
                "category": row.get("category"),
                "score": (row.get("objectiveScores") or {}).get(axis),
                "scoreEvidence": row.get("scoreEvidence"),
            }
            for row in rows[:top]
            if as_float((row.get("objectiveScores") or {}).get(axis), 0.0) > 0.0
        ]
    return views


def research_plan_shortlist(candidates: list[dict[str, Any]], top: int) -> list[dict[str, Any]]:
    selected: dict[tuple[str, str], dict[str, Any]] = {}
    for rows in research_plan_goal_views(candidates, top).values():
        for row in rows:
            key = (str(row.get("kind")), str(row.get("template")))
            found = next(
                (
                    candidate
                    for candidate in candidates
                    if candidate.get("kind") == row.get("kind") and candidate.get("template") == row.get("template")
                ),
                None,
            )
            if found:
                selected[key] = found
    return sorted(
        selected.values(),
        key=lambda candidate: (
            str(candidate.get("kind")),
            str(candidate.get("category")),
            as_float((candidate.get("scoreEvidence") or {}).get("estimatedDaysAtReferenceWeight"), 1_000_000_000.0),
            str(candidate.get("display") or candidate.get("template")),
        ),
    )


def calculate_research_plan(
    indexed: IndexedState,
    templates_dir: Path | None,
    faction_name: str | None = None,
    top: int = 8,
    mode: str = "all",
    include_all_candidates: bool = False,
) -> dict[str, Any]:
    research_templates = load_research_templates(indexed, templates_dir)
    base_daily_cache: dict[int, float] = {}
    trait_templates = research_templates.traits
    org_templates = research_templates.orgs
    hab_module_templates = research_templates.hab_modules
    utility_module_templates = research_templates.utility_modules
    tech_templates = research_templates.techs
    project_templates = research_templates.projects

    faction_id, faction = find_faction_state(indexed, faction_name)
    topbar = calculate_topbar(
        indexed,
        templates_dir,
        faction_name,
        include_details=False,
        research_templates=research_templates,
        base_daily_cache=base_daily_cache,
    )
    base_daily = faction_base_research_daily(
        indexed,
        templates_dir,
        faction,
        templates=research_templates,
        cache=base_daily_cache,
    )
    research_ui = calculate_research_ui(
        indexed,
        templates_dir,
        faction_name,
        templates=research_templates,
        base_daily_cache=base_daily_cache,
    )
    progress_by_project = project_progress_records_by_template(faction)

    global_candidates: list[dict[str, Any]] = []
    if mode in {"all", "global"}:
        global_fraction = research_plan_reference_weight_fraction(faction, "global")
        global_candidates = [
            research_plan_candidate_row(
                indexed,
                faction,
                name,
                template,
                "global",
                base_daily,
                global_fraction,
                None,
                topbar,
                trait_templates,
                org_templates,
                hab_module_templates,
                utility_module_templates,
                tech_templates,
                project_templates,
            )
            for name, template in available_global_research_templates(indexed, tech_templates)
        ]
        score_research_plan_candidates(global_candidates)

    project_candidates: list[dict[str, Any]] = []
    if mode in {"all", "project"}:
        project_fraction = research_plan_reference_weight_fraction(faction, "project")
        project_candidates = [
            research_plan_candidate_row(
                indexed,
                faction,
                name,
                template,
                "project",
                base_daily,
                project_fraction,
                progress_by_project.get(name),
                topbar,
                trait_templates,
                org_templates,
                hab_module_templates,
                utility_module_templates,
                tech_templates,
                project_templates,
            )
            for name, template in available_project_research_templates(faction, project_templates)
        ]
        score_research_plan_candidates(project_candidates)

    current_projects = research_ui.get("projects") if isinstance(research_ui.get("projects"), dict) else {}
    report = {
        "faction": faction_brief(faction_id, faction),
        "date": (first_value(indexed, "TITimeState") or {}).get("currentDateTime"),
        "questionSupported": "다음 글로벌 연구/프로젝트 연구는 어떤 기술이 좋아?",
        "mode": mode,
        "templateAvailability": {
            "source": "packaged-runtime-catalog",
            "templatesDir": None,
            "globalTechTemplates": len(tech_templates),
            "projectTemplates": len(project_templates),
            "warning": None if tech_templates and project_templates else "The packaged research catalog is missing required candidate rows.",
        },
        "currentState": {
            "researchIncome": research_ui.get("researchIncome"),
            "slotAllocation": research_ui.get("slotAllocation"),
            "activeGlobalResearch": research_ui.get("globalResearch"),
            "activeProjects": current_projects.get("active"),
            "pausedOrStoredProjects": current_projects.get("pausedOrStored"),
            "resourceConstraints": {
                "resourceIncomeDeficiencies": topbar.get("resourceIncomeDeficiencies"),
                "missionControl": (topbar.get("resources") or {}).get("MissionControl"),
                "monthlyResourceDeltas": {
                    resource: row.get("monthly")
                    for resource, row in (topbar.get("resources") or {}).items()
                    if isinstance(row, dict) and resource in {"Money", "Boost", "Water", "Volatiles", "Metals", "NobleMetals", "Fissiles"}
                },
            },
        },
        "globalResearchCandidates": {
            "count": len(global_candidates),
            "source": "TITechTemplate entries whose prereqs are all in TIGlobalResearchState.finishedTechsNames, excluding finished and active techs.",
            "goalViews": research_plan_goal_views(global_candidates, top),
            "shortlist": research_plan_shortlist(global_candidates, top),
        },
        "projectResearchCandidates": {
            "count": len(project_candidates),
            "source": "TIFactionState.availableProjectNames, excluding active project slots; paused/stored progress is included as candidate progress.",
            "goalViews": research_plan_goal_views(project_candidates, top),
            "shortlist": research_plan_shortlist(project_candidates, top),
        },
        "scoreModel": {
            "automatedJudgmentBoundary": "Scores are objective proxy signals for LLM review, not a final utility ranking.",
            "axes": {
                "fastCompletion": "100 for the fastest candidate in the same candidate pool; uses remaining research divided by estimated daily output at the current reference slot weight.",
                "factionSynergy": "Normalized effective multiplier from current category bonuses if this candidate were added to the current research mix.",
                "unlockBreadth": "Normalized count of direct downstream global tech and project templates listing this template as a prereq or alternate prereq.",
                "criticalTemplate": "100 when template metadata marks AI_criticalTech true; otherwise 0.",
                "resourceReliefCoverage": "Normalized count of resource types granted by the project that are currently listed as faction resource-income deficiencies; quantities are kept separately by resource.",
                "currentProgress": "Existing accumulated progress divided by cost, useful for paused/stored projects.",
            },
            "referenceSlotWeights": {
                "global": research_plan_reference_weight_fraction(faction, "global"),
                "project": research_plan_reference_weight_fraction(faction, "project"),
            },
            "limitations": [
                "The tool does not decide strategic priority weights such as whether war, economy, alien-objective progress, or expansion matters most.",
                "Global candidate ETA assumes adding the candidate to the current research mix and current slot weights; actual UI selection may replace a completed slot and change category-penalty math.",
                "Project availability is taken from the save's availableProjectNames; hidden unlock chance mechanics are not re-simulated.",
                "Resource grants are not converted into a single cross-resource utility value.",
            ],
        },
        "llmDecision": {
            "recommendedUse": [
                "Pick the user's strategic goal first.",
                "Use goalViews to find candidates high on the relevant objective signal.",
                "Use shortlist rows for effects, unlocks, costs, ETA, current constraints, and deficiencies.",
                "Make the final recommendation in natural language, explicitly separating automated facts from strategic judgment.",
            ],
            "finalRecommendationAutomated": False,
        },
        "sourceNotes": [
            "This report combines research-ui, topbar, global tech templates, project templates, and faction available-project state.",
            "ObjectiveScores are normalized within global and project candidate pools separately.",
            "Keyword tags are transparent string matches over template names, AI roles, and effect names; they are aids for scanning, not game rules.",
        ],
    }
    if include_all_candidates:
        report["globalResearchCandidates"]["all"] = global_candidates
        report["projectResearchCandidates"]["all"] = project_candidates
    return clean_numbers(report, 6)
