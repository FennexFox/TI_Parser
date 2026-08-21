# Phase 01: Canonical LF catalog artifacts

## Goal

- Make every generated catalog byte-for-byte stable across CRLF and LF hosts.

## Scope

- Canonical UTF-8/LF writers, `.gitattributes`, six manifest catalogs, module/location JSON serialization, integrity error typing, portability regressions.

## Non-goals

- No catalog schema migration or new payload fields.

## Affected files

- `.gitattributes`, `tools/catalog_utils.py`, `tools/build_runtime_catalogs.py`, `tools/ti_parser_catalogs.py`, generated `data/*.json`, catalog tests.

## Implementation steps

- Write JSON with `write_bytes(canonical_text.encode("utf-8"))` and one trailing LF.
- Separate catalog integrity failures from unsupported scenario selection at calculation boundaries.
- Regenerate research first, then runtime catalogs and manifest from the local authoritative inputs.
- Add LF-only, actual-byte SHA, normalized-copy load, and deterministic double-generation tests.

## Acceptance criteria

- No generated catalog contains CRLF; manifest hashes match file bytes and an LF-normalized copy loads every supported scenario.

## Validation commands

- python -m unittest tests.test_runtime_catalogs tests.test_catalog_generators tests.test_research_catalog -v
- python -m unittest discover -s tests -v

## Manual smoke tests

- Compare manifest, worktree, and `git show` SHA values; verify `git ls-files --eol` reports LF attributes.

## Rollback risks

- Regeneration touches large tracked files; stage only canonical generated artifacts and verify payload fingerprints are unchanged except for intended metadata.

## Progress

- Completed.
- Added canonical UTF-8/LF byte writers with exactly one trailing LF and applied them to JSON/text catalog output.
- Added LF enforcement for tracked catalog JSON and regenerated research, module/location serialization, the six runtime catalogs, and the manifest from the local authoritative game inputs.
- Added distinct catalog-integrity and unsupported-scenario failures, including calculation-boundary dependency mapping.
- Applied the same dependency-kind mapping to snapshot and org-plan bundle loading, not only direct calculation commands.
- Added writer, actual-byte SHA, normalized-copy, supported-scenario, corruption, and calculation-boundary regressions.

## Decision log

- `CatalogIntegrityError` represents malformed envelopes, fingerprints, manifests, hashes, and missing catalog rows/files; `UnsupportedCatalogScenarioError` represents exact scenario selection failure.
- Calculation boundaries map integrity failures to a `catalog-integrity` dependency and unsupported scenarios to a `scenario` dependency so callers can distinguish damaged packaged data from an unsupported save.
- `.gitattributes` applies `text eol=lf` to `data/*.json`; the writers still normalize bytes themselves so generation is stable independently of Git checkout configuration.
- Module schema 1 and location schema 2 remain unchanged. Their generated payloads remain unchanged; only canonical trailing-LF serialization changed.
- Runtime catalog schema versions and payload fingerprints remain unchanged. The manifest SHA values and bundle fingerprint changed because they now describe the canonical LF bytes.

## Outcomes / Retrospective

- Focused validation passed: 36 tests across runtime catalogs, generators, research catalog, package-only boundaries, snapshot, and org-plan.
- Full validation passed: 183 tests, with one expected skip for the unavailable local `ExitSave(3).gz` fixture.
- Manual portability smoke verified all six manifest SHA-256 values against actual LF bytes and loaded all six supported scenarios from an LF-normalized copy.
- `git ls-files --eol data` reports `i/lf`, `w/lf`, and `attr/text eol=lf` for every generated catalog.
- No schema migration or payload-field expansion was introduced in this phase.
