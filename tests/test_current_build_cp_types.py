"""Current-build control-point type selection and monthly integration."""

import copy
from dataclasses import replace
from datetime import datetime

import pytest

from tests.test_current_build_monthly import rest_context, source_state
from tests.test_nation_projection import context, state
from ti_parser_mechanics import Rules
import ti_parser_nation_projection as projection


def source_control_point_state(count=6):
    value = state(cp_count=count)
    value.rest_state_context.update({"sourceBacked": True, "alienNation": False, "wars": [], "rivals": []})
    return value


@pytest.mark.parametrize(
    ("democracy", "education", "cohesion", "enemy_count", "expected"),
    [
        # Knowledge needs both values strictly above 9; the financial branch
        # then wins when its own strict thresholds are met.
        (9.0, 10.0, 4.0, None, "FinancialSector"),
        (10.0, 9.0, 4.0, None, "FinancialSector"),
        # The first branch has precedence over DefenseSector.
        (9.5, 9.5, 7.0, 6, "KnowledgeSector"),
        (8.0, 8.0, 7.01, 6, "DefenseSector"),
        # An enemy must have at least as many control points as this nation.
        (8.0, 8.0, 7.01, 5, "FinancialSector"),
        # Financial requires democracy > 6, while exactly 6 falls through.
        (6.0, 8.0, 4.0, None, "AgriculturalSector"),
    ],
)
def test_last_control_point_sector_thresholds_match_current_dll(
    democracy, education, cohesion, enemy_count, expected
):
    value = source_control_point_state()
    value.democracy = democracy
    value.education = education
    value.cohesion = cohesion
    if enemy_count is not None:
        value.rest_state_context["wars"] = [{"id": 22, "numControlPoints": enemy_count}]

    projection._refresh_control_point_types(value, context())

    last_position = next(cp for cp in value.control_points.values() if cp.position == 0)
    assert last_position.control_point_type == expected


def test_each_control_point_position_uses_its_current_build_role():
    value = source_control_point_state()
    value.democracy = 5.0
    value.education = 8.0
    value.cohesion = 4.0

    types_by_id = projection._refresh_control_point_types(value, context())

    assert {
        cp.position: types_by_id[cp.id]
        for cp in value.control_points.values()
    } == {
        0: "AgriculturalSector",
        1: "RegionalAuthorities",
        2: "Corporations",
        3: "MassMedia",
        4: "Legislature",
        5: "Executive",
    }


def test_missing_enemy_inputs_stop_before_any_control_point_type_is_changed():
    value = source_control_point_state()
    value.democracy = 8.0
    value.education = 8.0
    value.cohesion = 8.0
    value.rest_state_context.pop("rivals")
    # Evaluate all non-sector ranks before the last sector rank, so this also
    # protects the collect-then-commit behavior from partial mutation.
    value.control_points = {
        cp.id: cp
        for cp in sorted(value.control_points.values(), key=lambda item: item.position, reverse=True)
    }
    for cp in value.control_points.values():
        cp.control_point_type = f"previous-{cp.position}"

    with pytest.raises(projection.ProjectionRuntimeStop, match="resolved war and rival inputs") as caught:
        projection._refresh_control_point_types(value, context())

    assert caught.value.dependencies[0]["field"] == "rivals.numControlPoints"
    assert {cp.control_point_type for cp in value.control_points.values()} == {
        f"previous-{cp.position}" for cp in value.control_points.values()
    }


def test_live_faction_contribution_flags_follow_recomputed_sector_types():
    value = source_control_point_state()
    for cp in value.control_points.values():
        cp.owner_faction_id = 8
    sector_cp = next(cp for cp in value.control_points.values() if cp.position == 0)
    sector_cp.owner_faction_id = 7
    current_context = replace(context(), knowledge_sector_bonus=1.5, financial_sector_bonus=1.25)

    projection._refresh_control_point_types(value, current_context)

    value.democracy = 10.0
    value.education = 10.0
    projection._refresh_control_point_types(value, current_context)
    knowledge = projection._contribution(value, current_context)
    without_knowledge = copy.deepcopy(value)
    without_knowledge.control_points[sector_cp.id].control_point_type = "AgriculturalSector"
    knowledge_baseline = projection._contribution(without_knowledge, current_context)
    assert sector_cp.control_point_type == "KnowledgeSector"
    assert knowledge["research"] == pytest.approx(knowledge_baseline["research"] * 1.5)
    assert knowledge["funding"] == pytest.approx(knowledge_baseline["funding"])

    value.democracy = 8.0
    value.education = 8.0
    projection._refresh_control_point_types(value, current_context)
    financial = projection._contribution(value, current_context)
    without_financial = copy.deepcopy(value)
    without_financial.control_points[sector_cp.id].control_point_type = "AgriculturalSector"
    financial_baseline = projection._contribution(without_financial, current_context)
    assert sector_cp.control_point_type == "FinancialSector"
    assert financial["research"] == pytest.approx(financial_baseline["research"])
    assert financial["funding"] == pytest.approx(financial_baseline["funding"] * 1.25)


def test_monthly_commits_control_point_types_with_exact_rule_coverage():
    value = source_state()
    value.at = datetime(2030, 1, 31, 23)
    value.control_points[1].control_point_type = "Aristocracy"
    plan = projection.PriorityPlan("p", (projection.PlanSegment(None, None, None, None),))

    result = projection.run_projection(value, plan, rest_context(), days=1, details=True)

    monthly = next(row for row in result["transactions"] if row["kind"] == "monthly")
    execution = next(
        row for row in monthly["ruleExecutions"]
        if row["ruleId"] == Rules.NATION_PERIODIC_CONTROL_POINT_TYPES.id
    )
    type_phase = next(row for row in monthly["phaseTrace"] if row["phase"] == "monthly.controlPointTypes")
    assert result["status"] == "complete"
    assert execution["effectiveCoverage"] == "exact"
    assert Rules.NATION_PERIODIC_CONTROL_POINT_TYPES.id in monthly["mechanicRules"]
    assert type_phase["types"] == {1: "Executive"}
    assert result["transactions"].index(monthly) < next(
        index for index, row in enumerate(result["transactions"]) if row["kind"] == "investment"
    )


def test_exact_type_rule_retains_expected_coverage_from_mean_path_inputs():
    value = source_state()
    value.control_points = state(cp_count=4).control_points
    for cp in value.control_points.values():
        cp.control_point_type = "Aristocracy"
    value.democracy = 5.0
    value.education = 8.0
    value.inequality = 3.0
    current_context = replace(
        rest_context(),
        global_config={
            **rest_context().global_config,
            "controlPointCountScaling": {"value": 0.2},
        },
    )

    transaction, _ = projection._run_monthly_transaction(value, current_context, 1)

    execution = next(
        row for row in transaction["ruleExecutions"]
        if row["ruleId"] == Rules.NATION_PERIODIC_CONTROL_POINT_TYPES.id
    )
    sector_point = next(cp for cp in value.control_points.values() if cp.position == 0)
    assert execution["effectiveCoverage"] == "exact"
    assert value.metric_tracker.evidence["internal.controlPointTypes"].coverage == "expected"
    assert sector_point.control_point_type == "TradeUnions"


def test_monthly_type_dependency_keeps_only_the_authoritative_prefix():
    value = source_state()
    value.at = datetime(2030, 1, 31, 23)
    value.control_points = state(cp_count=6).control_points
    value.democracy = 8.0
    value.education = 8.0
    value.cohesion = 8.0
    value.rest_state_context["rivals"] = [{"democracy": 8.0, "numControlPoints": 6}]
    for cp in value.control_points.values():
        cp.control_point_type = "KnowledgeSector"
    current_context = replace(
        rest_context(),
        global_config={
            **rest_context().global_config,
            "controlPointCountScaling": {"value": 0.26},
        },
    )
    plan = projection.PriorityPlan("p", (projection.PlanSegment(None, None, None, None),))

    result = projection.run_projection(value, plan, current_context, days=1, details=True)

    assert result["status"] == "incomplete"
    assert result["runtimeStop"]["phase"] == "beforeControlPointTypeMutation"
    assert result["missingDependencies"] == [{"field": "rivals.id", "source": "save.TINationState"}]
    assert [row["kind"] for row in result["transactions"]] == ["factionCache"]
    assert result["runtimeStop"]["lastAuthoritativeTransaction"] == {
        "kind": "factionCache",
        "day": 0,
        "at": "2030-02-01T00:00:00",
        "transactionStatus": "committed",
    }
    assert result["runtimeStop"]["attemptedTransaction"]["kind"] == "monthly"
    assert result["runtimeStop"]["attemptedTransaction"]["ruleExecutions"] == []
