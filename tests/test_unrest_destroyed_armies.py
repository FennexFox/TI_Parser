"""Destroyed armies do not contribute to the live unrest army term."""

from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import patch

from tests.fixtures.fairplay_projection import make_save_data, ref, row
from tests.test_nation_projection import context, state
import ti_parser_nation_projection as projection
import ti_parser_projection_adapter as adapter
import ti_save_parser as parser


def test_source_backed_unrest_excludes_destroyed_own_armies_from_eligibility_and_impact():
    value = state()
    value.rest_state_context = {
        "sourceBacked": True,
        "ownBaseInvestmentPointsMonth": None,
    }
    value.armies = [
        projection.ArmyProjectionState(1, 3.0, "Standard", 1, 1, 0, None, "Human", destroyed=True),
    ]

    # A destroyed army in the nation must neither demand the saved base-IP cache
    # nor lower the unrest target.
    assert projection._own_army_unrest_impact(value, context()) == 0.0

    value.rest_state_context["ownBaseInvestmentPointsMonth"] = 30.0
    value.armies.append(
        projection.ArmyProjectionState(2, 1.0, "Standard", 1, 1, 0, None, "Human"),
    )
    assert projection._own_army_unrest_impact(value, context()) == -2.5


def test_source_backed_rest_extraction_skips_destroyed_allied_armies():
    data = make_save_data()
    nation = data["gamestates"]["TINationState"][0]["Value"]
    nation["allies"] = [ref(200)]
    data["gamestates"]["TINationState"].append(
        row(
            200,
            templateName="Ally",
            alienNation=False,
            regions=[],
            controlPoints=[],
            armies=[ref(301), ref(302)],
            baseInvestmentPoints_month=14.0,
        )
    )
    data["gamestates"]["TIArmyState"] = [
        row(
            301,
            armyType="Human",
            strength=0.5,
            currentRegion=ref(100),
            homeNation=ref(200),
            destroyed=False,
        ),
        row(
            302,
            armyType="Human",
            strength=4.0,
            currentRegion=ref(100),
            homeNation=ref(200),
            destroyed=True,
        ),
    ]

    value = state()
    region = replace(value.regions[1], id=100, template_name="California")
    value.regions = {100: region}
    value.public_opinion = {"Resist": 1.0, "Undecided": 0.0}
    value.world_context["pcgdpToReduceUnrestBy1"] = 10_000.0
    development = {
        "regionTemplates": {"California": {"mapRegionName": "California"}},
        "mapRegionTemplates": {"California": {"solarBody": "Earth"}},
    }

    with (
        patch.object(
            adapter,
            "load_location_catalog",
            return_value=SimpleNamespace(body_templates={"Earth": {"meanRadius_km": 6371.0}}),
        ),
        patch.object(adapter, "_projection_alien_hab_surveillance", return_value=0.0),
    ):
        rest_inputs = adapter._extract_projection_rest_inputs(
            parser.build_index(data), nation, value, development
        )

    assert rest_inputs["alliedArmies"] == [
        {
            "strength": 0.5,
            "armyType": "Human",
            "factionId": None,
            "currentRegionId": 100,
            "homeBaseInvestmentPointsMonth": 14.0,
        }
    ]
