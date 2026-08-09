# Phase 03: Add regression coverage and validate the latest Broken Earth save

## Goal

- Demonstrate the corrected output with focused tests, the complete test suite, and the latest Broken Earth save.

## Scope

- Run focused org-plan tests.
- Run all repository tests.
- Inspect current-save candidate diagnostics and verify previously rejected nationality orgs now have eligible councilors where appropriate.

## Non-goals

- Committing user save data or adding a machine-specific save fixture.

## Affected files

- `tests/test_org_plan.py`
- `dev-docs/plan/org-eligibility-output/*.md`

## Implementation steps

- Run the focused unittest module.
- Run full unittest discovery.
- Run `org-plan` against the parser's latest-save default and inspect representative nationality and owner-trait candidates.
- Record exact outcomes and remaining limitations.

## Acceptance criteria

- All focused and full tests pass.
- Latest-save output includes requirements and both eligible and ineligible councilor diagnostics.
- At least one nationality-gated market org is no longer falsely rejected solely because a prospective owner has a different homeland.

## Validation commands

- python -m unittest discover -s tests -v

## Manual smoke tests

- python tools\ti_save_parser.py org-plan --compact

## Rollback risks

- The smoke test depends on a local save and templates; automated correctness remains covered by synthetic tests.

## Progress

- Not started.

## Decision log

- No decisions recorded yet.

## Outcomes / Retrospective

- Not completed yet.
