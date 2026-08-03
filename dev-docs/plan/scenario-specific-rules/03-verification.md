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
- Broken Earth real-save outputs show cost 40, CP usage near 42.690437, and populated DLC research metadata.
- A standard save remains on standard rules; a 2003 save loads the Millennium overlay.

## Validation commands

- `python -m unittest discover -s tests -v`

## Manual smoke tests

- `python -m tools.ti_parser_cli --help`

## Rollback risks

- Test-only phase; rollback removes regression coverage and recorded validation.

## Progress

- Not started.

## Decision log

- No decisions recorded yet.

## Outcomes / Retrospective

- Not completed yet.
