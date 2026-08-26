"""Execution-derived metric coverage and provenance for nation projection."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Mapping


COVERAGE_ORDER = {
    "exact": 0,
    "expected": 1,
    "aggregateOnly": 2,
    "unsupported": 3,
}


def _names(values: str | Iterable[str]) -> tuple[str, ...]:
    if isinstance(values, str):
        return (values,)
    return tuple(str(value) for value in values)


def combine_coverage(*values: str) -> str:
    """Return the least authoritative coverage represented by ``values``."""

    if not values:
        return "exact"
    unknown = [value for value in values if value not in COVERAGE_ORDER]
    if unknown:
        raise ValueError(f"Unknown metric coverage: {unknown[0]}")
    return max(values, key=COVERAGE_ORDER.__getitem__)


@dataclass
class MetricEvidence:
    coverage: str = "exact"
    provenance: set[str] = field(default_factory=set)
    depends_on: set[str] = field(default_factory=set)
    rule_ids: set[str] = field(default_factory=set)
    blockers: set[str] = field(default_factory=set)

    def output(self) -> dict[str, object]:
        result: dict[str, object] = {
            "coverage": self.coverage,
            "provenance": sorted(self.provenance),
            "dependsOn": sorted(self.depends_on),
            "ruleIds": sorted(self.rule_ids),
            "blockers": sorted(self.blockers),
        }
        if "meanPath" in self.provenance:
            result.update({
                "stochasticTreatment": "deterministicMeanInput",
                "expectationGuarantee": False,
            })
        return result


@dataclass
class MetricDependencyTracker:
    evidence: dict[str, MetricEvidence] = field(default_factory=dict)
    reverse_dependencies: dict[str, set[str]] = field(default_factory=dict)

    def ensure(
        self,
        metric: str,
        *,
        coverage: str = "exact",
        provenance: Iterable[str] = (),
        rule_ids: Iterable[str] = (),
        blockers: Iterable[str] = (),
    ) -> MetricEvidence:
        if coverage not in COVERAGE_ORDER:
            raise ValueError(f"Unknown metric coverage: {coverage}")
        current = self.evidence.get(metric)
        if current is None:
            current = MetricEvidence(coverage=coverage)
            self.evidence[metric] = current
        else:
            current.coverage = combine_coverage(current.coverage, coverage)
        current.provenance.update(str(value) for value in provenance)
        current.rule_ids.update(str(value) for value in rule_ids)
        current.blockers.update(str(value) for value in blockers)
        if "meanPath" in current.provenance:
            current.coverage = combine_coverage(current.coverage, "expected")
        return current

    def record(
        self,
        outputs: str | Iterable[str],
        *,
        inputs: Iterable[str] = (),
        rule_ids: Iterable[str] = (),
        coverage: str = "exact",
        provenance: Iterable[str] = (),
        blockers: Iterable[str] = (),
    ) -> MetricEvidence | dict[str, MetricEvidence]:
        """Replace evidence for calculated outputs with their actual input graph."""

        if coverage not in COVERAGE_ORDER:
            raise ValueError(f"Unknown metric coverage: {coverage}")
        output_names = _names(outputs)
        input_names = tuple(str(value) for value in inputs)
        snapshots = {
            name: self.evidence.get(name, MetricEvidence())
            for name in input_names
        }
        combined = combine_coverage(coverage, *(item.coverage for item in snapshots.values()))
        combined_provenance = set(str(value) for value in provenance)
        combined_rules = set(str(value) for value in rule_ids)
        combined_blockers = set(str(value) for value in blockers)
        for item in snapshots.values():
            combined_provenance.update(item.provenance)
            combined_rules.update(item.rule_ids)
            combined_blockers.update(item.blockers)
        if "meanPath" in combined_provenance:
            combined = combine_coverage(combined, "expected")
        written: dict[str, MetricEvidence] = {}
        for output in output_names:
            evidence = MetricEvidence(
                coverage=combined,
                provenance=set(combined_provenance),
                depends_on=set(input_names),
                rule_ids=set(combined_rules),
                blockers=set(combined_blockers),
            )
            self.evidence[output] = evidence
            written[output] = evidence
            for input_name in input_names:
                self.reverse_dependencies.setdefault(input_name, set()).add(output)
        if len(written) == 1:
            return next(iter(written.values()))
        return written

    def descendants(self, seeds: Iterable[str]) -> set[str]:
        pending = list(str(value) for value in seeds)
        reached: set[str] = set()
        while pending:
            source = pending.pop()
            for target in self.reverse_dependencies.get(source, ()):
                if target not in reached:
                    reached.add(target)
                    pending.append(target)
        return reached

    def public(
        self,
        metrics: Iterable[str],
        *,
        blockers: Iterable[str] = (),
        affected: Iterable[str] = (),
    ) -> dict[str, dict[str, object]]:
        blocker_values = tuple(str(value) for value in blockers)
        patterns = tuple(str(value) for value in affected)
        result: dict[str, dict[str, object]] = {}
        for metric in sorted(set(str(value) for value in metrics)):
            evidence = self.evidence.get(metric, MetricEvidence())
            row = evidence.output()
            is_affected = any(
                metric == pattern
                or pattern.endswith(".*") and metric.startswith(pattern[:-1])
                for pattern in patterns
            )
            if is_affected:
                row["coverage"] = "unsupported"
                row["blockers"] = sorted(set(row["blockers"]) | set(blocker_values))
            result[metric] = row
        return result


def execution_record(
    *,
    rule_id: str,
    inputs: Iterable[str],
    outputs: Iterable[str],
    effective_coverage: str,
    dependencies: Iterable[str] = (),
    provenance: str | Iterable[str] = "dllReimplementation",
    coverage_resolver_id: str | None = None,
) -> dict[str, object]:
    provenance_values = (provenance,) if isinstance(provenance, str) else tuple(provenance)
    result: dict[str, object] = {
        "ruleId": rule_id,
        "effectiveCoverage": effective_coverage,
        "provenance": sorted(set(str(value) for value in provenance_values)),
        "dependencies": sorted(set(str(value) for value in dependencies)),
        "inputs": sorted(set(str(value) for value in inputs)),
        "outputs": sorted(set(str(value) for value in outputs)),
    }
    if coverage_resolver_id is not None:
        result["coverageResolverId"] = coverage_resolver_id
    if "meanPath" in result["provenance"]:
        result["expectationGuarantee"] = False
    return result
