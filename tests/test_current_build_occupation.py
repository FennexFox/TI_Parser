"""Current-DLL war-alliance occupation aggregation regressions."""
import math
from ti_parser_core import build_index
from ti_parser_projection_adapter import _region_occupation_fraction


def indexed(wars):
    def row(key, **value):
        return {"Key": {"value": key}, "Value": {"ID": {"value": key}, **value}}
    return build_index({"gamestates": {
        "TINationState": [row(n) for n in (1, 2, 3, 4)],
        "TIWarState": [row(k, **v) for k,v in wars.items()]}})


def test_occupation_sums_enemy_alliance_and_takes_highest_war_not_individual():
    idx = indexed({10: {"_attackingAlliance": [{"value":1}], "_defendingAlliance": [{"value":2},{"value":3}]},
                   11: {"_attackingAlliance": [{"value":4}], "_defendingAlliance": [{"value":1}]}})
    region = {"occupations": [{"Key": {"value":n}, "Value": v} for n,v in ((2,.4),(3,.35),(4,.6))]}
    nation = {"currentWarStates": [{"value":10},{"value":11}]}
    assert _region_occupation_fraction(region, idx, nation, 1) == .75
    region["occupations"][0]["Value"] = .9
    assert _region_occupation_fraction(region, idx, nation, 1) == 1.0
    assert _region_occupation_fraction(region, idx, {"currentWarStates": []}, 1) == 0.0


def test_occupation_unresolved_war_and_malformed_rows_fail_closed():
    idx = indexed({10: {"_attackingAlliance": [{"value":1}], "_defendingAlliance": [{"value":99}]}})
    region = {"occupations": [{"Key": {"value":2}, "Value": .4}]}
    assert math.isnan(_region_occupation_fraction(region, idx, {"currentWarStates": [{"value":10}]}, 1))
    assert math.isnan(_region_occupation_fraction(region, idx, {}, 1))
    assert math.isnan(_region_occupation_fraction({"occupations": [{"Key": {"value":2}}]}, idx, {}, 1))
    assert _region_occupation_fraction({"occupations": []}, idx, {}, 1) == 0.0
