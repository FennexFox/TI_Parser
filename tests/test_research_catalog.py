import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import build_research_catalog as rc


class ResearchCatalogTests(unittest.TestCase):
    def test_alt_prereq_is_or_alternative_for_first_prereq(self):
        requirement = rc.normalize_requirements(
            {
                "dataName": "Project_Test",
                "prereqs": ["Project_PlatformCore", "AdvancedNeuralNetworks", "ArrivalDomesticPolitics"],
                "altPrereq0": "Project_OutpostCore",
            }
        )

        self.assertEqual(
            requirement,
            {
                "all": [
                    {
                        "any": [
                            {"node": "Project_PlatformCore", "kind": "project"},
                            {"node": "Project_OutpostCore", "kind": "project"},
                        ]
                    },
                    {"node": "AdvancedNeuralNetworks", "kind": "tech"},
                    {"node": "ArrivalDomesticPolitics", "kind": "tech"},
                ]
            },
        )

        self.assertFalse(
            rc.requirement_satisfied(
                requirement,
                {"Project_OutpostCore", "AdvancedNeuralNetworks"},
            )
        )
        self.assertTrue(
            rc.requirement_satisfied(
                requirement,
                {"Project_OutpostCore", "AdvancedNeuralNetworks", "ArrivalDomesticPolitics"},
            )
        )

    def test_objective_faction_milestone_and_nation_gates_are_contextual(self):
        requirement = rc.normalize_requirements(
            {
                "dataName": "Project_Contextual",
                "requiredObjectiveName": "SalvageAlienWarship",
                "altRequiredObjectiveName": "ContactTheAliens",
                "requiredMilestone": "AccessAlienTech",
                "factionPrereq": ["ResistCouncil", "DestroyCouncil"],
                "requiresNation": "GBR",
            }
        )

        self.assertFalse(rc.requirement_satisfied(requirement, set()))
        self.assertTrue(
            rc.requirement_satisfied(
                requirement,
                set(),
                {
                    "completedObjectives": {"ContactTheAliens"},
                    "completedMilestones": {"AccessAlienTech"},
                    "factionTemplate": "ResistCouncil",
                    "availableNations": {"GBR"},
                },
            )
        )

    def test_graph_links_include_node_edges_but_not_state_gates(self):
        nodes = [
            {
                "dataName": "A",
                "requirements": {"all": []},
                "prerequisiteNodes": [],
            },
            {
                "dataName": "B",
                "requirements": {
                    "all": [
                        {"node": "A", "kind": "tech"},
                        {"objective": "InvestigateAlienCrashdown"},
                    ]
                },
                "prerequisiteNodes": ["A"],
            },
        ]

        edges, children, unknown = rc.build_graph_links(nodes)

        self.assertEqual(edges, [{"from": "A", "to": "B"}])
        self.assertEqual(children, {"A": ["B"]})
        self.assertEqual(unknown, [])

    def test_unmet_requirements_preserve_any_groups(self):
        requirement = rc.normalize_requirements(
            {
                "dataName": "Project_Exotics",
                "prereqs": ["Project_TheirTechnology"],
                "altPrereq0": "Project_HydraDiplomacy",
                "requiredObjectiveName": "SalvageAlienWarship",
                "altRequiredObjectiveName": "ContactTheAliens",
            }
        )

        missing = rc.unmet_requirements(requirement, set())

        self.assertEqual(
            missing,
            [
                {
                    "any": [
                        {"node": "Project_TheirTechnology", "kind": "project"},
                        {"node": "Project_HydraDiplomacy", "kind": "project"},
                    ]
                },
                {
                    "any": [
                        {"objective": "SalvageAlienWarship"},
                        {"objective": "ContactTheAliens"},
                    ]
                },
            ],
        )

    def test_strict_runtime_lookup_rejects_missing_and_corrupt_rows(self):
        base = {
            "techs": {
                "Tech_A": {
                    "dataName": "Tech_A",
                    "kind": "tech",
                    "techCategory": "Energy",
                    "researchCost": 100,
                    "requirements": {"all": []},
                    "prerequisiteNodes": [],
                    "effects": [],
                }
            },
            "projects": {},
        }
        payload = {"base": base, "scenarioOverrides": {}}
        catalog = {
            "supportedScenarios": ["ModernScenario"],
            **payload,
            "payloadFingerprint": rc.value_fingerprint(payload),
        }

        self.assertEqual(
            rc.require_runtime_row(catalog, "ModernScenario", "tech", "Tech_A")["researchCost"],
            100,
        )
        with self.assertRaisesRegex(rc.ResearchCatalogError, "Missing required tech row"):
            rc.require_runtime_row(catalog, "ModernScenario", "tech", "Missing")

        catalog["base"]["techs"]["Tech_A"].pop("researchCost")
        catalog["payloadFingerprint"] = rc.value_fingerprint(
            {"base": catalog["base"], "scenarioOverrides": catalog["scenarioOverrides"]}
        )
        with self.assertRaisesRegex(rc.ResearchCatalogError, "missing.*researchCost"):
            rc.select_runtime_payload(catalog, "ModernScenario")

    def test_packaged_v2_catalog_runtime_indexes_are_self_consistent(self):
        catalog_path = Path(__file__).resolve().parents[1] / "data" / "research_catalog.json"
        if not catalog_path.is_file():
            self.skipTest("packaged research catalog is absent")
        import json

        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        self.assertEqual(catalog.get("schemaVersion"), 2)
        for scenario in catalog["supportedScenarios"]:
            payload = rc.select_runtime_payload(catalog, scenario)
            self.assertTrue(payload["techs"])
            self.assertTrue(payload["projects"])


if __name__ == "__main__":
    unittest.main()
