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

- Not started.

## Decision log

- No decisions recorded yet.

## Outcomes / Retrospective

- Not completed yet.
