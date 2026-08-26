# Nation priority and conditional Advisor projection

## Issue Target And Scope Summary

- Issue target: user-plan
- Title: Nation priority and conditional Advisor projection
- Source plan: None
- Scope: add package-only nation development data, a shared mechanics rule registry, deterministic/fail-closed nation projection, conditional CP/advisor segments, faction-contribution views, diagnostics, and CLI/tests; then harden the feature against the local Broken Earth CAL save with verified Population, Government legitimize, Welfare, Mission Control, BuildArmy, event scheduling, and runtime dependency propagation.

## Strategy

- Keep game mechanics auditable and fail closed: only DLL/template-verified rules may produce authoritative projected state.
- Put formulas in Python and template/config values plus hashes in the generated catalog.
- Clone save state into projection dataclasses; never mutate `IndexedState`.
- Apply plan changes immediately before a verified investment transaction and evaluate segment/goal conditions only after a complete transaction.
- Keep `nation.*` state separate from target-nation `factionContribution.*`; whole-faction future totals remain out of scope.
- Treat advisor placement as `hypotheticalPolicy`, with successful continuous Advise renewal assumed.
- Replace the approximate date loop with verified DLL event boundaries and execute every transaction on a clone. A newly discovered unsupported dependency discards the whole transaction and preserves `lastAuthoritativeState`.
- Derive coverage from the rules and branches actually executed. Conditional coverage resolvers must close every branch and record effective coverage and provenance.
- Treat Population as a deterministic mean-input trajectory: replace each stochastic input with its mean, propagate `meanPath`, and never claim that the nonlinear trajectory equals the mathematical expectation of all stochastic paths.

## Phase Order

1. [Mechanics audit registry and data catalog](01-audit-registry.md)
2. [Projection model and transactional engine](02-projection-core.md)
3. [CLI faction contribution and diagnostics integration](03-cli-integration.md)
4. [Regression verification and documentation](04-verification.md)
5. [Real-save mechanics registry and catalog extension](05-real-save-mechanics.md)
6. [DLL-boundary runtime engine and priority mechanics](06-runtime-engine.md)
7. [Runtime diagnostics and CLI contract hardening](07-cli-diagnostics.md)
8. [Independent fixtures, real-save validation, and Graphify refresh](08-real-save-verification.md)

## Phase Dependencies

- Phase 1 has no phase dependency beyond resolved issue context.
- Phase 2 depends on completion and validation of phase 1.
- Phase 3 depends on completion and validation of phase 2.
- Phase 4 depends on completion and validation of phase 3.
- Phase 5 extends the completed phase-1 registry/catalog work and depends on phases 1 through 4 remaining green.
- Phase 6 depends on the verified rule metadata and packaged data produced in phase 5.
- Phase 7 depends on phase 6 exposing rule executions, runtime stops, and authoritative state boundaries.
- Phase 8 depends on phases 5 through 7 and completes full-suite, opt-in local-save, package-only, and Graphify verification.

## Source Of Truth Decisions

- `00-master-plan.md` is the phased implementation plan source of truth.
- Phase files in this directory define phase-local scope and validation.
- Earlier monolithic plans are input material only unless explicitly retained.
- Installed `Assembly-CSharp.dll` and templates are audit/generator inputs; packaged catalogs and audited Python rules are the runtime source.
- Stable mechanics IDs are shared constants referenced by code, tests, audit records, and diagnostics.
- Phases 1 through 4 remain the completed initial implementation record. Phases 5 through 8 are the source of truth for the real-save compatibility extension and supersede conflicting mechanics assumptions in earlier outcomes.
- The primary opt-in smoke input is the uncommitted local `ExitSave.gz` Broken Earth CAL save selected through `TI_PARSER_REAL_SAVE`; its path, object IDs, and current values are never encoded into production code or committed fixtures.
- `coverage: "expected"` is the compatibility coverage label for Population-derived results, while `provenance: "meanPath"`, `stochasticTreatment: "deterministicMeanInput"`, and `expectationGuarantee: false` state the stricter semantics.
- Welfare decolonization is a conditional dependency reached only by the completion that crosses its threshold. Mission Control and BuildArmy coverage is resolved per execution instance, not fixed to the lowest possible mechanic-wide coverage.

## Global Validation Expectations

- Pre-extension baseline: 198 tests passed, 1 skipped, and 10 subtests passed.
- py -3 -m unittest discover -s tests -p 'test_*.py'
- py -3 -m unittest tests.test_mechanics_registry tests.test_catalog_generators tests.test_runtime_catalogs
- py -3 -m unittest tests.test_nation_projection tests.test_nation_projection_cli tests.test_package_only_runtime
- $env:TI_PARSER_REAL_SAVE = '<local ExitSave.gz>'; py -3 -m unittest tests.test_nation_projection_real_save; Remove-Item Env:TI_PARSER_REAL_SAVE
- graphify update .; graphify diagnose multigraph --graph graphify-out/graph.json --json; graphify query "nation projection runtime dependency population government welfare mission control build army"

## Known Risks And Assumptions

- The installed game build may change; source hashes make such drift visible.
- Exogenous events, player actions, mission failure/travel, and stochastic nation events are not replayed.
- A plan using any unsupported nonzero priority is incomplete and has no authoritative final state or ranking.
- Periodic rules are implemented only when cadence and formulas are verified; otherwise limitations remain explicit.
- Installed DLL/template inputs can drift independently of the repository. Catalog regeneration and provenance parity must fail visibly, while runtime remains package-only.
- Population feedback is nonlinear. The deterministic mean-input trajectory is generally not guaranteed to equal the expected value over complete stochastic trajectories.
- Monthly `UpdateControlPoints` mutation is outside this extension; a required CP-count change must stop before mutation under `nation.periodic.control-points`.
- Economy remains unsupported because its region transformation, nation effect, market, and environment dependencies are not all implemented. Unity-dependent resting-state metrics remain unsupported until its public-opinion side effect is modeled.
