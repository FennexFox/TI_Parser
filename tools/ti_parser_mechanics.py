"""Audited Terra Invicta mechanics registry shared by code, tests and diagnostics.

The registry describes provenance; executable mechanics live in Python modules.
Stable IDs must not be reused for a different meaning.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


COVERAGE_LEVELS = frozenset({"exact", "expected", "aggregateOnly", "unsupported"})
AUDIT_STATUSES = frozenset({"verified", "partial", "pending", "deprecated"})
ASSEMBLY_CSHARP_SHA256 = "5ec67c601a6ce39d985aa9830a99faa9844aee7d7e12ec5e28ea46ff020ba982"


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

    def diagnostics(self) -> dict[str, object]:
        return {
            "id": self.id,
            "implementationRevision": self.implementation_revision,
            "auditStatus": self.audit_status,
            "coverage": self.coverage,
            "dllSymbols": list(self.dll_symbols),
            "callers": list(self.callers),
            "dataDependencies": list(self.data_dependencies),
            "deterministic": self.deterministic,
            "sourceHash": self.source_hash,
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
        "nation.priority.government.complete", 1,
        "Apply Government democracy change below the cap; delegate to Knowledge at the cap.",
        "verified", "aggregateOnly",
        ("TINationState.OnGovernmentPriorityComplete", "TINationState.governmentPriorityDemocracyChange"),
        data_dependencies=("nationDevelopment.globalConfig.governmentPriorityDemocracyIncrease",),
        test_ids=("tests.test_nation_projection.NationProjectionTransactionTests.test_government_completion_below_cap",),
    )
    NATION_PRIORITY_UNITY_COMPLETE = MechanicRule(
        "nation.priority.unity.complete", 1,
        "Apply Unity cohesion and education effects; public-opinion details are not projected.",
        "verified", "aggregateOnly",
        ("TINationState.OnUnityPriorityComplete", "TINationState.unityPriorityCohesionChange", "TINationState.unityPriorityEducationChange"),
        data_dependencies=("nationDevelopment.globalConfig.unityBaseCohesionChange", "nationDevelopment.globalConfig.unityMinCohesionChange", "nationDevelopment.globalConfig.unityPriorityEducationChange"),
        test_ids=("tests.test_nation_projection.NationProjectionTransactionTests.test_unity_completion",),
    )
    NATION_PRIORITY_FUNDING_COMPLETE = MechanicRule(
        "nation.priority.funding.complete", 1,
        "Increase annual national funding on completion.",
        "verified", "exact",
        ("TINationState.OnFundingPriorityComplete", "TINationState.spaceFundingPriorityIncomeChange"),
        data_dependencies=("nationDevelopment.globalConfig.fundingPriorityBaseIncomeIncrease",),
        test_ids=("tests.test_nation_projection.NationProjectionTransactionTests.test_funding_completion_and_contribution",),
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
    NATION_PERIODIC_POPULATION = MechanicRule(
        "nation.periodic.population", 1,
        "Grow each region population during the monthly nation update.",
        "verified", "expected",
        ("TINationState.MonthlyNationUpdate", "TIRegionState.GrowPopulationByMonth"),
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
    Rules.NATION_IP_CONTROL_POINT_ALLOCATION,
    Rules.NATION_IP_PRIORITY_BONUS,
    Rules.NATION_PRIORITY_COMPLETION_ORDER,
    Rules.NATION_PRIORITY_KNOWLEDGE_COMPLETE,
    Rules.NATION_PRIORITY_GOVERNMENT_COMPLETE,
    Rules.NATION_PRIORITY_UNITY_COMPLETE,
    Rules.NATION_PRIORITY_FUNDING_COMPLETE,
    Rules.NATION_PERIODIC_COHESION,
    Rules.NATION_PERIODIC_UNREST,
    Rules.NATION_PERIODIC_POPULATION,
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
        if rule.coverage != "unsupported" and not rule.test_ids:
            raise ValueError(f"Supported mechanic rule has no tests: {rule.id}")


def mechanic_diagnostics(rule_ids: Iterable[str]) -> list[dict[str, object]]:
    output = []
    for rule_id in sorted(set(rule_ids)):
        if rule_id not in REGISTRY:
            raise ValueError(f"Unregistered mechanic rule ID: {rule_id}")
        output.append(REGISTRY[rule_id].diagnostics())
    return output


validate_registry()
