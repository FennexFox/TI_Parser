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


class ResearchPlanTests(unittest.TestCase):
    def test_available_global_research_excludes_finished_active_and_locked(self):
        gamestates = {}
        add_state(
            gamestates,
            "TIGlobalResearchState",
            1,
            {
                "finishedTechsNames": ["Root", "Done"],
                "techProgress": [{"techTemplateName": "Active", "accumulatedResearch": 0.0}],
            },
        )
        indexed = ti.build_index({"gamestates": gamestates})
        tech_templates = {
            "Free": {"dataName": "Free", "researchCost": 50},
            "Next": {"dataName": "Next", "researchCost": 100, "prereqs": ["Root"]},
            "Locked": {"dataName": "Locked", "researchCost": 100, "prereqs": ["Missing"]},
            "Done": {"dataName": "Done", "researchCost": 100},
            "Active": {"dataName": "Active", "researchCost": 100},
            "Invalid": {"dataName": "Invalid", "researchCost": 0},
        }

        names = [name for name, _ in ti.available_global_research_templates(indexed, tech_templates)]

        self.assertEqual(names, ["Free", "Next"])

    def test_available_projects_exclude_active_slots_but_keep_paused_progress(self):
        faction = {
            "availableProjectNames": ["Project_Paused", "Project_Active", "Project_New"],
            "currentProjectProgress": [
                {"projectTemplateName": "Project_Active", "slot": 3, "accumulatedResearch": 10.0},
                {"projectTemplateName": "Project_Paused", "slot": 6, "accumulatedResearch": 40.0},
            ],
            "researchWeights": [3, 3, 3, 2, 2, 2],
            "orgProjectSlotUnlocked": True,
            "habProjectSlotUnlocked": True,
        }
        project_templates = {
            "Project_Paused": {"dataName": "Project_Paused", "researchCost": 100},
            "Project_Active": {"dataName": "Project_Active", "researchCost": 100},
            "Project_New": {"dataName": "Project_New", "researchCost": 200},
        }

        names = [name for name, _ in ti.available_project_research_templates(faction, project_templates)]
        progress = ti.project_progress_records_by_template(faction)

        self.assertEqual(names, ["Project_Paused", "Project_New"])
        self.assertEqual(progress["Project_Paused"]["accumulatedResearch"], 40.0)

    def test_direct_unlocks_count_normal_prereqs_and_alt_prereqs(self):
        tech_templates = {
            "ChildTech": {"dataName": "ChildTech", "friendlyName": "Child Tech", "prereqs": ["Parent"]},
        }
        project_templates = {
            "ChildProject": {"dataName": "ChildProject", "friendlyName": "Child Project", "prereqs": ["Parent"]},
            "AltChild": {"dataName": "AltChild", "friendlyName": "Alt Child", "altPrereq0": "Parent"},
        }

        unlocks = ti.direct_unlocks_for_template("Parent", tech_templates, project_templates)

        self.assertEqual(unlocks["count"], 3)
        self.assertEqual([row["template"] for row in unlocks["globalTechs"]], ["ChildTech"])
        self.assertEqual({row["template"] for row in unlocks["projects"]}, {"ChildProject", "AltChild"})

    def test_research_plan_scores_are_normalized_per_objective_axis(self):
        candidates = [
            {
                "scoreEvidence": {
                    "estimatedDaysAtReferenceWeight": 10.0,
                    "categoryEffectiveMultiplier": 2.0,
                    "directUnlockCount": 4,
                    "aiCriticalTech": True,
                    "deficientResourceTypesCovered": 1,
                    "progressFraction": 0.25,
                }
            },
            {
                "scoreEvidence": {
                    "estimatedDaysAtReferenceWeight": 20.0,
                    "categoryEffectiveMultiplier": 1.0,
                    "directUnlockCount": 2,
                    "aiCriticalTech": False,
                    "deficientResourceTypesCovered": 0,
                    "progressFraction": 0.5,
                }
            },
        ]

        ti.score_research_plan_candidates(candidates)

        self.assertEqual(candidates[0]["objectiveScores"]["fastCompletion"], 100.0)
        self.assertEqual(candidates[1]["objectiveScores"]["fastCompletion"], 50.0)
        self.assertEqual(candidates[0]["objectiveScores"]["factionSynergy"], 100.0)
        self.assertEqual(candidates[1]["objectiveScores"]["factionSynergy"], 50.0)
        self.assertEqual(candidates[0]["objectiveScores"]["unlockBreadth"], 100.0)
        self.assertEqual(candidates[1]["objectiveScores"]["unlockBreadth"], 50.0)
        self.assertEqual(candidates[0]["objectiveScores"]["criticalTemplate"], 100.0)
        self.assertEqual(candidates[1]["objectiveScores"]["criticalTemplate"], 0.0)
        self.assertEqual(candidates[0]["objectiveScores"]["resourceReliefCoverage"], 100.0)
        self.assertEqual(candidates[1]["objectiveScores"]["currentProgress"], 50.0)


if __name__ == "__main__":
    unittest.main()
