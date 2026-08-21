# Phase 03: Ship scenario delta generation

## Goal

- Generate and select normalized scenario deltas for all ship component families.

## Scope

- Hulls, drives, plants, radiators, armor, batteries, heat sinks, utilities, and all weapon collections.

## Non-goals

- No new simulation fields or combat mechanics.

## Affected files

- `tools/build_runtime_catalogs.py`, runtime/generator tests, generated ship catalog and manifest.

## Implementation steps

- Normalize base and scenario-resolved collections with the same function.
- Diff resolved scenario rows against base and store only changed/added rows under collection keys.
- Include scenario ship files in provenance and reject cross-family weapon name collisions.
- Verify existing recursive overlay selection needs no runtime special case.

## Acceptance criteria

- Standard selects base drive; synthetic Broken Earth selects override and reports `overrideApplied: true`; unsupported scenarios remain errors.

## Validation commands

- python -m unittest tests.test_runtime_catalogs tests.test_catalog_generators tests.test_ship_plan -v

## Manual smoke tests

- Generate from synthetic templates and inspect the nested `scenarioOverrides.BrokenEarthScenario.drives` delta.

## Rollback risks

- Weapon rows are combined from several files; collision validation must run on both base and each resolved scenario.

## Progress

- Not started.

## Decision log

- No decisions recorded yet.

## Outcomes / Retrospective

- Not completed yet.
