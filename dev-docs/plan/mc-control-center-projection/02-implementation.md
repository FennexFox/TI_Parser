# Phase 02: Add current-queue mission-control projection

## Goal

- Represent queued MissionControl capacity and usage changes explicitly and
  feed projected availability to habitat planning.

## Scope

- Add a helper that aggregates unfinished hab-module deltas for the faction.
- Treat a completed prior template as the current MC source during an upgrade.
- Add `projectedAfterCurrentQueue` to the MissionControl topbar row.
- Use projected queue availability for candidate feasibility and suggested fill.

## Non-goals

- Altering current capacity/usage values or excess-MC research.
- Predicting completion dates, power failures, decommissioning, or queue order.
- Changing non-MC habitat plan scoring.

## Affected files

- `tools/ti_save_parser.py`
- `tools/ti_parser_hab.py`
- `tests/test_hab_plan.py`
- `tests/test_research_ui.py`
- `README.md`

## Implementation steps

- Compute target and prior positive capacity and negative usage per unfinished
  record, then sum their deltas.
- Reuse the same current/prior MC rule in topbar and research-breakdown paths.
- Reapply `MissionControlDisruption_PCT` to the full projected pre-effect
  capacity instead of adding raw queue capacity after effects.
- Ignore module records on sectors explicitly not owned by the hab faction.
- Derive projected capacity, usage, and non-negative available headroom from the
  current topbar values.
- Preserve the current fields and add the projection as a nested diagnostic.
- Prefer projected availability in `hab_plan_row()` while falling back to the
  current field for callers that provide an older topbar shape.

## Acceptance criteria

- An unfinished Operations Center contributes +4 projected capacity, not current
  capacity.
- A completed Operations Center being upgraded contributes its current +4 until
  the Command Center replaces it.
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

- Completed implementation and focused regression tests.

## Decision log

- The projection is split into capacity and usage deltas rather than exposing
  only a signed net, so the result remains auditable.
- Current MC chooses the target template only when it is active; otherwise an
  unfinished upgrade with `priorModuleCompleted` uses the prior template.
- The projection exposes both raw `habCapacityChange` and effective
  `capacityChange`, with `effectsChange` explaining the difference.
- Review found and closed effect-consistency gaps for multiplicative and fixed MC
  effects in both topbar projection and research/excess-MC calculation.

## Outcomes / Retrospective

- Topbar current MC now restores upgrading Operations Centers, exposes queued
  capacity/usage/headroom changes, and supplies the projected available value to
  habitat and prospective-project planning. Research details now include MC-only
  habs and their current MC.
