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
2. Run dynamic opt-in CAL plans without hardcoded IDs, names, counts, or current values.
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

- Inspect Economy-only, Economy mixed/conditional, Unity opt-in/negative, Government→Economy fallback, and Economy+Unity CAL outputs.

## Rollback risks

- Graph artifacts are generated and should be committed separately from mechanic code after all source commits settle.

## Progress

- Pending.

## Decision log

- Real-save checks are observational; synthetic literals remain the strict regression source.

## Outcomes / Retrospective

- Pending.
