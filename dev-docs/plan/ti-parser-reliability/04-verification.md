# Phase 04: Diagnostics and ExitSave regression verification

## Goal

- Lock reliability behavior with synthetic and live-save regression coverage and documentation.

## Scope

- Missing-data, player, state, MC, CP, mining, forecast, diagnostics, and full-suite validation.

## Non-goals

- Shipping the large save fixture in the repository.

## Affected files

- `tests/test_parser_reliability.py`, affected existing fixtures, `README.md`, plan files.

## Implementation steps

- Add focused tests and optional local ExitSave regression.
- Update older synthetic tests to use explicit faction overrides or player metadata.
- Run the full suite and live diagnostic smoke commands.

## Acceptance criteria

- All tests pass and live-save outputs satisfy requested regression bounds.

## Validation commands

- python -m unittest discover -s tests -v

## Manual smoke tests

- Compare current/default, diagnostic, and forecast outputs for `ExitSave(3).gz`.

## Rollback risks

- CI skips the real-save regression when the local copyrighted fixture is absent.

## Progress

- Completed.

## Decision log

- Keep the save external; the regression auto-runs when it is installed in a standard save directory.

## Outcomes / Retrospective

- Added 12 reliability tests; all 124 tests completed successfully.
