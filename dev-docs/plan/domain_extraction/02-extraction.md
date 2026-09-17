# Phase 02: Move remaining implementation to domain modules

## Goal

- Move remaining implementation to domain modules

## Scope

- tools/ti_save_parser.py, new domain modules, tests and README

## Non-goals

- Mechanics changes, output redesign, generator changes, performance claims.

## Affected files

- tools/ti_save_parser.py, new domain modules, tests and README

## Implementation steps

- Move exact bodies; add explicit imports and compatibility exports; retarget mock ownership; verify AST/signature parity and full tests.

## Acceptance criteria

- Facade owns only entry functions, domain modules do not import facade, behavior tests pass.

## Validation commands

- python -B -m pytest -q -p no:cacheprovider

## Manual smoke tests

- Compare baseline public signatures and real-save command output; verify independent module imports.

## Rollback risks

- Cross-module references and test patch targets must follow ownership; revert the phase as a unit.

## Progress

- Not started.

## Decision log

- Existing graph is stale; use its relationships as navigation and current AST/source as authority.

## Outcomes / Retrospective

- Pending.
