# Phase 01: Establish extraction ownership and baseline

## Goal

- Establish extraction ownership and baseline

## Scope

- Plan documents and read-only source/graph inventory

## Non-goals

- Mechanics changes, output redesign, generator changes, performance claims.

## Affected files

- Plan documents and read-only source/graph inventory

## Implementation steps

- Inspect shared globals, cross-domain calls, mock sites, and baseline tests.

## Acceptance criteria

- Complete inventory and baseline before implementation.

## Validation commands

- python -B -m pytest -q -p no:cacheprovider

## Manual smoke tests

- Compare baseline public signatures and real-save command output; verify independent module imports.

## Rollback risks

- Cross-module references and test patch targets must follow ownership; revert the phase as a unit.

## Progress

- Complete. Reviewed current AST, existing graph navigation, cross-domain calls and facade mock sites.

## Decision log

- Existing graph is stale; use its relationships as navigation and current AST/source as authority.

## Outcomes / Retrospective

- Baseline full suite: 325 passed, 13 skipped, 45 subtests passed.
- Domain boundaries include separate research planning and base research; shared configuration and configured runtime adapters are explicitly distinguished.
- No mechanics or output changes are authorized by this refactor.
