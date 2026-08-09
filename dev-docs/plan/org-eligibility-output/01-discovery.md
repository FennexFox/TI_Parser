# Phase 01: Confirm authoritative nation-interest and owner-trait rules

## Goal

- Record the authoritative acquisition/assignment rules and the backward-compatible output contract before changing behavior.

## Scope

- Verify the installed game's `TIOrgState` nation-interest and owner-trait checks.
- Map those checks to save fields used by the parser.
- Define stable machine-readable candidate diagnostics.

## Non-goals

- Reimplementing technology, ideology, special faction-org, detention, or space-location acquisition checks.
- Changing org scoring, costs, or market candidate discovery.

## Affected files

- `dev-docs/plan/org-eligibility-output/*.md`

## Implementation steps

- Confirm `requiresNationality` maps to the org home region's nation.
- Confirm nation interest is satisfied by a faction control point or any faction councilor home nation.
- Confirm required/prohibited owner traits are evaluated per prospective councilor.
- Define `requirements`, `factionEligibility`, `eligibleCouncilors`, and per-councilor `ineligibleReasons` fields while preserving current candidate fields.

## Acceptance criteria

- The rule mapping and output shape are explicit enough to implement without inference.
- Non-goals prevent the patch from claiming full `IsEligibleForFaction` parity.

## Validation commands

- python -m unittest discover -s tests -v

## Manual smoke tests

- python tools\ti_save_parser.py org-plan --compact

## Rollback risks

- Documentation-only phase; rollback removes this plan directory.

## Progress

- Complete.

## Decision log

- Game nation interest is faction-scoped, not a direct org/councilor nationality equality test.
- Market presence continues to mean faction-visible; the new output diagnoses nation interest and owner-trait assignment eligibility.

## Outcomes / Retrospective

- Installed game logic and the latest Broken Earth save both demonstrate that the previous councilor-nationality comparison rejects valid market orgs.
