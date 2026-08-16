import sys
import unittest
from pathlib import Path
from unittest.mock import patch


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
                            "controlPoints": [ref(30)],
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
                            "homeRegion": ref(21),
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
                            "homeRegion": ref(20),
                        },
                    )
                ],
                "TIRegionState": [
                    save_state(20, {"nation": ref(40)}),
                    save_state(21, {"nation": ref(41)}),
                ],
                "TINationState": [
                    save_state(40, {"templateName": "NationA", "controlPoints": [ref(30)]}),
                    save_state(41, {"templateName": "NationB", "controlPoints": []}),
                ],
                "TIControlPointState": [save_state(30, {"nation": ref(40)})],
            }
        }
        indexed = ti.build_index(data)

        with patch.object(
            org,
            "load_named_templates",
            return_value={"Org100": {"requiresNationality": True}},
        ):
            wrapper = ti.calculate_org_plan(indexed, None, "ResistCouncil")
            direct = org.calculate_org_plan(indexed, None, "ResistCouncil")

        self.assertEqual(wrapper, direct)
        self.assertEqual(wrapper["committeePlan"]["actions"][0]["candidate"]["id"], 100)
        self.assertEqual(wrapper["councilors"][0]["current"]["attributes"]["Administration"], 1)
        candidate = wrapper["candidateSources"]["market"]["orgs"][0]
        self.assertEqual(candidate["requirements"]["requiredOwnerTraits"], [])
        self.assertTrue(candidate["requirements"]["requiresNationInterest"])
        self.assertEqual(candidate["factionEligibility"]["nationInterest"]["satisfiedBy"], ["controlledNation"])
        self.assertEqual(candidate["eligibleCouncilors"], [{"id": 10, "display": "Councilor 10"}])
        self.assertEqual(candidate["ineligibleReasons"], [])
        self.assertEqual(candidate["orgCountCapacity"]["maxOrgCount"], 15)
        self.assertEqual(candidate["orgCountCapacity"]["councilors"][0]["currentOrgCount"], 0)
        self.assertEqual(wrapper["committeePlan"]["finalRoster"][0]["maxOrgCount"], 15)

    def test_random_criminal_candidate_is_filtered_by_actual_eligible_councilors(self):
        data = {
            "gamestates": {
                "TIFactionState": [
                    save_state(
                        1,
                        {
                            "templateName": "CooperateCouncil",
                            "displayName": "Academy",
                            "councilors": [ref(10), ref(11)],
                            "controlPoints": [],
                            "availableOrgs": [ref(100), ref(101), ref(102)],
                            "unassignedOrgs": [],
                            "resources": {},
                        },
                    )
                ],
                "TICouncilorState": [
                    save_state(
                        councilor_id,
                        {
                            "templateName": f"Councilor{councilor_id}",
                            "displayName": f"Councilor {councilor_id}",
                            "traitTemplateNames": [],
                            "conditionalTraitMods": [],
                            "orgs": [],
                            "attributes": {
                                **{attribute: 0 for attribute in ti.COUNCILOR_ATTRIBUTES},
                                "Administration": 3,
                            },
                        },
                    )
                    for councilor_id in (10, 11)
                ],
                "TIOrgState": [
                    save_state(
                        100,
                        {
                            "templateName": "RandomCriminal13",
                            "displayName": "High Stat Criminal Org",
                            "tier": 1,
                            "science": 10,
                        },
                    ),
                    save_state(
                        101,
                        {
                            "templateName": "OpenOrg",
                            "displayName": "Open Org",
                            "tier": 1,
                            "science": 2,
                        },
                    ),
                    save_state(
                        102,
                        {
                            "templateName": "RestrictedOrg",
                            "displayName": "Faction Restricted Org",
                            "tier": 1,
                            "science": 20,
                        },
                    ),
                ],
            }
        }
        indexed = ti.build_index(data)
        templates = {
            "RandomCriminal13": {"requiredOwnerTraits": ["Criminal"]},
            "OpenOrg": {},
            "RestrictedOrg": {"restricted": ["Cooperate"]},
        }

        with patch.object(org, "load_named_templates", return_value=templates):
            plan = org.calculate_org_plan(indexed, None, "CooperateCouncil", focus="science", max_actions=1)

        candidates = {
            row["template"]: row
            for row in plan["candidateSources"]["market"]["orgs"]
        }
        criminal = candidates["RandomCriminal13"]
        self.assertEqual(criminal["requirements"]["requiredOwnerTraits"], ["Criminal"])
        self.assertEqual(criminal["eligibleCouncilors"], [])
        self.assertFalse(criminal["recommendationEligibility"]["eligible"])
        self.assertEqual(criminal["recommendationEligibility"]["basis"], "eligibleCouncilors")
        restricted = candidates["RestrictedOrg"]
        self.assertEqual(restricted["eligibleCouncilors"], [])
        self.assertEqual(
            restricted["factionEligibility"]["reasons"],
            ["faction ideology is restricted: Cooperate"],
        )
        self.assertFalse(restricted["recommendationEligibility"]["eligible"])
        self.assertEqual(plan["candidateSources"]["market"]["recommendationEligibleOrgIds"], [101])

        recommended_ids = {
            action["candidate"]["id"]
            for councilor in plan["councilors"]
            for actions in councilor["goalViews"].values()
            for action in actions
        }
        recommended_ids.update(
            action["candidate"]["id"]
            for action in plan["committeePlan"]["actions"]
        )
        self.assertNotIn(100, recommended_ids)
        self.assertNotIn(102, recommended_ids)
        self.assertEqual([action["candidate"]["id"] for action in plan["committeePlan"]["actions"]], [101])

    def test_candidate_sources_deduplicate_with_owned_inventory_precedence(self):
        data = {
            "gamestates": {
                "TIFactionState": [
                    save_state(
                        1,
                        {
                            "templateName": "ResistCouncil",
                            "displayName": "Resistance",
                            "councilors": [ref(10)],
                            "controlPoints": [],
                            "availableOrgs": [ref(100), ref(100)],
                            "unassignedOrgs": [ref(100), ref(100)],
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

        with patch.object(org, "load_named_templates", return_value={"Org100": {}}):
            plan = org.calculate_org_plan(indexed, None, "ResistCouncil", focus="science", max_actions=1)
            market_only_plan = org.calculate_org_plan(
                indexed,
                None,
                "ResistCouncil",
                focus="science",
                max_actions=1,
                include_unassigned=False,
            )

        self.assertEqual(plan["candidateSources"]["market"]["count"], 0)
        self.assertEqual(plan["candidateSources"]["ownedInventory"]["count"], 1)
        self.assertEqual(plan["candidateSources"]["normalization"]["overlappingOrgIds"], [100])
        self.assertEqual(plan["committeePlan"]["actions"][0]["source"], "ownedInventory")
        self.assertEqual(plan["committeePlan"]["marketAcquisitions"], 0)
        self.assertEqual(market_only_plan["candidateSources"]["market"]["count"], 0)
        self.assertEqual(market_only_plan["candidateSources"]["ownedInventory"]["count"], 0)
        self.assertEqual(
            market_only_plan["candidateSources"]["normalization"]["overlappingOrgIds"],
            [100],
        )

    def test_calculate_org_plan_fails_closed_without_org_templates(self):
        indexed = ti.build_index(
            {
                "gamestates": {
                    "TIFactionState": [
                        save_state(
                            1,
                            {
                                "templateName": "ResistCouncil",
                                "displayName": "Resistance",
                                "councilors": [],
                                "availableOrgs": [],
                                "unassignedOrgs": [],
                            },
                        )
                    ]
                }
            }
        )

        with patch.object(org, "load_named_templates", return_value={}):
            with self.assertRaisesRegex(FileNotFoundError, "eligibility cannot be evaluated safely"):
                org.calculate_org_plan(indexed, None)


if __name__ == "__main__":
    unittest.main()
