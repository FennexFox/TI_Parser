# Phase 01: Reproduce and bound the mission-control omission

## Goal

- Reproduce the reported control-center omission and determine whether it is a
  current-state calculation error or a planning projection gap.

## Scope

- Trace the topbar and hab-plan MissionControl paths.
- Inspect Operations Center template values and active-module rules.
- Compare the latest local save's current MC with its construction queue.

## Non-goals

- Changing current MC semantics.
- Counting unfinished modules as currently active.
- Refactoring unrelated research or resource calculations.

## Affected files

- `tools/ti_save_parser.py`
- `tools/ti_parser_hab.py`
- `data/module_catalog.json`
- `tests/test_hab_plan.py`

## Implementation steps

- Confirm the canonical topbar path counts active positive-MC hab modules.
- Enumerate queued positive and negative MissionControl module deltas.
- Identify which planning call consumes current rather than projected MC.

## Acceptance criteria

- The observed gap is reproduced from the latest save.
- The intended current-state behavior and projected behavior are separated.
- Phase 2 has a bounded implementation target and test strategy.

## Validation commands

- `python -m unittest tests.test_parser_income tests.test_parser_hab tests.test_hab_plan -v`

## Manual smoke tests

- Run `topbar --details` logic against the latest loadable save.
- Enumerate active and queued Operations Centers and reconcile their MC values.

## Rollback risks

- Read-only discovery has no runtime rollback risk.

## Progress

- Completed code, catalog, graph, and live-save inspection.

## Decision log

- Current topbar MC remains current-state only; unfinished Operations Centers
  must not be folded into `capacity`.
- Habitat planning should consume a separately labeled current-queue projection.

## Outcomes / Retrospective

- The latest autosave has 15 unfinished Operations Centers (+60 capacity) and
  four unfinished Research Campuses (+4 usage), for a net projected MC headroom
  change of +56. `hab-plan` currently uses only current availability, so it
  omits the entire queued change.
