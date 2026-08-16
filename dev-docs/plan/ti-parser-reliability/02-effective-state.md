# Phase 02: Unified hab module effective-state calculations

## Goal

- Use one lifecycle resolver across MC, power, resources, crew, and bonuses.

## Scope

- Construction, upgrade, unpowered, destroyed, decommissioning, foreign-sector, disabled, and damaged states.

## Non-goals

- Exact future power-management priority ordering.

## Affected files

- `tools/ti_parser_hab.py`, `tools/ti_save_parser.py`, hab/research/reliability tests.

## Implementation steps

- Implement `get_effective_module_state(record, at_date)`.
- Route operational/crew/MC template selection through the resolver.
- Honor `ConsumesMCWhenUnpowered` and fail on unknown catalog templates.
- Verify installed `TIHabState.GetNetCurrentMonthlyIncome` and `TIHabModuleState.crew` code.

## Acceptance criteria

- Current and future state transitions match installed game-code semantics and subsystem tests.

## Validation commands

- python -m unittest discover -s tests -v

## Manual smoke tests

- Compare current resource and power results for upgrading modules in `ExitSave(3).gz`.

## Rollback risks

- Over-generalizing prior-module behavior would incorrectly keep power/production active.

## Progress

- Completed.

## Decision log

- Prior-module continuation is metric-specific in the game: MC retains the prior template, while
  resource/power active paths do not. The common model records both selectors explicitly.

## Outcomes / Retrospective

- Current volatile balance remains -34.212962/month; the previous resource semantics were confirmed.
