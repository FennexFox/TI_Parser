# Phase 16: Economy and BuildArmy market branches

## Goal

- Implement Economy's authoritative nation/region effects and its independent expected world-market branch; repair the same missing branch in BuildArmy.

## Scope

- GDP/PCGDP/economy score, inequality/overshoot, Oil/Mining/Core transformation, downstream caches, market midpoint trajectory, and persistent Economy fallback execution.

## Non-goals

- Do not implement coupled climate feedback or actual CP-count mutation.
- Do not make market values goal/condition metrics.

## Affected files

- projection engine, coverage tracker, snapshots/output, and Economy/BuildArmy fixtures

## Implementation steps

1. Implement audited Economy calculation and executive-faction modifier source.
2. Apply inequality clamp and overshoot cohesion/unrest effects.
3. Reproduce cached Oil→Mining→Core precedence, live candidate ordering, stable ties, transformations, and same-day no-fallthrough behavior.
4. Recompute immediate live dependencies while preserving daily resource/core caches until their next boundary.
5. Apply Metals/Noble Metals midpoint mutation as `expected/meanPath/deterministicMeanInput` when available.
6. If only market data is unavailable, commit Economy/BuildArmy nation mutations and progress, mark only world-market scope incomplete, and retain ranking.
7. Let default-Economy fallback allocate and complete on later investment ticks.

## Acceptance criteria

- Economy GDP, inequality, region transitions, progress, and fallback are authoritative when their inputs resolve.
- Market-only unsupported evidence never lowers unrelated Economy or Army metrics.
- A later audited consumer of missing market data promotes the dependency to a blocking runtime stop.

## Validation commands

- `py -3 -m pytest -q tests/test_nation_projection.py tests/test_nation_projection_cli.py`
- package-only and catalog parity focused tests

## Manual smoke tests

- Run Economy-only and long Government plans against the opt-in CAL save; confirm fallback proceeds into Economy and record any later CP-count blocker.

## Rollback risks

- Handler order crosses an unsupported-but-independent market branch; dependency edges must prove that skipping it cannot affect nation/faction output.

## Progress

- Complete.

## Decision log

- Nation/faction authority is retained when the only missing branch is world market.

## Outcomes / Retrospective

- Economy completion now applies the audited executive-faction effect source,
  PCGDP/GDP change, economy-score refresh, inequality clamp/overshoot, and
  cached Oil-before-Mining-before-Core trigger path.
- Region selection preserves the daily cached branch while using live candidate
  state and stable region ordering. A depleted cached branch does not fall
  through to another transformation type during the same day.
- Economy and BuildArmy market mutations use separate conditional child rules.
  Available Metals/Noble Metals values receive midpoint mean-input changes;
  missing values mark only `worldMarket` unsupported and do not lower nation,
  faction, army-placement, or maintenance coverage.
- Default Economy pips created by Government/MC invalidation now allocate and
  complete on later investment ticks instead of causing the previous runtime
  stop.
- The pre-existing catalog-verify synthetic fixture was updated with the
  faction/ideology sources made mandatory in phase 14; this repaired five
  full-suite fixture failures without changing runtime behavior.
- A 10-day Economy-only observational CAL smoke completed 14 Economy
  completions, increased GDP, retained complete nation/faction/world scopes,
  and reported market evidence as expected/meanPath/deterministicMeanInput.
  No CP-count blocker occurred in that window.
- Validation: the full suite passes 242 tests with 9 skips and 23 subtests.
