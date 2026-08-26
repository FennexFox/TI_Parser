# Phase 10: Authoritative-prefix fail-closed diagnostics

## Goal

- Preserve every fully verified mutation before an unsupported next step and make the exact runtime boundary machine-readable.

## Scope

- Add commit boundaries for CP revalidation/fallback, completed priority handlers plus cost consumption, and completed periodic phases.
- Keep atomic completion rollback for unresolved Welfare decolonization/downstream dependencies.
- Gate any dynamically activated unsupported priority before allocation on the next investment tick.
- Expand runtime-stop diagnostics, attempted-transaction trace, affected metrics, and CP-inclusive authoritative snapshots.

## Non-goals

- Do not simulate Economy allocation/effects or `UpdateControlPoints` mutation.
- Do not evaluate plan conditions against a partially completed transaction.

## Affected files

- `tools/ti_parser_nation_projection.py`
- `tools/ti_parser_projection_coverage.py`
- `tests/test_nation_projection.py`
- `tests/test_nation_projection_cli.py`

## Implementation steps

1. Define structured stop context: timestamp/day/kind/phase, trigger, last transaction, authoritative mutations, unsupported next step, state context, affected metrics, and attempted transaction.
2. Make each completion atomic, but commit a successful handler, cost consumption, and fallback/cache repair before checking the next priority dependency.
3. Preserve post-Government democracy/progress and Economy pip/cache, then stop before the next Economy allocation.
4. Include CP raw/effective pips and serialized/recomputed cache data in authoritative state snapshots.
5. Derive blockers and affected metrics from dependency descendants and enrich the CP-count gate diagnostics before mutation.

## Acceptance criteria

- Government cap/fallback preserves its effect, cost, Economy pip 1, and repaired cache in `lastAuthoritativeState`.
- No Economy allocation/effect rule execution occurs before the stop.
- Incomplete Welfare decolonization rolls back only its incomplete completion.
- Fully completed transactions remain in `transactions`; an interrupted prefix is represented under `runtimeStop.attemptedTransaction`.
- Existing runtime-stop keys remain compatible while all new structured fields are present.

## Validation commands

- py -3 -m unittest tests.test_nation_projection tests.test_nation_projection_cli
- py -3 -m unittest discover -s tests -p 'test_*.py'

## Manual smoke tests

- Run a long Government projection to cap, inspect the Economy fallback authoritative prefix, then confirm the next allocation is the unsupported boundary.
- Force a monthly CP-count change requirement and inspect pre-mutation state context.

## Rollback risks

- A boundary placed before cost consumption would duplicate an effect on resume; a boundary placed after an unsupported mutation would violate fail-closed semantics.
- Partial transaction traces must not be presented as ordinary committed transactions.

## Progress

- Pending.

## Decision log

- Successful completion handler plus cost consumption is the smallest reusable authoritative completion boundary.

## Outcomes / Retrospective

- Pending.
