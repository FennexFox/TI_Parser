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


if __name__ == "__main__":
    unittest.main()
