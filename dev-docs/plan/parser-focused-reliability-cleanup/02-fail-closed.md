# Phase 02: Referenced definition fail-closed

## Goal

- Eliminate silent zero/default behavior when save state names a missing packaged definition.

## Scope

- Common resolver plus research, project analysis, hab, org, fleet, and saved-design named lookups.

## Non-goals

- Empty trait/org lists, zero-weight research slots, empty ship slots, and absent modifier sources remain valid.

## Affected files

- `tools/ti_parser_catalogs.py`, `tools/ti_save_parser.py`, relevant research/org/ship tests.

## Implementation steps

- Add `resolve_required_definition()` and delegate `RuntimeCatalogs.require()` to it.
- Replace required `.get(name, {})` paths in active modifier, facility, category-slot, fleet utility, and design/component calculations.
- Guard optional absence before invoking the resolver.
- Assert structured `kind`, `name`, `context`, `scenario`, and `reason` output.

## Acceptance criteria

- Missing active trait, applying org, active hab module, weighted research row, or referenced ship component raises `CalculationDependencyError`; optional absence does not.

## Validation commands

- python -m unittest tests.test_research_ui tests.test_project_analysis tests.test_ship_plan tests.test_parser_org -v
- python -m unittest discover -s tests -v

## Manual smoke tests

- Reproduce ComputerScientist, CERN, EnergyLab, and saved-design row deletion cases against synthetic saves.

## Rollback risks

- Over-strict resolution could reject genuinely optional state; every changed call site must have an explicit reference-presence guard.

## Progress

- Completed.
- Added the shared `resolve_required_definition()` boundary and delegated `RuntimeCatalogs.require()` plus save-parser named lookups to it.
- Converted active research modifiers/facilities, weighted active and hypothetical research slots, fleet design/utilities, saved ship components, shipyard rows, and named hab body locations to structured fail-closed resolution.
- Added ComputerScientist, CERN, EnergyLab, weighted research, fleet, saved component, and shipyard deletion regressions with complete `missingDependencies` field assertions.

## Decision log

- Case A (valid absence/fallback): empty trait/org lists, non-applying orgs, absent modifier sources, non-SpaceScience or docked fleets, `Empty` ship slots, zero-weight or locked/unused research slots, and the drive open-cycle derived single-engine alias fallback do not invoke required-definition resolution.
- Case B (explicit reference): active traits, applying orgs, active hab modules, named hab body locations, weighted named tech/project rows, undocked SpaceScience fleet designs/utilities, saved non-empty ship components, and packaged SpaceDock/Shipyard/Spaceworks rows must resolve or raise `CalculationDependencyError`.
- The prior hard-coded shipyard value fallback was removed; tier constants now identify packaged rows only.
- Org-plan's existing missing-template policy remains recommendation-ineligible rather than becoming a calculation dependency, because this phase does not change org-plan candidate semantics.
- `research_points_to_slot()` and hypothetical project calculation return the valid unused-slot result before resolving definitions when the selected slot weight is zero.

## Outcomes / Retrospective

- Focused validation passed: 64 tests across research UI, hab planning, project analysis, ship planning, and runtime catalogs.
- Full validation passed: 195 tests, with one expected skip for the unavailable local `ExitSave(3).gz` fixture.
- Synthetic deletion smoke cases now fail with structured `kind`, `name`, `context`, `scenario`, and `reason`; optional Case A paths remain normal results.
