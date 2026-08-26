# Phase 05: Real-save mechanics registry and catalog extension

## Goal

- Encode the DLL/template findings needed by the Broken Earth CAL compatibility work as shared rule metadata and package-only data, without copying executable formulas into the catalog.

## Scope

- Add or refine stable rules for economy-score/cache recomputation, persistent Economy fallback, priority validity, Government legitimize, the four Welfare stages, Mission Control placement, BuildArmy placement and maintenance, derived/CP periodic updates, and Population annual/monthly growth.
- Support static and conditional coverage metadata, registered resolver IDs, allowed effective-coverage results, test linkage, and per-execution provenance.
- Extend the generated nation development catalog with verified IP, Welfare, Army, cohesion, population, nation-template, region-template, map/environment, start-time, scenario-overlay, and source-hash data.
- Generate and verify Modern, 2003, and Broken Earth overlays while preserving package-only runtime behavior.
- Expand projection input/state extraction with the nation, region, army, and held-fixed world context required by later phases.
- Return `CalculationDependencyError` with field, source, and rule ID when a required save/template/effect value is absent.

## Non-goals

- Do not implement event execution or completion effects in this phase.
- Do not put Population, Welfare, IP, or cache algorithms into JSON.
- Do not implement Economy completion or Unity public-opinion effects.
- Do not commit the primary local save, current CAL values, game object IDs, or installation paths.

## Affected files

- `tools/ti_parser_mechanics.py`
- `tools/build_runtime_catalogs.py`
- `tools/ti_save_parser.py`
- `tools/ti_parser_nation_projection.py`
- `data/nation_development_catalog.json`
- `data/catalog_manifest.json`
- `docs/nation_projection_mechanics_audit.md`
- `tests/test_mechanics_registry.py`
- `tests/test_catalog_generators.py`
- `tests/test_runtime_catalogs.py`
- `tests/test_package_only_runtime.py`

## Implementation steps

1. Register the new stable rule IDs and preserve the meaning of existing IDs; update implementation revisions, DLL symbols/callers, source hashes, data dependencies, and tests rather than renaming compatible rules.
2. Add `coverageMode: "static"` for fixed rules and `coverageMode: "conditional"` plus a registered resolver and allowed outcomes for branch-sensitive rules. Make registry validation prove every resolver result closes to `exact`, `expected`, `aggregateOnly`, or `unsupported`.
3. Record the verified DLL call order and source symbols in the audit while keeping formula execution exclusively in Python.
4. Extend catalog generation with data-only global values and resolved base/scenario nation, region, map, and start-time overlays for Modern, 2003, and Broken Earth.
5. Regenerate the nation catalog and manifest; assert installed-source parity during generation tests and assert no installed-game access at runtime.
6. Extend projection extraction/state types for ordered regions, dynamic regional flags/counters/caps, nation timing/cache inputs, complete army identity/deployment fields, and a greenhouse-gas snapshot marked `heldFixedWorldContext`.
7. Make every required value fail closed with a structured dependency error rather than supplying a compiled or zero default.

## Acceptance criteria

- Registry, audit, tests, and later diagnostics can reference the same stable rule IDs and implementation revisions.
- Conditional rules declare a known resolver and a closed allowed-outcome set.
- Catalog JSON contains only consumed data/provenance and supports all three scenario overlays.
- Runtime projection imports and uses packaged data with no DLL/template filesystem dependency.
- Ordered region and army state can represent CAL without hardcoded save values.
- Missing required inputs report field, source, and mechanic rule ID.

## Validation commands

- py -3 -m unittest tests.test_mechanics_registry
- py -3 -m unittest tests.test_catalog_generators tests.test_runtime_catalogs tests.test_package_only_runtime
- py -3 tools/ti_save_parser.py catalog-verify --catalog nation-development
- py -3 C:/Users/techn/.codex/skills/phased-issue-implementation/scripts/phase_plan_helper.py validate --strict --plan-dir docs/plan/nation_projection

## Manual smoke tests

- Generate each Modern, 2003, and Broken Earth nation-development payload from installed inputs and compare its source hashes and overlay provenance with the packaged artifact.
- With `TI_PARSER_REAL_SAVE` pointing to the local `ExitSave.gz`, extract CAL into projection state and inspect ordered regions, one existing army, campaign time, PCGDP tracker inputs, and held-fixed climate context without serializing save-specific values into tracked files.
- Temporarily remove one required extracted field in a local copy of the input fixture and confirm the error names the field, source, and rule ID.

## Rollback risks

- Registry schema changes affect integrity checks and diagnostics consumers; rollback must keep registry code, generated catalog, manifest, audit, and tests in one atomic phase.
- Scenario overlay bugs can silently select base data. Source hashes and explicit scenario keys are required to make rollback and drift visible.
- Extraction fields may expose previously tolerated malformed saves; retain structured errors and avoid broad fallback defaults.

## Progress

- Completed: registry coverage resolvers, shared test metadata, packaged scenario data, strict extraction dependencies, and expanded projection state are implemented.

## Decision log

- Coverage is an execution result when a rule is conditional; the registry records the resolver contract rather than a mechanic-wide pessimistic minimum.
- Catalogs store data and source provenance only. Python remains the single executable location for mechanics formulas.
- The local Broken Earth save is opt-in validation input and is never a committed fixture or production default.

## Outcomes / Retrospective

- Registry validation now closes conditional MC, BuildArmy, and monthly CP reconciliation paths and verifies that supported tests declare the same stable rule IDs.
- The regenerated package contains Modern, 2003, and Broken Earth nation/region/map/start/bilateral data and source hashes without moving mechanics formulas into JSON.
- Catalog, manifest, runtime-loader, and package-only regression tests pass against the generated package.
