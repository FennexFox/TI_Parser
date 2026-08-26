# Nation priority and conditional Advisor projection

## Issue Target And Scope Summary

- Issue target: user-plan
- Title: Nation priority and conditional Advisor projection
- Source plan: None
- Scope: add package-only nation development data, a shared mechanics rule registry, deterministic/fail-closed nation projection, conditional CP/advisor segments, faction-contribution views, diagnostics, and CLI/tests.

## Strategy

- Keep game mechanics auditable and fail closed: only DLL/template-verified rules may produce authoritative projected state.
- Put formulas in Python and template/config values plus hashes in the generated catalog.
- Clone save state into projection dataclasses; never mutate `IndexedState`.
- Apply plan changes immediately before a verified investment transaction and evaluate segment/goal conditions only after a complete transaction.
- Keep `nation.*` state separate from target-nation `factionContribution.*`; whole-faction future totals remain out of scope.
- Treat advisor placement as `hypotheticalPolicy`, with successful continuous Advise renewal assumed.

## Phase Order

1. [Mechanics audit registry and data catalog](01-audit-registry.md)
2. [Projection model and transactional engine](02-projection-core.md)
3. [CLI faction contribution and diagnostics integration](03-cli-integration.md)
4. [Regression verification and documentation](04-verification.md)

## Phase Dependencies

- Phase 1 has no phase dependency beyond resolved issue context.
- Phase 2 depends on completion and validation of phase 1.
- Phase 3 depends on completion and validation of phase 2.
- Phase 4 depends on completion and validation of phase 3.

## Source Of Truth Decisions

- `00-master-plan.md` is the phased implementation plan source of truth.
- Phase files in this directory define phase-local scope and validation.
- Earlier monolithic plans are input material only unless explicitly retained.
- Installed `Assembly-CSharp.dll` and templates are audit/generator inputs; packaged catalogs and audited Python rules are the runtime source.
- Stable mechanics IDs are shared constants referenced by code, tests, audit records, and diagnostics.

## Global Validation Expectations

- py -3 -m unittest discover -s tests -p 'test_*.py'

## Known Risks And Assumptions

- The installed game build may change; source hashes make such drift visible.
- Exogenous events, player actions, mission failure/travel, and stochastic nation events are not replayed.
- A plan using any unsupported nonzero priority is incomplete and has no authoritative final state or ranking.
- Periodic rules are implemented only when cadence and formulas are verified; otherwise limitations remain explicit.
