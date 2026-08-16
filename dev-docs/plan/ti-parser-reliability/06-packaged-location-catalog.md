# Phase 06: Packaged body and orbit location catalog

## Goal

- Remove runtime dependence on installed body/orbit templates while preserving location-aware solar, gravity, irradiation, construction, and mining calculations.

## Scope

- Generate normalized `TISpaceBodyTemplate` and `TIOrbitTemplate` fields into `data/location_catalog.json`.
- Add a validated, cached runtime loader and catalog provenance diagnostics.
- Route every parser body/orbit lookup through the packaged catalog.
- Fail closed on a missing, corrupt, empty, or incompatible catalog.
- Verify the packaged data reproduces raw-template solar results for the current Academy campaign.

## Non-goals

- Packaging dynamic effect templates.
- Reconstructing automatic module load shedding.
- Guessing future scenario overrides that are absent from the installed source templates.

## Affected files

- `tools/build_location_catalog.py`
- `tools/ti_parser_core.py`
- `tools/ti_save_parser.py`
- `data/location_catalog.json`
- `tests/test_catalog_generators.py`
- `tests/test_hab_power.py`
- `tests/test_parser_reliability.py`
- `README.md`

## Implementation steps

- Define a versioned catalog with source fingerprints, normalized body/orbit rows, and name indexes.
- Validate identity, row uniqueness, field types, schema version, and non-empty body/orbit collections.
- Replace all runtime `TISpaceBodyTemplate.json` and `TIOrbitTemplate.json` loads with the packaged loader.
- Expose path, schema, row counts, and source fingerprints under diagnostics.
- Add generator, loader, missing-data, and packaged-solar regression tests.

## Acceptance criteria

- Normal parser execution does not read raw body/orbit template files.
- Variable solar power works without an installed templates directory when the packaged catalog is present.
- Missing or invalid packaged location data raises an explicit location-catalog error rather than returning nominal or zero values.
- Existing fixed-output power behavior and location-aware Mercury output remain unchanged.

## Validation commands

- python -m unittest tests.test_catalog_generators tests.test_parser_reliability tests.test_hab_power -v
- python -m unittest discover -s tests -v

## Manual smoke tests

- Run a packaged-catalog power audit over every player hab in the current `ExitSave.gz`.
- Compare Bloomer and Hong Bao current/projected power with the prior complete raw-template audit.
- Search runtime parser code for direct body/orbit JSON loads.

## Rollback risks

- A game update that changes body/orbit data requires regenerating and reviewing the packaged catalog.
- A future scenario-specific body/orbit override must be explicitly incorporated into catalog generation instead of silently overlaid at runtime.

## Progress

- Completed.

## Decision log

- Use one combined location catalog because body and orbit values form a single dependency graph for solar and gravity calculations.
- Keep rows in the existing template-shaped flat form so calculation functions do not gain a second interpretation path.
- Treat raw template files as explicit build inputs only; there is no runtime fallback.
- Preserve raw numeric precision, derive normalized mean/max/hill radii, and record SHA-256 source fingerprints.
- Preserve synchronous-orbit metadata and reproduce the game's stationary-orbit radius formula; unresolved solar geometry is fatal.
- Package no scenario overrides because the installed 2003 and Broken Earth sources contain none; a future non-empty override set fails until explicit scenario selection is implemented.

## Outcomes / Retrospective

- Packaged 495 body and 919 orbit rows in one versioned, indexed catalog.
- Removed all raw body/orbit loads from normal parser execution and added location-catalog provenance to diagnostics.
- Added generator, loader integrity, Mercury packaged-solar, synchronous-orbit, and unresolved-geometry regressions.
- Compared all 29 variable-solar player habs in the current Academy save against raw-template calculations with no current/projected power differences.
- Confirmed Bloomer at +600, Hong Bao at +111 current/+101 projected, no current player-hab deficits, and only 제108자원채굴단 at -15 in the final queued projection.
