import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import ti_parser_claims as claims
import ti_parser_core as core


class NationClaimsTests(unittest.TestCase):
    def _build_indexed(self) -> core.IndexedState:
        nations = [
            self._nation(1, "CLA", 5.0, [101, 102, 103, 104], [102]),
            self._nation(2, "LOW", 6.0, [101, 102]),
            self._nation(3, "HIGH", 8.0, [103]),
            self._nation(4, "EDGE", 7.0, [104]),
        ]
        regions = [
            self._region(101, "LowPeace", 2),
            self._region(102, "LowStatic", 2),
            self._region(103, "HighConditional", 3),
            self._region(104, "BoundaryPeace", 4),
        ]
        return core.build_index(
            {
                "gamestates": {
                    "TITimeState": [
                        {
                            "Key": {"value": 10},
                            "Value": {
                                "ID": {"value": 10},
                                "scenarioMetaTemplateName": "StandardScenario",
                            },
                        }
                    ],
                    "TINationState": nations,
                    "TIRegionState": regions,
                }
            }
        )

    @staticmethod
    def _nation(
        state_id: int,
        name: str,
        democracy: float,
        claims: list[int] | None = None,
        hostile_claims: list[int] | None = None,
    ) -> dict:
        return {
            "Key": {"value": state_id},
            "Value": {
                "ID": {"value": state_id},
                "templateName": name,
                "displayName": name.title(),
                "democracy": democracy,
                "claims": [{"value": value} for value in claims or []],
                "hostileClaims": [{"value": value} for value in hostile_claims or []],
            },
        }

    @staticmethod
    def _region(state_id: int, name: str, owner_id: int) -> dict:
        return {
            "Key": {"value": state_id},
            "Value": {
                "ID": {"value": state_id},
                "templateName": name,
                "displayName": name,
                "nation": {"value": owner_id},
            },
        }

    @staticmethod
    def _catalog() -> dict:
        return {
            "schemaVersion": 1,
            "payloadFingerprint": "synthetic",
            "sourceFiles": [{"name": "Assembly-CSharp.dll", "sha256": "test"}],
            "base": {
                "rules": {
                    "democracyDecreaseToMakeHostileClaim": 2.0,
                },
                "claims": [
                    {
                        "claimant": "CLA",
                        "region": "LowStatic",
                        "permanent": True,
                        "source": "synthetic-code-evidence",
                    }
                ],
            },
            "scenarioOverrides": {},
        }

    def _rows(self) -> dict[str, dict]:
        result = claims.calculate_nation_claims(
            self._build_indexed(),
            claimant_name="CLA",
            claim_catalog=self._catalog(),
            diagnostics=True,
        )
        self.assertEqual(result["status"], "complete")
        return {row["target"]["region"]["template"]: row for row in result["claims"]}

    def test_peaceful_claim(self):
        row = self._rows()["LowPeace"]
        self.assertEqual(row["hostilityKind"], "peaceful")
        self.assertEqual(row["currentEffectiveStatus"], "peaceful")
        self.assertFalse(row["hostile"])
        self.assertTrue(row["changeability"]["canBecomeHostileByFormula"])

    def test_static_hostile_claim_uses_saved_hostile_claims(self):
        row = self._rows()["LowStatic"]
        self.assertEqual(row["hostilityKind"], "static")
        self.assertTrue(row["staticHostile"])
        self.assertTrue(row["hostile"])
        self.assertTrue(row["permanent"])
        self.assertFalse(row["changeability"]["changeableByGovernmentValues"])
        self.assertIn("TINationState.hostileClaims", row["provenance"]["observed"])

    def test_conditional_hostile_claim_reports_values_and_formula(self):
        row = self._rows()["HighConditional"]
        self.assertEqual(row["hostilityKind"], "conditional")
        self.assertTrue(row["hostile"])
        self.assertIsNone(row["permanent"])
        self.assertEqual(row["governmentRule"]["claimantDemocracy"], 5.0)
        self.assertEqual(row["governmentRule"]["targetDemocracy"], 8.0)
        self.assertEqual(row["governmentRule"]["hostileBoundary"], 7.0)
        self.assertTrue(row["governmentRule"]["comparisonResult"])
        self.assertTrue(row["changeability"]["canBecomePeacefulByFormula"])

    def test_strict_threshold_boundary_is_peaceful(self):
        row = self._rows()["BoundaryPeace"]
        self.assertEqual(row["governmentRule"]["targetDemocracy"], 7.0)
        self.assertEqual(row["governmentRule"]["hostileBoundary"], 7.0)
        self.assertFalse(row["governmentRule"]["comparisonResult"])
        self.assertEqual(row["hostilityKind"], "peaceful")

    def test_missing_threshold_fails_closed_for_dynamic_claims(self):
        result = claims.calculate_nation_claims(
            self._build_indexed(),
            claimant_name="CLA",
            claim_catalog={"base": {}, "scenarioOverrides": {}},
        )
        self.assertEqual(result["status"], "incomplete")
        rows = {row["target"]["region"]["template"]: row for row in result["claims"]}
        self.assertEqual(rows["LowStatic"]["currentEffectiveStatus"], "hostile")
        self.assertEqual(rows["LowPeace"]["currentEffectiveStatus"], "unknown")
        self.assertTrue(
            any(item["name"] == "democracyDecreaseToMakeHostileClaim" for item in result["missingDependencies"])
        )

    def test_target_filter_selects_current_region_owner(self):
        result = claims.calculate_nation_claims(
            self._build_indexed(),
            claimant_name="CLA",
            target_name="HIGH",
            claim_catalog=self._catalog(),
        )
        self.assertEqual(len(result["claims"]), 1)
        self.assertEqual(result["claims"][0]["target"]["region"]["template"], "HighConditional")

    def test_succession_is_explicitly_not_reconstructed(self):
        row = self._rows()["LowPeace"]
        self.assertEqual(row["succession"]["annexation"], "unknown / not reconstructed")
        self.assertEqual(row["succession"]["federation"], "unknown / not reconstructed")


if __name__ == "__main__":
    unittest.main()
