# Phase 05: Ship runtime migration

## Goal

- Package ship component data and make planner/simulation/upkeep strict and standalone.

## Scope

- Hull, drive, power plant, radiator, armor, battery, heat sink, utility, weapon, and effect migration.

## Non-goals

- Do not add combat simulation or change documented shortlist heuristics.

## Affected files

- Ship builder/catalog, save parser ship functions, ship and package-only tests.

## Implementation steps

- Preserve empty optional slots; fail on every non-empty referenced component whose row is missing.
- Replace empty catalog warnings with structured incomplete failures.
- Use packaged hull data for ship Money upkeep.

## Acceptance criteria

- Existing ship tests and new missing-component/package-only tests pass.

## Validation commands

- python -m unittest discover -s tests -v

## Manual smoke tests

- Compare one saved design's mass, acceleration, delta-v, heat, cost, time, MC, and upkeep to raw-reference output.

## Rollback risks

- Component families overlap utility modules; one canonical ship row must serve research and simulation consumers.

## Progress

- Complete: hull, propulsion, thermal, armor, utility, weapon, and effect data are packaged and used by planning/simulation/upkeep.

## Decision log

- `Empty` component slots are optional; any other referenced missing component raises a structured dependency error.

## Outcomes / Retrospective

- Real-save ship-plan and saved-design raw/package simulation parity both pass.
