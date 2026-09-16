# Phase 03: Cross-platform acceptance

## Goal

- Complete reviewable acceptance and documentation.

## Scope

- Full tests, fresh-export gate, phase documentation and final diff review.

## Non-goals

- New features and unrelated formatting.

## Affected files

- Phase documentation and validation follow-ups only.

## Implementation steps

- Run full pytest; inspect diff; commit implementation; run fresh-export gate against commits; record exact outcomes.

## Acceptance criteria

- Full and package-only tests pass; supported scenarios load from committed bytes; worktree is clean.

## Validation commands

- python -B -m pytest -q -p no:cacheprovider

## Manual smoke tests

- Run CLI help and archive acceptance; inspect git status.

## Rollback risks

- Public compatibility must remain; revert the phase commit rather than weakening checks.

## Progress

- Not started.

## Decision log

- No decisions recorded yet.

## Outcomes / Retrospective

- Not completed yet.
