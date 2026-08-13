# Phase 02: Add current-queue mission-control projection

## Goal

- Represent queued MissionControl capacity and usage changes explicitly and
  feed projected availability to habitat planning.

## Scope

- Add a helper that aggregates unfinished hab-module deltas for the faction.
- Add `projectedAfterCurrentQueue` to the MissionControl topbar row.
- Use projected queue availability for candidate feasibility and suggested fill.

## Non-goals

- Altering current capacity/usage values or excess-MC research.
- Predicting completion dates, power failures, decommissioning, or queue order.
- Changing non-MC habitat plan scoring.

## Affected files

- `tools/ti_save_parser.py`
- `tests/test_hab_plan.py`
- `tests/test_research_ui.py`

## Implementation steps

- Compute target and prior positive capacity and negative usage per unfinished
  record, then sum their deltas.
- Derive projected capacity, usage, and non-negative available headroom from the
  current topbar values.
- Preserve the current fields and add the projection as a nested diagnostic.
- Prefer projected availability in `hab_plan_row()` while falling back to the
  current field for callers that provide an older topbar shape.

## Acceptance criteria

- An unfinished Operations Center contributes +4 projected capacity, not current
  capacity.
- An unfinished Research Campus contributes +1 projected usage.
- Completed, destroyed, and decommissioning records do not enter the queue
  projection.
- Habitat planning receives the queue-projected available MC value.

## Validation commands

- `python -m unittest tests.test_hab_plan tests.test_research_ui -v`

## Manual smoke tests

- Inspect the latest save's MissionControl row and confirm a +60 capacity, +4
  usage, +56 available projection without changing current capacity.

## Rollback risks

- Consumers that rigidly validate topbar keys may need to accept the new nested
  projection; existing fields and meanings remain unchanged for rollback safety.

## Progress

- Not started.

## Decision log

- The projection is split into capacity and usage deltas rather than exposing
  only a signed net, so the result remains auditable.

## Outcomes / Retrospective

- Not completed yet.
