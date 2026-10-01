# Phase 04: Build deterministic ZIP from committed allowlisted bytes.

## Goal

- Build deterministic ZIP from committed allowlisted bytes.

## Scope

- Builder/version, MIT LICENSE/data notice, distribution tests and docs.

## Non-goals

- No game formula changes, catalog regeneration, projection restructuring or external publication.

## Affected files

- Builder/version, MIT LICENSE/data notice, distribution tests and docs.

## Implementation steps

- Select explicit git ref; allowlist runtime assets; stable ZIP metadata and hash manifest; exclude private/developer artifacts.

## Acceptance criteria

- Same ref yields same ZIP; extracted runtime works; code license excludes game-derived data.

## Validation commands

- python -m pytest tests/test_beta_distribution.py -q

## Manual smoke tests

- Build committed ZIP and run --version/help outside checkout.

## Rollback risks

- No redistribution rights inferred; externally sharing data needs resolved permission.

## Progress

- Implemented deterministic commit-only ZIP allowlist, version and manifest hashes, MIT code license and separate data notice. Builder tests: 5 passed.

## Decision log

- Use user-approved beta contract; root integrates independent worker changes.

## Outcomes / Retrospective

- Builder tests cover deterministic bytes, selected commit vs dirty checkout, missing required assets and overwrite protection. Extracted ZIP acceptance follows in phase 5. External game-data redistribution conditions remain unresolved; no release is published.


## Extracted-runtime correction
The isolated ZIP run exposed standalone_catalog_integrity.py as a runtime dependency despite its non-ti_parser filename. It is now explicitly allowlisted and required. catalog-verify is source-checkout-only and reports a structured error from a runtime ZIP.
