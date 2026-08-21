import math
import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import ti_parser_core as core


class StrictEffectResolutionTests(unittest.TestCase):
    def test_all_supported_operations_preserve_order(self):
        contexts = {"Research": ["add", "multiply", "fixed", "increase", "decrease"]}
        templates = {
            "add": {"operation": "Additive", "value": 2},
            "multiply": {"operation": "Multiplicative", "value": "3"},
            "fixed": {"operation": "SetToFixedValue", "value": 4.0},
            "increase": {"operation": "IncreaseToValue", "value": 6},
            "decrease": {"operation": "DecreaseToValue", "value": 5},
        }

        self.assertEqual(core.apply_effect_modifiers(contexts, templates, "Research", 1), 5.0)

    def test_missing_referenced_effect_fails_with_structured_dependency(self):
        with self.assertRaises(core.CalculationDependencyError) as raised:
            core.apply_effect_modifiers({"Research": ["MissingEffect"]}, {}, "Research", 10)

        dependency = raised.exception.dependencies[0]
        self.assertEqual(dependency.kind, "effect")
        self.assertEqual(dependency.name, "MissingEffect")
        self.assertEqual(dependency.context, "Research")
        self.assertIsNone(dependency.scenario)
        self.assertIn("missing", dependency.reason)
        self.assertEqual(raised.exception.missing_dependencies, [dependency.to_dict()])

    def test_non_object_effect_row_fails_closed(self):
        with self.assertRaises(core.CalculationDependencyError) as raised:
            core.apply_effect_modifiers(
                {"Research": ["BrokenEffect"]},
                {"BrokenEffect": None},  # type: ignore[dict-item]
                "Research",
                10,
            )

        self.assertIn("row must be an object", str(raised.exception))

    def test_missing_or_unknown_operation_fails_closed(self):
        for template in ({"value": 1}, {"operation": "Divide", "value": 1}):
            with self.subTest(template=template):
                with self.assertRaises(core.CalculationDependencyError) as raised:
                    core.apply_effect_modifiers(
                        {"Research": ["BrokenEffect"]},
                        {"BrokenEffect": template},
                        "Research",
                        10,
                    )
                self.assertIn("operation", raised.exception.dependencies[0].reason)

    def test_missing_or_invalid_value_fails_closed(self):
        invalid_values = [None, True, "", "not-a-number", math.nan, math.inf, -math.inf]
        templates = [
            {"operation": "Additive"},
            *({"operation": "Additive", "value": value} for value in invalid_values),
        ]
        for template in templates:
            with self.subTest(template=template):
                with self.assertRaises(core.CalculationDependencyError) as raised:
                    core.apply_effect_modifiers(
                        {"Research": ["BrokenEffect"]},
                        {"BrokenEffect": template},
                        "Research",
                        10,
                    )
                self.assertIn("value", raised.exception.dependencies[0].reason)

    def test_effects_in_irrelevant_context_are_not_validated(self):
        contexts = {
            "Research": ["ValidEffect"],
            "Mining": ["MissingEffect"],
        }
        templates = {"ValidEffect": {"operation": "Additive", "value": 2}}

        self.assertEqual(core.apply_effect_modifiers(contexts, templates, "Research", 10), 12.0)
        self.assertEqual(core.apply_effect_modifiers(contexts, templates, "MissionControl", 10), 10.0)

    def test_malformed_requested_context_fails_but_irrelevant_one_does_not(self):
        contexts = {"Research": "BrokenEffect"}  # type: ignore[dict-item]

        self.assertEqual(core.apply_effect_modifiers(contexts, {}, "Mining", 10), 10.0)
        with self.assertRaises(core.CalculationDependencyError) as raised:
            core.apply_effect_modifiers(contexts, {}, "Research", 10)
        self.assertEqual(raised.exception.dependencies[0].kind, "effectContext")


if __name__ == "__main__":
    unittest.main()
