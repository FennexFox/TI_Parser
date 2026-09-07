# Phase 05: Fail-closed location-aware solar power

## Goal

- Prevent nominal module power from masquerading as location-aware solar output when required body or orbit template data is unavailable.

## Scope

- Detect active or projected `Solar_Power_Variable_Output` calculations.
- Require resolvable hab, body-chain, and orbital template context.
- Raise a specific calculation-data error instead of returning nominal power or visibility defaults.
- Recalculate player-hab power deficits in `ExitSave(3).gz` with complete location data.

## Non-goals

- Packaging a normalized body/orbit catalog in this phase.
- Reconstructing the game's automatic module load-shedding order.
- Changing non-solar nominal power semantics.

## Affected files

- `tools/ti_parser_core.py`
- `tools/ti_parser_hab.py`
- `tools/ti_save_parser.py`
- `tests/test_hab_power.py`
- `README.md`

## Implementation steps

- Add a specific solar calculation data exception shared by parser layers.
- Validate body/orbit template resolution before applying variable solar output.
- Remove nominal and visibility fallback paths for missing solar context.
- Add missing-collection, missing-body, missing-orbit, and valid-Mercury regression tests.
- Re-run live-save current/projected power audits and discard prior contaminated warning lists.

## Acceptance criteria

- A variable-output solar module cannot return nominal power when location templates are missing.
- Surface and orbital solar calculations identify the missing template in the error.
- Non-solar modules retain their existing nominal behavior.
- All tests pass and the live-save power warning list is regenerated with complete templates.

## Validation commands

- python -m unittest tests.test_hab_power -v
- python -m unittest discover -s tests -v

## Manual smoke tests

- Run the player-hab active/projected power audit for `ExitSave(3).gz` with resolved raw body/orbit templates.
- Repeat a solar power calculation with empty template mappings and verify an explicit error.

## Rollback risks

- Installations without raw body/orbit templates will now fail on solar hab calculations instead of producing plausible nominal values.

## Progress

- Completed.

## Decision log

- Use a specific exception now; a normalized packaged body/orbit catalog remains a separate follow-up.
- Validate only calculation-relevant solar context and keep ordinary fixed-output modules independent of location templates.
- Propagate `SolarPowerDataError` through forecast generation so a contaminated negative-power warning cannot be emitted.
- `ExitSave(3).gz` was no longer installed during final verification; use the current same-campaign `ExitSave.gz` for the replacement power audit.

## Outcomes / Retrospective

- Removed every nominal-output fallback reached by variable solar module power calculations.
- Added seven regression cases covering empty/missing body and orbit data, unresolved solar distance,
  summary/forecast propagation, and fixed-output compatibility; 130 tests pass and one optional fixture test skips.
- Recomputed the current Academy save with 495 body and 919 orbit templates: no current deficits,
  Bloomer is +600, Hong Bao is +111 current/+101 projected, and the only final projected deficit is
  non-solar 제108자원채굴단 at -15.
