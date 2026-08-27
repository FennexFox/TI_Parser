# Phase 18: Real-save verification, documentation, and Graphify

## Goal

- Complete independent, package-only, observational real-save, documentation, and dependency-graph verification for Economy and Unity.

## Scope

- Full test suite, opt-in CAL matrix, mechanics audit/README updates, Phase outcomes, and Graphify incremental refresh/diagnostics.

## Non-goals

- Do not call observational save results strict validation.
- Do not add CP-count mutation, Monte Carlo, optimizer, climate coupling, or new goal namespaces.

## Affected files

- tests and documentation
- `graphify-out` generated graph artifacts

## Implementation steps

1. Add independent literal fixtures for Economy/Unity formulas, ordering, coverage branches, fallback, and stochastic semantics.
2. Prefer CAL when it is projection-capable; otherwise select a viable nation
   from the opt-in save dynamically. Do not hardcode IDs, names, counts, or
   current values.
3. Record first `UpdateControlPoints` blocker timing/context in long Economy runs rather than implementing it.
4. Update audit, README, and all phase outcomes with exact/expected/unsupported distinctions and remaining limitations.
5. Run both complete test runners and package/catalog verification.
6. Run Graphify update, multigraph diagnostics, and targeted queries for Economy/Unity dependencies.

## Acceptance criteria

- Current baseline remains green and all new direct mechanic evidence passes.
- Government fallback reaches a later Economy completion in synthetic and real-save smoke.
- World-market incompleteness remains non-blocking only while it has no nation/faction descendant.
- Graphify contains the new rule, policy, completion, scope, and dependency paths with no malformed edges.

## Validation commands

- `py -3 -m pytest -q`
- `py -3 -m unittest discover -s tests -p 'test_*.py'`
- focused package-only/catalog verification
- opt-in `tests.test_nation_projection_real_save`
- strict phase-plan validation
- Graphify update, diagnose, and targeted query commands

## Manual smoke tests

- Inspect Economy-only, Economy mixed/conditional, Unity opt-in/negative,
  Government→Economy fallback, and Economy+Unity outputs from the dynamically
  selected observational target.

## Rollback risks

- Graph artifacts are generated and should be committed separately from mechanic code after all source commits settle.

## Progress

- Mechanics, tests, real-save smoke, README, and audit updates are complete.
- Graphify refresh and final graph diagnostics remain before phase completion.

## Decision log

- Real-save checks are observational; synthetic literals remain the strict regression source.

## Outcomes / Retrospective

- Real-save selection no longer assumes that the token `CAL` still identifies
  the earlier four-CP/five-region nation. CAL is preferred only when its saved
  refs are projection-capable; otherwise the fixture chooses the first viable
  non-alien nation from the save and derives every CP position dynamically.
- The opt-in Broken Earth run passed 10 real-save tests and 16 subtests. The
  one-year Economy, Unity, and Economy+Unity cases all completed without a CP
  mutation blocker. The long Government path preserved its cap/invalidation
  fallback and continued into later Economy completions instead of stopping at
  the former unsupported boundary. These are observational results, not a
  controlled A-to-B validation.
- The synthetic suite directly covers Economy formulas/branch isolation,
  Unity integer sample counts and sequential owner state, Religion/disabled/allied
  strength, direct deltas, legitimize, public/elite rest impact, and the
  distinction between Population mean-input and Unity expected-transition
  provenance.
- Full runner results before Graphify: pytest reports 249 passed, 11 skipped,
  and 23 subtests; unittest discovery reports 260 tests passed with 12 skips.
  Strict validation accepts all 18 phase files.
- Installed-template parity for `nation_development_catalog.json` passes for
  Modern, 2003, and Broken Earth, including payload and source hashes. The
  aggregate `catalog-verify` command remains failed because three unrelated
  research-catalog source hashes have drifted; this phase did not regenerate
  unrelated research artifacts.
