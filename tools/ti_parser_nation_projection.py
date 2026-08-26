"""Fail-closed nation priority and conditional Advisor projection engine."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, time, timedelta
import copy
import math
import operator
from typing import Any, Callable, Iterable, Mapping

from ti_parser_income import (
    adviser_attribute_bonus_from_values,
    mission_control_contribution_from_values,
    nation_monthly_research_from_values,
    proportional_cp_contribution,
)
from ti_parser_mechanics import Rules, mechanic_diagnostics, validate_rule_execution


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
STATIC_COMPLETIONS = {
    "Knowledge": ("exact", Rules.NATION_PRIORITY_KNOWLEDGE_COMPLETE),
    "Government": ("exact", Rules.NATION_PRIORITY_GOVERNMENT_COMPLETE),
    "Welfare": ("exact", Rules.NATION_PRIORITY_WELFARE_COMPLETE),
    "MissionControl": ("exact", Rules.NATION_PRIORITY_MISSION_CONTROL_COMPLETE),
    "Military_BuildArmy": ("exact", Rules.NATION_PRIORITY_BUILD_ARMY_COMPLETE),
    "Funding": ("exact", Rules.NATION_PRIORITY_FUNDING_COMPLETE),
}
COMPLETION_RULES = {
    "Economy": Rules.NATION_PRIORITY_ECONOMY_COMPLETE,
    "Welfare": Rules.NATION_PRIORITY_WELFARE_COMPLETE,
    "Environment": Rules.NATION_PRIORITY_ENVIRONMENT_COMPLETE,
    "Knowledge": Rules.NATION_PRIORITY_KNOWLEDGE_COMPLETE,
    "Government": Rules.NATION_PRIORITY_GOVERNMENT_COMPLETE,
    "Unity": Rules.NATION_PRIORITY_UNITY_COMPLETE,
    "Oppression": Rules.NATION_PRIORITY_OPPRESSION_COMPLETE,
    "Funding": Rules.NATION_PRIORITY_FUNDING_COMPLETE,
    "Spoils": Rules.NATION_PRIORITY_SPOILS_COMPLETE,
    "Civilian_InitiateSpaceflightProgram": Rules.NATION_PRIORITY_SPACEFLIGHT_COMPLETE,
    "LaunchFacilities": Rules.NATION_PRIORITY_BOOST_COMPLETE,
    "MissionControl": Rules.NATION_PRIORITY_MISSION_CONTROL_COMPLETE,
    "Military_FoundMilitary": Rules.NATION_PRIORITY_FOUND_MILITARY_COMPLETE,
    "Military": Rules.NATION_PRIORITY_MILITARY_COMPLETE,
    "Military_BuildArmy": Rules.NATION_PRIORITY_BUILD_ARMY_COMPLETE,
    "Military_BuildNavy": Rules.NATION_PRIORITY_BUILD_NAVY_COMPLETE,
    "Military_InitiateNuclearProgram": Rules.NATION_PRIORITY_INITIATE_NUCLEAR_COMPLETE,
    "Military_BuildNuclearWeapons": Rules.NATION_PRIORITY_BUILD_NUCLEAR_COMPLETE,
    "Military_BuildSpaceDefenses": Rules.NATION_PRIORITY_SPACE_DEFENSE_COMPLETE,
    "Military_BuildSTOSquadron": Rules.NATION_PRIORITY_STO_COMPLETE,
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


class ProjectionRuntimeStop(RuntimeError):
    """A transaction discovered a dependency that cannot be applied authoritatively."""

    def __init__(
        self,
        reason: str,
        *,
        rule_ids: Iterable[str] = (),
        dependencies: Iterable[Mapping[str, Any]] = (),
        affected_metrics: Iterable[str] = (),
        trace: Iterable[Mapping[str, Any]] = (),
    ) -> None:
        super().__init__(reason)
        self.reason = reason
        self.rule_ids = tuple(rule_ids)
        self.dependencies = tuple(dict(item) for item in dependencies)
        self.affected_metrics = tuple(affected_metrics)
        self.trace = tuple(dict(item) for item in trace)


@dataclass
class RegionProjectionState:
    id: int
    population_millions: float
    boost_per_year: float = 0.0
    mission_control: int = 0
    annual_population_growth: float | None = None
    per_capita_gdp: float = 0.0
    gdp: float | None = None
    region_order: int = 0
    template_name: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    annual_population_growth_modifier: float | None = None
    environment: str | None = None
    xenoforming_level: float | None = None
    nuclear_detonations: int | None = None
    colony: bool | None = None
    permanent_colony: bool | None = None
    resource_region: bool | None = None
    oil_region: bool | None = None
    core_economic_region: bool | None = None
    mine_capable: bool | None = None
    oil_capable: bool | None = None
    capital: bool | None = None
    occupation_fraction: float | None = None
    fully_occupied: bool | None = None
    mission_control_cap: int | None = None
    welfare_colony_counter: int | None = None
    economy_region_counters: dict[str, int] = field(default_factory=dict)
    adjacent_region_ids: tuple[int, ...] = ()


@dataclass
class ArmyProjectionState:
    id: int
    strength: float
    deployment_type: str
    home_region_id: int
    current_region_id: int
    control_point_position: int
    faction_id: int | None
    operations: float = 0.0
    destroyed: bool = False


@dataclass
class ControlPointProjectionState:
    id: int
    position: int
    owner_faction_id: int | None
    benefits_disabled: bool
    control_point_type: str | None
    pips: dict[str, int]
    priority_bonuses: dict[str, float] = field(default_factory=dict)
    total_weight: int = 0
    num_priorities_with_weight: int = 0
    diversity_bonus_cache: dict[str, float] = field(default_factory=dict)


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
    days_in_campaign: float = 0.0
    current_quarter: int = 0
    pcgdp_tracker: dict[int, float] = field(default_factory=dict)
    military: bool = False
    space_flight_program: bool = False
    nuclear_program: bool = False
    can_build_space_defenses: bool = False
    can_build_sto: bool = False
    num_control_points_unclamped: int | None = None
    legitimize_counter: float = 0.0
    hostile_region_ids: set[int] = field(default_factory=set)
    executive_faction_id: int | None = None
    public_opinion_context: dict[str, Any] = field(default_factory=dict)
    rest_state_context: dict[str, Any] = field(default_factory=dict)
    armies: list[ArmyProjectionState] = field(default_factory=list)
    world_context: dict[str, float] = field(default_factory=dict)
    world_context_provenance: str = "heldFixedWorldContext"
    population_mean_path: bool = False
    metric_provenance: dict[str, set[str]] = field(default_factory=dict)
    federation_economy_bonus: float = 0.0

    @property
    def population_millions(self) -> float:
        return sum(region.population_millions for region in self.regions.values())

    @property
    def num_control_points(self) -> int:
        return len(self.control_points)

    @property
    def standard_armies(self) -> list[ArmyProjectionState]:
        return [army for army in self.armies if not army.destroyed and army.deployment_type.casefold() != "naval"]


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
    nation_template: Mapping[str, Any] = field(default_factory=dict)
    region_templates: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    start_template: Mapping[str, Any] = field(default_factory=dict)
    faction_priority_modifiers: Mapping[int, Mapping[str, float]] = field(default_factory=dict)


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
    if name not in context.global_config:
        raise ProjectionRuntimeStop(
            f"Required nation-development value is unavailable: {name}",
            dependencies=({"field": name, "source": "nationDevelopment.globalConfig"},),
        )
    value = context.global_config[name]
    if isinstance(value, Mapping):
        value = value.get("value")
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ProjectionRuntimeStop(
            f"Required nation-development value is not numeric: {name}",
            dependencies=({"field": name, "source": "nationDevelopment.globalConfig"},),
        )
    return float(value)


def priority_coverage(priorities: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    result = {}
    for name in priorities:
        completion, supported_rule = STATIC_COMPLETIONS.get(name, ("unsupported", None))
        if name == "Unity":
            completion, supported_rule = "unsupported", Rules.NATION_PRIORITY_UNITY_COMPLETE
        rule = COMPLETION_RULES.get(name, supported_rule)
        overall = completion
        resolver_rule = (
            Rules.NATION_PRIORITY_MISSION_CONTROL_PLACEMENT if name == "MissionControl"
            else Rules.NATION_PRIORITY_BUILD_ARMY_PLACEMENT if name == "Military_BuildArmy"
            else None
        )
        conditional = resolver_rule is not None
        result[name] = {
            "allocation": "exact",
            "completion": completion,
            "downstream": completion,
            "overall": overall,
            "coverageMode": "conditional" if conditional else "static",
            "allowedCoverages": list(resolver_rule.allowed_coverages) if resolver_rule else [overall],
            "coverageResolverId": resolver_rule.coverage_resolver_id if resolver_rule else None,
            "mechanicRules": [Rules.NATION_IP_CONTROL_POINT_ALLOCATION.id, Rules.NATION_IP_PRIORITY_BONUS.id]
            + ([rule.id] if rule else []),
        }
    return result


def _region_gdp_value(state: NationProjectionState, region: RegionProjectionState, context: ProjectionContext) -> float:
    weights: dict[int, float] = {}
    for item in state.regions.values():
        if item.colony is None or item.core_economic_region is None or item.resource_region is None or item.oil_region is None:
            raise ProjectionRuntimeStop(
                "Regional GDP allocation inputs are incomplete",
                dependencies=({"field": "region.gdpWeightInputs", "source": f"save.region.{item.id}"},),
                affected_metrics=("nation.missionControl", "nation.population", "nation.gdp"),
            )
        weight = item.population_millions
        if item.core_economic_region:
            weight *= _global(context, "coreEcoRegionGDPModifier")
        if item.resource_region or item.oil_region:
            weight *= _global(context, "coreResourceRegionGDPModifier")
        if item.colony:
            weight *= _global(context, "colonyRegionGDPModifier")
        weights[item.id] = weight
    total = sum(weights.values())
    return state.gdp * weights[region.id] / total if total > 0 else 0.0


def _region_mc_cap(state: NationProjectionState, region: RegionProjectionState, context: ProjectionContext) -> int:
    regional_gdp = _region_gdp_value(state, region, context)
    divisor = max(200.0, 300.0 - 6.0 * state.education)
    derived = 1 + int((regional_gdp / 1_000_000_000.0) / divisor)
    return max(region.mission_control, derived)


def _allowed_armies(state: NationProjectionState, context: ProjectionContext) -> int:
    if not state.military:
        return 0
    minimum = _global(context, "minPopulationForFirstArmy_millions")
    if state.population_millions < minimum:
        return 0
    eligible = 0
    for region in state.regions.values():
        if region.colony is None or region.fully_occupied is None:
            raise ProjectionRuntimeStop(
                "Army validity requires colony and occupation state",
                rule_ids=(Rules.NATION_PRIORITY_VALIDITY.id, Rules.NATION_PRIORITY_BUILD_ARMY_PLACEMENT.id),
                dependencies=({"field": "region.colony/fullyOccupied", "source": f"save.region.{region.id}"},),
                affected_metrics=("nation.armies", "nation.baseInvestmentPointsMonth"),
            )
        if not region.colony and not region.fully_occupied:
            eligible += 1
    interval = _global(context, "minPopulationForAdditionalArmiesPer_millions")
    return min(eligible, 1 + int(state.population_millions / interval))


def _priority_valid(state: NationProjectionState, priority: str, context: ProjectionContext) -> bool:
    if priority in {"Economy", "Welfare", "Environment", "Knowledge", "Unity", "Oppression", "Spoils", "LaunchFacilities", "Military"}:
        return True
    if priority == "Government":
        return state.democracy < 10.0 or any(region_id in state.regions for region_id in state.hostile_region_ids)
    if priority == "Funding":
        return state.funding_year < 0.005 * (state.gdp / 1_000_000.0)
    if priority == "MissionControl":
        if not state.space_flight_program:
            return False
        return any(region.mission_control < _region_mc_cap(state, region, context) for region in state.regions.values())
    if priority == "Military_BuildArmy":
        return _allowed_armies(state, context) > len(state.standard_armies)
    if priority == "Military_FoundMilitary":
        return not state.military
    if priority == "Civilian_InitiateSpaceflightProgram":
        return not state.space_flight_program
    if priority == "Military_InitiateNuclearProgram":
        return state.military and not state.nuclear_program
    if priority == "Military_BuildNuclearWeapons":
        return state.nuclear_program
    if priority == "Military_BuildSpaceDefenses":
        return state.military and state.can_build_space_defenses
    if priority == "Military_BuildSTOSquadron":
        return state.military and state.can_build_sto and any(region.boost_per_year > 0 for region in state.regions.values())
    return False


def _effective_pips(state: NationProjectionState, cp: ControlPointProjectionState, context: ProjectionContext) -> dict[str, int]:
    return {name: pip for name, pip in cp.pips.items() if pip > 0 and _priority_valid(state, name, context)}


def _record_and_fix_control_point(
    state: NationProjectionState,
    cp: ControlPointProjectionState,
    context: ProjectionContext,
    *,
    trace: list[dict[str, Any]] | None = None,
) -> dict[str, int]:
    effective = _effective_pips(state, cp, context)
    if not effective:
        cp.pips["Economy"] = 1
        effective = {"Economy": 1}
        if trace is not None:
            trace.append({"operation": "defaultEconomy", "controlPointPosition": cp.position, "rawPips": dict(cp.pips)})
    cp.total_weight = sum(effective.values())
    cp.num_priorities_with_weight = len(effective)
    cp.diversity_bonus_cache = {
        priority: _diversity_bonus(cp, priority, effective, context) for priority in effective
    }
    return effective


def _diversity_bonus(cp: ControlPointProjectionState, priority: str, effective: Mapping[str, int], context: ProjectionContext) -> float:
    total = sum(effective.values())
    if total <= 0 or len(effective) <= 1:
        return 0.0
    return sum(float(context.diversity_bonuses.get(other, 0.0)) * pip / total for other, pip in effective.items() if other != priority)


def _national_priority_bonus(state: NationProjectionState, priority: str, context: ProjectionContext) -> float:
    if priority == "Economy":
        return state.federation_economy_bonus * _global(context, "federationGDPEconomyBonus")
    if priority in {"Military_BuildArmy", "Military_BuildNavy"}:
        mining_regions = sum(
            1 for region in state.regions.values()
            if region.resource_region is True and region.fully_occupied is False
        )
        return mining_regions * _global(context, "coreMineralBuildMilitaryModifier")
    return 0.0


def _army_maintenance(state: NationProjectionState, context: ProjectionContext) -> float:
    if not state.armies:
        return state.army_maintenance
    total = 0.0
    for army in state.armies:
        if army.destroyed:
            continue
        home = army.home_region_id == army.current_region_id
        total += _global(context, "nationalInvestmentArmyFactorHome" if home else "nationalInvestmentArmyFactorAway")
        if army.deployment_type.casefold() == "naval":
            total += _global(context, "nationalInvestmentNavyFactor")
    return total


def _base_ip(state: NationProjectionState, context: ProjectionContext | None = None) -> float:
    admin = adviser_attribute_bonus_from_values([advisor.administration for advisor in state.advisors])
    unrest_factor = 1.0 - max(state.unrest - 2.0, 0.0) / 10.0
    maintenance = _army_maintenance(state, context) if context is not None else state.army_maintenance
    return max(state.economy_score * (1.0 + admin) * state.occupation_factor * unrest_factor - maintenance, 0.0)


def _refresh_economy_score(state: NationProjectionState, context: ProjectionContext, used: set[str] | None = None) -> None:
    state.economy_score = (state.gdp / 1_000_000_000.0) ** _global(context, "controlPointIPScaling") * _global(context, "controlPointIPFactor")
    if used is not None:
        used.add(Rules.NATION_IP_ECONOMY_SCORE.id)


def _population_scaling(state: NationProjectionState, context: ProjectionContext) -> float:
    if state.population_millions <= 0:
        return 0.0
    return (state.population_millions * 1_000_000.0 / 50_000_000.0) ** _global(context, "populationBasedIPEffectScaling")


def _next_legitimize_region(state: NationProjectionState) -> RegionProjectionState | None:
    candidates = [state.regions[region_id] for region_id in state.hostile_region_ids if region_id in state.regions]
    if not candidates:
        return None
    non_hostile = set(state.regions) - state.hostile_region_ids
    return sorted(
        candidates,
        key=lambda region: (
            -int(any(adjacent in non_hostile for adjacent in region.adjacent_region_ids)),
            -region.population_millions,
            region.region_order,
        ),
    )[0]


def _welfare_modifier(state: NationProjectionState, context: ProjectionContext) -> float:
    if state.executive_faction_id is None:
        return 0.0
    return float(context.faction_priority_modifiers.get(state.executive_faction_id, {}).get("WelfareInequalityReductionBonus", 0.0))


def _mission_control_candidates(state: NationProjectionState, context: ProjectionContext) -> list[RegionProjectionState]:
    candidates = []
    for region in state.regions.values():
        if region.fully_occupied is None:
            raise ProjectionRuntimeStop(
                "Mission Control placement requires occupation state",
                rule_ids=(Rules.NATION_PRIORITY_MISSION_CONTROL_PLACEMENT.id,),
                dependencies=({"field": "region.fullyOccupied", "source": f"save.region.{region.id}"},),
                affected_metrics=("nation.missionControl", "factionContribution.missionControl"),
            )
        if not region.fully_occupied and region.mission_control < _region_mc_cap(state, region, context):
            candidates.append(region)
    return candidates


def _equivalent_mc_candidates(candidates: list[RegionProjectionState]) -> bool:
    signatures = {
        (region.mission_control, region.colony, region.capital, region.core_economic_region, region.fully_occupied, region.mission_control_cap)
        for region in candidates
    }
    return len(signatures) <= 1


def _next_army_region(state: NationProjectionState) -> RegionProjectionState | None:
    homes = {army.home_region_id for army in state.standard_armies}
    candidates = []
    for region in state.regions.values():
        if region.fully_occupied is None or region.colony is None or region.core_economic_region is None:
            raise ProjectionRuntimeStop(
                "BuildArmy placement requires region occupation, colony and core-economic state",
                rule_ids=(Rules.NATION_PRIORITY_BUILD_ARMY_PLACEMENT.id,),
                dependencies=({"field": "region.armyPlacementInputs", "source": f"save.region.{region.id}"},),
                affected_metrics=("nation.armies", "nation.baseInvestmentPointsMonth"),
            )
        if not region.fully_occupied and not region.colony and region.id not in homes:
            candidates.append(region)
    if any(region.core_economic_region for region in candidates):
        candidates = [region for region in candidates if region.core_economic_region]
    return max(candidates, key=lambda region: region.population_millions, default=None)


def _next_army_control_point_position(state: NationProjectionState) -> int:
    positions = sorted((cp.position for cp in state.control_points.values()))
    counts = {position: 0 for position in positions}
    for army in state.standard_armies:
        if army.control_point_position in counts:
            counts[army.control_point_position] += 1
    maximum = max(counts.values(), default=0)
    selected = positions[-1]
    selected_count = selected
    for position in reversed(positions):
        count = counts[position]
        if count < maximum and count < selected_count:
            selected = position
            selected_count = count
    return selected


def _apply_completion(
    state: NationProjectionState,
    priority: str,
    context: ProjectionContext,
    used: set[str],
    *,
    trace: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    scale = _population_scaling(state, context)
    execution: dict[str, Any] = {
        "ruleId": COMPLETION_RULES[priority].id,
        "effectiveCoverage": "exact",
        "provenance": "dllReimplementation",
        "dependencies": [],
    }
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
            _apply_completion(state, "Knowledge", context, used, trace=trace)
        else:
            state.democracy = min(10.0, state.democracy + scale * _global(context, "governmentPriorityDemocracyIncrease") * state.education / 10.0)
        if state.hostile_region_ids:
            used.add(Rules.NATION_PRIORITY_GOVERNMENT_LEGITIMIZE.id)
            state.legitimize_counter += 1.0
            threshold = _global(context, "numPrioritiesForLegitimize")
            if state.legitimize_counter >= threshold:
                target = _next_legitimize_region(state)
                if target is not None:
                    state.hostile_region_ids.remove(target.id)
                    state.legitimize_counter = 0.0
                    execution["removedHostileClaimRegionId"] = target.id
                    if trace is not None:
                        trace.append({"operation": "removeHostileClaim", "regionId": target.id})
            execution["dependencies"].append(Rules.NATION_PRIORITY_GOVERNMENT_LEGITIMIZE.id)
    elif priority == "Welfare":
        used.update({Rules.NATION_PRIORITY_WELFARE_COMPLETE.id, Rules.NATION_PRIORITY_WELFARE_INEQUALITY.id})
        state.inequality = min(9.0, max(1.0, state.inequality + (_global(context, "welfarePriorityInequalityChange") + _welfare_modifier(state, context)) * scale))
        execution["dependencies"].append(Rules.NATION_PRIORITY_WELFARE_INEQUALITY.id)
        colonies = [region for region in state.regions.values() if region.colony is True]
        if colonies:
            used.add(Rules.NATION_PRIORITY_WELFARE_COLONY_TRIGGER.id)
            execution["dependencies"].append(Rules.NATION_PRIORITY_WELFARE_COLONY_TRIGGER.id)
            if any(region.welfare_colony_counter is None for region in colonies):
                raise ProjectionRuntimeStop(
                    "Welfare colony trigger requires the saved decolonization counter",
                    rule_ids=(Rules.NATION_PRIORITY_WELFARE_COLONY_TRIGGER.id,),
                    dependencies=({"field": "accumulatedDecolonizeTriggers", "source": "save.region"},),
                    affected_metrics=("nation.inequality", "nation.population", "nation.missionControl", "nation.armies"),
                )
            target = sorted(
                colonies,
                key=lambda region: (
                    -int(region.welfare_colony_counter or 0),
                    -_region_gdp_value(state, region, context),
                    -region.population_millions,
                    region.region_order,
                ),
            )[0]
            next_counter = int(target.welfare_colony_counter or 0) + 1
            if next_counter >= 1000:
                used.update({Rules.NATION_PRIORITY_WELFARE_DECOLONIZATION.id, Rules.NATION_PRIORITY_WELFARE_DECOLONIZATION_DOWNSTREAM.id})
                execution["dependencies"].extend([
                    Rules.NATION_PRIORITY_WELFARE_DECOLONIZATION.id,
                    Rules.NATION_PRIORITY_WELFARE_DECOLONIZATION_DOWNSTREAM.id,
                ])
                if target.permanent_colony is None or target.fully_occupied is None or target.gdp is None:
                    raise ProjectionRuntimeStop(
                        "Decolonization downstream state is incomplete",
                        rule_ids=(Rules.NATION_PRIORITY_WELFARE_DECOLONIZATION_DOWNSTREAM.id,),
                        dependencies=({"field": "region.decolonizationDownstream", "source": f"save.region.{target.id}"},),
                        affected_metrics=("nation.population", "nation.missionControl", "nation.armies", "nation.cohesionRest"),
                    )
                target.colony = False
                target.permanent_colony = True
                target.welfare_colony_counter = 0
                execution["decolonizedRegionId"] = target.id
            else:
                target.welfare_colony_counter = next_counter
            if trace is not None:
                trace.append({"operation": "welfareColonyCounter", "regionId": target.id, "value": target.welfare_colony_counter})
    elif priority == "Unity":
        raise ProjectionRuntimeStop(
            "Unity public-opinion side effects are not implemented",
            rule_ids=(Rules.NATION_PRIORITY_UNITY_COMPLETE.id,),
            affected_metrics=("nation.cohesion", "nation.cohesionRest", "factionContribution.research"),
        )
    elif priority == "Funding":
        used.add(Rules.NATION_PRIORITY_FUNDING_COMPLETE.id)
        state.funding_year += _global(context, "fundingPriorityBaseIncomeIncrease") + state.num_control_points
    elif priority == "MissionControl":
        used.update({Rules.NATION_PRIORITY_MISSION_CONTROL_COMPLETE.id, Rules.NATION_PRIORITY_MISSION_CONTROL_PLACEMENT.id})
        execution["ruleId"] = Rules.NATION_PRIORITY_MISSION_CONTROL_PLACEMENT.id
        execution["coverageResolverId"] = Rules.NATION_PRIORITY_MISSION_CONTROL_PLACEMENT.coverage_resolver_id
        execution["dependencies"].append(Rules.NATION_PRIORITY_MISSION_CONTROL_PLACEMENT.id)
        candidates = _mission_control_candidates(state, context)
        if not candidates:
            for cp in sorted(state.control_points.values(), key=lambda value: value.position):
                cp.pips["MissionControl"] = 0
                if trace is not None:
                    trace.append({"operation": "setPriority", "priority": "MissionControl", "value": 0, "controlPointPosition": cp.position})
                _record_and_fix_control_point(state, cp, context, trace=trace)
            execution["candidateCount"] = 0
            execution["noAssetCreated"] = True
        elif len(candidates) == 1:
            target = candidates[0]
            target.mission_control += 1
            state.mission_control += 1
            execution.update({"candidateCount": 1, "regionId": target.id})
        elif _equivalent_mc_candidates(candidates):
            target = min(candidates, key=lambda region: region.region_order)
            target.mission_control += 1
            state.mission_control += 1
            execution.update({"candidateCount": len(candidates), "regionId": target.id, "effectiveCoverage": "aggregateOnly"})
        else:
            raise ProjectionRuntimeStop(
                "Mission Control has multiple non-equivalent stochastic placement candidates",
                rule_ids=(Rules.NATION_PRIORITY_MISSION_CONTROL_PLACEMENT.id,),
                affected_metrics=("nation.missionControl", "factionContribution.missionControl"),
                trace=trace or (),
            )
    elif priority == "Military_BuildArmy":
        used.update({Rules.NATION_PRIORITY_BUILD_ARMY_COMPLETE.id, Rules.NATION_PRIORITY_BUILD_ARMY_PLACEMENT.id})
        execution["ruleId"] = Rules.NATION_PRIORITY_BUILD_ARMY_PLACEMENT.id
        execution["coverageResolverId"] = Rules.NATION_PRIORITY_BUILD_ARMY_PLACEMENT.coverage_resolver_id
        execution["dependencies"].append(Rules.NATION_PRIORITY_BUILD_ARMY_PLACEMENT.id)
        target = _next_army_region(state)
        if target is None:
            for cp in sorted(state.control_points.values(), key=lambda value: value.position):
                cp.pips["Military_BuildArmy"] = 0
                _record_and_fix_control_point(state, cp, context, trace=trace)
            execution["noAssetCreated"] = True
        else:
            position = _next_army_control_point_position(state)
            cp = next(cp for cp in state.control_points.values() if cp.position == position)
            new_id = min([army.id for army in state.armies] + [0]) - 1
            state.armies.append(ArmyProjectionState(
                id=new_id,
                strength=1.0,
                deployment_type="Standard",
                home_region_id=target.id,
                current_region_id=target.id,
                control_point_position=position,
                faction_id=cp.owner_faction_id,
                operations=0.0,
            ))
            state.army_count += 1
            used.add(Rules.NATION_ASSET_ARMY_MAINTENANCE.id)
            execution.update({"homeRegionId": target.id, "controlPointPosition": position})
            if trace is not None:
                trace.append({"operation": "createArmy", "homeRegionId": target.id, "controlPointPosition": position})
    else:
        raise ProjectionRuntimeStop(
            f"Priority completion is not implemented: {priority}",
            rule_ids=(COMPLETION_RULES[priority].id,),
        )
    return execution


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


def _nation_snapshot(state: NationProjectionState, context: ProjectionContext | None = None) -> dict[str, Any]:
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
        "baseInvestmentPointsMonth": _base_ip(state, context),
        "priorityProgress": dict(state.progress),
    }


METRIC_NAMES = frozenset({
    "nation.gdp", "nation.population", "nation.inequality", "nation.education", "nation.democracy",
    "nation.cohesion", "nation.unrest", "nation.sustainability", "nation.militaryTech", "nation.funding",
    "nation.boost", "nation.missionControl", "nation.research",
    "factionContribution.research", "factionContribution.funding", "factionContribution.boost", "factionContribution.missionControl",
})


def _metrics(state: NationProjectionState, context: ProjectionContext) -> dict[str, float]:
    nation = _nation_snapshot(state, context)
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


def _run_investment_transaction(
    state: NationProjectionState,
    context: ProjectionContext,
    day: int,
    segment_index: int,
    *,
    at: datetime | None = None,
    fail_on_unsupported_fallback: bool = False,
) -> dict[str, Any]:
    used = {
        Rules.NATION_IP_BASE.id,
        Rules.NATION_IP_ECONOMY_SCORE.id,
        Rules.NATION_IP_CONTROL_POINT_ALLOCATION.id,
        Rules.NATION_IP_PRIORITY_BONUS.id,
        Rules.NATION_PRIORITY_COMPLETION_ORDER.id,
        Rules.NATION_PRIORITY_VALIDITY.id,
        Rules.NATION_ADVISOR_ATTRIBUTE_SOURCE.id,
        Rules.NATION_ADVISOR_STACKING.id,
        Rules.NATION_ASSET_ARMY_MAINTENANCE.id,
    }
    trace: list[dict[str, Any]] = []
    rule_executions: list[dict[str, Any]] = []
    allocation = {name: 0.0 for name in context.priorities}
    _refresh_economy_score(state, context, used)
    base_ip = _base_ip(state, context)
    cp_ip = base_ip / state.num_control_points if state.num_control_points else 0.0
    for cp in sorted(state.control_points.values(), key=lambda value: value.position):
        before_economy = cp.pips.get("Economy", 0)
        effective = _record_and_fix_control_point(state, cp, context, trace=trace)
        total = sum(effective.values())
        if cp.pips.get("Economy", 0) and not before_economy:
            used.add(Rules.NATION_IP_CONTROL_POINT_DEFAULT_ECONOMY.id)
            if fail_on_unsupported_fallback:
                raise ProjectionRuntimeStop(
                    "Control-point validation generated a nonzero unsupported Economy fallback",
                    rule_ids=(Rules.NATION_IP_CONTROL_POINT_DEFAULT_ECONOMY.id, Rules.NATION_PRIORITY_ECONOMY_COMPLETE.id),
                    affected_metrics=("nation.gdp", "nation.inequality", "nation.cohesion", "nation.unrest"),
                    trace=trace,
                )
        for priority, pip in effective.items():
            bonus = cp.priority_bonuses.get(priority, 0.0)
            bonus += _diversity_bonus(cp, priority, effective, context)
            bonus += _national_priority_bonus(state, priority, context)
            if bonus >= 0.0 and cp.benefits_disabled:
                bonus = 0.0
            allocation[priority] += cp_ip * pip / total * (1.0 + bonus) * 12.0 / DAYS_PER_YEAR
    for priority, amount in allocation.items():
        state.progress[priority] = max(0.0, state.progress.get(priority, 0.0) + amount)
    completions: list[dict[str, Any]] = []
    ordered = sorted(context.priorities, key=lambda name: int(context.priorities[name]["enumValue"]))
    for priority in ordered:
        cost = float(context.priorities[priority]["investmentCost"]) / max(context.national_ip_multiplier, 1e-12)
        while state.progress.get(priority, 0.0) + 1e-12 >= cost and _priority_valid(state, priority, context):
            if priority not in STATIC_COMPLETIONS or priority == "Unity":
                raise ProjectionRuntimeStop(
                    f"Reached unsupported priority completion: {priority}",
                    rule_ids=(COMPLETION_RULES[priority].id,),
                    affected_metrics=("nation.*", "factionContribution.*"),
                    trace=trace,
                )
            trace.append({"operation": "completionGuard", "priority": priority, "progress": state.progress[priority], "cost": cost})
            trace_start = len(trace)
            execution = _apply_completion(state, priority, context, used, trace=trace)
            if fail_on_unsupported_fallback and any(row.get("operation") == "defaultEconomy" for row in trace[trace_start:]):
                raise ProjectionRuntimeStop(
                    "Priority completion generated a nonzero unsupported Economy fallback",
                    rule_ids=(Rules.NATION_IP_CONTROL_POINT_DEFAULT_ECONOMY.id, Rules.NATION_PRIORITY_ECONOMY_COMPLETE.id),
                    affected_metrics=("nation.gdp", "nation.inequality", "nation.cohesion", "nation.unrest"),
                    trace=trace,
                )
            validate_rule_execution(
                str(execution["ruleId"]),
                str(execution["effectiveCoverage"]),
                coverage_resolver_id=execution.get("coverageResolverId"),
            )
            state.progress[priority] -= cost
            trace.append({"operation": "consumeProgress", "priority": priority, "cost": cost, "remainingProgress": state.progress[priority]})
            event = {
                "day": day,
                "at": (at or state.at).isoformat(),
                "priority": priority,
                "cost": cost,
                "remainingProgress": state.progress[priority],
                **{key: value for key, value in execution.items() if key not in {"ruleId", "dependencies", "provenance"}},
            }
            completions.append(event)
            rule_executions.append(execution)
    for cp in sorted(state.control_points.values(), key=lambda value: value.position):
        before = cp.pips.get("Economy", 0)
        _record_and_fix_control_point(state, cp, context, trace=trace)
        if cp.pips.get("Economy", 0) and not before:
            used.add(Rules.NATION_IP_CONTROL_POINT_DEFAULT_ECONOMY.id)
            if fail_on_unsupported_fallback:
                raise ProjectionRuntimeStop(
                    "Priority completion generated a nonzero unsupported Economy fallback",
                    rule_ids=(Rules.NATION_IP_CONTROL_POINT_DEFAULT_ECONOMY.id, Rules.NATION_PRIORITY_ECONOMY_COMPLETE.id),
                    affected_metrics=("nation.gdp", "nation.inequality", "nation.cohesion", "nation.unrest"),
                    trace=trace,
                )
    return {
        "sequence": day,
        "kind": "investment",
        "day": day,
        "at": (at or state.at).isoformat(),
        "segmentIndex": segment_index,
        "baseInvestmentPointsMonth": base_ip,
        "allocation": {name: value for name, value in allocation.items() if value},
        "completions": completions,
        "mechanicRules": sorted(used),
        "ruleExecutions": rule_executions,
        "mutationTrace": trace,
    }


def _annual_population_growth(state: NationProjectionState, region: RegionProjectionState, context: ProjectionContext) -> float:
    if region.annual_population_growth is not None:
        return float(region.annual_population_growth)
    missing = [
        name for name, value in (
            ("latitude", region.latitude),
            ("annualPopGrowthModifier", region.annual_population_growth_modifier),
            ("environment", region.environment),
            ("xenoformingLevel", region.xenoforming_level),
            ("nuclearDetonations", region.nuclear_detonations),
        ) if value is None
    ]
    if missing:
        raise ProjectionRuntimeStop(
            "Population annual growth inputs are incomplete",
            rule_ids=(Rules.NATION_POPULATION_ANNUAL_GROWTH.id,),
            dependencies=tuple({"field": name, "source": f"save/catalog.region.{region.id}"} for name in missing),
            affected_metrics=("nation.population", "nation.gdp", "nation.research", "factionContribution.research"),
        )
    regression_years = context.start_template.get("populationRegressionPeriod_years")
    nation_modifier = context.nation_template.get("popGrowthModifier")
    temperature = state.world_context.get("temperatureAnomaly_C")
    if not isinstance(regression_years, (int, float)) or not isinstance(nation_modifier, (int, float)) or not isinstance(temperature, (int, float)):
        raise ProjectionRuntimeStop(
            "Population catalog or held-fixed climate context is incomplete",
            rule_ids=(Rules.NATION_POPULATION_ANNUAL_GROWTH.id,),
            dependencies=(
                {"field": "populationRegressionPeriod_years", "source": "nationDevelopment.startTimeTemplates"},
                {"field": "popGrowthModifier", "source": "nationDevelopment.nationTemplates"},
                {"field": "temperatureAnomaly_C", "source": "save.TIGlobalValuesState"},
            ),
            affected_metrics=("nation.population", "nation.gdp", "nation.research", "factionContribution.research"),
        )
    pcgdp = state.gdp / (state.population_millions * 1_000_000.0) if state.population_millions else 0.0
    regression = (
        4.49788037409348
        + max(-4.49788037409348, -0.418190741 * state.education)
        - 0.0624798523403752 * state.cohesion
        + 9.80843732089162e-06 * min(180_000.0, pcgdp)
        - 0.115739931206548 * math.sqrt(abs(float(region.latitude)))
        + float(region.annual_population_growth_modifier)
        * max(0.0, (float(regression_years) - state.days_in_campaign / DAYS_PER_YEAR) / float(regression_years))
        + float(nation_modifier)
        - float(region.xenoforming_level) / 200.0
        - int(region.nuclear_detonations) * 4.0
    )
    annual_percent = min(10.0, max(-10.0, regression))
    environment_factor = {"Beneficiary": 0.5, "Vulnerable": 2.0, "Standard": 1.0}.get(str(region.environment), 1.0)
    annual_percent -= max(0.0, abs(float(temperature)) - 8.0) * environment_factor
    return max(-100.0, annual_percent) * 0.01


def _expected_control_point_count(state: NationProjectionState, context: ProjectionContext) -> int:
    unclamped = max(round((state.gdp / 1_000_000_000.0) ** _global(context, "controlPointCountScaling") / _global(context, "controlPointScalingDivisor")), 1)
    return min(max(unclamped, 1), 6)


def _run_monthly_transaction(
    state: NationProjectionState,
    context: ProjectionContext,
    day: int,
    *,
    at: datetime | None = None,
    quarterly: bool = False,
) -> tuple[dict[str, Any], bool]:
    used = {
        Rules.NATION_PERIODIC_CONTROL_POINTS.id,
        Rules.NATION_PERIODIC_COHESION.id,
        Rules.NATION_PERIODIC_UNREST.id,
        Rules.NATION_PERIODIC_POPULATION.id,
        Rules.NATION_POPULATION_ANNUAL_GROWTH.id,
        Rules.NATION_POPULATION_MONTHLY_GROWTH.id,
        Rules.NATION_IP_ECONOMY_SCORE.id,
    }
    expected_cps = _expected_control_point_count(state, context)
    if expected_cps != state.num_control_points:
        raise ProjectionRuntimeStop(
            "Monthly UpdateControlPoints would change the target nation's control-point count",
            rule_ids=(Rules.NATION_PERIODIC_CONTROL_POINTS.id,),
            affected_metrics=("nation.*", "factionContribution.*"),
        )
    state.num_control_points_unclamped = max(round((state.gdp / 1_000_000_000.0) ** _global(context, "controlPointCountScaling") / _global(context, "controlPointScalingDivisor")), 1)
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
    population_rows = []
    for region in sorted(state.regions.values(), key=lambda value: value.region_order):
        annual_growth = _annual_population_growth(state, region, context)
        monthly_rate = math.pow(1.0 + annual_growth, 0.0833333358168602) - 1.0
        old = region.population_millions
        new = max(old * (1.0 + monthly_rate), 0.001)
        delta = new - old
        regional_gdp = _region_gdp_value(state, region, context)
        regional_pcgdp = regional_gdp / (region.population_millions * 1_000_000.0) if region.population_millions else 0.0
        region.population_millions = new
        gdp_delta = regional_pcgdp * delta * 1_000_000.0
        state.gdp += gdp_delta
        region.gdp = regional_gdp + gdp_delta
        if delta < 0:
            state.education += max(-0.005, min(0.0, delta / 100.0))
        _refresh_economy_score(state, context, used)
        population_rows.append({
            "regionId": region.id,
            "annualGrowth": annual_growth,
            "monthlyRate": monthly_rate,
            "jitterInput": 0.0,
            "populationDeltaMillions": delta,
            "gdpDelta": gdp_delta,
        })
    state.population_mean_path = True
    for metric in ("nation.population", "nation.gdp", "nation.research", "nation.cohesionRest", "factionContribution.research"):
        state.metric_provenance.setdefault(metric, set()).update({"meanPath", state.world_context_provenance})
    if quarterly:
        state.current_quarter += 1
        state.pcgdp_tracker[state.current_quarter] = state.gdp / (state.population_millions * 1_000_000.0) if state.population_millions else 0.0
    return ({
        "kind": "monthly",
        "day": day,
        "at": (at or state.at).isoformat(),
        "mechanicRules": sorted(used),
        "populationCoverage": "expected",
        "stochasticTreatment": "deterministicMeanInput",
        "provenance": "meanPath",
        "expectationGuarantee": False,
        "populationUpdates": population_rows,
        "quarterlyTrackerUpdated": quarterly,
        "ruleExecutions": [
            {
                "ruleId": Rules.NATION_PERIODIC_CONTROL_POINTS.id,
                "effectiveCoverage": "exact",
                "coverageResolverId": Rules.NATION_PERIODIC_CONTROL_POINTS.coverage_resolver_id,
                "provenance": "dllReimplementation",
                "dependencies": [],
            },
            {
                "ruleId": Rules.NATION_POPULATION_MONTHLY_GROWTH.id,
                "effectiveCoverage": "expected",
                "provenance": "meanPath",
                "expectationGuarantee": False,
                "dependencies": [Rules.NATION_POPULATION_ANNUAL_GROWTH.id],
            }
        ],
    }, True)


def _hostile_claim_population_fraction(state: NationProjectionState) -> float:
    total = state.population_millions
    if total <= 0:
        return 0.0
    return sum(
        state.regions[region_id].population_millions
        for region_id in state.hostile_region_ids
        if region_id in state.regions
    ) / total


def _cohesion_dynamic_impact(state: NationProjectionState, context: ProjectionContext) -> float:
    inequality = min(1.0, 0.5 + state.education / 20.0) * (
        -state.inequality * _global(context, "inequalityCohesionMultiplier")
        - max(0.0, state.inequality - _global(context, "severeInequality"))
    )
    population = -(state.population_millions ** (
        _global(context, "populationCohesionImpactPower") + (0.1 if len(state.regions) == 1 else 0.0)
    ))
    pcgdp = state.gdp / (state.population_millions * 1_000_000.0) if state.population_millions else 0.0
    recent = [value for quarter, value in state.pcgdp_tracker.items() if quarter >= state.current_quarter - 40]
    maximum = max(recent + [100.0])
    pcgdp_impact = (1.0 - pcgdp / maximum) * -state.inequality if pcgdp < maximum else 0.0
    hostile_total = _hostile_claim_population_fraction(state) * _global(context, "maxCombinedImpactFromHostileClaims")
    hostile = -hostile_total * state.democracy / 10.0
    autocracy = ((3.5 ** 1.285) - (state.democracy ** 1.285)) * ((10.0 - state.unrest) / 10.0) if state.democracy <= 3.5 else 0.0
    anocracy = 2.0 * abs(5.0 - state.democracy) - 3.0 if 3.5 < state.democracy <= 6.5 else 0.0
    return inequality + population + pcgdp_impact + hostile + autocracy + anocracy


def _democracy_cohesion_transform(original: float, democracy: float) -> float:
    if democracy <= 6.5:
        return original
    distance = abs((6.5 - democracy) / 2.0)
    return min(5.0, original + distance) if original <= 5.0 else max(5.0, original - distance)


def _own_army_unrest_impact(state: NationProjectionState, context: ProjectionContext) -> float:
    denominator = max(len(state.regions) ** (1.0 - _global(context, "controlPointIPScaling")), 1.0)
    region_ids = set(state.regions)
    return sum(
        -army.strength * 0.5 * (10.0 - state.democracy) / denominator
        for army in state.standard_armies
        if army.current_region_id in region_ids
    )


def _refresh_rest_caches(
    state: NationProjectionState,
    context: ProjectionContext,
    day: int,
    *,
    at: datetime | None = None,
) -> dict[str, Any]:
    used = {Rules.NATION_PERIODIC_DERIVED_CACHE.id, Rules.NATION_PERIODIC_COHESION.id, Rules.NATION_PERIODIC_UNREST.id}
    fixed_cohesion = state.rest_state_context.get("cohesionFixedImpact")
    fixed_unrest = state.rest_state_context.get("unrestFixedImpact")
    unrest_divisor = state.rest_state_context.get("pcgdpToReduceUnrestBy1")
    if not all(isinstance(value, (int, float)) for value in (fixed_cohesion, fixed_unrest, unrest_divisor)) or float(unrest_divisor) <= 0:
        raise ProjectionRuntimeStop(
            "Daily resting-state cache inputs are incomplete",
            rule_ids=(Rules.NATION_PERIODIC_DERIVED_CACHE.id,),
            dependencies=(
                {"field": "cohesionFixedImpact", "source": "projection.restStateContext"},
                {"field": "unrestFixedImpact", "source": "projection.restStateContext"},
                {"field": "pcgdpToReduceUnrestBy1", "source": "save.TIGlobalValuesState"},
            ),
            affected_metrics=("nation.cohesionRest", "nation.unrestRest"),
        )
    raw_cohesion = float(fixed_cohesion) + _cohesion_dynamic_impact(state, context)
    state.cohesion_rest = min(10.0, max(0.0, _democracy_cohesion_transform(raw_cohesion, state.democracy)))
    pcgdp = state.gdp / (state.population_millions * 1_000_000.0) if state.population_millions else 0.0
    hostile_total = _hostile_claim_population_fraction(state) * _global(context, "maxCombinedImpactFromHostileClaims")
    hostile_unrest = hostile_total * (1.0 - state.democracy / 10.0)
    raw_unrest = float(fixed_unrest) - state.cohesion - pcgdp / float(unrest_divisor) + _own_army_unrest_impact(state, context) + hostile_unrest
    state.unrest_rest = min(10.0, max(0.0, raw_unrest))
    return {
        "kind": "derivedCache",
        "day": day,
        "at": (at or state.at).isoformat(),
        "cohesionRest": state.cohesion_rest,
        "unrestRest": state.unrest_rest,
        "mechanicRules": sorted(used),
        "ruleExecutions": [
            {"ruleId": Rules.NATION_PERIODIC_DERIVED_CACHE.id, "effectiveCoverage": "exact", "provenance": "dllReimplementation", "dependencies": []}
        ],
    }


def calibrate_rest_state_context(
    state: NationProjectionState,
    context: ProjectionContext,
    *,
    pcgdp_to_reduce_unrest_by_one: float,
) -> None:
    """Anchor held-fixed external rest-state terms to the serialized daily caches."""

    cached = state.cohesion_rest
    if state.democracy > 6.5:
        shift = abs((6.5 - state.democracy) / 2.0)
        if cached < 5.0:
            pre_democracy = cached - shift
        elif cached > 5.0:
            pre_democracy = cached + shift
        else:
            pre_democracy = 5.0
    else:
        pre_democracy = cached
    state.rest_state_context["cohesionFixedImpact"] = pre_democracy - _cohesion_dynamic_impact(state, context)
    pcgdp = state.gdp / (state.population_millions * 1_000_000.0) if state.population_millions else 0.0
    hostile_total = _hostile_claim_population_fraction(state) * _global(context, "maxCombinedImpactFromHostileClaims")
    hostile_unrest = hostile_total * (1.0 - state.democracy / 10.0)
    own_army = _own_army_unrest_impact(state, context)
    if 0.0 < state.unrest_rest < 10.0:
        fixed_unrest = state.unrest_rest + state.cohesion + pcgdp / pcgdp_to_reduce_unrest_by_one - own_army - hostile_unrest
    else:
        fixed_unrest = 10.5
    state.rest_state_context.update({
        "unrestFixedImpact": fixed_unrest,
        "pcgdpToReduceUnrestBy1": pcgdp_to_reduce_unrest_by_one,
        "provenance": "heldFixedWorldContext",
    })


def _projection_preflight(
    state: NationProjectionState,
    plan: PriorityPlan,
    context: ProjectionContext,
    coverage: Mapping[str, Mapping[str, Any]],
) -> tuple[list[str], dict[str, Any]]:
    working = copy.deepcopy(state)
    unsupported: set[str] = set()
    active: set[str] = set()
    dormant: set[str] = set()
    implicit: list[dict[str, Any]] = []
    for segment_index, segment in enumerate(plan.segments):
        _apply_segment(working, segment)
        for cp in sorted(working.control_points.values(), key=lambda value: value.position):
            effective: dict[str, int] = {}
            for name, value in cp.pips.items():
                if value <= 0:
                    continue
                if name not in coverage:
                    unsupported.add(name)
                    dormant.add(name)
                    continue
                try:
                    valid = _priority_valid(working, name, context)
                except ProjectionRuntimeStop:
                    valid = False
                (active if valid else dormant).add(name)
                if valid:
                    effective[name] = value
                if coverage[name]["overall"] == "unsupported":
                    unsupported.add(name)
            if not effective:
                implicit.append({
                    "segmentIndex": segment_index,
                    "controlPointPosition": cp.position,
                    "priority": "Economy",
                    "reason": "noValidPositivePips",
                })
                unsupported.add("Economy")
    return sorted(unsupported), {
        "activePriorities": sorted(active),
        "dormantPriorities": sorted(dormant),
        "implicitFallbacks": implicit,
    }


def _event_schedule(start: datetime, days: int, checkpoints: Iterable[int]) -> list[tuple[datetime, int, str, int]]:
    horizon = start + timedelta(days=days)
    events: list[tuple[datetime, int, str, int]] = []
    calendar = start.date()
    end_date = horizon.date()
    investment_day = 0
    while calendar <= end_date:
        if calendar.day == 1:
            moment = datetime.combine(calendar, time(0, 0))
            if start < moment <= horizon:
                events.append((moment, 0, "monthly", investment_day))
        investment = datetime.combine(calendar, time(10, 30))
        if start < investment <= horizon:
            investment_day += 1
            events.append((investment, 1, "investment", investment_day))
        rest = datetime.combine(calendar, time(12, 0))
        if start < rest <= horizon:
            events.append((rest, 2, "rest", investment_day))
        calendar += timedelta(days=1)
    for checkpoint in sorted(set(checkpoints)):
        events.append((start + timedelta(days=checkpoint), 3, "checkpoint", checkpoint))
    return sorted(events, key=lambda row: (row[0], row[1]))


def _metric_coverage(
    state: NationProjectionState,
    *,
    blockers: Iterable[str] = (),
    affected_metrics: Iterable[str] = (),
) -> dict[str, dict[str, Any]]:
    affected = set(affected_metrics)
    blocked = list(blockers)
    result: dict[str, dict[str, Any]] = {}
    rule_map = {
        "nation.population": [Rules.NATION_POPULATION_ANNUAL_GROWTH.id, Rules.NATION_POPULATION_MONTHLY_GROWTH.id],
        "nation.gdp": [Rules.NATION_POPULATION_MONTHLY_GROWTH.id, Rules.NATION_IP_ECONOMY_SCORE.id],
        "nation.research": [Rules.NATION_POPULATION_MONTHLY_GROWTH.id],
        "nation.cohesionRest": [Rules.NATION_PERIODIC_DERIVED_CACHE.id],
        "factionContribution.research": [Rules.NATION_FACTION_CONTRIBUTION.id, Rules.NATION_POPULATION_MONTHLY_GROWTH.id],
        "factionContribution.funding": [Rules.NATION_FACTION_CONTRIBUTION.id],
        "factionContribution.boost": [Rules.NATION_FACTION_CONTRIBUTION.id],
        "factionContribution.missionControl": [Rules.NATION_FACTION_CONTRIBUTION.id, Rules.NATION_PRIORITY_MISSION_CONTROL_PLACEMENT.id],
        "nation.missionControl": [Rules.NATION_PRIORITY_MISSION_CONTROL_PLACEMENT.id],
    }
    for metric in sorted(METRIC_NAMES):
        provenance_values = set(state.metric_provenance.get(metric, set()))
        if state.advisors:
            provenance_values.add("hypotheticalPolicy")
        provenance = sorted(provenance_values)
        is_blocked = metric in affected or "nation.*" in affected and metric.startswith("nation.") or "factionContribution.*" in affected and metric.startswith("factionContribution.")
        result[metric] = {
            "coverage": "unsupported" if is_blocked else "expected" if "meanPath" in provenance else "exact",
            "provenance": provenance,
            "ruleIds": rule_map.get(metric, []),
            "blockers": blocked if is_blocked else [],
        }
        if "meanPath" in provenance:
            result[metric].update({
                "stochasticTreatment": "deterministicMeanInput",
                "expectationGuarantee": False,
            })
    return result


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
    unsupported, preflight = _projection_preflight(state, plan, context, coverage)
    _apply_segment(state, plan.segments[0])
    initial_metrics = _metrics(state, context)
    if unsupported:
        missing_rules = sorted({COMPLETION_RULES[name].id for name in unsupported if name in COMPLETION_RULES})
        initial_snapshot = {"nation": _nation_snapshot(state, context), "factionContribution": _contribution(state, context)}
        return {
            "name": plan.name,
            "status": "incomplete",
            "preflight": preflight,
            "unsupportedPriorities": unsupported,
            "missingMechanicRules": missing_rules,
            "missingDependencies": [],
            "dependencyTrace": [],
            "affectedMetrics": ["nation.*", "factionContribution.*"],
            "runtimeStop": None,
            "currentAllocation": {str(cp.position): dict(cp.pips) for cp in state.control_points.values()},
            "authoritativeFinalState": None,
            "lastAuthoritativeState": initial_snapshot,
            "limitations": ["Nonzero pips reference priority completion/downstream mechanics that are not audited."],
            "mechanicRuleIds": [],
            "coverage": {name: coverage[name] for name in unsupported},
            "metricCoverage": _metric_coverage(state, blockers=missing_rules, affected_metrics=("nation.*", "factionContribution.*")),
            "ruleExecutions": [],
        }
    segment_index = 0
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
    checkpoint_rows: list[dict[str, Any]] = []
    used: set[str] = set()
    rule_executions: list[dict[str, Any]] = []
    goal_first = {name: (0 if _condition_met(condition, initial_metrics, initial_metrics) else None) for name, condition in goals}
    incomplete_reasons: list[str] = []
    advisor_used = bool(state.advisors)
    pending_segment: int | None = None
    runtime_stop: ProjectionRuntimeStop | None = None
    runtime_stop_at: datetime | None = None
    investment_day = 0

    def evaluate_boundary(day: int, reason: str, at: datetime) -> None:
        nonlocal pending_segment
        metrics = _metrics(state, context)
        for goal_name, condition in goals:
            if goal_first[goal_name] is None and _condition_met(condition, metrics, initial_metrics):
                goal_first[goal_name] = day
        if pending_segment is None and segment_index < len(plan.segments) - 1 and _segment_met(
            plan.segments[segment_index], day, metrics, initial_metrics
        ):
            pending_segment = segment_index + 1
            transitions.append({
                "day": day,
                "at": at.isoformat(),
                "effectiveDay": day + 1,
                "from": segment_index,
                "to": pending_segment,
                "reason": reason,
            })

    for moment, _order, kind, day_value in _event_schedule(state.at, days, checkpoints):
        state.days_in_campaign = initial_state.days_in_campaign + (moment - initial_state.at).total_seconds() / 86400.0
        if kind == "checkpoint":
            checkpoint_rows.append({"day": day_value, "at": moment.isoformat(), "nation": _nation_snapshot(state, context), "factionContribution": _contribution(state, context, used)})
            continue
        if kind == "investment":
            investment_day = day_value
            if pending_segment is not None:
                before = state.advisors
                segment_index = pending_segment
                pending_segment = None
                _apply_segment(state, plan.segments[segment_index])
                if state.advisors != before:
                    advisor_transitions.append({"day": investment_day, "at": moment.isoformat(), "advisors": [item.output() for item in state.advisors]})
        working = copy.deepcopy(state)
        try:
            if kind == "investment":
                transaction = _run_investment_transaction(
                    working,
                    context,
                    investment_day,
                    segment_index,
                    at=moment,
                    fail_on_unsupported_fallback=True,
                )
            elif kind == "monthly":
                transaction, _ = _run_monthly_transaction(
                    working,
                    context,
                    investment_day,
                    at=moment,
                    quarterly=moment.month in {1, 4, 7, 10},
                )
            else:
                transaction = _refresh_rest_caches(working, context, investment_day, at=moment)
        except ProjectionRuntimeStop as exc:
            runtime_stop = exc
            runtime_stop_at = moment
            incomplete_reasons.append(exc.reason)
            break
        for execution in transaction.get("ruleExecutions", []):
            validate_rule_execution(
                str(execution["ruleId"]),
                str(execution["effectiveCoverage"]),
                coverage_resolver_id=execution.get("coverageResolverId"),
            )
        state = working
        transactions.append(transaction)
        completion_events.extend(transaction.get("completions", []))
        used.update(transaction.get("mechanicRules", []))
        rule_executions.extend(transaction.get("ruleExecutions", []))
        evaluate_boundary(
            investment_day,
            "conditionSatisfiedAfterInvestmentTransaction" if kind == "investment" else "conditionSatisfiedAfterPeriodicTransaction",
            moment,
        )
        advisor_used = advisor_used or bool(state.advisors)
    final_nation = _nation_snapshot(state, context)
    final_contribution = _contribution(state, context, used)
    status = "incomplete" if runtime_stop is not None else "complete"
    blockers = list(runtime_stop.rule_ids) if runtime_stop else []
    affected = list(runtime_stop.affected_metrics) if runtime_stop else []
    result = {
        "name": plan.name,
        "status": status,
        "preflight": preflight,
        "nationProjection": final_nation,
        "factionContribution": final_contribution,
        "authoritativeFinalState": {"nation": final_nation, "factionContribution": final_contribution} if status == "complete" else None,
        "lastAuthoritativeState": {"nation": final_nation, "factionContribution": final_contribution},
        "segmentTransitions": transitions,
        "advisorTransitions": advisor_transitions,
        "completionEvents": completion_events,
        "checkpoints": checkpoint_rows,
        "goalResults": [{"name": name, "met": goal_first[name] is not None, "firstMetDay": goal_first[name]} for name, _ in goals],
        "coverage": coverage,
        "metricCoverage": _metric_coverage(state, blockers=blockers, affected_metrics=affected),
        "ruleExecutions": rule_executions,
        "mechanicRuleIds": sorted(used),
        "runtimeStop": ({
            "at": runtime_stop_at.isoformat() if runtime_stop_at is not None else state.at.isoformat(),
            "reason": runtime_stop.reason,
            "ruleIds": list(runtime_stop.rule_ids),
        } if runtime_stop else None),
        "missingMechanicRules": blockers,
        "missingDependencies": list(runtime_stop.dependencies) if runtime_stop else [],
        "dependencyTrace": list(runtime_stop.trace) if runtime_stop else [],
        "affectedMetrics": affected,
        "inputProvenance": "hypotheticalPolicy" if advisor_used else "saveStateAndPlan",
        "limitations": incomplete_reasons + [
            "Exogenous events, missions, wars, ownership changes and player actions are held fixed.",
            "Population uses a deterministic mean-input trajectory; it is not guaranteed to equal the expectation of all stochastic trajectories.",
        ],
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
    initial = {"nation": _nation_snapshot(initial_state, context), "factionContribution": _contribution(initial_state, context, initial_used)}
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
