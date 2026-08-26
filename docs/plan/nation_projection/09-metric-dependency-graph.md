# Phase 09: Execution-based metric dependency graph

## Goal

- Replace static metric coverage maps and manual provenance sets with evidence recorded by the calculations that actually execute.

## Scope

- Add a projection coverage module containing `MetricEvidence` and `MetricDependencyTracker`.
- Record inputs, outputs, direct rule IDs, blockers, execution coverage, and provenance for periodic updates, allocation, progress, completions, rest caches, research, and faction contribution.
- Propagate `meanPath` only through metrics that consume mean-input-derived values and emit `expectationGuarantee: false` whenever it reaches a public metric.
- Record Welfare child executions independently and keep rule execution coverage distinct from output-metric coverage.

## Non-goals

- Do not implement Economy completion, Unity public-opinion effects, Monte Carlo, or new priority mechanics.
- Do not expand the public condition namespace merely because an internal metric is tracked.

## Affected files

- `tools/ti_parser_projection_coverage.py`
- `tools/ti_parser_nation_projection.py`
- `tests/test_nation_projection.py`
- `tests/test_nation_projection_cli.py`

## Implementation steps

1. Define coverage ordering, immutable evidence serialization, dependency edges, transitive rule/provenance propagation, blocker propagation, descendants, and tracker cloning.
2. Attach the tracker to projection state and replace `_metric_coverage()` static rule maps with tracker output for all published nation, asset, progress, and faction-contribution metrics.
3. Record regional Population/GDP, PCGDP/economy score, base IP, allocation/progress, completion control dependencies, priority effects, monthly movement, noon rest cache, research, and faction contribution.
4. Emit execution records with inputs, outputs, direct dependencies, effective coverage, and actual provenance. Emit each reached Welfare child independently.
5. Add independent fixtures for mean-path propagation, unaffected exact metrics, completion-control dependencies, rest caches, and rule-versus-metric coverage.

## Acceptance criteria

- Knowledge education/cohesion and other metrics that consume mean-path inputs no longer remain incorrectly exact.
- `cohesionRest`, `unrestRest`, per-capita GDP, base IP, assets, all priority progress, research, and faction contribution have metric coverage.
- Every mean-path public metric reports `coverage: expected`, `provenance: [meanPath]`, and `expectationGuarantee: false`.
- Exact metrics that did not consume stochastic-derived inputs remain exact.

## Validation commands

- py -3 -m unittest tests.test_nation_projection tests.test_nation_projection_cli
- py -3 -m unittest discover -s tests -p 'test_*.py'

## Manual smoke tests

- Run a one-year all-CP Knowledge projection and inspect population-to-education/cohesion/research coverage propagation.
- Inspect a short pre-monthly-boundary run and confirm unrelated metrics remain exact.

## Rollback risks

- Over-propagating control dependencies can mark unrelated metrics expected; fixtures must prove both propagation and non-propagation.
- Deep-copied transaction state must include tracker evidence so rollback cannot leak attempted writes.

## Progress

- Pending.

## Decision log

- Metric evidence is execution-instance data; the mechanics registry remains the stable rule/provenance catalog.

## Outcomes / Retrospective

- Pending.
