"""Required nation relations cannot be satisfied by unrelated state rows."""

import copy

import pytest

from tests.fixtures.fairplay_projection import make_save_data, ref, row
import ti_save_parser as parser


@pytest.mark.parametrize("relation", ["rivals", "wars", "allies", "adjacentNations"])
def test_rest_relation_rejects_wrong_type_even_with_nation_shaped_fields(relation):
    data = make_save_data()
    nation = data["gamestates"]["TINationState"][0]["Value"]
    # A resolvable row with all the expected field names is still not a nation.
    impostor = copy.deepcopy(nation)
    impostor.pop("ID")
    data["gamestates"]["TIHabSiteState"] = [row(900, **impostor)]
    nation[relation] = (
        [{"Key": ref(900), "Value": "FullAdjacency"}]
        if relation == "adjacentNations" else [ref(900)]
    )
    with pytest.raises(parser.CalculationDependencyError) as caught:
        parser.calculate_nation_projection(
            parser.build_index(data), "USA", None,
            {"plans": [{"name": "p", "segments": [{}]}]},
            days=1, checkpoints=[], details=False, diagnostics=False,
        )
    assert any(
        dependency["name"] == f"nation.{relation}"
        for dependency in caught.value.missing_dependencies
    )


def test_projection_rejects_nonfederation_membership_reference():
    data = make_save_data()
    data["gamestates"]["TINationState"][0]["Value"]["federation"] = ref(31)
    with pytest.raises(parser.CalculationDependencyError) as caught:
        parser.calculate_nation_projection(
            parser.build_index(data), "USA", None,
            {"plans": [{"name": "p", "segments": [{}]}]},
            days=1, checkpoints=[], details=False, diagnostics=False,
        )
    assert any(
        dependency["name"] == "nation.federation"
        for dependency in caught.value.missing_dependencies
    )
