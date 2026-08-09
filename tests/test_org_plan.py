import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

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


def org(state_id, *, tier, **values):
    return {
        "ID": ref(state_id),
        "displayName": f"Org {state_id}",
        "templateName": values.pop("templateName", f"Org{state_id}"),
        "tier": tier,
        **values,
    }


def eligibility_fixture(*, controlled=False, matching_homeland=False, traits_by_id=None, direct_control_point_nation=False):
    traits_by_id = traits_by_id or {}
    councilor_home_nations = {10: 21 if matching_homeland else 22, 11: 22}
    region_entries = []
    councilor_entries = []
    for councilor_id, nation_id in councilor_home_nations.items():
        region_id = 100 + councilor_id
        region_entries.append(
            {
                "Key": ref(region_id),
                "Value": {"ID": ref(region_id), "nation": ref(nation_id)},
            }
        )
        councilor_entries.append(
            {
                "Key": ref(councilor_id),
                "Value": {
                    "ID": ref(councilor_id),
                    "displayName": f"Councilor {councilor_id}",
                    "homeRegion": ref(region_id),
                    "traitTemplateNames": list(traits_by_id.get(councilor_id, ())),
                    "orgs": [],
                },
            }
        )
    region_entries.append(
        {
            "Key": ref(120),
            "Value": {"ID": ref(120), "nation": ref(21)},
        }
    )
    faction = {
        "ID": ref(1),
        "templateName": "ResistCouncil",
        "displayName": "Resistance",
        "councilors": [ref(10), ref(11)],
        "controlPoints": [ref(31)] if controlled else [],
    }
    gamestates = {
        "TIFactionState": [{"Key": ref(1), "Value": faction}],
        "TICouncilorState": councilor_entries,
        "TIRegionState": region_entries,
        "TINationState": [
            {
                "Key": ref(21),
                "Value": {
                    "ID": ref(21),
                    "templateName": "NationA",
                    "displayName": "Nation A",
                    "controlPoints": [ref(31)],
                },
            },
            {
                "Key": ref(22),
                "Value": {
                    "ID": ref(22),
                    "templateName": "NationB",
                    "displayName": "Nation B",
                    "controlPoints": [],
                },
            },
        ],
        # Deliberately omit the nation field to cover the nation-state fallback.
        "TIControlPointState": [
            {
                "Key": ref(31),
                "Value": {"ID": ref(31), **({"nation": ref(21)} if direct_control_point_nation else {})},
            }
        ],
    }
    indexed = ti.build_index({"gamestates": gamestates})
    profiles = {
        councilor_id: {
            **profile(councilor_id, 3, traits=traits_by_id.get(councilor_id, ())),
            "councilor": ti.state_value_by_id(indexed, councilor_id),
        }
        for councilor_id in (10, 11)
    }
    return indexed, faction, profiles


class OrgPlanTests(unittest.TestCase):
    def test_administration_bonus_can_fund_incoming_org_tier(self):
        orgs = {1: org(1, tier=2, administration=2)}

        action = ti.org_plan_best_assignment(profile(10, 0), orgs, [], 1, "market", {}, "balanced")

        self.assertIsNotNone(action)
        self.assertEqual(action["removedOrgs"], [])
        self.assertEqual(action["tierTotalAfter"], 2)
        self.assertEqual(action["attributesAfter"]["Administration"], 2)
        self.assertEqual(action["freeCapacityAfter"], 0)

    def test_replacement_removes_lowest_value_org(self):
        orgs = {
            1: org(1, tier=1, science=2),
            2: org(2, tier=1),
            3: org(3, tier=1, science=3),
        }
        councilor = profile(10, 2, (1, 2))

        action = ti.org_plan_best_assignment(councilor, orgs, councilor["assignedOrgIds"], 3, "market", {}, "science")

        self.assertIsNotNone(action)
        self.assertEqual([row["id"] for row in action["removedOrgs"]], [2])
        self.assertEqual(action["attributesAfter"]["Science"], 5)

    def test_attribute_focus_preserves_other_stats_when_gain_is_tied(self):
        orgs = {
            1: org(1, tier=1, persuasion=2),
            2: org(2, tier=1),
            3: org(3, tier=1, science=1),
        }
        councilor = profile(10, 2, (1, 2))

        action = ti.org_plan_best_assignment(councilor, orgs, councilor["assignedOrgIds"], 3, "market", {}, "science")

        self.assertEqual([row["id"] for row in action["removedOrgs"]], [2])
        self.assertEqual(action["attributesAfter"]["Persuasion"], 2)

    def test_committee_search_assigns_market_org_once_to_best_councilor(self):
        orgs = {1: org(1, tier=1, science=3)}
        profiles = [
            profile(10, 1),
            {**profile(11, 1), "baseAttributes": {**profile(11, 1)["baseAttributes"], "Science": 24}},
        ]

        plan = ti.search_org_committee_plan(
            profiles,
            orgs,
            market_ids=[1],
            inventory_ids=[],
            resources={},
            focus="science",
            max_actions=2,
            beam_width=2,
        )

        self.assertEqual(len(plan["actions"]), 1)
        self.assertEqual(plan["actions"][0]["councilorId"], 10)
        self.assertEqual(plan["marketAcquisitions"], 1)
        self.assertNotIn(1, plan["remainingMarketOrgIds"])

    def test_committee_search_excludes_unaffordable_market_org(self):
        orgs = {1: org(1, tier=1, science=10, costMoney=100)}

        plan = ti.search_org_committee_plan(
            [profile(10, 1)],
            orgs,
            market_ids=[1],
            inventory_ids=[],
            resources={"Money": 1},
            focus="science",
            max_actions=1,
            beam_width=1,
        )

        self.assertEqual(plan["actions"], [])
        self.assertEqual(plan["remainingMarketOrgIds"], [1])

    def test_committee_search_can_bootstrap_capacity_for_attribute_focus(self):
        orgs = {
            1: org(1, tier=1, administration=2),
            2: org(2, tier=1, science=3),
        }

        plan = ti.search_org_committee_plan(
            [profile(10, 0)],
            orgs,
            market_ids=[1, 2],
            inventory_ids=[],
            resources={},
            focus="science",
            max_actions=2,
            beam_width=2,
        )

        self.assertEqual([action["candidate"]["id"] for action in plan["actions"]], [1, 2])
        self.assertEqual(plan["committeeAttributesAfter"]["Science"], 3)
        self.assertEqual(plan["finalRoster"][0]["freeCapacity"], 0)

    def test_required_owner_trait_is_checked(self):
        orgs = {1: org(1, tier=1, templateName="GovernmentOrg", science=1)}
        templates = {"GovernmentOrg": {"requiredOwnerTraits": ["Government"]}}

        blocked = ti.org_plan_best_assignment(
            profile(10, 1),
            orgs,
            [],
            1,
            "market",
            {},
            "science",
            org_templates=templates,
        )
        eligible = ti.org_plan_best_assignment(
            profile(11, 1, traits=("Government",)),
            orgs,
            [],
            1,
            "market",
            {},
            "science",
            org_templates=templates,
        )

        self.assertIsNone(blocked)
        self.assertIsNotNone(eligible)

    def test_nation_interest_is_satisfied_by_faction_control_not_owner_nationality(self):
        indexed, faction, profiles = eligibility_fixture(controlled=True)
        candidate = org(1, tier=1, templateName="NationalOrg", homeRegion=ref(120))
        templates = {"NationalOrg": {"requiresNationality": True}}

        row = ti.org_plan_candidate_row(indexed, faction, profiles, candidate, "market", templates)

        self.assertTrue(row["factionEligibility"]["eligible"])
        self.assertEqual(row["factionEligibility"]["nationInterest"]["satisfiedBy"], ["controlledNation"])
        self.assertEqual([item["id"] for item in row["eligibleCouncilors"]], [10, 11])
        self.assertEqual(row["ineligibleReasons"], [])

    def test_nation_interest_uses_control_point_direct_nation_reference(self):
        indexed, faction, profiles = eligibility_fixture(controlled=True, direct_control_point_nation=True)
        candidate = org(1, tier=1, templateName="NationalOrg", homeRegion=ref(120))

        row = ti.org_plan_candidate_row(
            indexed,
            faction,
            profiles,
            candidate,
            "market",
            {"NationalOrg": {"requiresNationality": True}},
        )

        self.assertEqual(row["factionEligibility"]["nationInterest"]["satisfiedBy"], ["controlledNation"])

    def test_public_assignment_helper_recovers_faction_from_councilor_roster(self):
        indexed, _faction, profiles = eligibility_fixture(matching_homeland=True)
        candidate = org(1, tier=1, templateName="NationalOrg", homeRegion=ref(120), science=3)

        action = ti.org_plan_best_assignment(
            profiles[11],
            {1: candidate},
            [],
            1,
            "market",
            {},
            "science",
            indexed=indexed,
            org_templates={"NationalOrg": {"requiresNationality": True}},
        )

        self.assertIsNotNone(action)
        self.assertTrue(action["candidate"]["factionEligibility"]["eligible"])

    def test_one_councilor_homeland_satisfies_nation_interest_for_whole_faction(self):
        indexed, faction, profiles = eligibility_fixture(matching_homeland=True)
        candidate = org(1, tier=1, templateName="NationalOrg", homeRegion=ref(120))
        templates = {"NationalOrg": {"requiresNationality": True}}

        row = ti.org_plan_candidate_row(indexed, faction, profiles, candidate, "market", templates)

        self.assertEqual(row["factionEligibility"]["nationInterest"]["satisfiedBy"], ["councilorHomeNation"])
        self.assertEqual([item["id"] for item in row["eligibleCouncilors"]], [10, 11])

    def test_missing_nation_interest_is_explicit_for_every_councilor(self):
        indexed, faction, profiles = eligibility_fixture()
        candidate = org(1, tier=1, templateName="NationalOrg", homeRegion=ref(120))
        templates = {"NationalOrg": {"requiresNationality": True}}

        row = ti.org_plan_candidate_row(indexed, faction, profiles, candidate, "market", templates)

        reason = "faction lacks interest in required nation: Nation A"
        self.assertFalse(row["factionEligibility"]["eligible"])
        self.assertEqual(row["factionEligibility"]["reasons"], [reason])
        self.assertEqual(row["eligibleCouncilors"], [])
        self.assertEqual([item["reasons"] for item in row["ineligibleReasons"]], [[reason], [reason]])

    def test_unresolved_required_home_nation_is_reported(self):
        indexed, faction, profiles = eligibility_fixture(controlled=True)
        candidate = org(1, tier=1, templateName="NationalOrg", homeRegion=ref(999))

        row = ti.org_plan_candidate_row(
            indexed,
            faction,
            profiles,
            candidate,
            "market",
            {"NationalOrg": {"requiresNationality": True}},
        )

        self.assertFalse(row["factionEligibility"]["eligible"])
        self.assertEqual(
            row["factionEligibility"]["reasons"],
            ["nation interest requirement could not be resolved"],
        )

    def test_candidate_row_exposes_owner_trait_requirements_and_reasons(self):
        indexed, faction, profiles = eligibility_fixture(
            controlled=True,
            traits_by_id={10: ("Government",), 11: ("Criminal",)},
        )
        candidate = org(1, tier=1, templateName="GovernmentOrg", homeRegion=ref(120))
        templates = {
            "GovernmentOrg": {
                "requiresNationality": True,
                "requiredOwnerTraits": ["Government"],
                "prohibitedOwnerTraits": ["Criminal"],
            }
        }

        row = ti.org_plan_candidate_row(indexed, faction, profiles, candidate, "market", templates)

        self.assertEqual(
            row["requirements"],
            {
                "requiresNationInterest": True,
                "homeNation": {
                    "id": 21,
                    "type": "TINationState",
                    "template": "NationA",
                    "code": "NationA",
                    "display": "Nation A",
                },
                "requiredOwnerTraits": ["Government"],
                "prohibitedOwnerTraits": ["Criminal"],
            },
        )
        self.assertEqual(row["eligibleCouncilors"], [{"id": 10, "display": "Councilor 10"}])
        self.assertEqual(row["ineligibleReasons"][0]["id"], 11)
        self.assertEqual(
            row["ineligibleReasons"][0]["reasons"],
            ["missing required owner traits: Government", "prohibited owner traits: Criminal"],
        )

    def test_committee_search_uses_faction_wide_councilor_homeland_interest(self):
        indexed, faction, profiles = eligibility_fixture(matching_homeland=True)
        profiles[10]["baseAttributes"]["Science"] = 24
        candidate = org(1, tier=1, templateName="NationalOrg", homeRegion=ref(120), science=3)

        plan = ti.search_org_committee_plan(
            profiles,
            {1: candidate},
            market_ids=[1],
            inventory_ids=[],
            resources={},
            focus="science",
            max_actions=1,
            beam_width=2,
            indexed=indexed,
            org_templates={"NationalOrg": {"requiresNationality": True}},
            faction=faction,
        )

        self.assertEqual(len(plan["actions"]), 1)
        self.assertEqual(plan["actions"][0]["councilorId"], 11)
        self.assertTrue(plan["actions"][0]["candidate"]["requirements"]["requiresNationInterest"])
        self.assertTrue(plan["actions"][0]["candidate"]["factionEligibility"]["eligible"])

    def test_committee_search_keeps_org_when_faction_lacks_nation_interest(self):
        indexed, faction, profiles = eligibility_fixture()
        candidate = org(1, tier=1, templateName="NationalOrg", homeRegion=ref(120), science=3)

        plan = ti.search_org_committee_plan(
            profiles,
            {1: candidate},
            market_ids=[1],
            inventory_ids=[],
            resources={},
            focus="science",
            max_actions=1,
            beam_width=2,
            indexed=indexed,
            org_templates={"NationalOrg": {"requiresNationality": True}},
            faction=faction,
        )

        self.assertEqual(plan["actions"], [])
        self.assertEqual(plan["remainingMarketOrgIds"], [1])


if __name__ == "__main__":
    unittest.main()
