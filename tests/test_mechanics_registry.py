import sys
import unittest
import importlib
from dataclasses import replace
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from ti_parser_mechanics import REGISTRY, Rules, mechanic_diagnostics, validate_registry
from ti_parser_catalogs import RuntimeCatalogs


class MechanicsRegistryTests(unittest.TestCase):
    def test_registry_ids_are_unique_supported_rules_have_tests_and_diagnostics_resolve(self):
        validate_registry()
        self.assertEqual(len(REGISTRY), len(set(REGISTRY)))
        self.assertTrue(all(rule.test_ids for rule in REGISTRY.values() if rule.coverage != "unsupported"))
        self.assertEqual({row["id"] for row in mechanic_diagnostics(REGISTRY)}, set(REGISTRY))
        for rule in REGISTRY.values():
            for test_id in rule.test_ids:
                module_name, class_name, method_name = test_id.rsplit(".", 2)
                test_class = getattr(importlib.import_module(module_name), class_name)
                self.assertTrue(callable(getattr(test_class, method_name)), test_id)

    def test_duplicate_and_unregistered_rule_ids_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            validate_registry((Rules.NATION_IP_BASE, replace(Rules.NATION_IP_BASE, description="duplicate")))
        with self.assertRaisesRegex(ValueError, "Unregistered"):
            mechanic_diagnostics(["nation.unknown"])

    def test_nation_development_catalog_is_data_only_and_scenario_aware(self):
        modern = RuntimeCatalogs.load("ModernScenario").nation_development
        broken = RuntimeCatalogs.load("BrokenEarthScenario").nation_development
        self.assertEqual(modern["priorities"]["Military_BuildArmy"]["investmentCost"], 60)
        self.assertEqual(broken["priorities"]["Military_BuildArmy"]["investmentCost"], 40)
        serialized = repr(modern).lower()
        for forbidden in ("formula", "algorithm", "transaction", "completionorder", "mechanicrule"):
            self.assertNotIn(forbidden, serialized)


if __name__ == "__main__":
    unittest.main()
