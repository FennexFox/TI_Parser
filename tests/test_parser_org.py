import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import ti_parser_org as org
import ti_save_parser as ti


def ref(state_id):
    return {"value": state_id}


def profile(councilor_id, administration, org_ids=(), traits=()):
    attributes = {attribute: 0 for attribute in ti.COUNCILOR_ATTRIBUTES}
    attributes["Administration"] = administration
    return {
        "id": councilor_id,
        "display": f"Councilor {councilor_id}",
        "baseAttributes": attributes,
        "traitAttributeMods": {},
        "assignedOrgIds": list(org_ids),
        "councilor": {"traitTemplateNames": list(traits)},
    }


def org_state(state_id, *, tier, **values):
    return {
        "ID": ref(state_id),
        "displayName": f"Org {state_id}",
        "templateName": values.pop("templateName", f"Org{state_id}"),
        "tier": tier,
        **values,
    }


def save_state(state_id, value):
    return {"Key": ref(state_id), "Value": {"ID": ref(state_id), **value}}


class ParserOrgParityTests(unittest.TestCase):
    def test_match_named_parity(self):
        items = [
            {"template": "AlphaTemplate", "code": "ALPHA", "display": "Alpha Display"},
            {"template": "BetaTemplate", "code": "BETA", "display": "Beta Display"},
        ]

        self.assertEqual(ti.match_named(items, "beta"), org.match_named(items, "beta"))
        self.assertEqual(ti.match_named(items, "Alpha Display"), org.match_named(items, "Alpha Display"))

    def test_best_assignment_parity(self):
        orgs = {
            1: org_state(1, tier=1, science=2),
            2: org_state(2, tier=1),
            3: org_state(3, tier=1, science=3),
        }
        councilor = profile(10, 2, (1, 2))

        wrapper = ti.org_plan_best_assignment(councilor, orgs, councilor["assignedOrgIds"], 3, "market", {}, "science")
        direct = org.org_plan_best_assignment(councilor, orgs, councilor["assignedOrgIds"], 3, "market", {}, "science")

        self.assertEqual(wrapper, direct)
        self.assertEqual([row["id"] for row in wrapper["removedOrgs"]], [2])

    def test_investigation_focus_is_preserved(self):
        orgs = {1: org_state(1, tier=1, investigation=4)}

        action = ti.org_plan_best_assignment(profile(10, 1), orgs, [], 1, "market", {}, "investigation")

        self.assertIsNotNone(action)
        self.assertEqual(action["attributeDelta"], {"Investigation": 4})
        self.assertEqual(action["objectiveGain"], 4)

    def test_nation_condition_fields_are_preserved(self):
        result = ti.evaluate_condition(
            {
                "conditionType": "TINationCondition_fCohesion",
                "condition": {"sign": "GreaterThanOrEqualTo", "strValue": "5"},
            },
            {},
            {"global": {}},
            {"cohesion": 6},
        )

        self.assertTrue(result["conditionResult"])
        self.assertEqual(result["conditionField"], "cohesion")

    def test_calculate_org_plan_parity(self):
        data = {
            "gamestates": {
                "TIFactionState": [
                    save_state(
                        1,
                        {
                            "templateName": "ResistCouncil",
                            "displayName": "Resistance",
                            "councilors": [ref(10)],
                            "availableOrgs": [ref(100)],
                            "unassignedOrgs": [],
                            "resources": {},
                        },
                    )
                ],
                "TICouncilorState": [
                    save_state(
                        10,
                        {
                            "templateName": "Councilor10",
                            "displayName": "Councilor 10",
                            "traitTemplateNames": [],
                            "conditionalTraitMods": [],
                            "orgs": [],
                            "attributes": {
                                **{attribute: 0 for attribute in ti.COUNCILOR_ATTRIBUTES},
                                "Administration": 1,
                            },
                        },
                    )
                ],
                "TIOrgState": [
                    save_state(
                        100,
                        {
                            "templateName": "Org100",
                            "displayName": "Org 100",
                            "tier": 1,
                            "science": 3,
                        },
                    )
                ],
            }
        }
        indexed = ti.build_index(data)

        wrapper = ti.calculate_org_plan(indexed, None)
        direct = org.calculate_org_plan(indexed, None)

        self.assertEqual(wrapper, direct)
        self.assertEqual(wrapper["committeePlan"]["actions"][0]["candidate"]["id"], 100)
        self.assertEqual(wrapper["councilors"][0]["current"]["attributes"]["Administration"], 1)


if __name__ == "__main__":
    unittest.main()
