# Phase 04: Campaign-start GDP CP-maintenance fix

## Goal

- Reconstruct BE control-point usage with the same campaign-start GDP scale as the game.

## Scope

- Read the saved fixed GDP scale used by `TINationState.ControlPointMaintenanceCost`.
- Apply that scale before the existing exponent, per-nation CP division, and scenario modifier.
- Add focused unit coverage and verify the current BE save reports cap 341 and rounded usage 342.

## Non-goals

- Change control-point cap composition.
- Change army costs, template overlays, or other scenario calculations.
- Store or commit a user save as a test fixture.

## Affected files

- `tools/ti_save_parser.py`
- `tests/test_scenario_rules.py`
- `dev-docs/plan/scenario-specific-rules/*`

## Implementation steps

- Add a helper that resolves `fixedPCGDPToRaiseBaseCPMaintenanceCostBy1`, derives it from
  campaign-start GDP when possible, and otherwise retains the legacy 1-billion fallback.
- Pass the resolved scale into each nation's control-point maintenance calculation.
- Expose the resolved GDP scale in calculation components for diagnosis.
- Replace the multiplier-only regression with assertions for both GDP scaling and the BE modifier.

## Acceptance criteria

- The current BE save produces CP cap 341 and CP usage 342.054941, which rounds to 342.
- A supplied positive saved GDP scale is used exactly once before exponentiation.
- The BE 0.7 scenario modifier remains applied exactly once.
- Missing scale metadata preserves the prior 1-billion fallback behavior.
- The full unit test suite passes.

## Validation commands

- `python -m unittest tests.test_scenario_rules -v`
- `python -m unittest discover -s tests -v`
- `python tools/ti_save_parser.py --compact topbar`

## Manual smoke tests

- Confirm `controlPointMaintenance.cap` rounds to 341 and `.usage` rounds to 342 on the
  newest local `BrokenEarthScenario` save.

## Rollback risks

- Reverting the GDP-scale lookup restores materially understated CP usage in scenarios whose
  campaign-start GDP scale differs from 1 billion.

## Progress

- Complete.

## Decision log

- The installed assembly is authoritative: `TINationState.ControlPointMaintenanceCost` divides
  GDP by `TIGlobalValuesState.PCGDPToRaiseBaseCPMaintenanceCostBy1` before applying exponent 0.6.
- The current save stores the resolved value as
  `fixedPCGDPToRaiseBaseCPMaintenanceCostBy1 = 323869500.0`.
- The existing cap result is correct and remains unchanged.

## Outcomes / Retrospective

- The parser now reads the save's fixed campaign-start GDP scale and reports it in
  `controlPointMaintenance.components.gdpScale`.
- The newest local BE save reports cap 341.0 and usage 342.054941, matching the game's
  displayed 341/342 values.
- Standard `2026Scenario` saves inspected during verification retain the 1-billion scale.
- All 81 unit tests pass, the focused scenario suite passes, plan validation passes, and
  `git diff --check` reports no whitespace errors.
