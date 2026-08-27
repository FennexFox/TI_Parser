# Phase 14: Economy and Unity audit, catalog, and state

## Goal

- Establish shared rule, data, extraction, state, and output contracts required by Economy and Unity without enabling their completion handlers.

## Scope

- Add child mechanic rules and Unity's conditional coverage resolver.
- Package audited Economy/Unity constants, faction/ideology data, and scenario overlays without formulas.
- Extract region counters, public opinion, faction ideology/order, effect expirations, and world market values.
- Add branch-aware scope status and stochastic-policy parsing/materialization.

## Non-goals

- Do not execute Economy or Unity completions.
- Do not change scheduler/cache semantics until phase 15.
- Do not expose market or ideology rows as goal/condition metrics.

## Affected files

- `tools/ti_parser_mechanics.py`
- `tools/build_runtime_catalogs.py` and packaged catalog data
- `tools/ti_parser_nation_projection.py` plus extraction/CLI wrappers
- focused registry, catalog, extraction, and plan-validation tests

## Implementation steps

1. Register Economy/Unity child rules, dependencies, scopes, evidence, and the Unity public-opinion resolver.
2. Extend generated catalog allowlists for audited constants and normalized faction/ideology templates; preserve package-only runtime and scenario hashes.
3. Extract exact save fields, including `accumulatedCoreMiningRegionTriggers` and `accumulatedCoreOilRegionTriggers`, with structured dependency failures.
4. Extend projection state/snapshots for public opinion, CP-owner ordering, cached/live effect inputs, market values, and region transform inputs.
5. Parse `stochasticPolicy.unityPublicOpinion`; materialize inherited pips across all segments and fail preflight when any possible Unity pip lacks `meanPath` opt-in.
6. Add `scopeStatus` and branch-scoped metric evidence without changing existing complete/incomplete behavior for blocking nation dependencies.

## Acceptance criteria

- Catalogs rebuild deterministically for Modern, 2003, and Broken Earth and verify package-only.
- All new supported/conditional rules have direct non-contract test evidence.
- Unity policy validation catches later/inherited segments and implicit current-pip plans.
- Existing unsupported Economy/Unity execution remains fail closed until their later phases.

## Validation commands

- `py -3 -m pytest -q tests/test_mechanics_registry.py tests/test_catalog_generators.py tests/test_runtime_catalogs.py`
- `py -3 -m pytest -q tests/test_nation_projection.py tests/test_nation_projection_cli.py`
- strict phase-plan validation

## Manual smoke tests

- Load the local CAL save through extraction and inspect public-opinion, ideology order, market values, and corrected region counters without hardcoding them.

## Rollback risks

- Catalog schema additions must not make runtime depend on installed game files.
- Optional world-market absence must not be confused with a missing nation dependency.

## Progress

- Pending.

## Decision log

- Market authority is scoped independently from nation/faction authority.
- Unity opt-in is a whole-materialized-plan preflight contract.

## Outcomes / Retrospective

- Pending.
