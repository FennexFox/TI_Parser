# Phase 12: Real-save matrix, documentation, and Graphify refresh

## Goal

- Validate the hardened contracts against independent fixtures and the opt-in current CAL save, document the resulting boundaries, and refresh the repository graph.

## Scope

- Expand the `TI_PARSER_REAL_SAVE` observational matrix across Knowledge, Government, Welfare, Mission Control, BuildArmy, and long Government fallback paths.
- Compute deterministic candidates from independently encoded audited order rather than production helpers or hardcoded current locations.
- Update mechanics audit, README, phase outcomes, and before/after coverage/runtime-stop examples.
- Rebuild Graphify after all code and tests stabilize and query coverage, runtime-stop, validity, and scheduler paths.

## Non-goals

- Do not commit the save, absolute path, object IDs, current values, CP count, region count, or placement as fixtures.
- Do not call uncontrolled campaign endpoints strict validation.
- Do not add Economy completion, actual CP-count mutation, Monte Carlo, optimizer, or new priority coverage.

## Affected files

- `tests/test_nation_projection_real_save.py`
- `docs/nation_projection_mechanics_audit.md`
- `README.md`
- `docs/plan/nation_projection/*.md`
- `graphify-out/`

## Implementation steps

1. Add independent exact fixtures for completion deltas, Population feedback, rest caches, MC branches/mutation order, BuildArmy selection/maintenance, fallback prefix, registry evidence, and scheduler order.
2. Run independent one-year real-save plans for Knowledge, Government, mixed Government/Knowledge, Knowledge/Welfare, and conditional Government-to-Knowledge/Welfare.
3. Exercise MC/Knowledge and BuildArmy/Knowledge and compare their placements to the audited deterministic order calculated from extracted state.
4. Run long Government to cap/fallback and verify the structured stop and authoritative prefix.
5. Record unsupported rules and observational limitations, run all regressions and package-only checks, then execute the Graphify update/diagnostics/query procedure.

## Acceptance criteria

- The original CAL coverage bug, dynamic priority-validity bug, and whole-transaction rollback bug have direct regressions.
- Full suite and opt-in current real-save matrix pass without hardcoded mutable save facts.
- Documentation distinguishes deterministic mean-input from mathematical expectation and observational smoke from controlled validation.
- Graphify artifacts are current and focused queries connect metrics, rules, runtime stops, validity, scheduler, tests, and CLI output.

## Validation commands

- py -3 -m unittest discover -s tests -p 'test_*.py'
- $env:TI_PARSER_REAL_SAVE = '<local ExitSave.gz>'; py -3 -m unittest tests.test_nation_projection_real_save; Remove-Item Env:TI_PARSER_REAL_SAVE
- graphify update .
- graphify diagnose multigraph --graph graphify-out/graph.json --json
- graphify query "nation projection metric dependency coverage runtime stop authoritative prefix priority validity scheduler"

## Manual smoke tests

- Compare a CAL Knowledge one-year report before and after the metric tracker and list every newly propagated mean-path metric.
- Inspect a long Government stop and verify its CP snapshot and unsupported next step without relying on a fixed completion date.

## Rollback risks

- Local save values can drift between runs; only structural/audited selection properties are asserted.
- Graph generation is an atomic final artifact update and should be reverted as a unit if diagnostics fail.

## Progress

- Completed: implementation, documentation, full-suite and opt-in real-save
  validation, Graphify refresh, multigraph diagnostics, and focused dependency
  queries all passed.

## Decision log

- Real-save runs remain observational smoke until a deliberately controlled A-to-B pair is supplied.

## Outcomes / Retrospective

- The original behavior was reproduced before the fix: Population/GDP/research
  were `expected/meanPath`, while dependent education/cohesion incorrectly
  remained exact and rest-cache metrics were absent. Execution-derived evidence
  now propagates `expected/meanPath` through only the metrics that consume the
  mean-input trajectory, while unrelated Funding and sustainability remain
  exact.
- The static nation-UI inactive-key grouping was the MC false-positive root
  cause. Shared live validity now keeps valid MC pips effective and reports
  serialized/recomputed consistency for every current CP without freezing save
  counts or values.
- A long Government observational run now stops before the next Economy
  allocation and preserves the completed Government effect, consumed progress,
  persistent Economy fallback, and repaired CP caches in
  `lastAuthoritativeState`. No Economy completion execution is emitted.
- Ordinary Welfare completions emit the parent and inequality child execution;
  decolonization rules are absent until their threshold path is actually
  reached. Synthetic fixtures separately prove completion-local rollback when
  downstream data is unavailable.
- Independent fixtures cover Population-to-next-tick scaling, literal priority
  deltas, rest-cache values, MC branch/mutation ordering, deterministic Army
  placement/next-tick maintenance, registry evidence, and the complete
  same-timestamp scheduler phase order.
- Validation before Graphify: 70 focused tests, 242 full tests with 9 opt-in or
  environment-dependent skips, and 8 opt-in local-save observational tests all
  pass. The local save remains an observational smoke input, not strict A-to-B
  validation.
- Graphify rebuilt the stabilized source into 2,146 nodes, 6,194 edges, and 110
  communities. Multigraph diagnostics report zero malformed, missing-endpoint,
  dangling, self-loop, or duplicate edges. Focused queries connect
  `MetricDependencyTracker`, `ProjectionRuntimeStop`, shared
  `PriorityValidityResult`, projection transactions, nation UI, direct tests,
  and the mechanics registry in the refreshed graph.
