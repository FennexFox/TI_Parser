"""Fail-closed nation priority and conditional Advisor projection engine."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
import copy
import operator
from typing import Any, Callable, Iterable, Mapping

from ti_parser_income import (
    adviser_attribute_bonus_from_values,
    mission_control_contribution_from_values,
    nation_monthly_research_from_values,
    proportional_cp_contribution,
)
from ti_parser_mechanics import Rules, mechanic_diagnostics


DAYS_PER_YEAR = 365.2422  # TINationState.ControlPointWeightsTotalToPriorityIP literal.
PRIORITY_ALIASES = {
    "Boost": "LaunchFacilities",
    "BuildArmy": "Military_BuildArmy",
    "BuildNavy": "Military_BuildNavy",
    "BuildNuclearWeapons": "Military_BuildNuclearWeapons",
    "BuildSpaceDefenses": "Military_BuildSpaceDefenses",
    "BuildSTOSquadron": "Military_BuildSTOSquadron",
    "FoundMilitary": "Military_FoundMilitary",
    "InitiateNuclearProgram": "Military_InitiateNuclearProgram",
    "InitiateSpaceflightProgram": "Civilian_InitiateSpaceflightProgram",
}
SUPPORTED_COMPLETIONS = {
    "Knowledge": ("exact", Rules.NATION_PRIORITY_KNOWLEDGE_COMPLETE),
    "Government": ("aggregateOnly", Rules.NATION_PRIORITY_GOVERNMENT_COMPLETE),
    "Unity": ("aggregateOnly", Rules.NATION_PRIORITY_UNITY_COMPLETE),
    "Funding": ("exact", Rules.NATION_PRIORITY_FUNDING_COMPLETE),
}
OPS: dict[str, Callable[[float, float], bool]] = {
    ">=": operator.ge,
    "<=": operator.le,
    ">": operator.gt,
    "<": operator.lt,
    "==": operator.eq,
}


class ProjectionInputError(ValueError):
    pass


@dataclass
class RegionProjectionState:
    id: int
    population_millions: float
    boost_per_year: float = 0.0
    mission_control: int = 0
    annual_population_growth: float | None = None
    per_capita_gdp: float = 0.0


@dataclass
class ControlPointProjectionState:
    id: int
    position: int
    owner_faction_id: int | None
    benefits_disabled: bool
    control_point_type: str | None
    pips: dict[str, int]
    priority_bonuses: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class AdvisorProfile:
    source: str
    name: str
    administration: float
    science: float
    councilor_id: int | None = None

    def output(self) -> dict[str, Any]:
        value = {
            "source": self.source,
            "name": self.name,
            "administration": self.administration,
            "science": self.science,
        }
        if self.councilor_id is not None:
            value["id"] = self.councilor_id
        return value


@dataclass
class NationProjectionState:
    nation_id: int
    at: datetime
    gdp: float
    inequality: float
    education: float
    democracy: float
    cohesion: float
    cohesion_rest: float
    unrest: float
    unrest_rest: float
    sustainability: float
    military_tech: float
    funding_year: float
    economy_score: float
    occupation_factor: float
    army_maintenance: float
    progress: dict[str, float]
    regions: dict[int, RegionProjectionState]
    control_points: dict[int, ControlPointProjectionState]
    advisors: tuple[AdvisorProfile, ...]
    mission_control: int = 0
    army_count: int = 0
    navy_count: int = 0
    nuclear_weapons: int = 0
    space_defenses: int = 0
    sto_fighters: int = 0

    @property
    def population_millions(self) -> float:
        return sum(region.population_millions for region in self.regions.values())

    @property
    def num_control_points(self) -> int:
        return len(self.control_points)


@dataclass(frozen=True)
class MetricCondition:
    metric: str
    op: str
    value: float
    relative_to_start: bool = False


@dataclass(frozen=True)
class ControlPointPolicy:
    control_point_id: int
    pips: Mapping[str, int]


@dataclass(frozen=True)
class PlanSegment:
    until_day: int | None
    until_condition: MetricCondition | None
    control_points: tuple[ControlPointPolicy, ...] | None
    advisors: tuple[AdvisorProfile, ...] | None


@dataclass(frozen=True)
class PriorityPlan:
    name: str
    segments: tuple[PlanSegment, ...]


@dataclass(frozen=True)
class ProjectionContext:
    faction_id: int
    priorities: Mapping[str, Mapping[str, Any]]
    global_config: Mapping[str, Any]
    diversity_bonuses: Mapping[str, float]
    national_ip_multiplier: float = 1.0
    initial_funding_pool_year: float = 0.0
    initial_own_funding_year: float = 0.0
    initial_boost_pool_year: float = 0.0
    knowledge_sector_owned: bool = False
    financial_sector_owned: bool = False
    knowledge_sector_bonus: float = 1.0
    financial_sector_bonus: float = 1.0
    research_effect_factor: float = 1.0


def _canonical_priority(value: str, priorities: Mapping[str, Any]) -> str:
    canonical = PRIORITY_ALIASES.get(value, value)
    if canonical not in priorities:
        raise ProjectionInputError(f"Unknown priority: {value}")
    return canonical


def _condition(value: Any) -> MetricCondition:
    if not isinstance(value, dict):
        raise ProjectionInputError("Metric condition must be an object")
    metric = value.get("metric")
    op = value.get("op")
    target = value.get("value")
    if metric not in METRIC_NAMES:
        raise ProjectionInputError(f"Unsupported metric: {metric}")
    if op not in OPS:
        raise ProjectionInputError(f"Unsupported condition operator: {op}")
    if not isinstance(target, (int, float)) or isinstance(target, bool):
        raise ProjectionInputError("Condition value must be numeric")
    return MetricCondition(str(metric), str(op), float(target), bool(value.get("relativeToStart", False)))


def _resolve_advisor(value: Any, councilors: Mapping[int, AdvisorProfile]) -> AdvisorProfile:
    if not isinstance(value, dict) or ("councilor" in value) == ("virtual" in value):
        raise ProjectionInputError("Each advisor must contain exactly one of councilor or virtual")
    if "virtual" in value:
        profile = value["virtual"]
        if not isinstance(profile, dict):
            raise ProjectionInputError("virtual advisor must be an object")
        name = profile.get("name")
        administration = profile.get("administration")
        science = profile.get("science")
        if not isinstance(name, str) or not name:
            raise ProjectionInputError("virtual advisor requires a name")
        if any(not isinstance(item, (int, float)) or isinstance(item, bool) or not 0 <= float(item) <= 25 for item in (administration, science)):
            raise ProjectionInputError("virtual advisor administration/science must be in 0..25")
        return AdvisorProfile("virtual", name, float(administration), float(science))
    selector = value["councilor"]
    if not isinstance(selector, dict) or ("id" in selector) == ("name" in selector):
        raise ProjectionInputError("councilor advisor requires exactly one of id or name")
    matches: list[AdvisorProfile]
    if "id" in selector:
        key = selector["id"]
        matches = [councilors[key]] if isinstance(key, int) and key in councilors else []
    else:
        name = str(selector["name"]).casefold()
        matches = [profile for profile in councilors.values() if profile.name.casefold() == name]
    if len(matches) != 1:
        raise ProjectionInputError("Saved councilor advisor was not found uniquely in the selected active faction roster")
    return matches[0]


def parse_projection_document(
    payload: Any,
    *,
    state: NationProjectionState,
    councilors: Mapping[int, AdvisorProfile],
    priorities: Mapping[str, Any],
) -> tuple[tuple[PriorityPlan, ...], tuple[tuple[str, MetricCondition], ...]]:
    if payload is None:
        return (PriorityPlan("current", (PlanSegment(None, None, None, None),)),), ()
    if not isinstance(payload, dict):
        raise ProjectionInputError("Plan file root must be an object")
    raw_plans = payload.get("plans")
    if not isinstance(raw_plans, list) or not raw_plans:
        raise ProjectionInputError("Plan file requires a non-empty plans array")
    plans: list[PriorityPlan] = []
    names: set[str] = set()
    cp_by_position = {cp.position: cp.id for cp in state.control_points.values()}
    for raw_plan in raw_plans:
        if not isinstance(raw_plan, dict) or not isinstance(raw_plan.get("name"), str) or not raw_plan["name"]:
            raise ProjectionInputError("Each plan requires a non-empty name")
        if raw_plan["name"] in names:
            raise ProjectionInputError(f"Duplicate plan name: {raw_plan['name']}")
        names.add(raw_plan["name"])
        raw_segments = raw_plan.get("segments")
        if not isinstance(raw_segments, list) or not raw_segments:
            raise ProjectionInputError(f"Plan {raw_plan['name']} requires segments")
        segments: list[PlanSegment] = []
        for index, raw_segment in enumerate(raw_segments):
            if not isinstance(raw_segment, dict):
                raise ProjectionInputError("Plan segment must be an object")
            until_day = None
            until_condition = None
            if "until" in raw_segment:
                until = raw_segment["until"]
                if not isinstance(until, dict):
                    raise ProjectionInputError("until must be an object")
                if "day" in until:
                    if set(until) != {"day"} or not isinstance(until["day"], int) or until["day"] < 0:
                        raise ProjectionInputError("until.day must be a non-negative integer")
                    until_day = until["day"]
                else:
                    until_condition = _condition(until)
            elif index < len(raw_segments) - 1:
                raise ProjectionInputError("Every non-final segment requires until")
            cp_policies: tuple[ControlPointPolicy, ...] | None = None
            if "controlPoints" in raw_segment:
                raw_cps = raw_segment["controlPoints"]
                if not isinstance(raw_cps, list):
                    raise ProjectionInputError("controlPoints must be an array")
                parsed: list[ControlPointPolicy] = []
                seen: set[int] = set()
                for raw_cp in raw_cps:
                    if not isinstance(raw_cp, dict) or ("id" in raw_cp) == ("position" in raw_cp):
                        raise ProjectionInputError("Control point policy requires exactly one of id or position")
                    cp_id = raw_cp.get("id") if "id" in raw_cp else cp_by_position.get(raw_cp.get("position"))
                    if not isinstance(cp_id, int) or cp_id not in state.control_points:
                        raise ProjectionInputError("Control point policy does not identify a target-nation control point")
                    if cp_id in seen:
                        raise ProjectionInputError(f"Duplicate control point policy: {cp_id}")
                    seen.add(cp_id)
                    raw_pips = raw_cp.get("pips")
                    if not isinstance(raw_pips, dict):
                        raise ProjectionInputError("Control point pips must be an object")
                    pips: dict[str, int] = {}
                    for priority, pip in raw_pips.items():
                        canonical = _canonical_priority(str(priority), priorities)
                        if not isinstance(pip, int) or isinstance(pip, bool) or not 0 <= pip <= 3:
                            raise ProjectionInputError(f"Priority pip must be integer 0..3: {priority}")
                        if canonical in pips:
                            raise ProjectionInputError(f"Duplicate priority alias: {priority}")
                        pips[canonical] = pip
                    parsed.append(ControlPointPolicy(cp_id, pips))
                cp_policies = tuple(parsed)
            advisors: tuple[AdvisorProfile, ...] | None = None
            if "advisors" in raw_segment:
                raw_advisors = raw_segment["advisors"]
                if not isinstance(raw_advisors, list):
                    raise ProjectionInputError("advisors must be an array")
                advisors = tuple(_resolve_advisor(value, councilors) for value in raw_advisors)
                identities = [(item.source, item.councilor_id if item.source == "saved" else item.name.casefold()) for item in advisors]
                if len(identities) != len(set(identities)):
                    raise ProjectionInputError("Duplicate advisor placement")
            segments.append(PlanSegment(until_day, until_condition, cp_policies, advisors))
        plans.append(PriorityPlan(raw_plan["name"], tuple(segments)))
    goals: list[tuple[str, MetricCondition]] = []
    raw_goals = payload.get("goals", [])
    if not isinstance(raw_goals, list):
        raise ProjectionInputError("goals must be an array")
    for raw_goal in raw_goals:
        if not isinstance(raw_goal, dict) or not isinstance(raw_goal.get("name"), str) or not raw_goal["name"]:
            raise ProjectionInputError("Each goal requires a name")
        goals.append((raw_goal["name"], _condition(raw_goal)))
    return tuple(plans), tuple(goals)


def _global(context: ProjectionContext, name: str) -> float:
    value = context.global_config[name]
    if isinstance(value, Mapping):
        value = value.get("value")
    return float(value)


def priority_coverage(priorities: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    result = {}
    for name in priorities:
        completion, rule = SUPPORTED_COMPLETIONS.get(name, ("unsupported", None))
        overall = completion
        result[name] = {
            "allocation": "exact",
            "completion": completion,
            "downstream": completion,
            "overall": overall,
            "mechanicRules": [Rules.NATION_IP_CONTROL_POINT_ALLOCATION.id, Rules.NATION_IP_PRIORITY_BONUS.id]
            + ([rule.id] if rule else []),
        }
    return result


def _priority_valid(state: NationProjectionState, priority: str) -> bool:
    if priority in {"Knowledge", "Unity"}:
        return True
    if priority == "Government":
        return state.democracy < 10.0
    if priority == "Funding":
        return state.funding_year < 0.005 * (state.gdp / 1_000_000.0)
    return True


def _effective_pips(state: NationProjectionState, cp: ControlPointProjectionState) -> dict[str, int]:
    return {name: pip for name, pip in cp.pips.items() if pip > 0 and _priority_valid(state, name)}


def _diversity_bonus(cp: ControlPointProjectionState, priority: str, effective: Mapping[str, int], context: ProjectionContext) -> float:
    total = sum(effective.values())
    if total <= 0 or len(effective) <= 1:
        return 0.0
    return sum(float(context.diversity_bonuses.get(other, 0.0)) * pip / total for other, pip in effective.items() if other != priority)


def _base_ip(state: NationProjectionState) -> float:
    admin = adviser_attribute_bonus_from_values([advisor.administration for advisor in state.advisors])
    unrest_factor = 1.0 - max(state.unrest - 2.0, 0.0) / 10.0
    return max(state.economy_score * (1.0 + admin) * state.occupation_factor * unrest_factor - state.army_maintenance, 0.0)


def _apply_completion(state: NationProjectionState, priority: str, context: ProjectionContext, used: set[str]) -> None:
    scale = (state.population_millions * 1_000_000.0 / 50_000_000.0) ** _global(context, "populationBasedIPEffectScaling") if state.population_millions > 0 else 0.0
    if priority == "Knowledge":
        used.add(Rules.NATION_PRIORITY_KNOWLEDGE_COMPLETE.id)
        change = _global(context, "knowledgePriorityEducationIncrease")
        if state.education < 8.5:
            change *= 8.5 / max(1.0, state.education)
        elif state.education >= 12.0:
            change *= 12.0 / max(1.0, state.education)
        state.education = max(0.0, state.education + scale * change)
        state.cohesion = min(10.0, max(0.0, state.cohesion + scale * (0.01 if state.cohesion < 5 else -0.01 if state.cohesion > 5 else 0.0)))
    elif priority == "Government":
        used.add(Rules.NATION_PRIORITY_GOVERNMENT_COMPLETE.id)
        if state.democracy >= 10.0:
            _apply_completion(state, "Knowledge", context, used)
        else:
            state.democracy = min(10.0, state.democracy + scale * _global(context, "governmentPriorityDemocracyIncrease") * state.education / 10.0)
    elif priority == "Unity":
        used.add(Rules.NATION_PRIORITY_UNITY_COMPLETE.id)
        base = _global(context, "unityBaseCohesionChange")
        cohesion_change = scale * min(base, max(_global(context, "unityMinCohesionChange"), base - base * 0.05 * (state.education + state.democracy)))
        state.cohesion = min(10.0, max(0.0, state.cohesion + cohesion_change))
        state.education = max(0.0, state.education + scale * _global(context, "unityPriorityEducationChange"))
    elif priority == "Funding":
        used.add(Rules.NATION_PRIORITY_FUNDING_COMPLETE.id)
        state.funding_year += _global(context, "fundingPriorityBaseIncomeIncrease") + state.num_control_points


def _contribution(state: NationProjectionState, context: ProjectionContext, used: set[str] | None = None) -> dict[str, float | int]:
    if used is not None:
        used.add(Rules.NATION_FACTION_CONTRIBUTION.id)
    owned = [cp for cp in state.control_points.values() if cp.owner_faction_id == context.faction_id and not cp.benefits_disabled]
    positions = [cp.position for cp in owned]
    sciences = [advisor.science for advisor in state.advisors]
    research = nation_monthly_research_from_values(
        population_millions=state.population_millions,
        gdp=state.gdp,
        education=state.education,
        democracy=state.democracy,
        cohesion=state.cohesion,
        unrest=state.unrest,
        num_control_points=state.num_control_points,
        advisor_sciences=sciences,
    )
    research *= context.knowledge_sector_bonus if context.knowledge_sector_owned else 1.0
    research *= context.research_effect_factor
    funding_pool = context.initial_funding_pool_year + state.funding_year - context.initial_own_funding_year
    return {
        "research": proportional_cp_contribution(research, len(owned), state.num_control_points),
        "funding": proportional_cp_contribution(funding_pool / 12.0, len(owned), state.num_control_points, sector_bonus=context.financial_sector_bonus if context.financial_sector_owned else 1.0),
        "boost": proportional_cp_contribution(context.initial_boost_pool_year / 12.0, len(owned), state.num_control_points),
        "missionControl": mission_control_contribution_from_values(state.mission_control, positions, state.num_control_points),
    }


def _nation_snapshot(state: NationProjectionState) -> dict[str, Any]:
    population = state.population_millions
    return {
        "gdp": state.gdp,
        "perCapitaGdp": state.gdp / (population * 1_000_000.0) if population else 0.0,
        "populationMillions": population,
        "inequality": state.inequality,
        "education": state.education,
        "democracy": state.democracy,
        "cohesion": state.cohesion,
        "cohesionRest": state.cohesion_rest,
        "unrest": state.unrest,
        "unrestRest": state.unrest_rest,
        "sustainability": state.sustainability,
        "militaryTech": state.military_tech,
        "fundingYear": state.funding_year,
        "boostYear": sum(region.boost_per_year for region in state.regions.values()),
        "missionControl": state.mission_control,
        "armies": state.army_count,
        "navies": state.navy_count,
        "nuclearWeapons": state.nuclear_weapons,
        "spaceDefenses": state.space_defenses,
        "stoFighters": state.sto_fighters,
        "baseInvestmentPointsMonth": _base_ip(state),
        "priorityProgress": dict(state.progress),
    }


METRIC_NAMES = frozenset({
    "nation.gdp", "nation.population", "nation.inequality", "nation.education", "nation.democracy",
    "nation.cohesion", "nation.unrest", "nation.sustainability", "nation.militaryTech", "nation.funding",
    "nation.boost", "nation.missionControl", "nation.research",
    "factionContribution.research", "factionContribution.funding", "factionContribution.boost", "factionContribution.missionControl",
})


def _metrics(state: NationProjectionState, context: ProjectionContext) -> dict[str, float]:
    nation = _nation_snapshot(state)
    contribution = _contribution(state, context)
    research = nation_monthly_research_from_values(
        population_millions=state.population_millions, gdp=state.gdp, education=state.education,
        democracy=state.democracy, cohesion=state.cohesion, unrest=state.unrest,
        num_control_points=state.num_control_points, advisor_sciences=[a.science for a in state.advisors],
    )
    return {
        "nation.gdp": state.gdp, "nation.population": state.population_millions,
        "nation.inequality": state.inequality, "nation.education": state.education,
        "nation.democracy": state.democracy, "nation.cohesion": state.cohesion,
        "nation.unrest": state.unrest, "nation.sustainability": state.sustainability,
        "nation.militaryTech": state.military_tech, "nation.funding": state.funding_year,
        "nation.boost": float(nation["boostYear"]), "nation.missionControl": float(state.mission_control),
        "nation.research": research,
        **{f"factionContribution.{key}": float(value) for key, value in contribution.items()},
    }


def _condition_met(condition: MetricCondition, metrics: Mapping[str, float], initial: Mapping[str, float]) -> bool:
    value = metrics[condition.metric]
    if condition.relative_to_start:
        value -= initial[condition.metric]
    return OPS[condition.op](value, condition.value)


def _apply_segment(state: NationProjectionState, segment: PlanSegment) -> None:
    if segment.control_points is not None:
        for policy in segment.control_points:
            state.control_points[policy.control_point_id].pips = dict(policy.pips)
    if segment.advisors is not None:
        state.advisors = segment.advisors


def _segment_met(segment: PlanSegment, day: int, metrics: Mapping[str, float], initial: Mapping[str, float]) -> bool:
    if segment.until_day is not None:
        return day >= segment.until_day
    return segment.until_condition is not None and _condition_met(segment.until_condition, metrics, initial)


def _run_investment_transaction(state: NationProjectionState, context: ProjectionContext, day: int, segment_index: int) -> dict[str, Any]:
    used = {
        Rules.NATION_IP_BASE.id,
        Rules.NATION_IP_CONTROL_POINT_ALLOCATION.id,
        Rules.NATION_IP_PRIORITY_BONUS.id,
        Rules.NATION_PRIORITY_COMPLETION_ORDER.id,
        Rules.NATION_ADVISOR_ATTRIBUTE_SOURCE.id,
        Rules.NATION_ADVISOR_STACKING.id,
    }
    allocation = {name: 0.0 for name in context.priorities}
    base_ip = _base_ip(state)
    cp_ip = base_ip / state.num_control_points if state.num_control_points else 0.0
    for cp in sorted(state.control_points.values(), key=lambda value: value.position):
        effective = _effective_pips(state, cp)
        total = sum(effective.values())
        if total <= 0:
            effective = {"Economy": 1}
            total = 1
        for priority, pip in effective.items():
            bonus = 0.0 if cp.benefits_disabled else cp.priority_bonuses.get(priority, 0.0)
            bonus += _diversity_bonus(cp, priority, effective, context)
            allocation[priority] += cp_ip * pip / total * (1.0 + bonus) * 12.0 / DAYS_PER_YEAR
    for priority, amount in allocation.items():
        state.progress[priority] = max(0.0, state.progress.get(priority, 0.0) + amount)
    completions: list[dict[str, Any]] = []
    ordered = sorted(context.priorities, key=lambda name: int(context.priorities[name]["enumValue"]))
    for priority in ordered:
        cost = float(context.priorities[priority]["investmentCost"]) / max(context.national_ip_multiplier, 1e-12)
        while state.progress.get(priority, 0.0) + 1e-12 >= cost and _priority_valid(state, priority):
            _apply_completion(state, priority, context, used)
            state.progress[priority] -= cost
            completions.append({"day": day, "priority": priority, "cost": cost, "remainingProgress": state.progress[priority]})
    return {
        "sequence": day,
        "kind": "investment",
        "day": day,
        "segmentIndex": segment_index,
        "baseInvestmentPointsMonth": base_ip,
        "allocation": {name: value for name, value in allocation.items() if value},
        "completions": completions,
        "mechanicRules": sorted(used),
    }


def _run_monthly_transaction(state: NationProjectionState, context: ProjectionContext, day: int) -> tuple[dict[str, Any], bool]:
    used = {Rules.NATION_PERIODIC_COHESION.id, Rules.NATION_PERIODIC_UNREST.id, Rules.NATION_PERIODIC_POPULATION.id}
    if state.cohesion < state.cohesion_rest:
        state.cohesion += min(_global(context, "maxMonthlyCohesionIncrease_normal"), state.cohesion_rest - state.cohesion)
    elif state.cohesion > state.cohesion_rest:
        normal = max(0.0, state.inequality - 3.0) ** 2 / 10.0
        cap = min(max(normal, _global(context, "maxMonthlyCohesionDecrease_normal")), _global(context, "maxMonthlyCohesionDecrease_cap"))
        state.cohesion -= min(cap, state.cohesion - state.cohesion_rest)
    if state.unrest < state.unrest_rest:
        limit = _global(context, "maxMonthlyUnrestMovement_rapidIncrease") if state.cohesion == 0 else _global(context, "maxMonthlyUnrestMovement_normal")
        state.unrest += min(limit, state.unrest_rest - state.unrest)
    elif state.unrest > state.unrest_rest:
        state.unrest -= min(_global(context, "maxMonthlyUnrestMovement_normal"), state.unrest - state.unrest_rest)
    population_supported = all(region.annual_population_growth is not None for region in state.regions.values())
    if population_supported:
        for region in state.regions.values():
            old = region.population_millions
            region.population_millions = max(old * (1.0 + float(region.annual_population_growth)) ** (1.0 / 12.0), 0.001)
            delta = region.population_millions - old
            state.gdp += region.per_capita_gdp * delta * 1_000_000.0
            if delta < 0:
                state.education += max(-0.005, min(0.0, delta / 100.0))
    return ({"kind": "periodic", "day": day, "mechanicRules": sorted(used), "populationCoverage": "expected" if population_supported else "unsupported"}, population_supported)


def _unsupported_priorities(state: NationProjectionState, plan: PriorityPlan, coverage: Mapping[str, Mapping[str, Any]]) -> list[str]:
    pips = {cp.id: dict(cp.pips) for cp in state.control_points.values()}
    unsupported: set[str] = set()
    for segment in plan.segments:
        if segment.control_points is not None:
            for policy in segment.control_points:
                pips[policy.control_point_id] = dict(policy.pips)
        for cp_pips in pips.values():
            unsupported.update(name for name, value in cp_pips.items() if value > 0 and coverage[name]["overall"] == "unsupported")
    return sorted(unsupported)


def run_projection(
    initial_state: NationProjectionState,
    plan: PriorityPlan,
    context: ProjectionContext,
    *,
    days: int,
    checkpoints: Iterable[int] = (),
    goals: tuple[tuple[str, MetricCondition], ...] = (),
    details: bool = False,
) -> dict[str, Any]:
    state = copy.deepcopy(initial_state)
    coverage = priority_coverage(context.priorities)
    unsupported = _unsupported_priorities(state, plan, coverage)
    initial_metrics = _metrics(state, context)
    if unsupported:
        return {
            "name": plan.name,
            "status": "incomplete",
            "unsupportedPriorities": unsupported,
            "currentAllocation": {str(cp.position): dict(cp.pips) for cp in state.control_points.values()},
            "authoritativeFinalState": None,
            "limitations": ["Nonzero pips reference priority completion/downstream mechanics that are not audited."],
            "mechanicRuleIds": [],
            "coverage": {name: coverage[name] for name in unsupported},
        }
    segment_index = 0
    _apply_segment(state, plan.segments[0])
    transitions: list[dict[str, Any]] = [{"day": 0, "from": None, "to": 0, "reason": "planStart"}]
    advisor_transitions: list[dict[str, Any]] = [{"day": 0, "advisors": [item.output() for item in state.advisors]}]
    while segment_index < len(plan.segments) - 1 and _segment_met(plan.segments[segment_index], 0, _metrics(state, context), initial_metrics):
        prior = segment_index
        segment_index += 1
        _apply_segment(state, plan.segments[segment_index])
        transitions.append({"day": 0, "from": prior, "to": segment_index, "reason": "satisfiedAtStart"})
        advisor_transitions.append({"day": 0, "advisors": [item.output() for item in state.advisors]})
    transactions: list[dict[str, Any]] = []
    completion_events: list[dict[str, Any]] = []
    checkpoint_set = set(checkpoints)
    checkpoint_rows: list[dict[str, Any]] = []
    used: set[str] = set()
    goal_first = {name: (0 if _condition_met(condition, initial_metrics, initial_metrics) else None) for name, condition in goals}
    incomplete_reasons: list[str] = []
    advisor_used = bool(state.advisors)
    current_date = state.at
    for day in range(1, days + 1):
        transaction = _run_investment_transaction(state, context, day, segment_index)
        transactions.append(transaction)
        completion_events.extend(transaction["completions"])
        used.update(transaction["mechanicRules"])
        current_date += timedelta(days=1)
        if current_date.day == 1:
            periodic, population_supported = _run_monthly_transaction(state, context, day)
            transactions.append(periodic)
            used.update(periodic["mechanicRules"])
            if not population_supported and "population periodic rule is unsupported for this save" not in incomplete_reasons:
                incomplete_reasons.append("population periodic rule is unsupported for this save")
        metrics = _metrics(state, context)
        for name, condition in goals:
            if goal_first[name] is None and _condition_met(condition, metrics, initial_metrics):
                goal_first[name] = day
        if day in checkpoint_set:
            checkpoint_rows.append({"day": day, "nation": _nation_snapshot(state), "factionContribution": _contribution(state, context, used)})
        if segment_index < len(plan.segments) - 1 and _segment_met(plan.segments[segment_index], day, metrics, initial_metrics):
            prior = segment_index
            segment_index += 1
            transitions.append({"day": day, "effectiveDay": day + 1, "from": prior, "to": segment_index, "reason": "conditionSatisfiedAfterTransaction"})
            before = state.advisors
            _apply_segment(state, plan.segments[segment_index])
            if state.advisors != before:
                advisor_transitions.append({"day": day, "effectiveDay": day + 1, "advisors": [item.output() for item in state.advisors]})
        advisor_used = advisor_used or bool(state.advisors)
    final_nation = _nation_snapshot(state)
    final_contribution = _contribution(state, context, used)
    status = "incomplete" if incomplete_reasons else "complete"
    result = {
        "name": plan.name,
        "status": status,
        "nationProjection": final_nation,
        "factionContribution": final_contribution,
        "authoritativeFinalState": {"nation": final_nation, "factionContribution": final_contribution} if status == "complete" else None,
        "segmentTransitions": transitions,
        "advisorTransitions": advisor_transitions,
        "completionEvents": completion_events,
        "checkpoints": checkpoint_rows,
        "goalResults": [{"name": name, "met": goal_first[name] is not None, "firstMetDay": goal_first[name]} for name, _ in goals],
        "coverage": coverage,
        "mechanicRuleIds": sorted(used),
        "inputProvenance": "hypotheticalPolicy" if advisor_used else "saveStateAndPlan",
        "limitations": incomplete_reasons + ["Exogenous events, missions, wars, ownership changes and player actions are held fixed."],
    }
    if details:
        result["transactions"] = transactions
    return result


def projection_output(
    initial_state: NationProjectionState,
    plans: tuple[PriorityPlan, ...],
    context: ProjectionContext,
    *,
    days: int,
    checkpoints: Iterable[int],
    goals: tuple[tuple[str, MetricCondition], ...],
    details: bool,
    diagnostics: bool,
    faction_context: Mapping[str, Any],
    source_notes: list[str],
) -> dict[str, Any]:
    initial_used: set[str] = set()
    initial = {"nation": _nation_snapshot(initial_state), "factionContribution": _contribution(initial_state, context, initial_used)}
    results = [run_projection(initial_state, plan, context, days=days, checkpoints=checkpoints, goals=goals, details=details) for plan in plans]
    complete = [result for result in results if result["status"] == "complete"]
    nation_metrics: dict[str, Any] = {}
    faction_metrics: dict[str, Any] = {}
    for result in complete:
        nation_metrics[result["name"]] = result["nationProjection"]
        faction_metrics[result["name"]] = result["factionContribution"]
    all_rule_ids = initial_used | {rule_id for result in results for rule_id in result["mechanicRuleIds"]}
    output = {
        "initialState": initial,
        "factionContext": dict(faction_context),
        "plans": results,
        "comparison": {"nationMetrics": nation_metrics, "factionContributionMetrics": faction_metrics, "excludedIncompletePlans": [result["name"] for result in results if result["status"] != "complete"]},
        "coverage": priority_coverage(context.priorities),
        "mechanicRulesUsed": mechanic_diagnostics(all_rule_ids) if diagnostics else sorted(all_rule_ids),
        "limitations": sorted({limitation for result in results for limitation in result["limitations"]}),
        "sourceNotes": source_notes,
    }
    return output
