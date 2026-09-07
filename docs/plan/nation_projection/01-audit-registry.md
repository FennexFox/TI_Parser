# Phase 01: Mechanics audit registry and data catalog

## Goal

- Establish the shared mechanics registry and generated nation development catalog before calculation code is added.

## Scope

- Audit installed DLL symbols for daily investment, completion order, monthly movement, and Advise.
- Add registry metadata, integrity validation, diagnostics serialization, and stable constants.
- Extend runtime catalog generation/manifest/loading with priority costs, global constants, overlays, and source hashes.

## Non-goals

- No projection state mutation or CLI command.
- No executable formulas in JSON.

## Affected files

- `tools/ti_parser_mechanics.py`
- `tools/build_runtime_catalogs.py`
- `tools/ti_parser_catalogs.py`
- `data/nation_development_catalog.json`
- `data/catalog_manifest.json`
- `tests/test_mechanics_registry.py`
- runtime catalog generator/loading tests

## Implementation steps

1. Encode stable rule IDs and audit metadata confirmed from installed symbols.
2. Validate IDs, revisions, coverage, test links, and diagnostics resolution.
3. Extract template/config values into a scenario-aware catalog with DLL/template hashes.
4. Regenerate packaged catalogs and update loader properties/default file list.
5. Add package-only and parity tests.

## Acceptance criteria

- Duplicate/unregistered rule IDs fail validation.
- Supported rules have test IDs; diagnostics entries resolve through the registry.
- Nation development data loads without an installed game and contains no algorithm source.

## Validation commands

- py -3 -m unittest discover -s tests -p 'test_*.py'

## Manual smoke tests

- Run registry tests and build the catalog to a temporary directory; compare packaged hashes.

## Rollback risks

- Manifest changes require regenerating all runtime catalog metadata together; rollback is a phase commit revert.

## Progress

- Completed: registry, generated catalog, runtime loader, verifier, and packaged data are implemented.

## Decision log

- Verified `TINationState.DailyNationUpdate`, `ControlPointWeightsTotalToPriorityIP`, `ProcessPrioritySpending`, `MonthlyNationUpdate`, and `GetAdvisingScore` in the installed DLL; exact symbols/hashes will be stored as provenance, not duplicated executable formulas.
- The current installed game data regenerated effect and claim catalog provenance together with the new catalog so the bundle manifest remains internally consistent.

## Outcomes / Retrospective

- Registry IDs/revisions/DLL symbols now form the shared provenance layer. `nation_development_catalog.json` contains only allowlisted costs/constants/overlays and source hashes; algorithms remain in Python.
