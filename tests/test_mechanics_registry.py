import sys
import unittest
import importlib
from dataclasses import replace
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from ti_parser_mechanics import (
    COVERAGE_RESOLVERS,
    REGISTRY,
    Rules,
    mechanic_diagnostics,
    mechanic_rule_test,
    validate_registry,
    validate_rule_execution,
    validate_test_metadata,
)
from ti_parser_catalogs import RuntimeCatalogs


class MechanicsRegistryTests(unittest.TestCase):
    def test_registry_ids_are_unique_supported_rules_have_tests_and_diagnostics_resolve(self):
        validate_registry()
        self.assertEqual(len(REGISTRY), len(set(REGISTRY)))
        self.assertTrue(all(
            rule.test_ids
            for rule in REGISTRY.values()
            if rule.coverage != "unsupported"
            or any(value != "unsupported" for value in rule.allowed_coverages)
        ))
        self.assertEqual({row["id"] for row in mechanic_diagnostics(REGISTRY)}, set(REGISTRY))
        for rule in REGISTRY.values():
            for test_id in rule.test_ids:
                module_name, class_name, method_name = test_id.rsplit(".", 2)
                test_class = getattr(importlib.import_module(module_name), class_name)
                self.assertTrue(callable(getattr(test_class, method_name)), test_id)

        def resolve_test(test_id):
            module_name, class_name, method_name = test_id.rsplit(".", 2)
            return getattr(getattr(importlib.import_module(module_name), class_name), method_name)

        validate_test_metadata(resolve_test)

    def test_duplicate_and_unregistered_rule_ids_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            validate_registry((Rules.NATION_IP_BASE, replace(Rules.NATION_IP_BASE, description="duplicate")))
        with self.assertRaisesRegex(ValueError, "Unregistered"):
            mechanic_diagnostics(["nation.unknown"])

    @mechanic_rule_test(
        "nation.ip.economy-score",
        "nation.ip.control-point-default-economy",
        "nation.priority.validity",
        "nation.priority.government.legitimize",
        "nation.priority.welfare.complete",
        "nation.priority.welfare.inequality",
        "nation.priority.welfare.colony-trigger",
        "nation.priority.welfare.decolonization",
        "nation.priority.welfare.decolonization-downstream",
        "nation.priority.mission-control.complete",
        "nation.priority.mission-control.placement",
        "nation.priority.build-army.complete",
        "nation.priority.build-army.placement",
        "nation.asset.army.maintenance",
        "nation.periodic.derived-cache",
        "nation.periodic.control-points",
        "nation.population.annual-growth",
        "nation.population.monthly-growth",
        evidence="contract",
    )
    def test_real_save_rule_contracts_are_registered(self):
        required = set(self.test_real_save_rule_contracts_are_registered.mechanic_rule_ids)
        self.assertLessEqual(required, set(REGISTRY))
        self.assertEqual(REGISTRY["nation.priority.unity.complete"].coverage, "unsupported")
        self.assertEqual(REGISTRY["nation.priority.government.complete"].coverage, "exact")
        self.assertEqual(REGISTRY["nation.periodic.control-points"].coverage_mode, "conditional")
        self.assertEqual(REGISTRY["nation.periodic.control-points"].allowed_coverages, ("exact", "unsupported"))

        mission_control = REGISTRY["nation.priority.mission-control.placement"]
        self.assertEqual(mission_control.coverage_mode, "conditional")
        self.assertEqual(
            mission_control.allowed_coverages,
            ("exact", "aggregateOnly", "unsupported"),
        )
        self.assertIn(mission_control.coverage_resolver_id, COVERAGE_RESOLVERS)

        build_army = REGISTRY["nation.priority.build-army.placement"]
        self.assertEqual(build_army.coverage_mode, "conditional")
        self.assertEqual(build_army.allowed_coverages, ("exact", "unsupported"))

    def test_execution_coverage_is_validated_against_registered_resolver(self):
        mission_control = Rules.NATION_PRIORITY_MISSION_CONTROL_PLACEMENT
        validate_rule_execution(
            mission_control.id,
            "aggregateOnly",
            coverage_resolver_id=mission_control.coverage_resolver_id,
        )
        with self.assertRaisesRegex(ValueError, "Wrong coverage resolver"):
            validate_rule_execution(mission_control.id, "exact")
        with self.assertRaisesRegex(ValueError, "cannot yield"):
            validate_rule_execution(
                Rules.NATION_PRIORITY_BUILD_ARMY_PLACEMENT.id,
                "aggregateOnly",
                coverage_resolver_id=Rules.NATION_PRIORITY_BUILD_ARMY_PLACEMENT.coverage_resolver_id,
            )
        with self.assertRaisesRegex(ValueError, "requires exact"):
            validate_rule_execution(Rules.NATION_IP_BASE.id, "expected")

    def test_rule_test_metadata_must_name_the_same_rule_id(self):
        rule = replace(
            Rules.NATION_IP_BASE,
            test_ids=("fixture",),
        )

        @mechanic_rule_test(rule.id, evidence="expectedValue")
        def declared_fixture():
            pass

        validate_test_metadata(lambda _test_id: declared_fixture, (rule,))

        @mechanic_rule_test(Rules.NATION_IP_PRIORITY_BONUS.id, evidence="expectedValue")
        def mismatched_fixture():
            pass

        with self.assertRaisesRegex(ValueError, "does not declare"):
            validate_test_metadata(lambda _test_id: mismatched_fixture, (rule,))

        @mechanic_rule_test(rule.id, evidence="contract")
        def contract_only_fixture():
            pass

        with self.assertRaisesRegex(ValueError, "no direct non-contract evidence"):
            validate_test_metadata(lambda _test_id: contract_only_fixture, (rule,))

        with self.assertRaisesRegex(ValueError, "Invalid mechanic test evidence"):
            mechanic_rule_test(rule.id, evidence="directional")

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
