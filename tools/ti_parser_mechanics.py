"""Audited Terra Invicta mechanics registry shared by code, tests and diagnostics.

The registry describes provenance; executable mechanics live in Python modules.
Stable IDs must not be reused for a different meaning.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable


COVERAGE_LEVELS = frozenset({"exact", "expected", "aggregateOnly", "unsupported"})
COVERAGE_MODES = frozenset({"static", "conditional"})
AUDIT_STATUSES = frozenset({"verified", "partial", "pending", "deprecated"})
TEST_EVIDENCE_TYPES = frozenset({"expectedValue", "stateTransition", "ordering", "coverageBranch", "contract"})
ASSEMBLY_CSHARP_SHA256 = "5ec67c601a6ce39d985aa9830a99faa9844aee7d7e12ec5e28ea46ff020ba982"
REGISTRY_CONTRACT_TEST_ID = (
    "tests.test_mechanics_registry.MechanicsRegistryTests."
    "test_real_save_rule_contracts_are_registered"
)


@dataclass(frozen=True)
class CoverageResolver:
    """Registry contract for an executable, path-sensitive coverage resolver."""

    id: str
    allowed_coverages: tuple[str, ...]
    description: str


@dataclass(frozen=True)
class MechanicRule:
    id: str
    implementation_revision: int
    description: str
    audit_status: str
    coverage: str
    dll_symbols: tuple[str, ...]
    callers: tuple[str, ...] = ()
    data_dependencies: tuple[str, ...] = ()
    deterministic: bool = True
    test_ids: tuple[str, ...] = ()
    source_hash: str | None = ASSEMBLY_CSHARP_SHA256
    coverage_mode: str = "static"
    allowed_coverages: tuple[str, ...] = ()
    coverage_resolver_id: str | None = None

    def diagnostics(self) -> dict[str, object]:
        return {
            "id": self.id,
            "implementationRevision": self.implementation_revision,
            "auditStatus": self.audit_status,
            "coverage": self.coverage,
            "coverageMode": self.coverage_mode,
            "allowedCoverages": list(self.allowed_coverages or (self.coverage,)),
            "coverageResolverId": self.coverage_resolver_id,
            "dllSymbols": list(self.dll_symbols),
            "callers": list(self.callers),
            "dataDependencies": list(self.data_dependencies),
            "deterministic": self.deterministic,
            "sourceHash": self.source_hash,
        }


class CoverageResolvers:
    MISSION_CONTROL_PLACEMENT = CoverageResolver(
        "nation.priority.mission-control.placement.v1",
        ("exact", "aggregateOnly", "unsupported"),
        "Resolve placement coverage from candidate count and downstream equivalence.",
    )
    BUILD_ARMY_PLACEMENT = CoverageResolver(
        "nation.priority.build-army.placement.v1",
        ("exact", "unsupported"),
        "Resolve deterministic placement coverage from availability of every selection input.",
    )
    PERIODIC_CONTROL_POINTS = CoverageResolver(
        "nation.periodic.control-points.v1",
        ("exact", "unsupported"),
        "Resolve exact no-count-change monthly reconciliation or stop before an unsupported mutation.",
    )


COVERAGE_RESOLVERS = {
    resolver.id: resolver
    for resolver in (
        CoverageResolvers.MISSION_CONTROL_PLACEMENT,
        CoverageResolvers.BUILD_ARMY_PLACEMENT,
        CoverageResolvers.PERIODIC_CONTROL_POINTS,
    )
}


class Rules:
    NATION_IP_BASE = MechanicRule(
        "nation.ip.base", 1,
        "Nation monthly base investment points, including Advisor and army/navy maintenance.",
        "verified", "exact",
        ("TINationState.SetBaseInvestmentPoints_month",),
        ("TINationState.DailyNationUpdate", "TINationState.AddAdvisingCouncilor"),
        ("nationDevelopment.globalConfig.nationalInvestmentArmyFactor*",),
        test_ids=("tests.test_nation_projection.NationProjectionTransactionTests.test_advisor_base_ip_and_rank_decay",),
    )
    NATION_IP_ECONOMY_SCORE = MechanicRule(
        "nation.ip.economy-score", 1,
        "Recompute the GDP-derived economy score immediately after GDP changes.",
        "verified", "exact",
        ("TINationState.ModifyGDP", "TINationState.SetEconomyScore"),
        ("TIRegionState.GrowPopulationByMonth", "TINationState.SetBaseInvestmentPoints_month"),
        ("nationDevelopment.globalConfig.controlPointIPScaling", "nationDevelopment.globalConfig.controlPointIPFactor"),
        test_ids=("tests.test_nation_projection.NationProjectionTransactionTests.test_economy_score_recomputes_from_literal_gdp",),
    )
    NATION_IP_CONTROL_POINT_ALLOCATION = MechanicRule(
        "nation.ip.control-point-allocation", 1,
        "Allocate daily nation IP independently through each control point's valid pip weights.",
        "verified", "exact",
        ("TINationState.GetInvestmentFromControlPoint", "TINationState.ControlPointWeightsTotalToPriorityIP"),
        ("TINationState.DailyNationUpdate",),
        ("nationDevelopment.daysPerYear", "nationDevelopment.controlPointPips"),
        test_ids=("tests.test_nation_projection.NationProjectionTransactionTests.test_one_tick_control_point_allocation",),
    )
    NATION_IP_PRIORITY_BONUS = MechanicRule(
        "nation.ip.priority-bonus", 1,
        "Apply owner, diversity and national priority bonuses after each CP share is calculated.",
        "verified", "exact",
        ("TINationState.ControlPointPriorityBonuses_Uncached", "TIControlPoint.RecordAndFixControlPointValues", "TIFactionState.SumPriorityBonuses"),
        ("TINationState.ControlPointWeightsTotalToPriorityIP",),
        ("nationDevelopment.diversityBonuses",),
        test_ids=("tests.test_nation_projection.NationProjectionTransactionTests.test_diversity_and_owner_priority_bonus",),
    )
    NATION_IP_CONTROL_POINT_DEFAULT_ECONOMY = MechanicRule(
        "nation.ip.control-point-default-economy", 1,
        "Persist raw Economy pip one when a control point has no valid nonzero priority.",
        "verified", "exact",
        ("TIControlPoint.RecordAndFixControlPointValues", "TIControlPoint.SetControlPointPriority"),
        ("TINationState.ProcessPrioritySpending",),
        ("nationDevelopment.controlPointPips",),
        test_ids=("tests.test_nation_projection.NationProjectionTransactionTests.test_invalid_only_control_point_persistently_falls_back_to_raw_economy",),
    )
    NATION_PRIORITY_VALIDITY = MechanicRule(
        "nation.priority.validity", 1,
        "Evaluate priority validity from live nation and region state whenever the DLL revalidates CP values.",
        "verified", "exact",
        ("TINationState.ValidPriority", "TIControlPoint.RecordAndFixControlPointValues"),
        ("TINationState.DailyNationUpdate", "TIControlPoint.SetControlPointPriority"),
        test_ids=("tests.test_nation_validity.NationPriorityValidityTests.test_government_cap_requires_hostile_region",),
    )
    NATION_PRIORITY_COMPLETION_ORDER = MechanicRule(
        "nation.priority.completion-order", 1,
        "Process all completed priorities in PriorityType enum order within one investment transaction.",
        "verified", "exact",
        ("TINationState.ProcessPrioritySpending", "PriorityType"),
        ("TINationState.DailyNationUpdate",),
        ("nationDevelopment.priorities.*.enumValue",),
        test_ids=("tests.test_nation_projection.NationProjectionTransactionTests.test_condition_waits_for_multi_completion_transaction",),
    )
    NATION_PRIORITY_KNOWLEDGE_COMPLETE = MechanicRule(
        "nation.priority.knowledge.complete", 1,
        "Apply Knowledge education and cohesion completion effects.",
        "verified", "exact",
        ("TINationState.OnKnowledgePriorityComplete", "TINationState.knowledgePriorityEducationChange", "TINationState.knowledgePriorityCohesionChange"),
        data_dependencies=("nationDevelopment.globalConfig.knowledgePriorityEducationIncrease", "nationDevelopment.globalConfig.populationBasedIPEffectScaling"),
        test_ids=("tests.test_nation_projection.NationProjectionTransactionTests.test_knowledge_completion",),
    )
    NATION_PRIORITY_GOVERNMENT_COMPLETE = MechanicRule(
        "nation.priority.government.complete", 2,
        "Apply Government democracy below the cap or Knowledge plus legitimize handling at the cap.",
        "verified", "exact",
        ("TINationState.OnGovernmentPriorityComplete", "TINationState.governmentPriorityDemocracyChange"),
        data_dependencies=("nationDevelopment.globalConfig.governmentPriorityDemocracyIncrease",),
        test_ids=("tests.test_nation_projection.NationProjectionTransactionTests.test_government_completion_below_cap",),
    )
    NATION_PRIORITY_GOVERNMENT_LEGITIMIZE = MechanicRule(
        "nation.priority.government.legitimize", 1,
        "Accumulate cap-democracy legitimize triggers and deterministically remove a hostile-region claim.",
        "verified", "exact",
        (
            "TINationState.OnGovernmentPriorityComplete",
            "TINationState.canAccumulateLegitimizeClaimTriggers",
            "TINationState.GetNextRegionToLegitimizeClaim",
        ),
        data_dependencies=(
            "nationDevelopment.globalConfig.governmentPriorityLegitimizeClaimThreshold",
            "nationDevelopment.regions.*.adjacency",
        ),
        test_ids=("tests.test_nation_projection.NationProjectionTransactionTests.test_government_at_cap_applies_knowledge_and_legitimizes_claim",),
    )
    NATION_PRIORITY_UNITY_COMPLETE = MechanicRule(
        "nation.priority.unity.complete", 2,
        "Apply Unity only when its public-opinion side effect and resting-cohesion dependency are projected.",
        "partial", "unsupported",
        ("TINationState.OnUnityPriorityComplete", "TINationState.unityPriorityCohesionChange", "TINationState.unityPriorityEducationChange"),
        data_dependencies=("nationDevelopment.globalConfig.unityBaseCohesionChange", "nationDevelopment.globalConfig.unityMinCohesionChange", "nationDevelopment.globalConfig.unityPriorityEducationChange"),
    )
    NATION_PRIORITY_FUNDING_COMPLETE = MechanicRule(
        "nation.priority.funding.complete", 1,
        "Increase annual national funding on completion.",
        "verified", "exact",
        ("TINationState.OnFundingPriorityComplete", "TINationState.spaceFundingPriorityIncomeChange"),
        data_dependencies=("nationDevelopment.globalConfig.fundingPriorityBaseIncomeIncrease",),
        test_ids=("tests.test_nation_projection.NationProjectionTransactionTests.test_funding_completion_and_contribution",),
    )
    NATION_PRIORITY_ECONOMY_COMPLETE = MechanicRule(
        "nation.priority.economy.complete", 1, "Apply Economy completion and all national/global downstream effects.",
        "partial", "unsupported", ("TINationState.OnEconomyPriorityComplete",),
    )
    NATION_PRIORITY_WELFARE_COMPLETE = MechanicRule(
        "nation.priority.welfare.complete", 2,
        "Coordinate Welfare inequality and the conditionally activated colony/decolonization child rules.",
        "verified", "exact", ("TINationState.OnWelfarePriorityComplete",),
        test_ids=("tests.test_nation_projection.NationProjectionTransactionTests.test_welfare_children_activate_only_on_the_executed_path",),
    )
    NATION_PRIORITY_WELFARE_INEQUALITY = MechanicRule(
        "nation.priority.welfare.inequality", 1,
        "Apply the Welfare completion inequality reduction.",
        "verified", "exact",
        ("TINationState.OnWelfarePriorityComplete", "TINationState.welfarePriorityInequalityChange"),
        data_dependencies=("nationDevelopment.globalConfig.welfarePriorityInequalityDecrease",),
        test_ids=("tests.test_nation_projection.NationProjectionTransactionTests.test_welfare_children_activate_only_on_the_executed_path",),
    )
    NATION_PRIORITY_WELFARE_COLONY_TRIGGER = MechanicRule(
        "nation.priority.welfare.colony-trigger", 1,
        "Select and increment the deterministic colony-removal trigger when a colony candidate exists.",
        "verified", "exact",
        ("TINationState.OnWelfarePriorityComplete", "TINationState.GetNextRegionToDecolonize"),
        data_dependencies=("nationDevelopment.regions.*.colony",),
        test_ids=("tests.test_nation_projection.NationProjectionTransactionTests.test_welfare_children_activate_only_on_the_executed_path",),
    )
    NATION_PRIORITY_WELFARE_DECOLONIZATION = MechanicRule(
        "nation.priority.welfare.decolonization", 1,
        "Apply the threshold colony/permanent-state transition without activating it before threshold.",
        "verified", "exact",
        ("TINationState.OnWelfarePriorityComplete", "TIRegionState.SetColonialStatus"),
        data_dependencies=("nationDevelopment.globalConfig.welfarePriorityDecolonizationThreshold",),
        test_ids=("tests.test_nation_projection.NationProjectionTransactionTests.test_welfare_children_activate_only_on_the_executed_path",),
    )
    NATION_PRIORITY_WELFARE_DECOLONIZATION_DOWNSTREAM = MechanicRule(
        "nation.priority.welfare.decolonization-downstream", 1,
        "Refresh every projected GDP-share, capacity, MC-weight and rest-state dependency after decolonization.",
        "verified", "exact",
        ("TINationState.CacheRegionValues", "TINationState.ValidPriority", "TINationState.cohesionRestState"),
        data_dependencies=("nationDevelopment.regions.*",),
        test_ids=("tests.test_nation_projection.NationProjectionTransactionTests.test_welfare_children_activate_only_on_the_executed_path",),
    )
    NATION_PRIORITY_ENVIRONMENT_COMPLETE = MechanicRule(
        "nation.priority.environment.complete", 1, "Apply Environment sustainability and decontamination effects.",
        "partial", "unsupported", ("TINationState.OnEnvironmentPriorityComplete",),
    )
    NATION_PRIORITY_OPPRESSION_COMPLETE = MechanicRule(
        "nation.priority.oppression.complete", 1, "Apply Oppression unrest, democracy and cohesion effects.",
        "partial", "unsupported", ("TINationState.OnOppressionPriorityComplete",),
    )
    NATION_PRIORITY_SPOILS_COMPLETE = MechanicRule(
        "nation.priority.spoils.complete", 1, "Apply Spoils faction payouts and national downstream effects.",
        "partial", "unsupported", ("TINationState.OnSpoilsPriorityComplete",),
    )
    NATION_PRIORITY_BOOST_COMPLETE = MechanicRule(
        "nation.priority.launch-facilities.complete", 1, "Apply Launch Facilities to an audited target region.",
        "partial", "unsupported", ("TINationState.OnBoostPriorityComplete",),
    )
    NATION_PRIORITY_MISSION_CONTROL_COMPLETE = MechanicRule(
        "nation.priority.mission-control.complete", 2,
        "Apply Mission Control, including the no-candidate raw-pip mutation order.",
        "verified", "unsupported", ("TINationState.OnMissionControlPriorityComplete",),
        test_ids=("tests.test_nation_projection.NationProjectionTransactionTests.test_mission_control_no_candidate_preserves_dll_mutation_order",),
        coverage_mode="conditional",
        allowed_coverages=CoverageResolvers.MISSION_CONTROL_PLACEMENT.allowed_coverages,
        coverage_resolver_id=CoverageResolvers.MISSION_CONTROL_PLACEMENT.id,
    )
    NATION_PRIORITY_MISSION_CONTROL_PLACEMENT = MechanicRule(
        "nation.priority.mission-control.placement", 1,
        "Resolve candidate placement as exact, downstream-equivalent aggregate, or unsupported before mutation.",
        "verified", "unsupported",
        ("TINationState.OnMissionControlPriorityComplete", "TINationState.ValidPriority"),
        data_dependencies=("nationDevelopment.regions.*.missionControl",),
        deterministic=False,
        test_ids=(
            "tests.test_nation_projection.NationProjectionTransactionTests.test_mission_control_no_candidate_preserves_dll_mutation_order",
            "tests.test_nation_projection.NationProjectionTransactionTests.test_mission_control_non_equivalent_candidates_stop_before_mutation",
        ),
        coverage_mode="conditional",
        allowed_coverages=CoverageResolvers.MISSION_CONTROL_PLACEMENT.allowed_coverages,
        coverage_resolver_id=CoverageResolvers.MISSION_CONTROL_PLACEMENT.id,
    )
    NATION_PRIORITY_FOUND_MILITARY_COMPLETE = MechanicRule(
        "nation.priority.found-military.complete", 1, "Create the national military capability.",
        "pending", "unsupported", ("TINationState.OnFoundMilitaryPriorityComplete",),
    )
    NATION_PRIORITY_MILITARY_COMPLETE = MechanicRule(
        "nation.priority.military.complete", 1, "Apply national military technology progress.",
        "partial", "unsupported", ("TINationState.OnMilitaryPriorityComplete",),
    )
    NATION_PRIORITY_BUILD_ARMY_COMPLETE = MechanicRule(
        "nation.priority.build-army.complete", 2,
        "Create an army using the deterministic DLL region and control-point selection path.",
        "verified", "unsupported", ("TINationState.OnBuildArmyPriorityComplete",),
        test_ids=("tests.test_nation_projection.NationProjectionTransactionTests.test_build_army_deterministic_selection_and_next_tick_maintenance",),
        coverage_mode="conditional",
        allowed_coverages=CoverageResolvers.BUILD_ARMY_PLACEMENT.allowed_coverages,
        coverage_resolver_id=CoverageResolvers.BUILD_ARMY_PLACEMENT.id,
    )
    NATION_PRIORITY_BUILD_ARMY_PLACEMENT = MechanicRule(
        "nation.priority.build-army.placement", 1,
        "Select core-economic, then maximum-population region and reverse-tie control point deterministically.",
        "verified", "unsupported",
        (
            "TINationState.GetNextArmyRegion",
            "TINationState.GetNextArmyControlPoint",
            "TINationState.OnBuildArmyPriorityComplete",
        ),
        data_dependencies=(
            "nationDevelopment.regions.*.coreEconomicRegion",
            "nationDevelopment.regions.*.population",
        ),
        test_ids=("tests.test_nation_projection.NationProjectionTransactionTests.test_build_army_deterministic_selection_and_next_tick_maintenance",),
        coverage_mode="conditional",
        allowed_coverages=CoverageResolvers.BUILD_ARMY_PLACEMENT.allowed_coverages,
        coverage_resolver_id=CoverageResolvers.BUILD_ARMY_PLACEMENT.id,
    )
    NATION_PRIORITY_BUILD_NAVY_COMPLETE = MechanicRule(
        "nation.priority.build-navy.complete", 1, "Upgrade an army to naval deployment and retain maintenance.",
        "partial", "unsupported", ("TINationState.OnBuildSealiftPriorityComplete",),
    )
    NATION_ASSET_ARMY_MAINTENANCE = MechanicRule(
        "nation.asset.army.maintenance", 1,
        "Charge each army's scenario-dependent maintenance on the next daily base-IP calculation.",
        "verified", "exact",
        ("TINationState.SetBaseInvestmentPoints_month", "TIArmyState.GetInvestmentPointsMaintenance"),
        data_dependencies=("nationDevelopment.globalConfig.nationalInvestmentArmyFactor*",),
        test_ids=("tests.test_nation_projection.NationProjectionTransactionTests.test_build_army_deterministic_selection_and_next_tick_maintenance",),
    )
    NATION_PRIORITY_INITIATE_NUCLEAR_COMPLETE = MechanicRule(
        "nation.priority.initiate-nuclear-program.complete", 1, "Create the national nuclear program capability.",
        "pending", "unsupported", ("TINationState.OnInitiateNuclearProgramComplete",),
    )
    NATION_PRIORITY_BUILD_NUCLEAR_COMPLETE = MechanicRule(
        "nation.priority.build-nuclear-weapons.complete", 1, "Increase the national nuclear weapon count.",
        "partial", "unsupported", ("TINationState.OnBuildNuclearWeaponsPriorityComplete",),
    )
    NATION_PRIORITY_SPACE_DEFENSE_COMPLETE = MechanicRule(
        "nation.priority.build-space-defenses.complete", 1, "Create regional space defenses with aggregate dependencies.",
        "partial", "unsupported", ("TINationState.OnBuildSpaceDefensesPriorityComplete",),
    )
    NATION_PRIORITY_STO_COMPLETE = MechanicRule(
        "nation.priority.build-sto-squadron.complete", 1, "Create a regional STO fighter squadron.",
        "partial", "unsupported", ("TINationState.OnBuildSTOSquadronPriorityComplete",),
    )
    NATION_PRIORITY_SPACEFLIGHT_COMPLETE = MechanicRule(
        "nation.priority.initiate-spaceflight.complete", 1, "Create the national spaceflight program capability.",
        "pending", "unsupported", ("TINationState.OnSpaceFlightProgramPriorityComplete",),
    )
    NATION_PERIODIC_COHESION = MechanicRule(
        "nation.periodic.cohesion", 1,
        "Move cohesion toward its cached resting value during the monthly nation update.",
        "verified", "exact",
        ("TINationState.MonthlyNationUpdate", "TINationState.GetMonthlyCohesionMovement"),
        data_dependencies=("nationDevelopment.globalConfig.maxMonthlyCohesion*",),
        test_ids=("tests.test_nation_projection.NationProjectionTransactionTests.test_monthly_cohesion_and_unrest",),
    )
    NATION_PERIODIC_UNREST = MechanicRule(
        "nation.periodic.unrest", 1,
        "Move unrest toward its cached resting value during the monthly nation update.",
        "verified", "exact",
        ("TINationState.MonthlyNationUpdate", "TINationState.GetMonthlyUnrestMovement"),
        data_dependencies=("nationDevelopment.globalConfig.maxMonthlyUnrestMovement*",),
        test_ids=("tests.test_nation_projection.NationProjectionTransactionTests.test_monthly_cohesion_and_unrest",),
    )
    NATION_PERIODIC_DERIVED_CACHE = MechanicRule(
        "nation.periodic.derived-cache", 1,
        "Refresh daily region/priority caches and the 12:00 cohesion/unrest resting-state cache at DLL boundaries.",
        "verified", "exact",
        ("TINationState.CacheRegionValues", "TINationState.DailyNationUpdate2"),
        ("TINationState.DailyNationUpdate", "TINationState.NationPeriodicUpdate"),
        test_ids=("tests.test_nation_projection.NationProjectionTransactionTests.test_daily_rest_cache_matches_literal_formula",),
    )
    NATION_PERIODIC_CONTROL_POINTS = MechanicRule(
        "nation.periodic.control-points", 1,
        "Run monthly control-point reconciliation; v1 stops before a projected CP-count mutation.",
        "partial", "unsupported",
        ("TINationState.UpdateControlPoints", "TINationState.MonthlyNationUpdate"),
        test_ids=("tests.test_nation_projection.NationProjectionTransactionTests.test_monthly_control_point_count_change_rolls_back_before_population",),
        coverage_mode="conditional",
        allowed_coverages=CoverageResolvers.PERIODIC_CONTROL_POINTS.allowed_coverages,
        coverage_resolver_id=CoverageResolvers.PERIODIC_CONTROL_POINTS.id,
    )
    NATION_PERIODIC_POPULATION = MechanicRule(
        "nation.periodic.population", 2,
        "Orchestrate nation-order monthly region population growth and immediate GDP/cache dependencies.",
        "verified", "expected",
        ("TINationState.MonthlyNationUpdate", "TIRegionState.GrowPopulationByMonth"),
        test_ids=("tests.test_nation_projection.NationProjectionTransactionTests.test_monthly_population_expected",),
    )
    NATION_POPULATION_ANNUAL_GROWTH = MechanicRule(
        "nation.population.annual-growth", 1,
        "Derive annual regional population growth from live nation, region, campaign and held-fixed world context.",
        "verified", "exact",
        ("TIRegionState.get_annualPopulationGrowth", "GameControl.get_CampaignDurationYearsExact"),
        data_dependencies=(
            "nationDevelopment.startTime.populationRegressionPeriod_years",
            "nationDevelopment.nations.*.popGrowthModifier",
            "nationDevelopment.regions.*.annualPopGrowthModifier",
            "nationDevelopment.regions.*.environment",
            "nationDevelopment.regions.*.latitude",
        ),
        test_ids=("tests.test_nation_projection.NationProjectionTransactionTests.test_population_formula_uses_deterministic_mean_input_not_trajectory_expectation",),
    )
    NATION_POPULATION_MONTHLY_GROWTH = MechanicRule(
        "nation.population.monthly-growth", 1,
        "Apply monthly compound growth with uniform jitter replaced by its zero mean input and population floor.",
        "verified", "expected",
        ("TIRegionState.GrowPopulationByMonth",),
        data_dependencies=("nationDevelopment.daysPerYear",),
        deterministic=False,
        test_ids=("tests.test_nation_projection.NationProjectionTransactionTests.test_monthly_population_expected",),
    )
    NATION_ADVISOR_ATTRIBUTE_SOURCE = MechanicRule(
        "nation.advisor.attribute-source", 1,
        "Use TICouncilorState.GetAttribute values for nation Advise bonuses.",
        "verified", "exact",
        ("TICouncilorState.AdvisingBonus", "TIMissionEffect_Advise.ApplyEffect"),
        test_ids=("tests.test_nation_projection.NationProjectionPlanTests.test_saved_and_virtual_advisor_validation",),
    )
    NATION_ADVISOR_STACKING = MechanicRule(
        "nation.advisor.stacking", 1,
        "Sort advisors by attribute and apply 1/rank decay after stat/100 conversion.",
        "verified", "exact",
        ("TINationState.GetAdvisingScore", "TICouncilorState.AdvisingBonus"),
        test_ids=("tests.test_nation_projection.NationProjectionTransactionTests.test_advisor_base_ip_and_rank_decay",),
    )
    NATION_FACTION_CONTRIBUTION = MechanicRule(
        "nation.faction-contribution", 1,
        "Convert the target nation's totals to the selected faction's active CP share.",
        "verified", "exact",
        ("TINationState.GetMonthlyResearchFromControlPoint", "TINationState.GetMonthlyMoneyIncomeFromControlPoint", "TINationState.GetMonthlyBoostIncomeFromControlPoint", "TINationState.GetMissionControlFromControlPoint"),
        test_ids=("tests.test_nation_projection.NationProjectionTransactionTests.test_funding_completion_and_contribution",),
    )


REGISTRY = {rule.id: rule for rule in (
    Rules.NATION_IP_BASE,
    Rules.NATION_IP_ECONOMY_SCORE,
    Rules.NATION_IP_CONTROL_POINT_ALLOCATION,
    Rules.NATION_IP_PRIORITY_BONUS,
    Rules.NATION_IP_CONTROL_POINT_DEFAULT_ECONOMY,
    Rules.NATION_PRIORITY_VALIDITY,
    Rules.NATION_PRIORITY_COMPLETION_ORDER,
    Rules.NATION_PRIORITY_KNOWLEDGE_COMPLETE,
    Rules.NATION_PRIORITY_GOVERNMENT_COMPLETE,
    Rules.NATION_PRIORITY_GOVERNMENT_LEGITIMIZE,
    Rules.NATION_PRIORITY_UNITY_COMPLETE,
    Rules.NATION_PRIORITY_FUNDING_COMPLETE,
    Rules.NATION_PRIORITY_ECONOMY_COMPLETE,
    Rules.NATION_PRIORITY_WELFARE_COMPLETE,
    Rules.NATION_PRIORITY_WELFARE_INEQUALITY,
    Rules.NATION_PRIORITY_WELFARE_COLONY_TRIGGER,
    Rules.NATION_PRIORITY_WELFARE_DECOLONIZATION,
    Rules.NATION_PRIORITY_WELFARE_DECOLONIZATION_DOWNSTREAM,
    Rules.NATION_PRIORITY_ENVIRONMENT_COMPLETE,
    Rules.NATION_PRIORITY_OPPRESSION_COMPLETE,
    Rules.NATION_PRIORITY_SPOILS_COMPLETE,
    Rules.NATION_PRIORITY_BOOST_COMPLETE,
    Rules.NATION_PRIORITY_MISSION_CONTROL_COMPLETE,
    Rules.NATION_PRIORITY_MISSION_CONTROL_PLACEMENT,
    Rules.NATION_PRIORITY_FOUND_MILITARY_COMPLETE,
    Rules.NATION_PRIORITY_MILITARY_COMPLETE,
    Rules.NATION_PRIORITY_BUILD_ARMY_COMPLETE,
    Rules.NATION_PRIORITY_BUILD_ARMY_PLACEMENT,
    Rules.NATION_PRIORITY_BUILD_NAVY_COMPLETE,
    Rules.NATION_ASSET_ARMY_MAINTENANCE,
    Rules.NATION_PRIORITY_INITIATE_NUCLEAR_COMPLETE,
    Rules.NATION_PRIORITY_BUILD_NUCLEAR_COMPLETE,
    Rules.NATION_PRIORITY_SPACE_DEFENSE_COMPLETE,
    Rules.NATION_PRIORITY_STO_COMPLETE,
    Rules.NATION_PRIORITY_SPACEFLIGHT_COMPLETE,
    Rules.NATION_PERIODIC_COHESION,
    Rules.NATION_PERIODIC_UNREST,
    Rules.NATION_PERIODIC_DERIVED_CACHE,
    Rules.NATION_PERIODIC_CONTROL_POINTS,
    Rules.NATION_PERIODIC_POPULATION,
    Rules.NATION_POPULATION_ANNUAL_GROWTH,
    Rules.NATION_POPULATION_MONTHLY_GROWTH,
    Rules.NATION_ADVISOR_ATTRIBUTE_SOURCE,
    Rules.NATION_ADVISOR_STACKING,
    Rules.NATION_FACTION_CONTRIBUTION,
)}


def validate_registry(rules: Iterable[MechanicRule] | None = None) -> None:
    values = tuple(rules or REGISTRY.values())
    ids = [rule.id for rule in values]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate mechanic rule ID")
    for rule in values:
        if not rule.id or rule.id != rule.id.lower() or " " in rule.id:
            raise ValueError(f"Invalid mechanic rule ID: {rule.id!r}")
        if rule.implementation_revision < 1:
            raise ValueError(f"Invalid implementation revision for {rule.id}")
        if rule.audit_status not in AUDIT_STATUSES:
            raise ValueError(f"Invalid audit status for {rule.id}")
        if rule.coverage not in COVERAGE_LEVELS:
            raise ValueError(f"Invalid coverage for {rule.id}")
        if rule.coverage_mode not in COVERAGE_MODES:
            raise ValueError(f"Invalid coverage mode for {rule.id}")
        if rule.coverage_mode == "static":
            if rule.allowed_coverages or rule.coverage_resolver_id is not None:
                raise ValueError(f"Static mechanic rule declares a resolver: {rule.id}")
        else:
            if not rule.coverage_resolver_id:
                raise ValueError(f"Conditional mechanic rule has no resolver: {rule.id}")
            resolver = COVERAGE_RESOLVERS.get(rule.coverage_resolver_id)
            if resolver is None:
                raise ValueError(f"Unregistered coverage resolver for {rule.id}")
            if not rule.allowed_coverages:
                raise ValueError(f"Conditional mechanic rule has no allowed coverage: {rule.id}")
            if tuple(rule.allowed_coverages) != resolver.allowed_coverages:
                raise ValueError(f"Coverage resolver branches do not match for {rule.id}")
            if any(value not in COVERAGE_LEVELS for value in rule.allowed_coverages):
                raise ValueError(f"Conditional mechanic rule has invalid coverage branch: {rule.id}")
            if len(rule.allowed_coverages) != len(set(rule.allowed_coverages)):
                raise ValueError(f"Conditional mechanic rule has duplicate coverage branch: {rule.id}")
            if rule.coverage not in rule.allowed_coverages:
                raise ValueError(f"Conditional mechanic rule default coverage is not an allowed branch: {rule.id}")
        has_supported_path = rule.coverage != "unsupported" or any(
            value != "unsupported" for value in rule.allowed_coverages
        )
        if has_supported_path and not rule.test_ids:
            raise ValueError(f"Supported mechanic rule has no tests: {rule.id}")


def validate_rule_execution(
    rule_id: str,
    effective_coverage: str,
    *,
    coverage_resolver_id: str | None = None,
) -> MechanicRule:
    """Fail closed when a runtime execution claims coverage outside registry metadata."""

    rule = REGISTRY.get(rule_id)
    if rule is None:
        raise ValueError(f"Unregistered mechanic rule ID: {rule_id}")
    if effective_coverage not in COVERAGE_LEVELS:
        raise ValueError(f"Invalid effective coverage for {rule_id}: {effective_coverage}")
    if rule.coverage_mode == "static":
        if coverage_resolver_id is not None:
            raise ValueError(f"Static mechanic rule cannot use a coverage resolver: {rule_id}")
        if effective_coverage != rule.coverage:
            raise ValueError(
                f"Static mechanic rule {rule_id} requires {rule.coverage}, got {effective_coverage}"
            )
    else:
        if coverage_resolver_id != rule.coverage_resolver_id:
            raise ValueError(f"Wrong coverage resolver for {rule_id}: {coverage_resolver_id}")
        if effective_coverage not in rule.allowed_coverages:
            raise ValueError(
                f"Coverage resolver {coverage_resolver_id} cannot yield {effective_coverage}"
            )
    return rule


def mechanic_rule_test(
    *rule_ids: str,
    evidence: str,
) -> Callable[[Callable[..., object]], Callable[..., object]]:
    """Attach stable mechanic rule IDs and the assertion evidence kind."""

    unknown = sorted(set(rule_ids) - set(REGISTRY))
    if unknown:
        raise ValueError(f"Unregistered mechanic rule ID: {', '.join(unknown)}")
    if evidence not in TEST_EVIDENCE_TYPES:
        raise ValueError(f"Invalid mechanic test evidence: {evidence}")

    def decorate(test: Callable[..., object]) -> Callable[..., object]:
        setattr(test, "mechanic_rule_ids", tuple(dict.fromkeys(rule_ids)))
        setattr(test, "mechanic_rule_evidence", evidence)
        return test

    return decorate


def validate_test_metadata(
    resolve_test: Callable[[str], Callable[..., object]],
    rules: Iterable[MechanicRule] | None = None,
) -> None:
    """Verify every supported registry/test link is declared by the test itself."""

    for rule in tuple(rules or REGISTRY.values()):
        has_supported_path = rule.coverage != "unsupported" or any(
            value != "unsupported" for value in rule.allowed_coverages
        )
        if not has_supported_path:
            continue
        has_direct_evidence = False
        for test_id in rule.test_ids:
            test = resolve_test(test_id)
            declared = set(getattr(test, "mechanic_rule_ids", ()))
            if rule.id not in declared:
                raise ValueError(f"Test {test_id} does not declare mechanic rule {rule.id}")
            evidence = getattr(test, "mechanic_rule_evidence", None)
            if evidence not in TEST_EVIDENCE_TYPES:
                raise ValueError(f"Test {test_id} has no valid mechanic evidence kind")
            if evidence != "contract" and test_id != REGISTRY_CONTRACT_TEST_ID:
                has_direct_evidence = True
        if not has_direct_evidence:
            raise ValueError(f"Supported mechanic rule has no direct non-contract evidence: {rule.id}")


def mechanic_diagnostics(rule_ids: Iterable[str]) -> list[dict[str, object]]:
    output = []
    for rule_id in sorted(set(rule_ids)):
        if rule_id not in REGISTRY:
            raise ValueError(f"Unregistered mechanic rule ID: {rule_id}")
        output.append(REGISTRY[rule_id].diagnostics())
    return output


validate_registry()
