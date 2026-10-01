# Phase 04: Build deterministic ZIP from committed allowlisted bytes.

## Goal

- Build deterministic ZIP from committed allowlisted bytes.

## Scope

- Builder/version, MIT LICENSE/data notice, distribution tests and docs.

## Non-goals

- No game formula changes, catalog regeneration, projection restructuring or external publication.

## Affected files

- Builder/version, MIT LICENSE/data notice, distribution tests and docs.

## Implementation steps

- Select explicit git ref; allowlist runtime assets; stable ZIP metadata and hash manifest; exclude private/developer artifacts.

## Acceptance criteria

- Same ref yields same ZIP; extracted runtime works; code license excludes game-derived data.

## Validation commands

- python -m pytest tests/test_beta_distribution.py -q

## Manual smoke tests

- Build committed ZIP and run --version/help outside checkout.

## Rollback risks

- No redistribution rights inferred; externally sharing data needs resolved permission.

## Progress

- Planning complete; implementation in progress.

## Decision log

- Use user-approved beta contract; root integrates independent worker changes.

## Outcomes / Retrospective

- Pending implementation and verification; no completion claimed.

