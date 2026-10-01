# Phase 05: Automate matrix and distribution acceptance and document remaining gates.

## Goal

- Automate matrix and distribution acceptance and document remaining gates.

## Scope

- CI workflow, ZIP verifier, acceptance record and final regression.

## Non-goals

- No game formula changes, catalog regeneration, projection restructuring or external publication.

## Affected files

- CI workflow, ZIP verifier, acceptance record and final regression.

## Implementation steps

- Run full pytest/fresh export; isolated extracted ZIP synthetic workflow; configure Windows/Linux3.11-3.14; record actual Codex/ChatGPT evidence.

## Acceptance criteria

- All available checks pass; unavailable platform/ChatGPT/data rights checks remain explicitly pending.

## Validation commands

- python -m pytest -q
- python tools/verify_fresh_export.py

## Manual smoke tests

- Codex extracted ZIP scenario; ChatGPT if accessible, otherwise pending.

## Rollback risks

- Local success is not remote CI or ChatGPT evidence.

## Progress

- Planning complete; implementation in progress.

## Decision log

- Use user-approved beta contract; root integrates independent worker changes.

## Outcomes / Retrospective

- Pending implementation and verification; no completion claimed.


## Machine contract checks
Verify saveIdentity stability across copies and changes when save contents change, unknown player/version handling, and capabilities inventory consistency.
