# Phase 03: Regression and live-save verification

## Goal

- Prove the queue projection fixes the reported planning omission without
  regressing current MC or unrelated parser behavior.

## Scope

- Focused unit tests, full test discovery, plan validation, and a live-save smoke
  test.

## Non-goals

- Feature expansion beyond the reported MC projection gap.
- Generated catalog changes.

## Affected files

- `tests/test_hab_plan.py`
- `tests/test_research_ui.py`
- Phase documents in this directory

## Implementation steps

- Run focused tests after implementation.
- Run the complete unittest suite.
- Recalculate latest-save current and projected MissionControl.
- Record validation results and remaining assumptions.

## Acceptance criteria

- All tests pass.
- Current topbar MC remains unchanged for the same save.
- Projected MC includes queued Operations Centers and consuming modules.
- `hab-plan` reports and uses projected MC availability.

## Validation commands

- `python -m unittest tests.test_hab_plan tests.test_research_ui -v`
- `python -m unittest discover -s tests -v`
- `python C:\Users\techn\.codex\skills\phased-issue-implementation\scripts\phase_plan_helper.py validate --plan-dir dev-docs\plan\mc-control-center-projection`

## Manual smoke tests

- Latest-save projection reconciles module counts and signed MC changes.
- Current capacity/usage still match the pre-change result.

## Rollback risks

- The live-save smoke test depends on an unlocked, readable autosave and local
  Terra Invicta templates; unit tests provide deterministic coverage if it is
  unavailable.

## Progress

- Complete.

## Decision log

- Current and projected MC are verified separately: unfinished new construction
  never inflates current capacity, while a completed prior module remains current
  during an upgrade.
- Both multiplicative and `SetToFixedValue` MC effects are regression-tested
  because adding a raw queue delta after effects would produce incorrect planning
  headroom.
- Live autosave values are recorded as a point-in-time smoke test because the
  game may update `Autosave.gz` while verification is running.

## Outcomes / Retrospective

- All 112 tests pass, including 13 focused research/topbar MC tests; Python
  compilation, diff checks, and phased-plan validation also pass.
- At verification time the latest autosave reports current MC 100 capacity / 99
  usage / 1 available in both topbar and research. Its current queue projects 160
  capacity / 103 usage / 57 available: 15 Operations Centers add 60 capacity and
  queued consuming modules add 4 usage, for +56 headroom.
- Historical save `Resistsave00604_2038-6-16.gz` now counts the three completed
  Operations Centers that remain active during Command Center upgrades. Hab MC
  rises from the old calculation's 152 to 164, restoring the missing 12 current
  MC; the projected upgrade delta is then +18 rather than double-counting +30.
- Topbar and research agree on the historical save's current 446 capacity / 432
  usage / 14 available.
- Independent review findings for MC effects and foreign-sector ownership were
  resolved and covered by deterministic tests.
