import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import ti_parser_nation_projection as projection


def context(*, diversity=None):
    return projection.ProjectionContext(
        faction_id=1,
        priorities={},
        global_config={
            "coreEcoRegionGDPModifier": {"value": 2.0},
            "coreResourceRegionGDPModifier": {"value": 1.5},
            "colonyRegionGDPModifier": {"value": 0.5},
            "federationGDPEconomyBonus": {"value": 0.01},
        },
        diversity_bonuses=diversity or {"Economy": 0.5, "Knowledge": 0.2, "Unity": 0.2},
    )


def region(region_id, population, *, occupation, core=False, resource=False, oil=False, colony=False):
    return projection.RegionProjectionState(
        id=region_id,
        population_millions=population,
        core_economic_region=core,
        resource_region=resource,
        oil_region=oil,
        colony=colony,
        occupation_fraction=occupation,
    )


def control_point(priority_bonuses):
    return projection.ControlPointProjectionState(
        id=1,
        position=0,
        owner_faction_id=1,
        benefits_disabled=False,
        control_point_type=None,
        pips={"Knowledge": 1, "Unity": 1},
        priority_bonuses=priority_bonuses,
    )


class CurrentBuildInvestmentTests(unittest.TestCase):
    def test_diversity_requires_national_plus_owner_bonus_above_negative_one(self):
        ctx = context()
        effective = {"Knowledge": 1, "Unity": 1}
        state = SimpleNamespace(federation_economy_bonus=0.0, cached_num_mining_regions=0)

        self.assertEqual(
            projection._diversity_bonus(state, control_point({"Knowledge": -1.0}), "Knowledge", effective, ctx),
            0.0,
        )
        self.assertAlmostEqual(
            projection._diversity_bonus(state, control_point({"Knowledge": -0.999}), "Knowledge", effective, ctx),
            0.1,
        )

        national_penalty_state = SimpleNamespace(federation_economy_bonus=-100.0, cached_num_mining_regions=0)
        economy_effective = {"Economy": 1, "Unity": 1}
        self.assertEqual(
            projection._diversity_bonus(
                national_penalty_state,
                control_point({}),
                "Economy",
                economy_effective,
                ctx,
            ),
            0.0,
        )

    def test_base_ip_uses_live_gdp_weighted_region_occupation(self):
        state = SimpleNamespace(
            advisors=(),
            economy_score=30.0,
            occupation_factor=0.0,
            unrest=2.0,
            army_maintenance=0.0,
            armies=[],
            regions={
                1: region(1, 10.0, occupation=0.5, core=True),
                2: region(2, 30.0, occupation=0.0, resource=True),
            },
            metric_tracker=projection.MetricDependencyTracker(),
        )

        # DLL weights are 10 * 2.0 and 30 * 1.5, so the penalty is
        # (20 / 65) * 0.5 and the live occupation factor is 55 / 65.
        self.assertAlmostEqual(projection._base_ip(state, context()), 30.0 * 55.0 / 65.0)

    def test_base_ip_stops_when_a_region_occupation_value_is_missing(self):
        state = SimpleNamespace(
            advisors=(),
            economy_score=30.0,
            occupation_factor=1.0,
            unrest=2.0,
            army_maintenance=0.0,
            armies=[],
            regions={1: region(1, 10.0, occupation=None)},
            metric_tracker=projection.MetricDependencyTracker(),
        )

        with self.assertRaises(projection.ProjectionRuntimeStop):
            projection._base_ip(state, context())


if __name__ == "__main__":
    unittest.main()
