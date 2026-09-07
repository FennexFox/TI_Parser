# Phase 19: Exact BuildNavy coastal validity

## Goal

- Make `Military_BuildNavy` validity exact for nation UI and projection by reproducing the audited `TINationState.canBuildNavy` predicate.

## Scope

- Preserve serialized region `oceanType` in projection state and validate it fail closed.
- Treat `Yes` and `Seasonal` ocean types as coastal, matching `TIRegionState.isCoastal`.
- Precompute one exact `canBuildNavy` value for the shared priority-validity evaluator in both nation UI and projection.
- Cover the normal four-control-point path, the three-control-point PCGDP exception, existing-navies behavior, no-coast behavior, and missing-input behavior.
- Correct the resolved PR #2 review response after the implementation is pushed.

## Non-goals

- Do not change BuildNavy completion, army selection, naval combat, or seasonal movement mechanics.
- Do not add template catalog fields when the authoritative current value is already serialized in `TIRegionState.oceanType`.
- Do not infer a missing or unknown ocean type as inland.

## Affected files

- `tools/ti_parser_nation_validity.py`
- `tools/ti_parser_nation_projection.py`
- `tools/ti_save_parser.py`
- `tests/test_nation_validity.py`
- `tests/test_nation_projection.py`
- `tests/test_scenario_rules.py`
- `tests/test_nation_projection_real_save.py`
- `docs/nation_projection_mechanics_audit.md`

## Implementation steps

1. Add a shared value-only helper that implements the audited `canBuildNavy` predicate from military, army/navy counts, coastal-region count, control-point count, PCGDP, and the exception thresholds.
2. Add `ocean_type` to `RegionProjectionState` and require `TIRegionState.oceanType` during save extraction.
3. Precompute `canBuildNavy` in nation UI and projection and pass it to `evaluate_priority_validity`.
4. Add literal evaluator, projection, nation-UI, extraction, and opt-in real-save assertions.
5. Record the DLL evidence and run focused plus full-suite validation.

## Acceptance criteria

- A qualifying coastal nation with a convertible army reports BuildNavy valid in both nation UI and projection.
- A nation with no `Yes` or `Seasonal` region reports BuildNavy invalid.
- The three-control-point/40,000-PCGDP exception allows only the first navy.
- Missing or invalid `oceanType` produces unknown/structured dependency behavior, never a guessed boolean.
- Full automated regression remains green.

## Validation commands

- `python -m pytest -q tests/test_nation_validity.py tests/test_nation_projection.py tests/test_scenario_rules.py tests/test_nation_projection_cli.py`
- `python -m pytest -q`
- `$env:TI_PARSER_REAL_SAVE = '<local-save-path>'; python -m pytest -q tests/test_nation_projection_real_save.py; Remove-Item Env:TI_PARSER_REAL_SAVE`
- strict phase-plan validation over `docs/plan/nation_projection`

## Manual smoke tests

- Inspect the local Broken Earth save's `oceanType` distribution and confirm `Yes` and `Seasonal` are represented.
- Compare the Python decision table with the audited DLL `TINationState.canBuildNavy` and `TIRegionState.isCoastal` bodies.

## Rollback risks

- Treating `Seasonal` as non-coastal would diverge from `isCoastal`; tests must pin it as coastal.
- Counting only non-naval armies incorrectly as `numStandardArmies` would alter the DLL comparison; the equivalent Python condition is that at least one non-naval army exists.
- A partial UI-only implementation would leave projection fail-closed; both callers must share the same derived value.

## Progress

- Complete: added the shared audited predicate, UI/preprojection inputs, fail-closed `oceanType` extraction, and literal regression coverage.
- Passed focused validation: `81 passed, 13 subtests passed`.
- Passed full validation: `287 passed, 12 skipped, 25 subtests passed`.
- Strict plan validation passed for all 19 phase files.
- The opt-in real-save assertion passed against `C:\Users\techn\OneDrive\문서\My Games\TerraInvicta\Saves\ExitSave.gz`; the observed ocean-state distribution was `Yes: 236`, `No: 119`, and `Seasonal: 8`.
- That run exposed and fixed two independent projection wiring defects: a stale unsupported `hab_module_templates` keyword and a test helper that passed the `(bonuses, baseBonuses)` tuple where extraction requires the first mapping.
- Final review found that MissionControl also accepts a federation space program. DLL `ValidPriority` and `TIFederationState.SetSpaceProgramValue` confirm that any member's spaceflight program qualifies. UI and projection now share this derived input; unresolved references remain unknown. External member state is held fixed during projection.
- Restored the separate maximum-navy capacity calculation and added a public UI regression for a nation with only naval armies.
- Final validation: general suite `289 passed, 12 skipped, 25 subtests passed`; full opt-in ExitSave suite `11 passed, 16 subtests passed`; strict plan validation and diff whitespace checks passed.

## Decision log

- Use serialized `TIRegionState.oceanType`, not a generated template field, because it is the authoritative mutable state read by `TIRegionState.isCoastal`.
- Pass a precomputed `canBuildNavy` boolean to the pure evaluator, consistent with the existing `missionControlHasCapacity` contract.
- Keep unknown coastal state as `null` in nation UI and as a structured projection stop; do not reuse the old CP/PCGDP-only helper for live BuildNavy validity.

## Outcomes / Retrospective

- `Military_BuildNavy` is valid only when the game predicate is satisfied: military capability, a convertible live army, one `Yes` or `Seasonal` region, and either four control points or the first-navy three-control-point/40,000-PCGDP exception.
- BuildNavy completion remains outside this phase and remains unsupported by projection.
