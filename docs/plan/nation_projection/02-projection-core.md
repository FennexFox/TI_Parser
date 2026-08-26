# Phase 02: Projection model and transactional engine

## Goal

- Implement immutable plan parsing, cloned projection state, transaction stepping, priority coverage, and condition/goal semantics.

## Scope

- Dataclasses for nation/region/CP/advisor/plan/result state.
- Strict JSON validation for CP pips, metrics, segment transitions, councilors, and virtual advisors.
- Daily investment transactions using audited allocation/completion rules.
- Exact audited deterministic effects; unsupported priorities fail closed.
- Monthly periodic transactions only for audited formulas and boundaries.

## Non-goals

- No optimizer, stochastic event replay, asset placement guess, or whole-faction projection.

## Affected files

- `tools/ti_parser_nation_projection.py`
- `tests/test_nation_projection.py`

## Implementation steps

1. Parse plans and resolve CP/advisor references.
2. Build cloned state from `IndexedState`.
3. Apply segments before transactions; evaluate conditions after transactions.
4. Allocate daily IP per CP, apply bonuses, process completions in audited order.
5. Accumulate mechanic IDs, completion logs, checkpoints, goal results, limitations, and coverage.

## Acceptance criteria

- Omitted versus empty advisor/CP semantics match the user plan.
- Start-satisfied segments skip immediately; transitions affect the next investment tick.
- Unsupported nonzero priorities return incomplete without authoritative final state.
- Multi-completion conditions cannot observe intermediate completion state.

## Validation commands

- py -3 -m unittest discover -s tests -p 'test_*.py'

## Manual smoke tests

- Run a synthetic one-day projection and a start-satisfied segment transition.

## Rollback risks

- Formula changes are localized by rule ID and phase revert; no save state is mutated.

## Progress

- Completed: pure income helpers, plan/state dataclasses, validation, transaction engine, conditions, goals, coverage and deterministic fixtures are implemented.

## Decision log

- Daily investment is one transaction; all enum-ordered completions finish before policy conditions are evaluated.
- Population is `expected` only when an audited annual growth input is available. Real saves that lack this computed property continue diagnostically across monthly boundaries but lose authoritative status.
- Only Knowledge, Government, Unity and Funding completion paths are currently supported; every other nonzero priority fails closed.

## Outcomes / Retrospective

- The engine is independent of save loading and never mutates `IndexedState`. Tests cover full CP replacement, advisor tri-state semantics, rank decay, multi-completion transactions, monthly movement, expected population and unsupported priority behavior.
