# Phase 03: Verification and cleanup

## Goal

- Prove recurring timing numerically and remove the obsolete continuous-renewal limitation.

## Scope

- Focused/full tests, catalog verification, real-save smoke, plan validation, documentation, and Graphify refresh.

## Non-goals

- No unrelated projection mechanics.

## Affected files

- Tests, docs, plan, generated artifacts, and Graphify outputs touched by this extension.

## Implementation steps

1. Cover cadence transitions, mean resolution offsets, repeated downtime, segment changes, and cost totals.
2. Run focused and full suites plus package verification.
3. Run a local-save smoke and refresh Graphify.

## Acceptance criteria

- Tests pass and catalog hashes match installed inputs.
- Output no longer says travel/failure are ignored.
- No fictional 14-day travel constant or user-supplied success probability remains.

## Validation commands

- All commands in the master plan plus strict plan validation and Graphify diagnostics.

## Manual smoke tests

- Compare no-advisor, current-advisor, and newly-selected-advisor plans across two phases.

## Rollback risks

- Generated artifacts must roll back with generator and runtime code.

## Progress

- Not started.

## Decision log

- No decisions recorded yet.

## Outcomes / Retrospective

- Not completed yet.
