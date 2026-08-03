# Phase 03: Regression and save-file verification

## Goal

- Prove standard behavior is stable and scenario-specific behavior matches game data.

## Scope

- Unit tests, full regression suite, CLI smoke tests, and installed-save checks.

## Non-goals

- Visual comparison against every in-game screen.

## Affected files

- scenario-focused tests and phase outcomes.

## Implementation steps

- Test scenario identity, overlay ordering, cache fingerprinting, and snapshot fields.
- Test default/2003/BE costs, custom IP scaling, CP maintenance, and Influence effects.
- Run the full test suite and real-save parser commands.

## Acceptance criteria

- Full tests pass.
- Broken Earth real-save outputs show cost 40, CP usage scaled by 0.7, and populated DLC research metadata.
- A standard save remains on standard rules; a 2003 save loads the Millennium overlay.

## Validation commands

- `python -m unittest discover -s tests -v`

## Manual smoke tests

- `python tools/ti_save_parser.py --help`

## Rollback risks

- Test-only phase; rollback removes regression coverage and recorded validation.

## Progress

- Complete.

## Decision log

- Real-save CP usage is asserted through its reported 0.7 multiplier rather than a fixed total,
  because the user's active autosave changed while verification was running.
- No local 2003 save was present, so installed 2003 templates were verified with a synthetic
  canonical scenario state in addition to unit coverage.

## Outcomes / Retrospective

- All 78 unit tests pass.
- CLI help smoke test passes and phased-plan validation reports no errors or warnings.
- A standard `2026Scenario` save selects one base template source, army cost 60, and CP multiplier 1.0.
- The active `BrokenEarthScenario` save selects the BE overlay, army cost 40, CP multiplier 0.7,
  and resolves `BSBE_ANewSpaceRace` as SpaceScience with cost 15000.
- Installed 2003 templates resolve `MissionToSpace` at cost 1000 and the initial Influence
  penalty at -0.25, rather than the base campaign's values.
