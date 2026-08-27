# Phase 15: Scheduler, cache, and validation triggers

## Goal

- Match DLL cache and validation timing required by Economy and Unity before enabling their effects.

## Scope

- Daily faction priority-bonus cache, relevant saved effect expiry, allocation cache/live distinctions, and explicit CP validation triggers.
- Branch-aware dependency execution records.

## Non-goals

- Do not enable Economy or Unity completions.
- Do not implement unsaved future effects, ownership changes, or CP-count mutation.

## Affected files

- projection engine and dependency tracker
- scheduler/cache/ordering fixtures

## Implementation steps

1. Cache faction priority bonuses at daily 00:00 and process relevant expirations on the 1st/15th after caching.
2. Use cached owner bonuses for allocation and live executive-faction effects for direct Economy calculations.
3. Separate live-valid numerator from cached denominator/diversity state.
4. Replace blanket post-completion revalidation with pip-setter, capability/asset, GDP-cap, and audited explicit triggers; preserve stale cache otherwise.
5. Record branch scope, direct inputs/outputs, control dependencies, and validation-trigger traces.

## Acceptance criteria

- Same-day expiry fixtures prove allocation can use the pre-expiry cache while direct handlers see live effects.
- Unity-like education changes do not spuriously repair CP caches.
- Economy-relevant GDP/cap changes invoke the audited validation path.

## Validation commands

- `py -3 -m pytest -q tests/test_nation_projection.py tests/test_nation_projection_cli.py`
- `py -3 -m unittest tests.test_nation_projection tests.test_nation_projection_cli`

## Manual smoke tests

- Inspect detailed phase traces for one day spanning daily cache, investment, and noon resting-cache events.

## Rollback risks

- Removing blanket repair can expose stale serialized caches intentionally; tests must distinguish game parity from data corruption.

## Progress

- Pending.

## Decision log

- Cache staleness is preserved when the DLL preserves it; projection does not normalize state merely for convenience.

## Outcomes / Retrospective

- Pending.
