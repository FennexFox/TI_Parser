import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import ti_save_parser as ti


def ref(state_id):
    return {"value": state_id}


def add_state(gamestates, type_name, state_id, value):
    value = dict(value)
    value.setdefault("ID", ref(state_id))
    gamestates.setdefault(type_name, []).append({"Key": ref(state_id), "Value": value})
    return value


class HabPlanTests(unittest.TestCase):
    def test_research_projects_and_category_scores_are_separate(self):
        monthly_delta = {
            "Research": {"income": 10.0, "support": 0.0, "net": 10.0},
            "Projects": {"income": 1.0, "support": 0.0, "net": 1.0},
        }
        template = {"techBonuses": [{"category": "SpaceScience", "bonus": 0.1}]}

        self.assertEqual(ti.module_research_score(monthly_delta), 10.0)
        self.assertEqual(ti.module_project_score(monthly_delta), 1.0)
        self.assertAlmostEqual(ti.module_category_bonus_score(template), 0.1)

    def test_upgrade_to_higher_tier_counts_locked_empty_as_planned_slots(self):
        records = [
            {
                "templateName": "RingCore",
                "template": {"dataName": "RingCore", "coreModule": True, "tier": 3},
                "priorTemplateName": "OrbitalCore",
                "priorTemplate": {"dataName": "OrbitalCore", "coreModule": True, "tier": 2},
                "completed": False,
                "state": {"completionDate": "2035-10-19T01:46:38.1630000"},
            }
        ]

        upgrade = ti.hab_upgrade_info(records)
        planned = ti.hab_planned_empty_slots(
            {"raw": 21, "usable": 13, "occupied": 13, "empty": 0, "locked": 8, "lockedEmpty": 8},
            upgrade,
            current_tier=2,
        )

        self.assertTrue(upgrade["isUpgrading"])
        self.assertEqual(upgrade["targetTier"], 3)
        self.assertEqual(planned["currentUsableEmpty"], 0)
        self.assertEqual(planned["futureUnlockedEmpty"], 8)
        self.assertEqual(planned["plannedEmpty"], 8)

    def test_suggested_fill_aggregates_focus_and_power_modules(self):
        candidates = [
            {
                "template": "ResearchLab",
                "display": "Research Lab",
                "tier": 2,
                "power": -30,
                "missionControl": 0,
                "onePerHab": False,
                "affordableByTemplateWeights": True,
                "fitsCurrentProjectedPower": False,
                "scores": {"research": 10.0, "resources": -1.0, "balanced": 9.0},
                "monthlyDelta": {"Research": {"income": 10.0, "support": 0.0, "net": 10.0}},
            },
            {
                "template": "Reactor",
                "display": "Reactor",
                "tier": 2,
                "power": 120,
                "missionControl": 0,
                "onePerHab": False,
                "affordableByTemplateWeights": True,
                "fitsCurrentProjectedPower": True,
                "scores": {"research": 0.0, "resources": -2.0, "balanced": -2.0},
                "monthlyDelta": {"Water": {"income": 0.0, "support": 1.0, "net": -1.0}},
            },
            {
                "template": "SkunkWorks",
                "display": "Skunk Works",
                "tier": 2,
                "power": 0,
                "missionControl": 0,
                "onePerHab": False,
                "affordableByTemplateWeights": True,
                "fitsCurrentProjectedPower": True,
                "scores": {"research": 0.0, "projects": 1.0, "category-bonus": 0.0, "resources": 0.0, "balanced": 0.0},
                "monthlyDelta": {"Projects": {"income": 1.0, "support": 0.0, "net": 1.0}},
            },
        ]

        fill = ti.suggested_hab_fill(candidates, slots=5, focus="research", projected_power=0, mc_available=0)

        self.assertEqual(fill["slotsFilled"], 5)
        self.assertEqual(fill["projectedPowerNetAfter"], 0)
        self.assertEqual(fill["moduleCounts"][0]["template"], "ResearchLab")
        self.assertEqual(fill["moduleCounts"][0]["count"], 4)
        self.assertEqual(fill["moduleCounts"][1]["template"], "Reactor")
        self.assertEqual(fill["moduleCounts"][1]["count"], 1)
        self.assertEqual(fill["monthlyDeltaTotal"]["Research"]["net"], 40.0)
        self.assertNotIn("Projects", fill["monthlyDeltaTotal"])
        self.assertEqual(fill["score"]["gross"], 40.0)
        self.assertEqual(fill["score"]["opportunityCost"], 10.0)
        self.assertEqual(fill["score"]["unfilledSlotOpportunityCost"], 0.0)
        self.assertEqual(fill["score"]["totalOpportunityCostIncludingUnfilledSlots"], 10.0)
        self.assertEqual(fill["score"]["afterOpportunityCost"], 30.0)
        self.assertEqual(fill["score"]["afterOpportunityCostIncludingUnfilledSlots"], 30.0)
        self.assertEqual(fill["score"]["bestAlternativePerSlot"]["template"], "ResearchLab")
        self.assertEqual(fill["moduleCounts"][0]["opportunityCost"]["costTotal"], 0.0)
        self.assertEqual(fill["moduleCounts"][1]["opportunityCost"]["costTotal"], 10.0)

    def test_candidate_opportunity_costs_compare_against_best_affordable_slot_alternative(self):
        candidates = [
            {
                "template": "ResearchLab",
                "display": "Research Lab",
                "tier": 2,
                "affordableByTemplateWeights": True,
                "scores": {"research": 10.0, "projects": 0.0, "category-bonus": 0.0, "resources": -1.0, "balanced": 9.0},
            },
            {
                "template": "Reactor",
                "display": "Reactor",
                "tier": 2,
                "affordableByTemplateWeights": True,
                "scores": {"research": 0.0, "projects": 0.0, "category-bonus": 0.0, "resources": -2.0, "balanced": -2.0},
            },
        ]

        ti.annotate_candidate_opportunity_costs(candidates)

        self.assertEqual(candidates[0]["opportunityCosts"]["research"]["cost"], 0.0)
        self.assertEqual(candidates[1]["opportunityCosts"]["research"]["bestAlternative"]["template"], "ResearchLab")
        self.assertEqual(candidates[1]["opportunityCosts"]["research"]["cost"], 10.0)
        self.assertEqual(candidates[1]["opportunityCosts"]["research"]["scoreAfterOpportunityCost"], -10.0)

    def test_suggested_fill_reports_unfilled_slot_opportunity_separately(self):
        candidates = [
            {
                "template": "UniqueLab",
                "display": "Unique Lab",
                "tier": 2,
                "power": 0,
                "missionControl": 0,
                "onePerHab": True,
                "affordableByTemplateWeights": True,
                "fitsCurrentProjectedPower": True,
                "scores": {"research": 10.0, "resources": 0.0, "balanced": 10.0},
                "monthlyDelta": {"Research": {"income": 10.0, "support": 0.0, "net": 10.0}},
            },
        ]

        fill = ti.suggested_hab_fill(candidates, slots=2, focus="research", projected_power=0, mc_available=0)

        self.assertEqual(fill["slotsFilled"], 1)
        self.assertEqual(fill["unfilledSlots"], 1)
        self.assertEqual(fill["score"]["opportunityCost"], 0.0)
        self.assertEqual(fill["score"]["unfilledSlotOpportunityCost"], 10.0)
        self.assertEqual(fill["score"]["afterOpportunityCostIncludingUnfilledSlots"], 0.0)

    def test_projects_focus_is_explicitly_separate_from_research_focus(self):
        candidates = [
            {
                "template": "ResearchCampus",
                "display": "Research Campus",
                "tier": 2,
                "power": 0,
                "missionControl": 0,
                "onePerHab": False,
                "affordableByTemplateWeights": True,
                "fitsCurrentProjectedPower": True,
                "scores": {"research": 60.0, "projects": 0.0, "category-bonus": 0.0, "resources": 0.0, "balanced": 60.0},
                "monthlyDelta": {"Research": {"income": 60.0, "support": 0.0, "net": 60.0}},
            },
            {
                "template": "SkunkWorks",
                "display": "Skunk Works",
                "tier": 2,
                "power": 0,
                "missionControl": 0,
                "onePerHab": False,
                "affordableByTemplateWeights": True,
                "fitsCurrentProjectedPower": True,
                "scores": {"research": 0.0, "projects": 1.0, "category-bonus": 0.0, "resources": 0.0, "balanced": 0.0},
                "monthlyDelta": {"Projects": {"income": 1.0, "support": 0.0, "net": 1.0}},
            },
        ]

        research_fill = ti.suggested_hab_fill(candidates, slots=1, focus="research", projected_power=0, mc_available=0)
        projects_fill = ti.suggested_hab_fill(candidates, slots=1, focus="projects", projected_power=0, mc_available=0)

        self.assertEqual(research_fill["moduleCounts"][0]["template"], "ResearchCampus")
        self.assertEqual(projects_fill["moduleCounts"][0]["template"], "SkunkWorks")

    def test_suggested_fill_excludes_unaffordable_power_support(self):
        candidates = [
            {
                "template": "ResearchLab",
                "display": "Research Lab",
                "tier": 2,
                "power": -30,
                "missionControl": 0,
                "onePerHab": False,
                "affordableByTemplateWeights": True,
                "fitsCurrentProjectedPower": False,
                "scores": {"research": 10.0, "resources": -1.0, "balanced": 9.0},
                "monthlyDelta": {"Research": {"income": 10.0, "support": 0.0, "net": 10.0}},
            },
            {
                "template": "UnpayableReactor",
                "display": "Unpayable Reactor",
                "tier": 3,
                "power": 500,
                "missionControl": 0,
                "onePerHab": False,
                "affordableByTemplateWeights": False,
                "fitsCurrentProjectedPower": True,
                "scores": {"research": 0.0, "resources": -1.0, "balanced": -1.0},
                "monthlyDelta": {},
            },
            {
                "template": "SmallReactor",
                "display": "Small Reactor",
                "tier": 1,
                "power": 60,
                "missionControl": 0,
                "onePerHab": False,
                "affordableByTemplateWeights": True,
                "fitsCurrentProjectedPower": True,
                "scores": {"research": 0.0, "resources": -2.0, "balanced": -2.0},
                "monthlyDelta": {},
            },
        ]

        fill = ti.suggested_hab_fill(candidates, slots=3, focus="research", projected_power=0, mc_available=0)

        templates = {row["template"] for row in fill["moduleCounts"]}
        self.assertNotIn("UnpayableReactor", templates)
        self.assertIn("SmallReactor", templates)

    def test_gas_giant_requirement_resolves_hab_barycenter_ref(self):
        gamestates = {}
        add_state(gamestates, "TISpaceBodyState", 10, {"templateName": "Earth"})
        add_state(gamestates, "TISpaceBodyState", 11, {"templateName": "Jupiter"})
        indexed = ti.build_index({"gamestates": gamestates})
        template = {"dataName": "Harvester", "specialRules": ["Requires_GasGiant_Orbit"], "tier": 2}
        faction = {"finishedProjectNames": []}

        earth_reasons = ti.module_unmet_requirements(indexed, template, {"barycenter": ref(10), "habType": "Station"}, faction, 3, {})
        jupiter_reasons = ti.module_unmet_requirements(indexed, template, {"barycenter": ref(11), "habType": "Station"}, faction, 3, {})

        self.assertIn("requires gas giant orbit", earth_reasons)
        self.assertNotIn("requires gas giant orbit", jupiter_reasons)

    def test_earth_counts_as_colonized_body_for_orbital_modules(self):
        gamestates = {}
        add_state(gamestates, "TISpaceBodyState", 10, {"templateName": "Earth", "habSites": []})
        indexed = ti.build_index({"gamestates": gamestates})
        template = {"dataName": "ResearchCampus", "specialRules": ["Requires_Colonized_Body"], "tier": 2}
        faction = {"finishedProjectNames": []}

        reasons = ti.module_unmet_requirements(indexed, template, {"barycenter": ref(10), "habType": "Station"}, faction, 3, {})

        self.assertNotIn("requires colonized body", reasons)

    def test_planner_filters_combat_objective_only_and_irradiated_rules(self):
        gamestates = {}
        add_state(gamestates, "TISpaceBodyState", 10, {"templateName": "Mercury", "irradiatedMultiplier": 2.0})
        indexed = ti.build_index({"gamestates": gamestates})
        faction = {"finishedProjectNames": []}
        hab = {"barycenter": ref(10), "habType": "Station"}

        combat_reasons = ti.module_unmet_requirements(
            indexed,
            {"dataName": "Defense", "spaceCombatModule": True, "tier": 2},
            hab,
            faction,
            3,
            {},
        )
        objective_reasons = ti.module_unmet_requirements(
            indexed,
            {"dataName": "PlotDevice", "objectiveModule": True, "tier": 3, "power": -100},
            hab,
            faction,
            3,
            {},
        )
        hospital_reasons = ti.module_unmet_requirements(
            indexed,
            {"dataName": "Hospital", "specialRules": ["NotInIrradiated"], "tier": 2},
            hab,
            faction,
            3,
            {},
        )

        self.assertIn("combat module outside economic planner", combat_reasons)
        self.assertIn("objective-only module outside economic planner", objective_reasons)
        self.assertIn("not buildable on irradiated body", hospital_reasons)


if __name__ == "__main__":
    unittest.main()
