import copy
import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from ti_parser_projection_coverage import MetricDependencyTracker, combine_coverage


class ProjectionCoverageTests(unittest.TestCase):
    def test_coverage_order(self):
        self.assertEqual(combine_coverage("exact", "expected"), "expected")
        self.assertEqual(combine_coverage("aggregateOnly", "expected"), "aggregateOnly")
        self.assertEqual(combine_coverage("unsupported", "exact"), "unsupported")

    def test_transitive_evidence_and_mean_path_contract(self):
        tracker = MetricDependencyTracker()
        tracker.record(
            "region.1.population",
            rule_ids=("nation.population.monthly-growth",),
            coverage="expected",
            provenance=("meanPath", "heldFixedWorldContext"),
        )
        tracker.record(
            "nation.population",
            inputs=("region.1.population",),
            rule_ids=("nation.periodic.population",),
        )
        tracker.record("nation.research", inputs=("nation.population",), rule_ids=("nation.research",))
        row = tracker.public(("nation.research",))["nation.research"]
        self.assertEqual(row["coverage"], "expected")
        self.assertEqual(row["provenance"], ["heldFixedWorldContext", "meanPath"])
        self.assertFalse(row["expectationGuarantee"])
        self.assertEqual(row["ruleIds"], [
            "nation.periodic.population",
            "nation.population.monthly-growth",
            "nation.research",
        ])

    def test_unread_metric_does_not_receive_provenance(self):
        tracker = MetricDependencyTracker()
        tracker.record("nation.population", coverage="expected", provenance=("meanPath",))
        tracker.record("nation.funding", rule_ids=("nation.priority.funding.complete",))
        row = tracker.public(("nation.funding",))["nation.funding"]
        self.assertEqual(row["coverage"], "exact")
        self.assertEqual(row["provenance"], [])

    def test_descendants_and_blockers(self):
        tracker = MetricDependencyTracker()
        tracker.record("internal.baseIp", inputs=("nation.gdp",))
        tracker.record("internal.progress.Knowledge", inputs=("internal.baseIp",))
        tracker.record("nation.education", inputs=("internal.progress.Knowledge",))
        self.assertEqual(
            tracker.descendants(("nation.gdp",)),
            {"internal.baseIp", "internal.progress.Knowledge", "nation.education"},
        )
        row = tracker.public(
            ("nation.education",),
            blockers=("nation.priority.economy.complete",),
            affected=("nation.*",),
        )["nation.education"]
        self.assertEqual(row["coverage"], "unsupported")
        self.assertEqual(row["blockers"], ["nation.priority.economy.complete"])

    def test_deepcopy_is_transaction_safe(self):
        tracker = MetricDependencyTracker()
        tracker.ensure("nation.gdp")
        working = copy.deepcopy(tracker)
        working.record("nation.gdp", inputs=("nation.population",), coverage="expected", provenance=("meanPath",))
        self.assertEqual(tracker.public(("nation.gdp",))["nation.gdp"]["coverage"], "exact")
        self.assertEqual(working.public(("nation.gdp",))["nation.gdp"]["coverage"], "expected")


if __name__ == "__main__":
    unittest.main()
