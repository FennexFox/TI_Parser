# Phase 07: Lagrange point catalog coverage

## Goal

- Ensure every saved hab barycenter represented by `TILagrangePointState` resolves from the packaged location catalog.

## Scope

- Normalize all `TINavigableTemplate` Lagrange point rows into `data/location_catalog.json`.
- Version and validate the expanded catalog schema without treating Lagrange points as physical bodies.
- Add an explicit combined location mapping for display/identity lookups while keeping physical calculations on body-only data.
- Add diagnostics and regression coverage for `SunMarsL1` and `hab-slots --all`.

## Non-goals

- Packaging arbitrary non-location metadata from `TINavigableTemplate`.
- Inventing body radius, mass, atmosphere, or irradiation values for Lagrange points.
- Adding scenario-specific navigable overrides that are absent from the installed sources.

## Affected files

- `tools/build_location_catalog.py`
- `tools/ti_parser_core.py`
- `tools/ti_save_parser.py`
- `data/location_catalog.json`
- `tests/test_catalog_generators.py`
- `tests/test_parser_reliability.py`
- `README.md`

## Implementation steps

- Add `TINavigableTemplate.json` source fingerprinting and normalized Lagrange fields.
- Bump the catalog schema and add `navigables` count, rows, and name index.
- Validate row identity, required Lagrange fields, count/index integrity, and name collisions with physical bodies.
- Expose separate physical-body, navigable, and combined-location counts in diagnostics.
- Reproduce and then eliminate the `SunMarsL1` failure in full hab traversal.

## Acceptance criteria

- `load_location_catalog().navigable_templates` and `.location_templates` resolve `SunMarsL1`, while `.body_templates` does not.
- `hab_location_summary()` reports `SunMarsL1` and its max tier without requiring installed raw templates.
- `hab-slots --all` completes on the current Academy save.
- Existing Mercury solar and all physical-body/orbit calculations remain unchanged.

## Validation commands

- python -m unittest tests.test_catalog_generators tests.test_parser_reliability tests.test_hab_power -v
- python -m unittest discover -s tests -v

## Manual smoke tests

- Run `hab-slots --all` on the current `ExitSave.gz` and verify Susan B. Anthony is present.
- Compare current Academy variable-solar hab outputs before and after the schema expansion.

## Rollback risks

- Treating Lagrange rows as ordinary bodies could create plausible but false gravity or irradiation values.
- A name collision between body and navigable collections must be rejected rather than silently overwritten.

## Progress

- Completed.

## Decision log

- Keep `navigables` as a separate catalog collection and use the combined mapping only in natural-location identity/display paths.
- Preserve only source-native Lagrange identity, relation, orbit list, and max-hab fields; do not synthesize physical properties.
- Validate navigable-to-body and navigable-to-orbit foreign keys, orbit barycenters, collection indexes, and cross-collection name collisions.
- Existing L2 eclipse logic still identifies L2 from saved `templateName`; using packaged `lagrangeValue` directly remains a separate provenance improvement.

## Outcomes / Retrospective

- Bumped the catalog to schema 2 with 495 physical bodies, 117 Lagrange navigables, and 919 orbits.
- Kept physics consumers on the physical-only mapping and routed `hab_location_summary()` through the combined 612-location mapping.
- Added generator and loader regressions for Lagrange normalization, source provenance, collection separation, collisions, and a synthetic SunMarsL1 station.
- `hab-slots --all` now completes for all 59 Academy habs and reports Susan B. Anthony at SunMarsL1 with max tier 3 and no fabricated gravity.
- All 29 current Academy variable-solar habs retain identical current/projected power; Susan B. Anthony remains +23.
