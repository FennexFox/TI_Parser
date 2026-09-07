# Phase 03: CP capacity and event-based resource forecast

## Goal

- Make CP capacity auditable and add completion-date resource forecasts.

## Scope

- CP components/effects, mining formula samples, event rows, first sustained surplus helper.

## Non-goals

- Full strategic simulation after the current saved construction queue.

## Affected files

- `tools/ti_save_parser.py`, `tools/ti_parser_hab.py`, CLI, reliability tests.

## Implementation steps

- Validate calculation-relevant effect templates and expose operation/value rows.
- Return a CP-cap breakdown whose sum equals cap.
- Recompute faction-hab production/support after each `completionDate`.
- Report module events, change, impacted power, status, warnings, and first sustained surplus.

## Acceptance criteria

- CP cap exceeds 500 for ExitSave; volatile transition occurs at the saved mining completion event.

## Validation commands

- python -m unittest discover -s tests -v

## Manual smoke tests

- Run `topbar --diagnostics --forecast-resource Volatiles` on `ExitSave(3).gz`.

## Rollback risks

- Forecast target modules are assumed powered unless power diagnostics disprove feasibility.

## Progress

- Completed.

## Decision log

- Negative projected hab power does not invent an activation order; it marks forecast incomplete.

## Outcomes / Retrospective

- ExitSave CP is 525 and volatile first sustained surplus is 2123-10-17T13:18:05.229.
