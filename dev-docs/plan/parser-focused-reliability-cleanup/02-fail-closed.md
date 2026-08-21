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

- Not started.

## Decision log

- No decisions recorded yet.

## Outcomes / Retrospective

- Not completed yet.
