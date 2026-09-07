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

- Completed.
- The ship generator now resolves each component family against every discovered scenario directory, validates the resolved weapon namespace, and emits recursive minimal deltas.
- Synthetic Broken Earth drive overrides exercise nested field preservation and exact runtime selection.
- Installed 0.4.77 Dark Skies scenario directories contain no ship component overlay files, so the regenerated packaged ship payload remains byte-identical while the generator is ready for future deltas.

## Decision log

- Delta generation compares fully resolved, normalized scenario collections with normalized base collections; omitted raw fields therefore inherit base values before diffing.
- Weapon collision validation runs after resolving all six weapon families for base and for each scenario, so an overlay cannot introduce an ambiguous combined runtime key.
- Source provenance includes only scenario ship files that exist; scenario metadata still records the supported overlay roots.

## Outcomes / Retrospective

- Focused validation passed: 32 tests across runtime catalogs, catalog generators, and ship planning.
- Full validation passed: 198 tests, with one expected local-fixture skip.
- Synthetic generation proves a nested Broken Earth drive delta, base preservation, `overrideApplied` diagnostics, overlay source hashing, duplicate-row rejection, cross-family weapon collision rejection, and deterministic regeneration.
- Authoritative local regeneration retained ship payload fingerprint `1327d1ef9a25f413a23073455e0035dceaac29eafec04c0f9fa2dcf286a0964b` because the installed scenario templates currently add no ship rows.
