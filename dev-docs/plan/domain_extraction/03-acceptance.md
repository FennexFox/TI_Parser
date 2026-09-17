# Phase 03: Verify final compatibility from checkout and committed export

## Goal

- Verify final compatibility from checkout and committed export

## Scope

- Architecture/import regression tests and plan records

## Non-goals

- Mechanics changes, output redesign, generator changes, performance claims.

## Affected files

- Architecture/import regression tests and plan records

## Implementation steps

- Run full tests, fresh export and real-save CLI parity against baseline; record exact results.

## Acceptance criteria

- Tests and parity pass; reviewed commits and clean worktree.

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
